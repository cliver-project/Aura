"""Agent profile CRUD."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import AgentProfile
from aura.schemas import AgentCreate, AgentOut, AgentUpdate
from aura.services.claude_env import mask_env, restore_masked_env

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _to_out(agent: AgentProfile) -> AgentOut:
    return AgentOut(
        **{column.name: getattr(agent, column.name) for column in AgentProfile.__table__.columns},
    ).model_copy(update={"env": mask_env(agent.env or {})})


@router.get("", response_model=list[AgentOut])
async def list_agents(session: Annotated[AsyncSession, Depends(get_session)]) -> list[AgentOut]:
    agents = (
        await session.execute(select(AgentProfile).order_by(AgentProfile.is_builtin.desc(), AgentProfile.name.asc()))
    ).scalars()
    return [_to_out(agent) for agent in agents]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    payload: AgentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentOut:
    existing = await session.execute(select(AgentProfile).where(AgentProfile.role_key == payload.role_key))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Role key already exists")
    agent = AgentProfile(**payload.model_dump(), is_builtin=False)
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentOut:
    agent = await session.get(AgentProfile, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    updates = payload.model_dump(exclude_unset=True)
    if "env" in updates:
        updates["env"] = restore_masked_env(agent.env or {}, updates["env"] or {})
    for key, value in updates.items():
        setattr(agent, key, value)
    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    agent = await session.get(AgentProfile, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.is_builtin:
        raise HTTPException(status_code=409, detail="Built-in agents cannot be deleted")
    await session.delete(agent)
    await session.commit()
