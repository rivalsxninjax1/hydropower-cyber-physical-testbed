"""
Cyber-physical incident correlation timeline.

Reads independently-timestamped records from three different sources —
the attacker/experiment log (network event), the PLC's own event log
(command applied), and the historian (physics telemetry + alarm
transitions) — and merges them into a single chronological narrative.

This is the practical demonstration of Section 24 of the project spec:
    Network Event + PLC Event + Physics Event + HMI Event = Security Incident

No IDS exists yet (that's Phase 11) — there is deliberately no
"detection" row with a real timestamp in this timeline, only an
explicit note that the gap exists. Labeling that gap rather than
inventing a detection event matches Section 43's "do not fake results"
rule.

Usage:
    python3 -m security.correlation.build_timeline [experiment_result.json]

If no path is given, the most recent file under
data/experiments/01-modbus-control/ is used.
"""

import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scada.historian import db as historian  # noqa: E402
from industrial.plc import register_map as regs  # noqa: E402

EXPERIMENT_DIR = REPO_ROOT / "data" / "experiments" / "01-modbus-control"
TIMELINE_WINDOW_BEFORE_S = 2
TIMELINE_WINDOW_AFTER_S = 30


def find_latest_experiment_result() -> Path:
    files = sorted(glob.glob(str(EXPERIMENT_DIR / "result_*.json")))
    if not files:
        raise FileNotFoundError(
            f"No experiment result files found in {EXPERIMENT_DIR}. "
            f"Run experiments/01-modbus-control/run_experiment.py first."
        )
    return Path(files[-1])


def build_timeline(experiment_path: Path) -> list:
    with open(experiment_path) as f:
        experiment = json.load(f)

    network_event_time = experiment["timestamp"]
    window_start = network_event_time - TIMELINE_WINDOW_BEFORE_S
    window_end = network_event_time + TIMELINE_WINDOW_AFTER_S

    events = [{
        "timestamp": network_event_time,
        "source": "Network",
        "description": (
            f"Unauthorized Modbus write: register {experiment['register_written']} "
            f"= {experiment['raw_value_written']} (from {experiment['target_host']})"
        ),
    }]

    for plc_event in historian.get_recent_plc_events(limit=200):
        if window_start <= plc_event["timestamp"] <= window_end:
            events.append({
                "timestamp": plc_event["timestamp"],
                "source": "PLC",
                "description": plc_event["description"] or (
                    f"Register {plc_event['register']} changed "
                    f"{plc_event['previous_raw']} -> {plc_event['new_raw']}"
                ),
            })

    baseline = experiment["baseline_registers"]
    baseline_flow = regs.decode("FLOW_RATE_M3S", baseline[2])
    baseline_rpm = regs.decode("TURBINE_RPM", baseline[3])

    flow_milestone_logged = False
    rpm_milestone_logged = False
    for row in reversed(historian.get_recent_telemetry(limit=500)):
        if not (window_start <= row["timestamp"] <= window_end):
            continue
        if not flow_milestone_logged and row["flow_m3s"] > baseline_flow * 1.1:
            events.append({
                "timestamp": row["timestamp"],
                "source": "Physics",
                "description": (
                    f"Flow rate detectably increasing: {baseline_flow:.1f} -> "
                    f"{row['flow_m3s']:.1f} m3/s"
                ),
            })
            flow_milestone_logged = True
        if not rpm_milestone_logged and row["turbine_rpm"] > baseline_rpm * 1.05:
            events.append({
                "timestamp": row["timestamp"],
                "source": "Physics",
                "description": (
                    f"Turbine RPM detectably increasing: {baseline_rpm:.1f} -> "
                    f"{row['turbine_rpm']:.1f}"
                ),
            })
            rpm_milestone_logged = True

    for alarm_event in historian.get_recent_alarm_events(limit=100):
        if window_start <= alarm_event["timestamp"] <= window_end:
            events.append({
                "timestamp": alarm_event["timestamp"],
                "source": "HMI/Alarm",
                "description": (
                    f"Alarm state changed: {alarm_event['previous_state']} -> "
                    f"{alarm_event['new_state']}"
                ),
            })

    ids_alerts_in_window = [
        a for a in historian.get_recent_ids_alerts(limit=100)
        if window_start <= a["timestamp"] <= window_end
    ]
    if ids_alerts_in_window:
        for alert in ids_alerts_in_window:
            events.append({
                "timestamp": alert["timestamp"],
                "source": "IDS",
                "description": (
                    f"[{alert['severity']}] {alert['rule']}: {alert['description']} "
                    f"(source {alert['source_ip']})"
                ),
            })
    else:
        events.append({
            "timestamp": window_end,
            "source": "IDS",
            "description": (
                "NO DETECTION EVENT logged in this window - either the IDS "
                "(Phase 11) was not running, or this particular write did "
                "not trigger any of its rules. This gap is reported "
                "honestly rather than inventing a detection event."
            ),
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def print_timeline(events: list) -> None:
    print("\n=== Cyber-Physical Incident Timeline ===\n")
    t0 = events[0]["timestamp"]
    for e in events:
        offset = e["timestamp"] - t0
        print(f"  t+{offset:5.2f}s  [{e['source']:10s}]  {e['description']}")
    print()


def main() -> None:
    if len(sys.argv) > 1:
        experiment_path = Path(sys.argv[1])
    else:
        experiment_path = find_latest_experiment_result()

    print(f"[timeline] Using experiment result: {experiment_path}")
    events = build_timeline(experiment_path)
    print_timeline(events)

    output_path = experiment_path.parent / f"timeline_{int(events[0]['timestamp'])}.json"
    with open(output_path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"[timeline] Saved: {output_path}")


if __name__ == "__main__":
    main()