"""W3 coverage wave / TDFIX-1: the two shapes `td_us` could not survive.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* found in
the td_us population (40 documents: 28 validated, 2 withheld, 10 declined). The
institution and column markers are TD's own layout sentinels — the same ones
the parser keys on — and every counterparty, date, amount and account number is
invented.

U1 the overdrawn opening
    TD prints an overdrawn balance as a leading minus, and prints it on the
    same ACCOUNT SUMMARY rows as every other balance. `_summary` read the
    closing balance sign-aware and the opening one not, so an overdrawn period
    left `beginning_balance` None and `parse_td_us_statement` discarded the
    whole document (:196). Six of the ten declines print exactly that. The same
    gap on `Average Collected Balance` silently dropped a printed negative
    average from a document that otherwise read perfectly.

U2 the section subtotal that does not add up
    A section whose rows do not reproduce its own printed subtotal used to
    discard the entire document. On a scanned statement that is Tesseract
    losing a row, not the statement contradicting itself: the summary is intact
    and the other sections are exact. The document now keeps what it read and
    fails CLOSED downstream on coverage, which is the platform's convention for
    an incomplete ledger — it must never publish as validated.
"""
from __future__ import annotations

import pytest

from analysis.pipeline import analyze_markdown
from analysis.td_us import (
    _heading_marks,
    _line_items,
    _section,
    detect,
    parse_td_us_statement,
)

#: The layout sentinels this parser recognises itself in, plus an invented
#: account. Nothing below is a real institution's customer data.
#:
#: -100.00 + 500.00 - 425.00 = -25.00: an overdrawn period that closes
#: overdrawn, so reading the sign is the only way the ledger can balance.
TD_OVERDRAWN = (
    "STATEMENT OF ACCOUNT\n"
    "Page: 1 of 1 Statement Period: Jan 01 2026-Jan 31 2026 "
    "Cust Ref #: 0000000000-000-X-*** Primary Account #: 000-0000000\n"
    "EXAMPLE COMPANY LLC 1 EXAMPLE WAY EXAMPLETOWN NY 10000\n"
    "TD Business Simple Checking\n"
    "EXAMPLE COMPANY LLC Account # 000-0000000\n"
    "ACCOUNT SUMMARY Beginning Balance -100.00 Electronic Deposits 500.00\n"
    "Average Collected Balance -50.00 Interest Earned This Period 0.00 "
    "Interest Paid Year-to-Date 0.00 Annual Percentage Yield Earned 0.00% "
    "Days in Period 31\n"
    "Electronic Payments 425.00 Ending Balance -25.00\n"
    "DAILY ACCOUNT ACTIVITY Electronic Deposits POSTING DATE DESCRIPTION AMOUNT\n"
    "01/05 INBOUND, EXAMPLE PAYER PAYROLL 500.00\n"
    "Subtotal: 500.00 Electronic Payments POSTING DATE DESCRIPTION AMOUNT\n"
    "01/09 ACH DEBIT, EXAMPLE COUNTERPARTY 425.00\n"
    "Subtotal: 425.00\n"
    "Bank Deposits FDIC Insured | TD Bank, N.A. | Equal Housing Lender\n"
)

#: The same statement in credit: every figure positive, nothing else changed.
TD_IN_CREDIT = (
    TD_OVERDRAWN
    .replace("Beginning Balance -100.00", "Beginning Balance 100.00")
    .replace("Average Collected Balance -50.00", "Average Collected Balance 50.00")
    .replace("Ending Balance -25.00", "Ending Balance 175.00")
)


# ------------------------------------------------ U1 the overdrawn opening


def test_an_overdrawn_td_opening_balance_is_read_with_its_sign():
    """The U1 capability: an overdrawn opening is a balance, not a missing one.

    Before the fix the opening row's money pattern could not stand next to the
    sign, so `beginning_balance` stayed None and :196 discarded the document —
    the defect arrived filed as an unclaimed layout.
    """
    statement = parse_td_us_statement(TD_OVERDRAWN)
    assert statement is not None
    assert statement.beginning_balance == -100.00
    assert statement.ending_balance == -25.00


def test_the_overdrawn_statement_closes_on_its_own_arithmetic():
    """Reading the sign is only correct if the ledger then closes with it."""
    statement = parse_td_us_statement(TD_OVERDRAWN)
    moved = round(sum(txn.amount for txn in statement.transactions), 2)
    assert moved == 75.00
    assert round(statement.beginning_balance + moved, 2) == statement.ending_balance


def test_the_captured_rows_reproduce_the_printed_section_subtotals():
    statement = parse_td_us_statement(TD_OVERDRAWN)
    credits = round(sum(t.amount for t in statement.transactions if t.amount > 0), 2)
    debits = round(-sum(t.amount for t in statement.transactions if t.amount < 0), 2)
    assert credits == 500.00   # Subtotal: 500.00
    assert debits == 425.00    # Subtotal: 425.00
    assert statement.stated_total_credits == 500.00
    assert statement.stated_total_debits == 425.00


def test_a_negative_printed_average_is_no_longer_dropped():
    """The quieter half of U1, and the one that touches documents that always
    read: `Average Collected Balance` is a balance too. One statement in the
    validated population prints it negative under a positive opening, and the
    field simply vanished rather than reading wrong."""
    text = TD_IN_CREDIT.replace(
        "Average Collected Balance 50.00", "Average Collected Balance -78.54"
    )
    statement = parse_td_us_statement(text)
    assert statement.beginning_balance == 100.00
    assert statement.stated_average_balance == -78.54


def test_a_td_summary_in_credit_is_unchanged_by_the_sign_fix():
    """The pattern is a strict superset: on a statement that read correctly
    before, every captured figure is identical."""
    statement = parse_td_us_statement(TD_IN_CREDIT)
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 175.00
    assert statement.stated_average_balance == 50.00
    assert statement.days_in_period == 31


def test_the_sign_fix_did_not_move_td_us_detection():
    """U1 is a parse-level fix. Detection reads two institution markers and
    cannot see a balance, let alone its sign."""
    detection = detect(TD_OVERDRAWN)
    assert detection.claims
    assert detection.matched == ("bank_name", "title")
    assert detect(TD_IN_CREDIT).matched == detection.matched
    assert detect(TD_IN_CREDIT).score == detection.score


# ------------------------------------------- U2 the section that lost a row

#: The scanned shape, reduced to its structure: a debit section whose rows
#: fall 100.00 short of the subtotal TD printed for it — on the real documents,
#: Tesseract losing one row out of forty. Everything else is intact: the
#: summary, the other section, and both balances still agree with each other.
TD_DROPPED_ROW = TD_IN_CREDIT.replace(
    "01/09 ACH DEBIT, EXAMPLE COUNTERPARTY 425.00\nSubtotal: 425.00\n",
    "01/09 ACH DEBIT, EXAMPLE COUNTERPARTY 325.00\nSubtotal: 425.00\n",
)


def test_a_section_that_misses_its_printed_subtotal_keeps_the_rows_it_read():
    """The U2 capability. Before, one short section discarded the document and
    the OCR defect was filed as an unclaimed layout."""
    statement = parse_td_us_statement(TD_DROPPED_ROW)
    assert statement is not None
    assert len(statement.transactions) == 2
    assert round(sum(t.amount for t in statement.transactions), 2) == 175.00
    # The bank's own summary is intact and is read from the summary block, not
    # from the rows — which is what makes the shortfall measurable downstream.
    assert statement.stated_total_debits == 425.00
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 175.00


def test_the_incomplete_ledger_then_fails_closed():
    """Claimed is not published. The document must reach the platform's
    fail-closed gate and be refused there, with the gap named."""
    report = analyze_markdown(TD_DROPPED_ROW, parse_mode="deterministic")
    assert report.reconciliation.ok is False
    assert report.reconciliation.summary_ok is True
    assert report.reconciliation.sum_delta == 100.00
    assert report.reconciliation.debit_coverage is not None
    assert report.reconciliation.debit_coverage < 0.98
    assert report.quality.corporate_use != "approved"
    assert report.metrics.average_daily_balance is None
    assert "ledger_sum_mismatch" in report.integrity.flags
    assert "debit_detail_coverage_mismatch" in report.integrity.flags


def test_a_document_whose_sections_do_add_up_is_unaffected():
    """The softening must not cost the intact statements anything."""
    report = analyze_markdown(TD_IN_CREDIT, parse_mode="deterministic")
    assert report.reconciliation.ok is True
    assert report.reconciliation.sum_delta == 0.00
    assert report.quality.corporate_use == "approved"
    assert report.integrity.flags == []


# ---------------------------------------------------------------------------
# W3 §WITHHELDTD — a section is bounded by the bank's own headings.
#
# Every fixture below is INVENTED: the layout sentinels and the column legend
# are TD's own furniture (the same ones the parser keys on), the OCR damage is
# written by hand rather than copied from a scan, and every counterparty, date,
# amount and account number is made up.
# ---------------------------------------------------------------------------

#: Two detail sections, each with its own rows and its own printed subtotal.
_TWO_SECTIONS = (
    "STATEMENT OF ACCOUNT\n"
    "Page: 1 of 1 Statement Period: Jan 01 2026-Jan 31 2026 "
    "Cust Ref #: 0000000000-000-X-*** Primary Account #: 000-0000000\n"
    "EXAMPLE COMPANY LLC 1 EXAMPLE WAY EXAMPLETOWN NY 10000\n"
    "TD Business Simple Checking\n"
    "ACCOUNT SUMMARY Beginning Balance 1,000.00 Electronic Deposits 300.00\n"
    "Average Collected Balance 900.00 Days in Period 31\n"
    "Other Withdrawals 40.00 Service Charges 3.00 Ending Balance 1,257.00\n"
    "DAILY ACCOUNT ACTIVITY\n"
    "Electronic Deposits\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/05 INBOUND, EXAMPLE PAYER PAYROLL 300.00\n"
    "{deposit_subtotal}\n"
    "Other Withdrawals\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/09 EXAMPLE OUTBOUND FEE 40.00\n"
    "{withdrawal_subtotal}\n"
    "Service Charges\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/31 EXAMPLE MONTHLY FEE 3.00\n"
    "Subtotal: 3.00\n"
    "Bank Deposits FDIC Insured | TD Bank, N.A. | Equal Housing Lender\n"
)


def _two_sections(deposit_subtotal="Subtotal: 300.00",
                  withdrawal_subtotal="Subtotal: 40.00"):
    return _TWO_SECTIONS.format(deposit_subtotal=deposit_subtotal,
                                withdrawal_subtotal=withdrawal_subtotal)


def test_a_section_stops_at_the_next_heading_rather_than_the_next_subtotal():
    """The defect this replaces: a section whose OWN subtotal line came through
    mangled ran on to the next section's, took its rows, and published that
    section's figure as its own total. Here `Other Withdrawals` loses its
    subtotal to a decimal-comma misread, and must NOT become the Service
    Charges section wearing its name."""
    text = _two_sections(withdrawal_subtotal="Subtotal: 40,00")
    body, total = _section(text, "Other Withdrawals")
    assert total is None
    assert "EXAMPLE MONTHLY FEE" not in body
    # ...and the section that owns those rows still reads them, under its name.
    charges_body, charges_total = _section(text, "Service Charges")
    assert charges_total == 3.00
    assert "EXAMPLE MONTHLY FEE" in charges_body


def test_a_section_with_no_readable_subtotal_contributes_nothing():
    """Fail closed: the rows are not published under a total the bank did not
    print for them. The shortfall then shows up against the stated totals."""
    text = _two_sections(withdrawal_subtotal="Subtotal: 40,00")
    statement = parse_td_us_statement(text)
    assert [t.amount for t in statement.transactions] == [300.00, -3.00]
    assert analyze_markdown(text, parse_mode="deterministic").reconciliation.ok is False


def test_a_continued_reprint_of_the_same_heading_does_not_end_the_section():
    """TD reprints the heading at every page break. That is the same section,
    and its later rows belong to it."""
    text = _two_sections().replace(
        "01/05 INBOUND, EXAMPLE PAYER PAYROLL 300.00\n",
        "01/05 INBOUND, EXAMPLE PAYER PAYROLL 100.00\n"
        "Electronic Deposits (continued)\n"
        "POSTING DATE DESCRIPTION AMOUNT\n"
        "01/06 INBOUND, EXAMPLE PAYER PAYROLL 200.00\n",
    )
    body, total = _section(text, "Electronic Deposits")
    assert total == 300.00
    assert len(_line_items(body, year=2026, sign=1)) == 2


def test_the_account_summary_line_is_not_a_section_heading():
    """`<heading> <total>` in ACCOUNT SUMMARY names the same section and opens
    nothing: the detail heading carries no figure of its own."""
    marks = [name for _start, _end, name in _heading_marks(_two_sections())]
    assert marks == ["Electronic Deposits", "Other Withdrawals", "Service Charges"]


def test_the_page_footer_does_not_open_a_deposits_section():
    """`Bank Deposits FDIC Insured ...` contains the `Deposits` heading, and the
    `(?<!Electronic )` guard is about the OTHER heading and has nothing to say
    about it. What keeps it out is that no column legend follows it.

    The footer is placed MID-document on purpose. TD prints it at the foot of
    every page, so on a real multi-page statement there are sections after it —
    and a footer at the end of a fixture is a footer that could not have done
    any damage even if it were admitted, which is a test that proves nothing.
    Here, admitting it would open a `Deposits` section over the whole of the
    next page and publish that page's withdrawals as DEPOSITS."""
    header = "Other Withdrawals\nPOSTING DATE DESCRIPTION AMOUNT\n"
    text = _two_sections().replace(
        header,
        "Bank Deposits FDIC Insured | TD Bank, N.A. | Equal Housing Lender\n"
        "Page: 2 of 2 Primary Account #: 000-0000000\n" + header,
        1,
    )
    assert _section(text, "Deposits") == ("", None)
    statement = parse_td_us_statement(text)
    assert [t.amount for t in statement.transactions] == [300.00, -40.00, -3.00]


def test_the_cheque_footnote_does_not_open_an_electronic_payments_section():
    """TD's own cheque legend ends `...listed under Electronic Payments`, and
    the legend `DATE SERIAL NO. AMOUNT` follows it one line later. A heading is
    never preceded by a lower-case word."""
    text = _two_sections().replace(
        "Electronic Deposits\nPOSTING DATE DESCRIPTION AMOUNT\n",
        "Checks Paid No. Checks: 2 *Indicates break in serial sequence or check "
        "processed electronically and listed under Electronic Payments\n"
        "DATE SERIAL NO. AMOUNT\n"
        "01/04 1001 120.00 01/07 1002 180.00\n"
        "Subtotal: 300.00\n"
        "Electronic Deposits\nPOSTING DATE DESCRIPTION AMOUNT\n",
    )
    marks = [name for _start, _end, name in _heading_marks(text)]
    assert "Electronic Payments" not in marks
    assert _section(text, "Checks Paid")[1] == 300.00


@pytest.mark.parametrize("damage", [
    "Electronic Deposits Xxx\nPOSTING DATE DESCRIPTION AMOUNT Yyy",
    "Electronic Deposits\nPOSTING DATE DESCRIPTION AMQUNT",
    "Electronic Deposits\n \nPOSTING BATE DESCRIPTION ARMOUNT",
    "Electronic Deposits (continued) z\nPOSTING DATE DESCRIPTION AMOUNT g",
])
def test_ocr_damage_around_the_legend_does_not_lose_the_section(damage):
    """The legend is furniture, and a scan damages furniture. Requiring it
    verbatim discarded whole sections — and with them the rows that close the
    ledger."""
    text = _two_sections().replace(
        "Electronic Deposits\nPOSTING DATE DESCRIPTION AMOUNT", damage, 1
    )
    assert _section(text, "Electronic Deposits")[1] == 300.00


#: Review MINOR-1. The ACCOUNT SUMMARY's last line runs straight into the first
#: detail legend, so the summary's `Other Withdrawals` sits inside the legend
#: window — and the summary prints the next section's heading right beside it.
#: Without the money gate the summary line opens a spurious `Other Withdrawals`
#: mark whose slice ends at the summary's own `Service Charges` and holds no
#: `Subtotal:`, and the REAL section is lost.
_SUMMARY_RUNS_INTO_THE_LEGEND = (
    "STATEMENT OF ACCOUNT\n"
    "Page: 1 of 1 Statement Period: Jan 01 2026-Jan 31 2026 "
    "Cust Ref #: 0000000000-000-X-*** Primary Account #: 000-0000000\n"
    "TD Business Simple Checking\n"
    "ACCOUNT SUMMARY Beginning Balance 1,000.00 Electronic Deposits 300.00\n"
    "Other Withdrawals 40.00 Service Charges 3.00 Ending Balance 1,257.00\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/05 INBOUND, EXAMPLE PAYER PAYROLL 300.00\n"
    "Subtotal: 300.00\n"
    "Other Withdrawals\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/09 EXAMPLE OUTBOUND FEE 40.00\n"
    "Subtotal: 40.00\n"
    "Service Charges\n"
    "POSTING DATE DESCRIPTION AMOUNT\n"
    "01/31 EXAMPLE MONTHLY FEE 3.00\n"
    "Subtotal: 3.00\n"
)


def test_a_summary_line_inside_the_legend_window_does_not_open_a_section():
    """The legend window alone excludes the summary line on all 40 archive
    documents, and this is the shape where it does not: the money on the
    heading's own line is what says `<heading> <total>` is the summary."""
    marks = [name for _s, _e, name in _heading_marks(_SUMMARY_RUNS_INTO_THE_LEGEND)]
    assert marks == ["Other Withdrawals", "Service Charges"]
    assert _section(_SUMMARY_RUNS_INTO_THE_LEGEND, "Other Withdrawals")[1] == 40.00
    assert _section(_SUMMARY_RUNS_INTO_THE_LEGEND, "Service Charges")[1] == 3.00


def test_a_subtotal_line_is_read_whatever_case_the_scan_gives_it():
    """Review MINOR-3. This is a scanned family and `SUBTOTAL:` is a subtotal
    line. Inert on today's archive (194 of 194 arrive exactly cased), and the
    base pattern carried the flag, so dropping it would be a silent narrowing.
    """
    for spelling in ("Subtotal:", "SUBTOTAL:", "subtotal:"):
        text = _two_sections(deposit_subtotal=f"{spelling} 300.00")
        assert _section(text, "Electronic Deposits")[1] == 300.00


def test_compound_damage_can_still_carry_a_section_across_a_boundary():
    """Review MINOR-2, pinned as a RESIDUAL rather than argued away.

    The bound on a section is the next heading MARK. Damage this section's
    `Subtotal:` and the next section's legend at the same time and the next
    heading is not a mark, so the slice runs on and this section reports the
    next section's rows and total under its own name. Strictly narrower than
    the shipped failure, which needed only the one mangled subtotal — and not
    zero.
    """
    text = _two_sections(deposit_subtotal="Subtotal: 300,00").replace(
        "Other Withdrawals\nPOSTING DATE DESCRIPTION AMOUNT\n",
        "Other Withdrawals\n", 1,
    )
    _body, total = _section(text, "Electronic Deposits")
    assert total == 40.00          # the NEXT section's printed subtotal
