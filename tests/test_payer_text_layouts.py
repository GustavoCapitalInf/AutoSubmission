"""Audit fix batch B10 (I05, I12, I14, I60): the payer text a statement prints beside a credit's posting-type label.

Deterministic readers published only the label (`ACH DEPOSIT`, `ACH Credit`, `Preauthorized Credit`, `REAL TIME
CREDIT`, `TRANSFER IN`, `TRNSFR CREDIT`, `International IWT`, `Wire Credit`, First Citizens' `Other Credit`) and dropped
the payer the statement printed after the amount or on the lines below it, so pass 7 read the row as Q2's bare deposit
('no payer printed') when the statement did print one. BMO US, the counted core-processor template, the community
platform, the balance-by-date template and U.S. Bank now keep that text on their credits (a debit keeps its label until
the owner admits the debit readings, G7), and a credit whose printed payer a reader could not attribute is marked
(`Transaction.payer_text_unread`), which pass 7 counts as 'payer text not read'. The daily core-processor template's
own reading waits on G7 (its restored text pairs a returned credit with a debit), so only the shared count it would
use is pinned here.

Every fixture is synthetic: CONTOSO, FABRIKAM, NORTHWIND and SAMPLE names, invented amounts and 2054 dates. The
platforms' own furniture words and the processors' public names are the only real words.
"""
from __future__ import annotations

import json

from analysis import balance_by_date as bbd
from analysis import core_processor_counted as cpc
from analysis import core_processor_daily as cpd
from analysis import tables
from analysis.bmo_us_activity import parse_bmo_us_activity_statement
from analysis.community_section import parse_community_section_statement
from analysis.first_citizens import parse_first_citizens_statement
from analysis.metrics import compute_metrics
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from analysis.true_revenue import PAYER_TEXT_NOT_READ
from analysis.us_bank import parse_us_bank_statement
from tests import test_balance_by_date as bbd_fixture
from tests import test_core_processor_counted as cpc_fixture
from tests.test_bmo_layouts import us_statement
from tests.test_community_section_layouts import PLATFORM_HEAD
from tests.test_first_citizens_layouts import REPORTED, flattened
from tests.test_us_bank_variants import DESCRIBED_HEADER, document as us_bank_document


def _tiers(statement: Statement) -> list[tuple[str, str | None, str]]:
    """(tier, reason, description) of every posted credit, in ledger order."""
    return [
        (record.revenue_tier, record.revenue_tier_reason, transaction.description)
        for transaction, record in zip(statement.transactions, classify_statement_transactions(statement))
        if record.amount > 0
    ]


def _credits(rows: list[tuple[str, str]]) -> Statement:
    """A plain statement of credits: (description, unread mark)."""
    return Statement(
        bank="Fabrikam Bank", account_name="NORTHWIND BAKERY LLC",
        period_start="2054-01-01", period_end="2054-01-31",
        transactions=[
            Transaction(date=f"2054-01-{index + 2:02d}", description=text, amount=1000.0 + index,
                        direction="credit", payer_text_unread=unread)
            for index, (text, unread) in enumerate(rows)
        ],
    )


# ---------------------------------------------------------------------------
# The mark: a parser fact, kept out of the extractor's schema and out of every payload that does not carry it
# ---------------------------------------------------------------------------

def test_the_mark_is_not_part_of_the_extraction_response_schema():
    """The extractor is told nothing new (tests/test_extraction_schema_prompt_surface.py's digest holds)."""
    assert "payer_text_unread" not in json.dumps(Statement.model_json_schema())


def test_the_mark_is_serialized_only_on_a_transaction_that_carries_it():
    plain = Transaction(date="2054-01-02", description="ACH CREDIT", amount=10.0, direction="credit")
    marked = plain.model_copy(update={"payer_text_unread": True})
    assert "payer_text_unread" not in plain.model_dump()
    assert marked.model_dump()["payer_text_unread"] is True
    restored = Statement.model_validate(Statement(transactions=[plain, marked]).model_dump())
    assert [t.payer_text_unread for t in restored.transactions] == [False, True]


# ---------------------------------------------------------------------------
# Pass 7: 'payer text not read' replaces Q2's 'no payer printed' on a marked row, and nothing else moves
# ---------------------------------------------------------------------------

def test_a_marked_bare_label_is_counted_as_payer_text_not_read_never_verified():
    tiers = _tiers(_credits([("ACH CREDIT", True), ("PREAUTHORIZED CREDIT", True), ("OTHER CREDIT", True)]))
    assert [tier[:2] for tier in tiers] == [("counted_flagged", PAYER_TEXT_NOT_READ)] * 3


def test_an_unmarked_bare_label_keeps_q2s_no_payer_printed():
    """Q2 covers a row whose statement prints no payer, which is what an unmarked label says."""
    assert _tiers(_credits([("ACH CREDIT", False)]))[0][:2] == ("counted_flagged", "no_payer_printed")


def test_a_marked_transfer_label_stays_held_as_a_transfer_with_no_counterparty():
    """The mark changes no hold: a bare transfer label is still held (Q2's transfer wording)."""
    assert _tiers(_credits([("TRANSFER IN", True)]))[0][:2] == (
        "excluded_pending_review", "transfer_no_counterparty",
    )


def test_a_marked_row_that_names_its_payer_keeps_its_named_reading():
    """The mark only replaces the bare-deposit reason: a payer the row does print is read as before."""
    assert _tiers(_credits([("ACH CREDIT CONTOSO CAPITAL FUNDING", True)]))[0][:2] == (
        "excluded_pending_review", "financing_named_payer",
    )


def test_the_reason_is_a_counted_reason_of_the_one_reason_table():
    assert REVENUE_TIER_REASONS[PAYER_TEXT_NOT_READ] == ("counted_flagged", "Payer text not read")


def test_the_metrics_say_when_most_of_a_statements_payer_text_is_unread():
    many = _credits([("ACH CREDIT", True), ("ACH CREDIT", True), ("CONTOSO SUPPLY INC", False)])
    few = _credits([("ACH CREDIT", True), ("CONTOSO SUPPLY INC", False), ("FABRIKAM TOOLS LLC", False),
                    ("SAMPLE GOODS CO", False)])
    none = _credits([("CONTOSO SUPPLY INC", False)])
    assert (compute_metrics(many).payer_text_unread, compute_metrics(many).payer_text_unread_count) == (True, 2)
    assert (compute_metrics(few).payer_text_unread, compute_metrics(few).payer_text_unread_count) == (False, 1)
    assert (compute_metrics(none).payer_text_unread, compute_metrics(none).payer_text_unread_count) == (False, 0)


# ---------------------------------------------------------------------------
# The shared attribution count, reading the block printed below a row's amount
# ---------------------------------------------------------------------------

def _attributed(run: str, *, below, block_under_its_row=False):
    cells = tables.dated_cells(run, date_pattern=cpd._DATE_RE, value_pattern=cpd._FIGURE_RE)
    assert cells is not None
    unread: list[list[bool]] = []
    texts = tables.attributed_descriptions(
        [cells], strip=cpd._DESCRIPTION_FURNITURE, limit=cpd._DESCRIPTION_LIMIT,
        below=below, block_under_its_row=block_under_its_row, unread=unread,
    )
    return texts[0], unread[0]


def test_a_block_below_a_row_alone_on_its_line_is_that_rows_own():
    run = "\n02-03 ACH Credit 300.00\nCONTOSO SUPPLY 540203\n02-04 ACH Credit 400.00\nFABRIKAM TOOLS 540204\n"
    texts, unread = _attributed(run, below=lambda lines: True)
    assert texts == ["ACH Credit CONTOSO SUPPLY 540203", "ACH Credit FABRIKAM TOOLS 540204"]
    assert unread == [False, False]


def test_a_block_below_two_rows_of_one_line_is_published_on_neither_and_marks_both():
    run = "\n02-03 Deposit 300.00 02-03 ACH Credit 400.00\nCONTOSO SUPPLY 540203\n"
    texts, unread = _attributed(run, below=lambda lines: True)
    assert texts == ["Deposit", "ACH Credit"]
    assert unread == [True, True]


def test_without_the_callers_rule_the_block_below_is_read_as_before():
    run = "\n02-03 ACH Credit 300.00\nCONTOSO SUPPLY 540203\n"
    assert _attributed(run, below=None) == (["ACH Credit"], [False])


def test_a_page_break_ends_the_block_below_the_last_row_of_a_page():
    run = "\n02-03 ACH Credit 300.00\nCONTOSO SUPPLY 540203\n\n--- Page 2 ---\n\nNORTHWIND BAKERY LLC Page 2\n"
    assert _attributed(run, below=lambda lines: True)[0] == ["ACH Credit CONTOSO SUPPLY 540203"]


def test_a_row_with_nothing_printed_under_it_is_no_longer_outstanding_on_a_block_under_its_row_template():
    run = "\n02-03 Deposit 300.00\n02-04 Deposit 50.00 02-04 ACH Credit 400.00\nCONTOSO SUPPLY 540204\n"
    _texts, unread = _attributed(run, below=lambda lines: True, block_under_its_row=True)
    assert unread == [False, True, True]


# ---------------------------------------------------------------------------
# BMO Bank N.A. (US): the head line after the amount and the Description column's lines below it
# ---------------------------------------------------------------------------

BMO_ROWS = (
    "Apr 02 POS PURCHASE ($100.00)",
    "RECORD NO. 000001   CARD NO. 0001",
    "SAMPLE MERCHANT            SOMEWHERE      FL",
    "Apr 03 TRANSFER IN $150.00",
    "RECORD NO. P0A0B0",
    "ZELLE FROM PAT SAMPLE",
    "Apr 04 REAL TIME CREDIT $250.00",
    "RTP CREDIT SQUARE INST ID=20540404000000000P1SAMPLE0001 E2E ID =SAMPLE0001",
    "CONTINUED ON NEXT PAGE",
    "1 of 2",
    "--- Page 2 ---",
    "bmo.com/contact 000-000-0000",
    "Monthly Activity Details (cont'd)",
    "Date Transaction description Withdrawal Deposit Balance",
    "Apr 07 ACH DEPOSIT $5,000.00 $6,300.00",
    "CCD CONTOSO CAPITAL FUNDING",
    "Apr 08 CARD CREDIT $20.00",
    "RECORD NO. 000002   CARD NO. 0001",
    "FABRIKAM STORE            SOMEWHERE      FL",
)


def _bmo() -> Statement:
    statement = parse_bmo_us_activity_statement(us_statement(
        credit_count=4, credits="$5,420.00", debit_count=1, debits="$100.00", ending="$6,320.00",
        rows=BMO_ROWS,
    ))
    assert statement is not None
    return statement


def test_bmo_us_credits_carry_the_payer_printed_after_and_below_the_amount():
    descriptions = [t.description for t in _bmo().transactions]
    assert descriptions == [
        "POS PURCHASE",
        "TRANSFER IN ZELLE FROM PAT SAMPLE",
        "REAL TIME CREDIT RTP CREDIT SQUARE INST ID=20540404000000000P1SAMPLE0001 E2E ID =SAMPLE0001",
        "ACH DEPOSIT CCD CONTOSO CAPITAL FUNDING",
        "CARD CREDIT FABRIKAM STORE SOMEWHERE FL",
    ]


def test_bmo_us_restored_payers_are_read_by_the_existing_rules():
    """Zelle is counted person-to-person, the funder is held, the card credit stays a possible return (B3)."""
    tiers = _tiers(_bmo())
    assert tiers[0][:2] == ("counted_flagged", "p2p")
    assert tiers[2][:2] == ("excluded_pending_review", "financing_named_payer")
    assert tiers[3][:2] == ("excluded_pending_review", "possible_return")


def test_bmo_us_page_furniture_and_record_numbers_never_join_a_description():
    joined = " ".join(t.description for t in _bmo().transactions)
    for furniture in ("CONTINUED", "bmo.com", "Monthly Activity", "RECORD NO", "CARD NO", "1 of 2"):
        assert furniture not in joined


# ---------------------------------------------------------------------------
# The counted core-processor template: the merchant block printed below a credit's amount
# ---------------------------------------------------------------------------

COUNTED_SUMMARY = cpc_fixture.SUMMARY.replace("Electronic cr (1) + 300.00", "Electronic cr (3) + 600.00").replace(
    "+$300.00", "+$600.00").replace("Ending balance (2/27/2054)\n$150.00", "Ending balance (2/27/2054)\n$450.00")
COUNTED_GRID = cpc_fixture.GRID.replace("2-3 200.00", "2-3 500.00").replace("2-5 150.00", "2-5 450.00")


def test_core_processor_counted_attributes_one_ach_block_and_never_a_welded_line():
    credits = (
        "ELECTRONIC CREDITS\n"
        "Date Description Credits\n"
        "2-3 Preauthorized Credit 100.00 2-3 Preauthorized Credit 200.00\n"
        "CONTOSO SUPPLY PAYABLES CCD NORTHWIND FABRIKAM TOOLS PAYABLES CCD NORTHWIND\n"
        "2-3 Preauthorized Credit 300.00\n"
        "SAMPLE GOODS INC PAYMENT 1234567890 NORTHWIND CCD\n"
    )
    statement = cpc_fixture.published(summary=COUNTED_SUMMARY, credits=credits, grid=COUNTED_GRID)
    assert [(t.description, t.payer_text_unread) for t in statement.transactions if t.amount > 0] == [
        ("Preauthorized Credit", True),
        ("Preauthorized Credit", True),
        ("Preauthorized Credit SAMPLE GOODS INC PAYMENT 1234567890 NORTHWIND CCD", False),
    ]


def test_core_processor_counted_two_class_codes_on_a_single_rows_line_are_not_one_block():
    """The layer can flush blocks of rows printed BELOW after a row alone on its line: a line of two ACH blocks
    is never one row's."""
    assert cpc._block_below_is_one(["CONTOSO SUPPLY PAYABLES CCD NORTHWIND"])
    assert not cpc._block_below_is_one(["CONTOSO SUPPLY CCD NORTHWIND FABRIKAM TOOLS PPD NORTHWIND"])
    assert not cpc._block_below_is_one(["CONTOSO SUPPLY CCD", "NORTHWIND"])


# ---------------------------------------------------------------------------
# The community platform: Arbor's and Falcon's text after a credit's amount, on the row's own printed line
# ---------------------------------------------------------------------------

def _platform(credits: str, debits: str, *, count: int, total: str, ending: str) -> Statement:
    body = (
        "Business Checking - XXXXXX1234\n"
        "Account Summary Date Description Amount 01/01/2054 Beginning Balance $100.00"
        f" {count} Credit(s) This Period ${total} 1 Debit(s) This Period $5.00"
        f" 01/30/2054 Ending Balance ${ending}\n"
        f"Electronic Credits Date Description Amount {credits}\n"
        "THIS FORM IS PROVIDED TO HELP YOU BALANCE YOUR STATEMENT\n"
        f"Other Debits Date Description Amount {debits}\n"
    )
    statement = parse_community_section_statement(PLATFORM_HEAD + body)
    assert statement is not None
    return statement


def test_arbor_style_credits_carry_their_payer_and_verify_on_repeat():
    statement = _platform(
        "01/02/2054 ACH Credit $1,234.56 Jobber - By Stripe TRANSFER NORTHWIND LLC"
        " 01/09/2054 ACH Credit $1,234.56 Jobber - By Stripe TRANSFER NORTHWIND LLC",
        "01/03/2054 ACH Debit $5.00 CONTOSO SERVICES FEE NORTHWIND LLC",
        count=2, total="2,469.12", ending="2,564.12",
    )
    credits = [t.description for t in statement.transactions if t.amount > 0]
    assert credits == ["ACH Credit Jobber - By Stripe TRANSFER NORTHWIND LLC"] * 2
    assert [t.description for t in statement.transactions if t.amount < 0] == ["ACH Debit"]
    assert [tier[0] for tier in _tiers(statement)] == ["verified", "verified"]


def test_the_platforms_furniture_on_the_next_printed_line_never_joins_a_credit():
    statement = _platform("01/02/2054 Mobile Deposit $10.00", "01/03/2054 SERVICE CHARGE $5.00",
                          count=1, total="10.00", ending="105.00")
    assert [t.description for t in statement.transactions] == ["Mobile Deposit", "SERVICE CHARGE"]


def test_falcon_style_wires_read_their_sender_after_the_banks_own_wire_field():
    statement = _platform(
        "01/02/2054 International IWT $2,000.00 Falcon Internati Wires CONTOSO TRADING SA"
        " 01/05/2054 Incoming Wire Trf $3,000.00 Falcon Internati Wires NORTHWIND SUPPLY",
        "01/03/2054 Incoming Wire Fee $5.00 Falcon Internati Wires CONTOSO TRADING SA",
        count=2, total="5,000.00", ending="5,095.00",
    )
    assert [tier[:2] for tier in _tiers(statement)] == [("counted_flagged", "wire_named_sender")] * 2


# ---------------------------------------------------------------------------
# U.S. Bank: an incoming wire's ORG= sender, printed below its amount
# ---------------------------------------------------------------------------

def _us_bank(org: str) -> Statement:
    statement = parse_us_bank_statement(us_bank_document(
        summary="Other Deposits 1 2,500.00 Other Withdrawals 1 80.00-",
        closing="3,420.00",
        sections=(
            "Other Deposits\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 3 Wire Credit REF000001\n"
            "FABRIKAM BANK SAMPLEVILLE 540303B0000001\n"
            "$ 2,500.00\n"
            f"ORG={org}\n"
            "100 MAIN ST SAMPLEVILLE\n"
            "Total Other Deposits $ 2,500.00\n"
            "Other Withdrawals\n"
            f"{DESCRIBED_HEADER}\n"
            "Mar 6 Electronic Withdrawal\n"
            "To A COUNTERPARTY\n"
            "$ 80.00-\n"
            "Total Other Withdrawals $ 80.00-\n"
        ),
    ))
    assert statement is not None
    return statement


def test_us_bank_wires_keep_their_org_sender_and_are_counted():
    statement = _us_bank("NORTHWIND SUPPLY INC")
    assert statement.transactions[0].description.endswith("ORG=NORTHWIND SUPPLY INC 100 MAIN ST SAMPLEVILLE")
    assert _tiers(statement)[0][:2] == ("counted_flagged", "wire_named_sender")


def test_us_bank_a_funder_named_after_org_is_held():
    assert _tiers(_us_bank("CONTOSO FINANCIAL SOLUTIONS"))[0][:2] == (
        "excluded_pending_review", "financing_named_payer",
    )


# ---------------------------------------------------------------------------
# The balance-by-date template: a transfer's own field, and the hold it keeps
# ---------------------------------------------------------------------------

def test_balance_by_date_transfers_carry_their_field_and_stay_held():
    credits = (
        "e Deposits and Other Credits\n"
        "Date Amount Description Date Amount Description\n"
        "03/02 100.00 TRNSFR CREDIT 03/05 200.00 SYNTHETIC CREDIT TWO\n"
        "OLB XFER FROM 1234 0000000000000000PPD\n"
        "03/31 .50 SYNTHETIC INTEREST\n"
    )
    statement = bbd.parse_balance_by_date_statement(bbd_fixture.document(credits=credits))
    assert statement is not None
    descriptions = [t.description for t in statement.transactions if t.amount > 0]
    assert "TRNSFR CREDIT OLB XFER FROM 1234" in descriptions
    assert "SYNTHETIC CREDIT TWO" in descriptions
    held = [tier for tier in _tiers(statement) if tier[2].startswith("TRNSFR CREDIT")]
    assert [tier[:2] for tier in held] == [("excluded_pending_review", "transfer_no_counterparty")]


def test_balance_by_date_attributes_no_field_whose_count_disagrees():
    published = [("03/02", 100.0, "TRNSFR CREDIT"), ("03/05", 200.0, "TRNSFR CREDIT")]
    below = "OLB XFER FROM 1234 0000000000000000PPD"
    assert bbd._with_own_transfer_field(published, below, bbd._ROW_AMOUNT_RE) == published


# ---------------------------------------------------------------------------
# First Citizens: a section label standing in for a description the overlay could not read
# ---------------------------------------------------------------------------

def test_first_citizens_a_one_cent_overlay_mismatch_marks_its_credits_unread():
    statement = parse_first_citizens_statement(flattened(rows=REPORTED.replace("|04-08|200.00|", "|04-08|200.01|")))
    assert statement is not None
    credits = [(t.description, t.payer_text_unread) for t in statement.transactions if t.amount > 0]
    assert credits == [("Deposit", False), ("Other Credit", True), ("Other Credit", True)]
    tiers = _tiers(statement)
    assert tiers[0][:2] == ("counted_flagged", "no_payer_printed")
    assert [tier[:2] for tier in tiers[1:]] == [("counted_flagged", PAYER_TEXT_NOT_READ)] * 2


def test_first_citizens_an_agreeing_overlay_leaves_no_mark():
    statement = parse_first_citizens_statement(flattened(rows=REPORTED))
    assert statement is not None
    assert not any(t.payer_text_unread for t in statement.transactions)
