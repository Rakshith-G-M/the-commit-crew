"""CampusIQ — telemetry profiling engine (M5 core).

Single-pass analysis of every sensor channel CSV. All downstream M5 modules
(baseline, features, anomaly, health, intelligence summary) consume the
per-channel analysis produced here, so the raw 1,390,297 readings are read
exactly ONCE per pipeline run.

RAW DATA -> NORMALIZED DATA -> FEATURES -> BASELINE -> ANOMALY -> INTELLIGENCE

Read-only w.r.t. the raw CSVs: nothing is modified, and no full-density copy of
the readings is persisted (only aggregates, features, flagged anomalies and
bucket statistics).

Everything here is deterministic: no generated timestamps, stable ordering,
fixed thresholds from telemetry_config.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import investigate_sensor_ifc_mapping as source  # noqa: E402
import telemetry_config as cfg  # noqa: E402

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def _out_dir() -> str:
    return cfg.OUTPUT_DIR if hasattr(cfg, "OUTPUT_DIR") else OUTPUT_DIR


def load_source() -> Any:
    return source


# ---------------------------------------------------------------------------
# Stream normalization (STEP 2)
# ---------------------------------------------------------------------------
def normalize_stream(path: str) -> dict[str, Any]:
    """Parse + normalize one channel CSV into sorted time/value arrays."""
    ts: list[datetime] = []
    raw_ts: list[str] = []
    vals: list[float] = []
    missing_rows = 0
    invalid_ts_rows = 0
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            t = source.parse_timestamp((row.get("timestamp") or "").strip())
            if t is None:
                invalid_ts_rows += 1
                continue
            v = row.get("value")
            try:
                fv = float(v) if v is not None and v.strip() else float("nan")
            except ValueError:
                missing_rows += 1
                continue
            if not np.isfinite(fv):
                missing_rows += 1
                continue
            ts.append(t)
            raw_ts.append((row.get("timestamp") or "").strip())
            vals.append(fv)
    order = sorted(range(len(ts)), key=lambda i: ts[i])
    ts_sorted = [ts[i] for i in order]
    raw_sorted = [raw_ts[i] for i in order]
    val_sorted = np.asarray([vals[i] for i in order], dtype=float)
    return {
        "timestamps": ts_sorted,
        "raw_timestamps": raw_sorted,
        "values": val_sorted,
        "missing_rows": missing_rows,
        "invalid_ts_rows": invalid_ts_rows,
        "duplicate_timestamp_count": _count_duplicate_ts(ts_sorted),
    }


def _count_duplicate_ts(ts: list[datetime]) -> int:
    dup = 0
    for i in range(1, len(ts)):
        if ts[i] == ts[i - 1]:
            dup += 1
    return dup


def interval_stats(ts: list[datetime]) -> dict[str, Any]:
    """Inter-sample intervals over distinct consecutive timestamps."""
    dts = []
    prev = None
    for t in ts:
        if prev is not None:
            d = (t - prev).total_seconds()
            if d > 0:
                dts.append(d)
        prev = t
    out: dict[str, Any] = {"count": len(dts)}
    if not dts:
        out.update({"min": None, "max": None, "median": None,
                    "mean": None, "std": None})
        return out
    arr = np.asarray(dts, dtype=float)
    out.update({
        "min": cfg.round2(float(arr.min())),
        "max": cfg.round2(float(arr.max())),
        "median": cfg.round2(float(np.median(arr))),
        "mean": cfg.round2(float(arr.mean())),
        "std": cfg.round2(float(arr.std(ddof=1) if len(arr) > 1 else 0.0)),
    })
    return out


def detect_gaps(ts: list[datetime], expected_seconds: float,
                limit: int = 10) -> dict[str, Any]:
    gaps = []
    prev = None
    for t in ts:
        if prev is not None:
            d = (t - prev).total_seconds()
            threshold = max(expected_seconds * cfg.QUALITY["gap_threshold_multiple"],
                            cfg.BASELINE["gap_min_seconds"])
            if d > threshold:
                gaps.append((prev, t, d))
        prev = t
    gaps_sorted = sorted(gaps, key=lambda g: g[2], reverse=True)
    return {
        "count": len(gaps),
        "largest_seconds": cfg.round2(gaps_sorted[0][2]) if gaps_sorted else None,
        "top": [
            {"from": cfg.iso_from_dt(g[0]), "to": cfg.iso_from_dt(g[1]),
             "gap_seconds": cfg.round2(g[2])}
            for g in gaps_sorted[:limit]
        ],
    }


def rolling_stats(values: np.ndarray, window: int) -> dict[str, Any]:
    """Tail-anchored rolling mean/std arrays (same length; NaN before window)."""
    n = len(values)
    if n == 0:
        return {"mean": values, "std": values}
    cs = np.cumsum(np.insert(values, 0, 0.0))
    cs_sq = np.cumsum(np.insert(values ** 2, 0, 0.0))
    mean = np.full(n, np.nan)
    var = np.full(n, np.nan)
    if n >= window:
        mean_window = (cs[window:] - cs[:-window]) / window
        var_window = (cs_sq[window:] - cs_sq[:-window]) / window - mean_window ** 2
        np.maximum(var_window, 0.0, out=var_window)
        std_window = np.sqrt(var_window)
        mean[window - 1:] = mean_window
        var[window - 1:] = np.where(std_window > 1e-12, std_window, 0.0)
    return {"mean": mean, "std": var}


def hour_bucket_stats(ts: list[datetime], values: np.ndarray) -> dict[str, Any]:
    """Aggregate mean/min/max/count per hour-of-day (0..23)."""
    hours = np.asarray([t.hour for t in ts], dtype=int)
    res: dict[int, dict[str, float]] = {}
    for h in range(24):
        mask = hours == h
        sel = values[mask]
        if sel.size == 0:
            continue
        res[h] = {
            "count": int(sel.size),
            "mean": cfg.round2(float(sel.mean())),
            "min": cfg.round2(float(sel.min())),
            "max": cfg.round2(float(sel.max())),
            "std": cfg.round2(float(sel.std(ddof=1) if sel.size > 1 else 0.0)),
        }
    return res


def dow_hour_basin(ts: list[datetime], values: np.ndarray) -> dict[str, Any]:
    """Day-of-week x hour-of-day buckets. Detection uses a robust expectation
    (median) and robust spread (1.4826-anchored MAD) so that a single extreme
    reading cannot contaminate the very bucket statistics used to find it."""
    keys = np.asarray([t.weekday() * 24 + t.hour for t in ts], dtype=int)
    out = []
    present = set()
    for k in sorted(set(keys.tolist())):
        sel = values[keys == k]
        present.add(k)
        med = float(np.median(sel))
        mad = float(np.median(np.abs(sel - med))) if sel.size > 1 else 0.0
        out.append({
            "dow": k // 24, "hour": k % 24, "count": int(sel.size),
            "mean": float(sel.mean()), "median": med,
            "std": float(sel.std(ddof=1) if sel.size > 1 else 0.0),
            "mad": mad,
        })
    return {"coverage_buckets": len(present), "buckets": out}


def _suspect_flags(values: np.ndarray, mean: float, std: float,
                   lo: float | None, hi: float | None) -> int:
    oor = np.zeros(values.size, dtype=bool)
    if lo is not None or hi is not None:
        if lo is not None:
            oor |= values < lo
        if hi is not None:
            oor |= values > hi
    extreme = np.zeros(values.size, dtype=bool)
    if std and std > 0:
        extreme = np.abs(values - mean) / std >= cfg.QUALITY["suspect_z"]
    suspect = oor | extreme
    return int(suspect.sum())


# ---------------------------------------------------------------------------
# Per-channel analysis (one full scan)
# ---------------------------------------------------------------------------
def profile_channel(path: str) -> dict[str, Any]:
    fname = os.path.basename(path)
    sensor_id = source.extract_uuid_from_filename(fname) or ""
    sensor_type = source.infer_sensor_type(fname)
    limits = cfg.limits_for(sensor_type)
    stream = normalize_stream(path)
    ts, vals = stream["timestamps"], stream["values"]
    n = int(vals.size)

    profile: dict[str, Any] = {
        "file": fname,
        "sensor_id": sensor_id,
        "measurement_type": sensor_type,
        "unit": None,
        "record_count": n,
        "missing_count": stream["missing_rows"] + stream["invalid_ts_rows"],
        "invalid_timestamp_count": stream["invalid_ts_rows"],
        "duplicate_timestamp_count": stream["duplicate_timestamp_count"],
    }
    if n == 0:
        profile.update({
            "first_timestamp": None, "last_timestamp": None, "duration_hours": 0.0,
            "min": None, "max": None, "mean": None, "median": None, "std": None,
        })
        return profile

    unit = _read_unit(path)
    profile["unit"] = unit
    mean = float(vals.mean())
    std = float(vals.std(ddof=1) if n > 1 else 0.0)
    median = float(np.median(vals))
    min_v = float(vals.min())
    max_v = float(vals.max())
    profile.update({
        "first_timestamp": cfg.iso_from_dt(ts[0]),
        "last_timestamp": cfg.iso_from_dt(ts[-1]),
        "duration_hours": cfg.round2((ts[-1] - ts[0]).total_seconds() / 3600.0),
        "min": cfg.round2(min_v), "max": cfg.round2(max_v),
        "mean": cfg.round2(mean), "median": cfg.round2(median),
        "std": cfg.round2(std),
        "percentiles": {int(q): cfg.round2(float(np.percentile(vals, q)))
                        for q in (1, 5, 25, 50, 75, 90, 95, 99)},
    })

    intervals = interval_stats(ts)
    expected = intervals["median"] or 0.0
    gaps = detect_gaps(ts, expected)
    oor = 0
    if limits:
        lo, hi = limits
        oo = (vals < lo) | (vals > hi)
        oor = int(oo.sum())
    suspect = _suspect_flags(vals, mean, std,
                             limits[0] if limits else None,
                             limits[1] if limits else None)
    valid = n - oor
    dup = stream["duplicate_timestamp_count"]
    missing = profile["missing_count"]

    quality = {
        "VALID": valid,
        "MISSING": missing,
        "DUPLICATE": dup,
        "OUT_OF_RANGE": oor,
        "TIME_GAP": gaps["count"],
        "SUSPECT": suspect,
    }
    profile["quality"] = quality
    profile["interval_stats"] = intervals
    profile["expected_interval_seconds"] = expected
    profile["gaps"] = gaps
    profile["rolling"] = rolling_stats(vals, cfg.ANOMALY["rolling_window"])
    profile["hour_of_day"] = hour_bucket_stats(ts, vals)
    profile["time_aware"] = dow_hour_basin(ts, vals)

    # baselines (global + robust)
    mad = float(np.median(np.abs(vals - median))) if n > 1 else 0.0
    profile["baseline"] = {
        "method": "gaussian",
        "sample_count": n,
        "first": profile["first_timestamp"],
        "last": profile["last_timestamp"],
        "mean": cfg.round2(mean), "median": cfg.round2(median),
        "std": cfg.round2(std), "min": cfg.round2(min_v),
        "max": cfg.round2(max_v),
        "mad": cfg.round2(mad),
    }

    # features-derived quantities
    profile["rate_of_change"] = _rate_of_change(ts, vals)
    profile["recent_window"] = _recent_window(ts, vals)
    profile["energy_registers"] = _energy_register_estimate(ts, vals, sensor_type)

    # anomaly candidate detection (dominant signal scoring, persistence runs)
    records, det_counts = detect_anomalies(profile, ts, vals, sensor_type)
    profile["anomalies"] = records
    profile["anomaly_summary"] = {
        **det_counts,
        "recorded_detail_count": len(records),
    }
    profile["health"] = _health_indicators(profile, ts, vals, sensor_type, expected)
    return profile


def _read_unit(path: str) -> str | None:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            u = (row.get("unit") or "").strip()
            return u if u else None
    return None


def _rate_of_change(ts: list[datetime], vals: np.ndarray) -> dict[str, Any]:
    if vals.size < 2:
        return {"median_abs_per_hour": None, "max_abs_per_hour": None,
                "positive_sign_changes": None}
    dt = np.asarray([(ts[i] - ts[i - 1]).total_seconds()
                     for i in range(1, len(ts))], dtype=float)
    dv = np.diff(vals)
    mask = dt > 0
    rates = np.abs(dv[mask]) / (dt[mask] / 3600.0)
    sign_changes = int(((dv[1:] * dv[:-1]) < 0).sum()) if dv.size > 1 else 0
    return {
        "median_abs_per_hour": cfg.round2(float(np.median(rates))),
        "max_abs_per_hour": cfg.round2(float(rates.max())),
        "sign_changes": sign_changes,
    }


def _recent_window(ts: list[datetime], vals: np.ndarray) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if vals.size == 0:
        return out
    t_arr = np.asarray([np.datetime64(t) for t in ts])
    last96 = vals[-min(96, vals.size):]
    out["last_96_samples"] = {
        "count": int(last96.size),
        "mean": cfg.round2(float(last96.mean())),
        "min": cfg.round2(float(last96.min())),
        "max": cfg.round2(float(last96.max())),
        "std": cfg.round2(float(last96.std(ddof=1) if last96.size > 1 else 0.0)),
    }
    cutoff = t_arr[-1] - np.timedelta64(7, "D")
    mask = t_arr >= cutoff
    week = vals[mask] if mask.any() else vals[:0]
    if week.size:
        out["last_7_days"] = {
            "count": int(week.size),
            "mean": cfg.round2(float(week.mean())),
            "min": cfg.round2(float(week.min())),
            "max": cfg.round2(float(week.max())),
            "std": cfg.round2(float(week.std(ddof=1) if week.size > 1 else 0.0)),
        }
    else:
        out["last_7_days"] = None
    return out


def _daily_energy_curve(ts: list[datetime],
                        vals: np.ndarray) -> list[dict[str, Any]]:
    """Daily kWh consumed (cumulative register delta per calendar day).

    Takes each day's LAST reading as the register value, then diffs
    consecutive days -> robust to any intra-day cadence (15-min, 1-s bursts,
    night gaps). Returns [] when values do not increase across days.
    """
    n = len(ts)
    if n < 2:
        return []
    by_day: list[tuple[datetime, float]] = []
    cur_day = ts[0].date()
    last_ts = ts[0]
    last_val = float(vals[0])
    curve: list[dict[str, Any]] = []
    for i in range(1, n):
        d = ts[i].date()
        if d != cur_day:
            by_day.append((last_ts, last_val))
            cur_day = d
        last_ts = ts[i]
        last_val = float(vals[i])
    by_day.append((last_ts, last_val))
    for i in range(1, len(by_day)):
        prev_v, cur_v = by_day[i - 1][1], by_day[i][1]
        delta = cur_v - prev_v
        if delta > 0:
            curve.append({"ts": by_day[i][0], "date": by_day[i][0].date().isoformat(),
                          "value": delta})
    return curve


def _energy_register_estimate(ts: list[datetime], vals: np.ndarray,
                              sensor_type: str) -> dict[str, Any]:
    if sensor_type != "energy":
        return {}
    curve = _daily_energy_curve(ts, vals)
    values = [c["value"] for c in curve]
    if not values:
        return {"derived_kwh_per_day_median": None,
                "derived_sample_count": 0,
                "note": "cumulative register did not increment across days"}
    return {
        "derived_kwh_per_day_median": cfg.round2(float(np.median(values))),
        "derived_sample_count": len(values),
        "burn_test_confidence": "medium",
        "note": "MEDIAN of per-calendar-day register deltas (cumulative kWh "
                "meter); a derived estimate, not a Native rate.",
    }


# ---------------------------------------------------------------------------
# Anomaly scoring + persistence (baseline statistical detector)
# ---------------------------------------------------------------------------
def detect_anomalies(profile: dict, ts: list[datetime], vals: np.ndarray,
                     sensor_type: str) -> tuple[list[dict[str, Any]], dict]:
    """Entry point. Energy channels are scored on their derived daily
    kWh/day delta curve (cumulative registers are monotonic staircases that
    would otherwise flood a raw-value detector); all other channels are
    scored directly."""
    if sensor_type == "energy":
        curve = _daily_energy_curve(ts, vals)
        if len(curve) < 3:
            return [], {"candidates_surviving": 0, "by_method": {},
                        "energy_derived_scores": True,
                        "energy_delta_samples": len(curve)}
        dts = [c["ts"] for c in curve]
        dv = np.asarray([c["value"] for c in curve], dtype=float)
        mini = _mini_profile(profile, dts, dv)
        # daily-resolution series: a single extreme day is a real event, so
        # the "2 consecutive samples" persistence floor is relaxed to 1.
        records, counts = _score_series(mini, dts, dv, "energy",
                                        persistence_min=1)
        for r in records:
            r["derived"] = "cumulative_register_daily_delta_processed"
        counts["energy_derived_scores"] = True
        counts["energy_delta_samples"] = len(dv)
        counts["scored_raw"] = False
        return records, counts
    return _score_series(profile, ts, vals, sensor_type)


def _mini_profile(profile: dict, dts: list[datetime],
                  dv: np.ndarray) -> dict[str, Any]:
    mean = float(dv.mean())
    std = float(dv.std(ddof=1) if dv.size > 1 else 0.0)
    median = float(np.median(dv))
    mad = float(np.median(np.abs(dv - median))) if dv.size > 1 else 0.0
    return {
        "sensor_id": profile["sensor_id"],
        "unit": profile["unit"],
        "baseline": {"mean": mean, "std": std, "median": median, "mad": mad},
        "rolling": rolling_stats(dv, cfg.ANOMALY["rolling_window"]),
        "time_aware": dow_hour_basin(dts, dv),
    }


def _score_series(profile: dict, ts: list[datetime], vals: np.ndarray,
                  sensor_type: str,
                  persistence_min: int | None = None) -> tuple[list[dict[str, Any]], dict]:
    """Contextual statistical anomaly detector.

    Primary expected-value baseline is chosen per reading by context, in
    priority order -> hour-of-day/day-of-week buckets (captures the building's
    occupancy/weather cycle), else rolling tail mean, else global mean. Bucket
    expectation is a *robust* median anchored by 1.4826-MAD so extreme values
    cannot contaminate their own bucket statistics. MAD and global z-score are
    secondary signals reported on every record, never the primary driver (a
    flat median/MAD fit on cyclic indoor telemetry flags the daily rhythm
    itself).
    """
    cfgA = cfg.ANOMALY
    if persistence_min is None:
        persistence_min = cfgA["persistence_min"]
    n = vals.size
    if n < 2:
        return [], {"candidates_surviving": 0, "by_method": {}, "scored_raw": True}
    glob = profile["baseline"]
    mean, std, median = glob["mean"], glob["std"], glob["median"]
    mad = glob["mad"]
    # robust noise floor: Gaussian-consistent Mad-sigma = MAD / 0.6745
    floor = max(mad / 0.6745 if mad > 1e-12 else 1e-6, 1e-6)

    # secondary signals (modified z-score, Iglewicz & Hoaglin: 0.6745*MAD-z)
    z_mad = 0.6745 * np.abs(vals - median) / mad if mad > 1e-12 else np.zeros(n)
    z_global = np.abs(vals - mean) / std if std > 1e-12 else np.zeros(n)
    roll = profile["rolling"]
    w = cfgA["rolling_window"]
    defined = np.arange(n) >= w - 1
    rstd = roll["std"]
    z_roll = np.zeros(n)
    ok = defined & (rstd > 1e-12)
    np.divide(np.abs(vals - roll["mean"]), np.maximum(rstd, 1e-6),
              out=z_roll, where=ok)

    # primary: contextual expected value / std arrays (robust median/MAD)
    exp = np.full(n, mean, dtype=float)
    eff_std = np.full(n, max(std, 1e-6), dtype=float)
    method = np.full(n, "z_score", dtype=object)
    bucket_map = {(b["dow"], b["hour"]): b
                  for b in profile["time_aware"]["buckets"]}
    time_valid = np.zeros(n, dtype=bool)
    for i, t in enumerate(ts):
        b = bucket_map.get((t.weekday(), t.hour))
        if b and b["count"] >= cfgA["time_bucket_min_samples"]:
            exp[i] = b["median"]
            if b["mad"] > 1e-12:
                eff_std[i] = max(b["mad"] / 0.6745, 1e-12)
            else:
                eff_std[i] = max(b["std"] if b["std"] > 1e-12 else floor, 1e-12)
            method[i] = "time_aware"
            time_valid[i] = True
    roll_valid = ~time_valid & defined
    exp[roll_valid] = roll["mean"][roll_valid]
    eff_std[roll_valid] = np.maximum(rstd[roll_valid], floor)
    method[roll_valid] = "rolling"

    score = np.abs(vals - exp) / np.maximum(eff_std, 1e-12)
    flagged = score >= cfgA["candidate_z"]
    run_len = _run_lengths(flagged)
    med_series = float(np.median(vals)) if n else 1.0

    lim = cfg.limits_for(sensor_type)
    oor = np.zeros(n, dtype=bool)
    if lim:
        oor = (vals < lim[0]) | (vals > lim[1])

    anomalies: list[dict[str, Any]] = []
    by_method: dict[str, int] = {}
    cap = cfgA["detail_cap"]
    for i in np.nonzero(flagged)[0]:
        run = run_len[i]
        is_extreme = (run >= persistence_min or
                      score[i] >= cfgA["extreme_isolated_z"] or
                      z_mad[i] >= cfgA["mad_candidate_z"] or
                      bool(oor[i]))
        if not is_extreme:
            continue
        m = str(method[i])
        by_method[m] = by_method.get(m, 0) + 1
        if len(anomalies) >= cap:
            continue
        anomalies.append({
            "sensor_id": profile["sensor_id"],
            "measurement_type": sensor_type,
            "unit": profile["unit"],
            "timestamp": cfg.iso_from_dt(ts[i]),
            "value": cfg.round2(float(vals[i])),
            "expected": cfg.round2(float(exp[i])),
            "deviation": cfg.round2(float(vals[i] - exp[i])),
            "score": cfg.round2(float(score[i])),
            "method": m,
            "persistence": int(run),
            "magnitude_ratio": cfg.round2(max(float(vals[i]), 0.0) /
                                          max(med_series, 1e-9)),
            "severity_score": cfg.round2(max(float(score[i]),
                                             float(z_mad[i]),
                                             float(z_global[i]))),
            "signals": {
                "z_time_aware": cfg.round2(float(score[i])) if time_valid[i] else None,
                "z_rolling": cfg.round2(float(z_roll[i])) if defined[i] else None,
                "z_global": cfg.round2(float(z_global[i])),
                "z_mad": cfg.round2(float(z_mad[i])),
            },
            "baseline": {
                "method": m,
                "expected_value": cfg.round2(float(exp[i])),
                "expected_std": cfg.round2(float(eff_std[i])),
            },
            "location_status": "UNKNOWN",
            "space_id": None,
        })
    anomalies.sort(key=lambda a: (a["sensor_id"], a["timestamp"]))
    total = sum(by_method.values())
    counts = {
        "candidates_surviving": total,
        "by_method": by_method,
        "capped_detail": len(anomalies) < total,
        "scored_raw": True,
    }
    return anomalies, counts


def _run_lengths(flagged: np.ndarray) -> np.ndarray:
    out = np.zeros(flagged.size, dtype=int)
    run = 0
    for i in range(flagged.size):
        run = run + 1 if flagged[i] else 0
        out[i] = run
    return out


# ---------------------------------------------------------------------------
# Health indicators (STEP 8 building blocks)
# ---------------------------------------------------------------------------
def _health_indicators(profile: dict, ts: list[datetime], vals: np.ndarray,
                       sensor_type: str, expected: float) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    q = profile["quality"]
    n = vals.size
    if n and expected and expected > 0:
        interval = profile["interval_stats"]
        cv = interval["std"] / interval["mean"] if interval["mean"] else 0.0
        if cv >= cfg.HEALTH["irregular_cv"]:
            issues.append({"type": "IRREGULAR_SAMPLING",
                           "severity": "LOW",
                           "detail": f"interval CV {cv:.2f} >= "
                                     f"{cfg.HEALTH['irregular_cv']}"})
        largest_gap = profile["gaps"]["largest_seconds"]
        if largest_gap and largest_gap >= cfg.HEALTH["long_gap_hours"] * 3600:
            issues.append({"type": "LONG_GAP",
                           "severity": "MEDIUM",
                           "detail": f"largest gap {largest_gap / 3600:.1f} h"})
    if n and q["DUPLICATE"] / max(n, 1) >= cfg.HEALTH["duplicate_ratio"]:
        issues.append({"type": "EXCESSIVE_DUPLICATES",
                       "severity": "MEDIUM",
                       "detail": f"{q['DUPLICATE']} duplicate timestamps"})
    if q["OUT_OF_RANGE"] > 0:
        issues.append({"type": "IMPOSSIBLE_VALUES",
                       "severity": "HIGH" if q["OUT_OF_RANGE"] > 10 else "MEDIUM",
                       "detail": f"{q['OUT_OF_RANGE']} readings outside "
                                 "configured physical limits"})
    distinct = int(np.unique(vals).size) if n else 0
    longest_run = _longest_identical_run(vals)
    if sensor_type != "energy":
        if n and distinct / max(n, 1) <= cfg.HEALTH["constant_distinct_ratio"]:
            issues.append({"type": "CONSTANT_VALUE",
                           "severity": "HIGH",
                           "detail": f"only {distinct} distinct values in {n}"})
        elif longest_run >= cfg.HEALTH["constant_run_min"]:
            issues.append({"type": "CONSTANT_VALUE",
                           "severity": "MEDIUM",
                           "detail": f"identical value for {longest_run} rows"})
    else:
        reg = profile["energy_registers"]
        if not reg.get("derived_sample_count"):
            issues.append({"type": "REGISTER_NO_INCREMENT",
                           "severity": "HIGH",
                           "detail": "cumulative register never incremented "
                                     "across days"})
        elif (reg.get("derived_kwh_per_day_median") is not None and
              reg["derived_kwh_per_day_median"] < 1e-6):
            issues.append({"type": "REGISTER_NO_INCREMENT",
                           "severity": "LOW",
                           "detail": "daily register deltas ~ 0"})
    return {
        "distinct_values": distinct,
        "longest_identical_run": longest_run,
        "issue_count": len(issues),
        "issues": issues,
    }


def _longest_identical_run(vals: np.ndarray) -> int:
    if vals.size == 0:
        return 0
    best = run = 1
    for i in range(1, vals.size):
        if vals[i] == vals[i - 1]:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------
def analyze_all(csv_dir: str | None = None) -> list[dict[str, Any]]:
    if csv_dir is None:
        csv_dir = source.CSV_DATA_DIR
    files = sorted(os.listdir(csv_dir))
    files = [f for f in files if f.endswith(".csv")]
    analyses = {}
    for f in files:
        key = f.lower()
        if key in analyses:
            raise ValueError(f"duplicate channel file: {f}")
        analyses[key] = profile_channel(os.path.join(csv_dir, f))
    return [analyses[k] for k in sorted(analyses)]


def strip_channel_for_json(analysis: dict[str, Any]) -> dict[str, Any]:
    """Drop in-memory-only heavy/derived fields from the persisted profile."""
    out = {}
    for k, v in analysis.items():
        if k in ("rolling", "anomalies"):
            continue
        out[k] = v
    out["rolling"] = {"window_samples": cfg.ANOMALY["rolling_window"]}
    return out


def build_profile_payload(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(a["record_count"] for a in analyses)
    by_type: dict[str, int] = {}
    for a in analyses:
        by_type[a["measurement_type"]] = by_type.get(a["measurement_type"], 0) + 1
    quality_totals = {flag: 0 for flag in cfg.QUALITY_FLAGS}
    for a in analyses:
        for flag, v in a.get("quality", {}).items():
            quality_totals[flag] = quality_totals.get(flag, 0) + v
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "summary": {
            "channels": len(analyses),
            "sensors": len({a["sensor_id"] for a in analyses}),
            "total_readings": total,
            "channels_by_type": by_type,
            "quality_totals": quality_totals,
        },
        "channels": [strip_channel_for_json(a) for a in analyses],
    }


def write_profile(analyses: list[dict[str, Any]],
                  out_dir: str | None = None) -> str:
    out = out_dir or OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "telemetry_profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_profile_payload(analyses), f, indent=2,
                  ensure_ascii=False, default=str)
    return path


if __name__ == "__main__":
    import argparse
    argparse_helper = argparse.ArgumentParser(description="profile telemetry")
    argparse_helper.add_argument("--out-dir", default=OUTPUT_DIR)
    options = argparse_helper.parse_args()
    data = analyze_all()
    written = write_profile(data, options.out_dir)
    print(f"profiled {len(data)} channels, {written}")