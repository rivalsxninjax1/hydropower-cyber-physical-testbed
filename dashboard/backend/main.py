"""
Phase 6 backend: polls the PLC over real Modbus TCP, streams state to
the HMI over WebSocket, and persists telemetry + alarm transitions to
the historian (scada/historian/db.py).

Run with (PLC must already be running separately):
    python -m industrial.plc.plc_server        (terminal 1)
    uvicorn dashboard.backend.main:app --reload --port 8000   (terminal 2)
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pymodbus.client import AsyncModbusTcpClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from industrial.plc import register_map as regs  # noqa: E402
from scada.historian import db as historian  # noqa: E402

PLC_HOST = "127.0.0.1"
PLC_PORT = 5020
POLL_SECONDS = 1.0

app = FastAPI(title="Hydropower Plant Dashboard — Phase 6 (Modbus-backed + Historian)")

connected_clients: List[WebSocket] = []
modbus_client: Optional[AsyncModbusTcpClient] = None
latest_state: dict = {"plc_connected": False}
last_alarm_state: Optional[str] = None


class GateCommand(BaseModel):
    target_pct: float = Field(ge=0, le=100)


@app.on_event("startup")
async def startup() -> None:
    global modbus_client
    historian.init_db()
    modbus_client = AsyncModbusTcpClient(PLC_HOST, port=PLC_PORT)
    asyncio.create_task(poll_loop())


async def poll_loop() -> None:
    """Polls the PLC's registers once per second, broadcasts the
    decoded state to every connected HMI client, and persists it to
    the historian. Also detects and records alarm state transitions —
    this poll interval and its measured latency become directly
    relevant in Phase 22's availability/DoS experiment, which measures
    exactly this value under attack."""
    global latest_state, last_alarm_state
    while True:
        start = time.monotonic()
        state = await read_plc_state()
        state["poll_latency_ms"] = round((time.monotonic() - start) * 1000, 1)
        latest_state = state

        historian.record_telemetry(state)

        if state.get("plc_connected") and state.get("alarm_state") != last_alarm_state:
            historian.record_alarm_transition(last_alarm_state, state["alarm_state"])
            last_alarm_state = state["alarm_state"]

        message = json.dumps(state)
        stale_clients = []
        for client in connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                stale_clients.append(client)
        for client in stale_clients:
            connected_clients.remove(client)

        await asyncio.sleep(POLL_SECONDS)


async def read_plc_state() -> dict:
    global modbus_client
    try:
        if not modbus_client.connected:
            await modbus_client.connect()

        result = await modbus_client.read_holding_registers(
            address=0, count=regs.REGISTER_COUNT, slave=1
        )
        if result.isError():
            raise ConnectionError("PLC returned a Modbus error response")

        raw = result.registers
        alarm_code = raw[regs.by_name("ALARM_STATE").zero_based_address]

        return {
            "plc_connected": True,
            "reservoir_level_pct": regs.decode("RESERVOIR_LEVEL_PCT", raw[0]),
            "gate_position_pct": regs.decode("GATE_POSITION_PCT", raw[1]),
            "flow_m3s": regs.decode("FLOW_RATE_M3S", raw[2]),
            "turbine_rpm": regs.decode("TURBINE_RPM", raw[3]),
            "generator_power_mw": regs.decode("GENERATOR_POWER_MW", raw[4]),
            "alarm_state": regs.ALARM_STATE_NAMES.get(alarm_code, "UNKNOWN"),
            "gate_target_pct": regs.decode("GATE_TARGET_COMMAND_PCT", raw[6]),
        }
    except Exception as exc:
        return {
            "plc_connected": False,
            "error": str(exc),
        }


@app.get("/api/state")
async def get_state() -> dict:
    return latest_state


@app.get("/api/history")
async def get_history(limit: int = 100) -> list:
    """Recent telemetry rows from the historian, most recent first."""
    return historian.get_recent_telemetry(limit=limit)


@app.get("/api/alarms")
async def get_alarms(limit: int = 50) -> list:
    """Recent alarm state transitions (not every tick — only changes)."""
    return historian.get_recent_alarm_events(limit=limit)


@app.post("/api/gate")
async def set_gate(command: GateCommand) -> dict:
    """
    Writes the operator's gate target to the PLC's control register
    (40007) over real Modbus TCP. This is the legitimate HMI -> PLC
    control path — the SAME register an unauthorized Modbus client
    could write to directly, bypassing this HMI entirely. That
    equivalence is exactly what Phase 9's Modbus control experiment
    demonstrates.
    """
    global modbus_client
    if not modbus_client.connected:
        await modbus_client.connect()

    target_reg = regs.by_name("GATE_TARGET_COMMAND_PCT")
    raw_value = regs.encode("GATE_TARGET_COMMAND_PCT", command.target_pct)

    result = await modbus_client.write_register(
        address=target_reg.zero_based_address, value=raw_value, slave=1
    )
    if result.isError():
        return {"ok": False, "error": "Modbus write failed"}

    return {"ok": True, "target_pct": command.target_pct}


@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps(latest_state))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))