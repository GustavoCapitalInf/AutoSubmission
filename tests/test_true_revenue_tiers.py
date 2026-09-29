"""Classification 5.6 (true revenue spec §5.3, §8, T11 to T14): the tier and reason of every posted credit, the holds,
the channel tiers, and the Q5 and Q6 verifications with their guards. Fabricated rows only, in the banks' printed
formats."""
from __future__ import annotations

import pytest

from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "CONTOSO BAKERY LLC"


def _records(rows, *, holder: str | None = HOLDER):
    return classify_statement_transactions(Statement(account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _one(text: str, amount: float = 1234.0, *, holder: str | None = HOLDER):
    return _records([(text, amount)], holder=holder)[0]


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


@pytest.mark.parametrize(("text", "reason"), [
    ("STATE FARM DES:DRP PAYMENT ID:1", "insurer_payer"),
    ("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", "insurer_named_payer"),
    ("NORTHWIND SUPPLY DES:RETURN ID:1", "possible_return"),
    ("CONTOSO PARTNERS LLC DES:FUNDING ID:1", "financing_named_payer"),
    ("FABRIKAM GROUP LLC DES:CASH ADV ID:1", "financing_named_payer"),
    ("CAPITAL FABRIKAM LLC DES:PAYMENT ID:1", "financing_named_payer"),
    ("FABRIKAM FUNDING LLC DES:PAYMENT ID:1", "financing_named_payer"),
    ("FABRIKAM MERCHANT FUNDING DES:DEAL FUNDING ID:1", "financing_named_payer"),
    ("CONTOSO HOLDINGS LLC DES:PAYMENT ID:1", "holder_name"),
    ("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1", "holder_name"),
    ("ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF 99", "holder_name"),
    ("FABRIKAM INC DES:BONUS ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DES:PAYRL ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DES:PAYROLL ID:1", "payroll_or_salary"),
    ("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "payroll_or_salary"),
    ("FABRIKAM INC DES:EXP REIMB ID:1", "payroll_or_salary"),
    ("SSA TREAS 310 DES:XXSOC SEC ID:1", "personal_income"),
    ("FABRIKAM HOLDINGS LLC DES:INVESTMENT ID:1", "non_sale_purpose"),
    ("FABRIKAM PARTNERS LP DES:DISTRIB ID:1", "non_sale_purpose"),
    ("FABRIKAM SUPPLY INC DES:REBATE ID:1", "non_sale_purpose"),
    ("COMPTROLLER OF MD DES:MDREFUND ID:1", "non_sale_purpose"),
    ("IRS TREAS 310 DES:TAX EIC ID:1", "non_sale_purpose"),
    ("STATE OF OHIO DES:GRANT ID:1", "non_sale_purpose"),
    ("DIVIDEND", "non_sale_purpose"),
    ("WIRE IN DATE 540102 TRN 123", "wire_no_sender"),
    ("ONLINE BANKING TRANSFER CREDIT REF 88", "transfer_no_counterparty"),
    ("TELLER TRANSFER", "transfer_no_counterparty"),
    ("ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234 REF IB0ABCD", "transfer_account_designation"),
    ("WIRE IN FROM JOHN SMITH TRN 99", "wire_named_sender"),
    ("MOBILE DEPOSIT", "check_deposit"),
    ("REMOTE ONLINE DEPOSIT 1", "check_deposit"),
    ("COUNTER CREDIT", "no_payer_printed"),
    ("BRANCH DEPOSIT", "no_payer_printed"),
    ("DEPOSIT", "no_payer_printed"),
    ("ZELLE PAYMENT FROM JOHN SMITH CONF 99", "p2p"),
    ("ONLINE TRANSFER FROM JOHN SMITH REF IB0ABCD", "p2p"),
    ("SQUARE INC DES:TRANSFER ID:1", "platform_unconfirmed"),
    ("SEZZLE DES:PAYOUT ID:1", "payout_credit_entity"),
    ("DIRECT DEPOSIT 1234567", "numbered_company_payer"),
    ("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1", "numbered_company_payer"),
    ("NORTHWIND LANDSCAPE DES:SETTLEMENT ID:1", "named_payer_purpose_refused"),
    ("NORTHWIND SUPPLY DES:CREDIT ID:1", "named_payer_one_off"),
    ("NORTHWIND LANDSCAPE", "named_payer_unlabelled"),
])
def test_each_reason_code(text, reason):
    record = _one(text)
    assert _tier(record) == (REVENUE_TIER_REASONS[reason][0], reason)
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_review_required is (REVENUE_TIER_REASONS[reason][0] == "excluded_pending_review")


def test_a_direction_conflict_and_a_payer_debited_as_a_lender_or_otherwise_are_held():
    conflict = classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-02", description="NORTHWIND SUPPLY DES:PAYMENT ID:1", amount=500.0,
                    direction="debit")]))[0]
    assert _tier(conflict) == ("excluded_pending_review", "direction_conflict")
    # An unregistered funder that funds and then collects on a weekly cadence (D6 makes its debits potential).
    lender = classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-01", description="NORTHWIND VENTURES DES:PAYMENT ID:1", amount=9000.0,
                    direction="credit"),
        *(Transaction(date=f"2054-03-{day:02d}", description="NORTHWIND VENTURES DES:DEBIT ID:2", amount=-300.0,
                      direction="debit") for day in (2, 9, 16, 23)),
    ]))
    assert {record.classification for record in lender[1:]} == {"potential_lender"}
    assert _tier(lender[0]) == ("excluded_pending_review", "payer_debited_as_lender")
    affiliate = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1", 5000.0), ("NORTHWIND SUPPLY DES:DEBIT ID:2", -250.0)])
    assert _tier(affiliate[0]) == ("excluded_pending_review", "payer_also_debited")
    # The verifier's funder statement: an AP-worded credit and same-name debits no rule classifies as a lender.
    funder = _records([("NORTHWIND SUPPLY DES:VENDOR PAY ID:1", 5000.0),
                       *[("NORTHWIND SUPPLY DES:DEBIT ID:2", -250.0 - day) for day in range(5)]])
    assert _tier(funder[0]) == ("excluded_pending_review", "payer_also_debited")


def test_a_factoring_payout_is_counted_and_keeps_its_flag():
    record = _one("RTS FINANCIAL DES:PAYMENT ID:1")
    assert _tier(record) == ("counted_flagged", "factoring_payout")
    assert record.flagged_group == "factoring"


def test_round_sums_from_one_sender_are_held_on_rails_and_named_transfers_alike():
    rails = _records([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0), ("ZELLE PAYMENT FROM JOHN SMITH CONF 2", 700.0),
                      ("ZELLE PAYMENT FROM JOHN SMITH CONF 3", 123.0)])
    assert [_tier(record)[1] for record in rails] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]
    one_round = _records([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0),
                          ("ZELLE PAYMENT FROM JOHN SMITH CONF 2", 123.0)])
    assert [_tier(record)[1] for record in one_round] == ["p2p", "p2p"]
    transfers = _records([("ONLINE TRANSFER FROM JOHN SMITH REF 1", 300.0),
                          ("ONLINE TRANSFER FROM JOHN SMITH REF 2", 300.0)])
    assert [_tier(record)[1] for record in transfers] == ["p2p_round_repeat", "p2p_round_repeat"]


def test_q5_verifies_a_company_that_wires_twice_and_its_guards_refuse():
    wire = "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK ID:1"
    twice = _records([(wire.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0),
                      (wire.format(n=2, orig="NORTHWIND EXPORTS LLC"), 26000.0)])
    assert {record.revenue_match_method for record in twice} == {"repeat_wire_sender"}
    once = _records([(wire.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0)])
    assert _tier(once[0]) == ("counted_flagged", "wire_named_sender")
    for orig in ("JOHN SMITH", "SAMPLE BANK NA", "NORTHWIND TITLE LLC", "1234567 ONTARIO INC"):
        rows = _records([(wire.format(n=1, orig=orig), 25000.0), (wire.format(n=2, orig=orig), 26000.0)])
        assert {record.revenue_classification for record in rows} == {"unverified_deposit"}, orig
    investment = _records([(wire.format(n=1, orig="FABRIKAM VENTURES LLC") + " OBI SERIES A INVESTMENT", 50000.0),
                           (wire.format(n=2, orig="FABRIKAM VENTURES LLC") + " OBI SERIES A INVESTMENT", 50000.0)])
    assert {_tier(record) for record in investment} == {("excluded_pending_review", "non_sale_purpose")}
    payroll = _records([(wire.format(n=1, orig="FABRIKAM INC") + " OBI PAYROLL JAN", 9000.0),
                        (wire.format(n=2, orig="FABRIKAM INC") + " OBI PAYROLL JAN", 9000.0)])
    assert {_tier(record) for record in payroll} == {("excluded_pending_review", "payroll_or_salary")}


def test_a_third_party_book_transfer_sweep_is_held():
    rows = _records([("BOOK TRANSFER CREDIT B/O: FABRIKAM HOLDINGS LLC SAMPLEVILLE REF: INTERCO SWEEP", 20000.0)] * 2)
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


def test_q6_verifies_a_repeat_a_company_form_and_a_public_or_healthcare_payer():
    repeat = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1 CCD", 700.0), ("NORTHWIND SUPPLY DES:PAYMENT ID:2 CCD", 710.0)])
    assert {record.revenue_match_method for record in repeat} == {"named_payer_repeats"}
    consumer = _records([("NORTHWIND SUPPLY DES:PAYMENT ID:1 PPD", 700.0),
                         ("NORTHWIND SUPPLY DES:PAYMENT ID:2 PPD", 710.0)])
    assert {record.revenue_classification for record in consumer} == {"unverified_deposit"}
    assert _one("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1").revenue_match_method == "named_payer_company_form"
    assert _one("SAMPLE COUNTY DES:PAYMENT ID:1").revenue_match_method == "public_or_healthcare_payer"
    assert _one("AETNA DES:PAYMENT ID:1").revenue_match_method == "public_or_healthcare_payer"
    assert _tier(_one("AETNA DES:MEMBER REIMB ID:1")) == ("excluded_pending_review", "non_sale_purpose")


def test_a_held_row_never_makes_a_repeat():
    rows = _records([("NORTHWIND SUPPLY DES:RETURN ID:1", 50.0), ("NORTHWIND SUPPLY DES:CREDIT ID:2", 700.0)])
    assert [_tier(record) for record in rows] == [
        ("excluded_pending_review", "possible_return"), ("counted_flagged", "named_payer_one_off")]


def test_a_distributor_and_an_owner_operator_are_customers():
    assert _one("FABRIKAM DISTRIBUTORS INC DES:PAYMENT ID:1").revenue_tier == "verified"
    assert _one("FABRIKAM CARRIERS INC DES:OWNER OP ID:1").revenue_tier == "verified"


def test_the_registry_is_exempt_from_the_holder_test():
    record = _one("SQUARE INC DES:SQ540115 ID:1", holder="SQUARE ONE BAKERY LLC")
    assert _tier(record) == ("verified", None)


def test_the_four_tiers_add_up_to_the_posted_credits():
    records = _records([("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), ("MOBILE DEPOSIT", 300.0),
                        ("FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), ("INTERNAL TRANSFER FROM SAVINGS", 100.0),
                        ("FABRIKAM SUPPLY DES:DEBIT ID:1", -50.0)])
    tiers = {}
    for record in records:
        if record.amount > 0:
            tiers[record.revenue_tier] = tiers.get(record.revenue_tier, 0.0) + record.amount
    assert tiers == {"verified": 700.0, "counted_flagged": 300.0, "excluded_pending_review": 900.0,
                     "non_revenue": 100.0}
    assert records[4].revenue_tier is None


# ---------------------------------------------------------------------------------------------------------------------
# The review's holes (2026-09-29): refunds, platform capital, the holder's own ACH transfer, paychecks, title firms,
# card refunds and the auction's refunds, each alone and repeated.
# ---------------------------------------------------------------------------------------------------------------------
REFUNDS = [
    "FABRIKAM INC DES:REFUNDS ID:1",
    "FABRIKAM INC DES:REFUNDING ID:1",
    "FABRIKAM INC DES:CUST REFUNDS ID:1",
    "FABRIKAM INC DES:REFUNDREQ ID:1",
    "FABRIKAM INC DES:PREFUND ID:1",
    "NORTHWIND SUPPLY DES:REFUNDS ID:1 CCD",
    "ORIG CO NAME:FABRIKAM INC ORIG ID:1 DESC DATE: CO ENTRY DESCR:REFUNDS SEC:CCD",
]


@pytest.mark.parametrize("text", REFUNDS)
def test_a_refund_word_glued_or_not_is_held_alone_and_repeated(text):
    # Review C1: the financing root reads FUND only when RE does not precede it (a refund is no funding), so the
    # refund words hold the row as a non-sale purpose; a repeat or a company form never verifies it.
    alone = _one(text, 250.0)
    assert _tier(alone) == ("excluded_pending_review", "non_sale_purpose")
    repeated = _records([(text, 250.0), (text.replace("ID:1", "ID:2"), 260.0)])
    assert {_tier(record) for record in repeated} == {("excluded_pending_review", "non_sale_purpose")}


@pytest.mark.parametrize("text", [
    "STRIPE DES:CAPITAL ID:1", "SHOPIFY DES:CAPITAL ID:1", "DOORDASH INC DES:CAPITAL ID:1", "TOAST INC DES:CAPITAL ID:1",
    "CLOVER DES:CAPITAL ADV ID:1", "SPOTON DES:ADVANCE ID:1", "HEARTLAND PAYMENT SYSTEMS DES:FUNDING ID:1",
    "UBER DES:ADVANCE ID:1", "ETSY DES:FUNDING ID:1", "MANHEIM US DES:FUNDING ID:1", "MANHEIM US DES:FLOORPLAN ID:1",
    "MANHEIM US DES:ACH PAYMNT NGC ID:1",
])
def test_a_platform_s_capital_or_an_auction_s_floor_plan_credit_is_held(text):
    # Review C2: the registry never claims a row that prints a financing word, so it is held as financing.
    records = _records([(text, 15000.0), (text.replace("ID:1", "ID:2"), 15001.0),
                        (text.replace("ID:1", "ID:3"), 15002.0)], holder="SAMPLE MOTORS LLC")
    assert {_tier(record) for record in records} == {("excluded_pending_review", "financing_named_payer")}


def test_a_platform_s_own_settlement_words_keep_it_counted():
    # §7.0: TapGoods prints FUNDING on its settlements; a delivery platform prints the merchant's store (the
    # holder's own words) in its entry field. Neither is financing.
    tapgoods = _one("TGPAYMENTS DES:FUNDING ID:1", 900.0)
    assert _tier(tapgoods) == ("counted_flagged", "platform_unconfirmed")
    store = _one("DOORDASH INC DES:SAMPLE CAPITA ID:1 INDN:SAMPLE CAPITAL GROUP CO ID:1 CCD", 900.0,
                 holder="SAMPLE CAPITAL GROUP LLC")
    assert _tier(store) == ("counted_flagged", "platform_unconfirmed")


@pytest.mark.parametrize("text", [
    "CONTOSO BAKERY DES:TRANSFER ID:1",
    "CONTOSO BAKERY LLC DES:XFER ID:1 CCD",
    "ORIG CO NAME:CONTOSO BAKERY LLC ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:CCD",
])
def test_the_holder_s_own_ach_transfer_is_held(text):
    # Review C3: a transfer-worded ACH row with no FROM sender reads its originator as its payer.
    assert _tier(_one(text, 10000.0)) == ("excluded_pending_review", "holder_name")


def test_an_ach_transfer_from_a_payer_the_statement_also_debits_is_held():
    records = _records([
        ("NORTHWIND BAKERY DES:TRANSFER ID:1 INDN:NORTHWIND BAKERY CO ID:1 CCD", 5000.0),
        ("NORTHWIND BAKERY DES:TRANSFER ID:2 INDN:NORTHWIND BAKERY CO ID:1 CCD", -3000.0),
    ], holder="BUSINESS CHECKING")
    assert _tier(records[0]) == ("excluded_pending_review", "payer_also_debited")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYCHECK ID:1 PPD", "FABRIKAM INC DES:PR PAYMENT ID:1", "FABRIKAM INC DES:EMPLOYEE PAY ID:1 PPD",
])
def test_a_paycheck_is_payroll(text):
    # Review I6: PAYCHECK, PR PAY and EMPLOYEE PAY join Q8's pay words.
    assert _tier(_one(text, 2500.0)) == ("excluded_pending_review", "payroll_or_salary")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYMENT ID:1 PPD",          # a consumer entry never verifies by its company form (review I6)
    "NORTHWIND TITLE LLC DES:PAYMENT ID:1",       # a title firm is no customer (§8.5's senders)
    "SAMPLE COMMUNITY BANK INC DES:PAYMENT ID:1",  # nor is a bank
])
def test_a_consumer_entry_a_title_firm_or_a_bank_never_verifies_by_its_company_form(text):
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")


@pytest.mark.parametrize("text", [
    "VISA CREDIT FABRIKAM STORE", "CHECKCARD CREDIT FABRIKAM STORE", "PURCHASE CREDIT FABRIKAM STORE",
    "MANHEIM US DES:DEALSHIELD ID:1", "MANHEIM US DES:ARB CREDIT ID:1",
])
def test_a_card_refund_and_an_auction_refund_are_possible_returns(text):
    # Review M6 and §7.8: a card credit's posting label and an auction's guarantee or arbitration refund.
    assert _tier(_one(text, 80.0, holder="SAMPLE MOTORS LLC")) == ("excluded_pending_review", "possible_return")


def test_q5_never_verifies_a_wire_that_prints_a_push_rail():
    # §6.1 step 9b: a real-time or push rail verifies through the registry only, never by Q5's repeats.
    wire = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} ORIG:FABRIKAM EXPORTS LLC ID:1 SND BK:SAMPLE BANK "
            "ID:1 PMT DET:PAYMENT RECEIVED")
    records = _records([(wire.format(n=1), 20000.0), (wire.format(n=2), 21000.0)])
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}
