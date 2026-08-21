"""
Pure detection-rule functions for the Modbus IDS.

Deliberately kept separate from modbus_ids.py's packet-capture code so
these rules can be unit tested directly with synthetic inputs — no
root privileges, no real network, no scapy required to test the logic
that actually decides what counts as suspicious.

Two independent detection categories, matching different real-world
attacker capabilities:

  1. unauthorized_source — a signature/identity-based rule. Catches an
     attacker with network access but no legitimate reason to be
     writing to the PLC at all.

  2. anomalous_command_value — a behavioral/process-based rule. Catches
     an extreme command even if it came from the "right" source (e.g.
     a compromised HMI, or a legitimate operator mistake) — this is
     the category real ICS security calls "process-aware" detection,
     distinct from network-signature detection, and it's what a purely
     source-IP-based check would miss entirely.
"""

from typing import Optional

GATE_TARGET_REGISTER = 6
GATE_NORMAL_MIN_PCT = 10.0
GATE_NORMAL_MAX_PCT = 90.0
FIXED_POINT_SCALE = 10.0


def evaluate_write(
    source_ip: str,
    expected_source_ip: Optional[str],
    register: int,
    raw_value: int,
) -> list:
    """Returns a list of (severity, rule_name, description) tuples for
    one observed Modbus register write. Empty list = no alert."""
    alerts = []

    if expected_source_ip is not None and source_ip != expected_source_ip:
        alerts.append((
            "CRITICAL",
            "unauthorized_source",
            f"Modbus write to register {register} from unexpected source "
            f"{source_ip} (expected {expected_source_ip})",
        ))

    if register == GATE_TARGET_REGISTER:
        decoded_pct = raw_value / FIXED_POINT_SCALE
        if not (GATE_NORMAL_MIN_PCT <= decoded_pct <= GATE_NORMAL_MAX_PCT):
            alerts.append((
                "WARNING",
                "anomalous_command_value",
                f"Gate target command {decoded_pct:.1f}% is outside the "
                f"normal operating range ({GATE_NORMAL_MIN_PCT}-{GATE_NORMAL_MAX_PCT}%)",
            ))

    return alerts