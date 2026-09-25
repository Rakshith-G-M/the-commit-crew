"""CampusIQ — canonical IFC space extraction (M3.1).

Builds the CampusIQ campus foundation objects from DS3_TalTech_V4.ifc:
  Campus -> Building -> Storey -> Space

Read-only w.r.t. the source data (never modifies the .ifc / raw CSVs).

Reuses the IFC loader from `investigate_sensor_ifc_mapping` (M1) and
extends it (site / buildings / storeys / full bim_properties / quantities)
without duplicating the traversal.

Outputs:
  output/campus_registry.json   (campus, buildings, storeys, spaces, metadata)
  output/spaces.json            ({spaces: [...]} — same records as the registry)

IDs are deterministic: derived from the preserved IFC GlobalIds, e.g.
  space_3WAA5EqJ58HBqF0jqdih16
The same IFC space always receives the same CampusIQ space_id.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import investigate_sensor_ifc_mapping as source  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IFC_PATH = os.path.join(BASE_DIR, "DS3_TalTech_V4.ifc")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SCHEMA_VERSION = "campusiq.campus_registry/1.0"
CAMPUS_NAME = "TalTech (Tallinn University of Technology)"
# IfcBuilding.Name is EMPTY in the source export; the display fallback is the
# externally documented identity of this exact IFC (Zenodo 15782433, DS3,
# SmartLivingEPC). The raw IFC name is always preserved as `ifc_name`.
BUILDING_NAME_FALLBACK = "Ehituse Mäemaja (DS3, TalTech)"
TASK = "M3.1-CANONICAL-CAMPUS-FOUNDATION"


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------
def space_id_for(ifc_global_id: str) -> str:
    return f"space_{ifc_global_id}"


def building_id_for(ifc_global_id: str) -> str:
    return f"building_{ifc_global_id}"


def storey_id_for(ifc_global_id: str) -> str:
    return f"storey_{ifc_global_id}"


def campus_id_for(ifc_global_id: str | None) -> str:
    return f"campus_{ifc_global_id}" if ifc_global_id else "campus_taltech"


# ---------------------------------------------------------------------------
# Value coercion helpers (no fabrication: None is preserved as None)
# ---------------------------------------------------------------------------
def as_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def as_bool(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("yes", "true", "1", "on"):
            return True
        if s in ("no", "false", "0", "off"):
            return False
    return None


def _sort_key_space(sp: dict[str, Any]) -> tuple:
    name = sp["space_name"]
    try:
        return (0, int(name))
    except (TypeError, ValueError):
        return (1, str(name or ""))


# ---------------------------------------------------------------------------
# Canonical building blocks
# ---------------------------------------------------------------------------
def build_spaces(ifc_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Canonical Space records (schema documented in module docstring)."""
    spaces = []
    for sp in sorted(ifc_summary["spaces"], key=_sort_key_space):
        gid = sp["ifc_global_id"]
        bim = sp.get("bim_properties") or {}
        qty = sp.get("quantities") or {}
        area = as_number(sp.get("area"))
        if area is None:
            area = as_number(qty.get("Qto_SpaceBaseQuantities.GrossFloorArea"))
        volume = as_number(sp.get("volume"))
        if volume is None:
            volume = as_number(qty.get("Qto_SpaceBaseQuantities.NetVolume"))
        height = as_number(sp.get("unbounded_height"))
        if height is None:
            height = as_number(qty.get("Qto_SpaceBaseQuantities.Height"))
        spaces.append(
            {
                "space_id": space_id_for(gid),
                "building_id": building_id_for(sp["building_global_id"]),
                "storey_id": storey_id_for(sp["storey_global_id"]),
                "ifc_global_id": gid,
                "ifc_name": sp.get("space_name"),
                "ifc_long_name": sp.get("long_name"),
                "ifc_description": sp.get("description"),
                "ifc_tag": sp.get("space_type_tag"),
                "predefined_type": sp.get("predefined_type"),
                "area_m2": area,
                "volume_m3": volume,
                "height_m": height,
                "occupiable": as_bool(sp.get("occupiable")),
                "capacity": as_number(sp.get("num_people")),
                "geometry_ref": sp.get("geometry_ref"),
                "bim_properties": bim,
                "quantities": qty,
            }
        )
    return spaces


def build_storeys(ifc_summary: dict[str, Any], spaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for sp in spaces:
        counts[sp["storey_id"]] = counts.get(sp["storey_id"], 0) + 1
    storeys = []
    for st in ifc_summary["storeys"]:
        sid = storey_id_for(st["global_id"])
        storeys.append(
            {
                "id": sid,
                "building_id": building_id_for(st["building_global_id"]),
                "name": st.get("name"),
                "long_name": st.get("long_name"),
                "elevation": as_number(st.get("elevation")),
                "ifc_global_id": st.get("global_id"),
                "space_count": counts.get(sid, 0),
            }
        )
    return storeys


def build_buildings(ifc_summary: dict[str, Any], storeys: list[dict[str, Any]],
                    spaces: list[dict[str, Any]],
                    campus_id: str) -> list[dict[str, Any]]:
    storey_ids_by_building: dict[str, list[str]] = {}
    for st in storeys:
        storey_ids_by_building.setdefault(st["building_id"], []).append(st["id"])
    space_counts: dict[str, int] = {}
    for sp in spaces:
        space_counts[sp["building_id"]] = space_counts.get(sp["building_id"], 0) + 1
    buildings = []
    for b in ifc_summary["buildings"]:
        bid = building_id_for(b["global_id"])
        raw_name = (b.get("name") or "").strip()
        buildings.append(
            {
                "id": bid,
                "campus_id": campus_id,
                "name": raw_name or BUILDING_NAME_FALLBACK,
                "ifc_name": b.get("name"),
                "ifc_global_id": b.get("global_id"),
                "long_name": b.get("long_name"),
                "storey_ids": sorted(storey_ids_by_building.get(bid, [])),
                "space_count": space_counts.get(bid, 0),
            }
        )
    return buildings


def build_campus_registry(ifc_summary: dict[str, Any]) -> dict[str, Any]:
    site = ifc_summary.get("site")
    campus_id = campus_id_for(site["global_id"] if site else None)
    spaces = build_spaces(ifc_summary)
    storeys = build_storeys(ifc_summary, spaces)
    buildings = build_buildings(ifc_summary, storeys, spaces, campus_id)
    campus = {
        "id": campus_id,
        "name": CAMPUS_NAME,
        "ifc_site_global_id": site["global_id"] if site else None,
        "ifc_site_name": site["name"] if site else None,
        "building_count": len(buildings),
        "storey_count": len(storeys),
        "space_count": len(spaces),
    }
    return {
        "campus": campus,
        "buildings": buildings,
        "storeys": storeys,
        "spaces": spaces,
        "metadata": {
            "task": TASK,
            "schema_version": SCHEMA_VERSION,
            "source_ifc": IFC_PATH,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "ifc_schema": ifc_summary["schema"],
            "building_name_note": (
                "IfcBuilding.Name is empty in the source export; the display "
                "`name` uses an evidence-backed fallback (Zenodo 15782433 / DS3 "
                "SmartLivingEPC), while the raw value is kept in `ifc_name`."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def build_outputs(ifc_path: str = IFC_PATH) -> dict[str, Any]:
    ifc_summary = source.load_ifc(ifc_path)
    return build_campus_registry(ifc_summary)


def write_outputs(registry: dict[str, Any], out_dir: str = OUTPUT_DIR) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    registry_path = os.path.join(out_dir, "campus_registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False, default=str)
    spaces_path = os.path.join(out_dir, "spaces.json")
    with open(spaces_path, "w", encoding="utf-8") as f:
        json.dump({"spaces": registry["spaces"]}, f, indent=2,
                  ensure_ascii=False, default=str)
    return [registry_path, spaces_path]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CampusIQ canonical campus foundation — IFC extraction")
    parser.add_argument("--ifc", default=IFC_PATH)
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    print("Loading IFC (IfcOpenShell, reuse of M1 loader):", args.ifc)
    registry = build_outputs(args.ifc)
    paths = write_outputs(registry, args.out_dir)
    c = registry["campus"]
    print(f"  campus: {c['id']} ({c['name']})")
    print(f"  buildings: {c['building_count']} | storeys: {c['storey_count']} "
          f"| spaces: {c['space_count']}")
    for p in paths:
        print(f"  wrote {p}")


if __name__ == "__main__":
    main()