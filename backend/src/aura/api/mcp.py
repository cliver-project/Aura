"""MCP server CRUD."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.db import get_session
from aura.models import McpServer
from aura.schemas import McpCreate, McpOut, McpUpdate
from aura.services.mcp_service import masked_server

router = APIRouter(prefix="/api/mcp-servers", tags=["mcp"])


def _to_out(server: McpServer) -> McpOut:
    return McpOut(**masked_server(server))


@router.get("", response_model=list[McpOut])
async def list_servers(session: Annotated[AsyncSession, Depends(get_session)]) -> list[McpOut]:
    servers = (await session.execute(select(McpServer).order_by(McpServer.created_at.asc()))).scalars().all()
    return [_to_out(server) for server in servers]


@router.post("", response_model=McpOut, status_code=201)
async def create_server(
    payload: McpCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpOut:
    if payload.transport not in {"stdio", "http", "sse"}:
        raise HTTPException(status_code=422, detail="Transport must be stdio, http, or sse")
    existing = await session.execute(select(McpServer).where(McpServer.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="MCP server name already exists")
    server = McpServer(**payload.model_dump())
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return _to_out(server)


@router.patch("/{server_id}", response_model=McpOut)
async def update_server(
    server_id: str,
    payload: McpUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpOut:
    server = await session.get(McpServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    updates: dict[str, Any] = payload.model_dump(exclude_unset=True)
    if updates.get("transport") and updates["transport"] not in {"stdio", "http", "sse"}:
        raise HTTPException(status_code=422, detail="Transport must be stdio, http, or sse")
    for field in ("env", "headers"):
        if updates.get(field):
            existing = dict(getattr(server, field) or {})
            updates[field] = {
                key: (existing.get(key, "") if value == "********" else value) for key, value in updates[field].items()
            }
    for key, value in updates.items():
        setattr(server, key, value)
    await session.commit()
    await session.refresh(server)
    return _to_out(server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    server = await session.get(McpServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await session.delete(server)
    await session.commit()
