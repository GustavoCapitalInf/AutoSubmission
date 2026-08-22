"""The scanned Citizens ROP template: the reader that stopped one glyph short.

W3 §SCANFINISH, closing §DECLINESD D5.1. Every gate here is a place where the
digital text layer and a photograph of the SAME page disagree about a glyph or
about the order two printed columns arrive in — and where the old reader
treated that disagreement as a statement about the document.

Two of the widenings would be tolerances if they stood on their own argument,
so they do not: a comma read as a decimal point and a date cell that lost its
solidus are admitted only when reading them that way makes the section sum
EXACTLY the total the same page prints. The document's own arithmetic is what
accepts them, and a re-read that lands anywhere else is discarded whole.

The statement below is the template's structure with invented figures. It is
not any archive document.
"""
from __future__ import annotations

from analysis.citizens import (
    _checks_the_total_agrees_with,
    _debits_section,
    _rows_the_total_agrees_with,
    _summary,
    detect,
    parse_citizens_statement,
)

PERIOD = ("2026-04-01", "2026-04-30")

HEADER = (
    "Business Account Statement\n"
    "citizensbank.com\n"
    "P.O. Box 7000 Providence, RI 02940\n"
    "ACME WIDGETS LLC\n"
    "Business Advisor Checking for 1234567890\n"
    "Beginning April 01, 2026 through April 30, 2026\n"
)

STRIP = (
    "Balance Calculation\n"
    "Previous Balance 1,000.00\n"
    "Checks - 300.00\n"
    "Debits - 200.00\n"
    "Deposits & Credit + 800.00\n"
    "Current Balance = 1,300.00\n"
)

CHECKS = (
    "Checks\n"
    "Total Checks 300.00\n"
    "Check # Amount Date\n"
    "1001 100.00 04/03\n"
    "1002 200.00 04/10\n"
)

DEBITS = (
    "Debits **\n"
    "Total Debits 200.00\n"
    "ATM/Purchases\n"
    "Date Amount Description\n"
    "04/02 150.00 POS PURCHASE HARDWARE STORE\n"
    "Other Debits\n"
    "Date Amount Description\n"
    "04/05 50.00 MONTHLY SERVICE CHARGE\n"
)

CREDITS = (
    "Deposits & Credits\n"
    "Total Deposits & Credits 800.00\n"
    "Date Amount Description\n"
    "04/01 500.00 REMOTE DEPOSIT\n"
    "04/20 300.00 INCOMING TRANSFER\n"
)

FOOTER = (
    "Current Balance Daily Balance\n"
    "Date Balance Date Balance\n"
    "04/01 1,500.00\n"
)

#: The same footer as a photograph of the same page emits it: the left-hand
#: column first. Nothing about the statement changed.
FOOTER_OCR = (
    "Daily Balance Current Balance\n"
    "Date Balance Date Balance\n"
    "04/01 1,500.00\n"
)


def document(
    *,
    header: str = HEADER,
    strip: str = STRIP,
    checks: str = CHECKS,
    debits: str = DEBITS,
    credits: str = CREDITS,
    footer: str = FOOTER,
) -> str:
    return "--- Page 1 ---\n" + "".join(
        block for block in (header, strip, checks, debits, credits, footer) if block
    )


def whole() -> str:
    return document()


def amounts(stmt) -> list[tuple[str, float]]:
    return sorted((txn.date, txn.amount) for txn in stmt.transactions)


WHOLE_LEDGER = [
    ("2026-04-01", 500.00),
    ("2026-04-02", -150.00),
    ("2026-04-03", -100.00),
    ("2026-04-05", -50.00),
    ("2026-04-10", -200.00),
    ("2026-04-20", 300.00),
]


# ---------------------------------------------------------------------------
# The whole statement
# ---------------------------------------------------------------------------


def test_the_whole_statement_reads_and_reconciles_to_the_printed_strip():
    stmt = parse_citizens_statement(whole())
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == PERIOD
    assert stmt.stated_total_credits == 800.00
    assert stmt.stated_total_debits == 500.00
    assert amounts(stmt) == WHOLE_LEDGER
    assert round(sum(t.amount for t in stmt.transactions), 2) == round(
        stmt.ending_balance - stmt.beginning_balance, 2
    )


# ---------------------------------------------------------------------------
# CF1 - the strip's separator is ink, and its own arithmetic is the gate
# ---------------------------------------------------------------------------


def test_a_subtraction_marker_the_scan_resolved_as_a_leader_dot_still_reads():
    """`Checks .` and `Debits .` are `Checks -` and `Debits -` photographed.
    Requiring the exact glyph declined four archive statements whose strip
    reconciles to the cent."""
    dotted = whole().replace("Checks - 300.00", "Checks . 300.00").replace(
        "Debits - 200.00", "Debits . 200.00"
    )
    stmt = parse_citizens_statement(dotted)
    assert stmt is not None
    assert amounts(stmt) == WHOLE_LEDGER


def test_a_column_rule_beside_the_block_heading_still_reads():
    """`Balance Calculation _ -` is a rule fragment between the heading and
    its first row."""
    ruled = whole().replace("Balance Calculation\n", "Balance Calculation _ -\n")
    assert parse_citizens_statement(ruled) is not None


def test_the_marker_class_never_swallows_a_letter_or_a_figure_or_a_line():
    assert _summary(STRIP.replace("Checks - ", "Checks X ")) is None
    assert _summary(STRIP.replace("Checks - ", "Checks -----")) is None
    assert _summary(STRIP.replace("Balance Calculation\n", "Balance Calculation\n\n")) \
        is not None


def test_a_strip_whose_arithmetic_does_not_close_publishes_nothing():
    """This is what makes the separator safe to treat as furniture. Five
    figures that do not add up are five figures at least one of which was
    misread, and there is then no summary to publish."""
    assert _summary(STRIP.replace("Current Balance = 1,300.00",
                                  "Current Balance = 1,900.00")) is None
    assert parse_citizens_statement(
        whole().replace("Deposits & Credit + 800.00", "Deposits & Credit + 900.00")
    ) is None


def test_the_strip_returns_its_two_debit_rows_separately():
    """`Checks` and `Debits` are two printed rows with two printed totals, and
    each is the oracle for its own section."""
    assert _summary(STRIP) == (1000.00, 300.00, 200.00, 800.00, 1300.00)


# ---------------------------------------------------------------------------
# CF2 - the credit section's end is a printed footer, not a reading order
# ---------------------------------------------------------------------------


def test_the_credit_section_closes_whichever_column_arrives_first():
    """The footer prints `Daily Balance` over its grid on the left and
    `Current Balance = <figure>` on the right. The digital text layer emits the
    right column first; the OCR of the same page emits the left one first.
    Naming one order made the section's end unreachable on every scanned
    statement in the archive — `credit_coverage` 0.000 on all four, a ledger
    publishing no credits at all beside a summary that reconciles."""
    stmt = parse_citizens_statement(document(footer=FOOTER_OCR))
    assert stmt is not None
    assert amounts(stmt) == WHOLE_LEDGER
    credits = [t for t in stmt.transactions if t.amount > 0]
    assert round(sum(t.amount for t in credits), 2) == stmt.stated_total_credits


def test_the_credit_grid_header_survives_a_column_rule_between_its_labels():
    """`Date Amount _ Description` is the same header with the rule between two
    of its labels — which is what a photograph of a ruled table looks like."""
    ruled = whole().replace("Date Amount Description\n04/01 500.00",
                            "Date Amount _ Description\n04/01 500.00")
    stmt = parse_citizens_statement(ruled)
    assert stmt is not None
    assert ("2026-04-01", 500.00) in amounts(stmt)


# ---------------------------------------------------------------------------
# CF3 - the debits container, and the sub-section under a lost heading
# ---------------------------------------------------------------------------


def test_the_container_heading_is_taken_whole():
    assert "04/02 150.00" in _debits_section(whole())
    assert "04/05 50.00" in _debits_section(whole())


def test_a_lost_container_heading_falls_to_the_first_sub_section_not_the_last():
    """One archive scan renders the container heading `sevathie * f Total
    Debits`. Falling straight through to `Other Debits` starts the read AFTER
    the `ATM/Purchases` sub-section and drops every row in it."""
    wrecked = whole().replace("Debits **\n", "sevathie * f\n")
    section = _debits_section(wrecked)
    assert "04/02 150.00" in section
    assert "04/05 50.00" in section
    stmt = parse_citizens_statement(wrecked)
    assert stmt is not None
    assert amounts(stmt) == WHOLE_LEDGER


def test_a_layout_with_no_atm_sub_section_still_reads_its_other_debits():
    plain = whole().replace(
        "Debits **\nTotal Debits 200.00\nATM/Purchases\nDate Amount Description\n"
        "04/02 150.00 POS PURCHASE HARDWARE STORE\n",
        "",
    ).replace("Debits - 200.00", "Debits - 50.00").replace(
        "Current Balance = 1,300.00", "Current Balance = 1,450.00"
    )
    stmt = parse_citizens_statement(plain)
    assert stmt is not None
    assert ("2026-04-05", -50.00) in amounts(stmt)


# ---------------------------------------------------------------------------
# CF4 - a row boundary that one stray glyph could weld shut
# ---------------------------------------------------------------------------


def test_a_stray_glyph_after_the_cents_no_longer_welds_two_printed_rows():
    """A column rule the scan resolves as a full stop — `150.00.` — used to
    make the NEXT row's amount disappear into this row's description, leaving
    the ledger short by it with nothing to show for it."""
    welded = whole().replace("04/02 150.00 POS PURCHASE HARDWARE STORE",
                             "04/02 150.00. POS PURCHASE HARDWARE STORE")
    stmt = parse_citizens_statement(welded)
    assert stmt is not None
    assert amounts(stmt) == WHOLE_LEDGER


def test_nothing_may_extend_the_cents_themselves():
    """The boundary is about the TOKEN, not about the ink after it: a third
    digit means the cents were never the cents."""
    rows = _rows_the_total_agrees_with(
        "04/02 150.007 POS PURCHASE\n", year=2026, sign=-1, printed_total=None
    )
    assert rows == []


def test_a_malformed_amount_never_starts_a_new_row_either():
    """The same statement said at the row BOUNDARY. A token that is not an
    amount is not the start of a row, so the text stays inside the row it was
    printed in and is visible in that row's description — rather than being
    promoted to a row of its own and then silently dropped, which is how a
    printed figure disappears without trace."""
    section = "04/01 500.00 REMOTE DEPOSIT\n04/02 150.007 POS PURCHASE\n"
    rows = _rows_the_total_agrees_with(section, year=2026, sign=1, printed_total=None)
    assert [t.amount for t in rows] == [500.00]
    assert rows[0].description == "REMOTE DEPOSIT 04/02 150.007 POS PURCHASE"


# ---------------------------------------------------------------------------
# CF5 - the two widenings the document's own arithmetic admits
# ---------------------------------------------------------------------------


def test_a_decimal_comma_is_read_only_when_it_makes_the_section_total_close():
    section = "04/02 150,00 POS PURCHASE\n04/05 50.00 SERVICE CHARGE\n"
    strict = _rows_the_total_agrees_with(section, year=2026, sign=-1, printed_total=None)
    assert [t.amount for t in strict] == [-50.00]
    widened = _rows_the_total_agrees_with(section, year=2026, sign=-1, printed_total=200.00)
    assert sorted(t.amount for t in widened) == [-150.00, -50.00]


def test_a_decimal_comma_reading_that_lands_anywhere_else_is_discarded_whole():
    """Including one that OVERSHOOTS. The same shape with a three-digit tail
    (`29,444,311`) is a different accident, and guessing at it would publish a
    figure off by a factor of a thousand."""
    section = "04/02 150,00 POS PURCHASE\n04/05 50.00 SERVICE CHARGE\n"
    for wrong_total in (199.00, 201.00, 50.00):
        rows = _rows_the_total_agrees_with(
            section, year=2026, sign=-1, printed_total=wrong_total
        )
        assert [t.amount for t in rows] == [-50.00], wrong_total


def test_the_strict_reading_is_never_re_read_when_it_already_agrees():
    section = "04/02 150.00 POS PURCHASE\n04/05 50.00 SERVICE CHARGE\n"
    rows = _rows_the_total_agrees_with(section, year=2026, sign=-1, printed_total=200.00)
    assert sorted(t.amount for t in rows) == [-150.00, -50.00]


def test_a_slash_less_cheque_date_is_read_only_on_the_printed_cheque_total():
    grid = "Check # Amount Date\n1001 100.00 0403\n1002 200.00 04/10\nTotal Debits\n"
    strict = _checks_the_total_agrees_with(
        grid, year=2026, period=PERIOD, printed_total=None)
    assert [t.date for t in strict] == ["2026-04-10"]
    widened = _checks_the_total_agrees_with(
        grid, year=2026, period=PERIOD, printed_total=300.00)
    assert sorted(t.date for t in widened) == ["2026-04-03", "2026-04-10"]


def test_when_neither_reading_matches_the_printed_total_the_strict_one_stands():
    """The widened grid is adopted ONLY on the printed total, and `only` is the
    whole of the safety claim: a widened read that agrees with nothing is not
    better evidence than the strict one, it is a second guess. One archive
    statement is exactly this case — its cheque grid reads 50.00 more than the
    page's own `Total Checks`, both strictly and widened (W3 §SCANFINISH SF10)
    — so this is the branch that document actually takes."""
    grid = "Check # Amount Date\n1001 100,00 0403\n1002 200.00 04/10\nTotal Debits\n"
    rows = _checks_the_total_agrees_with(
        grid, year=2026, period=PERIOD, printed_total=999.00)
    assert [t.date for t in rows] == ["2026-04-10"]
    assert round(sum(abs(t.amount) for t in rows), 2) == 200.00


def test_a_widened_cheque_date_must_land_inside_the_printed_period():
    """Without this the widened pattern reads the NEXT cheque's NUMBER as a
    date. `3978` is not a date at all and falls over on its own; `1231` is a
    perfectly good date that this statement cannot possibly carry, and only the
    period says so. A widened read that produces it is discarded whole, which
    is why the cheque that IS readable comes back alone."""
    for not_a_date in ("3978", "1231"):
        grid = (f"Check # Amount Date\n1001 100.00 {not_a_date}\n"
                "1002 200.00 04/10\nTotal Debits\n")
        widened = _checks_the_total_agrees_with(
            grid, year=2026, period=PERIOD, printed_total=300.00)
        assert [t.date for t in widened] == ["2026-04-10"], not_a_date


# ---------------------------------------------------------------------------
# CF6 - the cheque grid is opened by its own column header
# ---------------------------------------------------------------------------


def test_the_cheque_grid_starts_at_its_header_not_at_the_right_hand_total():
    """`Total Checks` and the figure under it belong to a narrow column down
    the page's right edge, and a photograph reads that column's cells out at
    the END of whichever grid row they sit beside — so anchoring the section on
    it started the read one or two printed rows late."""
    late = whole().replace(
        "Checks\nTotal Checks 300.00\nCheck # Amount Date\n1001 100.00 04/03\n",
        "Checks\nCheck # Amount Date\n1001 100.00 04/03 Total Checks 300.00\n",
    )
    stmt = parse_citizens_statement(late)
    assert stmt is not None
    assert ("2026-04-03", -100.00) in amounts(stmt)


def test_the_out_of_sequence_footnote_glyph_does_not_cost_the_cheque():
    """The statement explains the glyph itself — cheques out of numeric
    sequence are denoted with an asterisk — and a photograph resolves it as
    `*`, `"` or nothing. It is a footnote about the SEQUENCE, never part of the
    number."""
    for glyph in ("*", '"', "'"):
        marked = whole().replace("1001 100.00 04/03", f"1001{glyph} 100.00 04/03")
        stmt = parse_citizens_statement(marked)
        assert stmt is not None, glyph
        assert ("2026-04-03", -100.00) in amounts(stmt), glyph


def test_the_asterisk_stays_inside_the_published_cheque_number():
    """It is published in the row's description on every statement that prints
    one, and moving it would move an audited field."""
    stmt = parse_citizens_statement(whole().replace("1001 100.00", "1001* 100.00"))
    assert stmt is not None
    assert any(t.description == "Check 1001*" for t in stmt.transactions)


# ---------------------------------------------------------------------------
# What the reader refuses
# ---------------------------------------------------------------------------


def test_a_statement_with_no_strip_publishes_nothing():
    assert parse_citizens_statement(document(strip="")) is None


def test_a_statement_with_no_ledger_at_all_publishes_nothing():
    header_only = document(checks="", debits="", credits="")
    assert detect(header_only).claims
    assert parse_citizens_statement(header_only) is None


def test_a_document_this_parser_does_not_recognise_is_not_claimed():
    assert not detect(whole().replace("citizensbank.com", "example.com")).claims
    assert not detect(whole().replace("Balance Calculation", "Account Summary")).claims
