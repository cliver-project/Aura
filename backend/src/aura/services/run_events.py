"""Persist agent events and broadcast them to live subscribers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from aura.db import SessionLocal
from aura.models import AgentEvent, AgentRun
from aura.services.event_bus import event_bus

# Claude Code emits fine-grained progress events that are useful on a terminal
# but would produce thousands of database rows per run. Persist only events
# that carry conversational or tool-level meaning.
NOISY_SYSTEM_SUBTYPES = {
    "thinking_tokens",
    "hook_started",
    "hook_response",
    "hook_progress",
    "status",
    "token_usage",
    "rate_limit_event",
}
NOISY_TYPES = {"ping", "stream_event"}


def is_noise(raw: dict[str, Any]) -> bool:
    event_type = raw.get("type")
    if event_type in NOISY_TYPES:
        return True
    return event_type == "system" and raw.get("subtype") in NOISY_SYSTEM_SUBTYPES


async def next_seq(run_id: str) -> int:
    async with SessionLocal() as session:
        current = (
            await session.execute(select(func.max(AgentEvent.seq)).where(AgentEvent.agent_run_id == run_id))
        ).scalar_one()
    return int(current or 0) + 1


class RunEventRecorder:
    """One recorder per agent run; seq is monotonic and persisted."""

    def __init__(self, run_id: str, start_seq: int = 0) -> None:
        self.run_id = run_id
        self._seq = start_seq

    @classmethod
    async def create(cls, run_id: str) -> RunEventRecorder:
        async with SessionLocal() as session:
            current = (
                await session.execute(select(func.max(AgentEvent.seq)).where(AgentEvent.agent_run_id == run_id))
            ).scalar_one()
        return cls(run_id, int(current or 0))

    async def record(self, raw: dict[str, Any]) -> None:
        if is_noise(raw):
            return
        self._seq += 1
        event_type = str(raw.get("type") or "event")
        async with SessionLocal() as session:
            session.add(
                AgentEvent(
                    agent_run_id=self.run_id,
                    seq=self._seq,
                    type=event_type,
                    data=raw,
                )
            )
            await session.commit()
        await event_bus.publish(self.run_id, {"seq": self._seq, "type": event_type, "data": raw})


async def mark_run_started(run_id: str, pid: int | None = None) -> None:
    from datetime import UTC, datetime

    async with SessionLocal() as session:
        run = await session.get(AgentRun, run_id)
        if run is None:
            return
        run.status = "running"
        run.pid = pid
        run.started_at = datetime.now(UTC)
        await session.commit()
