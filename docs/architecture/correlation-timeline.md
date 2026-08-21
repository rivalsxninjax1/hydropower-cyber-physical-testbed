# Cyber-Physical Correlation Timeline

## What this is

`security/correlation/build_timeline.py` merges timestamped records
from **four independent sources** into one chronological narrative —
the practical implementation of Section 24 of the project spec:
Network Event + PLC Event + Physics Event + HMI Event = Security Incident

None of these sources know about each other. Each just timestamps its
own observations:

| Source | Where it's recorded | What it records |
|---|---|---|
| Network | `data/experiments/01-modbus-control/result_*.json` | The moment the Modbus write was sent (`run_experiment.py`) |
| PLC | `plc_events` table (historian DB) | The moment the PLC's own control loop noticed and applied the changed register (Phase 4/10) |
| Physics | `telemetry_log` table (historian DB) | Flow rate and turbine RPM crossing a "detectably different from baseline" threshold |
| HMI/Alarm | `alarm_events` table (historian DB) | The moment the alarm state itself transitioned (Phase 6) |

The correlator's only job is reading all four, filtering to a time
window around the network event, and sorting by timestamp.

## Real measured output

=== Cyber-Physical Incident Timeline ===
t+ 0.00s [Network ] Unauthorized Modbus write: register 6 = 1000 (from 127.0.0.1)
t+ 0.99s [PLC ] Gate target command changed to 100.0%
t+ 3.12s [HMI/Alarm ] Alarm state changed: None -> NORMAL
t+ 4.12s [Physics ] Flow rate detectably increasing: 68.7 -> 81.0 m3/s
t+ 6.13s [Physics ] Turbine RPM detectably increasing: 1500.0 -> 1592.0
t+ 8.14s [HMI/Alarm ] Alarm state changed: NORMAL -> WARNING
t+30.00s [IDS ] NO DETECTION EVENT logged - no intrusion detection
system exists yet in this project (see Phase 11).


## A caveat worth understanding, not hiding

The `t+3.12s Alarm state changed: None -> NORMAL` row above is a real,
honestly-logged event — but it's an artifact of the dashboard having
just been started a few seconds before the experiment ran (the
historian logs `previous_state: None` the very first time it observes
any alarm state after startup). It is not part of the attack's actual
effect. **For a clean demo recording, start the full stack and let it
run for at least 10-15 seconds before triggering the experiment**, so
this startup-seed event falls outside the timeline's window rather
than appearing to be part of the incident. This is documented here
rather than filtered out silently, per Section 43's rule against
quietly reshaping real data to look cleaner than it is.

## Why the "no detection" row is there on purpose

Section 43 of the project spec: never fabricate results. It would be
easy to add a plausible-looking `[IDS] Suspicious write detected` row
at, say, t+1.5s — but no IDS exists yet at this phase. The row is
included specifically to make that gap visible and undeniable, so a
reader can see exactly what Phase 11 needs to add and why it matters:
right now, the ONLY thing that "detects" this attack is the plant's
own alarm thresholds reacting to the physical consequence, roughly 8
seconds after the fact. A real IDS should be able to flag the
Modbus write itself, at t+0, before any physical damage occurs — that
gap between t+0 and t+8.14s is precisely what Phase 11 will be
measured against reducing.

## How to reproduce

Requires the PLC and dashboard both running (the dashboard is what
populates `telemetry_log` and `alarm_events`; the PLC populates
`plc_events`):

```bash
docker compose up -d
sleep 15   # let startup-seed events age out of any future window
docker compose exec attacker python3 experiments/01-modbus-control/run_experiment.py plc 5020 6 1000
python3 -m security.correlation.build_timeline
```

(The correlator itself needs no network access — it only reads local
files and the shared SQLite historian, so it can run directly on the
host with the local venv, not just inside a container.)

## Automated tests

Phase 10 additions are covered by:
- `scada/tests/test_historian.py` — `plc_events` table round-trip and
  ordering (2 new tests, 8 total in that file)
- `industrial/tests/test_plc.py` — confirms the PLC actually writes a
  `plc_events` row when it applies a command, and does NOT write one
  when a register is unchanged (2 new tests, 11 total in that file)

Both test files monkeypatch `historian.DB_PATH` to a temporary file,
so running the test suite never reads or writes the real
`data/logs/historian.db`.

