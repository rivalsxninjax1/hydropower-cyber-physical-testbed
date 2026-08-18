"""
Standalone demo: runs the physics engine for a simulated period with
no Docker, no networking, no PLC — proving the physical model is
correct in isolation before anything else is layered on top of it.

Run with:  python simulation/run_demo.py
"""

from physics_engine.engine import PhysicsEngine


def main():
    engine = PhysicsEngine()

    print(f"{'t(s)':>6} {'level%':>8} {'gate%':>7} {'flow(m3/s)':>11} "
          f"{'rpm':>8} {'power(MW)':>10} {'freq(Hz)':>9} {'alarm':>10}")

    # Run 30 seconds of normal operation.
    for _ in range(30):
        engine.step(dt=1.0)
        s = engine.state()
        print(f"{s['sim_time_s']:>6} {s['reservoir_level_pct']:>8} "
              f"{s['gate_position_pct']:>7} {s['flow_m3s']:>11} "
              f"{s['turbine_rpm']:>8} {s['generator_power_mw']:>10} "
              f"{s['grid_frequency_hz']:>9} {s['alarm_state']:>10}")

    print("\n--- Simulating a gate command change (target -> 90%) ---\n")
    engine.set_gate_target(90.0)

    for _ in range(30):
        engine.step(dt=1.0)
        s = engine.state()
        print(f"{s['sim_time_s']:>6} {s['reservoir_level_pct']:>8} "
              f"{s['gate_position_pct']:>7} {s['flow_m3s']:>11} "
              f"{s['turbine_rpm']:>8} {s['generator_power_mw']:>10} "
              f"{s['grid_frequency_hz']:>9} {s['alarm_state']:>10}")


if __name__ == "__main__":
    main()
