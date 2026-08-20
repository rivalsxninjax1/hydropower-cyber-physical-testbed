"""
Step 2 of the manual attack workflow: inspect an open Modbus TCP
service found during reconnaissance.

Usage:
    docker compose exec attacker python3 tools/modbus_recon.py <host> [port] [count]

This deliberately does NOT import the project's own
industrial/plc/register_map.py — a real attacker has no access to our
source code. It reads raw holding register values and prints them
as-is; making sense of them (which one is the control register, what
scale factor applies) is the attacker's job, not something read from
a convenient answer key. See modbus_probe_writable.py for how that
gets figured out.
"""

import sys
from pymodbus.client import ModbusTcpClient


def probe_valid_register_count(client: ModbusTcpClient, max_count: int = 20) -> int:
    """A real attacker doesn't know in advance how many registers a
    device exposes. This probes downward from max_count until a read
    succeeds, which is itself a legitimate (if crude) reconnaissance
    technique — the point where reads stop failing tells you where
    the device's valid register range ends."""
    for count in range(max_count, 0, -1):
        result = client.read_holding_registers(address=0, count=count, slave=1)
        if not result.isError():
            return count
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 modbus_recon.py <host> [port] [count]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5020

    client = ModbusTcpClient(host, port=port)
    if not client.connect():
        print(f"Could not connect to {host}:{port}")
        sys.exit(1)

    print(f"[recon] Connected to Modbus TCP service at {host}:{port}")

    if len(sys.argv) > 3:
        count = int(sys.argv[3])
    else:
        print("[recon] No register count given — probing to find the valid range...")
        count = probe_valid_register_count(client)
        print(f"[recon] Largest read that didn't error: {count} registers")

    print(f"[recon] Reading {count} holding registers, starting at address 0...\n")

    result = client.read_holding_registers(address=0, count=count, slave=1)
    if result.isError():
        print(f"Read failed: {result}")
        client.close()
        sys.exit(1)

    for i, value in enumerate(result.registers):
        print(f"  register[{i}] (Modbus addr 4000{i + 1}) = {value}")

    print("\n[recon] Raw values only — no field names or scaling known yet.")
    print("[recon] Next: figure out which register(s) actually control")
    print("[recon] something, rather than just reflecting sensor readings.")

    client.close()


if __name__ == "__main__":
    main()