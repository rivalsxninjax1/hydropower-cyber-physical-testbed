# Network Architecture

## Current state: Config A (flat network)

`docker-compose.yml` runs two services on a **single** Docker network
(`flat_net`):
┌─────────────────────────────────────────┐
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

## What's coming

| Phase | Adds |
|---|---|
| 8 | An attacker container, also on `flat_net` initially — proving it can reach the PLC directly |
| 12 | `docker-compose.segmented.yml`: splits `flat_net` into `corp_net` / `dmz_net` / `ot_net`, moves the attacker to `corp_net` only, and adds a firewall/gateway container as the sole conduit between zones |

At that point the same attack from Phase 9 gets repeated against the
segmented topology, and the difference in outcome (blocked, or at
least detected sooner) becomes the project's strongest single
demonstration per Section 18 of the spec.

## Container inventory (current)

| Container | Image built from | Network | Exposed to host | Purpose |
|---|---|---|---|---|
| `plc` | `industrial/plc/Dockerfile` | `flat_net` | No | Modbus TCP PLC (Phase 4) |
| `dashboard` | `dashboard/backend/Dockerfile` | `flat_net` | `8000` | HMI + historian (Phase 5/6) |

`plc` is intentionally NOT published to the host — in the real
Purdue-model layout it has no business being reachable from outside
the OT network at all. Only `dashboard` (the HMI, which a real
operator legitimately needs to view) is published.

## How to verify the network topology yourself

```bash
docker compose up --build -d
docker network inspect hydropower-cyber-physical-testbed_flat_net
```

Look at the `Containers` section of the output — both `plc` and
`dashboard` should be listed, confirming they're on the same network
and can reach each other. This is the exact command used later to
verify Config B actually creates the isolation it claims to.

To confirm connectivity directly (not just Compose's network
membership) run a shell inside the dashboard container and reach the
PLC by its service name:

```bash
docker compose exec dashboard python3 -c "
import socket
s = socket.create_connection(('plc', 5020), timeout=3)
print('Reached PLC on port 5020 via service name \"plc\"')
s.close()
"
```