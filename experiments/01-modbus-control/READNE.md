# Experiment 01 — Unauthorized Modbus Control of the Intake Gate

## Objective

Determine whether an actor with only network access to the OT segment
(no credentials, no HMI access) can issue a control command to the
hydropower plant's PLC and produce a measurable, observable change in
the physical process.

## Hypothesis

Because the PLC's Modbus TCP interface currently has no authentication
and no source-address validation (documented as an intentional
baseline in `docs/architecture/plc-register-map.md`), any Modbus TCP
client that can reach the PLC on port 5020 will be able to write to
the gate's control register and produce a physical effect
indistinguishable, at the register level, from a legitimate operator
command issued through the HMI.

## Method

1. **Reconnaissance** — from the isolated attacker container, scan
   the local network for open ports (`attacker/tools/network_scan.py`).
2. **Service inspection** — connect to the discovered Modbus TCP
   service and read all holding registers with no prior knowledge of
   their meaning (`attacker/tools/modbus_recon.py`).
3. **Control register identification** — write a marker value to
   every register and observe which one is NOT overwritten by the
   PLC's own control loop within a few seconds
   (`attacker/tools/modbus_probe_writable.py`).
4. **Measured attack** — write an operator-level command to the
   identified control register and measure the time until the plant's
   own alarm state changes as a result
   (`experiments/01-modbus-control/run_experiment.py`).

Steps 1-3 are exploratory and manual (see
`docs/architecture/attacker-environment.md` for the full transcript).
Step 4 is the repeatable, measured experiment this document reports.

### Variables

- **Independent variable:** whether the Modbus write is sent at all,
  and its value (100.0% gate target vs. the plant's steady-state
  45.0%).
- **Dependent variables:** whether the write is accepted, whether the
  physical state changes, and the time elapsed between the write and
  the plant's own alarm system detecting the resulting deviation.

## Result (measured, 3 independent runs)

Command sent: write raw value `1000` (= 100.0% gate target, fixed-point
scale x10) to register 6 (`GATE_TARGET_COMMAND_PCT`, Modbus address
40007), against the PLC's default steady state.

| Run | Write accepted | Baseline registers | Final registers (after 6s) | Alarm changed | Time to alarm change |
|---|---|---|---|---|---|
| 1 | Yes | `[720, 450, 687, 1500, 313, 0, 450]` | `[720, 690, 1054, 1712, 480, 1, 1000]` | NORMAL → WARNING | 5.51s |
| 2 | Yes | `[720, 450, 687, 1500, 313, 0, 450]` | `[720, 690, 1054, 1712, 480, 1, 1000]` | NORMAL → WARNING | 5.51s |
| 3 | Yes | `[720, 450, 687, 1500, 313, 0, 450]` | `[720, 690, 1054, 1712, 480, 1, 1000]` | NORMAL → WARNING | 5.51s |

Decoded (register scale factors from `docs/architecture/plc-register-map.md`):

| Field | Baseline | After attack |
|---|---|---|
| Reservoir level | 72.0% | 72.0% (unaffected — reservoir has large surface area, no meaningful change in 6s) |
| Gate position | 45.0% | 69.0% (climbing toward the 100% target; rate-limited actuator, see Phase 2 physics model) |
| Flow rate | 68.7 m³/s | 105.4 m³/s |
| Turbine RPM | 1500.0 | 1712.0 |
| Generator power | 31.3 MW | 48.0 MW |
| Alarm state | NORMAL | WARNING |

Raw data backing this table: `data/experiments/01-modbus-control/results.csv`
and per-run JSON snapshots in the same folder.

**Write accepted every time. Physical state changed every time.
Result was bit-for-bit identical across all 3 runs** — expected,
since the physics engine (Phase 2) is deterministic by design and no
randomness is involved anywhere in this path.

## Conclusion

The hypothesis is confirmed. An attacker with only network reachability
to the PLC — no HMI access, no credentials, no prior knowledge of the
register map beyond what recon revealed — can reliably command the
intake gate and produce a measurable physical deviation within
approximately 5.5 seconds of the write being accepted. The PLC applies
the command with no way to distinguish it from a legitimate operator
action originating from the HMI (Phase 5/6 confirmed the HMI uses the
exact same register, the exact same write operation).

This is the "before" baseline Phase 12's segmentation mitigation will
be measured against: the same four-step sequence, repeated once the
attacker container is moved to a separate network segment with no
route to the PLC, should fail at Step 1 or 2 rather than succeeding at
Step 4.

## MITRE ATT&CK for ICS mapping

| Field | Value |
|---|---|
| Technique ID | [T0855](https://attack.mitre.org/techniques/T0855/) |
| Technique Name | Unauthorized Command Message |
| Tactic | Impair Process Control (TA0106) |
| Target | PLC control register (Modbus TCP holding register 40007) |
| Attack Vector | Direct Modbus TCP write from an unauthenticated network client |
| Observed Behavior | Gate position, flow rate, turbine RPM, and generator power all changed within one control-loop tick of the write being applied; alarm state escalated within ~5.5s |
| Detection | None yet — no IDS exists at this phase. This experiment's own polling loop is the only thing that "detected" the change. Phase 11 adds real network-based detection. |
| Mitigation | None yet — this experiment intentionally targets the unmitigated baseline. Phase 12 adds network segmentation and is measured against this same experiment. |

A full threat model consolidating this and later experiments' ATT&CK
mappings is built in Phase 14; this table is this experiment's own
contribution to that later document, recorded now while the context is
fresh (per Section 29 of the project spec).

## How to reproduce

```bash
docker compose exec attacker python3 experiments/01-modbus-control/run_experiment.py plc 5020 6 1000
```

(Requires `experiments/` to be reachable inside the attacker
container — see the volume mount added to `docker-compose.yml`.)

Each run appends a row to `data/experiments/01-modbus-control/results.csv`
and writes a timestamped JSON snapshot alongside it — this is real,
accumulating experimental evidence, not a static table maintained by
hand.