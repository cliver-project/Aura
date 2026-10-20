"""First-run onboarding endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.schemas import (
    GenerateSshKeyRequest,
    GiteaIdentityRequest,
    GitIdentityRequest,
    OnboardingStatus,
    RagflowConfigRequest,
    SshKeyRequest,
)
from aura.services import onboarding

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _error(exc: onboarding.OnboardingError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/status", response_model=OnboardingStatus)
async def status(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    return await onboarding.get_status(session)


@router.post("/gitea-user", response_model=OnboardingStatus)
async def configure_gitea_user(
    payload: GiteaIdentityRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        return await onboarding.configure_gitea_user(session, payload)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/ssh-key/generate", response_model=OnboardingStatus)
async def generate_ssh_key(
    payload: GenerateSshKeyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        onboarding.generate_ssh_key(payload.email)
        return await onboarding.get_status(session)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/ssh-key/register", response_model=OnboardingStatus)
async def register_ssh_key(
    payload: SshKeyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        return await onboarding.register_ssh_key(session, payload.path)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/git-identity", response_model=OnboardingStatus)
async def set_git_identity(
    payload: GitIdentityRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        return await onboarding.set_git_identity(session, payload)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/ragflow", response_model=OnboardingStatus)
async def configure_ragflow(
    payload: RagflowConfigRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        return await onboarding.configure_ragflow(session, payload)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/complete", response_model=OnboardingStatus)
async def complete(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    try:
        return await onboarding.complete_onboarding(session)
    except onboarding.OnboardingError as exc:
        raise _error(exc) from exc


@router.post("/reset", response_model=OnboardingStatus)
async def reset(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OnboardingStatus:
    return await onboarding.reset_onboarding(session)
