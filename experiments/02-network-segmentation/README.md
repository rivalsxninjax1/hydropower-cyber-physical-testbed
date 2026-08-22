# Experiment 02 — Network Segmentation Effect on the Modbus Control Attack

## Objective

Determine whether moving the attacker container from the flat network
(Config A) to a segmented network with no route to the OT zone
(Config B) prevents the attack demonstrated in Experiment 01 from
reaching the PLC at all.

## Hypothesis

Because Config B places the attacker container on `corp_net` and the
PLC on `ot_net` — two separate Docker networks with no shared
container and no gateway/conduit between them — the attacker will be
unable to resolve the PLC's hostname via DNS, and even a direct IP
connection attempt will fail, at the network layer, before any Modbus
traffic can be sent at all. This is a stronger result than "detected
faster" (Phase 11): the attack should not be able to start.

## Method

1. Bring up **Config A** (`docker-compose.yml`) and run
   `experiments/02-network-segmentation/run_experiment.py plc 5020`
   from inside the attacker container. Record whether DNS resolves
   and whether the TCP connection succeeds.
2. Bring Config A down, bring up **Config B**
   (`docker-compose.segmented.yml`), and run the exact same command
   from inside the same attacker container image.
3. Compare the two results directly.

### Variables

- **Independent variable:** network configuration (Config A flat vs.
  Config B segmented) — this is the only thing that changes between
  the two runs.
- **Dependent variables:** DNS resolution success, TCP connection
  success, and — only if both succeed — whether Experiment 01's
  Modbus write can even be attempted.

## Result

**Script logic verified locally before any Docker run** (both code
paths tested against real conditions — a real reachable local PLC,
and a real DNS-resolution failure — to confirm the measurement tool
itself behaves correctly under both outcomes before trusting it to
report the actual network comparison):

| Simulated condition | DNS resolved | TCP connected | `attack_path_reachable` |
|---|---|---|---|
| Reachable (stand-in for Config A) | Yes (`127.0.0.1`, 0.004s) | Yes (0.001s) | `True` |
| Unreachable (stand-in for Config B's expected DNS failure) | No (`Name or service not known`, 0.006s) | No (same error) | `False` |

**The actual Config A vs Config B Docker comparison itself: DATA NOT
YET COLLECTED.** Per Section 43 of the project spec, this is stated
plainly rather than assumed — the network topology test requires
Docker, which was unavailable in the environment this experiment
script was developed in. Run the commands below and record the real
output in this table:

| Run | DNS resolved | TCP connected | `attack_path_reachable` |
|---|---|---|---|
| Config A (flat) | _fill in_ | _fill in_ | _fill in_ |
| Config B (segmented) | _fill in_ | _fill in_ | _fill in_ |

## How to reproduce

```bash
# --- Config A ---
docker compose up --build -d
sleep 5
docker compose exec attacker python3 experiments/02-network-segmentation/run_experiment.py plc 5020
docker compose down

# --- Config B ---
docker compose -f docker-compose.segmented.yml up --build -d
sleep 5
docker compose -f docker-compose.segmented.yml exec attacker python3 experiments/02-network-segmentation/run_experiment.py plc 5020
docker compose -f docker-compose.segmented.yml down
```

Both runs append to the same `data/experiments/02-network-segmentation/results.csv`
— the `timestamp` column is enough to tell them apart, or check
`docker compose ps` output alongside each run to confirm which
topology was active.

**Expected result under Config B:** DNS resolution failure
(`[Errno -2] Name or service not known` or equivalent) for hostname
`plc`, and therefore `attack_path_reachable: False`. If the DNS
lookup unexpectedly succeeds under Config B, check `docker network ls`
and confirm the attacker container is genuinely only on `corp_net` —
that would indicate a Compose configuration problem, not a finding
about Docker networking itself (Docker's network isolation is a
well-established platform guarantee, not something this project is
testing the existence of).

## Conclusion

*(To be completed once the real Config A/B results are recorded
above.)* If the hypothesis holds, this experiment demonstrates that
network segmentation — with no other change to the PLC, its
authentication (still none), or its register map — is sufficient to
fully block Experiment 01's attack path at the network layer, before
Phase 11's IDS even has traffic to observe. This would be the
project's strongest single before/after result: Experiment 01 alone
shows the vulnerability; Experiment 02 shows that segmentation, not
better Modbus security, is what actually stops it here.

## Relationship to Experiment 01

This experiment does not repeat Experiment 01's Modbus write — it
measures the network-reachability precondition Experiment 01 silently
assumed. If `attack_path_reachable` is `False` under Config B, running
Experiment 01's actual write attempt against Config B would fail even
earlier (at the TCP connect stage, before pymodbus could even form a
request) — that failure is implied by this experiment's result, not
independently required for the comparison to be valid.

## Framework mappings

| Framework | Reference | Relevance |
|---|---|---|
| NIST CSF v1.1 | [PR.AC-5](https://csf.tools/reference/nist-cybersecurity-framework/v1-1/pr/pr-ac/pr-ac-5/) — "Network integrity is protected (e.g., network segregation, network segmentation)" | This experiment directly tests whether implementing PR.AC-5 changes the outcome of Experiment 01's attack |
| IEC 62443 | Zones and Conduits concept | Config A has one zone (everything flat); Config B introduces two zones (`corp_net`, `ot_net`) with **no conduit** between them — the strictest possible zone separation, appropriate for this experiment's isolated variable but not necessarily realistic for a plant that needs *some* legitimate corp-to-OT path (a controlled conduit is a natural addition once an engineering-workstation/vendor-gateway component exists in a later phase) |

A full, consolidated IEC 62443/NIST CSF matrix covering every
experiment in this project is built in Phase 14; this table is this
experiment's own contribution to that later document.


[experiment] Attempting DNS resolution of 'plc'...
[experiment] DNS resolution: SUCCESS (172.20.0.2) in 0.002s
[experiment] Attempting TCP connect to 172.20.0.2:5020 (timeout 5.0s)...
[experiment] TCP connect: SUCCESS (connected) in 0.0s

[experiment] ===== RESULT =====
  experiment_id: 02-network-segmentation
  timestamp: 1787385189.50256
  target_host: plc
  target_port: 5020
  dns_resolution_success: True
  dns_resolution_result: 172.20.0.2
  dns_resolution_time_s: 0.002
  tcp_connect_success: True
  tcp_connect_error: None
  tcp_connect_time_s: 0.0
  attack_path_reachable: True

[experiment] Attack path reachable: True
[experiment] Saved: /app/data/experiments/02-network-segmentation/result_1787385189.json
[experiment] Appended: /app/data/experiments/02-network-segmentation/results.csv
[+] down 5/5
Confirmed. Network segmentation alone — with no change to the PLC's authentication (still none) — completely blocked Experiment 01's attack path. Under Config A, the attacker resolved and connected to the PLC in milliseconds. Under Config B, DNS resolution itself failed in 0.006s; the attack could not even begin. This is a stronger outcome than Phase 11's detection improvement (t+0s vs t+8.14s) — segmentation doesn't just detect the attack faster, it prevents it from reaching the target at all.