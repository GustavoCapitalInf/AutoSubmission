"""Statement periods that cross a year boundary (audit 2026-10-13 PARSERS-2).

Most readers stamp the period's END year on a row that prints only month and
day, and rely on `analysis.dates.assign_transaction_years` to correct the year
afterwards. That correction rewrites `Statement.transactions` and nothing
else, so the shortcut breaks wherever a reader compares or publishes a date
INSIDE its own parse:

* PNC walks its end-of-day ladder against the rows inside `parse`, so every
  December-to-January statement with December activity was refused;
* IBC keyed its daily balances by ``MM/DD`` (so the minimum was January and the
  maximum December) and published them under the end year;
* Columbia forced a row whose printed month is not the start month onto the
  start month (a silent re-date), and dated everything else with the end year;
* First Community built the period start with the end year, inverting the
  period of a December-to-January statement.

The fix is the REFUSE form, and only that: each of these readers now dates a
row and a printed cell through the printed period, a token that is not a
calendar date is treated as it was before, and a row or printed cell the period
does not contain declines the document (it is never skipped). Every fixture is
synthetic: neutral figures, years 2053-2054, account numbers of zeros.
"""
from __future__ import annotations

import re

import pytest

from analysis import columbia_bank, first_community, ibc, pnc
from analysis.adb import compute_average_daily_balance
from analysis.dates import assign_transaction_years


def _adb_after_years(stmt):
    """What the pipeline does next: correct the row years, then the ADB."""
    return compute_average_daily_balance(assign_transaction_years(stmt))


def _failing(result) -> list[str]:
    return sorted(name for name, ok in (result.validations or {}).items() if ok is False)


# ---------------------------------------------------------------------------
# PNC — the commercial skin of tests/test_pnc_layouts.py, period varied.
# beginning 1,000.00 + 500.00 - 300.00 = ending 1,200.00
# ---------------------------------------------------------------------------

PNC_DESCRIBED_HEADER = "Date posted\nAmount\nTransaction description\nReference\nnumber\n"


def pnc_doc(*, start: str, end: str, credit_day: str, debit_day: str, ladder: str) -> str:
    index = (
        "Description Items Amount Deposits 1 500.00 National Lockbox 0 .00 "
        "Trade Services 0 .00 Other Credits 0 .00\n"
        "Description Items Amount ACH Debits 1 300.00 Trade Services 0 .00 "
        "Other Debits 0 .00 Total 1 500.00 Total 1 300.00\n"
    )
    activity = (
        "Deposits and Other Credits\n"
        "Deposits 1 transaction for a total of $500.00\n"
        f"{PNC_DESCRIBED_HEADER}"
        f"{credit_day} 500.00 Deposit 000000001\n"
        "Checks and Other Debits\n"
        "ACH Debits 1 transaction for a total of $300.00\n"
        f"{PNC_DESCRIBED_HEADER}"
        f"{debit_day} 300.00 An ACH Debit 000000002\n"
    )
    return (
        "PNC Core Commercial Checking Account Statement\n"
        "Page 1 of 1\n"
        "Account Number: XX-XXXX-0000\n"
        f"For the period {start} to {end}\n"
        "Visit us at PNC.com/treasury\n"
        "Account Summary Information\n"
        "Balance Summary\n"
        "Ending balance 1,000.00 500.00 300.00 1,200.00\n"
        "Beginning\nDeposits and\nChecks and other debits\nbalance\nother credits\n"
        "Deposits and Other Credits\nChecks and Other Debits\n"
        f"{index}"
        "Ledger Balance\n"
        f"Date Ledger balance {ladder}\n"
        f"{activity}"
    )


def pnc_dec_jan(*, ladder: str = "12/20 1,500.00 01/10 1,200.00",
                credit_day: str = "12/20", debit_day: str = "01/10") -> str:
    return pnc_doc(start="12/16/2053", end="01/15/2054", credit_day=credit_day,
                   debit_day=debit_day, ladder=ladder)


def test_pnc_a_december_to_january_statement_with_a_ladder_in_both_months_publishes():
    stmt = pnc.parse_pnc_statement(pnc_dec_jan())
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == ("2053-12-16", "2054-01-15")
    assert [t.date for t in stmt.transactions] == ["2053-12-20", "2054-01-10"]
    assert [s.date for s in stmt.stated_daily_balances] == ["2053-12-20", "2054-01-10"]
    result = _adb_after_years(stmt)
    assert result.ok, _failing(result)
    assert result.validations["bank_daily_balance_dates_valid"] is True


def test_pnc_a_december_row_under_a_january_only_ladder_is_walked_in_its_own_year():
    """The December row used to be dated in the END year, so the walk never
    applied it and the January cell disagreed."""
    stmt = pnc.parse_pnc_statement(pnc_dec_jan(ladder="01/10 1,200.00"))
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == ["2053-12-20", "2054-01-10"]


@pytest.mark.parametrize("ladder", [
    "11/30 1,000.00 12/20 1,500.00 01/10 1,200.00",   # a November cell
    "12/20 1,500.00 01/10 1,200.00 01/20 1,200.00",   # a cell after the period
])
def test_pnc_negative_a_ladder_cell_outside_a_year_crossing_period_still_refuses(ladder):
    assert pnc.parse_pnc_statement(pnc_dec_jan(ladder=ladder)) is None


def test_pnc_negative_a_row_outside_the_printed_period_refuses_the_document():
    """A row the period does not contain is refused, never skipped or kept. On
    a single-year period such a row used to be KEPT under an out-of-period
    date whenever no ladder cell stood after it (this ladder prints none)."""
    doc = pnc_doc(start="04/01/2054", end="04/30/2054", credit_day="04/02",
                  debit_day="05/01", ladder="04/02 1,500.00")
    assert pnc.parse_pnc_statement(doc) is None
    # the same document with the row inside the period publishes
    inside = pnc_doc(start="04/01/2054", end="04/30/2054", credit_day="04/02",
                     debit_day="04/29", ladder="04/02 1,500.00")
    assert pnc.parse_pnc_statement(inside) is not None


def test_pnc_negative_a_year_crossing_row_outside_the_period_refuses():
    assert pnc.parse_pnc_statement(pnc_dec_jan(debit_day="02/10", ladder="12/20 1,500.00")) is None


def test_pnc_a_ladder_token_that_is_no_calendar_date_is_still_passed_over():
    """Not a date (``04/31``) and outside the period are different findings:
    the first is a token the grammar cannot read and is passed over as it
    always was; only the second refuses."""
    doc = pnc_doc(start="04/01/2054", end="04/30/2054", credit_day="04/02",
                  debit_day="04/30", ladder="04/02 1,500.00 04/31 9.99 04/30 1,200.00")
    stmt = pnc.parse_pnc_statement(doc)
    assert stmt is not None
    assert [s.date for s in stmt.stated_daily_balances] == ["2054-04-02", "2054-04-30"]


def test_pnc_a_single_year_mid_month_statement_reads_exactly_as_before():
    stmt = pnc.parse_pnc_statement(pnc_doc(
        start="03/16/2054", end="04/15/2054", credit_day="03/20", debit_day="04/10",
        ladder="03/20 1,500.00 04/10 1,200.00"))
    assert stmt is not None
    assert [(t.date, t.amount) for t in stmt.transactions] == [
        ("2054-03-20", 500.0), ("2054-04-10", -300.0)]
    assert [(s.date, s.balance) for s in stmt.stated_daily_balances] == [
        ("2054-03-20", 1500.0), ("2054-04-10", 1200.0)]


# ---------------------------------------------------------------------------
# IBC — the reader requires exactly 12 deposits, 9 electronic credits, 30
# cheques and 266 electronic debits, so the fixture prints exactly those.
# ---------------------------------------------------------------------------

def ibc_doc(*, start: str, end: str, first: str, second: str, cheque_day: str | None = None,
            daily_extra: str = "") -> str:
    def day(i: int, in_first: bool) -> str:
        # first month: days 17..28; second month: days 02..13 (inside a 16th-to-15th period)
        return f"{first}/{17 + (i % 12):02d}" if in_first else f"{second}/{2 + (i % 12):02d}"

    deposits = "\n".join(f"{day(i, i % 2 == 1)} 1 10.00" for i in range(12))
    cheques = [f"{day(i, True)} {100 + i} 1.00" for i in range(30)]
    if cheque_day is not None:
        cheques[0] = f"{cheque_day} 100 1.00"
    electronic_credits = "\n".join(f"{day(i, False)} ACH Deposit PAYER 10.00" for i in range(9))
    electronic_debits = "\n".join(
        f"{day(i, i % 2 == 1)} ACH Payment VENDOR 1.00" for i in range(266))
    beginning, credits, debits = 1000.00, 210.00, 296.00
    ending = round(beginning + credits - debits, 2)
    return (
        "IBC\n"
        f"Statement Period: {start} - {end}\n"
        "Biz Rite Account Recap Account Number: 0000000\n"
        "Balance Credits Credits Debits Debits Balance\n"
        f"{beginning:,.2f} 21 {credits:,.2f} 296 {debits:,.2f} {ending:,.2f}\n"
        "Total Service Charge Posted 0.00\n"
        "Average Collected Balance 1,000.00\n"
        "Deposits (Credits)\n"
        f"{deposits}\n"
        "Checks (Debits)\n"
        + "\n".join(cheques) + "\n"
        "--- Page 2 ---\n"
        "Credits Date Description Amount\n"
        f"{electronic_credits}\n"
        "Debits Date Description Amount\n"
        f"{electronic_debits}\n"
        "APCNH\n"
        "Daily Ending Balance\n"
        f"{start[:5]} {beginning:,.2f}\n"
        f"{daily_extra}"
        f"{end[:5]} {ending:,.2f}\n"
        "APCNH\n"
    )


IBC_DEC_JAN = dict(start="12/16/2053", end="01/15/2054", first="12", second="01")
IBC_SINGLE_YEAR = dict(start="03/16/2054", end="04/15/2054", first="03", second="04")


def test_ibc_a_december_to_january_statement_publishes_its_daily_balances_inside_the_period():
    """It used to decline itself: the daily map was keyed by ``MM/DD``, so its
    "first" day was in January and its "last" in December."""
    stmt = ibc.parse_ibc_statement(ibc_doc(**IBC_DEC_JAN))
    assert stmt is not None
    assert [s.date for s in stmt.stated_daily_balances] == ["2053-12-16", "2054-01-15"]
    assert sorted({t.date[:4] for t in stmt.transactions}) == ["2053", "2054"]
    assert all("2053-12-16" <= t.date <= "2054-01-15" for t in stmt.transactions)
    result = _adb_after_years(stmt)
    assert result.validations["bank_daily_balance_dates_valid"] is True
    assert result.validations["transactions_within_period"] is True


def test_ibc_a_single_year_statement_reads_as_before():
    stmt = ibc.parse_ibc_statement(ibc_doc(**IBC_SINGLE_YEAR))
    assert stmt is not None
    assert [s.date for s in stmt.stated_daily_balances] == ["2054-03-16", "2054-04-15"]
    assert {t.date[:4] for t in stmt.transactions} == {"2054"}


def test_ibc_negative_a_daily_balance_outside_the_period_refuses():
    assert ibc.parse_ibc_statement(ibc_doc(**IBC_SINGLE_YEAR, daily_extra="05/02 994.00\n")) is None


def test_ibc_negative_a_row_outside_the_period_refuses():
    assert ibc.parse_ibc_statement(ibc_doc(**IBC_SINGLE_YEAR, cheque_day="05/20")) is None


@pytest.mark.parametrize("bad_day", ["02/30", "13/05"])
def test_ibc_a_row_that_is_no_calendar_date_refuses_without_quoting_it(bad_day):
    """`date()` used to raise here with a message that echoed the printed day,
    month and the statement's year. The refusal is now the shared private one."""
    with pytest.raises(ValueError) as caught:
        ibc.parse_ibc_statement(ibc_doc(**IBC_SINGLE_YEAR, cheque_day=bad_day))
    message = str(caught.value)
    assert "date grammar refused a printed token" in message
    assert not re.search(r"\d", message), message
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_ibc_a_period_that_is_no_calendar_date_refuses_without_quoting_it():
    doc = ibc_doc(**IBC_SINGLE_YEAR).replace("03/16/2054 - 04/15/2054", "02/30/2054 - 04/15/2054")
    with pytest.raises(ValueError) as caught:
        ibc.parse_ibc_statement(doc)
    message = str(caught.value)
    assert message.startswith("date grammar refused a printed token (")
    # the only number the shared refusal may carry is its own length bound
    from analysis.date_tokens import MAX_DATE_TOKEN_CHARS

    assert not re.search(r"\d", message.replace(f"{MAX_DATE_TOKEN_CHARS}-character", "")), message
    assert caught.value.__cause__ is None and caught.value.__context__ is None


# ---------------------------------------------------------------------------
# Columbia — the template of tests/test_columbia_bank.py, period varied.
# opening 100.00 +200.00 -400.00 +300.00 -30.00 -20.00 = ending 150.00
# ---------------------------------------------------------------------------

def columbia_doc(*, last: str, this: str, deposit: str, ach_debit: str, ach_credit: str,
                 other_debit: str, cheque: str, grid: str) -> str:
    return "\n".join((
        f"{this} Page: 1 of 4\n"
        "Customer Service:\n"
        "HOLDER NAME PLLC\n"
        "1 EXAMPLE ST\n"
        "EXAMPLETOWN XX 00000-0000\n"
        f"Last statement: {last}\n"
        f"This statement: {this}\n"
        "MARKETPLACE CHECKING\n",
        "Account number XXXXXX0000 Beginning balance $100.00\n"
        "Low balance $60.00 Deposits/Additions $500.00\n"
        "Average balance $80.00 Withdrawals/Subtractions $450.00\n"
        "Interest earned $0.00 Ending balance $150.00\n",
        "Deposits/Additions\n"
        "Date Description Additions\n"
        f"{deposit} Deposit 200.00\n"
        "Total Additions $200.00\n",
        "ACH and Electronic Payments/Subtractions\n"
        "Date Description Subtractions\n"
        f"{ach_debit} ACH Debit Example Vendor 400.00\n"
        "Total ACH and Electronic Payments/Subtractions $400.00\n",
        "ACH and Electronic Deposits/Additions\n"
        "Date Description Additions\n"
        f"{ach_credit} ACH Credit Example Payer 300.00\n"
        "Total ACH and Electronic Deposits/Additions $300.00\n",
        "Other Withdrawals/Subtractions\n"
        "Date Description Subtractions\n"
        f"{other_debit} Automatic Ln Paymt Automatic Loan Pay 30.00\n"
        "Total Other Withdrawals/Subtractions $30.00\n",
        "Daily Balances\n"
        "Date Amount Date Amount Date Amount\n"
        f"{grid}\n",
        "Overdraft Fee Summary\n"
        "Total For Total\n"
        "This Period Year-to-Date\n"
        "Total Overdraft Fees $0.00 $0.00\n",
        "Checks\n"
        "Check # Amount Date\n"
        f"1001 $20.00 {cheque}\n"
        "(* Skip in check sequence, R-Check has been returned, + Electronified check) )\n"
        "Total Checks paid: 1 for -$20.00\n",
    ))


def columbia_dec_jan(**overrides) -> str:
    fields = dict(
        last="December 15, 2053", this="January 15, 2054",
        deposit="12-20", ach_debit="12-22", ach_credit="01-05", other_debit="01-06",
        cheque="01-07",
        grid=("12-15 100.00 12-22 -100.00 01-06 170.00\n"
              "12-20 300.00 01-05 200.00 01-07 150.00"),
    )
    fields.update(overrides)
    return columbia_doc(**fields)


def columbia_april(**overrides) -> str:
    fields = dict(
        last="March 31, 2054", this="April 30, 2054",
        deposit="04-02", ach_debit="04-03", ach_credit="04-05", other_debit="04-06",
        cheque="04-07",
        grid="03-31 100.00 04-05 200.00 04-07 150.00\n04-02 300.00 04-06 170.00\n04-03 -100.00",
    )
    fields.update(overrides)
    return columbia_doc(**fields)


def test_columbia_a_december_to_january_statement_dates_every_row_in_its_own_year():
    stmt = columbia_bank.parse_columbia_bank_statement(columbia_dec_jan())
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == ("2053-12-16", "2054-01-15")
    assert [(t.date, t.amount) for t in stmt.transactions] == [
        ("2053-12-20", 200.0), ("2053-12-22", -400.0), ("2054-01-05", 300.0),
        ("2054-01-06", -30.0), ("2054-01-07", -20.0)]
    # the grid's opening line (the previous statement's last day) is not a
    # balance of this period and stays out, as it always has
    assert [s.date for s in stmt.stated_daily_balances] == [
        "2053-12-20", "2053-12-22", "2054-01-05", "2054-01-06", "2054-01-07"]
    assert columbia_bank.daily_grid_contradictions(columbia_dec_jan(), stmt) == []
    result = _adb_after_years(stmt)
    assert result.ok, _failing(result)


def test_columbia_a_single_year_two_month_period_reads_its_second_month():
    """The forced start month pushed every second-month row into the first
    month, out of the period, and the section totals then declined it."""
    doc = columbia_doc(
        last="March 15, 2054", this="April 15, 2054",
        deposit="03-20", ach_debit="03-22", ach_credit="04-05", other_debit="04-06",
        cheque="04-07",
        grid="03-15 100.00 03-22 -100.00 04-06 170.00\n03-20 300.00 04-05 200.00 04-07 150.00",
    )
    stmt = columbia_bank.parse_columbia_bank_statement(doc)
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == [
        "2054-03-20", "2054-03-22", "2054-04-05", "2054-04-06", "2054-04-07"]


@pytest.mark.parametrize("printed", ["05-02", "01-02"])
def test_columbia_negative_a_row_printed_in_another_month_is_refused_not_re_dated(printed):
    """It used to be moved onto the start month and published as 04-02, with
    no flag. A row the printed period does not contain refuses."""
    assert columbia_bank.parse_columbia_bank_statement(columbia_april()) is not None
    assert columbia_bank.parse_columbia_bank_statement(columbia_april(deposit=printed)) is None


def test_columbia_negative_a_row_whose_month_is_no_month_is_not_re_dated():
    assert columbia_bank.parse_columbia_bank_statement(columbia_april(deposit="13-02")) is None


def test_columbia_negative_a_cheque_outside_the_period_refuses():
    assert columbia_bank.parse_columbia_bank_statement(columbia_april(cheque="05-07")) is None


def test_columbia_the_april_template_reads_exactly_as_before():
    stmt = columbia_bank.parse_columbia_bank_statement(columbia_april())
    assert [(t.date, t.amount) for t in stmt.transactions] == [
        ("2054-04-02", 200.0), ("2054-04-03", -400.0), ("2054-04-05", 300.0),
        ("2054-04-06", -30.0), ("2054-04-07", -20.0)]
    assert [s.date for s in stmt.stated_daily_balances] == [
        "2054-04-02", "2054-04-03", "2054-04-05", "2054-04-06", "2054-04-07"]


# ---------------------------------------------------------------------------
# First Community
# ---------------------------------------------------------------------------

def fc_doc(*, ending: str, start_mmdd: str, end_mmdd: str, d1: str, d2: str) -> str:
    return (
        "firstcommunity.com\n"
        f"STATEMENT ENDING {ending}\n"
        "BUSINESS PLUS CKG-000-70\n"
        "ACCOUNT SUMMARY\n"
        "DATE DESCRIPTION AMOUNT\n"
        f"{start_mmdd} Beginning Balance $1,000.00\n"
        "1 Credits This Period $500.00\n"
        "1 Debits This Period $300.00\n"
        f"{end_mmdd} Ending Balance $1,200.00\n"
        "ACCOUNT ACTIVITY\n"
        f"{d1} DEPOSIT 500.00 1,500.00\n"
        f"{d2} POS PURCHASE -300.00 1,200.00\n"
        "OVERDRAFT AND RETURNED ITEM FEES\n"
    )


def test_first_community_a_december_to_january_period_is_not_inverted():
    stmt = first_community.parse_first_community_statement(fc_doc(
        ending="01/15/2054", start_mmdd="12/16", end_mmdd="01/15", d1="12/20", d2="01/10"))
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == ("2053-12-16", "2054-01-15")
    assert stmt.days_in_period == 31
    result = _adb_after_years(stmt)
    assert result.ok, _failing(result)
    assert [d.date for d in result.daily_balances][:1] == ["2053-12-16"]


def test_first_community_days_in_period_is_the_period_not_the_end_day():
    """The end date's day-of-month was published as the bank-stated period
    length: 15 for a 16th-to-15th cycle of 31 days."""
    stmt = first_community.parse_first_community_statement(fc_doc(
        ending="04/15/2054", start_mmdd="03/16", end_mmdd="04/15", d1="03/20", d2="04/10"))
    assert stmt.days_in_period == 31
    assert (stmt.period_start, stmt.period_end) == ("2054-03-16", "2054-04-15")


def test_first_community_a_calendar_month_reads_as_before():
    stmt = first_community.parse_first_community_statement(fc_doc(
        ending="03/31/2054", start_mmdd="03/01", end_mmdd="03/31", d1="03/05", d2="03/20"))
    assert (stmt.period_start, stmt.period_end, stmt.days_in_period) == (
        "2054-03-01", "2054-03-31", 31)
    assert [t.date for t in stmt.transactions] == ["2054-03-05", "2054-03-20"]
