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
# The THIRD printed issue: read (W3 §FISERVISS FI2, card FISERV-ISSUE3)
#
# Four archive documents print this issue. Before this cell they were claimed
# and refused twice over — the period in a wording no clause read, and a ledger
# vocabulary no section head matched. Both facts were PRINTED; neither was
# absent. These tests pin the two wordings, the one money-grammar rule the
# ledger needed, and — at more length than anything else here — the refusal
# that rule is built around.
# ===========================================================================

#: The summary strip as the third issue prints it: the same clauses the two read
#: issues print, minus the optional ones (`Average Ledger`, `Average Collected`,
#: the two fee terms) and with the closing figure under the `Current Balance`
#: wording. Every one of this registration's three required markers is in it,
#: which is why these documents are claimed and not merely ignored.
#:
#: $100.00 + $70.00 − $50.00 = $120.00, and the two counts are 2 and 3.
ISSUE_THREE_SUMMARY = (
    "Previous Balance $100.00 Deposits/Credits (2) $70.00 "
    "Checks/Debits (3) $50.00 Current Balance $120.00"
)
#: The period, printed as two facts in two places instead of one clause.
ISSUE_THREE_PERIOD = "Statement of Account March 01, 2026 thru March 31, 2026"
ISSUE_THREE_DAYS = "Activity Summary Days in the Statement Period:  31"
#: The registered wording, for the counterfactuals below.
READ_PERIOD = "Statement of Account\nStatement Dates 3/01/26 to 3/31/26 (31 days)"

#: The attested fee row. The FIRST money token names the item that caused the
#: fee; the row's own amount is the last one. 109 rows of this shape are printed
#: across the four archive documents (34 / 10 / 37 / 28).
FEE_ROW = "3/04 CHK# 00 AMT $10.00, NSF PAID ITEM FEE $31.00"

#: The disclosure page the template prints in the MIDDLE of a section, and the
#: cheque-image page it prints after the ledger has ended. Neither declares a
#: column header; both are outside every section for that reason alone.
DISCLOSURE_PAGE = (
    "PROMPTLY EXAMINE YOUR STATEMENT AND REPORT ANY PROBLEMS.\n"
    "We must hear from you no later than 60 days after we sent you the first "
    "statement on which the error appeared."
)
CHEQUE_IMAGE_PAGE = "3/06/26 101 $9.00"


def issue_three_document(
    *,
    period: str = ISSUE_THREE_PERIOD,
    days: str = ISSUE_THREE_DAYS,
    summary: str = ISSUE_THREE_SUMMARY,
    deposits: str = "3/03 SYNTHETIC DEPOSIT $50.00",
    other_credits: str = "3/05 RETURNED ITEM, INSUFFICIENT FUNDS, SYNTHETIC $20.00",
    debits: str = "3/02 SYNTHETIC DEBIT ONE $10.00 " + FEE_ROW,
    cheques: str = "Date Check No Amount $ 3/06 101 $9.00",
    grid: str = (
        "Date Balance $ 3/02 $90.00 3/03 $140.00 3/04 $109.00 "
        "3/05 $129.00 3/06 $120.00"
    ),
    header: str = "SYNTHETIC BUSINESS CHECKING ACCOUNT XXXXXX0000",
    strip_prefix: str = "SYNTHETIC HOLDINGS LLC XXXXXX0000 ",
) -> str:
    """The third issue's furniture, printed the way the four documents print it.

    Everything is synthetic. The structure is not: the credits arrive in two
    printed sections and the debits in two, one section is interrupted by a
    disclosure page and resumed by the bare column header, the cheque recap is
    posting detail rather than a recap, and the printed daily grid closes on the
    ledger to the cent.
    """
    return (
        "--- Page 1 ---\n\n"
        f"{RETURN_ADDRESS}\n"
        "Managing Your Accounts Branch Name Synthetic Customer Service 000-000-0000\n"
        "Address 1 Example Street Springfield, ZZ 00000 "
        "Online Access www.example-bank.com\n"
        f"{period}\n"
        f"{header}\n"
        f"{strip_prefix}{summary}\n"
        f"{days}\n"
        f"Deposits Date Description Amount\n{deposits}\n"
        f"Other Credits Date Description Amount $\n{other_credits}\n"
        "Page 1 of 4\n"
        "--- Page 2 ---\n\n"
        f"{DISCLOSURE_PAGE}\n"
        "Page 2 of 4\n"
        "--- Page 3 ---\n\n"
        f"Debits Date Description Amount $\n{debits}\n"
        f"Checks Cleared\n{cheques}\n"
        "(*) Indicates a Gap in Check Number Sequence\n"
        "Itemization of Service Charge Paid this Period "
        "TOTAL CHARGE FOR MAINTENANCE FEE: $0.00\n"
        f"Daily Balance Information\n{grid}\n"
        "Overdraft and Returned Item Fees\n"
        "TOTAL OVERDRAFT FEES: $31.00 $31.00\n"
        "Page 3 of 4\n"
        "--- Page 4 ---\n\n"
        f"{CHEQUE_IMAGE_PAGE}\n"
        "Page 4 of 4\n"
    )


def _sides(statement):
    return (
        [t for t in statement.transactions if t.direction == "credit"],
        [t for t in statement.transactions if t.direction == "debit"],
    )


# ---------------------------------------------------------------------------
# What the issue publishes
# ---------------------------------------------------------------------------


def test_the_third_printed_issue_is_read_end_to_end():
    """Both printed causes lifted, under the module's existing oracles.

    The summary identity, the two printed counts, the two printed totals and
    the printed daily grid all gate this — and the fixture's cheque item is
    inside the printed debit count, which is why it is posting detail here and
    not a recap.
    """
    statement = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None
    assert statement.period_start == "2026-03-01"
    assert statement.period_end == "2026-03-31"
    assert statement.days_in_period == 31
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 120.00
    credits, debits = _sides(statement)
    assert [t.amount for t in credits] == [50.00, 20.00]
    assert [t.amount for t in debits] == [-10.00, -31.00, -9.00]
    assert statement.stated_credit_count == 2
    assert statement.stated_debit_count == 3
    assert statement.stated_total_credits == 70.00
    assert statement.stated_total_debits == 50.00


def test_the_third_issue_publishes_no_bank_because_it_prints_none():
    """All four archive documents print a web address under `Online Access` and
    no bank name anywhere — not in the masthead, not beside a return address,
    not in the Regulation E notice, which defers to "the address listed on the
    front of this statement". `bank=None` is therefore what the page supports,
    and the domain alone is never promoted to an identity."""
    statement = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None
    assert statement.bank is None


# ---------------------------------------------------------------------------
# THE REFERENCE-NUMBER REFUSAL
#
# The money-grammar rule this issue needed is "the description may cross a `$`
# where the token is an `AMT`-introduced reference". Relaxing only that much is
# half the rule; the other half is that such a token can NEVER be the row's
# amount. These tests are the second half.
# ---------------------------------------------------------------------------


def test_the_reference_is_read_as_description_and_the_fee_as_the_amount():
    """The attested row: `CHK# 00 AMT $10.00, NSF PAID ITEM FEE $31.00`."""
    statement = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None
    fee = [t for t in statement.transactions if t.description.startswith("CHK#")]
    assert len(fee) == 1
    assert fee[0].amount == -31.00, "the fee, not the item that caused it"
    assert fee[0].description == "CHK# 00 AMT $10.00, NSF PAID ITEM FEE"


def test_the_refusal_does_not_rest_on_the_reference_comma():
    """§FI5.4: the comma is what makes the row FAIL today rather than publish
    `$10.00` as the fee, and it is doing that by accident — `_PLAIN_ROW_RE`'s
    `(?=\\s|$)` lookahead rejects a comma-terminated amount. A rule that read
    the reference only when a comma followed would keep the accident and
    inherit its failure mode. Strip the comma and the reference is still
    refused as an amount, and still read as description."""
    document = issue_three_document(
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 "
               + FEE_ROW.replace("$10.00,", "$10.00")
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    fee = [t for t in statement.transactions if t.description.startswith("CHK#")]
    assert [t.amount for t in fee] == [-31.00]
    assert fee[0].description == "CHK# 00 AMT $10.00 NSF PAID ITEM FEE"


def test_the_refusal_survives_a_double_space_after_the_reference_keyword():
    """This text layer prints double spaces (`Days in the Statement Period:  31`
    on all four documents). A lookbehind anchored to exactly one space would
    step around `AMT  $10.00` and publish the reference as the fee, so the
    section text is whitespace-normalized before the row grammar reads it."""
    document = issue_three_document(
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 " + FEE_ROW.replace("AMT $", "AMT  $")
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert [t.amount for t in _sides(statement)[1]] == [-10.00, -31.00, -9.00]


def test_a_reference_standing_where_the_amount_belongs_refuses_the_document():
    """The failure mode the rule exists to prevent, driven to its end: a row
    whose LAST money token is the `AMT` reference. There is no fee to publish,
    so publishing anything would publish the referenced item's size as a fee.
    The row is unreadable and the document goes with it."""
    document = issue_three_document(
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 CHK# 00 AMT $31.00"
    )
    assert parse_fiserv_premier_statement(document) is None


#: The reference-in-the-amount-slot row, with the whole document arranged so
#: that reading it as an amount would satisfy every gate this module has: two
#: printed debits totalling $41.00, a summary identity that closes on $129.00,
#: and a daily grid walked from the same reading.
_BAITED_SUMMARY = (
    "Previous Balance $100.00 Deposits/Credits (2) $70.00 "
    "Checks/Debits (2) $41.00 Current Balance $129.00"
)
_BAITED_GRID = "Date Balance $ 3/02 $90.00 3/03 $140.00 3/04 $109.00 3/05 $129.00"


def test_the_reference_is_refused_even_when_every_other_gate_would_pass():
    """The sharp form of the refusal, and the reason it is grammar rather than
    an after-the-fact check.

    The printed counts, the printed totals, the summary identity and the
    printed daily grid have all been arranged to agree with reading the
    reference as the row's amount. Every oracle in this module says yes. The
    only thing that says no is the rule that a token the reference keyword
    introduces is never an amount — so this is the one test that fails if that
    lookbehind is deleted.
    """
    baited = issue_three_document(
        summary=_BAITED_SUMMARY,
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 CHK# 00 AMT $31.00",
        cheques="",
        grid=_BAITED_GRID,
    )
    assert parse_fiserv_premier_statement(baited) is None


def test_the_baited_document_is_sound_apart_from_the_reference():
    """The control that stops the test above being vacuous: the same document
    with the reference keyword replaced by an ordinary word publishes, with the
    $31.00 in exactly the slot the refusal denied it."""
    sound = issue_three_document(
        summary=_BAITED_SUMMARY,
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 CHK# 00 REF 31 $31.00",
        cheques="",
        grid=_BAITED_GRID,
    )
    statement = parse_fiserv_premier_statement(sound)
    assert statement is not None
    assert [t.amount for t in _sides(statement)[1]] == [-10.00, -31.00]
    assert statement.ending_balance == 129.00


def test_a_money_token_that_is_not_a_reference_still_bounds_the_row():
    """The relaxation is exactly one shape wide. Any other embedded money token
    still stops the description dead, so a row can never run into its
    neighbour and swallow the neighbour's amount — the merge hazard §FI2.3
    measured when a plain last-token rule was tried here (1–3 rows lost per
    document)."""
    document = issue_three_document(
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 3/04 CHK# 00 REF $10.00, NSF FEE $31.00"
    )
    assert parse_fiserv_premier_statement(document) is None


def test_rows_do_not_merge_across_the_end_of_a_section():
    """The other half of the merge hazard: the last row of the debit section
    must not reach forward into the cheque section for its amount. If it did,
    the debit count would come back short by one and the totals would miss."""
    statement = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None
    debits = _sides(statement)[1]
    assert len(debits) == 3
    assert [t.date for t in debits] == ["2026-03-02", "2026-03-04", "2026-03-06"]


# ---------------------------------------------------------------------------
# The second period wording
# ---------------------------------------------------------------------------


def test_the_registered_period_clause_is_still_the_first_reading():
    """A document that prints `Statement Dates ... (N days)` takes exactly the
    path it took before the second wording existed."""
    statement = parse_fiserv_premier_statement(
        issue_three_document(period=READ_PERIOD, days="")
    )
    assert statement is not None
    assert (statement.period_start, statement.period_end) == ("2026-03-01", "2026-03-31")
    assert statement.days_in_period == 31


def test_the_second_wordings_two_halves_must_corroborate_each_other():
    """The dates and the length are printed in two different places, so they
    are two reads and either could be the wrong one. They are welded by the
    calendar: a printed length that is not the span of the printed dates means
    one of them was misread, and a wrong period basis silently re-bounds every
    row and re-bases the average daily balance."""
    assert parse_fiserv_premier_statement(
        issue_three_document(days="Activity Summary Days in the Statement Period:  30")
    ) is None


def test_the_length_alone_is_not_a_period_and_neither_are_the_dates_alone():
    assert parse_fiserv_premier_statement(issue_three_document(days="")) is None
    assert parse_fiserv_premier_statement(
        issue_three_document(period="Statement of Account")
    ) is None


# ---------------------------------------------------------------------------
# The section vocabulary, and where it stops
# ---------------------------------------------------------------------------


def test_a_section_is_suspended_by_a_page_break_and_resumed_by_the_column_header():
    """This issue re-declares only the bare `Date Description Amount $` header
    on a continuation page, so a reader that closes at `--- Page` loses the
    continuation and a reader that carries blindly swallows the disclosure
    page. Neither: the page break suspends, the document's own re-declared
    header resumes."""
    document = issue_three_document().replace(
        "--- Page 3 ---\n\nDebits Date Description Amount $\n"
        "3/02 SYNTHETIC DEBIT ONE $10.00",
        "Debits Date Description Amount $\n3/02 SYNTHETIC DEBIT ONE $10.00\n"
        "--- Page 3 ---\n\nDate Description Amount $",
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert len(_sides(statement)[1]) == 3


def test_a_page_break_that_is_never_resumed_ends_the_section():
    """The same document with nothing declaring the section after the break:
    the rows below it are outside every section, the debit count comes back
    short, and the document refuses rather than publishing a partial ledger."""
    document = issue_three_document().replace(
        "Debits Date Description Amount $\n3/02 SYNTHETIC DEBIT ONE $10.00",
        "Debits Date Description Amount $\n--- Page 9 ---\n\n"
        "3/02 SYNTHETIC DEBIT ONE $10.00",
    )
    assert parse_fiserv_premier_statement(document) is None


def test_the_disclosure_page_in_the_middle_of_a_section_is_not_in_the_ledger():
    """Page 2 sits inside the credit run in the fixture, exactly as it does on
    the archive documents, and it declares no column header. A dated amount
    printed on it is therefore outside every section and changes NOTHING — the
    published ledger is the same five rows, not six and not a refusal."""
    document = issue_three_document().replace(
        DISCLOSURE_PAGE, DISCLOSURE_PAGE + "\n3/09 NOT A POSTING $999.00"
    )
    statement = parse_fiserv_premier_statement(document)
    baseline = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None and baseline is not None
    assert statement.transactions == baseline.transactions
    assert len(statement.transactions) == 5


def test_the_cheque_image_page_printed_after_the_ledger_is_not_in_the_ledger():
    """The template reprints every cleared cheque as an image list on the last
    pages, with no section head. `Overdraft and Returned Item Fees` has already
    ended the ledger by then, and nothing can resume it — not even the column
    header, which is what resumes a suspended section everywhere else."""
    document = issue_three_document().replace(
        CHEQUE_IMAGE_PAGE, "Date Check No Amount $ 3/06 101 $9.00"
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert len(_sides(statement)[1]) == 3, "the cheque is posted once, not twice"


def test_the_cheque_section_is_posting_detail_and_is_inside_the_printed_count():
    """`Checks Cleared` is a recap in the two read issues and posting detail
    here: its items are inside `Checks/Debits (3)` and inside the printed debit
    total. Dropping it leaves every one of the four archive documents short."""
    assert parse_fiserv_premier_statement(issue_three_document(cheques="")) is None


def test_the_cheque_sections_direction_comes_from_its_own_head():
    """`Checks Cleared` names a direction; it does not inherit one.

    On all four archive documents it happens to follow the debit section, so a
    reader that simply let the previous section run on would get the same
    answer. It would get it for the wrong reason, and the wrong reason files
    every cheque as a CREDIT the moment an issuer prints the recap after the
    credit sections instead. Here it does exactly that, with no debit section
    on the page at all.
    """
    document = issue_three_document(
        summary=("Previous Balance $100.00 Deposits/Credits (2) $70.00 "
                 "Checks/Debits (1) $9.00 Current Balance $161.00"),
        debits="",
        grid="Date Balance $ 3/03 $150.00 3/05 $170.00 3/06 $161.00",
    ).replace("Debits Date Description Amount $\n", "")
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    credits, debits = _sides(statement)
    assert [t.amount for t in credits] == [50.00, 20.00]
    assert [t.amount for t in debits] == [-9.00], "the cheque is a debit, by its head"


def test_a_document_printing_a_read_vocabulary_never_reaches_this_branch():
    """Structural non-interference: the embedded branch is the `else` of the two
    that came first, so a document printing `Transaction Activity` or the
    `Credit Transactions` / `Debit Transactions` split cannot reach it however
    much of this issue's furniture it also prints."""
    document = split_document() + (
        "\nDeposits Date Description Amount\n3/09 SYNTHETIC $999.00\n"
        "Debits Date Description Amount $\n3/09 SYNTHETIC $999.00\n"
        "Daily Balance Information\nDate Balance $ 3/09 $999.00\n"
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert len(statement.transactions) == 3, "the split sections, and only those"


# ---------------------------------------------------------------------------
# The printed daily grid, as an oracle
# ---------------------------------------------------------------------------


def test_the_printed_daily_grid_must_reproduce_the_rows_that_were_read():
    """The third oracle, and the only one that binds a row to a DAY. Both
    printed counts and both printed totals can be satisfied by a ledger whose
    rows are on the wrong days — and the underwriting ADB is a calendar-day
    average over exactly these balances, so that ledger would publish a wrong
    average with every other gate green."""
    assert parse_fiserv_premier_statement(
        issue_three_document(
            grid=("Date Balance $ 3/02 $90.00 3/03 $140.00 3/04 $109.00 "
                  "3/05 $129.00 3/06 $121.00")
        )
    ) is None


def test_a_row_on_a_day_the_grid_never_prints_refuses_the_document():
    """A row filed on a day the grid does not print is a row the grid cannot
    vouch for, and the walk must not simply carry it forward into the next
    printed day.

    The pair here is deliberately OFFSETTING — a $15.00 credit and a $15.00
    debit on 3/10 — so the walk still lands on the printed closing balance and
    every printed count and total still agrees. The closing check therefore
    cannot see them; only "no row falls outside the grid" can.
    """
    document = issue_three_document(
        summary=("Previous Balance $100.00 Deposits/Credits (3) $85.00 "
                 "Checks/Debits (4) $65.00 Current Balance $120.00"),
        other_credits=("3/05 RETURNED ITEM, INSUFFICIENT FUNDS, SYNTHETIC $20.00 "
                       "3/10 SYNTHETIC LATE CREDIT $15.00"),
        debits="3/02 SYNTHETIC DEBIT ONE $10.00 " + FEE_ROW
               + " 3/10 SYNTHETIC LATE DEBIT $15.00",
    )
    assert parse_fiserv_premier_statement(document) is None


def test_an_absent_daily_grid_refuses_rather_than_waiving_the_oracle():
    assert parse_fiserv_premier_statement(issue_three_document(grid="")) is None
    assert parse_fiserv_premier_statement(
        issue_three_document().replace("Daily Balance Information\n", "")
    ) is None


# ===========================================================================
# THE ACCOUNT LABELS (W3 §DECLINESG, the FISERV-LABELS card)
#
# The third issue prints its product and its masked account number on one line
# and repeats the mask in the summary strip, and both fields published as None.
# They are audited columns, so the rule that lifts them is a CORROBORATION
# rule: two printings agree, or nothing is published.
# ===========================================================================


def test_the_third_issue_reads_the_account_labels_its_page_prints():
    statement = parse_fiserv_premier_statement(issue_three_document())
    assert statement is not None
    assert statement.account_name == "SYNTHETIC BUSINESS CHECKING ACCOUNT"
    assert statement.account_number == "XXXXXX0000"


def test_the_labels_are_the_only_thing_the_rule_changes():
    """Everything else the third issue publishes is untouched by the labels."""
    with_labels = parse_fiserv_premier_statement(issue_three_document())
    without = parse_fiserv_premier_statement(issue_three_document(strip_prefix=""))
    assert without is not None
    assert (without.account_name, without.account_number) == (None, None)
    assert with_labels.model_copy(
        update={"account_name": None, "account_number": None}
    ) == without


def test_the_corroborating_printing_may_not_be_the_header_s_own_token():
    r"""THE mutation this rule is built around. The header line sits directly
    above the summary strip, so a corroboration written with `\s+` — which
    spans the newline — would find the header's OWN mask and call it a second
    printing. `[^\S\n]+` is what makes "printed twice" mean printed twice."""
    document = issue_three_document(strip_prefix="")
    assert "XXXXXX0000\nPrevious Balance" in document
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert statement.account_number is None


def test_a_second_printing_that_disagrees_publishes_neither_label():
    statement = parse_fiserv_premier_statement(
        issue_three_document(strip_prefix="SYNTHETIC HOLDINGS LLC XXXXXX9999 ")
    )
    assert statement is not None
    assert (statement.account_name, statement.account_number) == (None, None)


def test_two_account_headers_publish_neither_label():
    """A document naming two accounts cannot be labelled with one of them; the
    ledger it publishes is still gated by every other oracle, so the labels go
    and the statement stays."""
    statement = parse_fiserv_premier_statement(
        issue_three_document(
            header="SYNTHETIC BUSINESS CHECKING ACCOUNT XXXXXX0000\n"
                   "SYNTHETIC SAVINGS ACCOUNT XXXXXX1111"
        )
    )
    assert statement is not None
    assert (statement.account_name, statement.account_number) == (None, None)


def test_the_registered_product_wording_is_still_the_first_reading():
    """A document printing `<product> - <mask>` takes the path it took before
    this rule existed, even when a bare masked header stands beside it."""
    document = activity_document().replace(
        "SYNTHETIC BUSINESS CHECKING - XXXXXX0000",
        "SYNTHETIC OTHER PRODUCT ACCOUNT XXXXXX2222\n"
        "SYNTHETIC BUSINESS CHECKING - XXXXXX0000",
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert statement.account_name == "SYNTHETIC BUSINESS CHECKING"
    assert statement.account_number == "XXXXXX0000"


def test_the_account_title_stays_the_name_of_last_resort():
    """`Account Title:` is the account HOLDER, not the product. It is used only
    where no product line was corroborated, and it never supplies a number."""
    document = issue_three_document(strip_prefix="").replace(
        "SYNTHETIC BUSINESS CHECKING ACCOUNT XXXXXX0000",
        "Account Title: SYNTHETIC HOLDINGS LLC",
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert statement.account_name == "SYNTHETIC HOLDINGS LLC"
    assert statement.account_number is None


def test_a_name_and_a_bare_mask_on_two_lines_are_not_one_header():
    r"""`\s` spans the newline; `[^\S\n]` does not. Written with `\s+` this
    document reads `ACME HOLDINGS LLC` + `XXXXXX0000` as a single header line,
    finds the corroborating printing in the strip, and publishes labels the
    page never printed as one."""
    document = issue_three_document(header="ACME HOLDINGS LLC\nXXXXXX0000")
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert (statement.account_name, statement.account_number) == (None, None)


def test_the_registered_wording_wins_when_both_wordings_would_read():
    """Pins the ORDER, not merely the presence, of `_PRODUCT_RE`.

    A `<product> - <mask>` line also matches `_MASKED_HEADER_RE`, with the
    separator trailing the name. When the strip repeats the mask so the
    corroboration would succeed too, only trying `_PRODUCT_RE` FIRST publishes
    the product name without its separator.
    """
    document = activity_document().replace(
        "Previous Balance", "XXXXXX0000 Previous Balance"
    )
    statement = parse_fiserv_premier_statement(document)
    assert statement is not None
    assert statement.account_name == "SYNTHETIC BUSINESS CHECKING"
    assert statement.account_number == "XXXXXX0000"
