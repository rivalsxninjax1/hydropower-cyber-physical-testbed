#!/bin/bash
# Captures Modbus TCP traffic to a labeled pcap file, using the
# existing `ids` container's tcpdump. That container already shares
# the PLC's network namespace (network_mode: "service:plc", Phase 11),
# so it sees exactly the traffic addressed to the PLC — no new
# container is needed just for packet capture (Section 54: no
# unnecessary complexity).
#
# Usage:
#   scripts/testing/capture_traffic.sh <label> <duration_seconds>
#
# Examples:
#   scripts/testing/capture_traffic.sh normal 30
#   scripts/testing/capture_traffic.sh modbus_attack 15
#
# Output: data/pcaps/<label>_<NNN>.pcap  (auto-numbered — matches
# Section 36's naming convention: normal_001.pcap, modbus_attack_001.pcap)
#
# Run the actual normal-operation or attack commands in a SECOND
# terminal while this is capturing.

set -e

LABEL="${1:?Usage: capture_traffic.sh <label> <duration_seconds>}"
DURATION="${2:-30}"

mkdir -p data/pcaps

N=1
while [ -f "data/pcaps/${LABEL}_$(printf '%03d' $N).pcap" ]; do
  N=$((N + 1))
done
FILENAME="${LABEL}_$(printf '%03d' $N).pcap"

echo "[capture] Capturing ${DURATION}s of Modbus TCP traffic on the PLC's interface..."
echo "[capture] Output: data/pcaps/${FILENAME}"
echo "[capture] Run your normal-operation or attack commands in another terminal now."
echo ""

docker compose exec ids timeout "$DURATION" tcpdump -i eth0 -w "/app/data/pcaps/${FILENAME}" "tcp port 5020"

echo ""
echo "[capture] Done."
ls -la "data/pcaps/${FILENAME}"