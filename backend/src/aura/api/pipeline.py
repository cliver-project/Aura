"""Pipeline endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import AgentRun, PipelineRun, StageRun
from aura.schemas import PipelineRunOut, PipelineStart, RejectRequest, StageRunOut
from aura.services.pipeline import engine
from aura.services.pricing import agent_cost, prices_from_runtime
from aura.services.pricing import total_tokens as usage_total_tokens
from aura.services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["pipeline"])


async def _to_out(session: AsyncSession, pipeline: PipelineRun) -> PipelineRunOut:
    stages = list(
        (
            await session.execute(
                select(StageRun)
                .where(StageRun.pipeline_run_id == pipeline.id)
                .order_by(StageRun.started_at.asc().nulls_first())
            )
        )
        .scalars()
        .all()
    )
    stage_ids = [stage.id for stage in stages]
    runs = (
        list(
            (
                await session.execute(select(AgentRun).where(AgentRun.stage_run_id.in_(stage_ids)))
            )
            .scalars()
            .all()
        )
        if stage_ids
        else []
    )
    runs_by_stage: dict[str, list[AgentRun]] = {}
    for run in runs:
        if run.stage_run_id:
            runs_by_stage.setdefault(run.stage_run_id, []).append(run)

    runtime = await SettingsService.effective_raw(session)
    prices = prices_from_runtime(runtime)
    stage_out: list[StageRunOut] = []
    total_cost = 0.0
    total_usage_tokens = 0
    for stage in stages:
        stage_runs = runs_by_stage.get(stage.id, [])
        stage_cost = sum(
            (agent_cost(run.model_usage or {}, run.cost_usd, prices) or 0.0) for run in stage_runs
        )
        stage_tokens = sum(usage_total_tokens(run.model_usage or {}) for run in stage_runs)
        total_cost += stage_cost
        total_usage_tokens += stage_tokens
        stage_out.append(
            StageRunOut.model_validate(stage).model_copy(
                update={"cost_usd": stage_cost, "total_tokens": stage_tokens}
            )
        )

    data = {column.name: getattr(pipeline, column.name) for column in PipelineRun.__table__.columns}
    return PipelineRunOut(
        **data,
        total_cost_usd=total_cost,
        total_tokens=total_usage_tokens,
        stages=stage_out,
    )


@router.post("/requirements/{requirement_id}/pipeline", response_model=PipelineRunOut, status_code=202)
async def start_pipeline(
    requirement_id: str,
    payload: PipelineStart,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PipelineRunOut:
    try:
        pipeline = await engine.start(session, requirement_id, start_stage=payload.start_stage, auto=payload.auto)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _to_out(session, pipeline)


@router.get("/requirements/{requirement_id}/pipeline-runs", response_model=list[PipelineRunOut])
async def list_pipeline_runs(
    requirement_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PipelineRunOut]:
    pipelines = (
        (
            await session.execute(
                select(PipelineRun)
                .where(PipelineRun.requirement_id == requirement_id)
                .order_by(PipelineRun.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _to_out(session, pipeline) for pipeline in pipelines]


@router.get("/pipeline-runs/{pipeline_id}", response_model=PipelineRunOut)
async def get_pipeline(
    pipeline_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PipelineRunOut:
    pipeline = await session.get(PipelineRun, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return await _to_out(session, pipeline)


@router.post("/pipeline-runs/{pipeline_id}/cancel", response_model=PipelineRunOut)
async def cancel_pipeline(
    pipeline_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PipelineRunOut:
    try:
        await engine.cancel(session, pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pipeline = await session.get(PipelineRun, pipeline_id)
    assert pipeline is not None
    return await _to_out(session, pipeline)


@router.post("/pipeline-runs/{pipeline_id}/merge", response_model=PipelineRunOut)
async def merge_pipeline(
    pipeline_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PipelineRunOut:
    try:
        pipeline = await engine.merge(session, pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await _to_out(session, pipeline)


@router.post("/pipeline-runs/{pipeline_id}/reject", response_model=PipelineRunOut)
async def reject_pipeline(
    pipeline_id: str,
    payload: RejectRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PipelineRunOut:
    try:
        pipeline = await engine.reject(session, pipeline_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _to_out(session, pipeline)
