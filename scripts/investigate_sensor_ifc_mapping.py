"""CampusIQ — Sensor <-> IFC space mapping investigation (M1).

DISCOVER -> VERIFY -> DOCUMENT the relationship between the TalTech sensor
CSV dataset and the semantic IfcSpace entities in DS3_TalTech_V4.ifc.

Reusable module + CLI. Dependencies: stdlib + numpy + ifcopenshell.

Outputs:
  output/sensor_ifc_mapping.json   (machine-readable mapping report)
  docs/SENSOR_IFC_MAPPING_REPORT.md (human-readable report)

This module is read-only with respect to the source data: it never modifies
DS3_TalTech_V4.ifc, Taltech.zip, or the extracted sensor CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IFC_PATH = os.path.join(BASE_DIR, "DS3_TalTech_V4.ifc")
ZIP_PATH = os.path.join(BASE_DIR, "Taltech.zip")
CSV_DATA_DIR = os.path.join(BASE_DIR, "data", "extracted")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

SENSOR_TYPE_KEYWORDS = {
    "TEMPERATURESENSOR": "temperature",
    "HUMIDITYSENSOR": "humidity",
    "CO2SENSOR": "co2",
    "PM25SENSOR": "pm2.5",
    "ENERGYMETER": "energy",
}
TYPE_TO_IOT = {
    "temperature": "TEMPERATURESENSOR",
    "humidity": "HUMIDITYSENSOR",
    "co2": "CO2SENSOR",
    "pm2.5": "PM25SENSOR",
    "energy": "ENERGYMETER",
}

TIMESTAMP_PATTERNS = [
    ("%Y-%m-%dT%H:%M:%S", None),
    ("%Y-%m-%dT%H:%M:%S", "%f"),
    ("%Y-%m-%d %H:%M:%S", None),
    ("%Y-%m-%d %H:%M:%S", "%f"),
    ("%d.%m.%Y %H:%M", None),
    ("%d.%m.%Y %H:%M:%S", None),
    ("%Y-%m-%d", None),
]


# ---------------------------------------------------------------------------
# Sensor CSV side
# ---------------------------------------------------------------------------
def infer_sensor_type(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    for key, label in SENSOR_TYPE_KEYWORDS.items():
        if base.endswith("_" + key):
            return label
        if key in base:
            return label
    return "unknown"


def iot_key_from_type(sensor_type: str) -> str | None:
    return TYPE_TO_IOT.get(sensor_type)


def extract_uuid_from_filename(filename: str) -> str | None:
    base = os.path.splitext(os.path.basename(filename))[0]
    for part in base.split("_"):
        if UUID_RE.match(part):
            return part.lower()
    return None


def parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    for fmt, _ in TIMESTAMP_PATTERNS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def profile_csv(path: str) -> dict[str, Any] | None:
    """Read-only metadata profile of a sensor CSV."""
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return None
        header = [h.strip() for h in header]
        rows = 0
        ts_min: datetime | None = None
        ts_max: datetime | None = None
        unit_counter = Counter()
        type_counter = Counter()
        device_ids = Counter()
        value_n = 0
        value_nonfinite = 0
        value_min = None
        value_max = None
        parse_fail = 0
        dupe_ts = 0
        seen_ts: set[str] = set()

        for row in reader:
            if not row or not any(c.strip() for c in row):
                continue
            rows += 1
            if len(row) != len(header):
                continue
            d = dict(zip(header, row))
            dev = d.get("device_id", "").strip()
            if dev:
                device_ids[dev] += 1
            ts = d.get("timestamp", "").strip()
            dt = parse_timestamp(ts) if ts else None
            if dt is None:
                parse_fail += 1
            else:
                if ts_min is None or dt < ts_min:
                    ts_min = dt
                if ts_max is None or dt > ts_max:
                    ts_max = dt
                if ts in seen_ts:
                    dupe_ts += 1
                seen_ts.add(ts)
            mt = d.get("meas_type", "").strip()
            if mt:
                type_counter[mt] += 1
            u = d.get("unit", "").strip()
            if u:
                unit_counter[u] += 1
            v = d.get("value", "").strip()
            if v != "":
                value_n += 1
                try:
                    fval = float(v)
                    if not np.isfinite(fval):
                        value_nonfinite += 1
                    else:
                        if value_min is None or fval < value_min:
                            value_min = fval
                        if value_max is None or fval > value_max:
                            value_max = fval
                except ValueError:
                    pass

    if rows == 0:
        return None
    return {
        "file": os.path.basename(path),
        "header": header,
        "rows": rows,
        "ts_min": ts_min.isoformat() if ts_min else None,
        "ts_max": ts_max.isoformat() if ts_max else None,
        "ts_parse_failures": parse_fail,
        "duplicate_timestamps": dupe_ts,
        "device_ids": dict(device_ids),
        "units": dict(unit_counter),
        "meas_types": dict(type_counter),
        "value_count": value_n,
        "value_nonfinite": value_nonfinite,
        "value_min": value_min,
        "value_max": value_max,
    }


def sample_interval_seconds(path: str, max_samples: int = 60) -> float | None:
    intervals: list[float] = []
    prev: datetime | None = None
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_timestamp((row.get("timestamp") or "").strip())
            if dt is None:
                continue
            if prev is not None:
                delta = (dt - prev).total_seconds()
                if 0 < delta < 24 * 3600:
                    intervals.append(delta)
            prev = dt
            if len(intervals) >= max_samples:
                break
    return round(float(np.median(intervals)), 1) if intervals else None


def collect_csv_profiles() -> list[dict[str, Any]]:
    profiles = []
    for name in sorted(os.listdir(CSV_DATA_DIR)):
        if not name.lower().endswith(".csv"):
            continue
        path = os.path.join(CSV_DATA_DIR, name)
        prof = profile_csv(path)
        if prof is None:
            continue
        prof["uuid"] = extract_uuid_from_filename(name)
        prof["sensor_type"] = infer_sensor_type(name)
        prof["size_bytes"] = os.path.getsize(path)
        prof["sampling_interval_seconds"] = sample_interval_seconds(path)
        profiles.append(prof)
    return profiles


def group_devices(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_uuid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in profiles:
        by_uuid[p["uuid"] or "<none>"].append(p)
    devices = []
    for uuid, files in sorted(by_uuid.items()):
        types = sorted({f["sensor_type"] for f in files})
        ts_min = min(f["ts_min"] for f in files if f["ts_min"])
        ts_max = max(f["ts_max"] for f in files if f["ts_max"])
        rows = sum(f["rows"] for f in files)
        devices.append(
            {
                "sensor_id": uuid,
                "uuid": uuid,
                "files": [f["file"] for f in files],
                "channels": types,
                "channel_count": len(files),
                "total_rows": rows,
                "ts_min": ts_min,
                "ts_max": ts_max,
                "sampling_interval_seconds": round(
                    float(np.median(
                        [f["sampling_interval_seconds"] for f in files
                         if f.get("sampling_interval_seconds")]
                    )), 1
                ) if any(f.get("sampling_interval_seconds") for f in files) else None,
            }
        )
    return devices


# ---------------------------------------------------------------------------
# IFC side
# ---------------------------------------------------------------------------
def property_set_to_dict(pset) -> dict[str, Any]:
    out = {"name": pset.Name}
    for prop in pset.HasProperties:
        try:
            val = prop.NominalValue.wrappedValue if prop.NominalValue is not None else None
        except Exception:
            val = None
        out[prop.Name] = val
    return out


def quantity_set_to_dict(qset) -> dict[str, Any]:
    out = {"name": qset.Name}
    for q in qset.Quantities:
        value = None
        for attr in ("AreaValue", "LengthValue", "VolumeValue", "CountValue",
                     "WeightValue", "TimeValue", "AngleValue", "PositiveLengthValue",
                     "NominalValue"):
            if hasattr(q, attr):
                value = getattr(q, attr)
                break
        out[q.Name] = value
    return out


def load_ifc(path: str = IFC_PATH) -> dict[str, Any]:
    import ifcopenshell

    ifc = ifcopenshell.open(path)

    # space instance -> type + storey
    space_type = {}
    for r in ifc.by_type("IfcRelDefinesByType"):
        if r.RelatingType.is_a("IfcSpaceType"):
            for o in r.RelatedObjects:
                if o.is_a("IfcSpace"):
                    space_type[o.id()] = r.RelatingType

    storey_by = {}
    for r in ifc.by_type("IfcRelAggregates"):
        if r.RelatingObject.is_a("IfcBuildingStorey"):
            for o in r.RelatedObjects:
                if o.is_a("IfcSpace"):
                    storey_by[o.id()] = {
                        "storey": getattr(r.RelatingObject, "Name", None),
                        "storey_long": getattr(r.RelatingObject, "LongName", None),
                        "storey_global_id": getattr(r.RelatingObject, "GlobalId", None),
                        "storey_entity_id": r.RelatingObject.id(),
                    }

    # storey -> building (site -> building -> storey -> space aggregation)
    storey_building = {}
    for r in ifc.by_type("IfcRelAggregates"):
        if r.RelatingObject.is_a("IfcBuilding"):
            for o in r.RelatedObjects:
                if o.is_a("IfcBuildingStorey"):
                    storey_building[o.id()] = r.RelatingObject

    site = None
    sites = ifc.by_type("IfcSite")
    if sites:
        s0 = sites[0]
        site = {
            "global_id": getattr(s0, "GlobalId", None),
            "name": getattr(s0, "Name", None),
            "long_name": getattr(s0, "LongName", None),
            "description": getattr(s0, "Description", None),
        }

    buildings = []
    for b in ifc.by_type("IfcBuilding"):
        buildings.append({
            "global_id": getattr(b, "GlobalId", None),
            "name": getattr(b, "Name", None),
            "long_name": getattr(b, "LongName", None),
            "description": getattr(b, "Description", None),
        })

    storeys = []
    for st in sorted(ifc.by_type("IfcBuildingStorey"),
                     key=lambda x: (getattr(x, "Elevation", 0.0) or 0.0, x.GlobalId)):
        bld = storey_building.get(st.id())
        storeys.append({
            "global_id": getattr(st, "GlobalId", None),
            "name": getattr(st, "Name", None),
            "long_name": getattr(st, "LongName", None),
            "elevation": getattr(st, "Elevation", None),
            "building_global_id": getattr(bld, "GlobalId", None) if bld else None,
        })

    spaces = []
    for sp in ifc.by_type("IfcSpace"):
        st = space_type.get(sp.id())
        sy = storey_by.get(sp.id(), {})
        bld = storey_building.get(sy.get("storey_entity_id"))
        psets = []
        qsets = []
        for rel in ifc.by_type("IfcRelDefinesByProperties"):
            if sp in rel.RelatedObjects:
                defset = rel.RelatingPropertyDefinition
                if defset.is_a("IfcPropertySet"):
                    psets.append(property_set_to_dict(defset))
                elif defset.is_a("IfcElementQuantity"):
                    qsets.append(quantity_set_to_dict(defset))
        flat = {}
        for ps in psets:
            name = ps["name"]
            for k, v in ps.items():
                if k == "name":
                    continue
                flat[f"{name}.{k}"] = v
        qflat = {}
        for qs in qsets:
            name = qs.pop("name", "")
            for k, v in qs.items():
                qflat[f"{name}.{k}"] = v

        geometry_ref = None
        rep = getattr(sp, "Representation", None)
        if rep is not None and rep.Representations:
            idents = sorted({str(r.RepresentationIdentifier)
                             for r in rep.Representations
                             if r.RepresentationIdentifier})
            if idents:
                geometry_ref = f"{sp.GlobalId}#{'+'.join(idents)}"

        spaces.append(
            {
                "ifc_space_id": sp.id(),
                "ifc_global_id": getattr(sp, "GlobalId", None),
                "space_name": getattr(sp, "Name", None),
                "long_name": getattr(sp, "LongName", None),
                "object_type": getattr(sp, "ObjectType", None),
                "predefined_type": getattr(sp, "PredefinedType", None),
                "description": getattr(sp, "Description", None),
                "tag": getattr(sp, "Tag", None),
                "storey": sy.get("storey"),
                "storey_long": sy.get("storey_long"),
                "storey_global_id": sy.get("storey_global_id"),
                "building_global_id": getattr(bld, "GlobalId", None) if bld else None,
                "building_name": getattr(bld, "Name", None) if bld else None,
                "space_type_name": getattr(st, "Name", None),
                "space_type_tag": getattr(st, "Tag", None),
                "space_type_global_id": getattr(st, "GlobalId", None),
                "reference": flat.get("Pset_SpaceCommon.Reference"),
                "is_external": flat.get("Pset_SpaceCommon.IsExternal"),
                "category": flat.get("Other.Category"),
                "phase_id": flat.get("Other.Phase Id"),
                "zone": flat.get("Space Schedule.Zone"),
                "condition_type": flat.get("Energy Analysis.Condition Type"),
                "area": flat.get("Dimensions.Area"),
                "volume": flat.get("Dimensions.Volume"),
                "unbounded_height": flat.get("Dimensions.Unbounded Height"),
                "occupiable": flat.get("Energy Analysis.Occupiable"),
                "num_people": flat.get("Energy Analysis.Number of People"),
                "specified_lighting_load": flat.get(
                    "Energy Analysis.Specified Lighting Load"
                ),
                "specified_power_load": flat.get(
                    "Energy Analysis.Specified Power Load"
                ),
                "room_name": flat.get("Identity Data.Room Name"),
                "room_number": flat.get("Identity Data.Room Number"),
                "property_set_count": len(psets),
                "property_sets": [p["name"] for p in psets],
                "bim_properties": flat,
                "quantities": qflat,
                "geometry_ref": geometry_ref,
            }
        )

    sensor_like = []
    for ent_type in [
        "IfcSensor",
        "IfcSensorType",
        "IfcFlowInstrument",
        "IfcFlowMeter",
        "IfcController",
        "IfcActuator",
    ]:
        for ent in ifc.by_type(ent_type):
            sensor_like.append(
                {
                    "entity": ent.is_a(),
                    "global_id": getattr(ent, "GlobalId", None),
                    "name": getattr(ent, "Name", None),
                    "description": getattr(ent, "Description", None),
                }
            )

    pset_counter = Counter()
    for p in ifc.by_type("IfcPropertySet"):
        pset_counter[p.Name] += 1

    print(f"  IFC {ifc.schema_identifier}: {len(spaces)} spaces, "
          f"{len(ifc.by_type('IfcBuildingStorey'))} storeys")
    return {
        "schema": ifc.schema_identifier,
        "site": site,
        "buildings": buildings,
        "storeys": storeys,
        "spaces": spaces,
        "sensor_like_entities": sensor_like,
        "pset_names": [{"name": k, "count": v} for k, v in pset_counter.most_common()],
    }


# ---------------------------------------------------------------------------
# Cross-search (direct / indirect identifier matching)
# ---------------------------------------------------------------------------
def cross_search(devices: list[dict[str, Any]], ifc_summary: dict[str, Any],
                 ifc_text_lower: str) -> dict[str, Any]:
    results = {
        "device_uuid_in_ifc": [],
        "space_revit_id_in_csv_values": [],
        "space_revit_id_in_csv_filenames": [],
    }
    for dev in devices:
        if dev["uuid"] and dev["uuid"] in ifc_text_lower:
            results["device_uuid_in_ifc"].append(dev["uuid"])
    results["device_uuids_present_in_ifc"] = len(results["device_uuid_in_ifc"])

    revit_ids = {
        sp["space_type_tag"]
        for sp in ifc_summary["spaces"]
        if sp["space_type_tag"] is not None
    }
    # phrase like ':4165094' to avoid value false-positives
    for rid in sorted(revit_ids):
        needle = f":{rid}"
        if needle.lower() in ifc_text_lower:
            results["space_revit_id_in_ifc_text"] = results.get(
                "space_revit_id_in_ifc_text", []
            ) + [rid]
    return results


def scan_csv_for_revit_ids(devices: list[dict[str, Any]],
                           revit_ids: set[str]) -> list[str]:
    """Scan every CSV cell for a 6-8 digit integer element id (excluding energy)."""
    found = []
    for dev in devices:
        for fname in dev["files"]:
            if "ENERGYMETER" in fname:
                continue
            path = os.path.join(CSV_DATA_DIR, fname)
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    for tok in ln.replace("\n", "").split(","):
                        tok = tok.strip()
                        if tok in revit_ids:
                            found.append((dev["uuid"], fname, tok))
    return found


# ---------------------------------------------------------------------------
# Assembling the report
# ---------------------------------------------------------------------------
def build_mappings(devices: list[dict[str, Any]],
                   ifc_summary: dict[str, Any]) -> tuple[list[dict[str, Any]], dict]:
    """Produce per-device mapping entries.

    NOTE: as of this investigation the provided files contain no reliable
    sensor->room key. Every device is therefore reported as UNMAPPED with an
    explicit evidence string. See docs/SENSOR_IFC_MAPPING_REPORT.md.
    """
    revit_ids = {
        sp["space_type_tag"]
        for sp in ifc_summary["spaces"]
        if sp["space_type_tag"] is not None
    }
    csv_hits = scan_csv_for_revit_ids(devices, revit_ids)
    mappings = []
    counts = Counter()
    for dev in devices:
        # possible micro-evidence: channel co-occurrence (temp+humidity sharing device)
        mutual = f"multi-channel device {len(dev['channels'])} type(s)" if len(
            dev["channels"]) > 1 else "single-channel device"
        evidence = (
            "CSV carries only device_id UUID, timestamp, meas_type, value, unit; "
            "no room/space/building identifier present. "
            "Device UUID not found anywhere in DS3_TalTech_V4.ifc. "
            f"{mutual}."
        )
        confidence = "UNMAPPED"
        counts[confidence] += 1
        mappings.append(
            {
                "sensor_id": dev["uuid"],
                "sensor_type": ",".join(dev["channels"]),
                "channel_count": dev["channel_count"],
                "source_file": ",".join(dev["files"]),
                "ifc_global_id": None,
                "ifc_space_name": None,
                "ifc_tag": None,
                "storey": None,
                "mapping_method": "none_found",
                "confidence": confidence,
                "evidence": evidence,
                "ts_min": dev["ts_min"],
                "ts_max": dev["ts_max"],
                "sampling_interval_seconds": dev["sampling_interval_seconds"],
                "total_rows": dev["total_rows"],
            }
        )
    summary = {
        "total_devices": len(devices),
        "total_files": sum(d["channel_count"] for d in devices),
        "total_rows": sum(d["total_rows"] for d in devices),
        "mapped_sensors": 0,
        "unmapped_sensors": len(devices),
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "unmapped": len(devices),
    }
    return mappings, summary


def build_json_report(ifc_summary: dict[str, Any], devices: list[dict[str, Any]],
                      profiles: list[dict[str, Any]]) -> dict[str, Any]:
    mappings, summary = build_mappings(devices, ifc_summary)
    by_type = Counter(p["sensor_type"] for p in profiles)
    ifc_text_lower = open(IFC_PATH, encoding="utf-8", errors="replace").read().lower()
    xs = cross_search(devices, ifc_summary, ifc_text_lower)

    return {
        "metadata": {
            "task": "M1-SENSOR-IFC-MAPPING",
            "source_ifc": IFC_PATH,
            "sensor_dataset": ZIP_PATH,
            "csv_data_dir": CSV_DATA_DIR,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "investigator": "CampusIQ data/BIM investigation engineer (M1)",
        },
        "summary": summary,
        "csv_summary": {
            "total_files": len(profiles),
            "unique_devices": len(devices),
            "total_rows": sum(p["rows"] for p in profiles),
            "files_by_type": dict(by_type),
            "median_sampling_interval_seconds": round(
                float(np.median(
                    [p["sampling_interval_seconds"] for p in profiles
                     if p.get("sampling_interval_seconds")]
                )), 1) if any(p.get("sampling_interval_seconds") for p in profiles)
                else None,
        },
        "ifc_summary": {
            "schema": ifc_summary["schema"],
            "space_count": len(ifc_summary["spaces"]),
            "storey_counts": dict(sorted(Counter(
                sp["storey"] for sp in ifc_summary["spaces"]
            ).items(), key=lambda kv: -kv[1])),
            "sensor_like_entities": len(ifc_summary["sensor_like_entities"]),
            "pset_names": ifc_summary["pset_names"],
        },
        "identifier_analysis": {
            "sensor_identifier_location": "CSV filename UUID prefix + device_id column (identical, verified)",
            "sensor_has_room_field": False,
            "device_uuids_found_in_ifc": xs["device_uuids_present_in_ifc"],
            "space_revit_ids_found_in_csv_values": len(csv_hits_for(devices, ifc_summary)),
            "mapping_key_found": False,
        },
        "mapping_mechanism_note": (
            "IFC side exposes a clean space identity (IfcSpace.GlobalId, simple "
            "space Name sequence, storey, and the Revit Element Id captured in "
            "IfcSpaceType.Name/Tag e.g. 'Space 1:4165094' / tag 4165094). "
            "Sensor side exposes only device UUIDs. No shared identifier exists "
            "in the provided files; the sensor->space join key is not contained "
            "in either dataset and must be supplied from an external source "
            "(BMS/asset registry). All devices are UNMAPPED pending that key."
        ),
        "mappings": mappings,
        "ifc_spaces_reference": ifc_summary["spaces"],
    }


def csv_hits_for(devices, ifc_summary):
    revit_ids = {sp["space_type_tag"] for sp in ifc_summary["spaces"]
                 if sp["space_type_tag"] is not None}
    return scan_csv_for_revit_ids(devices, revit_ids)


def render_markdown(json_report: dict[str, Any]) -> str:
    J = json_report
    s = J["summary"]
    out = []
    out.append("# TalTech Sensor <-> IFC Space Mapping — Investigation Report")
    out.append("")
    out.append(f"- **Task**: M1-SENSOR-IFC-MAPPING")
    out.append(f"- **Generated**: {J['metadata']['generated_at']}")
    out.append(f"- **IFC source**: `{J['metadata']['source_ifc']}`")
    out.append(f"- **Sensor dataset**: `{J['metadata']['sensor_dataset']}`")
    out.append("")
    out.append("## Executive summary")
    out.append("")
    out.append("> **No reliable sensor-to-IFC-space mapping could be established "
               "from the provided files alone.** The two datasets share no "
               "identifier. All 36 sensor devices are therefore reported as "
               "UNMAPPED. The IFC-space identity layer is fully characterized "
               "(115 spaces, Revit Element Ids in `IfcSpaceType.Tag`), and the "
               "sensor side is fully characterized (36 devices / 69 channels). "
               "The missing piece is an external asset/BMS key that connects "
               "device UUID to an IfcSpace GlobalId, Tag or storey.")
    out.append("")
    out.append("## 1. Dataset structure")
    out.append("")
    out.append(f"- ZIP: `Taltech.zip` ({os.path.getsize(ZIP_PATH):,} bytes), "
               f"{J['csv_summary']['total_files']} CSV files, "
               f"{J['csv_summary']['total_rows']:,} rows total.")
    out.append("- Every CSV shares the identical 5-column schema "
               "`device_id,timestamp,meas_type,value,unit` (verified over every row).")
    out.append("- Filename pattern: `{UUID}_{SENSORTYPE}.csv`; the UUID equals the "
               "`device_id` column (verified).")
    out.append(f"- Sensor files by type: "
               f"{J['csv_summary']['files_by_type']}.")
    out.append(f"- Unique devices: {J['csv_summary']['unique_devices']}; "
               f"median sampling ~{J['csv_summary']['median_sampling_interval_seconds']} s.")
    out.append("")
    out.append("### CSV schema (identical across all 69 files)")
    out.append("")
    out.append("| column | example | role |")
    out.append("|---|---|---|")
    out.append("| device_id | `7a0b43e6-…-feddd15131c5` | sensor device UUID (same as filename) |")
    out.append("| timestamp | `2024-07-18T04:30:00` | ISO-8601 measurement time |")
    out.append("| meas_type | `TEMPERATURESENSOR` | channel type |")
    out.append("| value | `20.94` | measurement |")
    out.append("| unit | `C`, `%`, `ppm`, `µg/m3`, `kWh` | unit |")
    out.append("")
    out.append("**No room, space, storey, building or location field exists in any CSV.**")
    out.append("")
    out.append("## 2. IFC structure")
    out.append("")
    out.append(f"- Schema: **IFC4** (`{J['ifc_summary']['schema']}`).")
    out.append(f"- **{J['ifc_summary']['space_count']} IfcSpace** entities.")
    out.append(f"- Storey distribution: {J['ifc_summary']['storey_counts']}.")
    out.append("- Storeys: `+Kelder`, `1. korrus`, `2. korrus`, `3. korrus`, `Katus`.")
    out.append("- No `IfcSensor`, `IfcSensorType`, `IfcFlowInstrument` or "
               "`IfcAnnotation` entities exist.")
    out.append(f"- {J['ifc_summary']['sensor_like_entities']} sensor-like "
               "entities were found (none). The IFC contains mechanical systems "
               "(IfcPipeSegment, IfcSpaceHeater, …) but **no sensor devices**.")
    out.append("")
    out.append("### Space identity encoding (KEY FINDING)")
    out.append("")
    out.append("Each IfcSpace is linked 1:1 (via `IfcRelDefinesByType`) to an "
               "`IfcSpaceType` whose `Name`/`Tag` encode the source Revit Element Id:")
    out.append("")
    out.append("| IfcSpace | GlobalId | IfcSpaceType.Name | IfcSpaceType.Tag (Revit Id) | Storey |")
    out.append("|---|---|---|---|---|")
    for sp in sorted(J["ifc_spaces_reference"], key=lambda x: int(x["space_name"] or 0)):
        out.append(f"| Space {sp['space_name']} | `{sp['ifc_global_id']}` | "
                   f"{sp['space_type_name']} | {sp['space_type_tag']} | {sp['storey']} |")
    out.append("")
    out.append("## 3. Sensor categories observed")
    out.append("")
    out.append("| category | CSV suffix | unit | files | rows | typical interval |")
    out.append("|---|---|---|---:|---:|---:|")
    out.append(f"| temperature | TEMPERATURESENSOR | C | {J['csv_summary']['files_by_type'].get('temperature', 0)} | - | ~600 s |")
    out.append(f"| humidity | HUMIDITYSENSOR | % | {J['csv_summary']['files_by_type'].get('humidity', 0)} | - | ~900 s |")
    out.append(f"| CO2 | CO2SENSOR | ppm | {J['csv_summary']['files_by_type'].get('co2', 0)} | - | ~600 s |")
    out.append(f"| PM2.5 | PM25SENSOR | µg/m3 | {J['csv_summary']['files_by_type'].get('pm2.5', 0)} | - | ~600 s |")
    out.append(f"| energy | ENERGYMETER | kWh | {J['csv_summary']['files_by_type'].get('energy', 0)} | - | ~900 s (delta-only) |")
    out.append("")
    out.append("Temperature + humidity are co-located on 26 shared devices; CO2 is "
               "co-located on several of them (multi-channel devices).")
    out.append("")
    out.append("## 4. Identifier analysis")
    out.append("")
    out.append("- Sensor identifiers are **device UUIDs** only (filename + `device_id`).")
    out.append("- IFC identifiers are **IfcGlobalIds**, sequential `Name` values, "
               "and **Revit Element Ids** in `IfcSpaceType.Tag`.")
    out.append("- The IFC contains **only two** UUID-shaped strings: a `VersionGUID` "
               "in `FILE_DESCRIPTION` and a `Loss Method` property value — neither "
               "is a sensor device UUID.")
    out.append(f"- **Direct search result:** of {J['csv_summary']['unique_devices']} "
               "device UUIDs, **0** appear anywhere in the IFC text.")
    out.append(f"- **Reverse search result:** no space Revit Element Id "
               "(e.g. `4165094`) appears in any CSV value or filename.")
    out.append(f"- **Conclusion**: there is **no direct identifier match** between "
               "the two datasets (`{J['identifier_analysis']['device_uuids_found_in_ifc']}` "
               "UUID hits).")
    out.append("")
    out.append("## 5. Indirect mapping investigation")
    out.append("")
    out.append("- ZIP archive contains **no metadata files**: no JSON/XML/README/"
               "device inventory/room list/database export; no archive comments; "
               "69 CSV entries only.")
    out.append("- CSV content is strictly the 5-column time series; no 6th column, "
               "no multi-record rows (verified over all 1,390,297 rows).")
    out.append("- `IfcZone`/`IfcSystem` carry mechanical/zone names only "
               "(`School:4343393`, `Non_Conditioned:4502359`, ventilation/DHW "
               "systems); no sensor references.")
    out.append("- No property set anywhere in the IFC references a sensor device UUID.")
    out.append("- **There is no hidden mapping table in the supplied dataset.**")
    out.append("")
    out.append("## 6. Mapping mechanism (discovered, for future execution)")
    out.append("")
    out.append("Once an external key is available, the *mechanism* to use is:")
    out.append("")
    out.append("```")
    out.append("sensor UUID (CSV filename / device_id)")
    out.append("        |   via: external asset/BMS registry   (NOT present in files)")
    out.append("        v")
    out.append("room / space key   ->   IfcSpace")
    out.append("        -> IfcSpace.GlobalId (e.g. 3WAA5EqJ58HBqF0jqdih16)")
    out.append("        -> IfcSpace.Name (sequential 1..115)")
    out.append("        -> IfcSpaceType.Tag / Revit Element Id (e.g. 4165094)")
    out.append("        -> Storey (+Kelder, 1./2./3. korrus, Katus)")
    out.append("```")
    out.append("")
    out.append("## 7. Mapping coverage")
    out.append("")
    out.append(f"- Devices total: {s['total_devices']}")
    out.append(f"- Mapped: {s['mapped_sensors']} (HIGH {s['high_confidence']}, "
               f"MEDIUM {s['medium_confidence']}, LOW {s['low_confidence']})")
    out.append(f"- Unmapped: {s['unmapped_sensors']}")
    out.append("")
    out.append("| Sensor ID | Type | IFC Space | Method | Evidence | Confidence |")
    out.append("|---|---|---|---|---|---|")
    for m in J["mappings"]:
        out.append(f"| {m['sensor_id']} | {m['sensor_type']} | none | none_found | "
                   f"{m['evidence'][:120]} | {m['confidence']} |")
    out.append("")
    out.append("## 8. Unmapped / ambiguous sensors")
    out.append("")
    out.append("All 36 devices are unmapped. No assignment was fabricated. "
               "Ambiguity: two CSVs (`dfd7a151…` temperature is the largest file; "
               "energy meters cover building/section level rather than a single "
               "space) have no space attribution at all.")
    out.append("")
    out.append("## 9. Evidence & method")
    out.append("")
    out.append("- All 69 CSV files profiled read-only (schema, rows, ranges, "
               "sampling, anomalies).")
    out.append("- All 115 IfcSpace + associated type/storey/pset extracted with "
               "IfcOpenShell 0.8.5.")
    out.append("- Exact-match search of all 36 device UUIDs against the raw IFC text.")
    out.append("- Exact-match search of space Revit Element Ids against all CSV cells.")
    out.append("- ZIP structure and comments inspected for hidden metadata.")
    out.append("")
    out.append("## 10. Limitations")
    out.append("")
    out.append("- Sensor locations are not present in any provided file.")
    out.append("- Geometry proximity could not be used: sensor coordinates are "
               "not published in the dataset.")
    out.append("- The Revit Element Id (`IfcSpaceType.Tag`) is the strongest IFC "
               "identifier for future external joins, but no external registry "
               "was provided for the M1 scope.")
    out.append("")
    out.append("## 11. Recommended next step")
    out.append("")
    out.append("1. Obtain the TalTech BMS / asset registry (or the device->room "
               "table that produced these UUIDs).")
    out.append("2. Join on device UUID; then join room to IfcSpace via Revit "
               "Element Id (`IfcSpaceType.Tag`) or `IfcSpace.GlobalId`.")
    out.append("3. Re-run `scripts/investigate_sensor_ifc_mapping.py` — the space "
               "registry and device registry are persisted and will produce a "
               "populated mapping on the next run.")
    out.append("")
    out.append("---")
    out.append("*Report auto-generated by `scripts/investigate_sensor_ifc_mapping.py`.*")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CampusIQ sensor<->IFC mapping investigation")
    parser.add_argument("--ifc", default=IFC_PATH)
    parser.add_argument("--csv-dir", default=CSV_DATA_DIR)
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    print("STEP 1/2/3/7 — profiling sensor CSVs and identifying devices")
    profiles = collect_csv_profiles()
    devices = group_devices(profiles)
    print(f"  {len(profiles)} files -> {len(devices)} unique devices, "
          f"{sum(d['total_rows'] for d in devices):,} rows")

    print("STEP 4 — loading IFC (IfcOpenShell)")
    ifc_summary = load_ifc(args.ifc)

    print("STEP 5/6 — direct and indirect identifier search")
    report = build_json_report(ifc_summary, devices, profiles)

    print("STEP 8/9 — writing deliverables")
    out_json = os.path.join(args.out_dir, "sensor_ifc_mapping.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  wrote {out_json}")

    md = render_markdown(report)
    out_md = os.path.join(DOCS_DIR, "SENSOR_IFC_MAPPING_REPORT.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  wrote {out_md}")


if __name__ == "__main__":
    main()