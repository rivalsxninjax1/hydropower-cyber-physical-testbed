# Demonstration Script

An 8-step guided walkthrough, matching the demonstration sequence
planned in `docs/architecture/01-architecture-blueprint.md`. Every
command below has been tested against a real running system during
development — the expected results quoted are real measured values,
not illustrative placeholders (per this project's own rule against
fabricated data, see Section 43 references throughout `docs/`).

**Before you start:** run `scripts/reset/reset_environment.sh --yes`
so the historian and experiment data are clean, and note the caveat
in `docs/architecture/correlation-timeline.md` about waiting ~15
seconds after startup before triggering an attack, so a startup-seed
alarm event doesn't appear inside your demo's timeline window.

---

## Demo 1 — Normal hydropower operation

```bash
docker compose up --build -d
sleep 15
```

Open `http://127.0.0.1:8000` (Dashboard), then `/plant`.

**Show:** reservoir at 72%, gate at 45%, turbine visibly spinning,
alarm banner **teal/NORMAL**. Let it sit for a few seconds — the
values are static because the plant is genuinely at a stable
operating point (Phase 2's deterministic physics engine), not because
nothing is happening.

---

## Demo 2 — Unauthorized Modbus control

Narrate the manual reconnaissance first (or run it live):

```bash
docker compose exec attacker python3 tools/network_scan.py
docker compose exec attacker python3 tools/modbus_recon.py plc 5020
docker compose exec attacker python3 tools/modbus_probe_writable.py plc 5020
```

**Show:** the probe step correctly and reproducibly identifies
register 6 as the sole persistent (control) register, with zero prior
knowledge of the project's own source code.

Then the actual attack:

```bash
docker compose exec attacker python3 tools/exploit_gate.py plc 6 1000
```

**Show:** "Write accepted — no authentication was required."

---

## Demo 3 — Physical impact appears on the HMI

Switch back to the browser, `/plant` page, still open.

**Show, over the next ~6-10 seconds:** gate position climbs from 45%
toward 100%, flow rate and turbine RPM rise, generator power increases,
alarm banner turns **amber (WARNING)**. This is the same measured
sequence documented in `experiments/01-modbus-control/README.md`:
gate 45%→69% at the 6-second mark, flow 68.7→105.4 m³/s, RPM
1500→1712.

---

## Demo 4 — IDS detects the attack

Open `/security` in another tab, or:

```bash
docker compose logs ids --tail 20
```

**Show:** an `[ids] ALERT [WARNING] anomalous_command_value: ...`
line, timestamped essentially immediately after the write (Phase 11
measured this at **t+0.00s**, compared to the 5.5-8 second delay
before the plant's own alarm system would have reacted — see
`docs/architecture/ids.md`).

Then open `/attack-path` and show the full structured timeline:
Control Command → PLC/RTU Access → Physical Impact (×2) → HMI Alarm →
IDS Alert, all from real logged timestamps.

---

## Demo 5 — Enable segmentation

```bash
docker compose down
docker compose -f docker-compose.segmented.yml up --build -d
sleep 15
```

**Show (optional, for technical audiences):**
```bash
docker network inspect hydropower-cyber-physical-testbed_ot_net
docker network inspect hydropower-cyber-physical-testbed_corp_net
```
The attacker container appears only in `corp_net`; the PLC and
dashboard only in `ot_net` — no shared network.

---

## Demo 6 — Repeat the attack

```bash
docker compose exec attacker python3 experiments/02-network-segmentation/run_experiment.py plc 5020
```

**Show, live in the terminal:**
```
[experiment] Attempting DNS resolution of 'plc'...
[experiment] DNS resolution: FAILED ([Errno -2] Name or service not known)
[experiment] Attempting TCP connect to plc:5020...
[experiment] TCP connect: FAILED
  attack_path_reachable: False
```

This is real output from this project's own segmentation experiment,
run against the actual Docker network — not a simulated failure
message.

---

## Demo 7 — Attack is blocked

**Say:** the attack failed at the network layer, before any Modbus
traffic could even be sent — meaning the IDS (Demo 4) never even had
traffic to observe, because the attacker never got that far. This is
a *stronger* result than detection: segmentation prevents the attack
from starting at all, rather than catching it after the fact.

Point to the comparison already documented in
`docs/evaluation/evaluation.md`, Section 2, for the full before/after
table with both configurations' measured results side by side.

---

## Demo 8 — System recovers

**Important framing point, stated honestly rather than overclaimed:**
this project does **not** have an automated incident-response or
recovery capability — `docs/threat-model/threat-model.md`'s NIST CSF
mapping explicitly marks the "Recover" function as not implemented.
What this demo shows instead is that the *physical process itself*
can be restored to normal once a legitimate corrective command is
issued — a property of the physics/control loop (Phase 2), not a
designed recovery feature.

Switch back to Config A so the dashboard's legitimate control path is
reachable again:

```bash
docker compose -f docker-compose.segmented.yml down
docker compose up -d
sleep 15
```

On `/plant`, use the **Operator Gate Control** slider to set the gate
back to 45% and click "Send gate target."

**Show:** over the following seconds, flow, RPM, and power settle back
toward their original steady-state values, and the alarm banner
returns to **NORMAL** — the same rate-limited, physically consistent
behavior documented in `docs/architecture/physics-model.md`, running
in reverse.

---

## After the demo

```bash
scripts/reset/reset_environment.sh --yes
docker compose down
```

Leaves the environment clean for the next run.