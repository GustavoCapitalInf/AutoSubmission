"""The CitiBusiness `CHECKING ACTIVITY` statement (W3 §CITI3 card B).

Fixtures are hand-built in the layout's printed shape with invented names and
figures. The two flattenings the family arrives in are both pinned, because
they are the reason the module reads an invariant rather than an arrangement.
"""
from __future__ import annotations

from analysis import citibusiness as cb
from analysis.schema import Statement

_HEADER = (
    "Citibank CBO Services 729 P.O. Box 6201 Sioux Falls, SD 57117-6201\n"
    "000 CITIBANK, N. A. Account 17505240 Statement Period Apr 1 - Apr 30, 2054 "
    "Relationship Manager Citibusiness Service Center Page 1  of  4\n"
    "EXAMPLE COMPANY INC\n"
    "CitiBusiness  ACCOUNT AS OF APRIL 30, 2054\n"
    "Relationship Summary:\n"
    "Checking $1,200.00 Savings ----- Checking Plus -----\n"
    "SERVICE CHARGE SUMMARY FROM MARCH 1, 2054 THRU MARCH 31, 2054\n"
    "Type of Charge No./Units Price/Unit Amount\n"
    "CITIBUSINESS CHECKING # 17505240\n"
    "Average Daily Collected Balance $33,564.86\n"
    "Total Charges for Services $189.35\n"
    "CHECKING ACTIVITY\n"
    "CitiBusiness Checking 17505240 Beginning Balance: $1,000.00 Ending Balance: $1,200.00\n"
)
_FOOTER = "CUSTOMER SERVICE INFORMATION\nMember FDIC.\n"


def _document(rows: str, *, totals: str = "300.00 500.00", header: str = _HEADER) -> str:
    return (
        header
        + "Date Description Debits Credits Balance "
        + rows
        + "\n"
        + f"Total Debits/Credits {totals}\n"
        + _FOOTER
    )


#: The flattening that prints both money cells at the END of the row.
_TRAILING = (
    "04/01 ELECTRONIC CREDIT SOME PAYER     EDI PYMNTS MR1812191363491 Apr 01 500.00 1,500.00\n"
    "04/02 ACH DEBIT SOME BILLER  ACHPAY  70904150        Apr 02 300.00 1,200.00"
)
#: The flattening that prints them straight after the transaction TYPE and the
#: rest of the description after them.
_INTERLEAVED = (
    "04/01 FUNDS TRANSFER 500.00 1,500.00 WIRE FROM SOME PAYER Apr 01 "
    "04/02 ACH DEBIT 300.00 1,200.00 SOME BILLER  ACH PMT  M3662  Apr 02"
)


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------

def test_detects_its_own_layout():
    assert cb.detect(_document(_TRAILING)).claims


def test_the_bank_name_alone_is_not_evidence():
    assert not cb.detect("CITIBANK, N. A.\nBeginning Balance\nEnding Balance\n").claims


def test_the_product_name_alone_is_not_evidence():
    assert not cb.detect("CitiBusiness\nAccount Summary\n").claims


def test_detection_does_not_depend_on_the_filename():
    named = "<!-- SOURCE: CitiBusiness CHECKING ACTIVITY.pdf -->\nBeginning Balance\n"
    assert not cb.detect(named).claims


# ---------------------------------------------------------------------------
# both flattenings of one printed grid
# ---------------------------------------------------------------------------

def test_reads_the_flattening_that_trails_its_money_cells():
    stmt = cb.parse_citibusiness_statement(_document(_TRAILING))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [500.00, -300.00]
    assert [t.running_balance for t in stmt.transactions] == [1500.00, 1200.00]
    assert stmt.transactions[0].description.startswith("ELECTRONIC CREDIT SOME PAYER")


def test_reads_the_flattening_that_interleaves_its_money_cells():
    """The description is printed on BOTH sides of the two figures here, and
    the published description must carry all of it."""
    stmt = cb.parse_citibusiness_statement(_document(_INTERLEAVED))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [500.00, -300.00]
    assert stmt.transactions[0].description == "FUNDS TRANSFER WIRE FROM SOME PAYER Apr 01"
    assert stmt.transactions[1].description == "ACH DEBIT SOME BILLER ACH PMT M3662 Apr 02"


def test_both_flattenings_publish_the_same_ledger():
    trailing = cb.parse_citibusiness_statement(_document(_TRAILING))
    interleaved = cb.parse_citibusiness_statement(_document(_INTERLEAVED))
    assert [t.amount for t in trailing.transactions] == [
        t.amount for t in interleaved.transactions
    ]
    assert [t.date for t in trailing.transactions] == [
        t.date for t in interleaved.transactions
    ]


# ---------------------------------------------------------------------------
# what is a printed cell, and what is only quoted
# ---------------------------------------------------------------------------

def test_an_edi_reference_quoting_the_amount_is_not_two_more_columns():
    """`RMR*IV*...*AI*508497.83*508497.83*0.` names the payment twice inside
    the description. A printed cell stands in a column, so it begins a
    whitespace-delimited token; these quotations do not."""
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME AGENCY MISC PAY 521888039690011 Apr 01 "
            "RMR*IV*REF-2605*AI*500.00*500.00*0. 500.00 1,500.00\n"
            "04/02 ACH DEBIT SOME BILLER Apr 02 300.00 1,200.00"
        )
    )
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [500.00, -300.00]
    assert "RMR*IV*REF-2605*AI*500.00*500.00*0." in stmt.transactions[0].description


def test_a_digit_run_containing_a_slash_does_not_open_a_row():
    """`SAFE BOX DR, BOX# 07730/0001157` prints `30/00` inside a longer run."""
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME PAYER Apr 01 500.00 1,500.00\n"
            "04/02 SAFE BOX DR, BOX# 07730/0001157 300.00 1,200.00"
        )
    )
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert "07730/0001157" in stmt.transactions[1].description


def test_two_rows_printed_on_one_physical_line_are_two_rows():
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME PAYER Apr 01 500.00 1,500.00 "
            "04/02 ACH DEBIT SOME BILLER Apr 02 300.00 1,200.00"
        )
    )
    assert stmt is not None
    assert len(stmt.transactions) == 2


# ---------------------------------------------------------------------------
# direction, read from the bank's own arithmetic
# ---------------------------------------------------------------------------

def test_direction_comes_from_the_printed_balances_not_the_wording():
    """The description says CREDIT on a row the balances say is a debit. The
    balances win, because they are the column the layout kept."""
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME PAYER Apr 01 500.00 1,500.00\n"
            "04/02 ELECTRONIC CREDIT SOME PAYER Apr 02 300.00 1,200.00"
        )
    )
    assert [t.direction for t in stmt.transactions] == ["credit", "debit"]


def test_a_magnitude_that_contradicts_the_balance_movement_fails_closed():
    assert cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME PAYER Apr 01 500.00 1,500.00\n"
            "04/02 ACH DEBIT SOME BILLER Apr 02 999.00 1,200.00"
        )
    ) is None


def test_an_overdrawn_balance_carries_its_trailing_minus():
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ACH DEBIT SOME BILLER Apr 01 800.00 200.00\n"
            "04/02 ACH DEBIT SOME BILLER Apr 02 300.00 100.00-",
            header=_HEADER.replace("Ending Balance: $1,200.00", "Ending Balance: $100.00-")
            .replace("Checking $1,200.00", "Checking $100.00-"),
            totals="1,100.00 0.00",
        )
    )
    assert stmt is not None
    assert stmt.ending_balance == -100.00
    assert stmt.transactions[-1].running_balance == -100.00
    assert stmt.transactions[-1].amount == -300.00


def test_a_zero_amount_row_is_published_at_zero():
    stmt = cb.parse_citibusiness_statement(
        _document(
            "04/01 ELECTRONIC CREDIT SOME PAYER Apr 01 500.00 1,500.00\n"
            "04/02 ELECTRONIC CREDIT SOME PAYER  ACH Apr 02 0.00 1,500.00\n"
            "04/03 ACH DEBIT SOME BILLER Apr 03 300.00 1,200.00"
        )
    )
    assert stmt is not None
    assert stmt.transactions[1].amount == 0.0


# ---------------------------------------------------------------------------
# the summary figures
# ---------------------------------------------------------------------------

def test_reads_the_period_the_account_and_both_balances():
    stmt = cb.parse_citibusiness_statement(_document(_TRAILING))
    assert stmt.bank == "Citibank"
    assert stmt.account_number == "17505240"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00


def test_the_totals_row_prints_debits_first():
    stmt = cb.parse_citibusiness_statement(_document(_TRAILING))
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_total_credits == 500.00


def test_the_totals_row_prints_no_counts_so_none_are_claimed():
    stmt = cb.parse_citibusiness_statement(_document(_TRAILING))
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_the_service_charge_average_is_the_previous_periods_and_is_not_published():
    """Every statement of this family prints `Average Daily Collected Balance`
    inside a `SERVICE CHARGE SUMMARY` block covering the PREVIOUS analysis
    period — an April statement carries March's. Publishing it would report
    another period's average as this one's."""
    markdown = _document(_TRAILING)
    assert "Average Daily Collected Balance $33,564.86" in markdown
    assert "FROM MARCH 1, 2054 THRU MARCH 31, 2054" in markdown
    stmt = cb.parse_citibusiness_statement(markdown)
    assert stmt.period_start == "2054-04-01"
    assert stmt.stated_average_balance is None


def test_a_period_that_crosses_a_year_boundary_takes_the_earlier_start_year():
    stmt = cb.parse_citibusiness_statement(
        _document(
            "12/31 ELECTRONIC CREDIT SOME PAYER Dec 31 500.00 1,500.00\n"
            "01/02 ACH DEBIT SOME BILLER Jan 02 300.00 1,200.00",
            header=_HEADER.replace(
                "Statement Period Apr 1 - Apr 30, 2054",
                "Statement Period Dec 1 - Jan 31, 2055",
            ),
        )
    )
    assert stmt is not None
    assert stmt.period_start == "2054-12-01"
    assert stmt.period_end == "2055-01-31"
    assert [t.date for t in stmt.transactions] == ["2054-12-31", "2055-01-02"]


def test_a_header_with_no_ledger_is_not_a_statement():
    assert cb.parse_citibusiness_statement(_document("")) is None


# ---------------------------------------------------------------------------
# the integrity check
# ---------------------------------------------------------------------------

def test_the_relationship_balance_agreeing_with_the_ledger_raises_nothing():
    markdown = _document(_TRAILING)
    stmt = cb.parse_citibusiness_statement(markdown)
    assert cb.closing_balance_contradictions(markdown, stmt) == []


def test_a_relationship_balance_that_contradicts_the_ledger_is_reported():
    markdown = _document(_TRAILING).replace("Checking $1,200.00", "Checking $9,999.00")
    stmt = cb.parse_citibusiness_statement(markdown)
    flags = cb.closing_balance_contradictions(markdown, stmt)
    assert flags and "Relationship Summary" in flags[0]


def test_the_integrity_check_is_wired_to_the_registration():
    from analysis.parser_registry import registrations
    from analysis.parser_registry_entries import load

    load()
    entry = next(r for r in registrations() if r.id == "citibusiness")
    assert cb.closing_balance_contradictions in entry.integrity_checks


def test_the_published_statement_is_a_statement_object():
    assert isinstance(cb.parse_citibusiness_statement(_document(_TRAILING)), Statement)
