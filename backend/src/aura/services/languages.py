"""Language choices for the local Gitea and RAGFlow accounts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aura.config import get_settings
from aura.services.gitea import GiteaError
from aura.services.ragflow import RagflowClient, RagflowError

GITEA_LANGUAGES = ("en-US", "zh-CN", "zh-TW")
RAGFLOW_LANGUAGES = ("en", "zh-Hans", "zh-Hant")
INITIAL_ONLY_KEYS = frozenset({"gitea_language", "ragflow_language"})

_GITEA_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "english": "en-US",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "chinese": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hant": "zh-TW",
    "traditional chinese": "zh-TW",
}
_RAGFLOW_ALIASES = {
    "en": "en",
    "en-us": "en",
    "english": "en",
    "zh": "zh-Hans",
    "zh-cn": "zh-Hans",
    "zh-hans": "zh-Hans",
    "chinese": "zh-Hans",
    "zh-tw": "zh-Hant",
    "zh-hant": "zh-Hant",
    "traditional chinese": "zh-Hant",
}


class LanguageError(ValueError):
    """The configured language is not supported."""


def _normalize(
    value: Any,
    choices: tuple[str, ...],
    aliases: dict[str, str],
    label: str,
) -> str:
    text = str(value or "").strip()
    if text in choices:
        return text
    normalized = aliases.get(text.lower())
    if normalized is not None:
        return normalized
    raise LanguageError(f"{label} must be one of: {', '.join(choices)}.")


def normalize_gitea_language(value: Any) -> str:
    return _normalize(value, GITEA_LANGUAGES, _GITEA_ALIASES, "Gitea language")


def normalize_ragflow_language(value: Any) -> str:
    return _normalize(value, RAGFLOW_LANGUAGES, _RAGFLOW_ALIASES, "RAGFlow language")


async def apply_gitea_language(runtime: Mapping[str, Any], language: str) -> str | None:
    """Update the configured Gitea user's UI language; return a warning on failure."""
    settings = get_settings()
    username = str(runtime.get("gitea_user") or settings.gitea_user or "")
    password = str(settings.gitea_password or "")
    if not username or not password:
        return "Gitea language was saved but not applied: missing Gitea user or password."
    from aura.services.projects import gitea_client

    client = gitea_client(runtime)
    try:
        await client.update_current_user_settings(language, username=username, password=password)
    except GiteaError as exc:
        return f"Gitea language was saved but not applied: {exc}"
    return None


async def apply_ragflow_language(runtime: Mapping[str, Any], language: str) -> str | None:
    """Update the configured RAGFlow tenant account's UI language."""
    settings = get_settings()
    url = str(runtime.get("ragflow_url") or settings.ragflow_url or "")
    key = str(runtime.get("ragflow_api_key") or "")
    if not url or not key:
        return "RAGFlow language was saved but not applied: missing RAGFlow URL or API key."
    client = RagflowClient(url, api_key=key, timeout=10.0)
    try:
        await client.update_language(language)
    except RagflowError as exc:
        return f"RAGFlow language was saved but not applied: {exc}"
    return None


async def apply_language_settings(
    runtime: Mapping[str, Any],
    changed: set[str] | None = None,
) -> list[str]:
    settings = get_settings()
    warnings: list[str] = []
    if changed is None or "gitea_language" in changed:
        language = normalize_gitea_language(
            runtime.get("gitea_language") or settings.gitea_language
        )
        warning = await apply_gitea_language(runtime, language)
        if warning:
            warnings.append(warning)
    if changed is None or "ragflow_language" in changed:
        language = normalize_ragflow_language(
            runtime.get("ragflow_language") or settings.ragflow_language
        )
        warning = await apply_ragflow_language(runtime, language)
        if warning:
            warnings.append(warning)
    return warnings
