"""
Physical constants and default plant parameters for the hydropower
physics simulation.

All values here are DESIGN PARAMETERS for a fictional small/medium
hydropower plant, chosen to produce a plausible steady-state operating
point (not measured field data). They are documented, not fabricated
results — see docs/physics-model.md for the reasoning behind each one.
"""

# --- Universal physical constants ---
GRAVITY_M_S2 = 9.81          # g
WATER_DENSITY_KG_M3 = 1000.0  # rho

# --- Reservoir ---
RESERVOIR_MIN_LEVEL_M = 30.0
RESERVOIR_MAX_LEVEL_M = 60.0
RESERVOIR_INITIAL_LEVEL_M = 51.6          # ~72% of the operating band
RESERVOIR_SURFACE_AREA_M2 = 250_000.0     # constant surface area (simplification:
                                           # real reservoirs have level-dependent
                                           # surface area; ignored here)

# Baseline river inflow. A mild deterministic diurnal variation (sine wave)
# is layered on top in Reservoir, NOT random noise — see docs/physics-model.md
# section "Why inflow is deterministic".
RESERVOIR_BASE_INFLOW_M3S = 65.0
RESERVOIR_INFLOW_VARIATION_M3S = 5.0      # amplitude of the diurnal sine variation
RESERVOIR_INFLOW_PERIOD_S = 86400.0       # 24h period (compressed in demo runs)

# --- Gate ---
GATE_MAX_RATE_PCT_PER_S = 4.0   # actuator speed limit: gate can move at most
                                 # this many percentage points per second
GATE_DISCHARGE_COEFF = 0.8      # Cd, standard orifice discharge coefficient
GATE_MAX_AREA_M2 = 6.0          # cross-sectional area of a fully open gate
GATE_INITIAL_POSITION_PCT = 45.0
GATE_INITIAL_TARGET_PCT = 45.0

# --- Turbine ---
TURBINE_NOMINAL_RPM = 1500.0
TURBINE_INERTIA_TIME_CONSTANT_S = 8.0
# design_flow is CALIBRATED (not fitted to fake data) so that, at the
# initial steady-state gate position and reservoir level, target RPM
# equals TURBINE_NOMINAL_RPM. This is standard plant-design practice:
# you size the turbine for its intended operating point.
TURBINE_DESIGN_FLOW_M3S = None  # computed at engine init; see engine.py

# --- Generator ---
GENERATOR_EFFICIENCY = 0.9      # eta, combined turbine+generator efficiency
GENERATOR_RATED_MW = 120.0      # hard capacity ceiling
GRID_NOMINAL_FREQUENCY_HZ = 50.0

# --- Simulation ---
DEFAULT_TICK_SECONDS = 1.0
