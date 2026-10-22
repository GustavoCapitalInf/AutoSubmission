"""Fabricated rows and payees for the lender-detection classifier tests (spec §9).

Every descriptor, name and amount here is fabricated: no statement text, no
real amount, no customer name. Amounts are whole dollars.
"""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.transaction_classifier import funder_returns
from analysis.classification import credit_predicates
from analysis.classification import payees
from analysis.payee_matcher import PayeeMatch
from analysis.schema import Transaction


def txn(day: str, description: str, amount: float, *, balance: float | None = None) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )


#: alias -> (canonical entity, classification state); at least one payee per group.
FAKE_PAYEES: dict[str, tuple[str, str]] = {
    "FABRICATED LENDER": ("Fabricated Lender", "confirmed_lender"),
    "FABRICATED ALT": ("Fabricated Alt Capital", "alternative_position"),
    "FABRICATED BNPL": ("Fabricated BNPL", "alternative_position"),
    "FABRICATED LINE": ("Fabricated Line", "line_of_credit"),
    "FABRICATED CARMAKER FINANCIAL": ("Fabricated Carmaker Financial", "vehicle_financing"),
    "FABRICATED MORTGAGE CO": ("Fabricated Mortgage Co", "mortgage"),
    "FABRICATED PERSONAL": ("Fabricated Personal Loans", "personal_loan"),
    "FABRICATED FLOORPLAN": ("Fabricated Floorplan Finance", "floor_plan_financing"),
    "FABRICATED FACTOR": ("Fabricated Factor", "factoring"),
    "FABRICATED RENTALS": ("Fabricated Rentals", "lease_or_rental"),
    "FABRICATED ISSUER": ("Fabricated Issuer", "credit_card_payment"),
    "FABRICATED DEBT RELIEF": ("Fabricated Debt Relief", "debt_relief"),
}


def fake_match(normalized_text: str, *, credit: bool = False) -> PayeeMatch | None:
    """A stand-in for S1's matcher over FAKE_PAYEES: the longest alias found wins. `credit` (audit B6: the matcher's
    credit index) reads the same fabricated payees."""
    for alias in sorted(FAKE_PAYEES, key=len, reverse=True):
        if alias in normalized_text:
            entity, state = FAKE_PAYEES[alias]
            return PayeeMatch(entity=entity, state=state, alias=alias)
    return None


@pytest.fixture
def fake_payees(monkeypatch):
    """Route the classifier's known-payee lookups to FAKE_PAYEES for one test."""
    monkeypatch.setattr(transaction_classifier, "match_known_payee", fake_match)
    monkeypatch.setattr(credit_predicates, "match_known_payee", fake_match)
    monkeypatch.setattr(funder_returns, "match_known_payee", fake_match)
    return FAKE_PAYEES


@pytest.fixture
def fake_premium_finance(monkeypatch):
    """Route the insurance rule's two registries to fabricated insurers for one test.

    `FABRICATED INSURER FUNDING` (premium finance) contains the shorter insurer
    alias `FABRICATED INSURER`, as a premium financier's name can contain an
    insurer's.
    """
    monkeypatch.setattr(payees, "INSURANCE_PROVIDER_ALIASES", {"Fabricated Insurer": ("FABRICATED INSURER",)})
    monkeypatch.setattr(
        payees,
        "PREMIUM_FINANCE_ALIASES",
        {
            "Fabricated Premium Finance": ("FABRICATED PFC",),
            "Fabricated Insurer Funding": ("FABRICATED INSURER FUNDING",),
        },
    )


#: One statement with four flagged groups, one lender (all via FAKE_PAYEES or
#: descriptors) and one deposit. Transaction numbers follow the tuple order.
FLAGGED_ROWS: tuple[tuple[str, str, float], ...] = (
    ("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
    ("2054-01-06", "ACH DEBIT FABRICATED ALT 0001", -700.0),
    ("2054-01-13", "ACH DEBIT FABRICATED ALT 0002", -700.0),
    ("2054-01-08", "ACH DEBIT FABRICATED BNPL 0001", -900.0),
    ("2054-01-05", "MORTGAGE PMT FABRICATED HOME", -1200.0),
    ("2054-02-05", "MORTGAGE PMT FABRICATED HOME", -1200.0),
    ("2054-01-10", "CREDIT CARD PAYMENT", -300.0),
    ("2054-01-20", "CREDIT CARD PAYMENT", -500.0),
    ("2054-01-12", "EQUIPMENT RENTAL FABRICATED", -200.0),
    ("2054-01-15", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
)

FLAGGED_GROUPS_EXPECTED: dict[str, dict[str, float | int]] = {
    "alternative_positions": {"count": 3, "total": 2300.0, "count_credited": 0, "total_credited": 0.0, "payees": 2},
    "credit_cards": {"count": 2, "total": 800.0, "count_credited": 0, "total_credited": 0.0, "payees": 1},
    "mortgages": {"count": 2, "total": 2400.0, "count_credited": 0, "total_credited": 0.0, "payees": 1},
    "leases_rentals": {"count": 1, "total": 200.0, "count_credited": 0, "total_credited": 0.0, "payees": 1},
}


def flagged_statement(rows: tuple[tuple[str, str, float], ...] = FLAGGED_ROWS):
    from analysis.schema import Statement

    return Statement(
        bank="Fabricated Bank",
        account_number="0000",
        transactions=[txn(day, description, amount) for day, description, amount in rows],
    )


def flagged_report(rows: tuple[tuple[str, str, float], ...] = FLAGGED_ROWS):
    """A full Report for `rows` (FLAGGED_ROWS by default). Call it with the fake_payees fixture active."""
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement(rows)
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    return Report(
        statement=statement,
        reconciliation=reconcile(statement),
        metrics=metrics,
        detection=detect(statement, classifications=records, eligible_deposits=metrics.eligible_deposits),
        quality=Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=True,
            corporate_use="approved",
        ),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="fabricated-test",
        escalated=False,
        classifications=records,
    )
