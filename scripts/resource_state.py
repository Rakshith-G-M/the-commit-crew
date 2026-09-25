"""CampusIQ — M6 campus resource state (Part 2 of Decision Intelligence).

Builds a canonical per-space resource state from the M4 IFC result
(``output/spaces.json``) plus the campus registry (storey/building context).

Everything here is a BIM **design/specification** value or a derived design
metric computed from BIM quantities (area, volume, capacity, lighting/power
density, airflow, loads). Nothing in this file is a measurement of real
consumption: there is no per-space sensor and no confirmed sensor->space
mapping, so ``measured_*`` fields are ``null`` and explicitly labelled as
unavailable. The distinction between BIM_DESIGN values and measured values is
kept explicit on every record (``metric_origin`` / ``is_measured``), and the
file-level ``availability`` block states clearly that no occupancy timetable
exists — availability is NOT fabricated here (it is surfaced as an explicit
external input to the allocation step).

Design intent: give the front-end and the recommendation engine (M7) a
uniform, location-verified inventory of what each space *is* per BIM, so that
capacity/allocation decisions can be evaluated against IFC geometry and design
values rather than guesses.
"""

from __future__ import annotations

import json
import math
from typing import Any

from telemetry_config import RESOURCE_STATE

TASK = "M6-CAMPUS-RESOURCE-STATE"
SCHEMA_VERSION = "campusiq.resource_state/v1"
ORIGIN_BIM = "BIM_DESIGN"
MEASURED_NOTE = (
    "No per-space consumption measurement exists in this dataset (all sensor "
    "mappings are UNRESOLVED and no space energy meter is linked). "
    "measured_* values are therefore null; BIM specification values are design "
    "values, NOT measured consumption."
)
NO_AVAILABILITY_NOTE = (
    "No occupancy timetable or space availability schedule exists in the "
    "dataset. Availability is NOT fabricated here; it must be supplied as an "
    "explicit external input to the allocation step."
)

_BIM_LOAD_KEYS = {
    "Energy Analysis.Specified Lighting Load",
    "Energy Analysis.Specified Power Load",
    "Energy Analysis.Specified Lighting Load per area",
    "Energy Analysis.Specified Power Load per area",
}
_BIM_FLOW_KEYS = {
    "Energy Analysis.Design Heating Load",
    "Energy Analysis.Design Cooling Load",
    "Mechanical - Flow.Specified Supply Airflow",
    "Mechanical - Flow.Specified Return Airflow",
    "Mechanical - Flow.Specified Exhaust Airflow",
    "Mechanical - Flow.Outdoor Air per Person",
    "Mechanical - Flow.Outdoor Air per Area",
    "Energy Analysis.Outdoor Air per Area",
    "Energy Analysis.Air Changes per Hour",
}


def _num(props: dict, key: str) -> float | None:
    v = props.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _norm_num(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _bim_design(bit: dict) -> dict:
    """A canonical BIM_DESIGN field wrapper — never labelled as measured."""
    return {
        "value": (_norm_num(bit.get("value")) if isinstance(bit, dict) else _norm_num(bit)),
        "unit": bit.get("unit") if isinstance(bit, dict) else None,
        "bim_property": bit.get("bim_property") if isinstance(bit, dict) else None,
        "metric_origin": ORIGIN_BIM,
        "is_measured": False,
    }


def space_resource(record: dict, storey: dict | None, building: dict | None, props: dict) -> dict:
    area = _num(props, "Dimensions.Area") or _norm_num(record.get("area_m2"))
    height = _num(props, "Dimensions.Unbounded Height") or _num(props, "Dimensions.Computation Height")
    volume = _num(props, "Dimensions.Volume") or _norm_num(record.get("volume_m3"))
    perimeter = _num(props, "Dimensions.Perimeter")
    area = area or _norm_num(record.get("area_m2"))

    design_cap = _num(props, "Energy Analysis.Number of People")
    area_pp = _num(props, "Energy Analysis.Area per Person")
    if design_cap is None and area_pp and area_pp > 0 and area and area > 0:
        design_cap = area / area_pp
    density = (design_cap / area) if (design_cap is not None and area) else None

    cond_type = props.get("Energy Analysis.Condition Type")
    zone = props.get("Energy Analysis.Zone")

    lighting_load = _num(props, "Energy Analysis.Specified Lighting Load")
    lighting_density = _num(props, "Energy Analysis.Specified Lighting Load per area")
    lighting_units = props.get("Energy Analysis.Lighting Load Units")
    power_load = _num(props, "Energy Analysis.Specified Power Load")
    power_density = _num(props, "Energy Analysis.Specified Power Load per area")
    power_units = props.get("Energy Analysis.Power Load Units")
    supply_flow = _num(props, "Mechanical - Flow.Specified Supply Airflow")
    return_flow = _num(props, "Mechanical - Flow.Specified Return Airflow")
    exhaust_flow = _num(props, "Mechanical - Flow.Specified Exhaust Airflow")
    outdoor_pp = _num(props, "Mechanical - Flow.Outdoor Air per Person")
    outdoor_area = _num(props, "Energy Analysis.Outdoor Air per Area") or _num(props, "Mechanical - Flow.Outdoor Air per Area")
    ach = _num(props, "Energy Analysis.Air Changes per Hour")
    design_heat = _num(props, "Energy Analysis.Design Heating Load")
    design_cool = _num(props, "Energy Analysis.Design Cooling Load")

    return {
        "space_id": record.get("space_id"),
        "building_id": record.get("building_id"),
        "storey_id": record.get("storey_id"),
        "building_name": (building or {}).get("name"),
        "storey_name": (storey or {}).get("name"),
        "ifc_global_id": record.get("ifc_global_id"),
        "ifc_name": record.get("ifc_name"),
        "ifc_long_name": record.get("ifc_long_name"),
        "ifc_tag": record.get("ifc_tag"),
        "predefined_type": record.get("predefined_type"),
        "space_name": props.get("Identity Data.Room Name") or record.get("ifc_name"),
        "space_number": props.get("Identity Data.Room Number") or record.get("ifc_tag"),
        "geometry": {
            "area_m2": round(area, 6) if area else None,
            "perimeter_m": round(perimeter, 6) if perimeter else None,
            "height_m": round(height, 6) if height else None,
            "volume_m3": round(volume, 6) if volume else None,
        },
        "occupancy": {
            "occupiable": bool(record.get("occupiable") is not False),
            "capacity_occupants": round(design_cap, 6) if design_cap else None,
            "area_per_occupant_m2": round(area_pp, 6) if area_pp else None,
            "max_density_ppl_per_m2": round(density, 6) if density else None,
            "design_conditioning": cond_type,
            "zone": zone,
        },
        "lighting": {
            **_bim_design({"value": lighting_load, "unit": lighting_units, "bim_property": "Energy Analysis.Specified Lighting Load"}),
            "density_w_per_m2": _bim_design({"value": lighting_density, "unit": "W/m2", "bim_property": "Energy Analysis.Specified Lighting Load per area"}),
        },
        "power": {
            **_bim_design({"value": power_load, "unit": power_units, "bim_property": "Energy Analysis.Specified Power Load"}),
            "density_w_per_m2": _bim_design({"value": power_density, "unit": "W/m2", "bim_property": "Energy Analysis.Specified Power Load per area"}),
        },
        "hvac": {
            "condition_type": cond_type,
            "zone": zone,
            "specified_supply_airflow_m3_s": _bim_design({"value": supply_flow, "unit": "L/s", "bim_property": "Mechanical - Flow.Specified Supply Airflow"}),
            "specified_return_airflow_m3_s": _bim_design({"value": return_flow, "unit": "L/s", "bim_property": "Mechanical - Flow.Specified Return Airflow"}),
            "specified_exhaust_airflow_m3_s": _bim_design({"value": exhaust_flow, "unit": "L/s", "bim_property": "Mechanical - Flow.Specified Exhaust Airflow"}),
            "outdoor_air_per_person_L_s": _bim_design({"value": outdoor_pp, "unit": "L/s/person", "bim_property": "Mechanical - Flow.Outdoor Air per Person"}),
            "outdoor_air_per_area_L_s_m2": _bim_design({"value": outdoor_area, "unit": "L/s/m2", "bim_property": "Energy Analysis.Outdoor Air per Area"}),
            "design_heating_load_w": _bim_design({"value": design_heat, "unit": "W", "bim_property": "Energy Analysis.Design Heating Load"}),
            "design_cooling_load_w": _bim_design({"value": design_cool, "unit": "W", "bim_property": "Energy Analysis.Design Cooling Load"}),
            "air_changes_per_hour": _bim_design({"value": ach, "unit": "ACH", "bim_property": "Energy Analysis.Air Changes per Hour"}),
        },
        "design_metrics": {
            "capacity_density_ppl_per_m2": round(density, 6) if density else None,
            "area_per_occupant_m2": round(area_pp, 6) if area_pp else None,
            "design_lighting_density_w_per_m2": (round(lighting_density, 6) if lighting_density else None),
            "design_power_density_w_per_m2": (round(power_density, 6) if power_density else None),
            "design_thermal_load_w_per_m2": (
                round((design_heat or 0.0) + (design_cool or 0.0), 6) / area
                if area
                else None
            ),
            "metric_origin": ORIGIN_BIM,
        },
        "measurements": {
            "measured_energy_consumption": None,
            "measured_consumption_available": False,
            "measurement_note": MEASURED_NOTE,
        },
        "bim_properties_source": "IFC_SPACE_PROPERTIES_M4",
        "bim_properties": props,
    }


def _storey_map(registry: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in registry.get("storeys", []):
        out[d["id"]] = d
    return out


def load_spaces(resource_state_path: str) -> list[dict]:
    """Return sorted ``spaces`` from a resource-state document."""
    doc = json.load(open(resource_state_path, encoding="utf-8"))
    return sorted(doc["spaces"], key=lambda s: s["space_id"])


def build_resource_state(spaces_path: str, registry_path: str, cfg: dict | None = None) -> dict:
    cfg = cfg or RESOURCE_STATE
    registry = json.load(open(registry_path, encoding="utf-8"))
    storeys = _storey_map(registry)
    buildings = {b["id"]: b for b in registry.get("buildings", [])}

    spaces_doc = json.load(open(spaces_path, encoding="utf-8"))
    spaces = spaces_doc["spaces"]

    records = []
    for s in spaces:
        records.append(
            space_resource(
                s,
                storeys.get(s.get("storey_id")),
                buildings.get(s.get("building_id")),
                s.get("bim_properties") or {},
            )
        )
    records.sort(key=lambda r: r["space_id"])

    storey_agg: dict[str, dict] = {}
    for r in records:
        sid = r["storey_id"] or "UNKNOWN"
        agg = storey_agg.setdefault(
            sid,
            {
                "storey_id": sid,
                "storey_name": r["storey_name"],
                "building_id": r["building_id"],
                "space_count": 0,
                "area_m2": 0.0,
                "volume_m3": 0.0,
                "capacity_occupants": 0.0,
            },
        )
        agg["space_count"] += 1
        agg["area_m2"] += (r["geometry"]["area_m2"] or 0.0)
        agg["volume_m3"] += (r["geometry"]["volume_m3"] or 0.0)
        agg["capacity_occupants"] += (r["occupancy"]["capacity_occupants"] or 0.0)
    for agg in storey_agg.values():
        for k in ("area_m2", "volume_m3", "capacity_occupants"):
            agg[k] = round(agg[k], 6)

    building_agg: dict[str, dict] = {}
    for r in records:
        bid = r["building_id"] or "UNKNOWN"
        agg = building_agg.setdefault(
            bid,
            {
                "building_id": bid,
                "building_name": r["building_name"],
                "storey_count": 0,
                "space_count": 0,
                "area_m2": 0.0,
                "volume_m3": 0.0,
                "capacity_occupants": 0.0,
            },
        )
        agg["space_count"] += 1
        agg["area_m2"] += (r["geometry"]["area_m2"] or 0.0)
        agg["volume_m3"] += (r["geometry"]["volume_m3"] or 0.0)
        agg["capacity_occupants"] += (r["occupancy"]["capacity_occupants"] or 0.0)
    for agg in building_agg.values():
        agg["storey_count"] = sum(
            1 for a in storey_agg.values() if a["building_id"] == agg["building_id"]
        )
        for k in ("area_m2", "volume_m3", "capacity_occupants"):
            agg[k] = round(agg[k], 6)

    total_area = sum((r["geometry"]["area_m2"] or 0.0) for r in records)
    total_volume = sum((r["geometry"]["volume_m3"] or 0.0) for r in records)
    total_capacity = sum((r["occupancy"]["capacity_occupants"] or 0.0) for r in records)

    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "building_count": len(building_agg),
            "storey_count": len(storey_agg),
            "storey_count_registry": len(registry.get("storeys", [])),
            "space_count": len(records),
            "occupiable_count": sum(1 for r in records if r["occupancy"]["occupiable"]),
            "total_area_m2": round(total_area, 6),
            "total_volume_m3": round(total_volume, 6),
            "total_capacity_occupants": round(total_capacity, 6),
            "metric_origin_note": (
                "All area/volume/capacity/lighting/power/HVAC values are BIM DESIGN "
                "or derived design metrics; none are measured consumption."
            ),
        },
        "availability": {
            "present": False,
            "source": None,
            "note": NO_AVAILABILITY_NOTE,
        },
        "storeys": sorted(storey_agg.values(), key=lambda a: a["storey_id"]),
        "buildings": sorted(building_agg.values(), key=lambda a: a["building_id"]),
        "spaces": records,
    }


if __name__ == "__main__":
    import os
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "output"
    result = build_resource_state(
        os.path.join(out, "spaces.json"),
        os.path.join(out, "campusiq.campus_registry.json"),
    )
    print(json.dumps(result["summary"], indent=2))
