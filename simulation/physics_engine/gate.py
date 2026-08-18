"""
Intake gate model.

Two behaviours matter for this project:

1. Rate-limited actuator: the gate cannot jump instantly from one
   position to another. It moves toward `target_pct` at a fixed
   maximum rate (GATE_MAX_RATE_PCT_PER_S). This is what makes an
   unauthorized command produce a *visible, gradual* physical change
   later, instead of an instant jump.

2. Outflow via a simplified orifice equation:
       Q = Cd * A_max * (position/100) * sqrt(2 * g * head)
   This is the standard discharge equation for flow through a gated
   orifice under head `head` (here: reservoir level above the intake).
"""

import math

from . import config


class Gate:
    def __init__(
        self,
        position_pct: float = config.GATE_INITIAL_POSITION_PCT,
        target_pct: float = config.GATE_INITIAL_TARGET_PCT,
    ):
        self.position_pct = position_pct
        self.target_pct = target_pct

    def set_target(self, target_pct: float) -> None:
        """This is the method a PLC register write will call in Phase 4/5."""
        self.target_pct = max(0.0, min(100.0, target_pct))

    def step(self, dt: float) -> None:
        max_move = config.GATE_MAX_RATE_PCT_PER_S * dt
        diff = self.target_pct - self.position_pct
        if abs(diff) <= max_move:
            self.position_pct = self.target_pct
        else:
            self.position_pct += max_move if diff > 0 else -max_move

    def outflow_m3s(self, head_m: float) -> float:
        head = max(0.0, head_m)
        return (
            config.GATE_DISCHARGE_COEFF
            * config.GATE_MAX_AREA_M2
            * (self.position_pct / 100.0)
            * math.sqrt(2 * config.GRAVITY_M_S2 * head)
        )
