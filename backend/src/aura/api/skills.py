"""Skill library API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.schemas import SkillContent, SkillCreate, SkillOut
from aura.services.skills_service import SkillError, SkillReadOnlyError, SkillsService

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _out(info) -> SkillOut:
    return SkillOut(
        name=info.name,
        description=info.description,
        path=info.path,
        source=info.source,
        enabled=info.enabled,
        read_only=info.read_only,
    )


@router.get("", response_model=list[SkillOut])
async def list_skills(session: Annotated[AsyncSession, Depends(get_session)]) -> list[SkillOut]:
    return [_out(info) for info in await SkillsService().list(session)]


@router.post("/refresh", response_model=list[SkillOut])
async def refresh(session: Annotated[AsyncSession, Depends(get_session)]) -> list[SkillOut]:
    return [_out(info) for info in await SkillsService().refresh(session)]


@router.get("/{name}", response_model=SkillContent)
async def read_skill(name: str) -> SkillContent:
    try:
        return SkillContent(content=SkillsService().read(name))
    except SkillError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=SkillOut, status_code=201)
async def create_skill(payload: SkillCreate) -> SkillOut:
    try:
        return _out(SkillsService().create(payload.name, payload.content))
    except SkillError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{name}", response_model=SkillOut)
async def update_skill(name: str, payload: SkillContent) -> SkillOut:
    try:
        return _out(SkillsService().update(name, payload.content))
    except SkillReadOnlyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SkillError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
