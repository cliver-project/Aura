"""Project endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import Project, Requirement
from aura.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from aura.services.projects import create_project, list_projects, repo_url
from aura.services.settings_service import SettingsService

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _to_out(session: AsyncSession, project: Project, count: int | None = None) -> ProjectOut:
    runtime = await SettingsService.effective_raw(session)
    if count is None:
        count = (
            await session.execute(select(func.count(Requirement.id)).where(Requirement.project_id == project.id))
        ).scalar_one()
    return ProjectOut(
        **{column.name: getattr(project, column.name) for column in Project.__table__.columns},
        requirement_count=count,
        repo_url=repo_url(runtime, project.repo_owner, project.repo_name),
    )


@router.get("", response_model=list[ProjectOut])
async def index(session: Annotated[AsyncSession, Depends(get_session)]) -> list[ProjectOut]:
    return [await _to_out(session, project, count) for project, count in await list_projects(session)]


@router.post("", response_model=ProjectOut, status_code=201)
async def create(
    payload: ProjectCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectOut:
    try:
        project = await create_project(
            session,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            template=payload.template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface Gitea/Git failures to the UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await _to_out(session, project, 0)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update(
    project_id: str,
    payload: ProjectUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectOut:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = payload.model_dump(exclude_unset=True)
    if "ragflow_dataset_ids" in updates and updates["ragflow_dataset_ids"] is not None:
        project.ragflow_dataset_ids = list(updates["ragflow_dataset_ids"])
    await session.commit()
    await session.refresh(project)
    return await _to_out(session, project)


@router.get("/{project_id}", response_model=ProjectOut)
async def detail(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectOut:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _to_out(session, project)
