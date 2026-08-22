"""The scanned Southside template: the grid the bank prints, read as a grid.

W3 §SCANFINISH. What is under test is not "it parses" — every one of these
gates exists because a photograph of this template defeats an exact spelling,
and the failure modes are asymmetric. Publishing a daily-balance cell as a
withdrawal invents money; repairing a damaged date cell by preference dates a
payment to a day it was not made on; inferring a count from a total that
happens to be zero publishes a measurement nobody made.

The synthetic statement below is the template's structure with invented
figures. It is not any archive document, and nothing in this file is a
memorised reading of one.
"""
from __future__ import annotations

from analysis.scanned_small_bank import (
    _southside_day,
    _southside_grids,
    _southside_money,
    _southside_posted_days,
    _southside_row_date,
    _southside_summary,
    detect_southside,
    parse_southside_scanned_statement,
)

PERIOD = ("2026-04-01", "2026-04-30")

MASTHEAD = (
    "<B SOUTHSIDE STATEMENT OF ACCOUNT\n"
    "PO BOX 1079, TYLER, TX 75710-1079\n"
    "ACCOUNT NUMBER 1234567\n"
    "ACME WIDGETS, LLC\n"
    "100 MAIN ST\n"
    "TYLER TX 75702-0000\n"
)

SUMMARY = (
    "ACCOUNT SUMMARY\n"
    "Smart Business\n"
    "Account Number 1234567 Statement Dates 4/01/26 thru 4/30/26\n"
    "Previous Balance 1,000.00 Days in Statement Period 30\n"
    "2 Deposits/Credits 800.00\n"
    "3 Checks/Debits 500.00\n"
    "Total Service Charge 0.00\n"
    "Interest Paid 0.00\n"
    "Ending Balance 1,300.00\n"
)

DEPOSITS = (
    "*** DEPOSITS ***\n"
    "Date Description Amount\n"
    "4/01 Regular Deposit 500.00\n"
    "4/15 Telephone transfer 300.00\n"
)

WITHDRAWALS = (
    "*** WITHDRAWALS ***\n"
    "Date Description Amount\n"
    "4/02 ONLINE PMT UTILITY CO CCD 200.00\n"
)

CHECKS = (
    "*** SUMMARY BY CHECK NUMBER ***\n"
    "Listed in numerical order\n"
    "Date Check Number Amount\n"
    "4/03 1001 100.00 4/10 1002 200.00\n"
)

DAILY = (
    "*** DAILY BALANCE SUMMARY ***\n"
    "Date Balance Date Balance Date Balance\n"
    "4/01 1,500.00 4/02 1,300.00 4/03 1,200.00\n"
    "4/10 1,000.00 4/15 1,300.00\n"
)

FOOTER = "Member\nCSI REV 010101 FDIC 1234-STMT\n"


def document(
    *,
    summary: str = SUMMARY,
    deposits: str = DEPOSITS,
    withdrawals: str = WITHDRAWALS,
    checks: str = CHECKS,
    daily: str = DAILY,
    masthead: str = MASTHEAD,
    extra: str = "",
) -> str:
    """One sheet of the template, in the markdown the intake ladder emits."""
    body = ["--- Page 1 ---", masthead, summary]
    for block in (deposits, withdrawals, checks, daily):
        if block:
            body.append(block)
    body.append(FOOTER)
    if extra:
        body.append(extra)
    return "\n".join(body) + "\n"


def whole() -> str:
    return document()


def amounts(stmt) -> list[tuple[str, float]]:
    return sorted((txn.date, txn.amount) for txn in stmt.transactions)


# ---------------------------------------------------------------------------
# The whole statement
# ---------------------------------------------------------------------------


def test_the_whole_statement_reads_and_its_ledger_reproduces_the_printed_grid():
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == PERIOD
    assert stmt.days_in_period == 30
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 3
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1300.00
    assert amounts(stmt) == [
        ("2026-04-01", 500.00),
        ("2026-04-02", -200.00),
        ("2026-04-03", -100.00),
        ("2026-04-10", -200.00),
        ("2026-04-15", 300.00),
    ]
    # The bank's own printed daily grid, walked from the beginning balance.
    walked, carry = {}, stmt.beginning_balance
    for txn in sorted(stmt.transactions, key=lambda t: t.date):
        carry = round(carry + txn.amount, 2)
        walked[txn.date] = carry
    assert walked == {
        "2026-04-01": 1500.00,
        "2026-04-02": 1300.00,
        "2026-04-03": 1200.00,
        "2026-04-10": 1000.00,
        "2026-04-15": 1300.00,
    }


# ---------------------------------------------------------------------------
# SF1 - the detector names the issuer's print, never the customer's words
# ---------------------------------------------------------------------------


def test_the_detector_claims_the_masthead_plus_the_summary_row_labels():
    assert detect_southside(whole()).claims


def test_a_statement_whose_grid_heading_the_scan_destroyed_is_still_claimed():
    """The heading is one line of large print and the rows beneath it survive
    it. Gating on the heading is what hid six of this issuer's nine archive
    statements behind a reader that could read them."""
    without_heading = whole().replace("ACCOUNT SUMMARY\n", "AGCOUNT SUMMAaY\n")
    assert detect_southside(without_heading).claims
    assert parse_southside_scanned_statement(without_heading) is not None


def test_the_detector_needs_all_three_summary_rows_and_the_masthead():
    for row in ("2 Deposits/Credits 800.00", "3 Checks/Debits 500.00",
                "Days in Statement Period 30"):
        maimed = whole().replace(row, "")
        assert not detect_southside(maimed).claims, row
    assert not detect_southside(whole().replace("SOUTHSIDE", "NORTHSIDE")).claims


# ---------------------------------------------------------------------------
# SF2 - the summary is a labelled grid, and its own arithmetic admits it
# ---------------------------------------------------------------------------


def test_one_mis_resolved_margin_glyph_no_longer_takes_the_whole_summary_down():
    """The furniture between the printed rows is the page's ROTATED LEFT
    MARGIN, and Tesseract resolves those glyphs as digits as readily as
    letters. The single regex this replaced spanned all seven rows with `\\D`
    between them, so one digit in the margin declined the document."""
    with_margin_digits = whole().replace(
        "2 Deposits/Credits 800.00\n3 Checks/Debits 500.00",
        "z 2 Deposits/Credits 800.00\n4 3 Checks/Debits 500.00",
    )
    stmt = parse_southside_scanned_statement(with_margin_digits)
    assert stmt is not None
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 3


def test_a_row_the_scan_destroyed_costs_that_row_and_not_the_document():
    """Reading the grid row by row is what makes the damage local. The service
    charge is optional; the rows the reader cannot do without are named."""
    stmt = parse_southside_scanned_statement(
        whole().replace("Total Service Charge 0.00\n", "Total Sarvice Gharge O.0O\n")
    )
    assert stmt is not None
    assert stmt.stated_service_charge is None


def test_a_count_whose_digit_did_not_survive_is_unknown_and_not_inferred():
    """`Q Checks/Debits 0.00` is the archive shape: the digit `0` resolved as a
    letter. Inferring the count from the total being zero would publish a
    measurement nobody made."""
    stmt = parse_southside_scanned_statement(
        whole().replace("3 Checks/Debits 500.00", "Q Checks/Debits 500.00")
    )
    assert stmt is not None
    assert stmt.stated_debit_count is None
    assert stmt.stated_total_debits == 500.00


def test_a_summary_whose_arithmetic_does_not_close_publishes_nothing():
    """`previous + credits - debits == ending`, to the cent. This is what lets
    the row labels be matched loosely: five figures that do not add up are five
    figures at least one of which was misread."""
    assert parse_southside_scanned_statement(
        whole().replace("Ending Balance 1,300.00", "Ending Balance 1,900.00")
    ) is None


def test_a_summary_missing_a_required_row_publishes_nothing():
    for row in ("Previous Balance 1,000.00 ", "Ending Balance 1,300.00\n",
                "Days in Statement Period 30", "2 Deposits/Credits 800.00\n"):
        maimed = whole().replace(row, "")
        assert parse_southside_scanned_statement(maimed) is None, row


def test_the_summary_reader_in_isolation():
    found = _southside_summary(SUMMARY)
    assert found is not None
    assert found["days"] == 30
    assert found["credit_count"] == 2
    assert found["debit_total"] == 500.00
    assert _southside_summary(SUMMARY.replace("1,300.00", "1,301.00")) is None


# ---------------------------------------------------------------------------
# SF3 - a money cell whose decimal point the scan resolved as a comma
# ---------------------------------------------------------------------------


def test_a_comma_before_exactly_two_digits_at_the_end_is_the_decimal_point():
    """A thousands group is THREE digits, so the token has told us which glyph
    it is. This is the token's shape, not a preference for one separator."""
    assert _southside_money("225,00") == 225.00
    assert _southside_money("9,000,00") == 9000.00
    assert _southside_money("2,549,33") == 2549.33
    assert _southside_money("1,234.56") == 1234.56


def test_an_ambiguous_token_is_left_to_the_shared_grammar():
    """`1,234` says nothing about its own separator, so this reader decides
    nothing about it."""
    assert _southside_money("1,234") == _southside_money("1,234")
    assert _southside_money("29,444,311") == 29444311.0


def test_a_row_whose_decimal_point_became_a_comma_still_reads():
    stmt = parse_southside_scanned_statement(
        whole().replace("4/02 ONLINE PMT UTILITY CO CCD 200.00",
                        "4/02 ONLINE PMT UTILITY CO CCD 200,00")
    )
    assert stmt is not None
    assert ("2026-04-02", -200.00) in amounts(stmt)


# ---------------------------------------------------------------------------
# SF4 - a grid ends where the next grid begins
# ---------------------------------------------------------------------------


def test_a_one_page_statement_keeps_its_withdrawals():
    """The old boundary for this grid was the literal page separator `--- Page
    2 ---`. A one-page statement has none, so the search failed and two printed
    withdrawals read as zero."""
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    assert [t.date for t in stmt.transactions if t.amount == -200.00 and "ONLINE" in t.description] \
        == ["2026-04-02"]


def test_a_daily_balance_cell_is_never_published_as_a_withdrawal():
    """The grid that follows the withdrawals is the daily-balance grid, and
    running into it publishes a balance as a payment — a reader inventing
    money (`debit_coverage` 1.248 on an archive statement)."""
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    debits = [abs(t.amount) for t in stmt.transactions if t.amount < 0]
    assert sum(debits) == 500.00
    assert 1500.00 not in debits and 1300.00 not in debits


def test_a_grid_that_continues_across_a_sheet_break_keeps_its_later_rows():
    """The bank reprints only the column header on a continuation sheet, so
    the span must survive the break with no rule of its own."""
    paged = whole().replace(
        "4/15 Telephone transfer 300.00\n",
        "--- Page 2 ---\n" + MASTHEAD + "Date Description Amount\n"
        "4/15 Telephone transfer 300.00\n",
    )
    stmt = parse_southside_scanned_statement(paged)
    assert stmt is not None
    assert ("2026-04-15", 300.00) in amounts(stmt)


def test_a_heading_the_scan_mangled_around_its_words_still_bounds_its_grid():
    """`*** WITHDRAWALS ***`, `[eee *** WITHDRAWALS **` and `: ?WITHDRAWALS ***
    Sos .` are one heading photographed three times. The words survive; the
    asterisks do not."""
    mangled = whole().replace("*** WITHDRAWALS ***", "[eee *** WITHDRAWALS **  Sos .")
    stmt = parse_southside_scanned_statement(mangled)
    assert stmt is not None
    assert amounts(stmt) == amounts(parse_southside_scanned_statement(whole()))


def test_a_heading_line_must_carry_a_rule_glyph():
    """A heading is set with rules; a DESCRIPTION that happens to contain the
    word is a ledger row and must not open a grid."""
    grids = _southside_grids(
        "*** DEPOSITS ***\n4/01 Regular Deposit 500.00\n"
        "4/02 REFUND OF WITHDRAWALS FEE 5.00\n"
        "*** DAILY BALANCE SUMMARY ***\n4/01 100.00\n"
    )
    assert "REFUND OF WITHDRAWALS FEE" in grids["deposits"]
    assert grids["withdrawals"] == ""


def test_the_cheque_image_sheets_end_the_grid_above_them():
    """The sheets after the ledger are photographs of cheques and deposit
    tickets, and they carry dates and figures of their own."""
    with_images = whole() + (
        "--- Page 2 ---\nSouthside Bank Page: 2 of 2\n"
        "Credit DDA Deposit\nSUBSTITUTE IMAGE / VIRTUAL DOCUMENT\n"
        "4/22 999999 9,999.99\n"
    )
    stmt = parse_southside_scanned_statement(with_images)
    assert stmt is not None
    assert all(abs(t.amount) != 9999.99 for t in stmt.transactions)


# ---------------------------------------------------------------------------
# SF5 - a damaged date cell is enumerated, never repaired by preference
# ---------------------------------------------------------------------------


def test_a_clean_cell_reads_as_itself():
    assert _southside_day("4/17", PERIOD) == "2026-04-17"
    assert _southside_day("4/01", PERIOD) == "2026-04-01"


def test_a_cell_outside_the_printed_period_is_not_a_date():
    assert _southside_day("5/17", PERIOD) is None
    assert _southside_day("2/30", PERIOD) is None


def test_a_two_glyph_residue_is_refused_however_readable_it_looks():
    """This template zero-pads the day in every cell it prints, so `47` cannot
    be a whole cell that merely lost its solidus. It is `4/17`, `4/07` or
    `4/27` with two glyphs gone, and nothing in the token says which. Reading
    it as `4/7` looked unique and was wrong on an archive statement."""
    assert _southside_day("47", PERIOD) is None
    assert _southside_day("41", PERIOD) is None


def test_a_lost_solidus_reads_only_when_exactly_one_reading_is_possible():
    assert _southside_day("413", PERIOD) == "2026-04-13"
    assert _southside_day("0413", ("2026-04-01", "2026-04-30")) == "2026-04-13"
    # `1130` inside a period spanning the new year is `1/13` in the later year
    # and `11/30` in the earlier one at once.
    across = ("2025-11-01", "2026-01-31")
    assert _southside_day("1130", across) is None


def test_the_year_comes_from_the_period_and_from_both_ends_of_it():
    """The cell carries no year. This template prints a period inside one
    month, so both ends agree and the second offer changes nothing — but a
    period the scan damaged into spanning a new year would otherwise drop
    every row on the far side of it without saying so."""
    across = ("2025-12-15", "2026-01-14")
    assert _southside_day("12/20", across) == "2025-12-20"
    assert _southside_day("1/05", across) == "2026-01-05"
    assert _southside_day("2/05", across) is None


def test_a_solidus_resolved_as_a_digit_is_admitted_only_for_one_and_seven():
    """`4101` is `4/01` and `4724` is `4/24`; those are the glyphs a solidus is
    confused with. `4801` is not offered that reading."""
    assert _southside_day("4101", PERIOD) == "2026-04-01"
    assert _southside_day("4724", PERIOD) == "2026-04-24"
    assert _southside_day("4801", PERIOD) is None


def test_a_reconstructed_day_must_be_a_day_the_printed_grid_names():
    """The daily-balance grid prints a cell for every day the account MOVED, so
    a day it does not name is a day nothing posted on. That is the
    corroboration a damaged cell needs and a clean one does not."""
    posted = _southside_posted_days(DAILY, PERIOD)
    assert posted == {"2026-04-01", "2026-04-02", "2026-04-03",
                      "2026-04-10", "2026-04-15"}
    assert _southside_row_date(["413"], PERIOD, posted) is None
    assert _southside_row_date(["410"], PERIOD, posted) == ("2026-04-10", 1)


def test_a_clean_cell_beats_stray_margin_ink_that_reads_as_a_date():
    """The left margin drops one or two glyphs into the row, and one of those
    can itself be a readable date. The cell the bank printed cleanly is taken
    first, wherever on the line it stands."""
    posted = _southside_posted_days(DAILY, PERIOD)
    assert _southside_row_date(["410", "4/02", "PAYMENT"], PERIOD, posted) \
        == ("2026-04-02", 2)


def test_a_row_whose_date_cell_cannot_be_read_is_dropped_not_dated():
    stmt = parse_southside_scanned_statement(
        whole().replace("4/02 ONLINE PMT UTILITY CO CCD 200.00",
                        "AN ONLINE PMT UTILITY CO CCD 200.00")
    )
    assert stmt is not None
    assert all(t.description != "ONLINE PMT UTILITY CO CCD" for t in stmt.transactions)


# ---------------------------------------------------------------------------
# SF6 - the row grammar is structural, not a memorised glyph list
# ---------------------------------------------------------------------------


def test_margin_ink_before_the_date_is_not_a_memorised_list():
    """What this replaced stripped six named OCR glyphs off the front of each
    line. That list is a reading of six statements; a seventh photograph makes
    a seventh glyph."""
    for junk in ("ae", "if", "cy", "z", "ee", "a", "Ei", "@", "%s"):
        stmt = parse_southside_scanned_statement(
            whole().replace("4/01 Regular Deposit 500.00",
                            f"{junk} 4/01 Regular Deposit 500.00")
        )
        assert stmt is not None, junk
        assert ("2026-04-01", 500.00) in amounts(stmt), junk


def test_a_row_with_no_description_left_is_dropped():
    stmt = parse_southside_scanned_statement(
        whole().replace("4/02 ONLINE PMT UTILITY CO CCD 200.00", "4/02 200.00")
    )
    assert stmt is not None
    assert all(t.date != "2026-04-02" for t in stmt.transactions)


def test_the_column_header_is_not_read_as_a_row():
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    assert all("Description" not in t.description for t in stmt.transactions)


# ---------------------------------------------------------------------------
# SF7 - the cheque grid
# ---------------------------------------------------------------------------


def test_the_cheque_grid_reads_several_cheques_to_a_printed_line():
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    cheques = sorted(
        (t.date, t.amount) for t in stmt.transactions if t.description.startswith("Check ")
    )
    assert cheques == [("2026-04-03", -100.00), ("2026-04-10", -200.00)]


def test_a_cheque_whose_date_cell_was_reconstructed_needs_the_printed_grid():
    """A cheque number is a run of digits sitting beside a date cell, so a
    widened date reading here is the easiest way to date a payment to a day it
    was not made on."""
    reconstructed = whole().replace("4/03 1001 100.00", "403 1001 100.00")
    stmt = parse_southside_scanned_statement(reconstructed)
    assert stmt is not None
    assert ("2026-04-03", -100.00) in amounts(stmt)

    off_grid = whole().replace(
        "4/03 1001 100.00 4/10 1002 200.00", "413 1001 100.00 4/10 1002 200.00"
    )
    stmt = parse_southside_scanned_statement(off_grid)
    assert stmt is not None
    assert all(not t.description.startswith("Check 1001") for t in stmt.transactions)


def test_the_out_of_sequence_asterisk_does_not_cost_the_row():
    stmt = parse_southside_scanned_statement(
        whole().replace("4/03 1001 100.00", "4/03 1001* 100.00")
    )
    assert stmt is not None
    assert ("2026-04-03", -100.00) in amounts(stmt)


# ---------------------------------------------------------------------------
# What the reader refuses outright
# ---------------------------------------------------------------------------


def test_a_document_with_fewer_rows_than_the_stated_credit_count_refuses():
    assert parse_southside_scanned_statement(document(deposits="", checks="")) is None


def test_a_summary_with_no_ledger_at_all_publishes_nothing():
    header_only = document(deposits="", withdrawals="", checks="")
    assert detect_southside(header_only).claims
    assert parse_southside_scanned_statement(header_only) is None
