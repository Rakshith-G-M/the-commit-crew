"""CampusIQ — telemetry baselines (M5).

Recipes are computed from the single-scan analysis dicts produced by
telemetry_profile.analyze_all(); thresholds come from telemetry_config and are
explicitly NOT TalTech ground truth. Output is deterministic.

BASELINES MODEL
  global_   - full-history Gaussian fit (mean/median/std/MAD), *not* the best
              baseline for cyclic building data but the honest fallback.
  rolling   - tail-anchored 96-sample mean/std (used by the detector when a
              time-of-day bucket is under-populated).
  time_aware - hour-of-day (+day-of-week) expected values, the recommended
              baseline for cyclic indoor telemetry (occupancy + weather).
recommended_baseline is chosen per channel from available evidence.
"""

from __future__ import annotations

import json
import os
from typing import Any

import telemetry_config as cfg


def channel_baseline(a: dict[str, Any]) -> dict[str, Any]:
    b = a["baseline"]
    sufficient = (
        b["sample_count"] >= cfg.BASELINE["min_samples"]
        and (a.get("duration_hours") or 0.0) >= cfg.BASELINE["min_history_days"] * 24
    )
    hour_of_day = a.get("hour_of_day", {})
    peaks = sorted(hour_of_day.items(), key=lambda kv: kv[1]["mean"], reverse=True)
    troughs = sorted(hour_of_day.items(), key=lambda kv: kv[1]["mean"])
    day_mean = _range_mean(hour_of_day, list(range(9, 17)))
    night_mean = _range_mean(hour_of_day, list(range(0, 6)))
    return {
        "sensor_id": a["sensor_id"],
        "measurement_type": a["measurement_type"],
        "unit": a["unit"],
        "file": a["file"],
        "global": {
            "method": "gaussian",
            "sample_count": b["sample_count"],
            "first": b["first"],
            "last": b["last"],
            "mean": b["mean"], "median": b["median"], "std": b["std"],
            "min": b["min"], "max": b["max"], "mad": b["mad"],
            "sufficient_history": sufficient,
        },
        "rolling": {
            "window_samples": cfg.ANOMALY["rolling_window"],
            "window_days": cfg.round2(cfg.ANOMALY["rolling_window"] *
                                      (a.get("expected_interval_seconds") or 0) / 86400.0),
            "warmup_for_detector": cfg.ANOMALY["rolling_window"] - 1,
        },
        "time_aware": {
            "coverage_buckets": a["time_aware"]["coverage_buckets"],
            "expected_buckets": 168,
            "hour_grid": {
                str(int(h)): {
                    "mean": cfg.round2(hour_of_day[h]["mean"]),
                    "count": hour_of_day[h]["count"],
                } for h in sorted(hour_of_day)
            },
            "peak_hour": {
                "hour": int(peaks[0][0]) if peaks else None,
                "mean": cfg.round2(peaks[0][1]["mean"]) if peaks else None,
            },
            "trough_hour": {
                "hour": int(troughs[0][0]) if troughs else None,
                "mean": cfg.round2(troughs[0][1]["mean"]) if troughs else None,
            },
            "workday_9_16_delta": cfg.round2((day_mean or 0.0) - (night_mean or 0.0)),
        },
        "recommended_baseline": (
            "time_aware_hour_of_day" if sufficient else "global_gaussian"
        ),
        "energy_daily": a.get("energy_registers", {}) or None,
    }


def _range_mean(hour_of_day: dict, hours: list[int]) -> float | None:
    vals = [hour_of_day[h]["mean"] for h in hours if h in hour_of_day]
    if not vals:
        return None
    return sum(vals) / len(vals)


def build_payload(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    channels = [channel_baseline(a) for a in analyses]
    recommended: dict[str, int] = {}
    sufficient = 0
    for c in channels:
        recommended[c["recommended_baseline"]] = recommended.get(
            c["recommended_baseline"], 0) + 1
        if c["global"]["sufficient_history"]:
            sufficient += 1
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "summary": {
            "channels": len(channels),
            "sufficient_history": sufficient,
            "recommended_baseline_distribution": recommended,
        },
        "channels": channels,
    }


def write_baselines(analyses: list[dict[str, Any]],
                    out_dir: str | None = None) -> str:
    out = out_dir or cfg.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "telemetry_baselines.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_payload(analyses), f, indent=2, ensure_ascii=False)
    return path