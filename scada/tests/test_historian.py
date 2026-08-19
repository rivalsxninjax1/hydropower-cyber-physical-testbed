"""
Tests for scada/historian/db.py.

Each test points DB_PATH at a temporary file so these tests never
touch (or depend on) the real data/logs/historian.db.

Run with:  pytest scada/tests/test_historian.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scada.historian import db


def use_temp_db(tmp_path):
    db.DB_PATH = tmp_path / "test_historian.db"
    db.init_db()


def test_init_db_creates_file(tmp_path):
    use_temp_db(tmp_path)
    assert db.DB_PATH.exists()


def test_record_and_read_telemetry(tmp_path):
    use_temp_db(tmp_path)
    state = {
        "plc_connected": True,
        "reservoir_level_pct": 72.0,
        "gate_position_pct": 45.0,
        "gate_target_pct": 45.0,
        "flow_m3s": 68.7,
        "turbine_rpm": 1500.0,
        "generator_power_mw": 31.3,
        "alarm_state": "NORMAL",
        "poll_latency_ms": 0.5,
    }
    db.record_telemetry(state)

    rows = db.get_recent_telemetry(limit=10)
    assert len(rows) == 1
    assert rows[0]["reservoir_level_pct"] == 72.0
    assert rows[0]["alarm_state"] == "NORMAL"


def test_telemetry_skipped_when_plc_disconnected(tmp_path):
    use_temp_db(tmp_path)
    db.record_telemetry({"plc_connected": False, "error": "unreachable"})

    rows = db.get_recent_telemetry(limit=10)
    assert len(rows) == 0


def test_recent_telemetry_returns_most_recent_first(tmp_path):
    use_temp_db(tmp_path)
    for level in [10.0, 20.0, 30.0]:
        db.record_telemetry({"plc_connected": True, "reservoir_level_pct": level})

    rows = db.get_recent_telemetry(limit=10)
    assert rows[0]["reservoir_level_pct"] == 30.0
    assert rows[-1]["reservoir_level_pct"] == 10.0


def test_recent_telemetry_respects_limit(tmp_path):
    use_temp_db(tmp_path)
    for i in range(20):
        db.record_telemetry({"plc_connected": True, "reservoir_level_pct": float(i)})

    rows = db.get_recent_telemetry(limit=5)
    assert len(rows) == 5


def test_record_and_read_alarm_transition(tmp_path):
    use_temp_db(tmp_path)
    db.record_alarm_transition(previous_state=None, new_state="NORMAL")
    db.record_alarm_transition(previous_state="NORMAL", new_state="WARNING")
    db.record_alarm_transition(previous_state="WARNING", new_state="CRITICAL")

    events = db.get_recent_alarm_events(limit=10)
    assert len(events) == 3
    assert events[0]["new_state"] == "CRITICAL"
    assert events[0]["previous_state"] == "WARNING"
    assert events[-1]["previous_state"] is None