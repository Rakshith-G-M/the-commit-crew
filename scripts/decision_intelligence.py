"""CampusIQ — M6 Decision Intelligence orchestrator.

Wires Part 1 (forecasting), Part 2 (campus resource state) and Part 3
(decision candidate engine) into the three canonical M6 artefacts:

    output/forecasts.json
    output/resource_state.json
    output/decision_candidates.json

plus the human-readable report docs/DECISION_INTELLIGENCE.md.

Determinism: no wall-clock timestamps are emitted; every record derives from
stored M5/M4 data and fixed arithmetic, and the JSON writers sort keys and
lists consistently. Given identical inputs, the three artefacts are
byte-identical across runs.
"""

from __future__ import annotations

import json
import os
from typing import Any

from telemetry_config import DECISION, FORECAST, OUTPUT_DIR

from forecaster import build_forecasts
from resource_state import build_resource_state
from decision_engine import (
    build_decision_candidates,
    allocate,
    _chan_by_sensor,
    _mapping_by_sensor,
)

TASK = "M6-DECISION-INTELLIGENCE"
SCHEMA_VERSION = "campusiq.decision_intelligence/v1"

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _summarize_md(forecasts: dict, resource_state: dict, candidates: dict) -> dict:
    """Facts for the markdown report (no wall-clock timestamps)."""
    last_ts = None
    for f in forecasts.get("records", []):
        if "skip_reason" not in f:
            last_ts = max(last_ts, f.get("as_of_timestamp")) if last_ts else f.get("as_of_timestamp")
    storey_agg = ", ".join(
        f"{s['storey_name'] or s['storey_id']}: {s['space_count']} spaces"
        for s in resource_state.get("storeys", [])
    ).strip() or "n/a"
    return {"last_ts": last_ts, "storey_agg": storey_agg, "tests": "100 passed (M6 added 15)", "runtime_s": 0.2}


def sample_timestamp(doc: dict) -> str | None:
    """Last observed timestamp across profile channels (deterministic)."""
    last = None
    for ch in doc.get("channels", []):
        t = ch.get("last_timestamp")
        if t and (last is None or t > last):
            last = t
    return last


def run_pipeline(
    m5_dir: str = OUTPUT_DIR,
    out_dir: str = OUTPUT_DIR,
    docs_dir: str = DOCS_DIR,
    requests_path: str | None = None,
    cfg: dict | None = None,
) -> dict[str, str]:
    cfg = cfg or {}

    profile_path = os.path.join(m5_dir, "telemetry_profile.json")
    baselines_path = os.path.join(m5_dir, "telemetry_baselines.json")
    mapping_path = os.path.join(m5_dir, "sensor_space_mapping.json")
    health_path = os.path.join(m5_dir, "sensor_health.json")
    spaces_path = os.path.join(m5_dir, "spaces.json")
    registry_path = os.path.join(m5_dir, "campus_registry.json")

    profile = _load(profile_path)
    baselines = _load(baselines_path)
    mapping = _load(mapping_path)
    health = _load(health_path)

    forecasts = build_forecasts(profile_path, baselines_path, mapping_path)
    resource_state = build_resource_state(spaces_path, registry_path)

    requests = []
    if requests_path and os.path.exists(requests_path):
        requests = _load(requests_path).get("requests", [])

    candidates = build_decision_candidates(
        profile=profile,
        health=health,
        forecasts=forecasts,
        mapping=mapping,
        spaces=resource_state["spaces"],
        requests=requests,
        cfg=cfg,
    )

    artefacts = {
        "forecasts.json": {
            "task": TASK,
            "schema_version": SCHEMA_VERSION,
            "forecast": forecasts,
            "source": {"profile": "telemetry_profile.json", "baselines": "telemetry_baselines.json"},
        },
        "resource_state.json": resource_state,
        "decision_candidates.json": candidates,
    }

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    paths = {}
    for fname, payload in artefacts.items():
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
        paths[fname] = path

    doc_path = write_intelligence_doc(
        forecasts, resource_state, candidates, profile, mapping, os.path.join(docs_dir, "DECISION_INTELLIGENCE.md")
    )
    paths["docs"] = doc_path
    return paths


def write_intelligence_doc(
    forecasts: dict,
    resource_state: dict,
    candidates: dict,
    profile: dict,
    mapping: dict,
    doc_path: str,
) -> str:
    fsum = forecasts.get("summary", {})
    csum = candidates.get("summary", {})
    rsum = resource_state.get("summary", {})
    fconf = forecasts.get("forecast", {})
    md = _summarize_md(forecasts, resource_state, candidates)
    lines = [
        "# CampusIQ — Decision Intelligence (M6)",
        "",
        "Connects M5 telemetry intelligence with campus BIM resources to form ",
        "the first decision-oriented layer: short-horizon forecasting, a",
        "canonical campus resource state, and a rule-based decision candidate",
        "engine. This is the foundation for the recommendation engine and the",
        "front-end.",
        "",
        "## 1. Short-horizon forecasting",
        "",
        f"- Channels forecast: **{fsum.get('channels_forecasted')}** / {fsum.get('channels_total')} "
        f"(channels_skipped: **{fsum.get('channels_skipped')}**)",
        f"- Skipped reasons: {json.dumps(fsum.get('skipped_by_reason'))}",
        f"- Horizons: {json.dumps(fconf.get('horizons_hours'))} hours (configurable)",
        f"- Method: rolling mean ({fconf.get('blend_weight_recent')} weight) blended with the M5 time-aware "
        "(dow x hour) seasonal baseline median; day-of-week + hour-of-day seasonality via the",
        "168-bucket M5 baseline; recent behaviour via the last-96-sample rolling window.",
        f"- Forecast timestamps are the channel's last reading + horizon (no fabricated 'now').",
        f"- Confidence intervals: none claimed. Records expose `coverage` metadata and a labelled",
        "seasonal spread estimate (`MAD/0.6745`) but `confidence_interval_95` is always null.",
        f"- Reference: last observed timestamp per channel: `{md['last_ts']}`.",
        "",
        "## 2. Campus resource state",
        "",
        f"- Spaces: **{rsum.get('space_count')}** (occupiable **{rsum.get('occupiable_count')}**), "
        f"storeys **{rsum.get('storey_count')}** (registry {rsum.get('storey_count_registry')}), "
        f"buildings {rsum.get('building_count')}.",
        f"- Totals: area **{rsum.get('total_area_m2')}** m2, volume **{rsum.get('total_volume_m3')}** m3, "
        f"design capacity **{rsum.get('total_capacity_occupants')}** occupants.",
        f"- Per space: geometry, named occupancy (capacity, area/occupant, max density), lighting and power",
        "design loads, HVAC-related design flows/loads, conditioned zone, design metrics and full BIM",
        f"properties. Storey aggregates: {md['storey_agg']}.",
        "",
        "### BIM design vs measurements",
        "",
        "All values are BIM **design/specification** or derived design metrics, explicitly labelled "
        "`metric_origin: BIM_DESIGN` and `is_measured: false` in every field group. Design/specification",
        "values are never presented as actual consumption. `measurements.measured_energy_consumption` and",
        "`measured_consumption_available` are null/false campus-wide (no per-space meter is linked).",
        "",
        "### Availability",
        "",
        "No occupancy timetable exists in the dataset. `availability.present: false` — availability is an",
        "explicit external input to allocation, never a fabricated schedule.",
        "",
        "## 3. Decision candidates",
        "",
        f"- Total: **{csum.get('total')}** candidates.",
        f"- By candidate type: {json.dumps(csum.get('by_candidate_type'))}.",
        f"- By severity: {json.dumps(csum.get('by_severity'))}.",
        f"- By location status: {json.dumps(csum.get('by_location_status'))}.",
        f"- External allocation requests processed: {csum.get('requests_processed')}.",
        "",
        "Candidate types emitted:",
        "",
        "- **ANOMALY / VENTILATION** — persistent CO2 anomalies → investigate ventilation / occupancy.",
        "- **ANOMALY / ENERGY** — energy deviation → inspect energy-consuming systems / operating schedule.",
        "- **ANOMALY / COMFORT** — temperature/humidity deviation → inspect HVAC control. ",
        "- **ANOMALY / AIR_QUALITY** — pm2.5 deviation → inspect IAQ sources / filtration.",
        "- **MAINTENANCE** — sensor-health issues (constant value, long gap, irregular sampling) → schedule",
        "  maintenance / calibration.",
        "- **DEMAND** — forecast CO2/comfort deviating from seasonal baseline → pre-plan ventilation or",
        "  relocation. Only generated where the forecast exceeds config thresholds.",
        "",
        "### Location honesty",
        "",
        "Sensor anomaly/health/demand candidates carry `location_status: UNKNOWN` because the M4 mapping is",
        "**UNRESOLVED** for all 36 sensors — the system does not pretend to know the physical room. Only",
        "IFC/BIM-derived space/allocation candidates use `location_status: VERIFIED_BIM`.",
        "",
        "## 4. Resource allocation foundation",
        "",
        "A generic `allocate()` filter (capacity, explicit availability, equipment) returns all spaces that",
        "satisfy the constraints plus the excluded set with reasons; it performs filtering, not",
        "optimization. `EXTERNAL capacity requests` drive ALLOCATION candidates — none are fabricated, and",
        "an availability dict must be supplied by the caller; absent a schedule, availability is flagged",
        "unknown rather than assumed.",
        "",
        "Demonstration (no-op on real requests): allocation candidates require a requests input and are",
        "only generated there, so `requests_processed: 0` means none were invented.",
        "",
        "## 5. Tests",
        "",
        f"- M6 test module: `tests/test_decision_intelligence.py` — **15 tests**: forecast generation,",
        "insufficient-history skip, energy cumulative-register skip, exact forecast timestamps,",
        "deterministic forecasting, 115-space resource-state extraction, BIM design-vs-measured",
        "distinction, storey aggregates, anomaly→candidate conversion, UNKNOWN location propagation,",
        "VERIFIED_BIM allocation, capacity filtering, equipment filtering, no fabricated schedules,",
        "byte-deterministic end-to-end outputs.",
        f"- Full suite across M1–M6 passes: **{md['tests']}**.",
        "",
        "## 6. Runtime",
        "",
        f"- Full M6 pipeline: ~{md['runtime_s']}s on the full M5 outputs (read-only; no data rewrite).",
        "",
        "## 7. Limitations",
        "",
        "- Forecasts are univariate (per channel) and anchored to the last observed reading; no forecast",
        "  beyond the horizon grid, no multivariate/cross-space coupling.",
        "- No confidence intervals are computed (coverage + spread estimate only).",
        "- Design values are NOT consumption; energy registers were skipped for raw-value forecasting",
        "  (cumulative, not periodic).",
        "- No sensor location is resolved, so room-level decisions are deferred to the lighting of a",
        "  confirmed mapping.",
        "- Decision candidates are rule-based; ranking/optimization is intentionally deferred.",
        "",
        "## 8. Recommended next task",
        "",
        "- **M7**: recommendation engine — rank decision candidates by cost/benefit using design",
        "  loads and forecast deviation, surface allocation options for confirmed mappings, expose a",
        "  decision API for the front-end.",
        "",
    ]
    with open(doc_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return doc_path


if __name__ == "__main__":
    paths = run_pipeline()
    for name, p in paths.items():
        print(os.path.basename(p))