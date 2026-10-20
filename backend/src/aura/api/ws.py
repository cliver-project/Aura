"""WebSocket endpoint for live agent events."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from aura.db import SessionLocal
from aura.models import AgentEvent, AgentRun
from aura.services.event_bus import event_bus

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/agent-runs/{run_id}")
async def agent_run_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()

    async with SessionLocal() as session:
        run = await session.get(AgentRun, run_id)
        if run is None:
            await websocket.send_json({"type": "error", "message": "Agent run not found"})
            await websocket.close()
            return
        persisted = list(
            (
                await session.execute(
                    select(AgentEvent).where(AgentEvent.agent_run_id == run_id).order_by(AgentEvent.seq.asc())
                )
            )
            .scalars()
            .all()
        )
        status = run.status

    for event in persisted:
        await websocket.send_json({"seq": event.seq, "type": event.type, "data": event.data})

    if status != "running":
        await websocket.close()
        return

    async with event_bus.subscribe(run_id) as queue:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    await websocket.send_json(event)
                except TimeoutError:
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            return
