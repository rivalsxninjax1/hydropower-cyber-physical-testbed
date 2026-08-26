# Project Evaluation (Phase 16)

This document does three things, per Section 16 of the blueprint's
own phase table: cross-checks measured claims already published in
this project's docs against their raw source data, presents a
consolidated before/after summary from real measured numbers only,
and honestly audits the project against its own MVP checklist
(`docs/architecture/01-architecture-blueprint.md`, Section 9).

---

## 1. Cross-check: the 5.51s vs 8.14s detection-time discrepancy

**Finding:** two different documents (`docs/architecture/ids.md`,
`docs/threat-model/threat-model.md`) cited two different numbers —
5.51s and 8.14s — for the same underlying quantity ("how long before
Experiment 01's attack was detected without an IDS"), without
explaining why they differ. Both numbers are real and were measured
correctly; the problem was presenting them as interchangeable.

**Root cause, traced to source:**

| Measurement | Poller | Interval | Result |
|---|---|---|---|
| `experiments/01-modbus-control/run_experiment.py` | The experiment script itself, polling the PLC's Modbus registers directly | 0.5s (`POLL_INTERVAL_S`) | **5.51s**, identical across 3 independent runs |
| `docs/architecture/correlation-timeline.md`'s captured example | The dashboard's own background poll loop (`dashboard/backend/main.py`) | 1.0s (`POLL_SECONDS`) | **8.14s**, one specific run |

These are two different observers watching for the same physical
event (the alarm register changing) at two different polling
cadences. Neither is "wrong" — a tighter poll interval will, on
average, notice a state change sooner, simply because it checks more
often. This is not a bug; it's an artifact of polling-based detection
in general, and it's actually a useful finding in its own right: **it
demonstrates why the IDS's approach (observing the packet itself,
not polling for its consequence) is structurally better than either
baseline** — an IDS doesn't have a poll interval to be limited by,
because it doesn't wait for a state change to occur before reacting.

**Correction applied:** both docs now cite the range "~5.5-8s,
poll-cadence-dependent" with a pointer to this document, instead of a
single unqualified number.

**What this doesn't change:** the core comparison (IDS at t+0.00s vs.
either polled baseline) is unaffected — if anything, this makes the
IDS's advantage clearer, not weaker, once the polling-dependency is
explained rather than hidden behind one cherry-picked figure.

---

## 2. Before/After Summary (measured data only)

### Detection time: before vs. after Phase 11's IDS

| Condition | Detection time | Source |
|---|---|---|
| No IDS, attacker's own tight polling (0.5s) | 5.51s | `experiments/01-modbus-control/` — 3 identical runs |
| No IDS, dashboard's independent polling (1.0s) | 8.14s | `docs/architecture/correlation-timeline.md` — 1 captured run |
| **With IDS (Phase 11)** | **~0s (t+0.00s in captured runs)** | `docs/architecture/ids.md` — verified against real packet capture |

### Attack reachability: before vs. after Phase 12's segmentation

| Condition | DNS resolved | TCP connected | Attack path reachable | Source |
|---|---|---|---|---|
| Config A (flat network) | Yes | Yes | **True** | Repeatedly confirmed: 3 successful Experiment 01 runs against Config A (Phases 9/11), plus direct manual Modbus connectivity tests in Phases 7-8. `experiments/02-network-segmentation/run_experiment.py` was not separately re-run against Config A specifically — flagged here rather than silently assumed equivalent, though the underlying reachability was independently confirmed by every other Config A attack that succeeded. |
| **Config B (segmented network)** | **No** (`Name or service not known`) | **No** | **False** | `experiments/02-network-segmentation/` — real run, user-executed, real Docker environment, `docker-compose.segmented.yml` |

---

## 3. MVP Checklist Audit

Against the MVP list defined in Phase 1
(`docs/architecture/01-architecture-blueprint.md`, Section 9):

| # | Item | Status |
|---|---|---|
| 1 | Working physics engine + animated HMI (normal operation demo) | **Done** (Phase 2/3) |
| 2 | PLC with Modbus TCP, documented register map | **Done** (Phase 4) |
| 3 | Attacker container on separate network reaching PLC (Config A) | **Done** (Phase 8) |
| 4 | One full experiment: unauthorized Modbus write → visible physical impact → HMI alarm | **Done** (Phase 9, Experiment 01) |
| 5 | Basic IDS rule detecting that specific unauthorized write | **Done** (Phase 11) |
| 6 | Config B segmentation demonstrating the same attack blocked | **Done** (Phase 12, Experiment 02, real confirmed block) |
| 7 | Before/after comparison | **Done** (this document, Section 2 above) |
| 8 | Threat model document + one ATT&CK mapping table | **Done, exceeded** (Phase 14 — 3 verified ATT&CK techniques, not just 1) |
| 9 | README + ETHICS.md + basic architecture diagram | **Partially done.** Architecture diagrams and extensive `docs/architecture/` content exist. **Repo-root `README.md` and `ETHICS.md` do NOT exist yet** — confirmed by direct filesystem check during this evaluation, not assumed. This is a real, currently-open gap, not a minor omission: Section 44 of the master spec explicitly requires `ETHICS.md`, and no GitHub visitor currently has an entry-point document explaining what this repository is. |

**8 of 9 MVP items fully complete.** Item 9 is the one clear
outstanding gap — properly Phase 18's responsibility (documentation),
but surfaced here explicitly so it isn't lost track of between now and
then.

---

## 4. What's genuinely strong vs. what's thin

Stated plainly, since an evaluation that only lists successes isn't a
real evaluation:

**Strong, well-evidenced:**
- The full cyber-physical chain (Modbus write → PLC → physics →
  telemetry → alarm) is real, tested, and deterministic — not staged.
- Both major before/after comparisons (detection, segmentation) are
  backed by real measured data, including data the *user* personally
  generated in their own Docker environment, not just this
  development sandbox.
- Three ATT&CK for ICS techniques and two NIST CSF controls were each
  individually verified against their primary sources before being
  cited — not pulled from memory.

**Thin or incomplete:**
- Only one full attack experiment (Modbus control) has real measured
  data. DNP3, vendor-access, traffic-analysis, and DoS experiments
  (Sections 19-22 of the master spec) remain unbuilt.
- The dashboard's own `/api/gate` HTTP endpoint is a confirmed,
  documented, but never-tested attack surface (`docs/threat-model/threat-model.md`,
  Section 3) — a real gap in experimental coverage, not just a
  theoretical one.
- No repo-root README/ETHICS.md (Section 3 above).
- NIST CSF Respond and Recover functions have zero implementation —
  explicitly stated in the threat model, not hidden.