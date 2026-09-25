"""CampusIQ M5 — telemetry intelligence engine tests.

Two layers:
  1. unit/behaviour tests on synthetic channel CSVs (fast, deterministic,
     exercising duplicate/gap/out-of-range detection, spike persistence,
     rolling/global baseline fallback, insufficient-history handling, the
     sensor-health rubric and M4 location propagation);
  2. integration checks against the generated `output/` artefacts and the
     pinned raw CSV hashes (read-only guard) — telemetry never rewrites raw.

Read-only w.r.t. the source data.
"""

import csv
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
sys.path.insert(0, os.path.join(BASE_DIR, "tests"))

import investigate_sensor_ifc_mapping as source  # noqa: E402
import telemetry_anomaly  # noqa: E402
import telemetry_baseline  # noqa: E402
import telemetry_config as cfg  # noqa: E402
import telemetry_features  # noqa: E402
import telemetry_health  # noqa: E402
import telemetry_profile  # noqa: E402
from test_sensor_ingestion import CSV_SHA256  # noqa: E402

OUT_DIR = cfg.OUTPUT_DIR
TEMP_UUID = "aaaaaaaa-0000-4000-8000-000000000000"
ENERGY_UUID = "bbbbbbbb-0000-4000-8000-000000000000"
HEALTHY_UUID = "cccccccc-0000-4000-8000-000000000000"


def _load(name: str) -> dict:
    with open(os.path.join(OUT_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_csv(dirpath: str, fname: str, rows: list[tuple]) -> str:
    path = os.path.join(dirpath, fname)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["device_id", "timestamp", "meas_type", "value", "unit"])
        w.writerows(rows)
    return path


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _make_temp_channel(dirpath: str) -> str:
    """14 days / 15-min temperature with duplicates, a 6h gap, a 3-reading
    35C spike, and an out-of-range 200C reading."""
    rng = np.random.default_rng(7)
    rows = []
    t = datetime(2025, 1, 1, 0, 0)
    for i in range(14 * 96 + 400):
        if i == 14 * 96 // 2:  # inject a 6h gap (24 samples)
            t += timedelta(hours=6)
        ts = _iso(t)
        base = 20.0 + 1.2 * np.sin(i * 0.05) + float(rng.normal(0, 0.3))
        if i == 400:  # out-of-range
            base = 200.0
        elif 600 <= i <= 602:  # 3-reading spike
            base = 35.0
        rows.append((TEMP_UUID, ts, "TEMPERATURESENSOR",
                     f"{base:.3f}", "C"))
        if i == 700:  # duplicate timestamp
            rows.append((TEMP_UUID, ts, "TEMPERATURESENSOR",
                         f"{base + 0.5:.3f}", "C"))
        t += timedelta(minutes=15)
    return _write_csv(dirpath, f"{TEMP_UUID}_TEMPERATURESENSOR.csv", rows)


def _make_energy_channel(dirpath: str) -> str:
    """Cumulative kWh register: constant within a day, ~80/day, one 1000kWh
    day -> a clear daily-delta anomaly on the derived curve."""
    rows = []
    t = datetime(2025, 2, 1, 0, 0)
    register = 5000.0
    for day in range(30):
        daily = 80.0
        if day == 25:
            daily = 1000.0
        register += daily
        for k in range(96):
            rows.append((ENERGY_UUID, _iso(t), "ENERGYMETER",
                         f"{register:.1f}", "kWh"))
            t += timedelta(minutes=15)
    return _write_csv(dirpath, f"{ENERGY_UUID}_ENERGYMETER.csv", rows)


def _make_healthy_channel(dirpath: str) -> str:
    """3 days of perfectly regular, gently-varying temperature -> no
    MEDIUM/HIGH health issues."""
    rows = []
    t = datetime(2025, 3, 1, 0, 0)
    for i in range(3 * 96):
        value = 21.0 + 0.3 * np.sin(i * 0.2)
        rows.append((HEALTHY_UUID, _iso(t), "TEMPERATURESENSOR",
                     f"{value:.2f}", "C"))
        t += timedelta(minutes=15)
    return _write_csv(dirpath, f"{HEALTHY_UUID}_TEMPERATURESENSOR.csv", rows)


@pytest.fixture(scope="module")
def synthetic_dir():
    with tempfile.TemporaryDirectory() as d:
        _make_temp_channel(d)
        _make_energy_channel(d)
        _make_healthy_channel(d)
        yield d


@pytest.fixture(scope="module")
def synthetic_analyses(synthetic_dir):
    return telemetry_profile.analyze_all(synthetic_dir)


def _analysis_by_type(analyses, mt: str):
    return [a for a in analyses if a["measurement_type"] == mt]


# ---------------------------------------------------------------------------
# 1–7  Profile / normalization / quality (synthetic + real)
# ---------------------------------------------------------------------------
def test_real_profile_69_channels():
    p = _load("telemetry_profile.json")
    assert p["summary"]["channels"] == 69


def test_real_profile_36_devices():
    p = _load("telemetry_profile.json")
    assert p["summary"]["sensors"] == 36


def test_real_profile_total_readings():
    p = _load("telemetry_profile.json")
    assert p["summary"]["total_readings"] == 1_390_297


def test_normalize_sorts_and_counts_duplicates(synthetic_dir,
                                               synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    assert temp["duplicate_timestamp_count"] >= 1
    assert temp["quality"]["DUPLICATE"] >= 1
    assert temp["first_timestamp"] == "2025-01-01T00:00:00"
    assert "T" in temp["last_timestamp"]


def test_gap_detection_finds_6h_gap(synthetic_dir, synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    assert temp["gaps"]["count"] >= 1
    assert temp["gaps"]["largest_seconds"] >= 6 * 3600 - 60


def test_quality_flags_present_and_oor_detected(synthetic_dir,
                                                synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    assert set(cfg.QUALITY_FLAGS).issubset(temp["quality"])
    assert temp["quality"]["OUT_OF_RANGE"] >= 1  # the 200C reading
    assert temp["quality"]["VALID"] == temp["record_count"] - temp["quality"]["OUT_OF_RANGE"]


def test_quality_totals_real_dataset_clean_values():
    p = _load("telemetry_profile.json")
    qt = p["summary"]["quality_totals"]
    assert qt["VALID"] == p["summary"]["total_readings"]
    assert qt["OUT_OF_RANGE"] >= 0
    assert qt["TIME_GAP"] > 0


def test_every_channel_has_full_profile_fields():
    p = _load("telemetry_profile.json")
    need = {"sensor_id", "measurement_type", "unit", "record_count",
            "first_timestamp", "last_timestamp", "min", "max", "mean",
            "median", "std", "quality", "gaps", "percentiles", "baseline",
            "rate_of_change", "anomaly_summary", "health"}
    for ch in p["channels"]:
        assert need.issubset(ch)


# ---------------------------------------------------------------------------
# 8–9  Baselines
# ---------------------------------------------------------------------------
def test_baseline_structure_and_recommendation(synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    b = telemetry_baseline.channel_baseline(temp)
    assert b["global"]["sufficient_history"] is True
    assert b["recommended_baseline"] == "time_aware_hour_of_day"
    assert b["rolling"]["window_samples"] == 96
    assert "hour_grid" in b["time_aware"]
    assert b["time_aware"]["expected_buckets"] == 168


def test_insufficient_history_falls_back_to_global(synthetic_analyses):
    healthy = _analysis_by_type(synthetic_analyses, "temperature")[-1]
    b = telemetry_baseline.channel_baseline(healthy)
    assert b["global"]["sufficient_history"] is False
    assert b["recommended_baseline"] == "global_gaussian"


def test_real_baselines_all_channels(synthetic_analyses):
    p = _load("telemetry_baselines.json")
    assert p["summary"]["channels"] == 69
    assert p["summary"]["sufficient_history"] >= 1


# ---------------------------------------------------------------------------
# 10–13  Anomaly detection (methods, persistence, severity)
# ---------------------------------------------------------------------------
def test_spike_detected_with_persistence(synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    spikes = [r for r in temp["anomalies"] if r["value"] >= 30]
    assert spikes, "35C 3-reading spike should be flagged"
    assert max(r["persistence"] for r in spikes) >= 2
    assert all(r["method"] in ("time_aware", "rolling", "z_score")
               for r in spikes)


def test_mad_secondary_signal_populated(synthetic_analyses):
    temp = _analysis_by_type(synthetic_analyses, "temperature")[0]
    rec = temp["anomalies"][0]
    assert rec["signals"]["z_mad"] is not None
    assert rec["signals"]["z_global"] is not None
    assert rec["severity_score"] >= rec["score"]


def test_energy_rolling_fallback_on_derived_curve(synthetic_analyses):
    energy = _analysis_by_type(synthetic_analyses, "energy")[0]
    assert energy["energy_registers"]["derived_sample_count"] >= 3
    big = [r for r in energy["anomalies"] if r["value"] >= 500]
    assert big, "1000kWh day should be detected on the daily-delta curve"
    assert {r["method"] for r in big} <= {"rolling", "z_score", "time_aware"}


def test_severity_bands_exact():
    assert cfg.classify_severity(3.4) == "LOW"
    assert cfg.classify_severity(3.5) == "LOW"
    assert cfg.classify_severity(4.5) == "MEDIUM"
    assert cfg.classify_severity(6.0) == "HIGH"
    assert cfg.classify_severity(8.0) == "CRITICAL"


def test_anomaly_intelligence_fields_and_categories(synthetic_analyses):
    mapping = {TEMP_UUID: {"space_id": "space_x", "location_status": "MAPPED",
                           "location_verified": True, "status": "CONFIRMED",
                           "confidence": 0.95}}
    rec = dict(synthetic_analyses[0]["anomalies"][0])
    aug = telemetry_anomaly.augment(rec, mapping)
    for key in ("severity", "category", "explanation", "space_id",
                "location_status", "mapping_status", "location_verified"):
        assert key in aug, key
    assert aug["space_id"] == "space_x"
    assert aug["mapping_status"] == "CONFIRMED"
    # out-of-range value => DATA_QUALITY category
    oor = dict(rec)
    oor["measurement_type"] = "temperature"
    oor["value"] = 200.0
    assert telemetry_anomaly.category_for(oor) == "DATA_QUALITY"
    # energy => RESOURCE
    eng = dict(rec)
    eng["measurement_type"] = "energy"
    assert telemetry_anomaly.category_for(eng) == "RESOURCE"


def test_real_anomalies_unknown_location():
    a = _load("anomalies.json")
    assert a["summary"]["total_candidates"] >= 1
    for r in a["anomalies"]:
        assert r["location_status"] == "UNKNOWN_LOCATION"
        assert r["space_id"] is None
    assert set(a["summary"]["by_severity"]).issubset(
        {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
    assert set(a["summary"]["by_category"]).issubset(
        {"ENVIRONMENTAL", "RESOURCE", "DATA_QUALITY"})


def test_real_anomalies_explain_and_consume(synthetic_analyses):
    a = _load("anomalies.json")
    assert a["summary"]["total_candidates"] >= a["summary"]["recorded_detail"]
    assert a["summary"]["by_method"], "per-method totals present"
    assert a["thresholds"]["candidate_z"] == 3.5


# ---------------------------------------------------------------------------
# 14  Sensor health
# ---------------------------------------------------------------------------
def test_health_rubric(synthetic_analyses):
    tmp_ch = _analysis_by_type(synthetic_analyses, "temperature")[0]
    health = telemetry_health.sensor_health(TEMP_UUID, [tmp_ch], 30.0, {})
    assert health["health_status"] in ("DEGRADED", "FAILED")
    assert health["valid_readings"] > 0
    assert len(health["issues"]) >= 1

    healthy_ch = _analysis_by_type(synthetic_analyses, "temperature")[-1]
    ok = telemetry_health.sensor_health(HEALTHY_UUID, [healthy_ch], 30.0, {})
    assert ok["health_status"] == "HEALTHY"
    assert ok["issues"] == []


def test_real_sensor_health_records():
    h = _load("sensor_health.json")
    assert h["summary"]["devices"] == 36
    assert h["summary"]["health_status_distribution"]
    for d in h["devices"]:
        assert d["health_status"] in ("HEALTHY", "DEGRADED", "FAILED")
        assert d["channels"]


# ---------------------------------------------------------------------------
# 16  Location propagation from M4 mapping
# ---------------------------------------------------------------------------
def test_synthetic_mapping_propagates_to_health(synthetic_analyses):
    mapping = {TEMP_UUID: {"space_id": "space_x", "location_status": "MAPPED",
                           "location_verified": True, "status": "CONFIRMED",
                           "confidence": 0.95}}
    payload = telemetry_health.build_payload(synthetic_analyses, mapping)
    by_id = {d["sensor_id"]: d for d in payload["devices"]}
    assert by_id[TEMP_UUID]["location"]["space_id"] == "space_x"
    assert by_id[TEMP_UUID]["location"]["location_status"] == "MAPPED"


def test_mapping_load_reads_m4_file():
    mapping = telemetry_anomaly.load_mapping()
    assert len(mapping) == 36
    assert all(not (m.get("space_id")) for m in mapping.values())


# ---------------------------------------------------------------------------
# 17  Determinism and raw-data integrity
# ---------------------------------------------------------------------------
def test_pipeline_byte_deterministic(synthetic_dir):
    with tempfile.TemporaryDirectory() as oa, tempfile.TemporaryDirectory() as ob:
        telemetry_intelligence.run_pipeline(synthetic_dir, oa, report_docs_dir=oa)
        telemetry_intelligence.run_pipeline(synthetic_dir, ob, report_docs_dir=ob)
        files = ["telemetry_profile.json", "telemetry_baselines.json",
                 "telemetry_features.json", "anomalies.json",
                 "sensor_health.json", "telemetry_intelligence_summary.json"]
        for fn in files:
            with open(os.path.join(oa, fn), "rb") as fa, \
                    open(os.path.join(ob, fn), "rb") as fb:
                assert fa.read() == fb.read(), f"{fn} not deterministic"


def test_raw_csv_hashes_unchanged():
    samples = ["04f80f82-e206-427c-a913-69758a1ec283_TEMPERATURESENSOR.csv",
               "065931eb-3930-492c-ac91-85a0936fcf82_ENERGYMETER.csv"]
    for name in samples:
        h = hashlib.sha256()
        with open(os.path.join(source.CSV_DATA_DIR, name), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        assert h.hexdigest() == CSV_SHA256[name], f"{name} modified"


# import here so the fixture-driven determinism test can use the orchestrator
import telemetry_intelligence  # noqa: E402