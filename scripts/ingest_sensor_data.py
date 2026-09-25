"""CampusIQ — sensor data ingestion (M3.1).

Normalizes the 69 sensor CSV channels / 36 devices from `Taltech.zip`
(extracted under `data/extracted`) into the CampusIQ canonical model.

Read-only w.r.t. the source data: raw CSVs and the ZIP are never modified.
No sensor-room mapping is invented: every device is registered with its
original UUID and an explicit UNRESOLVED SensorSpaceMapping (space_id null)
pending the external CIEM/BMS registry identified by M2.

TelemetryReading rows are NOT materialized into JSON (1.39M rows); the channel
manifest accounts for every channel/row with a documented streaming schema.

Reuses the M1 CSV profiler (`investigate_sensor_ifc_mapping`).

Outputs:
  output/sensors.json
  output/sensor_readings_manifest.json
  output/sensor_space_mapping.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import investigate_sensor_ifc_mapping as source  # noqa: E402
import linkage_engine  # noqa: E402   (canonical SensorSpaceMapping schema)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_DATA_DIR = source.CSV_DATA_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SOURCE_LABEL = "Taltech.zip (Zenodo 15782433) -> data/extracted"
TASK = "M3.1-CANONICAL-CAMPUS-FOUNDATION"
TELEMETRY_SCHEMA = ["sensor_id", "timestamp", "value", "unit", "quality"]


# ---------------------------------------------------------------------------
# Canonical sensor records
# ---------------------------------------------------------------------------
def build_sensors(devices: list[dict[str, Any]],
                  profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unit_by_uuid: dict[str, set[str]] = {}
    for p in profiles:
        unit_by_uuid.setdefault(p["uuid"], set()).update(p.get("units") or {})
    sensors = []
    for dev in sorted(devices, key=lambda d: d["uuid"]):
        uuid = dev["uuid"]
        channels = []
        for p in sorted([p for p in profiles if p.get("uuid") == uuid],
                        key=lambda p: (p["sensor_type"], p["file"])):
            meas_types = list((p.get("meas_types") or {}).keys())
            units = sorted(p.get("units") or {})
            channels.append(
                {
                    "channel_type": p["sensor_type"],
                    "meas_type": meas_types[0] if meas_types else None,
                    "unit": units[0] if units else None,
                    "file": p["file"],
                    "size_bytes": p["size_bytes"],
                    "rows": p["rows"],
                    "ts_min": p["ts_min"],
                    "ts_max": p["ts_max"],
                    "sampling_interval_seconds": p["sampling_interval_seconds"],
                }
            )
        units = sorted(unit_by_uuid.get(uuid, set()))
        sensors.append(
            {
                "sensor_id": uuid,
                "type": ",".join(dev["channels"]),
                "unit": ",".join(units),
                "source": SOURCE_LABEL,
                "status": "unmapped",
                "channels": channels,
                "channel_count": len(channels),
                "total_rows": dev["total_rows"],
                "ts_min": dev["ts_min"],
                "ts_max": dev["ts_max"],
                "sampling_interval_seconds": dev["sampling_interval_seconds"],
            }
        )
    return sensors


def build_manifest(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    channels = []
    for p in sorted(profiles, key=lambda x: x["file"]):
        meas_types = list((p.get("meas_types") or {}).keys())
        units = sorted(p.get("units") or {})
        channels.append(
            {
                "file": p["file"],
                "sensor_id": p["uuid"],
                "channel_type": p["sensor_type"],
                "meas_type": meas_types[0] if meas_types else None,
                "unit": units[0] if units else None,
                "rows": p["rows"],
                "size_bytes": p["size_bytes"],
                "ts_min": p["ts_min"],
                "ts_max": p["ts_max"],
                "sampling_interval_seconds": p["sampling_interval_seconds"],
            }
        )
    return {
        "task": TASK,
        "readings_location": "raw source CSVs under data/extracted (read-only); "
                             "TelemetryReading rows are NOT duplicated into JSON",
        "telemetry_reading_schema": {
            "columns": TELEMETRY_SCHEMA,
            "note": "quality is not present in the source CSVs; downstream "
                    "ingestors should mark rows as 'raw' until validated.",
        },
        "summary": {
            "channels": len(channels),
            "sensors": len({c["sensor_id"] for c in channels}),
            "files": len(channels),
            "total_rows": sum(c["rows"] for c in channels),
            "rows_by_type": dict(Counter(c["channel_type"] for c in channels)),
        },
        "channels": channels,
    }


def build_mappings(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canonical UNRESOLVED SensorSpaceMapping records (schema from linkage_engine)."""
    registry = [{"sensor_id": d["uuid"],
                 "sensor_type": ",".join(d["channels"])} for d in devices]
    return linkage_engine.build_unresolved_mappings(registry)


def build_outputs() -> dict[str, Any]:
    profiles = source.collect_csv_profiles()
    devices = source.group_devices(profiles)
    sensors = build_sensors(devices, profiles)
    manifest = build_manifest(profiles)
    mappings = build_mappings(devices)
    mapping_payload = linkage_engine.build_mapping_payload(sensors, mappings)
    payload = {
        "sensors.json": {"task": TASK, "summary": {
            "sensors": len(sensors),
            "devices": len(sensors),
            "channels": sum(s["channel_count"] for s in sensors),
        }, "sensors": sensors},
        "sensor_readings_manifest.json": manifest,
        "sensor_space_mapping.json": mapping_payload,
    }
    return payload


def write_outputs(payload: dict[str, Any], out_dir: str = OUTPUT_DIR) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for fname in ("sensors.json", "sensor_readings_manifest.json",
                  "sensor_space_mapping.json"):
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload[fname], f, indent=2, ensure_ascii=False, default=str)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CampusIQ canonical campus foundation — sensor ingestion")
    parser.add_argument("--csv-dir", default=CSV_DATA_DIR)
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    payload = build_outputs()
    paths = write_outputs(payload, args.out_dir)
    s = payload["sensors.json"]["summary"]
    m = payload["sensor_space_mapping.json"]["summary"]
    mm = payload["sensor_readings_manifest.json"]["summary"]
    print(f"  channels: {s['channels']} | devices: {s['sensors']} | "
          f"rows: {mm['total_rows']:,}")
    print(f"  mappings: {m['total']} (resolved {m['resolved']}, "
          f"unresolved {m['unresolved']})")
    for p in paths:
        print(f"  wrote {p}")


if __name__ == "__main__":
    main()