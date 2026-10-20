"""W3 Track A / REEF-2: Chase native-text layout families.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* found
in the withheld chase population (W3-2 cell `chase x detail_coverage`, 217
documents). Institution markers are Chase's own layout sentinels — the same
ones the existing chase tests use, because they are what the parser keys on —
and every description, counterparty, date and amount is invented.

The shapes, and why each one used to lose money:

F1 wrapped-amount-cell   the amount column wraps onto its own physical line
                         and the description keeps going after it
F2 unlisted-prefix       a row whose description begins with a phrase the old
                         `_ROW_STARTERS` whitelist did not list: the row was
                         folded into its predecessor, so one row vanished AND
                         the predecessor took the wrong amount
F3 compressed-line       the text layer emits the column header and several
                         rows on ONE physical line
F4 rate-suffixed amount  a foreign-currency row prints "X 0.000668276 (Exchg
                         Rte)" after the amount; the old last-token rule read
                         `0.00`
F5 heading-prefixed line a continuation line beginning "Fees Sec:..." made the
                         block scan claim an ELECTRONIC WITHDRAWALS block as
                         the FEES section, double-counting it
F6 cash-back row         the description carries its own money tokens and the
                         real amount is the wrapped amount cell
F7 check row variants    short/long check numbers and a second printed date
F8 described check row   an electronic check whose number and date/amount sit
                         on different physical lines
F9 multi-check line      several check rows on one physical line

Each family also carries a negative fixture: the rule must fire on the
printed structure, never on remembered wording.
"""
from __future__ import annotations

import pytest

from analysis.chase import parse_chase_statement
from analysis.reconcile import reconcile

HEADER = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
"""


def _summary(beginning: str = "$1,000.00", **totals: str) -> str:
    """A CHECKING SUMMARY block. Values are passed as printed strings."""
    line = " ".join(f"{label} {value}" for label, value in totals.items())
    return (
        "*start*summary\n"
        "CHECKING SUMMARY Chase Business Complete Checking\n"
        f"INSTANCES AMOUNT Beginning Balance {beginning}\n"
        f"{line}\n"
        "*end*summary\n"
    )


def _doc(summary: str, *blocks: str) -> str:
    return HEADER + summary + "".join(blocks)


def _amounts(markdown: str) -> list[float]:
    stmt = parse_chase_statement(markdown)
    assert stmt is not None
    return [t.amount for t in stmt.transactions]


# --------------------------------------------------------------------------
# F1 - the amount cell wraps onto its own line, description continues after it
# --------------------------------------------------------------------------

F1 = _doc(
    _summary(**{
        "Deposits and Additions": "2 4,300.00",
        "Electronic Withdrawals": "0 -0.00",
        "Ending Balance": "2 $5,300.00",
    }),
    """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/05 Chips Credit Via: Meridian Trust Company/0001 B/O: Quarry Lane Foods
1,300.00
Ref: Nbnf=Blue Harbor Partners Sec:CCD Trace#:100000000000001 Eed:260105 Ind
ID:900000000000001 Ind Name:Blue Harbor Partners Trn: 0000000001Tc
01/06 Chips Credit Via: Meridian Trust Company/0001 B/O: Quarry Lane Foods
3,000.00
Ref: Nbnf=Blue Harbor Partners Sec:CCD Trace#:100000000000002 Eed:260106 Ind
ID:900000000000001 Ind Name:Blue Harbor Partners Trn: 0000000002Tc
Total Deposits and Additions $4,300.00
*end*deposits and additions
""",
)


def test_f1_wrapped_amount_cell_keeps_every_row_and_its_own_amount():
    assert _amounts(F1) == [1300.0, 3000.0]
    assert reconcile(parse_chase_statement(F1)).ok


def test_f1_negative_a_trailing_reference_number_is_not_read_as_the_amount():
    """The continuation text ends in a trace/Trn token. Reading the row's
    LAST money-shaped token (the pre-fix rule) would drift; the amount cell is
    the wrapped line, whatever the description says afterwards."""
    stmt = parse_chase_statement(F1)
    assert [round(t.amount, 2) for t in stmt.transactions] == [1300.0, 3000.0]
    assert all("1,300.00" not in t.description for t in stmt.transactions)


# --------------------------------------------------------------------------
# F2 - a row whose description prefix was never on the whitelist
# --------------------------------------------------------------------------

def _f2(second_description: str) -> str:
    return _doc(
        _summary(**{
            "Deposits and Additions": "2 750.00",
            "Ending Balance": "2 $1,750.00",
        }),
        f"""*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/14 Zelle Payment From Harbor Freightways 10000000001 500.00
01/15 {second_description} 250.00
Total Deposits and Additions $750.00
*end*deposits and additions
""",
    )


@pytest.mark.parametrize(
    "description",
    [
        "Reversal: Ledger Adjustment Coastal Systems CA",
        "Chips Credit Via: Meridian Trust Company/0001 B/O: Northwind Freight",
        "Domestic Incoming Wire Fee Credit",
        "Cash Concentration Sweep From Sub Account",
        # a description that never existed in any whitelist and never will:
        "Qqzx Frobnicator Settlement 000000001",
    ],
)
def test_f2_a_row_starts_at_its_printed_date_whatever_the_description_says(description):
    assert _amounts(_f2(description)) == [500.0, 250.0]


def test_f2_negative_a_date_inside_a_description_does_not_start_a_row():
    """Card rows print a second MM/DD *inside* the row. That must stay part of
    the row it belongs to — the rule is 'the line begins with a date', not
    'the line contains one'."""
    md = _doc(
        _summary(**{
            "ATM & Debit Card Withdrawals": "1 -42.00",
            "Ending Balance": "1 $958.00",
        }),
        """*start*atm debit withdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/09 Card Purchase 01/08 Tidewater Supply 555-0100 NY Card 0001 42.00
Total ATM & Debit Card Withdrawals $42.00
*end*atm debit withdrawal
""",
    )
    assert _amounts(md) == [-42.0]


# --------------------------------------------------------------------------
# F2b - the dual-date row is dated by the POSTING date, not the second date
# --------------------------------------------------------------------------

F2B = _doc(
    _summary("$5,000.00", **{
        "Electronic Withdrawals": "2 -1,500.00",
        "Ending Balance": "2 $3,500.00",
    }),
    """*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/15 01/13 Online Transfer To Chk ...0001 Transaction#: 10000000004 1,000.00
01/16 01/16 Payment To Card Ending IN 0002 500.00
Total Electronic Withdrawals $1,500.00
*end*electronic withdrawal
""",
)


def test_f2b_a_dual_dated_row_carries_the_posting_date():
    """Chase's DATE column is the posting date; the second printed date is the
    transaction date. Dating the row by the second one puts its end-of-day
    balance on a day the bank prints no daily balance for — the condition
    `analysis/adb.py` calls `posting_dates_cover_source`, and the reason two
    pinned corpus statements reconstructed activity days the bank does not
    recognise (one of them outside the statement period entirely)."""
    stmt = parse_chase_statement(F2B)
    assert [t.date for t in stmt.transactions] == ["2054-01-15", "2054-01-16"]
    assert [t.amount for t in stmt.transactions] == [-1000.0, -500.0]


# --------------------------------------------------------------------------
# F3 - column header and several rows flattened onto ONE physical line
# --------------------------------------------------------------------------

F3 = _doc(
    _summary(**{
        "Deposits and Additions": "3 1,110.00",
        "Ending Balance": "3 $2,110.00",
    }),
    """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT 01/03 Chips Credit Via: Alder Works Bank/0001 $1,000.00 01/04 Cash Concentration Sweep From Sub Account 100.00 01/05 Reversal: Ledger Adjustment 10.00
Total Deposits and Additions $1,110.00
*end*deposits and additions
""",
)


def test_f3_rows_flattened_onto_one_line_are_separated_at_the_amount_date_seam():
    assert _amounts(F3) == [1000.0, 100.0, 10.0]
    assert reconcile(parse_chase_statement(F3)).ok


def test_f3_negative_a_date_not_preceded_by_an_amount_does_not_split_a_row():
    """Splitting inside a line is only legal where an amount cell ends and the
    next date column begins. A card row's second date is preceded by words,
    not by an amount, so it never splits."""
    md = _doc(
        _summary(**{
            "ATM & Debit Card Withdrawals": "2 -75.00",
            "Ending Balance": "2 $925.00",
        }),
        """*start*atm debit withdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT 01/09 Card Purchase 01/08 Tidewater Supply NY Card 0001 25.00 01/10 Card Purchase With Pin 01/10 Rockport Fuel NY Card 0001 50.00
Total ATM & Debit Card Withdrawals $75.00
*end*atm debit withdrawal
""",
    )
    assert _amounts(md) == [-25.0, -50.0]


# --------------------------------------------------------------------------
# F4 - a currency-conversion suffix after the amount
# --------------------------------------------------------------------------

F4 = _doc(
    _summary("$5,000.00", **{
        "ATM & Debit Card Withdrawals": "1 -3,319.46",
        "Ending Balance": "1 $1,680.54",
    }),
    """*start*atm debit withdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/26 Card Purchase 01/22 Harborline Ferries Overseas Card 0001
3,319.46
Won
4967200 X 0.000668276 (Exchg Rte)
Total ATM & Debit Card Withdrawals $3,319.46
*end*atm debit withdrawal
""",
)


def test_f4_a_conversion_rate_is_not_an_amount():
    assert _amounts(F4) == [-3319.46]


# --------------------------------------------------------------------------
# F5 - a continuation line that begins with another section's heading word
# --------------------------------------------------------------------------

F5 = _doc(
    _summary(**{
        "Electronic Withdrawals": "1 -25.19",
        "Fees": "1 -15.00",
        "Ending Balance": "2 $959.81",
    }),
    """*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/22 Orig CO Name:Summit Athletics Orig ID:B100000001 Desc Date: CO Entry Descr:Club
25.19
Fees Sec:PPD Trace#:100000000000003 Eed:260122 Ind ID: Ind
Name:Blue Harbor Partners Trn: 0000000003Tc
Total Electronic Withdrawals $25.19
*end*electronic withdrawal
*start*fees section
FEES
DATE DESCRIPTION AMOUNT
01/31 Monthly Service Fee 15.00
Total Fees $15.00
*end*fees section
""",
)


def test_f5_a_description_line_starting_with_a_heading_word_is_not_a_section():
    """`Fees Sec:PPD ...` is ACH furniture inside a description. Treating it as
    the FEES heading made the whole electronic-withdrawals block count twice."""
    assert _amounts(F5) == [-25.19, -15.0]
    assert reconcile(parse_chase_statement(F5)).ok


def test_f5_negative_a_real_heading_line_is_still_found_with_its_column_header():
    """The heading may stand alone, carry "(continued)", or be followed by the
    column header on the same physical line. All three are real."""
    md = _doc(
        _summary(**{
            "Electronic Withdrawals": "2 -60.00",
            "Ending Balance": "2 $940.00",
        }),
        """*start*electronic withdrawal
ELECTRONIC WITHDRAWALS DATE DESCRIPTION AMOUNT 01/05 Online Transfer To Chk ...0001 Transaction#: 10000000002 40.00
*end*electronic withdrawal
*start*electronic withdrawal
ELECTRONIC WITHDRAWALS (continued)
DATE DESCRIPTION AMOUNT
01/06 Online Transfer To Chk ...0001 Transaction#: 10000000003 20.00
Total Electronic Withdrawals $60.00
*end*electronic withdrawal
""",
    )
    assert _amounts(md) == [-40.0, -20.0]


# --------------------------------------------------------------------------
# F6 - purchase-with-cash-back: the description carries its own money tokens
# --------------------------------------------------------------------------

F6 = _doc(
    _summary(**{
        "ATM & Debit Card Withdrawals": "1 -392.94",
        "Ending Balance": "1 $607.06",
    }),
    """*start*atm debit withdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/26 Card Purchase W/Cash 01/25 Ridgeline Market Card 0001 Purchase $352.94 Cash Back $40.00
392.94
Total ATM & Debit Card Withdrawals $392.94
*end*atm debit withdrawal
""",
)


def test_f6_the_wrapped_amount_cell_wins_over_money_inside_the_description():
    assert _amounts(F6) == [-392.94]


# --------------------------------------------------------------------------
# F7/F8/F9 - CHECKS PAID variants
# --------------------------------------------------------------------------

F7 = _doc(
    _summary("$5,000.00", **{
        "Checks Paid": "4 -2,240.00",
        "Ending Balance": "4 $2,760.00",
    }),
    """*start*checks paid section
CHECKS PAID
DATE
AMOUNT
CHECK NO. DESCRIPTION
PAID
87 ^ 01/11 $240.00
222 ^ 01/25 01/25 1,000.00
1037 * ^ 01/11 500.00
500004963 * ^ 01/20 500.00
Total Checks Paid $2,240.00
*end*checks paid section
""",
)


def test_f7_short_long_and_dual_dated_check_rows_are_all_captured():
    assert _amounts(F7) == [-240.0, -1000.0, -500.0, -500.0]
    assert reconcile(parse_chase_statement(F7)).ok


F8 = _doc(
    _summary(**{
        "Checks Paid": "2 -382.50",
        "Ending Balance": "2 $617.50",
    }),
    """*start*checks paid section
CHECKS PAID
DATE
AMOUNT
CHECK NO. DESCRIPTION
PAID
133 Orig CO Name:Larkspur Motors Orig ID:C100000001 Desc
01/05 $182.50
Date:260103 CO Entry Descr:Purchase Sec:POP
Trace#:100000000000004 Eed:260105 Ind ID:133 Ind
Name:1400000000000000000000
Telechk 555-0100 Trn: 0000000004Tc
134 ^ 01/05 200.00
Total Checks Paid $382.50
*end*checks paid section
""",
)


def test_f8_a_described_electronic_check_row_spanning_lines_is_captured():
    assert _amounts(F8) == [-182.5, -200.0]
    assert reconcile(parse_chase_statement(F8)).ok


F9 = _doc(
    _summary("$5,000.00", **{
        "Checks Paid": "2 -1,740.00",
        "Ending Balance": "2 $3,260.00",
    }),
    """*start*checks paid section
CHECKS PAID
DATE PAID AMOUNT 87 ^ 01/11 $240.00 88 ^ 01/08 1,500.00
CHECK NO. DESCRIPTION
Total Checks Paid $1,740.00
*end*checks paid section
""",
)


def test_f9_several_check_rows_on_one_physical_line_are_separated():
    assert _amounts(F9) == [-240.0, -1500.0]
    assert reconcile(parse_chase_statement(F9)).ok


def test_negative_a_page_barcode_run_is_not_a_check_number():
    """Chase prints a long digit run (a page barcode) inside some blocks. It
    starts a line with digits but is not a check row, and must not swallow or
    split one."""
    md = _doc(
        _summary(**{
            "Checks Paid": "1 -300.00",
            "Ending Balance": "1 $700.00",
        }),
        """*start*checks paid section
CHECKS PAID
DATE
AMOUNT
CHECK NO. DESCRIPTION
PAID
127 ^ 01/12 $300.00
10540940402000000064
Total Checks Paid $300.00
*end*checks paid section
""",
    )
    assert _amounts(md) == [-300.0]


# --------------------------------------------------------------------------
# F10 - the Commercial Checking summary layout
# --------------------------------------------------------------------------

F10 = (
    HEADER
    + """*start*summary
Commercial Checking
CHECKING SUMMARY
INSTANCES AMOUNT
Beginning Balance $10,000.00
Deposits and Additions 2 5,000.00
Checks Paid 1 - 1,500.00
Electronic Withdrawals 1 - 2,000.00
Other Withdrawals, Fees & Charges 1 - 500.00
Ending Balance 5 $11,000.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/03 Zelle Payment From Alder Works Rgn0000000001 4,000.00
01/04 Deposit 1000000001 1,000.00
Total Deposits and Additions $5,000.00
*end*deposits and additions
*start*checks paid section
CHECKS PAID
DATE
AMOUNT
CHECK NO. DESCRIPTION
PAID
501 ^ 01/05 $1,500.00
Total Checks Paid $1,500.00
*end*checks paid section
*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/06 Online Transfer To Chk ...0001 Transaction#: 10000000009 2,000.00
Total Electronic Withdrawals $2,000.00
*end*electronic withdrawal
*start*other withdrawal fees charges
OTHER WITHDRAWALS, FEES & CHARGES
DATE DESCRIPTION AMOUNT
01/07 Account Analysis Settlement Charge 500.00
Total Other Withdrawals, Fees & Charges $500.00
*end*other withdrawal fees charges
"""
)


def test_f10_a_summary_that_spaces_its_minus_sign_still_states_its_debits():
    """`Checks Paid 1 - 1,500.00`: a space between the sign and the figure.
    A pattern demanding the sign adjacent to the digits matched no debit row,
    so `stated_total_debits` stayed None and the bank's own summary could not
    be checked against the ledger."""
    stmt = parse_chase_statement(F10)
    assert stmt is not None
    assert stmt.stated_total_credits == 5000.0
    assert stmt.stated_total_debits == 4000.0
    assert stmt.stated_debit_count == 3
    assert [t.amount for t in stmt.transactions] == [4000.0, 1000.0, -1500.0, -2000.0, -500.0]
    assert reconcile(stmt).ok


# --------------------------------------------------------------------------
# F11 - a row cut in half by a page break
# --------------------------------------------------------------------------

F11 = _doc(
    _summary(**{
        "Deposits and Additions": "2 3,000.00",
        "Ending Balance": "2 $4,000.00",
    }),
    """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/14 Zelle Payment From Harbor Freightways 10000000001 1,000.00
01/15 2,000.00
*end*deposits and additions
*start*deposits and additions
(continued)
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
Orig CO Name:Northwind Freight Orig ID:D100000001 Desc Date:260115 CO
Entry Descr:Claim Pmt Sec:CCD Trace#:100000000000005 Trn: 0000000005Tc
Total Deposits and Additions $3,000.00
*end*deposits and additions
""",
)


def test_f11_a_row_split_by_a_page_break_keeps_its_amount():
    """The amount cell can land on the last line of one page while the rest of
    the description opens the next page's block. "(continued)" is furniture,
    not a row boundary."""
    stmt = parse_chase_statement(F11)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [1000.0, 2000.0]
    assert reconcile(stmt).ok


def test_f11_negative_a_dateless_row_is_dropped_not_invented():
    """If the description never arrives, the row has nothing to publish. The
    platform drops it — which breaks the ledger identity and withholds the
    document — rather than inventing a description to keep the sum whole."""
    md = _doc(
        _summary(**{
            "Deposits and Additions": "2 3,000.00",
            "Ending Balance": "2 $4,000.00",
        }),
        """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/14 Zelle Payment From Harbor Freightways 10000000001 1,000.00
01/15 2,000.00
Total Deposits and Additions $3,000.00
*end*deposits and additions
""",
    )
    stmt = parse_chase_statement(md)
    assert [t.amount for t in stmt.transactions] == [1000.0]
    assert not reconcile(stmt).ok


def test_negative_a_summary_line_is_never_a_transaction_section():
    """CHECKING SUMMARY prints `Fees 1 -15.00` and `Deposits and Additions 2
    800.00` as whole lines. Those are the bank's totals, not rows, and the
    block scan must not claim the summary block as a detail section."""
    md = _doc(
        _summary(**{
            "Deposits and Additions": "1 500.00",
            "Fees": "1 -15.00",
            "Ending Balance": "2 $1,485.00",
        }),
        """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/02 Deposit 1000000001 500.00
Total Deposits and Additions $500.00
*end*deposits and additions
*start*fees section
FEES
DATE DESCRIPTION AMOUNT
01/31 Monthly Service Fee 15.00
Total Fees $15.00
*end*fees section
""",
    )
    assert _amounts(md) == [500.0, -15.0]
    assert reconcile(parse_chase_statement(md)).ok
