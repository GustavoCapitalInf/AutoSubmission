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

from analysis.pipeline import analyze_markdown
from analysis.td_us import detect, parse_td_us_statement

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
    "01/05 ACH DEPOSIT, EXAMPLE PAYER PAYROLL 500.00\n"
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

#: The scanned shape: one debit row of a forty-row section did not survive
#: Tesseract, so that section's rows fall 100.00 short of the subtotal TD
#: printed above them. Everything else about the document is intact — the
#: summary, the other section, the two balances.
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
