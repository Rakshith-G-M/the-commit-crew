"""CampusIQ — telemetry features (M5).

Derived analytical features per channel, computed from the single-scan
analysis dicts produced by telemetry_profile. Read-only with respect to raw
CSVs. Deterministic.
"""

from __future__ import annotations

import json
import os
from typing import Any

import telemetry_config as cfg


def channel_features(a: dict[str, Any]) -> dict[str, Any]:
    hod = a.get("hour_of_day", {})
    peak = max(hod.items(), key=lambda kv: kv[1]["mean"]) if hod else None
    trough = min(hod.items(), key=lambda kv: kv[1]["mean"]) if hod else None
    return {
        "sensor_id": a["sensor_id"],
        "measurement_type": a["measurement_type"],
        "unit": a["unit"],
        "file": a["file"],
        "statistics": {
            "count": a["record_count"],
            "min": a["min"], "max": a["max"],
            "mean": a["mean"], "median": a["median"], "std": a["std"],
            "coefficient_of_variation": cfg.round2(
                (a["std"] / a["mean"]) if a["mean"] else None),
            "percentiles": a.get("percentiles") or {},
            "duration_hours": a["duration_hours"],
            "first": a["first_timestamp"], "last": a["last_timestamp"],
        },
        "quality": {k: v for k, v in a["quality"].items()},
        "rate_of_change": a.get("rate_of_change"),
        "recent_window": a.get("recent_window"),
        "cyclic_hour_of_day": {
            "coverage_hours": len(hod),
            "peak_hour": int(peak[0]) if peak else None,
            "peak_value": cfg.round2(peak[1]["mean"]) if peak else None,
            "trough_hour": int(trough[0]) if trough else None,
            "trough_value": cfg.round2(trough[1]["mean"]) if trough else None,
            "peak_trough_delta": cfg.round2(
                (peak[1]["mean"] - trough[1]["mean"])
                if peak and trough else None),
        },
        "energy_daily": (a.get("energy_registers") or {}) or None,
    }


def build_payload(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "summary": _summary(analyses),
        "channels": [channel_features(a) for a in analyses],
    }


def _summary(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for a in analyses:
        by_type[a["measurement_type"]] = by_type.get(a["measurement_type"], 0) + 1
    return {
        "channels": len(analyses),
        "channels_by_type": by_type,
        "total_readings": sum(a["record_count"] for a in analyses),
    }


def write_features(analyses: list[dict[str, Any]],
                   out_dir: str | None = None) -> str:
    out = out_dir or cfg.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "telemetry_features.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_payload(analyses), f, indent=2, ensure_ascii=False)
    return path