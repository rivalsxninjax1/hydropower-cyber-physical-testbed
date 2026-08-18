"""
Turbine model.

Simplification (documented): a real grid-tied turbine is held at
synchronous speed by a governor almost regardless of flow, with power
output varying instead. For this project's teaching purpose — making
abnormal flow *visibly* change RPM on the HMI — we model RPM as
relaxing toward a flow-proportional target with first-order lag
(rotational inertia), rather than holding it rigidly constant:

    target_rpm = nominal_rpm * (flow / design_flow)
    d(rpm)/dt = (target_rpm - rpm) / tau

This is explicitly called out in docs/physics-model.md as a modelling
choice made for demonstrability, not an engineering claim about real
governor behaviour.
"""

from . import config


class Turbine:
    def __init__(
        self,
        design_flow_m3s: float,
        rpm: float = config.TURBINE_NOMINAL_RPM,
    ):
        self.design_flow_m3s = design_flow_m3s
        self.rpm = rpm

    def target_rpm(self, flow_m3s: float) -> float:
        if self.design_flow_m3s <= 0:
            return 0.0
        return config.TURBINE_NOMINAL_RPM * (flow_m3s / self.design_flow_m3s)

    def step(self, dt: float, flow_m3s: float) -> None:
        target = self.target_rpm(flow_m3s)
        tau = config.TURBINE_INERTIA_TIME_CONSTANT_S
        self.rpm += (target - self.rpm) / tau * dt
        self.rpm = max(0.0, self.rpm)
