# PLC Register Map

This document is the authoritative reference for the simulated
intake-gate PLC's Modbus TCP interface, implemented in
`industrial/plc/register_map.py` and served by
`industrial/plc/plc_server.py`.

## Connection details

| Setting | Value |
|---|---|
| Protocol | Modbus TCP |
| Host | `0.0.0.0` (listens on all interfaces) |
| Port | `5020` |

**Why port 5020, not the standard 502:** binding to port 502 requires
root/administrator privileges on most operating systems. Using 5020
lets the whole testbed run as a normal user on an ordinary student
laptop. This is documented here and called out in code comments so it
is never mistaken for an oversight — in a real deployment this would
be port 502.

## Library version note

This project pins `pymodbus==3.6.9`. The latest pymodbus release
(3.15 at time of writing) is mid-migration away from the classic
`ModbusSlaveContext` / `ModbusServerContext` / `ModbusSequentialDataBlock`
datastore API toward a new `SimData`/`SimDevice` design, and in that
version the classic classes' `getValues`/`setValues` no longer
function correctly for a live, dynamically-updating register map. This
was confirmed by direct testing before writing the PLC service, rather
than discovered as a runtime failure later. `3.6.9` is a stable
release where the classic API is fully documented and functional,
which matches the project's "prefer maintainable, well-documented
technology" principle. If pymodbus is later upgraded, this datastore
layer will need to be rewritten against the new API — noted as a
limitation, not a blocker.

## Register map

All registers are unsigned 16-bit holding registers (Modbus function
code 3 = read, 6/16 = write single/multiple).

| Modbus Address | Zero-based Address | Name | Access | Scale | Description |
|---|---|---|---|---|---|
| 40001 | 0 | `RESERVOIR_LEVEL_PCT` | Read | x10 | Reservoir level, % of operating band |
| 40002 | 1 | `GATE_POSITION_PCT` | Read | x10 | Actual (measured) gate position, % open |
| 40003 | 2 | `FLOW_RATE_M3S` | Read | x10 | Flow through the gate, m³/s |
| 40004 | 3 | `TURBINE_RPM` | Read | x1 | Turbine speed, RPM |
| 40005 | 4 | `GENERATOR_POWER_MW` | Read | x10 | Generator output, MW |
| 40006 | 5 | `ALARM_STATE` | Read | x1 | 0=NORMAL, 1=WARNING, 2=CRITICAL |
| 40007 | 6 | `GATE_TARGET_COMMAND_PCT` | **Read/Write** | x10 | Commanded gate target, % open — **the plant's only control register** |

**Fixed-point scaling:** registers store values as integers. A scale
of 10 means the real value is `raw / 10` — e.g. a raw value of `456`
in `GATE_POSITION_PCT` means 45.6%. This is standard practice for
protocols like Modbus that only support integer registers.

## The control register — intentional design, not a bug

`GATE_TARGET_COMMAND_PCT` (40007) is the only writable register, and
as of Phase 4/5 it has **no authentication, no access control, and no
validation beyond a 0-100% clamp.** Any Modbus TCP client that can
reach the PLC on port 5020 can command the gate to any position.

This is deliberate. It is the exact vulnerability Phase 9's Modbus
control experiment demonstrates, and what Phase 12's segmentation and
access-control mitigation is designed to fix. Documenting it here now
means there is a clear "before" state to compare the "after" mitigated
state against later (Section 27 of the project spec).

## How a command reaches the physical process
Modbus client writes raw value to register 40007
↓
PLC control loop (runs once per second) reads register 40007
↓
If the raw value changed since the last tick:
decode it back to a real percentage
call PhysicsEngine.set_gate_target(percentage)
↓
Physics engine's rate-limited gate actuator moves toward
the new target over several seconds (see docs/architecture/physics-model.md)
↓
PLC control loop writes the updated reservoir/gate/flow/turbine/
generator/alarm values back into registers 40001-40006 every tick


## How to test manually

Terminal 1:
```bash
python -m industrial.plc.plc_server
```

Terminal 2:
```bash
python -m industrial.plc.test_client
```

The test client reads all registers, prompts for a new gate target,
writes it to register 40007, waits 6 seconds, and reads all registers
again — you should see `GATE_POSITION_PCT`, `FLOW_RATE_M3S`,
`TURBINE_RPM`, and `GENERATOR_POWER_MW` all move toward the new
steady state, and `ALARM_STATE` may change if the deviation is large
enough.

## Automated tests

`industrial/tests/test_plc.py` covers:
- register encode/decode round-tripping and clamping
- the register map's structural integrity (exactly one writable register, no duplicate addresses)
- the PLC's control loop correctly applying a written command to the physics engine
- the PLC correctly ignoring an unchanged register (no spurious re-application every tick)
- a full write → multiple ticks → physical change assertion, without opening a real socket (fast, no port conflicts)

Run with:
```bash
pytest industrial/tests/test_plc.py -v
```