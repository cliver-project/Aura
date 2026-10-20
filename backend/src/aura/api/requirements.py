"""Requirement endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import Artifact, Requirement, RequirementVersion
from aura.schemas import ArtifactOut, RequirementCreate, RequirementOut, RequirementVersionOut
from aura.services.requirements import create_requirement, list_requirements

project_router = APIRouter(prefix="/api/projects", tags=["requirements"])
router = APIRouter(prefix="/api/requirements", tags=["requirements"])


@project_router.get("/{project_id}/requirements", response_model=list[RequirementOut])
async def list_for_project(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Requirement]:
    return await list_requirements(session, project_id)


@project_router.post("/{project_id}/requirements", response_model=RequirementOut, status_code=201)
async def create_for_project(
    project_id: str,
    payload: RequirementCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Requirement:
    try:
        return await create_requirement(session, project_id, payload.title, payload.idea)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{requirement_id}", response_model=RequirementOut)
async def detail(
    requirement_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Requirement:
    requirement = await session.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@router.get("/{requirement_id}/artifacts", response_model=list[ArtifactOut])
async def artifacts(
    requirement_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Artifact]:
    return list(
        (
            await session.execute(
                select(Artifact).where(Artifact.requirement_id == requirement_id).order_by(Artifact.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.get("/{requirement_id}/versions", response_model=list[RequirementVersionOut])
async def versions(
    requirement_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RequirementVersion]:
    return list(
        (
            await session.execute(
                select(RequirementVersion)
                .where(RequirementVersion.requirement_id == requirement_id)
                .order_by(RequirementVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
