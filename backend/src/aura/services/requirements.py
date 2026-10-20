"""Requirement creation and version history."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.models import Project, Requirement, RequirementVersion
from aura.services.git_workspace import GitWorkspace
from aura.services.projects import repo_url
from aura.services.settings_service import SettingsService

KEY_PATTERN = re.compile(r"^REQ-(\d+)$")


def allocate_key(existing_keys: list[str]) -> str:
    highest = 0
    for key in existing_keys:
        match = KEY_PATTERN.match(key)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"REQ-{highest + 1:03d}"


def render_requirement(
    key: str,
    title: str,
    idea: str,
    version: int = 1,
    status: str = "draft",
) -> str:
    created = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"""---
key: {key}
title: {title}
version: {version}
status: {status}
created_at: {created}
---

# {key}: {title}

## Initial idea

{idea.strip()}

## History

- v{version} ({created}): Initial requirement captured.
"""


async def create_requirement(
    session: AsyncSession,
    project_id: str,
    title: str,
    idea: str,
) -> Requirement:
    project = await session.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    runtime = await SettingsService.effective_raw(session)
    owner = project.repo_owner
    clone_url = f"{str(runtime['gitea_url']).rstrip('/')}/{owner}/{project.repo_name}.git"
    token = str(runtime.get("gitea_token") or "")
    username = str(runtime.get("gitea_user") or owner)

    existing_keys = (
        (await session.execute(select(Requirement.key).where(Requirement.project_id == project_id))).scalars().all()
    )
    key = allocate_key(list(existing_keys))
    content = render_requirement(key, title, idea)

    workspace = GitWorkspace()
    run_id = f"req-{uuid.uuid4().hex[:12]}"
    path = await workspace.prepare(clone_url, project.default_branch, run_id, token=token, username=username)
    try:
        relative = f"docs/requirements/{key}.md"
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        sha = await workspace.commit_all(path, f"docs({key}): add requirement")
        await workspace.push(path, project.default_branch, token=token, username=username)
    finally:
        workspace.cleanup(path)

    requirement = Requirement(
        project_id=project.id,
        key=key,
        title=title,
        status="draft",
        initial_idea=idea,
        current_version=1,
    )
    session.add(requirement)
    await session.flush()
    session.add(
        RequirementVersion(
            requirement_id=requirement.id,
            version=1,
            content_md=content,
            source="human",
            author="human",
            git_commit=sha,
        )
    )
    await session.commit()
    await session.refresh(requirement)
    return requirement


async def add_requirement_version(
    session: AsyncSession,
    requirement: Requirement,
    content: str,
    source: str,
    author: str,
    git_commit: str | None,
) -> RequirementVersion:
    version = requirement.current_version + 1
    requirement.current_version = version
    record = RequirementVersion(
        requirement_id=requirement.id,
        version=version,
        content_md=content,
        source=source,
        author=author,
        git_commit=git_commit,
    )
    session.add(record)
    await session.commit()
    return record


async def list_requirements(session: AsyncSession, project_id: str) -> list[Requirement]:
    return list(
        (
            await session.execute(
                select(Requirement).where(Requirement.project_id == project_id).order_by(Requirement.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


def requirement_repo_url(settings: dict, project: Project) -> str:
    return repo_url(settings, project.repo_owner, project.repo_name)
