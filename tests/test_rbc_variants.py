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

#: The furniture the French business statement actually prints. The previous
#: version of this fixture invented three wordings — a `Date Description
#: Retraits` header (which is CIBC's, not RBC's) and two `Total des ...`
#: rows that match no document — and the parser was written to them, so
#: `rbc_french` claimed nothing corpus-wide. See W3_TRACKA_LOG §RBCCIBC card C.
FR = """
BANQUE ROYALE DU CANADA
Relevé de compte d'entreprise
Du 3 mars 2026 au 2 avril 2026
Sommaire du compte pour cette période
Solde d'ouverture le 3 mars 2026 1 000,00 $
Total des dépôts et des crédits (1) + 500,00
Total des chèques et des débits (1) - 300,00
Solde de clôture le 2 avril 2026 = 1 200,00 $
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


# ---------------------------------------------------------------------------
# RBCCIBC-LAYOUTS card D - the money grammar, hardened against the shapes the
# unclaimed RBC/CIBC families print. Every fixture below fails against
# `cce8ac1`, and none of the shapes occurs in the 160 documents the registry
# already claims (the census and the byte-identity sweep are in
# W3_TRACKA_LOG.md §RBCCIBC).
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
    ).replace("Opening balance on March 2, 2026 $2.55",
              "Opening balance on March 2, 2026 - $2.55")
    stmt = parse_rbc_statement(doc)
    assert stmt is not None
    assert stmt.beginning_balance == -2.55


def test_d_a_summary_closing_balance_printed_equals_minus_symbol_is_negative():
    doc = statement(
        "02 Mar Withdrawal item 5.32 -2.55\n",
        opening="2.77", closing="2.55",
        credits="0.00", credit_count=0, debits="5.32", debit_count=1,
    ).replace("Closing balance on April 1, 2026 = $2.55",
              "Closing balance on April 1, 2026 = - $2.55")
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
    ).replace("Opening balance on March 2, 2026 $2.55",
              "Opening balance on March 2, 2026 - $2.55"
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
        [("Opening balance 1,000.00 Withdrawal item 100.00 900.00", "2026-03-02", True)],
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
        [("Opening balance 1,000.00", "2026-03-02", True)],
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
From December 19, 2025 to January 20, 2026
Your account number: 00144-0000000
Summary of your account for this period
Your opening balance on December 19, 2025 {opening}
Total deposits into your account + {credits}
Total withdrawals from your account - {debits}
Your closing balance on January 20, 2026 = {closing}
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
    assert stmt.period_start == "2025-12-19"
    assert stmt.period_end == "2026-01-20"
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
    """`... le 23 juillet 2025 801,53 $` opens at 801.53, not 25,801.53: the
    unanchored pattern began the grouped alternative inside the YEAR."""
    document = FR.replace(
        "Solde d'ouverture le 3 mars 2026 1 000,00 $",
        "Solde d'ouverture le 23 juillet 2025 801,53 $",
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
