"""
PhysicsEngine — ties reservoir, gate, turbine, and generator together
into one ticking simulation.

This is the ONLY object later phases (PLC, HMI) will talk to. In
Phase 4, the PLC's Modbus register writes will call
`engine.set_gate_target(...)` instead of touching Gate directly — this
keeps the physics model testable in isolation, per the spec's testing
requirement (Section 46).
"""

import math

from . import config
from .reservoir import Reservoir
from .gate import Gate
from .turbine import Turbine
from .generator import Generator


class PhysicsEngine:
    def __init__(self):
        self.reservoir = Reservoir()
        self.gate = Gate()

        # Calibrate design flow: the flow the gate produces at its
        # initial position and initial reservoir level becomes the
        # turbine's rated design flow, so the plant starts at its
        # own nominal operating point (1500 RPM) by construction.
        design_flow = self.gate.outflow_m3s(head_m=self.reservoir.level_m)
        self.turbine = Turbine(design_flow_m3s=design_flow)

        self.generator = Generator()
        self.alarm_state = "NORMAL"
        self.sim_time_s = 0.0

    # --- Command interface (what a PLC/attacker calls) ---
    def set_gate_target(self, target_pct: float) -> None:
        self.gate.set_target(target_pct)

    # --- Simulation tick ---
    def step(self, dt: float = config.DEFAULT_TICK_SECONDS) -> None:
        head_m = self.reservoir.level_m
        outflow = self.gate.outflow_m3s(head_m)

        self.gate.step(dt)
        self.reservoir.step(dt, outflow_m3s=outflow)
        self.turbine.step(dt, flow_m3s=outflow)

        self._update_alarm_state()
        self.sim_time_s += dt

    def _update_alarm_state(self) -> None:
        level_pct = self.reservoir.level_pct()
        rpm_deviation_pct = abs(
            self.turbine.rpm - config.TURBINE_NOMINAL_RPM
        ) / config.TURBINE_NOMINAL_RPM * 100.0

        if level_pct < 10 or level_pct > 95 or rpm_deviation_pct > 30:
            self.alarm_state = "CRITICAL"
        elif rpm_deviation_pct > 10:
            self.alarm_state = "WARNING"
        else:
            self.alarm_state = "NORMAL"

    # --- State snapshot (what the HMI/PLC registers will read) ---
    def state(self) -> dict:
        head_m = self.reservoir.level_m
        flow = self.gate.outflow_m3s(head_m)
        return {
            "sim_time_s": round(self.sim_time_s, 1),
            "reservoir_level_m": round(self.reservoir.level_m, 2),
            "reservoir_level_pct": round(self.reservoir.level_pct(), 1),
            "inflow_m3s": round(self.reservoir.inflow_m3s(), 2),
            "gate_position_pct": round(self.gate.position_pct, 1),
            "gate_target_pct": round(self.gate.target_pct, 1),
            "flow_m3s": round(flow, 2),
            "turbine_rpm": round(self.turbine.rpm, 1),
            "generator_power_mw": round(
                self.generator.power_mw(flow, head_m), 2
            ),
            "grid_frequency_hz": round(
                self.generator.frequency_hz(self.turbine.rpm), 3
            ),
            "alarm_state": self.alarm_state,
        }
