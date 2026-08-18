"""
Generator model.

Standard hydropower power equation:
    P = eta * rho * g * Q * H

where:
    eta = combined turbine + generator efficiency
    rho = water density
    g   = gravitational acceleration
    Q   = flow through the turbine (m^3/s)
    H   = effective head (m) — here approximated as reservoir level
          above the turbine, ignoring penstock friction losses
          (documented simplification, see docs/physics-model.md)

Frequency deviation is a purely illustrative simplification: real grid
governors correct frequency far faster/tighter than this. It exists so
an abnormal turbine RPM is visibly reflected in one more HMI value.
"""

from . import config


class Generator:
    def power_mw(self, flow_m3s: float, head_m: float) -> float:
        power_w = (
            config.GENERATOR_EFFICIENCY
            * config.WATER_DENSITY_KG_M3
            * config.GRAVITY_M_S2
            * max(0.0, flow_m3s)
            * max(0.0, head_m)
        )
        power_mw = power_w / 1_000_000.0
        return min(power_mw, config.GENERATOR_RATED_MW)

    def frequency_hz(self, rpm: float) -> float:
        deviation_fraction = (rpm - config.TURBINE_NOMINAL_RPM) / config.TURBINE_NOMINAL_RPM
        # Exaggerated-but-bounded illustrative deviation, not real governor physics.
        return config.GRID_NOMINAL_FREQUENCY_HZ + deviation_fraction * 0.5
