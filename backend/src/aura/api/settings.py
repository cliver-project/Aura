"""Global settings API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.schemas import SettingsOut, SettingsUpdate
from aura.services.languages import apply_language_settings
from aura.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def read_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsOut:
    return SettingsOut(
        values=await SettingsService.effective(session),
        sources=await SettingsService.sources(session),
    )


@router.patch("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsOut:
    try:
        values = await SettingsService.update(session, payload.values)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    changed_languages = set(payload.values) & {"gitea_language", "ragflow_language"}
    warnings = await apply_language_settings(
        await SettingsService.effective_raw(session),
        changed_languages,
    )
    return SettingsOut(
        values=values,
        sources=await SettingsService.sources(session),
        warnings=warnings,
    )
