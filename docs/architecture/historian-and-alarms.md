# Historian and Alarm Event Log

## What this is

`scada/historian/db.py` is a single lightweight SQLite database
(`data/logs/historian.db`) backing two tables:

- **`telemetry_log`** — one row per poll tick (1/second), the full
  plant state as read from the PLC.
- **`alarm_events`** — one row per alarm state *transition*
  (NORMAL→WARNING, WARNING→CRITICAL, etc.), not every tick.

A real industrial plant typically has a separate Historian and a
separate Alarm/Event Manager. They are combined into one small SQLite
file here deliberately: splitting them into two services would add
operational complexity (two databases, two connections, two things
that can fail) with no real benefit at this project's scale. This is
a stated simplification, not an oversight.

## Why the alarm log matters more than it looks

Recording every tick's alarm state would produce mostly duplicate rows
(the plant sits in NORMAL for long stretches). Recording only
*transitions* gives a clean, sparse timeline of exactly the moments
something changed — which is exactly what Phase 10's cyber-physical
correlation timeline needs: the ability to line up "network event at
10:42:19" against "alarm transition at 10:42:26" and show the delay
between cause and effect.

## API endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/history?limit=100` | Most recent telemetry rows, newest first |
| `GET /api/alarms?limit=50` | Most recent alarm transitions, newest first |

## Verified behavior

Tested end-to-end: sending a gate command that pushed the plant from
NORMAL into WARNING produced exactly one new row in `alarm_events`
(`NORMAL → WARNING`), while `telemetry_log` continued accumulating one
row per second as expected — confirming the transition-only logic
works and isn't just logging every tick.

## Automated tests

`scada/tests/test_historian.py` — 6 tests, all using a temporary
database file (never touches the real `data/logs/historian.db`):
- database file creation
- telemetry insert/read round-trip
- telemetry correctly skipped when the PLC is unreachable
- most-recent-first ordering
- `limit` parameter respected
- alarm transition insert/read round-trip, including the initial
  `previous_state = None` case at startup

Run with:
```bash
pytest scada/tests/test_historian.py -v
```