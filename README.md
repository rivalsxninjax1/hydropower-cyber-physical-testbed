# Hydropower Cyber-Physical Security Testbed

**Design and Development of a Cyber-Physical Security Testbed for
Threat Modeling, Attack Simulation, Detection, and Mitigation in
Hydropower ICS/OT Networks**

A final-year cybersecurity capstone project: a fully simulated,
self-contained hydropower plant — physics engine, PLC, HMI, network,
attacker, and intrusion detection system — built to study how
cyberattacks on industrial control systems propagate into physical
consequences, how they can be detected, and how network architecture
affects whether they succeed at all.

This is not a CTF. There are no flags, no scores, no leaderboards.
Every claim in this repository is backed by a real, reproducible
measurement — see [`docs/evaluation/evaluation.md`](docs/evaluation/evaluation.md)
for a full accounting of what's measured versus what's still
theoretical. Read [`ETHICS.md`](ETHICS.md) before using any of the
attacker tooling.

---

## What this demonstrates

```
CYBER ATTACK → NETWORK EVENT → PLC COMPROMISE → CONTROL COMMAND
     → PHYSICAL PROCESS CHANGE → HMI/ALARM → DETECTION → MITIGATION
```

Two measured, real experiments prove this chain end to end:

| Experiment | Finding | Evidence |
|---|---|---|
| **01 — Unauthorized Modbus Control** | An attacker with only network access (no credentials) can command the plant's intake gate directly, causing a measurable physical deviation in ~5.5s | [`experiments/01-modbus-control/README.md`](experiments/01-modbus-control/README.md) — 3 identical runs |
| **02 — Network Segmentation** | Moving the attacker to a properly segmented network blocks the attack entirely — DNS resolution fails before any Modbus traffic can be sent | [`experiments/02-network-segmentation/README.md`](experiments/02-network-segmentation/README.md) — real Docker-verified result |

Phase 11's passive IDS reduces detection time for Experiment 01's
attack from ~5.5-8s (the plant's own alarm system reacting to physical
symptoms) to **t+0.00s** (observing the malicious command itself). See
[`docs/architecture/ids.md`](docs/architecture/ids.md) for the full
methodology, including a documented measurement discrepancy that was
found and corrected during development rather than left unexamined.

---

## Quick start

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone <this-repo>
cd hydropower-cyber-physical-testbed
scripts/setup/setup.sh
```

Then open **http://127.0.0.1:8000** in a browser.

Run the first attack:
```bash
docker compose exec attacker python3 experiments/01-modbus-control/run_experiment.py plc 5020 6 1000
```

Watch it happen live on the Plant View and Security Monitoring pages.
For the full guided walkthrough (including the segmentation
comparison), see [`docs/demo-script.md`](docs/demo-script.md).

---

## The dashboard

Five pages, all built on real data — nothing on screen is
hardcoded or simulated for effect:

| Page | URL | What it shows |
|---|---|---|
| **Dashboard** | `/` | At-a-glance plant + security status tiles |
| **Plant View** | `/plant` | Live animated schematic, polled over real Modbus TCP |
| **Security Monitoring** | `/security` | IDS alerts, PLC command events, alarm log |
| **Attack Path** | `/attack-path` | Network topology graph + structured attack timeline |
| **Experiments** | `/experiments` | Raw and aggregated results from every experiment run |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCKER COMPOSE NETWORK                       │
│                                                                   │
│  ┌────────────┐                          ┌────────────────────┐ │
│  │  attacker  │──── flat or blocked ────▶ │      ot_net         │ │
│  │ (nmap +    │     depending on config   │ ┌────────┐ ┌──────┐│ │
│  │  Modbus     │                          │ │  plc   │◄┤ dash- ││ │
│  │  tools)     │                          │ │ :5020  │ │ board ││ │
│  └────────────┘                          │ └───┬────┘ │ :8000 ││ │
│                                            │ ┌───▼────┐ └───┬───┘│ │
│                                            │ │  ids   │     │    │ │
│                                            │ └────────┘     │    │ │
│                                            └────────────────┼────┘ │
└───────────────────────────────────────────────────────────┼──────┘
                                                        (published)
                                                              │
                                                        your browser
```

- **`simulation/`** — deterministic physics engine (reservoir → gate →
  turbine → generator), no randomness, every equation documented in
  [`docs/architecture/physics-model.md`](docs/architecture/physics-model.md)
- **`industrial/plc/`** — Modbus TCP PLC bridging the physics engine to
  a documented 7-register map ([`docs/architecture/plc-register-map.md`](docs/architecture/plc-register-map.md))
- **`dashboard/`** — FastAPI backend + vanilla HTML/CSS/JS frontend, no
  framework, no build step
- **`scada/historian/`** — SQLite-backed telemetry, alarm, PLC-event,
  and IDS-alert logging
- **`attacker/`** — isolated container with generic tools (nmap, a raw
  Modbus client) and zero access to this project's own source code —
  it has to discover the register map by observation, the same way a
  real attacker would ([`docs/architecture/attacker-environment.md`](docs/architecture/attacker-environment.md))
- **`security/ids/`** — passive Modbus TCP monitor, sniffing the PLC's
  own network traffic independently of the pymodbus library it's
  monitoring ([`docs/architecture/ids.md`](docs/architecture/ids.md))
- **`security/correlation/`** — merges network, PLC, physics, and
  alarm events from independent timestamped sources into one incident
  timeline ([`docs/architecture/correlation-timeline.md`](docs/architecture/correlation-timeline.md))

Full architecture rationale, including every "why this and not that"
technology decision, is in
[`docs/architecture/01-architecture-blueprint.md`](docs/architecture/01-architecture-blueprint.md).

## Two network configurations, one comparison

| | `docker-compose.yml` (Config A) | `docker-compose.segmented.yml` (Config B) |
|---|---|---|
| Topology | One flat network | `corp_net` (attacker) / `ot_net` (plc, dashboard) — no conduit |
| Attacker → PLC | Reachable | **Blocked** — DNS resolution fails |

Run either with `docker compose -f <file> up --build -d` (never both
at once — see the comment at the top of `docker-compose.segmented.yml`).

---

## Threat model & framework mappings

Every ATT&CK for ICS technique and NIST CSF control cited in this
project was individually verified against its primary source during
development — none were cited from memory. See
[`docs/threat-model/threat-model.md`](docs/threat-model/threat-model.md)
for the full assets/actors/surfaces analysis and mapping tables.

| Technique | Tool | Verified against |
|---|---|---|
| T0846.001 — Remote System Discovery: Port Scan | `attacker/tools/network_scan.py` | attack.mitre.org |
| T0861 — Point & Tag Identification | `attacker/tools/modbus_probe_writable.py` | attack.mitre.org |
| T0855 — Unauthorized Command Message | `experiments/01-modbus-control/` | attack.mitre.org |

---

## Testing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r industrial/plc/requirements.txt -r dashboard/backend/requirements.txt -r attacker/requirements.txt -r security/ids/requirements.txt
python -m pytest simulation/tests/ industrial/tests/ scada/tests/ security/tests/ -v
```

**43 automated tests**, covering the physics engine, PLC register
logic, historian persistence, and IDS detection rules. The packet-
capture and Docker-networking pieces are intentionally *not*
unit-tested — they were verified against real captured traffic and
real container-to-container connectivity during development instead,
which is documented directly in the relevant `docs/architecture/*.md`
file rather than asserted in a test file.

---

## Project status

**8 of 9 items on this project's own MVP checklist are complete** —
see [`docs/evaluation/evaluation.md`](docs/evaluation/evaluation.md)
for the full, honest audit, including what's explicitly *not* built
yet (DNP3/RTU, vendor-access compromise, traffic-analysis and DoS
experiments, and the dashboard's `/api/gate` HTTP endpoint, which is a
documented-but-untested attack surface).

## Requirements

- Docker Desktop (or Docker Engine + Compose v2)
- ~2GB RAM, minimal disk (~1GB for images)
- Tested on macOS; should work on Linux/Windows+WSL2 with Docker
  Compose v2, no OS-specific dependencies

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.