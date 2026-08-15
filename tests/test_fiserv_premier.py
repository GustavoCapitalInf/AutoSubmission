"""The Fiserv Premier parenthesised-counts issue (W3 §UNID-B, card 2).

Every fixture is synthetic; no customer, account, date or amount from the
archive appears here. The bank names used are deliberately impossible ones.

The first group of tests is the **anti-collision** contract, and it is the
reason this registration exists in the shape it does. Fiserv Premier is a
platform: the same template is printed by many issuers, three of which already
have their own registration. Detection therefore has to be narrow in two
different directions at once — away from Wells Fargo (whose summary yields a
false positive to the obvious counts clause) and away from the leading-counts
issue those three parsers read.
"""
from __future__ import annotations

from analysis.fiserv_premier import detect, parse_fiserv_premier_statement

RETURN_ADDRESS = "PO Box 1 Springfield, ZZ 00000"
DIRECTORY = (
    "Example Bank PO Box 1 Springfield, ZZ 00000 www.example-bank.com 000-000-0000 "
    "Second Example Bank PO Box 2 Shelbyville, ZZ 00001 www.second-example.com 000-000-0001"
)
HEAD = (
    f"{RETURN_ADDRESS}\n"
    "Customer Service: Website:\n"
    "000-000-0000 www.example-bank.com\n"
    "Statement of Account\n"
    "Account Title: SYNTHETIC HOLDINGS LLC\n"
    "Statement Dates 3/01/26 to 3/31/26 (31 days)\n"
    "SYNTHETIC BUSINESS CHECKING - XXXXXX0000"
)
SUMMARY = (
    "Previous Balance $100.00 Average Ledger $150.00 "
    "Deposits/Credits (1) $50.00 Average Collected $150.00 "
    "Checks/Debits (2) $30.00 Service Charge $0.00 "
    "Interest Paid $0.00 Ending Balance $120.00"
)


def activity_document(*, summary: str = SUMMARY, rows: str | None = None, tail: str = "") -> str:
    rows = rows if rows is not None else (
        "3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
        "3/03 SYNTHETIC CREDIT $50.00 $140.00\n"
        "3/04 SYNTHETIC DEBIT TWO -$20.00 $120.00"
    )
    return (
        "--- Page 1 ---\n\n"
        f"{HEAD}\n{summary}\n"
        "Transaction Activity Date Description Debits Credits Balance\n"
        f"{rows}\n{tail}\n"
        "--- Page 2 ---\n\n"
        f"{DIRECTORY}\n"
    )


def split_document(*, credits: str | None = None, debits: str | None = None) -> str:
    credits = credits if credits is not None else "3/03 SYNTHETIC CREDIT $50.00"
    debits = debits if debits is not None else (
        "3/02 SYNTHETIC DEBIT ONE $10.00 3/04 SYNTHETIC DEBIT TWO $20.00"
    )
    return (
        "--- Page 1 ---\n\n"
        f"{HEAD}\n{SUMMARY}\n"
        f"Credit Transactions Date Description Amount\n{credits}\n"
        f"Debit Transactions Date Description Amount\n{debits}\n"
        "--- Page 2 ---\n\n"
        f"{DIRECTORY}\n"
    )


# ===========================================================================
# The anti-collision contract
# ===========================================================================

#: The shape that makes the counts clause unusable on its own. A Wells Fargo
#: account summary prints the opening balance immediately to the left of the
#: `Deposits/Credits` label, and PDF flattening leaves the two on one line — so
#: `\d+\s+Deposits/Credits` matches the last digits of the BALANCE, not a count.
WELLS_SHAPED_SUMMARY = (
    "Beginning balance on 3/1 5,000.00 Deposits/Credits 12,345.67 "
    "Withdrawals/Debits 8,000.00 Ending balance on 3/31 9,345.67"
)


def test_the_wells_shaped_summary_is_not_claimed():
    """The measured collision: the loose counts clause reached 216 of the 236
    Wells Fargo documents in the stratified probe. The opening-balance clause
    is what keeps this registration off every one of them."""
    document = f"--- Page 1 ---\n\nWELLS FARGO\nStatement of Account\n{WELLS_SHAPED_SUMMARY}\n"
    assert not detect(document).claims


def test_every_marker_is_load_bearing():
    """Drop any one of the three and the registration must stop claiming;
    that is what makes each of them `required` rather than corroborating."""
    whole = activity_document()
    assert detect(whole).claims
    for removed in ("Statement of Account", "Previous Balance", "Deposits/Credits (1)"):
        assert not detect(whole.replace(removed, "")).claims, removed


def test_the_leading_counts_issue_is_not_claimed():
    """The issue `linkbank`, `capital_one` and `farmers_merchants` read prints
    its counts in front of the label and without parentheses. Registering that
    shape here would make every one of their documents ambiguous."""
    leading = (
        "--- Page 1 ---\n\nStatement of Account\n"
        "Account Number XXXXXXXXXXXX0000 Statement Dates 3/01/26 thru 3/31/26 "
        "Previous Balance 100.00 Days in the Statement Period 31 "
        "1 Deposits/Credits 50.00 Average Ledger 150.00 "
        "2 Checks/Debits 30.00 Average Collected 150.00\n"
    )
    assert not detect(leading).claims


def test_detection_ignores_the_source_filename_comment():
    plain = activity_document()
    renamed = "<!-- SOURCE: fiserv premier statement.pdf -->\n" + plain
    assert detect(plain).score == detect(renamed).score


def test_a_header_with_no_ledger_is_not_a_statement():
    header_only = f"--- Page 1 ---\n\n{HEAD}\n{SUMMARY}\n--- Page 2 ---\n\n{DIRECTORY}\n"
    assert detect(header_only).claims
    assert parse_fiserv_premier_statement(header_only) is None


# ===========================================================================
# The issuer is read off the document
# ===========================================================================

def test_the_issuer_is_recovered_from_the_disclosure_directory():
    stmt = parse_fiserv_premier_statement(activity_document())
    assert stmt is not None
    assert stmt.bank == "Example Bank"
    assert stmt.account_number == "XXXXXX0000"
    assert stmt.account_name == "SYNTHETIC BUSINESS CHECKING"


def test_a_document_whose_directory_names_no_division_publishes_no_bank():
    """This parser will not name a bank the page does not name — and an
    un-named issuer is not a reason to throw the arithmetic away. The statement
    is published with `bank=None`, which is what the page supports."""
    stmt = parse_fiserv_premier_statement(activity_document().replace(DIRECTORY, ""))
    assert stmt is not None
    assert stmt.bank is None
    assert stmt.ending_balance == 120.00


def test_two_corroborated_divisions_sharing_a_return_address_publish_no_bank():
    """Both names spell the same domain, so the document supports neither over
    the other and the parser declines to choose."""
    ambiguous = activity_document().replace(
        DIRECTORY,
        DIRECTORY + " Example Bank Of Springfield PO Box 1 Springfield, ZZ 00000",
    )
    stmt = parse_fiserv_premier_statement(ambiguous)
    assert stmt is not None
    assert stmt.bank is None


def test_repeated_glyph_furniture_is_not_mistaken_for_a_division_name():
    # Only the page-one printing: the directory's copy is what the issuer is
    # read out of, and this fixture is about the furniture in front of the
    # statement's own return address.
    noisy = activity_document().replace(
        RETURN_ADDRESS, f"AAAAAAAAAAAAAAAAAAAAAA\n{RETURN_ADDRESS}", 1
    )
    stmt = parse_fiserv_premier_statement(noisy)
    assert stmt is not None
    assert stmt.bank == "Example Bank"


# --- D1: a capitalized run in front of an address is not an identity --------

#: The three shapes a real issuer of this platform uses to name itself, and the
#: three shapes that merely look like it. Reported by Ocean's adversarial review
#: (§UNID-B RC-D1) after the first version of `_issuer` published all six.
GENUINE = {
    # the domain's label is inside the name
    "Alta Example Bank": "www.altaexample.com",
    # the Regulation E notice names the bank in front of the same address
    "Chesterfield Example Bank": "chesterfield.bank",
}


def named_document(name: str, domain: str, *, in_directory: bool = True) -> str:
    directory = (
        f"{name} {RETURN_ADDRESS} {domain} 000-000-0000" if in_directory
        else f"If you think your statement is wrong write us at {name} {RETURN_ADDRESS}."
    )
    return (
        "--- Page 1 ---\n\n"
        f"{RETURN_ADDRESS}\nCustomer Service: Website:\n000-000-0000 {domain}\n"
        "Statement of Account\nAccount Title: SYNTHETIC HOLDINGS LLC\n"
        "Statement Dates 3/01/26 to 3/31/26 (31 days)\n"
        "SYNTHETIC BUSINESS CHECKING - XXXXXX0000\n"
        f"{SUMMARY}\n"
        "Transaction Activity Date Description Debits Credits Balance\n"
        "3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
        "3/03 SYNTHETIC CREDIT $50.00 $140.00\n"
        "3/04 SYNTHETIC DEBIT TWO -$20.00 $120.00\n"
        "--- Page 2 ---\n\n"
        f"{directory}\n"
    )


def test_an_issuer_whose_name_carries_the_documents_own_domain_publishes():
    for name, domain in GENUINE.items():
        stmt = parse_fiserv_premier_statement(named_document(name, domain))
        assert stmt is not None and stmt.bank == name, name


def test_an_issuer_named_only_in_the_regulation_e_notice_publishes():
    """`ches.bank` / "Chesapeake Bank" in the archive: the bank names itself
    nowhere but the error-resolution notice, and the domain corroborates it."""
    stmt = parse_fiserv_premier_statement(
        named_document("Chesterfield Example Bank", "chesterfield.bank", in_directory=False)
    )
    assert stmt is not None
    assert stmt.bank == "Chesterfield Example Bank"


def test_an_issuer_named_only_beside_the_domain_in_the_directory_publishes():
    """The archive's third shape: an abbreviated domain that is no part of the
    name, corroborated instead by sitting in the same directory row."""
    stmt = parse_fiserv_premier_statement(
        named_document("First Example Bank of Springfield", "www.febspr.com")
    )
    assert stmt is not None
    assert stmt.bank == "First Example Bank of Springfield"


def test_boilerplate_in_front_of_the_return_address_is_not_an_identity():
    """The finding that reopened this function. Each of these is a capitalized
    run immediately in front of the statement's own return address, and none of
    them is a bank; the first version of `_issuer` published all three."""
    for impostor in (
        "Member FDIC Equal Housing Lender",
        "Notices to Smith and Jones LLP",
        "Please Remit Payment To",
    ):
        stmt = parse_fiserv_premier_statement(
            named_document(impostor, "www.altaexample.com")
        )
        assert stmt is not None, impostor
        assert stmt.bank is None, impostor


# ===========================================================================
# The summary, and the gates on the rows
# ===========================================================================

def test_reads_the_summary_and_both_counts():
    stmt = parse_fiserv_premier_statement(activity_document())
    assert stmt is not None
    assert stmt.period_start == "2026-03-01"
    assert stmt.period_end == "2026-03-31"
    assert stmt.days_in_period == 31
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == 120.00
    assert stmt.stated_total_credits == 50.00
    assert stmt.stated_total_debits == 30.00
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 2
    assert stmt.stated_average_balance == 150.00


def test_a_summary_that_does_not_close_is_refused():
    assert parse_fiserv_premier_statement(activity_document(
        summary=SUMMARY.replace("Ending Balance $120.00", "Ending Balance $121.00")
    )) is None


def test_the_service_charge_and_interest_clauses_are_optional():
    """The other printing of this summary omits both, and closes without
    them."""
    lean = (
        "Previous Balance $100.00 Deposits/Credits (1) $50.00 "
        "Checks/Debits (2) $30.00 Current Balance $120.00"
    )
    stmt = parse_fiserv_premier_statement(activity_document(summary=lean))
    assert stmt is not None
    assert stmt.stated_service_charge == 0.0
    assert stmt.stated_average_balance is None


def test_a_row_that_breaks_the_running_balance_chain_is_refused():
    assert parse_fiserv_premier_statement(activity_document(
        rows=(
            "3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
            "3/03 SYNTHETIC CREDIT $50.00 $141.00\n"
            "3/04 SYNTHETIC DEBIT TWO -$20.00 $120.00"
        )
    )) is None


# --- D2: a zero-amount row has no sign to read a direction from -------------

def test_a_zero_amount_row_in_the_running_grid_is_refused():
    """Ocean's four-row shape (§UNID-B RC-D2). The grid prints its amount in a
    Debits or a Credits column, and the flattened text layer has destroyed
    which — so a `$0.00` posting carries no direction at all. Partitioning by
    sign used to drop it out of both counts while it rode along in the ledger,
    so a four-row document passed a three-row count check."""
    hidden = parse_fiserv_premier_statement(activity_document(
        summary=(
            "Previous Balance $100.00 Average Ledger $150.00 "
            "Deposits/Credits (1) $50.00 Average Collected $150.00 "
            "Checks/Debits (2) $30.00 Service Charge $0.00 "
            "Interest Paid $0.00 Ending Balance $120.00"
        ),
        rows=(
            "3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
            "3/03 SYNTHETIC CREDIT $50.00 $140.00\n"
            "3/03 SYNTHETIC ZERO ADJUSTMENT $0.00 $140.00\n"
            "3/04 SYNTHETIC DEBIT TWO -$20.00 $120.00"
        ),
    ))
    assert hidden is None


def test_a_zero_amount_row_in_a_split_section_keeps_its_sections_direction():
    """Where the section heading fixes the direction there is nothing to guess,
    so the row is kept — and counted, which is the property that matters."""
    stmt = parse_fiserv_premier_statement(split_document(
        credits="3/03 SYNTHETIC CREDIT $50.00 3/05 SYNTHETIC ZERO CREDIT $0.00",
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 SYNTHETIC DEBIT TWO $20.00",
    ))
    assert stmt is None  # the printed count says 1 credit; the section prints 2

    counted = parse_fiserv_premier_statement(split_document(
        credits="3/03 SYNTHETIC CREDIT $50.00 3/05 SYNTHETIC ZERO CREDIT $0.00",
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 SYNTHETIC DEBIT TWO $20.00",
    ).replace("Deposits/Credits (1)", "Deposits/Credits (2)"))
    assert counted is not None
    zero = [t for t in counted.transactions if t.amount == 0]
    assert len(zero) == 1
    assert zero[0].direction == "credit"


def test_rows_that_do_not_match_the_printed_counts_are_refused():
    assert parse_fiserv_premier_statement(activity_document(
        rows=("3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
              "3/03 SYNTHETIC CREDIT $50.00 $140.00")
    )) is None


def test_a_chain_that_does_not_reach_the_closing_balance_is_refused():
    assert parse_fiserv_premier_statement(activity_document(
        summary=SUMMARY.replace("Checks/Debits (2) $30.00", "Checks/Debits (1) $10.00")
                       .replace("Ending Balance $120.00", "Ending Balance $140.00"),
        rows=("3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
              "3/03 SYNTHETIC CREDIT $50.00 $140.00\n"
              "3/04 SYNTHETIC DEBIT TWO -$20.00 $120.00"),
    )) is None


# ===========================================================================
# The split-section ledger
# ===========================================================================

def test_reads_separate_credit_and_debit_sections():
    stmt = parse_fiserv_premier_statement(split_document())
    assert stmt is not None
    assert len(stmt.transactions) == 3
    assert sum(t.amount for t in stmt.transactions if t.amount > 0) == 50.00
    assert sum(-t.amount for t in stmt.transactions if t.amount < 0) == 30.00
    assert all(t.running_balance is None for t in stmt.transactions)


def test_a_cheque_drawn_without_a_number_prints_as_a_bare_date_and_amount():
    stmt = parse_fiserv_premier_statement(split_document(
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 SUMMARY BY CHECK NUMBER Date Check No Amount 3/04 $20.00"
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 3
    assert sum(-t.amount for t in stmt.transactions if t.amount < 0) == 30.00


def test_the_daily_balance_recap_terminates_the_ledger():
    """The recap is printed inside the debit section and its pairs are
    row-shaped; read as postings they would double-count the whole month."""
    stmt = parse_fiserv_premier_statement(split_document(
        debits=(
            "3/02 SYNTHETIC DEBIT ONE $10.00 3/04 SYNTHETIC DEBIT TWO $20.00 "
            "Daily Balance Date Amount 3/02 $90.00 3/03 $140.00 3/04 $120.00"
        )
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 3


def test_two_ledger_shapes_in_one_document_are_refused():
    both = split_document().replace(
        "Credit Transactions Date Description Amount",
        "Transaction Activity Date Description Debits Credits Balance\n"
        "3/02 SYNTHETIC DEBIT ONE -$10.00 $90.00\n"
        "Credit Transactions Date Description Amount",
    )
    assert parse_fiserv_premier_statement(both) is None


def test_a_document_with_no_ledger_section_at_all_is_refused():
    assert parse_fiserv_premier_statement(
        activity_document().replace(
            "Transaction Activity Date Description Debits Credits Balance", ""
        )
    ) is None


# ===========================================================================
# The third printed issue: claimed, and refused twice over (W3 §FISERVISS)
# ===========================================================================

#: The summary strip as the third issue prints it: the same clauses the two read
#: issues print, minus the optional ones (`Average Ledger`, `Average Collected`,
#: the two fee terms) and with the closing figure under the `Current Balance`
#: wording. Every one of this registration's three required markers is in it,
#: which is why these documents are claimed and not merely ignored.
ISSUE_THREE_SUMMARY = (
    "Previous Balance $100.00 Deposits/Credits (1) $50.00 "
    "Checks/Debits (2) $30.00 Current Balance $120.00"
)
#: The period, printed as two facts in two places instead of one clause.
ISSUE_THREE_PERIOD = "Statement of Account March 01, 2026 thru March 31, 2026"
#: The registered wording, for the one-repair variant below.
READ_PERIOD = "Statement of Account\nStatement Dates 3/01/26 to 3/31/26 (31 days)"
ISSUE_THREE_CREDIT_HEAD = "Deposits Date Description Amount"
ISSUE_THREE_DEBIT_HEAD = "Debits Date Description Amount $"


def issue_three_document() -> str:
    """The third issue's furniture over an otherwise sound document.

    Everything this registration DOES read is deliberately intact and correct:
    the three detection markers fire, the summary parses, and its identity
    closes ($100.00 + $50.00 − $30.00 = $120.00). What differs is only the
    period wording and the section vocabulary — so a refusal here can only come
    from those two.
    """
    return (
        "--- Page 1 ---\n\n"
        f"{RETURN_ADDRESS}\n"
        "Managing Your Accounts Branch Name Synthetic Customer Service 000-000-0000\n"
        "Address 1 Example Street Springfield, ZZ 00000 "
        "Online Access www.example-bank.com\n"
        f"{ISSUE_THREE_PERIOD}\n"
        "SYNTHETIC BUSINESS CHECKING ACCOUNT XXXXXX0000\n"
        f"{ISSUE_THREE_SUMMARY}\n"
        "Activity Summary Days in the Statement Period:  31\n"
        f"{ISSUE_THREE_CREDIT_HEAD}\n"
        "3/03 SYNTHETIC DEPOSIT $50.00\n"
        f"{ISSUE_THREE_DEBIT_HEAD}\n"
        "3/02 SYNTHETIC DEBIT ONE $10.00 3/04 SYNTHETIC DEBIT TWO $20.00\n"
        "--- Page 2 ---\n\n"
        f"{DIRECTORY}\n"
    )


def _read_sections(document: str) -> str:
    return document.replace(
        ISSUE_THREE_CREDIT_HEAD, "Credit Transactions Date Description Amount"
    ).replace(ISSUE_THREE_DEBIT_HEAD, "Debit Transactions Date Description Amount")


def test_the_third_printed_issue_is_claimed_and_refused_twice_over():
    """The refusal is OVER-DETERMINED, and both halves are load-bearing.

    Repairing either one alone still refuses; repairing both publishes. That
    last assertion is what stops this test being vacuous — it proves the
    fixture is sound everywhere else, so the two named wordings really are the
    whole of what blocks this issue, and neither is a missing fact: the
    document prints its period and its ledger, in vocabularies no clause of
    this module matches.
    """
    document = issue_three_document()
    assert detect(document).claims, "the summary strip is the same; it must claim"
    assert parse_fiserv_premier_statement(document) is None

    period_only = document.replace(ISSUE_THREE_PERIOD, READ_PERIOD)
    assert parse_fiserv_premier_statement(period_only) is None, "sections still unread"

    sections_only = _read_sections(document)
    assert parse_fiserv_premier_statement(sections_only) is None, "period still unread"

    both = _read_sections(document.replace(ISSUE_THREE_PERIOD, READ_PERIOD))
    statement = parse_fiserv_premier_statement(both)
    assert statement is not None
    assert len(statement.transactions) == 3
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 120.00


def test_the_third_issues_unnamed_issuer_is_not_what_refuses_it():
    """All four archive documents of this issue print a web address and no bank
    name, so `_issuer` returns None — the `bank=None` path, which costs a label
    and not a document. Pinned here because the card that produced this test
    was written on the belief that the missing issuer was the refusal."""
    anonymous = _read_sections(
        issue_three_document().replace(ISSUE_THREE_PERIOD, READ_PERIOD)
    ).replace(DIRECTORY, "")
    statement = parse_fiserv_premier_statement(anonymous)
    assert statement is not None
    assert statement.bank is None
    assert len(statement.transactions) == 3
