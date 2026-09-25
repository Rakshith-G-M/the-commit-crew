"""CampusIQ M4 — sensor-space linkage engine tests.

Covers the 14 M4 validation items: mapping completeness, uniqueness,
status/method/confidence invariants, UUID/space-ID preservation, no
fabrication, determinism, and the mapping status API. Also exercises the
future BMS/CIEM adapter against a synthetic in-memory fixture (never written
to any output artefact and never treated as evidence for the real dataset).
"""

import csv
import hashlib
import json
import os
import re
import sys

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

import linkage_engine as eng  # noqa: E402

OUTPUT = os.path.join(BASE_DIR, "output")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

REAL_SENSOR_ID = "04f80f82-e206-427c-a913-69758a1ec283"
REAL_SPACE_ID = "space_3WAA5EqJ58HBqF0jqdih16"


def _load(name: str):
    with open(os.path.join(OUTPUT, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def mapping():
    return _load("sensor_space_mapping.json")


@pytest.fixture(scope="module")
def candidates():
    return _load("sensor_space_candidates.json")


@pytest.fixture(scope="module")
def sensors():
    return _load("sensors.json")


@pytest.fixture(scope="module")
def spaces():
    return _load("spaces.json")


@pytest.fixture(scope="module")
def engine_mappings():
    """Fresh canonical mappings from the engine (independent of disk output)."""
    return eng.build_unresolved_mappings(eng.load_sensors())


# ---------------------------------------------------------------------------
# 1. every sensor has a mapping record
# ---------------------------------------------------------------------------
def test_every_sensor_has_mapping_record(mapping, sensors):
    sensor_ids = {s["sensor_id"] for s in sensors["sensors"]}
    mapped_ids = {m["sensor_id"] for m in mapping["mappings"]}
    assert len(sensor_ids) == 36
    assert sensor_ids == mapped_ids


# ---------------------------------------------------------------------------
# 2. no sensor appears twice as an active mapping
# ---------------------------------------------------------------------------
def test_no_duplicate_active_mappings(mapping):
    ids = [m["sensor_id"] for m in mapping["mappings"]]
    assert len(ids) == len(set(ids)) == mapping["summary"]["total"] == 36


# ---------------------------------------------------------------------------
# 3. confirmed mappings require a valid space_id
# ---------------------------------------------------------------------------
def test_confirmed_requires_space_id():
    rec = eng.new_mapping_record(REAL_SENSOR_ID, "temperature")
    rec["status"] = "CONFIRMED"
    rec["confidence"] = 1.0
    rec["mapping_method"] = "bms_registry"
    assert eng.validate_mapping(rec)  # no space_id -> invalid
    rec["space_id"] = REAL_SPACE_ID
    rec["evidence"] = [eng.make_evidence(
        "bms_registry", "fixture", "test")]
    assert eng.validate_mapping(rec) == []


# ---------------------------------------------------------------------------
# 4. provisional mappings require evidence
# ---------------------------------------------------------------------------
def test_provisional_requires_evidence():
    rec = eng.new_mapping_record(REAL_SENSOR_ID, "temperature")
    rec["status"] = "PROVISIONAL"
    rec["confidence"] = 0.5
    rec["space_id"] = REAL_SPACE_ID
    rec["mapping_method"] = "candidate_inference"
    assert eng.validate_mapping(rec)  # empty evidence -> invalid
    rec["evidence"] = [eng.make_evidence(
        "candidate_inference", "fixture", "test")]
    assert eng.validate_mapping(rec) == []


# ---------------------------------------------------------------------------
# 5. unresolved mappings have null space_id
# ---------------------------------------------------------------------------
def test_unresolved_has_null_space(engine_mappings):
    for m in engine_mappings:
        assert m["status"] == "UNRESOLVED"
        assert m["space_id"] is None
        assert eng.validate_mapping(m) == []


# ---------------------------------------------------------------------------
# 6. confidence between 0 and 1
# ---------------------------------------------------------------------------
def test_confidence_bounds(mapping):
    for m in mapping["mappings"]:
        assert isinstance(m["confidence"], float)
        assert 0.0 <= m["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# 7. status and method consistent
# ---------------------------------------------------------------------------
def test_status_method_consistent(mapping):
    for m in mapping["mappings"]:
        assert eng.status_allows_method(m["status"], m["mapping_method"])
        assert eng.validate_mapping(m) == []


# ---------------------------------------------------------------------------
# 8. 36 sensor UUIDs unchanged
# ---------------------------------------------------------------------------
def test_sensor_uuids_unchanged(mapping, sensors):
    uuids = {m["sensor_id"] for m in mapping["mappings"]}
    assert len(uuids) == 36
    assert all(UUID_RE.match(u) for u in uuids)
    assert uuids == {s["sensor_id"] for s in sensors["sensors"]}


# ---------------------------------------------------------------------------
# 9. 115 space IDs unchanged
# ---------------------------------------------------------------------------
def test_space_ids_unchanged(spaces):
    ids = {s["space_id"] for s in spaces["spaces"]}
    assert len(ids) == 115
    assert all(s.startswith("space_") for s in ids)
    # candidate audit is anchored to the unchanged space set
    candidates_payload = eng.build_candidates_payload(
        eng.load_sensors(), eng.load_spaces())
    for c in candidates_payload["sensors"]:
        assert c["known_space_ids"] == 115
        assert c["known_sensor_ids"] == 36


# ---------------------------------------------------------------------------
# 10. no fabricated mapping exists
# ---------------------------------------------------------------------------
def test_no_fabricated_mapping(mapping, candidates):
    assert mapping["summary"]["resolved"] == 0
    assert mapping["summary"]["confirmed"] == 0
    assert mapping["summary"]["provisional"] == 0
    assert mapping["summary"]["unresolved"] == 36
    assert all(m["space_id"] is None for m in mapping["mappings"])
    assert candidates["summary"]["candidate_count"] == 0
    assert candidates["summary"]["sensors_with_candidates"] == 0
    for c in candidates["sensors"]:
        assert c["candidates"] == []
        assert c["linked"] is False
        assert c["telemetry_similarity_excluded"] is True


# ---------------------------------------------------------------------------
# 11. deterministic output
# ---------------------------------------------------------------------------
def test_deterministic_output(engine_mappings):
    second = eng.build_unresolved_mappings(eng.load_sensors())
    assert engine_mappings == second


def test_deterministic_payload_bytes(mapping):
    sensors = eng.load_sensors()
    a = json.dumps(eng.build_mapping_payload(sensors, mapping["mappings"]),
                   sort_keys=True)
    b = json.dumps(eng.build_mapping_payload(sensors, mapping["mappings"]),
                   sort_keys=True)
    assert a == b


# ---------------------------------------------------------------------------
# 12. get_space_sensors() works
# ---------------------------------------------------------------------------
def test_get_space_sensors_works():
    rec_a = eng.new_mapping_record(REAL_SENSOR_ID, "temperature")
    rec_a["space_id"] = REAL_SPACE_ID
    rec_a["status"] = "CONFIRMED"
    rec_a["confidence"] = 1.0
    rec_a["mapping_method"] = "manually_verified"
    rec_a["evidence"] = [eng.make_evidence("manually_verified", "x", "t")]
    other = eng.new_mapping_record(
        "99ca72a1-36de-4e79-b65d-16cdec7e42fb", "co2,humidity,temperature")
    assert [m["sensor_id"] for m in
            eng.get_space_sensors(REAL_SPACE_ID, [rec_a, other])] == \
        [REAL_SENSOR_ID]
    assert eng.get_space_sensors("space_no_such", [rec_a, other]) == []


# ---------------------------------------------------------------------------
# 13. get_unresolved_sensors() returns all currently unresolved devices
# ---------------------------------------------------------------------------
def test_unresolved_sensor_query(mapping, sensors):
    unresolved = eng.get_unresolved_sensors(mapping["mappings"])
    assert len(unresolved) == 36
    assert {m["sensor_id"] for m in unresolved} == \
        {s["sensor_id"] for s in sensors["sensors"]}
    assert eng.get_sensor_mapping(REAL_SENSOR_ID, mapping["mappings"])[
        "sensor_id"] == REAL_SENSOR_ID
    assert eng.get_sensor_mapping(
        "00000000-0000-4000-8000-000000000000", mapping["mappings"]) is None


# ---------------------------------------------------------------------------
# 14. mapping statistics are correct
# ---------------------------------------------------------------------------
def test_mapping_statistics(mapping):
    stats = eng.get_mapping_statistics(mapping["mappings"])
    assert stats["total"] == 36
    assert stats["confirmed"] == 0
    assert stats["provisional"] == 0
    assert stats["unresolved"] == 36
    assert stats["resolved"] == 0
    assert stats["verified_locations"] == 0
    assert stats["unknown_locations"] == 36


# ---------------------------------------------------------------------------
# BMS/CIEM import adapter (synthetic fixture — never written to outputs)
# ---------------------------------------------------------------------------
def _write_bms_csv(tmp_path, header):
    rows = [
        [REAL_SENSOR_ID, "FLOOR1.ZONE1.TEMP", REAL_SPACE_ID],
        ["not-a-uuid", "FLOOR1.ZONE2.TEMP", "room-xyz"],
    ]
    p = tmp_path / "bms_fixture.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


def test_adapter_imports_confirmed_mapping(tmp_path, mapping):
    src = _write_bms_csv(tmp_path, ["sensor_id", "bms_point", "space_id"])
    adapter = eng.BmsMappingAdapter(eng.load_spaces(), eng.load_sensors(),
                                    method="bms_registry",
                                    source="fixture-bms-export.csv")
    result = adapter.parse(str(src))

    imported = {r["sensor_id"]: r for r in result["imported"]}
    assert len(imported) == 1
    rec = imported[REAL_SENSOR_ID]
    assert rec["status"] == "CONFIRMED"
    assert rec["confidence"] == 1.0
    assert rec["space_id"] == REAL_SPACE_ID
    assert rec["mapping_method"] == "bms_registry"
    assert rec["evidence"][0]["type"] == "bms_registry"
    assert rec["location_status"] == "VERIFIED_LOCATION"
    assert rec["location_verified"] is True
    assert eng.validate_mapping(rec) == []

    # the bad row is rejected, never silently dropped or coerced
    assert any("invalid sensor id" in e or "sensor not in" in e
               for r in result["rejected"]
               for e in r["errors"])

    # adapter result is in-memory only: the canonical output must be untouched
    assert eng.get_mapping_statistics(mapping["mappings"])["resolved"] == 0
    assert all(m["space_id"] is None for m in mapping["mappings"])


def test_adapter_rejects_unknown_sensor_and_space(tmp_path):
    p = tmp_path / "bms_bad.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["device_id", "room"])
        w.writerow(["aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "9999"])
    adapter = eng.BmsMappingAdapter(eng.load_spaces(), eng.load_sensors())
    result = adapter.parse(str(p))
    assert result["imported"] == []
    assert len(result["rejected"]) == 1
    errors = " ".join(result["rejected"][0]["errors"])
    assert "sensor not in the CampusIQ registry" in errors


def test_adapter_detects_space_by_room_keyword(tmp_path):
    p = tmp_path / "bms_room.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["device_uuid", "bms_point", "room_number"])
        w.writerow([REAL_SENSOR_ID, "X", "1"])  # ifc_name "1" -> one space
    adapter = eng.BmsMappingAdapter(eng.load_spaces(), eng.load_sensors())
    result = adapter.parse(str(p))
    assert len(result["imported"]) == 1
    assert result["imported"][0]["space_id"] == REAL_SPACE_ID


def test_adapter_missing_sensor_column_reported(tmp_path):
    p = tmp_path / "bms_no_sensor_col.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        f.write("bms_point,room\nX,1\n")
    adapter = eng.BmsMappingAdapter(eng.load_spaces(), eng.load_sensors())
    result = adapter.parse(str(p))
    assert result["imported"] == []
    assert "no sensor_id" in result["error"]


def test_provisional_never_overwrites_confirmed():
    sensors = eng.load_sensors()
    current = eng.build_unresolved_mappings(sensors)[:1]
    confirmed = eng.new_mapping_record(REAL_SENSOR_ID, "temperature")
    confirmed["space_id"] = REAL_SPACE_ID
    confirmed["status"] = "CONFIRMED"
    confirmed["confidence"] = 1.0
    confirmed["mapping_method"] = "manually_verified"
    confirmed["evidence"] = [eng.make_evidence("manually_verified", "x", "t")]
    current[0] = confirmed

    provisional = eng.new_mapping_record(REAL_SENSOR_ID, "temperature")
    provisional["space_id"] = REAL_SPACE_ID
    provisional["status"] = "PROVISIONAL"
    provisional["confidence"] = 0.5
    provisional["mapping_method"] = "candidate_inference"
    provisional["evidence"] = [eng.make_evidence(
        "candidate_inference", "x", "t")]

    merged = eng.apply_import(current, [provisional])
    assert merged["blocked"][0]["reason"] == \
        "provisional cannot overwrite confirmed"
    assert [m["status"] for m in merged["result"] if
            m["sensor_id"] == REAL_SENSOR_ID] == ["CONFIRMED"]

    # an authoritative BMS import legitimately supersedes UNRESOLVED
    fresh = eng.build_unresolved_mappings(eng.load_sensors())[:1]
    upgraded = eng.apply_import(fresh, [confirmed])
    assert upgraded["applied"][0]["from"] == "UNRESOLVED"
    assert upgraded["applied"][0]["to"] == "CONFIRMED"
    merged_rec = eng.get_sensor_mapping(REAL_SENSOR_ID, upgraded["result"])
    assert merged_rec["history"][0]["action"] == "superseded"


def test_raw_dataset_hashes_unchanged_by_engine():
    """The engine never writes to the raw dataset (hash guard)."""
    ifc = os.path.join(BASE_DIR, "DS3_TalTech_V4.ifc")
    zipf = os.path.join(BASE_DIR, "Taltech.zip")
    assert hashlib.sha256(open(ifc, "rb").read()).hexdigest().startswith(
        "05919eee0701b955d3d08501c4889c879d9c486e2389a6a1a5cdaad32a5d10ba")
    assert hashlib.sha256(open(zipf, "rb").read()).hexdigest().startswith(
        "e4878a7d5315f1b3cdfbbb9c39a233099f4d169f3c9ad5dfd9402fbb380b183b")