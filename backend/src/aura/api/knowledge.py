"""Knowledge-base status and dataset listing."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import get_settings
from aura.db import get_session
from aura.schemas import KnowledgeStatus
from aura.services.onboarding import DEFAULT_RAGFLOW_URL
from aura.services.ragflow import RagflowClient, RagflowError
from aura.services.settings_service import SettingsService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


async def _client(session: AsyncSession) -> tuple[RagflowClient, str]:
    runtime = await SettingsService.effective_raw(session)
    settings = get_settings()
    url = str(runtime.get("ragflow_url") or DEFAULT_RAGFLOW_URL).rstrip("/")
    key = str(runtime.get("ragflow_api_key") or "")
    return (
        RagflowClient(
            url,
            api_key=key,
            account_email=str(runtime.get("ragflow_account_email") or settings.ragflow_account_email),
            account_password=str(runtime.get("ragflow_account_password") or settings.ragflow_account_password),
            timeout=10.0,
        ),
        url,
    )


@router.get("/status", response_model=KnowledgeStatus)
async def status(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeStatus:
    client, url = await _client(session)
    settings = get_settings()
    result = KnowledgeStatus(
        url=url,
        web_url=settings.ragflow_web_url,
        configured=bool(client.api_key),
        healthy=await client.health(),
    )
    if result.healthy and client.api_key:
        try:
            datasets = await client.list_datasets()
            result.key_valid = True
            result.dataset_count = len(datasets)
        except RagflowError as exc:
            result.error = str(exc)[:300]
    elif not result.healthy:
        result.error = "RAGFlow is not reachable."
    return result


@router.get("/datasets")
async def datasets(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    client, _url = await _client(session)
    if not client.api_key:
        raise HTTPException(status_code=409, detail="RAGFlow API key is not configured.")
    try:
        return await client.list_datasets()
    except RagflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
