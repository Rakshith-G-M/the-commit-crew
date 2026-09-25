"""CampusIQ — telemetry intelligence configuration (M5).

Central, documented, configurable thresholds for the M5 intelligence engine.

IMPORTANT: physical sanity limits and anomaly thresholds here are OPERATIONAL
CONFIGURATION, not TalTech ground truth. They are intentionally conservative
and documented as such in docs/TELEMETRY_INTELLIGENCE.md. They can be tuned
per deployment without touching engine code.
"""

from __future__ import annotations

import os
from typing import Any

TASK = "M5-TELEMETRY-INTELLIGENCE-ENGINE"
SCHEMA_VERSION = "campusiq.telemetry_intelligence/v1"

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# Measurement categories and their physical sanity limits (configurable).
PHYSICAL_LIMITS: dict[str, dict[str, float]] = {
    "temperature": {"min": -40.0, "max": 60.0},
    "humidity": {"min": 0.0, "max": 100.0},
    "co2": {"min": 0.0, "max": 5000.0},
    "pm2.5": {"min": 0.0, "max": 2000.0},
    "energy": {"min": 0.0, "max": 10_000_000.0},
}

QUALITY_FLAGS = ["VALID", "MISSING", "DUPLICATE", "OUT_OF_RANGE",
                 "TIME_GAP", "SUSPECT"]

ANOMALY: dict[str, Any] = {
    # statistical deviance that makes a reading a candidate
    "candidate_z": 3.5,
    # MAD-based robust candidate threshold (0.6745 * |v-median| / MAD)
    "mad_candidate_z": 6.0,
    # isolated fluctuations below this |score| are not reported
    "persistence_min": 2,
    "extreme_isolated_z": 6.0,
    # rolling baseline window in samples
    "rolling_window": 96,
    "time_bucket_min_samples": 5,
    "detail_cap": 500,
    # severity bands on the composite |score|
    "severity": {
        "low": 3.5,
        "medium": 4.5,
        "high": 6.0,
        "critical": 8.0,
    },
}


def severity_band() -> dict[str, float]:
    return ANOMALY["severity"]


def classify_severity(score: float) -> str:
    sev = severity_band()
    if score >= sev["critical"]:
        return "CRITICAL"
    if score >= sev["high"]:
        return "HIGH"
    if score >= sev["medium"]:
        return "MEDIUM"
    return "LOW"


BASELINE: dict[str, Any] = {
    # a time-aware (hour-of-day + day-of-week) baseline needs at least:
    "min_history_days": 14,
    "min_samples": 336,
    "global_min_samples": 10,
    "rolling_min_samples": 120,
    "time_bucket_min_samples": 5,
    "expected_interval_tolerance": 1.5,
    "gap_min_seconds": 60,
}

QUALITY: dict[str, Any] = {
    "gap_threshold_multiple": 1.5,
    "suspect_z": 4.0,
}

HEALTH: dict[str, Any] = {
    # reference "present" is the newest timestamp across all channels
    "stopped_reporting_tolerance_multiple": 3,
    "long_gap_hours": 24.0,
    "constant_distinct_ratio": 0.01,
    "constant_run_min": 200,
    "duplicate_ratio": 0.05,
    "irregular_cv": 0.25,
    "energy_no_increment_epsilon": 1e-6,
}

# M6 — short-horizon forecasting (lightweight, baseline-driven).
FORECAST: dict[str, Any] = {
    # forecast horizons (hours ahead of the channel's last reading)
    "horizons_hours": [1, 6, 24],
    # weight on the recent rolling mean; seasonal time-aware median gets (1-w)
    "blend_weight_recent": 0.4,
    # eligibility gates (a forecast is only emitted when all are met)
    "min_seasonal_samples": 10,
    "min_recent_samples": 24,
    # cumulative-register channels (energy meters) are not forecast on raw value
    "skip_cumulative_registers": True,
    # measurement types whose raw values ARE periodically forecastable
    "measurements": {"temperature", "humidity", "co2", "pm2.5"},
}

FORECAST_MEASUREMENTS = FORECAST["measurements"]

# M6 — campus resource state (BIM design representation).
RESOURCE_STATE: dict[str, Any] = {
    "schema_version": "campusiq.resource_state/v1",
}

# M6 — decision candidate engine (rule-based, pre-recommendation).
DECISION: dict[str, Any] = {
    # ventilation demand trigger: forecast CO2 at any horizon at/above this
    # ppm generates a DEMAND candidate (forecast, not measured peak)
    "co2_investigate_threshold_ppm": 900.0,
    # demand trigger: forecast at any horizon above this removes "ok" status
    "co2_demand_threshold_ppm": 1000.0,
    "temperature_demand_delta_c": 2.0,
    # severity bands keyed off per-channel anomaly survivor counts
    "survivor_severity": {
        "low": 1,
        "medium": 20,
        "high": 100,
        "critical": 400,
    },
    # rule-based confidence (0..1). These are heuristic scores, NOT confidence
    # intervals and NOT statistical coverage values.
    "confidence": {
        "anomaly": 0.55,
        "health": 0.50,
        "demand": 0.60,
        "allocation": 0.75,
    },
}


# M7 — recommendation ranking (transparent, explainable, configurable).
#
# priority_score = sum(weights[factor] * factors[factor]) over the factor set;
# the weights sum to 1.0 and every per-candidate factor (0..1) is stored with
# its derivation basis so the score is auditable. This is decision-SUPPORT
# ranking — it is NOT a claim that one action is objectively best.
RECOMMENDATION: dict[str, Any] = {
    "formula_version": "campusiq.weighted-linear/v1",
    "description": (
        "priority_score = sum(w*f); factor values are documented per "
        "candidate. Decision-support ranking, not an objective-best claim."
    ),
    "weights": {
        # severity of the underlying problem/candidate
        "severity": 0.30,
        # how persistent/confirmed the signal is (survivors, issues, demand)
        "persistence": 0.15,
        # magnitude of deviation from the historical baseline / threshold
        "deviation": 0.15,
        # whether a forecast supports the signal (proactive, not reactive)
        "forecast_relevance": 0.05,
        # connection to a known BIM resource (space, capacity, equipment)
        "resource_relevance": 0.10,
        # can the administrator act on it today
        "actionability": 0.10,
        # rule-based heuristic confidence of the underlying candidate
        "confidence": 0.10,
        # data quality: coverage/missing-ratio of the underlying channel
        "data_quality": 0.05,
    },
    # numeric palette for candidate severity labels
    "severity_numeric": {
        "LOW": 0.2,
        "MEDIUM": 0.5,
        "HIGH": 0.8,
        "CRITICAL": 1.0,
    },
    # priority label bands over the 0..1 priority_score
    "priority_bands": {
        "critical": 0.75,
        "high": 0.60,
        "medium": 0.40,
    },
    # survivor count treated as "fully persistent" in the log-normal basis
    "persistence_reference": 400,
    # default data-quality factor when no health coverage is available
    "neutral_data_quality": 0.5,
    # factors that always go through a documentation note
    "impact_classifications": [
        "CALCULATED",
        "ESTIMATED",
        "QUALITATIVE",
        "UNKNOWN",
    ],
}


def priority_label_for(score: float) -> str:
    """Map a 0..1 priority score to a priority label using the configured bands."""
    bands = RECOMMENDATION["priority_bands"]
    if score >= bands["critical"]:
        return "CRITICAL"
    if score >= bands["high"]:
        return "HIGH"
    if score >= bands["medium"]:
        return "MEDIUM"
    return "LOW"


def candidate_severity_for_survivors(count: int) -> str:
    bands = DECISION["survivor_severity"]
    if count >= bands["critical"]:
        return "CRITICAL"
    if count >= bands["high"]:
        return "HIGH"
    if count >= bands["medium"]:
        return "MEDIUM"
    return "LOW"


def candidate_confidence(base: float, boost: float = 0.0) -> float:
    value = min(0.9, base + max(0.0, min(0.25, boost)))
    return round(value, 3)


def measurement_type_for_label(label: str) -> str:
    mapping = {
        "temperature": "temperature",
        "humidity": "humidity",
        "co2": "co2",
        "pm2.5": "pm2.5",
        "energy": "energy",
    }
    return mapping.get(label, label)


def limits_for(measurement_type: str) -> tuple[float, float] | None:
    lim = PHYSICAL_LIMITS.get(measurement_type)
    return (lim["min"], lim["max"]) if lim else None


def round2(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def iso_from_dt(value: Any) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%S")