"""
Unit tests for security/ids/detection_rules.py.

These test the DECISION logic only — no packet capture, no root
privileges, no scapy. See docs/architecture/ids.md for how the
packet-parsing glue code (modbus_ids.py) was verified separately,
against real captured traffic.

Run with:  pytest security/tests/test_detection_rules.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from security.ids import detection_rules as rules


def test_unauthorized_source_triggers_critical_alert():
    alerts = rules.evaluate_write(
        source_ip="10.0.0.99",
        expected_source_ip="172.24.0.3",
        register=6,
        raw_value=450,  # a perfectly normal value
    )
    rule_names = [r for _, r, _ in alerts]
    assert "unauthorized_source" in rule_names
    severities = {r: s for s, r, _ in alerts}
    assert severities["unauthorized_source"] == "CRITICAL"


def test_authorized_source_with_normal_value_triggers_nothing():
    alerts = rules.evaluate_write(
        source_ip="172.24.0.3",
        expected_source_ip="172.24.0.3",
        register=6,
        raw_value=450,  # 45.0%, well within normal range
    )
    assert alerts == []


def test_authorized_source_with_extreme_value_triggers_warning_only():
    alerts = rules.evaluate_write(
        source_ip="172.24.0.3",
        expected_source_ip="172.24.0.3",
        register=6,
        raw_value=1000,  # 100.0%, outside normal range
    )
    rule_names = [r for _, r, _ in alerts]
    assert rule_names == ["anomalous_command_value"]
    severities = {r: s for s, r, _ in alerts}
    assert severities["anomalous_command_value"] == "WARNING"


def test_unauthorized_source_with_extreme_value_triggers_both():
    alerts = rules.evaluate_write(
        source_ip="10.0.0.99",
        expected_source_ip="172.24.0.3",
        register=6,
        raw_value=1000,
    )
    rule_names = sorted(r for _, r, _ in alerts)
    assert rule_names == ["anomalous_command_value", "unauthorized_source"]


def test_extreme_value_on_non_gate_register_does_not_trigger_value_rule():
    # Register 3 is TURBINE_RPM in this project's map — writing an
    # "extreme" raw value there should NOT trigger the gate-specific
    # anomalous_command_value rule, since that rule only applies to
    # the actual control register.
    alerts = rules.evaluate_write(
        source_ip="172.24.0.3",
        expected_source_ip="172.24.0.3",
        register=3,
        raw_value=65000,
    )
    rule_names = [r for _, r, _ in alerts]
    assert "anomalous_command_value" not in rule_names


def test_no_expected_source_configured_means_no_allowlist_check():
    # When expected_source_ip is None (DNS resolution failed at
    # startup), the source-based rule should not fire — a missing
    # allowlist is a different problem, not a false detection.
    alerts = rules.evaluate_write(
        source_ip="10.0.0.99",
        expected_source_ip=None,
        register=6,
        raw_value=450,
    )
    assert alerts == []


def test_boundary_values_at_edge_of_normal_range_do_not_alert():
    for boundary_pct in [10.0, 90.0]:
        alerts = rules.evaluate_write(
            source_ip="172.24.0.3",
            expected_source_ip="172.24.0.3",
            register=6,
            raw_value=int(boundary_pct * 10),
        )
        assert alerts == [], f"{boundary_pct}% should be within normal range"


def test_just_outside_boundary_does_alert():
    alerts = rules.evaluate_write(
        source_ip="172.24.0.3",
        expected_source_ip="172.24.0.3",
        register=6,
        raw_value=91,  # 9.1%, just under the 10% floor
    )
    rule_names = [r for _, r, _ in alerts]
    assert "anomalous_command_value" in rule_names