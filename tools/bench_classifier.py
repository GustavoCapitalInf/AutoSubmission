"""Classifier speed benchmark (spec section 4.6): a fabricated 300-row statement, classified with the
compiled matcher and with the matcher as it stood before S1. Nothing here reads a statement.

    python -m tools.bench_classifier
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.description_text import normalize_transaction_description  # noqa: E402


def legacy_registry_match(text: str, registry: dict[str, tuple[str, ...]]) -> tuple[str, str] | None:
    """The classifier's ``_registry_match`` before S1, verbatim in behaviour: re-normalizes and re-sorts
    every alias on every call. Kept only as the reference for parity and speed."""
    candidates = ((canonical, alias) for canonical, aliases in registry.items() for alias in aliases)
    for canonical, alias in sorted(
        candidates,
        key=lambda item: len(normalize_transaction_description(item[1])),
        reverse=True,
    ):
        normalized_alias = normalize_transaction_description(alias)
        if normalized_alias and re.search(
            rf"(?<![A-Z0-9]){re.escape(normalized_alias)}(?![A-Z0-9])", text
        ) is not None:
            return canonical, alias
    return None
