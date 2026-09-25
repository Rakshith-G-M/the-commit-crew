# CampusIQ — Decision Intelligence (M6)

Connects M5 telemetry intelligence with campus BIM resources to form 
the first decision-oriented layer: short-horizon forecasting, a
canonical campus resource state, and a rule-based decision candidate
engine. This is the foundation for the recommendation engine and the
front-end.

## 1. Short-horizon forecasting

- Channels forecast: **65** / 69 (channels_skipped: **4**)
- Skipped reasons: {"cumulative_register": 4}
- Horizons: [1, 6, 24] hours (configurable)
- Method: rolling mean (0.4 weight) blended with the M5 time-aware (dow x hour) seasonal baseline median; day-of-week + hour-of-day seasonality via the
168-bucket M5 baseline; recent behaviour via the last-96-sample rolling window.
- Forecast timestamps are the channel's last reading + horizon (no fabricated 'now').
- Confidence intervals: none claimed. Records expose `coverage` metadata and a labelled
seasonal spread estimate (`MAD/0.6745`) but `confidence_interval_95` is always null.
- Reference: last observed timestamp per channel: `2025-06-30T23:45:54`.

## 2. Campus resource state

- Spaces: **115** (occupiable **115**), storeys **4** (registry 5), buildings 1.
- Totals: area **3485.983514** m2, volume **15841.48114** m3, design capacity **871.495877** occupants.
- Per space: geometry, named occupancy (capacity, area/occupant, max density), lighting and power
design loads, HVAC-related design flows/loads, conditioned zone, design metrics and full BIM
properties. Storey aggregates: 2. korrus: 18 spaces, +Kelder: 44 spaces, 1. korrus: 29 spaces, 3. korrus: 24 spaces.

### BIM design vs measurements

All values are BIM **design/specification** or derived design metrics, explicitly labelled `metric_origin: BIM_DESIGN` and `is_measured: false` in every field group. Design/specification
values are never presented as actual consumption. `measurements.measured_energy_consumption` and
`measured_consumption_available` are null/false campus-wide (no per-space meter is linked).

### Availability

No occupancy timetable exists in the dataset. `availability.present: false` — availability is an
explicit external input to allocation, never a fabricated schedule.

## 3. Decision candidates

- Total: **98** candidates.
- By candidate type: {"MAINTENANCE": 36, "ANOMALY": 62}.
- By severity: {"MEDIUM": 22, "HIGH": 46, "CRITICAL": 23, "LOW": 7}.
- By location status: {"UNKNOWN": 98}.
- External allocation requests processed: 0.

Candidate types emitted:

- **ANOMALY / VENTILATION** — persistent CO2 anomalies → investigate ventilation / occupancy.
- **ANOMALY / ENERGY** — energy deviation → inspect energy-consuming systems / operating schedule.
- **ANOMALY / COMFORT** — temperature/humidity deviation → inspect HVAC control. 
- **ANOMALY / AIR_QUALITY** — pm2.5 deviation → inspect IAQ sources / filtration.
- **MAINTENANCE** — sensor-health issues (constant value, long gap, irregular sampling) → schedule
  maintenance / calibration.
- **DEMAND** — forecast CO2/comfort deviating from seasonal baseline → pre-plan ventilation or
  relocation. Only generated where the forecast exceeds config thresholds.

### Location honesty

Sensor anomaly/health/demand candidates carry `location_status: UNKNOWN` because the M4 mapping is
**UNRESOLVED** for all 36 sensors — the system does not pretend to know the physical room. Only
IFC/BIM-derived space/allocation candidates use `location_status: VERIFIED_BIM`.

## 4. Resource allocation foundation

A generic `allocate()` filter (capacity, explicit availability, equipment) returns all spaces that
satisfy the constraints plus the excluded set with reasons; it performs filtering, not
optimization. `EXTERNAL capacity requests` drive ALLOCATION candidates — none are fabricated, and
an availability dict must be supplied by the caller; absent a schedule, availability is flagged
unknown rather than assumed.

Demonstration (no-op on real requests): allocation candidates require a requests input and are
only generated there, so `requests_processed: 0` means none were invented.

## 5. Tests

- M6 test module: `tests/test_decision_intelligence.py` — **15 tests**: forecast generation,
insufficient-history skip, energy cumulative-register skip, exact forecast timestamps,
deterministic forecasting, 115-space resource-state extraction, BIM design-vs-measured
distinction, storey aggregates, anomaly→candidate conversion, UNKNOWN location propagation,
VERIFIED_BIM allocation, capacity filtering, equipment filtering, no fabricated schedules,
byte-deterministic end-to-end outputs.
- Full suite across M1–M6 passes: **100 passed (M6 added 15)**.

## 6. Runtime

- Full M6 pipeline: ~0.2s on the full M5 outputs (read-only; no data rewrite).

## 7. Limitations

- Forecasts are univariate (per channel) and anchored to the last observed reading; no forecast
  beyond the horizon grid, no multivariate/cross-space coupling.
- No confidence intervals are computed (coverage + spread estimate only).
- Design values are NOT consumption; energy registers were skipped for raw-value forecasting
  (cumulative, not periodic).
- No sensor location is resolved, so room-level decisions are deferred to the lighting of a
  confirmed mapping.
- Decision candidates are rule-based; ranking/optimization is intentionally deferred.

## 8. Recommended next task

- **M7**: recommendation engine — rank decision candidates by cost/benefit using design
  loads and forecast deviation, surface allocation options for confirmed mappings, expose a
  decision API for the front-end.

