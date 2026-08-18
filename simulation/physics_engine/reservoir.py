"""
Reservoir model.

Equation:
    dLevel/dt = (inflow - outflow) / surface_area

Inflow has a small deterministic sinusoidal variation representing a
diurnal cycle (NOT random noise — the spec explicitly requires
consistent, explainable behaviour rather than values that move only to
look alive on the UI).
"""

import math

from . import config


class Reservoir:
    def __init__(
        self,
        level_m: float = config.RESERVOIR_INITIAL_LEVEL_M,
        surface_area_m2: float = config.RESERVOIR_SURFACE_AREA_M2,
        base_inflow_m3s: float = config.RESERVOIR_BASE_INFLOW_M3S,
    ):
        self.level_m = level_m
        self.surface_area_m2 = surface_area_m2
        self.base_inflow_m3s = base_inflow_m3s
        self._sim_time_s = 0.0

    def inflow_m3s(self) -> float:
        """Deterministic inflow: constant baseline + slow sine variation."""
        variation = config.RESERVOIR_INFLOW_VARIATION_M3S * math.sin(
            2 * math.pi * self._sim_time_s / config.RESERVOIR_INFLOW_PERIOD_S
        )
        return max(0.0, self.base_inflow_m3s + variation)

    def level_pct(self) -> float:
        band = config.RESERVOIR_MAX_LEVEL_M - config.RESERVOIR_MIN_LEVEL_M
        pct = (self.level_m - config.RESERVOIR_MIN_LEVEL_M) / band * 100.0
        return max(0.0, min(100.0, pct))

    def step(self, dt: float, outflow_m3s: float) -> None:
        inflow = self.inflow_m3s()
        delta_level = (inflow - outflow_m3s) / self.surface_area_m2 * dt
        self.level_m += delta_level
        self.level_m = max(
            config.RESERVOIR_MIN_LEVEL_M,
            min(config.RESERVOIR_MAX_LEVEL_M, self.level_m),
        )
        self._sim_time_s += dt
