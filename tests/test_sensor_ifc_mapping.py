"""Sanity checks for the M1 sensor<->IFC mapping investigation.

These tests are read-only w.r.t. the source data. They verify:
  1. The raw source files are untouched (size/other invariants match STEP 1).
  2. The CSV dataset is uniform and its identifiers are self-consistent.
  3. The IFC space model is fully characterized.
  4. The generated mapping report is valid and internally consistent.
"""

import csv
import json
import os
import sys
from collections import Counter

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

import investigate_sensor_ifc_mapping as mod  # noqa: E402

IFC_SIZE = 38_728_810
ZIP_SIZE = 5_727_705


# ---------------------------------------------------------------------------
# 1. Raw data preserved
# ---------------------------------------------------------------------------
def test_raw_files_untouched():
    assert os.path.getsize(mod.IFC_PATH) == IFC_SIZE
    assert os.path.getsize(mod.ZIP_PATH) == ZIP_SIZE


def test_zip_contains_only_csv():
    import zipfile

    with zipfile.ZipFile(mod.ZIP_PATH) as z:
        names = z.namelist()
        assert z.testzip() is None  # archive integrity check
    assert len(names) == 69
    assert all(n.lower().endswith(".csv") for n in names)


# ---------------------------------------------------------------------------
# 2. CSV uniformity & identifiers
# ---------------------------------------------------------------------------
def test_all_csv_header_uniform():
    headers = Counter()
    for name in os.listdir(mod.CSV_DATA_DIR):
        if not name.endswith(".csv"):
            continue
        with open(os.path.join(mod.CSV_DATA_DIR, name), encoding="utf-8") as f:
            headers[tuple(f.readline().strip().split(","))] += 1
    assert list(headers) == [("device_id", "timestamp", "meas_type", "value", "unit")]
    assert sum(headers.values()) == 69


def test_filename_uuid_matches_device_id():
    for name in os.listdir(mod.CSV_DATA_DIR):
        if not name.endswith(".csv"):
            continue
        with open(os.path.join(mod.CSV_DATA_DIR, name), encoding="utf-8") as f:
            f.readline()
            first = f.readline().strip()
        dev = first.split(",")[0]
        assert dev == mod.extract_uuid_from_filename(name)


def test_infer_sensor_types():
    assert mod.infer_sensor_type("x_TEMPERATURESENSOR.csv") == "temperature"
    assert mod.infer_sensor_type("x_HUMIDITYSENSOR.csv") == "humidity"
    assert mod.infer_sensor_type("x_CO2SENSOR.csv") == "co2"
    assert mod.infer_sensor_type("x_PM25SENSOR.csv") == "pm2.5"
    assert mod.infer_sensor_type("x_ENERGYMETER.csv") == "energy"


def test_device_grouping_counts():
    profiles = mod.collect_csv_profiles()
    devices = mod.group_devices(profiles)
    assert len(devices) == 36
    assert sum(d["channel_count"] for d in devices) == 69
    assert sum(d["total_rows"] for d in devices) == 1_390_297


def test_no_revit_id_in_csv_values():
    ifc_summary = mod.load_ifc(mod.IFC_PATH)
    revit_ids = {sp["space_type_tag"] for sp in ifc_summary["spaces"]
                 if sp["space_type_tag"] is not None}
    hits = mod.scan_csv_for_revit_ids(mod.group_devices(mod.collect_csv_profiles()),
                                      revit_ids)
    assert hits == []


# ---------------------------------------------------------------------------
# 3. IFC space model
# ---------------------------------------------------------------------------
def test_ifc_space_count_and_depth():
    ifc_summary = mod.load_ifc(mod.IFC_PATH)
    assert len(ifc_summary["spaces"]) == 115
    assert ifc_summary["schema"] == "IFC4"
    storeys = Counter(sp["storey"] for sp in ifc_summary["spaces"])
    assert storeys == {"+Kelder": 44, "1. korrus": 29, "2. korrus": 18,
                       "3. korrus": 24}


def test_every_space_has_type_tag():
    ifc_summary = mod.load_ifc(mod.IFC_PATH)
    for sp in ifc_summary["spaces"]:
        assert sp["space_type_tag"], sp
        assert sp["space_type_name"].startswith(f"Space {sp['space_name']}:")
        assert sp["ifc_global_id"]
        assert sp["storey"]
    gids = [sp["ifc_global_id"] for sp in ifc_summary["spaces"]]
    assert len(set(gids)) == 115
    tags = [sp["space_type_tag"] for sp in ifc_summary["spaces"]]
    assert len(set(tags)) == 115
    assert all(t.isdigit() for t in tags)


def test_example_space_matches_task_description():
    """The catalogued example: IfcSpace name '1', tag 4165094, storey +Kelder."""
    ifc_summary = mod.load_ifc(mod.IFC_PATH)
    sp = next(s for s in ifc_summary["spaces"] if s["space_name"] == "1")
    assert sp["space_type_tag"] == "4165094"
    assert sp["space_type_name"] == "Space 1:4165094"
    assert sp["storey"] == "+Kelder"
    assert sp["ifc_global_id"] == "3WAA5EqJ58HBqF0jqdih16"


def test_no_sensor_entities_in_ifc():
    ifc_summary = mod.load_ifc(mod.IFC_PATH)
    assert ifc_summary["sensor_like_entities"] == []


# ---------------------------------------------------------------------------
# 4. Mapping report consistency
# ---------------------------------------------------------------------------
def test_mapping_report_json_valid():
    with open(os.path.join(mod.OUTPUT_DIR, "sensor_ifc_mapping.json"),
              encoding="utf-8") as f:
        rep = json.load(f)
    assert len(rep["mappings"]) == 36
    assert rep["summary"]["total_devices"] == 36
    assert rep["summary"]["mapped_sensors"] == 0
    assert rep["summary"]["unmapped_sensors"] == 36
    assert all(m["confidence"] == "UNMAPPED" for m in rep["mappings"])
    assert rep["identifier_analysis"]["device_uuids_found_in_ifc"] == 0
    assert rep["identifier_analysis"]["sensor_has_room_field"] is False
    assert rep["identifier_analysis"]["mapping_key_found"] is False
    assert len(rep["ifc_spaces_reference"]) == 115


def test_report_md_exists():
    md = os.path.join(mod.DOCS_DIR, "SENSOR_IFC_MAPPING_REPORT.md")
    assert os.path.exists(md)
    with open(md, encoding="utf-8") as f:
        text = f.read()
    assert "No reliable sensor-to-IFC-space mapping" in text
    assert "Revit Element Id" in text