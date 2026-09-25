"""CampusIQ — anomaly intelligence (M5).

Takes the flagged, persistence-filtered candidates from telemetry_profile and
enriches them with severity, category (DATA_QUALITY vs ENVIRONMENTAL vs
RESOURCE), human-readable explanation, and the M4 mapping's location context.
Deterministic; location comes only from the M4 linkage file (UNKNOWN unless
M4 says otherwise).

Severity rule:
  base = classify_severity(primary contextual score). A one-band escalation
  applies when the value is a large multiple of the channel's median
  (magnitude_ratio >= 3) — catches e.g. pm2.5/CO2 episodes whose hour-of-day
  residual score is modest even though the event is severe. MAD/global robust
  z-scores are reported per record (`signals`, `severity_score`) for
  transparency but never drive the band: on tight/zero-inflated distributions
  they explode for routine events (e.g. 4x on CO2), which would mislabel
  ordinary readings as CRITICAL.
"""

from __future__ import annotations

import json
import os
from typing import Any

import telemetry_config as cfg

CATEGORY_RESOURCE_TYPES = {"energy"}
QUALITY_CATEGORY = "DATA_QUALITY"

_SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _escalate_one(sev: str) -> str:
    idx = _SEVERITY_ORDER.index(sev)
    return _SEVERITY_ORDER[min(idx + 1, len(_SEVERITY_ORDER) - 1)]


def load_mapping(out_dir: str | None = None) -> dict[str, Any]:
    path = os.path.join(out_dir or cfg.OUTPUT_DIR, "sensor_space_mapping.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    by_id: dict[str, Any] = {}
    records = data.get("sensors") or data.get("mappings") or data
    if isinstance(records, list):
        for rec in records:
            sid = rec.get("sensor_id") or rec.get("device_id") or rec.get("id")
            if sid:
                by_id[sid] = rec
    elif isinstance(records, dict):
        for sid, rec in records.items():
            if isinstance(rec, dict):
                by_id[sid] = rec
    return by_id


def location_context(sensor_id: str, mapping: dict[str, Any]) -> dict[str, Any]:
    rec = mapping.get(sensor_id, {})
    space = rec.get("space_id") or None
    status = rec.get("location_status") or (
        "MAPPED" if space else "UNKNOWN_LOCATION")
    return {
        "space_id": space,
        "location_status": status,
        "location_verified": bool(rec.get("location_verified", False)),
        "mapping_status": rec.get("status") or rec.get("mapping_status") or "UNRESOLVED",
        "mapping_confidence": rec.get("confidence"),
        "mapping_method": rec.get("method") or rec.get("method_summary") or None,
    }


def severity_for(record: dict[str, Any]) -> str:
    base = cfg.classify_severity(float(record.get("score") or 0.0))
    ratio = record.get("magnitude_ratio") or 0.0
    value = record.get("value")
    expected = record.get("expected")
    if (ratio >= 3.0 and value is not None and expected is not None
            and value > expected):
        return _escalate_one(base)
    return base


def category_for(record: dict[str, Any]) -> str:
    limits = cfg.limits_for(record.get("measurement_type") or "")
    value = record.get("value")
    if limits and value is not None:
        lo, hi = limits
        if value < lo or value > hi:
            return QUALITY_CATEGORY
    if record.get("measurement_type") in CATEGORY_RESOURCE_TYPES:
        return "RESOURCE"
    return "ENVIRONMENTAL"


def explanation_for(record: dict[str, Any]) -> str:
    sid = (record.get("sensor_id") or "")[:8]
    m = record.get("measurement_type")
    ts = record.get("timestamp")
    val = record.get("value")
    unit = record.get("unit") or ""
    exp = record.get("expected")
    dev = record.get("deviation")
    score = record.get("score")
    method = record.get("method")
    run = record.get("persistence")
    return (
        f"Sensor {sid} reported {m}={val} {unit} at {ts}. Expected ~{exp} {unit} "
        f"from the {method} baseline (deviation {dev} {unit}, "
        f"statistical score {score}, persistence run {run})."
    )


def augment(record: dict[str, Any],
            mapping: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["severity"] = severity_for(record)
    out["category"] = category_for(record)
    out["explanation"] = explanation_for(record)
    out.update(location_context(record.get("sensor_id") or "", mapping))
    return out


def build_payload(analyses: list[dict[str, Any]],
                  mapping: dict[str, Any] | None = None) -> dict[str, Any]:
    mapping = mapping if mapping is not None else load_mapping()
    records: list[dict[str, Any]] = []
    total_candidates = 0
    capped_channels: list[str] = []
    for a in analyses:
        s = a.get("anomaly_summary", {})
        total_candidates += int(s.get("candidates_surviving") or 0)
        if s.get("capped_detail"):
            capped_channels.append(a["file"])
        for rec in a.get("anomalies", []):
            records.append(augment(rec, mapping))
    records.sort(key=lambda r: (r.get("timestamp") or "",
                                r.get("sensor_id") or "",
                                r.get("value") or 0))

    def count_by(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in records:
            k = str(r.get(key))
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    channels_with = sum(1 for a in analyses
                        if a.get("anomaly_summary", {}).get("candidates_surviving"))
    return {
        "task": cfg.TASK,
        "schema_version": cfg.SCHEMA_VERSION,
        "summary": {
            "total_candidates": total_candidates,
            "recorded_detail": len(records),
            "capped_channels": sorted(capped_channels),
            "channels_with_anomalies": channels_with,
            "by_severity": count_by("severity"),
            "by_category": count_by("category"),
            "by_method": count_by("method"),
            "by_measurement_type": count_by("measurement_type"),
            "by_location_status": count_by("location_status"),
        },
        "thresholds": {
            "candidate_z": cfg.ANOMALY["candidate_z"],
            "mad_candidate_z": cfg.ANOMALY["mad_candidate_z"],
            "extreme_isolated_z": cfg.ANOMALY["extreme_isolated_z"],
            "persistence_min": cfg.ANOMALY["persistence_min"],
            "severity_bands": cfg.ANOMALY["severity"],
            "note": "Operational configuration, NOT TalTech ground truth.",
        },
        "anomalies": records,
    }


def write_anomalies(analyses: list[dict[str, Any]],
                    mapping: dict[str, Any] | None = None,
                    out_dir: str | None = None) -> str:
    out = out_dir or cfg.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "anomalies.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_payload(analyses, mapping), f, indent=2,
                  ensure_ascii=False)
    return path