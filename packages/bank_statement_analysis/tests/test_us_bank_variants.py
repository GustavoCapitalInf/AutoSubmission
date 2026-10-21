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
loss.

Every fixture prints BOTH categories the pre-change parser required
(`Other Deposits` and `Other Withdrawals`), so each one is a document the old
reader could also read and the fails-before/passes-after replay in the log is a
real contrast rather than an artefact of a minimal fixture.
"""
from __future__ import annotations

import pytest

from analysis.us_bank import parse_us_bank_statement

PERIOD = "Statement Period:\nMar 2, 2054\nthrough Mar 31, 2054\n"
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
             sections: str, days: str | None = "31",
             product: str = "U.S. BANK SILVER - BUSINESS CHECKING",
             items_heading: str = "# Items\n") -> str:
    """A U.S. Bank statement with the printed blocks the parser reads.

    The header block is printed as the bank prints it — product name, `Member
    FDIC`, the association line and the account number, immediately above the
    Account Summary — because the published product name is read from it.

    `days=None` prints no `Number of Days in Statement Period` line, which is
    what the layouts without an `# Items` column do.
    """
    return (
        "Business Statement\n"
        f"{PERIOD}"
        f"{product}\n"
        "Member FDIC\n"
        "U.S. Bank National Association\n"
        "Account Number 1-234-5678-9012\n"
        "Account Summary\n"
        f"{items_heading}"
        + (f"Number of Days in Statement Period {days}\n" if days is not None else "")
        + f"Beginning Balance on Mar 2 $ {opening} {summary}\n"
        f"Ending Balance on  Mar 31, 2054 $ {closing}\n"
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
        "2054-03-03", "2054-03-06", "2054-03-04", "2054-03-05", "2054-03-06"]


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
        "2054-03-03", "2054-03-03", "2054-03-07"]


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
    assert stmt.transactions[1].date == "2054-03-03"


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
            "Mar 2, 2054 through Mar 31, 2054\n"
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


# --------------------------------------------------------------------------
# U-F9  the optional `Number of Days in Statement Period` line
# --------------------------------------------------------------------------
# The days line is an optional summary line, exactly like `Interest Earned this
# Period` and like the categories themselves: the layouts that print no
# `# Items` column print no days line either. Requiring it refused otherwise
# complete documents over a figure the printed period already states.

NO_DAYS_DOC = document(
    summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
    closing="1,420.00",
    sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
    days=None,
    items_heading="",
)


def test_f9_a_summary_that_prints_no_days_line_is_still_read():
    stmt = parse_us_bank_statement(NO_DAYS_DOC)
    assert stmt is not None
    assert amounts(stmt) == ANCHOR_AMOUNTS


def test_f9_the_day_count_falls_back_to_the_printed_period():
    stmt = parse_us_bank_statement(NO_DAYS_DOC)
    # Mar 2 through Mar 31 inclusive, from the period the bank prints.
    assert stmt.days_in_period == 30


def test_f9_a_printed_days_line_still_outranks_the_period():
    # The bank's two printed figures disagree on this layout as a matter of
    # course (the cycle ends on a business day, the count is calendar), and the
    # printed count is the one the bank states.
    stmt = parse_us_bank_statement(
        document(
            summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
            closing="1,420.00",
            sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
            days="31",
        )
    )
    assert stmt.days_in_period == 31


# --------------------------------------------------------------------------
# U-F10  the consumer grid — a category vocabulary with no count column
# --------------------------------------------------------------------------
# The consumer layout folds every inflow into one `Deposits / Credits` category
# and prints no `# Items` cells at all. A memorized six-name vocabulary matched
# nothing in it, so the parser read no categories and declined the document.

CONSUMER_DOC = document(
    summary="Deposits / Credits 500.00 Card Withdrawals 120.00- Other Withdrawals 80.00-",
    closing="1,300.00",
    days=None,
    items_heading="",
    product="U.S. BANK SMARTLY CHECKING",
    sections=(
        "Deposits / Credits\n"
        f"{DESCRIBED_HEADER}\n"
        "Mar 3 Mobile Banking Transfer From Account\n"
        "$ 500.00\n"
        "Total Deposits / Credits $ 500.00\n"
        "Card Withdrawals\n"
        "Card Number: xxxx-xxxx-xxxx-0000\n"
        f"{DESCRIBED_HEADER}\n"
        "Mar 4 Debit Purchase - VISA\n"
        "0000000001 120.00-\n"
        "Total Card Withdrawals $ 120.00-\n"
        "Other Withdrawals\n"
        f"{DESCRIBED_HEADER}\n"
        "Mar 6 Electronic Withdrawal\n"
        "$ 80.00-\n"
        "Total Other Withdrawals $ 80.00-\n"
    ),
)


def test_f10_a_category_vocabulary_outside_the_business_grid_is_read():
    stmt = parse_us_bank_statement(CONSUMER_DOC)
    assert stmt is not None
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 200.00
    assert amounts(stmt) == [500.00, -120.00, -80.00]


def test_f10_an_unprinted_item_count_is_not_a_zero():
    stmt = parse_us_bank_statement(CONSUMER_DOC)
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_f10_a_direction_counted_only_in_part_publishes_no_count():
    # One printed count in a direction does not state that direction's total.
    stmt = parse_us_bank_statement(
        document(
            summary="Other Deposits 1 500.00 Card Withdrawals 120.00- Other Withdrawals 1 80.00-",
            closing="1,300.00",
            sections=(
                ANCHOR_SECTIONS
                + "Card Withdrawals\n"
                "Card Number: xxxx-xxxx-xxxx-0000\n"
                f"{DESCRIBED_HEADER}\n"
                "Mar 4 Debit Purchase - VISA\n"
                "0000000001 120.00-\n"
                "Total Card Withdrawals $ 120.00-\n"
                + ANCHOR_WITHDRAWAL_SECTION
            ),
        )
    )
    assert stmt is not None
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count is None


# --------------------------------------------------------------------------
# U-F11  cheques presented under more than one heading
# --------------------------------------------------------------------------
# The summary states one `Checks Paid` figure; the ledger presents cheques by
# the MANNER of presentation, each manner under its own heading with its own
# subtotal. A one-heading-per-category map read the conventional block only,
# and the category's section-total check then refused the whole document.

ELECTRONIC_CHECKS_DOC = anchored(
    extra_categories="Checks Paid 2 300.00-",
    extra_sections=(
        "Checks Presented Conventionally\n"
        f"{CHECK_HEADER}\n"
        "1341 Mar 6 0000000001 100.00\n"
        "Conventional Checks Paid (1) $ 100.00-\n"
        "Checks Presented Electronically\n"
        "Check Date Ref Number Amount Description of Transaction Payee\n"
        "1344 Mar 27 200.00 Redepcheck A COUNTERPARTY\n"
        "Electronic Checks Paid (1) $ 200.00-\n"
        "Total Checks Paid $ 300.00-\n"
    ),
    closing="1,120.00",
    last=True,
)


def test_f11_both_presentation_sections_feed_the_one_checks_category():
    stmt = parse_us_bank_statement(ELECTRONIC_CHECKS_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -80.00, -100.00, -200.00]
    assert stmt.stated_total_debits == 380.00


def test_f11_an_electronic_cheque_keeps_its_printed_number_as_the_description():
    stmt = parse_us_bank_statement(ELECTRONIC_CHECKS_DOC)
    assert [t.description for t in stmt.transactions][-2:] == ["Check 1341", "Check 1344"]


def test_f11_negative_the_per_manner_subtotals_are_never_rows():
    stmt = parse_us_bank_statement(ELECTRONIC_CHECKS_DOC)
    assert len(stmt.transactions) == 4
    assert -300.00 not in amounts(stmt)


# --------------------------------------------------------------------------
# U-F12  the period, read from the label the bank prints it under
# --------------------------------------------------------------------------
# `Statement Period:`, the start date and `through <end>` are one column of the
# page header. Flattening a page interleaves the neighbouring columns between
# them, so the two halves are adjacent only by luck — and a single-page
# statement gets exactly one printing of the header to be lucky in.

INTERLEAVED_PERIOD_DOC = (
    "Business Statement\n"
    "Account Number:\n"
    "1 234 5678 9012 Statement Period:\n"
    "P.O. Box 1800 Saint Paul, Minnesota 55101-0800\n"
    "Mar 2, 2054\n"
    "1499 TRN S Y ST01\n"
    "through Mar 31, 2054\n"
    "Page 1 of 1\n"
    "U.S. BANK GOLD - BUSINESS CHECKING\n"
    "Member FDIC\n"
    "U.S. Bank National Association\n"
    "Account Number 1-234-5678-9012\n"
    "Account Summary\n"
    "# Items\n"
    "Number of Days in Statement Period 31\n"
    f"Beginning Balance on Mar 2 $ 1,000.00 {ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}\n"
    "Ending Balance on  Mar 31, 2054 $ 1,420.00\n"
    + ANCHOR_SECTIONS
    + ANCHOR_WITHDRAWAL_SECTION
)


def test_f12_a_period_split_by_an_interleaved_column_is_still_read():
    stmt = parse_us_bank_statement(INTERLEAVED_PERIOD_DOC)
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == ("2054-03-02", "2054-03-31")


def test_f12_negative_a_document_printing_no_period_label_is_refused():
    assert parse_us_bank_statement(
        INTERLEAVED_PERIOD_DOC.replace("Statement Period:", "")
    ) is None


def test_f12_negative_a_reversed_pair_is_not_a_period():
    assert parse_us_bank_statement(
        INTERLEAVED_PERIOD_DOC.replace("through Mar 31, 2054", "through Mar 1, 2054")
    ) is None


# --------------------------------------------------------------------------
# U-F13  the published product name, read from the printed header block
# --------------------------------------------------------------------------
# This parser serves several U.S. Bank products. It used to publish one
# memorized product name on every document it read (R-1 class).

@pytest.mark.parametrize("product", [
    "U.S. BANK SILVER - BUSINESS CHECKING",
    "U.S. BANK GOLD - BUSINESS CHECKING",
    "SILVER BUSINESS CHECKING",
    "U.S. BANK SMARTLY CHECKING",
    "PLATINUM BUSINESS MONEY MARKET",
])
def test_f13_the_published_product_is_the_one_printed(product):
    stmt = parse_us_bank_statement(
        document(
            summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
            closing="1,420.00",
            sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
            product=product,
        )
    )
    assert stmt is not None
    assert stmt.account_name == product


def test_f13_the_header_block_is_read_in_either_printed_order():
    # Some layouts print the account number above the association line.
    swapped = document(
        summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
        closing="1,420.00",
        sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
    ).replace(
        "U.S. Bank National Association\nAccount Number 1-234-5678-9012\n",
        "Account Number 1-234-5678-9012\nU.S. Bank National Association\n",
    )
    stmt = parse_us_bank_statement(swapped)
    assert stmt is not None
    assert stmt.account_name == "U.S. BANK SILVER - BUSINESS CHECKING"


def test_f13_negative_a_disclosure_page_footer_is_not_the_product_name():
    # `Member FDIC` is also printed under the credit-bureau disclosure, where
    # the line above it is prose. Only the block above an Account Summary names
    # the product.
    doc = document(
        summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
        closing="1,420.00",
        sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
    )
    with_disclosure = (
        "CONSUMER REPORT DISPUTES\n"
        "We may report information about account activity on consumer and small\n"
        "business deposit accounts to consumer reporting agencies.\n"
        "Member FDIC\n"
        "--- Page 2 ---\n"
    ) + doc
    stmt = parse_us_bank_statement(with_disclosure)
    assert stmt is not None
    assert stmt.account_name == "U.S. BANK SILVER - BUSINESS CHECKING"


def test_f13_negative_no_printed_header_block_publishes_no_product_name():
    doc = document(
        summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
        closing="1,420.00",
        sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
    ).replace("Member FDIC\n", "")
    stmt = parse_us_bank_statement(doc)
    assert stmt is not None
    assert stmt.account_name is None


# --------------------------------------------------------------------------
# U-F14  a product line is product-SHAPED, not merely product-POSITIONED
# --------------------------------------------------------------------------
# Adversarial review, closure 4. The anchor published whatever line sat above
# the header block. With the product line missing, the line above is whatever
# the previous page ended on — and a marketing sentence published as the
# account's name is a worse answer than admitting nothing was printed.

PROSE = (
    "We may report information about account activity on consumer and small "
    "business deposit accounts to consumer reporting agencies."
)


def product_replaced_by(line: str) -> str:
    return document(
        summary=f"{ANCHOR_CREDIT_CATEGORY} {ANCHOR_DEBIT_CATEGORY}",
        closing="1,420.00",
        sections=ANCHOR_SECTIONS + ANCHOR_WITHDRAWAL_SECTION,
    ).replace("U.S. BANK SILVER - BUSINESS CHECKING", line)


def test_f14_a_sentence_at_the_anchor_is_not_published_as_the_product():
    stmt = parse_us_bank_statement(product_replaced_by(PROSE))
    assert stmt is not None
    assert stmt.account_name is None


@pytest.mark.parametrize("line", [
    PROSE,
    "Here's what you should know:",
    "Effective May 11, 2054, please review updates made to the document.",
    "usbank.com/YDAA-upcoming-version",
    "Products and services available in U.S. only.",
])
def test_f14_no_prose_line_is_ever_published_as_a_product(line):
    stmt = parse_us_bank_statement(product_replaced_by(line))
    assert stmt is not None
    assert stmt.account_name is None


@pytest.mark.parametrize("product", [
    "U.S. BANK SILVER - BUSINESS CHECKING",
    "U.S. BANK GOLD - BUSINESS CHECKING",
    "SILVER BUSINESS CHECKING",
    "U.S. BANK SMARTLY CHECKING",
    "PLATINUM BUSINESS MONEY MARKET",
])
def test_f14_every_product_the_bank_actually_prints_still_passes_the_shape(product):
    stmt = parse_us_bank_statement(product_replaced_by(product))
    assert stmt is not None
    assert stmt.account_name == product


def test_f14_the_statement_is_still_published_without_a_product_name():
    """Refusing the NAME must not refuse the statement: the money is unaffected."""
    stmt = parse_us_bank_statement(product_replaced_by(PROSE))
    assert stmt.account_name is None
    assert amounts(stmt) == ANCHOR_AMOUNTS
    assert stmt.ending_balance == 1420.00
