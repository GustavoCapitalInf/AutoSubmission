"""Classifier speed benchmark (spec section 4.6): a fabricated 300-row statement, classified with the
compiled matcher and with the matcher as it stood before S1. Nothing here reads a statement.

    python -m tools.bench_classifier
"""
from __future__ import annotations

import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import transaction_classifier  # noqa: E402
from analysis.classification_registry import PAYEE_GROUP_REGISTRIES  # noqa: E402
from analysis.description_text import normalize_transaction_description  # noqa: E402
from analysis.payee_matcher import PayeeMatch  # noqa: E402
from analysis.schema import Statement, Transaction  # noqa: E402

#: Spec section 4.6: the new matcher must classify the statement at least this many times faster.
REQUIRED_SPEEDUP = 10.0


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


def legacy_match_known_payee(normalized_text: str) -> PayeeMatch | None:
    """The known-payee lookup done the pre-S1 way: one legacy scan per group registry."""
    best: tuple[int, PayeeMatch] | None = None
    for state, registry in PAYEE_GROUP_REGISTRIES.items():
        found = legacy_registry_match(normalized_text, registry)
        if found is not None:
            length = len(normalize_transaction_description(found[1]))
            if best is None or length > best[0]:
                best = (length, PayeeMatch(found[0], state, found[1]))
    return None if best is None else best[1]


@contextmanager
def legacy_matchers() -> Iterator[None]:
    """Swap the classifier's compiled matchers for the pre-S1 algorithm while the block runs. It swaps
    whichever of ``registry_match`` and ``match_known_payee`` the classifier module holds, so it works
    before and after S2 rewires the rule order."""
    swaps = {"registry_match": legacy_registry_match, "match_known_payee": legacy_match_known_payee}
    saved = {name: getattr(transaction_classifier, name) for name in swaps if hasattr(transaction_classifier, name)}
    try:
        for name in saved:
            setattr(transaction_classifier, name, swaps[name])
        yield
    finally:
        for name, value in saved.items():
            setattr(transaction_classifier, name, value)


def fabricated_statement(rows: int = 300) -> Statement:
    """A third credits, a third ACH debits, a third card purchases; every descriptor is invented."""
    transactions = []
    for index in range(rows):
        day = f"2054-01-{index % 28 + 1:02d}"
        if index % 3 == 0:
            transactions.append(Transaction(
                date=day, description=f"MOBILE DEPOSIT REF {index:06d}", amount=250.0 + index, direction="credit"))
        elif index % 3 == 1:
            transactions.append(Transaction(
                date=day, description=f"ACH DEBIT VENDOR {index} PAYMENT", amount=-(40.0 + index), direction="debit"))
        else:
            transactions.append(Transaction(
                date=day, description=f"POS DEBIT SHOP {index}", amount=-(5.0 + index), direction="debit"))
    return Statement(transactions=transactions)


def _seconds(statement: Statement, repeats: int) -> float:
    best = float("inf")
    for _ in range(repeats):
        started = time.perf_counter()
        transaction_classifier.classify_statement_transactions(statement)
        best = min(best, time.perf_counter() - started)
    return best


def measure(rows: int = 300) -> dict[str, float]:
    """Best of three with the compiled matchers; one run with the legacy matchers swapped in."""
    statement = fabricated_statement(rows)
    _seconds(statement, 1)
    current = _seconds(statement, 3)
    with legacy_matchers():
        legacy = _seconds(statement, 1)
    return {"rows": rows, "legacy_seconds": legacy, "current_seconds": current, "speedup": legacy / current}


def main() -> int:
    result = measure()
    print(f"{result['rows']} fabricated rows: legacy {result['legacy_seconds']:.3f} s, "
          f"compiled {result['current_seconds']:.3f} s, {result['speedup']:.1f}x faster "
          f"(required: {REQUIRED_SPEEDUP:.0f}x)")
    return 0 if result["speedup"] >= REQUIRED_SPEEDUP else 1


if __name__ == "__main__":
    raise SystemExit(main())
