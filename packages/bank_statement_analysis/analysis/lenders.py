"""Compatibility helpers backed by the authoritative transaction classifier."""
from __future__ import annotations

from .classification_registry import CONFIRMED_LENDER_ALIASES
from .transaction_classifier import (
    classify_transaction,
    normalize_transaction_description,
)


LENDER_KEYWORDS: dict[str, list[str]] = {
    lender: list(aliases)
    for lender, aliases in CONFIRMED_LENDER_ALIASES.items()
}


def normalize_description(description: str) -> str:
    return normalize_transaction_description(description)


def find_lender_match(description: str, amount: float = -1.0) -> tuple[str, str] | None:
    """Compatibility view that still honors the authoritative rule ordering."""
    result = classify_transaction(description, amount)
    if result.classification != "confirmed_lender" or not result.canonical_entity:
        return None
    return result.canonical_entity, result.matched_alias or ""


def has_false_lender_keyword(description: str) -> bool:
    result = classify_transaction(description, -1.0)
    return result.classification not in {"confirmed_lender", "potential_lender", "other"}


def is_pos_transaction(description: str, amount: float = -1.0) -> bool:
    return classify_transaction(description, amount).is_pos_purchase


def is_loan_transaction(description: str) -> bool:
    return classify_transaction(description, -1.0).is_loan_payment
