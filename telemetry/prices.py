"""Versioned model price estimates. Never invents a price.

The rule, inherited from the prototype's cost-telemetry pattern
(PROTOTYPE_REVIEW item 3): a model we do not have a price for contributes
**nothing** to the estimate and is named in ``unpriced_models``. A guessed
number in a cost report is worse than no number, because it looks like a
measurement.

``PRICE_TABLE_VERSION`` travels in every telemetry record, so re-pricing a
past run is a recomputation over stored token counts rather than a lost
measurement.

The table is deliberately empty of the local/self-hosted models this platform
runs today: local Tesseract costs no API money, and the visual-OCR endpoint is
a self-hosted vLLM whose price depends on infrastructure we do not meter here.
Both therefore report ``amount: null`` with the model named, which is the
honest answer.
"""
from __future__ import annotations

PRICE_TABLE_VERSION = "2026-08-06.1"

#: model id -> (USD per 1k prompt tokens, USD per 1k completion tokens).
#: Add an entry ONLY with a cited, current published price.
PRICES: dict[str, tuple[float, float]] = {}

#: Models known to cost no metered API money. They price to 0.0 rather than to
#: "unknown", because "this call was free" is a fact, not an absence.
FREE_MODELS: frozenset[str] = frozenset({
    "local-tesseract-ocr",
    "native-pdf-text",
    "deterministic-native-preflight",
})


def price_for(model: str) -> tuple[float, float] | None:
    """USD per 1k (prompt, completion) tokens, or None when unknown."""
    if model in FREE_MODELS or model.startswith("native-pdf-text"):
        return (0.0, 0.0)
    return PRICES.get(model)


def estimate(calls: list[dict]) -> dict:
    """Cost estimate for a list of model-call records.

    ``amount`` is the sum over calls we could price; ``complete`` is False when
    any call's model has no price entry, and every such model is named. When
    nothing could be priced at all, ``amount`` is None — an unknown cost is not
    a zero cost (H3_SCHEMA I5).
    """
    priced_total = 0.0
    priced_any = False
    unpriced: list[str] = []
    for call in calls:
        model = call.get("model") or ""
        rate = price_for(model)
        if rate is None:
            if model not in unpriced:
                unpriced.append(model)
            continue
        prompt_rate, completion_rate = rate
        prompt_tokens = call.get("prompt_tokens")
        completion_tokens = call.get("completion_tokens")
        if prompt_tokens is None and completion_tokens is None and rate != (0.0, 0.0):
            # Priced model, but the platform reported no usage: we cannot cost
            # it and must not pretend otherwise.
            if model not in unpriced:
                unpriced.append(model)
            continue
        priced_any = True
        priced_total += (prompt_tokens or 0) / 1000 * prompt_rate
        priced_total += (completion_tokens or 0) / 1000 * completion_rate
    return {
        "currency": "USD",
        "amount": round(priced_total, 6) if priced_any else None,
        "complete": not unpriced,
        "price_table_version": PRICE_TABLE_VERSION,
        "unpriced_models": sorted(unpriced),
    }
