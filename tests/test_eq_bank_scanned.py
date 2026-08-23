"""The scanned EQ Bank ledger: directions solved from the printed balance.

W3 §TANGERINE. What is under test is not "it parses" — it is what the reader
REFUSES. The class killers on a scanned registration are a fabricated row and
a hallucinated value, and this template offers three routes to each: the scan
flattens the Withdrawals and Deposits columns into one run of text so a
direction can be invented; it turns some day numbers into a stray glyph so a
posting date can be invented; and it can drop a row outright, which no total
this template prints would notice, because it prints no counts at all.

EVERY FIGURE, NAME, ACCOUNT NUMBER AND DATE IN THIS FILE IS INVENTED, and the
statement month is deliberately one that no archive document of this family
prints. `webapp_data/` is gitignored by design and no archive content is
reproduced anywhere in this repository (`tests/test_parser_crash_shapes.py`
states the norm); a scan over every printed money figure, name token, account
number and date in the five archive documents finds none of them anywhere in
this branch's diff.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis.eq_bank_scanned import (
    _read_rows,
    _resolve_dates,
    detect,
    parse_eq_bank_scanned_statement,
)

TITLE = "September 2026 Statement"
HEADER = "Jordan Halloway Account # 840-227-593 September 1, 2026 to September 30, 2026"
ADDRESS = "Jordan Halloway\n14 Sample Lane\nPlaceholder, ON X0X 0X0\n"
SUMMARY = (
    "Your activity summary\n"
    "Questions?\n"
    "Opening balance $1,037.41 Toll Free (within North America) 1-800-000-0000\n"
    "Total deposits + $713.26 Outside of North America 1-000-000-0000\n"
    "Total withdrawals - $268.13 Other contact options eqbank.ca/contact-us\n"
    "Closing balance = $1,482.54 Total interest earned $1.07\n"
)
COLUMN_HEAD = "Date Description Withdrawals Deposits Balance"
FOOTER = "Sample Tower. 1 Sample Street. Toronto, ON X0X 0X0 Page {n} of {total}"
COPYRIGHT = "(c) 2026 Sample Bank. All rights reserved"

#: `1,037.41 + 713.26 - 268.13 == 1,482.54`, and the walk reproduces it.
#: The last row is the following cycle's interest credit, dated the day after
#: the period ends — which is where this template prints it.
ROWS = (
    "Sep 2 Inbound transfer $531.62 $1,569.03\n"
    "Sep 3 Card Load - $268.13 $1,300.90\n"
    "Sep 5 Inbound transfer $180.57 $1,481.47\n"
    "Oct 1 Interest received $1.07 $1,482.54\n"
)


def page(rows: str, *, number: int = 1, total: int = 1, head: bool = True,
         title: str = TITLE, header: str = HEADER, summary: str = "",
         footer: str | None = None, before_head: str = "") -> str:
    body = [f"--- Page {number} ---", title, header, summary or "", before_head]
    if head:
        body.append(COLUMN_HEAD)
    body.append(rows.rstrip("\n"))
    body.append(FOOTER.format(n=number, total=total) if footer is None else footer)
    body.append(COPYRIGHT)
    return "\n".join(part for part in body if part) + "\n"


def document(rows: str = ROWS, **kwargs) -> str:
    kwargs.setdefault("summary", ADDRESS + SUMMARY)
    return page(rows, **kwargs)


def parsed(rows: str = ROWS, **kwargs):
    return parse_eq_bank_scanned_statement(document(rows, **kwargs))


# --- detection --------------------------------------------------------------


def test_the_whole_statement_is_claimed():
    assert detect(document()).claims


@pytest.mark.parametrize(
    "removed, replacement",
    [
        ("eqbank.ca/contact-us", "somewhere-else.example/contact-us"),
        ("Your activity summary", "Your summary"),
        ("Date Description Withdrawals Deposits Balance", "Date Description Amount"),
    ],
)
def test_each_required_marker_is_actually_required(removed, replacement):
    """Drop any one of the three and the registration must not claim."""
    assert not detect(document().replace(removed, replacement)).claims


def test_a_printing_without_the_running_balance_column_is_left_for_another_reader():
    """The column head is a DETECTION marker, not merely a parse requirement:
    the running balance is the only thing that says which way a row went, and
    claiming a printing without it would strand the document."""
    without = document().replace(COLUMN_HEAD, "Date Description Withdrawals Deposits")
    assert not detect(without).claims
    assert parse_eq_bank_scanned_statement(without) is None


# --- the whole statement ----------------------------------------------------


def test_the_whole_statement_publishes_what_the_bank_printed():
    stmt = parsed()
    assert stmt is not None
    assert stmt.bank == "EQ Bank"
    assert stmt.account_name == "Jordan Halloway"
    assert stmt.account_number == "840-227-593"
    assert (stmt.period_start, stmt.period_end) == ("2026-09-01", "2026-09-30")
    assert (stmt.beginning_balance, stmt.ending_balance) == (1037.41, 1482.54)
    assert (stmt.stated_total_credits, stmt.stated_total_debits) == (713.26, 268.13)
    assert stmt.stated_interest_paid == 1.07
    assert [(t.date, t.amount, t.direction, t.running_balance) for t in stmt.transactions] == [
        ("2026-09-02", 531.62, "credit", 1569.03),
        ("2026-09-03", -268.13, "debit", 1300.90),
        ("2026-09-05", 180.57, "credit", 1481.47),
        ("2026-10-01", 1.07, "credit", 1482.54),
    ]


def test_this_template_prints_no_counts_and_none_are_invented():
    """A count derived from our own parse is not a figure the bank stated."""
    stmt = parsed()
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None
    assert stmt.days_in_period is None
    assert stmt.bank_reported_average_balance is None


def test_currency_is_the_schema_default_because_this_reader_asserts_nothing():
    """CURRENCY_DOCTRINE §B: a jurisdiction default is affirmative evidence and
    is never an absence rule, and §C prices asserting one at a measurement
    packet this cell did not run. The field therefore carries what the schema
    gives it and this parser never writes it."""
    from analysis.schema import Statement

    assert parsed().currency == Statement().currency


def test_the_day_after_the_period_is_not_a_daily_snapshot_of_the_period():
    """`analysis/adb.py` refuses a whole document for one out-of-period
    snapshot, and a balance dated after the period is not a balance of it."""
    stmt = parsed()
    assert [(s.date, s.balance) for s in stmt.stated_daily_balances] == [
        ("2026-09-02", 1569.03),
        ("2026-09-03", 1300.90),
        ("2026-09-05", 1481.47),
    ]


def test_a_days_snapshot_is_the_balance_on_its_last_printed_row():
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 2 Card Load - $268.13 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    stmt = parsed(rows)
    assert [(s.date, s.balance) for s in stmt.stated_daily_balances] == [
        ("2026-09-02", 1300.90),
        ("2026-09-05", 1481.47),
    ]


# --- the direction of a row -------------------------------------------------


def test_a_credit_the_description_calls_a_transfer_sent_is_published_as_a_credit():
    """The reversal row this family actually prints. A description vocabulary
    would get it exactly backwards; the two printed balances do not."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Interac e-Transfer sent to es Someone - $268.13 $1,300.90\n"
        "Sep 3 Interac e-Transfer sent to es Someone $268.13 $1,569.03\n"
        "Sep 5 Card Load - $87.56 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    stmt = parsed(rows, summary=ADDRESS + SUMMARY.replace(
        "Total deposits + $713.26", "Total deposits + $800.82"
    ).replace("Total withdrawals - $268.13", "Total withdrawals - $355.69"))
    assert stmt is not None
    assert [t.direction for t in stmt.transactions] == [
        "credit", "debit", "credit", "debit", "credit"
    ]


def test_an_amount_that_is_not_the_step_between_two_printed_balances_refuses():
    assert parsed(ROWS.replace("$531.62 $1,569.03", "$431.62 $1,569.03")) is None


def test_a_row_that_moves_no_money_refuses():
    """A zero step is a row the printed balances do not account for."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep 4 Adjustment $0.00 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    assert parsed(rows) is None


def test_a_dropped_row_refuses_even_though_this_template_prints_no_counts():
    """The complete-coverage oracle. Delete the middle row and every remaining
    row is still internally consistent; the walk is what notices."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    assert parsed(rows) is None


def test_a_row_dropped_from_the_end_refuses():
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
    )
    assert parsed(rows) is None


def test_a_printed_minus_the_arithmetic_contradicts_refuses():
    """The glyph and the two balances are two readings of one fact. Where they
    disagree the document is not readable with confidence."""
    assert parsed(ROWS.replace(
        "Sep 5 Inbound transfer $180.57", "Sep 5 Inbound transfer - $180.57"
    )) is None


def test_a_minus_the_scan_dropped_refuses_rather_than_inverting_a_row():
    assert parsed(ROWS.replace(
        "Sep 3 Card Load - $268.13", "Sep 3 Card Load $268.13"
    )) is None


# --- the summary ------------------------------------------------------------


def test_a_summary_whose_own_identity_does_not_close_refuses():
    assert parsed(summary=ADDRESS + SUMMARY.replace(
        "Closing balance = $1,482.54", "Closing balance = $1,482.55"
    )) is None


def test_a_summary_term_printed_twice_with_two_values_refuses():
    """A continuation page reprinting the summary, a two-account document, an
    OCR duplication: one reading published under another's heading."""
    doubled = ADDRESS + SUMMARY + "Opening balance $2,031.88\n"
    assert parsed(summary=doubled) is None


def test_a_summary_term_printed_twice_with_the_same_value_is_corroboration():
    doubled = ADDRESS + SUMMARY + "Opening balance $1,037.41\n"
    assert parsed(summary=doubled) is not None


def test_two_grids_whose_totals_the_bank_denies_refuse():
    """Both halves removed, because they are mathematically coupled: the walk
    fixes `credits - debits`, so a wrong credit total implies an equally wrong
    debit total. Neither can fire alone; together they are the only thing
    standing between a short grid and a published statement whose stated
    totals it does not fill."""
    assert parsed(summary=ADDRESS + SUMMARY.replace(
        "Total deposits + $713.26", "Total deposits + $813.26"
    ).replace("Total withdrawals - $268.13", "Total withdrawals - $368.13")) is None


def test_a_statement_with_no_ledger_at_all_is_not_a_statement():
    assert parse_eq_bank_scanned_statement(
        "--- Page 1 ---\n" + TITLE + "\n" + HEADER + "\n" + ADDRESS + SUMMARY
        + COLUMN_HEAD + "\n" + FOOTER.format(n=1, total=1) + "\n"
    ) is None


# --- the header and the title -----------------------------------------------


def test_two_pages_that_disagree_about_the_account_refuse():
    first = page(
        "Sep 2 Inbound transfer $531.62 $1,569.03\n",
        number=1, total=2, summary=ADDRESS + SUMMARY,
    )
    second = page(
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n",
        number=2, total=2,
        header=HEADER.replace("840-227-593", "840-227-664"),
    )
    assert parse_eq_bank_scanned_statement(first + second) is None


def test_two_pages_that_agree_are_one_statement():
    first = page(
        "Sep 2 Inbound transfer $531.62 $1,569.03\n",
        number=1, total=2, summary=ADDRESS + SUMMARY,
    )
    second = page(
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n",
        number=2, total=2,
    )
    stmt = parse_eq_bank_scanned_statement(first + second)
    assert stmt is not None and len(stmt.transactions) == 4


def test_a_title_that_contradicts_the_printed_period_refuses():
    """A mis-scanned period date is exactly how a statement acquires a month
    it does not belong to; the title is the second printing that catches it."""
    assert parsed(title="August 2026 Statement") is None


def test_a_period_that_ends_before_it_starts_refuses():
    assert parsed(
        header="Jordan Halloway Account # 840-227-593 September 30, 2026 to September 1, 2026"
    ) is None


# --- the ledger region ------------------------------------------------------


def test_a_line_inside_the_ledger_that_is_not_a_row_refuses():
    """A region holding a line this reader cannot read is a region whose grid
    may be incomplete, and a partial grid published as a whole one is the
    failure this refuses."""
    rows = ROWS.replace(
        "Sep 3 Card Load - $268.13 $1,300.90\n",
        "Sep 3 Card Load - $268.13 $1,300.90\nSep 4 Card Load - $ai.00 $1,290.90\n",
    )
    assert parsed(rows) is None


def test_a_page_whose_footer_declaration_is_illegible_refuses():
    """Where the grid stopped is then not known."""
    assert parsed(footer="Sample Tower. 1 Sample Street. Toronto, ON X0X 0X0 Pane I of |") is None


def test_a_row_shaped_line_above_the_column_head_is_not_a_transaction():
    """Region scoping. Without it the stray line becomes a row and the walk,
    correctly, then refuses the whole document."""
    stmt = parsed(before_head="Sep 1 Previous cycle summary $4,321.09 $4,321.09")
    assert stmt is not None and len(stmt.transactions) == 4


def test_rows_are_read_from_every_page_and_only_from_its_own_region():
    rows = _read_rows(
        page("Sep 2 Inbound transfer $531.62 $1,569.03\n", number=1, total=2)
        + page("Sep 3 Card Load - $268.13 $1,300.90\n", number=2, total=2)
    )
    assert [row.day_token for row in rows] == ["2", "3"]


# --- the posting date -------------------------------------------------------

SEPTEMBER = dict(period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))


def resolve(rows: str):
    parsed_rows = _read_rows(page(rows))
    assert parsed_rows is not None
    return _resolve_dates(parsed_rows, **SEPTEMBER)


def test_the_year_comes_from_the_printed_period_and_nowhere_else():
    assert resolve("Sep 2 Inbound transfer $531.62 $1,569.03\n") == [date(2026, 9, 2)]


def test_the_following_cycles_opening_credit_is_dated_the_day_the_bank_dated_it():
    assert resolve("Oct 1 Interest received $1.07 $1,482.54\n") == [date(2026, 10, 1)]


def test_a_row_dated_two_days_past_the_period_refuses():
    """One day is the whole extension: the bank posts the next cycle's opening
    credit on `period_end + 1` and prints it here. Anything further out is a
    mis-read."""
    assert resolve("Oct 2 Interest received $1.07 $1,482.54\n") is None


def test_a_row_dated_before_the_period_refuses():
    assert resolve("Aug 31 Inbound transfer $531.62 $1,569.03\n") is None


def test_a_day_no_month_has_refuses():
    assert resolve("Sep 31 Inbound transfer $531.62 $1,569.03\n") is None


def test_a_day_number_outside_the_calendar_refuses():
    assert resolve("Sep 44 Inbound transfer $531.62 $1,569.03\n") is None


def test_an_illegible_day_between_two_rows_of_the_same_day_is_derived_not_guessed():
    assert resolve(
        "Sep 9 Inbound transfer $531.62 $1,569.03\n"
        "Sep g Card Load - $268.13 $1,300.90\n"
        "Sep 9 Inbound transfer $180.57 $1,481.47\n"
    ) == [date(2026, 9, 9)] * 3


def test_an_illegible_day_between_two_different_days_refuses():
    """Two candidate days means the document does not determine the date, and
    publishing either would publish a chronology the bank did not print."""
    assert resolve(
        "Sep 7 Inbound transfer $531.62 $1,569.03\n"
        "Sep & Card Load - $268.13 $1,300.90\n"
        "Sep 8 Inbound transfer $180.57 $1,481.47\n"
    ) is None


def test_an_illegible_first_row_is_bounded_below_by_the_period_start():
    assert resolve(
        "Sep & Card Load - $268.13 $1,300.90\n"
        "Sep 1 Inbound transfer $180.57 $1,481.47\n"
    ) == [date(2026, 9, 1), date(2026, 9, 1)]


def test_an_illegible_last_row_has_no_upper_bound_and_refuses():
    assert resolve(
        "Sep 9 Inbound transfer $531.62 $1,569.03\n"
        "Sep & Card Load - $268.13 $1,300.90\n"
    ) is None


def test_an_illegible_day_whose_derivation_lands_in_another_month_refuses():
    """The month token survived even where the day did not, and a derivation
    that contradicts it is not a derivation from this document."""
    assert resolve(
        "Oct 1 Interest received $1.07 $1,482.54\n"
        "Oct & Interest received $1.07 $1,483.61\n"
        "Oct 1 Interest received $1.07 $1,484.68\n"
    ) is not None
    assert resolve(
        "Sep 30 Inbound transfer $531.62 $1,569.03\n"
        "Oct & Interest received $1.07 $1,570.10\n"
        "Sep 30 Inbound transfer $1.07 $1,571.17\n"
    ) is None


def test_the_digit_that_survived_a_stray_glyph_is_read():
    assert resolve("Sep 8& Card Load - $268.13 $1,300.90\n") == [date(2026, 9, 8)]


# --- SCAN-DAY-GLYPH: the stray glyph is enumerated, not deleted (W3 §SCANHYG)


def test_a_glyph_beside_a_digit_is_ink_because_no_other_reading_is_a_day():
    """`8&` is not resolved by deleting the glyph — it is resolved by finding
    that the only reading which IS a day treats it as ink. Read as a digit the
    cell would be the eighty-somethingth of the month, and there is no such
    day, so the document itself settles it. No glyph table is consulted, which
    matters because the same glyph stands alone in the day column on other
    documents of the same family, where it can only be a digit."""
    assert resolve("Sep 8& Card Load - $268.13 $1,300.90\n") == [date(2026, 9, 8)]
    assert resolve("Sep 1&1 Card Load - $268.13 $1,300.90\n") == [date(2026, 9, 11)]


def test_a_glyph_BEFORE_a_digit_is_not_resolved_by_deleting_it():
    """THE HOLE THIS GATE CLOSES. `&8` is the 8th, the 18th or the 28th. The
    reader this replaced deleted every non-decimal glyph and took what was
    left, so it answered the 8th — silently, on a document whose printed order
    admits the 18th just as well."""
    assert resolve(
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep &8 Card Load - $268.13 $1,300.90\n"
        "Sep 20 Inbound transfer $180.57 $1,481.47\n"
    ) is None


def test_a_glyph_before_a_digit_READS_where_the_printed_order_leaves_one_day():
    """The same cell, and the gate is not merely stricter: where the printed
    order rules out the 18th and the 28th, the 8th is what the document says."""
    assert resolve(
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep &8 Card Load - $268.13 $1,300.90\n"
        "Sep 9 Inbound transfer $180.57 $1,481.47\n"
    ) == [date(2026, 9, 2), date(2026, 9, 8), date(2026, 9, 9)]


def test_a_day_cell_wider_than_a_day_cell_never_reaches_the_enumeration():
    """The shared enumeration refuses a cell wider than
    `MAX_DAY_CELL_GLYPHS`, and on THIS reader that bound is never the binding
    one: `_ROW_RE` already caps the day cell at three glyphs, so a wider one is
    a line inside a ledger region that is not a row, and the document refuses
    there. Stated as a measurement rather than assumed, because the bound is
    the shared helper's and the next reader to take it may have no such row
    grammar."""
    from analysis.date_tokens import MAX_DAY_CELL_GLYPHS, day_readings

    assert MAX_DAY_CELL_GLYPHS == 3
    assert day_readings("1&&&") == frozenset()
    assert _read_rows(page("Sep 1&&& Card Load - $268.13 $1,300.90\n")) is None
    assert parsed("Sep 1&&& Card Load - $268.13 $1,300.90\n") is None


def test_a_legible_day_that_breaks_the_printed_order_refuses():
    """The mis-read this catches and nothing else can: a `10` scanned as `1O`
    reads as day 1 in the middle of a run of 9s and 11s. It still sums, still
    reconciles, and corrupts the daily ledger — and therefore the ADB —
    silently.

    It does NOT catch a wrong day that still lands BETWEEN its neighbours; that
    residual is stated in `_resolve_dates` and is a limit of the evidence, not
    of the reader."""
    assert resolve(
        "Sep 9 Inbound transfer $531.62 $1,569.03\n"
        "Sep 1O Card Load - $268.13 $1,300.90\n"
        "Sep 11 Inbound transfer $180.57 $1,481.47\n"
    ) is None


def test_the_whole_statement_is_still_read_when_a_day_glyph_is_recoverable():
    """End to end, not just the date solver."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep g Inbound transfer $92.10 $1,393.00\n"
        "Sep 3 Inbound transfer $88.47 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    stmt = parsed(rows)
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == [
        "2026-09-02", "2026-09-03", "2026-09-03", "2026-09-03", "2026-10-01"
    ]


# --- the day token that is a digit to Python but not to `int` ---------------
#
# `str.isdigit()` is True for the superscripts U+00B9 U+00B2 U+00B3 and `int()`
# rejects them, so reading the day with `isdigit` raises ValueError out of the
# parser instead of refusing — the crash class
# `tests/test_parser_crash_shapes.py` exists for. Both halves are covered: the
# refusal, and the case where the printed order DOES determine the day, which
# is where a raising reader and a refusing reader differ visibly.

SUPERSCRIPT_TWO = "²"


def test_a_superscript_day_token_refuses_instead_of_raising():
    rows = ROWS.replace("Sep 3 Card Load", f"Sep {SUPERSCRIPT_TWO} Card Load")
    assert parsed(rows) is None
    assert resolve(f"Sep {SUPERSCRIPT_TWO} Card Load - $268.13 $1,300.90\n") is None


def test_a_superscript_day_the_printed_order_determines_is_read_not_raised():
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        f"Sep {SUPERSCRIPT_TWO} Inbound transfer $92.10 $1,393.00\n"
        "Sep 3 Inbound transfer $88.47 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    stmt = parsed(rows)
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == [
        "2026-09-02", "2026-09-03", "2026-09-03", "2026-09-03", "2026-10-01"
    ]


# --- gates the first mutation run proved untested ---------------------------
#
# Five of the ten survivors of the first 25-mutant run were NOT redundant;
# each of these tests is the counterexample that proves it. The other five are
# listed in W3 §TANGERINE with the derivation that makes them redundant.


def test_a_period_that_ends_one_day_before_it_starts_refuses():
    """The ordering check is not redundant with the date solver. At exactly one
    day of inversion the solver's window (`period_start .. period_end + 1`) is
    still non-empty, so every row dated on the start day resolves and nothing
    else notices that the period runs backwards."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 2 Card Load - $268.13 $1,300.90\n"
    )
    summary = ADDRESS + SUMMARY.replace(
        "Total deposits + $713.26", "Total deposits + $531.62"
    ).replace("Closing balance = $1,482.54", "Closing balance = $1,300.90")
    assert parsed(
        rows,
        header="Jordan Halloway Account # 840-227-593 September 2, 2026 to September 1, 2026",
        summary=summary,
    ) is None


def test_a_page_that_prints_no_footer_declaration_at_all_refuses():
    """The region-closed check is not redundant with the unreadable-line check:
    with the furniture gone entirely there is no unreadable line left to trip
    over, and the reader would publish a page whose end it never found."""
    doc = document().replace(FOOTER.format(n=1, total=1) + "\n", "").replace(COPYRIGHT + "\n", "")
    assert FOOTER.format(n=1, total=1) not in doc
    assert parse_eq_bank_scanned_statement(doc) is None


def test_a_printed_amount_the_balances_contradict_refuses_even_when_the_totals_agree():
    """Two rows whose printed figures are wrong by opposite amounts sum to the
    bank's own total, walk to the bank's own closing balance and satisfy the
    summary identity. Only the per-row agreement between the printed figure and
    the step between two printed balances says the grid is misread; without it
    this document publishes two amounts the bank did not print."""
    rows = (
        "Sep 2 Inbound transfer $431.62 $1,569.03\n"
        "Sep 3 Inbound transfer $281.64 $1,750.67\n"
    )
    summary = ADDRESS + SUMMARY.replace(
        "Total withdrawals - $268.13", "Total withdrawals - $0.00"
    ).replace("Closing balance = $1,482.54", "Closing balance = $1,750.67")
    assert parsed(rows, summary=summary) is None


def test_a_row_that_moves_no_money_refuses_even_when_it_prints_a_minus():
    """A minus makes the zero-step row agree with the direction check, so the
    zero-step refusal is the only thing left: the printed balances do not
    account for the row, and its direction is therefore not in the document."""
    rows = (
        "Sep 2 Inbound transfer $531.62 $1,569.03\n"
        "Sep 3 Card Load - $268.13 $1,300.90\n"
        "Sep 4 Adjustment - $0.00 $1,300.90\n"
        "Sep 5 Inbound transfer $180.57 $1,481.47\n"
        "Oct 1 Interest received $1.07 $1,482.54\n"
    )
    assert parsed(rows) is None


def test_a_month_with_no_row_at_all_is_not_a_statement_even_when_the_summary_closes():
    """A zero-activity summary closes on itself trivially, walks to its own
    closing balance and matches both printed totals. The empty-ledger refusal
    is what stops a header being published as a statement."""
    summary = ADDRESS + SUMMARY.replace(
        "Total deposits + $713.26", "Total deposits + $0.00"
    ).replace("Total withdrawals - $268.13", "Total withdrawals - $0.00").replace(
        "Closing balance = $1,482.54", "Closing balance = $1,037.41"
    )
    assert parsed("", summary=summary) is None
