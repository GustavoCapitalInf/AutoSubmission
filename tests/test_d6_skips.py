"""5.3 (2026-09-27): what D6 no longer takes (spec D6, clarified 2026-09-27 for 5.3). Fabricated descriptors only:
each keeps the bank's printed shape with invented names, amounts and dates."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier import (
    _d6_skip,
    _unknown_payee_tokens,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn

WEEKLY = (2, 9, 16, 23)
D6 = {("potential_lender", "recurring_fixed_debit")}
OTHER = {("other", "default")}


def _states(description: str, amount: float = -100.0, *, bank: str | None = None, account_name: str | None = None,
            days: tuple[int, ...] = WEEKLY) -> set[tuple[str, str]]:
    statement = Statement(
        bank=bank,
        account_name=account_name,
        transactions=[txn(f"2054-01-{day:02d}", description, amount) for day in days],
    )
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


def _reason(description: str, amount: float = -100.0) -> str | None:
    record = classify_transaction(description, amount)
    return _d6_skip(record, _unknown_payee_tokens(record.normalized_description))


@pytest.mark.parametrize(
    ("description", "reason"),
    [
        ("TRANSFER TO PAT EXAMPLE", "transfer_word"),
        ("ACH DEBIT FABRICATED COMMISSION", "compensation"),
        ("TST*FABRICATED GRILL AUSTIN TX", "card_purchase_posting"),
        ("ACH DEBIT FABRICATED WIDGETS LLC", None),
    ],
)
def test_the_5_2_skips_keep_their_reasons(description, reason):
    assert _reason(description) == reason


CHANNEL_ONLY = [
    "WITHDRAWAL MADE IN A BRANCH/STORE",
    "CASH WITHDRAWAL",
    "TELLER WITHDRAWAL",
    "ATM DEBIT 1234 FAB MAIN ST",
    "ONLINE BILL PAYMENT 1234567",
    "RECURRING PAYMENT",
    "AUTOPAY",
    "MISCELLANEOUS DEBIT",
    "DEBIT CARD PURCH CARD ENDING IN 1234 FAB MART",
    "COUNTER WITHDRAWAL",
]


@pytest.mark.parametrize("description", CHANNEL_ONLY)
def test_a_group_whose_payee_words_are_all_channel_words_is_no_payee(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "Other Debit",           # the intake lost the payee: the hunt could not tell (c00033's shape)
        "Bank Debit",            # a bank template with no payee: unclear (c00136's shape)
        "Preauthorized Wd",      # prints no payee at all: unclear (c00242's shape)
        "RECURRING PAYMENT 0105 FAB CAPITAL",  # channel words only, but the row names financing
        # D6's key stops at the first reference, so it is the template; the payee region names an organisation
        "Recurring Payment authorized on 01/02 Fab Holdings LLC Card 4321",
        "ONLINE BILL PAYMENT 1234567 TO FAB HOLDINGS LLC",
        "MOBILE PAYMENT 1234 FAB HOLDINGS GROUP LLC",
        "DEBIT CARD PURCH CARD ENDING IN 1234 FAB HOLDINGS LLC",
        "ACH DEBIT PAT EXAMPLE",
    ],
)
def test_unclear_templates_and_vetoed_rows_stay_in_review(description):
    assert _states(description) == D6
