"""
Simulated intake-gate PLC.

Exposes the register map defined in register_map.py over Modbus TCP,
and bridges it to the Phase 2 physics engine:

  - Read-only registers (level, gate position, flow, RPM, power, alarm)
    are refreshed from the physics engine every tick.
  - The one writable register (GATE_TARGET_COMMAND_PCT) is read every
    tick; if its value has changed since the last tick, the PLC calls
    engine.set_gate_target(...) — exactly the way a real PLC applies
    an operator's or a malicious actor's command to the physical
    process, with no distinction between the two. That is the
    intentional vulnerability this project studies: Phase 4-5 have NO
    authentication on this register. Segmentation/access-control
    mitigation is added later, in Phase 12.

Run with (from repo root):
    python -m industrial.plc.plc_server
"""

import asyncio
import sys
from pathlib import Path
from simulation.physics_engine.engine import PhysicsEngine  # noqa: E402
from industrial.plc import register_map as regs  # noqa: E402
from scada.historian import db as historian  # noqa: E402

from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)
from pymodbus.server import StartAsyncTcpServer

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from simulation.physics_engine.engine import PhysicsEngine  # noqa: E402
from industrial.plc import register_map as regs  # noqa: E402

PLC_HOST = "0.0.0.0"
PLC_PORT = 5020  # NOTE: real Modbus TCP uses port 502, which requires
                  # root/admin privileges to bind on most systems. 5020
                  # is used throughout this project so it runs on an
                  # ordinary student laptop without sudo. Documented
                  # here and in docs/architecture/plc-register-map.md.

TICK_SECONDS = 1.0


class PLC:
    def __init__(self):
        historian.init_db()
        self.engine = PhysicsEngine()

        # One holding-register block sized to the register map.
        self.holding_registers = ModbusSequentialDataBlock(
            0, [0] * regs.REGISTER_COUNT
        )
        slave_ctx = ModbusSlaveContext(hr=self.holding_registers)
        self.server_context = ModbusServerContext(slaves=slave_ctx, single=True)

        self._last_known_target_raw = None
        self._write_initial_registers()

    def _write_initial_registers(self) -> None:
        """Seed the datastore so the writable register starts at the
        engine's actual current target, not zero — otherwise the PLC
        would see a 0% command on its very first tick and slam the
        gate shut."""
        state = self.engine.state()
        raw_target = regs.encode("GATE_TARGET_COMMAND_PCT", state["gate_target_pct"])
        self.holding_registers.setValues(
            regs.by_name("GATE_TARGET_COMMAND_PCT").zero_based_address + 1,
            [raw_target],
        )
        self._last_known_target_raw = raw_target
        self._refresh_readonly_registers(state)

    def _refresh_readonly_registers(self, state: dict) -> None:
        mapping = {
            "RESERVOIR_LEVEL_PCT": state["reservoir_level_pct"],
            "GATE_POSITION_PCT": state["gate_position_pct"],
            "FLOW_RATE_M3S": state["flow_m3s"],
            "TURBINE_RPM": state["turbine_rpm"],
            "GENERATOR_POWER_MW": state["generator_power_mw"],
        }
        for name, value in mapping.items():
            reg = regs.by_name(name)
            raw = regs.encode(name, value)
            # pymodbus addresses are 1-based relative to the block's
            # starting address in this API — see register_map.py notes.
            self.holding_registers.setValues(reg.zero_based_address + 1, [raw])

        alarm_reg = regs.by_name("ALARM_STATE")
        alarm_code = regs.ALARM_STATE_CODES[state["alarm_state"]]
        self.holding_registers.setValues(alarm_reg.zero_based_address + 1, [alarm_code])

    def _check_for_new_command(self) -> None:
        target_reg = regs.by_name("GATE_TARGET_COMMAND_PCT")
        raw = self.holding_registers.getValues(
            target_reg.zero_based_address + 1, count=1
        )[0]

        if raw != self._last_known_target_raw:
            new_target_pct = regs.decode("GATE_TARGET_COMMAND_PCT", raw)
            print(
                f"[PLC] Gate target register changed: "
                f"{self._last_known_target_raw} -> {raw} "
                f"({new_target_pct:.1f}%). Applying to physics engine."
            )
            historian.record_plc_event(
                register=target_reg.zero_based_address,
                previous_raw=self._last_known_target_raw,
                new_raw=raw,
                description=f"Gate target command changed to {new_target_pct:.1f}%",
            )
            self.engine.set_gate_target(new_target_pct)
            self._last_known_target_raw = raw

            
    async def run_control_loop(self) -> None:
        while True:
            self._check_for_new_command()
            self.engine.step(dt=TICK_SECONDS)
            self._refresh_readonly_registers(self.engine.state())
            await asyncio.sleep(TICK_SECONDS)


async def main() -> None:
    plc = PLC()
    print(f"[PLC] Starting Modbus TCP server on {PLC_HOST}:{PLC_PORT}")
    print("[PLC] Register map:")
    for reg in regs.REGISTERS:
        access = "R/W" if reg.writable else "R  "
        print(f"       {reg.modbus_address}  [{access}]  {reg.name}")

    await asyncio.gather(
        StartAsyncTcpServer(
            context=plc.server_context,
            address=(PLC_HOST, PLC_PORT),
        ),
        plc.run_control_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())