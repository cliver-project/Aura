import pytest

from aura.services.pricing import (
    PricingError,
    agent_cost,
    model_usage_cost,
    normalize_model_prices,
    prices_from_runtime,
    total_tokens,
)


def test_normalize_model_prices_accepts_object_and_json_string() -> None:
    expected = {
        "example-model": {
            "input": 1.0,
            "output": 2.0,
            "cache_read": 0.1,
            "cache_write": 0.2,
        }
    }
    assert normalize_model_prices(
        {"example-model": {"input": 1, "output": 2, "cache_read": 0.1, "cache_write": 0.2}}
    ) == expected
    assert normalize_model_prices(
        '{"example-model": {"input": 1, "output": 2, "cache_read": 0.1, "cache_write": 0.2}}'
    ) == expected
    assert normalize_model_prices({"example-model": {"input": 1}})["example-model"]["output"] == 0.0
    assert normalize_model_prices(None) == {}
    assert normalize_model_prices("") == {}


def test_normalize_model_prices_rejects_invalid_shapes() -> None:
    with pytest.raises(PricingError):
        normalize_model_prices({"": {"input": 1}})
    with pytest.raises(PricingError):
        normalize_model_prices({"model": {"input": -1}})
    with pytest.raises(PricingError):
        normalize_model_prices({"model": {"input": "not-a-number"}})
    with pytest.raises(PricingError):
        normalize_model_prices(["not-a-dict"])
    with pytest.raises(PricingError):
        normalize_model_prices("{bad json")


def test_prices_from_runtime_ignores_invalid_value() -> None:
    assert prices_from_runtime({"model_prices": {"m": {"input": 1}}})["m"]["input"] == 1.0
    assert prices_from_runtime({"model_prices": ["bad"]}) == {}
    assert prices_from_runtime({}) == {}


def test_model_usage_cost_uses_per_million_prices() -> None:
    prices = {"m": {"input": 1.0, "output": 2.0, "cache_read": 0.5, "cache_write": 0.25}}
    usage = {
        "inputTokens": 1_000_000,
        "outputTokens": 500_000,
        "cacheReadInputTokens": 2_000_000,
        "cacheCreationInputTokens": 4_000_000,
    }
    assert model_usage_cost("m", usage, prices) == pytest.approx(4.0)
    assert model_usage_cost("unknown", usage, prices) is None


def test_agent_cost_prefers_prices_then_cli_then_fallback() -> None:
    prices = {"m": {"input": 1.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}}
    assert agent_cost(
        {"m": {"inputTokens": 1_000_000}},
        99.0,
        prices,
    ) == pytest.approx(1.0)
    assert agent_cost({"unknown": {"costUSD": 0.5}}, 99.0, prices) == pytest.approx(0.5)
    assert agent_cost({}, 2.5, prices) == pytest.approx(2.5)
    assert agent_cost(None, None, prices) is None


def test_total_tokens_counts_all_billed_categories() -> None:
    usage = {
        "m": {
            "inputTokens": 10,
            "outputTokens": 2,
            "cacheReadInputTokens": 3,
            "cacheCreationInputTokens": 4,
        }
    }
    assert total_tokens(usage) == 19
    assert total_tokens({}) == 0
    assert total_tokens(None) == 0
