"""Per-model token pricing and cost calculation.

Prices are USD per one million tokens. They live in ``app_settings`` as
``model_prices`` and override the cost reported by Claude Code, which may not
know a custom provider's rates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

PRICE_FIELDS = ("input", "output", "cache_read", "cache_write")
USAGE_FIELDS = (
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "cacheCreationInputTokens",
)


class PricingError(ValueError):
    """The model price table is invalid."""


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_model_prices(value: Any) -> dict[str, dict[str, float]]:
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PricingError("Model prices must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise PricingError("Model prices must be a JSON object keyed by model name.")

    normalized: dict[str, dict[str, float]] = {}
    for raw_model, raw_prices in value.items():
        model = str(raw_model).strip()
        if not model:
            raise PricingError("Model names cannot be empty.")
        if not isinstance(raw_prices, dict):
            raise PricingError(f"Prices for model '{model}' must be an object.")
        prices: dict[str, float] = {}
        for field in PRICE_FIELDS:
            try:
                price = float(raw_prices.get(field, 0))
            except (TypeError, ValueError) as exc:
                raise PricingError(f"Price '{field}' for model '{model}' must be a number.") from exc
            if price < 0:
                raise PricingError(f"Price '{field}' for model '{model}' cannot be negative.")
            prices[field] = price
        normalized[model] = prices
    return normalized


def prices_from_runtime(runtime: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    try:
        return normalize_model_prices(runtime.get("model_prices"))
    except PricingError:
        return {}


def model_usage_cost(
    model: str,
    usage: Mapping[str, Any],
    prices: Mapping[str, Mapping[str, float]],
) -> float | None:
    price = prices.get(model)
    if price is None:
        return None
    return sum(_number(usage.get(field)) / 1_000_000 * _number(price.get(key)) for field, key in zip(
        USAGE_FIELDS, PRICE_FIELDS, strict=True
    ))


def agent_cost(
    model_usage: Mapping[str, Any] | None,
    fallback: float | None,
    prices: Mapping[str, Mapping[str, float]],
) -> float | None:
    if not isinstance(model_usage, Mapping) or not model_usage:
        return fallback

    total = 0.0
    found = False
    for model, usage in model_usage.items():
        if not isinstance(usage, Mapping):
            continue
        cost = model_usage_cost(str(model), usage, prices)
        if cost is None:
            reported = usage.get("costUSD")
            if isinstance(reported, (int, float)) and not isinstance(reported, bool):
                cost = float(reported)
        if cost is not None:
            total += cost
            found = True
    return total if found else fallback


def total_tokens(model_usage: Mapping[str, Any] | None) -> int:
    if not isinstance(model_usage, Mapping):
        return 0
    total = 0
    for usage in model_usage.values():
        if not isinstance(usage, Mapping):
            continue
        total += int(sum(_number(usage.get(field)) for field in USAGE_FIELDS))
    return total
