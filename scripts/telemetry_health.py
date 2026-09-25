"""CampusIQ — sensor telemetry health (M5).

Per-DEVICE health assessments (36 devices; each device may carry several
channels e.g. temperature + humidity). Aggregates the per-channel quality and
health-issue indicators from telemetry_profile into a deterministic rubric:

  HEALTHY  - only LOW-severity sampling irregularities.
  DEGRADED - any HIGH issue, any MEDIUM CONSTANT_VALUE / LONG_GAP /
             IMPOSSIBLE_VALUES, or >5% missing/duplicate rows.
  FAILED   - zero valid readings.

Severity claims are operational configuration (telemetry_config), NOT TalTech
ground truth.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

import telemetry_config as cfg

DEGRADING_MEDIUM = {"CONSTANT_VALUE", "LONG_GAP", "IMPOSSIBLE_VALUES",
                    "EXCESSIVE_DUPLICATES"}


def _device_groups(analyses: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for a in analyses:
        groups.setdefault(a["sensor_id"], []).append(a)
    return groups


def _aggregate_issues(channels: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {}
    for a in channels:
        for issue in a.get("health", {}).get("issues", []):
            it = issue["type"]
            e = by_type.setdefault(it, {
                "affected": 0, "severities": Counter(), "examples": []})
            e["affected"] += 1
            e["severities"][issue["severity"]] += 1
            e["examples"].append({"channel": a["file"],
                                  "detail": issue.get("detail")})
    out = []
    for it, e in sorted(by_type.items()):
        max_sev = max(e["severities"], key=lambda s: _sev_rank(s))
        out.append({
            "type": it,
            "affected_channels": e["affected"],
            "max_severity": max_sev,
            "severity_distribution": dict(e["severities"]),
            "example": e["examples"][0],
        })
    return {"issues": out, "issue_count": len(out)}


def _sev_rank(s: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(s, 0)


def sensor_health(sensor_id: str, channels: list[dict[str, Any]],
                  dataset_span_days: float,
                  mapping: dict[str, Any]) -> dict[str, Any]:
    valid = sum(a["record_count"] for a in channels)
    missing = sum(a.get("missing_count", 0) for a in channels)
    duplicates = sum(a["quality"].get("DUPLICATE", 0) for a in channels)
    oor = sum(a["quality"].get("OUT_OF_RANGE", 0) for a in channels)
    gaps = sum(a["quality"].get("TIME_GAP", 0) for a in channels)
    suspect = sum(a["quality"].get("SUSPECT", 0) for a in channels)
    anomalies = sum(a.get("anomaly_summary", {}).get("candidates_surviving", 0)
                    for a in channels)

    ts_all = [a["first_timestamp"] for a in channels if a["first_timestamp"]]
    te_all = [a["last_timestamp"] for a in channels if a["last_timestamp"]]
    span_days = max(_day(t) for t in te_all) - min(_day(t) for t in ts_all) \
        if ts_all and te_all else 0.0
    known = max(valid, 1)
    missing_ratio = (missing + duplicates) / known
    agg = _aggregate_issues(channels)
    max_iss = max((_sev_rank(i["max_severity"]) for i in agg["issues"]),
                  default=0)
    has_high = any(_sev_rank(i["max_severity"]) >= 2 for i in agg["issues"])
    grav_medium = any(i["type"] in DEGRADING_MEDIUM and
                      _sev_rank(i["max_severity"]) >= 1
                      for i in agg["issues"])

    if valid == 0:
        status = "FAILED"
    elif has_high or grav_medium or missing_ratio > cfg.HEALTH["duplicate_ratio"]:
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    loc = _location(sensor_id, mapping)
    return {
        "sensor_id": sensor_id,
        "channels": sorted({a["measurement_type"] for a in channels}),
        "channel_count": len(channels),
        "health_status": status,
        "valid_readings": valid,
        "missing_readings": missing,
        "duplicate_timestamps": duplicates,
        "out_of_range_readings": oor,
        "time_gaps": gaps,
        "suspect_readings": suspect,
        "anomaly_candidates": anomalies,
        "missing_ratio": cfg.round2(missing_ratio),
        "observed_span_days": cfg.round2(span_days),
        "dataset_span_days": cfg.round2(dataset_span_days),
        "coverage_fraction": cfg.round2(min(span_days / max(dataset_span_days, 1e-9),
                                            1.0)),
        "first_report": min(ts_all) if ts_all else None,
        "last_report": max(te_all) if te_all else None,
        "issues": agg["issues"],
        "location": loc,
    }


def _day(iso: str) -> float:
    from datetime import datetime
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").timestamp() / 86400.0
    except (ValueError, TypeError):
        return 0.0


def _location(sensor_id: str, mapping: dict[str, Any]) -> dict[str, Any]:
    rec = mapping.get(sensor_id, {})
    space = rec.get("space_id") or None
    return {
        "space_id": space,
        "location_status": rec.get("location_status") or (
            "MAPPED" if space else "UNKNOWN_LOCATION"),
        "location_verified": bool(rec.get("location_verified", False)),
    }


def build_payload(analyses: list[dict[str, Any]],
                  mapping: dict[str, Any] | None = None) -> dict[str, Any]:
    import telemetry_anomaly as ta
    mapping = mapping if mapping is not None else ta.load_mapping()
    groups = _device_groups(analyses)
    starts = [a["first_timestamp"] for a in analyses if a["first_timestamp"]]
    ends = [a["last_timestamp"] for a in analyses if a["last_timestamp"]]
    span = (max(_day(e) for e in ends) - min(_day(s) for s in starts)
            if starts and ends else 0.0)
    devices = [sensor_health(sid, chans, span, mapping)
               for sid, chans in sorted(groups.items())]
    statuses = Counter(d["health_status"] for d in devices)
    issue_types = Counter()
    for d in devices:
        for i in d["issues"]:
            issue_types[i["type"]] += 1
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "summary": {
            "devices": len(devices),
            "health_status_distribution": dict(sorted(statuses.items())),
            "issue_type_counts": dict(sorted(issue_types.items())),
            "total_anomaly_candidates": sum(d["anomaly_candidates"]
                                            for d in devices),
        },
        "devices": devices,
    }


def write_health(analyses: list[dict[str, Any]],
                 mapping: dict[str, Any] | None = None,
                 out_dir: str | None = None) -> str:
    out = out_dir or cfg.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "sensor_health.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_payload(analyses, mapping), f, indent=2,
                  ensure_ascii=False)
    return path