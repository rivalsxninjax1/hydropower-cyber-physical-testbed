# Intrusion Detection System (IDS)

## What this is

`security/ids/modbus_ids.py` — a passive Modbus TCP monitor that
sniffs raw packets addressed to the PLC, parses the Modbus protocol
directly from the wire (not via pymodbus — an independent parsing
path, so a pymodbus bug or compromise can't blind this too), and
evaluates every register write against two independent detection
rules in `security/ids/detection_rules.py`.

## A real constraint that shaped this design

The first design idea was to have pymodbus itself report each
request's source IP via its `request_tracer` callback. This was
**tested directly against pymodbus 3.6.9's source**, not assumed —
and confirmed that for TCP connections, `request_tracer` always
receives `addr = [None]`; source-address tracking only works for UDP
in this library version. That dead end is why the IDS instead sniffs
raw packets independently of pymodbus entirely.

The second constraint: Docker's default bridge network does **not**
let one container promiscuously see another container's unicast
traffic (this is standard switched-network behavior, confirmed by
design, not just assumed) — so a separate `ids` container on the same
`flat_net` as everything else would see nothing. The fix is
`network_mode: "service:plc"` in `docker-compose.yml`: the `ids`
container shares the PLC's network namespace entirely, so it sees
every packet addressed to the PLC exactly as if it were the PLC
itself — a standard, legitimate Docker sidecar-monitoring pattern.

## Detection rules

Two independent categories, each catching a different kind of threat:

| Rule | Category | Catches |
|---|---|---|
| `unauthorized_source` | Signature/identity-based | An attacker with network access but no legitimate reason to write to the PLC — flags any write whose source IP isn't the known `dashboard` address |
| `anomalous_command_value` | Behavioral/process-based | An extreme command value (gate target outside 10-90%) regardless of source — catches a compromised *legitimate* source too, which a pure source-IP check would miss entirely |

The expected legitimate source IP is resolved via Docker's own DNS
(`socket.gethostbyname("dashboard")`) at startup, not hardcoded —
overridable via the `IDS_EXPECTED_SOURCE_IP` environment variable for
local (non-Docker) testing.

## Verified real-packet pipeline (not just unit tests)

Before trusting the design, the full chain was tested against a real
running PLC with real Modbus TCP traffic:

1. Sniffed raw loopback traffic with scapy, sent a real
   `write_register` call, and confirmed the captured payload decoded
   correctly: function code `06`, register `6`, value `1000` — exact
   match to what was sent.
2. Ran the actual `modbus_ids.py` script (not a mock) against a live
   PLC: a normal-range write (45%) produced zero alerts; an
   extreme write (100%) produced exactly one `anomalous_command_value`
   alert, correctly written to the historian's `ids_alerts` table.
3. Found and fixed a real duplicate-alert bug during this testing —
   scapy on a loopback interface can observe the same logical packet
   twice (once leaving the sender, once arriving at the receiver).
   Added a 1-second deduplication window keyed on
   `(source_ip, register, value)`, which also incidentally guards
   against legitimate TCP retransmissions causing duplicate alerts in
   a real deployment.

## Before/after: what Phase 11 actually closes

Re-running Experiment 01 (`experiments/01-modbus-control/`) with the
IDS active now produces a materially different timeline than Phase
10's:

| | Phase 10 (no IDS) | Phase 11 (with IDS) |
|---|---|---|
| First detection | t+8.14s (alarm system reacting to physical deviation) | **t+0.00s** (IDS observing the write itself) |
| Detection mechanism | Physical consequence crossing an alarm threshold | Direct observation of the anomalous command, before any physical effect |

This is the actual measurable value of an IDS in an ICS context: it
moves detection from "after the plant has already started
misbehaving" to "the moment the bad command is sent" — which is
exactly the improvement a real security team would want to
demonstrate to a plant operator.

## How to run it manually

```bash
docker compose up -d
docker compose logs -f ids
```

Then trigger the experiment from another terminal and watch alerts
appear in the `ids` logs in real time, or check
`security/correlation/build_timeline.py`'s output for the merged
view.

## Automated tests

`security/tests/test_detection_rules.py` — 8 tests covering the pure
decision logic (no root privileges, no scapy, no real network
required):
- unauthorized source alone → CRITICAL
- authorized source + normal value → no alert
- authorized source + extreme value → WARNING only
- unauthorized source + extreme value → both alerts
- extreme value on a non-control register → no anomalous-value alert
- no expected source configured (DNS resolution failed) → no false
  positives from a missing allowlist
- boundary values (exactly 10%/90%) → no alert
- just outside the boundary → alert

The packet-parsing and capture code (`modbus_ids.py` itself) is
intentionally NOT unit tested — it was instead verified against real
captured traffic during development (see above), which is the more
meaningful check for code whose entire job is correctly interpreting
real bytes off a real wire.