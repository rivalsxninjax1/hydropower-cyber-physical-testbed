"""
Experiment 02 — Network Segmentation Effect on the Modbus Control Attack.

Repeats the exact same attack as experiments/01-modbus-control/, but
measures the RECONNAISSANCE step rather than assuming it succeeds:
does DNS resolve "plc" at all, and does a TCP connection to port 5020
succeed, from the attacker container's point of view? This is run
once against Config A (flat_net) and once against Config B
(segmented), and the two results are the actual evidence for Section
18/27's before/after comparison — not a diagram, a measurement.

Usage (from inside the attacker container):
    python3 run_experiment.py <plc_host> [plc_port] [timeout_seconds]

Example:
    python3 run_experiment.py plc 5020 5
"""

import csv
import json
import socket
import sys
import time
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "experiments" / "02-network-segmentation"


def attempt_dns_resolution(host: str):
    start = time.time()
    try:
        ip = socket.gethostbyname(host)
        return True, ip, round(time.time() - start, 3)
    except socket.gaierror as exc:
        return False, str(exc), round(time.time() - start, 3)


def attempt_tcp_connect(host: str, port: int, timeout: float):
    start = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True, None, round(time.time() - start, 3)
    except (socket.timeout, socket.error, OSError) as exc:
        return False, str(exc), round(time.time() - start, 3)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 run_experiment.py <plc_host> [plc_port] [timeout_seconds]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5020
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    print(f"[experiment] Attempting DNS resolution of '{host}'...")
    dns_success, dns_result, dns_time = attempt_dns_resolution(host)
    print(f"[experiment] DNS resolution: {'SUCCESS' if dns_success else 'FAILED'} "
          f"({dns_result}) in {dns_time}s")

    connect_target = dns_result if dns_success else host
    print(f"[experiment] Attempting TCP connect to {connect_target}:{port} "
          f"(timeout {timeout}s)...")
    tcp_success, tcp_error, tcp_time = attempt_tcp_connect(connect_target, port, timeout)
    print(f"[experiment] TCP connect: {'SUCCESS' if tcp_success else 'FAILED'} "
          f"({tcp_error if tcp_error else 'connected'}) in {tcp_time}s")

    attack_path_reachable = dns_success and tcp_success

    result = {
        "experiment_id": "02-network-segmentation",
        "timestamp": time.time(),
        "target_host": host,
        "target_port": port,
        "dns_resolution_success": dns_success,
        "dns_resolution_result": dns_result,
        "dns_resolution_time_s": dns_time,
        "tcp_connect_success": tcp_success,
        "tcp_connect_error": tcp_error,
        "tcp_connect_time_s": tcp_time,
        "attack_path_reachable": attack_path_reachable,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"result_{int(result['timestamp'])}.json"
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
    print(f"\n[experiment] Attack path reachable: {attack_path_reachable}")
    print(f"[experiment] Saved: {json_path}")
    print(f"[experiment] Appended: {csv_path}")


if __name__ == "__main__":
    main()