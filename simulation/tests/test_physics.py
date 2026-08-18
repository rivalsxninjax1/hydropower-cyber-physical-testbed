"""
Unit tests for the physics engine, per Section 46 of the spec
(reservoir calculations, flow calculations, turbine calculations).

Run with:  pytest simulation/tests/test_physics.py -v
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simulation.physics_engine.reservoir import Reservoir
from simulation.physics_engine.gate import Gate
from simulation.physics_engine.turbine import Turbine
from simulation.physics_engine.generator import Generator
from simulation.physics_engine.engine import PhysicsEngine
from simulation.physics_engine import config


def test_reservoir_level_rises_when_inflow_exceeds_outflow():
    r = Reservoir(level_m=40.0, base_inflow_m3s=100.0)
    r.step(dt=10.0, outflow_m3s=0.0)
    assert r.level_m > 40.0


def test_reservoir_level_falls_when_outflow_exceeds_inflow():
    r = Reservoir(level_m=40.0, base_inflow_m3s=10.0)
    r.step(dt=10.0, outflow_m3s=100.0)
    assert r.level_m < 40.0


def test_reservoir_level_clamped_to_max():
    r = Reservoir(level_m=config.RESERVOIR_MAX_LEVEL_M, base_inflow_m3s=1000.0)
    r.step(dt=100.0, outflow_m3s=0.0)
    assert r.level_m == config.RESERVOIR_MAX_LEVEL_M


def test_reservoir_level_clamped_to_min():
    r = Reservoir(level_m=config.RESERVOIR_MIN_LEVEL_M, base_inflow_m3s=0.0)
    r.step(dt=100.0, outflow_m3s=1000.0)
    assert r.level_m == config.RESERVOIR_MIN_LEVEL_M


def test_gate_moves_toward_target_but_is_rate_limited():
    g = Gate(position_pct=0.0, target_pct=100.0)
    g.step(dt=1.0)
    # should have moved by at most GATE_MAX_RATE_PCT_PER_S, not jumped to 100
    assert 0.0 < g.position_pct <= config.GATE_MAX_RATE_PCT_PER_S + 1e-6
    assert g.position_pct < 100.0


def test_gate_reaches_target_eventually():
    g = Gate(position_pct=0.0, target_pct=50.0)
    for _ in range(1000):
        g.step(dt=1.0)
    assert math.isclose(g.position_pct, 50.0, abs_tol=1e-6)


def test_gate_outflow_zero_when_closed():
    g = Gate(position_pct=0.0, target_pct=0.0)
    assert g.outflow_m3s(head_m=50.0) == 0.0


def test_gate_outflow_increases_with_head():
    g = Gate(position_pct=50.0, target_pct=50.0)
    low_head_flow = g.outflow_m3s(head_m=10.0)
    high_head_flow = g.outflow_m3s(head_m=50.0)
    assert high_head_flow > low_head_flow


def test_gate_outflow_increases_with_position():
    g_open = Gate(position_pct=80.0, target_pct=80.0)
    g_closed = Gate(position_pct=20.0, target_pct=20.0)
    assert g_open.outflow_m3s(head_m=40.0) > g_closed.outflow_m3s(head_m=40.0)


def test_turbine_rpm_relaxes_toward_target():
    t = Turbine(design_flow_m3s=50.0, rpm=1500.0)
    # flow doubled relative to design -> target rpm doubles
    t.step(dt=1.0, flow_m3s=100.0)
    assert t.rpm > 1500.0
    assert t.rpm < 3000.0  # inertia means it hasn't jumped straight there


def test_turbine_rpm_converges_over_time():
    t = Turbine(design_flow_m3s=50.0, rpm=1500.0)
    for _ in range(500):
        t.step(dt=1.0, flow_m3s=100.0)
    assert math.isclose(t.rpm, 3000.0, rel_tol=0.01)


def test_generator_power_scales_with_flow_and_head():
    gen = Generator()
    low = gen.power_mw(flow_m3s=20.0, head_m=30.0)
    high = gen.power_mw(flow_m3s=40.0, head_m=30.0)
    assert high > low
    assert math.isclose(high, low * 2, rel_tol=0.01)


def test_generator_power_capped_at_rated_capacity():
    gen = Generator()
    power = gen.power_mw(flow_m3s=1_000_000.0, head_m=1000.0)
    assert power == config.GENERATOR_RATED_MW


def test_engine_starts_in_normal_state():
    engine = PhysicsEngine()
    state = engine.state()
    assert state["alarm_state"] == "NORMAL"
    assert 0.0 <= state["reservoir_level_pct"] <= 100.0


def test_engine_gate_command_eventually_changes_physical_state():
    engine = PhysicsEngine()
    initial_flow = engine.state()["flow_m3s"]

    engine.set_gate_target(90.0)
    for _ in range(60):
        engine.step(dt=1.0)

    new_state = engine.state()
    assert new_state["gate_position_pct"] > 45.0
    assert new_state["flow_m3s"] > initial_flow


def test_engine_full_gate_closure_drives_flow_and_power_toward_zero():
    engine = PhysicsEngine()
    engine.set_gate_target(0.0)
    for _ in range(60):
        engine.step(dt=1.0)

    state = engine.state()
    assert state["gate_position_pct"] == 0.0
    assert state["flow_m3s"] == 0.0
    assert state["generator_power_mw"] == 0.0
