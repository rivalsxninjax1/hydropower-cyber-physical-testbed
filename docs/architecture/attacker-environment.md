# Attacker Environment

## What this is

A container joined to `flat_net` alongside the `plc` and `dashboard`
containers, equipped with generic security tools (`nmap`, a Modbus TCP
client) but **no knowledge of this project's own source code** — it
does not import `industrial/plc/register_map.py`. Everything it
"knows" about the PLC's register map, it has to work out by observing
the device's behavior, the same way a real attacker probing an
unfamiliar ICS device would.

Per Section 15 of the project spec, this container runs nothing
automatically — it just stays alive (`tail -f /dev/null`) so each tool
is invoked manually, one step at a time, as a deliberate operator
action.

## The manual attack workflow

Run these from the host, in order, once `docker compose up` has all
three containers running:

### Step 1 — Network reconnaissance

```bash
docker compose exec attacker python3 tools/network_scan.py
```

Discovers the attacker's own subnet from its network interface (it
doesn't know this in advance either) and nmap-scans it for a handful
of common IT/ICS ports, including the ones this project actually uses.
**Expected finding:** port `5020` open on the `plc` container's
address — a Modbus TCP service, though at this stage the scanner
doesn't yet know that's what it is beyond nmap's own service
fingerprinting.

### Step 2 — Inspect the Modbus service

```bash
docker compose exec attacker python3 tools/modbus_recon.py plc 5020
```

Connects and probes downward from 20 registers until reads stop
returning `IllegalAddress`, then dumps every raw register value. At
this point the attacker has numbers, but no idea what any of them
mean — no field names, no scale factors.

### Step 3 — Identify the real control register

```bash
docker compose exec attacker python3 tools/modbus_probe_writable.py plc 5020
```

Writes a distinctive marker value into **every** register, waits two
seconds, and reads them all back. Registers driven by the PLC's own
control loop (sensor/computed values) get silently overwritten within
that window; the one genuine control register does not. This
correctly and unambiguously identifies the control register purely
through observation — verified against this project's real PLC, it
finds exactly one persistent register every time.

### Step 4 — Unauthorized command

```bash
docker compose exec attacker python3 tools/exploit_gate.py plc 6 1000
```

Writes an operator-level command directly to the register found in
Step 3, with no authentication required. Watch `http://127.0.0.1:8000`
in a browser, or re-run `modbus_recon.py`, to see the physical
consequence: gate position climbs, flow and turbine RPM rise, and the
alarm state escalates from NORMAL to WARNING — all triggered by a
container that never touched the HMI at all.

## Verified end-to-end (tested against the real PLC before shipping)

| Step | Result |
|---|---|
| Recon register count probe | Correctly found exactly 7 valid registers |
| Persistence probe | Correctly identified register 6 as the sole control register |
| Exploit (write 1000 to register 6) | Gate 45.0%→69.0%, flow 68.7→105.4 m³/s, RPM 1500→1712, alarm NORMAL→WARNING |

This is the "before" evidence for Phase 12's segmentation experiment —
the same four commands, repeated against the segmented network, should
fail or be detected far sooner once `docker-compose.segmented.yml`
exists.

## Why nmap and not a bigger toolkit

Section 15 lists several possible attacker tools (Nmap, Wireshark,
Hydra, etc.). Only `nmap` and a Modbus client are included in this
phase because they're what the Phase 9 Modbus experiment actually
needs — adding tools before there's an experiment that uses them would
be exactly the "unnecessary complexity" Section 54 warns against.
Wireshark/tshark for traffic analysis and Hydra for credential attacks
get added when Phase 8's later companion experiments (traffic
analysis, vendor-access) actually need them.