"""Normalization of transaction descriptions, shared by the classifier and the payee matcher.

It lives in its own module so that ``analysis.payee_matcher`` can normalize registry aliases at
import time without importing ``analysis.transaction_classifier``, which imports the matcher.
``analysis.transaction_classifier`` re-exports the function under its old import path.
"""
from __future__ import annotations

import re
import unicodedata


def normalize_transaction_description(description: str) -> str:
    """Normalize matching text while retaining the exact source separately."""
    decomposed = unicodedata.normalize("NFKD", description or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    normalized = re.sub(r"\bF1NANCE\b", "FINANCE", normalized)
    normalized = re.sub(r"\bLN\b", "LOAN", normalized)
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
