import inspect

import pytest

from aura.config import clear_settings_cache
from aura.services.settings_service import (
    MASK,
    SettingsService,
    coerce_value,
    environment_keys,
    mask_values,
    merge_effective,
)


def test_settings_service_has_no_reveal_path() -> None:
    assert "reveal" not in inspect.signature(SettingsService.effective).parameters


def test_database_overrides_win() -> None:
    baseline = {"gitea_url": "http://localhost:3000", "auto_pipeline": True}
    merged = merge_effective(baseline, {"gitea_url": "http://gitea.local:3001"})
    assert merged["gitea_url"] == "http://gitea.local:3001"
    assert merged["auto_pipeline"] is True


def test_unknown_override_is_ignored() -> None:
    baseline = {"gitea_url": "http://localhost:3000"}
    merged = merge_effective(baseline, {"database_url": "postgres://evil"})
    assert merged == baseline


def test_secrets_are_masked() -> None:
    masked = mask_values(
        {
            "gitea_token": "super-secret",
            "ragflow_api_key": "",
            "anthropic_auth_token": "provider-secret",
            "gitea_url": "x",
        }
    )
    assert masked["gitea_token"] == MASK
    assert masked["ragflow_api_key"] == ""
    assert masked["anthropic_auth_token"] == MASK
    assert masked["gitea_url"] == "x"


def test_environment_keys_are_detected(monkeypatch) -> None:
    monkeypatch.setenv("AURA_GITEA_URL", "http://from-env")
    assert "gitea_url" in environment_keys()
    assert "default_model" not in environment_keys()


def test_baseline_normalizes_language_aliases(monkeypatch) -> None:
    monkeypatch.setenv("AURA_GITEA_LANGUAGE", "Chinese")
    monkeypatch.setenv("AURA_RAGFLOW_LANGUAGE", "zh-Hant")
    clear_settings_cache()
    try:
        baseline = SettingsService.baseline()
        assert baseline["gitea_language"] == "zh-CN"
        assert baseline["ragflow_language"] == "zh-Hant"
    finally:
        clear_settings_cache()


def test_language_keys_are_initial_only(monkeypatch) -> None:
    monkeypatch.setenv("AURA_GITEA_LANGUAGE", "zh-CN")
    monkeypatch.setenv("AURA_RAGFLOW_LANGUAGE", "zh-Hans")
    assert "gitea_language" not in environment_keys()
    assert "ragflow_language" not in environment_keys()
    assert coerce_value("gitea_language", "Chinese", {"gitea_language": "en-US"}) == "zh-CN"
    assert coerce_value("ragflow_language", "Chinese", {"ragflow_language": "en"}) == "zh-Hans"


def test_coercion_follows_baseline_type() -> None:
    baseline = {"auto_pipeline": True, "max_concurrent_runs": 3, "max_budget_usd": 1.5}
    assert coerce_value("auto_pipeline", "false", baseline) is False
    assert coerce_value("max_concurrent_runs", "8", baseline) == 8
    assert coerce_value("max_budget_usd", "2.25", baseline) == 2.25


def test_model_prices_are_normalized_and_validated() -> None:
    prices = coerce_value("model_prices", {"m": {"input": 1}}, {"model_prices": {}})
    assert prices["m"]["input"] == 1.0
    assert prices["m"]["output"] == 0.0
    with pytest.raises(ValueError):
        coerce_value("model_prices", {"m": {"input": -1}}, {"model_prices": {}})
