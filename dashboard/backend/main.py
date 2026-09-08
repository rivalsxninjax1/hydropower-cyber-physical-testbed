"""
Phase 5 backend: polls the PLC over real Modbus TCP — not the physics
engine directly — and streams the result to the HMI over WebSocket.

This is the point the dashboard stops being "a webpage showing a
Python object" and becomes an actual SCADA HMI polling a PLC: the same
architectural boundary a real plant has, and the same boundary the
attacker will exploit starting in Phase 8/9 by talking to the PLC
directly and bypassing this HMI entirely.

Run with (PLC must already be running separately):
    python -m industrial.plc.plc_server        (terminal 1)
    uvicorn dashboard.backend.main:app --reload --port 8000   (terminal 2)
"""

import asyncio
import json
import os
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
from security.correlation import build_timeline as correlation  # noqa: E402
import glob  # noqa: E402

# Configurable via environment so this works both:
#   - run directly on the host (PLC_HOST defaults to 127.0.0.1)
#   - run as a Docker container reaching the PLC by its service name
#     (docker-compose sets PLC_HOST=plc — see docker-compose.yml)
PLC_HOST = os.environ.get("PLC_HOST", "127.0.0.1")
PLC_PORT = int(os.environ.get("PLC_PORT", "5020"))
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


@app.get("/api/ids-alerts")
async def get_ids_alerts(limit: int = 50) -> list:
    """Phase 17: recent IDS alerts (Phase 11) — this data has existed
    in the historian since Phase 11 but never had its own API/UI until
    the Security Monitoring page."""
    return historian.get_recent_ids_alerts(limit=limit)


@app.get("/api/plc-events")
async def get_plc_events(limit: int = 50) -> list:
    """Phase 17: recent PLC control-register command events (Phase 10)
    — same situation as ids-alerts, real data with no prior UI."""
    return historian.get_recent_plc_events(limit=limit)


@app.get("/api/experiments/summary")
async def get_experiments_summary() -> dict:
    """Phase 17: the consolidated evaluation summary generated by
    scripts/testing/generate_evaluation_summary.py, if it has been run.
    Returns {"available": False} rather than an error if it hasn't."""
    summary_path = REPO_ROOT / "data" / "experiments" / "evaluation_summary.json"
    if not summary_path.exists():
        return {
            "available": False,
            "reason": (
                "No evaluation summary found. Run "
                "scripts/testing/generate_evaluation_summary.py first."
            ),
        }
    with open(summary_path) as f:
        data = json.load(f)
    return {"available": True, "summary": data}


@app.get("/api/experiments/{experiment_id}/runs")
async def get_experiment_runs(experiment_id: str, limit: int = 20) -> dict:
    """Phase 17: raw per-run results for one experiment folder, most
    recent first, read directly from its results.csv."""
    experiment_dir = REPO_ROOT / "data" / "experiments" / experiment_id
    csv_path = experiment_dir / "results.csv"
    if not csv_path.exists():
        return {
            "available": False,
            "reason": f"No results.csv found for experiment '{experiment_id}'.",
            "runs": [],
        }

    import csv as csv_module
    with open(csv_path, newline="") as f:
        rows = list(csv_module.DictReader(f))

    rows = rows[-limit:][::-1]  # most recent first
    return {"available": True, "reason": None, "runs": rows}


@app.get("/api/attack-timeline")
async def get_attack_timeline() -> dict:
    """
    Phase 13: the structured, stage-by-stage attack timeline (Section
    16's timestamp/source/target/action/protocol/result fields),
    built from Experiment 01's most recent result plus the historian.

    Returns {"available": False, "reason": ...} rather than an error
    if no experiment has been run yet, so the frontend can show a
    clear "run an experiment first" message instead of a broken page.
    """
    try:
        experiment_path = correlation.find_latest_experiment_result()
    except FileNotFoundError as exc:
        return {"available": False, "reason": str(exc), "events": []}

    events = correlation.build_timeline(experiment_path)
    return {"available": True, "reason": None, "events": events}


@app.get("/api/attack-graph-state")
async def get_attack_graph_state() -> dict:
    """
    Phase 13: whether the most recently recorded attack attempt
    actually reached the PLC, for highlighting the attacker->plc edge
    on the network graph. Checks both experiment folders (01's Modbus
    write outcome and 02's network-reachability outcome) and uses
    whichever result is more recent, since either can be the most
    up-to-date signal depending on what was last run.
    """
    candidates = []

    exp01_files = sorted(glob.glob(str(
        REPO_ROOT / "data" / "experiments" / "01-modbus-control" / "result_*.json"
    )))
    if exp01_files:
        with open(exp01_files[-1]) as f:
            data = json.load(f)
        candidates.append({
            "timestamp": data["timestamp"],
            "path_reachable": bool(data.get("write_accepted")),
            "source_experiment": "01-modbus-control",
            "detail": f"Modbus write {'accepted' if data.get('write_accepted') else 'rejected'} by PLC",
        })

    exp02_files = sorted(glob.glob(str(
        REPO_ROOT / "data" / "experiments" / "02-network-segmentation" / "result_*.json"
    )))
    if exp02_files:
        with open(exp02_files[-1]) as f:
            data = json.load(f)
        candidates.append({
            "timestamp": data["timestamp"],
            "path_reachable": bool(data.get("attack_path_reachable")),
            "source_experiment": "02-network-segmentation",
            "detail": (
                "DNS + TCP reachable" if data.get("attack_path_reachable")
                else f"Blocked: {data.get('dns_resolution_result') or data.get('tcp_connect_error')}"
            ),
        })

    if not candidates:
        return {
            "available": False,
            "path_reachable": None,
            "detail": "No experiments have been run yet.",
        }

    latest = max(candidates, key=lambda c: c["timestamp"])
    return {"available": True, **latest}


@app.post("/api/gate")
async def set_gate(command: GateCommand) -> dict:
    """
    Writes the operator's gate target to the PLC's control register
    (40007) over real Modbus TCP. This is now the legitimate HMI -> PLC
    control path — the SAME register an unauthorized Modbus client
    could write to directly, bypassing this HMI entirely. That
    equivalence — legitimate operator command and unauthorized command
    are indistinguishable at the register level — is exactly what
    Phase 9's Modbus control experiment demonstrates.
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
async def serve_dashboard() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/plant")
async def serve_plant() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "plant.html"))


@app.get("/security")
async def serve_security() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "security.html"))


@app.get("/experiments")
async def serve_experiments() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "experiments.html"))


@app.get("/attack-path")
async def serve_attack_path() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "attack-path.html"))