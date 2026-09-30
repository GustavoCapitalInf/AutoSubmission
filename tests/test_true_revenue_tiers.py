"""Classification 5.6 (true revenue spec §5.3, §8, T11 to T14): the tier and reason of every posted credit, the holds,
the channel tiers, and the Q5, Q6 and Q7 verifications with their guards. Fabricated rows only, in the banks' printed
formats."""
from __future__ import annotations

import pytest

from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import _debit_first_distinctive_word, classify_statement_transactions

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


def test_q7_dealer_funding_from_a_listed_auto_lender():
    record = _one("WESTLAKE FINANCI DES:PAYABLES ID:EFT1234567 INDN:SAMPLE MOTORS LLC CO ID:1 CCD", holder="SAMPLE MOTORS LLC")
    assert (record.revenue_match_method, record.revenue_source_type) == (
        "auto_lender_dealer_funding", "auto_dealer_funding")
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", [
    "KAPITUS DES:CONTRACT FUNDING ID:1",
    "ONDECK CAPITAL DES:DEAL FUND ID:1",
    "GEICO DES:VEHICLE PURCHASE ID:1",
])
def test_q7_never_fires_on_a_lender_or_insurer_outside_vehicle_financing(text):
    assert _one(text).revenue_classification == "non_revenue"


def test_q7_refuses_a_loan_word_and_the_credit_union_arm_needs_two_credits():
    loan = _one("SUNCOAST CREDIT UNION DES:VHCL PURCH LOAN PROCEEDS ID:1")
    assert loan.revenue_classification != "verified_revenue"
    union = "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:{n}"
    two = _records([(union.format(n=1), 18000.0), (union.format(n=2), 21000.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_match_method for record in two} == {"auto_lender_dealer_funding"}
    lone = _records([(union.format(n=1), 18000.0)], holder="SAMPLE MOTORS LLC")
    assert _tier(lone[0]) == ("excluded_pending_review", "financing_named_payer")


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


@pytest.mark.parametrize("payer", ["NORTHWIND SUPPLY LLC DES:PAYMENT", "NORTHWIND SUPPLY DES:PAYMENT ID:1"])
@pytest.mark.parametrize("card", [
    "CHECKCARD 0302 NORTHWIND GRILL",
    "CARD PURCHASE 03 02 NORTHWIND GRILL HOUSTON TX CARD 1234",
    "PURCHASE AUTHORIZED ON 03/02 NORTHWIND GRILL HOUSTON TX S123456789 CARD 1234",
])
def test_a_card_purchase_at_a_merchant_sharing_the_payer_s_word_never_holds_the_payer(payer, card):
    # A1 census: a card purchase is spending at a merchant, never the circular money payer_also_debited holds. Pass 6
    # still reads the merchant's word (tests/test_revenue_payer_remittance.py); pass 7's hold leaves it out.
    alone = _one(payer, 5000.0)
    records = _records([(payer, 5000.0), (card, -25.0)])
    assert _debit_first_distinctive_word(records[1]) == "NORTHWIND"
    assert alone.revenue_tier != "excluded_pending_review"
    assert (records[0].revenue_classification, *_tier(records[0])) == (alone.revenue_classification, *_tier(alone))


@pytest.mark.parametrize("payer", ["NORTHWIND SUPPLY LLC DES:PAYMENT", "NORTHWIND SUPPLY DES:PAYMENT ID:1"])
def test_the_same_payer_beside_an_ach_debit_is_still_held_as_also_debited(payer):
    records = _records([(payer, 5000.0), ("NORTHWIND SUPPLY LLC DES:INVOICE", -250.0)])
    assert _tier(records[0]) == ("excluded_pending_review", "payer_also_debited")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYCHECK ID:1 PPD", "FABRIKAM INC DES:PR PAYMENT ID:1", "FABRIKAM INC DES:EMPLOYEE PAY ID:1 PPD",
])
def test_a_paycheck_is_payroll(text):
    # Review I6: PAYCHECK, PR PAY and EMPLOYEE PAY join Q8's pay words.
    assert _tier(_one(text, 2500.0)) == ("excluded_pending_review", "payroll_or_salary")


@pytest.mark.parametrize("text", [
    "FABRIKAM INC DES:PAYMENT ID:1 PPD",          # a consumer entry never verifies by its company form (review I6)
    "SAMPLE COMMUNITY BANK INC DES:PAYMENT ID:1",  # nor is a bank
])
def test_a_consumer_entry_or_a_bank_never_verifies_by_its_company_form(text):
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")


def test_a_title_firm_never_verifies_by_its_company_form_and_is_held():
    # §8.5's senders; A3 (precision sample): a title firm's payment is property-closing proceeds, held.
    assert _tier(_one("NORTHWIND TITLE LLC DES:PAYMENT ID:1", 2500.0)) == ("excluded_pending_review", "non_sale_purpose")


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


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 review, fix round 1 (2026-09-29): direction conflicts, leading dates, bare transfers, micro-deposits, loose
# wires, registry and family rows, deferred sources and owner money, senders printed without FROM, and wires from
# public or healthcare payers.
# ---------------------------------------------------------------------------------------------------------------------
WIRE = "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} ORIG:{orig} ID:99 SND BK:SAMPLE BANK ID:1"


def _directed(rows, *, holder: str | None = HOLDER):
    """Rows of (text, amount) or (text, amount, direction): a positive amount printed as a debit is a conflict."""
    return classify_statement_transactions(Statement(account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=row[0], amount=row[1],
                    direction=row[2] if len(row) > 2 else ("credit" if row[1] > 0 else "debit"))
        for index, row in enumerate(rows)
    ]))


CONFLICT = ("excluded_pending_review", "direction_conflict")


@pytest.mark.parametrize("text", ["NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "SAMPLE COUNTY DES:PAYMENT ID:1",
                                  "AETNA DES:PAYMENT ID:1"])
def test_q6_never_lifts_a_direction_conflict(text):
    # §6.1 step 2, §7.0 (review C1): a direction conflict is never lifted, by this pass or any other.
    [record] = _directed([(text, 500.0, "debit")])
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == CONFLICT


def test_a_direction_conflict_beside_two_good_repeats_stays_held_and_never_counts():
    rows = _directed([("NORTHWIND SUPPLY DES:PAYMENT ID:1 CCD", 500.0), ("NORTHWIND SUPPLY DES:PAYMENT ID:2 CCD", 510.0),
                      ("NORTHWIND SUPPLY DES:PAYMENT ID:3 CCD", 520.0, "debit")])
    assert [record.revenue_match_method for record in rows[:2]] == ["named_payer_repeats"] * 2
    assert _tier(rows[2]) == CONFLICT and rows[2].revenue_classification == "unverified_deposit"
    # A conflict never makes another row a repeat.
    one = _directed([("NORTHWIND SUPPLY DES:PAYMENT ID:1 CCD", 500.0), ("NORTHWIND SUPPLY DES:PAYMENT ID:2 CCD", 510.0,
                                                                        "debit")])
    assert _tier(one[0]) == ("counted_flagged", "named_payer_one_off")
    assert _tier(one[1]) == CONFLICT


def test_q5_never_lifts_a_direction_conflict_and_never_counts_it():
    rows = _directed([(WIRE.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0),
                      (WIRE.format(n=2, orig="NORTHWIND EXPORTS LLC"), 26000.0),
                      (WIRE.format(n=3, orig="NORTHWIND EXPORTS LLC"), 27000.0, "debit")])
    assert [record.revenue_match_method for record in rows[:2]] == ["repeat_wire_sender"] * 2
    assert _tier(rows[2]) == CONFLICT and rows[2].revenue_classification == "unverified_deposit"
    one = _directed([(WIRE.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0),
                     (WIRE.format(n=2, orig="NORTHWIND EXPORTS LLC"), 26000.0, "debit")])
    assert _tier(one[0]) == ("counted_flagged", "wire_named_sender")


def test_a_direction_conflict_never_makes_a_round_sum_repeat():
    rows = _directed([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0),
                      ("ZELLE PAYMENT FROM JOHN SMITH CONF 2", 600.0, "debit")])
    assert [_tier(record) for record in rows] == [("counted_flagged", "p2p"), CONFLICT]


@pytest.mark.parametrize("text", [
    "03/02 1234567 ONTARIO INC DES:PAYMENT ID:1", "0302 1234567 ONTARIO INC DES:PAYMENT ID:1",
    "03/021234567 ONTARIO INC DES:PAYMENT ID:1",
])
def test_a_leading_date_never_hides_a_numbered_company(text):
    # §5.2, T11 (review I1): the numbered-company guard reads past a leading date, spaced, run together or glued to
    # the number, so the company form and the repeats never verify the owner's possible holding company.
    assert _tier(_one(text, 700.0)) == ("counted_flagged", "numbered_company_payer")
    repeated = _records([(text, 700.0), (text.replace("ID:1", "ID:2"), 710.0)])
    assert {_tier(record) for record in repeated} == {("counted_flagged", "numbered_company_payer")}


def test_the_numbered_guard_reads_past_a_date_only_before_the_number():
    # A spaced pair before a name (Fifth Third's 5/3 brand prints so) never makes the name a numbered company.
    from analysis import transaction_classifier as classifier

    assert classifier.numbered_company("03 02 DIRECT DEPOSIT 7654321 CANA AP CC")
    assert not classifier.numbered_company("5 3 FABRIKAM SUPPLY LLC DES PAYMENT ID 1")
    assert _one("5/3 FABRIKAM SUPPLY LLC DES:PAYMENT ID:1", 700.0).revenue_match_method == "named_payer_company_form"


@pytest.mark.parametrize("text", [
    "EXTERNAL TRANSFER DES:TRANSFER ID:1234", "WEB TRANSFER DES:TRANSFER ID:1 WEB",
    "TRANSFER DES:TRANSFER ID:ABC123 CCD", "ORIG CO NAME:TRANSFER ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:PPD",
    "ONLINE TRANSFER REF #IBEABCD", "ONLINE TRANSFER FROM HELOC", "TRANSFER FROM LOC 1234", "TRANSFER FROM TAX RESERVE",
    "ONLINE TRANSFER FROM OPERATING", "TRANSFER FROM RESERVE", "ONLINE TRANSFER FROM PRIMARY", "TRANSFER FROM PERSONAL",
    "ONLINE TRANSFER FROM JOINT", "ONLINE TRANSFER FROM IRA",
])
def test_a_bare_transfer_or_an_own_account_nickname_is_held(text):
    # Q2 (review I2): field labels, SEC codes, references and account descriptions are no counterparty.
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.transaction_classifier import revenue_text

    assert _tier(_one(text, 500.0)) == ("excluded_pending_review", "transfer_no_counterparty")
    record = _one(text, 500.0)
    facts = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
    assert facts["transfer_no_counterparty"]


def test_a_named_transfer_keeps_its_counterparty():
    assert _tier(_one("ONLINE TRANSFER FROM JOHN SMITH REF IB0ABCD", 250.0)) == ("counted_flagged", "p2p")
    assert _tier(_one("TRANSFER JOHN SMITH REF IBEABCD", 250.0)) == ("counted_flagged", "p2p")


MICRO = ("excluded_pending_review", "non_sale_purpose")


def test_a_credit_under_one_dollar_never_verifies_and_never_counts():
    # §7.0, §8.10 (review I3): the micro-deposit floor is absolute; a verify entry never makes a payment a repeat.
    assert _tier(_one("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 0.37)) == MICRO
    verify = _records([("FABRIKAM INC DES:VERIFY ID:1 CCD", 0.12), ("FABRIKAM INC DES:VERIFY ID:2 CCD", 0.34)])
    assert [_tier(record) for record in verify] == [MICRO, MICRO]
    assert {record.revenue_classification for record in verify} == {"unverified_deposit"}
    repeat = _records([("FABRIKAM SUPPLY DES:VERIFY ID:1 CCD", 0.12), ("FABRIKAM SUPPLY DES:PAYMENT ID:2 CCD", 700.0)])
    assert [_tier(record) for record in repeat] == [MICRO, ("counted_flagged", "named_payer_one_off")]
    assert _tier(_one("SQUARE INC DES:TRANSFER ID:1", 0.32)) == MICRO
    # One dollar is not under the floor.
    assert _one("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 1.0).revenue_match_method == "named_payer_company_form"


# S4.4/S4.5 review, fix round 1 (2026-09-30): the $1 floor is absolute (§7.0, §7.8, §8.10). A single-row rule that
# verifies a credit under $1 (the registry's own context, a card settlement form, a verified descriptor, an AP
# remittance, an invoice wire) is overruled by pass 7's last step: the credit is held, never verified, never counted.
@pytest.mark.parametrize(("text", "method"), [
    ("SQUARE INC DES:SQ540115 ID:1", "operating_source_with_credit_context"),
    ("STRIPE DES:TRANSFER ID:ST-A1B2C3", "operating_source_with_credit_context"),
    ("MERCHANT BANKCD DES:DEPOSIT ID:1234567", "operating_income_descriptor"),
    ("NORTHWIND SUPPLY LLC DES:INVOICE PAYMENT ID:1", "operating_income_descriptor"),
    ("NORTHWIND SUPPLY LLC DES:ACCTS PAYABLE ID:1", "payer_remittance_descriptor"),
    ("WIRE TYPE:WIRE IN ORIG:NORTHWIND SUPPLY LLC OBI:INV 1234", "payer_remittance_descriptor"),
])
def test_the_floor_overrules_every_rule_that_verifies_a_credit_under_one_dollar(text, method):
    # One dollar is not under the floor: the rule verifies it.
    whole = _one(text, 1.0)
    assert (whole.revenue_classification, whole.revenue_match_method, _tier(whole)) == (
        "verified_revenue", method, ("verified", None))
    for amount in (0.03, 0.5, 0.99):
        record = _one(text, amount)
        assert _tier(record) == MICRO
        assert (record.revenue_classification, record.revenue_initial_classification) == (
            "unverified_deposit", "unverified_deposit")
        assert record.revenue_initial_tier == "excluded_pending_review"
        assert (record.revenue_match_method, record.revenue_review_status) == ("micro_deposit_floor", "pending")
        assert method in record.revenue_reason        # the audit keeps the rule the floor overruled
        assert record.revenue_review_required and record.contributes_to_excluded_pending_review
        assert not (record.contributes_to_verified_revenue or record.contributes_to_true_revenue
                    or record.contributes_to_counted_flagged)


def test_a_statement_s_figures_never_carry_a_credit_under_one_dollar():
    from analysis.metrics import compute_metrics

    statement = Statement(account_name=HOLDER, currency="USD", transactions=[
        Transaction(date="2054-03-02", description="SQUARE INC DES:SQ540115 ID:1", amount=0.03, direction="credit"),
        Transaction(date="2054-03-03", description="SQUARE INC DES:SQ540115 ID:2", amount=500.0, direction="credit"),
        Transaction(date="2054-03-04", description="NORTHWIND SUPPLY LLC DES:ACCTS PAYABLE ID:1", amount=0.5,
                    direction="credit"),
    ])
    records = classify_statement_transactions(statement)
    assert [_tier(record) for record in records] == [MICRO, ("verified", None), MICRO]
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.verified_revenue_total, metrics.true_revenue_total) == (500.0, 500.0)
    assert metrics.excluded_pending_review_by_reason == {"non_sale_purpose": {"count": 2, "total": 0.53}}


@pytest.mark.parametrize("loose", [
    "FABRIKAM EXPORTS LLC DES:WIRE PMT ID:1",
    "FABRIKAM EXPORTS LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD PMT INFO:WIRE REF 1",
    "123456W1234567WIRE FROM FABRIKAM EXPORTS LLC DES:PAYMENT",
])
def test_only_an_incoming_wire_counts_toward_a_q5_repeat(loose):
    # §8.5 (review I4): the loose wire words are for tiering only.
    rows = _records([(WIRE.format(n=1, orig="FABRIKAM EXPORTS LLC"), 25000.0), (loose, 7000.0)])
    assert [_tier(record) for record in rows] == [("counted_flagged", "wire_named_sender")] * 2


@pytest.mark.parametrize(("rows", "holder"), [
    ([(WIRE.format(n=1, orig="MANHEIM US INC"), 25000.0), (WIRE.format(n=2, orig="MANHEIM US INC"), 26000.0)],
     "SAMPLE MOTORS LLC"),
    ([(WIRE.format(n=1, orig="SUPER DISPATCH INC"), 2500.0), (WIRE.format(n=2, orig="SUPER DISPATCH INC"), 2600.0)],
     HOLDER),
    ([("SUPER DISPATCH INC DES:CASHOUT ID:1", 800.0), ("SUPER DISPATCH DES:CASHOUT ID:1 CCD", 810.0),
      ("SUPER DISPATCH DES:CASHOUT ID:2 CCD", 820.0)], HOLDER),
    ([("SUPER DISPATCH INC DES:MEMBERSHIP ID:1", 800.0)], HOLDER),
    ([("TIKTOK INC DES:TIKTOKSHOP ID:1", 800.0)], HOLDER),
    ([("NORTHWIND LAW GROUP LLC DES:NET SETTLE ID:1", 5000.0)], HOLDER),
    ([("SAMPLE TRUST DES:NET SETTLE ID:1 CCD", 900.0), ("SAMPLE TRUST DES:NET SETTLE ID:2 CCD", 950.0)], HOLDER),
    ([("FABRIKAM PAYMENTS LLC DES:NET SETTLE ID:1", 800.0)], HOLDER),
])
def test_q5_and_q6_leave_a_registry_or_net_settle_row_to_its_own_rule(rows, holder):
    # §7.1, §7.3, §7.8, §7.2 (review I5): a row the operating registry names, and a NET SETTLE row, is decided by its
    # family's rule alone; Q5 and Q6 never verify it.
    records = _records(rows, holder=holder)
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}
    assert {record.revenue_tier for record in records} == {"counted_flagged"}


def test_three_net_settle_credits_still_verify_by_the_card_rule():
    records = _records([(f"FABRIKAM PAYMENTS LLC DES:NET SETTLE ID:{n}", 800.0 + n) for n in (1, 2, 3)])
    assert {record.revenue_matched_rule for record in records} == {"card_settlement_form_net_settle"}


@pytest.mark.parametrize("text", [
    "LYFT INC DES:PAYMENT ID:1", "SHIPT INC DES:PAYOUT ID:1", "PAYONEER INC DES:WITHDRAWAL ID:1",
    "GOODLEAP LLC DES:PAYMENT ID:1", "MODIVCARE SOLUTIONS LLC DES:PAYMENT ID:1", "TIPALTI INC DES:PAYMENT ID:1",
    "MELIO PAYMENTS INC DES:PAYMENT ID:1",
])
def test_a_deferred_source_stays_counted_until_ruled(text):
    # §15, §19 OQ4 (review I6a): the deferred items stay counted and flagged until the owner rules. S4.2 re-review
    # (fix round 2): Q5 and Q6 refuse them as proof whatever their count, so their reason is §8.9's
    # named_payer_purpose_refused, never "One-off payer" (a deferred source often repeats).
    assert _tier(_one(text, 700.0)) == ("counted_flagged", "named_payer_purpose_refused")
    repeated = _records([(text + " CCD", 700.0), (text.replace("ID:1", "ID:2") + " CCD", 710.0)])
    assert {record.revenue_classification for record in repeated} == {"unverified_deposit"}
    assert {_tier(record) for record in repeated} == {("counted_flagged", "named_payer_purpose_refused")}


def test_a_deferred_source_s_wires_are_refused_and_its_unlabelled_row_keeps_its_channel_reason():
    # S4.2 re-review (fix round 2): Q5 refuses a deferred sender's repeated wires as proof; a row with no
    # electronic-payment form is never read by Q6, deferred or not, so it keeps named_payer_unlabelled.
    wires = _records([(WIRE.format(n=1, orig="LYFT INC"), 9000.0), (WIRE.format(n=2, orig="LYFT INC"), 9100.0)])
    assert {_tier(record) for record in wires} == {("counted_flagged", "named_payer_purpose_refused")}
    assert _tier(_one("MODIVCARE SOLUTIONS 1234", 700.0)) == ("counted_flagged", "named_payer_unlabelled")


def test_a_healthcare_payer_s_bare_x12_trace_stays_counted():
    # §7.7: a bare X12 TRN*1* with no entry description is out (counted and flagged); with an entry it verifies.
    assert _tier(_one("ACH CREDIT AETNA TRN*1*123456789*1234567890", 700.0)) == ("counted_flagged",
                                                                                  "named_payer_purpose_refused")
    assert _one("AETNA DES:PAYMENT ID:1", 700.0).revenue_match_method == "public_or_healthcare_payer"


@pytest.mark.parametrize("text", [
    "CHARLES SCHWAB & CO INC DES:MONEYLINK ID:1", "ROBINHOOD SECURITIES LLC DES:WITHDRAWAL ID:1",
    "COINBASE INC DES:WITHDRAWAL ID:1", "E*TRADE SECURITIES LLC DES:ACH TRNSFR ID:1",
    "FIDELITY BROKERAGE SERVICES LLC DES:MONEYLINE ID:1", "VANGUARD MARKETING CORP DES:REDEMPTION ID:1",
    "INTERACTIVE BROKERS LLC DES:PAYMENT ID:1", "WEBULL DES:WITHDRAWAL ID:1", "MERRILL EDGE DES:PAYMENT ID:1",
    "FABRIKAM WEALTH MANAGEMENT LLC DES:PAYMENT ID:1",
])
def test_owner_money_from_a_brokerage_or_an_exchange_is_held(text):
    # §7.5's investment words and the standing rule (review I6b): owner money never becomes revenue.
    assert _tier(_one(text, 3000.0)) == ("excluded_pending_review", "non_sale_purpose")


def test_q5_never_verifies_a_securities_firm_s_wires():
    rows = _records([(WIRE.format(n=1, orig="FABRIKAM SECURITIES LLC"), 25000.0),
                     (WIRE.format(n=2, orig="FABRIKAM SECURITIES LLC"), 26000.0)])
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


@pytest.mark.parametrize("text", [
    "FABRIKAM WEALT DES:PAYABLES ID:1", "FABRIKAM BROKERAGE LLC DES:ACCOUNTS PAYABLE ID:1",
    "FABRIKAM SECURITIES INC DES:VENDOR PAYMENT ID:1",
])
def test_the_investment_words_spare_an_accounts_payable_payment(text):
    # S4.2 fix measurement: a wealth, brokerage or securities firm paying a vendor from its payables pays the business
    # for a sale; it is not the holder's own money. §7.5's remittance veto still reads the words, so the row is counted
    # and flagged, never verified: alone, by its company form, or repeated.
    record = _one(text, 3000.0)
    assert _tier(record) == ("counted_flagged", "named_payer_purpose_refused")
    assert record.revenue_classification == "unverified_deposit"
    repeated = _records([(text, 3000.0), (text.replace("ID:1", "ID:2"), 3100.0)])
    assert {record.revenue_classification for record in repeated} == {"unverified_deposit"}
    assert {_tier(record) for record in repeated} == {("counted_flagged", "named_payer_purpose_refused")}


def test_q5_never_verifies_a_securities_firm_s_vendor_payment_wires():
    rows = _records([(WIRE.format(n=1, orig="FABRIKAM SECURITIES LLC") + " OBI VENDOR PAYMENT", 25000.0),
                     (WIRE.format(n=2, orig="FABRIKAM SECURITIES LLC") + " OBI VENDOR PAYMENT", 26000.0)])
    assert {record.revenue_classification for record in rows} == {"unverified_deposit"}
    assert {_tier(record) for record in rows} == {("counted_flagged", "named_payer_purpose_refused")}


@pytest.mark.parametrize("text", [
    "FABRIKAM WEALT DES:DIVIDEND PAYABLES ID:1", "FABRIKAM BROKERAGE LLC DES:ACCOUNTS PAYABLE DISTRIB ID:1",
    "FABRIKAM SECURITIES INC DES:VENDOR PAYMENT OWNER DRAW ID:1",
])
def test_every_other_non_sale_word_still_holds_an_accounts_payable_payment(text):
    assert _tier(_one(text, 3000.0)) == ("excluded_pending_review", "non_sale_purpose")


@pytest.mark.parametrize("text", [
    "E*TRADE SECURITIES LLC DES:ACCOUNTS PAYABLE ID:1", "ROBINHOOD SECURITIES LLC DES:PAYABLES ID:1",
    "FIDELITY BROKERAGE SERVICES LLC DES:VENDOR PAYMENT ID:1",
])
def test_a_brokerage_platform_s_accounts_payable_wording_stays_held_by_the_platform_list(text):
    # The investment word is spared by the AP wording; the platform list still holds the owner's money.
    assert _tier(_one(text, 3000.0)) == ("excluded_pending_review", "non_sale_purpose")


def test_schwab_s_accounts_payable_wording_is_the_payer_s_vendor_payment():
    # S4.2 re-review (fix round 2, the orchestrator's ruling under the owner's delegation): accounts-payable wording is
    # the payer's vendor payment, revenue even from a brokerage. Owner money from Schwab prints as a transfer or a
    # MoneyLink (held by the platform list above); a PAYABLES entry is Schwab paying the business as its vendor, so
    # §7.5's payer remittance rule verifies it before pass 7.
    record = _one("CHARLES SCHWAB & CO INC DES:PAYABLES ID:1", 3000.0)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "verified_revenue", "payer_remittance_descriptor")
    assert _tier(record) == ("verified", None)


@pytest.mark.parametrize("rail", ["E TRANSFER AUTODEPOSIT {name} CA1234ABCD", "INTERAC E TRANSFER RECEIVED {name}",
                                  "ZELLE TRANSFER {name}", "ZELLE CREDIT {name} CONF 1"])
def test_a_p2p_sender_printed_without_from_takes_the_holder_test_and_the_round_repeat(rail):
    # Q4 (review I7): the sender printed after the rail label.
    assert _tier(_one(rail.format(name="CONTOSO BAKERY LLC"), 5000.0)) == ("excluded_pending_review", "holder_name")
    rows = _records([(rail.format(name="JOHN SMITH"), 500.0), (rail.format(name="JOHN SMITH"), 600.0),
                     (rail.format(name="JOHN SMITH"), 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize("text", [
    "VIREMENT INTERAC RECU {n}", "ZELLE DEBIT {n}", "VENMO DES:CASHOUT ID:{n}", "ZELLE TO JOHN SMITH {n}",
    "FABRIKAM INC 03 02 {n} PMNT RCVD FABRIKAM INC VISA DIRECT CA", "E TRANSFER {n} EPAY",
])
def test_a_rail_s_own_words_a_recipient_or_a_platform_before_a_push_rail_are_no_sender(text):
    # Q4 (review I7): no sender is read, so unrelated round sums are never one sender's repeat.
    rows = _records([(text.format(n=1), 500.0), (text.format(n=2), 600.0)])
    assert [_tier(record) for record in rows] == [("counted_flagged", "p2p")] * 2


def test_the_sender_follows_the_next_rail_and_a_numbered_sender_keeps_its_number():
    layout = "NOW NETWORK CREDIT ZELLE CREDIT NOW NET ID {n} ZELLE {name} 5678"
    rows = _records([(layout.format(n=1, name="JOHN SMITH"), 500.0), (layout.format(n=2, name="JOHN SMITH"), 600.0),
                     (layout.format(n=3, name="MARY JONES"), 700.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]
    numbered = _records([("E TRANSFER AUTODEPOSIT 1234567 ONTARIO INC", 500.0),
                         ("E TRANSFER AUTODEPOSIT 7654321 ONTARIO INC", 600.0)])
    assert [_tier(record)[1] for record in numbered] == ["p2p", "p2p"]
    same = _records([("E TRANSFER AUTODEPOSIT 1234567 ONTARIO INC", 500.0),
                     ("E TRANSFER AUTODEPOSIT 1234567 ONTARIO INC", 600.0)])
    assert [_tier(record)[1] for record in same] == ["p2p_round_repeat", "p2p_round_repeat"]
    holder = _one("E TRANSFER AUTODEPOSIT 1234567 ONTARIO INC", 500.0, holder="1234567 ONTARIO INC")
    assert _tier(holder) == ("excluded_pending_review", "holder_name")


def test_a_sender_read_after_the_rail_never_hides_a_financing_root_on_the_row():
    # Q4's two holds read the sender; every other hold keeps reading the whole row of a row with no payer region.
    record = _one("PAYMENT RECEIVED 03 02 NORTHWIND 12AB FUNDING NORTHWIND 123", 900.0)
    assert _tier(record) == ("excluded_pending_review", "financing_named_payer")


def test_a_sender_printed_with_and_without_from_is_one_sender():
    rows = _records([("ZELLE PAYMENT FROM JOHN SMITH CONF 1", 500.0), ("ZELLE TRANSFER JOHN SMITH", 600.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat"]
    # A Venmo or Cash App cash-out prints no sender.
    cashouts = _records([("VENMO CASHOUT", 500.0), ("VENMO CASHOUT", 600.0)])
    assert [_tier(record)[1] for record in cashouts] == ["p2p", "p2p"]


@pytest.mark.parametrize("orig", ["STATE OF OHIO", "SAMPLE COUNTY", "AETNA"])
def test_q5_verifies_a_public_or_healthcare_payer_that_wires_twice(orig):
    # §8.5 (review M2): the public-payer test reads the wire's originator.
    rows = _records([(WIRE.format(n=1, orig=orig), 9000.0), (WIRE.format(n=2, orig=orig), 9100.0)])
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}


def test_a_public_payer_s_non_sale_wire_is_held():
    # §7.6, §8.1 (review M2): the public payer's non-sale hold reads a wire's originator too.
    rows = _records([(WIRE.format(n=1, orig="STATE OF OHIO") + " OBI STIPEND", 9000.0),
                     (WIRE.format(n=2, orig="STATE OF OHIO") + " OBI STIPEND", 9100.0)])
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


def test_the_guard_facts_read_the_known_payee_without_the_receiver_value():
    # Review M3: the holder's name in the receiver field never names a payout entity or a lender.
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.transaction_classifier import revenue_text

    text = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1 INDN:SEZZLE SALON LLC CO ID:1 CCD"
    record = _one(text, 700.0, holder="SEZZLE SALON LLC")
    facts = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
    assert not facts["payout_or_factoring"] and not facts["known_financing"]
    # A registry-claimed row says so, for the census's holder guards (§8.1: the holds skip claimed rows).
    square = _one("SQUARE INC DES:TRANSFER ID:1", 700.0, holder="SQUARE ONE BAKERY LLC")
    assert true_revenue.guard_facts(square, "SQUARE INC DES TRANSFER ID 1")["claimed"]


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 re-review, fix round 2 (2026-09-29): the P2P sender reader (references and layout words), Q6 and the gated
# processors' words, the accounts-payable template after a leading date, short and company-formed transfer
# counterparties, the registry's tables, the deferred sources' reason, and a credit wire's beneficiary.
# ---------------------------------------------------------------------------------------------------------------------
P2P = ("counted_flagged", "p2p")


@pytest.mark.parametrize("layout", [
    "E TRANSFER {ref} {name}", "INTERAC E TRANSFER RECEIVED {ref} {name}", "VIREMENT INTERAC {ref} {name}",
    "E TRANSFER AUTODEPOSIT {ref} {name}",
])
def test_a_per_row_reference_before_the_sender_never_splits_one_sender(layout):
    # Q4, §5.2 (re-review fix 1a): a reference printed before the sender is no part of the sender's key.
    rows = _records([(layout.format(ref="123456789012", name="JOHN SMITH"), 500.0),
                     (layout.format(ref="210987654321", name="JOHN SMITH"), 600.0),
                     (layout.format(ref="112233445566", name="MARY JONES"), 700.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


def test_a_numbered_company_after_a_reference_keeps_its_number():
    # The number stays when a numbered-company form follows it: one company groups, two never do.
    same = _records([("E TRANSFER 123456789012 1234567 ONTARIO INC", 500.0),
                     ("E TRANSFER 210987654321 1234567 ONTARIO INC", 600.0)])
    assert [_tier(record)[1] for record in same] == ["p2p_round_repeat", "p2p_round_repeat"]
    two = _records([("E TRANSFER 123456789012 1234567 ONTARIO INC", 500.0),
                    ("E TRANSFER 210987654321 7654321 ONTARIO INC", 600.0)])
    assert [_tier(record) for record in two] == [P2P, P2P]
    llc = _records([("ZELLE CR NORTHWIND SUPPLY LLC", 500.0), ("ZELLE CR NORTHWIND SUPPLY LLC", 600.0)])
    assert [_tier(record)[1] for record in llc] == ["p2p_round_repeat", "p2p_round_repeat"]


@pytest.mark.parametrize(("first", "second"), [
    ("APPLE CASH TRANSFER CUPERTINO CA", "APPLE CASH SENT MONEY CUPERTINO CA"),
    ("CARD CREDIT APPLE CASH INST 1234 CUPERTINO CA12345 1234", "CARD CREDIT APPLE CASH INST 5678 CUPERTINO CA12345 5678"),
    ("APPLE CASH INS 03/02 123456789 PMNT RCVD APPLE CASH INST X 8005551234 CA",
     "APPLE CASH INS 03/03 987654321 PMNT RCVD APPLE CASH INST X 8005551234 CA"),
    ("CASH APP*CASH OUT*OAKLAND CA", "CASH APP*CASH OUT*OAKLAND CA 2"),
    ("VENMO CASHOUT 123456 1234567890123 JOHN SMITH", "VENMO CASHOUT 654321 3210987654321 JOHN SMITH"),
    ("RTP CREDIT VENMO NEW YORK CITY 03 12345", "RTP CREDIT VENMO NEW YORK CITY 03 54321"),
    ("ZELLE CREDIT BANK OF AMERICA", "ZELLE CREDIT BANK OF AMERICA 2"),
    ("INTERAC E TRANSFER REQUEST FULFILLED", "INTERAC E TRANSFER REQUEST FULFILLED"),
    ("VIREMENT INTERAC DEPOT AUTOMATIQUE", "VIREMENT INTERAC DEPOT AUTOMATIQUE"),
    ("VIREMENT INTERAC ENTRANT", "VIREMENT INTERAC ENTRANT"),
    ("ZELLE BUSINESS PAYMENT", "ZELLE BUSINESS PAYMENT"),
    ("ZELLE RECURRING PAYMENT", "ZELLE RECURRING PAYMENT"),
    ("ZELLE PAY ID 12345", "ZELLE PAY ID 67890"),
    ("RTP CREDIT REMITTANCE INFO", "RTP CREDIT REMITTANCE INFO"),
    ("RTP CREDIT 1ABC INC SAN FRANCISCO CA", "RTP CREDIT 2XYZ INC SAN FRANCISCO CA"),
])
def test_layout_words_a_cash_out_and_a_bare_legal_form_are_never_a_sender(first, second):
    # Q4, §5.2 (re-review fix 1b): a wallet's city and state, a sending bank, the French and English layout words and
    # a legal form alone name no sender, and a cash-out prints none, so unrelated round sums are never one sender's.
    rows = _records([(first, 500.0), (second, 600.0)])
    assert [_tier(record) for record in rows] == [P2P, P2P]


@pytest.mark.parametrize(("holder", "text"), [
    ("OAKLAND CAFE LLC", "CASH APP*CASH OUT*OAKLAND CA"),
    ("OAKLAND CAFE LLC", "CASH APP*JOHN SMITH*OAKLAND CA"),
    ("CUPERTINO BAKERY LLC", "APPLE CASH TRANSFER CUPERTINO CA"),
    ("AMERICA FIRST PLUMBING LLC", "ZELLE CREDIT BANK OF AMERICA"),
])
def test_a_holder_named_after_a_wallet_city_or_a_bank_is_never_the_sender(holder, text):
    assert _tier(_one(text, 250.0, holder=holder)) == P2P


def test_a_wallet_s_city_state_and_bank_tails_end_the_sender_and_the_sender_still_groups():
    cash_app = _records([("CASH APP*JOHN SMITH*OAKLAND CA", 500.0), ("CASH APP*JOHN SMITH*OAKLAND CA", 600.0),
                         ("CASH APP*MARY JONES*OAKLAND CA", 700.0)])
    assert [_tier(record)[1] for record in cash_app] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]
    venmo = _records([("PAYMENT RECEIVED 03/02 VENMO JOHN SMITH NEW YORK CITY NY CARD 1234", 500.0),
                      ("PAYMENT RECEIVED 03/03 VENMO JOHN SMITH VISA DIRECT NY CARD 1234", 600.0)])
    assert [_tier(record)[1] for record in venmo] == ["p2p_round_repeat", "p2p_round_repeat"]
    zelle = _records([("ZELLE CREDIT JOHN SMITH WELLS FARGO", 500.0), ("ZELLE CREDIT JOHN SMITH", 600.0)])
    assert [_tier(record)[1] for record in zelle] == ["p2p_round_repeat", "p2p_round_repeat"]
    # The holder test still reads the sender before the city.
    assert _tier(_one("CASH APP*CONTOSO BAKERY*OAKLAND CA", 250.0)) == ("excluded_pending_review", "holder_name")


def test_a_gated_processor_s_word_inside_a_payer_s_name_never_skips_q6():
    # §7.1 (re-review fix 2): a waiting processor's bare word (BRAINTREE, SMARTTAB) is no operating-registry alias,
    # so Q6 reads the payer as it reads any other; the registry and NET SETTLE rows stay with their own rules.
    assert _one("BRAINTREE PLUMBING LLC DES:PAYMENT ID:1", 700.0).revenue_match_method == "named_payer_company_form"
    rows = _records([("SMARTTAB SUPPLY DES:PAYMENT ID:1 CCD", 700.0), ("SMARTTAB SUPPLY DES:PAYMENT ID:2 CCD", 710.0)])
    assert {record.revenue_match_method for record in rows} == {"named_payer_repeats"}


def test_a_leading_date_never_hides_the_accounts_payable_pmt_numbered_template():
    # §5.2, T11 (re-review fix 3): 'ACC(OUN)TS PAYABLE PMT <digits>' after a leading date reads as its undated twin.
    from analysis import transaction_classifier as classifier
    from analysis.description_text import normalize_transaction_description

    for text in ("03/02 ACCOUNTS PAYABLE PMT 1234567 NORTHWIND LTD", "ACCOUNTS PAYABLE PMT 1234567 NORTHWIND LTD",
                 "0302 ACCTS PAYABLE PMT 1234567 NORTHWIND LTD"):
        assert classifier.numbered_company(classifier.revenue_text(normalize_transaction_description(text)))
        record = _one(text, 700.0)
        assert record.revenue_classification == "unverified_deposit"
        assert _tier(record) == ("counted_flagged", "numbered_company_payer")


@pytest.mark.parametrize("text", [
    "ONLINE TRANSFER FROM LI WU", "ONLINE TRANSFER FROM LE VU", "TRANSFER FROM JD LLC",
    "TRANSFER FROM AMERICAN NATIONAL INC", "TRANSFER FROM USA HOLDINGS LLC",
])
def test_a_short_or_company_formed_counterparty_is_a_named_transfer(text):
    # §8.2, T13 (re-review fix 4): two name words of any length, or a company form, after FROM name a counterparty.
    assert _tier(_one(text, 250.0)) == P2P


@pytest.mark.parametrize("text", [
    "TRANSFER FROM OPERATING LLC", "TRANSFER FROM NATIONAL TRUST", "TRANSFER FROM TYPE A LLC",
    "TRANSFER FROM NAME COMPANY LLC", "ONLINE TRANSFER FROM ID 12345", "TRANSFER FROM OPERATIONS TRANSFER IN",
    "ONLINE TRANSFER FROM TAX RESERVE", "TRANSFER FROM AB CO",
])
def test_an_account_description_or_a_field_label_after_from_is_still_no_counterparty(text):
    assert _tier(_one(text, 250.0)) == ("excluded_pending_review", "transfer_no_counterparty")


def test_the_owner_money_and_deferred_payer_tables_live_in_the_registry():
    # §7.0 "Where vocabulary lives" (re-review fix 5): the tables that name companies are the registry's.
    from analysis import classification_registry as registry
    from analysis import true_revenue

    assert true_revenue._OWNER_MONEY_PLATFORMS.pattern == registry.OWNER_MONEY_PLATFORMS
    assert true_revenue._SECTION_15_DEFERRED_PAYERS.pattern == registry.SECTION_15_DEFERRED_PAYERS
    assert "BANK OF AMERICA" in registry.P2P_SENDING_BANK_NAMES


def test_a_credit_wire_s_beneficiary_never_names_a_source():
    # §5.2 (re-review fix 7): on an incoming wire the beneficiary is the holder, so a holder named after a platform
    # never makes its customer's wires that platform's settlements.
    rows = _records([(WIRE.format(n=1, orig="NORTHWIND EXPORTS LLC") + " BNF:SQUARE ONE BAKERY", 9000.0),
                     (WIRE.format(n=2, orig="NORTHWIND EXPORTS LLC") + " BNF:SQUARE ONE BAKERY", 9100.0)],
                    holder="SQUARE ONE BAKERY LLC")
    assert {record.revenue_canonical_entity for record in rows} == {None}
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}


def test_the_beneficiary_is_removed_only_from_an_incoming_wire():
    # Chase's real-time layout prints 'From: Bnf-<originator>': there the field names the payer, not the holder.
    from analysis import transaction_classifier as classifier

    wire = "WIRE TYPE WIRE IN DATE 540102 TRN 1 ORIG NORTHWIND EXPORTS LLC ID 99 BNF SQUARE ONE BAKERY OBI INV 12"
    assert "SQUARE" not in classifier._without_receiver_value(wire)
    assert "NORTHWIND" in classifier._without_receiver_value(wire)
    assert "OBI INV 12" in classifier._without_receiver_value(wire)
    rtp = "REAL TIME TRANSFER RECD FROM ABA CONTR BNK 021000021 FROM BNF INTUIT PAYMENTS INC REF 1234 INFO SAMPLE"
    assert classifier._without_receiver_value(rtp) == rtp
    remittance = "WIRE IN FROM NORTHWIND EXPORTS LLC ORIG TO BNF INFO SQUARE PAYOUT"
    assert "SQUARE PAYOUT" in classifier._without_receiver_value(remittance)
    record = _one("REAL TIME TRANSFER RECD FROM ABA/CONTR BNK-021000021 FROM: BNF-INTUIT PAYMENTS INC REF: 1234 "
                  "INFO: SAMPLE", 700.0)
    assert record.revenue_canonical_entity == "QuickBooks Payments"


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 follow-up 2 (2026-09-29, under the owner's delegation): pass 7 reads VIREMENT as §8.4's person-to-person rail
# only in its Interac forms. 'VIREMENT EN LIGNE', 'VIREMENT ENTRE COMPTES', 'VIREMENT DE COMPTE', 'VIREMENT DE FONDS'
# and a bare VIREMENT are a French transfer (typically between the holder's own accounts): they take the transfer
# rules. The 5.5 channel gate is unchanged.
# ---------------------------------------------------------------------------------------------------------------------
HELD_TRANSFER = ("excluded_pending_review", "transfer_no_counterparty")
FRENCH_TRANSFERS = [
    "VIREMENT EN LIGNE TF 1234567", "VIREMENT EN LIGNE TF 1234567890123456789", "VIREMENT ENTRE COMPTES 1234567",
    "VIREMENT ENTRE COMPTES", "VIREMENT DE COMPTE 1234567", "VIREMENT DE COMPTE A COMPTE 1234567",
    "VIREMENT DE FONDS 1234567", "VIREMENT 1234567", "VIREMENT", "VIREMENT RECU 1234567",
    "03 02 VIREMENT EN LIGNE TF 1234", "VIREMENT INTERNET 123456789012", "VIREMENT PAR BANQUE EN DIRECT 1234",
]
INTERAC_VIREMENTS = [
    "VIREMENT INTERAC FABRIKAM LTEE", "VIREMENT INTERAC 123456789012 JOHN SMITH", "VIREMENT INTERAC RECU 1234",
    "VIREMENT AUTODEPOSIT JOHN SMITH", "VIREMENT E TRANSFER JOHN SMITH", "VIREMENT ETRANSFER JOHN SMITH",
    "VIREMENT E TFR JOHN SMITH",
]


@pytest.mark.parametrize("text", FRENCH_TRANSFERS)
def test_a_virement_without_an_interac_form_is_a_transfer_with_no_counterparty(text):
    # §8.2: the transfer words, the reference TF and the account words name no counterparty, so the row is held.
    assert _tier(_one(text, 2500.0)) == HELD_TRANSFER
    # The hold comes before the round-sum repeat, and two references never make one sender.
    rows = _records([(text, 500.0), (text.replace("1234", "4321"), 600.0)])
    assert [_tier(record) for record in rows] == [HELD_TRANSFER] * 2


@pytest.mark.parametrize("text", ["VIREMENT EN LIGNE FABRIKAM LTEE", "VIREMENT DE FABRIKAM LTEE",
                                  "VIREMENT ENTRE COMPTES NORTHWIND SUPPLY INC"])
def test_a_virement_that_names_its_counterparty_is_a_named_transfer(text):
    # §8.2, §8.4: counted as a named transfer, and round sums from the one counterparty are held as on the rails.
    assert _tier(_one(text, 250.0)) == P2P
    rows = _records([(text, 500.0), (text, 600.0), (text, 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


def test_a_virement_in_the_holder_s_name_is_still_held_as_the_holder_s():
    assert _tier(_one("VIREMENT EN LIGNE CONTOSO BAKERY LLC", 250.0)) == ("excluded_pending_review", "holder_name")


@pytest.mark.parametrize("text", INTERAC_VIREMENTS)
def test_an_interac_virement_keeps_its_person_to_person_reading(text):
    # §8.4: Interac prints VIREMENT INTERAC; with the e-transfer or autodeposit words a VIREMENT is the rail too.
    assert _tier(_one(text, 250.0)) == P2P


@pytest.mark.parametrize("name", ["FABRIKAM LTEE", "123456789012 JOHN SMITH"])
def test_an_interac_virement_s_round_repeat_is_unchanged(name):
    rows = _records([(f"VIREMENT INTERAC {name}", 500.0), (f"VIREMENT INTERAC {name}", 600.0),
                     (f"VIREMENT INTERAC {name}", 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize("text", FRENCH_TRANSFERS + INTERAC_VIREMENTS)
def test_the_5_5_channel_gate_of_a_virement_is_unchanged(text):
    # The 5.5 census was accepted on _CONSUMER_P2P_RAIL: every VIREMENT row is still a closed person-to-person row
    # there, never verified; only pass 7's tiering reads the Interac forms.
    from analysis import transaction_classifier as classifier
    from analysis.description_text import normalize_transaction_description

    normalized = classifier.revenue_text(normalize_transaction_description(text))
    assert classifier.channel_gate(normalized) == "closed"
    assert classifier._CONSUMER_P2P_RAIL.search(normalized) is not None
    assert _one(text, 250.0).revenue_classification == "unverified_deposit"


def test_the_census_reads_a_virement_s_transfer_fact_as_pass_7_does():
    # §14.3 G4 reads the pass's own transfer fact.
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.transaction_classifier import revenue_text

    for text, held in [("VIREMENT EN LIGNE TF 1234567", True), ("VIREMENT ENTRE COMPTES 1234567", True),
                       ("VIREMENT EN LIGNE FABRIKAM LTEE", False), ("VIREMENT INTERAC FABRIKAM LTEE", False),
                       ("VIREMENT INTERAC RECU 1234", False)]:
        record = _one(text, 250.0)
        facts = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
        assert facts["transfer_no_counterparty"] is held


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 final review, fix round 3 (2026-09-29, under the owner's delegation): an Interac company sender after a
# reference groups, a company printed without FROM is a transfer's counterparty, a wallet's city and a state code are
# tails only and a cash-out voids only a wallet's sender, French cancelled transfers are reversals, French months and
# bank branches are never a counterparty, and a credit wire's beneficiary value ends at the originator's label.
# ---------------------------------------------------------------------------------------------------------------------
HOLDER_HELD = ("excluded_pending_review", "holder_name")


@pytest.mark.parametrize("layout", [
    "E TRANSFER {ref} FABRIKAM SUPPLY LTD", "INTERAC E TRANSFER RECEIVED {ref} NORTHWIND TRADING INC",
    "E TRANSFER AUTODEPOSIT {ref} FABRIKAM SUPPLY CORP", "VIREMENT INTERAC {ref} SAMPLE SUPPLY LTD",
])
def test_an_interac_company_sender_after_a_reference_groups(layout):
    # Q4, §5.2 (fix 1): only a numbered company proper (six or more digits and a province) keeps its number; any other
    # reference before a company sender is dropped, so one company's round sums are one sender's.
    rows = _records([(layout.format(ref="123456789012"), 500.0), (layout.format(ref="210987654321"), 600.0),
                     (layout.format(ref="112233445566"), 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


def test_a_numbered_company_sender_keeps_its_number():
    same = _records([("E TRANSFER 123456789012 1234567 ALBERTA LTD", 500.0),
                     ("E TRANSFER 210987654321 1234567 ALBERTA LTD", 600.0)])
    assert [_tier(record)[1] for record in same] == ["p2p_round_repeat", "p2p_round_repeat"]
    two = _records([("E TRANSFER 1234567 QUEBEC INC", 500.0), ("E TRANSFER 7654321 QUEBEC INC", 600.0)])
    assert [_tier(record) for record in two] == [P2P, P2P]
    holder = _one("E TRANSFER 123456789012 1234567 ALBERTA LTD", 500.0, holder="1234567 ALBERTA LTD")
    assert _tier(holder) == HOLDER_HELD


@pytest.mark.parametrize("text", [
    "VIREMENT RECU 1234567 QUEBEC INC", "VIREMENT RECU 1234-5678 QUEBEC INC", "VIREMENT DE 9123-4567 QUEBEC INC",
    "02 JUIN VIREMENT RECU 1234-5678 QUEBEC INC AB12CD", "ONLINE TRANSFER 1234567 ONTARIO INC",
    "ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC", "ONLINE TRANSFER REF 1234 NORTHWIND LTD",
])
def test_a_company_printed_without_from_is_a_transfer_s_counterparty(text):
    # §8.2, T13 (fix 2): the company-form arm reads the words after the transfer wording when no FROM prints; a
    # numbered company is a counterparty too: counted and flagged, never verified (OQ3).
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.transaction_classifier import revenue_text

    record = _one(text, 2500.0)
    assert _tier(record) == P2P
    assert record.revenue_classification == "unverified_deposit"
    facts = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
    assert facts["transfer_no_counterparty"] is False


@pytest.mark.parametrize("text", [
    "ONLINE TRANSFER 1234567", "ONLINE TRANSFER OPERATING LLC", "VIREMENT RECU 1234567", "ONLINE TRANSFER AB CO",
    "ONLINE BANKING TRANSFER CREDIT REF 88",
])
def test_a_transfer_printing_no_company_without_from_stays_held(text):
    assert _tier(_one(text, 2500.0)) == HELD_TRANSFER


@pytest.mark.parametrize(("text", "holder"), [
    ("ZELLE CREDIT NEW YORK FABRIKAM LLC", "NEW YORK FABRIKAM LLC"),
    ("INTERAC E TRANSFER RECEIVED SAN JOSE CONTOSO LLC", "SAN JOSE CONTOSO LLC"),
    ("ZELLE CREDIT OAKLAND AUTO NORTHWIND LLC", "OAKLAND AUTO NORTHWIND LLC"),
    ("ZELLE CREDIT CUPERTINO SAMPLE LLC", "CUPERTINO SAMPLE LLC"),
    ("CASH APP*NEW YORK FABRIKAM LLC*OAKLAND CA", "NEW YORK FABRIKAM LLC"),
    ("ZELLE CREDIT CASH OUT AUTO LLC", "CASH OUT AUTO LLC"),
    ("ZELLE CREDIT REQUEST FABRIKAM LLC", "REQUEST FABRIKAM LLC"),
])
def test_a_sender_named_after_a_city_or_a_layout_word_takes_the_holder_test_and_the_round_repeat(text, holder):
    # Q4, §5.2 (fix 3): a city ends the sender only as its tail, a cash-out voids only a wallet's sender, and a layout
    # word inside a name never defeats the holder test.
    assert _tier(_one(text, 5000.0, holder=holder)) == HOLDER_HELD
    rows = _records([(text, 500.0), (text, 600.0), (text, 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize(("first", "second"), [
    ("APPLE CASH INST XFER 12345678901234567890 CUPERTINO CA", "APPLE CASH INST XFER 09876543210987654321 CUPERTINO CA"),
    ("CARD CREDIT APPLE CASH INST 1234 CUPERTINO CAUS", "CARD CREDIT APPLE CASH INST 5678 CUPERTINO CAUS"),
    ("RTP CREDIT VENMO SAN JOSE CA 03 12345", "RTP CREDIT VENMO SAN JOSE CA 03 54321"),
    ("RTP CREDIT 1BOOK INC SOUTH SAN FRANCISCO CA 123456789", "RTP CREDIT 2BOOK INC SOUTH SAN FRANCISCO CA 987654321"),
    ("PAYMENT RECEIVED 03 02 CASH APP JOHN SMITH CASH OUT OAKLAND CA CARD 1234",
     "PAYMENT RECEIVED 03 03 CASH APP JOHN SMITH CASH OUT OAKLAND CA CARD 1234"),
])
def test_a_wallet_s_own_city_or_cash_out_still_prints_no_sender(first, second):
    rows = _records([(first, 500.0), (second, 600.0)])
    assert [_tier(record) for record in rows] == [P2P, P2P]


def test_a_state_code_is_a_tail_only_after_two_words():
    # M7: 'KIM PA' and 'KIM MA' are two senders; 'JOHN SMITH NY' is John Smith.
    two = _records([("ZELLE CREDIT KIM PA", 500.0), ("ZELLE CREDIT KIM MA", 600.0)])
    assert [_tier(record) for record in two] == [P2P, P2P]
    one = _records([("ZELLE CREDIT JOHN SMITH NY", 500.0), ("ZELLE CREDIT JOHN SMITH", 600.0),
                    ("VENMO FABRIKAM LLC VISA DIRECT NY", 700.0), ("ZELLE CREDIT FABRIKAM LLC", 800.0)])
    assert [_tier(record)[1] for record in one] == ["p2p_round_repeat"] * 4


@pytest.mark.parametrize("text", [
    "VIREMENT ANNULE JOHN SMITH", "VIREMENT INTERAC ANNULE", "VIREMENT INTERAC ANNULE JOHN SMITH",
    "VIREMENT ANNULE", "ANNUL VFC 1VT", "VIREMENT ANNULATION 1234", "OPERATION ANNULEE 1234", "1234ANNULE VIREMENT",
])
def test_a_french_cancelled_transfer_is_a_reversal(text):
    # §6 precedence (fix 4): refunds and reversals never become revenue; ANNULE is CANCELLED's French.
    record = _one(text, 250.0)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"
    assert record.revenue_tier == "non_revenue"


def test_a_french_cancelled_transfer_pairs_with_its_equal_row_as_a_reversal():
    # §6.2 pass 4: the reversal pair reads the credit markers on the credit or on the debit it pairs, ANNULE included.
    cancelled_in = _records([("VIREMENT INTERAC JOHN SMITH", -400.0), ("VIREMENT INTERAC ANNULE JOHN SMITH", 400.0)])
    assert cancelled_in[1].revenue_match_method == "matched_reversal_pair"
    cancelled_out = _records([("VIREMENT INTERAC ANNULE JOHN SMITH", -400.0), ("VIREMENT INTERAC JOHN SMITH", 400.0)])
    assert cancelled_out[1].revenue_match_method == "matched_reversal_pair"


def test_a_word_that_only_starts_like_annule_is_no_reversal():
    assert _one("VIREMENT INTERAC ANNULUS JOHN SMITH", 250.0).revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("text", [
    "02 JUIN VIREMENT EN LIGNE TF 1234", "02 JANV VIREMENT PAR BANQUE EN DIRECT 1234",
    "02 FEVR VIREMENT PAR BANQUE EN DIRECT 1234", "02 MAI VIREMENT PAR BANQUE EN DIRECT 1234",
    "02 AOUT VIREMENT PAR BANQUE EN DIRECT 1234", "02 MARS VIREMENT EN LIGNE TF 1234",
    "02 DECEMBRE VIREMENT PAR BANQUE EN DIRECT 1234", "02 JUIL VIREMENT EN LIGNE TF 1234",
    "VIREMENT CTR BANCAIRE 1234", "VIREMENT CENTRE BANCAIRE 1234", "VIREMENT SUCCURSALE 1234",
    "ONLINE TRANSFER BRANCH 1234",
])
def test_a_french_month_or_a_bank_branch_is_never_a_transfer_s_counterparty(text):
    # §8.2 (fix 5): a date's French month and a bank's branch name nobody who pays the business.
    assert _tier(_one(text, 2500.0)) == HELD_TRANSFER


@pytest.mark.parametrize("text", [
    "INCOMING WIRE BNF SQUARE ONE BAKERY FROM STRIPE INC",
    "INCOMING WIRE BNF SQUARE ONE BAKERY WIRE FROM STRIPE INC",
])
def test_a_credit_wire_s_beneficiary_value_ends_at_the_originator_label(text):
    # §5.2 (fix 6): the beneficiary field's value ends at an originator label, so the originator still names a source.
    from analysis import transaction_classifier as classifier

    assert classifier._is_wire_row(text)
    stripped = classifier._without_receiver_value(text)
    assert "STRIPE INC" in stripped and "SQUARE" not in stripped
    for label in ("B O", "ORIGINATOR", "ORG"):
        assert "NORTHWIND" in classifier._without_receiver_value(
            f"INCOMING WIRE BNF SQUARE ONE BAKERY {label} NORTHWIND EXPORTS LLC")
    rows = _records([(text, 9000.0), (text, 9100.0)], holder="SQUARE ONE BAKERY LLC")
    assert {record.revenue_canonical_entity for record in rows} == {"Stripe"}


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 fix round 4 (2026-09-29, under the owner's delegation): a Quebec numbered company (NNNN-NNNN QUEBEC INC) keys
# by both its numbers, and a French month is dropped from a transfer's counterparty only where a date prints it.
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("first", "second"), [
    ("VIREMENT INTERAC 1234-5678 QUEBEC INC", "VIREMENT INTERAC 8765-4321 QUEBEC INC"),
    ("E TRANSFER 123456789012 1234-5678 QUEBEC INC", "E TRANSFER 210987654321 8765-4321 QUEBEC INC"),
    ("INTERAC E TRANSFER RECEIVED 1234-5678 QC INC", "INTERAC E TRANSFER RECEIVED 1234-5679 QC INC"),
])
def test_two_quebec_numbered_companies_are_two_senders(first, second):
    # Q4, §5.2: Quebec registers a numbered company as four digits, a hyphen and four digits ('1234-5678 QUEBEC INC',
    # normalized to '1234 5678 QUEBEC INC'); both digit groups are its identity, so two such companies never group.
    rows = _records([(first, 500.0), (second, 600.0)])
    assert [_tier(record) for record in rows] == [P2P, P2P]


@pytest.mark.parametrize("layout", [
    "VIREMENT INTERAC {ref}1234-5678 QUEBEC INC", "E TRANSFER {ref}1234-5678 QUEBEC INC",
    "INTERAC E TRANSFER RECEIVED {ref}1234-5678 QUE INC",
])
def test_one_quebec_numbered_company_s_round_sums_are_one_sender_s(layout):
    rows = _records([(layout.format(ref=""), 500.0), (layout.format(ref="123456789012 "), 600.0),
                     (layout.format(ref="210987654321 "), 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


def test_a_quebec_numbered_holder_is_held_on_its_own_numbers_only():
    # The holder test reads the key's digit runs: the holder's own numbers hold the row, another company's do not.
    holder = "1234-5678 QUEBEC INC"
    assert _tier(_one("VIREMENT INTERAC 1234-5678 QUEBEC INC", 500.0, holder=holder)) == HOLDER_HELD
    assert _tier(_one("VIREMENT INTERAC 8765-4321 QUEBEC INC", 500.0, holder=holder)) == P2P


def test_two_four_digit_references_before_a_company_that_is_not_quebec_s_are_no_number():
    # Only the Quebec form keeps the pair: any other sender after two short references is one sender.
    rows = _records([("E TRANSFER 1234 5678 FABRIKAM SUPPLY LTD", 500.0),
                     ("E TRANSFER 8765 4321 FABRIKAM SUPPLY LTD", 600.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat"]


@pytest.mark.parametrize("text", [
    "TRANSFER FROM MARS INC", "ONLINE TRANSFER FROM MAI LE", "ONLINE TRANSFER MARS INC",
    "ONLINE TRANSFER FROM MAI VU", "VIREMENT RECU MARS INC",
])
def test_a_french_month_word_outside_a_date_is_a_counterparty_s_name(text):
    # §8.2, T13: MARS or MAI printed as a name, not beside a day number nor at the row's start before the transfer
    # wording, is the counterparty's own word.
    record = _one(text, 2500.0)
    assert _tier(record) == P2P
    assert record.revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("text", [
    "02 JUIN VIREMENT EN LIGNE TF 1234", "JUIN 02 VIREMENT EN LIGNE TF 1234", "02JUIN VIREMENT EN LIGNE TF 1234",
    "JANV VIREMENT PAR BANQUE EN DIRECT 1234", "02 JANV VIREMENT PAR BANQUE EN DIRECT 1234",
    "MARS VIREMENT EN LIGNE TF 1234", "ONLINE TRANSFER FROM 02 MAI", "ONLINE TRANSFER FROM MAI 02",
    "ONLINE TRANSFER 2 MARS REF 1234",
])
def test_a_french_month_printed_as_a_date_is_still_never_a_counterparty(text):
    assert _tier(_one(text, 2500.0)) == HELD_TRANSFER


# ---------------------------------------------------------------------------------------------------------------------
# S4.2 fix round 5 (2026-09-29, under the owner's delegation): T13's two holds on a named transfer printed without FROM
# (the holder test and the round-sum repeat), read on its counterparty words as the FROM form reads its payer region;
# and CANCELLED's French plurals.
# ---------------------------------------------------------------------------------------------------------------------
NAMED_WITHOUT_FROM = [
    "ONLINE TRANSFER 1234567 ONTARIO INC", "ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC", "ONLINE TRANSFER FABRIKAM LLC",
    "INTERNET TRANSFER FABRIKAM HOLDINGS LLC",
]


@pytest.mark.parametrize(("text", "holder"), [
    ("ONLINE TRANSFER 1234567 ONTARIO INC", "1234567 ONTARIO INC"),
    ("ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC", "1234-5678 QUEBEC INC"),
    ("ONLINE TRANSFER FABRIKAM LLC", "FABRIKAM LLC"),
    ("INTERNET TRANSFER FABRIKAM HOLDINGS LLC", "FABRIKAM HOLDINGS LLC"),
    ("ONLINE TRANSFER FABRIKAM LLC MEMO INVOICE 1234", "FABRIKAM LLC"),
])
def test_a_named_transfer_printed_without_from_takes_the_holder_test(text, holder):
    # T13: a counted named transfer stays under the holder's name, with or without FROM; a numbered company's number
    # is read, as the FROM form's payer region reads it.
    assert _tier(_one(text, 2500.0, holder=holder)) == HOLDER_HELD


@pytest.mark.parametrize(("text", "holder"), [
    ("ONLINE TRANSFER 7654321 ONTARIO INC", "1234567 ONTARIO INC"),
    ("ONLINE BANKING TRANSFER 8765-4321 QUEBEC INC", "1234-5678 QUEBEC INC"),
    ("TRANSFER FABRIKAM LLC TO CONTOSO BAKERY", HOLDER),
])
def test_another_company_or_a_recipient_after_to_is_not_the_holder(text, holder):
    # Another numbered company's number is not the holder's, and a name printed after TO is the recipient's.
    assert _tier(_one(text, 2500.0, holder=holder)) == P2P


@pytest.mark.parametrize("text", NAMED_WITHOUT_FROM)
def test_a_named_transfer_printed_without_from_takes_the_round_repeat(text):
    # T13: one company's round sums printed without FROM are one sender's, into a holder of another name.
    rows = _records([(text, 500.0), (text, 600.0), (text, 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize("text", NAMED_WITHOUT_FROM)
def test_a_single_named_transfer_printed_without_from_is_still_counted(text):
    assert _tier(_one(text, 1234.0)) == P2P


def test_one_company_printed_with_and_without_from_or_a_memo_is_one_sender():
    # The key is the FROM form's (_payer_key of the same name); the sender ends at §5.2's sender ends.
    rows = _records([("ONLINE TRANSFER FROM FABRIKAM LLC", 500.0), ("ONLINE TRANSFER FABRIKAM LLC", 600.0),
                     ("ONLINE TRANSFER FABRIKAM LLC FOR JOB 88", 700.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat"] * 3


@pytest.mark.parametrize(("first", "second"), [
    ("ONLINE TRANSFER 1234567 ONTARIO INC", "ONLINE TRANSFER 7654321 ONTARIO INC"),
    ("ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC", "ONLINE BANKING TRANSFER 8765-4321 QUEBEC INC"),
])
def test_two_numbered_companies_printed_without_from_are_two_senders(first, second):
    rows = _records([(first, 500.0), (second, 600.0)])
    assert [_tier(record) for record in rows] == [P2P, P2P]


@pytest.mark.parametrize("text", ["VIREMENT ANNULES JOHN SMITH", "VIREMENT INTERAC ANNULEES"])
def test_a_french_cancelled_transfer_in_the_plural_is_a_reversal(text):
    # §6 precedence: ANNULES and ANNULEES are the plurals of CANCELLED's French words.
    record = _one(text, 250.0)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"
    assert record.revenue_tier == "non_revenue"


# ---------------------------------------------------------------------------------------------------------------------
# S4.3 (Q7, §8.7): an auto lender's dealer funding. Only a listed auto lender printing a dealer-funding word (or a
# credit union's VHCL PURCH, two or more a statement) verifies; every other credit of a listed lender, a floor-plan
# lender's, a funder's and a refund stay financing or held.
# ---------------------------------------------------------------------------------------------------------------------
DEALER = "SAMPLE MOTORS LLC"
UNION = "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:{n}"


@pytest.mark.parametrize("text", [
    "ALLY FINANCIAL DES:DEALER PAY ID:1",
    "WESTLAKE FINANCI DES:TRADE PAYABLE ID:1",
    "WESTLAKE FINANCIAL DES:ACCT FUNDING ID:1",
    "GLOBAL LENDING SERVICES DES:DEALER FUNDING ID:1",
    "CU DIRECT DES:VHCL PURCH ID:1",
])
def test_q7_verifies_each_listed_arm_on_one_row(text):
    record = _one(text, 15000.0, holder=DEALER)
    assert (record.revenue_classification, record.revenue_match_method, record.revenue_source_type) == (
        "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")
    assert _tier(record) == ("verified", None)
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", [
    "WESTLAKE FINANCI DES:PAYMENT ID:1",
    "ALLY FINANCIAL DES:PAYMENT ID:1",
    "WESTLAKE FLOORIN DES:PAYABLES ID:1",
    "NEXTGEAR CAPITAL DES:DEALER PAY ID:1",
])
def test_q7_leaves_a_listed_lender_s_other_credits_and_a_floor_plan_lender_s_to_financing(text):
    record = _one(text, 15000.0, holder=DEALER)
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", [
    "WESTLAKE FINANCI DES:PAYABLES LOAN ID:1",
    "WESTLAKE FINANCI DES:PAYABLES ID:1 INDN:SAMPLE MOTORS LLC CO ID:1 CCD PMT INFO:LOAN 1234567",
    "WESTLAKE FINANCI DES:DEALER ADV ID:1",
    "WESTLAKE FINANCI DES:DEALER PAY REFUNDS ID:1",
    "WESTLAKE FINANCI DES:DEALER PAY CHARGEBACKS ID:1",
    "WESTLAKE FINANCI DES:PAYABLES INTEREST PAID ID:1",
    "WESTLAKE FINANCI DES:ACCT FUND TRANSFER ID:1",
    "RTP CREDIT WESTLAKE FINANCIAL DEALER PAY",
    "ZELLE PAYMENT FROM WESTLAKE FINANCIAL DEALER PAY",
    "ACH CREDIT DEALER PAY RECEIVER NAME ALLY FINANCIAL",
    "ONE RIVER DES:DEAL FUNDING ID:1",
    "ONE RIVER FUNDING DES:PAYABLES DEALER PAY ID:1",
    "ONE RIVER GROUP DES:DEAL FUNDING ID:1",
    "GLS AUTO DES:DEALER PAY ID:1",
])
def test_q7_never_verifies_a_veto_word_a_gated_or_transfer_row_or_a_lender_it_does_not_list(text):
    # §8.7: a loan, proceeds, advance or refund word anywhere on the row but the holder's name; §6 precedence: the
    # strong non-revenue rule and a transfer; §6.1 step 9b: a closed row, and a push rail (the registry's alone); the
    # receiver field's value never names the lender; One River funds merchants (the ledger's spellings, and one it does
    # not list); GLS AUTO also names body shops.
    record = _one(text, 15000.0, holder=DEALER)
    assert record.revenue_match_method != "auto_lender_dealer_funding"
    assert record.revenue_classification != "verified_revenue"


def test_q7_s_other_readings_hold_or_keep_a_row_as_5_5_did():
    # A dealer-funding word from an unlisted payer is held; the listed lender's other credits stay financing.
    assert _tier(_one("GLS AUTO DES:DEALER PAY ID:1", holder=DEALER)) == ("excluded_pending_review",
                                                                          "financing_named_payer")
    assert _tier(_one("ONE RIVER DES:DEAL FUNDING ID:1", holder=DEALER)) == ("excluded_pending_review",
                                                                             "financing_named_payer")


def test_the_holder_s_own_name_never_vetoes_q7():
    # §5.2: the receiver field's value is the holder: a dealer named with a veto word is still paid by the lender.
    record = _one("WESTLAKE FINANCI DES:PAYABLES ID:1 INDN:ADVANCE AUTO SALES LLC CO ID:1 CCD", 15000.0,
                  holder="ADVANCE AUTO SALES LLC")
    assert record.revenue_match_method == "auto_lender_dealer_funding"


def test_q7_never_verifies_a_direction_conflict_or_a_credit_under_one_dollar():
    conflict = classify_statement_transactions(Statement(account_name=DEALER, transactions=[
        Transaction(date="2054-03-02", description="WESTLAKE FINANCI DES:PAYABLES ID:1", amount=15000.0,
                    direction="debit")]))[0]
    assert _tier(conflict) == ("excluded_pending_review", "direction_conflict")
    # The record keeps its 5.5 reading: a listed lender's credit, excluded from lender credits' eligible deposits.
    assert (conflict.classification, conflict.match_method) == ("other", "financing_proceeds_credit")
    assert conflict.contributes_to_lender_credit_exclusion
    micro = _one("WESTLAKE FINANCI DES:PAYABLES ID:1", 0.37, holder=DEALER)
    assert (micro.revenue_classification, micro.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert micro.contributes_to_lender_credit_exclusion
    reversal = _one("WESTLAKE FINANCI DES:PAYABLES REVERSAL ID:1", 15000.0, holder=DEALER)
    assert reversal.revenue_match_method == "reversal_cancellation_exclusion"


def test_the_credit_union_arm_never_counts_a_conflict_a_micro_entry_or_a_vetoed_row():
    rows = classify_statement_transactions(Statement(account_name=DEALER, transactions=[
        Transaction(date="2054-03-02", description=UNION.format(n=1), amount=18000.0, direction="credit"),
        Transaction(date="2054-03-03", description=UNION.format(n=2), amount=21000.0, direction="debit"),
        Transaction(date="2054-03-04", description=UNION.format(n=3), amount=0.37, direction="credit"),
        Transaction(date="2054-03-05", description=UNION.format(n=4).replace("Purchsec", "Purch Loansec"),
                    amount=19000.0, direction="credit"),
    ]))
    assert "auto_lender_dealer_funding" not in {record.revenue_match_method for record in rows}
    assert _tier(rows[0]) == ("excluded_pending_review", "financing_named_payer")
    assert rows[0].revenue_match_method == "credit_union_vehicle_purchase"
    assert _tier(rows[1]) == ("excluded_pending_review", "direction_conflict")


def test_two_credit_union_rows_verify_beside_other_credits_and_count_once_each():
    rows = _records([(UNION.format(n=1), 18000.0), ("NORTHWIND SUPPLY DES:CREDIT ID:2", 700.0),
                     (UNION.format(n=2), 21000.0)], holder=DEALER)
    assert [record.revenue_match_method for record in rows] == [
        "auto_lender_dealer_funding", "unidentified_posted_credit", "auto_lender_dealer_funding"]
    assert {rows[0].revenue_source_type, rows[2].revenue_source_type} == {"auto_dealer_funding"}
    assert [_tier(record) for record in rows] == [("verified", None), ("counted_flagged", "named_payer_one_off"),
                                                  ("verified", None)]


def test_gls_auto_is_no_dealer_funding_payer_and_its_legal_name_still_is():
    from analysis.classification_registry import DEALER_FUNDING_PAYERS

    assert DEALER_FUNDING_PAYERS["GLS Auto"] == ("GLOBAL LENDING SERVICES",)


def test_the_q7_guard_facts():
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.transaction_classifier import revenue_text

    def facts(text):
        record = _one(text, 15000.0, holder=DEALER)
        found = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
        return {key: found[key] for key in ("q7_payer_ok", "q7_listed", "q7_credit_union", "q7_veto_word")}

    assert facts("WESTLAKE FINANCI DES:PAYABLES ID:1 INDN:ADVANCE AUTO SALES LLC CO ID:1 CCD") == {
        "q7_payer_ok": True, "q7_listed": True, "q7_credit_union": False, "q7_veto_word": False}
    assert facts(UNION.format(n=1)) == {
        "q7_payer_ok": True, "q7_listed": False, "q7_credit_union": True, "q7_veto_word": False}
    # S4.3 fix round 1: Suncoast is no listed lender; it is a credit union like any other.
    assert facts("SUNCOAST CREDIT UNION DES:VHCL PURCH LOAN PROCEEDS ID:1") == {
        "q7_payer_ok": True, "q7_listed": False, "q7_credit_union": True, "q7_veto_word": True}
    assert facts("ACH CREDIT DEALER PAY RECEIVER NAME ALLY FINANCIAL") == {
        "q7_payer_ok": False, "q7_listed": False, "q7_credit_union": False, "q7_veto_word": False}
    assert true_revenue.CREDIT_UNION_DEALER_MIN_CREDITS == 2


# ---------------------------------------------------------------------------------------------------------------------
# S4.3 review, fix round 1 (2026-09-29): a Q7 row names its lender on the record and the revenue fields; Q7 honours
# the section 8.1 holds and G11; Suncoast verifies only through the credit-union arm; a Q7 row is never a Q6 repeat;
# One River's ledger spellings stay financing.
# ---------------------------------------------------------------------------------------------------------------------
WESTLAKE = ("Westlake Services, LLC (Westlake Financial)", "WESTLAKE FINANCI")


@pytest.mark.parametrize(("text", "lender"), [
    ("WESTLAKE FINANCI DES:PAYABLES ID:EFT1234567 INDN:SAMPLE MOTORS LLC CO ID:1 CCD", WESTLAKE),
    ("CU DIRECT DES:VHCL PURCH ID:1", ("CU Direct", "CU DIRECT")),
    ("UNITED AUTO CREDIT DES:DEALER FUNDING ID:1", ("United Auto Credit Corporation", "UNITED AUTO CREDIT")),
])
def test_a_q7_row_names_its_listed_lender_on_the_record_and_the_revenue_fields(text, lender):
    record = _one(text, 15000.0, holder=DEALER)
    assert record.revenue_match_method == "auto_lender_dealer_funding"
    assert (record.canonical_entity, record.matched_alias) == lender
    assert (record.revenue_canonical_entity, record.revenue_matched_alias) == lender
    assert (record.classification, record.match_method) == ("other", "auto_lender_dealer_funding")
    # A truthful reason: the lender and the dealer-funding reading, never "no rule matched".
    for reason in (record.reason, record.revenue_reason):
        assert lender[0] in reason and "dealer" in reason.lower()
        assert "No verified lender" not in reason
    assert not record.contributes_to_lender_credit_exclusion


def test_cu_direct_s_vadmin_fee_is_a_q7_record_not_a_bank_fee():
    record = _one("CU DIRECT DES:VADMIN FEE ID:1", 250.0, holder=DEALER)
    assert record.revenue_match_method == "auto_lender_dealer_funding"
    assert (record.classification, record.match_method, record.canonical_entity) == (
        "other", "auto_lender_dealer_funding", "CU Direct")
    assert "VADMIN FEE" in record.reason


def test_the_credit_union_arm_names_its_credit_union():
    rows = _records([(UNION.format(n=1), 18000.0), (UNION.format(n=2), 21000.0)], holder=DEALER)
    for record in rows:
        assert record.revenue_match_method == "auto_lender_dealer_funding"
        assert (record.canonical_entity, record.revenue_canonical_entity) == ("SAMPLE CU", "SAMPLE CU")
        assert record.revenue_matched_alias == record.matched_alias == "SAMPLE CU"
        assert record.match_method == "credit_union_vehicle_purchase"
        assert "SAMPLE CU" in record.reason and "VHCL PURCH" in record.reason
        assert "SAMPLE CU" in record.revenue_reason and "2 " in record.revenue_reason
    lone = _one(UNION.format(n=1), 18000.0, holder=DEALER)
    assert _tier(lone) == ("excluded_pending_review", "financing_named_payer")
    assert (lone.canonical_entity, lone.revenue_canonical_entity) == ("SAMPLE CU", "SAMPLE CU")
    assert "No verified lender" not in lone.reason


def test_a_q7_lender_never_joins_an_operating_pool():
    from analysis.classification_registry import DEALER_FUNDING_PAYERS, OPERATING_REVENUE_SOURCE_TYPES
    from analysis.transaction_classifier import _in_operating_pool

    rows = _records([(f"WESTLAKE FINANCI DES:PAYABLES ID:{n}", 15000.0 + n) for n in range(1, 5)]
                    + [(UNION.format(n=n), 18000.0 + n) for n in range(1, 4)], holder=DEALER)
    assert {record.revenue_match_method for record in rows} == {"auto_lender_dealer_funding"}
    assert not any(_in_operating_pool(record) for record in rows)
    assert not set(DEALER_FUNDING_PAYERS) & set(OPERATING_REVENUE_SOURCE_TYPES)
    assert WESTLAKE[0] not in OPERATING_REVENUE_SOURCE_TYPES


@pytest.mark.parametrize("text", [
    # Q8 pay words (G11), before the receiver and in a BofA PMT INFO addenda after it.
    "WESTLAKE FINANCI DES:DEALER PAY BONUS ID:1",
    "ALLY FINANCIAL DES:DEALER PAY SALARY ID:1",
    "WESTLAKE FINANCI DES:PAYABLES DIR DEP ID:1",
    "WESTLAKE FINANCI DES:PAYABLES ID:1 INDN:SAMPLE MOTORS LLC CO ID:1 CCD PMT INFO:PAYROLL 12",
    # Personal income (G11).
    "WESTLAKE FINANCI DES:PAYABLES PENSION ID:1",
    # Owner money and financing that carries no root (non_sale_purpose).
    "WESTLAKE FINANCI DES:PAYABLES INVESTMENT ID:1",
    "WESTLAKE FINANCI DES:PAYABLES DIVIDEND ID:1",
    "WESTLAKE FINANCI DES:PAYABLES PAYOFF ID:1",
    # A lender refunding an overpaid payoff (possible_return).
    "WESTLAKE FINANCI DES:PAYABLES OVERPAYMENT ID:1",
    "WESTLAKE FINANCI DES:PAYABLES ADJUSTMENT ID:1",
    "WESTLAKE FINANCI DES:PAYABLES CREDIT MEMO ID:1",
    "WESTLAKE FINANCI DES:PAYABLES DISPUTE ID:1",
    # Insurer and claim words.
    "WESTLAKE FINANCI DES:PAYABLES INSURANCE ID:1",
    "WESTLAKE FINANCI DES:PAYABLES CLAIM ID:1",
    # Floor-plan financing.
    "ALLY FINANCIAL DES:FLOOR PLAN PAYABLES ID:1",
    "ALLY FINANCIAL DES:FLOORPLAN DEALER PAY ID:1",
    "ALLY FINANCIAL DES:WHOLESALE PAYABLES ID:1",
])
def test_q7_honours_the_section_8_1_holds_and_a_listed_lender_s_row_stays_financing(text):
    record = _one(text, 15000.0, holder=DEALER)
    assert record.revenue_match_method != "auto_lender_dealer_funding"
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion
    assert record.match_method != "auto_lender_dealer_funding"


@pytest.mark.parametrize("text", [
    "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purch Payroll Sec:CCD Trace#:{n}",
    "Orig CO Name:Sample Mutual Insurance CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:{n}",
    "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purch Dividend Sec:CCD Trace#:{n}",
    "Orig CO Name:Sample CU Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purch Adj Sec:CCD Trace#:{n}",
    "CU DIRECT DES:VHCL PURCH PAYROLL ID:{n}",
])
def test_the_credit_union_arm_and_cu_direct_honour_the_section_8_1_holds(text):
    rows = _records([(text.format(n=1), 18000.0), (text.format(n=2), 21000.0)], holder=DEALER)
    for record in rows:
        assert record.revenue_match_method not in {"auto_lender_dealer_funding", "credit_union_vehicle_purchase"}
        assert record.revenue_classification != "verified_revenue"
        assert record.revenue_tier == "excluded_pending_review"
        assert record.match_method not in {"auto_lender_dealer_funding", "credit_union_vehicle_purchase"}


def test_suncoast_verifies_only_through_the_credit_union_arm():
    from analysis.classification_registry import DEALER_FUNDING_PAYERS

    assert "Suncoast Credit Union" not in DEALER_FUNDING_PAYERS
    # S1.5: Suncoast prints the holder's own funding transfers as ACCT FUND: never dealer funding, alone or repeated.
    for text in ("SUNCOAST CU DES:ACCT FUND ID:1", "SUNCOAST CREDIT UNION DES:ACCT FUNDING ID:1"):
        record = _one(text, 15000.0, holder=DEALER)
        assert record.revenue_classification != "verified_revenue"
        assert record.revenue_match_method != "auto_lender_dealer_funding"
    repeated = _records([("SUNCOAST CU DES:ACCT FUND ID:1", 15000.0), ("SUNCOAST CU DES:ACCT FUND ID:2", 16000.0)],
                        holder=DEALER)
    assert "verified_revenue" not in {record.revenue_classification for record in repeated}
    lone = _one("SUNCOAST CREDIT UNION DES:VHCL PURCH ID:1", 18000.0, holder=DEALER)
    assert _tier(lone) == ("excluded_pending_review", "financing_named_payer")
    two = _records([("SUNCOAST CREDIT UNION DES:VHCL PURCH ID:1", 18000.0),
                    ("SUNCOAST CREDIT UNION DES:VHCL PURCH ID:2", 21000.0)], holder=DEALER)
    for record in two:
        assert (record.revenue_classification, record.revenue_match_method) == (
            "verified_revenue", "auto_lender_dealer_funding")
        assert record.revenue_canonical_entity == "SUNCOAST CREDIT UNION"
        assert record.match_method == "credit_union_vehicle_purchase"


def test_a_q7_verified_row_never_makes_a_q6_repeat():
    neutral = "Orig CO Name:Contoso CU Orig ID:1 Desc Date: CO Entry Descr:Payment Sec:CCD Trace#:7"
    union = UNION.replace("Sample CU", "Contoso CU")
    alone = _one(neutral, 5000.0, holder=DEALER)
    rows = _records([(union.format(n=1), 18000.0), (union.format(n=2), 21000.0), (neutral, 5000.0)], holder=DEALER)
    assert [record.revenue_match_method for record in rows[:2]] == ["auto_lender_dealer_funding"] * 2
    assert rows[2].revenue_classification != "verified_revenue"
    assert _tier(rows[2]) == _tier(alone) == ("counted_flagged", "named_payer_one_off")


@pytest.mark.parametrize("text", [
    "ONE RIVER FUNDING DES:PAYABLES DEALER PAY ID:1",
    "ONE RIVER GROUP DES:PAYABLES DEAL FUNDING ID:1",
])
def test_one_river_s_ledger_spellings_with_payables_and_a_dealer_word_stay_financing(text):
    record = _one(text, 15000.0, holder=DEALER)
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert record.canonical_entity == "One River Group Inc"
    assert record.contributes_to_lender_credit_exclusion


# A3 (the precision sample of the largest counted rows, 2026-09-30): four shapes counted in True that are not sales.
_A3_WIRE = "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK ID:1"


@pytest.mark.parametrize("text", [
    "INCOMING FEDWIRE TRANSFER",
    "INCOMING FEDWIRE TRANSFER REF 12345678",
    "FEDWIRE TRANSFER CREDIT",
    "INCOMING FED WIRE TRANSFER",
    "INCOMING CHIPS TRANSFER",
    "SWIFT TRANSFER CREDIT REF 12345678",
    "WIRE TRANSFER REF NUMBER 123456 1",
])
def test_a3_a_wire_worded_transfer_with_no_sender_is_held_as_a_wire_with_no_sender(text):
    # Q5: a wire with no sender stays out until confirmed. The wire's channel and layout words name nobody.
    from analysis.transaction_classifier import revenue_text
    from analysis.true_revenue import _transfer_counterparty_words

    record = _one(text, 24950.0)
    assert _tier(record) == ("excluded_pending_review", "wire_no_sender")
    assert not record.contributes_to_true_revenue
    assert _transfer_counterparty_words(revenue_text(record.normalized_description)) == []


def test_a3_a_named_wire_sender_is_still_counted_or_verified():
    assert _tier(_one("WIRE IN FROM FABRIKAM SUPPLY LLC TRN 99", 24950.0)) == ("counted_flagged", "wire_named_sender")
    twice = _records([(_A3_WIRE.format(n=1, orig="NORTHWIND EXPORTS LLC"), 25000.0),
                      (_A3_WIRE.format(n=2, orig="NORTHWIND EXPORTS LLC"), 26000.0)])
    assert {record.revenue_match_method for record in twice} == {"repeat_wire_sender"}
    # A wire-worded transfer that names its sender keeps its named-transfer reading.
    assert _tier(_one("FEDWIRE TRANSFER FROM FABRIKAM SUPPLY LLC", 24950.0)) == ("counted_flagged", "p2p")


@pytest.mark.parametrize("text", [
    "ONLINE BANKING FOREIGN EXCHANGE #WW123456789012",
    "ONLINE TRANSFER FOREIGN EXCHANGE REF 12345678",
    "CURRENCY CONVERSION REF 12345678",
    "FX CONVERSION 12345678",
    "CONVERSION DE DEVISES 12345678",
    "CHANGE DE DEVISES 12345678",
])
def test_a3_the_holder_s_own_currency_conversion_is_held(text):
    # The standing rule: owner money never becomes revenue. A conversion names no counterparty and designates no
    # account (T13), so it is held as non_sale_purpose (§8.1's own-money group, as SWEEP and ZBA are).
    from analysis.transaction_classifier import revenue_text
    from analysis.true_revenue import _transfer_counterparty_words

    record = _one(text, 12000.0)
    assert _tier(record) == ("excluded_pending_review", "non_sale_purpose")
    assert _transfer_counterparty_words(revenue_text(record.normalized_description)) == []


def test_a3_repeated_round_currency_conversions_are_held_as_own_money():
    rows = _records([("ONLINE BANKING FOREIGN EXCHANGE #WW123456789012", 1500.0),
                     ("ONLINE BANKING FOREIGN EXCHANGE #WW123456789013", 1500.0)])
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


def _banked(text: str, amount: float, *, bank: str | None, holder: str | None = HOLDER):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date="2054-03-02", description=text, amount=amount, direction="credit")]))[0]


def test_a3_a_named_payer_that_prints_currency_wording_keeps_its_reading():
    wire = ("WIRE TYPE:FX IN DATE:540102 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:FABRIKAM GMBH ID:99 SND BK:SAMPLE BANK ID:1 "
            "OBI:FOREIGN EXCHANGE")
    assert _tier(_one(wire, 24950.0)) == ("counted_flagged", "wire_named_sender")
    # A payer other than the statement's bank, printed before the wording, names someone (A3 review).
    for bank in (None, "Royal Bank of Canada"):
        assert _tier(_banked("NORTHWIND FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789", 2500.0, bank=bank)) == (
            "counted_flagged", "named_payer_unlabelled")
    assert _tier(_banked("ROYAL FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789", 2500.0, bank="Chase")) == (
        "counted_flagged", "named_payer_unlabelled")


@pytest.mark.parametrize("bank", ["Royal Bank of Canada", "Banque Royale du Canada"])
@pytest.mark.parametrize("text", [
    "ROYAL FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345",
    "RBC FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345",
    "ROYAL BANK FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345",
])
def test_a3_the_statement_bank_s_own_foreign_exchange_deposit_is_held(bank, text):
    # A3 review: the statement's bank printing its own name before the wording names no payer; the credit is the
    # holder's own money converted, held like every other conversion.
    record = _banked(text, 20000.0, bank=bank)
    assert _tier(record) == ("excluded_pending_review", "non_sale_purpose")
    assert not record.contributes_to_true_revenue


def test_a3_any_statement_bank_s_whole_name_before_the_wording_names_no_payer():
    text = "CHASE FX CONVERSION DEPOSIT 12345678"
    assert _tier(_banked(text, 5000.0, bank="Chase")) == ("excluded_pending_review", "non_sale_purpose")
    assert _tier(_banked(text, 5000.0, bank="Wells Fargo")) == ("counted_flagged", "named_payer_unlabelled")


@pytest.mark.parametrize("text", [
    "ROYAL FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345",
    "RBC ROYAL BANK FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345",
])
def test_a3_review_2_a_bank_field_that_contains_rbc_s_name_reads_rbc_s_printed_forms(text):
    # A3 review round 2: the statement's bank is matched by its normalized words, not its exact spelling.
    for bank in ("RBC Royal Bank", "RBC ROYAL BANK (CANADA)"):
        assert _tier(_banked(text, 20000.0, bank=bank)) == ("excluded_pending_review", "non_sale_purpose")


def test_a3_review_2_rbc_s_forms_never_read_on_another_bank_or_an_empty_bank_field():
    text = "ROYAL FOREIGN EXCHANGE DEPOSIT REFERENCE 123456789012345"
    for bank in ("Chase", "", None):
        assert _tier(_banked(text, 20000.0, bank=bank)) == ("counted_flagged", "named_payer_unlabelled")


@pytest.mark.parametrize(("text", "reason"), [
    ("CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", "named_payer_one_off"),
    ("Orig CO Name:Foreign Exchange Intl Orig ID:1 Desc Date: CO Entry Descr:Payment Sec:CCD Trace#:1",
     "named_payer_one_off"),
    (_A3_WIRE.format(n=1, orig="CURRENCY EXCHANGE INTERNATIONAL"), "wire_named_sender"),
    ("FOREIGN EXCHANGE CO DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", "named_payer_one_off"),
])
def test_a3_review_a_named_currency_exchange_company_is_a_payer(text, reason):
    # A3 review: the wording is the payer's own name when an originator field (an ACH originator, a wire's labelled
    # sender) names it with a company form (LLC, INC, CORP, CO, LTD, INTERNATIONAL or INTL) beside the wording.
    assert _tier(_one(text, 8000.0)) == ("counted_flagged", reason)


@pytest.mark.parametrize("text", [
    "ONLINE BANKING FOREIGN EXCHANGE #WW123456789012",
    "ONLINE TRANSFER INTL FOREIGN EXCHANGE REF 12345678",
    "CURRENCY EXCHANGE DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    # A3 review round 2: an organisation word on a row with no originator field names no company.
    "INTL FOREIGN EXCHANGE DEPOSIT 12345678",
    "INTERNATIONAL FX CONVERSION 12345678",
    "FX CONVERSION INTL 12345678",
])
def test_a3_review_the_wording_with_no_payer_name_beside_it_stays_held(text):
    assert _tier(_one(text, 8000.0)) == ("excluded_pending_review", "non_sale_purpose")


def test_a3_a_currency_conversion_debit_is_untouched():
    debit = classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-02", description="ONLINE BANKING FOREIGN EXCHANGE #WW123456789012", amount=-2500.0,
                    direction="debit")]))[0]
    assert (debit.classification, debit.match_method) == ("other", "default")
    assert (debit.revenue_classification, debit.revenue_tier, debit.revenue_tier_reason) == (None, None, None)


@pytest.mark.parametrize("text", [
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O CHICAGO TITLE TRUST COMPANY CHICAGO IL 60601 US REF SAMPLE NYC "
    "CTR BNF CONTOSO BAKERY LLC SAMPLEVILLE IL",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHWIND TITLE AND TRUST COMPANY SAMPLEVILLE IL 60601 US REF "
    "SAMPLE NYC CTR BNF CONTOSO BAKERY LLC",
    "CHIPS CREDIT VIA SAMPLE BANK N A 1234 B/O FIDELITY NATIONAL TITLE COMPANY 12345 REF NBNF CONTOSO BAKERY LLC",
    _A3_WIRE.format(n=1, orig="FABRIKAM TITLE LLC"),
    _A3_WIRE.format(n=1, orig="STEWART TITLE"),
    "FIRST AMERICAN TITLE DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "OLD REPUBLIC TITLE DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "Orig CO Name:Fabrikam Title Agency Orig ID:1 Desc Date: CO Entry Descr:Payment Sec:CCD Trace#:1",
    "NORTHWIND TITLE SERVICES DES:PAYMENT ID:1",
    "NORTHWIND TITLE GUARANTY CO DES:PAYMENT ID:1",
    "NORTHWIND CLOSING TITLE DES:PAYMENT ID:1",
])
def test_a3_a_title_firm_s_payment_is_held_on_wires_and_ach(text):
    # A title firm pays out property-closing proceeds (an asset sale), never the business's operating revenue.
    record = _one(text, 150000.0)
    assert _tier(record) == ("excluded_pending_review", "non_sale_purpose")
    assert not record.contributes_to_true_revenue


def test_a3_a_title_firm_that_pays_twice_is_held_not_verified():
    rows = _records([("FIRST AMERICAN TITLE DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", 2500.0),
                     ("FIRST AMERICAN TITLE DES:PAYMENT ID:2 INDN:CONTOSO BAKERY CO ID:1 CCD", 2600.0)])
    assert {_tier(record) for record in rows} == {("excluded_pending_review", "non_sale_purpose")}


@pytest.mark.parametrize("text", [
    "TITLEIST DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "TITLE BOXING CLUB DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
])
def test_a3_a_payer_named_title_in_another_sense_is_not_held(text):
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")
    assert _tier(_one("WIRE IN FROM TITLE BOXING CLUB LLC TRN 99", 2500.0)) == ("counted_flagged", "wire_named_sender")


@pytest.mark.parametrize("payer", ["CHICAGO TITLE BOXING CLUB", "STEWART TITLE CLUB"])
def test_a3_review_a_title_insurer_s_city_or_name_before_boxing_or_club_is_no_title_firm(payer):
    from analysis.true_revenue import _TITLE_FIRM

    assert _TITLE_FIRM.search(payer) is None
    text = f"{payer} DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD"
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")
    insurer = text.replace(" BOXING CLUB", "").replace(" CLUB", "")
    assert _tier(_one(insurer, 2500.0)) == ("excluded_pending_review", "non_sale_purpose")


_A3_TITLE_FEDWIRE = ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O FIRST AMERICAN TITLE COMPANY 12345 REF SAMPLE NYC CTR "
                     "BNF CONTOSO REALTY LLC SAMPLEVILLE CA 12345 US AC 123456789 OBI {obi} IMAD 0102A1B2C3D4 TRN 1234FF")


@pytest.mark.parametrize(("obi", "reason"), [
    # The holder's fee paid at closing takes its normal reading (orchestrator ruling, A3): a commission or a fee is a
    # verification-only word (§8.6), and an invoice wire from a title firm never verifies (§7.9's title veto).
    ("COMMISSION 1234 SAMPLE ST", "named_payer_purpose_refused"),
    ("URI 1234 ORIGINATION FEE SAMPLE", "named_payer_purpose_refused"),
    ("BROKER FEE 1234", "named_payer_purpose_refused"),
    ("INVOICE 1042 SAMPLE", "wire_named_sender"),
    ("URI CONSULTING 1234", "wire_named_sender"),
    ("FEE FOR SERVICES 1234", "named_payer_purpose_refused"),
    ("URI 1234 ORIGINATION SAMPLE", "wire_named_sender"),
    # A3 review round 2: ORIG FEE is purpose wording, never the start of an originator field.
    ("ORIG FEE 1234", "wire_named_sender"),
])
def test_a3_a_title_firm_s_wire_that_cites_the_holder_s_fee_is_not_held(obi, reason):
    assert _tier(_one(_A3_TITLE_FEDWIRE.format(obi=obi), 10000.0, holder="CONTOSO REALTY LLC")) == (
        "counted_flagged", reason)


def test_a3_a_title_firm_s_purpose_invoice_wire_and_commission_ach_are_not_held():
    purpose_invoice = _A3_WIRE.format(n=1, orig="STEWART TITLE") + " PMT DET:INV 1042"
    assert _tier(_one(purpose_invoice, 10000.0)) == ("counted_flagged", "wire_named_sender")
    ach = "FIRST AMERICAN TITLE DES:COMMISSION ID:1 INDN:CONTOSO REALTY CO ID:1 CCD"
    assert _tier(_one(ach, 10000.0, holder="CONTOSO REALTY LLC")) == ("counted_flagged", "named_payer_purpose_refused")
    # A book transfer prints its URI purpose inside its REF field: the URI is read, never the REF text before it.
    book = ("BOOK TRANSFER CREDIT B O FIRST AMERICAN TITLE COMPANY SAMPLEVILLE CA 12345 US REF 1234ABCD URI COMMISSION "
            "5678 SAMPLE ST")
    assert _tier(_one(book, 10000.0, holder="CONTOSO REALTY LLC")) == ("counted_flagged", "named_payer_purpose_refused")


_A3_TITLE_FEDWIRE_REF = ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O FIRST AMERICAN TITLE COMPANY 12345 REF {ref} "
                         "BNF CONTOSO REALTY LLC SAMPLEVILLE CA 12345 US AC 123456789 OBI PROP ADDR 12 SAMPLE ST IMAD "
                         "0102A1B2C3D4 TRN 1234FF")


@pytest.mark.parametrize("text", [
    # Fedwire's REF field is the sender's bank reference, never the wire's purpose (A3 review).
    _A3_TITLE_FEDWIRE_REF.format(ref="COMM BANK NYC"),
    _A3_TITLE_FEDWIRE_REF.format(ref="SAMPLE INV CTR 1234"),
    _A3_WIRE.format(n=1, orig="STEWART TITLE") + " REF INV 1042",
    "BOOK TRANSFER CREDIT B O FIRST AMERICAN TITLE COMPANY SAMPLEVILLE CA 12345 US REF COMMISSION 5678 SAMPLE ST",
    # Bank of America's SERVICE REF is its own reference field (A3 review round 2).
    "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 SERVICE REF:COMM 1234 SEQ:1/2 ORIG:STEWART TITLE ID:99 SND "
    "BK:SAMPLE BANK ID:1",
])
def test_a3_review_the_title_fee_exemption_never_reads_a_ref_field(text):
    assert _tier(_one(text, 150000.0, holder="CONTOSO REALTY LLC")) == ("excluded_pending_review", "non_sale_purpose")


_A3_SANTANDER_TITLE = "USD WIRE IN FROM SAMPLE BANK ACCT 123456 FIRST AMERICAN TITLE CO REF {purpose}"


def test_a3_review_2_santander_s_ref_field_is_its_purpose():
    # A3 review round 2: Santander prints 'ACCT <n> <originator> REF <purpose>': its REF field is the purpose.
    fee = _one(_A3_SANTANDER_TITLE.format(purpose="COMMISSION 1234 SAMPLE ST"), 10000.0, holder="CONTOSO REALTY LLC")
    assert _tier(fee) == ("counted_flagged", "named_payer_purpose_refused")
    plain = _one(_A3_SANTANDER_TITLE.format(purpose="PROP ADDR 12 SAMPLE ST"), 150000.0, holder="CONTOSO REALTY LLC")
    assert _tier(plain) == ("excluded_pending_review", "non_sale_purpose")


def test_a3_a_plain_title_wire_with_closing_proceeds_stays_held():
    plain = _one(_A3_TITLE_FEDWIRE.format(obi="URI FN 1234 PROP ADDR 123 SAMPLE ST"), 150000.0)
    assert _tier(plain) == ("excluded_pending_review", "non_sale_purpose")


@pytest.mark.parametrize("text", [
    # BMO: the label printed twice, then the sender's country code and the sender.
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA NORTHWIND STAFFING INC",
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT MX FABRIKAM SA DE CV",
    # A reference, then the sender, then NOTPROVIDED or the sending bank's reference.
    "INCOMING WIRE 20540102 NORTHWIND SOLAR LLC NOTPROVIDED",
    "INCOMING WIRE 20540102 JOHN Q SAMPLE OW12345678901234",
    # TD Bank.
    "WIRE TRANSFER INCOMING FABRIKAM ENTERPRISES LLC",
    # Wilson & Muir.
    "WIRE TRANSFER FROM JOHN Q SAMPLE",
    # Capital One.
    "WIRE TRANSFER DEPOSIT FABRIKAM SUPPLY LLC 123456 USD1234567XXXXXX1234",
    # Scotiabank.
    "INCOMING WIRE TRANSFER NORTHWIND METALS INC WIRE PAYMENT",
    # SECU.
    "DOMESTIC WIRE DEPOSIT WIRE IN NORTHWIND BUILDERS LLC",
])
def test_a3_a_wire_that_prints_its_sender_after_the_label_is_never_held_as_no_sender(text):
    record = _one(text, 24950.0)
    assert _tier(record) == ("counted_flagged", "wire_named_sender")


def test_a3_a_numbered_company_after_bmo_s_country_code_keeps_its_number():
    from analysis.transaction_classifier import payer_region, revenue_text

    record = _one("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA 1234567 ONTARIO INC", 24950.0)
    assert payer_region(revenue_text(record.normalized_description)) == "1234567 ONTARIO INC"
    assert _tier(record) == ("counted_flagged", "wire_named_sender")
    assert record.revenue_classification == "unverified_deposit"


def test_a3_a_company_that_wires_twice_in_bmo_s_layout_verifies_by_q5():
    rows = _records([("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA NORTHWIND STAFFING INC", 24950.0),
                     ("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA NORTHWIND STAFFING INC", 26950.0)])
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}


def test_a3_a_sender_read_after_the_label_whose_name_a_line_wrap_splits_still_reads_as_financing():
    record = _one("WIRE TRANSFER DEPOSIT SAMPLE F INANCIAL S 123456 USD1234567XXXXXX1234", 55000.0)
    assert _tier(record) == ("excluded_pending_review", "financing_named_payer")


def _a3_fedwire(orig: str) -> str:
    return (f"FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O {orig} SAMPLEVILLE CA 12345 US REF SAMPLE NYC CTR "
            "BNF CONTOSO BAKERY LLC")


@pytest.mark.parametrize("text", [
    _A3_WIRE.format(n=1, orig="FABRIKAM SERVICE REPAIR LLC"),
    _A3_WIRE.format(n=1, orig="SOLO ANALYTICS LLC"),
    _A3_WIRE.format(n=1, orig="ROYAL ENDEAVORS INC"),
    _a3_fedwire("FABRIKAM SERVICE REPAIR LLC"),
    _a3_fedwire("SOLO ANALYTICS LLC"),
    _a3_fedwire("ROYAL ENDEAVORS INC"),
    # A3 review round 2: the senders read after the label.
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA ROYAL ENDEAVORS INC",
    "WIRE TRANSFER INCOMING SOLO ANALYTICS LLC",
    "WIRE TRANSFER INCOMING FABRIKAM SERVICE REPAIR LLC",
])
def test_a3_review_two_whole_words_run_together_never_make_a_financing_root(text):
    # A3 review: joined words make false roots (SERVICE REPAIR -> SERVICER, SOLO ANALYTICS -> LOAN, ROYAL ENDEAVORS
    # -> LEND). Round 2: a joined root counts only across one join whose shorter word has two letters or fewer (a line
    # wrap's split); §7.9's veto still reads the run, so such a wire never verifies by Q5.
    assert _tier(_one(text, 24950.0)) == ("counted_flagged", "wire_named_sender")


@pytest.mark.parametrize("text", [
    "WIRE TRANSFER DEPOSIT SAMPLE F INANCIAL S 123456 USD1234567XXXXXX1234",
    # A3 review round 2: a labelled originator's line-wrap split is read again.
    _A3_WIRE.format(n=1, orig="NORTHWIND F INANCIAL LLC"),
    _a3_fedwire("NORTHWIND F INANCIAL LLC"),
    _A3_WIRE.format(n=1, orig="NORTHWIND SERVICIN G LLC"),
])
def test_a3_review_2_a_line_wrap_split_financing_root_is_held_on_every_wire_sender(text):
    assert _tier(_one(text, 55000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("text", [
    "FABRICRED INC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    _A3_WIRE.format(n=1, orig="NORTHCRED INC"),
    "WIRE TRANSFER INCOMING FASTCRED LLC",
    # A3 review round 2: only the whole words SACRED and ACCRED are spared.
    "USACRED LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "VISACRED INC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "NACRED LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
])
def test_a3_review_a_payer_whose_name_ends_in_a_glued_cred_is_held_as_financing(text):
    # §7.9's word-end CRED arm, aligned in T4 with a glued letter on its left (a credit provider's glued name), read on
    # the payer's name only (an ACH originator, a wire's sender, a transfer's FROM sender).
    assert _tier(_one(text, 42000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize(("text", "tier"), [
    ("SACRED HEART ACADEMY DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", ("verified", None)),
    ("CRED SUPPLY LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", ("verified", None)),
    ("ACCRED HEALTH SERVICES DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", ("counted_flagged", "named_payer_one_off")),
    # A3 review round 2: an entry field and a row that prints no payer's name field are never read for it.
    ("FABRIKAM SUPPLY LLC DES:ACCTCRED ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", ("verified", None)),
    ("ACHCRED 12345678", ("counted_flagged", "named_payer_unlabelled")),
])
def test_a3_review_the_whole_word_cred_sacred_accred_an_entry_and_a_payerless_row_are_no_root(text, tier):
    assert _tier(_one(text, 4200.0)) == tier


@pytest.mark.parametrize("text", [
    "INCOMING WIRE",
    "INCOMING WIRE 12345678 NOTPROVIDED",
    "INCOMING WIRE TRANSFER WIRE REF 12345678 12345678",
    "DOMESTIC INCOMING WIRE QA1234F12QN1 WQA1234F12QN1",
    "WIRE TRANSFER IN",
    "WIRE TRANSFER CREDIT",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789",
    # Its only name-like words are a reference token and a legal form, and a legal form alone names nobody (the P2P
    # reader's rule): held, so census guard G4 (no transfer-worded row without a counterparty in True) stays green.
    "WIRE TRANSFER INCOMING 1ABC LLC",
])
def test_a3_a_wire_that_prints_no_sender_stays_held(text):
    assert _tier(_one(text, 24950.0)) == ("excluded_pending_review", "wire_no_sender")
