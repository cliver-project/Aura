"""MCP server configuration and per-run runtime config materialization."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import select

from aura.config import get_settings
from aura.models import McpServer

SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def mask_mapping(values: dict[str, str]) -> dict[str, str]:
    return {
        key: ("********" if any(marker in key.upper() for marker in SECRET_MARKERS) and value else value)
        for key, value in values.items()
    }


def masked_server(server: McpServer) -> dict[str, Any]:
    return {
        "id": server.id,
        "name": server.name,
        "description": server.description,
        "transport": server.transport,
        "command": server.command,
        "args": list(server.args or []),
        "env": mask_mapping(dict(server.env or {})),
        "url": server.url,
        "headers": mask_mapping(dict(server.headers or {})),
        "enabled": server.enabled,
        "created_at": server.created_at,
        "updated_at": server.updated_at,
    }


def resolve_placeholders(value: str, runtime: Mapping[str, Any]) -> str | None:
    """Substitute ``{{setting_key}}`` values from runtime settings.

    Returns ``None`` when any referenced setting is missing or empty, so the
    caller can omit a server whose credentials are not configured.
    """
    unresolved = False

    def replace(match: re.Match[str]) -> str:
        nonlocal unresolved
        raw = runtime.get(match.group(1))
        if raw is None or str(raw).strip() == "":
            unresolved = True
            return match.group(0)
        return str(raw)

    resolved = PLACEHOLDER.sub(replace, value)
    return None if unresolved else resolved


def _resolve_mapping(values: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, str] | None:
    resolved: dict[str, str] = {}
    for key, value in values.items():
        text = str(value)
        substituted = resolve_placeholders(text, runtime)
        if substituted is None:
            return None
        resolved[str(key)] = substituted
    return resolved


def build_mcp_config(
    servers: list[McpServer],
    runtime: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a Claude Code MCP config from database rows.

    Values are resolved from runtime settings at run time. A server with an
    unresolved placeholder or missing required URL is skipped with a warning;
    it must never reach the model with an empty credential.
    """
    settings = runtime or {}
    entries: dict[str, Any] = {}
    warnings: list[str] = []

    for server in servers:
        if not server.enabled:
            continue

        if server.transport == "stdio":
            if not server.command:
                warnings.append(f"MCP server '{server.name}' omitted: missing command")
                continue
            env = _resolve_mapping(server.env or {}, settings)
            if env is None:
                warnings.append(f"MCP server '{server.name}' omitted: unresolved env placeholder")
                continue
            entries[server.name] = {
                "command": server.command,
                "args": list(server.args or []),
                "env": env,
            }
            continue

        url = resolve_placeholders(str(server.url or ""), settings)
        if url is None:
            warnings.append(f"MCP server '{server.name}' omitted: unresolved URL placeholder")
            continue
        if not url:
            warnings.append(f"MCP server '{server.name}' omitted: missing URL")
            continue
        headers = _resolve_mapping(server.headers or {}, settings)
        if headers is None:
            warnings.append(f"MCP server '{server.name}' omitted: unresolved header placeholder")
            continue
        entries[server.name] = {
            "type": server.transport,
            "url": url,
            "headers": headers,
        }

    return {"mcpServers": entries}, warnings


def write_mcp_config(
    config: dict[str, Any],
    run_id: str,
    directory: Path | None = None,
) -> Path:
    """Write per-run MCP config outside the cloned repository."""
    target_dir = (directory or (get_settings().log_dir / "mcp")).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{Path(run_id).name}.json"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(config, indent=2))
    target.chmod(0o600)
    return target


def remove_runtime_config(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def cleanup_runtime_configs(directory: Path | None = None) -> int:
    """Remove MCP configs left behind by a crashed process."""
    target_dir = (directory or (get_settings().log_dir / "mcp")).expanduser().resolve()
    if not target_dir.exists():
        return 0
    removed = 0
    for path in target_dir.glob("*.json"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


class McpService:
    @staticmethod
    async def prepare(
        server_ids: list[str],
        runtime: dict[str, Any],
        run_id: str,
    ) -> tuple[Path, list[str]]:
        servers: list[McpServer] = []
        if server_ids:
            from aura.db import SessionLocal

            async with SessionLocal() as session:
                servers = list(
                    (
                        await session.execute(
                            select(McpServer).where(McpServer.id.in_(server_ids), McpServer.enabled.is_(True))
                        )
                    )
                    .scalars()
                    .all()
                )
        config, warnings = build_mcp_config(servers, runtime)
        # Always write a config, even when empty: --strict-mcp-config then
        # prevents Claude Code from loading user-level MCP servers.
        return write_mcp_config(config, run_id), warnings
