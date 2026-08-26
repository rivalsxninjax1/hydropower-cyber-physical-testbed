# Network Architecture

## Current state: Config A (flat network)

`docker-compose.yml` runs two services on a **single** Docker network
(`flat_net`):
─────────────────────────────────────────┐
│ flat_net │
│ │
│ ┌─────────┐ ┌───────────┐ │
│ │ plc │◄────────►│ dashboard │ │
│ │ :5020 │ Modbus │ :8000 │ │
│ └─────────┘ TCP └─────┬─────┘ │
│ │ │
└───────────────────────────────┼───────────┘
│
(published to host)
│
your browser

This is **Config A** from Section 18 of the project spec — the
deliberate "before" state. Any container attached to `flat_net` can
reach any other container on it, on any port. There is no distinction
yet between what will become corporate, DMZ, and OT zones — that
distinction is architectural intent right now, not yet enforced by
anything.

## Why start here instead of building the segmented version first

The segmentation experiment (Phase 12, Section 18/27 of the spec) is
only meaningful as a **comparison**. Building the "after" (segmented,
Config B) state first would mean there's no working "before" state to
measure it against. Config A is built, run, and left as a permanent,
reproducible baseline — `docker-compose.yml` never changes to become
Config B; instead Phase 12 adds a *second* file,
`docker-compose.segmented.yml`, so both configurations can be brought
up independently and compared directly, with real container-to-
container connectivity tests as the evidence, not just a diagram.

## Config B now exists

`docker-compose.segmented.yml` implements the "after" state described
below — see `experiments/02-network-segmentation/README.md` for the
formal comparison experiment. Full topology diagram:
┌───────────────────┐ ┌──────────────────────────────┐
│ corp_net │ │ ot_net │
│ │ │ │
│ ┌──────────────┐ │ │ ┌─────────┐ ┌───────────┐ │
│ │ attacker │ │ X │ │ plc │◄──►│ dashboard │ │
│ └──────────────┘ │ no │ │ :5020 │ │ :8000 │ │
│ │ route │ └────┬────┘ └─────┬─────┘ │
└───────────────────┘ │ │ (network_mode) │ │
│ ┌────▼─────┐ │ │
│ │ ids │ │ │
│ └──────────┘ │ │
└─────────────────────────┼────────┘
│
(published to host)
│
your browser

`corp_net` and `ot_net` share no container and no gateway — Docker's
own network isolation means the attacker container cannot resolve
`plc` or `dashboard` by name, and cannot route to their IPs even if it
somehow learned them.

## What's still coming (beyond Phase 12)

- A DMZ zone and a controlled conduit (vendor-access gateway,
  engineering workstation jump host) for a more realistic
  "some legitimate corp-to-OT path exists" topology, once those
  components are built in later phases
- Firewall rules as an explicit, inspectable artifact (currently the
  isolation is implicit in "no shared network" rather than an explicit
  rule set — sufficient for this project's segmentation experiment,
  but worth noting as a simplification)

## Container inventory (current, both configs)

| Container | Image built from | Network (Config A) | Network (Config B) | Exposed to host | Purpose |
|---|---|---|---|---|---|
| `plc` | `industrial/plc/Dockerfile` | `flat_net` | `ot_net` | No | Modbus TCP PLC (Phase 4) |
| `dashboard` | `dashboard/backend/Dockerfile` | `flat_net` | `ot_net` | `8000` | HMI + historian (Phase 5/6) |
| `attacker` | `attacker/Dockerfile` | `flat_net` | `corp_net` | No | Manual attack tools (Phase 8) |
| `ids` | `security/ids/Dockerfile` | shares `plc`'s netns | shares `plc`'s netns | No | Passive Modbus monitor (Phase 11) |

`plc` is intentionally NOT published to the host — in the real
Purdue-model layout it has no business being reachable from outside
the OT network at all. Only `dashboard` (the HMI, which a real
operator legitimately needs to view) is published. `ids` never appears
with its own IP/ports in either config since `network_mode:
"service:plc"` means it shares the PLC's network stack entirely
rather than joining a network of its own.

## How to verify the network topology yourself

**Config A:**
```bash
docker compose up --build -d
docker network inspect hydropower-cyber-physical-testbed_flat_net
```
Look at the `Containers` section — `plc`, `dashboard`, and `attacker`
should all be listed (confirming they share one network and can reach
each other).

**Config B:**
```bash
docker compose down
docker compose -f docker-compose.segmented.yml up --build -d
docker network inspect hydropower-cyber-physical-testbed_ot_net
docker network inspect hydropower-cyber-physical-testbed_corp_net
```
`ot_net` should list `plc` and `dashboard`. `corp_net` should list
only `attacker`. No container should appear in both.

To confirm connectivity directly (not just network membership), run a
shell inside the dashboard container and reach the PLC by its service
name — this should succeed under BOTH configs, since `dashboard` and
`plc` share `ot_net` in both:

```bash
docker compose exec dashboard python3 -c "
import socket
s = socket.create_connection(('plc', 5020), timeout=3)
print('Reached PLC on port 5020 via service name \"plc\"')
s.close()
"
```

Then try the same test from the attacker container — this should
succeed under Config A and FAIL under Config B (see
`experiments/02-network-segmentation/` for the formal measured
version of exactly this test):

```bash
docker compose exec attacker python3 -c "
import socket
s = socket.create_connection(('plc', 5020), timeout=3)
print('Reached PLC')
s.close()
"
```