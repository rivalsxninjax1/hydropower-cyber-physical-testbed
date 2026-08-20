# Attacker workstation container.
#
# This container does NOT run any attack automatically — per Section
# 15 of the project spec, the person operating this testbed runs these
# tools manually, the same way a real security tester would. The
# container just stays alive (tail -f /dev/null) so it can be entered
# with `docker compose exec attacker <command>` or
# `docker compose exec attacker bash`.
#
# Deliberately does NOT copy or install this project's own
# industrial/plc/register_map.py — the attacker only gets generic,
# real-world tools (nmap, a Modbus client library), not inside
# knowledge of our register map. Figuring that out is the actual point
# of modbus_recon.py and modbus_probe_writable.py.

FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap iputils-ping && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY attacker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY attacker/tools/ ./tools/

CMD ["tail", "-f", "/dev/null"]