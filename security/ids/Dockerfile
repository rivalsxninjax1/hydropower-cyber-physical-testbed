# Passive Modbus IDS container.
#
# Requires libpcap (for scapy's packet capture) and raw-socket
# capability at runtime — this was tested directly: scapy's sniff()
# fails outright without libpcap installed, confirmed during
# development rather than assumed.
#
# This container does NOT get its own network in docker-compose.yml —
# it uses `network_mode: "service:plc"` to share the PLC's network
# namespace, since a standard Docker bridge network does not let one
# container see another's unicast traffic. See
# docs/architecture/ids.md for why.

FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpcap-dev tcpdump && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY security/ids/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY security/ids/ ./security/ids/
COPY security/__init__.py ./security/__init__.py
COPY scada/ ./scada/

CMD ["python3", "security/ids/modbus_ids.py"]