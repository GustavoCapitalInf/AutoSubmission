"""Fabricated rows and payees for the lender-detection classifier tests (spec §9).

Every descriptor, name and amount here is fabricated: no statement text, no
real amount, no customer name. Amounts are whole dollars.
"""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
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
}


def fake_match(normalized_text: str) -> PayeeMatch | None:
    """A stand-in for S1's matcher over FAKE_PAYEES: the longest alias found wins."""
    for alias in sorted(FAKE_PAYEES, key=len, reverse=True):
        if alias in normalized_text:
            entity, state = FAKE_PAYEES[alias]
            return PayeeMatch(entity=entity, state=state, alias=alias)
    return None


@pytest.fixture
def fake_payees(monkeypatch):
    """Route the classifier's known-payee lookups to FAKE_PAYEES for one test."""
    monkeypatch.setattr(transaction_classifier, "match_known_payee", fake_match)
    return FAKE_PAYEES
