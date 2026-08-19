"""
Tests for the PLC register map and PLC control logic.

Two kinds of tests here, per Section 46:
  1. Pure register map tests (encode/decode) — no server needed.
  2. PLC control-loop tests — exercise PLC.run_control_loop() logic
     directly against the datastore, without opening a real TCP socket
     (fast, no port conflicts, no network flakiness in CI).

A separate manual/integration check — actually connecting a Modbus TCP
client over the network — is documented in
docs/architecture/plc-register-map.md, since that requires a running
server process and is better run as a one-off script during
development than as an automated pytest case.

Run with:  pytest industrial/tests/test_plc.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from industrial.plc import register_map as regs
from industrial.plc.plc_server import PLC


# --- Register map: encode/decode ---

def test_encode_decode_round_trip():
    for reg in regs.REGISTERS:
        raw = regs.encode(reg.name, 12.3 if reg.scale != 1.0 else 5)
        back = regs.decode(reg.name, raw)
        # Allow small fixed-point rounding error
        assert abs(back - (12.3 if reg.scale != 1.0 else 5)) < 0.2


def test_encode_clamps_to_uint16_range():
    raw = regs.encode("RESERVOIR_LEVEL_PCT", 999999)
    assert 0 <= raw <= 65535


def test_encode_clamps_negative_to_zero():
    raw = regs.encode("GATE_POSITION_PCT", -50)
    assert raw == 0


def test_by_name_raises_on_unknown_register():
    try:
        regs.by_name("NOT_A_REAL_REGISTER")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_register_map_has_exactly_one_writable_register():
    writable = [r for r in regs.REGISTERS if r.writable]
    assert len(writable) == 1
    assert writable[0].name == "GATE_TARGET_COMMAND_PCT"


def test_register_addresses_are_sequential_and_unique():
    addresses = [r.zero_based_address for r in regs.REGISTERS]
    assert addresses == sorted(addresses)
    assert len(addresses) == len(set(addresses))


# --- PLC control loop (no network, direct datastore access) ---

def test_plc_seeds_registers_from_initial_engine_state():
    plc = PLC()
    level_reg = regs.by_name("RESERVOIR_LEVEL_PCT")
    raw = plc.holding_registers.getValues(level_reg.zero_based_address + 1, count=1)[0]
    assert regs.decode("RESERVOIR_LEVEL_PCT", raw) == plc.engine.state()["reservoir_level_pct"]


def test_plc_applies_a_written_gate_command():
    plc = PLC()
    target_reg = regs.by_name("GATE_TARGET_COMMAND_PCT")

    # Simulate a Modbus client writing 90% directly into the datastore
    # (this is exactly what a real Modbus write does on the wire).
    raw_command = regs.encode("GATE_TARGET_COMMAND_PCT", 90.0)
    plc.holding_registers.setValues(target_reg.zero_based_address + 1, [raw_command])

    plc._check_for_new_command()
    assert plc.engine.gate.target_pct == 90.0


def test_plc_ignores_unchanged_register_value():
    plc = PLC()
    initial_target = plc.engine.gate.target_pct

    plc._check_for_new_command()  # no write happened; should be a no-op
    assert plc.engine.gate.target_pct == initial_target


def test_plc_control_loop_produces_visible_physical_change():
    """End-to-end without a socket: write a command, run several ticks
    of the same loop the async server uses, confirm physics moved."""
    plc = PLC()
    target_reg = regs.by_name("GATE_TARGET_COMMAND_PCT")

    raw_command = regs.encode("GATE_TARGET_COMMAND_PCT", 90.0)
    plc.holding_registers.setValues(target_reg.zero_based_address + 1, [raw_command])

    for _ in range(10):
        plc._check_for_new_command()
        plc.engine.step(dt=1.0)
        plc._refresh_readonly_registers(plc.engine.state())

    flow_reg = regs.by_name("FLOW_RATE_M3S")
    raw_flow = plc.holding_registers.getValues(flow_reg.zero_based_address + 1, count=1)[0]
    flow = regs.decode("FLOW_RATE_M3S", raw_flow)

    assert flow > 68.7  # steady-state baseline flow from Phase 2 defaults