"""Service health checks."""

from __future__ import annotations

import shutil
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import get_settings
from aura.db import get_session
from aura.schemas import HealthOut, ServiceStatus
from aura.services.settings_service import SettingsService

router = APIRouter(tags=["health"])


async def _check_database(session: AsyncSession) -> ServiceStatus:
    try:
        await session.execute(text("SELECT 1"))
        return ServiceStatus(name="database", status="ok", detail="PostgreSQL reachable")
    except Exception as exc:  # noqa: BLE001 - health checks report any failure
        return ServiceStatus(name="database", status="error", detail=str(exc)[:300])


async def _check_gitea() -> ServiceStatus:
    settings = get_settings()
    url = f"{settings.gitea_web_url}/api/v1/version"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            version = response.json().get("version", "unknown")
        return ServiceStatus(name="gitea", status="ok", detail=f"Gitea {version}", url=settings.gitea_web_url)
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(
            name="gitea",
            status="error",
            detail=str(exc)[:300],
            url=settings.gitea_web_url,
        )


def _check_claude() -> ServiceStatus:
    settings = get_settings()
    path = shutil.which(settings.claude_bin)
    if path:
        return ServiceStatus(name="claude", status="ok", detail=path)
    return ServiceStatus(
        name="claude",
        status="error",
        detail=f"'{settings.claude_bin}' not found on PATH",
    )


async def _check_ragflow(session: AsyncSession) -> ServiceStatus:
    runtime = await SettingsService.effective_raw(session)
    settings = get_settings()
    ragflow_url = str(runtime.get("ragflow_url") or "")
    if not ragflow_url:
        return ServiceStatus(name="ragflow", status="off", detail="Not configured", url="")
    url = f"{ragflow_url.rstrip('/')}/api/v1/system/healthz"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return ServiceStatus(
            name="ragflow", status="ok", detail="RAGFlow reachable", url=settings.ragflow_web_url or ragflow_url
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(name="ragflow", status="error", detail=str(exc)[:300], url=ragflow_url)


@router.get("/api/health", response_model=HealthOut)
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthOut:
    services = [
        await _check_database(session),
        await _check_gitea(),
        _check_claude(),
        await _check_ragflow(session),
    ]
    overall = "ok" if all(service.status in {"ok", "off"} for service in services) else "degraded"
    return HealthOut(status=overall, services=services)
