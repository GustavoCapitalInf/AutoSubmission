"""W3 Track A, cell 3 — the RBC layout families, one fixture per ruling.

RBC's activity table prints THREE money columns:

    Date | Description | Cheques & Debits ($) | Deposits & Credits ($) | Balance ($)

and the native text layer collapses every run of whitespace, so the column a
money cell was printed in is not in the text. A transaction row therefore
carries up to TWO money cells whose meaning cannot be read off the token order
("the amount is the last money token" reads the running balance as the amount),
and the amount's SIGN — which of the two activity columns it stood in — is not
in the text at all.

Both questions are answered from the statement's own printed evidence:

  * amount vs balance — the Balance column is printed last and is never printed
    without an amount beside it, so two money cells with no text between them
    are one row's amount and running balance and a lone cell is an amount;
  * debit vs credit — the printed running balance closes the arithmetic: over
    the rows between two printed balances the signed amounts must reproduce the
    delta, and the deposits column is printed above the withdrawals column
    inside a block, so the credit set is a prefix. Where the chain cannot close,
    the signs are not invented: the rows keep their descriptive reading and the
    document fails the platform's own coverage and ledger checks.

Every fixture below is synthetic. Nothing here names a customer, and no
constant in `analysis/rbc.py` comes from a corpus document.
"""
from __future__ import annotations

import pytest

from analysis.rbc import parse_rbc_statement
from analysis.reconcile import reconcile

HEAD = """
ROYAL BANK OF CANADA
Business Account Statement
{period}
Account number: 00000 100-000-0
Account Summary for this Period
Opening balance on {start} ${opening}
Total deposits & credits ({credit_count}) + {credits}
Total cheques & debits ({debit_count}) - {debits}
Closing balance on {end} = ${closing}
Account Activity Details
Date Description Cheques & Debits ($) Deposits & Credits ($) Balance ($)
Opening balance {opening}
"""

PERIOD = {
    "period": "March 2, 2026 to April 1, 2026",
    "start": "March 2, 2026",
    "end": "April 1, 2026",
}


def statement(body: str, *, opening, closing, credits, credit_count, debits, debit_count):
    return HEAD.format(
        opening=opening, closing=closing,
        credits=credits, credit_count=credit_count,
        debits=debits, debit_count=debit_count, **PERIOD,
    ) + body


def amounts(stmt):
    return [t.amount for t in stmt.transactions]


def descriptions(stmt):
    return [t.description for t in stmt.transactions]


def balances(stmt):
    return [t.running_balance for t in stmt.transactions]


# ---------------------------------------------------------------------------
# F1 - the dual money cell. THE fixture the cell exists for.
# ---------------------------------------------------------------------------

F1_BODY = """02 Mar Deposit item 1,000.00
Withdrawal item 300.00 1,700.00
03 Mar Withdrawal item 2,500.00
Deposit item 100.00 -700.00
"""


def test_f1_a_row_carrying_two_money_cells_reads_amount_then_balance():
    """The last money token on a row is the RUNNING BALANCE, not the amount.

    Rows 2 and 4 each print an amount and a running balance. Reading the last
    token as the amount would book 1,700.00 and -700.00 as transactions — the
    exact misread the Chase row grouper's "the amount is the right-aligned
    cell" rule would have produced here.
    """
    stmt = parse_rbc_statement(statement(
        F1_BODY, opening="1,000.00", closing="-700.00",
        credits="1,100.00", credit_count=2, debits="2,800.00", debit_count=2,
    ))
    assert stmt is not None
    assert amounts(stmt) == [1000.0, -300.0, -2500.0, 100.0]
    assert balances(stmt) == [None, 1700.0, None, -700.0]


def test_f1_the_naive_last_money_token_rule_is_what_this_fixture_refutes():
    """Adversarial: the naive read is arithmetically impossible, and named."""
    stmt = parse_rbc_statement(statement(
        F1_BODY, opening="1,000.00", closing="-700.00",
        credits="1,100.00", credit_count=2, debits="2,800.00", debit_count=2,
    ))
    naive = [1000.0, 1700.0, 2500.0, -700.0]     # last token as the amount
    assert [abs(a) for a in amounts(stmt)] != [abs(a) for a in naive]
    assert reconcile(stmt).ok


def test_f1_a_lone_money_cell_is_an_amount_not_a_balance():
    """RBC never prints a balance without an amount beside it."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 500.00\nWithdrawal item 200.00 1,300.00\n",
        opening="1,000.00", closing="1,300.00",
        credits="500.00", credit_count=1, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -200.0]
    assert balances(stmt) == [None, 1300.0]


def test_f1_a_balance_smaller_than_the_amount_is_still_the_balance():
    """Size is not evidence: the second cell is the balance because of its column."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Withdrawal item 900.00 100.00\n",
        opening="1,000.00", closing="100.00",
        credits="0.00", credit_count=0, debits="900.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-900.0]
    assert balances(stmt) == [100.0]


# ---------------------------------------------------------------------------
# F2 - the sign is the printed balance chain, never the wording
# ---------------------------------------------------------------------------

def test_f2_signs_come_from_the_balance_delta_not_from_the_description():
    """Descriptions carry no direction here; the printed chain still decides."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Item one 400.00\nItem two 150.00\nItem three 50.00 1,200.00\n",
        opening="1,000.00", closing="1,200.00",
        credits="400.00", credit_count=1, debits="200.00", debit_count=2,
    ))
    assert stmt is not None
    assert amounts(stmt) == [400.0, -150.0, -50.0]
    assert [t.direction for t in stmt.transactions] == ["credit", "debit", "debit"]
    assert reconcile(stmt).ok


def test_f2_the_same_rows_take_the_opposite_signs_under_the_opposite_chain():
    """Nothing is memorised: flip the printed balance and the signs follow."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Item one 400.00\nItem two 150.00\nItem three 50.00 400.00\n",
        opening="1,000.00", closing="400.00",
        credits="0.00", credit_count=0, debits="600.00", debit_count=3,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-400.0, -150.0, -50.0]
    assert reconcile(stmt).ok


def test_f2_the_credits_need_not_be_a_prefix_for_the_chain_to_decide():
    """When the printed order is not credits-first the delta still decides:
    only {200.00} reproduces it, whatever column order the block was printed in."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Item one 100.00\nItem two 200.00\nItem three 50.00 1,050.00\n",
        opening="1,000.00", closing="1,050.00",
        credits="200.00", credit_count=1, debits="150.00", debit_count=2,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-100.0, 200.0, -50.0]
    assert reconcile(stmt).ok


def test_f2_equal_amounts_on_both_sides_resolve_to_the_printed_column_order():
    """Two rows of the same amount, one on each side: every candidate publishes
    the identical credit and debit totals, so the choice cannot change a
    financial result. It is made by the printed column order — deposits above
    withdrawals — rather than left to a memorised description vocabulary."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Item one 500.00\nItem two 500.00\nItem three 40.00 960.00\n",
        opening="1,000.00", closing="960.00",
        credits="500.00", credit_count=1, debits="540.00", debit_count=2,
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -500.0, -40.0]
    assert reconcile(stmt).ok


def test_f2_a_segment_the_chain_cannot_close_is_not_invented():
    """Fail closed: an unreachable delta leaves the descriptive reading and the
    document fails the platform's own arithmetic rather than being repaired."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Item one 400.00\nItem two 150.00 1,234.56\n",
        opening="1,000.00", closing="1,234.56",
        credits="400.00", credit_count=1, debits="150.00", debit_count=1,
    ))
    assert stmt is not None
    assert [abs(a) for a in amounts(stmt)] == [400.0, 150.0]
    assert not reconcile(stmt).ok


# ---------------------------------------------------------------------------
# F3 - compressed line: several printed rows share one physical line
# ---------------------------------------------------------------------------

def test_f3_several_rows_on_one_physical_line_are_separated_at_the_money_cells():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 2,000.00 3,000.00 Withdrawal item 500.00 2,500.00\n",
        opening="1,000.00", closing="2,500.00",
        credits="2,000.00", credit_count=1, debits="500.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [2000.0, -500.0]
    assert descriptions(stmt) == ["Deposit item", "Withdrawal item"]
    assert balances(stmt) == [3000.0, 2500.0]


def test_f3_a_balance_opening_a_line_belongs_to_the_previous_row():
    """The row's amount ends one physical line and its balance opens the next."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 2,000.00\n3,000.00 Withdrawal item 500.00 2,500.00\n",
        opening="1,000.00", closing="2,500.00",
        credits="2,000.00", credit_count=1, debits="500.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [2000.0, -500.0]
    assert balances(stmt) == [3000.0, 2500.0]


# ---------------------------------------------------------------------------
# F4 - wrapped description, F5 - vertically centred amount cell
# ---------------------------------------------------------------------------

def test_f4_a_line_with_no_money_cell_continues_the_description():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item reference\ncontinued reference 750.00 1,750.00\n",
        opening="1,000.00", closing="1,750.00",
        credits="750.00", credit_count=1, debits="0.00", debit_count=0,
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["Deposit item reference continued reference"]
    assert amounts(stmt) == [750.0]


def test_f5_an_amount_printed_between_two_description_lines_keeps_both():
    """The amount cell is vertically centred: the description line after it is
    still the same row's description, not the next row's."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item reference\n750.00\ncontinued reference\n"
        "Withdrawal item 250.00 1,500.00\n",
        opening="1,000.00", closing="1,500.00",
        credits="750.00", credit_count=1, debits="250.00", debit_count=1,
    ))
    assert stmt is not None
    assert descriptions(stmt) == [
        "Deposit item reference continued reference",
        "Withdrawal item",
    ]
    assert amounts(stmt) == [750.0, -250.0]


# ---------------------------------------------------------------------------
# F6 - printed rates are not grid cells
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row, expected_description", [
    ("Regular transaction fee 4 Drs @ 2.50 10.00 990.00", "Regular transaction fee 4 Drs @ 2.50"),
    ("Handling fee 2 @ $ 5.00 10.00 990.00", "Handling fee 2 @ $ 5.00"),
    ("Overdraft interest @ RBP+05.00%P.A 10.00 990.00", "Overdraft interest @ RBP+05.00%P.A"),
])
def test_f6_an_at_rate_or_percentage_operand_is_not_a_money_cell(row, expected_description):
    stmt = parse_rbc_statement(statement(
        f"02 Mar {row}\n",
        opening="1,000.00", closing="990.00",
        credits="0.00", credit_count=0, debits="10.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-10.0]
    assert balances(stmt) == [990.0]
    assert descriptions(stmt) == [expected_description]


def test_f6_the_fee_breakdown_that_wraps_onto_its_own_line_keeps_one_row():
    stmt = parse_rbc_statement(statement(
        "02 Mar Regular transaction fee 4 Drs @ 2.50\n2 Crs @ 2.50 15.00 985.00\n",
        opening="1,000.00", closing="985.00",
        credits="0.00", credit_count=0, debits="15.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-15.0]
    assert descriptions(stmt) == ["Regular transaction fee 4 Drs @ 2.50 2 Crs @ 2.50"]


# ---------------------------------------------------------------------------
# F7 - a printed reference number is not a money cell
# ---------------------------------------------------------------------------

def test_f7_a_leading_zero_reference_number_is_not_a_money_cell():
    """A printed price carries no leading zero; `00314.06` is a reference."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Utility payment 00314.06 250.00 750.00\n",
        opening="1,000.00", closing="750.00",
        credits="0.00", credit_count=0, debits="250.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-250.0]
    assert balances(stmt) == [750.0]
    assert descriptions(stmt) == ["Utility payment 00314.06"]


def test_f7_a_single_leading_zero_before_the_decimal_is_still_money():
    stmt = parse_rbc_statement(statement(
        "02 Mar Interest item 0.45 1,000.45\n",
        opening="1,000.00", closing="1,000.45",
        credits="0.45", credit_count=1, debits="0.00", debit_count=0,
    ))
    assert stmt is not None
    assert amounts(stmt) == [0.45]


# ---------------------------------------------------------------------------
# F8 - table furniture
# ---------------------------------------------------------------------------

def test_f8_a_page_number_never_becomes_a_row_and_never_breaks_a_row():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 500.00\n1 of 2\nWithdrawal item 200.00 1,300.00\n",
        opening="1,000.00", closing="1,300.00",
        credits="500.00", credit_count=1, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -200.0]


def test_f8_a_closing_balance_cell_ends_the_table_mid_line():
    stmt = parse_rbc_statement(statement(
        "02 Mar Withdrawal item 200.00 800.00 Closing balance 800.00\n",
        opening="1,000.00", closing="800.00",
        credits="0.00", credit_count=0, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-200.0]
    assert balances(stmt) == [800.0]


# ---------------------------------------------------------------------------
# F9 - the posting date column
# ---------------------------------------------------------------------------

def test_f9_a_repeated_posting_date_on_a_continuation_page_is_one_date():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 500.00\n"
        "--- Page 2 ---\n"
        "Date Description Cheques & Debits ($) Deposits & Credits ($) Balance ($)\n"
        "02 Mar 02 Mar Withdrawal item 200.00 1,300.00\n",
        opening="1,000.00", closing="1,300.00",
        credits="500.00", credit_count=1, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == ["2026-03-02", "2026-03-02"]
    assert amounts(stmt) == [500.0, -200.0]


def test_f9_rows_after_a_new_posting_date_carry_that_date():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 500.00 1,500.00\n03 Mar Withdrawal item 200.00 1,300.00\n",
        opening="1,000.00", closing="1,300.00",
        credits="500.00", credit_count=1, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == ["2026-03-02", "2026-03-03"]


# ---------------------------------------------------------------------------
# Negative fixtures - these constrain the new rules
# ---------------------------------------------------------------------------

def test_negative_a_digit_run_in_a_description_never_opens_a_row():
    stmt = parse_rbc_statement(statement(
        "02 Mar Payment 29473680015 reference 12345 400.00 600.00\n",
        opening="1,000.00", closing="600.00",
        credits="0.00", credit_count=0, debits="400.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-400.0]
    assert descriptions(stmt) == ["Payment 29473680015 reference 12345"]


def test_negative_the_opening_balance_row_is_not_a_transaction():
    stmt = parse_rbc_statement(statement(
        "02 Mar Withdrawal item 200.00 800.00\n",
        opening="1,000.00", closing="800.00",
        credits="0.00", credit_count=0, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 1
    assert stmt.beginning_balance == 1000.0


def test_negative_a_third_adjacent_money_cell_does_not_become_a_second_balance():
    """Two cells make one row. A third with no description between them is not
    a row this reader can name, so it is dropped rather than guessed, and the
    document then fails the bank's own stated totals."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Withdrawal item 200.00 800.00 50.00\n",
        opening="1,000.00", closing="800.00",
        credits="0.00", credit_count=0, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-200.0]
    assert balances(stmt) == [800.0]


# ---------------------------------------------------------------------------
# The French layout is the same grid and gets the same rules
# ---------------------------------------------------------------------------

FR = """
BANQUE ROYALE DU CANADA
Relevé de compte
Du 3 mars 2026 au 2 avril 2026
Solde d'ouverture 1 000,00
Total des dépôts portés à votre compte + 500,00
Total des retraits - 300,00
Solde de clôture de votre compte = 1 200,00
Date Description Retraits ($) Dépôts ($) Solde ($)
Solde d'ouverture 1 000,00
{body}Solde de clôture de votre compte 1 200,00
"""


def test_french_two_money_cells_are_amount_then_balance():
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Article un 500,00 1 500,00\n12 mars Article deux 300,00 1 200,00\n"
    ))
    assert stmt is not None
    assert stmt.bank == "Banque Royale du Canada"
    assert amounts(stmt) == [500.0, -300.0]
    assert balances(stmt) == [1500.0, 1200.0]


def test_french_signs_come_from_the_printed_balance_chain():
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Article un 500,00\n12 mars Article deux 300,00 1 200,00\n"
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -300.0]


def test_french_a_leading_zero_reference_is_not_a_money_cell():
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Article un 500,00 1 500,00\n"
             "12 mars Article deux 00314,06 300,00 1 200,00\n"
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -300.0]
    assert descriptions(stmt)[1] == "Article deux 00314,06"


# ---------------------------------------------------------------------------
# MONEYFIX-1 card R — the summary TOTAL rows admit the currency symbol
#
# `Account Summary for this Period` prints four rows in one grid: the opening
# balance, the two totals, the closing balance. The balance rows admitted
# `$`; the total rows did not. Whether a statement prints the symbol is a
# property of the statement, not of the row, so on a statement that prints it
# the two stated totals AND both stated counts went None — which skips the
# summary identity check entirely and ships the document approved with
# `summary_totals_reliable=True` and no issue raised. (F-MONEYFMT finding 1.)
# ---------------------------------------------------------------------------

#: The grammar the total rows carried BEFORE the fix, quoted verbatim so the
#: fixtures below prove the defect in-process rather than describing it.
PRE_FIX_CREDIT_TOTAL_RE = r"Total deposits & credits \((\d+)\)\s*\+?\s*([\d,]+\.\d{2})"
PRE_FIX_DEBIT_TOTAL_RE = r"Total cheques & debits \((\d+)\)\s*-?\s*([\d,]+\.\d{2})"

DOLLAR_TOTALS = dict(
    opening="1,000.00", closing="1,700.00",
    credits="$1,000.00", credit_count=1, debits="$300.00", debit_count=1,
)
PLAIN_TOTALS = dict(
    opening="1,000.00", closing="1,700.00",
    credits="1,000.00", credit_count=1, debits="300.00", debit_count=1,
)
R_BODY = """02 Mar Deposit item 1,000.00
Withdrawal item 300.00 1,700.00
"""


def test_r_pre_fix_the_total_row_grammar_refused_the_symbol_the_balance_rows_took():
    """The defect, in process: same block, same symbol, opposite readings."""
    import re

    from analysis.rbc import _SUMMARY_MONEY

    credit_line = "Total deposits & credits (1) + $1,000.00"
    debit_line = "Total cheques & debits (1) - $300.00"
    balance_line = "Opening balance on March 2, 2026 $1,000.00"

    # What the block's balance rows have always admitted, on all three lines.
    assert re.search(r"Opening balance on .*?" + _SUMMARY_MONEY, balance_line)
    # What the total rows admitted before the fix: nothing at all.
    assert re.search(PRE_FIX_CREDIT_TOTAL_RE, credit_line) is None
    assert re.search(PRE_FIX_DEBIT_TOTAL_RE, debit_line) is None
    # What they admit now: the balance rows' own pattern, reused.
    assert re.search(
        r"Total deposits & credits \((\d+)\)\s*\+?\s*" + _SUMMARY_MONEY, credit_line
    ).group(2) == "$1,000.00"
    assert re.search(
        r"Total cheques & debits \((\d+)\)\s*-?\s*" + _SUMMARY_MONEY, debit_line
    ).group(2) == "$300.00"


def test_r_a_statement_printing_the_symbol_on_its_totals_reads_identically():
    """The symbol is cosmetic; the two documents are the same statement."""
    with_symbol = parse_rbc_statement(statement(R_BODY, **DOLLAR_TOTALS))
    without = parse_rbc_statement(statement(R_BODY, **PLAIN_TOTALS))
    assert with_symbol is not None and without is not None
    assert with_symbol.model_dump() == without.model_dump()
    assert with_symbol.stated_total_credits == 1000.00
    assert with_symbol.stated_total_debits == 300.00


def test_r_the_stated_counts_survive_with_the_totals():
    """The counts are captured by the same match, so they were lost with it."""
    stmt = parse_rbc_statement(statement(R_BODY, **DOLLAR_TOTALS))
    assert stmt is not None
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 1


def test_r_a_wrong_total_printed_with_a_symbol_is_caught():
    """The point of the fix: the summary oracle is live on these documents.

    Before it, this statement — whose printed credit total contradicts its own
    activity table by 8,999.00 — reconciled with `summary_ok` None and shipped
    approved. The mismatch has to be CAUGHT, not merely parsed.
    """
    stmt = parse_rbc_statement(statement(
        R_BODY, opening="1,000.00", closing="1,700.00",
        credits="$9,999.00", credit_count=1, debits="$300.00", debit_count=1,
    ))
    assert stmt is not None
    report = reconcile(stmt)
    assert report.summary_ok is False
    assert report.issues


def test_r_negative_a_symbol_less_statement_is_untouched():
    """The overwhelming majority of the archive; it must not move at all."""
    stmt = parse_rbc_statement(statement(R_BODY, **PLAIN_TOTALS))
    assert stmt is not None
    assert stmt.stated_total_credits == 1000.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 1
    assert reconcile(stmt).summary_ok is True


@pytest.mark.parametrize("printed", ["- $300.00", "-$300.00", "- 300.00", "-300.00"],
                         ids=["symbol, spaced", "symbol, tight", "plain, spaced", "plain, tight"])
def test_r_negative_the_debit_rows_minus_is_its_direction_cell_not_a_sign(printed):
    """A debit total is a magnitude however tightly the direction is printed.

    The row prints its direction as its own cell (`(1) - 300.00`), so the
    pattern must keep consuming the marker OUTSIDE the figure. Reading it into
    the figure would publish `stated_total_debits = -300.00` and break every
    identity that treats the stated totals as magnitudes.
    """
    doc = statement(R_BODY, **DOLLAR_TOTALS).replace("- $300.00", printed)
    assert printed in doc
    stmt = parse_rbc_statement(doc)
    assert stmt is not None
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_debit_count == 1
