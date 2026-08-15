"""W3 §SCANB — the second core processor's SECTIONED template.

The registration reads a TEMPLATE and names no bank, so the tests that matter
are the ones that prove the two halves of that claim separately:

* what the reader publishes is what the document printed, and every printed
  figure has to agree before anything is published — so each test below breaks
  exactly one of the five printings and asserts a REFUSAL. A reader whose gates
  are decorative passes the happy path and fails all of these;
* the issuer is read out of the masthead, and the merchant domains and
  counterparty bank names in the ledger below it are out of range.

The base document is modelled on the archive's layout with invented figures.
Every mutation of it is a one-line edit, so a test that fails names the rule
it broke.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.core_processor_sectioned import (
    _CREDITS_RE,
    _counts,
    detect,
    parse_core_processor_sectioned_statement as parse,
)

MASTHEAD = (
    "FIRST EXAMPLE BANK, N.A. 101 00031 O1 PAGE: 1\n"
    "P O BOX 1 ACCOUNT: XXXXXXXXXX4321 03/31/2026\n"
    "EXAMPLETOWN ST 00001\n"
    "TELEPHONE: 800-000-0000\n"
    "HOLDER COMPANY LLC 30\n"
    "1 MAIN ST 3\n"
    "EXAMPLETOWN ST 00001\n"
)
SUMMARY = (
    "BUSINESS CHECKING ACCOUNT XXXXXXXXXX4321\n"
    "LAST STATEMENT 02/28/26 1,000.00 MINIMUM BALANCE 900.00 "
    "2 CREDITS 1,500.00 AVG AVAILABLE BALANCE 1,400.00 "
    "2 DEBITS 600.00 AVERAGE BALANCE 1,450.00 THIS STATEMENT 03/31/26 1,900.00\n"
    "TOTAL DAYS IN STATEMENT PERIOD 03/01/26 THROUGH 03/31/26: 31\n"
)
LEDGER = (
    "DEPOSITS REF # DATE AMOUNT REF # DATE AMOUNT\n"
    "03/05 1,000.00\n"
    "OTHER CREDITS DESCRIPTION DATE AMOUNT INCOMING WIRE ACME LLC 03/10 500.00\n"
    "CHECKS CHECK # DATE AMOUNT CHECK # DATE AMOUNT\n"
    "1001 03/12 100.00\n"
    "OTHER DEBITS DESCRIPTION DATE AMOUNT CARD PURCHASE HARDWARE CO 03/20 500.00\n"
    "DAILY BALANCE DATE BALANCE DATE BALANCE\n"
    "03/05 2,000.00 03/10 2,500.00 03/12 2,400.00 03/20 1,900.00\n"
)
DOCUMENT = MASTHEAD + SUMMARY + LEDGER


def swap(original: str, replacement: str, document: str = DOCUMENT) -> str:
    """One printed thing changed, and exactly one."""
    assert document.count(original) == 1, f"{original!r} is not unique in the document"
    return document.replace(original, replacement)


# ===========================================================================
# What the document says, published as it says it
# ===========================================================================

def test_the_published_statement_is_the_one_the_document_printed():
    statement = parse(DOCUMENT)
    assert statement is not None
    assert statement.bank == "FIRST EXAMPLE BANK, N.A."
    assert statement.account_name == "BUSINESS CHECKING"
    assert statement.account_number == "XXXXXXXXXX4321"
    assert (statement.period_start, statement.period_end) == ("2026-03-01", "2026-03-31")
    assert statement.days_in_period == 31
    assert (statement.beginning_balance, statement.ending_balance) == (1000.0, 1900.0)
    assert (statement.stated_credit_count, statement.stated_total_credits) == (2, 1500.0)
    assert (statement.stated_debit_count, statement.stated_total_debits) == (2, 600.0)
    assert statement.stated_average_balance == 1450.0


def test_every_row_carries_the_direction_of_the_section_it_was_printed_in():
    """The COLUMN the bank printed the row in, never the sign of the amount."""
    rows = {(row.date, row.description): (row.direction, row.amount)
            for row in parse(DOCUMENT).transactions}
    assert rows[("2026-03-05", "Deposit")] == ("credit", 1000.0)
    assert rows[("2026-03-10", "INCOMING WIRE ACME LLC")] == ("credit", 500.0)
    assert rows[("2026-03-12", "Check 1001")] == ("debit", -100.0)
    assert rows[("2026-03-20", "CARD PURCHASE HARDWARE CO")] == ("debit", -500.0)


def test_the_printed_daily_balance_grid_is_published_as_evidence():
    printed = [(entry.date, entry.balance) for entry in parse(DOCUMENT).stated_daily_balances]
    assert printed == [
        ("2026-03-05", 2000.0), ("2026-03-10", 2500.0),
        ("2026-03-12", 2400.0), ("2026-03-20", 1900.0),
    ]


def test_a_cheque_the_platform_printed_no_serial_for_is_still_a_row():
    """The platform prints a cheque it holds no serial for as a bare pair, and
    a reader that requires the serial loses the row and the count with it."""
    statement = parse(swap("1001 03/12 100.00", "03/12 100.00"))
    assert statement is not None
    assert [row.description for row in statement.transactions if row.amount == -100.0] == ["Check"]


def test_a_sub_dollar_row_is_read_from_the_bare_cents_the_platform_prints():
    """This platform prints an amount below a dollar without its leading zero,
    in the ledger as well as in the summary."""
    document = swap("CARD PURCHASE HARDWARE CO 03/20 500.00", "CARD PURCHASE HARDWARE CO 03/20 .50")
    document = swap("2 DEBITS 600.00", "2 DEBITS 100.50", document)
    document = swap("THIS STATEMENT 03/31/26 1,900.00", "THIS STATEMENT 03/31/26 2,399.50", document)
    document = swap("03/20 1,900.00\n", "03/20 2,399.50\n", document)
    statement = parse(document)
    assert statement is not None
    assert [row.amount for row in statement.transactions if row.date == "2026-03-20"] == [-0.5]


def test_the_continued_marker_and_the_column_header_are_not_a_description():
    """A section broken across a page reprints its heading, its `(continued)`
    marker and its column header; none of the three is what the bank printed
    about the row that follows them."""
    document = swap(
        "OTHER DEBITS DESCRIPTION DATE AMOUNT CARD PURCHASE HARDWARE CO 03/20 500.00\n",
        "OTHER DEBITS DESCRIPTION DATE AMOUNT\n"
        "--- Page 2 ---\n"
        "FIRST EXAMPLE BANK, N.A. 101 00031 O1 PAGE: 2\n"
        "HOLDER COMPANY LLC\n"
        "OTHER DEBITS (continued) DESCRIPTION DATE AMOUNT "
        "CARD PURCHASE HARDWARE CO 03/20 500.00\n",
    )
    statement = parse(document)
    assert statement is not None
    assert [row.description for row in statement.transactions if row.amount == -500.0] == [
        "CARD PURCHASE HARDWARE CO"
    ]


# ===========================================================================
# The issuer, read out of the masthead and nowhere else
# ===========================================================================

def test_a_counterparty_in_the_ledger_is_not_published_as_the_issuer():
    """The generalised form of the §JHA issuer lesson: the names and domains
    below the masthead belong to whoever the holder paid."""
    document = swap(
        "CARD PURCHASE HARDWARE CO 03/20 500.00",
        "ACH DEBIT SECOND EXAMPLE BANK amazon.com 03/20 500.00",
    )
    assert parse(document).bank == "FIRST EXAMPLE BANK, N.A."


def test_a_masthead_that_opens_with_a_header_field_names_no_issuer():
    """Several issuers on this template print their name only inside the logo,
    which is an image, so the text layer opens on the folio instead. A label is
    furniture, not a bank — and this document carries the contact block, so the
    LABEL rule is the only thing refusing it.

    `bank=None` is the honest answer and the arithmetic does not depend on it:
    an unnamed issuer costs a label, not a document."""
    document = (
        "Statement Date: 03/31/2026\nPrimary Account: XXXXXXXXXX4321\n"
        "TELEPHONE: 800-000-0000\n"
        + SUMMARY + LEDGER
    )
    statement = parse(document)
    assert statement is not None
    assert statement.bank is None
    assert statement.ending_balance == 1900.0


def test_a_contact_block_in_the_small_print_does_not_corroborate_the_top_line():
    """The masthead SCOPE, isolated. The name at the top of this page has no
    contact block under it; the only telephone number on the statement is in
    the fine print at the foot, beside somebody else's disclosure. Read over
    the whole document that number would corroborate the top line."""
    document = (
        "SECOND EXAMPLE BANK 000 00002 PAGE: 1\n"
        + SUMMARY + LEDGER
        + "FOR CLAIMS UNDER THE CARD NETWORK RULES TELEPHONE: 800-111-1111\n"
    )
    statement = parse(document)
    assert statement is not None
    assert statement.bank is None


def test_the_issuer_name_stops_at_the_platforms_own_routing_codes():
    assert parse(swap("101 00031 O1 PAGE: 1", "999 00002 O7 PAGE: 1")).bank == (
        "FIRST EXAMPLE BANK, N.A."
    )


def test_the_page_separator_the_ocr_layer_inserts_is_not_printed_text():
    """The markdown the pipeline builds opens with `--- Page 1 ---`. It is our
    own separator, not something the bank printed, and a reader that took it
    for the first printed line would find no issuer on any document."""
    document = "--- Page 1 ---\n\n" + DOCUMENT
    assert parse(document).bank == "FIRST EXAMPLE BANK, N.A."


def test_the_contact_block_is_what_makes_the_top_line_an_issuer():
    """Without the platform's own contact furniture the run of words at the top
    of the page is not evidence of anything, and no name is published."""
    document = swap("TELEPHONE: 800-000-0000\n", "")
    statement = parse(document)
    assert statement is not None
    assert statement.bank is None


# ===========================================================================
# The five printings, broken one at a time
# ===========================================================================

def test_a_dropped_row_is_caught_by_the_printed_count():
    assert parse(swap("03/05 1,000.00\n", "\n")) is None


def test_a_duplicated_row_is_caught_by_the_printed_count():
    assert parse(swap("1001 03/12 100.00\n", "1001 03/12 100.00\n1002 03/12 100.00\n")) is None


def test_a_mis_read_amount_is_caught_by_the_printed_total_even_when_the_count_holds():
    """The count check cannot see this one: the row is there, its amount is
    not what the bank printed. This is the archive's commonest scanned defect
    and the reason the totals are checked as well as the counts."""
    document = swap("03/05 1,000.00\n", "03/05 1,060.00\n")
    document = swap("03/05 2,000.00", "03/05 2,060.00", document)
    document = swap("03/10 2,500.00", "03/10 2,560.00", document)
    document = swap("03/12 2,400.00", "03/12 2,460.00", document)
    document = swap("03/20 1,900.00\n", "03/20 1,960.00\n", document)
    assert parse(document) is None


def test_a_summary_that_contradicts_itself_publishes_nothing():
    """`opening + credits - debits == closing` is the document's own identity,
    checked in the parser where it is cheap and local (§JHA J9.8)."""
    assert parse(swap("THIS STATEMENT 03/31/26 1,900.00", "THIS STATEMENT 03/31/26 1,901.00")) is None


def test_the_printed_daily_balance_grid_is_an_independent_second_opinion():
    """Every summary figure still holds; only the grid disagrees."""
    assert parse(swap("03/12 2,400.00", "03/12 2,401.00")) is None


def test_a_day_the_ledger_posts_on_must_appear_in_the_grid():
    """The other direction of the same check: a grid that is missing a day the
    ledger posted on cannot corroborate it."""
    assert parse(swap(" 03/12 2,400.00", "")) is None


def test_a_day_the_grid_prints_that_the_ledger_never_reached_is_refused():
    assert parse(swap("03/20 1,900.00\n", "03/20 1,900.00 03/25 1,900.00\n")) is None


# ===========================================================================
# Look-alike glyphs are refused, never absorbed
# ===========================================================================

def test_a_date_whose_leading_zero_ocr_read_as_a_letter_is_not_read_as_a_date():
    """The boundary rule, measured on the archive: without it the corrupted
    token matches one character in, as a single-digit month, and the row is
    published on a day the bank never printed. With it the row is invisible and
    the count check refuses the document — which is the honest outcome for a
    scan we cannot read."""
    assert parse(swap("1001 03/12 100.00", "1001 o3/12 100.00")) is None


def test_a_look_alike_digit_from_another_script_is_not_money():
    """`\\d` is Unicode-aware in Python and would admit these. Every figure in
    this reader is matched with an explicit ASCII class instead."""
    assert parse(swap("03/05 1,000.00\n", "03/05 1,00\N{DEVANAGARI DIGIT ZERO}.00\n")) is None


def test_a_look_alike_letter_inside_the_column_header_costs_the_section_not_the_truth():
    """One archive issuer prints `DATE` with a Cyrillic capital E in the column
    header. It is not evidence this reader consults, so it changes nothing —
    what the same corruption does to a DATE TOKEN is the test above."""
    document = swap("CHECKS CHECK # DATE AMOUNT", "CHECKS CHECK # DAT\N{CYRILLIC CAPITAL LETTER IE} AMOUNT")
    statement = parse(document)
    assert statement is not None
    assert len(statement.transactions) == 4


# ===========================================================================
# The summary strip
# ===========================================================================

def test_a_direction_with_no_items_prints_no_count_and_is_read_as_zero():
    document = DOCUMENT.replace("2 CREDITS 1,500.00", "CREDITS .00")
    document = swap("03/05 1,000.00\n", "\n", document)
    document = swap("OTHER CREDITS DESCRIPTION DATE AMOUNT INCOMING WIRE ACME LLC 03/10 500.00\n", "", document)
    document = swap("LAST STATEMENT 02/28/26 1,000.00", "LAST STATEMENT 02/28/26 2,500.00", document)
    document = swap("03/05 2,000.00 03/10 2,500.00 03/12 2,400.00 03/20 1,900.00",
                    "03/12 2,400.00 03/20 1,900.00", document)
    statement = parse(document)
    assert statement is not None
    assert (statement.stated_credit_count, statement.stated_total_credits) == (0, 0.0)
    assert [row.direction for row in statement.transactions] == ["debit", "debit"]


def test_a_count_the_scan_lost_from_a_non_zero_row_is_not_read_as_zero():
    """An absent count is admitted only against a zero total — the one case
    where "no count" and "no items" are the same statement about the document.
    Against a printed total it means the scan dropped the count, and reading
    that as zero would publish a ledger the bank contradicts.

    Asserted on the rule itself as well as through the document: the ledger
    gates would refuse this document anyway, and a test that only watched the
    document could not tell the rule from its neighbours."""
    assert _counts("2 CREDITS 1,500.00", _CREDITS_RE) == (2, 1500.0)
    assert _counts("CREDITS .00", _CREDITS_RE) == (0, 0.0)
    assert _counts("CREDITS 1,500.00", _CREDITS_RE) is None
    assert parse(swap("2 CREDITS 1,500.00", "CREDITS 1,500.00")) is None


def test_a_figure_that_lost_its_decimal_point_is_not_money():
    assert parse(swap("2 DEBITS 600.00", "2 DEBITS 600")) is None


def test_the_cents_of_the_figure_beside_a_label_are_not_read_as_its_count():
    """`MINIMUM BALANCE 900.00 2 CREDITS ...` — a count is a whole token, and
    the boundary is what stops `00` from being one."""
    statement = parse(DOCUMENT)
    assert statement.stated_credit_count == 2


def test_the_closing_balance_is_not_taken_from_the_disclosures_below_the_ledger():
    """The statement's own small print prints `THIS STATEMENT` again, in the
    sentence that asks the holder to compare it with their records."""
    document = DOCUMENT + (
        "IN CASE OF ERRORS OR QUESTIONS COMPARE THE AMOUNTS LISTED ON THIS STATEMENT "
        "03/31/26 9,999.99 WITH YOUR OWN RECORDS\n"
    )
    statement = parse(document)
    assert statement is not None
    assert statement.ending_balance == 1900.0


def test_a_summary_that_prints_its_closing_balance_twice_differently_is_refused():
    """No rule says which printing to believe, so there is no reading to
    publish. This is also what makes the strip's boundary above load-bearing:
    the disclosures print the same label again, and only the boundary keeps
    them from turning every statement into this."""
    document = swap(
        "THIS STATEMENT 03/31/26 1,900.00\n",
        "THIS STATEMENT 03/31/26 1,900.00 THIS STATEMENT 03/31/26 1,899.00\n",
    )
    assert parse(document) is None


def test_the_section_headings_are_the_ones_the_platform_printed_in_capitals():
    """Thirteen archive documents print a section's name in lower-case prose as
    well — the funds-availability notice says `deposits`, the interest
    disclosure says `average daily balance`. Case is the only thing that tells
    the heading from the sentence, and a case-insensitive split turns the
    sentence into a section whose contents become rows."""
    document = swap(
        "HOLDER COMPANY LLC 30\n",
        "HOLDER COMPANY LLC 30\n"
        "We have updated our funds availability policy so that more of your "
        "deposits clear sooner. Effective 03/25 1,000.00 of each cheque is now "
        "available the next business day.\n",
    )
    statement = parse(document)
    assert statement is not None
    assert len(statement.transactions) == 4


def test_the_account_name_cannot_begin_inside_the_figure_printed_before_it():
    """A regex matches leftmost-first and this heading is preceded on the page
    by figures (§JHA J4.5). A product name is a token sequence that must START
    with a word, so no token can be the tail of an amount."""
    document = swap(
        "BUSINESS CHECKING ACCOUNT XXXXXXXXXX4321",
        "AVAILABLE 1,034.78 BASIC BUSINESS CHECKING ACCOUNT XXXXXXXXXX4321",
    )
    assert parse(document).account_name == "BASIC BUSINESS CHECKING"


def test_a_statistic_is_not_a_balance_because_it_carries_no_date():
    """`MINIMUM BALANCE`, `AVG AVAILABLE BALANCE` and `AVERAGE BALANCE` are
    balances by name. What excludes them from being read as the period's
    opening or closing balance is structural and is the platform's own: a
    summary balance row carries the date it is a balance ON."""
    statement = parse(DOCUMENT)
    assert (statement.beginning_balance, statement.ending_balance) == (1000.0, 1900.0)
    assert statement.stated_average_balance == 1450.0


# ===========================================================================
# What this reader declines
# ===========================================================================

def test_a_document_with_no_ledger_section_is_not_a_statement():
    assert parse(MASTHEAD + SUMMARY) is None


def test_the_running_balance_issue_is_claimed_and_then_declined():
    """The other printed issue of the same template. It is the same platform on
    the same furniture, so detection claims it; its ledger is a running-balance
    grid this reader does not walk, so `parse` declines and the registration
    that does read it supersedes this one."""
    running = (
        "BUSINESS BASIC CHECKING ACCOUNT XXXXXXXXXX0947\n"
        "BALANCE LAST STATEMENT ... 02/28/26 1,000.00\n"
        "TOTAL CREDITS (2) 1,500.00 AVG AVAILABLE BALANCE 1,400.00\n"
        "TOTAL DEBITS (2) 600.00 AVERAGE BALANCE 1,450.00\n"
        "BALANCE THIS STATEMENT ... 03/31/26 1,900.00\n"
        "TOTAL DAYS IN STATEMENT PERIOD 03/01/26 THROUGH 03/31/26: 31\n"
    )
    assert detect(running).claims
    assert parse(running) is None


def test_an_unreadable_period_is_declined_rather_than_raised():
    """A raise inside `parse` is recorded as a crash of ours; this is a
    document we cannot read, and it has to be reported as one."""
    assert parse(swap("03/01/26 THROUGH", "13/45/26 THROUGH")) is None


def test_parse_re_checks_detection_and_never_trusts_the_caller():
    assert parse("a lease agreement, not a bank statement") is None


# ===========================================================================
# Detection
# ===========================================================================

def test_neither_marker_claims_on_its_own():
    assert not detect(
        "TOTAL DAYS IN STATEMENT PERIOD 03/01/26 THROUGH 03/31/26: 31\n"
    ).claims
    assert not detect(
        "LAST STATEMENT 02/28/26 1,000.00 THIS STATEMENT 03/31/26 1,900.00\n"
    ).claims


def test_the_period_statistic_corroborates_rather_than_gates():
    without = swap("AVG AVAILABLE BALANCE 1,400.00 ", "")
    assert detect(without).claims
    assert detect(without).score < detect(DOCUMENT).score


def test_the_period_line_needs_the_dates_the_template_prints():
    """`first_farmers`'s conformance fixture carries the label with no dates,
    and this registration must not reach it."""
    assert not detect(
        "WWW.FFBT.COM\nBUSINESS BASIC CHECKING ACCOUNT\n"
        "BALANCE LAST STATEMENT\nTOTAL DAYS IN STATEMENT PERIOD\n"
    ).claims


# ===========================================================================
# Dispatch
# ===========================================================================

def test_the_registration_claims_this_document_and_nothing_else_does():
    dispatch = pr.resolve(DOCUMENT)
    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "core_processor_sectioned"


def test_the_issuer_specific_reader_of_the_other_issue_wins_outright():
    """The supersedes edge, as dispatch sees it. Without it both registrations
    claim and the document resolves `ambiguous` — measured on all 7 of that
    issuer's archive documents, 6 of which publish today."""
    both = (
        "WWW.FFBT.COM\n"
        "BUSINESS BASIC CHECKING ACCOUNT XXXXXXXXXX0947\n"
        "BALANCE LAST STATEMENT ... 02/28/26 1,000.00\n"
        "BALANCE THIS STATEMENT ... 03/31/26 1,900.00\n"
        "TOTAL DAYS IN STATEMENT PERIOD 03/01/26 THROUGH 03/31/26: 31\n"
    )
    assert detect(both).claims
    assert pr.by_id("first_farmers").detect(both).claims
    assert pr.resolve(both).candidates == (("first_farmers", 0.5),)


@pytest.mark.parametrize("registration", pr.registrations(), ids=lambda r: r.id)
def test_no_other_registration_claims_this_template(registration):
    if registration.id == "core_processor_sectioned":
        return
    assert not registration.detect(DOCUMENT).claims
