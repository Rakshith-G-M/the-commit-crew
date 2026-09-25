"""CampusIQ — M6 decision candidate engine (Part 3 of Decision Intelligence).

Converts the intelligence layer (M5) + forecasts (Part 1) + resource state
(Part 2) into *decision candidates* — rule-based, pre-recommendation actions.

This is deliberately NOT the final recommendation engine: it generates
candidates (problem + proposed action + evidence + constraints), it does not
optimise, sequence, or rank by cost. A separate optimisation/recommendation
pass is the next task (M7).

Location honesty
----------------
* Sensor anomaly/forecast/health candidates carry
  ``location_status: "UNKNOWN"`` whenever the M4 mapping is UNRESOLVED — we do
  NOT pretend to know the physical room.
* Space/allocation candidates are IFC-derived and carry
  ``location_status: "VERIFIED_BIM"`` (BIM is the authority for what a space
  is; it is not a statement about measured occupancy).

Availability honesty
--------------------
No occupancy timetable exists in the dataset trades, so availability is NOT
fabricated. The allocation functions accept an explicit ``availability`` input
(``{"space_id": bool}``, potentially time-stamped) and require it — when the
engine is run without an availability input the candidates flag
``availability_known: false`` and the allocation result notes that no
schedule was assumed.
"""

from __future__ import annotations

import json
import hashlib
import math
from typing import Any

from telemetry_config import DECISION

TASK = "M6-DECISION-ENGINE"
SCHEMA_VERSION = "campusiq.decision_candidates/v1"

PROBLEM_VENTILATION = {"co2"}
PROBLEM_AIR_QUALITY = {"pm2.5"}
PROBLEM_ENERGY = {"energy"}
PROBLEM_COMFORT = {"temperature", "humidity"}


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _n(v) -> int | None:
    f = _num(v)
    return None if f is None else int(f)


def _severity_for(n: int, bands: dict) -> str:
    if n >= bands["critical"]:
        return "CRITICAL"
    if n >= bands["high"]:
        return "HIGH"
    if n >= bands["medium"]:
        return "MEDIUM"
    return "LOW"


def _location_unknown():
    return {"status": "UNKNOWN", "space_id": None}


def _location_bim(space_id: str | None):
    return {"status": "VERIFIED_BIM", "space_id": space_id}


def _chan_by_sensor(profile: dict) -> dict[str, dict]:
    """Index channels by (sensor_id, measurement_type).

    A single sensor may carry several measurement types (temperature +
    humidity + ...); the M5 profile emits one channel per combination, so
    candidates must be generated per channel, not collapsed per sensor."""
    out: dict[str, dict] = {}
    for c in profile.get("channels", []):
        out[(c["sensor_id"], c.get("measurement_type"))] = c
    return out


def _mapping_by_sensor(mapping: dict) -> dict[str, dict]:
    return {m["sensor_id"]: m for m in mapping.get("mappings", [])}


def anomaly_candidates(profile: dict, cfg: dict) -> list[dict]:
    out = []
    for (sensor_id, _mt), ch in sorted(_chan_by_sensor(profile).items()):
        summary = ch.get("anomaly_summary") or {}
        n = summary.get("candidates_surviving") or 0
        if n <= 0:
            continue
        mt = ch.get("measurement_type")
        if mt in PROBLEM_VENTILATION:
            ptype, action = "VENTILATION", (
                "Investigate CO2 / occupancy conditions around this sensor; "
                "assess mechanical ventilation response."
            )
        elif mt in PROBLEM_AIR_QUALITY:
            ptype, action = "AIR_QUALITY", (
                "Inspect airborne particulate sources near this sensor; "
                "review filtration."
            )
        elif mt in PROBLEM_ENERGY:
            ptype, action = "ENERGY", (
                "Inspect energy-consuming systems and operating schedule "
                "associated with this meter."
            )
        elif mt in PROBLEM_COMFORT:
            ptype, action = "COMFORT", (
                "Inspect HVAC/conditioning response for thermal-comfort "
                "deviation at this sensor."
            )
        else:
            ptype, action = "GENERIC", "Review channel conditions around this sensor."
        _gt = ch.get("measurement_type", "unknown")
        out.append(
            {
                "candidate_type": "ANOMALY",
                "problem_type": ptype,
                "source": "M5_TELEMETRY_ANOMALIES",
                "severity": _severity_for(n, cfg["survivor_severity"]),
                "affected_entity": {"type": "sensor", "sensor_id": sensor_id},
                "proposed_action": action,
                "reason": f"{n} anomaly readings survived contextual screening ({_gt}).",
                "evidence": {
                    "surviving_candidates": n,
                    "measurement_type": _gt,
                    "unit": ch.get("unit"),
                    "baseline_recommended": (ch.get("baseline") or {}).get("recommended_baseline"),
                },
                "constraints": [
                    "Sensor location is UNRESOLVED (M4); the physical room is unknown."
                ],
                "location_status": "UNKNOWN",
                "location": _location_unknown(),
                "confidence": cfg["confidence"]["anomaly"],
            }
        )
    return out


def health_candidates(health: dict, cfg: dict) -> list[dict]:
    out = []
    devices = health.get("devices") or []
    devices_sorted = sorted(devices, key=lambda d: d["sensor_id"])
    for d in devices_sorted:
        issues = d.get("issues") or []
        health_issues = [_issue_name(i) for i in issues]
        if not health_issues:
            continue
        out.append(
            {
                "candidate_type": "MAINTENANCE",
                "problem_type": "MAINTENANCE",
                "source": "M5_SENSOR_HEALTH",
                "severity": _health_severity(d, cfg),
                "affected_entity": {"type": "sensor", "sensor_id": d["sensor_id"]},
                "proposed_action": (
                    "Schedule sensor maintenance / calibration check for "
                    f"{d['sensor_id']} (issues: {', '.join(health_issues)})."
                ),
                "reason": f"Health status {d.get('health_status')} with {len(health_issues)} issue type(s).",
                "evidence": {
                    "health_status": d.get("health_status"),
                    "issue_types": health_issues,
                    "anomaly_candidates": d.get("anomaly_candidates"),
                    "location": d.get("location"),
                },
                "constraints": [
                    "Location cannot be targeted without a verified sensor->space mapping."
                ],
                "location_status": "UNKNOWN",
                "location": _location_unknown(),
                "confidence": cfg["confidence"]["health"],
            }
        )
    return out


def _issue_name(i: dict) -> str:
    return i.get("type") or "UNSPECIFIED"


def _health_severity(device: dict, cfg: dict) -> str:
    has_critical = any(
        (i.get("max_severity") or "") == "CRITICAL" for i in device.get("issues", [])
    )
    if has_critical:
        return "CRITICAL"
    has_high = any(
        (i.get("max_severity") or "") == "HIGH" for i in device.get("issues", [])
    )
    if has_high:
        return "HIGH"
    has_med = any(
        (i.get("max_severity") or "") == "MEDIUM" for i in device.get("issues", [])
    )
    return "MEDIUM" if has_med else "LOW"


def forecast_candidates(forecasts: dict, cfg: dict) -> list[dict]:
    out = []
    forecast_records = forecasts.get("records", forecasts.get("forecasts", []))
    forecast_records_sorted = sorted(
        forecast_records, key=lambda r: (r.get("sensor_id", ""), r.get("horizon_hours", 0))
    )
    seen: dict[str, dict] = {}
    for r in forecast_records_sorted:
        if "skip_reason" in r:
            continue
        sensor_id = r.get("sensor_id")
        prev = seen.get(sensor_id)
        if prev is None:
            location = r.get("location") or _location_unknown()
            prev = seen[sensor_id] = {
                "max_co2": -1.0,
                "max_temp_dev": -1.0,
                "location_status": location.get("location_status", "UNKNOWN"),
                "space_id": location.get("space_id"),
            }
        _mt = r.get("measurement_type")
        if _mt == "co2" and r.get("predicted_value") is not None:
            prev["max_co2"] = max(prev["max_co2"], r["predicted_value"])
        if _mt in ("temperature",) and r.get("predicted_value") and r.get("baseline_value"):
            prev["max_temp_dev"] = max(prev["max_temp_dev"], abs(r["predicted_value"] - r["baseline_value"]))

    for sensor_id in sorted(seen):
        prev = seen[sensor_id]
        if prev["max_co2"] >= cfg["co2_investigate_threshold_ppm"]:
            out.append(
                {
                    "candidate_type": "DEMAND",
                    "problem_type": "DEMAND_VENTILATION",
                    "source": "M6_FORECAST",
                    "severity": "HIGH" if prev["max_co2"] >= cfg["co2_demand_threshold_ppm"] else "MEDIUM",
                    "affected_entity": {"type": "sensor", "sensor_id": sensor_id},
                    "proposed_action": (
                        "Forecast CO2 exceeds the ventilation threshold; investigate "
                        "occupancy demand and pollutant sources, and pre-plan "
                        "responses (ventilation or relocation)."
                    ),
                    "reason": f"Forecast CO2 up to {prev['max_co2']:.0f} ppm at sensor.",
                    "evidence": {"max_forecast_co2_ppm": round(prev["max_co2"], 2),
                                 "threshold_ppm": cfg["co2_investigate_threshold_ppm"],
                                 "horizons_hours": forecasts.get("forecast", {}).get("horizons_hours")},
                    "constraints": [
                        "No timetable; demand is a forecast, not a confirmed booking."
                    ],
                    "location_status": prev["location_status"],
                    "location": {"status": prev["location_status"], "space_id": prev["space_id"]},
                    "confidence": cfg["confidence"]["demand"],
                }
            )
        if prev["max_temp_dev"] >= cfg["temperature_demand_delta_c"]:
            out.append(
                {
                    "candidate_type": "DEMAND",
                    "problem_type": "DEMAND_COMFORT",
                    "source": "M6_FORECAST",
                    "severity": "LOW" if prev["max_temp_dev"] < 3 else "MEDIUM",
                    "affected_entity": {"type": "sensor", "sensor_id": sensor_id},
                    "proposed_action": (
                        "Forecast temperature deviates from the seasonal baseline; "
                        "review expected HVAC/conditioning response."
                    ),
                    "reason": f"Forecast temperature deviation up to {prev['max_temp_dev']:.2f} C.",
                    "evidence": {
                        "max_temp_delta_c": round(prev["max_temp_dev"], 2),
                        "threshold_delta_c": cfg["temperature_demand_delta_c"],
                    },
                    "constraints": [
                        "No timetable; demand is a forecast, not a confirmed booking."
                    ],
                    "location_status": prev["location_status"],
                    "location": {"status": prev["location_status"], "space_id": prev["space_id"]},
                    "confidence": cfg["confidence"]["demand"],
                }
            )
    return out


def _resource_state_by_space(rs: dict) -> dict[str, dict]:
    return {s["space_id"]: s for s in rs.get("spaces", [])}


def _space_capacity(space: dict) -> float | None:
    cap = _num(space.get("capacity_occupants")) or _num(space.get("occupancy", {}).get("capacity_occupants"))
    if cap is None:
        occ = space.get("occupancy") or {}
        cap = _num(occ.get("capacity_occupants"))
    return cap


def allocate(
    required_capacity: float | None,
    spaces: list[dict],
    availability: dict | None = None,
    equipment: list[str] | None = None,
    cfg: dict | None = None,
) -> dict:
    """Return spaces satisfying capacity / availability / equipment constraints.

    ``availability``: optional ``{"space_id": bool}`` (or a per-space dict with
    ``available`` keys). If omitted, availability is unknown (not assumed) and
    the result notes it. ``equipment``: list of required space features, e.g.
    ``["lighting", "power"]``, resolved against declared design fields.
    """
    cfg = cfg or DECISION
    availability = availability or {}
    equipment = equipment or []

    suitable = []
    excluded = []
    for space in sorted(spaces, key=lambda s: s["space_id"]):
        reasons = []
        cap = _space_capacity(space)
        if required_capacity is not None:
            if cap is None:
                reasons.append("capacity_unknown")
            elif cap < required_capacity:
                reasons.append(f"capacity_{cap}<{required_capacity}")

        space_id = space["space_id"]
        availability_known = space_id in availability
        if availability:
            if not availability.get(space_id, False):
                reasons.append("not_available" if availability_known else "availability_not_declared")

        missing_verified_eq = [e for e in equipment if _check_equipment_status(space, e) == "VERIFIED_MISSING"]
        unverified_eq = [e for e in equipment if _check_equipment_status(space, e) == "UNVERIFIED"]
        if missing_verified_eq:
            reasons.append("equipment_missing:" + ",".join(missing_verified_eq))

        record = {
            "space_id": space_id,
            "capacity_occupants": cap,
            "availability_known": availability_known,
            "equipment_status": "NOT_VERIFIED" if unverified_eq else ("VERIFIED" if equipment else "NONE_REQUESTED"),
            "unverified_equipment": unverified_eq,
            "reason": sorted(reasons) if reasons else None,
        }
        if reasons:
            excluded.append(record)
        else:
            suitable.append(record)

    return {
        "satisfied": bool(suitable),
        "suitable": suitable,
        "excluded": excluded,
        "availability_known": bool(availability),
        "availability_note": (
            "Availability supplied by caller; none fabricated." if availability
            else "No availability input supplied; availability must be an explicit external input."
        ),
    }


def _check_equipment_status(space: dict, feature: str) -> str:
    """Check whether equipment feature is verified present, verified missing, or unverified in dataset."""
    if feature in space or feature in ("lighting", "power"):
        fld = space.get(feature)
        if isinstance(fld, dict):
            v = fld.get("value")
            if isinstance(v, dict):
                v = v.get("value")
            num_v = _num(v)
            if num_v is not None and num_v > 0:
                return "VERIFIED_PRESENT"
            return "VERIFIED_MISSING"
        elif fld is not None:
            num_v = _num(fld)
            if num_v is not None and num_v > 0:
                return "VERIFIED_PRESENT"
            return "VERIFIED_MISSING"
        else:
            return "VERIFIED_MISSING"
    return "UNVERIFIED"


def _has_equipment(space: dict, feature: str) -> bool:
    return _check_equipment_status(space, feature) == "VERIFIED_PRESENT"


def allocation_candidates(requests: list[dict], spaces: list[dict], availability: dict | None = None, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or DECISION
    out = []
    for req in sorted(requests, key=lambda r: r.get("request_id", "")):
        req_cap = _num(req.get("required_capacity"))
        req_eq = req.get("equipment") or []
        result = allocate(req_cap, spaces, availability=availability, equipment=req_eq, cfg=cfg)
        space_id = (result["suitable"][0]["space_id"] if result["suitable"] else None)
        out.append(
            {
                "candidate_type": "ALLOCATION",
                "problem_type": "ALLOCATION",
                "source": "M6_RESOURCE_ALLOCATION",
                "severity": "LOW",
                "affected_entity": {"type": "space", "space_id": space_id},
                "proposed_action": (
                    "Satisfied." if result["satisfied"]
                    else "No single space satisfies the request; evaluate grouped/combination allocation."
                ),
                "reason": f"Request {req.get('request_id')} capacity {req_cap}.",
                "evidence": {
                    "request_id": req.get("request_id"),
                    "required_capacity": req_cap,
                    "suitable_count": len(result["suitable"]),
                    "suitable_spaces": [s["space_id"] for s in result["suitable"]],
                    "excluded_count": len(result["excluded"]),
                },
                "constraints": [
                    "BIM provides capacity/geometry only; availability is explicit input."
                ],
                "location_status": "VERIFIED_BIM",
                "location": _location_bim(space_id),
                "confidence": cfg["confidence"]["allocation"],
            }
        )
    return out


def build_decision_candidates(
    profile: dict,
    health: dict,
    forecasts: dict,
    mapping: dict,
    spaces: list[dict],
    requests: list[dict] | None = None,
    cfg: dict | None = None,
) -> dict:
    cfg = cfg or DECISION
    records = []
    records.extend(anomaly_candidates(profile, cfg))
    records.extend(health_candidates(health, cfg))
    records.extend(forecast_candidates(forecasts, cfg))
    if requests:
        records.extend(allocation_candidates(requests, spaces, cfg=cfg))

    records.sort(
        key=lambda r: (
            r["source"],
            r["candidate_type"],
            r["location_status"],
            r["affected_entity"].get("sensor_id") or r["affected_entity"].get("space_id") or "",
        )
    )
    for i, r in enumerate(records, 1):
        r["candidate_id"] = f"DC-{i:04d}"

    counts = {}
    for r in records:
        counts[r["candidate_type"]] = counts.get(r["candidate_type"], 0) + 1
    sev = {}
    for r in records:
        sev[r["severity"]] = sev.get(r["severity"], 0) + 1
    loc = {}
    for r in records:
        loc[r["location_status"]] = loc.get(r["location_status"], 0) + 1

    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "confidence_note": (
            "Rule-based heuristic confidence (0-1), not a statistical "
            "probability or confidence interval."
        ),
        "location_caveat": (
            "Sensor anomaly/health/demand candidates report location_status "
            "'UNKNOWN' when M4 mapping is UNRESOLVED. Only IFC/BIM-derived "
            "space candidates use 'VERIFIED_BIM'."
        ),
        "summary": {
            "total": len(records),
            "by_candidate_type": counts,
            "by_severity": sev,
            "by_location_status": loc,
            "requests_processed": len(requests or []),
        },
        "records": records,
    }
