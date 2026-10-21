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

from analysis.money import parse_money
from analysis.rbc import _MONEY_RE, parse_rbc_statement
from analysis.tables import read_grid_rows
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
    "period": "March 2, 2054 to April 1, 2054",
    "start": "March 2, 2054",
    "end": "April 1, 2054",
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
    assert [t.date for t in stmt.transactions] == ["2054-03-02", "2054-03-02"]
    assert amounts(stmt) == [500.0, -200.0]


def test_f9_rows_after_a_new_posting_date_carry_that_date():
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 500.00 1,500.00\n03 Mar Withdrawal item 200.00 1,300.00\n",
        opening="1,000.00", closing="1,300.00",
        credits="500.00", credit_count=1, debits="200.00", debit_count=1,
    ))
    assert stmt is not None
    assert [t.date for t in stmt.transactions] == ["2054-03-02", "2054-03-03"]


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

#: The furniture the French business statement actually prints. The previous
#: version of this fixture invented three wordings — a `Date Description
#: Retraits` header (which is CIBC's, not RBC's) and two `Total des ...`
#: rows that match no document — and the parser was written to them, so
#: `rbc_french` claimed nothing corpus-wide.
FR = """
BANQUE ROYALE DU CANADA
Relevé de compte d'entreprise
Du 3 mars 2054 au 2 avril 2054
Sommaire du compte pour cette période
Solde d'ouverture le 3 mars 2054 1 000,00 $
Total des dépôts et des crédits (1) + 500,00
Total des chèques et des débits (1) - 300,00
Solde de clôture le 2 avril 2054 = 1 200,00 $
Détails des opérations passées au compte
Date Description Chèques et débits ($) Dépôts et crédits ($) Solde ($)
Solde d'ouverture 1 000,00
{body}Solde de clôture 1 200,00
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
    balance_line = "Opening balance on March 2, 2054 $1,000.00"

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


# ---------------------------------------------------------------------------
# RBCCIBC-LAYOUTS card D - the money grammar, hardened against the shapes the
# unclaimed RBC/CIBC families print. Every fixture below fails against
# `cce8ac1`, and none of the shapes occurs in the 160 documents the registry
# already claims.
# ---------------------------------------------------------------------------

def test_d_a_summary_balance_printed_minus_space_symbol_is_negative():
    """`- $2.55` is one figure: the minus is set in the label column.

    The shipped pattern admitted `-$2.55` and `$-2.55` and stopped there, so a
    statement that opens or closes overdrawn published `+2.55` and its summary
    identity balanced against a sign-flipped figure instead of failing.
    """
    doc = statement(
        "02 Mar Deposit item 1,000.00 997.45\n",
        opening="2.55", closing="997.45",
        credits="1,000.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace("Opening balance on March 2, 2054 $2.55",
              "Opening balance on March 2, 2054 - $2.55")
    stmt = parse_rbc_statement(doc)
    assert stmt is not None
    assert stmt.beginning_balance == -2.55


def test_d_a_summary_closing_balance_printed_equals_minus_symbol_is_negative():
    doc = statement(
        "02 Mar Withdrawal item 5.32 -2.55\n",
        opening="2.77", closing="2.55",
        credits="0.00", credit_count=0, debits="5.32", debit_count=1,
    ).replace("Closing balance on April 1, 2054 = $2.55",
              "Closing balance on April 1, 2054 = - $2.55")
    stmt = parse_rbc_statement(doc)
    assert stmt is not None
    assert stmt.ending_balance == -2.55


def test_d_a_bare_minus_between_two_cells_signs_the_balance():
    """`194.82 - 192.33`: the account went overdrawn on that row.

    The Balance column is the only column that prints a sign, so the minus
    belongs to the cell it stands in front of. Reading it as unrelated
    punctuation published a POSITIVE 192.33 balance and broke the chain.
    """
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit item 100.00 102.77\n"
        "03 Mar Withdrawal item 194.82 - 192.33\n",
        opening="2.77", closing="-192.33",
        credits="100.00", credit_count=1, debits="194.82", debit_count=1,
    ))
    assert stmt is not None
    assert balances(stmt) == [102.77, -192.33]
    assert amounts(stmt) == [100.0, -194.82]


def test_d_negative_a_description_ending_in_a_hyphen_does_not_sign_its_amount():
    """The adversary for the rule above, taken from a claimed document.

    `Interac purchase - 0184 B001 LITTLE KABUL - 180.59` prints a merchant
    name that ends with a hyphen and then a WITHDRAWAL. The minus is not
    between two cells — there is no open row awaiting a balance — so it stays
    description and 180.59 stays a debit magnitude.
    """
    stmt = parse_rbc_statement(statement(
        "02 Mar Interac purchase - 0184 B001 LITTLE KABUL - 180.59\n"
        "03 Mar Deposit item 250.00 1,069.41\n",
        opening="1,000.00", closing="1,069.41",
        credits="250.00", credit_count=1, debits="180.59", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-180.59, 250.0]
    assert balances(stmt) == [None, 1069.41]
    assert descriptions(stmt)[0] == "Interac purchase - 0184 B001 LITTLE KABUL -"


def test_d_the_opening_row_prints_its_own_sign():
    doc = statement(
        "02 Mar Deposit item 100.00 97.45\n",
        opening="2.55", closing="97.45",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace("Opening balance on March 2, 2054 $2.55",
              "Opening balance on March 2, 2054 - $2.55"
    ).replace("Opening balance 2.55", "Opening balance - 2.55")
    stmt = parse_rbc_statement(doc)
    assert stmt is not None
    assert stmt.beginning_balance == -2.55
    assert balances(stmt) == [97.45]
    assert amounts(stmt) == [100.0]


def test_d_the_opening_row_line_does_not_swallow_what_follows_it():
    """The opening row prints ONE cell; the rest of the line is the next row.

    This layout family compresses the column header, the opening row and the
    first posting onto one physical line, so consuming the whole line here
    discarded a real transaction.
    """
    rows, opening = read_grid_rows(
        [("Opening balance 1,000.00 Withdrawal item 100.00 900.00", "2054-03-02", True)],
        pattern=_MONEY_RE,
        to_amount=lambda token: parse_money(token) or 0.0,
        opening_label="OPENING BALANCE",
        closing_label="CLOSING BALANCE",
    )
    assert opening == 1000.0
    assert [row["description"] for row in rows] == ["Withdrawal item"]
    assert [row["abs_amount"] for row in rows] == [100.0]
    assert [row["balance"] for row in rows] == [900.0]


def test_d_negative_an_opening_row_alone_on_its_line_still_yields_no_row():
    rows, opening = read_grid_rows(
        [("Opening balance 1,000.00", "2054-03-02", True)],
        pattern=_MONEY_RE,
        to_amount=lambda token: parse_money(token) or 0.0,
        opening_label="OPENING BALANCE",
        closing_label="CLOSING BALANCE",
    )
    assert opening == 1000.0
    assert rows == []


def test_d_a_printed_rate_is_not_a_money_cell():
    """`2.25/1,000` is a price per thousand dollars deposited, not a cell."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Deposit note fee self-service 6170.0 AT 2.25/1,000 13.88 986.12\n",
        opening="1,000.00", closing="986.12",
        credits="0.00", credit_count=0, debits="13.88", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-13.88]
    assert balances(stmt) == [986.12]


def test_d_a_foreign_currency_operand_of_an_exchange_rate_is_not_a_money_cell():
    """`450000.00 PKR @.005` is what was sent abroad, not what left the account."""
    stmt = parse_rbc_statement(statement(
        "02 Mar Global money transfer 450000.00 PKR @.005 2,250.00 7,750.00\n",
        opening="10,000.00", closing="7,750.00",
        credits="0.00", credit_count=0, debits="2,250.00", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-2250.0]
    assert balances(stmt) == [7750.0]


def test_d_negative_a_three_letter_reference_after_an_amount_is_still_a_cell():
    """`403.50 SCD 09502` — the guard requires the `@`, not just the code."""
    stmt = parse_rbc_statement(statement(
        "02 Mar ABM withdrawal INTERAC SCD 09502 403.50 9,596.50\n",
        opening="10,000.00", closing="9,596.50",
        credits="0.00", credit_count=0, debits="403.50", debit_count=1,
    ))
    assert stmt is not None
    assert amounts(stmt) == [-403.50]


# ---------------------------------------------------------------------------
# Card B - the English PERSONAL product. Same institution, same three-column
# grid, same opening/closing rows; the product names its furniture differently
# and prints no instance counts beside its totals.
# ---------------------------------------------------------------------------

PERSONAL = """
Your RBC personal banking account statement
Royal Bank of Canada P.O. Box 4047 Terminal A Toronto ON M5W 1L5
From December 19, 2053 to January 20, 2054
Your account number: 00144-0000000
Summary of your account for this period
Your opening balance on December 19, 2053 {opening}
Total deposits into your account + {credits}
Total withdrawals from your account - {debits}
Your closing balance on January 20, 2054 = {closing}
Details of your account activity
Date Description Withdrawals ($) Deposits ($) Balance ($)
Opening Balance {open_row}
{body}Closing Balance {closing}
"""


def personal(body, *, opening, closing, credits, debits, open_row=None):
    return PERSONAL.format(
        opening=opening, closing=closing, credits=credits, debits=debits,
        open_row=open_row if open_row is not None else opening.lstrip("$"),
        body=body,
    )


def test_b_the_personal_product_is_detected_and_parsed():
    """`Details of your account activity` is the personal heading; the
    business product prints `Account Activity Details` over the same grid."""
    stmt = parse_rbc_statement(personal(
        "13 Jan e-Transfer received SENDER 100.00 102.77\n"
        "14 Jan e-Transfer sent PAYEE 15.00 87.77\n",
        opening="$2.77", closing="$87.77", credits="100.00", debits="15.00",
    ))
    assert stmt is not None
    assert stmt.bank == "Royal Bank of Canada"
    assert stmt.period_start == "2053-12-19"
    assert stmt.period_end == "2054-01-20"
    assert amounts(stmt) == [100.0, -15.0]
    assert balances(stmt) == [102.77, 87.77]


def test_b_the_personal_summary_totals_are_read_without_counts():
    """This product prints no instance count beside either total, so the two
    stated counts stay None: a count the document does not print is not a
    stated count, and deriving one from the ledger would invent an oracle."""
    stmt = parse_rbc_statement(personal(
        "13 Jan e-Transfer received SENDER 100.00 102.77\n"
        "14 Jan e-Transfer sent PAYEE 15.00 87.77\n",
        opening="$2.77", closing="$87.77", credits="100.00", debits="15.00",
    ))
    assert stmt is not None
    assert stmt.stated_total_credits == 100.0
    assert stmt.stated_total_debits == 15.0
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None
    assert reconcile(stmt).summary_ok is True


def test_b_a_personal_statement_that_closes_overdrawn_publishes_it_negative():
    """The card-D shape in its own family: six of the twelve documents in this
    layout print an overdrawn balance as `- $2.55`."""
    stmt = parse_rbc_statement(personal(
        "13 Jan e-Transfer sent PAYEE 5.32 - 2.55\n",
        opening="$2.77", closing="- $2.55", credits="0.00", debits="5.32",
    ))
    assert stmt is not None
    assert stmt.beginning_balance == 2.77
    assert stmt.ending_balance == -2.55
    assert balances(stmt) == [-2.55]
    assert amounts(stmt) == [-5.32]


def test_b_a_personal_statement_that_opens_overdrawn_publishes_it_negative():
    stmt = parse_rbc_statement(personal(
        "13 Jan e-Transfer received SENDER 100.00 97.45\n",
        opening="- $2.55", closing="$97.45", credits="100.00", debits="0.00",
        open_row="- 2.55",
    ))
    assert stmt is not None
    assert stmt.beginning_balance == -2.55
    assert amounts(stmt) == [100.0]
    assert balances(stmt) == [97.45]


def test_b_negative_the_personal_heading_alone_does_not_claim_another_issuer():
    """CIBC prints the identical column header over its own grid, so the
    heading is only ever evidence in conjunction with the bank name."""
    from analysis.rbc import detect

    foreign = personal(
        "13 Jan Item 1.00 1.77\n",
        opening="$2.77", closing="$1.77", credits="0.00", debits="1.00",
    ).replace("Royal Bank of Canada", "Some Other Bank")
    assert "Details of your account activity" in foreign
    assert not detect(foreign).claims
    assert parse_rbc_statement(foreign) is None


# ---------------------------------------------------------------------------
# Card C — the French BUSINESS layout, and the registration it resurrects.
# `rbc_french` claimed nothing corpus-wide: its activity marker was CIBC's
# French header, so paired with `BANQUE ROYALE` it matched no document at all
# while nineteen documents of the layout it was written for went unclaimed.
# ---------------------------------------------------------------------------

FR_CHEQUE_PAGES = "No de série: 253 Montant: 127,40 $\n"


def test_c_the_french_business_layout_is_detected_on_its_real_header():
    from analysis.rbc import detect_french

    document = FR.format(body="5 mars Article un 500,00 1 500,00\n"
                              "12 mars Article deux 300,00 1 200,00\n")
    assert detect_french(document).claims
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.bank == "Banque Royale du Canada"
    assert stmt.currency == "CAD"


def test_c_both_french_products_are_detected():
    """RBC issues its French statement under two products, as it does in
    English: the personal one heads its first money column `Retraits`, the
    business one `Chèques et débits`. The marker required only the personal
    wording, so the registration claimed the single pinned personal statement
    and nothing else — the whole business family went unclaimed."""
    from analysis.rbc import detect_french

    business = FR.format(body="5 mars Article un 500,00 1 500,00\n")
    personal = FR.replace(
        "Date Description Chèques et débits ($) Dépôts et crédits ($) Solde ($)",
        "Date Description Retraits ($) Dépôts ($) Solde ($)",
    ).format(body="5 mars Article un 500,00 1 500,00\n")
    assert detect_french(business).claims
    assert detect_french(personal).claims


def test_c_negative_the_personal_header_alone_does_not_reach_a_cibc_statement():
    """`Date Description Retraits` is also CIBC's French header. The
    conjunction with `BANQUE ROYALE` is what separates them."""
    from analysis.rbc import detect_french

    cibc = FR.replace("BANQUE ROYALE DU CANADA", "CIBC").replace(
        "Date Description Chèques et débits ($) Dépôts et crédits ($) Solde ($)",
        "Date Description Retraits ($) Dépôts ($) Solde ($)",
    ).format(body="5 mars Article un 500,00 1 500,00\n")
    assert not detect_french(cibc).claims


def test_c_the_personal_product_prints_no_counts_beside_its_totals():
    personal = FR.replace(
        "Total des dépôts et des crédits (1) + 500,00",
        "Total des dépôts dans votre compte + 500,00",
    ).replace(
        "Total des chèques et des débits (1) - 300,00",
        "Total des retraits de votre compte - 300,00",
    ).format(body="5 mars Article un 500,00 1 500,00\n"
                  "12 mars Article deux 300,00 1 200,00\n")
    stmt = parse_rbc_statement(personal)
    assert stmt is not None
    assert stmt.stated_total_credits == 500.0
    assert stmt.stated_total_debits == 300.0
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_c_the_summary_reads_both_totals_and_both_printed_counts():
    """The two total rows print an instance count in brackets and the French
    path never assigned either. Both totals matched no wording at all, so the
    summary identity had nothing to check and the document shipped anyway."""
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Article un 500,00 1 500,00\n"
             "12 mars Article deux 300,00 1 200,00\n"))
    assert stmt is not None
    assert stmt.beginning_balance == 1000.0
    assert stmt.ending_balance == 1200.0
    assert stmt.stated_total_credits == 500.0
    assert stmt.stated_total_debits == 300.0
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 1
    assert reconcile(stmt).summary_ok is True


def test_c_the_opening_balance_pattern_does_not_absorb_the_printed_year():
    """`... le 23 juillet 2053 801,53 $` opens at 801.53, not 25,801.53: the
    unanchored pattern began the grouped alternative inside the YEAR."""
    document = FR.replace(
        "Solde d'ouverture le 3 mars 2054 1 000,00 $",
        "Solde d'ouverture le 23 juillet 2053 801,53 $",
    ).replace("Solde d'ouverture 1 000,00", "Solde d'ouverture 801,53")
    stmt = parse_rbc_statement(document.format(
        body="5 mars Article un 500,00 1 301,53\n"))
    assert stmt is not None
    assert stmt.beginning_balance == 801.53


def test_c_a_bracket_negative_balance_survives_the_printed_gap():
    """`(1 066,25 )` — the closing bracket is set in its own column. The
    bracket is this layout's ONLY negative marker, so failing to span the gap
    sign-flipped every overdrawn balance in the family."""
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Article un 2 066,25 (1 066,25 )\n"
             "12 mars Article deux 2 266,25 1 200,00\n"))
    assert stmt is not None
    assert balances(stmt) == [-1066.25, 1200.0]
    assert amounts(stmt) == [-2066.25, 2266.25]


def test_c_a_reference_glued_to_a_plus_does_not_swallow_the_amount():
    """`ARCHIVE+8 129,14`: the `8` belongs to the reference, and the grouped
    alternative then read the amount as 8,129.14."""
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Frais ARCHIVE+8 129,14 870,86\n"))
    assert stmt is not None
    assert amounts(stmt) == [-129.14]
    assert balances(stmt) == [870.86]


def test_c_a_cheque_serial_is_read_from_the_statements_own_declaration():
    """`Chèque - 253 127,40` is serial 253 and $127.40, not $253,127.40.

    French thousands are spaced, so nothing inside the row settles it. The
    cheque-image pages the statement appends authorise the rule DOCUMENT-WIDE:
    their presence selects a money pattern that will not begin an amount at
    the number printed straight after `Chèque - `. The pattern does not consult
    which serials were declared — see the note on `_FR_MONEY_SERIAL_RE` for the
    two shapes that misreads, both of which fail closed.
    """
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Chèque - 253 127,40 872,60\n") + FR_CHEQUE_PAGES)
    assert stmt is not None
    assert amounts(stmt) == [-127.40]
    assert balances(stmt) == [872.60]
    assert descriptions(stmt) == ["Chèque - 253"]


def test_c_negative_without_the_declaration_the_row_is_left_whole():
    """A statement that declares no serials keeps the plain pattern: the row
    reads as one grouped number and fails the bank's own totals rather than
    being split on a guess."""
    stmt = parse_rbc_statement(FR.format(
        body="5 mars Chèque - 253 127,40 872,60\n"))
    assert stmt is not None
    assert amounts(stmt) == [-253127.40]


# ---------------------------------------------------------------------------
# Card F1 — the mangled-font guard.
#
# Four archive documents carry a broken character map. Their glyphs are right
# and their codepoints are not, so the text layer prints `ROYAL BANK OF CANADA`
# perfectly and renders seventeen thousand dollars as `17J000-00`. Detection
# fails safe on them today only because the furniture it looks for is corrupted
# too; a gate widened for any other reason would claim them and publish the
# corrupted figures. The guard makes that structurally impossible.
# ---------------------------------------------------------------------------

MANGLED = """
ROYAL BANK OF CANADA P.O. BOX 404( )ER,-./0 / )ORO.)O O. ,12 101
Bu-in0-- A11ount 4t5t060nt
4567589 2(, 2026 to FeA87589 2(, 2026
A11ount nu6C07D 0F6H8 F00-KLK-M
A11ount 4u66578 9o7 t:i- P07iod
)pening bABAnCe 9n DAnEAFG HIJ H0HL M17-I6
49NAB Oep9PiNP & CFeOiNP R.S T 17J000-00
49NAB CheqEeP & OebiNP R6S - LJH68-00
A11ount A1tiPit8 D0t5il-
D)=e De$crip=io& Cheq.e$ A De(i=$ B6C Depo$i=$ A CreDi=$ B6C B)l)&ce B6C
Fpe&i&g ()l)&ce 18:14
0H Yeb +CC9EnN ZAGAbBe ZmN H16L1U1 )N4+1$) 5J000-00
5iPC ZAGmenN Z+Y-Y$(2 Y22S H-00 5J013-74
59nNhBG fee L-00 5J007-74
Clo$i&g ()l)&ce 10,767.74
"""


def test_f1_a_broken_character_map_is_refused_however_intact_the_bank_name():
    """The bank name reads perfectly and the money does not. Publishing this
    document's figures would be worse than not reading it at all."""
    from analysis.tables import glyph_damaged

    assert "ROYAL BANK OF CANADA" in MANGLED
    assert glyph_damaged(MANGLED)


def test_f1_the_damaged_document_is_excluded_by_every_registration_here():
    from analysis.cibc import detect_en
    from analysis.rbc import detect, detect_french

    for detector in (detect, detect_french):
        detection = detector(MANGLED)
        assert not detection.claims
        assert detection.excluded_by == "glyph_damage"
    assert not detect_en(MANGLED).claims
    assert parse_rbc_statement(MANGLED) is None


def test_f1_the_guard_survives_a_gate_widened_to_the_intact_bank_name():
    """The point of an EXCLUDING marker rather than a parse-time refusal: it
    returns 0.0 before any other marker is scored, so a future marker that
    happened to match this text still cannot produce a claim."""
    from analysis.parser_registry import required, score_markers
    from analysis.tables import glyph_damaged
    from analysis.rbc import DETECTION_MARKERS

    widened = DETECTION_MARKERS + (required("anything", lambda t: True),)
    assert score_markers(widened, MANGLED.upper()).claims is False
    assert glyph_damaged(MANGLED.upper())


def test_f1_negative_a_healthy_statement_is_not_refused():
    from analysis.tables import glyph_damaged

    healthy = statement(
        "02 Mar Deposit item 1,000.00 2,000.00\n",
        opening="1,000.00", closing="2,000.00",
        credits="1,000.00", credit_count=1, debits="0.00", debit_count=0,
    )
    assert not glyph_damaged(healthy)
    assert parse_rbc_statement(healthy) is not None


def test_f1_negative_reference_codes_and_hashes_are_not_damage():
    """Real statements are full of letter-digit tokens — `E-TRANSFER105685026661`,
    `MRCH29473680015`, a 32-character autodeposit hash. None of them is a word
    with digits substituted INTO it, and the surveyed populations top out at
    0.036 against a 0.15 limit."""
    from analysis.tables import glyph_damaged

    noisy = statement(
        "02 Mar e-Transfer - Autodeposit ALI 3fa83159d62b456a96179bd988551150 100.00 1,100.00\n"
        "03 Mar Misc Payment MRCH29473680015 29473680015 50.00 1,050.00\n"
        "04 Mar E-TRANSFER105685026661 recipient 4506*********163 50.00 1,000.00\n",
        opening="1,000.00", closing="1,000.00",
        credits="100.00", credit_count=1, debits="100.00", debit_count=2,
    )
    assert not glyph_damaged(noisy)


def test_f1_negative_a_short_document_is_not_judged_on_a_noisy_ratio():
    from analysis.tables import glyph_damaged

    assert not glyph_damaged("A11ount 4t5t060nt")


# ---------------------------------------------------------------------------
# Card CUR — the printed denomination (W3 #CURRENCY).
#
# RBC issues this layout in both currencies and says so in two places when it
# says so at all: the `U.S. Funds` line in the header block, and the account's
# product name in the mailing header (`CAD CHEQUING ACCOUNT`, `US BUSINESS
# ACCOUNT`). 151 of the 169 RBC documents in the archive print NEITHER, and
# the platform's answer for those is the schema default, unchanged and named —
# a Canadian address is geography, not a printed fact about the account.
# ---------------------------------------------------------------------------

def test_cur_the_us_funds_line_publishes_usd_from_the_document():
    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace("Business Account Statement", "Business Account Statement\nU.S. Funds")
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_the_us_funds_line_is_read_when_set_on_the_title_line():
    """Some issues of the same header set both words on one line."""
    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace("Business Account Statement", "Business Account Statement U.S. Funds")
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_the_cad_product_line_publishes_cad():
    """The mover class. Six archive documents print `CAD CHEQUING ACCOUNT` in
    the mailing header and were published as USD by the schema default."""
    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace(
        "Account number: 00000 100-000-0",
        "RBBDA30000_0000000 E D 00000 00000 EXAMPLE INC. CAD CHEQUING ACCOUNT 1 EXAMPLE ST\n"
        "Account number: 00000 100-000-0",
    )
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "CAD"


def test_cur_the_us_product_line_publishes_usd():
    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace(
        "Account number: 00000 100-000-0",
        "RBBDA30000_0000000 E D 00000 00000 EXAMPLE INC. US BUSINESS ACCOUNT 1 EXAMPLE ST\n"
        "Account number: 00000 100-000-0",
    )
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_a_document_stating_no_denomination_keeps_the_default():
    """The ordinary case, and deliberately pinned: absence of evidence is not
    evidence, so nothing here infers CAD from `ROYAL BANK OF CANADA`."""
    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    )
    assert "U.S. Funds" not in document
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_negative_a_funds_transfer_posting_is_not_a_denomination():
    """`Funds transfer credit TT KM CAPITAL C` is a posting on the pinned RBC
    statements. An unanchored search for the words would read a transfer TYPE
    as the account's currency — and would have moved a pinned document."""
    document = statement(
        "02 Mar Funds transfer credit TT KM CAPITAL C 100.00 1,100.00\n"
        "03 Mar U.S. Funds wire fee 0.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=1,
    )
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"  # the schema default, NOT a read of the ledger
    from analysis.rbc import _printed_currency

    assert _printed_currency(document) is None


def test_cur_negative_an_e_transfer_reference_code_is_not_a_currency():
    """This layout prints `CAxxxxxx` reference codes in its ledger. A bare
    token scan would publish a customer's reference as the denomination."""
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar e-Transfer received PHILIPPESEGUIN CADWKEFS 100.00 1,100.00\n"
        "03 Mar e-Transfer received EXAMPLE CO CAD 50.00 1,150.00\n",
        opening="1,000.00", closing="1,150.00",
        credits="150.00", credit_count=2, debits="0.00", debit_count=0,
    )
    assert _printed_currency(document) is None
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_negative_a_self_contradicting_document_keeps_the_default():
    """Two denominations printed is not one denomination stated."""
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    ).replace(
        "Business Account Statement", "Business Account Statement\nU.S. Funds",
    ).replace(
        "Account number: 00000 100-000-0",
        "RBBDA30000_0000000 E D 00000 00000 EXAMPLE INC. CAD CHEQUING ACCOUNT 1 EXAMPLE ST\n"
        "Account number: 00000 100-000-0",
    )
    assert _printed_currency(document) is None
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_the_french_reader_is_untouched_by_the_english_evidence():
    """`_printed_currency` runs on the English branch only; the French reader
    keeps its own CAD, and `CDN TIRE` — a merchant on the pinned French
    statement — must not read as a denomination anywhere."""
    from analysis.rbc import _printed_currency

    assert _printed_currency("Versement par Banque en direct - 3841 CDN TIRE MC 1 350,00") is None


def _mailing(document: str, product: str) -> str:
    """Put `product` in the mailing header, where RBC prints it."""
    return document.replace(
        "Account number: 00000 100-000-0",
        f"RBBDA30000_0000000 E D 00000 00000 EXAMPLE INC. {product} 1 EXAMPLE ST\n"
        "Account number: 00000 100-000-0",
    )


def test_cur_the_product_read_is_anchored_to_the_mailing_header():
    """D-1. The product name counts as evidence in the mailing header and
    nowhere else. Measured over the archive: twelve product-spelling hits,
    twelve of them on the `RBBDA…` line, none outside it — so the anchor costs
    nothing today and is what keeps the ledger out of the read."""
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    )
    assert _printed_currency(_mailing(document, "CAD CHEQUING ACCOUNT")) == "CAD"
    unanchored = document.replace(
        "Account number: 00000 100-000-0",
        "EXAMPLE INC. CAD CHEQUING ACCOUNT 1 EXAMPLE ST\nAccount number: 00000 100-000-0",
    )
    assert _printed_currency(unanchored) is None


def test_cur_negative_a_posting_naming_an_account_cannot_counterfeit_the_product():
    """D-1, the shape the anchor exists for. This family prints 88 postings
    that name an account — `Online Transfer to Deposit Account-5887`,
    `ACCOUNT TRANSFER 06032-1122647` — so a customer who names an account
    `CAD Chequing` puts the product spelling in the LEDGER. A document-wide
    search would read that posting as the statement's denomination."""
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar Online Transfer to CAD Chequing Account-1718 400.00 700.00\n"
        "03 Mar ACCOUNT TRANSFER 06032-1122647 300.00 1,000.00\n",
        opening="1,000.00", closing="1,000.00",
        credits="300.00", credit_count=1, debits="400.00", debit_count=1,
    )
    assert "CAD Chequing Account" in document
    assert _printed_currency(document) is None
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


def test_cur_negative_the_unattested_product_spellings_are_not_admitted():
    """D-2. `CAD CHEQUING ACCOUNT` and `US BUSINESS ACCOUNT` are the two
    spellings the archive prints, 6 documents each. The cross product of
    `(CAD|US)` and `(CHEQUING|BUSINESS)` would also admit two spellings nobody
    has measured, so the table is literal and those two read as nothing."""
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    )
    for attested, expected in (
        ("CAD CHEQUING ACCOUNT", "CAD"),
        ("US BUSINESS ACCOUNT", "USD"),
    ):
        assert _printed_currency(_mailing(document, attested)) == expected
    for unattested in ("CAD BUSINESS ACCOUNT", "US CHEQUING ACCOUNT"):
        assert _printed_currency(_mailing(document, unattested)) is None, unattested


def test_cur_negative_the_source_filename_cannot_set_the_currency():
    """W3 FILENAME-BOUNDARY / F-PROVENANCE, exercised through the production
    seam (`admissible_text`), which is what strips the comment before any
    parser runs.

    The motivation is NOT that the archive's names mislead — measured, all
    twelve currency-named RBC files agree with their page, and no archive
    filename disagrees with what its document prints. That agreement is luck,
    not a guarantee: filenames are operator-supplied metadata and a rename must
    never move a published reading. The adversarial names below carry the exact
    tokens both evidence sites look for.

    Both anchors already make the comment unreachable — it is one line, and it
    can be neither an `RBBDA…` mailing header nor a bare `U.S. Funds` line — so
    this test pins the ANCHORING as much as the boundary: an unanchored rewrite
    of either read fails here even though the boundary still holds."""
    from analysis.parser_registry import admissible_text
    from analysis.rbc import _printed_currency

    document = statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    )
    for name in (
        "CAD CHEQUING ACCOUNT.pdf",
        "US BUSINESS ACCOUNT.pdf",
        "U.S. Funds.pdf",
        "RBBDA30000_1 E D CAD CHEQUING ACCOUNT.pdf",
    ):
        commented = f"<!-- source: {name} | pages: 1 | model: x | empty: 0 -->\n\n" + document
        # the production seam removes it ...
        admissible = admissible_text(commented)
        assert "source:" not in admissible
        assert _printed_currency(admissible) is None, name
        # ... and the anchors mean it was never reachable even unstripped.
        assert _printed_currency(commented) is None, name
        stmt = parse_rbc_statement(commented)
        assert stmt is not None
        assert stmt.currency == "USD"


# ---------------------------------------------------------------------------
# Card CUR-J — the RBC Canada native-currency default (CURRENCY_DOCTRINE §B,
# ratified 2054-08-16) and the evidence hierarchy it belongs to.
#
# The hierarchy, and every test below names which rung it exercises:
#
#   1. explicit statement currency evidence   — `_printed_currency`
#   2. proven account/jurisdiction default    — `_jurisdiction_currency`
#   3. otherwise unknown                      — None; the schema default stands
#
# The rejected framing was `absence of "U.S. Funds" => CAD`. What is
# implemented is a CONJUNCTION of four affirmative proofs the page must print,
# behind two refusals evaluated first. `test_curj_the_conjunction_is_load_
# bearing` is the test that would fail if anyone ever relaxed it back into an
# absence rule, and `test_cur_a_document_stating_no_denomination_keeps_the_
# default` above still pins the other side: a bare `ROYAL BANK OF CANADA` is
# geography, and geography is not a proven account.
# ---------------------------------------------------------------------------

#: The four structural proofs RBC Canada prints, added to the synthetic
#: statement above. Every string here is layout furniture — an issuing centre,
#: a service line, a CPA transit account, a branch of domicile — and none of it
#: names a customer or comes from a corpus document.
_JURISDICTION_FURNITURE = {
    "issuer": "ROYAL BANK OF CANADA P.O. BOX 4047 TERMINAL A TORONTO ON M5W 1L5",
    "service": "How to reach us: call 1-800-769-2520 www.rbcroyalbank.com/business",
    "account": "Account number: 00000 100-000-0",
    "branch": "Royal Bank of Canada 1 MAIN ST, MILTON, ON L9T 7H5",
}


def canadian(document: str, *, without: str | None = None) -> str:
    """The same synthetic statement, printing the RBC Canada jurisdiction proofs.

    `without` removes exactly one evidence class, which is what makes the
    ablation test able to show the conjunction is load-bearing rather than
    decorative.
    """
    parts = {key: "" if key == without else value
             for key, value in _JURISDICTION_FURNITURE.items()}
    document = document.replace(
        "ROYAL BANK OF CANADA\n",
        (parts["issuer"] or "ROYAL BANK OF CANADA") + "\n",
    )
    block = "\n".join(
        line for line in (parts["service"], parts["account"], parts["branch"]) if line
    )
    return document.replace(_JURISDICTION_FURNITURE["account"], block)


def plain_statement() -> str:
    return statement(
        "02 Mar Item 100.00 1,100.00\n",
        opening="1,000.00", closing="1,100.00",
        credits="100.00", credit_count=1, debits="0.00", debit_count=0,
    )


def test_curj_a_proven_rbc_canada_account_with_no_contrary_evidence_publishes_cad():
    """Rung 2, the mover class: 151 archive documents look exactly like this.

    Four affirmative proofs are printed — issuing centre with a Canadian postal
    code, RBC Canada's own service furniture, a CPA transit account number, a
    branch of domicile — and the page names no currency at all.
    """
    from analysis.rbc import _jurisdiction_currency, _printed_currency

    document = canadian(plain_statement())
    assert _printed_currency(document) is None      # the page states nothing
    assert _jurisdiction_currency(document) == "CAD"
    stmt = parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.bank == "Royal Bank of Canada"
    assert stmt.currency == "CAD"


def test_curj_the_conjunction_is_load_bearing_not_decorative():
    """Rung 2, negatively. Remove ANY ONE of the four proofs and the default is
    refused — so nothing here is reasoning from the absence of USD wording."""
    from analysis.rbc import _jurisdiction_currency

    assert _jurisdiction_currency(canadian(plain_statement())) == "CAD"
    for evidence in ("issuer", "service", "account", "branch"):
        ablated = canadian(plain_statement(), without=evidence)
        assert _jurisdiction_currency(ablated) is None, evidence
        stmt = parse_rbc_statement(ablated)
        if stmt is not None:              # `account` also removes the account line
            assert stmt.currency == "USD", evidence


def test_curj_explicit_us_evidence_beats_the_canadian_default():
    """Rung 1 over rung 2, both of the two spellings the archive prints. Twelve
    genuine RBC USD documents are Canadian-issued by every structural proof and
    must stay USD, so the hierarchy's order is the whole of their correctness."""
    from analysis.rbc import _jurisdiction_currency, _statement_currency

    for site in (
        lambda d: d.replace("Business Account Statement",
                            "Business Account Statement\nU.S. Funds"),
        lambda d: _mailing(d, "US BUSINESS ACCOUNT"),
    ):
        document = site(canadian(plain_statement()))
        # every Canadian proof still holds on the page ...
        assert _jurisdiction_currency(
            document.replace("U.S. Funds", "").replace("US BUSINESS ACCOUNT", "")
        ) == "CAD"
        # ... and the explicit evidence still wins.
        assert _statement_currency(document) == ("USD", "printed" if "U.S. Funds" in document else "product")
        stmt = parse_rbc_statement(document)
        assert stmt is not None
        assert stmt.currency == "USD"


#: Every alternation branch of `_US_INSTITUTION_RE`, one printing each. The
#: list is the discriminator's own shape turned into fixtures, so a branch that
#: is ever deleted has a test standing on it.
_US_INSTITUTION_PRINTINGS = (
    "www.rbcbank.com",
    "RBC Bank (Georgia), N.A.",
    "RBC Bank Georgia",
    "RBC Bank USA",
    "Royal Bank of Canada (USA)",
    "RBC Centura",
    "Member FDIC",
    "ABA 063216608",
    "RTN 063216608",
    "Routing Number: 063216608",
    "Raleigh, NC 27612",
)


def test_curj_an_rbc_us_product_refuses_the_canadian_default():
    """Doctrine §B item 3. There is no RBC U.S. document in the archive — zero
    hits of every U.S. marker across the 178-document RBC name superset — so
    this is proven on synthetic printings, and that is said plainly.

    TWO fixtures, because only the second one holds the discriminator to
    account. A wholly U.S. statement fails all four Canadian proofs as well, so
    it would still be refused by a build with the U.S. gate deleted outright —
    it proves the answer, not the mechanism. The second fixture prints all four
    Canadian proofs AND a U.S. marker, so the ONLY thing refusing it is the
    discriminator, and deleting the discriminator turns this test red.
    """
    from analysis.rbc import (
        _J_ACCOUNT_RE, _J_BRANCH_RE, _J_ISSUER_RE, _J_SERVICE_RE,
        _US_INSTITUTION_RE, _jurisdiction_currency,
    )

    # (a) a wholly U.S. statement: refused, and it fails every Canadian proof
    # independently rather than only on the U.S. gate.
    us_document = plain_statement().replace(
        "ROYAL BANK OF CANADA\n",
        "RBC Bank (Georgia), N.A.\n"
        "Member FDIC | www.rbcbank.com | Raleigh, NC 27612\n",
    ).replace(
        "Account number: 00000 100-000-0",
        "Account number: 1234567890\nRouting Number: 063216608",
    )
    assert _jurisdiction_currency(us_document) is None
    for proof in (_J_ISSUER_RE, _J_SERVICE_RE, _J_ACCOUNT_RE, _J_BRANCH_RE):
        assert proof.search(us_document) is None

    # (b) the discriminating fixture: every Canadian proof holds, so the page
    # is one U.S. token away from being a mover. Each token must refuse it.
    control = canadian(plain_statement())
    assert _jurisdiction_currency(control) == "CAD"
    for proof in (_J_ISSUER_RE, _J_SERVICE_RE, _J_ACCOUNT_RE, _J_BRANCH_RE):
        assert proof.search(control) is not None
    for token in _US_INSTITUTION_PRINTINGS:
        swept = control.replace(
            "Account Summary for this Period",
            f"{token}\nAccount Summary for this Period",
        )
        # the Canadian half is untouched — only the U.S. gate can refuse this
        for proof in (_J_ISSUER_RE, _J_SERVICE_RE, _J_ACCOUNT_RE, _J_BRANCH_RE):
            assert proof.search(swept) is not None, (token, proof.pattern[:40])
        assert _US_INSTITUTION_RE.search(swept) is not None, token
        assert _jurisdiction_currency(swept) is None, token
        stmt = parse_rbc_statement(swept)
        assert stmt is not None and stmt.currency == "USD", token


def test_curj_hostile_and_mixed_evidence_fails_closed():
    """Doctrine §B item 4. A genuine Canadian page with ONE foreign token
    grafted on refuses the default rather than being swept in on its Canadian
    half — which is why the U.S. gate is evaluated BEFORE any Canadian marker."""
    from analysis.rbc import _jurisdiction_currency, _statement_currency

    control = canadian(plain_statement())
    assert _jurisdiction_currency(control) == "CAD"
    for token in (
        "www.rbcbank.com",
        "Member FDIC",
        "RBC Bank (Georgia), N.A.",
        "Routing Number: 063216608",
        "RBC Bank USA",
        "Raleigh, NC 27612",
        "U.S. Funds are held separately",
        "USD",
        "U.S. Dollar",
        "EUR",
    ):
        grafted = control.replace(
            "Account Summary for this Period",
            f"{token}\nAccount Summary for this Period",
        )
        assert _jurisdiction_currency(grafted) is None, token

    # The two-code contradiction: both anchored sites fire, and they disagree.
    # The explicit reader publishes nothing and the default is NOT consulted to
    # break the tie — a default may not resolve an ambiguity.
    contradicting = _mailing(
        control.replace("Business Account Statement",
                        "Business Account Statement\nU.S. Funds"),
        "CAD CHEQUING ACCOUNT",
    )
    assert _statement_currency(contradicting) is None
    stmt = parse_rbc_statement(contradicting)
    assert stmt is not None
    assert stmt.currency == "USD"        # the schema default, nothing published


def test_curj_the_source_filename_and_folder_cannot_move_the_currency():
    """PROOF 8, both counterfeit directions, carried THROUGH `admissible_text`.

    (b) a filename printing every Canadian proof cannot manufacture the default
    on a document whose page proves nothing; (c) a filename printing every U.S.
    marker cannot suppress it on a document whose page proves everything.

    The two directions are closed by DIFFERENT mechanisms, and the difference
    is measured rather than glossed. Direction (c) is live: the U.S. gate is a
    document-wide sweep by design — a page carrying that token anywhere is not
    a Canadian retail account — so the unstripped comment really does suppress
    the default, and `admissible_text` is the only thing that closes it.
    Direction (b) is closed twice over: the seam removes the comment, and the
    two jurisdiction line anchors could never have read it anyway, because a
    filename arrives as one line that neither begins with the bank's name nor
    ends with a postal code. Both are exercised THROUGH the production seam."""
    from analysis.parser_registry import admissible_text
    from analysis.rbc import _jurisdiction_currency

    manufacturing = (
        "ROYAL BANK OF CANADA P.O. BOX 4047 TERMINAL A TORONTO ON M5W 1L5 "
        "Account number: 00000 100-000-0 rbcroyalbank.com "
        "Royal Bank of Canada 1 MAIN ST, MILTON, ON L9T 7H5.pdf"
    )
    suppressing = (
        "RBC Bank (Georgia), N.A. Member FDIC www.rbcbank.com "
        "Routing Number 063216608.pdf"
    )
    bare = plain_statement()
    proven = canadian(plain_statement())

    counterfeit = f"<!-- source: {manufacturing} | pages: 1 | model: x | empty: 0 -->\n\n" + bare
    # The claim is not vacuous: every token an unanchored reading would need is
    # present in the unstripped string, and a document-wide rule would find all
    # four. The anchors are what make it unreachable ...
    for token in ("ROYAL BANK OF CANADA P.O. BOX", "rbcroyalbank.com",
                  "Account number: 00000 100-000-0", "MILTON, ON L9T 7H5"):
        assert token in counterfeit
    assert _jurisdiction_currency(counterfeit) is None
    # ... and the seam removes it before any parser runs regardless.
    assert "source:" not in admissible_text(counterfeit)
    assert _jurisdiction_currency(admissible_text(counterfeit)) is None
    stmt = parse_rbc_statement(counterfeit)
    assert stmt is not None
    assert stmt.currency == "USD"

    smothered = f"<!-- source: {suppressing} | pages: 1 | model: x | empty: 0 -->\n\n" + proven
    assert _jurisdiction_currency(smothered) is None          # unstripped, it works
    assert _jurisdiction_currency(admissible_text(smothered)) == "CAD"
    # Through the PRODUCTION entry point, which is where the seam is applied
    # (`analysis.pipeline.analyze_markdown`, W3 FILENAME-BOUNDARY): the parser
    # is never handed the unstripped string, so the suppression never happens.
    from analysis.pipeline import analyze_markdown

    assert analyze_markdown(
        smothered, parse_mode="deterministic"
    ).statement.currency == "CAD"

    # And the folder half of the same claim: nothing in this rule is reachable
    # from a path at all — `_jurisdiction_currency`'s only argument is text.
    for folder in ("RBC USD/", "RBC French/", "Others/RBC Bank Georgia/"):
        assert _jurisdiction_currency(
            admissible_text(
                f"<!-- source: {folder}statement.pdf | pages: 1 | model: x | empty: 0 -->\n\n"
                + proven
            )
        ) == "CAD", folder


def test_curj_rung_1_is_consulted_before_rung_2_structurally(monkeypatch):
    """The hierarchy's ORDER, pinned independently of today's evidence sets.

    Swapping the two rungs is behaviourally invisible on this archive, and only
    by coincidence: every currency the explicit reader can return except `CAD`
    is also in `_CONTRARY_CURRENCY_RE`, so rung 2 would refuse exactly where
    rung 1 speaks, and on the `CAD CHEQUING ACCOUNT` documents the two rungs
    happen to agree. That coincidence is a property of the data, not of the
    doctrine — "explicit currency evidence always has precedence" has to hold
    for a code the refusal set has never heard of.

    So rung 1 is forced to return one: a page that satisfies all four Canadian
    proofs, whose explicit reader states `EUR`. The published answer must be
    `EUR`. Reverse the rungs and this test fails, because the jurisdiction
    default would answer `CAD` first.
    """
    import analysis.rbc as rbc

    document = canadian(plain_statement())
    assert rbc._jurisdiction_currency(document) == "CAD"      # rung 2 would say CAD
    monkeypatch.setattr(rbc, "_printed_currency_evidence", lambda _md: {"EUR": "printed"})
    assert rbc._statement_currency(document) == ("EUR", "printed")
    stmt = rbc.parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "EUR"

    # and the contradiction case keeps its precedence too: two stated codes
    # stop at rung 1 and publish nothing, rather than falling through to a
    # default that would resolve the ambiguity the document created.
    monkeypatch.setattr(
        rbc, "_printed_currency_evidence", lambda _md: {"EUR": "printed", "JPY": "printed"}
    )
    assert rbc._statement_currency(document) is None
    stmt = rbc.parse_rbc_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"                              # the schema default


def test_curj_the_dollar_symbol_alone_establishes_nothing():
    """`Do not infer currency from the $ symbol alone` (doctrine §A).

    RBC prints `$` on both denominations of this same layout — the twelve
    `U.S. Funds` documents print it exactly as the CAD ones do — so the symbol
    carries no information at all. Measured here in both directions: a page
    full of `$` that proves no jurisdiction publishes the schema default, and
    removing every `$` from a proven Canadian page changes nothing."""
    from analysis.rbc import _jurisdiction_currency, _statement_currency

    dollars = plain_statement()
    assert "$" in dollars
    assert _statement_currency(dollars) is None

    proven = canadian(plain_statement())
    assert _jurisdiction_currency(proven) == "CAD"
    assert _jurisdiction_currency(proven.replace("$", "")) == "CAD"


#: The nine CURRENCY-1 explicit-evidence corrections (batch 5, `9a0d391`),
#: named by `content_sha256`.
#: None of them moves under this card, for two structurally different reasons —
#: which is what the test below proves, one mechanism each.
_CURRENCY_1_CORRECTIONS = {
    # `rbc`, published CAD: the mailing header prints `CAD CHEQUING ACCOUNT`,
    # so rung 1 answers and rung 2 is never consulted.
    "0A482C2BEC8D3D1160BE14E6E9049A4F56C1B3AF7051124DD6E9C9488C5C19E0": ("rbc", "CAD"),
    "4AFA2F2102B981ADD0B38E3DE9A0F1458FE36258E295410963310FAE38185BAE": ("rbc", "CAD"),
    "64E841856FE419CD9B1D30CA8CE8E7552EEADBC9DC579E871B498EC79E6DADEA": ("rbc", "CAD"),
    "6C3E154C69FF0490424CB96600408A216C3DA14020D91C59B0D4F702BCA58E17": ("rbc", "CAD"),
    "839726D7A5BA213676E4400B12CCF57D06825611A74045498FB966AA2C87911E": ("rbc", "CAD"),
    "F93B688A7171B8CC28B2D0C958BC2E7574A1F51C1AC90DC6EA6DA7A9E7B292E0": ("rbc", "CAD"),
    # `td_canada_native`, published USD: this rule is confined to the `rbc`
    # registration, and a TD jurisdiction default would need its own proven
    # evidence base (doctrine §B, final paragraph).
    "0677AD7549FD1BF44DFBE03AF8DB70503661CFE57C57DCE15D5A8F75E93972E3": ("td_canada_native", "USD"),
    "780D0E3D3388076A9BC3B5F9C08E9A2F4F8B1AE7954B7A2CC60D0A5B3858D62D": ("td_canada_native", "USD"),
    "B8A8D69CC7FEA4214E90128C8FD31C5A245653DA08E296407DF028A7FC8B94D7": ("td_canada_native", "USD"),
}


def test_curj_the_nine_currency_1_corrections_are_untouched():
    """The nine batch-5 corrections keep their published currency, and this
    test proves the two MECHANISMS that keep them rather than re-reading the
    archive (the suite is hermetic; the archive proof is the payload
    differential in the cell's report)."""
    from analysis.rbc import _jurisdiction_currency, _printed_currency, _statement_currency

    assert len(_CURRENCY_1_CORRECTIONS) == 9
    assert sum(1 for parser, _ in _CURRENCY_1_CORRECTIONS.values() if parser == "rbc") == 6

    # Mechanism 1 (the six `rbc` corrections). The explicit CAD read answers,
    # and it answers WHETHER OR NOT the jurisdiction proofs are printed — so it
    # is the read that is publishing CAD, not a default that happens to agree.
    stated = _mailing(canadian(plain_statement()), "CAD CHEQUING ACCOUNT")
    assert _printed_currency(stated) == "CAD"
    assert _statement_currency(stated) == ("CAD", "product")
    bare = _mailing(plain_statement(), "CAD CHEQUING ACCOUNT")
    assert _jurisdiction_currency(bare) is None
    assert _statement_currency(bare) == ("CAD", "product")

    # Mechanism 2 (the three `td_canada_native` corrections). Another issuer's
    # statement is not claimed by this parser at all, however Canadian its own
    # furniture is, so no RBC rule can reach it.
    td_document = plain_statement().replace(
        "ROYAL BANK OF CANADA\n", "TD CANADA TRUST\n"
    ).replace(
        "Account number: 00000 100-000-0",
        "Account number: 00000 100-000-0\n"
        "TD Canada Trust 1 MAIN ST, MILTON, ON L9T 7H5",
    )
    assert parse_rbc_statement(td_document) is None


#: The discovery run of record the batch-5 CURRENCY-1 corrections were
#: measured in. Its `rows.csv` is what says WHICH text preparation each
#: document was actually read under, and the test below selects the matching
#: artifact rather than whichever one it finds first: enumerating the D-3 store
#: under a single settings key looks like the run's population but is not it,
#: because a re-read preparation lives under a different key and would feed the
#: replay a text the run never saw.
_RUN_OF_RECORD = "2026-08-16T000943.012887-0000-2e3ea385"


def _checkout_ancestor(*relative: str):
    """The nearest enclosing directory that holds `relative`, or None.

    A git worktree does not carry the gitignored `webapp_data/` or the
    discovery reports; the checkout it was created from does. Searching
    upwards is what lets this test run from either.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


@pytest.mark.corpus
def test_curj_the_nine_currency_1_corrections_publish_their_pinned_currency_from_the_archive():
    """The nine, DEREFERENCED — the executable half of the guard above.

    The unit test beside this one holds the literal list and its shape; it
    cannot notice a document that actually moved, because it never resolves a
    sha to a document. This one does: each of the nine is resolved from the D-3
    OCR artifact store BY DIRECT FILE PATH (the `webapp_data` sqlite index is
    never opened), replayed through the production analysis entry point, and
    held to the currency batch 5 corrected it to.

    Fail CLOSED throughout. A sha with no artifact, an artifact whose model
    does not match what the run of record read, or a document that cannot be
    analysed is a FAILURE — never a skip. A currency proof that quietly passes
    when it could not find the evidence is the defect this test exists to
    remove.
    """
    import csv
    import json
    from pathlib import Path

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown

    store = _checkout_ancestor("webapp_data", "artifacts", "ocr")
    rows_csv = _checkout_ancestor("discovery_reports", _RUN_OF_RECORD, "rows.csv")
    assert store is not None, (
        "the D-3 OCR artifact store was not found in this checkout or any "
        "ancestor; this proof reads the archive and must not be skipped"
    )
    assert rows_csv is not None, (
        f"the run of record {_RUN_OF_RECORD} was not found; its rows.csv is "
        f"what names the text preparation each document was read under"
    )

    wanted = {sha: expected for sha, (_parser, expected) in _CURRENCY_1_CORRECTIONS.items()}
    run_model: dict[str, str] = {}
    with rows_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").upper()
            if sha in wanted:
                run_model[sha] = row.get("source_model") or ""
    missing_rows = sorted(set(wanted) - set(run_model))
    assert not missing_rows, f"not in the run of record's rows: {missing_rows}"

    # Direct file path only. Artifact filenames are cache keys, not shas, so
    # the store is swept once; the cheap byte test keeps that affordable.
    needles = {sha: sha.encode("ascii") for sha in wanted}
    found: dict[str, dict] = {}
    for path in sorted(Path(store).glob("*/*.json")):
        raw = path.read_bytes()
        for sha, needle in needles.items():
            if needle not in raw:
                continue
            payload = json.loads(raw.decode("utf-8"))
            if payload.get("input_sha256") != sha:
                continue
            document = (payload.get("artifact") or {}).get("document") or {}
            if not document.get("pages"):
                continue
            if (document.get("model") or "") != run_model[sha]:
                continue          # a preparation the run of record did not read
            found[sha] = document

    absent = sorted(set(wanted) - set(found))
    assert not absent, (
        f"no artifact matching the run of record's source_model for: {absent}"
    )

    published: dict[str, str] = {}
    for sha, document in found.items():
        pages = list(document["pages"])
        markdown = StatementMarkdown(
            source_file="", model=document.get("model") or "", pages=pages
        ).to_markdown()
        payload = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
        )
        published[sha] = (payload.get("statement") or {}).get("currency")

    assert published == wanted, {
        sha: {"published": published.get(sha), "corrected to": wanted[sha]}
        for sha in sorted(wanted)
        if published.get(sha) != wanted[sha]
    }


def test_curj_the_personal_mailing_header_is_read_on_both_layouts():
    """R4. RBC sets the print-control header as `RBBDA…` on the business layout
    and `RBPDA…_…` on the personal one; 13 archive documents carry the personal
    spelling. Anchoring only the business one left their product line unread,
    so an explicit denomination printed there would have been missed and then
    defaulted. Measured over the RBC superset, widening moves no document's
    read today — it is a precedence repair, which is why it lands in the same
    commit as the default rather than after it."""
    from analysis.rbc import _printed_currency

    document = plain_statement()
    for header in (
        "RBBDA30000_0000000 E D 00000 00000 EXAMPLE INC. {product} 1 EXAMPLE ST",
        "RBPDA30000_5081501_12 E D 00000 00000 EXAMPLE INC. {product} 1 EXAMPLE ST",
    ):
        for product, expected in (("CAD CHEQUING ACCOUNT", "CAD"),
                                  ("US BUSINESS ACCOUNT", "USD")):
            personal = document.replace(
                "Account number: 00000 100-000-0",
                header.format(product=product) + "\nAccount number: 00000 100-000-0",
            )
            assert _printed_currency(personal) == expected, (header, product)


def test_curj_the_named_future_mover_is_not_admitted_by_weakening_the_parser():
    """`BFEB79B26E426C2FDA63DF0C1F422D95F4A8AF95319C03ADCA85D9560B6E58A3` — a
    genuine zero-activity 4-day RBC Canada statement that satisfies all four
    jurisdiction proofs and that NO registration claims, because it prints no
    posting. It would join the packet as a 152nd document the moment any parser
    claims it, and that movement is therefore expected rather than surprising.

    Gustavo's instruction is that parser admission must not be weakened merely
    to include it, so this pins the admission rule: a proven RBC Canada page
    with no rows publishes NOTHING, currency included."""
    from analysis.rbc import _jurisdiction_currency

    empty = canadian(statement(
        "", opening="1,000.00", closing="1,000.00",
        credits="0.00", credit_count=0, debits="0.00", debit_count=0,
    ))
    assert _jurisdiction_currency(empty) == "CAD"   # the page proves Canada ...
    assert parse_rbc_statement(empty) is None       # ... and still publishes nothing
