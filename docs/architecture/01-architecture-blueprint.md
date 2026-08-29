# Hydropower Cyber-Physical Security Testbed — Architecture Blueprint

**Status:** Phase 1 planning document. Delivered originally as a
standalone file before the repo's `docs/` structure existed; saved
here during Phase 18's final cleanup so every later phase's reference
to this path (`docs/architecture/01-architecture-blueprint.md`)
resolves correctly. Content is unchanged from the original.

---

## 0. How this maps to the VS Code + GitHub workflow

Repo skeleton, git branching convention, `.gitignore` essentials, and
README approach — see Section 0 of the original delivered document
for the full detail; superseded in practice by the actual `.gitignore`,
`README.md`, and commit history now present in this repository.

## 1. Final Project Title

**Design and Development of a Cyber-Physical Security Testbed for
Threat Modeling, Attack Simulation, Detection, and Mitigation in
Hydropower ICS/OT Networks**

## 2-4. System diagrams, Purdue architecture, cyber-physical data flow

See the equivalent, now-implemented versions of these diagrams in:
- `docs/architecture/network-architecture.md` (network/Purdue layout, both Config A and B)
- `docs/architecture/plc-register-map.md` (cyber-physical data flow, as actually implemented)

## 5. Directory Structure

The directory structure proposed here was followed closely through
Phases 2-17; see the repository root for the actual, current
structure, which matches this plan with only minor deviations
documented inline in each phase's own commit history.

## 6. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Backend/API | Python + FastAPI | async-friendly, auto OpenAPI docs, lightweight |
| Physics engine | Plain Python, no framework | deterministic equations, no framework needed |
| PLC simulation | Python + `pymodbus` (pinned 3.6.9) | most mature open-source Modbus TCP library; 3.6.9 pinned after direct testing showed the newer 3.15's classic datastore API no longer functions for a live register map |
| Frontend/HMI | HTML/CSS/JS + WebSocket, no framework | avoids build tooling |
| Containers | Docker + Docker Compose | segmentation via multiple networks |
| Database | SQLite | zero-setup, adequate at this scale |
| IDS | Python + `scapy`, custom rule engine | lighter and more explainable than Suricata/Zeek at this project's scale |
| Attacker tools | nmap, a raw Modbus client, Python | standard, well-documented |

## 7. Development Phases

The 18-phase plan below was followed in full; each phase's actual
implementation, testing, and outcome is documented in its own
`docs/architecture/*.md` file (or `docs/threat-model/`,
`docs/evaluation/` for the later phases) rather than repeated here.

| Phase | Objective |
|---|---|
| 1 | Architecture (this document) |
| 2 | Physics engine |
| 3 | Hydropower visualization |
| 4 | PLC simulation |
| 5 | Modbus communication |
| 6 | HMI/SCADA (historian + alarm log) |
| 7 | OT network architecture (Docker containerization) |
| 8 | Attacker environment |
| 9 | Attack experiments (Experiment 01) |
| 10 | Cyber-physical impact correlation |
| 11 | IDS/security monitoring |
| 12 | Mitigation (network segmentation, Experiment 02) |
| 13 | Attack visualization |
| 14 | Threat modeling |
| 15 | Experiment logging |
| 16 | Evaluation |
| 17 | Final dashboards |
| 18 | Documentation and demonstration |

## 8. Essential vs Optional Components

**Essential (MVP):** physics engine, PLC (Modbus), HMI, corp/OT
network split, attacker container, one full attack→physical-impact
chain, basic IDS, segmentation mitigation, threat model, real
experiment data. **Status: 8/9 complete** — see
`docs/evaluation/evaluation.md` for the full audit.

**Optional / not yet built:** DNP3/RTU experiment, vendor-access
experiment, traffic-analysis experiment, DoS experiment, ML anomaly
detection extension, full IEC 62443/NIST CSF compliance (never
claimed — see `docs/threat-model/threat-model.md`'s explicit scope
boundaries).

## 9. Realistic Development Timeline

Superseded by the actual commit history of this repository.

## 10. Technical Risks and Fallbacks (as anticipated, vs what happened)

| Anticipated risk | What actually happened |
|---|---|
| DNP3 libraries immature | Correctly anticipated — DNP3/RTU was never built, remains an open item |
| Docker network segmentation inconsistent across OS | Not encountered; segmentation worked as designed on the tested platform |
| pymodbus API instability | **Encountered exactly as feared**, but for a different reason than anticipated: not DNP3, but pymodbus's own classic Modbus TCP datastore API breaking between versions 3.6.9 and 3.15 — caught by direct testing before writing the PLC, documented in `docs/architecture/plc-register-map.md` |
| IDS false positives during demo | Not encountered — the two-rule design (source + behavioral) stayed precise across all tested runs |

## 11. Planned Final Demonstration Sequence

See `docs/demo-script.md` for the actual, tested 8-step demonstration
script — the plan below was the basis for it, refined once real
components existed to demonstrate.

1. Normal hydropower operation
2. Unauthorized Modbus control
3. Physical impact appears on HMI
4. IDS detects attack
5. Enable segmentation
6. Repeat attack
7. Attack is blocked/detected
8. System recovers