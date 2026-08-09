"""PNC section-vocabulary families (W3 Track A, cell `pnc x {detail_coverage 14,
ledger_identity 2}`).

Every document below is synthetic and built from the PRINTED GRID: the Balance
Summary, the Activity Detail section headings, and the two column groups those
sections use. No fixture carries a real customer, account, amount or date, and no
rule under test is keyed on one.

The cell's root cause is a closed section vocabulary, and it does two kinds of
damage at once because the same list is also the list of section BOUNDARIES. A
section PNC prints but the parser does not know is not merely unread: it is
swallowed by the section printed above it, so its rows take that section's
direction and its heading and column header are glued onto the last description
there. PNC publishes its own index of the list — a `Description Items Amount`
table naming every section it itemizes, with the item count and total of each —
and that table names two sections the parser did not have. See
`docs/moneythumb-replacement/W3_TRACKA_LOG.md` section TRIO.
"""
from __future__ import annotations

from analysis.pnc import parse_pnc_statement

DESCRIBED_HEADER = "Date posted\nAmount\nTransaction description\nReference\nnumber\n"
CHECK_HEADER = "Date posted\nCheck number\nAmount\nReference\nnumber\n"


def document(*, activity: str, beginning: str = "1,000.00", credits: str = "500.00",
             debits: str = "300.00", ending: str = "1,200.00") -> str:
    return (
        "Business Checking\n"
        "PNC Bank\n"
        "For the Period 04/01/2026 to 04/30/2026\n"
        "Primary Account Number: XX-XXXX-0000\n"
        "Balance Summary\n"
        "Beginning\n"
        f"Ending balance {beginning} {credits} {debits} {ending}\n"
        "Deposits and other additions\n"
        "Checks and other\n"
        "balance\n"
        "deductions\n"
        "Average ledger\n"
        "Average collected\n"
        "balance 900.00 900.00\n"
        "balance\n"
        "Overdraft and Returned Item Fee Summary\n"
        "Total Overdraft Fees .00 .00\n"
        "Activity Detail\n"
        f"{activity}"
        "Daily Balance\n"
        "Date Ledger balance\n"
        "04/30 1,200.00\n"
    )


def amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


def descriptions(stmt) -> list[str]:
    return [t.description for t in stmt.transactions]


# --------------------------------------------------------------------------
# P-F1  a printed section outside the parser's vocabulary
# --------------------------------------------------------------------------
# `Fee Refunds` is printed between two known sections. Because it was not in the
# section list it was also not a section BOUNDARY, so its rows were swallowed by
# `ATM Deposits and Additions` above it — and the heading and column header of
# the swallowed section were appended to that section's last description.

FEE_REFUNDS_DOC = document(
    activity=(
        "Deposits and Other Additions\n"
        "ATM Deposits and Additions\n"
        f"{DESCRIBED_HEADER}"
        "04/15 400.00 ATM Deposit A Branch 000000001\n"
        "Fee Refunds\n"
        f"{DESCRIBED_HEADER}"
        "04/28 100.00 A Fee Reimbursement 000000002\n"
        "Checks and Other Deductions\n"
        "Service Charges and Fees\n"
        f"{DESCRIBED_HEADER}"
        "04/30 300.00 A Monthly Service Charge 000000003\n"
    ),
)


def test_f1_a_printed_section_outside_the_old_vocabulary_is_read():
    stmt = parse_pnc_statement(FEE_REFUNDS_DOC)
    assert stmt is not None
    assert amounts(stmt) == [400.00, 100.00, -300.00]


def test_f1_the_swallowed_sections_heading_no_longer_joins_the_description_above_it():
    stmt = parse_pnc_statement(FEE_REFUNDS_DOC)
    assert descriptions(stmt)[0] == "ATM Deposit A Branch 000000001"
    assert descriptions(stmt)[1] == "A Fee Reimbursement 000000002"


def test_f1_a_swallowed_section_would_take_the_wrong_direction():
    """The sign hazard, pinned directly.

    In the archive `Fee Refunds` is always printed inside the
    `Deposits and Other Additions` group, so the section that swallowed it was
    always a credit section and no observed amount changed sign. The rule being
    fixed is nevertheless "a row's direction is the section the bank printed it
    in", and this fixture is the one that says so: the same section printed
    below a DEBIT section must still publish credits. It is a rule constraint,
    not a layout measured in the archive, and it is recorded as such."""
    doc = document(
        credits="100.00", debits="300.00", ending="800.00",
        activity=(
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Monthly Service Charge 000000003\n"
            "Fee Refunds\n"
            f"{DESCRIBED_HEADER}"
            "04/28 100.00 A Fee Reimbursement 000000002\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [100.00, -300.00]
    assert [t.direction for t in stmt.transactions] == ["credit", "debit"]


def test_f1_the_ledger_satisfies_the_printed_balance_summary():
    stmt = parse_pnc_statement(FEE_REFUNDS_DOC)
    activity = sum(t.amount for t in stmt.transactions)
    assert round(stmt.beginning_balance + activity, 2) == stmt.ending_balance


# --------------------------------------------------------------------------
# P-F2  the cheque section and its own column group
# --------------------------------------------------------------------------
# `Checks and Substitute Checks` prints `Date posted | Check number | Amount |
# Reference number` — a different column group from every other section — with
# several groups on one physical line and `*` sequence-gap markers.

CHECKS_DOC = document(
    debits="600.00", ending="900.00",
    activity=(
        "Deposits and Other Additions\n"
        "Deposits\n"
        f"{DESCRIBED_HEADER}"
        "04/02 500.00 Deposit 000000001\n"
        "Checks and Other Deductions\n"
        "Checks and Substitute Checks\n"
        f"{CHECK_HEADER}"
        "04/04 1100 * 50.00 018785793 04/03 1101 250.00 018074965 04/17 1102 300.00 014493645\n"
    ),
)


def test_f2_several_cheque_column_groups_on_one_printed_line_are_separate_rows():
    stmt = parse_pnc_statement(CHECKS_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -50.00, -250.00, -300.00]


def test_f2_the_printed_check_number_is_the_description_and_keeps_its_gap_marker():
    stmt = parse_pnc_statement(CHECKS_DOC)
    assert descriptions(stmt)[1:] == ["Check 1100*", "Check 1101", "Check 1102"]


def test_f2_negative_the_reference_number_is_never_the_amount():
    stmt = parse_pnc_statement(CHECKS_DOC)
    assert all(abs(t.amount) < 10_000 for t in stmt.transactions)


# --------------------------------------------------------------------------
# P-F3  the heading carries its own footnote
# --------------------------------------------------------------------------

def test_f3_the_gap_footnote_printed_on_the_heading_line_does_not_hide_the_section():
    doc = document(
        debits="600.00", ending="900.00",
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Checks and Other Deductions\n"
            "Checks and Substitute Checks * Gap in check sequence\n"
            f"{CHECK_HEADER}"
            "04/04 1100 * 600.00 018785793\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -600.00]


def test_f3_negative_a_heading_still_owns_its_line():
    """A row whose description happens to contain a section's words must not
    open that section."""
    doc = document(
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit reversing Service Charges and Fees 000000001\n"
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Monthly Service Charge 000000003\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]
    assert descriptions(stmt)[0] == "Deposit reversing Service Charges and Fees 000000001"


# --------------------------------------------------------------------------
# P-F4  a sub-dollar balance printed without its leading zero
# --------------------------------------------------------------------------

def test_f4_a_closing_balance_of_less_than_a_dollar_is_read_as_the_closing_balance():
    """PNC drops the leading zero on a sub-dollar figure, so a closing balance
    of eighty-seven cents prints as `.87`. The old pattern's `\\b` did not match
    after a space, so that figure was skipped and the NEXT one — the average
    ledger balance printed below it — was read as the closing balance."""
    doc = document(
        beginning="1.56", credits="500.00", debits="500.69", ending=".87",
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 500.69 A Monthly Service Charge 000000003\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert stmt.beginning_balance == 1.56
    assert stmt.ending_balance == 0.87
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 500.69
    activity = sum(t.amount for t in stmt.transactions)
    assert round(stmt.beginning_balance + activity, 2) == stmt.ending_balance


def test_f3_the_continued_on_next_page_trailer_is_furniture_not_description():
    """PNC prints `<section> continued on next page` at the foot of a page. It
    owns its line and belongs to no row, so it closes the section rather than
    joining the description of the row above it."""
    doc = document(
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Deposits continued on next page\n"
            "\n--- Page 2 ---\n\n"
            "Business Checking\n"
            "For the Period 04/01/2026 to 04/30/2026\n"
            "Deposits - continued\n"
            f"{DESCRIBED_HEADER}"
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Monthly Service Charge 000000003\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]
    assert descriptions(stmt)[0] == "Deposit 000000001"


def test_f4_negative_a_whole_dollar_summary_is_unchanged():
    stmt = parse_pnc_statement(FEE_REFUNDS_DOC)
    assert (stmt.beginning_balance, stmt.stated_total_credits,
            stmt.stated_total_debits, stmt.ending_balance) == (1000.00, 500.00, 300.00, 1200.00)
