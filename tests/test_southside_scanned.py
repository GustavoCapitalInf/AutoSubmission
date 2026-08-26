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
    daily_grid_amount_contradictions,
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
# SS-UNIQUE-MATCH — one distinct reading per printed row (W3 §SCANHYG)
# ---------------------------------------------------------------------------


def test_a_required_summary_row_printed_twice_with_two_values_refuses():
    """There is no rule that says which printing to believe, and taking the
    first is picking one. A two-account printing under one heading is exactly
    what produces this shape."""
    contradicted = whole().replace(
        "Previous Balance 1,000.00 Days in Statement Period 30\n",
        "Previous Balance 1,000.00 Days in Statement Period 30\n"
        "Previous Balance 9,000.00\n",
    )
    assert parse_southside_scanned_statement(contradicted) is None


def test_a_required_summary_row_printed_twice_and_AGREEING_still_reads():
    """A page header repeating itself is corroboration, not contradiction: the
    test is on the captured values, never on the number of printings."""
    repeated = whole().replace(
        "Previous Balance 1,000.00 Days in Statement Period 30\n",
        "Previous Balance 1,000.00 Days in Statement Period 30\n"
        "Previous Balance 1,000.00 Days in Statement Period 30\n",
    )
    stmt = parse_southside_scanned_statement(repeated)
    assert stmt is not None
    assert stmt.beginning_balance == 1000.00
    assert stmt.days_in_period == 30


def test_an_optional_summary_row_printed_twice_with_two_values_is_unknown():
    """The optional rows are not in the grid's identity, so a contradiction
    there costs that row and not the document — the same answer this reader
    already gives a count whose digit did not survive."""
    contradicted = whole().replace(
        "Interest Paid 0.00\n", "Interest Paid 0.00\nInterest Paid 4.19\n"
    )
    stmt = parse_southside_scanned_statement(contradicted)
    assert stmt is not None
    assert stmt.stated_interest_paid is None
    assert stmt.beginning_balance == 1000.00


def test_the_two_counted_rows_refuse_a_contradicting_second_printing():
    contradicted = whole().replace(
        "3 Checks/Debits 500.00\n", "3 Checks/Debits 500.00\n7 Checks/Debits 900.00\n"
    )
    assert parse_southside_scanned_statement(contradicted) is None


def test_a_figure_on_the_line_below_a_label_does_not_answer_it():
    """`\\s` matches a newline; a row of this grid is printed on one line. With
    the vertical class the margin echo below would be read as a SECOND
    `Previous Balance` and would refuse a document that is perfectly good."""
    echoed = document(extra="Previous Balance\n2,750.00 rotated margin ink\n")
    stmt = parse_southside_scanned_statement(echoed)
    assert stmt is not None
    assert stmt.beginning_balance == 1000.00


def test_a_count_digit_the_scan_made_a_superscript_is_unknown_not_a_crash():
    """`str.isdigit()` is True for U+00B2 and `int()` rejects it, so the
    reader that used it raised `ValueError` out of the parser on a scan that
    resolved this cell as a superscript. `isdecimal()` is exactly `int()`'s
    domain, so the cell is simply illegible and the count is unknown."""
    superscript = whole().replace("3 Checks/Debits 500.00", "² Checks/Debits 500.00")
    stmt = parse_southside_scanned_statement(superscript)
    assert stmt is not None
    assert stmt.stated_debit_count is None
    assert stmt.stated_total_debits == 500.00


# ---------------------------------------------------------------------------
# SF3 - a money cell whose decimal point the scan resolved as a comma
# ---------------------------------------------------------------------------


def test_a_comma_before_exactly_two_digits_at_the_end_is_the_decimal_point():
    """A thousands group is THREE digits, so the token has told us which glyph
    it is. This is the token's shape, not a preference for one separator."""
    assert _southside_money("225,00") == 225.00
    assert _southside_money("9,000,00") == 9000.00
    assert _southside_money("6,180,44") == 6180.44
    assert _southside_money("1,234.56") == 1234.56


def test_an_ambiguous_token_is_left_to_the_shared_grammar():
    """`1,234` says nothing about its own separator, so this reader decides
    nothing about it."""
    assert _southside_money("1,234") == _southside_money("1,234")
    assert _southside_money("37,215,608") == 37215608.0


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
    word is a ledger row and must not open a grid. Both headings, because both
    words turn up in this issuer's printed descriptions."""
    grids = _southside_grids(
        "*** DEPOSITS ***\n4/01 Regular Deposit 500.00\n"
        "4/02 REFUND OF WITHDRAWALS FEE 5.00\n"
        "*** DAILY BALANCE SUMMARY ***\n4/01 100.00\n"
    )
    assert "REFUND OF WITHDRAWALS FEE" in grids["deposits"]
    assert grids["withdrawals"] == ""

    grids = _southside_grids(
        "*** WITHDRAWALS ***\n4/01 Telephone transfer 500.00\n"
        "4/02 REVERSAL OF DEPOSITS FEE 5.00\n"
        "*** DAILY BALANCE SUMMARY ***\n4/01 100.00\n"
    )
    assert "REVERSAL OF DEPOSITS FEE" in grids["withdrawals"]
    assert grids["deposits"] == ""


def test_two_anchors_merged_onto_one_line_do_not_crash_the_reader():
    """A scan merges lines. The daily-balance heading and the page footer under
    it are separate lines on six of the nine archive statements, and one merge
    puts two anchors at the same offsets — where ordering the marks by their
    whole tuple compares a terminal anchor's `None` against a named anchor's
    `str` and raises `TypeError`. Through the pipeline that is a parser CRASH,
    and a crash is a worse answer than a decline."""
    grids = _southside_grids("DAILY BALANCE SUMMARY Southside Bank   Page: 2\n")
    assert "Page" not in grids["daily"]
    stmt = parse_southside_scanned_statement(
        whole().replace("*** DAILY BALANCE SUMMARY ***",
                        "*** DAILY BALANCE SUMMARY *** Southside Bank   Page: 1")
    )
    assert stmt is not None


def test_a_period_cell_shaped_like_a_date_but_not_one_refuses():
    """`5/41/26` has the shape of a date and is not one. The conversion RAISES
    on it, and a parser that raises is a parser crash: the document becomes an
    exception class in the telemetry instead of a decline with a reason. The
    widened summary reader routes four more archive documents through that
    conversion than the reader it replaced."""
    for broken in ("5/41/26", "13/01/26", "4/00/26"):
        maimed = whole().replace("thru 4/30/26", f"thru {broken}")
        assert _southside_summary(maimed) is None, broken
        assert parse_southside_scanned_statement(maimed) is None, broken


def test_the_cheque_image_sheets_end_the_grid_above_them():
    """The sheets after the ledger are photographs of cheques and deposit
    tickets, and they carry dates and figures of their own. Each marker is
    tested alone, because a sheet does not always print all of them — and what
    is at stake is not only a fabricated transaction: a figure absorbed into
    the DAILY grid becomes a day the bank is taken to have said had activity,
    which is the corroboration every reconstructed date is checked against."""
    for marker in ("SUBSTITUTE IMAGE / VIRTUAL DOCUMENT", "DEPOSIT TICKET",
                   "Credit DDA Deposit", "Southside Bank Page: 2 of 2",
                   "* Denotes missing check numbers", "ACCOUNT SUMMARY"):
        with_images = whole() + f"--- Page 2 ---\n{marker}\n4/22 999999 9,999.99\n"
        grids = _southside_grids(with_images)
        assert "9,999.99" not in "".join(grids.values()), marker
        assert "2026-04-22" not in _southside_posted_days(grids["daily"], PERIOD), marker
        stmt = parse_southside_scanned_statement(with_images)
        assert stmt is not None, marker
        assert all(abs(t.amount) != 9999.99 for t in stmt.transactions), marker


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
    # A reading is offered only where a two-digit DAY is left over, which is
    # what "the template zero-pads the day" means as a rule.
    assert _southside_day("4017", PERIOD) is None


def test_a_cell_that_is_not_all_digits_is_not_a_date_cell():
    """`ANT` is what one archive row's date column came back as. The reader
    enumerates readings of DIGITS; it does not guess at letters, and it does
    not fall over them either."""
    for token in ("ANT", "4a3", "A/17", "", "4//17"):
        assert _southside_day(token, PERIOD) is None, token


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


# ---------------------------------------------------------------------------
# SS-GRID-AMOUNTS — the printed daily grid as an AMOUNT oracle (W3 §SCANHYG)
# ---------------------------------------------------------------------------


def notes_for(markdown: str) -> list[str]:
    stmt = parse_southside_scanned_statement(markdown)
    assert stmt is not None
    return daily_grid_amount_contradictions(markdown, stmt)


def test_a_statement_whose_grid_the_ledger_reproduces_reports_nothing():
    """The check is not a standing accusation: on a statement whose rows walk
    the printed grid cell for cell it reports nothing at all."""
    assert notes_for(whole()) == []


def test_an_amount_read_too_large_is_caught_by_the_printed_daily_grid():
    """The failure this whole sub-card exists for. The row is otherwise
    perfect — a legible date, a legible description, a well-formed money
    cell — and the summary identity is untouched, so nothing else on the
    document notices that the reader now has more debit money than the bank
    printed. The grid's own step for that day does."""
    inflated = whole().replace(
        "4/02 ONLINE PMT UTILITY CO CCD 200.00", "4/02 ONLINE PMT UTILITY CO CCD 500.00"
    )
    notes = notes_for(inflated)
    assert len(notes) == 1
    assert "2026-04-02" in notes[0]


def test_an_over_capture_of_ONE_CENT_is_caught_and_not_rounded_away():
    """The oracle's resolution, pinned. It was `> 0.01` until W3 §SCANHYG SH13
    (review finding 5), so a span the grid and the ledger disagreed about by
    exactly one cent was SILENT — the smallest instance of the very thing this
    check exists to find, discarded by the check itself. Any non-zero
    difference is a contradiction now; the epsilon is float noise between two
    figures already rounded to the cent."""
    inflated = whole().replace(
        "4/02 ONLINE PMT UTILITY CO CCD 200.00", "4/02 ONLINE PMT UTILITY CO CCD 200.01"
    )
    notes = notes_for(inflated)
    assert len(notes) == 1
    assert "2026-04-02" in notes[0]


def test_the_walk_is_seeded_at_the_summarys_own_beginning_balance():
    """The first printed cell is a STEP from the beginning balance, not the
    start of the walk. A reader that seeded itself at the first cell would
    never check the span the first cell closes."""
    inflated = whole().replace("4/01 Regular Deposit 500.00", "4/01 Regular Deposit 800.00")
    notes = notes_for(inflated)
    assert len(notes) == 1
    assert "2026-04-01" in notes[0]


def test_a_span_covers_every_day_since_the_previous_printed_cell():
    """The grid prints a cell only for days the account moved, so consecutive
    cells partition the period: a row dated onto a day the grid does not name
    still has to be inside somebody's span. Comparing only the printed day
    would let it disappear."""
    misdated = whole().replace(
        "4/02 ONLINE PMT UTILITY CO CCD 200.00", "4/05 ONLINE PMT UTILITY CO CCD 200.00"
    )
    notes = notes_for(misdated)
    assert len(notes) == 2
    assert any("2026-04-02" in note for note in notes)
    assert any("2026-04-10" in note for note in notes)


def test_a_day_the_grid_prints_twice_with_two_balances_is_not_an_oracle():
    """The grid contradicting ITSELF. There is no rule that says which cell to
    believe, so that day states no balance — but it is still a day the bank
    says the account moved, which is what a reconstructed date is checked
    against, and that must survive."""
    contradicted = whole().replace(
        "4/10 1,000.00 4/15 1,300.00", "4/10 1,000.00 4/15 1,300.00\n4/10 9,999.00"
    )
    notes = notes_for(contradicted)
    assert len(notes) == 1
    assert "2026-04-10" in notes[0] and "not readable" in notes[0]
    grids = _southside_grids(contradicted)
    assert "2026-04-10" in _southside_posted_days(grids["daily"], PERIOD)


def test_the_grids_last_cell_is_held_against_the_printed_ending_balance():
    """Two printings of one figure, neither derived from the other."""
    trailing = whole().replace(
        "4/10 1,000.00 4/15 1,300.00", "4/10 1,000.00 4/15 1,300.00 4/20 1,250.00"
    )
    notes = notes_for(trailing)
    assert any("ending balance" in note for note in notes)


def test_the_registration_declares_the_daily_grid_amount_check():
    from analysis import parser_registry as pr
    from analysis.parser_registry_entries import load

    registration = next(r for r in load() if r.id == "southside_scanned")
    assert registration in pr.registrations()
    assert daily_grid_amount_contradictions in registration.integrity_checks


def test_the_disagreement_reaches_the_published_integrity_block():
    from analysis.pipeline import analyze_markdown

    inflated = whole().replace(
        "4/02 ONLINE PMT UTILITY CO CCD 200.00", "4/02 ONLINE PMT UTILITY CO CCD 500.00"
    )
    report = analyze_markdown(inflated, parse_mode="deterministic")
    assert "conflicting_statement_summaries" in report.integrity.flags


def test_a_period_the_check_cannot_read_answers_nothing_rather_than_raising():
    """A check that raises is a document routed to review for no finding."""
    stmt = parse_southside_scanned_statement(whole())
    assert stmt is not None
    for broken in ("4/31/26", "", "not-a-date"):
        maimed = stmt.model_copy(update={"period_start": broken})
        assert daily_grid_amount_contradictions(whole(), maimed) == []


def test_a_statement_with_no_printed_daily_grid_reports_nothing():
    assert notes_for(document(daily="")) == []
