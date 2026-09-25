"""CampusIQ — M8 digital-twin asset builder.

Produces a deterministic, IFC-derived web-ready GLB plus manifest for the
frontend's Digital Twin page.

What this is
------------
A *schematic BIM footprint layout* extruded from the real IFC-derived
quantities in M4's spaces.json (gross area, volume, height per space) and
campus_registry.json (storey name, elevation, membership). Every numeric
value (area / volume / height / elevation) is a real IFC quantity.

What this is NOT
----------------
The tessellated IFC mesh. In this environment the ifcopenshell geometry
backend proved unreliable, so per-space XZ *coordinates* are a deterministic
grid arrangement (documented in the manifest and surfaced in the UI). Storey
stacking/elevations ARE real. This is clearly labelled in the product; the
full mesh is a recommended follow-up (IfcConvert/xeokit).

Outputs (written to the frontend's public dir):
    {output}/models/campus_twin.glb      (glTF 2.0, embedded buffers, no deps)
    {output}/models/twin_manifest.json   (node->space join + provenance)

Writers are manual (struct.pack, no third-party modules) so this runs
anywhere; everything is sorted and float-formatted for byte-determinism.
"""

from __future__ import annotations

import json
import os
import struct

INPUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
DATA_SPACES = os.path.join(INPUT_ROOT, "spaces.json")
DATA_REGISTRY = os.path.join(INPUT_ROOT, "campus_registry.json")

TASK = "M8-TWIN-BUILDER"


def _num(v, d: float = 0.0) -> float:
    try:
        f = float(v)
        return f if f == f else d
    except (TypeError, ValueError):
        return d


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _space_key(space: dict) -> tuple:
    return (-_num(space.get("area_m2")), space["space_id"])


def _storey_key(storey: dict) -> tuple:
    return (_num(storey.get("elevation")), storey["id"])


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    v = hex_color.lstrip("#")
    if len(v) != 6:
        return (180, 180, 180)
    return tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# Storey palette (soft, operational; alpha 1.0 for spaces, 0.32 for slabs).
STORESTY_PALETTE = {
    "+Kelder": "#aeb2ba",
    "1. korrus": "#8fb0d6",
    "2. korrus": "#9fc9b1",
    "3. korrus": "#d8c59a",
    "Katus": "#c4b8a6",
}
DEFAULT_TINT = "#b0b4ba"


def _box(area_m2: float, height_m: float, cx: float, cy_base: float, cz: float, side_m: float) -> list[float]:
    """Return non-indexed positions/normals for an axis-aligned box.

    Box base sits at cy_base, extends up by `height_m`. Returns (positions,
    normals) as flat float lists with per-face flat shading (24 verts).
    """
    hx, hz = side_m / 2.0, side_m / 2.0
    y0, y1 = cy_base, cy_base + height_m
    corners = [
        (cx - hx, y0, cz - hz), (cx + hx, y0, cz - hz),
        (cx + hx, y0, cz + hz), (cx - hx, y0, cz + hz),
        (cx - hx, y1, cz - hz), (cx + hx, y1, cz - hz),
        (cx + hx, y1, cz + hz), (cx - hx, y1, cz + hz),
    ]
    faces = [
        (0, 1, 5, 4, "bottom", 0, -1, 0),  # +X faces iterate
        (1, 2, 6, 5, "front", 0, 0, 1),
        (2, 3, 7, 6, "back", 0, 0, -1),
        (3, 0, 4, 7, "left", -1, 0, 0),
        (4, 5, 6, 7, "top", 0, 1, 0),
        (3, 2, 1, 0, "right", 1, 0, 0),
    ]
    pos: list[float] = []
    nrm: list[float] = []
    for a, b, c, d, _name, nx, ny, nz in faces:
        for idx in (a, b, c, a, c, d):
            x, y, z = corners[idx]
            pos += [x, y, z]
            nrm += [float(nx), float(ny), float(nz)]
    return pos, nrm


def _slab(side_m: float, cy_base: float, thickness: float = 0.25) -> list[float]:
    h = thickness / 2.0
    y0, y1 = cy_base - h, cy_base + h
    s = side_m / 2.0
    corners = [
        (-s, y0, -s), (s, y0, -s), (s, y0, s), (-s, y0, s),
        (-s, y1, -s), (s, y1, -s), (s, y1, s), (-s, y1, s),
    ]
    faces = [
        (0, 1, 5, 4, 0, -1, 0), (1, 2, 6, 5, 0, 0, 1),
        (2, 3, 7, 6, 0, 0, -1), (3, 0, 4, 7, -1, 0, 0),
        (4, 5, 6, 7, 0, 1, 0), (3, 2, 1, 0, 1, 0, 0),
    ]
    pos, nrm = [], []
    for a, b, c, d, nx, ny, nz in faces:
        for idx in (a, b, c, a, c, d):
            x, y, z = corners[idx]
            pos += [x, y, z]
            nrm += [float(nx), float(ny), float(nz)]
    return pos, nrm


def _build_layout(spaces_by_storey: dict, storeys_sorted: list[dict]) -> dict:
    """Compute deterministic schematic layout per storey.

    Returns {storey: {nodes: [(space_id, cx, cy_base, cz, side, height)],
                      slab: (side, cy_base)}}.
    """
    shift = min([_num(s.get("elevation")) for s in storeys_sorted] or [0.0])
    layout: dict[str, dict] = {}
    for storey in storeys_sorted:
        sid = storey["id"]
        spaces = sorted(spaces_by_storey.get(sid, []), key=_space_key)
        total_area = sum(_num(s.get("area_m2")) for s in spaces)
        n = len(spaces)
        layout[sid] = {"nodes": [], "slab": None}
        if n == 0:
            continue
        cols = max(1, int(n ** 0.5))
        rows = (n + cols - 1) // cols
        stride = (total_area / n) ** 0.5 * 1.25
        base_y = _num(storey.get("elevation")) - shift
        for i, sp in enumerate(spaces):
            r, c = divmod(i, cols)
            cx = (c - (cols - 1) / 2.0) * stride
            cz = (r - (rows - 1) / 2.0) * stride
            side = max(0.4, min((_num(sp.get("area_m2")) ** 0.5), stride * 0.9))
            height = max(0.4, _num(sp.get("height_m")) * 0.92)
            layout[sid]["nodes"].append(
                {"space_id": sp["space_id"], "cx": cx, "cy_base": base_y,
                 "cz": cz, "side": side, "height": height})
        slab_side = max(cols, rows) * stride * 1.0
        layout[sid]["slab"] = (slab_side, base_y)
    return layout


def build_twin(spaces_path: str = DATA_SPACES, registry_path: str = DATA_REGISTRY,
               out_dir: str | None = None) -> tuple[str, str]:
    if out_dir is None:
        frontend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
        out_dir = os.path.join(frontend, "public", "models")
    os.makedirs(out_dir, exist_ok=True)

    spaces = _load(spaces_path)["spaces"]
    registry = _load(registry_path)
    storeys = sorted(registry["storeys"], key=_storey_key)
    spaces_by_storey: dict[str, list[dict]] = {}
    for sp in spaces:
        spaces_by_storey.setdefault(sp.get("storey_id"), []).append(sp)

    layout = _build_layout(spaces_by_storey, storeys)

    # --- collect geometry -------------------------------------------------
    node_geoms: dict[str, tuple[list[float], list[float]]] = {}
    storey_node_names: dict[str, list[str]] = {}
    storey_order: list[str] = []
    slabs: dict[str, tuple[list[float], list[float]]] = {}
    for storey in storeys:
        sid = storey["id"]
        storey_order.append(sid)
        if sid in layout:
            for node in layout[sid]["nodes"]:
                sp = next(s for s in spaces_by_storey[sid] if s["space_id"] == node["space_id"])
                area, height = _num(sp.get("area_m2")), max(0.4, _num(sp.get("height_m")) * 0.92)
                node_geoms[node["space_id"]] = _box(area, height, node["cx"], node["cy_base"], node["cz"], node["side"])
                storey_node_names.setdefault(sid, []).append(node["space_id"])
            if layout[sid]["slab"]:
                slab_side, cy = layout[sid]["slab"]
                slabs[sid] = _slab(slab_side, cy)

    # --- glTF writer -------------------------------------------------------
    json_nodes: list[dict] = [{"name": "campus_root", "children": []}]
    json_meshes: list[dict] = []
    json_materials: list[dict] = []
    json_accessors: list[dict] = []
    json_buffer_views: list[dict] = []
    bin_parts: list[bytes] = []
    bin_len = 0

    def add_geometry(pos_f, nrm_f) -> int:
        nonlocal bin_len
        pos = struct.pack(f"<{len(pos_f)}f", *pos_f)
        nrm = struct.pack(f"<{len(nrm_f)}f", *nrm_f)
        pad = b"\x00" * ((4 - (bin_len % 4)) % 4)
        bin_parts.append(pad); bin_len += len(pad)
        pos_off, bin_len = bin_len, bin_len + len(pos)
        bin_parts.append(pos)
        nrm_off, bin_len = bin_len, bin_len + len(nrm)
        bin_parts.append(nrm)
        json_buffer_views.append({"buffer": 0, "byteOffset": pos_off, "byteLength": len(pos)})
        json_buffer_views.append({"buffer": 0, "byteOffset": nrm_off, "byteLength": len(nrm)})
        json_accessors.append({"bufferView": len(json_buffer_views) - 2,
                               "componentType": 5126, "count": len(pos_f) // 3, "type": "VEC3"})
        json_accessors.append({"bufferView": len(json_buffer_views) - 1,
                               "componentType": 5126, "count": len(nrm_f) // 3, "type": "VEC3"})
        return len(json_accessors) - 2

    def add_material(rgb: tuple[int, int, int], alpha: float) -> int:
        r, g, b = tuple(v / 255.0 for v in rgb)
        mat = {
            "pbrMetallicRoughness": {
                "baseColorFactor": [r, g, b, alpha],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.9,
            },
        }
        if alpha < 1.0:
            mat["alphaMode"] = "BLEND"
        json_materials.append({"name": f"mat_{len(json_materials)}", **mat})
        return len(json_materials) - 1

    root_children: list[int] = []
    space_node_index: dict[str, int] = {}
    for sid in storey_order:
        group_idx = len(json_nodes)
        group = {"name": f"storey-{sid}", "children": []}
        json_nodes.append(group)
        root_children.append(group_idx)
        storey_name = next((s["name"] for s in storeys if s["id"] == sid), sid)
        tint = STORESTY_PALETTE.get(storey_name, DEFAULT_TINT)
        mat_idx = add_material(_hex_rgb(tint), 1.0)
        slab_mat_idx = add_material(_hex_rgb(tint), 0.32)
        for name in sorted(storey_node_names.get(sid, [])):
            pos_f, nrm_f = node_geoms[name]
            acc = add_geometry(pos_f, nrm_f)
            json_meshes.append({"primitives": [{
                "attributes": {"POSITION": acc, "NORMAL": acc + 1},
                "material": mat_idx}]})
            node_idx = len(json_nodes)
            json_nodes.append({"name": name, "mesh": len(json_meshes) - 1})
            group["children"].append(node_idx)
            space_node_index[name] = node_idx
        if sid in slabs:
            pos_f, nrm_f = slabs[sid]
            acc = add_geometry(pos_f, nrm_f)
            json_meshes.append({"primitives": [{
                "attributes": {"POSITION": acc, "NORMAL": acc + 1},
                "material": slab_mat_idx}]})
            node_idx = len(json_nodes)
            json_nodes.append({"name": f"slab-{sid}", "mesh": len(json_meshes) - 1})
            group["children"].append(node_idx)

    json_nodes[0]["children"] = root_children
    json_scenes = [{"nodes": [0]}]
    binary = b"".join(bin_parts)

    gltf = {
        "asset": {"version": "2.0", "generator": TASK},
        "scene": 0,
        "scenes": json_scenes,
        "nodes": json_nodes,
        "meshes": json_meshes,
        "materials": json_materials,
        "accessors": json_accessors,
        "bufferViews": json_buffer_views,
        "buffers": [{"byteLength": bin_len}],
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    if len(json_bytes) % 4:
        json_bytes += b" " * (4 - len(json_bytes) % 4)

    header = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_bytes) + 8 + bin_len)
    chunk0 = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    chunk1 = struct.pack("<I4s", bin_len, b"BIN\x00") + binary
    glb_path = os.path.join(out_dir, "campus_twin.glb")
    with open(glb_path, "wb") as fh:
        fh.write(header + chunk0 + chunk1)

    # --- manifest -----------------------------------------------------------
    manifest = {
        "task": TASK,
        "schema_version": "campusiq.twin_manifest/v1",
        "model": "campus_twin.glb",
        "generation": (
            "schematic footprint extrusion from M4 IFC quantities "
            "(spaces.json areas/volumes/heights + campus_registry storey elevations)"
        ),
        "honesty_note": (
            "Per-space XZ placement is a deterministic schematic grid; storey "
            "elevations and all areas/volumes/heights are real IFC quantities. "
            "Not the tessellated IFC mesh."
        ),
        "storeys": [
            {"storey_id": s["id"], "name": s.get("name"), "elevation": _num(s.get("elevation")),
             "node": f"storey-{s['id']}"}
            for s in storeys
        ],
        "spaces": sorted([
            {"space_id": sp["space_id"], "node": sp["space_id"],
             "storey_id": sp.get("storey_id"),
             "ifc_name": str(sp.get("ifc_name") or ""),
             "area_m2": _num(sp.get("area_m2")), "height_m": _num(sp.get("height_m")),
             "volume_m3": _num(sp.get("volume_m3"))}
            for sp in spaces
        ], key=lambda x: x["space_id"]),
    }
    man_path = os.path.join(out_dir, "twin_manifest.json")
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    return glb_path, man_path


if __name__ == "__main__":
    glb, man = build_twin()
    print("GLB ", os.path.relpath(glb))
    print("MAN ", os.path.relpath(man))