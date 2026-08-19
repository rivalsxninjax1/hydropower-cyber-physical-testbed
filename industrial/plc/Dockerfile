# PLC service container.
#
# Build context is the REPO ROOT (not industrial/plc/) because this
# service needs both simulation/ (the physics engine it wraps) and
# industrial/ (its own code) — see docker-compose.yml's build.context.

FROM python:3.11-slim

WORKDIR /app

COPY industrial/plc/requirements.txt ./industrial/plc/requirements.txt
RUN pip install --no-cache-dir -r industrial/plc/requirements.txt

COPY simulation/ ./simulation/
COPY industrial/ ./industrial/

EXPOSE 5020

CMD ["python", "-m", "industrial.plc.plc_server"]