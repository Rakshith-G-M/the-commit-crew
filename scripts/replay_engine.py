"""CampusIQ — Historical Telemetry Replay Engine.

Reads the REAL TalTech historical telemetry CSVs in chronological order and
maintains a "current sensor state" that simulates a live campus feed.

Key design decisions
─────────────────────
* NO random values. Every reading comes verbatim from a CSV row.
* The replay clock advances by the ACTUAL gap between consecutive historical
  readings, compressed by the configured speed multiplier.
* Anomaly detection is evaluated INLINE against the pre-computed baselines
  from output/telemetry_baselines.json — the same baselines used by the
  offline M5/M6 pipeline.
* A bounded rolling history window (max ROLLING_WINDOW_SIZE readings per
  channel) is kept in memory so charts can scroll without loading 1.39M rows.
* In-memory state only — no database; restart = reset.
* All public API is through the ReplayController singleton.
"""

import csv
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "extracted",
)
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output",
)
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "sensor_readings_manifest.json")
BASELINES_PATH = os.path.join(OUTPUT_DIR, "telemetry_baselines.json")

# Deterministic replay start — choose the earliest timestamp that has at least
# one CO₂ reading (most interesting for demo anomaly detection).
REPLAY_START_HINT = "2025-06-01T00:00:00"  # within co2 range, guaranteed anomalies

# How many readings to keep per channel in the rolling window (for charts).
ROLLING_WINDOW_SIZE = 200

# Anomaly z-score thresholds (match offline pipeline defaults).
Z_WARN = 2.5
Z_CRITICAL = 4.0


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Reading:
    sensor_id: str
    timestamp: str          # ISO string from CSV
    measurement_type: str   # normalised (temperature / co2 / humidity / etc.)
    meas_type_raw: str      # original CSV meas_type column
    value: float
    unit: str


@dataclass
class SensorState:
    """Latest known value for one channel."""
    sensor_id: str
    measurement_type: str
    unit: str
    value: float
    timestamp: str
    baseline_mean: Optional[float] = None
    baseline_std: Optional[float] = None
    z_score: Optional[float] = None
    severity: Optional[str] = None       # None / WARN / HIGH / CRITICAL
    rolling: list = field(default_factory=list)  # list of {ts, value}


@dataclass
class ReplayStatus:
    running: bool
    speed: float          # wall-clock multiplier (1/5/10)
    sim_timestamp: str    # current simulated ISO timestamp
    readings_replayed: int
    anomalies_detected: int
    channels_active: int


# ── Baseline loader ────────────────────────────────────────────────────────────

_MEAS_NORM = {
    "TEMPERATURESENSOR": "temperature",
    "CO2SENSOR":         "co2",
    "HUMIDITYSENSOR":    "humidity",
    "PM25SENSOR":        "pm2.5",
    "ENERGYMETER":       "energy",
}


def _normalise(raw: str) -> str:
    return _MEAS_NORM.get(raw.upper(), raw.lower())


class BaselineIndex:
    """Lightweight index over output/telemetry_baselines.json.

    For each (sensor_id, measurement_type) pair we store global mean/std so we
    can compute a z-score for every replayed reading instantly.
    """

    def __init__(self, path: str = BASELINES_PATH) -> None:
        self._index: dict[tuple[str, str], dict] = {}
        if not os.path.exists(path):
            log.warning("Baselines not found at %s — anomaly scoring disabled", path)
            return
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for ch in data.get("channels", []):
            sid = ch.get("sensor_id", "")
            mtype = ch.get("measurement_type", "")
            glb = ch.get("global", {})
            ta  = ch.get("time_aware", {})
            self._index[(sid, mtype)] = {
                "mean": glb.get("mean"),
                "std":  glb.get("std"),
                "hour_grid": ta.get("hour_grid", {}),
            }
        log.info("BaselineIndex loaded %d channels", len(self._index))

    def score(self, sensor_id: str, mtype: str, value: float,
              hour: Optional[int] = None) -> tuple[Optional[float], Optional[str]]:
        """Return (z_score, severity) or (None, None) if no baseline."""
        key = (sensor_id, mtype)
        bl  = self._index.get(key)
        if bl is None:
            return None, None
        # Prefer time-aware (hourly) baseline when hour is supplied
        mean = std = None
        if hour is not None and bl["hour_grid"]:
            hb = bl["hour_grid"].get(str(hour))
            if hb:
                mean = hb.get("mean")
                std  = None  # hour buckets don't store std individually
        if mean is None:
            mean = bl.get("mean")
            std  = bl.get("std")
        if mean is None or std is None or std == 0:
            return None, None
        z = abs(value - mean) / std
        if z >= Z_CRITICAL:
            sev = "CRITICAL"
        elif z >= Z_WARN:
            sev = "HIGH"
        else:
            sev = None
        return round(z, 3), sev


# ── CSV merger ────────────────────────────────────────────────────────────────

class ChronologicalReader:
    """Merges 69 CSVs into a single chronological stream of Readings.

    Uses a file cursor per CSV (not loading all into RAM) — memory O(n_files).
    Readings at or after `start_from` are returned.
    """

    def __init__(
        self,
        data_dir: str = DATA_DIR,
        manifest_path: str = MANIFEST_PATH,
        start_from: str = REPLAY_START_HINT,
    ) -> None:
        self._data_dir = data_dir
        self._start_from = start_from
        self._channels = self._load_channels(manifest_path)
        self._files: dict[str, object] = {}   # channel_key -> open file handle
        self._readers: dict[str, csv.DictReader] = {}
        self._peek: dict[str, Optional[Reading]] = {}  # buffered next row
        self._exhausted: set[str] = set()
        self._open_all()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _load_channels(self, manifest_path: str) -> list[dict]:
        if not os.path.exists(manifest_path):
            # Fallback: glob all CSVs
            import glob
            files = glob.glob(os.path.join(self._data_dir, "*.csv"))
            return [{"file": os.path.basename(f)} for f in files]
        with open(manifest_path, encoding="utf-8") as fh:
            return json.load(fh).get("channels", [])

    def _open_all(self) -> None:
        for ch in self._channels:
            fname = ch.get("file", "")
            fpath = os.path.join(self._data_dir, fname)
            if not os.path.exists(fpath):
                continue
            key = fname
            fh = open(fpath, encoding="utf-8", newline="")
            reader = csv.DictReader(fh)
            self._files[key] = fh
            self._readers[key] = reader
            self._peek[key] = None
            # Advance past rows before start_from
            self._advance_to_start(key)

    def _parse_row(self, key: str, row: dict) -> Optional[Reading]:
        try:
            return Reading(
                sensor_id=row.get("device_id") or row.get("sensor_id", ""),
                timestamp=row.get("timestamp", ""),
                measurement_type=_normalise(row.get("meas_type", "")),
                meas_type_raw=row.get("meas_type", ""),
                value=float(row.get("value", 0)),
                unit=row.get("unit", ""),
            )
        except (ValueError, TypeError):
            return None

    def _advance_to_start(self, key: str) -> None:
        reader = self._readers[key]
        while True:
            try:
                row = next(reader)
                ts = row.get("timestamp", "")
                if ts >= self._start_from:
                    r = self._parse_row(key, row)
                    if r:
                        self._peek[key] = r
                    return
            except StopIteration:
                self._exhausted.add(key)
                return

    def _fill_peek(self, key: str) -> None:
        if key in self._exhausted:
            return
        try:
            row = next(self._readers[key])
            r = self._parse_row(key, row)
            self._peek[key] = r
        except StopIteration:
            self._exhausted.add(key)
            self._peek[key] = None

    # ── public ────────────────────────────────────────────────────────────────

    def next_reading(self) -> Optional[Reading]:
        """Return the globally next chronological reading, or None if done."""
        best_key = None
        best_ts  = None
        for key, r in self._peek.items():
            if r is None:
                continue
            if best_ts is None or r.timestamp < best_ts:
                best_ts  = r.timestamp
                best_key = key
        if best_key is None:
            return None
        reading = self._peek[best_key]
        self._peek[best_key] = None
        self._fill_peek(best_key)
        return reading

    @property
    def exhausted(self) -> bool:
        return all(k in self._exhausted for k in self._readers) and \
               all(v is None for v in self._peek.values())

    def close(self) -> None:
        for fh in self._files.values():
            try:
                fh.close()
            except Exception:
                pass


# ── Replay controller ──────────────────────────────────────────────────────────

class ReplayController:
    """Singleton replay state machine.

    Thread-safe; internal tick loop runs in a daemon thread.
    External callers (FastAPI handlers / WebSocket broadcaster) read state
    through the public properties.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._baselines = BaselineIndex()

        # Replay state
        self._running = False
        self._speed: float = 10.0          # default 10×
        self._reader: Optional[ChronologicalReader] = None
        self._sim_ts: Optional[str] = None  # current simulated timestamp
        self._prev_ts: Optional[str] = None # previous reading's timestamp
        self._wall_prev: Optional[float] = None  # wall clock when prev reading was emitted
        self._readings_replayed: int = 0
        self._anomalies_detected: int = 0

        # Current live state per channel key (sensor_id, mtype)
        self._channel_state: dict[tuple[str, str], SensorState] = {}

        # Bounded rolling history per channel key → list of {ts, value}
        self._rolling: dict[tuple[str, str], list] = {}

        # Event callbacks (for WebSocket broadcast)
        self._on_update_callbacks: list = []

        # Background thread
        self._thread: Optional[threading.Thread] = None

    # ── configuration ────────────────────────────────────────────────────────

    def set_speed(self, speed: float) -> None:
        allowed = {1.0, 5.0, 10.0, 50.0}
        if speed not in allowed:
            speed = min(allowed, key=lambda x: abs(x - speed))
        with self._lock:
            self._speed = speed

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            if self._reader is None:
                self._reader = ChronologicalReader()
            self._running = True
            self._wall_prev = time.monotonic()
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._tick_loop, daemon=True, name="replay-tick"
            )
            self._thread.start()
        log.info("Replay started at speed=%.0f×", self._speed)

    def pause(self) -> None:
        with self._lock:
            self._running = False
        log.info("Replay paused at sim_ts=%s", self._sim_ts)

    def reset(self) -> None:
        with self._lock:
            self._running = False
            if self._reader:
                self._reader.close()
            self._reader = ChronologicalReader()
            self._sim_ts = None
            self._prev_ts = None
            self._wall_prev = None
            self._readings_replayed = 0
            self._anomalies_detected = 0
            self._channel_state.clear()
            self._rolling.clear()
        log.info("Replay reset")

    # ── state accessors ──────────────────────────────────────────────────────

    def get_status(self) -> ReplayStatus:
        with self._lock:
            return ReplayStatus(
                running=self._running,
                speed=self._speed,
                sim_timestamp=self._sim_ts or REPLAY_START_HINT,
                readings_replayed=self._readings_replayed,
                anomalies_detected=self._anomalies_detected,
                channels_active=len(self._channel_state),
            )

    def get_current_state(self) -> dict:
        """Return a snapshot suitable for the /api/replay/current endpoint."""
        with self._lock:
            channels = []
            for (sid, mtype), st in self._channel_state.items():
                channels.append({
                    "sensor_id": sid,
                    "measurement_type": mtype,
                    "unit": st.unit,
                    "value": st.value,
                    "timestamp": st.timestamp,
                    "baseline_mean": st.baseline_mean,
                    "z_score": st.z_score,
                    "severity": st.severity,
                    "location_status": "UNKNOWN_LOCATION",
                })
            # Aggregate by type for summary cards
            by_type: dict[str, list] = {}
            for ch in channels:
                by_type.setdefault(ch["measurement_type"], []).append(ch["value"])
            summaries = {
                mtype: {
                    "count": len(vals),
                    "mean": round(sum(vals) / len(vals), 2),
                    "min":  round(min(vals), 2),
                    "max":  round(max(vals), 2),
                }
                for mtype, vals in by_type.items()
            }
            active_anomalies = [
                ch for ch in channels if ch.get("severity") in ("HIGH", "CRITICAL")
            ]
            return {
                "sim_timestamp": self._sim_ts or REPLAY_START_HINT,
                "running": self._running,
                "speed": self._speed,
                "readings_replayed": self._readings_replayed,
                "anomalies_detected": self._anomalies_detected,
                "channels": channels,
                "summaries": summaries,
                "active_anomalies": active_anomalies,
                "location_note": (
                    "Sensor→space mapping is UNRESOLVED. "
                    "All readings shown at sensor/channel level only."
                ),
            }

    def get_rolling_history(
        self, sensor_id: str, measurement_type: str, limit: int = 100
    ) -> list:
        """Return bounded rolling history for chart rendering."""
        with self._lock:
            key = (sensor_id, measurement_type)
            hist = self._rolling.get(key, [])
            return hist[-limit:]

    def register_update_callback(self, cb) -> None:
        """Register a callable(snapshot) invoked on each reading processed."""
        with self._lock:
            self._on_update_callbacks.append(cb)

    def unregister_update_callback(self, cb) -> None:
        with self._lock:
            try:
                self._on_update_callbacks.remove(cb)
            except ValueError:
                pass

    # ── tick loop ────────────────────────────────────────────────────────────

    def _tick_loop(self) -> None:
        """Background thread: advance replay clock, process readings."""
        while True:
            with self._lock:
                if not self._running:
                    time.sleep(0.05)
                    continue
                reader = self._reader
                if reader is None or reader.exhausted:
                    self._running = False
                    log.info("Replay exhausted — resetting to start")
                    self._reader = ChronologicalReader()
                    time.sleep(0.1)
                    continue
                speed = self._speed
                prev_ts = self._prev_ts
                wall_prev = self._wall_prev

            # Peek at next reading without holding lock
            reading = reader.next_reading()
            if reading is None:
                time.sleep(0.01)
                continue

            # Calculate how long to sleep before emitting this reading
            if prev_ts is not None and wall_prev is not None:
                try:
                    dt_sim = (
                        datetime.fromisoformat(reading.timestamp)
                        - datetime.fromisoformat(prev_ts)
                    ).total_seconds()
                    # Clamp gap: never sleep more than 1s wall-clock between readings
                    dt_wall = min(dt_sim / speed, 1.0)
                    elapsed = time.monotonic() - wall_prev
                    sleep_for = max(0.0, dt_wall - elapsed)
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                except Exception:
                    time.sleep(0.01)
            else:
                time.sleep(0.02)  # brief pause on first reading

            # Process reading
            with self._lock:
                self._process_reading(reading)
                self._prev_ts = reading.timestamp
                self._wall_prev = time.monotonic()
                callbacks = list(self._on_update_callbacks)

            # Fire callbacks outside lock
            snapshot = self.get_current_state()
            for cb in callbacks:
                try:
                    cb(snapshot)
                except Exception as exc:
                    log.debug("Callback error: %s", exc)

    def _process_reading(self, r: Reading) -> None:
        """Update in-memory state with one reading. Must be called under lock."""
        key = (r.sensor_id, r.measurement_type)
        hour: Optional[int] = None
        try:
            hour = datetime.fromisoformat(r.timestamp).hour
        except Exception:
            pass

        z, sev = self._baselines.score(r.sensor_id, r.measurement_type, r.value, hour)
        bl = self._baselines._index.get(key, {})

        st = self._channel_state.get(key)
        if st is None:
            st = SensorState(
                sensor_id=r.sensor_id,
                measurement_type=r.measurement_type,
                unit=r.unit,
                value=r.value,
                timestamp=r.timestamp,
                baseline_mean=bl.get("mean"),
                baseline_std=bl.get("std"),
                z_score=z,
                severity=sev,
            )
            self._channel_state[key] = st
        else:
            st.value = r.value
            st.timestamp = r.timestamp
            st.z_score = z
            st.severity = sev

        # Update rolling history
        hist = self._rolling.setdefault(key, [])
        hist.append({"ts": r.timestamp, "value": r.value})
        if len(hist) > ROLLING_WINDOW_SIZE:
            del hist[:len(hist) - ROLLING_WINDOW_SIZE]

        self._sim_ts = r.timestamp
        self._readings_replayed += 1
        if sev in ("HIGH", "CRITICAL"):
            self._anomalies_detected += 1


# ── Module-level singleton ─────────────────────────────────────────────────────

_controller: Optional[ReplayController] = None


def get_controller() -> ReplayController:
    global _controller
    if _controller is None:
        _controller = ReplayController()
    return _controller
