"""U.S. Bank native-layout families (W3 Track A, cell `us_bank x summary_identity`).

Every document below is synthetic and built from the PRINTED GRID: the Account
Summary's `<category> <# items> <amount>` lines, the detail sections they index,
and the column headers U.S. Bank prints inside them. No fixture carries a real
customer, account, amount or date, and no rule under test is keyed on one.

The cell's root cause was a closed vocabulary. The parser knew three summary
categories and three detail sections; U.S. Bank prints six, and whichever a
statement has activity in are exactly the ones it itemizes. Every category
outside the three was dropped from the stated totals AND from the ledger at the
same time, so the bank's own summary identity failed on OUR reading of it while
the ledger still agreed with the (incomplete) totals we had assembled — which is
why all 20 documents diagnosed as `summary_identity` rather than as a coverage
loss. See `docs/moneythumb-replacement/W3_TRACKA_LOG.md` section TRIO.

Every fixture prints BOTH categories the pre-change parser required
(`Other Deposits` and `Other Withdrawals`), so each one is a document the old
reader could also read and the fails-before/passes-after replay in the log is a
real contrast rather than an artefact of a minimal fixture.
"""
from __future__ import annotations

import pytest

from analysis.us_bank import parse_us_bank_statement

PERIOD = "Statement Period:\nMar 2, 2026\nthrough Mar 31, 2026\n"
DESCRIBED_HEADER = "Date Description of Transaction Ref Number Amount"
NUMBERED_HEADER = "Number Date Ref Number Amount"
CHECK_HEADER = "Check Date Ref Number Amount Check Date Ref Number Amount"

#: The two categories every fixture prints, so that the pre-change reader — which
#: required exactly these two — also produces a statement for it. U.S. Bank
#: prints its categories deposits-first and its sections in the same order, so a
#: family under test sits BETWEEN them (or after them, for `Checks Paid`, which
#: the bank prints last).
ANCHOR_CREDIT_CATEGORY = "Other Deposits 1 500.00"
ANCHOR_DEBIT_CATEGORY = "Other Withdrawals 1 80.00-"
ANCHOR_SECTIONS = (
    "Other Deposits\n"
    f"{DESCRIBED_HEADER}\n"
    "Mar 3 Electronic Deposit\n"
    "From A COUNTERPARTY\n"
    "$ 500.00\n"
    "REF=000000000000000N00\n"
    "Total Other Deposits $ 500.00\n"
)
ANCHOR_WITHDRAWAL_SECTION = (
    "Other Withdrawals\n"
    f"{DESCRIBED_HEADER}\n"
    "Mar 6 Electronic Withdrawal\n"
    "To A COUNTERPARTY\n"
    "$ 80.00-\n"
    "Total Other Withdrawals $ 80.00-\n"
)
#: What the anchors alone contribute to `amounts()`, in printed order.
ANCHOR_AMOUNTS = [500.00, -80.00]


def document(*, summary: str, opening: str = "1,000.00", closing: str,
             sections: str, days: str = "31") -> str:
    """A U.S. Bank statement with the printed blocks the parser reads."""
    return (
        "Business Statement\n"
        f"{PERIOD}"
        "U.S. BANK SILVER - BUSINESS CHECKING\n"
        "U.S. Bank National Association\n"
        "Account Number 1-234-5678-9012\n"
        "Account Summary\n"
        "# Items\n"
        f"Number of Days in Statement Period {days}\n"
        f"Beginning Balance on Mar 2 $ {opening} {summary}\n"
        f"Ending Balance on  Mar 31, 2026 $ {closing}\n"
        f"{sections}"
    )


def anchored(*, extra_categories: str = "", extra_sections: str = "",
             closing: str, last: bool = False) -> str:
    """A statement carrying both anchor categories plus the family under test.

    `last=True` places the family after the anchors, which is where U.S. Bank
    prints `Checks Paid`.
    """
    if last:
        summary = f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY} {extra_categories}"
        body = ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION + extra_sections
    else:
        summary = f"{ANCHOR_CREDIT_CATEGORY} {extra_categories} {ANCHOR_DEBIT_CATEGORY}"
        body = ANCHOR_SECTIONS + extra_sections + ANCHOR_WITHDRAWAL_SECTION
    return document(summary=" ".join(summary.split()), closing=closing, sections=body)


def amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


# --------------------------------------------------------------------------
# U-F1  unlisted summary category
# --------------------------------------------------------------------------
# The summary line is the index to the ledger. A category outside the parser's
# three-entry list vanished from the stated totals and its whole detail section
# went unread, so the platform published a summary that failed its own identity.

CARD_WITHDRAWALS_DOC = anchored(
    extra_categories="Card Withdrawals 2 120.00-",
    extra_sections=(
        "Card Withdrawals\n"
        "Card Number: xxxx-xxxx-xxxx-0000\n"
        f"{DESCRIBED_HEADER}\n"
        "Mar 4 Debit Purchase - VISA\n"
        "On 030326 A MERCHANT ST\n"
        "0000000001 70.00-\n"
        "A MERCHANT ************0000\n"
        "Mar 5 Debit Purchase - VISA\n"
        "On 030426 A MERCHANT ST\n"
        "0000000002 50.00-\n"
        "A MERCHANT ************0000\n"
        "Card 0000  Withdrawals Subtotal $ 120.00-\n"
        "Total Card Withdrawals $ 120.00-\n"
    ),
    closing="1,300.00",
)


def test_f1_a_summary_category_outside_the_old_list_is_read():
    stmt = parse_us_bank_statement(CARD_WITHDRAWALS_DOC)
    assert stmt is not None
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 200.00
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 3
    assert amounts(stmt) == [500.00, -70.00, -50.00, -80.00]


def test_f1_the_ledger_now_satisfies_the_banks_own_identity():
    stmt = parse_us_bank_statement(CARD_WITHDRAWALS_DOC)
    activity = sum(t.amount for t in stmt.transactions)
    assert round(stmt.beginning_balance + activity, 2) == stmt.ending_balance


@pytest.mark.parametrize("category, heading, header, rows, subtotal", [
    ("Card Deposits 1 400.00", "Card Deposits", DESCRIBED_HEADER,
     "Mar 3 ATM Deposit A BRANCH\n$ 400.00\nSerial No. 000000000000\n",
     "Card xxxx-xxxx-xxxx-0000  Deposit Subtotal $ 400.00\n"),
    ("Customer Deposits 1 400.00", "Customer Deposits", NUMBERED_HEADER,
     "Mar 3 8000000000 400.00\n", ""),
])
def test_f1_every_printed_credit_category_is_indexed_to_its_section(
        category, heading, header, rows, subtotal):
    doc = anchored(
        extra_categories=category,
        extra_sections=(
            f"{heading}\n"
            + ("Card Number: xxxx-xxxx-xxxx-0000\n" if heading.startswith("Card") else "")
            + f"{header}\n{rows}{subtotal}"
            f"Total {heading} $ 400.00\n"
        ),
        closing="1,820.00",
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, 400.00, -80.00]
    assert stmt.stated_total_credits == 900.00
    assert stmt.stated_credit_count == 2


def test_f1_negative_an_unreadable_printed_category_fails_closed():
    """A category the parser cannot read makes OUR summary miss the bank's own
    identity by exactly that category, so nothing is published. This is the
    guard that turns the old silent drop into a refusal."""
    doc = anchored(extra_categories="Wire Transfers In 1 250.00", closing="1,670.00")
    assert parse_us_bank_statement(doc) is None


def test_f1_negative_a_section_that_does_not_reproduce_its_printed_total_fails_closed():
    doc = document(
        summary="Other Deposits 2 500.00 Other Withdrawals 1 80.00-",
        closing="1,420.00",
        sections=(
            "Other Deposits\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Electronic Deposit\n$ 300.00\n"
            "Total Other Deposits $ 500.00\n"
            + ANCHOR_WITHDRAWAL_SECTION
        ),
    )
    assert parse_us_bank_statement(doc) is None


# --------------------------------------------------------------------------
# U-F2  card sub-block furniture
# --------------------------------------------------------------------------

def test_f2_the_per_card_subtotal_is_never_a_row():
    stmt = parse_us_bank_statement(CARD_WITHDRAWALS_DOC)
    assert all(t.amount != -120.00 for t in stmt.transactions)


def test_f2_a_card_section_split_over_several_card_sub_blocks_is_read_whole():
    doc = anchored(
        extra_categories="Card Withdrawals 2 120.00-",
        extra_sections=(
            "Card Withdrawals\n"
            "Card Number: xxxx-xxxx-xxxx-0000\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 4 Debit Purchase - VISA\n0000000001 70.00-\n"
            "Card 0000  Withdrawals Subtotal $ 70.00-\n"
            "Card Number: xxxx-xxxx-xxxx-1111\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 5 Debit Purchase - VISA\n0000000002 50.00-\n"
            "Card 1111  Withdrawals Subtotal $ 50.00-\n"
            "Total Card Withdrawals $ 120.00-\n"
        ),
        closing="1,300.00",
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -70.00, -50.00, -80.00]


# --------------------------------------------------------------------------
# U-F3  the checks grid
# --------------------------------------------------------------------------
# `Checks Presented Conventionally` prints several column groups on one physical
# line, carries `*` gap markers, and closes with a differently-worded total that
# names no section (`Conventional Checks Paid (n) $ x-`).

CHECKS_DOC = anchored(
    last=True,
    extra_categories="Checks Paid 3 600.00-",
    extra_sections=(
        "Checks Presented Conventionally\n"
        f"{CHECK_HEADER}\n"
        "1001 Mar 4 8000000001 100.00 1002 Mar 5 8000000002 200.00 1004* Mar 6 8000000003 300.00\n"
        "* Gap in check sequence\n"
        "Conventional Checks Paid (3) $ 600.00-\n"
    ),
    closing="820.00",
)


def test_f3_several_check_column_groups_on_one_printed_line_are_separate_rows():
    stmt = parse_us_bank_statement(CHECKS_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -80.00, -100.00, -200.00, -300.00]
    assert [t.date for t in stmt.transactions] == [
        "2026-03-03", "2026-03-06", "2026-03-04", "2026-03-05", "2026-03-06"]


def test_f3_the_printed_check_number_is_the_description_and_keeps_its_gap_marker():
    stmt = parse_us_bank_statement(CHECKS_DOC)
    assert [t.description for t in stmt.transactions][2:] == [
        "Check 1001", "Check 1002", "Check 1004*"]


def test_f3_negative_the_gap_footnote_and_the_checks_total_are_never_rows():
    stmt = parse_us_bank_statement(CHECKS_DOC)
    assert len(stmt.transactions) == 5
    assert all(t.amount != -600.00 for t in stmt.transactions)


# --------------------------------------------------------------------------
# U-F4  money printed after the Amount cell
# --------------------------------------------------------------------------
# A foreign-currency purchase prints `Exchg Amt: $x Orig Curr:y` on a
# continuation line BELOW the Amount cell. Any "last money token" rule reads the
# original-currency figure as the amount.

FOREIGN_DOC = anchored(
    extra_categories="Card Withdrawals 1 54.63-",
    extra_sections=(
        "Card Withdrawals\n"
        "Card Number: xxxx-xxxx-xxxx-0000\n"
        f"{DESCRIBED_HEADER}\n"
        "Mar 4 Debit Purchase - VISA\n"
        "On 030326 A FOREIGN CITY\n"
        "0000000001 54.63-\n"
        "A MERCHANT ************0000 Exchg Amt: $54.63 Orig Curr:936.38\n"
        "REF # 00000000000000000000000 Currency Type: A FOREIGN CURRENCY\n"
        "Card 0000  Withdrawals Subtotal $ 54.63-\n"
        "Total Card Withdrawals $ 54.63-\n"
    ),
    closing="1,365.37",
)


def test_f4_an_original_currency_figure_below_the_amount_cell_is_not_the_amount():
    stmt = parse_us_bank_statement(FOREIGN_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -54.63, -80.00]


def test_f4_negative_a_wrapped_amount_cell_alone_on_its_line_is_still_the_amount():
    """The rule is "the money cell that terminates a printed line", so the
    common shape — the Amount column wrapped onto a line of its own, with the
    bank's trace lines printed below it — must keep working. This fixture is the
    contrast half of the pair above and it is the anchor deposit itself."""
    stmt = parse_us_bank_statement(anchored(closing="1,420.00"))
    assert amounts(stmt) == ANCHOR_AMOUNTS
    assert stmt.transactions[0].description == "Electronic Deposit From A COUNTERPARTY"


# --------------------------------------------------------------------------
# U-F5  compressed line in a described section
# --------------------------------------------------------------------------

def test_f5_two_printed_rows_on_one_physical_line_are_two_rows():
    doc = document(
        summary="Other Deposits 1 500.00 Other Withdrawals 2 17,000.00-",
        opening="20,000.00",
        closing="3,500.00",
        sections=(
            ANCHOR_SECTIONS
            + "Other Withdrawals\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Mobile Banking Transfer To Account 000000000000 $ 6,000.00- "
            "Mar 7 Internet Banking Transfer To Account 000000000000 11,000.00-\n"
            "Total Other Withdrawals $ 17,000.00-\n"
        ),
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -6000.00, -11000.00]
    assert [t.date for t in stmt.transactions] == [
        "2026-03-03", "2026-03-03", "2026-03-07"]


def test_f5_negative_a_date_inside_a_description_does_not_open_a_row():
    """The seam is an Amount cell followed by the next row's Date cell, so a
    date printed mid-description — with no amount in front of it — cannot cut
    the row."""
    doc = document(
        summary="Other Deposits 1 500.00 Other Withdrawals 1 250.00-",
        closing="1,250.00",
        sections=(
            ANCHOR_SECTIONS
            + "Other Withdrawals\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Electronic Withdrawal Invoice dated Feb 27 and Mar 1 $ 250.00-\n"
            "Total Other Withdrawals $ 250.00-\n"
        ),
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -250.00]
    assert stmt.transactions[1].date == "2026-03-03"


# --------------------------------------------------------------------------
# U-F6  a heading owns its line
# --------------------------------------------------------------------------

def test_f6_negative_the_account_summary_line_never_opens_a_detail_section():
    """The summary prints every section's name on one line
    (`... Other Withdrawals 1 80.00- ...`). If that opened a section, the
    summary's own figures would be read as ledger rows."""
    stmt = parse_us_bank_statement(CARD_WITHDRAWALS_DOC)
    assert amounts(stmt) == [500.00, -70.00, -50.00, -80.00]


def test_f6_negative_the_printed_section_total_is_never_a_row():
    stmt = parse_us_bank_statement(anchored(closing="1,420.00"))
    assert amounts(stmt) == ANCHOR_AMOUNTS


# --------------------------------------------------------------------------
# U-F7  page break inside a section
# --------------------------------------------------------------------------

def test_f7_a_section_continues_across_a_page_break_and_the_letterhead_stays_out():
    doc = document(
        summary="Other Deposits 1 500.00 Other Withdrawals 2 300.00-",
        closing="1,200.00",
        sections=(
            ANCHOR_SECTIONS
            + "Other Withdrawals\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Electronic Withdrawal\n"
            "To A COUNTERPARTY\n"
            "$ 100.00-\n"
            "Products and services available in U.S. only.\n"
            "\n--- Page 2 ---\n\n"
            "Mar 2, 2026 through Mar 31, 2026\n"
            "Page 2 of 3\n"
            "U.S. BANK SILVER - BUSINESS CHECKING (CONTINUED)\n"
            "U.S. Bank National Association\n"
            "Account Number 1-234-5678-9012\n"
            "Other Withdrawals (continued)\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 9 Electronic Withdrawal\n"
            "To A COUNTERPARTY\n"
            "200.00-\n"
            "Total Other Withdrawals $ 300.00-\n"
        ),
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -100.00, -200.00]
    assert stmt.transactions[2].description == "Electronic Withdrawal To A COUNTERPARTY"


def test_f7_negative_the_balance_summary_series_is_never_activity():
    doc = anchored(
        extra_sections="",
        closing="1,420.00",
    ) + (
        "Balance Summary\n"
        "Date Ending Balance Date Ending Balance\n"
        "Mar 3 1,500.00 Mar 6 1,420.00\n"
        "Balances only appear for days reflecting change.\n"
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == ANCHOR_AMOUNTS


# --------------------------------------------------------------------------
# U-F8  the printed sign
# --------------------------------------------------------------------------

def test_f8_direction_comes_from_the_printed_sign_not_from_the_category_name():
    """Every outflow line in the summary carries the bank's trailing minus, and
    that — not a memorised list of which names are debits — is what decides the
    direction of the section it indexes."""
    stmt = parse_us_bank_statement(CARD_WITHDRAWALS_DOC)
    assert [t.direction for t in stmt.transactions] == [
        "credit", "debit", "debit", "debit"]


def test_f8_an_overdrawn_balance_prints_its_minus_after_the_figure():
    doc = document(
        summary="Other Deposits 1 500.00 Other Withdrawals 1 1,700.00-",
        closing="200.00-",
        sections=(
            ANCHOR_SECTIONS
            + "Other Withdrawals\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Electronic Withdrawal\n$ 1,700.00-\n"
            "Total Other Withdrawals $ 1,700.00-\n"
        ),
    )
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert stmt.ending_balance == -200.00
    assert amounts(stmt) == [500.00, -1700.00]
