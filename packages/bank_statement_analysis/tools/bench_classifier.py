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
from analysis.transaction_classifier import credit_decision  # noqa: E402
from analysis.transaction_classifier import obligations  # noqa: E402
from analysis.transaction_classifier import row  # noqa: E402
from analysis.transaction_classifier import funder_returns  # noqa: E402
from analysis.transaction_classifier import operating_context  # noqa: E402
from analysis.classification import credit_predicates  # noqa: E402
from analysis.classification import operating_sources  # noqa: E402
from analysis.classification import payees  # noqa: E402
from analysis.classification import tax_forms  # noqa: E402
from analysis.descriptor import financing  # noqa: E402
from analysis.classification_registry import PAYEE_GROUP_REGISTRIES  # noqa: E402
from analysis.description_text import normalize_transaction_description  # noqa: E402
from analysis.payee_matcher import PayeeMatch  # noqa: E402
from analysis.schema import Statement, Transaction  # noqa: E402

#: Spec section 4.6: the new matcher must classify the statement at least this many times faster.
REQUIRED_SPEEDUP = 10.0


def legacy_registry_match(
    text: str, registry: dict[str, tuple[str, ...]], *, glued_digits: bool = False,
) -> tuple[str, str] | None:
    """The classifier's ``_registry_match`` before S1, verbatim in behaviour: re-normalizes and re-sorts
    every alias on every call. Kept only as the reference for parity and speed. `glued_digits` (audit B6) is
    accepted and ignored: the pre-S1 algorithm had no glued-digit arm."""
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


def legacy_match_known_payee(normalized_text: str, *, credit: bool = False) -> PayeeMatch | None:
    """The known-payee lookup done the pre-S1 way: one legacy scan per group registry. `credit` (audit B6) is
    accepted and ignored: the pre-S1 algorithm read credits and debits alike."""
    best: tuple[int, PayeeMatch] | None = None
    for state, registry in PAYEE_GROUP_REGISTRIES.items():
        found = legacy_registry_match(normalized_text, registry)
        if found is not None:
            length = len(normalize_transaction_description(found[1]))
            if best is None or length > best[0]:
                best = (length, PayeeMatch(found[0], state, found[1]))
    return None if best is None else best[1]


#: Each module whose functions read the classifier's matchers, with the matcher it reads. Each such module
#: holds its own binding of the matcher, so the swap sets every binding.
MATCHER_BINDINGS = (
    (credit_predicates, "match_known_payee"),
    (operating_sources, "registry_match"),
    (payees, "registry_match"),
    (tax_forms, "registry_match"),
    (financing, "registry_match"),
    (credit_decision, "match_known_payee"),
    (credit_decision, "registry_match"),
    (funder_returns, "match_known_payee"),
    (obligations, "registry_match"),
    (operating_context, "registry_match"),
    (row, "match_known_payee"),
    (row, "registry_match"),
)


@contextmanager
def legacy_matchers() -> Iterator[None]:
    """Swap the classifier's compiled matchers for the pre-S1 algorithm while the block runs. It sets each binding
    MATCHER_BINDINGS lists."""
    swaps = {"registry_match": legacy_registry_match, "match_known_payee": legacy_match_known_payee}
    saved = [(module, name, getattr(module, name)) for module, name in MATCHER_BINDINGS]
    try:
        for module, name, _compiled in saved:
            setattr(module, name, swaps[name])
        yield
    finally:
        for module, name, compiled in saved:
            setattr(module, name, compiled)


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


def _timed(statement: Statement, repeats: int) -> tuple[float, list]:
    """The best wall time of `repeats` classifications, and the records of the last one."""
    best = float("inf")
    records: list = []
    for _ in range(repeats):
        started = time.perf_counter()
        records = transaction_classifier.classify_statement_transactions(statement)
        best = min(best, time.perf_counter() - started)
    return best, records


def _seconds(statement: Statement, repeats: int) -> float:
    return _timed(statement, repeats)[0]


def measure(rows: int = 300, *, keep_records: bool = False) -> dict:
    """Best of three with the compiled matchers; one run with the legacy matchers swapped in.

    With `keep_records`, the result also carries each side's classification records (`current_records`,
    `legacy_records`), so one legacy pass can serve both the speed check and the no-change check."""
    statement = fabricated_statement(rows)
    _seconds(statement, 1)
    current, current_records = _timed(statement, 3)
    with legacy_matchers():
        legacy, legacy_records = _timed(statement, 1)
    result: dict = {"rows": rows, "legacy_seconds": legacy, "current_seconds": current, "speedup": legacy / current}
    if keep_records:
        result["current_records"] = current_records
        result["legacy_records"] = legacy_records
    return result


def main() -> int:
    result = measure()
    print(f"{result['rows']} fabricated rows: legacy {result['legacy_seconds']:.3f} s, "
          f"compiled {result['current_seconds']:.3f} s, {result['speedup']:.1f}x faster "
          f"(required: {REQUIRED_SPEEDUP:.0f}x)")
    return 0 if result["speedup"] >= REQUIRED_SPEEDUP else 1


if __name__ == "__main__":
    raise SystemExit(main())
