"""Tests for CampusIQ Historical Telemetry Replay Engine and API Endpoints."""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from fastapi.testclient import TestClient
from api_app import create_app
from replay_engine import (
    ReplayController,
    Reading,
    SensorState,
    get_controller,
)


@pytest.fixture
def replay_ctrl():
    ctrl = ReplayController()
    yield ctrl
    ctrl.pause()
    ctrl.reset()


def test_replay_controller_init(replay_ctrl):
    status = replay_ctrl.get_status()
    assert status.running is False
    assert status.speed == 10.0
    assert status.readings_replayed == 0
    assert status.anomalies_detected == 0
    assert status.channels_active == 0


def test_replay_controller_speed(replay_ctrl):
    replay_ctrl.set_speed(5.0)
    assert replay_ctrl.get_status().speed == 5.0

    replay_ctrl.set_speed(10.0)
    assert replay_ctrl.get_status().speed == 10.0

    # clamps/snaps to closest allowed speed
    replay_ctrl.set_speed(7.0)
    assert replay_ctrl.get_status().speed in (5.0, 10.0)


def test_replay_controller_process_reading(replay_ctrl):
    r = Reading(
        sensor_id="test_sensor_1",
        timestamp="2025-06-01T12:00:00",
        measurement_type="temperature",
        meas_type_raw="TEMPERATURESENSOR",
        value=22.5,
        unit="°C",
    )
    with replay_ctrl._lock:
        replay_ctrl._process_reading(r)

    st = replay_ctrl.get_status()
    assert st.readings_replayed == 1
    assert st.channels_active == 1

    curr = replay_ctrl.get_current_state()
    assert curr["readings_replayed"] == 1
    assert len(curr["channels"]) == 1
    assert curr["channels"][0]["sensor_id"] == "test_sensor_1"
    assert curr["channels"][0]["value"] == 22.5
    assert "temperature" in curr["summaries"]
    assert curr["summaries"]["temperature"]["count"] == 1
    assert curr["summaries"]["temperature"]["mean"] == 22.5


def test_replay_controller_rolling_history(replay_ctrl):
    for i in range(5):
        r = Reading(
            sensor_id="test_sensor_2",
            timestamp=f"2025-06-01T12:0{i}:00",
            measurement_type="co2",
            meas_type_raw="CO2SENSOR",
            value=400.0 + i * 50,
            unit="ppm",
        )
        with replay_ctrl._lock:
            replay_ctrl._process_reading(r)

    hist = replay_ctrl.get_rolling_history("test_sensor_2", "co2", limit=3)
    assert len(hist) == 3
    assert hist[-1]["value"] == 600.0


def test_api_replay_endpoints():
    app = create_app()
    client = TestClient(app)

    # Status
    res = client.get("/api/replay/status")
    assert res.status_code == 200
    data = res.json()
    assert "running" in data
    assert "speed" in data
    assert "sim_timestamp" in data

    # Speed
    res = client.post("/api/replay/speed", json={"speed": 5.0})
    assert res.status_code == 200
    assert res.json()["speed"] == 5.0

    # Start
    res = client.post("/api/replay/start")
    assert res.status_code == 200
    assert res.json()["status"] == "started"
    assert res.json()["running"] is True

    # Current state
    res = client.get("/api/replay/current")
    assert res.status_code == 200
    curr = res.json()
    assert "channels" in curr
    assert "summaries" in curr

    # Pause
    res = client.post("/api/replay/pause")
    assert res.status_code == 200
    assert res.json()["status"] == "paused"
    assert res.json()["running"] is False

    # Reset
    res = client.post("/api/replay/reset")
    assert res.status_code == 200
    assert res.json()["status"] == "reset"
