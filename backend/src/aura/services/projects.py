"""Project creation and repository seeding."""

from __future__ import annotations

import contextlib
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.models import Project, Requirement
from aura.services.git_workspace import GitError, GitWorkspace
from aura.services.gitea import GiteaClient, GiteaError
from aura.services.repo_seed import seed_files, write_files
from aura.services.settings_service import SettingsService

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:60].strip("-") or f"project-{uuid.uuid4().hex[:6]}"


def repo_url(settings: dict, owner: str, repo: str) -> str:
    return f"{str(settings['gitea_url']).rstrip('/')}/{owner}/{repo}"


def gitea_client(settings: dict) -> GiteaClient:
    return GiteaClient(
        base_url=str(settings["gitea_url"]),
        token=str(settings.get("gitea_token") or ""),
        username=str(settings.get("gitea_user") or ""),
        password=str(settings.get("gitea_password") or ""),
    )


async def create_project(
    session: AsyncSession,
    name: str,
    slug: str,
    description: str,
    template: str = "python-web",
) -> Project:
    """Create a Gitea repository, seed it, then persist the project row."""
    runtime = await SettingsService.effective_raw(session)
    owner = str(runtime.get("gitea_owner") or runtime.get("gitea_user") or "aura")
    slug = slug.strip() or slugify(name)
    if not SLUG_PATTERN.match(slug):
        raise ValueError("Slug must use lowercase letters, digits, and hyphens.")

    existing = await session.execute(select(Project).where(Project.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Project slug already exists: {slug}")

    client = gitea_client(runtime)
    # Local single-user instance: repositories are public by default.
    repo = await client.create_repo(slug, description=description, private=False, auto_init=True)

    workspace = GitWorkspace()
    seed_run_id = f"seed-{uuid.uuid4().hex[:12]}"
    clone_url = f"{str(runtime['gitea_url']).rstrip('/')}/{owner}/{slug}.git"
    workspace_path = None
    try:
        workspace_path = await workspace.prepare(
            clone_url,
            "main",
            seed_run_id,
            token=str(runtime.get("gitea_token") or ""),
            username=str(runtime.get("gitea_user") or owner),
        )
        write_files(workspace_path, seed_files(name, slug, description, template))
        await workspace.commit_all(workspace_path, "chore: initialize project with Aura")
        await workspace.push(
            workspace_path,
            "main",
            token=str(runtime.get("gitea_token") or ""),
            username=str(runtime.get("gitea_user") or owner),
        )
        await client.set_default_branch(owner, slug, "main")
    except (GitError, OSError) as exc:
        with contextlib.suppress(GiteaError):
            await client.delete_repo(owner, slug)
        raise RuntimeError(f"Repository was created but seeding failed: {exc}") from exc
    finally:
        if workspace_path is not None:
            workspace.cleanup(workspace_path)

    project = Project(
        name=name,
        slug=slug,
        description=description,
        repo_owner=owner,
        repo_name=str(repo.get("name") or slug),
        default_branch="main",
        template=template,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[tuple[Project, int]]:
    counts = (
        await session.execute(
            select(Requirement.project_id, func.count(Requirement.id)).group_by(Requirement.project_id)
        )
    ).all()
    count_map = {project_id: count for project_id, count in counts}
    projects = (await session.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
    return [(project, count_map.get(project.id, 0)) for project in projects]
