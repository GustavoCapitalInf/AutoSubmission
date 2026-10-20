"""FCX — the `+first-citizens-layout` intake extractor (`ocr/native_text.py`).

The generic native reader joins the lines INSIDE a PDF text block with a single
space, and MuPDF hands it this bank's whole description column as one block, so
every printed description in a section arrives welded into one string with
nothing marking the boundaries. Dates and amounts survive as their own blocks.
That is the flattening W3 §FIRSTCIT FI6 recorded, and FI14.1 measured its price:
twelve description-keyed production metrics reading zero on 35 of 35 documents.

These fixtures are synthetic PDFs drawn with PyMuPDF at the coordinates the real
layout uses — a date column, a description column, a right-aligned amount
column, one row per posting, wrapped descriptions on the following line — not
copies of customer documents. Each one pins a rule the extractor must hold:

* the generic pages are preserved BYTE for byte and the rows are additive;
* a description that contains a date is not mistaken for the date column;
* a wrapped line joins the row above it, even when that line carries money;
* a wrapped line cannot bleed across a row, out of a table, or into the next
  section;
* the deposits, cheque and daily-balance grids print a different column header
  and are never read here at all;
* a document with nothing to recover is not claimed, so the ladder falls
  through to the generic rung and the bytes are exactly today's.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from ocr.native_text import (
    FC_ROWS_BEGIN,
    FC_ROWS_END,
    parse_native_first_citizens,
    parse_native_pdf_text,
)
from tests.statements import statements_dir

# The printed template, in points. Rows sit 9pt apart; a description's baseline
# is ~1.3pt above the date and amount it belongs to, which is why row ownership
# is a band rather than an equality.
DATE_X = 37.0
DESC_X = 79.0
AMOUNT_RIGHT = 559.0
ROW_PITCH = 9.0
FONT_SIZE = 7.0

HEAD = (
    "Central Bank Operations - DAC02 P.O. Box 27131 Raleigh, NC 27611-7131\n"
    "Your Account(s) At A Glance\n"
    "Statement Period: April 1 , 2026     Thru April 30, 2054\n"
)


def _right(page, y, text):
    width = fitz.get_text_length(text, fontsize=FONT_SIZE)
    page.insert_text((AMOUNT_RIGHT - width, y), text, fontsize=FONT_SIZE)


def _statement_pdf(sections, *, preamble=HEAD, grids=()):
    """A one-page statement printing `sections` as Date/Description/Amount tables.

    `sections` is `[(heading, [(date, description, amount, [wrapped, ...]), ...])]`
    and `grids` is `[(heading, header_line, [row, ...])]` for the multi-column
    tables (deposits, cheques, daily balances) that print no description column.
    """
    doc = fitz.open()
    page = doc.new_page()
    y = 60.0
    page.insert_textbox(fitz.Rect(DESC_X, 20, 560, 58), preamble, fontsize=FONT_SIZE)

    for heading, rows in sections:
        page.insert_text((DATE_X, y), heading, fontsize=FONT_SIZE)
        y += 13.0
        page.insert_text((DATE_X, y), "Date", fontsize=FONT_SIZE)
        page.insert_text((DESC_X, y), "Description", fontsize=FONT_SIZE)
        _right(page, y, "Amount")
        y += 13.7
        for date, description, amount, wrapped in rows:
            page.insert_text((DATE_X, y), date, fontsize=FONT_SIZE)
            if description:
                page.insert_text((DESC_X, y - 1.3), description, fontsize=FONT_SIZE)
            _right(page, y, amount)
            y += ROW_PITCH
            for extra in wrapped:
                page.insert_text((DESC_X, y - 1.3), extra, fontsize=FONT_SIZE)
                y += ROW_PITCH
        page.insert_text((DESC_X, y), "Total", fontsize=FONT_SIZE)
        _right(page, y, "999.99")
        y += 20.0

    for heading, header, rows in grids:
        page.insert_text((DATE_X, y), heading, fontsize=FONT_SIZE)
        y += 13.0
        page.insert_text((DATE_X, y), header, fontsize=FONT_SIZE)
        y += 13.7
        for row in rows:
            page.insert_text((DATE_X, y), row, fontsize=FONT_SIZE)
            y += ROW_PITCH
        y += 20.0

    # Enough text for the generic rung's own volume gate, which this extractor
    # reuses rather than reimplementing.
    page.insert_textbox(
        fitz.Rect(DATE_X, 700, 560, 780),
        "Direct Customer Inquiry Calls To Personal 1-888-323-4732 " * 12,
        fontsize=FONT_SIZE,
    )
    return doc.tobytes()


def _rows(document):
    return [
        line
        for page in document.pages
        for line in page.splitlines()
        if line.startswith("FC_TX|")
    ]


ONE_SECTION = [
    (
        "Other Debits From Your Account",
        [
            ("04-02", "Overdraft Charge", "36.00", []),
            ("04-03", "Intuit 86148111 Payroll ****2563", "1,147.24", []),
        ],
    )
]


def test_generic_pages_are_preserved_byte_for_byte_and_rows_are_appended():
    pdf = _statement_pdf(ONE_SECTION)
    generic = parse_native_pdf_text(pdf, source_file="fc.pdf")
    layout = parse_native_first_citizens(pdf, source_file="fc.pdf")
    assert generic is not None and layout is not None
    assert layout.model == "native-pdf-text+first-citizens-layout"
    assert len(layout.pages) == len(generic.pages)
    for before, after in zip(generic.pages, layout.pages):
        assert after.startswith(before)
    tail = layout.pages[-1][len(generic.pages[-1]):].splitlines()
    assert tail[0] == "" or tail[0] == FC_ROWS_BEGIN
    assert FC_ROWS_BEGIN in layout.pages[-1] and FC_ROWS_END in layout.pages[-1]
    assert _rows(layout) == [
        "FC_TX|Other Debits From Your Account|04-02|36.00|Overdraft Charge",
        "FC_TX|Other Debits From Your Account|04-03|1,147.24|Intuit 86148111 Payroll ****2563",
    ]


def test_the_generic_reader_really_does_weld_the_column():
    """The defect this exists to repair, pinned so it cannot be argued about."""
    generic = parse_native_pdf_text(_statement_pdf(ONE_SECTION), source_file="fc.pdf")
    assert generic is not None
    welded = [
        line
        for page in generic.pages
        for line in page.splitlines()
        if "Overdraft Charge" in line
    ]
    assert len(welded) == 1
    assert "Intuit 86148111 Payroll ****2563" in welded[0]


def test_a_description_carrying_a_date_is_not_read_as_the_date_column():
    pdf = _statement_pdf(
        [
            (
                "Other Debits From Your Account",
                [("04-13", "ACH Batch         04-13 Seq #  5041", "1,700.00", [])],
            )
        ]
    )
    document = parse_native_first_citizens(pdf, source_file="fc.pdf")
    assert _rows(document) == [
        "FC_TX|Other Debits From Your Account|04-13|1,700.00|ACH Batch         04-13 Seq #  5041"
    ]


def test_a_wrapped_description_joins_its_own_row_even_when_it_carries_money():
    """The trap the handoff named: a memo continuation that looks like a cell.

    The wrapped line prints in the DESCRIPTION column, so the money in it is
    part of the merchant memo, not the row's amount — and the row below must not
    inherit any of it.
    """
    pdf = _statement_pdf(
        [
            (
                "Other Debits From Your Account",
                [
                    ("04-26", "Purchase       Visa #8269       04-26 ATM 061455", "38.46",
                     ["The Home Depot   Invoice 250.00 Ref 9911   Spartanburg  SC"]),
                    ("04-26", "POS Sig 04/25 Visa #8269 Lowes #00528*", "240.03", []),
                ],
            )
        ]
    )
    document = parse_native_first_citizens(pdf, source_file="fc.pdf")
    assert _rows(document) == [
        "FC_TX|Other Debits From Your Account|04-26|38.46|"
        "Purchase       Visa #8269       04-26 ATM 061455 "
        "The Home Depot   Invoice 250.00 Ref 9911   Spartanburg  SC",
        "FC_TX|Other Debits From Your Account|04-26|240.03|"
        "POS Sig 04/25 Visa #8269 Lowes #00528*",
    ]


@pytest.mark.parametrize("rows_before", [1, 2])
@pytest.mark.parametrize("stray_gap", [13.0, 2 * ROW_PITCH])
def test_a_lone_line_below_the_last_row_is_not_joined(rows_before, stray_gap):
    """The continuation window, in both the states it can be in.

    A continuation prints on the NEXT printed line. Anything further down is
    something else, and joining it would publish a footnote — or another row's
    text — as this posting's description.

    `stray_gap=13.0` is the case that made this fixture worth repointing: it is
    wider than the row pitch but NARROWER than the header-to-first-row gap the
    window used to be seeded from, so on a ONE-row table the old rule swallowed
    it and this parametrisation goes red against that rule. The window now comes
    from the table's own row pitch, or from the row's printed line box while
    there is only one row.
    """
    doc = fitz.open()
    page = doc.new_page()
    y = 60.0
    page.insert_text((DATE_X, y), "Other Debits From Your Account", fontsize=FONT_SIZE)
    y += 13.0
    page.insert_text((DATE_X, y), "Date", fontsize=FONT_SIZE)
    page.insert_text((DESC_X, y), "Description", fontsize=FONT_SIZE)
    _right(page, y, "Amount")
    y += 13.7
    for index in range(rows_before):
        page.insert_text((DATE_X, y), f"04-0{index + 2}", fontsize=FONT_SIZE)
        page.insert_text((DESC_X, y - 1.3), f"Coast Payment 939{index}", fontsize=FONT_SIZE)
        _right(page, y, "369.67")
        y += ROW_PITCH
    page.insert_text(
        (DESC_X, y - ROW_PITCH + stray_gap), "Detached Footnote Line", fontsize=FONT_SIZE
    )
    page.insert_textbox(fitz.Rect(DESC_X, 300, 560, 340), HEAD, fontsize=FONT_SIZE)
    page.insert_textbox(
        fitz.Rect(DATE_X, 700, 560, 780),
        "Direct Customer Inquiry Calls To Personal 1-888-323-4732 " * 12,
        fontsize=FONT_SIZE,
    )
    document = parse_native_first_citizens(doc.tobytes(), source_file="fc.pdf")
    assert _rows(document) == [
        f"FC_TX|Other Debits From Your Account|04-0{index + 2}|369.67|Coast Payment 939{index}"
        for index in range(rows_before)
    ]


def test_a_wrapped_line_cannot_reach_past_the_printed_total():
    """`Total` prints a money cell of its own, so it is never a lone cell."""
    pdf = _statement_pdf(
        [
            (
                "Other Credits To Your Account",
                [("04-02", "Workiz Inc Payout *jgzcz6A6G0Hbd2", "246.51", [])],
            ),
            (
                "Other Debits From Your Account",
                [("04-20", "Coast Payment 9392", "369.67", [])],
            ),
        ]
    )
    document = parse_native_first_citizens(pdf, source_file="fc.pdf")
    assert _rows(document) == [
        "FC_TX|Other Credits To Your Account|04-02|246.51|Workiz Inc Payout *jgzcz6A6G0Hbd2",
        "FC_TX|Other Debits From Your Account|04-20|369.67|Coast Payment 9392",
    ]


def test_the_multi_column_grids_are_never_read():
    """Deposits, cheques and daily balances print no description column at all."""
    pdf = _statement_pdf(
        ONE_SECTION,
        grids=[
            ("Deposits To Your Account", "Date Amount Date Amount Date Amount",
             ["04             3,698.39 04             1,000.00", "-02 -05"]),
            ("Checks Paid From Your Account",
             "Check No. Date Amount Check No. Date Amount",
             ["1181 04-03 1,450.00 1183 04-09 877.00"]),
            ("Daily Balance Summary", "Date Balance Date Balance",
             ["04             2,511.31+ 04               242.32+", "-02 -03"]),
        ],
    )
    document = parse_native_first_citizens(pdf, source_file="fc.pdf")
    sections = {line.split("|")[1] for line in _rows(document)}
    assert sections == {"Other Debits From Your Account"}


def test_a_table_the_page_does_not_name_is_not_read():
    """Nothing here guesses which section an unheaded run of postings belongs to."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((DATE_X, 60.0), "Date", fontsize=FONT_SIZE)
    page.insert_text((DESC_X, 60.0), "Description", fontsize=FONT_SIZE)
    _right(page, 60.0, "Amount")
    page.insert_text((DATE_X, 73.7), "04-02", fontsize=FONT_SIZE)
    page.insert_text((DESC_X, 72.4), "Overdraft Charge", fontsize=FONT_SIZE)
    _right(page, 73.7, "36.00")
    page.insert_textbox(fitz.Rect(DATE_X, 100, 560, 300), HEAD, fontsize=FONT_SIZE)
    page.insert_textbox(
        fitz.Rect(DATE_X, 300, 560, 500),
        "Direct Customer Inquiry Calls To Personal 1-888-323-4732 " * 12,
        fontsize=FONT_SIZE,
    )
    assert parse_native_first_citizens(doc.tobytes(), source_file="fc.pdf") is None


def test_a_document_outside_the_family_is_not_claimed():
    pdf = _statement_pdf(
        ONE_SECTION,
        preamble="COMMUNITY TRUST BANK\nStatement of Account\nDate Description Amount\n",
    )
    assert parse_native_first_citizens(pdf, source_file="fc.pdf") is None


def test_a_family_document_with_nothing_to_recover_falls_through_unchanged():
    pdf = _statement_pdf(
        [],
        grids=[
            ("Deposits To Your Account", "Date Amount Date Amount",
             ["04             3,698.39", "-02"]),
        ],
    )
    assert parse_native_first_citizens(pdf, source_file="fc.pdf") is None
    assert parse_native_pdf_text(pdf, source_file="fc.pdf") is not None


def test_a_pdf_without_usable_native_text_is_refused_by_the_same_gate():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Central Bank Operations - DAC02")
    pdf = doc.tobytes()
    assert parse_native_pdf_text(pdf, source_file="fc.pdf") is None
    assert parse_native_first_citizens(pdf, source_file="fc.pdf") is None


@pytest.mark.parametrize("field", ["section", "description"])
def test_a_field_that_would_corrupt_the_encoding_is_not_reported(field):
    heading = "Other Debits | And More" if field == "section" else "Other Debits From Your Account"
    description = "Coast | Payment 9392" if field == "description" else "Coast Payment 9392"
    pdf = _statement_pdf([(heading, [("04-20", description, "369.67", [])])])
    document = parse_native_first_citizens(pdf, source_file="fc.pdf")
    assert document is None


def test_the_intake_ladder_reaches_this_rung_before_the_generic_one():
    """Six call sites share one rung order; this pins that this rung is in it."""
    from ocr.pipeline import _native_statement

    document = _native_statement(_statement_pdf(ONE_SECTION), source_file="fc.pdf")
    assert document is not None
    assert document.model == "native-pdf-text+first-citizens-layout"


# ---------------------------------------------------------------------------
# The pinned corpus document, end to end through the real ladder
# ---------------------------------------------------------------------------

PINNED = Path("Others", "First Citizen", "First Citizens Bank.pdf")


@pytest.mark.corpus
def test_the_pinned_statement_recovers_its_printed_descriptions_and_nothing_else():
    """W3 §FIRSTCIT FI14.1, closed.

    Six production metrics read zero on this document because the classifier
    was handed `Other Debit` where the bank had printed `Overdraft Charge`,
    `Auto-Owners Ins. Prem` and `POS Sig ... Visa #8269`. The recovery restores
    exactly those six and moves no balance, no ADB input and no count: both
    readings are taken here, in one process, off the same bytes.
    """
    from analysis.parser_registry import admissible_text
    from analysis.pipeline import analyze_markdown
    from ocr.pipeline import _native_statement

    pdf = (statements_dir() / PINNED).read_bytes()
    generic = parse_native_pdf_text(pdf, source_file=PINNED.name)
    layout = _native_statement(pdf, source_file=PINNED.name)
    assert generic is not None and layout is not None
    assert layout.model == "native-pdf-text+first-citizens-layout"
    assert len(layout.pages) == len(generic.pages)
    for before, after in zip(generic.pages, layout.pages):
        assert after.startswith(before)

    before_report = analyze_markdown(generic.to_markdown(), parse_mode="deterministic")
    after_report = analyze_markdown(layout.to_markdown(), parse_mode="deterministic")

    assert before_report.statement.model_dump(
        exclude={"transactions"}
    ) == after_report.statement.model_dump(exclude={"transactions"})
    assert [
        (t.date, t.amount, t.direction) for t in before_report.statement.transactions
    ] == [(t.date, t.amount, t.direction) for t in after_report.statement.transactions]
    for field in (
        "average_daily_balance", "adb", "adb_ok", "daily_balance_sum",
        "calendar_day_count", "days_in_period", "min_balance", "max_balance",
        "negative_days", "total_deposits", "total_withdrawals", "num_deposits",
        "num_withdrawals", "total_posted_credits", "total_posted_credit_count",
    ):
        assert getattr(before_report.metrics, field) == getattr(
            after_report.metrics, field
        ), field

    assert (before_report.metrics.nsf_count, after_report.metrics.nsf_count) == (0, 1)
    # R18: the underwriting NSF count is negative-ending days in the daily ledger, which recovered
    # descriptions do not move; the recovered fee row is a returned item, counted in nsf_count above.
    assert (
        before_report.metrics.effective_nsf_count,
        before_report.metrics.nsf_source,
    ) == (
        after_report.metrics.effective_nsf_count,
        after_report.metrics.nsf_source,
    )
    assert (
        before_report.metrics.insurance_count,
        after_report.metrics.insurance_count,
    ) == (0, 1)
    assert (
        before_report.metrics.insurance_total,
        after_report.metrics.insurance_total,
    ) == (0.0, 494.00)
    assert (before_report.metrics.pos_count, after_report.metrics.pos_count) == (0, 18)
    assert (
        before_report.metrics.ach_debit_count,
        after_report.metrics.ach_debit_count,
    ) == (0, 5)

    labels = {"Other Credit", "Other Debit"}
    assert sum(
        1 for t in before_report.statement.transactions if t.description in labels
    ) == 95
    assert not any(
        t.description in labels for t in after_report.statement.transactions
    )
    assert admissible_text(layout.to_markdown()).count("FC_TX|") == 95
