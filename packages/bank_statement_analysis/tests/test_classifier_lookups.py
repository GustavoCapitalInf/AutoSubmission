from __future__ import annotations

from analysis import transaction_classifier
from analysis.true_revenue import self_originated_credits
from analysis.true_revenue import sender
from analysis.classification import counter_debit_reading
from analysis.classification import credit_predicates
from analysis.classification import operating_sources
from analysis.descriptor import holder
from analysis.descriptor import rails
from analysis.descriptor import financing
from analysis import description_text
from analysis.schema import Statement
from tests.flag_group_fixtures import txn


def synthetic_statement(rows_per_kind: int = 100) -> Statement:
    """300 fabricated rows: customer credits, vendor ACH debits and card purchases."""
    transactions = []
    for index in range(rows_per_kind):
        day = f"2054-01-{index % 28 + 1:02d}"
        transactions.append(txn(day, f"ACH CREDIT FABRICATED CUSTOMER {index:04d}", float(100 + index)))
        transactions.append(txn(day, f"ACH DEBIT FABRICATED VENDOR {index:04d}", -float(50 + index)))
        transactions.append(txn(day, f"POS PURCHASE FABRICATED STORE {index:04d}", -float(10 + index)))
    return Statement(transactions=transactions)


def test_each_row_is_normalized_exactly_once(monkeypatch):
    """Spec §4.6 speed: aliases are compiled once, so classifying a row never
    re-normalizes an alias. No row here matches an operating-revenue alias, so no
    account name is normalized either."""
    calls: list[str] = []
    original = description_text.normalize_transaction_description

    def counting(value: str) -> str:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(transaction_classifier, "normalize_transaction_description", counting)
    monkeypatch.setattr(counter_debit_reading, "normalize_transaction_description", counting)
    monkeypatch.setattr(credit_predicates, "normalize_transaction_description", counting)
    monkeypatch.setattr(operating_sources, "normalize_transaction_description", counting)
    monkeypatch.setattr(financing, "normalize_transaction_description", counting)
    monkeypatch.setattr(holder, "normalize_transaction_description", counting)
    monkeypatch.setattr(rails, "normalize_transaction_description", counting)
    monkeypatch.setattr(self_originated_credits, "normalize_transaction_description", counting)
    monkeypatch.setattr(sender, "normalize_transaction_description", counting)
    records = transaction_classifier.classify_statement_transactions(synthetic_statement())
    assert len(records) == 300
    assert len(calls) == len(records)


def test_the_ach_flag_needs_the_ach_token_on_its_own():
    assert transaction_classifier.classify_transaction("ACH DEBIT FABRICATED VENDOR", -50.0).is_ach
    assert not transaction_classifier.classify_transaction("CACHE FABRICATED VENDOR", -50.0).is_ach
