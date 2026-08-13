"""The Scotiabank printed structures, positive and negative (§SCOTIA-REBUILD).

The cell: `analysis/scotia.py` published the balance movement as every row's
amount and discarded the printed money cell, so `reconcile()` was comparing
the parser's arithmetic with itself — `sum_delta == 0.0` and
`continuity_breaks == 0` on all 80 scotiabank documents in the discovery
archive BY CONSTRUCTION. The rebuild makes the printed cell the amount of
record and leaves the balance walk as an independent check.

Every document below is synthetic. No archive bytes, no customer, and no
amount, account number or date copied from a real statement: what is
reproduced is the *shape* Scotiabank prints, including the four shapes that
defeat a naive reading —

* the amount column with its trailing zeros stripped (`25` for $25.00, `34.9`
  for $34.90), which a two-decimals-only tokeniser splits into two numbers;
* an 11-digit merchant reference printed on a continuation line AFTER the
  balance cell, which "the last numeric token is the balance" turns into a
  balance in the tens of billions;
* a `Deposit Interest` daily-yield sheet in the same PDF, one dated row per
  calendar day, which whole-document date splitting turns into postings;
* a period with no activity at all, which is a statement and not a failure —
  but only when the bank itself printed the zeros.

The negatives are not demonstrations of a defect: each constrains a rule this
cell added, and in particular pins that an empty captured ledger is NEVER
equated with a valid statement.
"""
from __future__ import annotations

from analysis.reconcile import reconcile
from analysis.scotia import parse_scotiabank_statement

# The furniture every Scotiabank statement prints, and which detection needs.
FOOTER = (
    "Please examine this statement promptly.\n"
    "Please see the terms and conditions of the applicable Scotiabank "
    "Financial Services Agreement for your account obligations.\n"
    "GST Registration No. R000000000 Registered trademark of "
    "The Bank of Nova Scotia\n"
)


def _statement(summary: str, rows: str, *, extra: str = "") -> str:
    return (
        "1 SAMPLE STREET 00000 SOMEWHERE NS A0A0A0 000-0000\n"
        "NORTHWIND SUPPLY LTD. 1 SAMPLE STREET SOMEWHERE NS A0A0A0 "
        "Statement Of: Account Number: From: To: Business Account "
        "00000 00000 00 Jan 30 2026 Feb 27 2026 Account Summary for this "
        "Period:\n"
        f"{summary}\n"
        "Account Details:\n"
        "Date Description Withdrawals/Debits ($) Deposits/Credits ($) "
        f"Balance ($) {rows}\n"
        "No. of Debits Total Amount - Debits No. of Credits Total Amount "
        "- Credits 2 $100.00 1 $50.00\n"
        f"{extra}"
        f"{FOOTER}"
    )


SUMMARY_2D_1C = (
    "No. of Debits Total Amount - Debits No. of Credits Total Amount "
    "- Credits 2 $100.00 1 $50.00"
)


# ---------------------------------------------------------------------------
# The amount of record
# ---------------------------------------------------------------------------

def test_f1_printed_cell_is_the_amount_not_the_balance_movement():
    """A well-formed ledger: printed amount and balance walk agree."""
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 60.00 940.00 "
        "02/03/2026 MISC PAYMENT SAMPLE PAYER 50.00 990.00 "
        "02/04/2026 SERVICE CHARGE 40.00 950.00",
    ))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-60.00, 50.00, -40.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "credit", "debit"]
    assert [t.running_balance for t in stmt.transactions] == [940.00, 990.00, 950.00]
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 950.00


def test_f2_printed_cell_survives_when_it_disagrees_with_the_walk():
    """The disagreement is published, never resolved toward either side.

    The middle row prints $50.00 but its balance moves by $70.00. The old
    parser published 70.00 and the ledger still "reconciled"; the printed
    cell must ship instead, and the platform's continuity check must SEE the
    contradiction rather than have it arithmetically erased.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 MISC PAYMENT SAMPLE PAYER 50.00 1,070.00 "
        "02/03/2026 SERVICE CHARGE 30.00 1,040.00",
    ))
    assert stmt is not None
    assert stmt.transactions[0].amount == 50.00
    assert stmt.transactions[0].running_balance == 1070.00

    result = reconcile(stmt)
    assert result.continuity_breaks >= 1
    assert result.sum_delta != 0.0
    assert not result.ok


def test_f3_trailing_zeros_are_stripped_from_the_amount_column():
    """`25` is $25.00, `2,500` is $2,500.00 and `34.9` is $34.90.

    `parse_money` accepts two or three decimals, so a one-decimal cell reads
    as two separate numbers unless the printed form is padded first. Left
    unpadded, `34.9` becomes the tokens `34` and `9` and the row's amount
    silently becomes $9.00.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 TRANSFER FROM 00000 00000 00 12345678 MB-TRANSFER 25 1,025.00 "
        "02/03/2026 TRANSFER FROM 00000 00000 00 12345679 MB-TRANSFER 2,500 3,525.00 "
        "02/04/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 34.9 3,490.10",
    ))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [25.00, 2500.00, -34.90]
    assert reconcile(stmt).continuity_breaks == 0


def test_f4_overdraft_balance_prints_a_trailing_minus():
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 100.00 "
        "02/02/2026 BUSINESS PAD SAMPLE CREDITOR 150.00 50.00- "
        "02/03/2026 OVERDRAWN HANDLING CHGS 5.00 55.00-",
    ))
    assert stmt is not None
    assert [t.running_balance for t in stmt.transactions] == [-50.00, -55.00]
    assert [t.amount for t in stmt.transactions] == [-150.00, -5.00]
    assert reconcile(stmt).continuity_breaks == 0


# ---------------------------------------------------------------------------
# A reference number is not a balance
# ---------------------------------------------------------------------------

def test_f5_merchant_reference_after_the_balance_is_not_a_balance():
    """The continuation line prints the merchant reference AFTER the cells.

    Reading "the last numeric token" as the balance made an 11-digit
    reference a balance in the tens of billions, and every amount on the
    document was then back-solved from it.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 780.37 "
        "02/02/2026 MISC PAYMENT 94.90 685.47 29473680015 "
        "MRCH SAMPLE PROCESSOR(K) "
        "02/03/2026 MISC PAYMENT 337.60 1,023.07 29473680015 "
        "MRCH SAMPLE PROCESSOR(K)",
    ))
    assert stmt is not None
    assert [t.running_balance for t in stmt.transactions] == [685.47, 1023.07]
    assert [t.amount for t in stmt.transactions] == [-94.90, 337.60]
    assert all(abs(t.amount) < 1_000 for t in stmt.transactions)
    assert reconcile(stmt).continuity_breaks == 0


def test_f6_account_number_fragments_are_not_amounts():
    """`TRANSFER FROM 00000 00000 00 12345678` is routing, not money."""
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 500.00 "
        "02/02/2026 TRANSFER FROM 00000 00000 00 12345678 MB-TRANSFER 60.00 560.00",
    ))
    assert stmt is not None
    assert stmt.transactions[0].amount == 60.00
    assert stmt.transactions[0].description == (
        "TRANSFER FROM 00000 00000 00 12345678 MB-TRANSFER"
    )


# ---------------------------------------------------------------------------
# Section discipline
# ---------------------------------------------------------------------------

DEPOSIT_INTEREST = (
    "Statement Of: Account Number: From: To: Deposit Interest "
    "00000 00000 00 Jan 30 2026 Feb 27 2026 Account Information Currency: CAD\n"
    "Date Closing Balance ($) Yield/Rate Calculated Interest ($) "
    "02/03/2026 940.00 0.000 CRITERIA NOT MET "
    "02/04/2026 940.00 1.488 0.41 "
    "02/05/2026 990.00 1.488 0.41\n"
)


def test_f7_deposit_interest_daily_yield_rows_are_not_postings():
    """The daily-yield sheet declares a different grid and prints no postings.

    Its rows are dated and carry money, so splitting the whole document on
    dates fabricated one posting per calendar day on a statement whose own
    summary stated three.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 60.00 940.00 "
        "02/03/2026 MISC PAYMENT SAMPLE PAYER 50.00 990.00",
        extra=DEPOSIT_INTEREST,
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert [t.date for t in stmt.transactions] == ["2026-02-02", "2026-02-03"]
    assert all("CRITERIA" not in t.description for t in stmt.transactions)


def test_f8_service_charge_sheet_contributes_no_postings():
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 60.00 940.00",
        extra=(
            "Statement Of: Account Number: From: To: Service Charge "
            "00000 00000 00 Jan 30 2026 Feb 27 2026\n"
            "Item Volume Rate Charge ($) Monthly Fee 25 20.00 "
            "Total Service Charges $20.00\n"
        ),
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 1


# ---------------------------------------------------------------------------
# Zero activity — admissible only on the bank's own evidence
# ---------------------------------------------------------------------------

ZERO_SUMMARY = (
    "No. of Debits Total Amount - Debits No. of Credits Total Amount "
    "- Credits 0 $0.00 0 $0.00"
)


def _zero_statement(summary: str, rows: str) -> str:
    return (
        "1 SAMPLE STREET 00000 SOMEWHERE NS A0A0A0 000-0000\n"
        "NORTHWIND SUPPLY LTD. 1 SAMPLE STREET SOMEWHERE NS A0A0A0 "
        "Statement Of: Account Number: From: To: Business Account "
        "00000 00000 00 Jan 30 2026 Feb 27 2026 Account Summary for this "
        "Period:\n"
        f"{summary}\n"
        "Account Details:\n"
        "Date Description Withdrawals/Debits ($) Deposits/Credits ($) "
        f"Balance ($) {rows}\n"
        f"{FOOTER}"
    )


def test_f9_printed_zero_activity_period_is_a_statement():
    """Zero instances AND zero totals in both directions, plus an opening."""
    stmt = parse_scotiabank_statement(
        _zero_statement(ZERO_SUMMARY, "01/30/2026 BALANCE FORWARD 0.00")
    )
    assert stmt is not None
    assert stmt.transactions == []
    assert stmt.stated_debit_count == 0
    assert stmt.stated_credit_count == 0
    assert stmt.beginning_balance == 0.00
    assert stmt.ending_balance == 0.00


def test_f10_zero_activity_admits_a_non_zero_carried_balance():
    stmt = parse_scotiabank_statement(
        _zero_statement(ZERO_SUMMARY, "01/30/2026 BALANCE FORWARD 1,234.56")
    )
    assert stmt is not None
    assert stmt.beginning_balance == 1234.56
    assert stmt.ending_balance == 1234.56


def test_f11_empty_ledger_refuses_when_the_bank_stated_activity():
    """The negative half of the rule: an unread ledger is not zero activity.

    The bank states two debits and one credit, but no detail row was
    captured. Publishing an empty statement here would silently assert that
    nothing happened.
    """
    assert parse_scotiabank_statement(
        _zero_statement(SUMMARY_2D_1C, "01/30/2026 BALANCE FORWARD 1,000.00")
    ) is None


def test_f12_empty_ledger_refuses_when_counts_are_zero_but_totals_are_not():
    assert parse_scotiabank_statement(_zero_statement(
        "No. of Debits Total Amount - Debits No. of Credits Total Amount "
        "- Credits 0 $100.00 0 $0.00",
        "01/30/2026 BALANCE FORWARD 1,000.00",
    )) is None


def test_f13_empty_ledger_refuses_without_a_printed_summary():
    assert parse_scotiabank_statement(_zero_statement(
        "Account activity for this period",
        "01/30/2026 BALANCE FORWARD 1,000.00",
    )) is None


def test_f14_empty_ledger_refuses_without_an_opening_balance():
    assert parse_scotiabank_statement(
        _zero_statement(ZERO_SUMMARY, "01/30/2026 OPENING ENTRY")
    ) is None


# ---------------------------------------------------------------------------
# Detection and the stated-count surface
# ---------------------------------------------------------------------------

def test_f15_declines_a_document_that_is_not_scotiabank():
    assert parse_scotiabank_statement(
        "SOME OTHER BANK Account Details 01/30/2026 BALANCE FORWARD 10.00"
    ) is None


def test_f16_stated_counts_come_from_the_account_level_grid():
    """The per-page footers repeat the labels for one page only.

    `count_semantics` records scotiabank as comparable in both directions on
    the strength of these being whole-period figures, so the account-level
    grid printed above `Account Details` must win.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 60.00 940.00 "
        "02/03/2026 MISC PAYMENT SAMPLE PAYER 50.00 990.00 "
        "02/04/2026 SERVICE CHARGE 40.00 950.00",
    ))
    assert stmt is not None
    assert stmt.stated_debit_count == 2
    assert stmt.stated_credit_count == 1
    assert stmt.stated_total_debits == 100.00
    assert stmt.stated_total_credits == 50.00
    assert sum(1 for t in stmt.transactions if t.direction == "debit") == 2
    assert sum(1 for t in stmt.transactions if t.direction == "credit") == 1


def test_f17_a_row_whose_amount_cell_is_missing_is_not_invented():
    """Dropping the row costs the ledger its reconciliation: fail closed.

    Publishing a back-solved amount instead would restore the very identity
    this cell removed. The dropped row also leaves the walk stale, so the
    surviving row's DIRECTION is derived from a balance that no longer
    follows its predecessor — the printed magnitude is still $50.00, and the
    incoherence is what `reconcile` is there to catch.
    """
    stmt = parse_scotiabank_statement(_statement(
        SUMMARY_2D_1C,
        "01/30/2026 BALANCE FORWARD 1,000.00 "
        "02/02/2026 DEBIT MEMO 940.00 12345678 INTERAC E-TRANSFER "
        "02/03/2026 MISC PAYMENT SAMPLE PAYER 50.00 990.00",
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 1
    assert abs(stmt.transactions[0].amount) == 50.00
    assert stmt.transactions[0].running_balance == 990.00
    assert not reconcile(stmt).ok
