"""Claude Code provider environment values.

Global provider settings live in ``app_settings``; each agent may override
individual environment variables. The merged mapping is passed to the Claude
Code subprocess on top of the inherited process environment.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MASK = "********"

PROVIDER_ENV_MAP: dict[str, str] = {
    "anthropic_base_url": "ANTHROPIC_BASE_URL",
    "anthropic_auth_token": "ANTHROPIC_AUTH_TOKEN",
    "anthropic_model": "ANTHROPIC_MODEL",
    "anthropic_default_opus_model": "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "anthropic_default_sonnet_model": "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "anthropic_default_haiku_model": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "claude_code_subagent_model": "CLAUDE_CODE_SUBAGENT_MODEL",
    "claude_code_effort_level": "CLAUDE_CODE_EFFORT_LEVEL",
    "claude_code_auto_compact_window": "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
}
SECRET_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "KEY")
DISABLE_WINDOW_ENFORCEMENT = "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT"


def is_secret_env_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in SECRET_ENV_MARKERS)


def build_claude_env(
    runtime: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Merge database provider settings with per-agent overrides.

    Empty values are omitted rather than exported, so an empty per-agent value
    cannot accidentally erase a working global default.
    """
    env: dict[str, str] = {}
    for setting_key, env_key in PROVIDER_ENV_MAP.items():
        value = runtime.get(setting_key)
        if value is not None and str(value).strip():
            env[env_key] = str(value)

    if runtime.get("claude_code_disable_unknown_model_window_enforcement"):
        env[DISABLE_WINDOW_ENFORCEMENT] = "1"

    for key, value in (overrides or {}).items():
        if value is None or str(value) == "":
            continue
        env[str(key)] = str(value)
    return env


def mask_env(values: Mapping[str, str]) -> dict[str, str]:
    return {
        key: (MASK if value and is_secret_env_key(key) else value)
        for key, value in values.items()
    }


def restore_masked_env(current: Mapping[str, str], updates: Mapping[str, str]) -> dict[str, str]:
    """Keep stored secrets when the client sends the mask back unchanged."""
    restored: dict[str, str] = {}
    for key, value in updates.items():
        if value == MASK and is_secret_env_key(key):
            if key in current:
                restored[key] = current[key]
            continue
        restored[key] = value
    return restored
