import pytest

from aura.services.languages import (
    INITIAL_ONLY_KEYS,
    LanguageError,
    normalize_gitea_language,
    normalize_ragflow_language,
)


def test_normalize_gitea_language_accepts_codes_and_aliases() -> None:
    assert normalize_gitea_language("en-US") == "en-US"
    assert normalize_gitea_language("English") == "en-US"
    assert normalize_gitea_language("Chinese") == "zh-CN"
    assert normalize_gitea_language("zh-Hans") == "zh-CN"
    assert normalize_gitea_language("zh-Hant") == "zh-TW"


def test_normalize_ragflow_language_accepts_codes_and_aliases() -> None:
    assert normalize_ragflow_language("en") == "en"
    assert normalize_ragflow_language("English") == "en"
    assert normalize_ragflow_language("Chinese") == "zh-Hans"
    assert normalize_ragflow_language("zh-CN") == "zh-Hans"
    assert normalize_ragflow_language("zh-Hant") == "zh-Hant"


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(LanguageError):
        normalize_gitea_language("fr")
    with pytest.raises(LanguageError):
        normalize_ragflow_language("fr")


def test_language_keys_are_initial_only() -> None:
    assert {"gitea_language", "ragflow_language"} <= INITIAL_ONLY_KEYS
