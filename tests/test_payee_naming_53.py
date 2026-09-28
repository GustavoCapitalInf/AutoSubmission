"""5.3 (2026-09-27): the D11 naming fixes: organisation cues by position, the legal-form cut, trailing connectors,
bank template prefixes, Truist's company field, wire beneficiaries and the printed 'NAME, CITY, ST' line.
Fabricated descriptors only, in each bank's printed format."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier import (
    UNIDENTIFIED_LENDER_OBLIGATION as UNIDENTIFIED,
    _canonical_unknown_entity,
    _unknown_payee_tokens,
    classify_statement_transactions,
)
from tests.flag_group_fixtures import txn

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")


def _name(printed: str) -> str | None:
    return _canonical_unknown_entity(normalize(printed))


# --- C5: cues by position, the legal-form cut, connectors, PAID and a leading AND --------------------------------

@pytest.mark.parametrize(
    ("printed", "name"),
    [
        # a legal form printed first is no cue; a name made only of cue words names no one
        ("ACH DEBIT CORP FABRIKAM CONSULT 0001", UNIDENTIFIED),
        ("BANK DEBIT", UNIDENTIFIED),
        # CO is Colorado's state code, never a cue (COMPANY stays one)
        ("Electronic Withdrawal To CO FAM SUPP REG", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING CO 0001", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING COMPANY 0001", "Fabricated Trading Company"),
        # the name ends at its first legal form after the first word
        ("FAB REVIEW INC PURCHASE", "Fab Review Inc"),
        ("ACH DEBIT FABRIKAM WIDGETS LLC INVOICES 0001", "Fabrikam Widgets LLC"),
        # a connector left by the four-word cap is dropped
        ("ACH DEBIT FABRIKAM NATIONAL A BANK OF OKLAHOMA 0001", "Fabrikam National Bank"),
        ("ACH DEBIT AND FAB FUNDING LLC", "Fab Funding LLC"),
        # multi-cue names keep every word up to the legal form
        ("ACH DEBIT FABRIKAM CAPITAL FUNDING LLC 0001", "Fabrikam Capital Funding LLC"),
    ],
)
def test_the_cue_rules_and_the_legal_form_cut(printed, name):
    assert _name(printed) == name


def test_paid_is_a_channel_word_not_part_of_the_payee():
    assert _unknown_payee_tokens(normalize("PAID TO - FAB CAPITAL GROUP 0001")) == ("FAB", "CAPITAL", "GROUP")
