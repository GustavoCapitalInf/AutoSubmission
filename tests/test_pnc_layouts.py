"""PNC's other three printed product skins, and the two identities the reader
now applies to all four (batch 9, cell `PNC-LAYOUTS`).

Every document below is synthetic and built from the PRINTED GRID: the product
title, the Balance Summary, the bank's own index of what it itemized, the
section headings and the end-of-day ladder. No fixture carries a real customer,
account, amount or date, and no rule under test is keyed on one. Every fixture
is arithmetically real — beginning plus the rows equals ending, the index
counts what the rows count, and the ladder is what the ledger walks to —
because a fixture that is not describes no statement PNC has ever issued and
would let a gate pass for the wrong reason.

Two of the rules here can only be tested by the ordering the archive does NOT
print, and both are: a merchant's date printed before a row's own (the ladder
is the only control that sees it) and a both-sided category printed under the
opposite umbrella (the sign follows the paper, not the name).
"""
from __future__ import annotations

from analysis.pnc import parse_pnc_statement

DESCRIBED_HEADER = "Date posted\nAmount\nTransaction description\nReference\nnumber\n"


def amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


def dates(stmt) -> list[str]:
    return [t.date for t in stmt.transactions]


# ---------------------------------------------------------------------------
# The commercial skin: no `Activity Detail` heading, no bank line, a lowercase
# period sentence, a `Ledger Balance` ladder, and each section restating its
# own item count and total on its heading line.
# ---------------------------------------------------------------------------

def commercial(*, index: str, activity: str, ladder: str = "04/02 1,500.00 04/30 1,200.00",
               summary: str = "Ending balance 1,000.00 500.00 300.00 1,200.00") -> str:
    return (
        "PNC Core Commercial Checking Account Statement\n"
        "Page 1 of 1\n"
        "Account Number: XX-XXXX-0000\n"
        "For the period 04/01/2054 to 04/30/2054\n"
        "Visit us at PNC.com/treasury\n"
        "Account Summary Information\n"
        "Balance Summary\n"
        f"{summary}\n"
        "Beginning\n"
        "Deposits and\n"
        "Checks and other debits\n"
        "balance\n"
        "other credits\n"
        "Deposits and Other Credits\n"
        "Checks and Other Debits\n"
        f"{index}"
        "Ledger Balance\n"
        f"Date Ledger balance {ladder}\n"
        f"{activity}"
    )


COMMERCIAL_INDEX = (
    "Description Items Amount Deposits 1 500.00 National Lockbox 0 .00 "
    "Trade Services 0 .00 Other Credits 0 .00\n"
    "Description Items Amount ACH Debits 1 300.00 Trade Services 0 .00 "
    "Other Debits 0 .00 Total 1 500.00 Total 1 300.00\n"
)
COMMERCIAL_ACTIVITY = (
    "Deposits and Other Credits\n"
    "Deposits 1 transaction for a total of $500.00\n"
    f"{DESCRIBED_HEADER}"
    "04/02 500.00 Deposit 000000001\n"
    "Checks and Other Debits\n"
    "ACH Debits 1 transaction for a total of $300.00\n"
    f"{DESCRIBED_HEADER}"
    "04/30 300.00 An ACH Debit 000000002\n"
)
COMMERCIAL_DOC = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY)


def test_the_commercial_skin_is_read_without_an_activity_detail_heading():
    """It prints none. Its detail begins at the first direction heading printed
    after the ledger — the two above that are the index's column headers."""
    stmt = parse_pnc_statement(COMMERCIAL_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]
    assert stmt.account_name == "PNC Core Commercial Checking"


def test_the_lowercase_period_sentence_is_the_same_sentence():
    stmt = parse_pnc_statement(COMMERCIAL_DOC)
    assert (stmt.period_start, stmt.period_end) == ("2054-04-01", "2054-04-30")


def test_the_institution_may_be_printed_as_its_domain_rather_than_its_name():
    """The commercial skin never prints the bank's name; it prints the treasury
    domain and the product title. Both are institution furniture."""
    assert "PNC Bank" not in COMMERCIAL_DOC
    assert parse_pnc_statement(COMMERCIAL_DOC) is not None


def test_the_summary_grid_is_found_with_neither_of_the_old_two_terminators():
    """This skin prints no `Activity Detail` and no overdraft summary anywhere,
    so the block had no end and the four columns were never read."""
    assert "Activity Detail" not in COMMERCIAL_DOC
    assert "Overdraft and Returned Item Fee Summary" not in COMMERCIAL_DOC
    stmt = parse_pnc_statement(COMMERCIAL_DOC)
    assert (stmt.beginning_balance, stmt.stated_total_credits,
            stmt.stated_total_debits, stmt.ending_balance) == (
        1000.00, 500.00, 300.00, 1200.00)


def test_negative_a_summary_the_block_bound_cannot_reach_is_not_taken_from_below():
    """A figure the reader cannot read WHOLE leaves the grid's row a column
    short, and the row is read where it stands rather than replaced."""
    doc = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY,
                     summary="Ending balance 1 0000.00 500.00 300.00 1,200.00")
    assert parse_pnc_statement(doc) is None


def test_negative_the_summary_block_ends_where_the_next_block_starts():
    """The bound, on its own terms. With the grid's row printing only three
    columns, the index below it prints four figures on one line — and the
    reader must come up a column short rather than walk on and read the index
    as the summary. Said of `_summary_amounts` because the identities further
    down would refuse the document either way, and this is the refusal that has
    to happen HERE: a summary taken from the index would be four plausible
    figures, none of them a balance."""
    from analysis.pnc import _summary_amounts

    doc = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY,
                     summary="Ending balance 1,000.00 500.00 300.00")
    assert _summary_amounts(doc) is None


# ---------------------------------------------------------------------------
# The consumer skin: a prose restatement and the first row on the heading line.
# ---------------------------------------------------------------------------

CONSUMER_DOC = (
    "Virtual Wallet With Performance Spend Statement\n"
    "PNC Bank\n"
    "Primary account number: XX-XXXX-0000\n"
    "For the period 04/01/2054 to 04/30/2054\n"
    "Balance Summary\n"
    "Beginning balance\n"
    "Ending balance 1,000.00 500.00 300.00 1,200.00\n"
    "Deposits and other additions\n"
    "Checks and other deductions\n"
    "Average monthly balance\n"
    "Charges and fees 900.00 .00\n"
    "Transaction Summary\n"
    "Checks paid/withdrawals\n"
    "Overdraft and Returned Item Fee Summary\n"
    "Total Overdraft Fees .00 .00\n"
    "Activity Detail\n"
    "Deposits and Other Additions There were 1 Deposits and Other Additions "
    "totaling $500.00. Date Amount Description 04/02 500.00 A Deposit\n"
    "Other Deductions There were 1 Other Deductions totaling $300.00. "
    "Date Amount Description\n"
    "04/30 300.00 A Monthly Service Charge\n"
    "Daily Balance Detail\n"
    "Date Balance Date Balance 04/02 1,500.00 04/30 1,200.00\n"
)


def test_the_consumer_skin_itemizes_under_the_direction_heading_itself():
    """There is no sub-section: the umbrella IS the section, and its first row
    is printed on its own heading line after the restatement sentence and the
    column header."""
    stmt = parse_pnc_statement(CONSUMER_DOC)
    assert stmt is not None
    assert amounts(stmt) == [-300.00, 500.00]
    assert stmt.account_name == "Virtual Wallet With Performance Spend"


def test_the_consumer_skin_needs_no_debit_umbrella_to_sign_its_deductions():
    """It prints none — the deduction sections simply follow the additions —
    so the direction in force is the last one the paper stated, whichever kind
    of heading stated it."""
    assert "Checks and Other Deductions" not in CONSUMER_DOC
    stmt = parse_pnc_statement(CONSUMER_DOC)
    assert [t.direction for t in stmt.transactions] == ["debit", "credit"]


def test_the_consumer_skins_average_is_read_under_its_own_label():
    stmt = parse_pnc_statement(CONSUMER_DOC)
    assert stmt.stated_average_balance == 900.00
    assert stmt.bank_reported_average_label == "Average monthly balance"


# ---------------------------------------------------------------------------
# The treasury skin, and the product name a statement titles itself with.
# ---------------------------------------------------------------------------

TREASURY_DOC = (
    "PO Box 609 Pittsburgh, PA  15230-9738 Treasury Enterprise Plan\n"
    "PNC Bank\n"
    "For the Period 04/01/2054 to 04/30/2054 Primary Account Number: XX-XXXX-0000\n"
    "Balance Summary\n"
    "Beginning\n"
    "Ending balance 1,000.00 500.00 300.00 1,200.00\n"
    "Deposits and other additions\n"
    "Checks and other\n"
    "balance\n"
    "deductions\n"
    "Average ledger\n"
    "Average collected\n"
    "balance 900.00 900.00\n"
    "balance\n"
    "Deposits and Other Additions\n"
    "Checks and Other Deductions\n"
    "Description Items Amount Deposits 1 500.00\n"
    "Description Items Amount Other Deductions 1 300.00\n"
    "Total 1 500.00 Total 1 300.00\n"
    "Daily Balance\n"
    "Date Ledger balance 04/02 1,500.00 04/30 1,200.00\n"
    "Activity Detail\n"
    "Deposits and Other Additions\n"
    "Deposits\n"
    f"{DESCRIBED_HEADER}"
    "04/02 500.00 Deposit 000000001\n"
    "Checks and Other Deductions\n"
    "Other Deductions\n"
    f"{DESCRIBED_HEADER}"
    "04/30 300.00 An Online Transfer 000000002\n"
    "Business Checking - Maintenance Fee Relationship Pricing\n"
)


def test_the_treasury_skin_is_read_and_titles_itself():
    stmt = parse_pnc_statement(TREASURY_DOC)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]


def test_the_product_is_the_title_and_not_a_product_named_further_down():
    """A treasury statement also prints `Business Checking` in the
    relationship-pricing table that names the OTHER accounts the balance
    requirement was met against. Publishing that as this account's product is
    what the earliest-name rule prevents."""
    assert "Business Checking" in TREASURY_DOC
    assert parse_pnc_statement(TREASURY_DOC).account_name == "Treasury Enterprise Plan"


# ---------------------------------------------------------------------------
# A control byte where the continuation heading's column gap belongs.
# ---------------------------------------------------------------------------

def _split_over_two_pages(separator: str) -> str:
    return commercial(
        index=(
            "Description Items Amount Deposits 2 800.00\n"
            "Description Items Amount ACH Debits 1 300.00 Total 2 800.00 Total 1 300.00\n"
        ),
        ladder="04/02 1,500.00 04/03 1,800.00 04/30 1,500.00",
        summary="Ending balance 1,000.00 800.00 300.00 1,500.00",
        activity=(
            "Deposits and Other Credits\n"
            "Deposits 2 transactions for a total of $800.00\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Deposits continued on next page\n"
            "\n--- Page 2 ---\n\n"
            "PNC Core Commercial Checking Account Statement\n"
            f"Deposits{separator}- continued 2 transactions for a total of $800.00\n"
            f"{DESCRIBED_HEADER}"
            "04/03 300.00 Deposit 000000002\n"
            "Checks and Other Debits\n"
            "ACH Debits 1 transaction for a total of $300.00\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 An ACH Debit 000000003\n"
        ),
    )


def test_a_continuation_heading_separated_by_a_control_byte_still_opens_the_section():
    """The whole second page of that section is the stake: `\\s` does not match
    a C0 control byte, so the heading was not a heading and its rows belonged
    to no section at all."""
    doc = _split_over_two_pages("\x00")
    assert "\x00" in doc
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, 300.00, -300.00]


def test_the_same_document_with_an_ordinary_space_reads_identically():
    """The control byte is the only difference between the two, so the reader's
    answer must be the only thing that does not differ."""
    plain = parse_pnc_statement(_split_over_two_pages(" "))
    control = parse_pnc_statement(_split_over_two_pages("\x00"))
    assert plain is not None and control is not None
    assert amounts(plain) == amounts(control)
    assert dates(plain) == dates(control)


def test_negative_a_dropped_continuation_page_is_refused_rather_than_published_short():
    """What the identity is FOR. Take the same statement and delete the second
    page's rows: the index still says two, the reader captures one, and the
    document declines instead of publishing a ledger the bank's own index
    contradicts."""
    doc = _split_over_two_pages("\x00").replace(
        "04/03 300.00 Deposit 000000002\n", "")
    assert parse_pnc_statement(doc) is None


# ---------------------------------------------------------------------------
# The printed index as an identity.
# ---------------------------------------------------------------------------

def test_negative_a_section_the_index_does_not_print_is_refused():
    """Rows in an unindexed section are rows the bank did not say were there.
    Measured in the archive on one document, which publishes a whole wire
    section its own index and its own printed totals both exclude."""
    doc = commercial(
        index=COMMERCIAL_INDEX,
        activity=COMMERCIAL_ACTIVITY + (
            "Other Deductions\n"
            f"{DESCRIBED_HEADER}"
            "04/29 100.00 An unindexed deduction 000000004\n"
        ),
    )
    assert parse_pnc_statement(doc) is None


def test_negative_a_section_read_LONG_is_refused_as_readily_as_one_read_short():
    """A row read twice is as wrong as a row not read, and only the count sees
    it: both readings can reproduce the same section total."""
    doc = commercial(
        index=COMMERCIAL_INDEX,
        activity=COMMERCIAL_ACTIVITY.replace(
            "04/02 500.00 Deposit 000000001\n",
            "04/02 250.00 Deposit 000000001 04/02 250.00 Deposit 000000001\n"),
    )
    assert parse_pnc_statement(doc) is None


def test_negative_two_index_entries_that_contradict_each_other_are_both_applied():
    """A section indexed twice with two different counts cannot be satisfied by
    any capture, which is the fail-closed reading of a bank contradicting
    itself — rather than silently keeping whichever was read last."""
    doc = commercial(
        index=COMMERCIAL_INDEX,
        activity=COMMERCIAL_ACTIVITY.replace(
            "Deposits 1 transaction for a total of $500.00",
            "Deposits 2 transactions for a total of $500.00"),
    )
    assert parse_pnc_statement(doc) is None


def test_the_index_and_the_detail_heading_may_spell_one_section_differently():
    """`Funds Transfers In` in the index, `Funds Transfer In` over the rows."""
    doc = commercial(
        index=("Description Items Amount Funds Transfers In 1 500.00\n"
               "Description Items Amount ACH Debits 1 300.00 "
               "Total 1 500.00 Total 1 300.00\n"),
        activity=(
            "Deposits and Other Credits\n"
            "Funds Transfer In 1 transaction for a total of $500.00\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Domestic Incoming Wire 000000001\n"
            "Checks and Other Debits\n"
            "ACH Debits 1 transaction for a total of $300.00\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 An ACH Debit 000000002\n"
        ),
    )
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [500.00, -300.00]


# ---------------------------------------------------------------------------
# The printed ladder as an identity — the only control that sees a wrong DAY.
# ---------------------------------------------------------------------------

def test_negative_a_row_on_the_wrong_day_is_refused_by_the_ladder_alone():
    """The row's own posting date is printed first and a merchant's note date
    follows it inside the description — the ordering the archive does not use,
    and the one that moves a row when the wrong token is read as its date.

    The count is unchanged, the section total is unchanged and the summary
    still closes, so the index and the Balance Summary are both blind to it.
    The ladder is not: the ledger walked against it disagrees on the day the
    row left and on every day up to the one it landed on."""
    moved = commercial(
        index=COMMERCIAL_INDEX,
        activity=COMMERCIAL_ACTIVITY.replace(
            "04/02 500.00 Deposit 000000001", "04/20 500.00 Deposit 000000001"),
    )
    assert parse_pnc_statement(moved) is None
    # the same document with the row on the day the ladder prints it publishes
    assert parse_pnc_statement(COMMERCIAL_DOC) is not None


def test_negative_a_ladder_cell_outside_the_printed_period_fails_the_document():
    """A ladder day the period does not contain is a page from another
    statement. Measured in the archive on one document, whose ladder belongs to
    a different month of the same account."""
    doc = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY,
                     ladder="04/02 1,500.00 05/30 1,200.00")
    assert parse_pnc_statement(doc) is None


def test_negative_a_ladder_that_prints_one_day_twice_with_two_balances_is_refused():
    doc = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY,
                     ladder="04/02 1,500.00 04/30 1,200.00 04/30 1,100.00")
    assert parse_pnc_statement(doc) is None


def test_a_ladder_reprinting_the_opening_day_is_admitted_against_the_walk():
    """PNC prints a cell for the period's first day even when nothing posted on
    it — the opening balance, printed a second time — and the walk carries the
    opening forward to meet it."""
    doc = commercial(index=COMMERCIAL_INDEX, activity=COMMERCIAL_ACTIVITY,
                     ladder="04/01 1,000.00 04/02 1,500.00 04/30 1,200.00")
    stmt = parse_pnc_statement(doc)
    assert stmt is not None
    assert [entry.date for entry in stmt.stated_daily_balances] == [
        "2054-04-01", "2054-04-02", "2054-04-30"]


def test_the_published_ladder_can_never_move_a_reconstructed_balance():
    """The property that makes publishing it safe, said as a test: the reader
    declines unless every printed cell already equals the day the ledger walks
    to, so the ladder the platform overrides with is the ladder it already had."""
    from analysis.adb import compute_average_daily_balance

    stmt = parse_pnc_statement(COMMERCIAL_DOC)
    published = {entry.date: entry.balance for entry in stmt.stated_daily_balances}
    stmt.stated_daily_balances = []
    walked = {entry.date: entry.ending_balance
              for entry in compute_average_daily_balance(stmt).daily_balances}
    assert published and all(walked[day] == balance for day, balance in published.items())


# ---------------------------------------------------------------------------
# A category the bank prints on BOTH sides of its index.
# ---------------------------------------------------------------------------

def _both_sided_under(group: str) -> str:
    sign_index = ("Description Items Amount Deposits 1 500.00 Trade Services 0 .00\n"
                  "Description Items Amount Trade Services 1 300.00 "
                  "Total 1 500.00 Total 1 300.00\n") if group == "Checks and Other Debits" else (
                  "Description Items Amount Trade Services 1 500.00\n"
                  "Description Items Amount ACH Debits 1 300.00 "
                  "Total 1 500.00 Total 1 300.00\n")
    if group == "Checks and Other Debits":
        activity = (
            "Deposits and Other Credits\n"
            "Deposits 1 transaction for a total of $500.00\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 Deposit 000000001\n"
            "Checks and Other Debits\n"
            "Trade Services 1 transaction for a total of $300.00\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 A Trade Services item 000000002\n"
        )
    else:
        activity = (
            "Deposits and Other Credits\n"
            "Trade Services 1 transaction for a total of $500.00\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 A Trade Services item 000000001\n"
            "Checks and Other Debits\n"
            "ACH Debits 1 transaction for a total of $300.00\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 An ACH Debit 000000002\n"
        )
    return commercial(index=sign_index, activity=activity)


def test_a_both_sided_category_takes_the_direction_of_the_group_above_it():
    debit = parse_pnc_statement(_both_sided_under("Checks and Other Debits"))
    credit = parse_pnc_statement(_both_sided_under("Deposits and Other Credits"))
    assert debit is not None and credit is not None
    assert sorted(amounts(debit)) == sorted(amounts(credit)) == [-300.00, 500.00]
    def both_sided(stmt) -> list[float]:
        return [t.amount for t in stmt.transactions
                if t.description.startswith("A Trade Services")]

    assert both_sided(debit) == [-300.00]
    assert both_sided(credit) == [500.00]


def test_negative_a_both_sided_category_with_no_direction_printed_is_declined():
    """The name is a credit category and a debit category on the same page, so
    with nothing above it the paper has not said which way the money moved —
    and a guess would sign a whole section wrongly."""
    doc = commercial(
        index=("Description Items Amount Trade Services 1 500.00\n"
               "Description Items Amount ACH Debits 1 300.00 "
               "Total 1 500.00 Total 1 300.00\n"),
        activity=(
            "Trade Services 1 transaction for a total of $500.00\n"
            f"{DESCRIBED_HEADER}"
            "04/02 500.00 A Trade Services item 000000001\n"
            "Checks and Other Debits\n"
            "ACH Debits 1 transaction for a total of $300.00\n"
            f"{DESCRIBED_HEADER}"
            "04/30 300.00 An ACH Debit 000000002\n"
        ),
    )
    assert parse_pnc_statement(doc) is None


# ---------------------------------------------------------------------------
# Detection stays as narrow as what the reader can name.
# ---------------------------------------------------------------------------

def test_negative_a_pnc_product_this_reader_cannot_name_is_left_unclaimed():
    """Detection reads the same list `account_name` comes from, so a fifth skin
    is unclaimed rather than published under a guessed product."""
    from analysis.pnc import detect

    doc = COMMERCIAL_DOC.replace("PNC Core Commercial Checking Account Statement",
                                 "Virtual Wallet With Performance Select Statement")
    assert not detect(doc).claims
    assert parse_pnc_statement(doc) is None
