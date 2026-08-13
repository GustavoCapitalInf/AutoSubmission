"""Layout tests for the `community_section` core-processor template.

This platform is a core processor's, not a bank's: Mission Valley Bank and
Dakota West Credit Union already print it and it recurs under other issuers'
names. These tests pin the two things that make the reader a *platform*
reader rather than a per-product one:

* a transaction section is classified by the **head noun of its printed
  name** ("... Credits" / "... Debits" / "Deposits"), so a qualifier this
  code has never seen is still read correctly, and
* the balances the platform prints with a sign are read with their sign.

Every fixture here is synthetic. No customer, account, amount or date from
the archive appears in this file.
"""
from __future__ import annotations

import pytest

from analysis.community_section import (
    parse_dakota_west_statement,
    parse_mission_valley_statement,
)
from analysis.reconcile import reconcile

MV_FURNITURE = (
    "Online Banking www.missionvalleybank.com\n"
    "Thank you for choosing Mission Valley Bank as your financial partner.\n"
)


def _mv(body: str) -> str:
    return MV_FURNITURE + body


def test_electronic_credits_is_a_credit_section_without_a_deposits_section():
    """The defect §C6.4 filed as "one product out of four".

    A statement whose only credit section is `Electronic Credits` used to read
    zero credits: the reader's credit headers were `Deposits` and
    `Other Credits`, and `Electronic Credits` rows were picked up only as a
    side effect of a `Deposits` section running on past them. With no
    `Deposits` section printed there was nothing to run past.
    """
    md = _mv(
        "Business Interest Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 2 Credit(s) This Period $300.00 1 Debit(s) This Period $50.00"
        " 01/30/2026 Ending Statement Balance $350.00\n"
        "Electronic Credits Date Description Amount"
        " 01/02/2026 CARD SETTLEMENT BATCH $120.00"
        " 01/03/2026 CARD SETTLEMENT BATCH $180.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $50.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert stmt.stated_credit_count == 2
    assert [t.amount for t in stmt.transactions] == [120.0, 180.0, -50.0]
    assert reconcile(stmt).ok


def test_a_qualifier_the_reader_has_never_seen_is_still_read_by_its_head_noun():
    """The capability, not the bank: section naming is a structural rule.

    `ATM Credits` and `Wire Debits` appear nowhere in the archive and nowhere
    in the parser. They are read because the platform's grammar is
    "<qualifier> <direction noun>" followed by the printed grid header.
    """
    md = _mv(
        "Business Analyzed Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $75.00 1 Debit(s) This Period $25.00"
        " 01/30/2026 Ending Statement Balance $150.00\n"
        "ATM Credits Date Description Amount 01/02/2026 ATM DEPOSIT $75.00\n"
        "Wire Debits Date Description Amount 01/03/2026 OUTGOING WIRE $25.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [75.0, -25.0]
    assert reconcile(stmt).ok


def test_account_summary_prints_the_same_grid_header_and_is_not_a_transaction_section():
    """`Account Summary Date Description Amount` uses the identical grid.

    It is excluded structurally - "Summary" is not a direction noun - rather
    than by naming it in a stop list.
    """
    md = _mv(
        "Business Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Statement Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 MERCHANT CAPTURE DEPOSIT $10.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $5.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    # The three summary rows carry dates and amounts; none of them is a txn.
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]
    assert reconcile(stmt).ok


def test_a_credit_section_stops_at_the_next_section_rather_than_running_into_it():
    """Sections are delimited by the next printed section header.

    The rows must land in the section that printed them, so a credit section
    followed immediately by a debit section cannot absorb the debit rows.
    """
    md = _mv(
        "Business Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $60.00 2 Debit(s) This Period $30.00"
        " 01/30/2026 Ending Statement Balance $130.00\n"
        "Electronic Credits Date Description Amount 01/02/2026 INCOMING ACH $60.00\n"
        "Electronic Debits Date Description Amount 01/03/2026 VENDOR ACH $20.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $10.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert [(t.amount, t.direction) for t in stmt.transactions] == [
        (60.0, "credit"), (-20.0, "debit"), (-10.0, "debit"),
    ]
    assert reconcile(stmt).ok


def test_a_continued_section_reprint_keeps_its_direction():
    """`(continued)` reprints across a page break are the same section."""
    md = _mv(
        "Business Analyzed Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 2 Credit(s) This Period $90.00 1 Debit(s) This Period $40.00"
        " 01/30/2026 Ending Statement Balance $150.00\n"
        "Electronic Credits Date Description Amount 01/02/2026 INCOMING ACH $50.00\n"
        "Electronic Credits (continued) Date Description Amount 01/03/2026 INCOMING ACH $40.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $40.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [50.0, 40.0, -40.0]
    assert reconcile(stmt).ok


def test_a_reprint_marker_survives_the_page_break_that_produced_it():
    """`(continued)` exists *because* of a page break, so the whitespace
    around it is whatever the break left behind - including a newline."""
    md = _mv(
        "Business Analyzed Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 2 Credit(s) This Period $90.00 1 Debit(s) This Period $40.00"
        " 01/30/2026 Ending Statement Balance $150.00\n"
        "Electronic Credits Date Description Amount 01/02/2026 INCOMING ACH $50.00\n"
        "--- Page 2 ---\n"
        "Business Analyzed Checking - XXXXXXXX1234 (continued)\n"
        "Electronic Credits\n(continued)\nDate Description Amount 01/03/2026 INCOMING ACH $40.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $40.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [50.0, 40.0, -40.0]
    assert reconcile(stmt).ok


def test_an_overdrawn_period_prints_its_balances_with_a_sign():
    """§C6.1's defect class in this parser.

    The summary's balance rows are the only figures this platform prints with
    a sign. The period's credit and debit totals stay magnitudes.
    """
    md = _mv(
        "Business Analyzed Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance -$25.00"
        " 1 Credit(s) This Period $100.00 1 Debit(s) This Period $50.00"
        " 01/30/2026 Ending Statement Balance $25.00\n"
        "Deposits Date Description Amount 01/02/2026 MERCHANT CAPTURE DEPOSIT $100.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $50.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert stmt.beginning_balance == -25.0
    assert stmt.ending_balance == 25.0
    assert reconcile(stmt).ok


def test_an_overdrawn_closing_balance_is_read_with_its_sign():
    md = _mv(
        "Business Analyzed Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $25.00"
        " 1 Credit(s) This Period $50.00 1 Debit(s) This Period $100.00"
        " 01/30/2026 Ending Statement Balance -$25.00\n"
        "Deposits Date Description Amount 01/02/2026 MERCHANT CAPTURE DEPOSIT $50.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $100.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert stmt.beginning_balance == 25.0
    assert stmt.ending_balance == -25.0
    assert reconcile(stmt).ok


def test_the_totals_are_magnitudes_and_a_signed_total_is_not_invented():
    """A defensive pin: widening the balance pattern must not widen the
    totals. If a total ever printed a sign the summary should not match at
    all rather than silently read a negative period total."""
    md = _mv(
        "Business Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period -$10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Statement Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 MERCHANT CAPTURE DEPOSIT $10.00\n"
    )
    assert parse_mission_valley_statement(md) is None


def test_dakota_west_still_selects_the_busiest_account_section():
    """The other issuer on this template keeps its primary-account semantics."""
    md = (
        "Thank you for being a member of Dakota West Credit Union.\n"
        "Website dakotawestcu.com\n"
        "Badlands Savings - 35127372\n"
        "Account Summary Date Description Amount 11/01/2025 Beginning Balance $10.00"
        " 1 Credit(s) This Period $5.00 0 Debit(s) This Period $0.00"
        " 11/30/2025 Ending Balance $15.00\n"
        "Other Credits Date Description Amount 11/04/2025 DIVIDEND $5.00\n"
        "Small Business Checking - 35127380\n"
        "Account Summary Date Description Amount 11/01/2025 Beginning Balance $100.00"
        " 1 Credit(s) This Period $500.00 2 Debit(s) This Period $125.00"
        " 11/30/2025 Ending Balance $475.00\n"
        "Electronic Credits Date Description Amount 11/04/2025 EXTERNAL DEPOSIT ACH $500.00\n"
        "Other Debits Date Description Amount 11/05/2025 POS PURCHASE $25.00"
        " 11/06/2025 EXTERNAL WITHDRAWAL $100.00\n"
    )
    stmt = parse_dakota_west_statement(md)
    assert stmt is not None
    assert stmt.account_name == "Small Business Checking"
    assert stmt.account_number == "35127380"
    assert [t.amount for t in stmt.transactions] == [500.0, -25.0, -100.0]
    assert reconcile(stmt).ok


@pytest.mark.parametrize("noun", ["Credits", "Debits", "Deposits"])
def test_a_direction_noun_inside_a_longer_word_is_not_a_section_header(noun: str):
    """`(?<![A-Za-z])` keeps the head-noun rule from firing mid-word."""
    md = _mv(
        "Business Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Statement Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 MERCHANT CAPTURE DEPOSIT $10.00\n"
        f"Other Debits Date Description Amount 01/03/2026 XX{noun} Date Description Amount FEE $5.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]
