"""
Manual Modbus TCP test client for the PLC.

This is a standalone script (not a pytest test) for interactively
exercising the PLC over a real network connection — read all
registers, then write a new gate target and watch the physical values
change over the following seconds.

The PLC must already be running:
    python -m industrial.plc.plc_server

Then in a second terminal:
    python -m industrial.plc.test_client

This script will later become the basis for the attacker's Modbus
client in Phase 8 — the same read/write calls, run from a machine that
is not supposed to have access.
"""

import time
import sys
from pathlib import Path

from pymodbus.client import ModbusTcpClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from industrial.plc import register_map as regs  # noqa: E402


def print_all_registers(client: ModbusTcpClient, heading: str) -> None:
    result = client.read_holding_registers(address=0, count=regs.REGISTER_COUNT, slave=1)
    print(f"\n=== {heading} ===")
    for reg, raw in zip(regs.REGISTERS, result.registers):
        real_value = regs.decode(reg.name, raw)
        access = "R/W" if reg.writable else "R  "
        print(f"  {reg.modbus_address}  [{access}]  {reg.name:28s} = {real_value}")


def main() -> None:
    client = ModbusTcpClient("127.0.0.1", port=5020)
    if not client.connect():
        print("Could not connect to PLC at 127.0.0.1:5020 — is plc_server.py running?")
        return

    print_all_registers(client, "BEFORE")

    new_target = float(input("\nEnter a new gate target percent (0-100): "))
    raw_command = regs.encode("GATE_TARGET_COMMAND_PCT", new_target)
    target_reg = regs.by_name("GATE_TARGET_COMMAND_PCT")

    print(f"\nWriting {new_target}% to register {target_reg.modbus_address}...")
    client.write_register(address=target_reg.zero_based_address, value=raw_command, slave=1)

    print("Waiting 6 seconds for the physics to respond...")
    time.sleep(6)

    print_all_registers(client, "AFTER")
    client.close()


if __name__ == "__main__":
    main()