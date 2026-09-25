# Telemetry Intelligence Engine — TalTech Campus (M5)

Task: `M5-TELEMETRY-INTELLIGENCE-ENGINE`  ·  Schema: `campusiq.telemetry_intelligence/v1`

## 1. Objective and scope
Transform the 69 sensor channels / 1,390,297 readings from "values" into
*intelligence*: profiling, data quality, baselines, features, statistical
anomaly detection, sensor health, and a machine-readable summary — all
deterministic and read-only with respect to the raw CSVs. This layer is the
input for M6 (forecasting), M7 (recommendations) and M9 (what-if).

## 2. Data
- **69 channels**, **36 devices** (co2: 7 channel(s), energy: 4 channel(s), humidity: 26 channel(s), pm2.5: 3 channel(s), temperature: 29 channel(s))
- **1,390,297 readings** from `DS3_TalTech_V4.ifc` / `Taltech.zip`.
- Units seen: `C`, `%`, `ppm`, `µg/m3`, `kWh`.
- Energy meters are **cumulative kWh registers** (monotone staircases); they
  are delta-transformed to a per-calendar-day kWh/day curve before analysis.

## 3. Pipeline
`RAW -> NORMALIZED -> FEATURES -> BASELINE -> ANOMALY -> INTELLIGENCE`
Single read of every CSV (`telemetry_profile.analyze_all`); the in-memory
analysis dicts feed all five writers — no second pass, no raw duplication.

## 4. Profiling and time normalization
- Timestamps normalized to `%Y-%m-%dT%H:%M:%S` and sorted; duplicate
  timestamps counted; inter-sample intervals profiled (median/max/CV).
- All 69 channels show irregular sampling (interval CV >= 0.25) with bursts
  and multi-hour gaps — a property of the source dataset.

## 5. Data quality engine
Every reading is classified with a quality flag. Totals across the dataset:

| Flag | Count |
|------|-------:|
| VALID | 1390297 |
| MISSING | 0 |
| DUPLICATE | 0 |
| OUT_OF_RANGE | 0 |
| TIME_GAP (intervals > 1.5x median) | 65777 |
| SUSPECT | 2890 |

`0` channel(s) contain duplicate timestamps;
`69` channel(s) contain time gaps.

## 6. Baselines
Three baseline families are computed per channel:
- **global** — full-history Gaussian (`mean`/`median`/`std`/`MAD`).
- **rolling** — tail-anchored `96`-sample mean/std.
- **time_aware** — hour-of-day × day-of-week expected values (recommended for
  cyclic building data; captures the occupancy/weather rhythm).

`69/69`
channels have sufficient history
(>= 14 days and >= 336
samples). Recommended baseline distribution:
  - time_aware_hour_of_day: 69


## 7. Features
Per channel: statistics (mean/median/std/min/max, percentiles 1..99, CV),
rate-of-change, recent windows (last 96 samples / last 7 days), hour-of-day
peak/trough and workday-vs-night delta, and energy daily-delta estimates.
See `output/telemetry_features.json`.

## 8. Anomaly detection
Detection is **context-first and robust**: per reading the primary baseline is
hour-of-day (if the bucket is well-populated), else rolling, else global. The
time-of-day expectation is a **robust median** with MAD/0.6745 spread, so a
single extreme reading cannot contaminate the very bucket statistics used to
find it. Modified z-scores (z = 0.6745·|v−median|/MAD) and global z-scores are
computed as secondary signals and reported on every record. A candidate must
exceed a statistical score and survive the **persistence rule** (run of
consecutive candidates >= 2), be an extreme
isolated outlier (score >= 6.0), a decisive
robust outlier (MAD z >= 6.0), or be an
impossible physical value (outside configured limits).

Result: **37359 anomaly candidates** detected
(15937 detail records persisted; detail is capped at
500 per channel).

- By severity: CRITICAL=3168, HIGH=1493, LOW=7790, MEDIUM=3486
- By category: ENVIRONMENTAL=15909, RESOURCE=28
- By method: time_aware=15937
- By measurement type: co2=3174, energy=28, humidity=3254, pm2.5=1500, temperature=7981
- Data-quality vs environmental/resource anomalies are separated by an
  explicit `category` field; energy anomalies are labelled `RESOURCE`.

Top anomalies:
  - `2025-02-10T17:31:43` sensor `08e2d921` pm2.5=123.0µg/m3 (expected 3.0µg/m3, score 26.98, time_aware, CRITICAL)
  - `2025-02-10T17:41:43` sensor `08e2d921` pm2.5=123.0µg/m3 (expected 3.0µg/m3, score 26.98, time_aware, CRITICAL)
  - `2025-02-10T19:31:43` sensor `08e2d921` pm2.5=123.0µg/m3 (expected 4.0µg/m3, score 20.066375, time_aware, CRITICAL)
  - `2025-02-10T19:41:43` sensor `08e2d921` pm2.5=123.0µg/m3 (expected 4.0µg/m3, score 20.066375, time_aware, CRITICAL)
  - `2025-01-17T23:00:00` sensor `4565853e` temperature=18.333334C (expected 22.573C, score 77.287966, time_aware, CRITICAL)

## 9. Multivariate / contextual awareness
Every anomaly and health record carries the M4 visitor-located context
(`space_id`, `location_status`, `location_verified`, `mapping_status`,
`mapping_confidence`) resolved from
`output/sensor_space_mapping.json`. In the current dataset all 36
mapped sensors are **UNRESOLVED**, hence `location_status = UNKNOWN_LOCATION`
and `space_id = null` on all anomalies; the machinery transparently upgrades
once confirmed/provisional mappings exist. Telemetry is **never** used as
physical-location evidence.

## 10. Sensor health
Per-device rubric in `output/sensor_health.json`:
- **HEALTHY** — only LOW-severity irregularities.
- **DEGRADED** — HIGH issue, or MEDIUM `CONSTANT_VALUE`/`LONG_GAP`/
  `IMPOSSIBLE_VALUES`, or >5% missing/duplicates.
- **FAILED** — zero valid readings.

Distribution: DEGRADED=36.
Top issue types: CONSTANT_VALUE=30, IRREGULAR_SAMPLING=36, LONG_GAP=36.

## 11. Intelligence summary
`output/telemetry_intelligence_summary.json` aggregates the five outputs into
one machine-readable object: dataset totals and quality, anomaly totals by
severity/category/method/type, baseline coverage, energy estimate
(total median kWh/day 2191.464), sensor
health distribution, and location-awareness state.

## 12. Known limitations
- Thresholds are **configuration, not TalTech ground truth**; they are
  intentionally conservative and tunable in `telemetry_config.py`.
- The detector is univariate-per-channel; cross-channel correlations are
  deliberately out of scope for M5 (contextual linkage layer only).
- Cumulative energy meters have volatile day-to-day deltas; the derived
  kWh/day estimate is coarse and summed only as an upper bound.
- Anomaly detail records per channel are capped; totals are exact.

## 13. Outputs and determinism
Files (all under `output/`): `telemetry_profile.json`,
`telemetry_baselines.json`, `telemetry_features.json`, `anomalies.json`,
`sensor_health.json`, `telemetry_intelligence_summary.json`.
Every writer sorts its output; no timestamps are generated; thresholds are
fixed → byte-identical output across runs.
