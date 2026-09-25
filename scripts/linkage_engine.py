"""CampusIQ — sensor-space linkage engine (M4).

Reusable, framework-independent intelligence layer that represents sensor ->
IFC space mappings in one of three canonical states:

  CONFIRMED    backed by authoritative evidence (BMS/CIEM registry, manual
               verification); treated as a VERIFIED location.
  PROVISIONAL  a candidate produced by an inference signal; explicit evidence,
                never treated as a verified location, never overwrites a
                CONFIRMED mapping.
  UNRESOLVED   no evidence; space_id is null; location is UNKNOWN.

The public TalTech dataset (M1/M3) contains no reliable sensor->space
identifier (M2: NOT_FOUND), so running the engine against the M3.1 data yields
36 UNRESOLVED mappings and 0 generated candidates.

Design principles
-----------------
- Never fabricate: a mapping requires explicit evidence; inference may only
  produce PROVISIONAL candidates that are never auto-accepted.
- No telemetry-similarity proof: raw value resemblance is not physical
  evidence and is not used here.
- Deterministic outputs: canonical files carry no generated timestamps.
- Extensible: a future BMS/CIEM export is ingested through the adapter
  pipeline (raw -> validate -> canonical -> evidence attribution) without
  redesigning the model.

Outputs (canonical, written by this module's CLI):
  output/sensor_space_mapping.json      (v2 canonical mapping artefact)
  output/sensor_space_candidates.json   (candidate slots + signal audit)

Read-only w.r.t. M3.1 inputs and all raw source data.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from typing import Any, Iterable

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

SCHEMA_VERSION = "campusiq.sensor_space_mapping/v2"
EVIDENCE_MODEL_VERSION = "campusiq.evidence_model/v1"
TASK = "M4-SENSOR-SPACE-LINKAGE-ENGINE"

STATUS_CONFIRMED = "CONFIRMED"
STATUS_PROVISIONAL = "PROVISIONAL"
STATUS_UNRESOLVED = "UNRESOLVED"

LOCATION_VERIFIED = "VERIFIED_LOCATION"
LOCATION_PROVISIONAL = "PROVISIONAL_LOCATION"
LOCATION_UNKNOWN = "UNKNOWN_LOCATION"

# mapping_method values the engine recognises and the state they imply.
METHOD_STATUS = {
    "none_found": STATUS_UNRESOLVED,
    "bms_registry": STATUS_CONFIRMED,
    "ciem_registry": STATUS_CONFIRMED,
    "manually_verified": STATUS_CONFIRMED,
    "explicit_dataset_metadata": STATUS_CONFIRMED,
    "ifc_identifier_match": STATUS_PROVISIONAL,
    "documented_room_reference": STATUS_PROVISIONAL,
    "candidate_inference": STATUS_PROVISIONAL,
}

# Evidence types and the strongest mapping state they can support on their own.
EVIDENCE_TYPE_TO_METHOD = {
    "bms_registry": ("bms_registry", STATUS_CONFIRMED),
    "ciem_registry": ("ciem_registry", STATUS_CONFIRMED),
    "manually_verified": ("manually_verified", STATUS_CONFIRMED),
    "explicit_dataset_metadata": ("explicit_dataset_metadata", STATUS_CONFIRMED),
    "ifc_identifier_match": ("ifc_identifier_match", STATUS_PROVISIONAL),
    "documented_room_reference": ("documented_room_reference", STATUS_PROVISIONAL),
    "candidate_inference": ("candidate_inference", STATUS_PROVISIONAL),
}

SIGNAL_TYPES = [
    "explicit_identifiers",
    "documented_room_references",
    "bms_metadata",
    "device_metadata",
    "external_authoritative_registry",
    "manual_verification",
]

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------
def make_evidence(evidence_type: str, description: str, source: str | None,
                  url: str | None = None,
                  recorded_at: str | None = None) -> dict[str, Any]:
    if evidence_type not in EVIDENCE_TYPE_TO_METHOD:
        raise ValueError(f"unknown evidence type: {evidence_type}")
    return {
        "type": evidence_type,
        "description": description,
        "source": source,
        "url": url,
        "recorded_at": recorded_at,
    }


# ---------------------------------------------------------------------------
# Canonical mapping records
# ---------------------------------------------------------------------------
def new_mapping_record(sensor_id: str, sensor_type: str | None = None) -> dict:
    return {
        "sensor_id": sensor_id,
        "sensor_type": sensor_type,
        "space_id": None,
        "status": STATUS_UNRESOLVED,
        "confidence": 0.0,
        "mapping_method": "none_found",
        "evidence": [],
        "source": None,
        "created_at": None,
        "updated_at": None,
        "valid_from": None,
        "valid_to": None,
        "history": [],
        "location_status": LOCATION_UNKNOWN,
        "location_verified": False,
    }


def status_allows_method(status: str, method: str) -> bool:
    return METHOD_STATUS.get(method) == status


def location_for(status: str) -> tuple[str, bool]:
    if status == STATUS_CONFIRMED:
        return LOCATION_VERIFIED, True
    if status == STATUS_PROVISIONAL:
        return LOCATION_PROVISIONAL, False
    return LOCATION_UNKNOWN, False


def validate_mapping(record: dict[str, Any]) -> list[str]:
    """Invariant checks for a canonical mapping record. Returns problem list."""
    problems: list[str] = []
    status = record.get("status")
    method = record.get("mapping_method")
    conf = record.get("confidence")
    space_id = record.get("space_id")
    evidence = record.get("evidence")

    if status not in (STATUS_CONFIRMED, STATUS_PROVISIONAL, STATUS_UNRESOLVED):
        problems.append(f"unknown status: {status!r}")
    if not status_allows_method(status, method):
        problems.append(f"method {method!r} inconsistent with status {status!r}")

    if status == STATUS_CONFIRMED:
        if not space_id:
            problems.append("CONFIRMED mapping requires a space_id")
        if conf != 1.0:
            problems.append(f"CONFIRMED confidence must be 1.0, got {conf!r}")
    elif status == STATUS_PROVISIONAL:
        if not space_id:
            problems.append("PROVISIONAL mapping requires a space_id")
        if not (isinstance(conf, (int, float)) and 0.0 < conf < 1.0):
            problems.append(f"PROVISIONAL confidence must be in (0,1), got {conf!r}")
    else:
        if space_id is not None:
            problems.append("UNRESOLVED mapping must have null space_id")
        if conf != 0.0:
            problems.append(f"UNRESOLVED confidence must be 0.0, got {conf!r}")

    if isinstance(conf, (int, float)) and not (0.0 <= conf <= 1.0):
        problems.append(f"confidence out of range: {conf!r}")
    if isinstance(evidence, list) and len(evidence) == 0 and status != STATUS_UNRESOLVED:
        problems.append(f"{status} mapping requires at least one evidence entry")

    if record.get("location_verified") not in (True, False, None):
        problems.append("location_verified must be boolean or null")
    stat = record.get("location_status")
    if stat not in (LOCATION_VERIFIED, LOCATION_PROVISIONAL, LOCATION_UNKNOWN):
        problems.append(f"invalid location_status: {stat!r}")
    return problems


def build_unresolved_mappings(sensors: Iterable[dict[str, Any]]) -> list[dict]:
    """Canonical UNRESOLVED records for every sensor registry entry.

    Follows the M4 schema example exactly (evidence [], source null,
    created_at null) — nothing has ever been resolved for the public dataset.
    """
    out = []
    for s in sensors:
        rec = new_mapping_record(
            s["sensor_id"], s.get("sensor_type") or s.get("type"))
        assert not validate_mapping(rec)
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Loading canonical inputs (M3.1 artefacts)
# ---------------------------------------------------------------------------
def load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_sensors(path: str | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = os.path.join(OUTPUT_DIR, "sensors.json")
    return sorted(load_json(path)["sensors"], key=lambda s: s["sensor_id"])


def load_spaces(path: str | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = os.path.join(OUTPUT_DIR, "spaces.json")
    return sorted(load_json(path)["spaces"], key=lambda s: s["space_id"])


# ---------------------------------------------------------------------------
# Mapping status API
# ---------------------------------------------------------------------------
def get_sensor_mapping(sensor_id: str,
                       mappings: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for m in mappings:
        if m["sensor_id"] == sensor_id:
            return m
    return None


def get_space_sensors(space_id: str | None,
                      mappings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in mappings if m.get("space_id") == space_id]


def get_unresolved_sensors(mappings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in mappings if m["status"] == STATUS_UNRESOLVED]


def get_confirmed_mappings(mappings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in mappings if m["status"] == STATUS_CONFIRMED]


def get_provisional_mappings(mappings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in mappings if m["status"] == STATUS_PROVISIONAL]


def get_mapping_statistics(mappings: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(mappings)
    confirmed = len(get_confirmed_mappings(records))
    provisional = len(get_provisional_mappings(records))
    unresolved = len(get_unresolved_sensors(records))
    return {
        "total": len(records),
        "confirmed": confirmed,
        "provisional": provisional,
        "unresolved": unresolved,
        "resolved": confirmed + provisional,
        "verified_locations": confirmed,
        "unknown_locations": unresolved,
    }


# ---------------------------------------------------------------------------
# Candidate generation framework
# ---------------------------------------------------------------------------
def signal_audit(sensors: list[dict], spaces: list[dict]) -> list[dict[str, Any]]:
    """Audit which candidate signals exist in the repository for each sensor.

    Returns candidate records. For the current public dataset every audit
    result is empty: no explicit identifiers, room references, BMS/device
    metadata, or authoritative registry is present, and telemetry similarity
    is deliberately excluded as a physical-location signal.
    """
    known_sensor_ids = {s["sensor_id"] for s in sensors}
    known_space_ids = {sp["space_id"] for sp in spaces}
    audit = []
    for s in sorted(sensors, key=lambda x: x["sensor_id"]):
        audit.append({
            "sensor_id": s["sensor_id"],
            "sensor_type": s.get("type"),
            "candidates": [],
            "signals_considered": {
                "explicit_identifiers": {
                    "present": False,
                    "note": "CSV carries only device_id UUID, timestamp, "
                            "meas_type, value, unit (M1 verified); no "
                            "room/space identifier appears.",
                },
                "documented_room_references": {
                    "present": False,
                    "note": "D6.2 names VAV rooms 206/207/309 and 4 IEQ test "
                            "rooms but associates no device UUID; using them "
                            "would be fabrication.",
                },
                "bms_metadata": {
                    "present": False,
                    "note": "No BMS point extract is present in the repository "
                            "(M2: access restricted; only a localized subset "
                            "was exposed to the project).",
                },
                "device_metadata": {
                    "present": False,
                    "note": "No device inventory beyond channel type/unit/range "
                            "is published in the dataset.",
                },
                "external_authoritative_registry": {
                    "present": False,
                    "note": "M2 NOT_FOUND: the CIEM/Web-Platform device-registry "
                            "record for DS3 is private (D5.1/D8.9).",
                },
                "manual_verification": {
                    "present": False,
                    "note": "No operator-confirmed assignments are available.",
                },
            },
            "telemetry_similarity_excluded": True,
            "known_space_ids": len(known_space_ids),
            "known_sensor_ids": len(known_sensor_ids),
            "linked": False,
        })
    return audit


def build_candidates_payload(sensors: list[dict], spaces: list[dict]) -> dict:
    audit = signal_audit(sensors, spaces)
    active = sum(1 for a in audit if a["candidates"])
    return {
        "task": TASK,
        "framework": {
            "candidate_acceptance": (
                "candidates are never auto-accepted; they can only become "
                "PROVISIONAL mappings through an explicit accept() call that "
                "attaches evidence, and PROVISIONAL never overwrites CONFIRMED"),
            "telemetry_similarity_excluded": True,
            "signal_types": SIGNAL_TYPES,
        },
        "summary": {
            "sensors_evaluated": len(audit),
            "sensors_with_candidates": active,
            "candidate_count": sum(len(a["candidates"]) for a in audit),
        },
        "sensors": audit,
    }


# ---------------------------------------------------------------------------
# Mapping payload writers (deterministic)
# ---------------------------------------------------------------------------
def build_mapping_payload(sensors: list[dict[str, Any]],
                          mappings: list[dict[str, Any]]) -> dict[str, Any]:
    stats = get_mapping_statistics(mappings)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "evidence_model_version": EVIDENCE_MODEL_VERSION,
        "total": stats["total"],
        "confirmed": stats["confirmed"],
        "provisional": stats["provisional"],
        "resolved": stats["resolved"],
        "unresolved": stats["unresolved"],
        "by_status": {
            "CONFIRMED": stats["confirmed"],
            "PROVISIONAL": stats["provisional"],
            "UNRESOLVED": stats["unresolved"],
        },
        "verified_locations": stats["verified_locations"],
        "unknown_locations": stats["unknown_locations"],
        "notes": (
            "Canonical mapping artefact produced by scripts/linkage_engine.py. "
            "For the public TalTech dataset no sensor->space evidence exists "
            "(M1/M2: NOT_FOUND); all mappings are UNRESOLVED and no candidate "
            "or fabricated assignment is emitted. See "
            "docs/SENSOR_SPACE_LINKAGE.md and output/external_mapping_evidence.json."
        ),
    }
    return {
        "task": TASK,
        "summary": summary,
        "mappings": sorted(mappings, key=lambda m: m["sensor_id"]),
    }


def write_mapping_payload(sensors: list[dict],
                          mappings: list[dict],
                          out_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "sensor_space_mapping.json")
    payload = build_mapping_payload(sensors, mappings)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    return path


def write_candidates_payload(sensors: list[dict], spaces: list[dict],
                             out_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "sensor_space_candidates.json")
    payload = build_candidates_payload(sensors, spaces)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    return path


# ---------------------------------------------------------------------------
# BMS / CIEM import adapter (future evidence)
# ---------------------------------------------------------------------------
class BmsMappingAdapter:
    """Adapter: raw BMS/CIEM mapping file -> canonical mapping records.

    The exact source format is unknown, so the CSV reader is tolerant:
    column names are matched case/space-insensitively across common aliases
    and each row is validated before any mapping record is produced.

    Pipeline: raw rows -> validation -> canonical mapping -> evidence
    attribution. Nothing is ever written by the adapter itself; callers
    decide whether to persist via apply_import().
    """

    COLUMN_ALIASES = {
        "sensor_id": [
            "sensor_id", "device_id", "uuid", "id", "sensor uuid",
            "sensor_uuid", "device uuid", "device_uuid",
        ],
        "space_id": ["space_id", "ifc_space_id", "campusiq_space_id"],
        "room": [
            "room", "room_number", "room_no", "space", "space_name",
            "space_no", "ifc_name", "name", "revit", "tag", "element_id",
        ],
        "bms_point": ["bms_point", "point", "device_point", "bms variable",
                      "point_name", "object_name"],
    }

    def __init__(self, spaces: list[dict], known_sensors: list[dict],
                 method: str = "bms_registry",
                 source: str | None = None):
        self.spaces = spaces
        self.known_sensors = {s["sensor_id"] for s in known_sensors}
        self.space_index = self.build_space_index(spaces)
        self.method = method
        self.source = source
        if METHOD_STATUS.get(method) != STATUS_CONFIRMED:
            raise ValueError(
                "BMS/CIEM evidence is authoritative; method must map to "
                f"CONFIRMED, got {method!r}")

    @staticmethod
    def build_space_index(spaces: list[dict]) -> dict[str, list[dict]]:
        index: dict[str, list[dict]] = {}
        for sp in spaces:
            keys = [
                sp.get("space_id"), sp.get("ifc_global_id"),
                sp.get("ifc_name"), sp.get("ifc_long_name"), sp.get("ifc_tag"),
            ]
            for k in keys:
                if k:
                    index.setdefault(str(k).strip().lower(), []).append(sp)
                if isinstance(k, int):
                    index.setdefault(str(k), []).append(sp)
        return index

    @staticmethod
    def _normalise_header(cells: list[str]) -> list[str]:
        return [re.sub(r"\s+", " ", c.strip().lower()) for c in cells]

    def _column_mapping(self, header: list[str]) -> dict[str, str]:
        cols: dict[str, str] = {}
        norm = self._normalise_header(header)
        for key, aliases in self.COLUMN_ALIASES.items():
            for i, cell in enumerate(norm):
                if cell in aliases:
                    cols[key] = cell
                    break
        return cols

    def _resolve_space(self, row: dict[str, str], cols: dict[str, str]):
        space_id = (row.get(cols.get("space_id", "")) or "").strip()
        if space_id:
            hits = self.space_index.get(space_id.strip().lower())
            if len(hits) == 1:
                return hits[0], None
            if len(hits) > 1:
                return None, f"space_id {space_id!r} is ambiguous"
            return None, f"space_id {space_id!r} is not a known CampusIQ space"
        room = (row.get(cols.get("room", "")) or "").strip()
        if room:
            hits = self.space_index.get(room.strip().lower())
            if len(hits) == 1:
                return hits[0], None
            if len(hits) > 1:
                return None, f"room keyword {room!r} is ambiguous"
            return None, f"room keyword {room!r} matches no IFC space"
        return None, "row carries neither a resolvable space_id nor room key"

    def parse(self, path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            cols = self._column_mapping(header)
        if "sensor_id" not in cols:
            return {"imported": [], "rejected": [], "header": header,
                    "error": "no sensor_id/device_id column found"}
        imported: list[dict] = []
        rejected: list[dict] = []
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f):
                sensor_id = (row.get(cols["sensor_id"]) or "").strip().lower()
                errors = []
                if not UUID_RE.match(sensor_id):
                    errors.append(f"invalid sensor id {sensor_id!r}")
                elif sensor_id not in self.known_sensors:
                    errors.append("sensor not in the CampusIQ registry")
                space = None
                space_err = None
                if not errors:
                    space, space_err = self._resolve_space(row, cols)
                    if space is None:
                        errors.append(space_err)
                if errors:
                    rejected.append(self._rejected_row(row, errors))
                    continue
                rec = new_mapping_record(sensor_id)
                rec["space_id"] = space["space_id"]
                rec["status"] = STATUS_CONFIRMED
                rec["confidence"] = 1.0
                rec["mapping_method"] = self.method
                rec["evidence"] = [make_evidence(
                    EVIDENCE_TYPE_TO_METHOD[self.method][0],
                    "sensor assigned to space by authoritative BMS/CIEM "
                    "registry row",
                    self.source or os.path.basename(path),
                    recorded_at=None)]
                rec["source"] = self.source or os.path.basename(path)
                rec["location_status"], rec["location_verified"] = \
                    location_for(STATUS_CONFIRMED)
                if validate_mapping(rec):
                    rejected.append(self._rejected_row(row, validate_mapping(rec)))
                    continue
                imported.append(rec)
        return {
            "imported": sorted(imported, key=lambda m: m["sensor_id"]),
            "rejected": rejected,
            "header": header,
        }

    @staticmethod
    def _rejected_row(row: dict[str, str], errors: list[str]) -> dict[str, Any]:
        return {"row": {k: v for k, v in row.items() if v},
                "errors": errors}


def apply_import(current: list[dict[str, Any]],
                 imported: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge imported mappings into the active mapping list.

    Rules:
      - an imported CONFIRMED record upgrades a UNRESOLVED or PROVISIONAL
        record for the same sensor (history preserved);
      - a PROVISIONAL record never overwrites a CONFIRMED record;
      - records for unknown sensors are never introduced.
    """
    by_id = {m["sensor_id"]: m for m in current}
    applied: list[dict] = []
    blocked: list[dict] = []
    for imp in imported:
        existing = by_id.get(imp["sensor_id"])
        if existing is None:
            blocked.append({"sensor_id": imp["sensor_id"],
                            "reason": "no existing mapping record for sensor"})
            continue
        if existing["status"] == STATUS_CONFIRMED and \
                imp["status"] != STATUS_CONFIRMED:
            blocked.append({"sensor_id": imp["sensor_id"],
                            "reason": "provisional cannot overwrite confirmed"})
            continue
        prior = {
            "status": existing["status"],
            "confidence": existing["confidence"],
            "mapping_method": existing["mapping_method"],
            "space_id": existing["space_id"],
        }
        imp = {**imp}
        imp["history"] = list(existing.get("history") or []) + [
            {"action": "superseded", **prior}]
        by_id[imp["sensor_id"]] = imp
        applied.append({"sensor_id": imp["sensor_id"],
                        "from": existing["status"], "to": imp["status"]})
    return {"applied": applied, "blocked": blocked,
            "result": sorted(by_id.values(), key=lambda m: m["sensor_id"])}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="CampusIQ sensor-space linkage engine")
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    parser.add_argument("--sensors-json", default=None)
    parser.add_argument("--spaces-json", default=None)
    args = parser.parse_args()

    sensors = load_sensors(args.sensors_json)
    spaces = load_spaces(args.spaces_json)
    mappings = build_unresolved_mappings(sensors)

    problems = [p for m in mappings for p in validate_mapping(m)]
    if problems:
        raise SystemExit("invalid generated mappings: " + "; ".join(problems[:10]))

    mapping_path = write_mapping_payload(sensors, mappings, args.out_dir)
    candidates_path = write_candidates_payload(sensors, spaces, args.out_dir)

    stats = get_mapping_statistics(mappings)
    print(f"sensors: {stats['total']} | confirmed: {stats['confirmed']} | "
          f"provisional: {stats['provisional']} | unresolved: {stats['unresolved']}")
    print(f"candidate count: 0 (no evidence; telemetry similarity excluded)")
    print(f"wrote {mapping_path}")
    print(f"wrote {candidates_path}")


if __name__ == "__main__":
    main()