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
             debits: str = "300.00", ending: str = "1,200.00",
             grid: str | None = None, index: str = "",
             product: str = "Business Checking",
             period: str = "For the Period 04/01/2054 to 04/30/2054") -> str:
    """A PNC statement of one of the printed skins.

    `grid` is the end-of-day ladder the bank prints, and it defaults to the
    period's last day carrying the ENDING balance — because that is what a real
    statement prints, and because the reader now walks its ledger against that
    ladder. A fixture whose ladder and whose activity disagree is a fixture that
    describes no statement PNC has ever issued.
    """
    return (
        f"{product}\n"
        "PNC Bank\n"
        f"{period}\n"
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
        f"{index}"
        "Activity Detail\n"
        f"{activity}"
        "Daily Balance\n"
        "Date Ledger balance\n"
        f"04/30 {ending if grid is None else grid}\n"
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
            "For the Period 04/01/2054 to 04/30/2054\n"
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


# --------------------------------------------------------------------------
# P-F5  a thousands separator the text layer prints as a space
# --------------------------------------------------------------------------
# The Balance Summary body is a FLATTENED grid, so the same space character
# separates the columns and — where a figure is printed `1 000.00` — groups its
# thousands. The old pattern could not match such a figure whole, and the piece
# that DID fit was its `000.00` tail: every column truncated by the same
# thousand, every printed identity still closing, and the statement published
# approved with beginning, ending and the average balance all wrong by it.
#
# Nothing downstream can catch that, which is why it is settled here. The
# separators are the ones `analysis/money.py` already surveys (`1 234.56`, its
# :17 format axes; `EITHER_MINUS_SPACED` :214) — an ASCII space and the two
# no-break spaces a PDF text layer emits in its place.

NBSP = "\u00a0"
NNBSP = "\u202f"


def summary_of(stmt):
    return (stmt.beginning_balance, stmt.stated_total_credits,
            stmt.stated_total_debits, stmt.ending_balance)


ACTIVITY = (
    "Deposits and Other Additions\n"
    "Deposits\n"
    f"{DESCRIBED_HEADER}"
    "04/02 500.00 Deposit 000000001\n"
    "Checks and Other Deductions\n"
    "Service Charges and Fees\n"
    f"{DESCRIBED_HEADER}"
    "04/30 300.00 A Monthly Service Charge 000000003\n"
)


def test_f5_a_space_grouped_thousands_figure_is_read_whole_not_truncated():
    """`1 000.00` is one figure. Read as `000.00` it is a thousand dollars of
    silent error that every identity in the document still agrees with."""
    doc = document(beginning="1 000.00", ending="1 200.00", activity=ACTIVITY)
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)


def test_f5_the_no_break_space_variant_is_the_same_figure():
    doc = document(beginning=f"1{NBSP}000.00", ending=f"1{NBSP}200.00",
                   activity=ACTIVITY)
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)


def test_f5_the_narrow_no_break_space_variant_is_the_same_figure():
    doc = document(beginning=f"1{NNBSP}000.00", ending=f"1{NNBSP}200.00",
                   activity=ACTIVITY)
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)


def test_f5_the_average_ledger_balance_is_read_whole_too():
    """The average balance is printed in the same block and the same format as
    the four columns above it, so a document whose columns are read whole must
    not publish a truncated average beside them."""
    doc = (
        "Business Checking\nPNC Bank\n"
        "For the Period 04/01/2054 to 04/30/2054\n"
        "Primary Account Number: XX-XXXX-0000\n"
        "Balance Summary\nBeginning\n"
        "Ending balance 1 000.00 500.00 300.00 1 200.00\n"
        "Deposits and other additions\nChecks and other\nbalance\ndeductions\n"
        "Average ledger\nAverage collected\nbalance 1 100.00 1 100.00\nbalance\n"
        "Activity Detail\n"
        f"{ACTIVITY}"
        "Daily Balance\nDate Ledger balance\n04/30 1,200.00\n"
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert stmt.stated_average_balance == 1100.00


def test_f5_negative_a_figure_that_cannot_be_read_whole_is_not_read_at_all():
    """The boundary guard, stated directly. `1 0000.00` is not a grouping this
    parser knows, and the reading it would otherwise fall back on is the
    `0000.00` tail — a truncation that publishes as a plausible `0.00` opening
    balance. Refusing the fragment leaves the grid a column short, so the
    document fails closed instead.

    The body here carries SPARE figures — the average ledger pair below the
    grid — which is what makes this the real test. Refusing a figure only
    fails closed if the reader is bounded to the grid's own row; an unbounded
    reader walks past the hole and takes the next four figures it can find,
    turning a loud refusal into a quiet, wrong approval."""
    doc = document(beginning="1 0000.00", ending="1,200.00", activity=ACTIVITY)
    assert parse_pnc_statement(doc) is None


def test_f5_negative_the_reader_never_walks_past_the_grid_to_find_four_figures():
    """The same construction, said as the property rather than the symptom: the
    figures printed BELOW the grid must never be able to stand in for it."""
    doc = document(beginning="1 0000.00", credits="500.00", debits="300.00",
                   ending="1,200.00", activity=ACTIVITY)
    stmt = parse_pnc_statement(doc)
    assert stmt is None, (
        "the average ledger pair was read as summary columns: "
        f"{stmt and (stmt.beginning_balance, stmt.ending_balance)}"
    )


def test_f5_negative_an_item_count_beside_an_amount_is_out_of_reach():
    """PNC prints a `Description Items Amount` index and a `Daily Balance`
    ladder inside the block this parser is handed, and both put a bare integer
    immediately left of a figure — `Deposits 1 500.00`, `02/11 953.78`. Read as
    money that is 1,500.00 and 11,953.78. They are below the grid row, so the
    summary reader never reaches them; this pins that.

    The index printed here is the one this document's own activity earns, since
    the reader now reads it as the bank's statement of what it itemized."""
    doc = (
        "Business Checking\nPNC Bank\n"
        "For the Period 04/01/2054 to 04/30/2054\n"
        "Primary Account Number: XX-XXXX-0000\n"
        "Balance Summary\nBeginning\n"
        "Ending balance 1,000.00 500.00 300.00 1,200.00\n"
        "Deposits and other additions\nChecks and other\nbalance\ndeductions\n"
        "Average ledger\nAverage collected\nbalance 900.00 900.00\nbalance\n"
        "Description Items Amount Deposits 1 500.00\n"
        "Description Items Amount Service Charges and Fees 1 300.00\n"
        "Date Ledger balance 02/10 1,195.48 02/11 953.78 02/12 840.03\n"
        "Activity Detail\n"
        f"{ACTIVITY}"
        "Daily Balance\nDate Ledger balance\n04/30 1,200.00\n"
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)
    assert stmt.stated_average_balance == 900.00


def test_f5_negative_the_space_between_two_columns_is_still_a_column_gap():
    """The same character does both jobs. A complete `.dd` figure ends a
    column, so the space after one separates columns and must not glue the next
    figure onto it — including the average ledger and average collected
    balances, which PNC prints as the same number twice."""
    doc = document(beginning="1,000.00", credits="500.00", debits="300.00",
                   ending="1,200.00", activity=ACTIVITY)
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)
    assert stmt.stated_average_balance == 900.00


def test_f5_negative_a_bare_sub_dollar_figure_after_another_figure_still_reads():
    """The concession that motivated the optional integer part: PNC prints
    eighty-seven cents as `.87`, and it can stand in any column — including
    directly after a complete figure, which is exactly the position the new
    boundary rule talks about."""
    doc = document(
        beginning="1,000.00", credits=".87", debits="300.00", ending="700.87",
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 .87 Deposit 000000001\n"
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Monthly Service Charge 000000003\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert summary_of(stmt) == (1000.00, 0.87, 300.00, 700.87)


# --------------------------------------------------------------------------
# P-F6  a dated row that moves no money is not a posting
# --------------------------------------------------------------------------
# PNC prints genuine sub-dollar amounts with the leading zero dropped, so the
# row grammar has to accept `.dd` — and a dated informational line carrying
# `.00` then satisfies that grammar exactly as a posting does. Such a row is
# invisible to every identity the fail-closed gate applies: it adds zero to the
# ledger sum and zero to the section total, so `beginning + activity == ending`
# still holds with it in the ledger, and PNC discloses no per-direction count
# oracle (`analysis/count_semantics.py` SECTION_LEVEL_ORACLES) that could see
# the extra row. It is refused on the structure of the row — a posting moves
# money — and not on the words the line happens to use.

def test_f6_a_dated_zero_amount_line_is_not_published_as_a_transaction():
    doc = document(activity=(
        "Deposits and Other Additions\n"
        "Deposits\n"
        f"{DESCRIBED_HEADER}"
        "04/02 500.00 Deposit 000000001\n"
        "Checks and Other Deductions\n"
        "Other Deductions\n"
        f"{DESCRIBED_HEADER}"
        "04/30 300.00 A Monthly Service Charge 000000003\n"
        "04/30 .00 Overdraft fees assessed this statement period\n"
    ))
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]
    assert all("Overdraft fees assessed" not in d for d in descriptions(stmt))


def test_f6_a_genuine_sub_dollar_posting_still_parses():
    """54 rows in the archive are printed this way — `02/02 .82 ACH Credit
    Acctverify ...`. The refusal above must not reach them."""
    doc = document(
        credits=".82", debits="300.00", ending="700.82",
        activity=(
            "Deposits and Other Additions\n"
            "ACH Additions\n"
            f"{DESCRIBED_HEADER}"
            "04/02 .82 ACH Credit Acctverify A Counterparty 00026033010231130\n"
            "Checks and Other Deductions\n"
            "Service Charges and Fees\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Monthly Service Charge 000000003\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [0.82, -300.00]
    assert descriptions(stmt)[0].startswith("ACH Credit Acctverify")


def test_f6_the_printed_overdraft_fee_summary_is_handled_as_it_was():
    """`Total Overdraft Fees .00 .00` is printed outside the Balance Summary
    body and carries no date, so it was never a row and still is not. The
    document around it reads exactly as before."""
    stmt = parse_pnc_statement(FEE_REFUNDS_DOC)
    assert stmt is not None
    assert "Total Overdraft Fees .00 .00" in FEE_REFUNDS_DOC
    assert amounts(stmt) == [400.00, 100.00, -300.00]
    assert summary_of(stmt) == (1000.00, 500.00, 300.00, 1200.00)


def test_f6_a_zero_amount_cheque_is_not_published_either():
    """The cheque section prints its own column group but has the same hole:
    `.00` is a readable amount there too, and a cheque that moves no money is
    not a cheque."""
    doc = document(
        debits="600.00", ending="900.00",
        activity=(
            "Deposits and Other Additions\n"
            "Deposits\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Checks and Other Deductions\n"
            "Checks and Substitute Checks\n"
            f"{CHECK_HEADER}"
            "04/04 1100 600.00 018785793 04/28 1099 * .00 018074965\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -600.00]
    assert descriptions(stmt)[1:] == ["Check 1100"]
