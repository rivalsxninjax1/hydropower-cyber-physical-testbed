# Physics Model — Equations and Assumptions

This document records exactly what the physics engine (`simulation/physics_engine/`)
models, and every simplification made, so results can be defended in a viva.

## Component equations

**Reservoir**
```
dLevel/dt = (inflow - outflow) / surface_area
```
Surface area is held constant (real reservoirs have level-dependent
surface area — ignored here as out of scope for this project).

**Inflow**
```
inflow(t) = base_inflow + amplitude * sin(2*pi*t / period)
```
Deterministic diurnal-style variation, not random noise, so behaviour
is reproducible and explainable run to run.

**Gate (actuator + discharge)**
```
position moves toward target at <= GATE_MAX_RATE_PCT_PER_S per second
outflow = Cd * A_max * (position/100) * sqrt(2 * g * head)
```
Standard orifice discharge equation. The rate limit models real
actuator speed and is what makes attack effects propagate over several
seconds rather than jumping instantly — this is deliberate, it is what
Phase 10's cyber-physical correlation timeline will show.

**Turbine**
```
target_rpm = nominal_rpm * (flow / design_flow)
d(rpm)/dt = (target_rpm - rpm) / tau        [tau = inertia time constant]
```
Simplification: a real grid-tied turbine is held near synchronous
speed by a governor regardless of flow, with *power* varying instead
of RPM. We deliberately model RPM as flow-responsive so abnormal flow
is visibly obvious on the HMI, which serves this project's
demonstration goal. This is stated explicitly so it is never mistaken
for an engineering claim about real turbine-governor behaviour.

**Generator**
```
power = eta * rho * g * flow * head          (capped at rated capacity)
frequency = 50Hz + (rpm - nominal_rpm)/nominal_rpm * 0.5
```
`power` is the standard hydropower power equation. Head is
approximated as reservoir level above the turbine (penstock friction
losses are ignored). The frequency-deviation term is illustrative only
— real grid frequency is regulated far more tightly; it exists purely
so RPM deviation is reflected in one more HMI value.

## Design-point calibration

`design_flow` for the turbine is computed once, at engine
initialization, as the flow the gate produces at its initial position
and the initial reservoir level. This means the plant starts at its
own nominal operating point (1500 RPM) by construction — standard
plant-design practice, not a fitted/fabricated result.

## Alarm thresholds

| Condition | State |
|---|---|
| RPM deviation > 30% from nominal, or reservoir <10% / >95% | CRITICAL |
| RPM deviation > 10% from nominal | WARNING |
| otherwise | NORMAL |

## What is intentionally NOT modelled

- Reservoir geometry (level-dependent surface area)
- Penstock friction losses / travel-time delay between gate and turbine
- Governor control loop (real turbines actively regulate speed against flow changes)
- Multiple turbine units / load-sharing
- Transformer and grid-side electrical dynamics beyond the frequency approximation above

These are out of scope for a lightweight, laptop-runnable teaching
simulation. If asked in a viva, the honest answer is: "the model
captures the causal *direction* and *rough magnitude* of each
relationship, not engineering-grade accuracy."
