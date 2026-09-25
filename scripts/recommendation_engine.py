"""CampusIQ — M7 recommendation engine + product API core.

Converts M6 *decision candidates* into ranked, explainable, actionable
*recommendations* and answers the product questions:

    WHAT IS HAPPENING?       problem_type / affected_entity / reason
    WHY DOES IT MATTER?      expected_impact (classified, never fabricated)
    WHAT CAN THE ADMIN DO?   recommended_action / constraints
    WHY THIS ACTION?         ranking.priority_score + factors + explanation
    WHAT EVIDENCE SUPPORTS?  evidence_chain + evidence
    WHAT INFORMATION IS MISSING?  data_quality / constraints / location

Everything here is usable WITHOUT HTTP; the FastAPI layer (api_app.py) is a
thin projection over these deterministic pure functions.

Honesty guarantees (mirror M4/M6):
  * Sensor-derived recommendations report location_status UNKNOWN_LOCATION
    until M4 confirms a mapping. No "Room X has high CO2" is fabricated.
  * No measured savings are invented: impact claims are classified
    CALCULATED / ESTIMATED / QUALITATIVE / UNKNOWN, energy savings are
    UNKNOWN unless a verified intervention model exists.
  * Allocation evaluation acts ONLY on an explicit request + availability;
    no timetable is fabricated.

Determinism: no wall-clock timestamps are emitted into the artefacts and all
outputs are key-sorted and stably ordered, so identical inputs yield
byte-identical outputs.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

from telemetry_config import DECISION, OUTPUT_DIR, RECOMMENDATION, RESOURCE_STATE
from decision_engine import allocate, _has_equipment, _space_capacity, _check_equipment_status

TASK = "M7-RECOMMENDATION-ENGINE"
SCHEMA_VERSION = "campusiq.recommendations/v1"
ALLOCATION_EVAL_SCHEMA_VERSION = "campusiq.allocation_evaluation/v1"

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

# Recommendation categories (Part 3).
CATEGORY_ENVIRONMENTAL = "ENVIRONMENTAL"
CATEGORY_ENERGY = "ENERGY"
CATEGORY_SENSOR_HEALTH = "SENSOR_HEALTH"
CATEGORY_ALLOCATION = "ALLOCATION"

# Canonical allocation-exclusion reasons (Part 7).
REASON_CAPACITY = "insufficient capacity"
REASON_AVAILABILITY = "unavailable"
REASON_AVAILABILITY_UNDECLARED = "availability not declared"
REASON_EQUIPMENT = "equipment mismatch"
REASON_OCCUPIABLE = "not occupiable"
REASON_CAPACITY_UNKNOWN = "capacity unknown"
REASON_OTHER = "other explicit constraint"


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def category_for(candidate: dict) -> str:
    ctype = candidate.get("candidate_type")
    ptype = candidate.get("problem_type")
    if ctype == "ALLOCATION":
        return CATEGORY_ALLOCATION
    if ctype == "MAINTENANCE":
        return CATEGORY_SENSOR_HEALTH
    if ptype == "ENERGY":
        return CATEGORY_ENERGY
    return CATEGORY_ENVIRONMENTAL


def _sensor_id(candidate: dict) -> str | None:
    return (candidate.get("affected_entity") or {}).get("sensor_id")


def _space_id_of(candidate: dict) -> str | None:
    return (candidate.get("affected_entity") or {}).get("space_id")


def _health_by_sensor(health: dict) -> dict[str, dict]:
    return {d.get("sensor_id"): d for d in health.get("devices", [])}


def _forecast_by_channel(forecasts: dict) -> dict[tuple[str, str], list[dict]]:
    """Index non-skipped forecast records by (sensor_id, measurement_type)."""
    out: dict[tuple[str, str], list[dict]] = {}
    for r in forecasts.get("forecast", {}).get("records", []):
        if "skip_reason" in r:
            continue
        key = (r.get("sensor_id"), r.get("measurement_type"))
        out.setdefault(key, []).append(r)
    return out


def _profile_by_channel(profile: dict) -> dict[tuple[str, str], dict]:
    return {
        (c.get("sensor_id"), c.get("measurement_type")): c
        for c in profile.get("channels", [])
    }


def _location_for(candidate: dict) -> dict:
    """Canonical location semantics (M4 is the single source of truth)."""
    status = candidate.get("location_status")
    loc = candidate.get("location") or {}
    if status == "VERIFIED_BIM":
        return {
            "status": "VERIFIED_BIM",
            "space_id": loc.get("space_id") or _space_id_of(candidate),
            "location_verified": True,
            "note": "Location is BIM/IFC-derived (design placement), not measured occupancy.",
        }
    return {
        "status": "UNKNOWN_LOCATION",
        "space_id": None,
        "location_verified": False,
        "note": (
            "M4 sensor->space mapping is UNRESOLVED; the physical room is "
            "unknown and is not asserted."
        ),
    }


# --------------------------------------------------------------------------
# Part 2 — transparent ranking
# --------------------------------------------------------------------------

def _severity_factor(candidate: dict, cfg: dict) -> float:
    palette = cfg["severity_numeric"]
    return palette.get(candidate.get("severity"), palette["LOW"])


def _persistence_factor(candidate: dict, cfg: dict) -> float:
    ctype = candidate.get("candidate_type")
    ev = candidate.get("evidence") or {}
    if ctype == "ANOMALY":
        n = _num(ev.get("surviving_candidates")) or 0
        ref = cfg["persistence_reference"]
        return _clip(math.log10(1 + max(0, n)) / math.log10(1 + ref))
    if ctype == "MAINTENANCE":
        n = _num(ev.get("anomaly_candidates")) or 0
        ref = cfg["persistence_reference"]
        return _clip(0.4 + 0.6 * math.log10(1 + max(0, n)) / math.log10(1 + ref))
    if ctype == "DEMAND":
        return 0.7  # proactive forecast-based demand
    return 0.5  # ALLOCATION: a single explicit request, not a persistent signal


def _deviation_factor(candidate: dict, forecast_records: list[dict] | None, cfg: dict) -> tuple[float, str]:
    ev = candidate.get("evidence") or {}
    ctype = candidate.get("candidate_type")
    if ctype == "DEMAND":
        if ev.get("max_forecast_co2_ppm") is not None:
            thr = ev.get("threshold_ppm") or cfg.get("co2_investigate_threshold_ppm", 900.0)
            return _clip(_num(ev["max_forecast_co2_ppm"]) / max(1.0, thr)), "forecast CO2 relative to threshold"
        if ev.get("max_temp_delta_c") is not None:
            ref = cfg.get("temperature_demand_delta_c", 2.0) * 2.5
            return _clip(_num(ev["max_temp_delta_c"]) / max(0.1, ref)), "forecast temperature delta C"
    if forecast_records:
        f24 = sorted(forecast_records, key=lambda r: -_num(r.get("horizon_hours")))[0]
        pred = _num(f24.get("predicted_value"))
        base = _num(f24.get("baseline_value"))
        ev2 = f24.get("evidence") or {}
        thr = _num(ev2.get("threshold_ppm")) if ev2 else None
        mt = f24.get("measurement_type")
        if pred is not None and base is not None:
            delta = abs(pred - base)
            if mt == "co2" and thr:
                return _clip(delta / max(1.0, thr)), f"24h forecast {mt} absolute delta {delta:.2f} vs threshold"
            sc = {"co2": 500.0, "humidity": 25.0, "temperature": 5.0, "pm2.5": 25.0}.get(mt, 25.0)
            return _clip(delta / sc), f"24h forecast {mt} absolute delta {delta:.2f} vs scale {sc}"
    # fall back to the anomaly severity as a documented deviation proxy
    sev = _severity_factor(candidate, cfg)
    return sev, "deviation proxy from candidate severity (precise deviation is in anomalies.json)"


def _resource_factor(candidate: dict) -> float:
    if candidate.get("location_status") == "VERIFIED_BIM" or _space_id_of(candidate):
        return 1.0
    if category_for(candidate) == CATEGORY_ALLOCATION:
        return 1.0
    return 0.3  # sensor-derived: BIM placement unresolved


def _forecast_factor(candidate: dict) -> float:
    if candidate.get("candidate_type") == "DEMAND":
        return 1.0
    if candidate.get("source") == "M5_TELEMETRY_ANOMALIES":
        return 0.5  # reactive; forecast layer could support proactive action
    return 0.2


def _confidence_factor(candidate: dict) -> float:
    v = _num(candidate.get("confidence"))
    return _clip(0.2 if v is None else v)


def _quality_factor(sensor_id: str | None, health_by_sensor: dict) -> float:
    if not sensor_id:
        return 1.0  # BIM-derived entities: design geometry, not sampled
    dev = health_by_sensor.get(sensor_id)
    if not dev:
        return RECOMMENDATION["neutral_data_quality"]
    cov = _num(dev.get("coverage_fraction"))
    if cov is None:
        miss = _num(dev.get("missing_ratio"))
        cov = 1.0 - (miss if miss is not None else 0.0)
    return _clip(cov)


def rank_candidate(
    candidate: dict,
    forecast_records: list[dict] | None,
    health_by_sensor: dict,
    cfg: dict,
) -> dict:
    """Compute the explainable priority score and its contributing factors."""
    weights = cfg["weights"]
    severity = _severity_factor(candidate, cfg)
    persistence = _persistence_factor(candidate, cfg)
    deviation, dev_basis = _deviation_factor(candidate, forecast_records, cfg)
    forecast_relevance = _forecast_factor(candidate)
    resource_relevance = _resource_factor(candidate)
    actionability = _actionability_factor(candidate)
    confidence = _confidence_factor(candidate)
    quality = _quality_factor(_sensor_id(candidate), health_by_sensor)

    factors = {
        "severity": round(severity, 4),
        "persistence": round(persistence, 4),
        "deviation": round(deviation, 4),
        "forecast_relevance": round(forecast_relevance, 4),
        "resource_relevance": round(resource_relevance, 4),
        "actionability": round(actionability, 4),
        "confidence": round(confidence, 4),
        "data_quality": round(quality, 4),
    }
    score = sum(weights[k] * factors[k] for k in weights)
    score = round(_clip(score), 4)
    derivations = {
        "severity": f"candidate severity label -> numeric palette",
        "persistence": (
            "log-normal survivor/issue count (reference %s)"
            % cfg["persistence_reference"]
        ),
        "deviation": dev_basis,
        "forecast_relevance": (
            "DEMAND=1.0; anomaly=0.5 (reactive); others=0.2"
        ),
        "resource_relevance": (
            "1.0 for BIM/space/allocation, else 0.3 (placement unresolved)"
        ),
        "actionability": "see actionability basis",
        "confidence": "rule-based candidate confidence (heuristic, not CI)",
        "data_quality": (
            "sensor health coverage fraction; neutral 0.5 when absent"
        ),
    }
    explanation = (
        "priority_score = " + " + ".join(
            f"{weights[k]:.2f}*{factors[k]:.2f}" for k in weights
        ) + f" = {score:.4f} "
        f"({cfg['formula_version']}). Decision-support ranking, not a claim "
        "that this action is objectively best."
    )
    return {
        "priority_score": score,
        "priority": priority_label(score),
        "weights": {k: v for k, v in weights.items()},
        "factors": factors,
        "factor_basis": derivations,
        "formula_version": cfg["formula_version"],
        "explanation": explanation,
    }


def _actionability_factor(candidate: dict) -> float:
    category = category_for(candidate)
    if category == CATEGORY_ALLOCATION:
        return 1.0
    if candidate.get("candidate_type") == "MAINTENANCE":
        return 0.8  # maintenance is schedulable without resolved location
    if candidate.get("candidate_type") == "DEMAND":
        return 0.5
    return 0.35  # anomaly: actionable only after location/context confirmed


def priority_label(score: float) -> str:
    from telemetry_config import priority_label_for as _plf
    return _plf(score)


# --------------------------------------------------------------------------
# Part 4 — evidence chain
# --------------------------------------------------------------------------

def evidence_chain(candidate: dict, forecast_records: list[dict] | None, req: dict | None = None) -> list[dict]:
    """Build a frontend-displayable chain from real stored evidence."""
    ctype = candidate.get("candidate_type")
    ev = candidate.get("evidence") or {}
    chain = []
    if ctype == "ANOMALY":
        chain.append({"step": "ANOMALY", "entity": "sensor", "value": _sensor_id(candidate),
                      "note": "contextually-screened anomaly signal (M5)"})
        chain.append({"step": "MEASUREMENT", "entity": ev.get("measurement_type"),
                      "value": {"unit": ev.get("unit")}, "note": "measurement family flagged"})
        chain.append({"step": "HISTORICAL_BASELINE", "entity": ev.get("baseline_recommended"),
                      "value": None, "note": "M5 time-aware baseline method"})
        n = _num(ev.get("surviving_candidates"))
        chain.append({"step": "DEVIATION", "entity": ev.get("measurement_type"),
                      "value": {"surviving_candidates": n},
                      "note": "deviation deemed significant after contextual screening"})
        chain.append({"step": "PERSISTENCE", "entity": ev.get("measurement_type"),
                      "value": n, "note": "number of survivor readings sustaining the signal"})
    elif ctype == "MAINTENANCE":
        chain.append({"step": "SENSOR_HEALTH", "entity": _sensor_id(candidate),
                      "value": ev.get("health_status"), "note": "M5 device health status"})
        chain.append({"step": "HEALTH_ISSUE", "entity": _sensor_id(candidate),
                      "value": ev.get("issue_types"), "note": "issue types detected"})
        chain.append({"step": "OBSERVED", "entity": _sensor_id(candidate),
                      "value": {"anomaly_candidates": ev.get("anomaly_candidates")},
                      "note": "context from sensors with anomalies"})
    elif ctype == "DEMAND":
        chain.append({"step": "FORECAST", "entity": ev.get("measurement_type", "co2"),
                      "value": {"max_forecast_co2_ppm": ev.get("max_forecast_co2_ppm"),
                                "max_temp_delta_c": ev.get("max_temp_delta_c")},
                      "note": "M6 short-horizon forecast (1h/6h/24h)"})
        chain.append({"step": "HISTORICAL_BASELINE", "entity": ev.get("measurement_type", "co2"),
                      "value": {"threshold_ppm": ev.get("threshold_ppm"),
                                "threshold_delta_c": ev.get("threshold_delta_c")},
                      "note": "config threshold vs forecast"})
        chain.append({"step": "DEVIATION", "entity": ev.get("measurement_type", "co2"),
                      "value": None, "note": "forecast exceeds configured demand threshold"})
    else:  # ALLOCATION
        chain.append({"step": "REQUEST", "entity": (req or {}).get("request_id"),
                      "value": {"required_capacity": (req or {}).get("required_capacity"),
                                "equipment": (req or {}).get("equipment")},
                      "note": "explicit external capacity request (no fabricated schedule)"})
        chain.append({"step": "CAPACITY_CONSTRAINT", "entity": "space",
                      "value": {"suitable_count": ev.get("suitable_count"),
                                "qualified": ev.get("suitable_spaces")},
                      "note": "BIM design capacity >= required capacity"})
    chain.append({"step": "CANDIDATE", "entity": candidate.get("candidate_id"),
                  "value": None, "note": f"decision candidate ({candidate.get('candidate_type')})"})
    chain.append({"step": "RECOMMENDATION", "entity": None,
                  "value": None, "note": "this ranked, explainable recommendation"})
    return chain


# --------------------------------------------------------------------------
# Part 5 — impact estimation framework
# --------------------------------------------------------------------------

def estimate_impact(candidate: dict, resource_space: dict | None, cfg: dict) -> list[dict]:
    """Classify impact claims; never turn a qualitative assumption into a number."""
    category = category_for(candidate)
    ctype = candidate.get("candidate_type")
    slots = []
    if category == CATEGORY_ENERGY or ctype == "ANOMALY" and candidate.get("problem_type") == "ENERGY":
        slots.append({
            "type": "resource_usage_change",
            "value": None,
            "unit": "kWh",
            "status": "UNKNOWN",
            "method": None,
            "reason": (
                "No verified intervention model exists; design loads are "
                "BIM_DESIGN and measured consumption is unavailable. A numeric "
                "saving is not estimated."
            ),
        })
        slots.append({
            "type": "operational_priority",
            "value": None,
            "unit": None,
            "status": "QUALITATIVE",
            "method": "priority_score",
            "reason": "Raise priority of energy-behaviour inspection before any schedule change.",
        })
    elif category == CATEGORY_ENVIRONMENTAL:
        slots.append({
            "type": "risk_reduction",
            "value": None,
            "unit": None,
            "status": "QUALITATIVE",
            "method": "priority_score",
            "reason": (
                "Risk reduction is qualitative: no verified exposure/intervention "
                "response model exists for this space."
            ),
        })
        slots.append({
            "type": "operational_priority",
            "value": None,
            "unit": None,
            "status": "QUALITATIVE",
            "method": "priority_score",
            "reason": "Investigate conditions; confirm location before targeted action.",
        })
    elif category == CATEGORY_SENSOR_HEALTH:
        slots.append({
            "type": "data_quality_improvement",
            "value": None,
            "unit": None,
            "status": "QUALITATIVE",
            "method": "health_issues",
            "reason": (
                "Restoring measurements improves observability; the effect on "
                "operations is not quantified here."
            ),
        })
    else:  # ALLOCATION
        cap = _space_capacity(resource_space) if resource_space else None
        slots.append({
            "type": "capacity_suitability",
            "value": cap,
            "unit": "occupants",
            "status": "CALCULATED" if cap is not None else "UNKNOWN",
            "method": "BIM design capacity (area/occupant) >= required capacity",
            "reason": "Qualification is measured against BIM design capacity, not occupancy.",
        })
        slots.append({
            "type": "operational_priority",
            "value": None,
            "unit": None,
            "status": "QUALITATIVE",
            "method": "priority_score",
            "reason": "Allocation options are actionable once availability is supplied.",
        })
    return slots


# --------------------------------------------------------------------------
# Part 7 — allocation evaluation (explicit requests only)
# --------------------------------------------------------------------------

def _occupiable(space: dict) -> bool:
    occ = space.get("occupancy") or {}
    v = occ.get("occupiable")
    if v is not None:
        return bool(v)
    return True


def _canonical_reason(raw_reason: str) -> str:
    if raw_reason is None:
        return REASON_OTHER
    if raw_reason.startswith("capacity_unknown"):
        return REASON_CAPACITY_UNKNOWN
    if raw_reason.startswith("capacity_"):
        return REASON_CAPACITY
    if raw_reason == "not_available":
        return REASON_AVAILABILITY
    if raw_reason == "availability_not_declared":
        return REASON_AVAILABILITY_UNDECLARED
    if raw_reason.startswith("equipment_missing"):
        return REASON_EQUIPMENT + ":" + raw_reason.split(":", 1)[1]
    return REASON_OTHER


def evaluate_allocation(
    required_capacity: float | int,
    spaces: list[dict],
    equipment: list[str] | None = None,
    availability: dict | None = None,
    request_id: str | None = None,
    cfg: dict | None = None,
) -> dict:
    """Evaluate ONE explicit request; never fabricates availability.

    Capacity is evaluated as a hard BIM constraint. Unverified equipment inventory
    (missing from dataset) is flagged as unverified without excluding capacity-suitable rooms.
    """
    cfg = cfg or RECOMMENDATION
    equipment = equipment or []
    availability = availability or {}
    req_cap = _num(required_capacity)
    if req_cap is None or req_cap < 0:
        raise ValueError("required_capacity must be a non-negative number")

    qualified = []
    excluded = []
    for space in sorted(spaces, key=lambda s: s["space_id"]):
        reasons = []
        cap = _space_capacity(space)
        if req_cap is not None:
            if cap is None:
                reasons.append(REASON_CAPACITY_UNKNOWN)
            elif cap < req_cap:
                reasons.append(REASON_CAPACITY)
        if not _occupiable(space):
            reasons.append(REASON_OCCUPIABLE)
        space_id = space["space_id"]
        declared = space_id in availability
        if availability and not availability.get(space_id, False):
            reasons.append(REASON_AVAILABILITY if declared else REASON_AVAILABILITY_UNDECLARED)

        missing_verified = [e for e in equipment if _check_equipment_status(space, e) == "VERIFIED_MISSING"]
        unverified_items = [e for e in equipment if _check_equipment_status(space, e) == "UNVERIFIED"]
        verified_items = [e for e in equipment if _check_equipment_status(space, e) == "VERIFIED_PRESENT"]

        if missing_verified:
            reasons.append(REASON_EQUIPMENT + ":" + ",".join(missing_verified))

        eq_status = "NOT_VERIFIED" if unverified_items else ("VERIFIED" if equipment else "NONE_REQUESTED")

        record = {
            "space_id": space_id,
            "capacity_occupants": cap,
            "occupiable": _occupiable(space),
            "availability_known": declared,
            "capacity_suitable": True if (cap is not None and cap >= req_cap) else False,
            "equipment_status": eq_status,
            "unverified_equipment": unverified_items,
        }
        if reasons:
            record["reason_excluded"] = sorted(set(reasons))
            excluded.append(record)
        else:
            reason_qual = [
                "BIM design capacity sufficient",
                "space occupiable",
            ]
            if availability:
                reason_qual.append("explicit availability satisfied")
            if verified_items:
                reason_qual.append(f"verified equipment present: {', '.join(verified_items)}")
            if unverified_items:
                reason_qual.append(f"equipment compatibility unverified ({', '.join(unverified_items)} inventory unavailable in dataset)")
            record["reason_qualified"] = reason_qual
            qualified.append(record)

    eq_summary_note = (
        "Equipment inventory is not available in the current dataset. Rooms are evaluated by BIM capacity; equipment compatibility is reported as unverified."
        if equipment else "No equipment requested."
    )
    avail_summary_note = (
        "Availability supplied by caller; none fabricated." if availability
        else "Scheduling availability is not provided by the current dataset."
    )

    summary_counts = {
        "total_evaluated": len(spaces),
        "capacity_matches": len(qualified),
        "equipment_verified": len([s for s in qualified if s.get("equipment_status") == "VERIFIED"]),
        "unverified_equipment_matches": len([s for s in qualified if s.get("equipment_status") == "NOT_VERIFIED"]),
        "excluded": len(excluded),
    }

    return {
        "schema_version": ALLOCATION_EVAL_SCHEMA_VERSION,
        "request_id": request_id,
        "required_capacity": req_cap,
        "equipment": equipment,
        "equipment_status": {
            "status": "NOT_VERIFIED" if equipment else "NONE_REQUESTED",
            "verified_items": list({e for s in qualified for e in equipment if _check_equipment_status(s, e) == "VERIFIED_PRESENT"}),
            "unverified_items": equipment,
            "note": eq_summary_note,
        },
        "availability": {
            "present": bool(availability),
            "declared_space_count": len(availability) if availability else 0,
            "note": avail_summary_note,
        },
        "summary_counts": summary_counts,
        "qualified": qualified,
        "excluded": excluded,
        "satisfied": bool(qualified),
        "exclusion_reasons": sorted({r for e in excluded for r in e.get("reason_excluded", [])}),
        "note": "Ranked by verified BIM constraints. Unverified requirements are shown separately." if equipment else "Filtering only; no optimization, no invented schedule.",
    }


# --------------------------------------------------------------------------
# Part 1+2+3+6 — recommendation builder
# --------------------------------------------------------------------------

def build_recommendations(
    candidates_doc: dict,
    profile: dict,
    health: dict,
    mapping: dict,
    resource_state: dict,
    forecasts: dict,
    requests: list[dict] | None = None,
    availability: dict | None = None,
    cfg: dict | None = None,
) -> dict:
    cfg = cfg or RECOMMENDATION
    requests = requests or []
    candidates = candidates_doc.get("records", [])
    health_by_sensor = _health_by_sensor(health)
    profile_by_channel = _profile_by_channel(profile)
    forecast_by_channel = _forecast_by_channel(forecasts)
    space_by_id = {s["space_id"]: s for s in resource_state.get("spaces", [])}
    req_by_id = {r.get("request_id"): r for r in requests}

    records = []
    for candidate in sorted(candidates, key=lambda c: c.get("candidate_id", "")):
        sensor_id = _sensor_id(candidate)
        mt = (candidate.get("evidence") or {}).get("measurement_type")
        fore_recs = forecast_by_channel.get((sensor_id, mt)) if sensor_id and mt else None
        ranking = rank_candidate(candidate, fore_recs, health_by_sensor, cfg)

        location = _location_for(candidate)
        affected = dict(candidate.get("affected_entity") or {})
        req = None
        if candidate.get("affected_entity", {}).get("type") == "request":
            req = req_by_id.get(candidate.get("affected_entity", {}).get("request_id"))
        chain = evidence_chain(candidate, fore_recs, req)
        resource_space = space_by_id.get(_space_id_of(candidate) or location.get("space_id"))
        impact = estimate_impact(candidate, resource_space, cfg)

        chan = profile_by_channel.get((sensor_id, mt)) if sensor_id and mt else None
        dev = health_by_sensor.get(sensor_id) if sensor_id else None
        quality_info = {
            "sensor_id": sensor_id,
            "health_status": (dev or {}).get("health_status"),
            "coverage_fraction": (dev or {}).get("coverage_fraction") if dev else None,
            "missing_ratio": (dev or {}).get("missing_ratio") if dev else None,
            "forecast_samples": (
                min((rec.get("coverage") or {}).get("recent_sample_count", 0) for rec in fore_recs)
                if fore_recs else None
            ),
            "note": "data quality is observability quality, not measurement accuracy.",
        }

        record = {
            "recommendation_id": None,  # assigned after stable ordering
            "candidate_id": candidate.get("candidate_id"),
            "problem_type": candidate.get("problem_type"),
            "source": candidate.get("source"),
            "recommendation_category": category_for(candidate),
            "affected_entity": affected,
            "location_status": location["status"],
            "location": location,
            "recommended_action": candidate.get("proposed_action"),
            "reason": candidate.get("reason"),
            "evidence": candidate.get("evidence"),
            "evidence_chain": chain,
            "constraints": candidate.get("constraints") or [],
            "expected_impact": impact,
            "confidence": {
                "value": candidate.get("confidence"),
                "basis": "RULE_BASED_HEURISTIC (not a statistical probability/interval)",
            },
            "data_quality": quality_info,
            "priority_score": ranking["priority_score"],
            "priority": ranking["priority"],
            "priority_factors": ranking["factors"],
            "ranking": ranking,
        }
        records.append(record)

    # stable order: highest priority first, then candidate id
    records.sort(key=lambda r: (-r["priority_score"], r["candidate_id"]))
    for i, r in enumerate(records, 1):
        r["recommendation_id"] = f"R-{i:04d}"

    by_category = {}
    by_priority = {}
    by_location = {}
    for r in records:
        by_category[r["recommendation_category"]] = by_category.get(r["recommendation_category"], 0) + 1
        by_priority[r["priority"]] = by_priority.get(r["priority"], 0) + 1
        by_location[r["location_status"]] = by_location.get(r["location_status"], 0) + 1

    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "ranking_note": cfg["description"],
        "honesty_note": (
            "No measured savings, timetables, or sensor locations are "
            "fabricated. Impact claims are classified; energy savings remain "
            "UNKNOWN until a verified intervention model exists."
        ),
        "summary": {
            "total": len(records),
            "by_category": by_category,
            "by_priority": by_priority,
            "by_location_status": by_location,
            "sources": {
                "candidates_total": len(candidates),
                "requests_processed": len(requests),
            },
        },
        "records": records,
    }


# --------------------------------------------------------------------------
# Part 10 — dashboard / product state
# --------------------------------------------------------------------------

def build_dashboard_summary(datapack: dict) -> dict:
    """Compact, frontend-first product state (no huge raw lists)."""
    tis = datapack.get("telemetry_intelligence_summary", {})
    ds = tis.get("dataset", {})
    intel = tis.get("intelligence", {})
    anom = intel.get("anomalies", {})
    m4 = datapack.get("sensor_space_mapping", {}).get("summary", {})
    rs = datapack.get("resource_state", {}).get("summary", {})
    rec = datapack.get("recommendations", {}).get("summary", {})
    cand = datapack.get("decision_candidates", {}).get("summary", {})
    health = datapack.get("sensor_health", {}).get("summary", {})
    fcast = datapack.get("forecasts", {}).get("forecast", {}).get("summary", {})
    campus = datapack.get("campus_registry", {})
    buildings = campus.get("buildings") or []
    building = buildings[0] if buildings else {}
    anom_sev = anom.get("by_severity", {})
    high_critical = (anom_sev.get("HIGH", 0) or 0) + (anom_sev.get("CRITICAL", 0) or 0)
    cand_sev = cand.get("by_severity", {})
    cand_high_critical = (cand_sev.get("HIGH", 0) or 0) + (cand_sev.get("CRITICAL", 0) or 0)
    h = health if isinstance(health, dict) else {}
    h_dist = h.get("health_status_distribution", {}) if isinstance(h, dict) else {}
    h_healthy = h.get("healthy") if h.get("healthy") is not None else h_dist.get("HEALTHY", 0)
    h_degraded = h.get("degraded") if h.get("degraded") is not None else h_dist.get("DEGRADED", 0)
    h_devices = h.get("devices") or (h_healthy + h_degraded)
    return {
        "campus": {
            "campus_id": building.get("campus_id") or (campus.get("campus") or {}).get("campus_id"),
            "campus_name": (campus.get("campus") or {}).get("name"),
            "building_count": rs.get("building_count") or len(buildings),
            "storey_count": rs.get("storey_count_registry") or rs.get("storey_count"),
            "space_count": rs.get("space_count"),
        },
        "telemetry": {
            "sensor_count": ds.get("devices"),
            "channel_count": ds.get("channels"),
            "total_readings": ds.get("total_readings"),
            "channels_by_type": ds.get("channels_by_type"),
            "time_span": ds.get("time_span"),
        },
        "anomalies": {
            "channels_with_anomalies": anom.get("channels_with_anomalies"),
            "by_severity": anom_sev,
            "high_critical_total": high_critical,
        },
        "decision_candidates": {
            "total": cand.get("total"),
            "by_severity": cand_sev,
            "high_critical_total": cand_high_critical,
        },
        "sensor_health": {
            "devices": h_devices,
            "healthy": h_healthy,
            "degraded": h_degraded,
            "status": h.get("overall") or h.get("status") or ("DEGRADED" if h_degraded > 0 else "HEALTHY"),
        },
        "forecasts": {
            "channels_forecasted": fcast.get("channels_forecasted"),
            "channels_total": fcast.get("channels_total"),
            "available": bool(fcast.get("channels_forecasted")),
        },
        "recommendations": {
            "total": rec.get("total"),
            "by_priority": rec.get("by_priority"),
        },
        "mapping": {
            "total": m4.get("total"),
            "resolved": m4.get("resolved"),
            "confirmed": m4.get("confirmed"),
            "provisional": m4.get("provisional"),
            "unresolved": m4.get("unresolved"),
            "verified_locations": m4.get("verified_locations"),
            "status": "UNRESOLVED" if (m4.get("unresolved") or 0) > 0 and (m4.get("resolved") or 0) == 0 else "PARTIAL",
        },
        "data_status": {
            "sensor_location_mapping": "UNRESOLVED" if (m4.get("unresolved") or 0) >= (m4.get("total") or 0) else "PARTIAL",
            "availability_present": bool(datapack.get("resource_state", {}).get("availability", {}).get("present", False)),
            "measured_energy_available": bool(datapack.get("resource_state", {}).get("measured", {}).get("measured_energy_available", False)),
            "recommendation_records": rec.get("total"),
        },
    }


# --------------------------------------------------------------------------
# Orchestrator + report
# --------------------------------------------------------------------------

def run_pipeline(
    m6_dir: str = OUTPUT_DIR,
    out_dir: str = OUTPUT_DIR,
    docs_dir: str = DOCS_DIR,
    requests_path: str | None = None,
    availability_path: str | None = None,
    cfg: dict | None = None,
) -> dict[str, str]:
    cfg = cfg or RECOMMENDATION
    candidates = _load(os.path.join(m6_dir, "decision_candidates.json"))
    profile = _load(os.path.join(m6_dir, "telemetry_profile.json"))
    health = _load(os.path.join(m6_dir, "sensor_health.json"))
    mapping = _load(os.path.join(m6_dir, "sensor_space_mapping.json"))
    resource_state = _load(os.path.join(m6_dir, "resource_state.json"))
    forecasts = _load(os.path.join(m6_dir, "forecasts.json"))

    requests = []
    availability = None
    if requests_path and os.path.exists(requests_path):
        doc = _load(requests_path)
        requests = doc.get("requests", [])
        availability = doc.get("availability")
    elif availability_path and os.path.exists(availability_path):
        availability = _load(availability_path).get("availability")

    recommendations = build_recommendations(
        candidates, profile, health, mapping, resource_state, forecasts,
        requests=requests, availability=availability, cfg=cfg,
    )

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    paths = {}
    with open(os.path.join(out_dir, "recommendations.json"), "w", encoding="utf-8") as fh:
        json.dump(recommendations, fh, indent=2, sort_keys=True, ensure_ascii=False)
    paths["recommendations.json"] = os.path.join(out_dir, "recommendations.json")

    summary = {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "ranking_note": cfg["description"],
        "summary": recommendations["summary"],
        "generated_at": None,  # never a wall-clock in the artefact
    }
    with open(os.path.join(out_dir, "recommendation_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True, ensure_ascii=False)
    paths["recommendation_summary.json"] = os.path.join(out_dir, "recommendation_summary.json")

    paths["docs"] = write_recommendation_doc(
        recommendations, resource_state, mapping, forecasts,
        os.path.join(docs_dir, "RECOMMENDATION_ENGINE.md"),
    )
    return paths


def write_recommendation_doc(recommendations: dict, resource_state: dict, mapping: dict, forecasts: dict, doc_path: str) -> str:
    rec = recommendations["records"]
    summary = recommendations["summary"]
    top = (rec[0] if rec else {})
    lines = [
        "# CampusIQ — Recommendation Engine (M7)",
        "",
        "Converts M6 decision candidates into ranked, explainable, actionable",
        "recommendations. Answers WHAT IS HAPPENING, WHY IT MATTERS, WHAT THE",
        "ADMIN CAN DO, WHY THIS ACTION, WHAT EVIDENCE SUPPORTS IT, and WHAT",
        "INFORMATION IS MISSING.",
        "",
        "## 1. Ranking formula",
        "",
        f"- {RECOMMENDATION['formula_version']}:",
        f"  `priority_score = sum(weights[f] * factors[f])`",
        f"- Weights: {json.dumps(RECOMMENDATION['weights'])}",
        "- Factors (0..1, all stored per candidate in `ranking.factors` with",
        "  `factor_basis`): severity, persistence, deviation, forecast_relevance,",
        "  resource_relevance, actionability, confidence, data_quality.",
        f"- Priority bands: {json.dumps(RECOMMENDATION['priority_bands'])}.",
        "- This is decision-support ranking, not a claim of objective best.",
        "",
        f"## 2. Recommendations generated: {summary['total']}",
        "",
        f"- By category: {json.dumps(summary['by_category'])}",
        f"- By priority: {json.dumps(summary['by_priority'])}",
        f"- By location status: {json.dumps(summary['by_location_status'])}",
        f"- Top recommendation: {top.get('recommendation_id')} ({top.get('priority')}, "
        f"score {top.get('priority_score')}) -> {top.get('recommended_action')}"
        if top else "- (none)",
        "",
        "## 3. Categories",
        "",
        "- ENVIRONMENTAL: investigate ventilation / abnormal indoor conditions /",
        "  inspect affected environmental system.",
        "- ENERGY: inspect abnormal energy behaviour / operating schedule /",
        "  high-load equipment.",
        "- SENSOR_HEALTH: inspect sensor, check communication, validate readings.",
        "- ALLOCATION: feasible spaces, why they qualify, why others are rejected.",
        "",
        "## 4. Evidence chain",
        "",
        "Every recommendation carries `evidence_chain`, e.g. for anomalies:",
        "",
        "    ANOMALY -> MEASUREMENT -> HISTORICAL_BASELINE -> DEVIATION",
        "      -> PERSISTENCE -> CANDIDATE -> RECOMMENDATION",
        "",
        "Each step has an entity, value and note so the front-end can render it.",
        "",
        "## 5. Impact classification",
        "",
        "- `CALCULATED`   — from explicit model/data (e.g., BIM design capacity).",
        "- `ESTIMATED`    — reserved for a verified intervention model (none yet).",
        "- `QUALITATIVE`  — directional, non-numeric (e.g., risk reduction).",
        "- `UNKNOWN`      — no model/data (e.g., energy savings: value null, kWh,",
        "  'No verified intervention model').",
        "Never is a qualitative assumption turned into a numeric saving.",
        "",
        "## 6. Location and allocation honesty",
        "",
        f"- M4 status: {mapping.get('summary', {}).get('unresolved')} UNRESOLVED / "
        f"{mapping.get('summary', {}).get('total')} sensors -> sensor-derived",
        "  recommendations are UNKNOWN_LOCATION.",
        "- BIM/IFC-derived recommendations are VERIFIED_BIM.",
        "- Allocation evaluates ONLY explicit request + availability;"
        "  no timetable fabricated.",
        "",
        "## 7. Outputs",
        "",
        "- output/recommendations.json (full, ranked, explainable)",
        "- output/recommendation_summary.json (compact)",
        "- GET /api/* FastAPI layer (scripts/api_app.py)",
        "",
        "## 8. Recommended next step",
        "",
        "- M8: integrate a confirmed mapping (when available) to attach ",
        "  recommendations to rooms, and a schedule-aware allocation optimizer.",
        "",
    ]
    with open(doc_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return doc_path


if __name__ == "__main__":
    paths = run_pipeline()
    for name, p in sorted(paths.items()):
        print(name, os.path.relpath(p))