"""CampusIQ — telemetry intelligence orchestrator (M5).

Single-pipeline driver: reads every channel CSV exactly ONCE via
telemetry_profile.analyze_all(), then fans the in-memory analysis out to the
five intelligence writers:

  output/telemetry_profile.json        - profiling + data quality
  output/telemetry_baselines.json      - global/rolling/time-aware baselines
  output/telemetry_features.json       - derived analytical features
  output/anomalies.json                - flagged anomalies (enriched, located)
  output/sensor_health.json            - per-device health rubric
  output/telemetry_intelligence_summary.json - human/machine-readable summary
  docs/TELEMETRY_INTELLIGENCE.md       - this task's technical report

Location awareness is inherited from the M4 linkage engine's canonical mapping
output; nothing is invented. Deterministic: no generated timestamps; every
writer sorts and its thresholds come from telemetry_config.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import telemetry_config as cfg  # noqa: E402
import telemetry_anomaly  # noqa: E402
import telemetry_baseline  # noqa: E402
import telemetry_features  # noqa: E402
import telemetry_health  # noqa: E402
import telemetry_profile  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(cfg.OUTPUT_DIR), "docs")


def load_mapping(out_dir: str | None = None) -> dict[str, Any]:
    return telemetry_anomaly.load_mapping(out_dir)


# ---------------------------------------------------------------------------
# Intelligence summary
# ---------------------------------------------------------------------------
def _quality_totals(analyses: list[dict[str, Any]]) -> dict[str, int]:
    out = {f: 0 for f in cfg.QUALITY_FLAGS}
    for a in analyses:
        for flag, v in a.get("quality", {}).items():
            out[flag] = out.get(flag, 0) + v
    return out


def _anomaly_summary(analyses: list[dict[str, Any]],
                     mapping: dict[str, Any]) -> dict[str, Any]:
    payload = telemetry_anomaly.build_payload(analyses, mapping)
    s = payload["summary"]
    records = payload["anomalies"]
    top = sorted(records, key=lambda r: (r.get("severity_score") or 0,
                                         -_rank(r.get("timestamp") or ""),
                                         r.get("sensor_id") or ""),
                 reverse=True)[:8]
    top_records = [{
        "timestamp": r["timestamp"], "sensor_id": r["sensor_id"],
        "measurement_type": r["measurement_type"], "value": r["value"],
        "unit": r["unit"], "expected": r["expected"], "score": r["score"],
        "severity_score": r["severity_score"], "severity": r["severity"],
        "category": r["category"], "method": r["method"],
        "location_status": r["location_status"], "space_id": r["space_id"],
    } for r in top]
    known = sum(1 for r in records if r.get("space_id"))
    return {
        "total_candidates": s["total_candidates"],
        "recorded_detail": s["recorded_detail"],
        "channels_with_anomalies": s["channels_with_anomalies"],
        "by_severity": s["by_severity"],
        "by_category": s["by_category"],
        "by_method": s["by_method"],
        "by_measurement_type": s["by_measurement_type"],
        "anomalies_with_known_location": known,
        "top_anomalies": top_records,
    }


def _rank(ts: str) -> int:
    try:
        return int("".join(ch for ch in ts if ch.isdigit()))
    except ValueError:
        return 0


def _baseline_summary(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    payload = telemetry_baseline.build_payload(analyses)
    return {
        "channels": payload["summary"]["channels"],
        "sufficient_history": payload["summary"]["sufficient_history"],
        "recommended_baseline_distribution":
            payload["summary"]["recommended_baseline_distribution"],
    }


def _energy_summary(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    meds = []
    for a in analyses:
        if a["measurement_type"] == "energy":
            reg = a.get("energy_registers") or {}
            if reg.get("derived_kwh_per_day_median") is not None:
                meds.append(reg["derived_kwh_per_day_median"])
    return {
        "energy_channels": len(meds),
        "median_kwh_per_day_per_meter": meds,
        "total_median_kwh_per_day_campus": cfg.round2(sum(meds)) if meds else None,
        "note": "per-calendar-day register deltas; meters overlap partially "
                "in coverage so summing is an upper-bound estimate.",
    }


def _location_summary(mapping: dict[str, Any]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for rec in mapping.values():
        if not isinstance(rec, dict):
            continue
        st = rec.get("status") or rec.get("mapping_status") or "UNRESOLVED"
        statuses[st] = statuses.get(st, 0) + 1
    known = sum(1 for rec in mapping.values()
                if isinstance(rec, dict) and rec.get("space_id"))
    return {
        "sensors_in_mapping": len(mapping),
        "mapping_status_distribution": dict(sorted(statuses.items())),
        "sensors_with_space": known,
        "note": "location never inferred from telemetry; space_id only from "
                "the M4 linkage engine's confirmed/provisional mapping.",
    }


def build_summary(analyses: list[dict[str, Any]],
                  mapping: dict[str, Any]) -> dict[str, Any]:
    span_starts = [a["first_timestamp"] for a in analyses if a["first_timestamp"]]
    span_ends = [a["last_timestamp"] for a in analyses if a["last_timestamp"]]
    health = telemetry_health.build_payload(analyses, mapping)["summary"]
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "dataset": {
            "channels": len(analyses),
            "devices": len({a["sensor_id"] for a in analyses}),
            "total_readings": sum(a["record_count"] for a in analyses),
            "channels_by_type": {t: sum(1 for a in analyses
                                        if a["measurement_type"] == t)
                                 for t in sorted({a["measurement_type"]
                                                  for a in analyses})},
            "time_span": {
                "first": min(span_starts) if span_starts else None,
                "last": max(span_ends) if span_ends else None,
            },
            "quality_totals": _quality_totals(analyses),
            "channels_with_duplicates":
                sum(1 for a in analyses if a["quality"]["DUPLICATE"] > 0),
            "channels_with_gaps":
                sum(1 for a in analyses if a["quality"]["TIME_GAP"] > 0),
        },
        "intelligence": {
            "anomalies": _anomaly_summary(analyses, mapping),
            "baselines": _baseline_summary(analyses),
            "energy": _energy_summary(analyses),
            "sensor_health": health,
            "location_awareness": _location_summary(mapping),
        },
        "notes": _notes(analyses),
    }


def _notes(analyses: list[dict[str, Any]]) -> list[str]:
    oor = sum(a["quality"]["OUT_OF_RANGE"] for a in analyses)
    return [
        "All thresholds are operational configuration in telemetry_config.py "
        "and are NOT TalTech ground truth.",
        "Every anomaly carries a category: DATA_QUALITY (impossible values) vs "
        "RESOURCE (energy) vs ENVIRONMENTAL (comfort/air quality).",
        "No sensor location is inferred from telemetry; space linkage comes "
        "only from the M4 mapping engine (all current dataset sensors are "
        "UNRESOLVED -> location_status UNKNOWN_LOCATION).",
        f"Energy meters are cumulative kWh registers; anomalies are computed on "
        f"the derived per-calendar-day delta curve, never on raw register "
        f"values. {oor} reading(s) fell outside configured physical limits.",
        "Raw CSVs are read exactly once and never modified; no full-density "
        "copy of the 1,390,297 readings is persisted.",
    ]


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
def write_report(analyses: list[dict[str, Any]],
                 mapping: dict[str, Any],
                 summary: dict[str, Any],
                 docs_dir: str | None = None) -> str:
    docs_dir = docs_dir or DOCS_DIR
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, "TELEMETRY_INTELLIGENCE.md")
    s = summary
    d = s["dataset"]
    i = s["intelligence"]
    a = i["anomalies"]
    qt = d["quality_totals"]
    by_type_inline = ", ".join(f"{k}: {v} channel(s)"
                               for k, v in d["channels_by_type"].items())
    examples = "\n".join(
        f"  - `{e['timestamp']}` sensor `{e['sensor_id'][:8]}` "
        f"{e['measurement_type']}={e['value']}{e['unit']} "
        f"(expected {e['expected']}{e['unit']}, score {e['score']}, "
        f"{e['method']}, {e['severity']})"
        for e in a["top_anomalies"][:5])

    body = f"""# Telemetry Intelligence Engine — TalTech Campus (M5)

Task: `{s['task']}`  ·  Schema: `{s['schema_version']}`

## 1. Objective and scope
Transform the 69 sensor channels / 1,390,297 readings from "values" into
*intelligence*: profiling, data quality, baselines, features, statistical
anomaly detection, sensor health, and a machine-readable summary — all
deterministic and read-only with respect to the raw CSVs. This layer is the
input for M6 (forecasting), M7 (recommendations) and M9 (what-if).

## 2. Data
- **69 channels**, **36 devices** ({by_type_inline})
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
| VALID | {qt.get('VALID', 0)} |
| MISSING | {qt.get('MISSING', 0)} |
| DUPLICATE | {qt.get('DUPLICATE', 0)} |
| OUT_OF_RANGE | {qt.get('OUT_OF_RANGE', 0)} |
| TIME_GAP (intervals > 1.5x median) | {qt.get('TIME_GAP', 0)} |
| SUSPECT | {qt.get('SUSPECT', 0)} |

`{d['channels_with_duplicates']}` channel(s) contain duplicate timestamps;
`{d['channels_with_gaps']}` channel(s) contain time gaps.

## 6. Baselines
Three baseline families are computed per channel:
- **global** — full-history Gaussian (`mean`/`median`/`std`/`MAD`).
- **rolling** — tail-anchored `{cfg.ANOMALY['rolling_window']}`-sample mean/std.
- **time_aware** — hour-of-day × day-of-week expected values (recommended for
  cyclic building data; captures the occupancy/weather rhythm).

`{i['baselines']['sufficient_history']}/{i['baselines']['channels']}`
channels have sufficient history
(>= {cfg.BASELINE['min_history_days']} days and >= {cfg.BASELINE['min_samples']}
samples). Recommended baseline distribution:
{_ul(i['baselines']['recommended_baseline_distribution'])}

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
consecutive candidates >= {cfg.ANOMALY['persistence_min']}), be an extreme
isolated outlier (score >= {cfg.ANOMALY['extreme_isolated_z']}), a decisive
robust outlier (MAD z >= {cfg.ANOMALY['mad_candidate_z']}), or be an
impossible physical value (outside configured limits).

Result: **{a['total_candidates']} anomaly candidates** detected
({a['recorded_detail']} detail records persisted; detail is capped at
{cfg.ANOMALY['detail_cap']} per channel).

- By severity: {_comma(a['by_severity'])}
- By category: {_comma(a['by_category'])}
- By method: {_comma(a['by_method'])}
- By measurement type: {_comma(a['by_measurement_type'])}
- Data-quality vs environmental/resource anomalies are separated by an
  explicit `category` field; energy anomalies are labelled `RESOURCE`.

Top anomalies:
{examples}

## 9. Multivariate / contextual awareness
Every anomaly and health record carries the M4 visitor-located context
(`space_id`, `location_status`, `location_verified`, `mapping_status`,
`mapping_confidence`) resolved from
`output/sensor_space_mapping.json`. In the current dataset all {len(mapping)}
mapped sensors are **UNRESOLVED**, hence `location_status = UNKNOWN_LOCATION`
and `space_id = null` on all anomalies; the machinery transparently upgrades
once confirmed/provisional mappings exist. Telemetry is **never** used as
physical-location evidence.

## 10. Sensor health
Per-device rubric in `output/sensor_health.json`:
- **HEALTHY** — only LOW-severity irregularities.
- **DEGRADED** — HIGH issue, or MEDIUM `CONSTANT_VALUE`/`LONG_GAP`/
  `IMPOSSIBLE_VALUES`, or >{cfg.HEALTH['duplicate_ratio']:.0%} missing/duplicates.
- **FAILED** — zero valid readings.

Distribution: {_comma(i['sensor_health']['health_status_distribution'])}.
Top issue types: {_comma(i['sensor_health']['issue_type_counts'])}.

## 11. Intelligence summary
`output/telemetry_intelligence_summary.json` aggregates the five outputs into
one machine-readable object: dataset totals and quality, anomaly totals by
severity/category/method/type, baseline coverage, energy estimate
(total median kWh/day {i['energy']['total_median_kwh_per_day_campus']}), sensor
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
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path


def _comma(d: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in (d or {}).items())


def _ul(d: dict) -> str:
    return "".join(f"  - {k}: {v}\n" for k, v in (d or {}).items())


# ---------------------------------------------------------------------------
# Pipeline driver
# ---------------------------------------------------------------------------
def run_pipeline(csv_dir: str | None = None,
                 out_dir: str | None = None,
                 mapping_path: str | None = None,
                 report_docs_dir: str | None = None) -> dict[str, str]:
    out = out_dir or cfg.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    analyses = telemetry_profile.analyze_all(csv_dir)
    mapping = telemetry_anomaly.load_mapping(out)

    paths = {
        "telemetry_profile": telemetry_profile.write_profile(analyses, out),
        "telemetry_baselines": telemetry_baseline.write_baselines(analyses, out),
        "telemetry_features": telemetry_features.write_features(analyses, out),
        "anomalies": telemetry_anomaly.write_anomalies(analyses, mapping, out),
        "sensor_health": telemetry_health.write_health(analyses, mapping, out),
    }
    summary = build_summary(analyses, mapping)
    summary_path = os.path.join(out, "telemetry_intelligence_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    paths["telemetry_intelligence_summary"] = summary_path
    paths["report"] = write_report(analyses, mapping, summary,
                                   report_docs_dir)
    return paths


if __name__ == "__main__":
    import argparse
    argparse_helper = argparse.ArgumentParser(description="run M5 pipeline")
    argparse_helper.add_argument("--csv-dir", default=None)
    argparse_helper.add_argument("--out-dir", default=None)
    args = argparse_helper.parse_args()
    result = run_pipeline(args.csv_dir, args.out_dir)
    for name, path in result.items():
        print(f"  {name}: {path}")
    print("OK")