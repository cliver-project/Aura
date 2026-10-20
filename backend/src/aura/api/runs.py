"""Agent run inspection and cancellation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import AgentEvent, AgentRun
from aura.schemas import AgentEventOut, AgentRunOut
from aura.services.claude_runner import ClaudeRunner
from aura.services.pricing import agent_cost, prices_from_runtime, total_tokens
from aura.services.settings_service import SettingsService

router = APIRouter(prefix="/api/agent-runs", tags=["runs"])


def _to_out(run: AgentRun, prices: dict[str, dict[str, float]]) -> AgentRunOut:
    return AgentRunOut.model_validate(run).model_copy(
        update={
            "cost_usd": agent_cost(run.model_usage or {}, run.cost_usd, prices),
            "total_tokens": total_tokens(run.model_usage or {}),
        }
    )


@router.get("", response_model=list[AgentRunOut])
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    project_id: str | None = None,
    requirement_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AgentRunOut]:
    query = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if project_id:
        query = query.where(AgentRun.project_id == project_id)
    if requirement_id:
        query = query.where(AgentRun.requirement_id == requirement_id)
    runs = list((await session.execute(query)).scalars().all())
    runtime = await SettingsService.effective_raw(session)
    prices = prices_from_runtime(runtime)
    return [_to_out(run, prices) for run in runs]


@router.get("/{run_id}", response_model=AgentRunOut)
async def detail(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRunOut:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    runtime = await SettingsService.effective_raw(session)
    return _to_out(run, prices_from_runtime(runtime))


@router.get("/{run_id}/events", response_model=list[AgentEventOut])
async def events(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    after_seq: int = 0,
) -> list[AgentEvent]:
    return list(
        (
            await session.execute(
                select(AgentEvent)
                .where(AgentEvent.agent_run_id == run_id, AgentEvent.seq > after_seq)
                .order_by(AgentEvent.seq.asc())
            )
        )
        .scalars()
        .all()
    )


@router.post("/{run_id}/cancel", response_model=AgentRunOut)
async def cancel(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRunOut:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    ClaudeRunner.cancel(run_id)
    runtime = await SettingsService.effective_raw(session)
    return _to_out(run, prices_from_runtime(runtime))
