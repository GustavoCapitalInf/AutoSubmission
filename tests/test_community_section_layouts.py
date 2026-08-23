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
    parse_community_section_statement,
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


# ===========================================================================
# The platform registered without an issuer (W3 §JHA-CELL)
# ===========================================================================
#
# Every fixture below is synthetic. The issuer domains are invented and the
# product names generic: what is pinned is the TEMPLATE's grammar, which is the
# only thing this registration is allowed to know.

PLATFORM_HEAD = (
    "Statement Ending 01/30/2026\n"
    "Online Access www.examplecommunitybank.com\n"
    "Summary of Accounts\n"
    "Account Type Account Number Ending Balance Business Checking XXXXXX1234 $105.00\n"
)

SIMPLE_BODY = (
    "Business Checking - XXXXXX1234\n"
    "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
    " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
    " 01/30/2026 Ending Balance $105.00\n"
    "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00\n"
    "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $5.00\n"
)


def test_the_platform_is_read_without_naming_the_issuer():
    """The whole point: an issuer this code has never seen is read anyway, and
    the bank published is the one the DOCUMENT printed."""
    stmt = parse_community_section_statement(PLATFORM_HEAD + SIMPLE_BODY)
    assert stmt is not None
    assert stmt.bank == "examplecommunitybank.com"
    assert stmt.account_name == "Business Checking"
    assert stmt.account_number == "XXXXXX1234"
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]
    assert reconcile(stmt).ok


NO_ISSUER = (
    "Statement Ending 01/30/2026\nSummary of Accounts\n"
    + SIMPLE_BODY.replace("BRANCH DEPOSIT", "PURCHASE AT WWW.EXAMPLE-MERCHANT.COM")
)


def test_a_document_that_names_no_issuer_publishes_an_absent_bank():
    """The honest-unknown-issuer ruling (Gustavo 2026-08-14, W3 §JHA J9.2).

    Five archive documents are on this template, reconcile against every
    figure their summary grid prints, and name no issuer. The reader used to
    refuse them outright. It now publishes them with `bank=None`: the ledger
    is a fact we checked, the issuer is a fact the document does not state,
    and reporting the second as absent is not a reason to withhold the first.
    """
    stmt = parse_community_section_statement(NO_ISSUER)
    assert stmt is not None
    assert stmt.bank is None
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]
    assert reconcile(stmt).ok


def test_the_absent_bank_is_never_filled_in_from_a_merchant_domain():
    """The trap this must not fall into, pinned as its own assertion.

    Four of the five real documents print MERCHANT domains in their
    transaction descriptions - `walmart.com`, `apple.com`, `gosq.com`. An
    unknown issuer must publish as nothing at all; "the first domain in the
    document" would publish the shop the customer bought lunch at as the bank.
    """
    stmt = parse_community_section_statement(NO_ISSUER)
    assert stmt is not None
    assert stmt.bank is None
    assert "MERCHANT" in stmt.transactions[0].description


def test_an_unknown_issuer_does_not_relax_the_arithmetic_gate():
    """`bank=None` is a statement about the ISSUER and about nothing else. A
    document that names no issuer AND does not reconcile is still refused."""
    broken = NO_ISSUER.replace("1 Credit(s) This Period $10.00",
                               "1 Credit(s) This Period $11.00")
    assert parse_community_section_statement(broken) is None


def test_the_issuer_is_read_from_the_masthead_not_from_a_cited_regulator():
    """A statement of this template cites its state banking regulator in the
    fine print below the ledger. That must not make the issuer unreadable, and
    must never resolve to the regulator."""
    md = (
        PLATFORM_HEAD + SIMPLE_BODY
        + "\nMEMBER NOTICE Website: www.example-regulator.gov\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.bank == "examplecommunitybank.com"


def test_a_label_ending_a_line_does_not_adopt_the_domain_on_the_next_one():
    """The adversarial review's construction, pinned.

    `_clean` collapses newlines, so a label word ending the holder's own
    address line and an unrelated domain beginning the next line became
    adjacent and were read as the issuer — this document published
    `bank='walmart.com'`. `Online` and `Visit` are ordinary words and the
    holder's address block is inside the masthead, so the LABEL alone was
    never the guard it was described as; the issuer's real contact block
    prints label and domain on ONE line, and that is now required.

    The property being pinned is that **`walmart.com` is not published as the
    bank**. It used to be pinned as `parse(...) is None`, because before the
    honest-unknown-issuer ruling a document with no readable issuer was
    refused outright, and the refusal was the only observable. It is now a
    document whose issuer is absent and whose ledger is published, so the
    assertion says what it always meant.
    """
    md = (
        "Statement Ending 01/30/2026\n"
        "ACME HOLDINGS LLC 123 MAIN ST SPRINGFIELD Visit\n"
        "walmart.com\n"
        "Summary of Accounts\n"
        "Account Type Account Number Ending Balance Business Checking XXXXXX1234 $105.00\n"
        + SIMPLE_BODY
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.bank is None


def test_the_issuer_is_still_read_when_such_a_line_break_is_present():
    """The control: the tightening must not cost a document whose issuer does
    print a proper contact line."""
    md = (
        "Statement Ending 01/30/2026\n"
        "ACME HOLDINGS LLC 123 MAIN ST SPRINGFIELD Visit\n"
        "walmart.com\n"
        "Online Access www.examplecommunitybank.com\n"
        "Summary of Accounts\n"
        "Account Type Account Number Ending Balance Business Checking XXXXXX1234 $105.00\n"
        + SIMPLE_BODY
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.bank == "examplecommunitybank.com"


def test_two_different_issuers_in_the_masthead_is_declined():
    """Still a refusal, and deliberately NOT the honest-unknown case above.

    Printing no issuer is a gap in the document; printing two labelled domains
    in the masthead is a gap in our reading of it - the likeliest cause is
    that `_MASTHEAD_END_RE` missed this layout's first account and the scope
    ran on into the fine print, where the state regulator is cited. Publishing
    `bank=None` there would file our own defect as the document's honest
    silence. No archive document is in this class (measured: 0 of 115), so
    there is nothing to prove a publication rule against either.
    """
    md = PLATFORM_HEAD.replace(
        "Online Access www.examplecommunitybank.com",
        "Online Access www.examplecommunitybank.com\nWebsite www.otherbank.com",
    ) + SIMPLE_BODY
    assert parse_community_section_statement(md) is None


def test_a_section_trailer_is_an_oracle_and_never_a_transaction_row():
    """`N item(s) totaling $X` carries no date, so it lands in the last row's
    chunk - and this reader takes the LAST money in a chunk. Left in place it
    republishes the section's total as that row's own amount."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 2 Credit(s) This Period $30.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $125.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00"
        " 01/03/2026 BRANCH DEPOSIT $20.00 2 item(s) totaling $30.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $5.00"
        " 1 item(s) totaling $5.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [10.0, 20.0, -5.0]
    assert reconcile(stmt).ok


def test_a_section_trailer_that_disagrees_with_the_rows_refuses_the_document():
    """The only PER-SECTION oracle this platform prints. The summary grid
    checks a whole direction, so a row lost inside one section of the right
    direction is invisible to it and visible here."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 2 Credit(s) This Period $30.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $125.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00"
        " 01/03/2026 BRANCH DEPOSIT $20.00 3 item(s) totaling $30.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $5.00\n"
    )
    assert parse_community_section_statement(md) is None


def test_a_trailer_is_matched_against_the_whole_section_it_closes():
    """A page break reprints the header as `(continued)`, but the trailer is
    printed once and counts every row of the section."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 2 Credit(s) This Period $30.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $125.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00\n"
        "Deposits (continued) Date Description Amount 01/03/2026 BRANCH DEPOSIT $20.00"
        " 2 item(s) totaling $30.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $5.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [10.0, 20.0, -5.0]


def test_a_trailer_less_section_is_not_folded_into_its_neighbour():
    """The adversarial review's second construction, pinned.

    The accumulator that lets a page-broken section be compared as one section
    also carried a trailer-LESS section's rows into the next section's
    comparison. Here `Deposits` prints no trailer and `Other Debits` prints
    one for its single row; folding the deposit in made the debit trailer read
    as 2-vs-1 and refused a sound document. A false refusal is still a bug.
    """
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $5.00"
        " 1 item(s) totaling $5.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]


def test_the_reset_still_catches_a_row_missing_from_the_trailered_section():
    """The control for the reset: it must not have turned the oracle off.

    Same shape as above, but the debit section's trailer counts two items and
    only one is printed — the section really does disagree with itself, and
    the document must still be refused."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $5.00"
        " 2 item(s) totaling $5.00\n"
    )
    assert parse_community_section_statement(md) is None


def test_sub_layout_j_b_is_read_from_its_running_balance():
    """The other arrangement: one `Account Activity` ledger, where a row's
    direction is the direction its balance moved."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $105.00\n"
        "Account Activity\n"
        "Post Date Description Debits Credits Balance\n"
        "01/01/2026 Beginning Balance $100.00\n"
        "01/02/2026 INCOMING ACH $10.00 $110.00\n"
        "01/03/2026 SERVICE CHARGE $5.00 $105.00\n"
        "Daily Balances Date Amount 01/03/2026 $105.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert [(t.amount, t.direction) for t in stmt.transactions] == [
        (10.0, "credit"), (-5.0, "debit"),
    ]
    assert reconcile(stmt).ok


def test_a_j_b_ledger_whose_balance_chain_does_not_close_is_refused():
    """The chain IS the direction evidence here, so a broken chain must not be
    published with a guessed sign."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 1 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $105.00\n"
        "Account Activity\n"
        "Post Date Description Debits Credits Balance\n"
        "01/01/2026 Beginning Balance $100.00\n"
        "01/02/2026 INCOMING ACH $10.00 $999.00\n"
        "01/03/2026 SERVICE CHARGE $5.00 $105.00\n"
    )
    assert parse_community_section_statement(md) is None


def test_a_cheque_row_does_not_mask_a_j_b_ledger():
    """Both arrangements print `Checks Cleared`. Choosing the body reader by
    "did we capture anything at all" let one cheque row hide a whole ledger -
    the defect eleven archive documents had."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 1 Credit(s) This Period $10.00 2 Debit(s) This Period $25.00"
        " 01/30/2026 Ending Balance $85.00\n"
        "Account Activity\n"
        "Post Date Description Debits Credits Balance\n"
        "01/01/2026 Beginning Balance $100.00\n"
        "01/02/2026 INCOMING ACH $10.00 $110.00\n"
        "01/03/2026 Check 1001 $20.00 $90.00\n"
        "01/04/2026 SERVICE CHARGE $5.00 $85.00\n"
        "Checks Cleared Check Nbr Date Amount 1001 01/03/2026 $20.00\n"
        "Daily Balances Date Amount 01/04/2026 $85.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    # Three rows, not four: the cheque is published once, from the ledger.
    assert [t.amount for t in stmt.transactions] == [10.0, -20.0, -5.0]
    assert reconcile(stmt).ok


def test_a_zero_amount_row_is_counted_in_the_column_the_bank_printed_it_in():
    """The platform posts a returned ACH of $0.00 and counts it as a credit. A
    sign-keyed count sees it on neither side and rejects a complete ledger."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $100.00"
        " 2 Credit(s) This Period $10.00 1 Debit(s) This Period $5.00"
        " 01/30/2026 Ending Balance $105.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00"
        " 01/03/2026 ACH ORIG RETURN $0.00\n"
        "Other Debits Date Description Amount 01/04/2026 SERVICE CHARGE $5.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.stated_credit_count == 2
    assert [t.amount for t in stmt.transactions] == [10.0, 0.0, -5.0]
    assert [t.direction for t in stmt.transactions] == ["credit", "credit", "debit"]


def test_a_second_account_with_activity_is_refused_rather_than_half_published():
    """L-1: the schema holds ONE account. Publishing the busiest of two active
    accounts would report a subset of the customer's money as though it were
    all of it."""
    md = PLATFORM_HEAD + SIMPLE_BODY + (
        "Business Savings - XXXXXX5678\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $50.00"
        " 1 Credit(s) This Period $1.00 0 Debit(s) This Period $0.00"
        " 01/30/2026 Ending Balance $51.00\n"
        "Other Credits Date Description Amount 01/05/2026 DIVIDEND $1.00\n"
    )
    assert parse_community_section_statement(md) is None


def test_a_dormant_second_account_does_not_block_the_one_that_posted():
    """The same credit unions print a membership share that never moves."""
    md = PLATFORM_HEAD + (
        "Business Ownership - XXXXXX5678\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Balance $5.00"
        " 0 Credit(s) This Period $0.00 0 Debit(s) This Period $0.00"
        " 01/30/2026 Ending Balance $5.00\n"
    ) + SIMPLE_BODY
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.account_number == "XXXXXX1234"
    assert [t.amount for t in stmt.transactions] == [10.0, -5.0]


def test_the_two_column_summary_interleaves_statistics_between_its_rows():
    """`Minimum Balance` and `Average Ledger Balance` are balances by name, and
    are excluded because they carry no DATE - the platform's own rule, not a
    list of their names."""
    md = PLATFORM_HEAD + (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount\n"
        "01/01/2026 Balance Last Statement $100.00 Minimum Balance $80.00"
        " 1 Credit(s) This Period $10.00 Average Ledger Balance $95.00\n"
        "1 Debit(s) This Period $5.00 Average Available Balance $93.00\n"
        "01/30/2026 Balance This Statement $105.00\n"
        "Deposits Date Description Amount 01/02/2026 BRANCH DEPOSIT $10.00\n"
        "Other Debits Date Description Amount 01/03/2026 SERVICE CHARGE $5.00\n"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.beginning_balance == 100.0
    assert stmt.ending_balance == 105.0
    assert reconcile(stmt).ok


def test_a_printed_minus_on_the_debit_total_is_a_direction_not_a_negative_total():
    """One archive document prints `106 Debit(s) This Period -$372,804.35`, and
    its summary identity closes on the MAGNITUDE."""
    md = PLATFORM_HEAD + SIMPLE_BODY.replace(
        "1 Debit(s) This Period $5.00", "1 Debit(s) This Period -$5.00"
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.stated_total_debits == 5.0
    assert reconcile(stmt).ok


def test_a_printed_minus_on_the_credit_total_still_refuses_the_summary():
    """A credit total that reduced the balance contradicts the row it is
    printed on. Widening the debit row must not widen this one."""
    md = PLATFORM_HEAD + SIMPLE_BODY.replace(
        "1 Credit(s) This Period $10.00", "1 Credit(s) This Period -$10.00"
    )
    assert parse_community_section_statement(md) is None


def test_the_account_name_published_is_the_product_the_document_printed():
    """Not a constant in the parser, and not the page furniture printed just
    before the heading - four documents published an account name of
    `tal Statement Ending 01/31/2026 Business Checking` before the heading
    grammar was written as a token sequence."""
    md = (
        "Statement Ending 01/30/2026\n"
        "Online Access www.examplecommunitybank.com\n"
        "Summary of Accounts\n"
        "Account Type Account Number Ending Balance\n"
        "Total Current Value $105.00 Statement Ending 01/30/2026\n"
        + SIMPLE_BODY.replace("Business Checking - XXXXXX1234",
                              "COMM BUS CHCKING - XXXXXX1234")
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.account_name == "COMM BUS CHCKING"


def test_an_account_number_is_not_absorbed_into_the_product_name():
    md = PLATFORM_HEAD.replace(
        "Business Checking XXXXXX1234 $105.00",
        "Business Checking XXXXXX1234 $105.00 XXXXXX6909",
    ) + SIMPLE_BODY
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.account_name == "Business Checking"


def test_a_joint_owner_line_between_the_heading_and_the_grid_is_stepped_over():
    md = PLATFORM_HEAD + SIMPLE_BODY.replace(
        "Business Checking - XXXXXX1234\n",
        "Business Checking - XXXXXX1234 Joint Owner -A Person;Joint Owner -B Person\n",
    )
    stmt = parse_community_section_statement(md)
    assert stmt is not None
    assert stmt.account_name == "Business Checking"
    assert stmt.account_number == "XXXXXX1234"


# ---- the printed `Daily Balances` grid (W3 §WITHHELDGRIDS) -------------------

_DISCLOSURE = (
    "DAILY BALANCE METHOD (including current transactions) To get daily balances,"
    " we take the beginning balance of your account each day, add any new loans"
    " and subtract any payments or credits.\n"
)


def _with_grid(*, grid: str, disclosure_first: bool) -> str:
    ledger = (
        "Business Interest Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $300.00 1 Debit(s) This Period $250.00"
        " 01/03/2026 Ending Statement Balance $150.00\n"
        "Electronic Credits Date Description Amount 01/02/2026 A CREDIT $300.00\n"
        "Other Debits Date Description Amount 01/03/2026 A DEBIT $250.00\n"
    )
    block = "Daily Balances\nDate Amount " + grid + "\n" + "Overdraft and Returned Item Fees Total for this period\n"
    return _mv((_DISCLOSURE + ledger + block) if disclosure_first else (ledger + block + _DISCLOSURE))


def test_the_grid_and_the_method_disclosure_are_not_confused():
    """The words `daily balances` also open the platform's METHOD paragraph,
    which on most of these documents is printed BEFORE the grid.

    Measured over all nine archive documents on this template: anchoring the
    region on the grid's own printed header instead of on those two words
    changes the grid on NONE of them, because the grid is the last thing in
    the region either way. The anchor was written, measured, and removed; what
    this pins is the outcome that matters — the disclosure contributes no day.
    """
    stmt = parse_mission_valley_statement(
        _with_grid(grid="01/02/2026 $400.00 01/03/2026 $150.00", disclosure_first=True)
    )
    assert stmt is not None
    printed = {t.date: t.running_balance for t in stmt.transactions}
    assert printed == {"2026-01-02": 400.0, "2026-01-03": 150.0}


def test_an_overdrawn_day_is_read_from_the_grid_with_its_sign():
    """This platform prints an overdrawn day `-$1,234.56`. The minus sits
    between the date and the `$`, so an unsigned pattern does not lose the
    sign — the pair does not match and the DAY is dropped from the grid."""
    stmt = parse_mission_valley_statement(
        _with_grid(grid="01/02/2026 -$400.00 01/03/2026 $150.00", disclosure_first=True)
    )
    assert stmt is not None
    printed = {t.date: t.running_balance for t in stmt.transactions}
    assert printed == {"2026-01-02": -400.0, "2026-01-03": 150.0}


def test_a_document_that_prints_no_grid_publishes_no_printed_balances():
    """The header anchor is required, not optional: a statement without the
    grid must not acquire one from the disclosure paragraph."""
    md = _mv(
        _DISCLOSURE
        + "Business Interest Checking - XXXXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2026 Beginning Statement Balance $100.00"
        " 1 Credit(s) This Period $300.00 1 Debit(s) This Period $250.00"
        " 01/03/2026 Ending Statement Balance $150.00\n"
        "Electronic Credits Date Description Amount 01/02/2026 A CREDIT $300.00\n"
        "Other Debits Date Description Amount 01/03/2026 A DEBIT $250.00\n"
    )
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert all(t.running_balance is None for t in stmt.transactions)
