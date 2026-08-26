# Threat Model

This document consolidates the project's threat modeling per Section
28 of the project spec, and maps every tool and experiment already
built (Phases 8-12) against three security frameworks. Every framework
reference in this document was verified against its primary source
before being cited — technique/control IDs are not quoted from memory.
Where a framework category has no real implementation yet, that gap is
stated explicitly rather than glossed over, per Section 43's rule
against fabricating coverage.

---

## 1. Assets

| Asset | Component | Criticality | Notes |
|---|---|---|---|
| PLC | `industrial/plc/plc_server.py` | Critical | Sole control point for the physical process; compromise = direct physical impact |
| Physics engine | `simulation/physics_engine/` | Critical | Represents the actual physical process; the PLC's only reason to exist |
| HMI/Dashboard | `dashboard/backend/`, `dashboard/frontend/` | High | Operator's view and control surface; also a Modbus write client itself |
| Historian | `scada/historian/db.py` | Medium | Loss of this data doesn't affect plant operation, but destroys incident evidence and experiment results |
| IDS | `security/ids/` | Medium | Its compromise or failure doesn't affect the plant directly, but silently removes detection capability |
| Attacker container | `attacker/` | N/A (not a plant asset) | Included for completeness — this is the threat source, not something to protect |

## 2. Threat Actors

| Actor | Capability modeled | Status in this project |
|---|---|---|
| External attacker with network access to the OT segment | Standard tools (nmap, a Modbus client), no credentials, no insider knowledge of the register map | **Implemented and tested** — this is exactly `attacker/` in Phases 8-9 |
| Compromised legitimate source (e.g. a compromised HMI) | Access to legitimate credentials/position, but issuing anomalous commands | **Partially modeled** — Phase 11's `anomalous_command_value` rule specifically detects this case (extreme values from an authorized source), but no actual "HMI compromise" scenario has been built |
| Malicious insider | Legitimate access, deliberately harmful action | **Not modeled.** No distinction currently exists in this project between "operator" and "insider" — the dashboard's `/api/gate` endpoint has no user accounts at all, so there is no concept of an authorized-but-malicious user to distinguish from a legitimate one |
| Compromised vendor/remote-access account | External party with a legitimate but abusable access path | **Not modeled.** No vendor-access component exists yet (a natural candidate for a later phase, per Section 20 of the spec) |

## 3. Attack Surfaces

| Surface | Exposed by | Status |
|---|---|---|
| Modbus TCP, port 5020 | `industrial/plc/plc_server.py` | **Tested.** Zero authentication, zero source validation (Phase 4/9). This is the surface every experiment so far has targeted. |
| Dashboard HTTP API, port 8000 (`POST /api/gate`) | `dashboard/backend/main.py` | **Identified but NOT tested.** This endpoint also has zero authentication and writes to the exact same PLC control register as the Modbus surface — meaning it is, in principle, an equally valid attack path, just never exercised in an experiment. Flagged here rather than silently left out. |
| Docker network (`flat_net` / Config A) | `docker-compose.yml` | **Tested and mitigated.** Experiment 02 confirmed both the vulnerability (flat network = reachable) and the mitigation (segmented network = unreachable). |
| Historian database file | `data/logs/historian.db` | **Not tested.** No access control exists beyond filesystem/container boundaries; a compromised `dashboard` or `plc` container could tamper with historical records. Out of scope for this project's current experiments. |

## 4. Impacts

| Impact category | Demonstrated? | Evidence |
|---|---|---|
| Unauthorized control of physical process | **Yes** | Experiment 01: gate commanded to 100%, flow/RPM/power all measurably changed |
| Loss of availability | **No — not yet built.** | Section 22's DoS experiment is a planned future phase; no availability attack has been attempted |
| Incorrect/falsified telemetry | **Partially identified, not fully exploited.** | Phase 8's reconnaissance found that registers 0-5 (sensor/computed values) ARE technically writable at the Modbus protocol level, but the PLC's control loop overwrites them within ~1 second (`_refresh_readonly_registers` runs every tick) — so a sustained telemetry-falsification attack is not currently practical against this PLC's specific implementation. This is a real, tested finding (see `attacker/tools/modbus_probe_writable.py`'s results), not a theoretical concern. |
| Equipment instability | **Yes** | Experiment 01's alarm escalation (NORMAL→WARNING) is exactly this — measured, not assumed |

---

## 5. MITRE ATT&CK for ICS Mapping

Every technique ID below was verified against `attack.mitre.org` before being cited here.

| Tool / Experiment | Technique ID | Technique Name | Tactic | Target | Attack Vector | Observed Behavior | Detection | Mitigation |
|---|---|---|---|---|---|---|---|---|
| `attacker/tools/network_scan.py` | [T0846.001](https://attack.mitre.org/techniques/T0846/001/) | Remote System Discovery: Port Scan | Discovery | `flat_net` hosts | nmap port scan | Correctly discovered PLC (5020 open), dashboard (8000 open) | None (Phase 11's IDS does not monitor for port scans, only Modbus writes) | Phase 12 segmentation (attacker on `corp_net` cannot reach `ot_net` hosts to scan at all) |
| `attacker/tools/modbus_recon.py`, `modbus_probe_writable.py` | [T0861](https://attack.mitre.org/techniques/T0861/) | Point & Tag Identification | Collection | PLC register map | Blind register read + write-and-observe technique | Correctly and reproducibly identified register 6 as the sole control register, with zero prior knowledge | None | None currently — this is passive reconnaissance against an already-reachable PLC; segmentation (Phase 12) prevents reaching this stage at all |
| `experiments/01-modbus-control/` | [T0855](https://attack.mitre.org/techniques/T0855/) | Unauthorized Command Message | Impair Process Control | PLC control register (40007) | Direct Modbus TCP write, no auth | Gate 45%→69%, flow 68.7→105.4 m³/s, RPM 1500→1712, alarm NORMAL→WARNING (measured, 3 runs, bit-identical) |Phase 11: passive IDS, confirmed to reduce detection time to t+0.00s from a ~5.5-8s baseline (poll-cadence-dependent — see `docs/evaluation/evaluation.md`) | **Phase 12 segmentation**: fully blocks this attack at the network layer, confirmed by Experiment 02 |

Note: Experiment 02 (network segmentation) is a **mitigation test**, not an attack technique — MITRE ATT&CK catalogs adversary behaviors, not defensive controls, so it has no technique ID of its own. Its relevance is captured in the "Mitigation" column above and in the NIST CSF/IEC 62443 mappings below.

---

## 6. IEC 62443 Mapping (Zones & Conduits)

| Concept | Status | Detail |
|---|---|---|
| **Zones** | **Implemented (Config B)** | Two zones: `corp_net` (attacker) and `ot_net` (plc, dashboard). This is a minimal two-zone model, not the full Enterprise/DMZ/OT three-or-more-zone hierarchy IEC 62443 typically describes. |
| **Conduits** | **Not implemented — deliberately absent.** | Config B has zero conduit between `corp_net` and `ot_net`. A real plant needs *some* controlled path (engineering workstation, vendor gateway) between zones; this project's segmentation experiment isolates the "zones exist, no conduit" variable specifically, per the experiment design discipline in Section 34 of the spec (one independent variable at a time). A conduit is a natural addition once a DMZ/vendor-gateway component exists. |
| **Authentication** | **Not implemented anywhere in this project.** | Neither the Modbus interface nor the dashboard's HTTP API require credentials. This is the single largest gap between this project's current state and IEC 62443's expectations for a real deployment. |
| **Access control** | **Not implemented.** | No role-based access, no distinction between operator and any other actor. |
| **System integrity** | **Partially addressed.** | The PLC's own control loop overwrites sensor registers every tick, which incidentally limits (but does not prevent) telemetry tampering — see Impact #3 above. This is a side effect of the PLC's design, not a deliberate integrity control. |
| **Availability** | **Not addressed.** | No DoS testing or availability protection exists yet (Section 22, future phase). |
| **Monitoring** | **Implemented (Phase 11).** | The passive Modbus IDS is a real, tested monitoring capability, covering exactly one protocol on one segment. |

**This project does NOT claim IEC 62443 compliance of any kind** — the table above exists to show, honestly, which specific IEC 62443 concepts have a real, tested implementation behind them (Zones, Monitoring) versus which are explicitly out of scope so far (Authentication, Access Control, Availability, Conduits).

---

## 7. NIST CSF v1.1 Mapping

| Function | Category | Status | Evidence |
|---|---|---|---|
| **Identify** | Asset Management, Risk Assessment | **Implemented** | This document; `docs/architecture/` generally |
| **Protect** | [PR.AC-5](https://csf.tools/reference/nist-cybersecurity-framework/v1-1/pr/pr-ac/pr-ac-5/) — "Network integrity is protected (e.g., network segregation, network segmentation)" | **Implemented and measured** | Phase 12 / Experiment 02: segmentation confirmed to block the attack entirely |
| **Protect** | [PR.AC-1](https://csf.tools/reference/nist-cybersecurity-framework/v1-1/pr/pr-ac/pr-ac-1/) — "Identities and credentials are issued, managed, verified, revoked, and audited for authorized devices, users and processes" | **Not implemented** | No authentication exists anywhere in this project (see IEC 62443 section above) |
| **Detect** | DE.CM — Security continuous monitoring | **Implemented and measured** | Phase 11: passive IDS, confirmed to reduce detection time from t+8.14s to t+0.00s |
| **Respond** | RS.RP, RS.AN, RS.CO | **Not implemented.** | No automated or documented incident-response procedure exists. IDS alerts are logged (`ids_alerts` table) but nothing acts on them. |
| **Recover** | RC.RP, RC.IM | **Not implemented.** | No recovery procedure, automated or manual, has been built or tested. The plant does self-correct physically (e.g. alarm state returns to NORMAL if the gate is commanded back to a normal position), but this is a property of the physics/control loop, not a designed "recovery" capability. |

Two of five NIST CSF functions (Identify, Protect, Detect) have real,
tested implementations behind them in this project. Respond and
Recover are explicitly unimplemented — stated here rather than left
ambiguous, since a threat model that only lists what's covered
without saying what isn't is not a complete threat model.

---

## 8. What this threat model does NOT cover

Listed explicitly, since an unstated scope boundary is easy to mistake
for an oversight:

- DNP3/RTU attacks (no RTU component exists yet)
- Vendor/remote-access compromise (no such component exists yet)
- Traffic analysis / plaintext exposure (not yet a dedicated experiment)
- Denial-of-service / availability attacks (not yet a dedicated experiment)
- Physical/procedural security (out of scope for a software testbed)
- Attacks against the dashboard's HTTP API specifically (identified as
  a real attack surface in Section 3 above, but never exercised)
- Attacks against the historian database directly
- Any attack requiring credentials, since no component in this project
  currently has any