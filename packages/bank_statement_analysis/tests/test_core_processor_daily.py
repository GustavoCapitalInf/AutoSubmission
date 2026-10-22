"""W3 §LCPERIOD — the third core processor's template, read generically.

Every document here is synthetic. The archive documents that motivated the
registration are named by content sha in the branch log and in the commit
message; none of them is reproduced, because a test that needs a real
statement to make its point is a test of that statement rather than of the
rule.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from analysis import b1, core_processor_daily as cpd, parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry

# ---------------------------------------------------------------------------
# One document of the template, in the pieces a test can vary
# ---------------------------------------------------------------------------

MASTHEAD = (
    "Last statement: March 31, 2054 This statement: April 30, 2054 "
    "Total days in statement period: 30\n"
    "HOLDER NAME 1 EXAMPLE ST EXAMPLETOWN XX 00000-0000\n"
    "Page 1 XXXXXX0000 ( 2)\n"
    "Direct inquiries to: 000-000-0000\n"
    "Example State Bank PO Box 1 Exampletown XX 00000\n"
)
PRODUCT = "Example Business Checking\n"
ACCOUNT = (
    "Account number XXXXXX0000 Enclosures 2 Low balance $50.00 "
    "Average balance $120.00\n"
)
SUMMARY = (
    "Beginning balance $100.00 Total additions 300.00 "
    "Total subtractions 250.00 Ending balance $150.00\n"
)
DEBITS = (
    "DEBITS\n"
    "Date Description Subtractions\n"
    "04-02 ' ACH Debit 250.00\n"
    "EXAMPLE VENDOR 260402\n"
)
CREDITS = (
    "CREDITS\n"
    "Date Description Additions\n"
    "04-03 ' Deposit 300.00\n"
)
GRID = (
    "DAILY BALANCES\n"
    "Date Amount\n"
    "03-31 100.00 04-02 -150.00 04-03 150.00\n"
)
FOOTER = "Thank you for banking with Example State Bank\n"


def document(*, masthead=MASTHEAD, product=PRODUCT, account=ACCOUNT,
             summary=SUMMARY, debits=DEBITS, credits=CREDITS, grid=GRID,
             footer=FOOTER) -> str:
    return masthead + product + account + summary + debits + credits + grid + footer


def parse(markdown: str):
    return cpd.parse_core_processor_daily_statement(markdown)


# ---------------------------------------------------------------------------
# Detection — the template's furniture, and the case that separates templates
# ---------------------------------------------------------------------------

def test_the_template_is_recognised_by_its_own_period_sentence():
    assert cpd.detect(document()).claims


def test_upper_casing_the_document_is_not_this_template():
    """Sentence case is what separates this template's period sentence from
    the SECOND core processor's upper-case period line. A normalization that
    folded case would make the two indistinguishable, so this registration
    deliberately declares none — pinned here rather than left to a reviewer to
    notice."""
    assert not cpd.detect(document().upper()).claims


def test_the_registration_declares_no_normalization():
    assert pr.by_id("core_processor_daily").normalize is None


@pytest.mark.parametrize("missing", ["Last statement:", "This statement:",
                                     "Total days in statement period:"])
def test_no_single_period_field_claims_on_its_own(missing):
    """Two required markers, so removing either field's contribution must
    withdraw the claim."""
    assert not cpd.detect(document().replace(missing, "Removed field")).claims


def test_the_page_and_account_fields_may_interleave_the_period_sentence():
    """One issuer's text layer prints the three period fields with the page
    and account fields between them. A contiguous pattern reads that document
    as printing no period at all."""
    interleaved = (
        "Last statement: March 31, 2054 Page 1 of 9\n"
        "This statement: April 30, 2054 XXXXXX0000\n"
        "Total days in statement period: 30\n"
    ) + MASTHEAD.split("\n", 1)[1]
    statement = parse(document(masthead=interleaved))
    assert statement is not None
    assert (statement.period_start, statement.period_end) == ("2054-04-01", "2054-04-30")


def test_a_title_case_period_line_of_another_platform_is_not_claimed():
    """Two archive documents print `Total Days in Statement Period 31` in
    title case with no colon, inside a `Statement Period Start:` layout. They
    are a different platform and this registration must not reach them."""
    other = (
        "Statement Period Start: May 1, 2054 Statement Period End: May 31, 2054\n"
        "Account Summary\n"
        "Beginning Balance as of 05/01/2054 $3,297.98 "
        "+ Deposits and Credits  (31) $80,351.88\n"
        "Total Days in Statement Period 31\n"
    )
    assert not cpd.detect(other).claims


# ---------------------------------------------------------------------------
# What one document publishes
# ---------------------------------------------------------------------------

def test_the_whole_statement_is_published_from_the_printed_figures():
    statement = parse(document())
    assert statement is not None
    assert statement.bank is None
    assert statement.account_name == "Example Business Checking"
    assert statement.account_number == "XXXXXX0000"
    assert statement.period_start == "2054-04-01"
    assert statement.period_end == "2054-04-30"
    assert statement.days_in_period == 30
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 150.00
    assert statement.stated_total_credits == 300.00
    assert statement.stated_total_debits == 250.00
    assert statement.stated_average_balance == 120.00
    assert [(row.date, row.amount, row.direction) for row in statement.transactions] == [
        ("2054-04-02", -250.00, "debit"),
        ("2054-04-03", 300.00, "credit"),
    ]


def test_the_period_opens_the_day_after_the_last_statement_closed():
    """The two dates the template prints are the dates of the two STATEMENTS.
    Reading them as the period's own endpoints would publish a period a day
    too long, and would put the grid's first cell outside it."""
    statement = parse(document())
    assert statement.period_start == "2054-04-01"  # not 2054-03-31


def test_the_printed_day_count_must_match_the_span_of_the_two_dates():
    off_by_one = MASTHEAD.replace("statement period: 30", "statement period: 31")
    assert parse(document(masthead=off_by_one)) is None


def test_the_pre_period_grid_cell_is_not_published_as_a_snapshot():
    """It is a real printing and it is used as a gate, but the field's
    contract is in-period snapshots and the ADB engine treats an out-of-period
    one as a defect of the statement."""
    statement = parse(document())
    assert [entry.date for entry in statement.stated_daily_balances] == [
        "2054-04-02", "2054-04-03",
    ]


def test_a_sub_dollar_balance_is_read_rather_than_refused():
    """The platform prints a zero closing balance as `$.00`."""
    zeroed = (
        "Beginning balance $250.00 Total additions 0.00 "
        "Total subtractions 250.00 Ending balance $.00\n"
    )
    grid = "DAILY BALANCES\nDate Amount\n03-31 250.00 04-02 .00\n"
    statement = parse(document(summary=zeroed, credits="", grid=grid))
    assert statement is not None
    assert statement.ending_balance == 0.00


# ---------------------------------------------------------------------------
# The gates — each refuses on its own
# ---------------------------------------------------------------------------

def test_a_credit_total_the_ledger_does_not_reproduce_refuses():
    """The summary is rewritten so that its OWN identity still closes and the
    grid still walks: only the credit total is wrong. A test that merely
    changes one figure is caught by the identity gate instead, and proves
    nothing about this one."""
    consistent = (
        "Beginning balance $100.00 Total additions 400.00 "
        "Total subtractions 250.00 Ending balance $250.00\n"
    )
    assert parse(document(summary=consistent)) is None


def test_a_debit_total_the_ledger_does_not_reproduce_refuses():
    consistent = (
        "Beginning balance $100.00 Total additions 300.00 "
        "Total subtractions 150.00 Ending balance $250.00\n"
    )
    assert parse(document(summary=consistent)) is None


def test_a_document_that_prints_no_grid_at_all_refuses():
    """Not a corrupted heading — no grid section. The summary balances, both
    totals reproduce and the identity closes, and it still publishes nothing,
    because on this platform the grid is the only per-day evidence there is.
    """
    assert parse(document(grid="")) is None


def test_a_grid_cell_the_scan_left_unreadable_refuses_rather_than_being_skipped():
    """The `_grid` REFUSAL path, which the two tests above do not reach: they
    go through the empty-run path, where the walked set does the refusing.

    Here the grid is present and complete for every day the ledger posts on,
    and carries one extra date whose balance the scan lost. A reader that
    skipped the unreadable cell would find its printed set equal to the walked
    set and publish; this one refuses, because a cell we could not read is not
    a cell that is not there.
    """
    assert parse(document(grid=GRID.rstrip("\n") + " 04-04\n")) is None


def test_the_grid_refusal_is_the_contract_of_the_reader_not_of_the_caller():
    """The same thing pinned at the seam, so the refusal cannot be reduced to
    the walked-set comparison by a later edit."""
    assert cpd._grid(["\n03-31 100.00 04-02\n"], seed=date(2054, 3, 31),
                     end=date(2054, 4, 30)) is None
    assert cpd._grid(["\n05-15 100.00\n"], seed=date(2054, 3, 31),
                     end=date(2054, 4, 30)) is None


def test_a_summary_whose_own_identity_does_not_close_refuses():
    """`beginning + additions - subtractions == ending`, checked against the
    printed closing balance rather than against the walked one."""
    broken = (
        "Beginning balance $100.00 Total additions 300.00 "
        "Total subtractions 250.00 Ending balance $151.00\n"
    )
    assert parse(document(summary=broken)) is None


def test_a_grid_day_that_disagrees_with_the_walk_refuses():
    assert parse(document(grid=GRID.replace("04-02 -150.00",
                                            "04-02 -151.00"))) is None


def test_a_grid_that_omits_a_day_the_ledger_posts_on_refuses():
    assert parse(document(grid="DAILY BALANCES\nDate Amount\n"
                               "03-31 100.00 04-03 150.00\n")) is None


def test_a_grid_day_the_ledger_never_posts_on_refuses():
    assert parse(document(grid=GRID.replace("04-03 150.00",
                                            "04-03 150.00 04-04 150.00"))) is None


def test_a_grid_whose_first_cell_contradicts_the_printed_opening_refuses():
    """The pre-period cell is the platform's own second printing of the
    beginning balance."""
    assert parse(document(grid=GRID.replace("03-31 100.00",
                                            "03-31 110.00"))) is None


def test_a_document_whose_grid_heading_a_scan_corrupted_refuses():
    """`DALY BALANCES` is what the archive's scans of this template actually
    print. The grid is the only per-day evidence this platform gives — it
    prints no transaction count at all — so a document without it is one we
    can check two ways instead of five, and the honest answer is the refusal.
    """
    assert parse(document(grid=GRID.replace("DAILY BALANCES",
                                            "DALY BALANCES"))) is None


def test_a_missing_summary_figure_refuses_rather_than_defaulting_to_zero():
    for label in ("Beginning balance $100.00 ", "Ending balance $150.00",
                  "Total additions 300.00 ", "Total subtractions 250.00 "):
        assert parse(document(summary=SUMMARY.replace(label, ""))) is None


def test_a_summary_row_printed_twice_with_different_figures_refuses():
    """There is no rule that says which printing to believe, and taking the
    first would be picking one."""
    contradicted = SUMMARY + "Total additions 400.00\n"
    assert parse(document(summary=contradicted)) is None


def test_a_summary_row_printed_twice_identically_is_one_reading():
    assert parse(document(summary=SUMMARY + "Total additions 300.00\n")) is not None


def test_a_row_that_prints_no_amount_before_the_next_row_refuses():
    """A row we could not read is a refusal, not a skip: dropping it silently
    is how a ledger comes to disagree with a printed total by one row while
    still looking complete."""
    lost = DEBITS.replace("04-02 ' ACH Debit 250.00", "04-02 ' ACH Debit")
    assert parse(document(debits=lost)) is None


def test_a_dated_row_with_no_amount_refuses_even_when_the_totals_still_close():
    """The discriminating form of the test above. There the lost amount also
    broke the debit total, so the document would have refused either way; here
    the readable rows still reproduce both printed totals and the grid, and
    only the dateful row the scan left amountless is unaccounted for. A reader
    that skipped it publishes a document that looks complete."""
    stray = DEBITS + "04-02\n"
    assert parse(document(debits=stray)) is None


def test_the_missing_amount_refusal_is_the_contract_of_the_reader():
    """Pinned at the seam as well, for the same reason as the grid's: an
    outcome test cannot distinguish `_rows` refusing from `_rows` returning a
    short list that some later gate happens to catch."""
    assert cpd._rows(["04-02 ' ACH Debit\n"], credit=False, start=date(2054, 4, 1),
                     end=date(2054, 4, 30), default="Debit") is None


def test_a_row_the_period_cannot_place_refuses_its_whole_section():
    """`_rows` returns None rather than skipping, and that contract is pinned
    directly: an outcome test cannot separate "refused" from "skipped", because
    a skipped row also breaks the total it was counted in. The distinction
    matters for a row the summary did NOT count — a date the scan invented —
    where skipping publishes a document that looks complete."""
    from datetime import date as _date

    section = ["05-15 ' ACH Debit 250.00\n"]
    assert cpd._rows(section, credit=False, start=_date(2026, 4, 1),
                     end=_date(2026, 4, 30), default="Debit") is None


def test_an_amount_a_scan_mangled_out_of_money_refuses():
    """`5,000.00` scanned as `5,000,00` is not money, and this reader does not
    guess what it was meant to be."""
    mangled = CREDITS.replace("04-03 ' Deposit 300.00", "04-03 ' Deposit 300,00")
    assert parse(document(credits=mangled)) is None


# ---------------------------------------------------------------------------
# The glyph law — both boundaries, each preventing a different failure
# ---------------------------------------------------------------------------

def test_a_card_date_inside_a_description_is_not_a_second_posting():
    """The RIGHT-hand boundary. This template prints a card purchase's own
    date in the description as `mm-dd-yy`; without the boundary its first two
    fields are a posting date and the row is published twice."""
    with_card_date = DEBITS + "XXXXXXXXXXXX1494 04-01-26 12:00 AM\n"
    statement = parse(document(debits=with_card_date))
    assert statement is not None
    assert len(statement.transactions) == 2


def test_a_date_may_not_begin_inside_another_date():
    """The LEFT-hand boundary. In `04-01-26` the tail `01-26` is also a
    `mm-dd` token; read as one it is a January posting on a statement that
    printed no January, which would refuse the whole document."""
    assert cpd._DATE_TOKEN is not None
    with_card_date = DEBITS + "TERMINAL 0001 04-01-26 12:00 AM\n"
    assert parse(document(debits=with_card_date)) is not None


def test_a_space_a_scan_put_inside_a_card_date_leaves_no_posting_behind():
    """W3 §CPSCAN CPS5 — the left-hand boundary's other half.

    The boundary above only holds while the card date is CONTIGUOUS. Two
    archive scans of this template print `02- 18-26`, and there the boundary
    sees a space and lets `18-26` through as a posting date; `dated_cells`
    then opens a cell on it, finds no amount before the next real row, and
    refuses the document. The month bound is what says `18` is not a month.

    The line below is INVENTED, and its placeholder town and state are the
    ones `core_processor_daily._ROW_DATE`'s own docstring uses for this
    construction. An earlier form of it carried a place name printed on one of
    the archive documents this card censused, which is the standing privacy
    rule's "example block copied from a document" however inert the token is
    to the assertion (W3 §CPSCAN CPS12, F1)."""
    split_card_date = DEBITS + "EXAMPLETOWN XX 02- 18-26 11:02 AM XXXXXXXXXXXX1494\n"
    statement = parse(document(debits=split_card_date))
    assert statement is not None
    assert len(statement.transactions) == 2


@pytest.mark.parametrize("fragment", ["18-26", "26-26", "13-01", "00-02", "04-00",
                                      "04-32", "04-45"])
def test_a_token_no_calendar_can_hold_is_not_a_posting_date(fragment):
    """The bound, one impossible field at a time. Each of these matched the
    unbounded `[0-9]{2}-[0-9]{2}` and opened a ledger cell on something no
    calendar can hold."""
    assert cpd._DATE_RE.search(f" {fragment} ") is None


@pytest.mark.parametrize("printed", ["01-01", "09-30", "10-31", "12-29"])
def test_every_printed_calendar_field_still_matches(printed):
    """The bound is a tightening and must not cost a real date: the month's
    two ranges and the day's three each have to keep matching."""
    assert cpd._DATE_RE.search(f" {printed} ").group(1) == printed


def test_a_letter_look_alike_in_a_date_is_refused_rather_than_absorbed():
    """What the archive's scans of this template really substitute: a Cyrillic
    `З` for a three, a lower-case `o` for a leading zero. The row must become
    invisible — which the totals then catch — rather than be placed on a
    guessed day.

    The leading-zero half of that is THIS reader's choice and not the
    complex's: the sibling `core_processor_sectioned` reads `o` and `O` as the
    zero they stand for, on 154 rows of its own template's scans. This module
    refuses because its own 20 documents print none — a grammar widened past
    its evidence is a grammar nothing tests — and the divergence is pinned by
    `test_the_sectioned_sibling_reads_the_zero_glyph_and_this_reader_does_not`
    below (W3 §CPSCAN CPS12, F7)."""
    for corrupted in ("З0-02 ' ACH Debit", "o4-02 ' ACH Debit"):
        assert parse(document(
            debits=DEBITS.replace("04-02 ' ACH Debit", corrupted))) is None


def test_the_sectioned_sibling_reads_the_zero_glyph_and_this_reader_does_not():
    """W3 §CPSCAN CPS12 (F7) — the divergence between the two sibling readers,
    pinned so that a future edit to either cannot silently converge them.

    `core_processor_sectioned._LEADING_ZERO` admits `o` and `O` in the leading
    position of a month or a day; this module's `_ROW_DATE` is digits only.
    Both choices are measured rather than stylistic — the sectioned template's
    scans print 154 such marks across 10 documents, this template's 20 print
    zero — so the two grammars are asserted here against each other rather
    than left to a pair of docstrings.

    UNIFYING them is out of scope for this card: admitting the glyph here
    would be a behaviour change on `core_processor_daily` with no archive
    evidence behind it, and refusing it there would give back the 154 rows.
    If a later cell brings evidence, this test is what it has to change."""
    from analysis import core_processor_sectioned as sectioned

    assert re.search(sectioned._DATE_TOKEN, " o3/12 100.00") is not None
    assert re.search(sectioned._DATE_TOKEN, " O3/12 100.00") is not None
    assert cpd._DATE_RE.search(" o3-12 100.00") is None
    assert cpd._DATE_RE.search(" O3-12 100.00") is None


def test_an_amount_whose_integer_part_is_not_ascii_is_invisible_not_zero():
    """The boundary class, and the reason it is `\\w` rather than `[0-9A-Za-z]`.

    `٢٥٠.00` is an amount whose integer part a scan rendered in another script.
    Under §SCANB's boundary class the character before the dot is not excluded,
    so the BARE sub-dollar alternative `.00` matches and the reader publishes
    0.00 where the bank printed 250.00 — a figure the bank never printed, and
    the exact failure the ASCII digit class is credited with preventing.

    `int()` and `float()` map non-ASCII digits to their own values, so no
    outcome test can separate the two digit CLASSES; the boundary is where the
    difference is real, so that is where it is pinned.
    """
    scanned = "٢٥٠.00"
    assert re.fullmatch(r"\d[\d,]*\.\d{2}", scanned), "the token is digits to `\\d`"
    assert re.search(r"(?<![0-9A-Za-z.,/-])(\.[0-9]{2})(?![0-9.,])", " " + scanned), (
        "the ASCII boundary lets the bare sub-dollar alternative through"
    )
    assert not re.search(cpd._FIGURE_TOKEN, " " + scanned)
    assert not re.search(cpd._DATE_TOKEN, " ٠٤-02")


def test_an_amount_run_onto_a_word_is_refused():
    """The right-hand boundary is `\\w` too, so a figure a flattened text layer
    welded to the next word is not read as money."""
    welded = DEBITS.replace("ACH Debit 250.00", "ACH Debit 250.00WT")
    assert parse(document(debits=welded)) is None


# ---------------------------------------------------------------------------
# Direction, sections and cheque serials
# ---------------------------------------------------------------------------

def test_direction_is_the_column_the_bank_printed_the_row_in():
    """Never the sign of the amount: this template prints every section figure
    as an unsigned magnitude."""
    statement = parse(document())
    assert all(row.amount < 0 for row in statement.transactions if row.direction == "debit")
    assert all(row.amount > 0 for row in statement.transactions if row.direction == "credit")


def test_a_signed_amount_in_a_section_is_not_read_as_money():
    """A section figure carrying a sign contradicts its own column."""
    signed = DEBITS.replace("ACH Debit 250.00", "ACH Debit -250.00")
    assert parse(document(debits=signed)) is None


def test_the_cheque_section_reads_its_serial_from_the_text_before_the_row():
    checks = "CHECKS\nNumber Date Amount\n1001 04-02 250.00\n"
    statement = parse(document(debits=checks))
    assert statement is not None
    assert [(row.description, row.direction) for row in statement.transactions] == [
        ("Check 1001", "debit"), ("Deposit", "credit"),
    ]


def test_a_cheque_the_bank_printed_no_serial_for_does_not_borrow_the_last_one():
    """The gap a serial is read from starts at the PREVIOUS ROW'S AMOUNT, not
    at its date. A gap that still held `250.00` would put that amount on this
    row's line and publish `Check 00` for a cheque the bank printed no serial
    for — a number the statement does not carry, invented out of another
    row's money."""
    checks = ("CHECKS\nNumber Date Amount\n"
              "1001 04-02 150.00\n"
              "04-02 100.00\n")
    statement = parse(document(debits=checks))
    assert statement is not None
    assert [row.description for row in statement.transactions] == [
        "Check 1001", "Check", "Deposit",
    ]


@pytest.mark.parametrize("furniture", [
    # the review's three constructions, each of which an end-anchored search
    # over the whole gap turns into a serial the statement does not carry
    "Continued on page 27\n",
    "XXXXXXXXXXXX0000\n",
    # a gap longer than the description truncation: an end-anchored read that
    # first truncated to 200 characters would split `7654321` mid-token and
    # publish `765432` — a WRONG number rather than a missing one
    ("MERCHANT PURCHASE TERMINAL 00000000 EXAMPLE FURNITURE LINE " * 5) + "7654321\n",
])
def test_page_furniture_between_cheque_rows_never_becomes_a_serial(furniture):
    """The serial is the LEADING cell of the printed `Number Date Amount`
    grid, read as the whole of what the bank printed on that row's own line.
    Furniture printed above the row is a different line and cannot reach it,
    however it ends."""
    checks = ("CHECKS\nNumber Date Amount\n"
              "1001 04-02 150.00\n"
              + furniture +
              "04-02 100.00\n")
    statement = parse(document(debits=checks))
    assert statement is not None
    assert [row.description for row in statement.transactions] == [
        "Check 1001", "Check", "Deposit",
    ]


def test_furniture_sharing_a_cheque_rows_line_is_not_a_serial_either():
    """The line-scoped read is a `fullmatch`, so furniture that a flattened
    text layer put on the ROW's line is refused too — a serial is a bare digit
    run and nothing else."""
    checks = ("CHECKS\nNumber Date Amount\n"
              "Continued on page 27 04-02 250.00\n")
    statement = parse(document(debits=checks))
    assert statement is not None
    assert [row.description for row in statement.transactions] == ["Check", "Deposit"]


def test_two_cheque_rows_on_one_line_each_keep_their_own_serial():
    """This platform prints two rows on one line, and that is what makes the
    gap's START load-bearing even under the line-scoped read: a gap that began
    at the previous row's DATE would carry that row's amount onto this row's
    line and lose a serial the bank did print."""
    checks = "CHECKS\nNumber Date Amount\n1001 04-02 150.00 1002 04-02 100.00\n"
    statement = parse(document(debits=checks))
    assert statement is not None
    assert [row.description for row in statement.transactions] == [
        "Check 1001", "Check 1002", "Deposit",
    ]


def test_a_serial_the_platform_marked_as_a_sequence_break_is_still_read():
    """The platform prints `*` after a serial where the sequence broke."""
    checks = "CHECKS\nNumber Date Amount\n1001 * 04-02 250.00\n"
    statement = parse(document(debits=checks))
    assert [row.description for row in statement.transactions] == ["Check 1001", "Deposit"]


def test_a_described_row_publishes_the_text_between_its_date_and_its_amount():
    statement = parse(document())
    assert [row.description for row in statement.transactions] == ["ACH Debit", "Deposit"]


# ---------------------------------------------------------------------------
# W3 §DESCATTRIB — a description stays attached to its own posting
# ---------------------------------------------------------------------------

#: The interleaving printing the sibling grammar's documents really print, on
#: this reader's template: two rows' merchant blocks welded onto ONE line
#: inside the second row's span, then a third row whose span holds a flush the
#: layer proves is its own. Three rows on the day the single row used to post
#: on, summing to the same printed total, so the summary and the grid stand.
INTERLEAVED_DEBITS = (
    "DEBITS\n"
    "Date Description Subtractions\n"
    "04-02 ' ACH Debit 100.00 04-02 ' ACH Debit\n"
    "EXAMPLE FIRST VENDOR EXAMPLE SECOND VENDOR\n"
    "50.00 04-02 ' ACH Debit\n"
    "EXAMPLE THIRD VENDOR\n"
    "100.00\n"
)


def interleaved():
    statement = parse(document(debits=INTERLEAVED_DEBITS))
    assert statement is not None
    return [row.description for row in statement.transactions
            if row.direction == "debit"]


def test_an_interleaved_block_pair_is_published_on_neither_of_its_rows():
    """This reader's 13 validated documents print their merchant blocks BELOW
    the amount, where no row's span can reach them — measured, not assumed
    (W3 §DESCATTRIB DA3). The rule is still shared, because the printing is
    the layer's rather than the template's and this reader is one re-extraction
    away from the sibling's."""
    assert interleaved()[:2] == ["ACH Debit", "ACH Debit"]


def test_a_block_the_layer_proves_is_one_rows_own_is_published_on_that_row():
    assert interleaved()[2] == "ACH Debit EXAMPLE THIRD VENDOR"


def test_no_row_publishes_a_merchant_printed_for_another_row():
    published = " ".join(interleaved())
    assert "EXAMPLE FIRST" not in published
    assert "EXAMPLE SECOND" not in published


def test_the_reader_attributes_through_the_shared_call_and_not_beside_it():
    """Patching the shared function must change what this reader publishes.
    Importing the name proves nothing about the call site; this does."""
    marker = "REPLACED BY THE HARNESS"
    original = cpd.attributed_descriptions
    try:
        cpd.attributed_descriptions = (
            lambda runs, **kwargs: [[marker] * len(cells) for cells in runs])
        assert interleaved() == [marker] * 3
    finally:
        cpd.attributed_descriptions = original


def test_a_merchant_block_printed_below_its_amount_reaches_no_rows_span():
    """The printing this reader's whole archive population uses: the block
    lands between one row's amount and the next row's date, which is no row's
    description span, and every row publishes the label printed beside it."""
    assert parse(document()) is not None
    assert interleaved()[0] == "ACH Debit"


def test_case_sensitivity_is_load_bearing_where_it_cuts_the_summary_strip():
    """Prose printed BETWEEN the account field and the summary is where the
    case-sensitive split earns its keep, and the first form of this test did
    not put it there — it put the prose in the footer, where a case-folding
    split cuts a block nothing reads and the document publishes either way.

    Here a case-folding split would end the summary region before the strip
    begins and the document would publish nothing. Same lesson as §SCANB S9.3,
    which had to correct itself about which of its two guards was acting.
    """
    prose = "your deposits clear sooner than your debits do\n"
    assert parse(document(account=ACCOUNT + prose)) is not None


def test_prose_below_the_ledger_is_held_out_by_the_exact_upper_case_key():
    """The ledger path's guard is not the case-sensitive scan — it is the
    lookup, which asks for the template's exact upper-case names. Prose in the
    footer is filed, if at all, under a key nothing reads."""
    prose = "\nyour deposits and credits clear sooner than your debits\n"
    statement = parse(document(footer=prose + FOOTER))
    assert statement is not None
    assert len(statement.transactions) == 2


def test_the_blocks_printed_after_the_grid_stop_it():
    """Without them the grid's block runs to the end of the document and the
    interest block's dated figures are read as grid days."""
    after = (
        "INTEREST INFORMATION\n"
        "Annual percentage yield earned 0.26% Interest-bearing days 30\n"
        "04-30 12.34\n"
        "OVERDRAFT/RETURN ITEM FEES\n"
        "Total Overdraft Fees $0.00 $0.00\n"
    )
    assert parse(document(footer=after + FOOTER)) is not None


# ---------------------------------------------------------------------------
# The issuer, and the product name
# ---------------------------------------------------------------------------

def test_the_issuer_is_never_published_even_when_the_document_names_one():
    """This template prints no institution FIELD. The masthead line bounds a
    name on the left only — `Example State Bank PO Box 1` — and the closing
    courtesy sentence, which IS bounded on both sides, is prose: measured over
    the store the same sentence yields `us.`, `United!` and, on this
    platform's own sibling arrangement, a BRANCH office's name. So `bank` is
    None, under the honest-unknown-issuer ruling."""
    statement = parse(document())
    assert statement.bank is None
    assert "Example State Bank" in document()


def test_a_product_name_printed_once_is_published_as_printed():
    assert parse(document()).account_name == "Example Business Checking"


def test_a_product_name_the_text_layer_printed_four_times_is_declined():
    """Fill, stroke and two shadows of one printed string. The bank printed it
    once; publishing it as it stands publishes a name no statement carries,
    and collapsing it is a repair. So the label is lost and the document is
    not."""
    repeated = ("Example Business Checking " * 4).strip() + "\n"
    statement = parse(document(product=repeated))
    assert statement is not None
    assert statement.account_name is None


def test_a_product_line_that_merely_repeats_a_word_is_still_published():
    """The rule is a WHOLE-line repetition, not a repeated word: a genuine
    name may say the same word twice."""
    statement = parse(document(product="Business Business Checking\n"))
    assert statement.account_name == "Business Business Checking"


# ---------------------------------------------------------------------------
# The other printed issue, and the registry edge that keeps it
# ---------------------------------------------------------------------------

RUNNING_BALANCE = (
    MASTHEAD
    + "Essential Business Checking\n"
    + "Account number XXXXXX0000 Enclosures 2 Low balance $50.00 "
      "Average balance $120.00\n"
    + "DAILY ACTIVITY\n"
      "Date Description Additions Subtractions Balance\n"
      "03-31 Beginning balance $100.00\n"
      "04-02 Payment -250.00 -150.00\n"
      "04-03 Deposit 300.00 150.00\n"
      "04-03 Ending totals Ending totals Ending totals Ending totals "
      "300.00 300.00 300.00 300.00 -250.00 -250.00 -250.00 -250.00 "
      "$150.00 $150.00 $150.00 $150.00\n"
)


def test_the_running_balance_issue_is_claimed_and_then_declined():
    """Same platform, same period furniture — so detection claims it — and no
    `Total additions` summary, so this reader declines rather than guessing.
    That is what makes the supersedes edge safe: it cannot strand a document.
    """
    assert cpd.detect(RUNNING_BALANCE).claims
    assert parse(RUNNING_BALANCE) is None


def test_the_issuer_specific_reader_supersedes_this_one():
    """`b1` reads one issuer's running-balance issue and came first. Without
    the edge both would claim and the document would resolve `ambiguous`,
      which would move three validated documents to review."""
    document_ = RUNNING_BALANCE.replace("Example State Bank", "B1Bank")
    assert cpd.detect(document_).claims
    assert b1.detect(document_).claims
    assert pr.by_id("b1").supersedes == frozenset({"core_processor_daily"})
    assert pr.resolve(document_).outcome != "ambiguous"


# ---------------------------------------------------------------------------
# The limit of the gate set, stated rather than left to be found
# ---------------------------------------------------------------------------

def test_the_gates_are_blind_to_a_same_day_same_direction_redistribution():
    """Move value between two rows that share a date AND a direction and every
    printing still holds: neither total changes and no end-of-day balance
    moves.

    A FORGERY signature rather than an OCR one: a scan drops a row or mangles
    a digit, which moves a total and every grid day after it. Pinned so that
    no future reader of this module mistakes the five gates for a proof of
    authenticity.
    """
    two_debits = (
        "DEBITS\nDate Description Subtractions\n"
        "04-02 ' ACH Debit 100.00\n"
        "04-02 ' ACH Debit 150.00\n"
    )
    redistributed = two_debits.replace("100.00", "40.00").replace("150.00", "210.00")
    first = parse(document(debits=two_debits))
    second = parse(document(debits=redistributed))
    assert first is not None and second is not None
    assert [row.amount for row in first.transactions] != [
        row.amount for row in second.transactions
    ]


def test_the_gates_are_blind_to_a_row_split_in_two_on_the_same_day():
    """The second half of the same limit, EXERCISED rather than asserted in
    prose — the first version of this file claimed it in the docstring above
    and tested only the redistribution.

    Splitting one row into two on the same day and direction changes the row
    COUNT and nothing else, and this platform prints no count for anything to
    compare against. On the second core processor's template the printed count
    catches exactly this; here nothing can, and that difference is the price
    of a platform that prints totals and a grid but no counts.
    """
    split = (
        "DEBITS\nDate Description Subtractions\n"
        "04-02 ' ACH Debit 100.00\n"
        "04-02 ' ACH Debit 150.00\n"
    )
    whole = parse(document())
    halves = parse(document(debits=split))
    assert whole is not None and halves is not None
    assert len(whole.transactions) == 2 and len(halves.transactions) == 3
    assert whole.stated_total_debits == halves.stated_total_debits
    assert [entry.balance for entry in whole.stated_daily_balances] == [
        entry.balance for entry in halves.stated_daily_balances
    ]


# ---------------------------------------------------------------------------
# Audit round 3, R3-B09 (R3-91): a marked credit keeps the block it was marked
# at, apart from its description (Transaction.unread_payer_text), as the
# counted template's credits do. The text is still not read as the payer: it
# waits on the owner's G7 admission (spec §17.1), and every hold stays.
# ---------------------------------------------------------------------------

def _published_rows(statement):
    return [(t.date, t.description, t.amount, t.direction, t.running_balance) for t in statement.transactions]


def _credits_with_block(label: str, block: str) -> str:
    return f"CREDITS\nDate Description Additions\n04-03 ' {label} 300.00\n{block}\n"


def _tier(statement):
    from analysis.transaction_classifier.statement import classify_statement_transactions

    credit = next(record for record in classify_statement_transactions(statement) if record.amount > 0)
    return credit.revenue_tier, credit.revenue_tier_reason


def test_r3_91_a_marked_wire_keeps_its_block_apart_from_its_label_and_stays_held():
    statement = parse(document(credits=_credits_with_block("Incoming Wire", "WT FABRIKAM SUPPLY LLC")))
    assert statement is not None
    # Every published field is what the reader published before: the label alone.
    assert _published_rows(statement) == [
        ("2054-04-02", "ACH Debit", -250.0, "debit", None),
        ("2054-04-03", "Incoming Wire", 300.0, "credit", None),
    ]
    credit = statement.transactions[1]
    assert (credit.payer_text_unread, credit.unread_payer_text) == (True, "WT FABRIKAM SUPPLY LLC")
    assert _tier(statement) == ("excluded_pending_review", "wire_no_sender")
    # The debit keeps its label and carries no text (G7).
    debit = statement.transactions[0]
    assert (debit.payer_text_unread, debit.unread_payer_text) == (False, "")


def test_r3_91_a_marked_credit_whose_block_names_a_registry_lender_is_held_by_r07():
    statement = parse(document(credits=_credits_with_block("ACH Credit", "KAPITUS LLC FUNDING 540403")))
    assert statement is not None
    assert _published_rows(statement)[1] == ("2054-04-03", "ACH Credit", 300.0, "credit", None)
    assert statement.transactions[1].unread_payer_text == "KAPITUS LLC FUNDING 540403"
    assert _tier(statement) == ("excluded_pending_review", "unread_run_names_financing")
    # A wire whose block names one stays held as a wire with no sender read.
    wire = parse(document(credits=_credits_with_block("Incoming Wire", "WT KAPITUS LLC")))
    assert _tier(wire) == ("excluded_pending_review", "wire_no_sender")


def test_r3_91_a_block_naming_a_customer_keeps_payer_text_not_read_and_a_teller_reference_gives_no_text():
    statement = parse(document(credits=_credits_with_block("ACH Credit", "CONTOSO SUPPLY 540403")))
    assert statement.transactions[1].unread_payer_text == "CONTOSO SUPPLY 540403"
    assert _tier(statement) == ("counted_flagged", "payer_text_not_read")
    teller = parse(document(credits=_credits_with_block("Deposit", "TLR 00 BR 00")))
    assert (teller.transactions[1].payer_text_unread, teller.transactions[1].unread_payer_text) == (False, "")
