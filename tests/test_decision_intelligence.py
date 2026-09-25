"""CampusIQ M6 — decision intelligence tests.

Covers the three M6 parts plus their guarantee tests:

  Part 1  forecasting         — generation, per-channel coverage, timestamps,
                                insufficient-history handling, determinism.
  Part 2  resource state      — 115 spaces, BIM design-vs-measured distinction,
                                storey/building aggregates.
  Part 3  decision candidates — anomaly->candidate conversion, UNKNOWN vs
                                VERIFIED_BIM location handling, allocation
                                capacity filtering, no fabricated schedules,
                                deterministic outputs.

Read-only w.r.t. raw datasets; synthetic channels/spaces are built inline.
"""

import hashlib
import json
import os
import sys
import tempfile

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

import decision_engine  # noqa: E402
import forecaster  # noqa: E402
import resource_state  # noqa: E402
import telemetry_config as tcfg  # noqa: E402

OUT_DIR = tcfg.OUTPUT_DIR
DAY = 24
WEEK = 7 * DAY


def _buckets(median_base: float = 20.0, count: int = 92) -> list[dict]:
    """Full 168 dow x hour robust bucket grid (median/count)."""
    return [
        {
            "dow": d,
            "hour": h,
            "count": count,
            "mean": median_base,
            "median": median_base,
            "std": 1.0,
            "mad": 0.4,
        }
        for d in range(7)
        for h in range(24)
    ]


def make_channel(
    sensor_uuid: str,
    mt: str = "temperature",
    unit: str = "C",
    last_ts: str = "2025-06-30T23:45:20",
    survivors: int = 3,
    record_count: int = 15000,
) -> dict:
    return {
        "sensor_id": sensor_uuid,
        "measurement_type": mt,
        "unit": unit,
        "file": f"{sensor_uuid}.csv",
        "first_timestamp": "2025-02-07T12:15:22",
        "last_timestamp": last_ts,
        "record_count": record_count,
        "max": 40.0,
        "time_aware": {
            "coverage_buckets": 168,
            "expected_buckets": 168,
            "buckets": _buckets(),
        },
        "recent_window": {
            "last_96_samples": {"count": 96, "mean": 22.746458},
            "last_7_days": {"count": 399, "mean": 22.72},
        },
        "anomaly_summary": {
            "candidates_surviving": survivors,
            "scored_raw": True,
            "capped_detail": False,
            "recorded_detail_count": survivors,
        },
        "baseline": {"recommended_baseline": "time_aware_hour_of_day"},
    }


def make_baseline(sensor_uuid: str, mt: str = "temperature", unit: str = "C") -> dict:
    return {
        "sensor_id": sensor_uuid,
        "measurement_type": mt,
        "unit": unit,
        "recommended_baseline": "time_aware_hour_of_day",
        "global": {
            "sample_count": 15000,
            "mean": 22.68,
            "median": 22.59,
            "std": 0.89,
            "sufficient_history": True,
        },
        "hour_grid": {str(h): {"mean": 22.0, "count": 100} for h in range(24)},
    }


def make_mapping(sensor_uuid: str, status: str = "UNRESOLVED") -> dict:
    return {
        "sensor_id": sensor_uuid,
        "space_id": None,
        "location_status": "UNKNOWN_LOCATION",
        "status": status,
        "confidence": 0.0,
        "mapping_method": "none_found" if status == "UNRESOLVED" else "some_method",
        "location_verified": False,
    }


def make_health(sensor_uuid: str) -> dict:
    return {
        "sensor_id": sensor_uuid,
        "health_status": "DEGRADED",
        "anomaly_candidates": 185,
        "issues": [
            {"type": "LONG_GAP", "max_severity": "MEDIUM", "affected_channels": 1,
             "example": {"detail": "largest gap 66.0 h"}},
        ],
        "location": {"space_id": None, "location_status": "UNKNOWN_LOCATION",
                     "location_verified": False},
    }


def make_space(space_id: str, area: float, capacity: float) -> dict:
    """Resource-record shaped like `resource_state` output spaces."""
    return {
        "space_id": space_id,
        "building_id": "building_1",
        "storey_id": "storey_1",
        "geometry": {"area_m2": area, "volume_m3": area * 3.0, "height_m": 3.0},
        "capacity_occupants": capacity,
        "occupancy": {"occupiable": True, "capacity_occupants": capacity},
        "lighting": {"value": {"value": 120.0, "metric_origin": "BIM_DESIGN"}},
        "power": {"value": {"value": 200.0, "metric_origin": "BIM_DESIGN"}},
    }


def _dump_forecast_inputs(tmp: str) -> tuple[str, str, str]:
    prof = {"channels": [make_channel("sen-1"), make_channel("sen-2", "co2", "ppm")]}
    baselines = {
        "channels": [make_baseline("sen-1"), make_baseline("sen-2", "co2", "ppm")]
    }
    mapping = {"mappings": [make_mapping("sen-1"), make_mapping("sen-2")]}
    p, b, m = (os.path.join(tmp, k) for k in ("profile.json", "baselines.json", "mapping.json"))
    for path, doc in ((p, prof), (b, baselines), (m, mapping)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
    return p, b, m


# ---- Part 1: forecasting -------------------------------------------------

def test_forecast_generation():
    cfg = dict(tcfg.FORECAST)
    cfg["measurements"] = {"temperature", "co2", "humidity", "pm2.5"}
    with tempfile.TemporaryDirectory() as tmp:
        p, b, m = _dump_forecast_inputs(tmp)
        out = forecaster.build_forecasts(p, b, m, cfg=cfg)
    assert out["summary"]["channels_forecasted"] == 2
    recs = [r for r in out["records"] if "skip_reason" not in r]
    assert len(recs) == 2 * len(cfg["horizons_hours"])
    for r in recs:
        assert r["prediction_method"] == "time_aware_seasonal_blend"
        assert r["predicted_value"] is not None
        assert r["baseline_value"] is not None
        assert r["coverage"]["confidence_intervals_calculated"] is False
        assert r["confidence_interval_95"] is None
        for key in ("sensor_id", "measurement_type", "forecast_timestamp",
                    "predicted_value", "baseline_value", "prediction_method",
                    "location_status", "confidence"):
            assert key in r


def test_forecast_skip_insufficient_history():
    channel = make_channel("sen-3")
    channel["time_aware"]["buckets"] = [{"dow": 0, "hour": 0, "count": 1, "median": 20.0}]
    bl = make_baseline("sen-3")
    cfg = dict(tcfg.FORECAST)
    cfg["measurements"] = {"temperature", "co2", "humidity", "pm2.5"}
    reason = forecaster.channel_skip_reason(channel, bl, horizon=1.0, cfg=cfg)
    assert reason is not None
    assert reason["reason"] == forecaster.SKIP_REASON_BUCKET_SAMPLES


def test_forecast_energy_cumulative_register_skipped():
    cfg = dict(tcfg.FORECAST)
    cfg["measurements"] = {"temperature", "co2", "humidity", "pm2.5"}
    with tempfile.TemporaryDirectory() as tmp:
        prof = {"channels": [make_channel("sen-energy", "energy", "kWh"),
                             make_channel("sen-t", "temperature", "C")]}
        baselines = {"channels": [make_baseline("sen-energy", "energy", "kWh"),
                                  make_baseline("sen-t", "temperature", "C")]}
        mapping = {"mappings": [make_mapping("sen-energy"), make_mapping("sen-t")]}
        p, b, m = (os.path.join(tmp, k) for k in ("p.json", "b.json", "m.json"))
        for path, doc in ((p, prof), (b, baselines), (m, mapping)):
            json.dump(doc, open(path, "w"))
        out = forecaster.build_forecasts(p, b, m, cfg=cfg)
    assert out["summary"]["skipped_by_reason"] == {"cumulative_register": 1}
    assert out["summary"]["channels_forecasted"] == 1


def test_forecast_timestamps_exact():
    cfg = dict(tcfg.FORECAST)
    cfg["measurements"] = {"temperature", "co2", "humidity", "pm2.5"}
    from datetime import datetime as _dt
    with tempfile.TemporaryDirectory() as tmp:
        p, b, m = _dump_forecast_inputs(tmp)
        out = forecaster.build_forecasts(p, b, m, cfg=cfg)
    rec = [r for r in out["records"] if "skip_reason" not in r and r["sensor_id"] == "sen-1"][0]
    as_of = _dt.fromisoformat(rec["as_of_timestamp"])
    fc = _dt.fromisoformat(rec["forecast_timestamp"])
    assert (fc - as_of).total_seconds() / 3600 == rec["horizon_hours"]


def test_forecast_deterministic():
    cfg = dict(tcfg.FORECAST)
    cfg["measurements"] = {"temperature", "co2", "humidity", "pm2.5"}
    with tempfile.TemporaryDirectory() as tmp:
        p, b, m = _dump_forecast_inputs(tmp)
        out1 = forecaster.build_forecasts(p, b, m, cfg=cfg)
        out2 = forecaster.build_forecasts(p, b, m, cfg=cfg)
    assert json.dumps(out1, sort_keys=True) == json.dumps(out2, sort_keys=True)


# ---- Part 2: resource state ---------------------------------------------

def test_resource_state_extracts_115():
    rs_path = os.path.join(OUT_DIR, "resource_state.json")
    assert os.path.exists(rs_path)
    rs = json.load(open(rs_path, encoding="utf-8"))
    assert rs["summary"]["space_count"] == 115
    for s in rs["spaces"]:
        assert s["space_id"] and s["geometry"]["area_m2"]
        assert s["design_metrics"]["metric_origin"] == "BIM_DESIGN"


def test_bim_design_vs_measured():
    rs = json.load(open(os.path.join(OUT_DIR, "resource_state.json"), encoding="utf-8"))
    space = rs["spaces"][0]
    assert space["lighting"]["metric_origin"] == "BIM_DESIGN"
    assert space["lighting"]["is_measured"] is False
    assert space["power"]["metric_origin"] == "BIM_DESIGN"
    assert space["measurements"]["measured_energy_consumption"] is None
    assert space["measurements"]["measured_consumption_available"] is False
    rs2 = json.load(open(os.path.join(OUT_DIR, "resource_state.json"), encoding="utf-8"))
    assert rs2 == rs


def test_resource_state_storey_aggregates():
    rs = json.load(open(os.path.join(OUT_DIR, "resource_state.json"), encoding="utf-8"))
    assert rs["summary"]["storey_count"] == 4
    storeys = sorted(rs["storeys"], key=lambda s: s["storey_id"])
    assert sum(s["space_count"] for s in storeys) == 115


# ---- Part 3: decision candidates ----------------------------------------

def _cand_inputs() -> dict:
    profile = {"channels": [make_channel("sen-1"), make_channel("sen-2", "co2", "ppm", survivors=0)]}
    health = {"devices": [make_health("sen-1")]}
    mapping = {"mappings": [make_mapping("sen-1")]}
    return {
        "profile": profile,
        "health": health,
        "mapping": mapping,
        "forecasts": {"records": [], "forecast": {"horizons_hours": [1, 6, 24]}},
        "spaces": [make_space("space_A", 50.0, 12.0), make_space("space_B", 20.0, 3.0)],
    }


def test_anomaly_to_decision_candidate():
    inp = _cand_inputs()
    cfg = tcfg.DECISION
    out = decision_engine.build_decision_candidates(
        profile=inp["profile"], health=inp["health"], forecasts=inp["forecasts"],
        mapping=inp["mapping"], spaces=inp["spaces"], requests=None, cfg=cfg)
    kinds = {r["candidate_type"] for r in out["records"]}
    assert "ANOMALY" in kinds and "MAINTENANCE" in kinds
    anom = next(r for r in out["records"] if r["problem_type"] == "COMFORT")
    assert anom["source"] == "M5_TELEMETRY_ANOMALIES"
    assert anom["proposed_action"]
    assert anom["reason"]
    assert anom["evidence"]["surviving_candidates"] == 3


def test_unknown_location_propagation():
    inp = _cand_inputs()
    inp["mapping"] = {"mappings": [make_mapping("sen-1", "UNRESOLVED")]}
    out = decision_engine.build_decision_candidates(**inp, cfg=tcfg.DECISION)
    for r in out["records"]:
        if r["candidate_type"] in ("ANOMALY", "MAINTENANCE"):
            assert r["location_status"] == "UNKNOWN"


def test_verified_bim_allocation():
    inp = _cand_inputs()
    requests = [{"request_id": "req-1", "required_capacity": 8}]
    out = decision_engine.build_decision_candidates(**inp, requests=requests, cfg=tcfg.DECISION)
    alloc = [r for r in out["records"] if r["candidate_type"] == "ALLOCATION"]
    assert alloc and alloc[0]["location_status"] == "VERIFIED_BIM"
    assert alloc[0]["location"]["space_id"] == "space_A"


def test_allocation_capacity_filtering():
    cfg = tcfg.DECISION
    spaces = [make_space("space_A", 50.0, 12.0), make_space("space_B", 20.0, 3.0)]
    res = decision_engine.allocate(required_capacity=6, spaces=spaces, cfg=cfg)
    assert res["satisfied"] is True
    assert [s["space_id"] for s in res["suitable"]] == ["space_A"]
    assert {e["space_id"] for e in res["excluded"]} == {"space_B"}
    # availability excludes even a capacious space
    res2 = decision_engine.allocate(
        required_capacity=6, spaces=spaces, availability={"space_A": False}, cfg=cfg)
    assert res2["satisfied"] is False
    assert "not_available" in res2["excluded"][0]["reason"]


def test_allocate_respects_equipment():
    cfg = dict(tcfg.DECISION)
    spaces = [make_space("space_A", 50.0, 12.0), make_space("space_B", 50.0, 12.0)]
    spaces[1]["lighting"] = {"value": None}
    res = decision_engine.allocate(
        required_capacity=4, spaces=spaces, equipment=["lighting"], cfg=cfg)
    assert [s["space_id"] for s in res["suitable"]] == ["space_A"]


def test_no_fabricated_schedules():
    inp = _cand_inputs()
    out = decision_engine.build_decision_candidates(**inp, cfg=tcfg.DECISION)
    assert out["summary"]["requests_processed"] == 0
    assert not any(r["candidate_type"] == "ALLOCATION" for r in out["records"])
    rs = json.load(open(os.path.join(OUT_DIR, "resource_state.json"), encoding="utf-8"))
    assert rs["availability"]["present"] is False


def test_deterministic_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        p, b, m = _dump_forecast_inputs_copy(tmp)
        # run pipeline twice into separate dirs, comparing digests
        digests = []
        for sub in ("run1", "run2"):
            out_dir = os.path.join(tmp, sub)
            os.makedirs(out_dir)
            from decision_intelligence import run_pipeline
            paths = run_pipeline(m5_dir=tmp, out_dir=out_dir,
                                 docs_dir=os.path.join(out_dir, "docs"))
            combined = []
            for name in ("forecasts.json", "resource_state.json", "decision_candidates.json"):
                with open(paths[name], "rb") as fh:
                    combined.append(fh.read())
            digests.append(hashlib.sha256(b"".join(combined)).hexdigest())
        assert digests[0] == digests[1]


def _dump_forecast_inputs_copy(tmp: str):
    # real M5 artefacts drive the end-to-end determinism test
    for name in ("telemetry_profile.json", "telemetry_baselines.json",
                 "sensor_space_mapping.json", "sensor_health.json",
                 "spaces.json", "campus_registry.json"):
        with open(os.path.join(OUT_DIR, name), "rb") as src, \
                open(os.path.join(tmp, name), "wb") as dst:
            dst.write(src.read())
    return tmp, tmp, tmp