"""The scanned Texas First template: the ATM/POS grid whose split is solved.

W3 §SCANNEXT. The behaviour under test is not "it parses" — it is what the
reader REFUSES. The class killers here are a fabricated direction (the scan
destroys the two-column geometry that says whether an ATM figure was a deposit
or a withdrawal) and a hallucinated balance (an overdrawn day prints its minus
on the right, and reading it as positive publishes a five-figure error into the
ADB).
"""
from __future__ import annotations

import pytest

from datetime import date

from analysis.scanned_small_bank import (
    _tf_direct_atm,
    _tf_iso,
    _tf_read_grids,
    detect_texas_first,
    parse_texas_first_scanned_statement,
)

FURNITURE = (
    "TELEPHONE BANKING CUSTOMER SERVICE\n"
    "TEXAS FIRST BANK (409) 945-9889\n"
    "www.texasfirst.bank\n"
    "600 Gulf Freeway, Texas City, TX 77591\n"
    "SEAWALL8910 LLC\n"
    "5613 AVENUE R\n"
    "GALVESTON TX 77551-5525\n"
    "Account Number: FAKKAT AG\n"
)


def document(
    *,
    summary: str,
    credits: str = "",
    debits: str = "",
    atm: str = "",
    checks: str = "",
    daily: str = "",
    extra: str = "",
) -> str:
    """One page of the template, in the markdown the intake ladder emits."""
    body = ["--- Page 1 ---", FURNITURE, summary]
    if credits:
        body.append("Deposits and Other Credits\nDate Amount Activity Description\n" + credits)
    if debits:
        body.append("Debits and Other Withdrawals\nDate Amount Activity Description\n" + debits)
    if atm:
        body.append("ATM /POS Transactions\nDate Deposits Withdrawals Location\n" + atm)
    if checks:
        body.append(
            "Checks\nDate Check No Amount Date Check No Amount Date Check No Amount\n" + checks
        )
    if daily:
        body.append("Daily Balance Summary\nDate Balance Date Balance Date Balance\n" + daily)
    if extra:
        body.append(extra)
    return "\n".join(body) + "\n"


#: Three credits (two printed rows plus one ATM cash deposit) and four debits
#: (two printed rows, one cheque, one POS purchase). Nothing on the ATM rows
#: says which side they are on; the counts, the totals and the daily walk do.
WHOLE_STATEMENT_SUMMARY = (
    "Summary of Activity Since Your Last Statement\n"
    "Beginning Balance 4/01/54 1,000.00\n"
    "Deposits / Misc Credits 3 800.00\n"
    "Withdrawals / Misc Debits 4 510.00\n"
    "** Ending Balance 4/30/54 1,290.00 **\n"
    "Service Charge 10.00\n"
    "Average Balance 1,400\n"
)
WHOLE_STATEMENT = dict(
    summary=WHOLE_STATEMENT_SUMMARY,
    credits="4/01 500.00 Deposit\n4/02 200.00 Funds Transfer via Mobile\n",
    debits="4/02 300.00 ACME/BILL PAY\nref 12345 ACME UTILITIES\n"
           "4/03 10.00 BALANCE REQUIREMENT FEE\n",
    atm="4/01 100.00 ATM Cash Deposit\n4/03 50.00 POS Purchase Non-PIN\n",
    checks="4/03 1001 150.00\n* indicates a break in check number sequence\n",
    daily="4/01 1,600.00 4/02 1,500.00 4/03 1,290.00\n",
)


def whole(**overrides) -> str:
    return document(**{**WHOLE_STATEMENT, **overrides})


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detection_claims_the_template():
    assert detect_texas_first(whole()).claims


@pytest.mark.parametrize(
    "removed, replacement",
    [
        ("www.texasfirst.bank", "www.example.bank"),
        ("Summary of Activity Since Your Last Statement", "Account Summary"),
        ("Daily Balance Summary", "Balance History"),
    ],
)
def test_every_marker_is_load_bearing(removed, replacement):
    """Three required markers, and none of them is decoration."""
    assert not detect_texas_first(whole().replace(removed, replacement)).claims


def test_the_daily_grid_is_a_detection_marker_not_only_a_parse_requirement():
    """A printing with no daily grid is one whose ATM directions cannot be
    solved, so the registration must not CLAIM it — claiming and then declining
    would strand a document another reader could have taken."""
    without = whole().replace("Daily Balance Summary", "Balance History")
    assert not detect_texas_first(without).claims
    assert parse_texas_first_scanned_statement(without) is None


def test_parse_rechecks_detection():
    assert parse_texas_first_scanned_statement("a lease agreement") is None


# ---------------------------------------------------------------------------
# The whole statement
# ---------------------------------------------------------------------------


def test_the_statement_reproduces_every_printed_summary_figure():
    stmt = parse_texas_first_scanned_statement(whole())
    assert stmt is not None
    assert stmt.bank == "Texas First Bank"
    assert stmt.account_name == "SEAWALL8910 LLC"
    assert (stmt.period_start, stmt.period_end) == ("2054-04-01", "2054-04-30")
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 1290.00)
    assert (stmt.stated_credit_count, stmt.stated_total_credits) == (3, 800.00)
    assert (stmt.stated_debit_count, stmt.stated_total_debits) == (4, 510.00)
    assert stmt.stated_service_charge == 10.00
    assert stmt.bank_reported_average_balance == 1400.0
    assert stmt.bank_reported_average_label == "Average Balance"


def test_the_captured_ledger_equals_the_printed_counts_and_totals():
    stmt = parse_texas_first_scanned_statement(whole())
    credits = [t for t in stmt.transactions if t.amount > 0]
    debits = [t for t in stmt.transactions if t.amount < 0]
    assert (len(credits), round(sum(t.amount for t in credits), 2)) == (3, 800.00)
    assert (len(debits), round(-sum(t.amount for t in debits), 2)) == (4, 510.00)


def test_the_atm_directions_are_solved_and_not_read_off_the_row():
    """The proof that the split is arithmetic: the two ATM figures land on
    opposite sides, and nothing in their text was consulted to put them there.
    """
    stmt = parse_texas_first_scanned_statement(whole())
    atm = {t.description: t.amount for t in stmt.transactions if "ATM" in t.description or "POS" in t.description}
    assert atm == {"ATM Cash Deposit": 100.00, "POS Purchase Non-PIN": -50.00}


def test_the_wording_of_an_atm_row_is_not_what_decides_its_direction():
    """Rename both ATM rows to the same neutral string: the split is unchanged,
    because it never came from the words."""
    renamed = whole(atm="4/01 100.00 Debit Transfer\n4/03 50.00 Debit Transfer\n")
    stmt = parse_texas_first_scanned_statement(renamed)
    assert stmt is not None
    by_date = {(t.date, t.amount) for t in stmt.transactions if t.description == "Debit Transfer"}
    assert by_date == {("2054-04-01", 100.00), ("2054-04-03", -50.00)}


def test_a_multi_line_description_is_kept_whole():
    stmt = parse_texas_first_scanned_statement(whole())
    assert any(
        t.description == "ACME/BILL PAY ref 12345 ACME UTILITIES" for t in stmt.transactions
    )


def test_the_cheque_grid_is_three_columns_wide():
    """One printed line carries up to three (date, number, amount) cells; a
    reader that took only the first would under-count the debit side and the
    document would refuse."""
    stmt = parse_texas_first_scanned_statement(
        whole(
            summary=WHOLE_STATEMENT_SUMMARY.replace(
                "Withdrawals / Misc Debits 4 510.00", "Withdrawals / Misc Debits 6 710.00"
            ).replace("Ending Balance 4/30/54 1,290.00", "Ending Balance 4/30/54 1,090.00"),
            checks="4/03 1001 150.00 4/03 1002 120.00 4/03 1003* 80.00\n",
            daily="4/01 1,600.00 4/02 1,500.00 4/03 1,090.00\n",
        )
    )
    assert stmt is not None
    assert sorted(t.description for t in stmt.transactions if t.description.startswith("Check")) == [
        "Check 1001", "Check 1002", "Check 1003",
    ]


# ---------------------------------------------------------------------------
# The right-hand minus
# ---------------------------------------------------------------------------


OVERDRAWN = dict(
    summary=(
        "Summary of Activity Since Your Last Statement\n"
        "Beginning Balance 4/01/54 100.00\n"
        "Deposits / Misc Credits 1 500.00\n"
        "Withdrawals / Misc Debits 1 300.00\n"
        "** Ending Balance 4/30/54 300.00 **\n"
    ),
    credits="4/02 500.00 Deposit\n",
    debits="4/01 300.00 ACME/BILL PAY\n",
    daily="4/01 200.00 - 4/02 300.00\n",
)


def test_daily_balances_publish_chronologically_not_in_reading_order():
    """The grid is three columns wide, so its reading order is column-major:
    `4/01 ... 4/13 ... 4/23` on one line. Published in that order the series
    would zig-zag and its last entry would not be the period's last day."""
    stmt = parse_texas_first_scanned_statement(
        whole(daily="4/01 1,600.00 4/03 1,290.00\n4/02 1,500.00\n")
    )
    assert stmt is not None
    assert [d.date for d in stmt.stated_daily_balances] == [
        "2054-04-01", "2054-04-02", "2054-04-03",
    ]


def test_a_day_printed_twice_is_published_once():
    """A duplicate snapshot costs `analysis/adb.py` its `snapshot_dates_valid`
    for the whole document. The repeat has already had to agree to get here."""
    stmt = parse_texas_first_scanned_statement(
        whole(daily="4/01 1,600.00 4/02 1,500.00 4/03 1,290.00\n4/02 1,500.00\n")
    )
    assert stmt is not None
    assert [d.date for d in stmt.stated_daily_balances] == [
        "2054-04-01", "2054-04-02", "2054-04-03",
    ]


def test_a_day_printed_twice_with_two_balances_refuses():
    assert parse_texas_first_scanned_statement(
        whole(daily="4/01 1,600.00 4/02 1,500.00 4/03 1,290.00\n4/02 1,900.00\n")
    ) is None


def test_a_negative_daily_balance_prints_its_minus_on_the_right():
    stmt = parse_texas_first_scanned_statement(document(**OVERDRAWN))
    assert stmt is not None
    assert [(d.date, d.balance) for d in stmt.stated_daily_balances] == [
        ("2054-04-01", -200.00), ("2054-04-02", 300.00),
    ]


def test_reading_that_minus_as_absent_refuses_the_document():
    """The convention is proven, not assumed: with the hyphen gone the walk no
    longer reproduces the printed grid and nothing is published."""
    without = dict(OVERDRAWN, daily="4/01 200.00 4/02 300.00\n")
    assert parse_texas_first_scanned_statement(document(**without)) is None


def test_a_leading_minus_is_never_a_sign_here():
    """`-25.00` in the daily grid is a mis-scanned figure, not a negative
    balance: it must not clear the walk by being read as one."""
    mangled = dict(OVERDRAWN, daily="4/01 -200.00 4/02 300.00\n")
    assert parse_texas_first_scanned_statement(document(**mangled)) is None


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


def test_an_ambiguous_day_refuses_rather_than_choosing():
    """Two ATM rows of equal size on one day reach the printed balance under
    two different assignments. One of them calls a withdrawal a deposit, and
    the document does not say which — so nothing is published."""
    ambiguous = document(
        summary=(
            "Summary of Activity Since Your Last Statement\n"
            "Beginning Balance 4/01/54 1,000.00\n"
            "Deposits / Misc Credits 1 100.00\n"
            "Withdrawals / Misc Debits 1 100.00\n"
            "** Ending Balance 4/30/54 1,000.00 **\n"
        ),
        atm="4/01 100.00 Debit Transfer\n4/01 100.00 Debit Transfer\n",
        daily="4/01 1,000.00\n",
    )
    assert detect_texas_first(ambiguous).claims
    assert parse_texas_first_scanned_statement(ambiguous) is None


def test_a_stated_debit_count_the_grids_cannot_fill_refuses():
    """The aggregate COUNT fail-fast is LOAD-BEARING, not redundant.

    Every figure in this document agrees: both summary totals, both sections,
    the cheque, the closing identity and every printed daily balance. Only a
    COUNT is wrong — the summary says five debits and the grids hold four — and
    **nothing in the day walk constrains a count**, because the walk is
    arithmetic over money. Without this gate the document publishes
    `stated_debit_count=5` beside four debit transactions and every other
    oracle waves it through.
    """
    understated = document(
        summary=(
            "Summary of Activity Since Your Last Statement\n"
            "Beginning Balance 4/01/54 1,000.00\n"
            "Deposits / Misc Credits 1 500.00\n"
            "Withdrawals / Misc Debits 5 500.00\n"
            "** Ending Balance 4/30/54 1,000.00 **\n"
        ),
        credits="4/01 500.00 Deposit\n",
        debits=(
            "4/01 100.00 ACME/BILL PAY\n"
            "4/02 200.00 ACME/BILL PAY\n"
            "4/03 50.00 ACME/BILL PAY\n"
        ),
        checks="4/03 1001 150.00\n",
        daily="4/01 1,400.00 4/02 1,200.00 4/03 1,000.00\n",
    )
    assert detect_texas_first(understated).claims
    assert parse_texas_first_scanned_statement(understated) is None


def test_an_atm_split_whose_row_count_the_summary_denies_refuses():
    """The deposit-COUNT agreement is LOAD-BEARING, not corroboration.

    The summary counts ONE ATM deposit worth 100.00; the grid's `60.00` and
    `40.00` are uniquely both deposits under the day walk, which is two rows.
    The MONEY agrees on every side and the walk reproduces the printed balance
    exactly, so only this gate notices. Without it the document publishes three
    credit transactions against a stated credit count of two.
    """
    miscounted = document(
        summary=(
            "Summary of Activity Since Your Last Statement\n"
            "Beginning Balance 4/01/54 1,000.00\n"
            "Deposits / Misc Credits 2 600.00\n"
            "Withdrawals / Misc Debits 2 200.00\n"
            "** Ending Balance 4/30/54 1,400.00 **\n"
        ),
        credits="4/01 500.00 Deposit\n",
        debits="4/01 200.00 ACME/BILL PAY\n",
        atm="4/01 60.00 Debit Transfer\n4/01 40.00 Debit Transfer\n",
        daily="4/01 1,400.00\n",
    )
    assert detect_texas_first(miscounted).claims
    assert parse_texas_first_scanned_statement(miscounted) is None


def test_a_dropped_row_refuses_because_the_printed_counts_do_not_reconcile():
    """The archive's own failure mode: Tesseract loses a row and the summary's
    count is one short of what the grids hold."""
    assert parse_texas_first_scanned_statement(
        whole(atm="4/01 100.00 ATM Cash Deposit\n")
    ) is None


def test_a_row_the_scan_shrank_by_a_cent_refuses():
    assert parse_texas_first_scanned_statement(
        whole(atm="4/01 100.00 ATM Cash Deposit\n4/03 50.01 POS Purchase Non-PIN\n")
    ) is None


def test_an_illegible_daily_cell_refuses_the_whole_document():
    """`1,290.00` scanned as `1,290,00`. The ADB is computed over this grid, so
    a hole in it is not something to publish around."""
    assert parse_texas_first_scanned_statement(
        whole(daily="4/01 1,600.00 4/02 1,500.00 4/03 1,290,00\n")
    ) is None


PERIOD = dict(start=date(2054, 4, 1), end=date(2054, 4, 30))


def test_the_grid_reader_itself_refuses_an_unreadable_daily_cell():
    """Isolated from the walk on purpose. End to end an illegible cell is also
    caught downstream (the day it names then has ledger rows the grid does not
    mention), so only a direct reading proves that the GRID's own legibility is
    what this guard enforces."""
    legible = document(summary=WHOLE_STATEMENT_SUMMARY, daily="4/01 1,600.00 4/02 1,500.00\n")
    assert _tf_read_grids(legible, **PERIOD)[4] == [("2054-04-01", 160000), ("2054-04-02", 150000)]
    mangled = document(summary=WHOLE_STATEMENT_SUMMARY, daily="4/01 1,600.00 4/02 1,500,00\n")
    assert _tf_read_grids(mangled, **PERIOD) is None


def test_the_grid_reader_itself_refuses_an_unreadable_cheque_cell():
    legible = document(
        summary=WHOLE_STATEMENT_SUMMARY, checks="4/03 1001 150.00 4/03 1002 120.00\n"
    )
    assert len(_tf_read_grids(legible, **PERIOD)[3]) == 2
    mangled = document(
        summary=WHOLE_STATEMENT_SUMMARY, checks="4/03 1001 150.00 4/03 1002 12O.00\n"
    )
    assert _tf_read_grids(mangled, **PERIOD) is None


def test_a_day_the_grid_does_not_mention_refuses():
    assert parse_texas_first_scanned_statement(
        whole(daily="4/01 1,600.00 4/02 1,500.00\n")
    ) is None


def test_a_posting_dated_outside_the_printed_period_refuses():
    """The grids print month and day only; the year comes from the period and
    from nowhere else, so a mis-scanned month fails the document closed rather
    than acquiring a transaction in another year."""
    assert parse_texas_first_scanned_statement(
        whole(credits="5/01 500.00 Deposit\n4/02 200.00 Funds Transfer via Mobile\n")
    ) is None


def test_the_year_comes_from_the_period_and_a_date_outside_it_is_refused():
    """Isolated: end to end the same document is also caught by the daily grid
    (which does not mention the invented day), so only a direct reading proves
    that the period is what bounds the year."""
    assert _tf_iso("4/02", **PERIOD) == "2054-04-02"
    assert _tf_iso("5/01", **PERIOD) is None
    assert _tf_iso("2/30", **PERIOD) is None
    # A period spanning the new year resolves each half to its own year.
    across = dict(start=date(2053, 12, 28), end=date(2054, 1, 27))
    assert _tf_iso("12/30", **across) == "2053-12-30"
    assert _tf_iso("1/05", **across) == "2054-01-05"
    # A period long enough for BOTH candidate years to land inside it makes the
    # day genuinely ambiguous, and ambiguity refuses rather than picking one.
    # (A one-month template cannot print such a period — a mis-scanned period
    # date is how it would acquire one.)
    year_long = dict(start=date(2053, 3, 1), end=date(2054, 6, 30))
    assert _tf_iso("4/15", **year_long) is None
    assert _tf_iso("12/15", **year_long) == "2053-12-15"


def test_a_day_carrying_ledger_rows_but_no_printed_balance_is_refused():
    """Isolated at the solver: a grid that lost a day cannot be walked, and
    the walk must say so rather than skipping the day."""
    rows = _tf_read_grids(whole(), **PERIOD)
    credits, debits, atm, checks, daily = rows
    assert _tf_direct_atm(
        beginning=100000, daily=daily, credits=credits, debits=debits,
        atm=atm, checks=checks,
    ) is not None
    without_the_last_day = [cell for cell in daily if cell[0] != "2054-04-03"]
    assert _tf_direct_atm(
        beginning=100000, daily=without_the_last_day, credits=credits, debits=debits,
        atm=atm, checks=checks,
    ) is None


def test_a_summary_printed_twice_and_agreeing_is_corroboration():
    doubled = whole(extra=WHOLE_STATEMENT_SUMMARY)
    stmt = parse_texas_first_scanned_statement(doubled)
    assert stmt is not None
    assert stmt.beginning_balance == 1000.00


def test_a_summary_printed_twice_and_disagreeing_refuses():
    """Taking the first occurrence would publish one set of figures and never
    notice the other — on a two-account printing that is one account's summary
    under the other's heading."""
    contradicting = whole(
        extra=WHOLE_STATEMENT_SUMMARY.replace(
            "Beginning Balance 4/01/54 1,000.00", "Beginning Balance 4/01/54 9,000.00"
        )
    )
    assert parse_texas_first_scanned_statement(contradicting) is None


def test_a_summary_that_does_not_close_publishes_nothing():
    assert parse_texas_first_scanned_statement(
        whole(
            summary=WHOLE_STATEMENT_SUMMARY.replace(
                "Ending Balance 4/30/54 1,290.00", "Ending Balance 4/30/54 1,300.00"
            )
        )
    ) is None


def test_a_header_with_no_ledger_publishes_nothing():
    header = document(summary=WHOLE_STATEMENT_SUMMARY, daily="4/01 1,600.00\n")
    assert detect_texas_first(header).claims
    assert parse_texas_first_scanned_statement(header) is None


# ---------------------------------------------------------------------------
# Fields this reader deliberately does not publish
# ---------------------------------------------------------------------------


def test_a_card_mask_is_never_published_as_the_account_number():
    """The header block's account mask is what the scan destroys on this class;
    the masks that survive belong to the ATM rows' card numbers."""
    with_cards = whole(
        atm=(
            "4/01 100.00 ATM Cash Deposit\n"
            "TEXAS FIRST B 6501 STEWART GALVESTON T\n"
            "1C762450 *****5512 04/01 12:19\n"
            "4/03 50.00 POS Purchase Non-PIN\n"
            "MICROSOFT*MICROSOFT MICROSOFT.COM W\n"
            "DFFBPHK6 *****8152 04/03 08:26\n"
        )
    )
    stmt = parse_texas_first_scanned_statement(with_cards)
    assert stmt is not None
    assert stmt.account_number is None


def test_the_closing_disclosure_paragraph_is_not_read_as_daily_cells():
    """The grid ends at its last cell line; the URL that follows it carries
    digits and a slash and must not become a balance."""
    stmt = parse_texas_first_scanned_statement(
        whole(
            extra=(
                "Please review the Account Agreement for updates on our website\n"
                "https://texasfirst.bank/wp-content/uploads/2025/03/Account-Agreement\n"
            )
        )
    )
    assert stmt is not None
    assert [d.date for d in stmt.stated_daily_balances] == [
        "2054-04-01", "2054-04-02", "2054-04-03",
    ]


def test_the_page_furniture_between_sections_is_not_read_as_rows():
    """The template reprints each section head after the page break, so the
    section state resets at the break and the address block cannot be
    attributed to the section that ended on the previous page."""
    paged = whole().replace(
        "Checks\nDate Check No Amount",
        "--- Page 2 ---\n" + FURNITURE + "\nChecks\nDate Check No Amount",
    )
    stmt = parse_texas_first_scanned_statement(paged)
    assert stmt is not None
    assert len(stmt.transactions) == 7
