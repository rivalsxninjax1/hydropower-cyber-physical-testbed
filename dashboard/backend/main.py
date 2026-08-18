"""
Phase 3 backend: ticks the physics engine and streams its state to the
HMI over a WebSocket. Also serves the frontend and a temporary manual
gate-control endpoint used only to prove the visualization reacts
correctly before Phase 4 adds a real Modbus PLC.

Run with (from repo root):
    uvicorn dashboard.backend.main:app --reload --port 8000
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Make the `simulation` package (in the repo root) importable regardless
# of where uvicorn is launched from.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from simulation.physics_engine.engine import PhysicsEngine  # noqa: E402

app = FastAPI(title="Hydropower Plant Dashboard — Phase 3")

engine = PhysicsEngine()
connected_clients: List[WebSocket] = []

TICK_SECONDS = 1.0


class GateCommand(BaseModel):
    target_pct: float = Field(ge=0, le=100)


@app.on_event("startup")
async def start_simulation_loop() -> None:
    asyncio.create_task(simulation_loop())


async def simulation_loop() -> None:
    """Advances the physics engine and broadcasts state to every
    connected HMI client, once per tick."""
    while True:
        engine.step(dt=TICK_SECONDS)
        message = json.dumps(engine.state())

        stale_clients = []
        for client in connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                stale_clients.append(client)
        for client in stale_clients:
            connected_clients.remove(client)

        await asyncio.sleep(TICK_SECONDS)


@app.get("/api/state")
async def get_state() -> dict:
    """One-shot state read — useful for testing without a WebSocket client."""
    return engine.state()


@app.post("/api/gate")
async def set_gate(command: GateCommand) -> dict:
    """
    TEMPORARY manual control endpoint, Phase 3 only.

    This lets us prove the HMI reacts correctly to a gate command
    before the PLC exists. In Phase 4/5 this control path is replaced
    by a Modbus register write arriving from the PLC service — this
    HTTP endpoint should NOT exist in the final OT-facing system, since
    an unauthenticated HTTP control endpoint would itself be a
    vulnerability. It stays clearly labelled as temporary for exactly
    that reason.
    """
    engine.set_gate_target(command.target_pct)
    return {"ok": True, "target_pct": command.target_pct}


@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps(engine.state()))
        while True:
            # We don't expect client -> server messages, just keep the
            # connection open. Any received text is ignored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))