"""W3 §COREENC: the FOURTH core processor's enclosures / average-ledger template.

Every figure, name, account number and date in this module is INVENTED. No
archive content appears here — the standing privacy rule of batch 7 — and the
documents are built by `_document` below so that each test changes exactly the
one printing it is about.

The invented statement all of these are variations on::

    period 1/01/26 - 1/31/26, 31 days
    previous 100.00
    2 credits totalling 200.00   (1/05 +120.00, 1/12 +80.00)
    2 debits totalling  60.00    (1/08  -50.00, 1/20 -10.00)
    service charge .00, interest paid .00
    ending 240.00                (100 + 200 - 60 - 0 + 0)
    daily grid 1/05 220.00, 1/08 170.00, 1/12 250.00, 1/20 240.00

Each test names the printed fact it is about, and each gate below has a mutant
in the §COREENC mutation table that this module kills.
"""
from __future__ import annotations

import pytest

from analysis.core_processor_enclosures import (
    DETECTION_MARKERS, detect, parse_core_processor_enclosures_statement,
)

# ---------------------------------------------------------------------------
# The invented document
# ---------------------------------------------------------------------------

_CREDIT_BLOCK = (
    "DEPOSITS AND OTHER CREDITS Date Description Amount\n"
    "1/05 EXAMPLE PAYOUT ONE 120.00\n"
    "1/12 EXAMPLE PAYOUT TWO 80.00\n"
)
_DEBIT_BLOCK = (
    "CHECKS AND WITHDRAWALS Date Description Amount\n"
    "1/08 EXAMPLE CARD PURCHASE 50.00-\n"
    "1/20 EXAMPLE TRANSFER OUT 10.00-\n"
)
_GRID_BLOCK = (
    "DAILY BALANCE INFORMATION Date Balance Date Balance Date Balance\n"
    "1/05 220.00 1/08 170.00 1/12 250.00\n"
    "1/20 240.00\n"
)


def _strip(
    *,
    product: str = "Business Example Checking",
    enclosures: str = "Number of Enclosures 3",
    account: str = "Account Number XXXXXXXX0000",
    period: str = "Statement Dates 1/01/26 thru 1/31/26",
    previous: str = "Previous Balance 100.00",
    days: str = "Days in the statement period 31",
    credits: str = "2 Deposits/Credits 200.00",
    average: str = "Average Ledger 150.00",
    debits: str = "2 Checks/Debits 60.00",
    collected: str = "Average Collected 150.00",
    service: str = "Service Charge .00",
    interest: str = "Interest Paid .00",
    ending: str = "Ending Balance 240.00",
) -> str:
    """The two-column summary block, flattened onto one line as the text layer
    emits it. Every cell is a keyword so a test can change one of them."""
    return " ".join(part for part in (
        product, enclosures, account, period, previous, days, credits, average,
        debits, collected, service, interest, ending) if part)


def _document(strip: str | None = None, body: str | None = None) -> str:
    if strip is None:
        strip = _strip()
    if body is None:
        body = _CREDIT_BLOCK + _DEBIT_BLOCK + _GRID_BLOCK
    return (
        "<!-- SOURCE: invented.pdf -->\n"
        "--- Page 1 ---\n"
        "P.O. Box 1 Exampleton EX 00000 555-000-0000\n"
        "EXAMPLE HOLDER LLC 1 EXAMPLE WAY EXAMPLETON EX 00000\n"
        "CHECKING ACCOUNT CHECKING ACCOUNT\n"
        + strip + "\n" + body
    )


def _parse(*args, **kwargs):
    return parse_core_processor_enclosures_statement(_document(*args, **kwargs))


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_the_template_is_recognised_by_its_own_two_column_summary_block():
    detection = detect(_document())
    assert detection.claims
    assert set(detection.matched) >= {
        "platform_statement_dates", "platform_ledger_average_cell"}


def test_the_period_sentence_alone_is_not_a_claim():
    """Eight printed identities in the archive print it; it is one half of the
    conjunction and never the whole registration (R4-3)."""
    assert not detect(_document(strip=_strip(
        credits="", average="", debits="", collected=""))).claims


def test_the_ledger_average_cell_alone_is_not_a_claim():
    assert not detect(_document(strip=_strip(period=""))).claims


def test_a_three_count_summary_of_the_same_processor_is_not_this_template():
    """Census rank 62 prints the same vocabulary with THREE counted rows, and
    the row it prints against `Average Ledger` is a WITHDRAWALS row rather
    than the credit row. Registering on the pairing rather than on the
    statistic is what refuses it."""
    assert not detect(_document(strip=_strip(
        credits="", average="7 Withdrawals 300.00 Average Ledger 150.00",
        debits="4 Checks 60.00"))).claims


def test_detection_survives_the_upper_case_printing_of_the_same_block():
    """The same template arrives in title case under one masthead and in
    capitals under another; the registration normalizes and the reader does
    not care."""
    assert detect(_document(strip=_strip().upper())).claims
    assert _parse(strip=_strip().upper(),
                  body=(_CREDIT_BLOCK + _DEBIT_BLOCK + _GRID_BLOCK).upper()) is not None


# ---------------------------------------------------------------------------
# The published record
# ---------------------------------------------------------------------------

def test_a_complete_statement_publishes_every_printed_figure():
    stmt = _parse()
    assert stmt is not None
    assert stmt.bank is None
    assert stmt.account_number == "XXXXXXXX0000"
    assert stmt.account_name == "Business Example Checking"
    assert (stmt.period_start, stmt.period_end) == ("2026-01-01", "2026-01-31")
    assert stmt.days_in_period == 31
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == 240.00
    assert (stmt.stated_credit_count, stmt.stated_total_credits) == (2, 200.00)
    assert (stmt.stated_debit_count, stmt.stated_total_debits) == (2, 60.00)
    assert stmt.stated_service_charge == 0.0
    assert stmt.stated_interest_paid == 0.0
    assert stmt.bank_reported_average_balance == 150.00
    assert stmt.bank_reported_average_label == "Average Ledger"
    assert [(row.date, row.amount, row.direction) for row in stmt.transactions] == [
        ("2026-01-05", 120.00, "credit"),
        ("2026-01-08", -50.00, "debit"),
        ("2026-01-12", 80.00, "credit"),
        ("2026-01-20", -10.00, "debit"),
    ]
    assert [(day.date, day.balance) for day in stmt.stated_daily_balances] == [
        ("2026-01-05", 220.00), ("2026-01-08", 170.00),
        ("2026-01-12", 250.00), ("2026-01-20", 240.00),
    ]


def test_the_currency_is_the_schema_default_because_the_template_prints_none():
    """No member of this family prints a currency word, an ISO code or any
    Canadian furniture. A US mailing address is not a printed denomination, so
    the reader claims no evidence class it does not have."""
    stmt = _parse()
    assert stmt.currency == "USD"
    assert stmt.currency_source == "schema_default"


def test_the_row_description_is_what_the_bank_printed_on_the_row_s_own_line():
    stmt = _parse()
    assert [row.description for row in stmt.transactions] == [
        "EXAMPLE PAYOUT ONE", "EXAMPLE CARD PURCHASE",
        "EXAMPLE PAYOUT TWO", "EXAMPLE TRANSFER OUT",
    ]


def test_a_description_longer_than_the_bound_is_cut_at_a_token_boundary():
    """The bound is this template's own, and it is what keeps a welded span out
    of one row's description. `tables.attributed_descriptions` cuts at a token
    boundary rather than through a word, because half a token is a string the
    bank did not print — so what publishes is always a PREFIX of the printing,
    never a repair of it."""
    printed = " ".join(["EXAMPLE"] * 40)
    stmt = _parse(body=_CREDIT_BLOCK.replace("EXAMPLE PAYOUT ONE", printed)
                  + _DEBIT_BLOCK)
    assert stmt is not None
    published = stmt.transactions[0].description
    assert len(printed) > 200 and len(published) <= 200
    assert printed.startswith(published)


# ---------------------------------------------------------------------------
# The summary strip
# ---------------------------------------------------------------------------

def test_a_summary_whose_own_identity_does_not_close_is_refused():
    """`previous + credits - debits - service charge + interest == ending` is
    the fifth independent printing, and a strip that fails it has been
    misread."""
    assert _parse(strip=_strip(ending="Ending Balance 241.00")) is None


def test_the_service_charge_and_the_interest_are_outside_both_direction_totals():
    """Printed 5.00 of fees and 1.00 of interest with the same ledger: the
    identity closes only when both stand outside the two totals."""
    strip = _strip(service="Service Charge 5.00", interest="Interest Paid 1.00",
                   ending="Ending Balance 236.00")
    body = (_CREDIT_BLOCK + "1/28 INTEREST PAYMENT 1.00\n"
            + _DEBIT_BLOCK + "1/31 MONTHLY FEE 5.00-\n"
            + "DAILY BALANCE INFORMATION Date Balance Date Balance Date Balance\n"
              "1/05 220.00 1/08 170.00 1/12 250.00\n"
              "1/20 240.00 1/28 241.00 1/31 236.00\n")
    stmt = _parse(strip=strip, body=body)
    assert stmt is not None
    assert (stmt.stated_service_charge, stmt.stated_interest_paid) == (5.00, 1.00)
    # Both postings are published even though neither is inside a printed count.
    assert len(stmt.transactions) == 6


def test_an_interest_posting_is_admitted_only_for_the_figure_the_bank_printed():
    """The credit side may carry one row more than the printed count, and only
    when the excess is exactly the printed interest."""
    body = (_CREDIT_BLOCK + "1/28 INTEREST PAYMENT 2.00\n" + _DEBIT_BLOCK)
    assert _parse(strip=_strip(interest="Interest Paid 1.00",
                              ending="Ending Balance 241.00"), body=body) is None


def test_the_interest_allowance_admits_one_more_credit_row_and_never_fewer():
    """The allowance exists because the bank leaves the interest it credited
    out of its own `N Deposits/Credits` count, so it is an allowance for ONE
    EXTRA row. A ledger holding FEWER credit rows than the bank counted is a
    ledger that lost one, and the money closing to the printed total plus the
    printed interest does not make it whole."""
    body = ("DEPOSITS AND OTHER CREDITS Date Description Amount\n"
            "1/05 EXAMPLE PAYOUT ONE 201.00\n" + _DEBIT_BLOCK)
    assert _parse(strip=_strip(interest="Interest Paid 1.00",
                              ending="Ending Balance 241.00"), body=body) is None


def test_the_fee_allowance_admits_more_debit_rows_and_never_fewer():
    """`> debit_count` rather than `== debit_count + 1`, because one member
    posts its charge as two rows — but never FEWER rows than the bank counted,
    for the same reason as the credit side above."""
    body = (_CREDIT_BLOCK
            + "CHECKS AND WITHDRAWALS Date Description Amount\n"
              "1/08 EXAMPLE CARD PURCHASE 65.00-\n")
    assert _parse(strip=_strip(service="Service Charge 5.00",
                               ending="Ending Balance 235.00"), body=body) is None


def test_an_extra_debit_row_is_admitted_only_for_the_figure_the_bank_billed():
    """The count bound on the debit side is deliberately loose and the MONEY is
    what does the work: the excess must be exactly the service charge the bank
    printed, to the cent."""
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK + "1/31 EXAMPLE MONTHLY FEE 6.00-\n")
    assert _parse(strip=_strip(service="Service Charge 5.00",
                               ending="Ending Balance 235.00"), body=body) is None


def test_a_strip_that_prints_a_figure_twice_with_two_readings_is_refused():
    """A document contradicting itself about its own summary has no rule that
    says which printing to believe. Inside the strip, because the strip stops
    at the closing balance and a label printed after it is a different
    statistic (the year-to-date one below)."""
    assert _parse(strip=_strip(
        previous="Previous Balance 100.00 Previous Balance 999.00")) is None


def test_the_year_to_date_interest_printed_after_the_closing_balance_is_not_read():
    """An interest-bearing member prints its year-to-date interest under the
    same label AFTER the closing balance; the strip stops at the balance."""
    stmt = _parse(strip=_strip() + " 2026 Interest Paid 9.99")
    assert stmt is not None
    assert stmt.stated_interest_paid == 0.0


def test_an_overdrawn_figure_is_read_from_the_strip_s_right_aligned_sign_column():
    """Three members print the sign a space clear of the figure and four weld
    it; both are the same printed negative."""
    for printed in ("Ending Balance 40.00-", "Ending Balance 40.00 -"):
        strip = _strip(previous="Previous Balance 100.00 -",
                       credits="2 Deposits/Credits 200.00",
                       debits="2 Checks/Debits 140.00", ending=printed)
        body = ("DEPOSITS AND OTHER CREDITS Date Description Amount\n"
                "1/05 EXAMPLE PAYOUT ONE 120.00\n1/12 EXAMPLE PAYOUT TWO 80.00\n"
                "CHECKS AND WITHDRAWALS Date Description Amount\n"
                "1/08 EXAMPLE CARD PURCHASE 130.00-\n1/20 EXAMPLE TRANSFER OUT 10.00-\n")
        stmt = _parse(strip=strip, body=body)
        assert stmt is not None, printed
        assert stmt.beginning_balance == -100.00
        assert stmt.ending_balance == -40.00


def test_a_repeated_product_name_publishes_no_name_rather_than_the_repetition():
    """The text layer paints a printed string up to four times over; a name no
    statement carries is worse than no name."""
    stmt = _parse(strip=_strip(product="Business Example Checking "
                                       "Business Example Checking"))
    assert stmt is not None
    assert stmt.account_name is None


def test_a_product_slot_longer_than_this_template_prints_publishes_no_name():
    """The bound is the TEMPLATE's, not a guess about how long a name is: the
    longest product name the archive prints in that slot is 27 characters. It
    is what keeps a page of welded furniture out of the slot on a member whose
    strip opens with something other than a product, and a name no statement
    carries is worse than no name."""
    printed = "Business Example Checking Example Business Example Savings Example One"
    stmt = _parse(strip=_strip(product=printed))
    assert stmt is not None
    assert len(printed) > 60
    assert stmt.account_name is None


def test_the_label_drift_of_every_summary_cell_is_read():
    """One issuer prints `Balance Last Statement` / `Days This Statement
    Period` / `Deposits` / `Checks/Charges` / `Maintenance Charge` /
    `Balance This Statement` and no `Average Collected` at all."""
    stmt = _parse(strip=_strip(
        previous="Balance Last Statement $100.00",
        days="Days This Statement Period 31",
        credits="2 Deposits $200.00",
        average="Average Ledger Bal. $150.00",
        debits="2 Checks/Charges $60.00",
        collected="",
        service="Maintenance Charge $.00",
        ending="Balance This Statement $240.00"))
    assert stmt is not None
    assert stmt.ending_balance == 240.00


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

def test_the_direction_is_the_block_the_bank_printed_the_row_in():
    """The collapsed cheque grids print magnitudes and the sectioned debit
    blocks print a trailing minus; both are debits. A reader keyed on the sign
    books a quarter of this platform's debit side as deposits."""
    body = (_CREDIT_BLOCK
            + "CHECKS IN NUMBER ORDER Date Check No Amount\n"
              "1/08 1001 50.00 1/20 1002 10.00\n"
            + _GRID_BLOCK)
    stmt = _parse(body=body)
    assert stmt is not None
    assert [row.direction for row in stmt.transactions] == [
        "credit", "debit", "credit", "debit"]
    assert [row.description for row in stmt.transactions] == [
        "EXAMPLE PAYOUT ONE", "Check 1001", "EXAMPLE PAYOUT TWO", "Check 1002"]


def test_the_date_order_issue_reads_its_direction_from_the_printed_sign():
    """`ACTIVITY IN DATE ORDER` prints one undivided ledger and no column to
    read, so the sign is the only evidence there is."""
    body = ("ACTIVITY IN DATE ORDER Date Description Amount\n"
            "1/05 EXAMPLE PAYOUT ONE 120.00\n"
            "1/08 EXAMPLE CARD PURCHASE 50.00-\n"
            "1/12 EXAMPLE PAYOUT TWO 80.00\n"
            "1/20 EXAMPLE TRANSFER OUT 10.00-\n" + _GRID_BLOCK)
    stmt = _parse(body=body)
    assert stmt is not None
    assert [row.direction for row in stmt.transactions] == [
        "credit", "debit", "credit", "debit"]


def test_a_captured_credit_count_that_disagrees_with_the_printed_one_is_refused():
    """A row of 0.00 and no grid: the COUNT is the only gate that can see it,
    because the total and every walked balance are unmoved."""
    body = (_CREDIT_BLOCK + "1/28 EXAMPLE PAYOUT THREE 0.00\n" + _DEBIT_BLOCK)
    assert _parse(body=body) is None


def test_a_captured_credit_total_that_disagrees_with_the_printed_one_is_refused():
    """The same count and a different total, and no grid: the TOTAL is the
    only gate that can see it."""
    body = (_CREDIT_BLOCK.replace("80.00", "81.00") + _DEBIT_BLOCK)
    assert _parse(body=body) is None


def test_a_captured_debit_count_that_disagrees_with_the_printed_one_is_refused():
    """A cheque of 0.00 and no grid. This also pins that the extra debit row
    the printed count is allowed to omit is admitted ONLY against a service
    charge the bank actually billed, and none is printed here."""
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK
            + "CHECKS IN NUMBER ORDER Date Check No Amount\n1/22 1001 0.00\n")
    assert _parse(body=body) is None


def test_a_captured_debit_total_that_disagrees_with_the_printed_one_is_refused():
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK.replace("10.00-", "11.00-"))
    assert _parse(body=body) is None


def test_a_row_whose_date_closes_no_amount_declines_the_whole_document():
    """Two archive printings do this — a wrapped description welded across the
    date column, and a `mm/dd` token inside a merchant name. Dropping the row
    is how a ledger comes to disagree with a printed total while still looking
    complete, so the document is declined instead."""
    body = (_CREDIT_BLOCK.replace("1/12 EXAMPLE PAYOUT TWO 80.00",
                                  "1/12 EXAMPLE 1/12 PAYOUT TWO 80.00")
            + _DEBIT_BLOCK + _GRID_BLOCK)
    assert _parse(body=body) is None


def test_a_row_dated_outside_the_printed_period_declines_the_document():
    body = (_CREDIT_BLOCK.replace("1/12", "2/12") + _DEBIT_BLOCK + _GRID_BLOCK)
    assert _parse(body=body) is None


def test_a_document_with_no_ledger_block_publishes_nothing():
    assert _parse(body="") is None


def test_the_fee_detail_block_is_not_published_as_rows():
    """It itemizes the one service-charge posting the debit ledger already
    carries; publishing both posts the fee twice."""
    strip = _strip(service="Service Charge 5.00", ending="Ending Balance 235.00")
    body = ("SERVICE CHARGES AND ITEMIZED FEES Date Description Amount\n"
            "1/31 EXAMPLE BASE FEE 3.00\n1/31 EXAMPLE PAPER FEE 2.00\n"
            + _CREDIT_BLOCK + _DEBIT_BLOCK + "1/31 TOTAL SERVICE CHARGE 5.00-\n"
            + "DAILY BALANCE INFORMATION Date Balance Date Balance Date Balance\n"
              "1/05 220.00 1/08 170.00 1/12 250.00\n1/20 240.00 1/31 235.00\n")
    stmt = _parse(strip=strip, body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 5


def test_the_image_appendix_is_a_boundary_and_never_a_row_or_a_grid_cell():
    """34 of this family's members restate every item as
    `CHECK <serial> Date: mm/dd Amount: $<fig>` after the grid. A reader that
    let the grid's run reach it would read every restated amount as a grid
    cell, and a naive amount scraper would double the whole debit side."""
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK + _GRID_BLOCK
            + "CHECK 1001 Date: 01/08 Amount: $50.00\n"
              "CHECK 1002 Date: 01/20 Amount: $10.00\n")
    stmt = _parse(body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 4
    assert len(stmt.stated_daily_balances) == 4


def test_a_cheque_the_grid_cross_references_instead_of_pricing_is_not_a_row():
    """`-See above-` says in words that the amount is printed in the ledger
    above. Read as a row the cheque posts twice; left in place the date closes
    no cell and the whole document is lost."""
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK
            + "CHECKS IN NUMBER ORDER Date Check No Amount\n"
              "1/08 1001 -See above- 1/20 1002 -See above-\n"
            + _GRID_BLOCK)
    stmt = _parse(body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 4


def test_the_cross_reference_rule_skips_only_the_platform_s_own_pointer():
    """A cheque grid that carries a cross-reference AND a date closing no cell
    is still declined: the pointer is skipped because the platform says the
    amount is printed elsewhere, and a bare unreadable date says nothing."""
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK
            + "CHECKS IN NUMBER ORDER Date Check No Amount\n"
              "1/08 1001 -See above- 1/20 1002 -See above- 1/22 EXAMPLE\n")
    assert _parse(body=body) is None


def test_a_date_shaped_token_that_is_not_a_calendar_day_is_not_a_row_date():
    """A description carrying `26/04` — the tail of a reference number this
    platform prints on ACH rows — is not a row. Measured on the archive: with
    a digit-run row-date class three members of this family lose their whole
    read, and one prints 75 such tokens in a glyph-damaged disclosure block."""
    body = (_CREDIT_BLOCK
            + "CHECKS AND WITHDRAWALS Date Description Amount\n"
              "1/08 EXAMPLE CARD PURCHASE 50.00- REF 26/04 EXAMPLE TRACE\n"
              "1/20 EXAMPLE TRANSFER OUT 10.00-\n")
    stmt = _parse(body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 4


def test_the_issue_that_prints_the_amount_before_the_description_is_read():
    """Four members print `date -amount description`, with the sign LEADING.
    Measured: without the leading-minus half of the ledger token five members
    of this family lose their whole read. The row's description trails its
    amount on that arrangement, so nothing is printed before the amount and
    the row publishes the block's own label — named, not repaired; the column
    belongs to the extraction rung (DESC-COLUMNS)."""
    body = (_CREDIT_BLOCK
            + "CHECKS AND WITHDRAWALS Date Description Amount\n"
              "1/08 -50.00 EXAMPLE CARD PURCHASE\n"
              "1/20 -10.00 EXAMPLE TRANSFER OUT\n")
    stmt = _parse(body=body)
    assert stmt is not None
    assert [(row.amount, row.direction) for row in stmt.transactions] == [
        (120.00, "credit"), (-50.00, "debit"), (80.00, "credit"), (-10.00, "debit")]
    assert [row.description for row in stmt.transactions[1::2]] == ["Debit", "Debit"]


def test_an_unreadable_row_declines_the_document_even_when_its_run_is_droppable():
    """The section is printed across two runs and the second holds only a
    mangled date: dropping that run would leave both printed counts intact,
    which is exactly how a ledger comes to look complete while missing a row."""
    body = (_CREDIT_BLOCK
            + "DEPOSITS AND OTHER CREDITS Date Description Amount\n1/28 EXAMPLE\n"
            + _DEBIT_BLOCK)
    assert _parse(body=body) is None


def test_a_row_outside_the_period_declines_even_when_dropping_it_would_reconcile():
    body = (_CREDIT_BLOCK + "2/05 EXAMPLE PAYOUT THREE 5.00\n" + _DEBIT_BLOCK)
    assert _parse(body=body) is None


# ---------------------------------------------------------------------------
# The SUMMARY blocks, and the running balance that decides what they are
# ---------------------------------------------------------------------------

_RUNNING_LEDGER = (
    "Transaction Activity Date Description Amount Balance\n"
    "1/05 EXAMPLE PAYOUT ONE 120.00 220.00\n"
    "1/08 EXAMPLE CARD PURCHASE 50.00- 170.00\n"
    "1/12 EXAMPLE PAYOUT TWO 80.00 250.00\n"
    "1/20 EXAMPLE TRANSFER OUT 10.00- 240.00\n"
)


def test_a_summary_block_restates_the_ledger_when_the_ledger_prints_a_balance():
    """Eight archive members print both; reading the summary as postings
    doubles their whole ledger."""
    body = ("Summary of Deposits Reference Date Amount\n"
            "1/05 120.00 1/12 80.00\n"
            "Summary of Withdrawals Date Description Amount\n"
            "1/08 EXAMPLE CARD PURCHASE 50.00\n1/20 EXAMPLE TRANSFER OUT 10.00\n"
            + _RUNNING_LEDGER + _GRID_BLOCK)
    stmt = _parse(body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 4


def test_a_summary_block_is_the_cheque_side_when_the_ledger_prints_no_balance():
    """Four archive members print cheques in a `Summary by Check Number` grid
    and nowhere else; skipping it loses the whole cheque side."""
    body = (_CREDIT_BLOCK
            + "SUMMARY BY CHECK NUMBER\n1/08 1001 50.00 1/20 1002 10.00\n"
            + _GRID_BLOCK)
    stmt = _parse(body=body)
    assert stmt is not None
    assert len(stmt.transactions) == 4
    assert sum(1 for row in stmt.transactions if row.direction == "debit") == 2


# ---------------------------------------------------------------------------
# The daily-balance grid
# ---------------------------------------------------------------------------

def test_a_grid_balance_that_disagrees_with_the_walked_ledger_is_refused():
    assert _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK.replace("170.00", "171.00")) is None


def test_a_grid_missing_a_day_the_ledger_posts_on_is_refused():
    assert _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK.replace("1/08 170.00 ", "")) is None


def test_a_grid_day_the_ledger_never_posts_on_is_refused():
    assert _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK.replace("1/20 240.00", "1/20 240.00 1/25 240.00")) is None


def test_the_grid_may_open_on_the_period_s_first_day_with_the_opening_balance():
    """Some issues print an end-of-day cell for day one even when nothing
    posted on it. That cell is the opening balance printed a second time, and
    it is admitted against the printed opening balance and nothing else."""
    stmt = _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK.replace("1/05 220.00", "1/01 100.00 1/05 220.00"))
    assert stmt is not None
    assert stmt.stated_daily_balances[0].date == "2026-01-01"
    assert stmt.stated_daily_balances[0].balance == 100.00


def test_an_opening_day_cell_that_is_not_the_opening_balance_is_refused():
    assert _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK.replace("1/05 220.00", "1/01 101.00 1/05 220.00")) is None


def test_a_grid_printing_one_day_twice_with_two_balances_is_refused():
    """The grid arrives three columns to a line; a duplicate day with two
    readings is evidence the column recovery went wrong.

    This document's duplicate makes the LAST reading the wrong one, so the
    walked-balance comparison can see it too. The test below plants the same
    duplication the other way round, where only `_grid`'s own check can.
    """
    assert _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK
                  + _GRID_BLOCK + "1/08 999.00\n") is None


def test_a_duplicated_grid_day_whose_SECOND_reading_is_the_correct_one_is_refused():
    """The intra-block duplicate check, isolated.

    A map that silently kept the last reading would publish this document: the
    second printing of the day agrees with the walked ledger, so every gate
    downstream of `_grid` passes. What the bank printed is one day with two
    different balances, which is evidence the three-column recovery went wrong,
    and the reader refuses rather than choosing one of them.
    """
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK
            + "DAILY BALANCE INFORMATION Date Balance Date Balance Date Balance\n"
              "1/05 220.00 1/08 999.00 1/12 250.00\n"
              "1/20 240.00 1/08 170.00\n")
    assert _parse(body=body) is None


def test_two_grid_blocks_that_disagree_on_a_shared_day_refuse_the_document():
    """The cross-block merge check, isolated.

    A document printing its daily balances under two of the template's own grid
    banners is merged block by block, and the merge is the only place a
    disagreement BETWEEN the two printings can be seen: as above, the second
    block prints the reading that agrees with the walked ledger, so a merge
    that let the last block win would publish it.
    """
    body = (_CREDIT_BLOCK + _DEBIT_BLOCK
            + "DAILY BALANCE INFORMATION Date Balance Date Balance Date Balance\n"
              "1/05 220.00 1/08 999.00 1/12 250.00\n"
              "BALANCE BY DATE Date Balance Date Balance\n"
              "1/08 170.00 1/20 240.00\n")
    assert _parse(body=body) is None


def test_a_document_that_prints_no_grid_still_publishes_its_reconciled_ledger():
    """The four printed count and total gates plus the summary identity close
    without it, and `analysis/adb.py` reconstructs the calendar-day series
    from the ledger they prove."""
    stmt = _parse(body=_CREDIT_BLOCK + _DEBIT_BLOCK)
    assert stmt is not None
    assert stmt.stated_daily_balances == []
    assert len(stmt.transactions) == 4


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("markdown", ["", "\n", "not a statement at all"])
def test_a_document_that_is_not_this_template_is_declined_without_raising(markdown):
    assert detect(markdown).claims is False
    assert parse_core_processor_enclosures_statement(markdown) is None


def test_the_registration_carries_two_required_markers():
    required = [marker.id for marker in DETECTION_MARKERS if marker.kind == "required"]
    assert len(required) == 2
