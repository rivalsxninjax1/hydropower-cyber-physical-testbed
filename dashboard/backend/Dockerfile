# Dashboard/HMI backend container.
#
# Build context is the REPO ROOT because this service needs
# industrial/plc/register_map.py (to decode Modbus registers),
# scada/historian (to persist telemetry), and dashboard/ itself.
# It does NOT need simulation/ - the dashboard never touches physics
# directly, only Modbus registers via the PLC.

FROM python:3.11-slim

WORKDIR /app

COPY dashboard/backend/requirements.txt ./dashboard/backend/requirements.txt
RUN pip install --no-cache-dir -r dashboard/backend/requirements.txt

COPY industrial/plc/register_map.py ./industrial/plc/register_map.py
COPY industrial/plc/__init__.py ./industrial/plc/__init__.py
COPY industrial/__init__.py ./industrial/__init__.py
COPY scada/ ./scada/
COPY dashboard/ ./dashboard/

EXPOSE 8000

CMD ["uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
