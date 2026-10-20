"""Runtime settings with environment > database > defaults precedence."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import Settings, get_settings
from aura.models import AppSetting
from aura.services.languages import (
    INITIAL_ONLY_KEYS,
    normalize_gitea_language,
    normalize_ragflow_language,
)

SECRET_KEYS = {
    "gitea_token",
    "gitea_password",
    "ragflow_api_key",
    "ragflow_account_password",
    "anthropic_auth_token",
}
MASK = "********"
INITIAL_DEFAULTS = {"gitea_language": "en-US", "ragflow_language": "en"}

# Keys the UI may change. Infrastructure coordinates that would break the
# process if changed live (database URL, log directory) stay environment-only.
EDITABLE_KEYS: tuple[str, ...] = (
    "gitea_url",
    "gitea_user",
    "gitea_owner",
    "gitea_token",
    "gitea_language",
    "claude_bin",
    "default_model",
    "anthropic_base_url",
    "anthropic_auth_token",
    "anthropic_model",
    "anthropic_default_opus_model",
    "anthropic_default_sonnet_model",
    "anthropic_default_haiku_model",
    "claude_code_subagent_model",
    "claude_code_effort_level",
    "claude_code_auto_compact_window",
    "claude_code_disable_unknown_model_window_enforcement",
    "model_prices",
    "permission_mode",
    "max_budget_usd",
    "max_concurrent_runs",
    "agent_timeout_seconds",
    "public_url",
    "database_admin_url",
    "workspace_dir",
    "ragflow_url",
    "ragflow_api_key",
    "ragflow_account_email",
    "ragflow_account_password",
    "ragflow_mcp_url",
    "ragflow_language",
    "default_locale",
    "default_theme",
    "auto_pipeline",
)

BASELINE_ATTRS = {
    "gitea_url": "gitea_url",
    "gitea_user": "gitea_user",
    "gitea_owner": "gitea_owner",
    "gitea_token": "gitea_token",
    "gitea_language": "gitea_language",
    "claude_bin": "claude_bin",
    "default_model": "default_model",
    "anthropic_base_url": "anthropic_base_url",
    "anthropic_auth_token": "anthropic_auth_token",
    "anthropic_model": "anthropic_model",
    "anthropic_default_opus_model": "anthropic_default_opus_model",
    "anthropic_default_sonnet_model": "anthropic_default_sonnet_model",
    "anthropic_default_haiku_model": "anthropic_default_haiku_model",
    "claude_code_subagent_model": "claude_code_subagent_model",
    "claude_code_effort_level": "claude_code_effort_level",
    "claude_code_auto_compact_window": "claude_code_auto_compact_window",
    "claude_code_disable_unknown_model_window_enforcement": (
        "claude_code_disable_unknown_model_window_enforcement"
    ),
    "model_prices": "model_prices",
    "permission_mode": "permission_mode",
    "max_budget_usd": "max_budget_usd",
    "max_concurrent_runs": "max_concurrent_runs",
    "agent_timeout_seconds": "agent_timeout_seconds",
    "public_url": "public_url",
    "database_admin_url": "database_admin_url",
    "workspace_dir": "workspace_dir",
    "ragflow_url": "ragflow_url",
    "ragflow_api_key": "ragflow_api_key",
    "ragflow_account_email": "ragflow_account_email",
    "ragflow_account_password": "ragflow_account_password",
    "ragflow_mcp_url": "ragflow_mcp_url",
    "ragflow_language": "ragflow_language",
    "default_locale": "default_locale",
    "default_theme": "default_theme",
    "auto_pipeline": "auto_pipeline",
}


def _baseline(settings: Settings) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, attr in BASELINE_ATTRS.items():
        value = getattr(settings, attr)
        values[key] = str(value) if key == "workspace_dir" else value
    for key, normalizer, default in (
        ("gitea_language", normalize_gitea_language, "en-US"),
        ("ragflow_language", normalize_ragflow_language, "en"),
    ):
        try:
            values[key] = normalizer(values.get(key))
        except ValueError:
            values[key] = default
    return values


def merge_effective(baseline: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Database overrides win over the environment-backed baseline.

    The process environment remains authoritative for values consumed at
    startup (database URL, log directory). Every key exposed here is safe for a
    live database override.
    """
    merged = dict(baseline)
    for key, value in overrides.items():
        if key in EDITABLE_KEYS and value is not None:
            merged[key] = value
    return merged


def mask_values(values: dict[str, Any]) -> dict[str, Any]:
    masked = dict(values)
    for key in SECRET_KEYS:
        if masked.get(key):
            masked[key] = MASK
        else:
            masked[key] = ""
    return masked


def environment_keys() -> set[str]:
    """Keys explicitly pinned by the process environment.

    Language keys use the environment only as an editable initial value.
    """
    return {
        key
        for key in EDITABLE_KEYS
        if key not in INITIAL_ONLY_KEYS and os.environ.get(f"AURA_{key.upper()}") is not None
    }


def coerce_value(key: str, value: Any, baseline: dict[str, Any]) -> Any:
    if key == "gitea_language":
        return normalize_gitea_language(value)
    if key == "ragflow_language":
        return normalize_ragflow_language(value)
    if key == "model_prices":
        from aura.services.pricing import normalize_model_prices

        return normalize_model_prices(value)
    current = baseline.get(key)
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int) and not isinstance(current, bool):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return str(value)


class SettingsService:
    @staticmethod
    def baseline(settings: Settings | None = None) -> dict[str, Any]:
        return _baseline(settings or get_settings())

    @staticmethod
    async def overrides(session: AsyncSession) -> dict[str, Any]:
        rows = (await session.execute(select(AppSetting))).scalars().all()
        return {row.key: row.value for row in rows if row.key in EDITABLE_KEYS}

    @classmethod
    async def effective_raw(cls, session: AsyncSession) -> dict[str, Any]:
        baseline = cls.baseline()
        overrides = await cls.overrides(session)
        return merge_effective(baseline, overrides)

    @classmethod
    async def effective(cls, session: AsyncSession) -> dict[str, Any]:
        return mask_values(await cls.effective_raw(session))

    @classmethod
    async def sources(cls, session: AsyncSession) -> dict[str, str]:
        env_keys = environment_keys()
        db_keys = set((await cls.overrides(session)).keys())
        baseline = cls.baseline()
        result: dict[str, str] = {}
        for key in EDITABLE_KEYS:
            if key in env_keys:
                result[key] = "environment"
            elif key in db_keys:
                result[key] = "database"
            elif key in INITIAL_ONLY_KEYS and (
                os.environ.get(f"AURA_{key.upper()}") is not None
                or baseline.get(key) != INITIAL_DEFAULTS.get(key)
            ):
                result[key] = "initial"
            else:
                result[key] = "default"
        return result

    @classmethod
    async def update(cls, session: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        """Persist editable values. Raises ValueError for invalid or locked keys."""
        env_keys = environment_keys()
        baseline = cls.baseline()
        for key, value in values.items():
            if key not in EDITABLE_KEYS:
                raise ValueError(f"Unknown or read-only setting: {key}")
            if key in env_keys:
                raise PermissionError(f"Setting is pinned by the environment: {key}")
            if key in SECRET_KEYS and value == MASK:
                continue
            coerced = coerce_value(key, value, baseline)
            row = await session.get(AppSetting, key)
            if row is None:
                session.add(AppSetting(key=key, value=coerced))
            else:
                row.value = coerced
        await session.commit()
        return await cls.effective(session)
