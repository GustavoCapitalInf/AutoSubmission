"""Audit fix batch B10 (I05, I12, I14, I60): the payer text a statement prints beside a credit's posting-type label.

Deterministic readers published only the label (`ACH DEPOSIT`, `ACH Credit`, `Preauthorized Credit`, `REAL TIME
CREDIT`, `TRANSFER IN`, `TRNSFR CREDIT`, `International IWT`, `Wire Credit`, First Citizens' `Other Credit`) and dropped
the payer the statement printed after the amount or on the lines below it, so pass 7 read the row as Q2's bare deposit
('no payer printed') when the statement did print one. BMO US, the counted core-processor template, the community
platform, the balance-by-date template and U.S. Bank now keep that text on their credits (a debit keeps its label until
the owner admits the debit readings, G7), and a credit whose printed payer a reader could not attribute is marked
(`Transaction.payer_text_unread`), which pass 7 counts as 'payer text not read'. The daily core-processor template's
text reading waits on G7 (its restored text pairs a returned credit with a debit); since the B10 review (round 1) it
marks the credits whose block it does not read, which moves no text.

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
from tests import test_core_processor_daily as cpd_fixture
from tests.test_bmo_layouts import us_statement
from tests.test_community_section_layouts import PLATFORM_HEAD
from tests.test_first_citizens_layouts import REPORTED, flattened
from tests.test_us_bank_variants import DESCRIBED_HEADER, document as us_bank_document
from tests.zelle_reading import rules_reading


def _tiers(statement: Statement) -> list[tuple[str, str | None, str]]:
    """(tier, reason, description) of every posted credit, in ledger order. The owner's ruling of 2026-10-02 (the
    underwriter's Q3): a Zelle deposit is read through the rules' own reading, its final tier (non_revenue,
    zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7)."""
    return [
        (*rules_reading(record), transaction.description)
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
    """The JSON schema gains nothing (it was the hosted extractor's response schema until slice S3 of the model-code
    removal deleted the extractor and its schema digest test)."""
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


def test_a_marked_cash_teller_or_atm_label_keeps_q2s_no_payer_printed():
    """B10 review (round 1): the swap is §8.10's bare-row fall-through only. A cash, branch, teller or ATM label says
    itself that the statement printed no payer (Q2), whatever the parser marked; a bare 'Deposit' label does not."""
    tiers = _tiers(_credits([("ATM DEPOSIT", True), ("TELLER DEPOSIT", True), ("DEPOSIT", True)]))
    assert [tier[:2] for tier in tiers] == [
        ("counted_flagged", "no_payer_printed"),
        ("counted_flagged", "no_payer_printed"),
        ("counted_flagged", PAYER_TEXT_NOT_READ),
    ]


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


def test_a_block_the_template_proves_names_no_payer_is_published_on_no_row_and_marks_none():
    """B10 review (round 1): `below` answering None says the block holds no payer (a teller's own reference)."""
    run = "\n02-03 Deposit 300.00\nTLR 00 BR 00\n02-04 Deposit 50.00 02-04 ACH Credit 400.00\nTLR 00 BR 00\n"
    assert _attributed(run, below=lambda lines: None, block_under_its_row=True) == (
        ["Deposit", "Deposit", "ACH Credit"], [False, False, False],
    )


# Audit round 2, R2-B07 (R07): `unread_text`, parallel to `unread`, gives every row marked at an indeterminate flush
# that flush's joined text; the published descriptions do not change.

def _attributed_with_text(run: str, *, below, block_under_its_row=False):
    cells = tables.dated_cells(run, date_pattern=cpd._DATE_RE, value_pattern=cpd._FIGURE_RE)
    assert cells is not None
    unread: list[list[bool]] = []
    unread_text: list[list[str]] = []
    texts = tables.attributed_descriptions(
        [cells], strip=cpd._DESCRIPTION_FURNITURE, limit=cpd._DESCRIPTION_LIMIT,
        below=below, block_under_its_row=block_under_its_row, unread=unread, unread_text=unread_text,
    )
    without = tables.attributed_descriptions(
        [cells], strip=cpd._DESCRIPTION_FURNITURE, limit=cpd._DESCRIPTION_LIMIT,
        below=below, block_under_its_row=block_under_its_row,
    )
    assert texts == without  # the out-parameter never changes a published description
    return texts[0], unread[0], unread_text[0]


def test_a_welded_block_below_gives_every_row_it_marks_the_flushs_joined_text():
    """The below-the-amount branch, the template's rule answering False (two blocks welded on one line)."""
    run = "\n02-03 Deposit 300.00 02-03 ACH Credit 400.00\nCONTOSO SUPPLY 540203  FABRIKAM TOOLS 540204\n"
    assert _attributed_with_text(run, below=lambda lines: False) == (
        ["Deposit", "ACH Credit"], [True, True],
        ["CONTOSO SUPPLY 540203 FABRIKAM TOOLS 540204"] * 2,
    )


def test_a_welded_flush_inside_a_span_gives_every_row_it_marks_the_flushs_joined_text():
    """The span branch: a flush printed before the amount of the last of two outstanding rows, on two lines."""
    run = "\n02-03 ACH Credit 300.00 02-04 ACH Credit\nCONTOSO SUPPLY 540203\nFABRIKAM TOOLS 540204\n400.00\n"
    assert _attributed_with_text(run, below=None) == (
        ["ACH Credit", "ACH Credit"], [True, True],
        ["CONTOSO SUPPLY 540203 FABRIKAM TOOLS 540204"] * 2,
    )


def test_an_attributed_block_and_a_block_naming_no_payer_give_no_unread_text():
    attributed = "\n02-03 ACH Credit 300.00\nCONTOSO SUPPLY 540203\n"
    assert _attributed_with_text(attributed, below=lambda lines: True) == (
        ["ACH Credit CONTOSO SUPPLY 540203"], [False], [""],
    )
    teller = "\n02-03 Deposit 300.00 02-04 ACH Credit 400.00\nTLR 00 BR 00\n"
    assert _attributed_with_text(teller, below=lambda lines: None) == (
        ["Deposit", "ACH Credit"], [False, False], ["", ""],
    )


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
    """Zelle is counted person-to-person by the rules (then excluded by the owner's Zelle policy of 2026-10-02), the
    funder is held, the card credit stays a possible return (B3)."""
    tiers = _tiers(_bmo())
    assert tiers[0][:2] == ("counted_flagged", "p2p")
    assert tiers[2][:2] == ("excluded_pending_review", "financing_named_payer")
    assert tiers[3][:2] == ("excluded_pending_review", "possible_return")


def test_bmo_us_page_furniture_and_record_numbers_never_join_a_description():
    joined = " ".join(t.description for t in _bmo().transactions)
    for furniture in ("CONTINUED", "bmo.com", "Monthly Activity", "RECORD NO", "CARD NO", "1 of 2"):
        assert furniture not in joined


def _bmo_rows(*rows: str) -> Statement:
    statement = parse_bmo_us_activity_statement(us_statement(
        credit_count=1, credits="$500.00", debit_count=1, debits="$200.00", ending="$1,300.00", rows=rows,
    ))
    assert statement is not None
    return statement


def test_bmo_us_a_page_break_is_skipped_whole_up_to_the_reprinted_column_header():
    """B10 review (round 1): every line a page break prints, listed or not (a page counter with its word, a holder
    line, an account or period line), is furniture up to the reprinted column header; the description resumes after
    it."""
    statement = _bmo_rows(
        "Apr 03 ACH DEPOSIT $500.00",
        "CCD CONTOSO SUPPLY",
        "CONTINUED ON NEXT PAGE",
        "Page 1 of 2",
        "--- Page 2 ---",
        "bmo.com/contact 000-000-0000",
        "NORTHWIND SUPPLY LLC",
        "Account Number XXXXXX0000",
        "Statement Period April 01, 2054 through April 30, 2054",
        "Monthly Activity Details (cont'd)",
        "Date Transaction description Withdrawal Deposit Balance",
        "PAYABLES 540403",
        "Apr 04 TRANSFER OUT ($200.00) $1,300.00",
    )
    assert [t.description for t in statement.transactions] == [
        "ACH DEPOSIT CCD CONTOSO SUPPLY PAYABLES 540403", "TRANSFER OUT",
    ]


def test_bmo_us_a_page_break_whose_column_header_never_prints_drops_the_rest_of_the_group():
    """Fail closed: with no reprinted column header the furniture has no end, so nothing after the break is read."""
    statement = _bmo_rows(
        "Apr 03 ACH DEPOSIT $500.00",
        "CCD CONTOSO SUPPLY",
        "Page 1 of 2",
        "NORTHWIND SUPPLY LLC",
        "Apr 04 TRANSFER OUT ($200.00) $1,300.00",
    )
    assert statement.transactions[0].description == "ACH DEPOSIT CCD CONTOSO SUPPLY"


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


# ---------------------------------------------------------------------------
# The daily core-processor template: its text reading waits on G7, its marks do not
# ---------------------------------------------------------------------------

def _daily(credits: str, *, grid: str) -> Statement:
    statement = cpd_fixture.parse(cpd_fixture.document(
        summary=("Beginning balance $100.00 Total additions 800.00 "
                 "Total subtractions 250.00 Ending balance $650.00\n"),
        credits=credits, grid=grid,
    ))
    assert statement is not None
    return statement


DAILY_GRID = "DAILY BALANCES\nDate Amount\n03-31 100.00 04-02 -150.00 04-03 150.00\n04-06 650.00\n"


def _daily_credits(statement: Statement) -> list[tuple[str, bool]]:
    return [(t.description, t.payer_text_unread) for t in statement.transactions if t.amount > 0]


def test_core_processor_daily_credits_with_a_block_below_are_marked_and_publish_only_their_label():
    """B10 review (round 1): the statement prints each credit's payer below its amount; the reader does not read it
    yet (G7), so the credit is marked, never read as Q2's bare deposit, and the 30% fact fires."""
    statement = _daily(
        "CREDITS\nDate Description Additions\n"
        "04-03 ' ACH Credit 300.00\nCONTOSO SUPPLY 540403\n"
        "04-06 ' ACH Credit 500.00\nFABRIKAM TOOLS 540406\n",
        grid=DAILY_GRID,
    )
    assert _daily_credits(statement) == [("ACH Credit", True), ("ACH Credit", True)]
    assert [(t.description, t.payer_text_unread) for t in statement.transactions if t.amount < 0] == [
        ("ACH Debit", False),
    ]
    assert [tier[:2] for tier in _tiers(statement)] == [("counted_flagged", PAYER_TEXT_NOT_READ)] * 2
    metrics = compute_metrics(statement)
    assert (metrics.payer_text_unread, metrics.payer_text_unread_count) == (True, 2)


def test_core_processor_daily_two_credits_on_one_line_with_a_block_below_are_both_marked():
    statement = _daily(
        "CREDITS\nDate Description Additions\n"
        "04-03 Deposit 300.00 04-06 ' ACH Credit 500.00\nCONTOSO SUPPLY 540406\n",
        grid=DAILY_GRID,
    )
    assert _daily_credits(statement) == [("Deposit", True), ("ACH Credit", True)]


def test_core_processor_daily_a_credit_with_nothing_printed_under_it_keeps_q2s_reading():
    statement = _daily(
        "CREDITS\nDate Description Additions\n"
        "04-03 ' Deposit 300.00\n"
        "04-06 ' ACH Credit 500.00\nCONTOSO SUPPLY 540406\n",
        grid=DAILY_GRID,
    )
    assert _daily_credits(statement) == [("Deposit", False), ("ACH Credit", True)]
    assert [tier[:2] for tier in _tiers(statement)] == [
        ("counted_flagged", "no_payer_printed"), ("counted_flagged", PAYER_TEXT_NOT_READ),
    ]
    metrics = compute_metrics(statement)
    assert (metrics.payer_text_unread, metrics.payer_text_unread_count) == (True, 1)  # one of two credits: 50%


def test_core_processor_daily_a_teller_reference_below_a_deposit_is_no_payer_and_marks_nothing():
    """The template prints a teller and branch reference below a counter deposit: the statement printed no payer."""
    statement = _daily(
        "CREDITS\nDate Description Additions\n"
        "04-03 ' Deposit 300.00\nTLR 00 BR 00\n"
        "04-06 ' Deposit 500.00\nTLR 00 BR 00\n",
        grid=DAILY_GRID,
    )
    assert _daily_credits(statement) == [("Deposit", False), ("Deposit", False)]
    assert [tier[:2] for tier in _tiers(statement)] == [("counted_flagged", "no_payer_printed")] * 2


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


def _platform_lines(*sections: str, count: int = 1, total: str = "10.00", ending: str = "105.00") -> Statement:
    statement = parse_community_section_statement(
        PLATFORM_HEAD
        + "Business Checking - XXXXXX1234\n"
        + "Account Summary Date Description Amount 01/01/2054 Beginning Balance $100.00"
        + f" {count} Credit(s) This Period ${total} 1 Debit(s) This Period $5.00"
        + f" 01/30/2054 Ending Balance ${ending}\n"
        + "".join(f"{section}\n" for section in sections)
    )
    assert statement is not None
    return statement


def test_a_heading_printed_on_a_credits_own_line_never_joins_it():
    """B10 review (round 1): the next section's header, the Daily Balances grid and the account's continued heading
    end a credit's printed tail even when the layer prints them on the row's own line."""
    debits = "Other Debits Date Description Amount 01/03/2054 SERVICE CHARGE $5.00"
    credit = "Electronic Credits Date Description Amount 01/02/2054 ACH Credit $10.00 CONTOSO SUPPLY PAYMENT"
    for statement in (
        _platform_lines(f"{credit} {debits}"),
        _platform_lines(f"{credit} Daily Balances Date Amount 01/02/2054 $110.00", debits),
        _platform_lines(f"{credit} Business Checking - XXXXXX1234 (continued)", debits),
    ):
        assert [t.description for t in statement.transactions] == ["ACH Credit CONTOSO SUPPLY PAYMENT", "SERVICE CHARGE"]


def test_a_zero_amount_return_printed_under_deposits_keeps_its_label():
    """B10 review (round 1): the tail is read for a published credit only; the platform's $0.00 returned ACH, printed
    under Deposits and counted there, keeps its label as a debit does (G7)."""
    statement = _platform_lines(
        "Deposits Date Description Amount 01/02/2054 ACH Credit $10.00 CONTOSO SUPPLY PAYMENT"
        " 01/05/2054 ACH Return $0.00 CONTOSO SUPPLY PAYROLL",
        "Other Debits Date Description Amount 01/03/2054 SERVICE CHARGE $5.00",
        count=2,
    )
    assert [t.description for t in statement.transactions if t.direction == "credit"] == [
        "ACH Credit CONTOSO SUPPLY PAYMENT", "ACH Return",
    ]


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
    assert statement.transactions[0].description.endswith("ORG=NORTHWIND SUPPLY INC")
    assert _tiers(statement)[0][:2] == ("counted_flagged", "wire_named_sender")


def test_us_bank_a_funder_named_after_org_is_held():
    assert _tiers(_us_bank("CONTOSO FINANCIAL SOLUTIONS"))[0][:2] == (
        "excluded_pending_review", "financing_named_payer",
    )


def _us_bank_wires(*wires: list[str]) -> Statement:
    """U.S. Bank wires of $2,500.00 each, each followed by its own ORG= field lines."""
    rows = "".join(
        f"Mar {3 + 6 * index} Wire Credit REF00000{index + 1}\n"
        f"FABRIKAM BANK SAMPLEVILLE 5403{3 + 6 * index:02d}B000000{index + 1}\n"
        "$ 2,500.00\n" + "".join(f"{line}\n" for line in lines)
        for index, lines in enumerate(wires)
    )
    total = f"{2500 * len(wires):,}.00"
    statement = parse_us_bank_statement(us_bank_document(
        summary=f"Other Deposits {len(wires)} {total} Other Withdrawals 1 80.00-",
        closing=f"{1000 + 2500 * len(wires) - 80:,}.00",
        sections=(
            "Other Deposits\n" f"{DESCRIBED_HEADER}\n" + rows + f"Total Other Deposits $ {total}\n"
            "Other Withdrawals\n" f"{DESCRIBED_HEADER}\n"
            "Mar 6 Electronic Withdrawal\n" "To A COUNTERPARTY\n" "$ 80.00-\n" "Total Other Withdrawals $ 80.00-\n"
        ),
    ))
    assert statement is not None
    return statement


def test_us_bank_the_org_field_is_the_name_up_to_its_address_or_the_next_field():
    """B10 review (round 1): the ORG= field wraps the sender's name and address together; the sender is the name,
    read across the wrap up to the street number, and never a later field (BNF=, OBI=, REF=)."""
    statement = _us_bank_wires(
        ["ORG=NORTHWIND SUPPLY", "INC. 100 MAIN ST SAMPLEVILLE"],
        ["ORG=NORTHWIND SUPPLY INC", "100 MAIN ST SAMPLEVILLE", "BNF=SAMPLE HOLDER LLC"],
        ["ORG=FABRIKAM TOOLS LLC REF=INV 1234"],
        ["ORG=1000001 SAMPLE INC", "100 MAIN ST SAMPLEVILLE"],
    )
    assert [t.description.split(" ORG=")[1] for t in statement.transactions if t.amount > 0] == [
        "NORTHWIND SUPPLY INC.", "NORTHWIND SUPPLY INC", "FABRIKAM TOOLS LLC", "1000001 SAMPLE INC",
    ]


def test_us_bank_an_org_field_that_prints_no_name_names_no_sender():
    """B10 review (round 1): an empty ORG= is no sender, so its address is never read as one (Q5: held)."""
    statement = _us_bank("")
    assert "MAIN ST" not in statement.transactions[0].description
    assert _tiers(statement)[0][:2] == ("excluded_pending_review", "wire_no_sender")


def test_us_bank_two_wires_from_one_org_company_name_one_sender_whatever_their_address_wrap():
    """B10 review (round 1): Q5's repeat reads the sender, so the address the field wraps onto never makes one company
    two senders. (Whether the repeat then verifies is the wire vetoes' reading of the whole row, not the field's.)"""
    statement = _us_bank_wires(
        ["ORG=NORTHWIND SUPPLY INC", "100 MAIN ST SAMPLEVILLE"],
        ["ORG=NORTHWIND SUPPLY INC", "100 MAIN"],
    )
    senders = [t.description.split(" ORG=")[1] for t in statement.transactions if t.amount > 0]
    assert senders == ["NORTHWIND SUPPLY INC"] * 2


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
