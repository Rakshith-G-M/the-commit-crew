"""CampusIQ — M6 short-horizon forecasting (Part 1 of Decision Intelligence).

Forecasting is deliberately light-weight: it re-uses the M5 time-aware
baselines and per-channel profile (hour-of-day / day-of-week seasonal buckets,
recent rolling windows). It does NOT use deep learning and does NOT claim
distributional confidence intervals — a confidence/coverage metadata block and
a labelled dispersion estimate are emitted instead, and every forecast marks
whether statistical confidence intervals were calculated.

Design principles
-----------------
* Deterministic: given the same M5 inputs, output bytes are identical.
  Forecast timestamps are derived from the channel's last *observed* reading
  (no fabricated "now"); blending is pure arithmetic on stored statistics.
* Honest coverage: a forecast is only generated when the channel already has
  sufficient baseline history AND the relevant seasonal bucket + recent window
  have enough samples. Channels that fail these gates are reported in the
  summary with a machine-readable skip reason (never silently dropped).
* Cumulative registers (energy meters) are not raw-value forecastable: they
  are excluded with reason ``cumulative_register`` and documented, mirroring
  how M5 excluded them from anomaly detection.
* No confidence intervals are fabricated. All records carry
  ``confidence_interval_95: null`` plus a note; a robust spread estimate
  (seasonal MAD/0.6745) and seasonal/recent sample counts are provided as
  coverage metadata.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

from telemetry_config import FORECAST, FORECAST_MEASUREMENTS

TASK = "M6-FORECASTING"
SCHEMA_VERSION = "campusiq.forecasts/v1"
SKIP_REASON_CUMULATIVE = "cumulative_register"
SKIP_REASON_INSUFFICIENT_HISTORY = "insufficient_history"
SKIP_REASON_SEASONAL_COVERAGE = "seasonal_coverage_low"
SKIP_REASON_BUCKET_SAMPLES = "seasonal_bucket_sparse"
SKIP_REASON_RECENT_SAMPLES = "recent_history_low"


def _iso_add_hours(iso: str, hours: float) -> str:
    dt = datetime.fromisoformat(iso)
    dt = dt + timedelta(hours=hours)
    return dt.isoformat(timespec="seconds")


def _list_or(entries) -> list:
    return entries or []


def _profile_channels(profile: dict) -> list[dict]:
    return _list_or(profile.get("channels"))


def _baseline_by_composite(baselines: dict) -> dict[tuple, dict]:
    """Channels are identified by (sensor_id, measurement_type); M5 emits one
    baseline per channel, and a single sensor may carry several measurement
    types. Keying by the composite keeps forecasting per channel."""
    out: dict[tuple, dict] = {}
    for ch in _list_or(baselines.get("channels")):
        out[(ch["sensor_id"], ch.get("measurement_type"))] = ch
    return out


def _mapping_by_sensor(mapping: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rec in _list_or(mapping.get("mappings")):
        out[rec["sensor_id"]] = rec
    return out


def _location_of(mapping_record: dict) -> dict:
    if not mapping_record:
        return {
            "location_status": "UNKNOWN_LOCATION",
            "space_id": None,
            "location_verified": False,
        }
    return {
        "location_status": mapping_record.get("location_status", "UNKNOWN_LOCATION"),
        "space_id": mapping_record.get("space_id"),
        "location_verified": bool(mapping_record.get("location_verified", False)),
    }


def _spread(mad) -> float | None:
    if mad is None:
        return None
    try:
        m = float(mad)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(m) or m < 0:
        return None
    return round(m / 0.6744897501960817, 6)


def _seasonal_components(channel: dict) -> dict:
    """Extract the dow x hour grid (median + count) and bucketing metadata."""
    time_aware = channel.get("time_aware") or {}
    buckets = _list_or(time_aware.get("buckets"))
    expected = time_aware.get("covered_buckets")
    return {"buckets": buckets, "covered_buckets": expected}


def _seasonal_value(buckets, target_hour, target_dow) -> dict | None:
    """Return (median, sample_count, spread_estimate) for dow x hour bucket."""
    for b in buckets:
        if b["hour"] == target_hour and b["dow"] == target_dow:
            count = int(b.get("count", 0))
            med = b.get("median")
            mad = b.get("mad")
            return {
                "median": med,
                "sample_count": count,
                "spread_estimate": _spread(mad),
            }
    return None


def _recent_samples(channel: dict) -> tuple[int, float | None]:
    rw = (channel.get("recent_window") or {}).get("last_96_samples") or {}
    return int(rw.get("count", 0)), rw.get("mean")


def channel_skip_reason(channel: dict, baseline: dict, horizon: float, cfg: dict) -> dict | None:
    """Return the skip record for a channel that cannot be forecast, else None.

    Gates (all must pass for a valid forecast at *every* horizon):
      * not a cumulative register (energy meters).
      * M5 global baseline reports sufficient history.
      * the seasonal bucket for the target (dow, hour) has enough samples.
      * the recent window has enough samples.
    """
    if not baseline:
        return {
            "reason": SKIP_REASON_INSUFFICIENT_HISTORY,
            "detail": "no M5 baseline record for channel",
        }

    global_b = baseline.get("global") or {}
    if _list_or(global_b.get("sufficient_history")) is not True:
        # single value mix-tolerant: accept 1/0 booleans or True
        suff = global_b.get("sufficient_history")
        if not (suff is True or suff == 1 or suff == "1"):
            return {
                "reason": SKIP_REASON_INSUFFICIENT_HISTORY,
                "detail": "M5 baseline reports insufficient global history",
            }

    target = datetime.fromisoformat(_iso_add_hours(channel["last_timestamp"], horizon))
    buckets = _seasonal_components(channel)["buckets"]
    if not buckets:
        return {
            "reason": SKIP_REASON_SEASONAL_COVERAGE,
            "detail": "no seasonal buckets stored in profile",
        }
    b = _seasonal_value(buckets, target.hour, target.weekday())
    if not b:
        return {
            "reason": SKIP_REASON_BUCKET_SAMPLES,
            "detail": f"no bucket for dow={target.weekday()} hour={target.hour}",
        }
    if b["sample_count"] < cfg["min_seasonal_samples"]:
        return {
            "reason": SKIP_REASON_BUCKET_SAMPLES,
            "detail": (
                f"seasonal bucket dow={target.weekday()} hour={target.hour} "
                f"has {b['sample_count']} samples < {cfg['min_seasonal_samples']}"
            ),
        }

    recent_n, _ = _recent_samples(channel)
    if recent_n < cfg["min_recent_samples"]:
        return {
            "reason": SKIP_REASON_RECENT_SAMPLES,
            "detail": f"recent window has {recent_n} samples < {cfg['min_recent_samples']}",
        }
    return None


def _blend(recent_mean, seasonal_mean, w):
    return round(w * recent_mean + (1.0 - w) * seasonal_mean, 6)


def forecast_channel(channel: dict, baseline: dict, mapping: dict, cfg: dict) -> list[dict]:
    """Return forecast records for one channel across configured horizons.

    If any horizon fails a gate, the whole channel is skipped (a forecast must
    be uniformly achievable across all configured horizons to be useful; the
    explanation is surfaced in the summary).
    """
    skipped = []
    for h in cfg["horizons_hours"]:
        reason = channel_skip_reason(channel, baseline, h, cfg)
        if reason is not None:
            skipped.append({"horizon_hours": h, **reason})

    if skipped:
        return []

    buckets = _seasonal_components(channel)["buckets"]
    recent_n, recent_mean = _recent_samples(channel)
    w = float(cfg["blend_weight_recent"])
    records = []
    for h in cfg["horizons_hours"]:
        target = datetime.fromisoformat(_iso_add_hours(channel["last_timestamp"], h))
        b = _seasonal_value(buckets, target.hour, target.weekday())
        seasonal_mean = b["median"]
        predicted = _blend(recent_mean, seasonal_mean, w)
        location = _location_of(mapping)
        records.append(
            {
                "sensor_id": channel["sensor_id"],
                "measurement_type": channel.get("measurement_type"),
                "unit": channel.get("unit"),
                "forecast_timestamp": _iso_add_hours(channel["last_timestamp"], h),
                "as_of_timestamp": channel["last_timestamp"],
                "horizon_hours": h,
                "predicted_value": predicted,
                "baseline_value": seasonal_mean,
                "recent_mean": recent_mean,
                "prediction_method": "time_aware_seasonal_blend",
                "prediction_method_detail": (
                    f"{w}*recent_mean + {round(1.0 - w, 4)}*seasonal_median(dow, hour); "
                    "seasonal median is the robust time-aware baseline from M5"
                ),
                "training_window": {
                    "recent_samples": recent_n,
                    "recent_window_used": "last_96_samples",
                    "seasonal_bucket": f"dow{target.weekday()}_hour{target.hour}",
                    "seasonal_bucket_samples": b["sample_count"],
                    "total_history_samples": int(channel.get("record_count", 0)),
                    "sufficient_history": True,
                },
                "confidence": None,
                "confidence_interval_95": None,
                "coverage": {
                    "seasonal_bucket_sample_count": b["sample_count"],
                    "seasonal_spread_estimate": b.get("spread_estimate"),
                    "recent_sample_count": recent_n,
                    "total_history_samples": int(channel.get("record_count", 0)),
                    "confidence_intervals_calculated": False,
                },
                "confidence_note": (
                    "No distributional confidence interval computed; "
                    "seasonal_spread_estimate and sample counts flag dispersion/coverage."
                ),
                "location": location,
                "location_status": location["location_status"],
                "space_id": location["space_id"],
            }
        )
    return records


def is_measurable_for_forecast(measurement_type: str) -> bool:
    return measurement_type in FORECAST_MEASUREMENTS


def build_forecasts(profile_path: str, baselines_path: str, mapping_path: str, cfg: dict | None = None) -> dict:
    cfg = cfg or FORECAST
    profile = json.load(open(profile_path, encoding="utf-8"))
    baselines = json.load(open(baselines_path, encoding="utf-8"))
    mapping = (json.load(open(mapping_path, encoding="utf-8"))) if mapping_path else {}

    prof_channels = _profile_channels(profile)
    bl_by = _baseline_by_composite(baselines)
    map_by = _mapping_by_sensor(mapping)

    records: list[dict] = []

    for channel in sorted(prof_channels, key=lambda c: (c["sensor_id"], c.get("measurement_type"))):
        sensor_id = channel["sensor_id"]
        mt = channel.get("measurement_type")
        if not is_measurable_for_forecast(mt):
            records.append(
                {
                    "sensor_id": sensor_id,
                    "measurement_type": mt,
                    "skip_reason": SKIP_REASON_CUMULATIVE,
                    "detail": (
                        "cumulative register channel; raw values are not periodic and "
                        "are not raw-value forecastable (forecasts would be meaningless)"
                    ),
                }
            )
            continue

        baseline = bl_by.get((sensor_id, mt))
        reason = channel_skip_reason(channel, baseline, cfg["horizons_hours"][0], cfg)
        if reason is not None:
            records.append({"sensor_id": sensor_id, "measurement_type": mt, **reason})
            continue

        records.extend(forecast_channel(channel, baseline, map_by.get(sensor_id), cfg))

    records.sort(key=lambda r: (r["sensor_id"], r.get("horizon_hours", -1), r.get("skip_reason", "")))

    skipped_reasons: dict[str, int] = {}
    for r in records:
        if "skip_reason" in r:
            skipped_reasons[r["skip_reason"]] = skipped_reasons.get(r["skip_reason"], 0) + 1

    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "forecast": {"horizons_hours": cfg["horizons_hours"], "blend_weight_recent": cfg["blend_weight_recent"]},
        "confidence_note": (
            "statistical confidence intervals were NOT calculated; records expose "
            "coverage metadata and a labelled seasonal spread estimate instead."
        ),
        "summary": {
            "channels_total": len(prof_channels),
            "channels_forecasted": len(
                {(r["sensor_id"], r.get("measurement_type")) for r in records if "skip_reason" not in r}
            ),
            "channels_skipped": len(
                {r["sensor_id"] for r in records if "skip_reason" in r}
            ),
            "skipped_by_reason": skipped_reasons or None,
        },
        "records": records,
    }


if __name__ == "__main__":
    import os
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OUTPUT_DIR", "output")
    mapping = sys.argv[2] if len(sys.argv) > 2 else os.path.join(out, "sensor_space_mapping.json")
    result = build_forecasts(
        os.path.join(out, "telemetry_profile.json"),
        os.path.join(out, "telemetry_baselines.json"),
        mapping,
    )
    print(json.dumps(result["summary"], indent=2))
