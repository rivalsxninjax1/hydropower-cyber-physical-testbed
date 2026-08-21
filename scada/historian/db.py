"""
Historian + alarm-event database.

A single lightweight SQLite database backs two tables:

  telemetry_log  — one row per poll tick, the full plant state
  alarm_events   — one row per alarm STATE TRANSITION (not every tick)

This is the project's first persistent data store, and becomes the
foundation for:
  - Phase 10's cyber-physical correlation timeline (network event +
    PLC event + physics event + HMI event, all need timestamps to
    correlate against)
  - Phase 15's experiment logging / CSV export
  - Phase 33's metrics (detection time, recovery time, etc.)

A real historian and a real alarm/event log are usually separate
subsystems in an industrial plant. They are combined into one small
SQLite file here deliberately — splitting them into separate services
would add operational complexity (two databases, two connections)
with no benefit at this project's scale. This is a conscious
simplification, not an oversight; see docs/architecture for the
project's "no unnecessary complexity" principle.

Kept deliberately simple: stdlib sqlite3, no ORM, no extra dependency.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

# Module-level so tests can point this at a temporary file instead of
# the real data/logs/historian.db — see scada/tests/test_historian.py.
DB_PATH = REPO_ROOT / "data" / "logs" / "historian.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                reservoir_level_pct REAL,
                gate_position_pct REAL,
                gate_target_pct REAL,
                flow_m3s REAL,
                turbine_rpm REAL,
                generator_power_mw REAL,
                alarm_state TEXT,
                poll_latency_ms REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alarm_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                previous_state TEXT,
                new_state TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plc_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                register INTEGER NOT NULL,
                previous_raw INTEGER,
                new_raw INTEGER NOT NULL,
                description TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def record_telemetry(state: dict) -> None:
    """Insert one telemetry row. Silently skipped if the PLC was
    unreachable — an empty/error state isn't meaningful trend data."""
    if not state.get("plc_connected"):
        return
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO telemetry_log
               (timestamp, reservoir_level_pct, gate_position_pct, gate_target_pct,
                flow_m3s, turbine_rpm, generator_power_mw, alarm_state, poll_latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                state.get("reservoir_level_pct"),
                state.get("gate_position_pct"),
                state.get("gate_target_pct"),
                state.get("flow_m3s"),
                state.get("turbine_rpm"),
                state.get("generator_power_mw"),
                state.get("alarm_state"),
                state.get("poll_latency_ms"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_alarm_transition(previous_state: Optional[str], new_state: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO alarm_events (timestamp, previous_state, new_state) VALUES (?, ?, ?)",
            (time.time(), previous_state, new_state),
        )
        conn.commit()
    finally:
        conn.close()

def record_plc_event(register: int, previous_raw: Optional[int], new_raw: int, description: str = "") -> None:
    """Records the moment the PLC's control loop actually APPLIED a
    changed register value — distinct from the network write itself
    (which the PLC has no way to timestamp independently; it only
    knows about the write once its own polling loop notices the
    register changed). This timestamp gap between a network write and
    the PLC noticing it is itself meaningful data for the correlation
    timeline in security/correlation/build_timeline.py."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO plc_events (timestamp, register, previous_raw, new_raw, description)
               VALUES (?, ?, ?, ?, ?)""",
            (time.time(), register, previous_raw, new_raw, description),
        )
        conn.commit()
    finally:
        conn.close()

def get_recent_telemetry(limit: int = 100) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM telemetry_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_alarm_events(limit: int = 50) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alarm_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_recent_plc_events(limit: int = 50) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM plc_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()