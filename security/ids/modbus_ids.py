"""
Passive Modbus TCP write monitor.

Sniffs on this container's OWN network interface for TCP traffic to
the PLC's Modbus port, parses the Modbus Application Protocol (MBAP)
header + PDU directly from raw packets — NOT via pymodbus. This is
intentionally an independent, out-of-band observer: the same category
of tool a real passive ICS IDS is, and using a different parsing path
than the PLC itself means a bug or compromise in pymodbus doesn't
blind this monitor too.

Deployment note: this only works because docker-compose.yml runs this
container with `network_mode: "service:plc"` — it shares the PLC
container's network namespace, so packets addressed to the PLC are
visible on this container's own interface. A standard Docker bridge
network does NOT let one container promiscuously see another
container's unicast traffic — this was tested directly before writing
this file, not assumed.

Run with:
    python3 modbus_ids.py

Configurable via environment:
    IDS_INTERFACE          network interface to sniff (default: eth0)
    IDS_MODBUS_PORT        Modbus TCP port to watch (default: 5020)
    IDS_EXPECTED_SOURCE_IP override for the legitimate source IP
                            (default: resolved via DNS for "dashboard")
"""

import os
import socket
import struct
import sys
import time
from pathlib import Path

from scapy.all import sniff, TCP, IP

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scada.historian import db as historian  # noqa: E402
from security.ids import detection_rules  # noqa: E402

DEFAULT_INTERFACE = os.environ.get("IDS_INTERFACE", "eth0")
DEFAULT_PORT = int(os.environ.get("IDS_MODBUS_PORT", "5020"))

WRITE_SINGLE_REGISTER = 6
WRITE_MULTIPLE_REGISTERS = 16

# De-duplication window: on loopback interfaces specifically, scapy can
# observe the same logical packet twice (once leaving the sender's
# socket, once arriving at the receiver's) — confirmed during testing.
# This also guards against legitimate TCP retransmissions producing
# duplicate alerts for what is really one write. Keyed on
# (source_ip, register, value); any repeat within this window is
# suppressed.
DEDUP_WINDOW_SECONDS = 1.0
_recent_writes: dict = {}


def resolve_expected_source_ip():
    """The dashboard is the only legitimate writer to the PLC. Its
    address is resolved via Docker's embedded DNS (the service name
    'dashboard' on the same compose network) rather than hardcoded, so
    it stays correct if the network layout changes."""
    override = os.environ.get("IDS_EXPECTED_SOURCE_IP")
    if override:
        return override
    try:
        return socket.gethostbyname("dashboard")
    except socket.gaierror:
        print(
            "[ids] WARNING: could not resolve 'dashboard' - falling back "
            "to no source-IP allowlist (every write will be flagged as "
            "unauthorized_source). Set IDS_EXPECTED_SOURCE_IP to override."
        )
        return None


def parse_mbap_and_pdu(payload: bytes):
    """Parses a raw Modbus TCP frame. Returns (function_code, register,
    value) for write function codes, or None if this isn't a write we
    care about (reads, other function codes, malformed frames)."""
    if len(payload) < 8:
        return None

    # MBAP header: transaction_id(2) protocol_id(2) length(2) unit_id(1)
    _transaction_id, protocol_id, _length, _unit_id = struct.unpack(
        ">HHHB", payload[0:7]
    )
    if protocol_id != 0:
        return None  # not a Modbus frame

    function_code = payload[7]
    pdu_data = payload[8:]

    if function_code == WRITE_SINGLE_REGISTER and len(pdu_data) >= 4:
        register, value = struct.unpack(">HH", pdu_data[0:4])
        return (function_code, register, value)

    if function_code == WRITE_MULTIPLE_REGISTERS and len(pdu_data) >= 7:
        register, _quantity, _byte_count = struct.unpack(">HHB", pdu_data[0:5])
        value = struct.unpack(">H", pdu_data[5:7])[0]  # first written value only
        return (function_code, register, value)

    return None


def main() -> None:
    historian.init_db()
    expected_source_ip = resolve_expected_source_ip()
    print(f"[ids] Expected legitimate source IP: {expected_source_ip}")
    print(f"[ids] Monitoring interface={DEFAULT_INTERFACE} port={DEFAULT_PORT}")

    def handle_packet(pkt) -> None:
        if not (pkt.haslayer(TCP) and pkt.haslayer(IP)):
            return
        if pkt[TCP].dport != DEFAULT_PORT:
            return
        payload = bytes(pkt[TCP].payload)
        if not payload:
            return

        parsed = parse_mbap_and_pdu(payload)
        if parsed is None:
            return
        _function_code, register, value = parsed

        source_ip = pkt[IP].src

        dedup_key = (source_ip, register, value)
        now = time.time()
        last_seen = _recent_writes.get(dedup_key)
        if last_seen is not None and (now - last_seen) < DEDUP_WINDOW_SECONDS:
            return
        _recent_writes[dedup_key] = now

        alerts = detection_rules.evaluate_write(
            source_ip, expected_source_ip, register, value
        )
        for severity, rule, description in alerts:
            print(f"[ids] ALERT [{severity}] {rule}: {description}")
            historian.record_ids_alert(source_ip, severity, rule, description)

    sniff(
        iface=DEFAULT_INTERFACE,
        filter=f"tcp port {DEFAULT_PORT}",
        prn=handle_packet,
        store=False,
    )


if __name__ == "__main__":
    main()