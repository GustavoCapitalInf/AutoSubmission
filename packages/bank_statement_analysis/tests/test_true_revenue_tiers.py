"""Classification 5.6 (true revenue spec §5.3, §8, T11 to T14): the tier and reason of every posted credit, the holds,
the channel tiers, and the Q5, Q6 and Q7 verifications with their guards. Fabricated rows only, in the banks' printed
formats."""
from __future__ import annotations

import pytest

from analysis.true_revenue import tiers as true_revenue_tiers
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from analysis.classification.counter_debit_reading import _debit_first_distinctive_word
from tests.zelle_reading import rules_reading

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
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    return rules_reading(record)


@pytest.mark.parametrize(("text", "reason"), [
    # Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: a listed insurer's DRP pays for the business's work (the
    # service form), counted and flagged, never verified (it was held as insurer_payer).
    ("STATE FARM DES:DRP PAYMENT ID:1", "insurer_paid_for_services"),
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
    # GOV (owner ruling 2026-09-30): a payment the IRS issues is a tax refund, non_revenue (tests/
    # test_revenue_non_revenue_55.py); a state's earned-income credit is still the public payer's non-sale credit.
    ("STATE OF OHIO DES:TAX EIC ID:1", "non_sale_purpose"),
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
    from tests.zelle_reading import zelle_policy_due

    record = _one(text)
    assert _tier(record) == (REVENUE_TIER_REASONS[reason][0], reason)
    if zelle_policy_due(record):
        # The owner's ruling of 2026-10-02 (the underwriter's Q3): the rules' reading kept, the Zelle deposit excluded.
        assert (record.revenue_classification, record.revenue_review_required) == ("non_revenue", False)
        return
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
    # Audit B9 (I13): the credit's receiver is the holder, never the payer again (a row whose originator is its own
    # receiver is the holder's own push, held as holder_name first).
    records = _records([
        ("NORTHWIND BAKERY DES:TRANSFER ID:1 INDN:CONTOSO DINER CO ID:1 CCD", 5000.0),
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
    from analysis.descriptor import payer

    assert payer.numbered_company("03 02 DIRECT DEPOSIT 7654321 CANA AP CC")
    assert not payer.numbered_company("5 3 FABRIKAM SUPPLY LLC DES PAYMENT ID 1")
    assert _one("5/3 FABRIKAM SUPPLY LLC DES:PAYMENT ID:1", 700.0).revenue_match_method == "named_payer_company_form"


@pytest.mark.parametrize("text", [
    "EXTERNAL TRANSFER DES:TRANSFER ID:1234", "WEB TRANSFER DES:TRANSFER ID:1 WEB",
    "TRANSFER DES:TRANSFER ID:ABC123 CCD", "ORIG CO NAME:TRANSFER ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:PPD",
    # Audit B2 (I21): 'TRANSFER FROM LOC 1234' left this list: a transfer from the holder's line of credit is now
    # the strong rule's own-account source (non_revenue, tests/test_true_revenue_transfers.py).
    "ONLINE TRANSFER REF #IBEABCD", "ONLINE TRANSFER FROM HELOC", "TRANSFER FROM TAX RESERVE",
    "ONLINE TRANSFER FROM OPERATING", "TRANSFER FROM RESERVE", "ONLINE TRANSFER FROM PRIMARY", "TRANSFER FROM PERSONAL",
    "ONLINE TRANSFER FROM JOINT", "ONLINE TRANSFER FROM IRA",
])
def test_a_bare_transfer_or_an_own_account_nickname_is_held(text):
    # Q2 (review I2): field labels, SEC codes, references and account descriptions are no counterparty.
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.descriptor.lexical import revenue_text

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


#: Audit round 3, R3-B15 (R3-63): rows a remittance descriptor verifies and a pass-7 demotion overrules at $1 or more: a
#: builder's progress draw (Q11 (a)) and a public factoring payer's payout (A3-H; LOVES SOLUTIONS is the registry's
#: FACTORING_PAYOUT_PAYERS entry).
R3_63_DEMOTIONS = [
    ("CONTOSO BUILDERS INC DES:A P PMT DRAW 3 ID:0001 INDN:NORTHWIND SOLAR LLC CO ID:0000000001 CCD", 0.50,
     ("counted_flagged", "construction_progress_draw"), "construction_progress_draw"),
    ("LOVES SOLUTIONS DES:A P PMT ID:0001 INDN:NORTHWIND SOLAR LLC CO ID:0000000001 CCD", 0.55,
     ("counted_flagged", "factoring_payout"), "factoring_payout_payer"),
]


@pytest.mark.parametrize(("text", "micro", "demoted", "demoted_method"), R3_63_DEMOTIONS)
def test_r3_63_the_floor_overrules_a_demotion_of_a_credit_under_one_dollar(text, micro, demoted, demoted_method):
    """Audit round 3, R3-B15 (R3-63; §8.10, §20's $1-floor line): every pass-7 demotion leaves a credit under $1 to the
    floor, so the floor holds it with its own method, rule and sentence naming the rule it overruled (today the row kept
    the demotion's method, rule and "counted and flagged, never verified" sentence); at $1 and above the demotion reads
    as before."""
    record = _one(text, micro, holder="NORTHWIND SOLAR LLC")
    assert _tier(record) == MICRO
    assert (record.revenue_match_method, record.revenue_matched_rule) == (
        "micro_deposit_floor", "credit_under_micro_deposit_floor")
    assert "payer_remittance_descriptor" in record.revenue_reason
    assert "counted and flagged" not in record.revenue_reason
    assert record.revenue_classification == "unverified_deposit" and record.revenue_review_required
    for amount in (1.0, 12500.0):
        control = _one(text, amount, holder="NORTHWIND SOLAR LLC")
        assert _tier(control) == demoted
        assert control.revenue_match_method == demoted_method
        assert "counted and flagged, never verified" in control.revenue_reason


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
    "E*TRADE SECURITIES LLC DES:ACCOUNTS PAYABLE ID:1", "FIDELITY BROKERAGE SERVICES LLC DES:VENDOR PAYMENT ID:1",
])
def test_a_brokerage_platform_s_accounts_payable_wording_is_counted_never_verified(text):
    # The investment word is spared by the AP wording. Audit round 2, R2-B12 (R37; amends this test's S4.2 pin, under
    # which the platform list still held the row): the owner-money platforms hold no vendor payment either, as the
    # S4.2 re-review's ruling reads accounts-payable wording ("the payer's vendor payment, revenue even from a
    # brokerage"); the investment word keeps it counted and flagged, never verified.
    assert _tier(_one(text, 3000.0)) == ("counted_flagged", "named_payer_purpose_refused")


def test_a_savings_or_investing_app_s_accounts_payable_wording_stays_held():
    # The classifier's consumer savings and investing originators are read as before (R2-B12 spares only the
    # registry's owner-money platforms).
    assert _tier(_one("ROBINHOOD SECURITIES LLC DES:PAYABLES ID:1", 3000.0)) == (
        "excluded_pending_review", "non_sale_purpose")


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
    from analysis.descriptor.lexical import revenue_text

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
    # Audit B5 (I59): the template reads a number that nothing, a province (or a cut of one) or BMO's code tail
    # follows; a reference before a named payer ('... PMT 1234567 NORTHWIND LTD') is no numbered company, dated or not.
    from analysis.descriptor import payer
    from analysis.descriptor import lexical
    from analysis.description_text import normalize_transaction_description

    for text in ("03/02 ACCOUNTS PAYABLE PMT 1234567", "ACCOUNTS PAYABLE PMT 1234567", "0302 ACCTS PAYABLE PMT 1234567",
                 "03/02 ACCOUNTS PAYABLE PMT 1234567 ONTA", "0302 ACCTS PAYABLE PMT 1234567 ONTA"):
        assert payer.numbered_company(lexical.revenue_text(normalize_transaction_description(text)))
        record = _one(text, 700.0)
        assert record.revenue_classification == "unverified_deposit"
        assert _tier(record) == ("counted_flagged", "numbered_company_payer")
    for text in ("03/02 ACCOUNTS PAYABLE PMT 1234567 NORTHWIND LTD", "ACCOUNTS PAYABLE PMT 1234567 NORTHWIND LTD",
                 "0302 ACCTS PAYABLE PMT 1234567 NORTHWIND LTD"):
        assert not payer.numbered_company(lexical.revenue_text(normalize_transaction_description(text)))


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
    from analysis.true_revenue import eligibility

    assert true_revenue._OWNER_MONEY_PLATFORMS.pattern == registry.OWNER_MONEY_PLATFORMS
    assert eligibility._SECTION_15_DEFERRED_PAYERS.pattern == registry.SECTION_15_DEFERRED_PAYERS
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
    from analysis.descriptor import rails

    wire = "WIRE TYPE WIRE IN DATE 540102 TRN 1 ORIG NORTHWIND EXPORTS LLC ID 99 BNF SQUARE ONE BAKERY OBI INV 12"
    assert "SQUARE" not in rails._without_receiver_value(wire)
    assert "NORTHWIND" in rails._without_receiver_value(wire)
    assert "OBI INV 12" in rails._without_receiver_value(wire)
    rtp = "REAL TIME TRANSFER RECD FROM ABA CONTR BNK 021000021 FROM BNF INTUIT PAYMENTS INC REF 1234 INFO SAMPLE"
    assert rails._without_receiver_value(rtp) == rtp
    remittance = "WIRE IN FROM NORTHWIND EXPORTS LLC ORIG TO BNF INFO SQUARE PAYOUT"
    assert "SQUARE PAYOUT" in rails._without_receiver_value(remittance)
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
    # Audit round 3, R3-29 (R3-B12): Interac's French name, virement par courriel, is an Interac form (Banque Royale's
    # autodeposit prints 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender> <reference>').
    "DEPOT AUTO VIREMENT PAR COURRIEL FABRIKAM LTEE C1AX23X", "VIREMENT PAR COURRIEL FABRIKAM LTEE",
]
#: Audit round 3, R3-29 (R3-B12): the plural, which pass 7 reads as the rail (_INTERAC_COURRIEL) and the classifier's
#: VIREMENT never reads (the 5.5 channel gate's residual, §8.4).
INTERAC_COURRIEL_PLURAL = [
    "DEPOT AUTO VIREMENTS PAR COURRIEL FABRIKAM LTEE C1AX23X", "VIREMENTS PAR COURRIEL FABRIKAM LTEE",
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


@pytest.mark.parametrize("text", INTERAC_VIREMENTS + INTERAC_COURRIEL_PLURAL)
def test_an_interac_virement_keeps_its_person_to_person_reading(text):
    # §8.4: Interac prints VIREMENT INTERAC; with the e-transfer or autodeposit words a VIREMENT is the rail too.
    assert _tier(_one(text, 250.0)) == P2P


@pytest.mark.parametrize("text", INTERAC_COURRIEL_PLURAL)
def test_r3_29_the_plural_courriel_form_is_the_rail_in_pass_7_only(text):
    # Audit round 3, R3-29 (R3-B12): pass 7 reads it, with the round-sum repeat; the classifier's rail is unchanged.
    from analysis.descriptor import lexical
    from analysis.descriptor import words
    from analysis.description_text import normalize_transaction_description

    normalized = lexical.revenue_text(normalize_transaction_description(text))
    assert words._CONSUMER_P2P_RAIL.search(normalized) is None
    rows = _records([(text, 500.0), (text.replace("C1AX23X", "C1AX24X"), 600.0), (text, 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize("name", ["FABRIKAM LTEE", "123456789012 JOHN SMITH"])
def test_an_interac_virement_s_round_repeat_is_unchanged(name):
    rows = _records([(f"VIREMENT INTERAC {name}", 500.0), (f"VIREMENT INTERAC {name}", 600.0),
                     (f"VIREMENT INTERAC {name}", 123.0)])
    assert [_tier(record)[1] for record in rows] == ["p2p_round_repeat", "p2p_round_repeat", "p2p"]


@pytest.mark.parametrize("text", FRENCH_TRANSFERS + INTERAC_VIREMENTS)
def test_the_5_5_channel_gate_of_a_virement_is_unchanged(text):
    # The 5.5 census was accepted on _CONSUMER_P2P_RAIL: every VIREMENT row is still a closed person-to-person row
    # there, never verified; only pass 7's tiering reads the Interac forms.
    from analysis.descriptor import payer
    from analysis.descriptor import lexical
    from analysis.descriptor import words
    from analysis.description_text import normalize_transaction_description

    normalized = lexical.revenue_text(normalize_transaction_description(text))
    assert payer.channel_gate(normalized) == "closed"
    assert words._CONSUMER_P2P_RAIL.search(normalized) is not None
    assert _one(text, 250.0).revenue_classification == "unverified_deposit"


def test_the_census_reads_a_virement_s_transfer_fact_as_pass_7_does():
    # §14.3 G4 reads the pass's own transfer fact.
    from analysis import true_revenue
    from analysis.description_text import normalize_transaction_description
    from analysis.descriptor.lexical import revenue_text

    for text, held in [("VIREMENT EN LIGNE TF 1234567", True), ("VIREMENT ENTRE COMPTES 1234567", True),
                       ("VIREMENT EN LIGNE FABRIKAM LTEE", False), ("VIREMENT INTERAC FABRIKAM LTEE", False),
                       ("VIREMENT INTERAC RECU 1234", False),
                       # Audit round 3, R3-29 (R3-B12): the COURRIEL form is the rail, no transfer.
                       ("DEPOT AUTO VIREMENT PAR COURRIEL C1AX23X", False),
                       ("DEPOT AUTO VIREMENTS PAR COURRIEL C1AX23X", False)]:
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
    from analysis.descriptor.lexical import revenue_text

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
    from analysis.descriptor import rails

    assert rails._is_wire_row(text)
    stripped = rails._without_receiver_value(text)
    assert "STRIPE INC" in stripped and "SQUARE" not in stripped
    for label in ("B O", "ORIGINATOR", "ORG"):
        assert "NORTHWIND" in rails._without_receiver_value(
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
    from analysis.descriptor.lexical import revenue_text

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
    from analysis.transaction_classifier.operating_context import _in_operating_pool

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
    from analysis.descriptor.lexical import revenue_text
    from analysis.true_revenue.channel import _transfer_counterparty_words

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
    from analysis.descriptor.lexical import revenue_text
    from analysis.true_revenue.channel import _transfer_counterparty_words

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
    # A3 review round 3: RBC's markers are ROYAL BANK OF CANADA, RBC ROYAL BANK, RBC and BANQUE ROYALE; a bare ROYAL
    # BANK in another bank's name is no RBC.
    for bank in ("Chase", "", None, "Royal Bank of Scotland", "Royal Bank America"):
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
    # A3 review round 3: a legal form beside the wording names a company only on an originator field (an ACH
    # originator, a wire's labelled sender), never after a wire's label or on an unlabelled row.
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA FOREIGN EXCHANGE LTD",
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA FOREIGN EXCHANGE LLC",
    "FX CONVERSION LLC 12345678",
])
def test_a3_review_the_wording_with_no_payer_name_beside_it_stays_held(text):
    assert _tier(_one(text, 8000.0)) == ("excluded_pending_review", "non_sale_purpose")


@pytest.mark.parametrize("text", [
    "FOREIGN EXCHANGE LTD DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "FX CONVERSION LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
])
def test_a3_review_3_a_legal_form_on_an_originator_field_names_the_currency_company(text):
    assert _tier(_one(text, 8000.0)) == ("verified", None)


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
    from analysis.true_revenue.words import _TITLE_FIRM

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
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA 1234567 ONTARIO INC", 24950.0)
    assert payer_region(revenue_text(record.normalized_description)) == "1234567 ONTARIO INC"
    assert _tier(record) == ("counted_flagged", "wire_named_sender")
    assert record.revenue_classification == "unverified_deposit"


def test_a3_a_company_that_wires_twice_in_bmo_s_layout_verifies_by_q5():
    rows = _records([("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA NORTHWIND STAFFING INC", 24950.0),
                     ("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA NORTHWIND STAFFING INC", 26950.0)])
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}


def test_a3_a_sender_read_after_the_label_whose_name_a_line_wrap_splits_still_reads_as_financing():
    record = _one("WIRE TRANSFER DEPOSIT SAMPLE F INANCIAL S 123456 USD1234567XXXXXX1234", 45000.0)
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
    # A3 review round 3: a short word beside a name spells no financing word (ALLEN D -> LEND, HELEN DE and GLEN DI
    # -> LEND, CAPT L -> CAPTL, SERVICE RX -> SERVICER).
    _A3_WIRE.format(n=1, orig="ALLEN D JOHNSON"),
    _A3_WIRE.format(n=1, orig="HELEN DE JESUS"),
    _A3_WIRE.format(n=1, orig="GLEN DI MARCO"),
    _A3_WIRE.format(n=1, orig="CAPT L SMITH"),
    _A3_WIRE.format(n=1, orig="FAMILY SERVICE RX LLC"),
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O ALLEN D JOHNSON SAMPLEVILLE CA 12345 US REF SAMPLE NYC CTR BNF "
    "CONTOSO BAKERY LLC",
    # A Fedwire sender's city and state are never read for a joined root (GLEN DE -> LEND, LAMORT GA -> MORTG).
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHWIND SUPPLY LLC GLEN DE 12345 US REF SAMPLE NYC CTR BNF "
    "CONTOSO BAKERY LLC",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHWIND SUPPLY LLC LAMORT GA 12345 US REF SAMPLE NYC CTR BNF "
    "CONTOSO BAKERY LLC",
])
def test_a3_review_two_whole_words_run_together_never_make_a_financing_root(text):
    # A3 review: joined words make false roots (SERVICE REPAIR -> SERVICER, SOLO ANALYTICS -> LOAN, ROYAL ENDEAVORS
    # -> LEND). Round 3: a join counts only when its two words together spell a financing word, or a prefix of one of
    # five letters or more (a line wrap's split); §7.9's veto still reads the run, so such a wire never verifies by Q5.
    assert _tier(_one(text, 24950.0)) == ("counted_flagged", "wire_named_sender")


@pytest.mark.parametrize("text", [
    "WIRE TRANSFER DEPOSIT SAMPLE F INANCIAL S 123456 USD1234567XXXXXX1234",
    # A3 review round 2: a labelled originator's line-wrap split is read again.
    _A3_WIRE.format(n=1, orig="NORTHWIND F INANCIAL LLC"),
    _a3_fedwire("NORTHWIND F INANCIAL LLC"),
    _A3_WIRE.format(n=1, orig="NORTHWIND SERVICIN G LLC"),
    # A3 review round 3: the two words spell a financing word (LOAN, FUNDING) or a prefix of one (MORTG); recorded.
    _A3_WIRE.format(n=1, orig="NORTHWIND LO AN CO"),
    _A3_WIRE.format(n=1, orig="NORTHWIND MORT G CO"),
    _A3_WIRE.format(n=1, orig="NORTHWIND FUN DING LLC"),
])
def test_a3_review_2_a_line_wrap_split_financing_root_is_held_on_every_wire_sender(text):
    assert _tier(_one(text, 45000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("text", [
    "FABRICRED INC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    _A3_WIRE.format(n=1, orig="NORTHCRED INC"),
    "WIRE TRANSFER INCOMING FASTCRED LLC",
    # A3 review round 2: only the whole words SACRED and ACCRED are spared.
    "USACRED LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "VISACRED INC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "NACRED LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    # A3 review round 3: a payer region that prints a company form is a payer's name too.
    "FABRICRED INC EDI PYMNTS 240115 12345",
    "ACH CREDIT FABRICRED LLC 12345678",
    "ELECTRONIC DEPOSIT FABRICRED INC 12345678",
])
def test_a3_review_a_payer_whose_name_ends_in_a_glued_cred_is_held_as_financing(text):
    # §7.9's word-end CRED arm, aligned in T4 with a glued letter on its left (a credit provider's glued name), read on
    # the payer's name only (an ACH originator, a wire's sender, a transfer's FROM sender, a company-formed payer
    # region).
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


# A3-G (the redrawn largest_counted stratum's misses, 2026-09-30).
_A3G_BOFA = "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:{bank} ID:1 PMT DET:1234"


def _a3g_fedwire(orig: str, obi: str = "1234", place: str = "SAMPLEVILLE CA 12345 US") -> str:
    return (f"FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O {orig} {place} REF SAMPLE NYC CTR BNF "
            f"CONTOSO BAKERY LLC OBI {obi}")


@pytest.mark.parametrize("text", [
    # The originator reads as a bank by its own form.
    _A3G_BOFA.format(n=1, orig="NORTHWIND BANK", bank="NORTHWIND BANK"),
    _A3G_BOFA.format(n=1, orig="NORTHWIND BANK AP", bank="SAMPLE BANK"),
    _a3g_fedwire("NORTHWIND BANCORP"),
    _a3g_fedwire("NORTHWIND FEDERAL SAVINGS"),
    _a3g_fedwire("FABRIKAM SAVINGS BANK"),
    _a3g_fedwire("NORTHWIND BANK N A"),
    # The originator is the sending bank itself (a cut or a line wrap may split the bank field).
    _A3G_BOFA.format(n=1, orig="CONTOSO FEDERAL", bank="CONTOSO FEDERAL"),
    _A3G_BOFA.format(n=1, orig="FABRIKAMBA FIRST", bank="FABRIKAMBA FIRST NK"),
])
def test_a3g_a_wire_a_bank_originates_is_held_as_financing(text):
    # A3-G: money a bank sends on its own behalf is more often loan proceeds or the bank's own funds than a sale.
    assert _tier(_one(text, 257000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("text", [
    # Only the originator field is read: never the sending bank, the receiving bank or the purpose after it.
    _A3G_BOFA.format(n=1, orig="FABRIKAM SUPPLY LLC", bank="SAMPLE BANK"),
    _a3g_fedwire("FABRIKAM SUPPLY LLC", obi="INV 1234 SAMPLE BANK"),
    # A bank's merchant-services, bankcard, processor and settlement forms are settlements.
    _A3G_BOFA.format(n=1, orig="NORTHWIND BANK MERCHANT SERVICES", bank="NORTHWIND BANK"),
    _a3g_fedwire("NORTHWIND BANK BANKCARD SERVICES"),
    _a3g_fedwire("NORTHWIND BANK MERCH SVCS"),
    _A3G_BOFA.format(n=1, orig="NORTHWIND BANK SETTLEMENT", bank="NORTHWIND BANK"),
    _a3g_fedwire("NORTHWIND BANK STLMT"),
    # A3-G review: a company whose name holds the word BANK is no bank, nor is a food or blood bank.
    _A3G_BOFA.format(n=1, orig="LEFT BANK BAKERY LLC", bank="SAMPLE BANK"),
    _a3g_fedwire("BANK STREET PARTNERS LLC"),
    _A3G_BOFA.format(n=1, orig="NORTHWIND FOOD BANK", bank="SAMPLE BANK"),
    _a3g_fedwire("NORTHWIND BLOOD BANK"),
    # A3-G review: the sending-bank arm needs eight letters on its shorter side and an originator with no company form.
    _A3G_BOFA.format(n=1, orig="SUMMIT ROOFING LLC", bank="SUMMIT"),
    _A3G_BOFA.format(n=1, orig="SUMMIT ROOFING", bank="SUMMIT"),
])
def test_a3g_a_wire_whose_originator_is_no_bank_keeps_its_reading(text):
    assert _tier(_one(text, 24300.0))[1] != "financing_named_payer"


@pytest.mark.parametrize("text", [
    # The bank sends on its own behalf, its sending-bank field wrapped by a line ('BA NK').
    _A3G_BOFA.format(n=1, orig="NORTHWIND BANK AP", bank="NORTHWIND BA NK"),
    # A bank's own legal form after its name keeps it a bank ('<X> BANK LTD', '<X> BANK CO LTD', 'BANK OF <X> LIMITED').
    "BOOK TRANSFER CREDIT B O SAMPLE COMMERCIAL BANK LTD SAMPLE CITY CN REF SAMPLE 1 TRN 1234567890JS",
    "BOOK TRANSFER CREDIT B O SAMPLE INDUSTRIAL BANK CO LTD SAMPLE CITY CN REF SAMPLE 1 TRN 1234567890JS",
    "BOOK TRANSFER CREDIT B O BANK OF SAMPLELAND LIMITED HEAD OFFICE SAMPLE CITY REF SAMPLE 1 TRN 1234567890JS",
])
def test_a3g_review_a_bank_s_own_wire_stays_held(text):
    assert _tier(_one(text, 257000.0)) == ("excluded_pending_review", "financing_named_payer")


_A3G_RELAY = ("BOOK TRANSFER CREDIT B O SAMPLE COMMERCIAL BANK LTD SAMPLE CITY CN ORG {account} {customer} OGB SAMPLE "
              "COMMERCIAL BANK LTD REF SAMPLE {n} TRN 1234567890JS")


@pytest.mark.parametrize("text", [
    _A3G_RELAY.format(account="123456789012 1", customer="FABRIKAM TRADING LIMITED", n=1),
    _A3G_RELAY.format(account="GB12SAMP12345678901234", customer="FABRIKAM TRADING LIMITED", n=1),
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O SAMPLE BANK NA LONDON GB ORIGINATOR FABRIKAM TRADING LIMITED REF "
    "SAMPLE NYC CTR BNF CONTOSO BAKERY LLC",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O SAMPLE BANK NA LONDON GB BY ORDER OF FABRIKAM TRADING LIMITED "
    "REF SAMPLE NYC CTR BNF CONTOSO BAKERY LLC",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O SAMPLE BANK NA LONDON GB ORIG CUST FABRIKAM TRADING LIMITED REF "
    "SAMPLE NYC CTR BNF CONTOSO BAKERY LLC",
])
def test_a3g_refinement_a_relaying_bank_s_customer_is_the_wire_s_sender(text):
    # A3-G refinement: a correspondent bank that names the ultimate originator only relays: that customer is read.
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one(text, 13000.0)
    assert payer_region(revenue_text(record.normalized_description)) == "FABRIKAM TRADING LIMITED"
    assert _tier(record) == ("counted_flagged", "wire_named_sender")


def test_a3g_refinement_a_relayed_customer_that_wires_twice_verifies_by_q5():
    rows = _records([(_A3G_RELAY.format(account="123456789012 1", customer="FABRIKAM TRADING LIMITED", n=1), 13000.0),
                     (_A3G_RELAY.format(account="123456789012 1", customer="FABRIKAM TRADING LIMITED", n=2), 12000.0)])
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}


@pytest.mark.parametrize("text", [
    # A bank that names no customer after it sends on its own behalf (and an account number alone names nobody).
    "BOOK TRANSFER CREDIT B O SAMPLE EXPORT BANK SAMPLE CITY CN REF 1234 TRN 1234567890JS",
    _A3G_RELAY.format(account="123456789012", customer="", n=1),
    "FUNDS TRANSFER WIRE FROM SAMPLE EXPORT I MPORT BANK MAY 12",
])
def test_a3g_refinement_a_bank_that_names_no_customer_stays_held(text):
    assert _tier(_one(text, 13000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("obi", ["ORIGINATOR TO BENEFICIARY INFO 1234", "ORG TO BNF INFO 1234"])
def test_a3g_review_the_originator_to_beneficiary_phrase_names_no_relayed_customer(obi):
    # A3-G review: ORIGINATOR TO BENEFICIARY (ORG TO BNF) is the purpose's label, never a relay label.
    text = ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O SAMPLE BANK NA LONDON GB REF SAMPLE NYC CTR BNF CONTOSO "
            f"BAKERY LLC OBI {obi}")
    assert _tier(_one(text, 50000.0)) == ("excluded_pending_review", "financing_named_payer")


def test_a3g_review_a_b_o_company_that_ends_in_co_keeps_its_wrap_split_root():
    # A3-G review: the Fedwire city and state skip is gone; a company form CO is no state code.
    text = "BOOK TRANSFER CREDIT B O NORTHWIND F INANCIAL CO REF 1234 TRN 1234567890JS"
    assert _tier(_one(text, 45000.0)) == ("excluded_pending_review", "financing_named_payer")


def test_a3g_review_a_digit_without_its_slash_is_part_of_the_name():
    # A3-G review: a SWIFT 50F line number prints with its slash ('1/'); a name that starts with a number keeps it.
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one(_A3_WIRE.format(n=1, orig="2 NORTHWIND BAKERS LLC"), 1234.0)
    assert payer_region(revenue_text(record.normalized_description)) == "2 NORTHWIND BAKERS LLC"


_A3G_BOOK_IN = ("WIRE TYPE:BOOK IN DATE:540102 TIME:1200 ET TRN:20540102000012{n} SNDR REF:12345678 ORIG:{orig} "
                "ID:123456789012")


def test_a3g_refinement_bofa_s_book_in_wire_reads_its_originator():
    # A3-G refinement: WIRE TYPE BOOK IN is the WIRE TYPE WIRE IN layout: its ORIG is read, the SWIFT 50F prefix
    # stripped.
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one(_A3G_BOOK_IN.format(n=34, orig="1/NORTHWIND SUPPLY LLC"), 16000.0)
    assert payer_region(revenue_text(record.normalized_description)) == "NORTHWIND SUPPLY LLC"
    assert _tier(record) == ("counted_flagged", "wire_named_sender")
    held = _one(_A3G_BOOK_IN.format(n=34, orig="1/NORTHWIND SUPPLY LLC"), 16000.0, holder="NORTHWIND SUPPLY LLC")
    assert _tier(held) == ("excluded_pending_review", "holder_name")


@pytest.mark.parametrize("text", [
    "WIRE TYPE:BOOK IN DATE:540102 TIME:1200 ET TRN:2054010200001234 SNDR REF:12345678",
    "WIRE CREDIT REF123456 BOOK",
    # A layout that prints only the sending bank and its city after the reference names no sender.
    "WIRE CREDIT REF123456 SAMPLEBANK NYC 123456B12AB",
])
def test_a3g_refinement_a_bare_channel_word_is_no_named_sender(text):
    assert _tier(_one(text, 16000.0)) == ("excluded_pending_review", "wire_no_sender")


_A3G_PRODUCT = "BUSINESS ADVANTAGE RELATIONSHIP BANKING PREFERRED REWARDS"
#: A3-G review: a receiver name counts only when credits from two distinct originators print it.
_A3G_ORIGINATORS = ("FABRIKAM PAYMENTS", "SAMPLE MARKETS INC")
_A3G_RECEIVER = "{payer} DES:DEPOSIT ID:{n} INDN:{name} CO ID:1234567890 CCD"


def _a3g_receivers(name: str, count: int = 2) -> list[tuple[str, float]]:
    return [(_A3G_RECEIVER.format(payer=_A3G_ORIGINATORS[at % 2], n=at + 1, name=name), 10500.0 + at)
            for at in range(count)]


def test_a3g_refinement_the_holder_s_receiver_name_is_the_holder_when_the_account_name_is_a_product():
    rows = _records([
        *_a3g_receivers("NORTHWIND BUILDERS GROU"),
        (_A3G_BOOK_IN.format(n=34, orig="1/NORTHWIND BUILDERS GROUP"), 120000.0),
    ], holder=_A3G_PRODUCT)
    assert _tier(rows[2]) == ("excluded_pending_review", "holder_name")
    # The receiver name is the holder's, never a payer: the payer rows that print it keep their reading.
    assert rows[0].revenue_tier_reason != "holder_name"


def test_a3g_refinement_final_the_receiver_name_reads_wires_and_transfers_only():
    # A3-G refinement (final): read on a wire, a book transfer or a transfer or P2P row, where the holder moves its own
    # money; never on an ACH, card, processor or marketplace settlement (a platform prints the store's own name as its
    # payer) nor on a push rail.
    receivers = _a3g_receivers("NORTHWIND BUILDERS GROU")
    zelle = _records([*receivers, ("ZELLE PAYMENT FROM NORTHWIND BUILDERS GROUP CONF 1234567", 2500.0)],
                     holder=_A3G_PRODUCT)
    assert _tier(zelle[-1]) == ("excluded_pending_review", "holder_name")
    settlements = _records([
        *receivers,
        ("NORTHWIND BUILDERS GROUP DES:DEPOSIT ID:7 INDN:SAMPLE STORE 12 CO ID:1234567890 CCD", 900.0),
        ("NORTHWIND BUILDERS GROUP DES:DEPOSIT ID:8 INDN:SAMPLE STORE 12 CO ID:1234567890 CCD", 950.0),
        ("RTP CREDIT NORTHWIND BUILDERS GROUP 1234567", 800.0),
        # A3-G review: WIRE printed in an ACH entry makes no wire layout.
        ("NORTHWIND BUILDERS GROUP DES:WIRE PMT ID:9 INDN:SAMPLE STORE 12 CO ID:1234567890 CCD", 700.0),
    ], holder=_A3G_PRODUCT)
    assert {record.revenue_tier_reason for record in settlements[2:]}.isdisjoint({"holder_name"})


def test_a3g_re_review_one_platform_s_two_spellings_are_one_originator():
    # A3-G re-review: originators are compared by the payer's grouping word, so two spellings of one platform are one.
    rent = "{payer} DES:RENT ID:{n} INDN:JONATHAN SAMPLESON CO ID:1234567890 PPD"
    rows = _records([(rent.format(payer="SAMPLE RENT PAY", n=1), 1500.0),
                     (rent.format(payer="SAMPLE RENT PAYMENTS", n=2), 1500.0),
                     ("ZELLE PAYMENT FROM JONATHAN SAMPLESON CONF 1234567", 1500.0)], holder=_A3G_PRODUCT)
    assert _tier(rows[-1]) == ("counted_flagged", "p2p")


def test_a3g_review_a_receiver_name_one_platform_prints_is_no_holder_name():
    # A3-G review: a rent platform prints its tenant as the receiver: one originator only, so no holder's name.
    rent = "SAMPLE RENT PAY DES:RENT ID:{n} INDN:JONATHAN SAMPLESON CO ID:1234567890 PPD"
    rows = _records([(rent.format(n=1), 1500.0), (rent.format(n=2), 1500.0),
                     ("ZELLE PAYMENT FROM JONATHAN SAMPLESON CONF 1234567", 1500.0)], holder=_A3G_PRODUCT)
    assert _tier(rows[-1]) == ("counted_flagged", "p2p")


def test_a3g_review_a_row_an_earlier_rule_verified_keeps_its_verification():
    # A3-G review: the receiver name never demotes a row a sale-evidence rule verified (an invoice wire, §7.9).
    rows = _records([
        *_a3g_receivers("NORTHWIND BUILDERS GROU"),
        (_A3G_BOOK_IN.format(n=34, orig="NORTHWIND BUILDERS GROUP") + " PMT DET:INV 1234", 16000.0),
    ], holder=_A3G_PRODUCT)
    assert rows[-1].revenue_classification == "verified_revenue"


@pytest.mark.parametrize(("receivers", "holder"), [
    # One credit only.
    (("NORTHWIND BUILDERS GROU",), _A3G_PRODUCT),
    # A usable account name (a company form, or a person's name) is the holder's name: the receiver names are not read.
    (("NORTHWIND BUILDERS GROU", "NORTHWIND BUILDERS GROU"), "CONTOSO BAKERY LLC"),
    (("NORTHWIND BUILDERS GROU", "NORTHWIND BUILDERS GROU"), "JANE Q SAMPLE"),
    # A generic receiver value (a product or channel word, a bank, or fewer than two words or eight letters).
    (("BUSINESS CHECKING", "BUSINESS CHECKING"), _A3G_PRODUCT),
    (("NORTHWIND", "NORTHWIND"), _A3G_PRODUCT),
    (("NORTHWIND BUILDERS BANK", "NORTHWIND BUILDERS BANK"), _A3G_PRODUCT),
])
def test_a3g_refinement_a_receiver_name_needs_two_credits_a_real_name_and_an_unusable_account_name(receivers, holder):
    rows = _records([
        *[(_A3G_RECEIVER.format(payer=_A3G_ORIGINATORS[at % 2], n=at + 1, name=name), 10500.0 + at)
          for at, name in enumerate(receivers)],
        (_A3G_BOOK_IN.format(n=34, orig="1/NORTHWIND BUILDERS GROUP"), 120000.0),
        ("ZELLE PAYMENT FROM NORTHWIND BUILDERS BANK CONF 1234567", 1500.0),
    ], holder=holder)
    assert rows[-2].revenue_tier_reason != "holder_name"
    assert rows[-1].revenue_tier_reason != "holder_name"


def test_a3g_a_bank_s_ach_credit_is_no_wire_and_keeps_its_reading():
    assert _tier(_one("NORTHWIND BANK DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD", 2430.0))[1] != (
        "financing_named_payer")


def test_a3g_a_swift_50f_line_number_never_starts_the_originator():
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one(_A3_WIRE.format(n=1, orig="1/NORTHWIND SUPPLY LLC"), 24950.0)
    assert payer_region(revenue_text(record.normalized_description)) == "NORTHWIND SUPPLY LLC"
    # One sender, with and without the line number, is one sender: two wires verify by Q5.
    rows = _records([(_A3_WIRE.format(n=1, orig="1/NORTHWIND SUPPLY LLC"), 24950.0),
                     (_A3_WIRE.format(n=2, orig="NORTHWIND SUPPLY LLC"), 26950.0)])
    assert {record.revenue_match_method for record in rows} == {"repeat_wire_sender"}
    # A numbered company keeps its number.
    numbered = _one(_A3_WIRE.format(n=1, orig="1234567 ONTARIO INC"), 24950.0)
    assert payer_region(revenue_text(numbered.normalized_description)) == "1234567 ONTARIO INC"


@pytest.mark.parametrize(("orig", "holder"), [
    # A word-by-word prefix of the holder's name whose last word is cut: two whole words before the cut ...
    ("1/GLOBAL AMERICAN NORTHWIND", "GLOBAL AMERICAN NORTHWINDING INC"),
    ("GLOBAL AMERICAN NORTH", "GLOBAL AMERICAN NORTHWINDING INC"),
    # ... or twelve letters or more.
    ("CONTOSOBAKERYW", "CONTOSOBAKERYWORKS LLC"),
])
def test_a3g_a_sender_that_is_the_holder_s_cut_name_is_the_holder(orig, holder):
    assert _tier(_one(_A3_WIRE.format(n=1, orig=orig), 120000.0, holder=holder)) == (
        "excluded_pending_review", "holder_name")


@pytest.mark.parametrize(("orig", "holder"), [
    ("NORTH", "NORTHWIND BAKERY LLC"),
    ("FIRST CO", "FIRST CONTOSO BAKERY LLC"),
    ("GLOBAL NORTHWIND", "GLOBAL AMERICAN NORTHWINDING INC"),
])
def test_a3g_a_single_common_word_or_a_short_cut_never_names_the_holder(orig, holder):
    assert _tier(_one(_A3_WIRE.format(n=1, orig=orig), 16000.0, holder=holder))[1] != "holder_name"


@pytest.mark.parametrize("text", [
    "BOOK TRANSFER CREDIT B O JANE Q SAMPLE 1234 TRUST SAMPLEVILLE WA 12345 1234 US TRN 1234567890ES",
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE REVOCABLE TRUST"),
    _A3_WIRE.format(n=1, orig="SAMPLE FAMILY TRUST"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE TTEE"),
    _a3g_fedwire("JANE SAMPLE LIVING TR"),
    _a3g_fedwire("JOHN SAMPLE IRREVOCABLE TRUST"),
    "JOHN Q SAMPLE TRUST DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    # A sender read after the wire's label, before its digit cut.
    "INCOMING WIRE 20540102 SAMPLE 1234 FAMILY TRUST NOTPROVIDED",
    # A3-G review: the trust's beneficiary after FBO names no other sender.
    "INCOMING WIRE 20540102 SAMPLE 1234 FAMILY TRUST FBO JANE Q SAMPLE 12345678",
])
def test_a3g_a_personal_trust_s_credit_is_held_as_owner_money(text):
    # A3-G: money from a personal trust is far more often the owner's family money, an investment or a loan.
    assert _tier(_one(text, 75000.0)) == ("excluded_pending_review", "non_sale_purpose")


@pytest.mark.parametrize("text", [
    _A3_WIRE.format(n=1, orig="NORTHWIND TRUST COMPANY"),
    _a3g_fedwire("SAMPLE BANK AND TRUST"),
    _A3_WIRE.format(n=1, orig="NORTHWIND TRUST LLC"),
    _A3_WIRE.format(n=1, orig="CONTOSO TRUST"),
    _A3_WIRE.format(n=1, orig="SAMPLE LAW GROUP IOLTA TRUST ACCOUNT"),
    _A3_WIRE.format(n=1, orig="FABRIKAM TRUST ACCOUNT"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE"),
    # A bare TR is a trust only after a trust adjective ('LIVING TR'); a company's cut word is none ('... MOTOR TR').
    "Orig CO Name:Fabrikam Motor Tr Orig ID:1 Desc Date: CO Entry Descr:Ach Pmt Sec:CCD Trace#:1",
    # A person-to-person row prints the sending bank after the sender ('... NORTHWIND TRUST' is a bank's name).
    "ZELLE PAYMENT FROM JOHN SAMPLE NORTHWIND TRUST ID 1234567890",
])
def test_a3g_an_institutional_or_company_trust_or_a_person_is_no_personal_trust(text):
    assert _tier(_one(text, 7500.0))[1] != "non_sale_purpose"


@pytest.mark.parametrize("text", [
    # A3-G review (c): a bank's or a trust company's form after the trust word.
    _A3_WIRE.format(n=1, orig="NORTHWIND COUNTY TRUST NA"),
    _A3_WIRE.format(n=1, orig="NORTHWIND SAMPLE TRUST FSB"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE TRUST COMPANY"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE TRUST CO"),
    # (c): a lawyer's or a client trust account.
    _A3_WIRE.format(n=1, orig="JOHN SAMPLE ESQ IOTA TRUST"),
    _A3_WIRE.format(n=1, orig="JOHN SAMPLE ESQ IOLA TRUST"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE IOLTA TRUST"),
    # (b): a business, institutional or benefit word before the trust word, or a company form.
    "NORTHWIND REALTY TRUST DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    _A3_WIRE.format(n=1, orig="SAMPLE CARPENTERS HEALTH WELFARE TRUST"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE TRUST LLC"),
    # (a): the trust word does not end the sender's name.
    _A3_WIRE.format(n=1, orig="IN GOD WE TRUST ROOFING"),
    _A3_WIRE.format(n=1, orig="JOHN Q SAMPLE TRUST ACCOUNT"),
    # (a): a street named TRUST in a Fedwire sender's address.
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O JOHN SAMPLE 12 TRUST RD SAMPLEVILLE CA 12345 US REF SAMPLE NYC "
    "CTR BNF CONTOSO BAKERY LLC OBI 1234",
])
def test_a3g_review_a_personal_trust_is_a_person_s_name_ending_in_a_trust_form(text):
    assert _tier(_one(text, 7500.0))[1] != "non_sale_purpose"


_A3G_TRUST_ADDRESS_NEGATIVES = (
    "JOHN Q SAMPLE TRUST ACCOUNT", "JOHN Q SAMPLE TRUST SERVICES", "JOHN Q SAMPLE TRUST DEPT",
    "JOHN Q SAMPLE TRUST IOLTA", "JOHN Q SAMPLE TRUST LLC", "NORTHWIND SAMPLE TRUST ROOFING",
)


@pytest.mark.parametrize("text", [
    *[_a3g_fedwire(orig, place="SAMPLEVILLE WA 12345 US") for orig in _A3G_TRUST_ADDRESS_NEGATIVES],
    *[f"BOOK TRANSFER CREDIT B O {orig} SAMPLEVILLE WA 12345 US TRN 1234567890ES" for orig in _A3G_TRUST_ADDRESS_NEGATIVES],
])
def test_a3g_re_review_a_trust_s_address_holds_only_place_words(text):
    # A3-G re-review: after the trust form, a wire's address may hold only city words, a state, a ZIP and a country.
    assert _tier(_one(text, 75000.0))[1] != "non_sale_purpose"


@pytest.mark.parametrize("place", ["DENVER CO 80202 US", "LAS VEGAS NV 89101 US", "SAMPLEVILLE CA 12345 US"])
def test_a3g_re_review_an_address_s_state_is_never_a_company_form(place):
    # A3-G re-review: CO (Colorado) and NV (Nevada) at the end of a Fedwire city and state are the address's state.
    from analysis.descriptor.lexical import bank_by_form

    assert _tier(_one(_a3g_fedwire("NORTHWIND BANK", place=place), 257000.0)) == (
        "excluded_pending_review", "financing_named_payer")
    # A3-G re-review 2: the state ends a Fedwire B/O city and state region, or a ZIP or a country code follows it.
    assert bank_by_form("SAMPLE CREDIT UNION BOULDER CO", city_state_end=True)
    assert bank_by_form("NORTHWIND BANK LAS VEGAS NV", city_state_end=True)
    assert bank_by_form("SAMPLE CREDIT UNION BOULDER CO", " 12345 US REF 1234")
    assert bank_by_form("NORTHWIND BANK LAS VEGAS NV", " US TRN 1234567890ES")


def test_a3g_re_review_a_bank_with_a_state_address_relays_its_customer():
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    text = ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHWIND BANK DENVER CO ORIGINATOR FABRIKAM TRADING "
            "LIMITED REF SAMPLE NYC CTR BNF CONTOSO BAKERY LLC")
    record = _one(text, 13000.0)
    assert payer_region(revenue_text(record.normalized_description)) == "FABRIKAM TRADING LIMITED"
    assert _tier(record) == ("counted_flagged", "wire_named_sender")


@pytest.mark.parametrize("text", [
    # A Fedwire B/O field: the credit union's state before its ZIP, and a state that ends the city and state region.
    _a3g_fedwire("SAMPLE CREDIT UNION", place="BOULDER CO 12345 US"),
    _a3g_fedwire("NORTHWIND BANK", place="LAS VEGAS NV"),
    # Any other layout: a ZIP or a country code after the state.
    "BOOK TRANSFER CREDIT B O NORTHWIND BANK DENVER CO 12345 US TRN 1234567890JS",
])
def test_a3g_re_review_2_a_state_before_its_zip_or_ending_a_fedwire_city_and_state_is_the_address_s(text):
    assert _tier(_one(text, 257000.0)) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("text", [
    # A3-G re-review 2: a layout that prints no address, or a CO or NV with no ZIP or country after it outside a
    # Fedwire B/O city and state: the word is a company form, so the name that holds BANK is a company's.
    _A3G_BOFA.format(n=1, orig="LEFT BANK TRADING CO", bank="SAMPLE BANK"),
    "BOOK TRANSFER CREDIT B O WEST BANK OIL CO REF 1234 TRN 1234567890JS",
    _A3G_BOFA.format(n=1, orig="BANK STREET HOLDINGS NV", bank="SAMPLE BANK"),
    # ... and an originator that prints a company form is never its sending bank.
    _A3G_BOFA.format(n=1, orig="NORTHWIND SUPPLY CO", bank="NORTHWIND SUPPLY"),
])
def test_a3g_re_review_2_a_trailing_co_or_nv_with_no_address_is_a_company_form(text):
    from analysis.descriptor.lexical import bank_by_form

    assert _tier(_one(text, 9000.0)) == ("counted_flagged", "wire_named_sender")
    assert not bank_by_form("LEFT BANK TRADING CO")
    assert not bank_by_form("BANK STREET HOLDINGS NV")


@pytest.mark.parametrize("orig", [
    # A3-G re-review 2: custody and administration words are no place words.
    "JOHN Q SAMPLE TRUST CUSTODY", "JOHN Q SAMPLE TRUST CUSTODIAN", "JOHN Q SAMPLE TRUST ADMINISTRATOR",
    "JOHN Q SAMPLE TRUST ADMINISTRATORS", "NORTHWIND SAMPLE TRUST LANDSCAPE",
    # At most three address words before the state, whatever the words.
    "JOHN Q SAMPLE TRUST GARDEN CARE PROS",
])
def test_a3g_re_review_2_a_trust_s_address_is_at_most_three_place_words(orig):
    assert _tier(_one(_a3g_fedwire(orig, place="SAMPLEVILLE WA 12345 US"), 75000.0))[1] != "non_sale_purpose"


@pytest.mark.parametrize(("orig", "place"), [
    ("JOHN Q SAMPLE FAMILY TRUST", "SAMPLE LAKE CITY UT 12345 US"),
    # Only the address's own words count: never the agreement words, a PO box, a number, a street type or an initial.
    ("THE JANE SAMPLE TRUST U/A DTD PO BOX 123", "SAMPLEVILLE WA 12345-6789 US"),
    ("JOHN Q SAMPLE TTEE JANE D SAMPLESON9TH AVE", "SAMPLEVILLE WA 12345-6789 USA"),
    ("JOHN Q SAMPLE REVOCABLE TRUST UAD US/SAMPLE HARBOR", "WA 12345-6789"),
])
def test_a3g_re_review_2_a_city_of_three_words_or_fewer_keeps_a_personal_trust(orig, place):
    assert _tier(_one(_a3g_fedwire(orig, place=place), 75000.0)) == ("excluded_pending_review", "non_sale_purpose")


_A3G_DOTTED_FORMS = (
    ("JOHN Q SAMPLE TRUST L.L.C.", "SAMPLEVILLE WA 12345 US"),
    ("JOHN Q SAMPLE TRUST L.P.", "SAMPLEVILLE WA 12345 US"),
    ("JOHN Q SAMPLE TRUST P.A.", "SAMPLEVILLE FL 12345 US"),
    ("JOHN Q SAMPLE TRUST P.C. 123 MAIN ST", "SAMPLEVILLE WA 12345 US"),
)


@pytest.mark.parametrize("text", [
    *[_a3g_fedwire(orig, place=place) for orig, place in _A3G_DOTTED_FORMS],
    *[f"BOOK TRANSFER CREDIT B O {orig} {place} TRN 1234567890ES" for orig, place in _A3G_DOTTED_FORMS],
])
def test_a3g_re_review_3_a_dotted_company_form_in_a_trust_s_address_is_a_company_form(text):
    # A3-G re-review 3: two or more single letters in a row that join into a company form (L L C, L P, P A, P C).
    assert _tier(_one(text, 75000.0))[1] != "non_sale_purpose"


@pytest.mark.parametrize("orig", [
    # Initials that join into no company form keep their skip: the agreement's U A, a trustee's middle initial.
    "JOHN Q SAMPLE TRUST U/A DTD", "JOHN Q SAMPLE TTEE JANE D SAMPLESON",
])
def test_a3g_re_review_3_initials_that_spell_no_company_form_keep_a_personal_trust(orig):
    assert _tier(_one(_a3g_fedwire(orig, place="SAMPLEVILLE WA 12345 US"), 75000.0)) == (
        "excluded_pending_review", "non_sale_purpose")


@pytest.mark.parametrize("phrase", ["ORG TO BNF", "ORIGINATOR TO BENEFICIARY"])
def test_a3g_re_review_the_originator_label_skips_the_originator_to_beneficiary_phrase(phrase):
    # A3-G re-review: _WIRE_ORIGINATOR_LABEL takes the same TO BNF / TO BENEFICIARY guards as the relay label.
    from analysis.descriptor.payer import payer_region
    from analysis.descriptor.lexical import revenue_text

    record = _one(f"WIRE TRANSFER INCOMING NORTHWIND SUPPLY LLC {phrase} INFO 1234", 9000.0)
    assert payer_region(revenue_text(record.normalized_description)) == "NORTHWIND SUPPLY LLC"


# --- A3-H (the Verified strata's misses at s56c) ---------------------------------------------------------------------

_A3H_BOFA_WIRE = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK "
                  "ID:1 PMT DET:AB{n} SCHEDULE 10{n}")
_A3H_BOFA_ACH = "{payer} DES:{entry} ID:1234567 INDN:CONTOSO TRUCKING INC CO ID:1234567890 CCD"


def _a3h_factoring_aliases():
    from analysis.classification_registry import FACTORING_PAYOUT_PAYERS

    aliases = [alias for entity_aliases in FACTORING_PAYOUT_PAYERS.values() for alias in entity_aliases]
    assert aliases, "FACTORING_PAYOUT_PAYERS holds no alias"
    return aliases


def test_a3h_a_freight_factor_s_wires_and_ach_payouts_are_counted_as_factoring_payouts():
    # A3-H: a factoring payer the registry names (FACTORING_PAYOUT_PAYERS, never the lender ledger) pays the carrier's
    # own invoices: counted and flagged as a factoring payout, never verified by a repeat, on a wire or an ACH entry.
    for alias in _a3h_factoring_aliases():
        wires = _records([(_A3H_BOFA_WIRE.format(n=n, orig=f"{alias} LLC"), 5150.0 + 330.0 * n) for n in (1, 2, 3)])
        achs = _records([(_A3H_BOFA_ACH.format(payer=alias, entry="PAYMENT"), 5150.0 + 330.0 * n) for n in (1, 2)])
        for record in (*wires, *achs):
            assert record.revenue_classification == "unverified_deposit"
            assert _tier(record) == ("counted_flagged", "factoring_payout")
            # Q5 and Q6 never verify it, so no verification is overruled (A3-H review: factoring_payout_payer).
            assert record.revenue_match_method == "unidentified_posted_credit"


def test_a3h_the_factoring_payout_table_never_reads_a_debit_or_the_payee_groups():
    # A3-H: the table is read by the true-revenue pass alone: a debit to the payer, and the credit's own group, keep
    # their reading (no ledger entity, so no flag or lender reading moves).
    alias = _a3h_factoring_aliases()[0]
    debit, credit = _records([(f"{alias} DES:FUEL ID:1234567 INDN:CONTOSO TRUCKING INC CO ID:1234567890 CCD", -610.0),
                              (_A3H_BOFA_ACH.format(payer=alias, entry="PAYMENT"), 5150.0)])
    assert debit.classification not in {"factoring", "confirmed_lender", "potential_lender"}
    assert debit.revenue_tier is None
    assert credit.classification == "other"


def test_a3h_a_numbered_schedule_alone_names_no_factor():
    # A3-H: a generic SCHEDULE <n> purpose is out of scope (construction pay applications print schedules too): an
    # unlisted company that wires twice with a schedule reference still verifies (Q5).
    rows = _records([(_A3H_BOFA_WIRE.format(n=n, orig="NORTHWIND SOLUTIONS LLC"), 5150.0 + 330.0 * n) for n in (1, 2)])
    assert rows[-1].revenue_match_method == "repeat_wire_sender"


_A3H_CHASE = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:{entry}SEC:PPD "
              "TRACE#:123456789012345 EED:540102 IND ID: IND NAME:NORTHWIND INS AGENCY TRN: 1234567890TC")
_A3H_AGENCY = "{payer} DES:{entry} ID:1234567 INDN:NORTHWIND INS AGENCY CO ID:1234567890 PPD"


@pytest.mark.parametrize("text", [
    # A3-H: a healthcare, insurer or health-plan payer's premium-coded entry (PREM, PREMIUM, the Chase layout's glued
    # PREMSEC) is a commission or a premium refund: counted and flagged with the named payer, never verified by Q6c.
    _A3H_CHASE.format(payer="CIGNA", entry="CIGNA PREM"),
    _A3H_AGENCY.format(payer="HUMANA", entry="PREM"),
    _A3H_AGENCY.format(payer="HUMANA", entry="PREMIUM"),
])
def test_a3h_an_insurer_s_premium_coded_credit_is_no_claim_payment(text):
    record = _one(text, 640.0)
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == ("counted_flagged", "named_payer_purpose_refused")


def test_i26_an_insurer_spelled_ins_is_held_before_its_premium_code_is_read():
    # Audit I26 (by Q6 of 2026-09-28 and the underwriter's Q2 (2026-10-02) option's "a one-off claim ... stays out";
    # R2-OW07): an insurer whose name prints only the INS abbreviation is held as insurer_named_payer, as the same
    # credit spelled INSURANCE is, before Q6c's premium refusal is read (it was counted and refused until R2-OW07).
    for payer in ("NORTHWIND INS CO", "NORTHWIND INSURANCE CO"):
        record = _one(_A3H_AGENCY.format(payer=payer, entry="PREM"), 640.0)
        assert record.revenue_classification == "unverified_deposit"
        assert _tier(record) == ("excluded_pending_review", "insurer_named_payer")


@pytest.mark.parametrize(("text", "method"), [
    # A claim or plain payment still verifies, and an insurer's commission entry keeps its reading.
    (_A3H_AGENCY.format(payer="HUMANA", entry="PAYMENT"), "public_or_healthcare_payer"),
    (_A3H_AGENCY.format(payer="HUMANA", entry="COMM"), "public_or_healthcare_payer"),
    (_A3H_AGENCY.format(payer="HUMANA", entry="PREMIER"), "public_or_healthcare_payer"),
    # A government payer's PREM form is reported, never changed.
    (_A3H_AGENCY.format(payer="SAMPLE COUNTY", entry="PREM"), "public_or_healthcare_payer"),
])
def test_a3h_a_claim_a_commission_and_a_government_payer_keep_their_verification(text, method):
    assert _one(text, 640.0).revenue_match_method == method


def test_a3h_a_glued_premium_code_reads_where_no_sec_code_splits_it():
    # The revenue text splits a glued SEC code before its SEC label ('PREMSEC PPD'); a glued PREMSEC printed elsewhere
    # is read as the premium code too.
    from analysis.true_revenue.payroll import _premium_coded

    assert _premium_coded("CIGNA DES PREMSEC ID 1234567", "CIGNA")
    assert not _premium_coded("CIGNA DES PREMIER ID 1234567", "CIGNA")


def test_a3h_a_premium_refund_stays_non_revenue():
    # Non-revenue rules run first: the reversal rule's REFUND takes a premium refund out before any tier.
    assert _one(_A3H_AGENCY.format(payer="HUMANA", entry="PREM REFUND"), 640.0).revenue_classification == "non_revenue"


_A3H_WIRE_PURPOSE = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK "
                     "ID:1 PMT DET:{purpose}")


@pytest.mark.parametrize("shape", ["invoice_wire", "ach_remittance"])
def test_a3h_review_a_factor_is_never_verified_by_any_path(shape):
    # A3-H review: a factor's payout is counted and flagged whichever earlier rule verified it (an invoice-purpose wire,
    # an accounts-payable remittance descriptor).
    alias = _a3h_factoring_aliases()[0]
    text = (
        _A3H_WIRE_PURPOSE.format(n=1, orig=f"{alias} LLC", purpose="INV 1234") if shape == "invoice_wire"
        else _A3H_BOFA_ACH.format(payer=alias, entry="VENDOR PAY")
    )
    record = _one(text, 5480.0, holder="CONTOSO TRUCKING INC")
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == ("counted_flagged", "factoring_payout")


def test_a3h_review_a_factor_s_alias_before_a_company_form_is_the_factor():
    alias = _a3h_factoring_aliases()[0]
    record = _one(_A3H_BOFA_ACH.format(payer=f"{alias} LLC", entry="PAYMENT"), 5480.0, holder="CONTOSO TRUCKING INC")
    assert _tier(record) == ("counted_flagged", "factoring_payout")


@pytest.mark.parametrize("shape", ["longer_ach_name", "longer_wire_name", "cited_in_purpose"])
def test_a3h_review_the_alias_is_read_only_as_the_payer(shape):
    # A3-H review: the alias names the factor only as the whole payer region (the ACH originator or the wire sender),
    # a company form aside; a longer name that starts with it, or another payer's purpose citing it, is another payer.
    alias = _a3h_factoring_aliases()[0]
    if shape == "longer_ach_name":
        rows = [(_A3H_BOFA_ACH.format(payer=f"{alias} FOR PETS LLC", entry="PAYMENT"), 610.0)]
    elif shape == "longer_wire_name":
        rows = [(_A3H_WIRE_PURPOSE.format(n=n, orig=f"{alias} CLEANING LLC", purpose=f"12{n}"), 5150.0 + n)
                for n in (1, 2)]
    else:
        rows = [(_A3H_WIRE_PURPOSE.format(n=n, orig="NORTHWIND FREIGHT LLC", purpose=f"REF {alias} {n}"), 5150.0 + n)
                for n in (1, 2)]
    assert _tier(_records(rows, holder="CONTOSO TRUCKING INC")[-1])[1] != "factoring_payout"


@pytest.mark.parametrize("payer", ["MEDICARE", "STATE OF SAMPLE MEDICAID", "TRICARE"])
def test_a3h_review_a_public_health_payer_s_premium_form_keeps_its_reading(payer):
    # A3-H review: a government payer (Medicare, Medicaid, TRICARE, VA, a state, county or federal public payer) keeps
    # its reading whatever its entry prints.
    assert _one(_A3H_AGENCY.format(payer=payer, entry="PREM"), 640.0).revenue_match_method == (
        "public_or_healthcare_payer")


def test_a3h_review_a_commission_word_keeps_the_reading_beside_a_premium_code():
    assert _one(_A3H_AGENCY.format(payer="HUMANA", entry="PREM COMM"), 640.0).revenue_match_method == (
        "public_or_healthcare_payer")


@pytest.mark.parametrize(("text", "expected"), [
    # A3-H review: the premium code is read only in the entry field (DES, CO ENTRY DESCR); a layout that prints none
    # keeps its reading: a health plan's named payer stays unlabelled, a healthcare payer's PREMIUM stays held. Audit
    # I26 (R2-OW07): an insurer spelled INS is held as insurer_named_payer, whatever its layout (it stayed unlabelled
    # until R2-OW07).
    ("CIGNA PREM 1234567 CUSTOMER ID N1234567", ("counted_flagged", "named_payer_unlabelled")),
    ("NORTHWIND INS CO PREM 1234567 CUSTOMER ID N1234567", ("excluded_pending_review", "insurer_named_payer")),
    ("HUMANA PREMIUM 1234567 CUSTOMER ID N1234567", ("excluded_pending_review", "non_sale_purpose")),
])
def test_a3h_review_the_premium_code_is_read_only_in_the_entry_field(text, expected):
    assert _tier(_one(text, 640.0)) == expected


# A3-H review 2: the factor's printed variants.
_A3H_IND = "INDN:CONTOSO TRUCKING INC CO ID:1234567890 CCD"


def _a3h_factor(text):
    return _tier(_one(text, 5480.0, holder="CONTOSO TRUCKING INC"))


@pytest.mark.parametrize("layout", ["fedwire", "chase_book_transfer"])
def test_a3h_review_2_a_factor_is_read_before_its_b_o_address(layout):
    # A3-H review 2: the B/O field prints the sender's city, state, ZIP and country after its name (and its company
    # form): the address is dropped before the whole-name test, so the invoice-purpose wire is the factor's payout.
    alias = _a3h_factoring_aliases()[0]
    text = (
        f"FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O {alias} LLC SAMPLEVILLE OK 12345 US REF SAMPLE NYC CTR "
        "BNF CONTOSO TRUCKING INC OBI INV 1234" if layout == "fedwire"
        else f"BOOK TRANSFER CREDIT B O {alias} LLC SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS"
    )
    assert _a3h_factor(text) == ("counted_flagged", "factoring_payout")


@pytest.mark.parametrize("tail", [
    # (a) a DBA tail, (b) a glued company form, (c) an entry word, a date or a number that falls into the region.
    " LLC DBA NORTHWIND FINANCIAL DES:PAYMENT ID:1234567 " + _A3H_IND,
    "LLC DES:PAYMENT ID:1234567 " + _A3H_IND,
    " LLC PAYMENT 240115 1234567 CONTOSO TRUCKING INC",
])
def test_a3h_review_2_a_factor_s_dba_glued_form_and_entry_words_are_the_factor(tail):
    for alias in _a3h_factoring_aliases():
        assert _a3h_factor(alias + tail) == ("counted_flagged", "factoring_payout")


@pytest.mark.parametrize("text", [
    # A longer name that starts with the alias stays another payer, on every spelling and before an address too.
    "{alias} FOR PETS LLC DES:PAYMENT ID:1234567 " + _A3H_IND,
    "BOOK TRANSFER CREDIT B O {alias} FOR PETS LLC SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS",
    "{alias} CLEANING LLC PAYMENT 240115 1234567 CONTOSO TRUCKING INC",
    # A B/O address holds only place words (a trade word is no place), at most three of its own.
    "BOOK TRANSFER CREDIT B O {alias} CLEANING SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS",
    "BOOK TRANSFER CREDIT B O {alias} NORTHWIND GARDEN CARE SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS",
])
def test_a3h_review_2_a_longer_name_that_starts_with_the_alias_is_another_payer(text):
    for alias in _a3h_factoring_aliases():
        assert _a3h_factor(text.format(alias=alias))[1] != "factoring_payout"


def test_a3h_review_2_an_apostrophe_spelled_as_a_spaced_s_has_its_run_together_spelling():
    # A3-H review 2: the entity prints its apostrophe both ways, spaced ('<X> S <Y>') and dropped ('<X>S <Y>').
    from analysis.classification_registry import FACTORING_PAYOUT_PAYERS

    for aliases in FACTORING_PAYOUT_PAYERS.values():
        for alias in aliases:
            if " S " in alias:
                assert alias.replace(" S ", "S ", 1) in aliases


# ---------------------------------------------------------------------------------------------------------------------
# The final whole-branch review's fix wave (2026-09-30): fabricated rows only.
# ---------------------------------------------------------------------------------------------------------------------
_FW_BOFA = "{payer} DES:PAYMENT ID:{n} INDN:{holder} CO ID:1234567890 {sec}"
_FW_CHASE = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENT SEC:{sec} TRACE#:1234 "
             "EED:540302 IND ID:{n} IND NAME:{holder} TRN: 1234TC")


def _fw_method(record):
    return record.revenue_classification, record.revenue_match_method


@pytest.mark.parametrize("layout", [_FW_BOFA, _FW_CHASE])
def test_a_web_named_holder_never_makes_an_ach_payer_a_consumer_entry(layout):
    # Final review I1: the PPD/WEB test reads the SEC code's own slot, never the receiver field (the holder's name).
    holder = "CONTOSO WEB STUDIO LLC"
    one = _one(layout.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=holder, sec="CCD"), 2345.0, holder=holder)
    assert _fw_method(one) == ("verified_revenue", "named_payer_company_form")
    twice = _records([(layout.format(payer="NORTHWIND SUPPLY", n=n, holder=holder, sec="CCD"), 2345.0 + n)
                      for n in (1, 2)], holder=holder)
    assert {_fw_method(record) for record in twice} == {("verified_revenue", "named_payer_repeats")}


@pytest.mark.parametrize("layout", [_FW_BOFA, _FW_CHASE])
def test_a_web_named_payer_is_no_consumer_entry(layout):
    # Final review I1: nor is the payer's own name read as an SEC code.
    record = _one(layout.format(payer="NORTHWIND WEB DESIGN LLC", n=1, holder=HOLDER, sec="CCD"), 2345.0)
    assert _fw_method(record) == ("verified_revenue", "named_payer_company_form")


@pytest.mark.parametrize("text", [
    _FW_BOFA.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=HOLDER, sec="PPD"),
    _FW_BOFA.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=HOLDER, sec="WEB"),
    _FW_BOFA.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=HOLDER, sec="PPD PMT INFO:INV 1234"),
    _FW_CHASE.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=HOLDER, sec="PPD"),
    _FW_CHASE.format(payer="NORTHWIND SUPPLY LLC", n=1, holder=HOLDER, sec="WEB"),
    "ORIG CO NAME:NORTHWIND SUPPLY LLC ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENT PPD TRACE#:1234",
    "NORTHWIND SUPPLY LLC EFT PAYMENT 540302 WEB ID:1234567890",
    "FABRIKAM INC DES:PAYMENT ID:1 PPD",
])
def test_a_ppd_or_web_entry_in_its_sec_slot_stays_a_consumer_entry(text):
    # Final review I1: the code in its slot (Chase's SEC <code> or <code> before TRACE or ID, the code Bank of America
    # prints after the company id or at the row's end) still refuses the company-form verification.
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")


def test_ppd_repeats_in_their_sec_slot_never_verify_by_repetition():
    rows = [(_FW_BOFA.format(payer="NORTHWIND SUPPLY", n=n, holder=HOLDER, sec="PPD"), 2345.0 + n) for n in (1, 2)]
    assert {_tier(record) for record in _records(rows)} == {("counted_flagged", "named_payer_one_off")}


def test_recv_name_is_a_receiver_field_so_the_holder_never_names_an_operating_source():
    # Final review I2: every receiver vocabulary is built from one tuple, RECV NAME included: the holder's name in a
    # RECV NAME field ('SQUARE ONE BAKERY') never names Square, so nothing verifies by Square's recurrence.
    holder = "SQUARE ONE BAKERY LLC"
    rows = [(f"NORTHWIND PAYMENTS DES:DEPOSIT ID:{n} RECV NAME SQUARE ONE BAKERY CO ID:1234567890 CCD", 1200.0 + n)
            for n in range(3)]
    records = _records(rows, holder=holder)
    assert {record.revenue_canonical_entity for record in records} == {None}
    assert "recurring_operating_source" not in {record.revenue_match_method for record in records}
    from analysis.descriptor import rails
    from analysis.descriptor import lexical
    from analysis.description_text import RECEIVER_FIELD_LABELS, RECEIVER_NAME_LABELS

    assert "RECV NAME" in RECEIVER_NAME_LABELS and set(RECEIVER_NAME_LABELS) <= set(RECEIVER_FIELD_LABELS)
    text = "NORTHWIND PAYMENTS DES DEPOSIT ID 1 RECV NAME SQUARE ONE BAKERY CO ID 1234567890 CCD"
    assert lexical._before_receiver(text) == "NORTHWIND PAYMENTS DES DEPOSIT ID 1"
    assert "SQUARE" not in rails._without_receiver_value(text)


_FW_ACH = "{payer} DES:PAYMENT ID:1234 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD"


@pytest.mark.parametrize("payer", [
    "ANTHEM ROOFING", "WPS INDUSTRIES", "SAMPLE ANTHEM ROOFING", "OPTUM ROOFING", "CIGNA CLEANING", "AETNA LANDSCAPE",
    "ZELIS TRUCKING", "ANTHEM ROOFING HEALTH", "NORTHWIND UHC", "VPAY SOLUTIONS SAMPLE",
])
def test_a_short_healthcare_alias_is_read_only_as_the_whole_payer_name(payer):
    # Final review I3: WPS, UHC, ANTHEM, VPAY and every other alias of five letters or fewer name a healthcare payer
    # only as the whole payer name (a company form or a health-plan word may follow), never inside a business name.
    from analysis.true_revenue.public_payers import healthcare_payer

    assert not healthcare_payer(payer)
    assert _one(_FW_ACH.format(payer=payer), 2345.0).revenue_match_method != "public_or_healthcare_payer"


@pytest.mark.parametrize("payer", [
    "WPS", "WPS HEALTH SOLUTIONS", "WPS HEALTH INSURANCE", "UHC", "UHC PLAN OF THE SAMPLE VALLEY", "UHC COMMUNITY PLAN",
    "UHC BENEFITS", "ANTHEM BLUE CROSS", "ANTHEM INS COMPANIES INC", "ANTHEM HEALTH PLANS", "ANTHEM INC", "VPAY",
    "VPAY CLAIMS", "AETNA", "AETNA LIFE INS", "AETNA HEALTH INC", "CIGNA", "CIGNA HLTH LIFE", "CIGNA HEALTHCARE",
    "OPTUM", "OPTUM VA CCN", "ZELIS HEALTHCARE", "HCCLAIMPMT UHC COMMUNITY PLAN", "ANTHEM BCBS", "ANTHEM BCBSGA",
])
def test_a_short_healthcare_alias_with_its_plan_words_is_still_a_healthcare_payer(payer):
    from analysis.true_revenue.public_payers import healthcare_payer

    assert healthcare_payer(payer)


@pytest.mark.parametrize("payer", ["WPS", "WPS HEALTH SOLUTIONS", "UHC COMMUNITY PLAN", "ANTHEM BLUE CROSS", "VPAY",
                                   "AETNA", "OPTUM VA CCN"])
def test_a_whole_name_short_healthcare_alias_still_verifies_by_q6c(payer):
    assert _fw_method(_one(_FW_ACH.format(payer=payer), 2345.0)) == ("verified_revenue", "public_or_healthcare_payer")


_FW_STORE = "DOORDASH INC DES:{entry} ID:ST-A1B2C{n} INDN:SAMPLE {word} GROUP LLC CO ID:1234567890 CCD"


@pytest.mark.parametrize(("word", "entry"), [
    ("CAPITAL", "CAPITAL"), ("LENDING", "LENDING"), ("FUNDING", "FUNDING"), ("CAPITAL", "CAPITAL ADVANCE"),
    ("CAPITAL", "CAPITAL PAYMENT"), ("ADVANCE", "ADVANCE"),
])
def test_a_store_name_platform_s_financing_entry_never_takes_the_holder_s_word_exemption(word, entry):
    # Final review I4: a veto word that is the whole entry field, or forms it alone with generic words, is the
    # platform's own financing wording, never the holder's store name: the credit is held as financing, as it is for
    # a holder whose name lacks the word, while the holder's genuine store payouts still verify by recurrence.
    holder = f"SAMPLE {word} GROUP LLC"
    rows = [(_FW_STORE.format(entry=f"SAMPLE {word[:6]}", n=n, word=word), 1200.0 + n) for n in range(3)]
    rows.append((_FW_STORE.format(entry=entry, n=9, word=word), 25000.0))
    records = _records(rows, holder=holder)
    assert {record.revenue_match_method for record in records[:3]} == {"recurring_operating_source"}
    assert _tier(records[3]) == ("excluded_pending_review", "financing_named_payer")
    neutral = _records([(text.replace(f"SAMPLE {word} GROUP", "SAMPLE BAKERY"), amount) for text, amount in rows],
                       holder="SAMPLE BAKERY LLC")
    assert _tier(neutral[3]) == _tier(records[3])


@pytest.mark.parametrize("entry", ["NORTHWIND AND CAPITA", "N AND S CAPITA", "SAMPLE CAPITAL GRILL"])
def test_a_store_name_that_holds_the_holder_s_veto_word_still_verifies(entry):
    rows = [(f"DOORDASH INC DES:{entry} ID:ST-A1B2C{n} INDN:NORTHWIND CAPITAL GRILL LLC CO ID:1234567890 CCD",
             1200.0 + n) for n in range(3)]
    records = _records(rows, holder="NORTHWIND CAPITAL GRILL LLC")
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}


def test_a_no_entry_field_store_payout_that_prints_only_a_veto_word_is_held():
    # BMO prints no entry field ('DIRECT DEPOSIT DOORDASH <store> MSP/DIV'): the row itself is the store's field.
    rows = [(f"DIRECT DEPOSIT DOORDASH CAPITAL MSP/DIV {n}", 25000.0 + n) for n in range(3)]
    records = _records(rows, holder="SAMPLE CAPITAL GROUP LLC")
    assert "verified_revenue" not in {record.revenue_classification for record in records}


def test_q7_reads_the_strong_non_revenue_words_without_the_holder_s_receiver_name():
    # Final review M9 (§20): Q7 reads the strong non-revenue patterns on the row without the receiver field's value,
    # so a holder named '... LOAN ...' never stops a listed lender's dealer funding (a declared move out of
    # non_revenue: the whole-row read would decide it non_revenue).
    holder = "NORTHWIND LOAN CENTER LLC"
    record = _one(f"CU DIRECT DES:DEALER PMT ID:1 INDN:{holder} CO ID:1234567890 CCD", 25000.0, holder=holder)
    assert _fw_method(record) == ("verified_revenue", "auto_lender_dealer_funding")


def test_q7_reads_an_insurer_glued_to_its_claim_entry_as_step_5_does():
    # Final review M9: Q7's insurer check reads step 5's lookup text, a glued HCCLAIMPMT split from the name before it.
    glued = _one("WESTLAKE FINANCIAL DES:DEALER PMT ID:1 INDN:SAMPLE MOTORS LLC CO ID:1234567890 CCD PMT "
                 "INFO:STATE FARMHCCLAIMPMT 1234", 25000.0, holder="SAMPLE MOTORS LLC")
    assert glued.revenue_match_method != "auto_lender_dealer_funding"
    plain = _one("WESTLAKE FINANCIAL DES:DEALER PMT ID:1 INDN:SAMPLE MOTORS LLC CO ID:1234567890 CCD", 25000.0,
                 holder="SAMPLE MOTORS LLC")
    assert plain.revenue_match_method == "auto_lender_dealer_funding"


@pytest.mark.parametrize("text", [
    "BOOK TRANSFER CREDIT B O {alias} FOR PETS SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS",
    "FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O {alias} FOR PETS SAMPLEVILLE OK 12345 US REF SAMPLE NYC CTR "
    "BNF CONTOSO TRUCKING INC OBI INV 1234",
    "BOOK TRANSFER CREDIT B O {alias} OF THE SAMPLE OK 12345 US REF INV 1234 TRN 1234567890JS",
    "BOOK TRANSFER CREDIT B O {alias} AND PETS OK 12345 US REF INV 1234 TRN 1234567890JS",
])
def test_a_connector_word_after_a_factor_s_alias_is_no_address(text):
    # [A3H-m1]: FOR, OF, AND and THE join a longer name ('<alias> FOR PETS'), never an address's place words.
    for alias in _a3h_factoring_aliases():
        assert _a3h_factor(text.format(alias=alias))[1] != "factoring_payout"


def test_a_factor_s_plain_b_o_address_is_still_the_factor():
    for alias in _a3h_factoring_aliases():
        text = f"BOOK TRANSFER CREDIT B O {alias} SAMPLEVILLE OK 12345 US REF INV 1234 TRN 1234567890JS"
        assert _a3h_factor(text) == ("counted_flagged", "factoring_payout")


@pytest.mark.parametrize("payer", ["ANTHEM ROOFING", "WPS INDUSTRIES"])
def test_a_business_named_with_a_short_healthcare_alias_is_a_one_off_payer(payer):
    # The reviewer's probe: the control NORTHWIND ROOFING stays named_payer_one_off, and so do these now.
    assert _tier(_one(_FW_ACH.format(payer=payer), 2345.0)) == ("counted_flagged", "named_payer_one_off")


# ---------------------------------------------------------------------------------------------------------------------
# The final review's re-review of the fix wave (2026-09-30): I4-R, N6 and N1. Fabricated rows only.
# ---------------------------------------------------------------------------------------------------------------------
_RR_HOLDER = "SAMPLE CAPITAL LENDING FUNDING LLC"
_RR_STORE = "DOORDASH INC DES:{entry} ID:{n} INDN:{holder} CO ID:1234567890 CCD"


@pytest.mark.parametrize("entry", ["CAPITAL DISB", "CAPITAL DISBURSE", "CAPITAL OFFER", "CAPITAL XFER",
                                   "LENDING DAILY"])
def test_a_veto_word_that_leads_the_entry_field_is_never_the_holder_s_store_word(entry):
    # Re-review I4-R: the entry field is ten characters, so a platform's financing entry often prints a cut second
    # word; a veto word that leads the field is never spared as the holder's word, whatever follows it.
    for holder in (_RR_HOLDER, "SAMPLE BAKERY LLC"):
        rows = [(_RR_STORE.format(entry="PAYMENTS", n=n, holder=holder), 900.0 + n) for n in range(3)]
        rows.append((_RR_STORE.format(entry=entry, n=9, holder=holder), 23456.0))
        records = _records(rows, holder=holder)
        assert records[3].revenue_classification != "verified_revenue", (holder, entry)
        assert _tier(records[3]) == ("excluded_pending_review", "financing_named_payer"), (holder, entry)


@pytest.mark.parametrize("text", [
    "SQUARE INC DES:CAPITAL PAYOUT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "SHOPIFY DES:CAPITAL PAYOUT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "DOORDASH INC DES:ADVANCE PAYOUT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "GRUBHUB DES:LENDING PAYOUT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "SQUARE INC DES:LOAN DEPOSIT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "SHOPIFY DES:FUNDING PAYOUT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "SQUARE INC DES:FINANCING SETTLEMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
    "ORIG CO NAME:SHOPIFY ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:CAPITAL SEC:CCD TRACE#:1234 EED:540302 "
    "IND ID:1 IND NAME:CONTOSO BAKERY LLC TRN: 1234TC",
])
def test_a_platform_credit_whose_entry_leads_with_a_financing_word_is_never_verified(text):
    # Re-review N6 (true revenue spec §20): a processor, marketplace or platform credit whose entry field leads with a
    # financing word is the platform's financing, never revenue, for any holder: held as financing_named_payer, alone
    # or among the platform's own settlements.
    # (A LOAN entry is already non_revenue by the strong non-revenue rule, which runs first.)
    expected = ("non_revenue", None) if "LOAN" in text else ("excluded_pending_review", "financing_named_payer")
    alone = _one(text, 23456.0)
    assert alone.revenue_classification != "verified_revenue"
    assert _tier(alone) == expected
    settlements = [(text.replace("ID:1", f"ID:{n}"), 23456.0 + n) for n in range(3)]
    assert {_tier(record) for record in _records(settlements)} == {expected}


@pytest.mark.parametrize(("text", "tier"), [
    # The platform's own settlement words keep their reading: a store name, a settlement code, FUNDING on the three
    # platforms that print it on settlements.
    ("DOORDASH INC DES:SAMPLE CAPITA ID:1 INDN:SAMPLE CAPITAL GROUP LLC CO ID:1234567890 CCD",
     ("counted_flagged", "platform_unconfirmed")),
    ("TGPAYMENTS DES:FUNDING ID:1", ("counted_flagged", "platform_unconfirmed")),
    ("SQUARE INC DES:SQ540302 ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD", ("verified", None)),
])
def test_a_platform_s_settlement_words_keep_their_reading(text, tier):
    holder = "SAMPLE CAPITAL GROUP LLC" if "SAMPLE CAPITA" in text else HOLDER
    assert _tier(_one(text, 900.0, holder=holder)) == tier


@pytest.mark.parametrize("text", [
    # Re-review N1: a code right after a receiver value at the row's end, before DES, and right after a posting label.
    "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC PPD",
    "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC WEB",
    "NORTHWIND SUPPLY LLC PPD DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890",
    "NORTHWIND SUPPLY LLC 1234567890 WEB DES:PAYMENT ID:1",
    "ACH CREDIT PPD NORTHWIND SUPPLY LLC",
    "ACH CREDIT WEB NORTHWIND SUPPLY LLC 1234",
])
def test_a_consumer_code_in_its_other_slots_stays_a_consumer_entry(text):
    assert _tier(_one(text, 2500.0)) == ("counted_flagged", "named_payer_one_off")


@pytest.mark.parametrize(("text", "holder", "method"), [
    # Still never read inside a name or a receiver field: a holder whose name ends with WEB at the row's end, a payer
    # whose name ends with WEB before DES, and I1's WEB-named holder and payer.
    ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1 INDN:CONTOSO WEB", "CONTOSO WEB", "named_payer_company_form"),
    ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1 INDN:CONTOSO WEB STUDIO LLC CO ID:1234567890 CCD",
     "CONTOSO WEB STUDIO LLC", "named_payer_company_form"),
    ("NORTHWIND WEB DESIGN LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD", HOLDER,
     "named_payer_company_form"),
])
def test_a_web_named_holder_or_payer_is_still_no_consumer_entry(text, holder, method):
    assert _fw_method(_one(text, 2345.0, holder=holder)) == ("verified_revenue", method)


def test_a_payer_named_with_web_before_des_still_repeats():
    rows = [(f"NORTHWIND WEB DES:PAYMENT ID:{n} INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD", 2345.0 + n)
            for n in (1, 2)]
    assert {_fw_method(record) for record in _records(rows)} == {("verified_revenue", "named_payer_repeats")}


# ---------------------------------------------------------------------------------------------------------------------
# FW wave 3 (the wave 2 confirmation's W2-1): a store named with a financing word keeps its payouts. Fabricated rows.
# ---------------------------------------------------------------------------------------------------------------------
_W3_STORES = [
    ("SAMPLE CAPITAL GRILLE LLC", "CAPITAL GRILLE"), ("CAPITAL CITY SAMPLE DINER LLC", "CAPITAL CITY"),
    ("FIN AND FORK SAMPLE LLC", "FIN AND FORK"), ("NORTHWIND ADVANCE PIZZA LLC", "ADVANCE PIZZA"),
]
_W3_PLATFORMS = ["DOORDASH INC", "UBER EATS", "GRUBHUB"]


def _w3_payouts(platform, store, holder, receiver=None):
    return [(f"{platform} DES:{store} ID:{n} INDN:{receiver or holder} CO ID:1234567890 CCD", 900.0 + n)
            for n in range(3)]


@pytest.mark.parametrize("platform", _W3_PLATFORMS)
@pytest.mark.parametrize(("holder", "store"), _W3_STORES)
def test_a_store_named_with_a_financing_word_keeps_its_payouts(platform, holder, store):
    # W2-1: the entry field's words (two or more) are a consecutive run of the holder's own name, so the leading
    # financing word is the store's own word: its payouts verify, and the statement is not gated.
    records = _records(_w3_payouts(platform, store, holder), holder=holder)
    assert {_fw_method(record) for record in records} == {("verified_revenue", "recurring_operating_source")}


@pytest.mark.parametrize(("holder", "store"), _W3_STORES)
def test_a_store_name_the_receiver_field_prints_keeps_its_payouts(holder, store):
    # The holder's name as the classifier knows it: the account name, or the name the bank prints in the receiver
    # field (a product-name account).
    records = _records(_w3_payouts("DOORDASH INC", store, holder), holder="BUSINESS CHECKING")
    assert {_fw_method(record) for record in records} == {("verified_revenue", "recurring_operating_source")}


@pytest.mark.parametrize("platform", _W3_PLATFORMS)
@pytest.mark.parametrize(("holder", "store"), _W3_STORES)
def test_a_store_entry_that_matches_no_holder_name_is_still_held(platform, holder, store):
    records = _records(_w3_payouts(platform, store, "SAMPLE BAKERY LLC"), holder="SAMPLE BAKERY LLC")
    assert {_tier(record) for record in records} == {("excluded_pending_review", "financing_named_payer")}


@pytest.mark.parametrize("entry", ["CAPITAL", "CAPITAL DISBURSE", "CAPITAL DISB", "CAPITAL DI", "CAPITAL OFFER",
                                   "CAPITAL XFER", "LENDING DAILY", "CAPITAL PAYOUT"])
def test_the_doordash_financing_entries_stay_held_for_a_holder_who_shares_the_word(entry):
    # I4-R's eight entries: a financing entry is no run of the holder's name (a bare word is one word, and DISB, OFFER,
    # XFER, DAILY or PAYOUT is no word of 'SAMPLE CAPITAL LENDING FUNDING LLC'), so it stays held.
    rows = [(_RR_STORE.format(entry="PAYMENTS", n=n, holder=_RR_HOLDER), 900.0 + n) for n in range(3)]
    rows.append((_RR_STORE.format(entry=entry, n=9, holder=_RR_HOLDER), 23456.0))
    assert _tier(_records(rows, holder=_RR_HOLDER)[3]) == ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize(("holder", "fails"), [("FIN AND FORK SAMPLE LLC", False), ("SAMPLE BAKERY LLC", True)])
def test_a_no_entry_field_store_named_with_a_financing_word_keeps_its_payouts(holder, fails):
    # BMO prints no entry field; the store words after the platform are the run.
    records = _records([(f"DIRECT DEPOSIT DOORDASH FIN AND FORK MSP/DIV {n}", 900.0 + n) for n in range(3)],
                       holder=holder)
    held = {_tier(record) for record in records} == {("excluded_pending_review", "financing_named_payer")}
    assert held is fails
    if not fails:
        assert {_fw_method(record) for record in records} == {("verified_revenue", "recurring_operating_source")}


def test_ppd_before_des_is_the_sec_code_after_any_word():
    # Wave 2 concern 1: PPD is never a name word, so it is read as the code wherever it sits before DES; WEB after a
    # name word stays the payer's name.
    rows = [(f"NORTHWIND SUPPLY PPD DES:PAYMENT ID:{n} INDN:CONTOSO BAKERY LLC CO ID:1234567890", 2345.0 + n)
            for n in (1, 2)]
    assert {_tier(record) for record in _records(rows)} == {("counted_flagged", "named_payer_one_off")}


# GOV (owner ruling 2026-09-30): government money the business did not earn by selling goods or services leaves True
# revenue. Class B, a personal benefit, is held as personal_income; class D, a grant or subsidy, as non_sale_purpose;
# class C, a tax refund, is non_revenue (tests/test_revenue_non_revenue_55.py). Class A, a government or public program
# paying the business for its goods or services, and class E, a form whose purpose the row does not print, keep their
# readings.
_GOV_UI = "ACH DEPOSIT NYS DOL UI DD UI DD 1234567"
_GOV_HHS = ("Orig CO Name:US Hhs Stimulus Orig ID:1234567890 Desc Date: CO Entry Descr:Hhspaymentsec:CCD "
            "Trace#:123456789012345 Eed:540102 Ind ID:1234 Ind Name:Contoso Clinic")


@pytest.mark.parametrize("text", [
    # The Canadian Payments Association's federal benefit descriptors, which the banks print before the CRA's
    # originator name (CANADA); the GST/HST credit's new name in full too.
    "CANADA CHILD BENEFIT CANADA",
    "CANADA ESSENTIALS BENEFIT CANADA",
    "CANADA GROCERIES AND ESSENTIALS BENEFIT CANADA",
    "CANADA WORKERS BENEFIT CANADA",
    "CANADA DISABILITY BENEFIT CANADA",
    "OLD AGE SECURITY CANADA",
    "DIRECT DEPOSIT CANADA CHILD BENEFIT",
    # A provincial benefit the CRA pays on a province's behalf: the provincial payment code with the CRA's originator.
    "Prov/Local Gvt Payment CANADA",
    "PROVINCIAL PAYMENT CANADA",
    # A state's unemployment insurance direct deposit, and the IRS's stimulus and child tax credit.
    _GOV_UI,
    "IRS TREAS 310 DES:TAX EIP3 ID:1",
    "IRS TREAS 310 DES:CHILD CTC ID:1",
    # GOV review (I2, M4): the descriptor as the whole payer, after the posting words and template prefixes or with
    # the CRA's name around it; the Canada PRO labels; Bank of America's entry layout and a glued EIP.
    "DIRECT DEPOSIT CANADA OLD AGE SECURITY",
    "MISC PAYMENT CANADA WORKERS BENEFIT 1234",
    "PROV LOCAL GVT PAYMENT CANADA PRO",
    "PROV./LOCAL GVT PRO ONTARIO",
    "CANADA PRO DEPOSIT",
    "NYS DOL DES:UI DD ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD",
    "IRS TREAS 310 TAXEIP3 1234",
])
def test_gov_a_personal_benefit_is_held_as_personal_income(text):
    assert _tier(_one(text)) == ("excluded_pending_review", "personal_income")


@pytest.mark.parametrize("text", [
    # GOV review (I2): a business named with a benefit descriptor's words is a payer: the descriptor is read as the
    # whole payer, and a company form after UI DD or TAX EIP vetoes it; TAX EIP is read on an IRS Treasury row only.
    "CANADA DISABILITY BENEFITS CONSULTING INC DES:PAYMENT ID:1",
    "OLD AGE SECURITY SYSTEMS LTD DES:PAYMENT ID:1",
    "CANADA WORKERS BENEFIT PLAN TRUST DES:PAYMENT ID:1",
    "NORTHWIND UI DD LLC DES:PAYMENT ID:1",
    "FABRIKAM TAX EIP SERVICES DES:PAYMENT ID:1",
    "CANADA CHILD BENEFIT SOCIETY DES:PAYMENT ID:1",
    "IRS TREAS 310 DES:TAX EIP CONSULTING LLC ID:1",
])
def test_gov_review_a_business_named_like_a_benefit_is_no_personal_income(text):
    assert _one(text).revenue_tier_reason != "personal_income"


def test_gov_a_repeated_unemployment_deposit_is_never_verified():
    # Q6 verified two NYS UI deposits as a repeat payer; a benefit is no payer of the business.
    records = _records([(_GOV_UI, 450.0), (_GOV_UI, 450.0)])
    assert {(record.revenue_classification, *_tier(record)) for record in records} == {
        ("unverified_deposit", "excluded_pending_review", "personal_income")}


@pytest.mark.parametrize(("text", "reason"), [
    # Word boundaries are strict: a business named with a benefit's words pays the business.
    ("CANADA CHILD CARE CENTRE INC DES:PAYMENT ID:1", None),
    ("CHILD BENEFIT CONSULTING INC DES:PAYMENT ID:1", None),
    ("NORTHWIND UI DESIGN LLC DES:PAYMENT ID:1", None),
    # A provincial payment from a province names no CRA benefit: its purpose is not printed (class E).
    ("Prov/Local Gvt Payment ONTARIO", "named_payer_unlabelled"),
    ("PROVINCIAL PAYMENT CANADA GOOSE SUPPLY", "named_payer_unlabelled"),
])
def test_gov_a_name_is_no_personal_benefit(text, reason):
    record = _one(text)
    assert record.revenue_tier_reason != "personal_income"
    assert record.revenue_tier in ("verified", "counted_flagged")
    if reason is not None:
        assert record.revenue_tier_reason == reason


@pytest.mark.parametrize("text", [
    # The CARES Act Provider Relief Fund (HHS's stimulus to providers), and a USDA Farm Service Agency program payment.
    _GOV_HHS,
    "HHSSTIMULUS DES:HHSPAYMENT ID:1",
    "FSA TREAS 310 MISC PAY 1234",
    # GOV review (M4): the CRA's wage subsidy and the Commodity Credit Corporation's farm-program payments; and the
    # coordinator's E ruling: ESDC's federal payment code, its grants and contributions (a wage reimbursement).
    "CANADA CEWS CANADA",
    "DIRECT DEPOSIT CANADA CEWS",
    "CCC TREAS 310 MISC PAY 1234",
    "GOVERNMENT ESDC 123-456 Paiement federal/Federal Pmt",
])
def test_gov_a_government_grant_or_subsidy_is_held_as_not_a_sale(text):
    assert _tier(_one(text)) == ("excluded_pending_review", "non_sale_purpose")


def test_gov_a_repeated_provider_relief_payment_is_never_verified():
    records = _records([(_GOV_HHS, 23456.0), (_GOV_HHS, 3456.0)], holder="CONTOSO CLINIC LLC")
    assert {(record.revenue_classification, *_tier(record)) for record in records} == {
        ("unverified_deposit", "excluded_pending_review", "non_sale_purpose")}


@pytest.mark.parametrize("text", [
    "NORTHWIND FSA SERVICES LLC DES:PAYMENT ID:1",
    "HHS SUPPLY CO DES:PAYMENT ID:1",
    "CANADA CEWS CONSULTING INC DES:PAYMENT ID:1",
    # GOV review (M4): USDA's own Treasury form also pays vendors, so it keeps its reading.
    "USDA TREAS 310 MISC PAY 1234",
])
def test_gov_a_name_is_no_government_grant(text):
    record = _one(text)
    assert record.revenue_tier in ("verified", "counted_flagged")
    assert record.revenue_tier_reason != "non_sale_purpose"


@pytest.mark.parametrize(("rows", "expected"), [
    # Class A: a government or public program paying the business for its goods or services keeps its reading.
    ([("MISC PAYMENT GC CDCP ASO FABRIKAM LIFE", 812.0), ("MISC PAYMENT GC CDCP ASO FABRIKAM LIFE", 455.0)],
     ("verified_revenue", "named_payer_repeats")),
    ([("TREAS 310 DES:DOD MISC ID:1", 1234.0)], ("verified_revenue", "public_payer_remittance")),
    ([("SAMPLE STATE DHS DES:PROV PAY ID:1", 1234.0)], ("verified_revenue", "public_payer_remittance")),
    ([("SAMPLE COUNTY DHHS DES:VENDOR PAY ID:1", 1234.0)], ("verified_revenue", "payer_remittance_descriptor")),
    # Class E (the forms that print no purpose) is non_revenue since the owner's ruling of 2026-10-02 (the
    # underwriter's Q12): tests/test_true_revenue_government_no_purpose.py.
])
def test_gov_a_payment_for_services_keeps_its_reading(rows, expected):
    for record in _records(rows):
        state, reading = expected
        assert record.revenue_classification == state
        assert (record.revenue_match_method if state == "verified_revenue" else record.revenue_tier_reason) == reading


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B07 (R07): a welded run of unread payer blocks that names a lender is held, never counted
# ---------------------------------------------------------------------------------------------------------------------

UNREAD_FINANCING = "unread_run_names_financing"


def _welded_tiers(**lines):
    """The counted core-processor template's welded credit run (tests/test_core_processor_counted.py), classified:
    (tier, reason) of every credit in ledger order, the statement's lender credits, and whether any credit was put
    toward them."""
    from analysis.metrics import compute_metrics
    from tests import test_core_processor_counted as counted

    statement = counted.welded(**lines)
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    credits = [record for record in records if record.amount > 0]
    return ([_tier(record) for record in credits], metrics.lender_credits,
            any(record.contributes_to_lender_credit_exclusion for record in credits))


def test_a_welded_run_printing_a_funder_holds_every_row_of_its_flush():
    tiers, lender_credits, toward = _welded_tiers()
    assert tiers == [("verified", None)] + [("excluded_pending_review", UNREAD_FINANCING)] * 4 + [
        ("counted_flagged", "payer_text_not_read")] * 2
    # No amount is put toward lender credits from text the parser could not attribute to a row.
    assert (lender_credits, toward) == (0.0, False)


def _blocks(*names: str) -> tuple[str, ...]:
    from tests.test_core_processor_counted import RECEIVER

    return tuple(f"{name} 300000000{index} {RECEIVER} CCD" for index, name in enumerate(names, start=1))


_CUSTOMERS = ("CONTOSO INC. PAYABLES", "FABRIKAM INC. PAYABLES", "NORTHWIND INC. PAYABLES", "SAMPLE INC. PAYABLES")


@pytest.mark.parametrize(("first_line", "second_line", "held"), [
    # A lending bank (the registry's LENDING_BANK_CREDIT_PAYERS) in the second flush holds both of its rows.
    (_blocks(*_CUSTOMERS), _blocks("CELTIC BANK 600000001 NORTHWIND BAKERY LLC", "SAMPLE INC. PAYABLES"), "second"),
    # A lender's name the bank glued to its next word (a line of credit in the registry) at the start of the flush.
    (_blocks("HEADWAYCAPITAL 1", *_CUSTOMERS[:3]), _blocks(*_CUSTOMERS[:2]), "first"),
    # A confirmed lender anywhere in the flush.
    (_blocks(*_CUSTOMERS[:3], "ONDECK CAPITAL"), _blocks(*_CUSTOMERS[:2]), "first"),
    # A customer whose name holds a financing root is no registry lender: the bare root is not read.
    (_blocks(*_CUSTOMERS), _blocks("SAMPLE CAPITAL SUPPLY INC PAYABLES", "CONTOSO INC. PAYABLES"), None),
    # An alternative position or a factor names no lender for this hold (a platform's settlement, a factor's payout).
    (_blocks("SQUARE CAPITAL", *_CUSTOMERS[:3]), _blocks("OTR CAPITAL", "CONTOSO INC. PAYABLES"), None),
])
def test_a_welded_run_is_held_only_where_a_lender_or_a_lending_bank_is_printed(first_line, second_line, held):
    tiers, lender_credits, toward = _welded_tiers(first_line=first_line, second_line=second_line)
    unread = ("counted_flagged", "payer_text_not_read")
    hold = ("excluded_pending_review", UNREAD_FINANCING)
    assert tiers == [("verified", None)] + [hold if held == "first" else unread] * 4 + [
        hold if held == "second" else unread] * 2
    assert (lender_credits, toward) == (0.0, False)


def test_a_funder_block_printed_alone_under_its_row_is_still_financing_proceeds():
    """The control: attributed, the funder's block is the row's own text and the row is a lender credit."""
    from analysis.metrics import compute_metrics
    from tests import test_core_processor_counted as counted

    statement = counted.published(credits=(
        "ELECTRONIC CREDITS\nDate Description Credits\n2-3 Preauthorized Credit 300.00\n"
        f"{counted.KAPITUS_BLOCK}\n"
    ))
    records = classify_statement_transactions(statement)
    credit = next(record for record in records if record.amount > 0)
    assert (credit.revenue_tier, credit.contributes_to_lender_credit_exclusion) == ("non_revenue", True)
    assert compute_metrics(statement, classifications=records).lender_credits > 0


@pytest.mark.parametrize("name", ["CASH ARC LLC EDI PYMNTS", "CASH-ARC LLC EDI PYMNTS", "CASHARC LLC EDI PYMNTS"])
def test_r3_87_a_lender_whose_name_holds_a_class_code_word_holds_its_welded_run(name):
    """Audit round 3, R3-B09 (R3-87): a class-code word before a legal form (CashArc's 'CASH ARC LLC') is part of a
    name, never a block's end, so the run's lender block is read and both rows of its flush are held."""
    tiers, lender_credits, toward = _welded_tiers(first_line=_blocks(*_CUSTOMERS),
                                                  second_line=_blocks("CONTOSO INC PAYABLES", name))
    assert tiers == [("verified", None)] + [("counted_flagged", "payer_text_not_read")] * 4 + [
        ("excluded_pending_review", UNREAD_FINANCING)] * 2
    assert (lender_credits, toward) == (0.0, False)


@pytest.mark.parametrize("name", ["CASH ARC LLC EDI PYMNTS", "CASH-ARC LLC EDI PYMNTS"])
def test_r3_87_a_lender_block_holding_a_class_code_word_alone_under_its_row_is_financing_proceeds(name):
    from analysis.metrics import compute_metrics
    from tests import test_core_processor_counted as counted

    statement = counted.published(credits=(
        "ELECTRONIC CREDITS\nDate Description Credits\n2-3 Preauthorized Credit 300.00\n"
        f"{name} 0000001 {counted.RECEIVER} CCD\n"
    ))
    records = classify_statement_transactions(statement)
    credit = next(record for record in records if record.amount > 0)
    assert not statement.transactions[[t.amount > 0 for t in statement.transactions].index(True)].payer_text_unread
    assert (credit.revenue_tier, credit.contributes_to_lender_credit_exclusion) == ("non_revenue", True)
    assert credit.revenue_canonical_entity == "CashArc LLC"
    assert compute_metrics(statement, classifications=records).lender_credits > 0


@pytest.mark.parametrize(("text", "blocks"), [
    ("CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD CASH ARC LLC EDI PYMNTS 2 NORTHWIND BAKERY CCD",
     ["CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD", "CASH ARC LLC EDI PYMNTS 2 NORTHWIND BAKERY CCD"]),
    ("CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD CASH-ARC LLC EDI PYMNTS 2 NORTHWIND BAKERY CCD",
     ["CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD", "CASH ARC LLC EDI PYMNTS 2 NORTHWIND BAKERY CCD"]),
    # A real ARC entry (no legal form after the code) still closes its block.
    ("CONTOSO SUPPLY ARC 0001 NORTHWIND CCD", ["CONTOSO SUPPLY ARC", "0001 NORTHWIND CCD"]),
    ("CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD KAPITUS LLC FUNDING 2 NORTHWIND BAKERY CCD",
     ["CONTOSO INC PAYABLES 1 NORTHWIND BAKERY CCD", "KAPITUS LLC FUNDING 2 NORTHWIND BAKERY CCD"]),
])
def test_r3_87_an_unread_run_splits_after_a_class_code_never_before_a_legal_form(text, blocks):
    assert true_revenue_tiers.unread_run_blocks(text) == blocks


@pytest.mark.parametrize(("line", "expected"), [
    # R3-B09 review round 1: two blocks welded under one outstanding row, the second opening on a legal-form word
    # other than the LLC family. The row stays unread, as before R3-87: a customer's weld is counted and flagged as
    # unread (never Verified, never non_revenue), and a weld printing a lender holds the row with no lender credit.
    ("FABRIKAM INC. PAYABLES 2200000001 {R} CCD INC VILLAGE OF SAMPLE AP 0000000009 {R} CCD", "unread"),
    ("FABRIKAM INC. PAYABLES 2200000001 {R} CCD CO DEPT REVENUE TAX REFUND 0000000009 {R} PPD", "unread"),
    ("FABRIKAM INC. PAYABLES 2200000001 {R} CCD CO-OP POWER PAYMENT 2200000002 {R} CCD", "unread"),
    ("KAPITUS LLC FUNDING 5500000005 {R} CCD CO-OP POWER PAYMENT 2200000001 {R} CCD", "held"),
    ("KAPITUS LLC FUNDING 5500000005 {R} CCD COMPANY STORE SALES 2200000001 {R} CCD", "held"),
    ("KAPITUS LLC FUNDING 5500000005 {R} CCD INC VILLAGE OF SAMPLE AP 0000000009 {R} CCD", "held"),
    # The control: a second block opening on a plain name word.
    ("KAPITUS LLC FUNDING 5500000005 {R} CCD CONTOSO SUPPLY 2200000001 {R} CCD", "held"),
])
def test_r3_87_review_a_weld_whose_next_block_opens_on_a_legal_form_word_keeps_its_unread_reading(line, expected):
    from analysis.metrics import compute_metrics
    from tests import test_core_processor_counted as counted

    line = line.format(R=counted.RECEIVER)
    statement = counted.published(credits=(
        f"ELECTRONIC CREDITS\nDate Description Credits\n2-3 Preauthorized Credit 300.00\n{line}\n"
    ))
    records = classify_statement_transactions(statement)
    [index] = [i for i, t in enumerate(statement.transactions) if t.amount > 0]
    assert (statement.transactions[index].description, statement.transactions[index].payer_text_unread) == (
        "Preauthorized Credit", True)
    reading = {"unread": ("counted_flagged", "payer_text_not_read"),
               "held": ("excluded_pending_review", UNREAD_FINANCING)}[expected]
    assert _tier(records[index]) == reading
    assert compute_metrics(statement, classifications=records).lender_credits == 0.0


@pytest.mark.parametrize(("text", "blocks"), [
    ("FABRIKAM PAYABLES 1 NORTHWIND CCD CO OP POWER 2 NORTHWIND CCD",
     ["FABRIKAM PAYABLES 1 NORTHWIND CCD", "CO OP POWER 2 NORTHWIND CCD"]),
    ("KAPITUS LLC FUNDING 1 NORTHWIND CCD INC VILLAGE OF SAMPLE 2 NORTHWIND CCD",
     ["KAPITUS LLC FUNDING 1 NORTHWIND CCD", "INC VILLAGE OF SAMPLE 2 NORTHWIND CCD"]),
    ("FABRIKAM PAYABLES 1 NORTHWIND PPD COMPANY STORE 2 NORTHWIND CCD",
     ["FABRIKAM PAYABLES 1 NORTHWIND PPD", "COMPANY STORE 2 NORTHWIND CCD"]),
    ("CONTOSO PAYABLES 1 NORTHWIND CCD L L C SAMPLE 2 NORTHWIND CCD",
     ["CONTOSO PAYABLES 1 NORTHWIND CCD L L C SAMPLE 2 NORTHWIND CCD"]),
])
def test_r3_87_review_the_run_split_joins_a_code_only_to_the_llc_family(text, blocks):
    """The run split reads the counted template's narrowed rule: only LLC, L L C, LLP or PLLC after a class-code word
    makes it a name word (the last case is the disclosed residual: no ACH originator name opens on the LLC family)."""
    assert true_revenue_tiers.unread_run_blocks(text) == blocks


def test_r3_87_a_run_naming_casharc_names_financing_and_a_customer_s_arc_entry_does_not():
    assert true_revenue_tiers.unread_run_names_financing("CONTOSO INC PAYABLES 1 NORTHWIND CCD CASH ARC LLC EDI PYMNTS 2 NORTHWIND CCD")
    assert not true_revenue_tiers.unread_run_names_financing("CONTOSO SUPPLY ARC 0001 NORTHWIND CCD FABRIKAM INC 2 NORTHWIND CCD")


def _marked(text: str, unread_text: str, *, marked: bool = True):
    return classify_statement_transactions(Statement(account_name=HOLDER, transactions=[
        Transaction(date="2054-03-02", description=text, amount=1234.0, direction="credit",
                    payer_text_unread=marked, unread_payer_text=unread_text if marked else ""),
    ]))[0]


@pytest.mark.parametrize(("text", "expected"), [
    # A cash, branch, teller or ATM label says itself that no payer was printed (Q2).
    ("TELLER DEPOSIT", ("counted_flagged", "no_payer_printed")),
    ("ATM DEPOSIT", ("counted_flagged", "no_payer_printed")),
    # Every earlier hold keeps its precedence: a bare transfer label stays a transfer with no counterparty.
    ("TRANSFER IN", ("excluded_pending_review", "transfer_no_counterparty")),
    # A bare label is held.
    ("PREAUTHORIZED CREDIT", ("excluded_pending_review", UNREAD_FINANCING)),
])
def test_the_unread_run_hold_replaces_only_the_payer_text_not_read_reading(text, expected):
    unread = f"CONTOSO INC. PAYABLES 1 NORTHWIND BAKERY CCD KAPITUS LLC FUNDING 2 NORTHWIND BAKERY CCD"
    assert _tier(_marked(text, unread)) == expected


def test_an_unread_run_naming_no_lender_keeps_payer_text_not_read():
    record = _marked("PREAUTHORIZED CREDIT", "CONTOSO INC. PAYABLES 1 NORTHWIND BAKERY CCD FABRIKAM INC 2 CCD")
    assert _tier(record) == ("counted_flagged", "payer_text_not_read")


def test_the_unread_run_reason_is_a_held_reason_of_the_one_reason_table():
    assert REVENUE_TIER_REASONS[UNREAD_FINANCING] == (
        "excluded_pending_review", "A lender is printed among this credit's unread payer blocks",
    )


# ---------------------------------------------------------------------------------------------------------------------
# Owner ruling 2026-10-02 (the underwriter's Q9, part (c')), R2-OW05: a listed auto lender's credit read on a payables
# word alone (PAYABLES, TRADE PAY, ACCT FUND) verifies only on a statement with dealer evidence (a Q7 credit with a
# dealer-specific word or the credit-union arm, a floor-plan financier's row or FLOOR PLAN, a purchase at a dealer-only
# auction, a dealer word in the holder's name with no recovery, repossession, towing or collateral word); otherwise it
# is counted_flagged / lender_paid_for_services (a repossession agency's recoveries), or held as financing_named_payer
# when the lender also collects from the account (the hidden-loan guard). Fabricated rows, Bank of America's DES layout.
# ---------------------------------------------------------------------------------------------------------------------
AGENCY = "SAMPLE RECOVERY LLC"
WESTLAKE_PAYABLES = "WESTLAKE FINANCI DES:PAYABLES ID:EFT1234567 INDN:{holder} CO ID:1 CCD"
LENDER_SERVICE = ("counted_flagged", "lender_paid_for_services")


def _q7_reading(record):
    return (record.revenue_tier, record.revenue_tier_reason, record.revenue_classification,
            record.revenue_match_method, record.revenue_source_type)


@pytest.mark.parametrize(("text", "holder"), [
    (WESTLAKE_PAYABLES.format(holder=AGENCY), AGENCY),
    # The dealer-holder veto: a dealer word in a name that also prints RECOVERY is no dealer's name.
    (WESTLAKE_PAYABLES.format(holder="SAMPLE AUTOMOTIVE RECOVERY LLC"), "SAMPLE AUTOMOTIVE RECOVERY LLC"),
    ("GM FINANCIAL DES:PAYABLES ID:1 INDN:SAMPLE RECOVERY LLC CO ID:1 CCD", AGENCY),
    # No dealer evidence of any kind: a holding company's statement.
    ("WESTLAKE FINANCI DES:PAYABLES ID:1", "SAMPLE HOLDINGS LLC"),
    ("WESTLAKE FINANCI DES:TRADE PAYABLE ID:1", AGENCY),
    ("WESTLAKE FINANCIAL DES:ACCT FUNDING ID:1", AGENCY),
])
def test_q9_c_a_listed_lender_s_payables_with_no_dealer_evidence_is_a_lender_paid_for_services(text, holder):
    record = _one(text, 1500.0, holder=holder)
    assert _q7_reading(record) == (*LENDER_SERVICE, "unverified_deposit", "lender_paid_for_services", None)
    assert record.revenue_matched_rule == "q7_payables_without_dealer_evidence"
    assert record.revenue_confidence_score == 0.50
    assert "lender_paid_for_services" in record.revenue_context_signals
    assert record.contributes_to_true_revenue and not record.contributes_to_verified_revenue
    assert not record.revenue_review_required
    # The reason names the lender, says the statement shows no dealer evidence and that the ruling overrules Q7.
    assert record.revenue_canonical_entity in record.revenue_reason
    assert record.revenue_matched_alias in record.revenue_reason
    assert "no dealer evidence" in record.revenue_reason
    # (The date is the ruling's, never a literal year in the code: tests/test_no_statement_hardcodes.py.)
    assert "The owner's ruling on the underwriter's Q9 overrules auto_lender_dealer_funding." in record.revenue_reason
    # The transaction side is untouched: Q7's record, its lender and every lender flag.
    assert (record.classification, record.match_method) == ("other", "auto_lender_dealer_funding")
    assert record.canonical_entity == record.revenue_canonical_entity
    assert not record.contributes_to_lender_credit_exclusion


def test_q9_c_the_repossession_agency_s_westlake_row_keeps_its_lender_fields():
    record = _one(WESTLAKE_PAYABLES.format(holder=AGENCY), 1500.0, holder=AGENCY)
    assert (record.canonical_entity, record.matched_alias) == WESTLAKE
    assert (record.revenue_canonical_entity, record.revenue_matched_alias) == WESTLAKE
    assert (record.classification, record.match_method, record.contributes_to_lender_credit_exclusion) == (
        "other", "auto_lender_dealer_funding", False)


@pytest.mark.parametrize(("rows", "holder"), [
    # A dealer's name on the holder (every Q7 test above uses SAMPLE MOTORS LLC or ADVANCE AUTO SALES LLC).
    ([(WESTLAKE_PAYABLES.format(holder=DEALER), 15000.0)], DEALER),
    ([(WESTLAKE_PAYABLES.format(holder="ADVANCE AUTO SALES LLC"), 15000.0)], "ADVANCE AUTO SALES LLC"),
    # A floor-plan financier's debit.
    ([("WESTLAKE FINANCI DES:PAYABLES ID:1", 15000.0), ("NEXTGEAR CAPITAL DES:PAYMENT ID:2", -9000.0)],
     "SAMPLE HOLDINGS LLC"),
    # A purchase at a dealer-only wholesale auction.
    ([("WESTLAKE FINANCI DES:PAYABLES ID:1", 15000.0), ("MANHEIM US DES:ACH PAYMNT ID:3", -8000.0)],
     "SAMPLE HOLDINGS LLC"),
])
def test_q9_c_a_dealer_s_payables_with_dealer_evidence_stay_verified(rows, holder):
    record = _records(rows, holder=holder)[0]
    assert _q7_reading(record) == (
        "verified", None, "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")


def test_q9_c_a_dealer_specific_q7_credit_is_dealer_evidence_and_both_stay_verified():
    rows = _records([("WESTLAKE FINANCI DES:PAYABLES ID:1", 15000.0), ("ALLY FINANCIAL DES:DEALER PAY ID:2", 21000.0)],
                    holder="SAMPLE HOLDINGS LLC")
    assert [_q7_reading(record) for record in rows] == [
        ("verified", None, "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")] * 2


def test_q9_c_a_dealer_specific_word_verifies_even_at_a_repossession_agency():
    record = _one("WESTLAKE FINANCI DES:DEALER PAY ID:1", 1500.0, holder=AGENCY)
    assert _q7_reading(record) == (
        "verified", None, "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")


def test_q9_c_the_hidden_loan_guard_holds_a_payables_credit_whose_lender_also_debits_the_account():
    rows = _records([("WESTLAKE FINANCI DES:PAYABLES ID:1", 1500.0), ("WESTLAKE FINANCI DES:AUTO PAY ID:9", -450.0)],
                    holder=AGENCY)
    record = rows[0]
    assert _q7_reading(record) == (
        "excluded_pending_review", "financing_named_payer", "unverified_deposit", "lender_paid_for_services", None)
    assert record.revenue_review_required and not record.contributes_to_true_revenue
    assert record.revenue_matched_rule == "q7_payables_without_dealer_evidence"
    # The lender's debit keeps its reading.
    assert rows[1].classification == "vehicle_financing"
    # Audit round 3, R3-B15 (R3-53; §5.3): a held row's reason sentence never says it is counted; the hold names
    # itself by its own label. The counted twin (no debit) keeps "counted and flagged, never verified".
    assert "counted and flagged" not in record.revenue_reason
    assert f"never verified, and held for review ({REVENUE_TIER_REASONS['financing_named_payer'][1]})" in (
        record.revenue_reason)
    assert "auto_lender_dealer_funding" in record.revenue_reason
    counted = _one("WESTLAKE FINANCI DES:PAYABLES ID:1", 1500.0, holder=AGENCY)
    assert _q7_reading(counted)[:2] == ("counted_flagged", "lender_paid_for_services")
    assert "counted and flagged, never verified" in counted.revenue_reason
    assert counted.revenue_reason.replace(
        "counted and flagged, never verified",
        f"never verified, and held for review ({REVENUE_TIER_REASONS['financing_named_payer'][1]})",
    ) == record.revenue_reason


def test_q9_c_the_demotion_never_moves_a_debit_or_a_lender_reading():
    from analysis.metrics import compute_metrics

    def readings(holder):
        statement = Statement(account_name=holder, transactions=[
            Transaction(date="2054-03-02", description="WESTLAKE FINANCI DES:PAYABLES ID:1", amount=15000.0,
                        direction="credit"),
            Transaction(date="2054-03-03", description="WESTLAKE FINANCI DES:AUTO PAY ID:9", amount=-450.0,
                        direction="debit"),
            Transaction(date="2054-03-04", description="FABRIKAM SUPPLY DES:VENDOR PAY ID:1", amount=-300.0,
                        direction="debit"),
        ])
        records = classify_statement_transactions(statement)
        metrics = compute_metrics(statement, classifications=records)
        lender = [(record.classification, record.match_method, record.canonical_entity,
                   record.contributes_to_lender_count, record.contributes_to_lender_totals,
                   record.contributes_to_withholding_rate, record.contributes_to_lender_credit_exclusion)
                  for record in records]
        return lender, metrics.lender_credits, metrics.legacy_eligible_deposits

    # The same rows on a dealer's statement (verified) and on an agency's (held by the guard): one lender reading.
    assert readings(DEALER) == readings(AGENCY)


def test_q9_c_the_payables_only_reading_and_the_dealer_evidence_arms():
    from analysis import true_revenue

    assert true_revenue._payables_only_dealer_funding("WESTLAKE FINANCI DES PAYABLES ID 1")
    assert true_revenue._payables_only_dealer_funding("WESTLAKE FINANCI DES TRADE PAYABLE ID 1")
    assert true_revenue._payables_only_dealer_funding("WESTLAKE FINANCIAL DES ACCT FUNDING ID 1")
    # A dealer-specific word is read first, the credit-union arm is no listed arm, and no lender reads none.
    assert not true_revenue._payables_only_dealer_funding("WESTLAKE FINANCI DES DEALER PAY ID 1")
    assert not true_revenue._payables_only_dealer_funding("ONE RIVER FUNDING DES PAYABLES DEALER PAY ID 1")
    assert not true_revenue._payables_only_dealer_funding("CU DIRECT DES VHCL PURCH ID 1")
    assert not true_revenue._payables_only_dealer_funding("NORTHWIND SUPPLY DES PAYABLES ID 1")

    def evidence(rows, holder="SAMPLE HOLDINGS LLC"):
        records = _records(rows, holder=holder)
        credits = [index for index, record in enumerate(records) if record.amount > 0]
        return (true_revenue._dealer_activity(records, set(), credits),
                true_revenue._dealer_contract_evidence(records, set(), credits))

    payables = ("WESTLAKE FINANCI DES:PAYABLES ID:1", 15000.0)
    # A payables-only Q7 credit is no dealer activity.
    assert evidence([payables]) == (False, False)
    # Each activity arm, one by one.
    assert evidence([payables, ("ALLY FINANCIAL DES:DEALER PAY ID:2", 21000.0)]) == (True, True)
    assert evidence([payables, (UNION.format(n=1), 18000.0)]) == (True, True)
    assert evidence([payables, (UNION.format(n=1), 18000.0), (UNION.format(n=2), 21000.0)]) == (True, True)
    assert evidence([payables, ("NEXTGEAR CAPITAL DES:PAYMENT ID:2", -9000.0)]) == (True, True)
    assert evidence([payables, ("KINETIC ADVANTAGE DES:CURTAILMNT ID:2", -9000.0)]) == (True, True)
    assert evidence([payables, ("SAMPLE BANK DES:FLOOR PLAN ID:2", -9000.0)]) == (True, True)
    assert evidence([payables, ("SAMPLE BANK DES:FLOORPLAN INT ID:2", -900.0)]) == (True, True)
    assert evidence([payables, ("MANHEIM US DES:ACH PAYMNT ID:3", -8000.0)]) == (True, True)
    assert evidence([payables, ("ACV AUCTIONS INC DES:PURCHASE ID:3", -8000.0)]) == (True, True)
    assert evidence([payables, ("BACKLOTCARS PURCHASE 1234", -8000.0)]) == (True, True)
    # An auction's name on a credit is no purchase (its payout is Q11's evidence, R2-OW06, never Q9's).
    assert evidence([payables, ("MANHEIM US DES:ACH PAYMNT ID:3", 8000.0)]) == (False, False)
    # A duplicate row never counts.
    records = _records([payables, ("NEXTGEAR CAPITAL DES:PAYMENT ID:2", -9000.0)], holder="SAMPLE HOLDINGS LLC")
    assert not true_revenue._dealer_activity(records, {1}, [0])
    # The holder arm, and its veto.
    assert evidence([payables], holder="SAMPLE MOTORS LLC") == (False, True)
    assert evidence([payables], holder="SAMPLE AUTO SALES LLC") == (False, True)
    assert evidence([payables], holder="SAMPLE AUTO GROUP INC") == (False, True)
    assert evidence([payables], holder="SAMPLE MOTORS RECOVERY LLC") == (False, False)
    assert evidence([payables], holder="SAMPLE AUTOMOTIVE TOWING LLC") == (False, False)
    assert evidence([payables], holder="SAMPLE REPOSSESSIONS AUTO GROUP LLC") == (False, False)
    assert evidence([payables], holder="SAMPLE COLLATERAL MOTORS INC") == (False, False)
    assert evidence([payables], holder=AGENCY) == (False, False)
    # Audit round 3, R3-B14 (R3-52): a card purchase in an auction's town, a floor-plan financier's service credit and
    # a word that only starts like a floor plan are no dealer evidence; the floor-plan forms still read.
    assert evidence([payables, ("CHECKCARD 0302 CONTOSO DINER MANHEIM PA 0000", -38.50)]) == (False, False)
    assert evidence([payables, ("POS PURCHASE 0302 NORTHWIND FUEL MANHEIM PA", -61.20)]) == (False, False)
    assert evidence([payables, ("NEXTGEAR CAPITAL DES:VENDOR PAY ID:1", 475.0)]) == (False, False)
    assert evidence([payables, ("CONTOSO FLOORPLANNER DES:SUBSCRIPT ID:1", -19.99)]) == (False, False)
    assert evidence([payables, ("FPX FLOORPLAN XPRESS ADVANCE VIN 1FAKE0000000000001", 18000.0)]) == (True, True)
    assert evidence([payables, ("FLOOR PLAN PAYOFF", -9000.0)]) == (True, True)
    for form, read in (("FLOORPLAN", True), ("FLOOR PLAN", True), ("FLOORPLANS", True), ("FLOOR PLANNING", True),
                       ("FLOORPLAN INT", True), ("FLOORPLANNER", False), ("FLOOR PLANKS", False),
                       ("FLOOR PLANER", False), ("SUBFLOOR PLAN", False)):
        assert bool(true_revenue._FLOOR_PLAN_FORM.search(form)) is read, form
    for words, read in (("VENDOR PAY", True), ("VENDORPMT", True), ("VENDOR PAYMENT", True), ("REPO FEE", True),
                        ("REPOS", True), ("REPOSSESSION", True), ("RECOVERY", True), ("TOWING", True), ("TOW", True),
                        ("TRANSPORT", True), ("INSPECTION", True), ("COMMISSION", True),
                        ("ADVANCE", False), ("PAYMENT", False), ("CURTAILMNT", False), ("FLOOR PLAN", False)):
        assert bool(true_revenue._FLOOR_PLAN_SERVICE_CREDIT.search(words)) is read, words


# Audit round 3, R3-B14 (R3-52; the underwriter's Q9 (c), "a lender paying a business for services counts as 'lender
# paid for services', never verified. The hidden-loan guard stays"): a row that is no dealer evidence never keeps a
# repossession agency's Westlake PAYABLES Verified: a card purchase in the auction's town (Manheim, PA), a floor-plan
# financier's service credit, a FLOORPLANNER subscription and a FLOOR PLANKS purchase. Fabricated rows, Bank of
# America's DES layout.
_R3_52_AGENCY = "CONTOSO RECOVERY LLC"
_R3_52_PAYABLES = (
    "WESTLAKE FINANCI DES:PAYABLES ID:EFT0000001 INDN:CONTOSO RECOVERY LLC CO ID:0000000001 CCD", 3150.0)
_R3_52_AUTO_PAY = ("WESTLAKE FINANCI DES:AUTO PAY ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", -455.0)
_R3_52_NO_EVIDENCE = (
    ("CHECKCARD 0302 CONTOSO DINER MANHEIM PA 0000", -38.50),
    ("POS PURCHASE 0302 NORTHWIND FUEL MANHEIM PA", -61.20),
    ("NEXTGEAR CAPITAL DES:VENDOR PAY ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", 475.00),
    ("AFC FUNDING CORP DES:REPO FEE ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", 390.00),
    ("CONTOSO FLOORPLANNER DES:SUBSCRIPT ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", -19.99),
    ("NORTHWIND HARDWARE DES:FLOOR PLANKS ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", -310.00),
)
_R3_52_EVIDENCE = (
    ("MANHEIM US DES:ACH PAYMNT ID:1 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", -8400.00),
    # A NextGear debit the classifier reads as floor_plan_financing.
    ("NEXTGEAR CAPITAL DES:PAYMENT ID:2 INDN:CONTOSO RECOVERY LLC CO ID:1 CCD", -9000.00),
    ("FPX FLOORPLAN XPRESS ADVANCE VIN 1FAKE0000000000001", 18000.00),
    ("FLOOR PLAN PAYOFF", -9000.00),
)


@pytest.mark.parametrize("row", _R3_52_NO_EVIDENCE, ids=[row[0][:32] for row in _R3_52_NO_EVIDENCE])
def test_r3_52_a_row_that_is_no_dealer_evidence_never_keeps_payables_verified(row):
    # Today each is Verified (auto_lender_dealer_funding).
    record = _records([_R3_52_PAYABLES, row], holder=_R3_52_AGENCY)[0]
    assert _q7_reading(record) == (*LENDER_SERVICE, "unverified_deposit", "lender_paid_for_services", None)
    # The hidden-loan guard: where the lender also collects from the account, the row is held, never Verified.
    held = _records([_R3_52_PAYABLES, row, _R3_52_AUTO_PAY], holder=_R3_52_AGENCY)[0]
    assert _q7_reading(held) == (
        "excluded_pending_review", "financing_named_payer", "unverified_deposit", "lender_paid_for_services", None)
    assert not held.contributes_to_true_revenue


@pytest.mark.parametrize("row", _R3_52_EVIDENCE, ids=[row[0][:32] for row in _R3_52_EVIDENCE])
def test_r3_52_dealer_evidence_still_keeps_payables_verified(row):
    records = _records([_R3_52_PAYABLES, row], holder=_R3_52_AGENCY)
    assert _q7_reading(records[0]) == (
        "verified", None, "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")
    if row[0].startswith("NEXTGEAR"):
        assert records[1].classification == "floor_plan_financing"


# Audit round 3, R3-B14 review round 1 (findings 4 to 6): the narrowed arms read no more than their own words. A
# floor-plan financier's VIN-bearing advance whose unlabelled receiver is the holder's own name printing a service word
# (RECOVERY, TRANSPORT, COMMISSIONS: the service wording is read without the holder's names too); a wire or ACH
# purchase at the auction that prints the beneficiary's state and country (the card form's '<ST> USA|CAN' tail is no
# card purchase on a wire, ACH or check row); and a glued floor-plan word (FLOORPLANINT, FLOORPLANPAYOFF,
# FLOORPLANXPRESS, FLOORPLANADV). At 3939f5c each left the payables counted as lender_paid_for_services.
_R1_EVIDENCE = (
    ("CONTOSO AUTO RECOVERY LLC", ("NEXTGEAR CAPITAL FLOORPLAN ADV 1FAKE0000000000001 CONTOSO AUTO RECOVERY", 18000.0)),
    ("CONTOSO AUTO TRANSPORT LLC",
     ("NEXTGEAR CAPITAL FLOORPLAN ADV 1FAKE0000000000001 CONTOSO AUTO TRANSPORT", 18000.0)),
    ("CONTOSO VEHICLE COMMISSIONS LLC",
     ("NEXTGEAR CAPITAL FLOORPLAN ADV 1FAKE0000000000001 CONTOSO VEHICLE COMMISSIONS", 18000.0)),
    (_R3_52_AGENCY, ("OUTGOING WIRE MANHEIM REMARKETING ATLANTA GA USA", -12000.0)),
    (_R3_52_AGENCY, ("ACH DEBIT MANHEIM AUCTIONS ATLANTA GA USA", -12000.0)),
    (_R3_52_AGENCY, ("CHECK 1234 MANHEIM REMARKETING ATLANTA GA USA", -12000.0)),
    (_R3_52_AGENCY, ("FLOORPLANINT", -90.0)),
    (_R3_52_AGENCY, ("FLOORPLANPAYOFF 1FAKE0000000000001", -9000.0)),
    (_R3_52_AGENCY, ("FLOORPLANXPRESS DES:CURTAIL ID:1", -900.0)),
)


@pytest.mark.parametrize(("holder", "row"), _R1_EVIDENCE, ids=[row[0][:32] for _holder, row in _R1_EVIDENCE])
def test_r3_b14_r1_the_narrowed_arms_still_read_a_dealer_s_own_evidence(holder, row):
    payables = (WESTLAKE_PAYABLES.format(holder=holder), 3150.0)
    record = _records([payables, row], holder=holder)[0]
    assert _q7_reading(record) == (
        "verified", None, "verified_revenue", "auto_lender_dealer_funding", "auto_dealer_funding")


def test_r3_b14_r1_the_arms_controls():
    from analysis import true_revenue

    # A card charge in Found's or Bluevine's form (no wire, ACH or check word) is still a card purchase in the town.
    payables = (WESTLAKE_PAYABLES.format(holder=_R3_52_AGENCY), 3150.0)
    for row in (("CONTOSO DINER MANHEIM PA USA", -38.50), ("DEBIT CARD PURCHASE MANHEIM SIMULCAST GA USA", -120.0)):
        record = _records([payables, row], holder=_R3_52_AGENCY)[0]
        assert _q7_reading(record) == (*LENDER_SERVICE, "unverified_deposit", "lender_paid_for_services", None), row
    # A floor-plan financier's service word outside the holder's names still takes the credit out.
    holder = "CONTOSO AUTO RECOVERY LLC"
    service = ("NEXTGEAR CAPITAL REPO FEE 1FAKE0000000000001 CONTOSO AUTO RECOVERY", 475.0)
    record = _records([(WESTLAKE_PAYABLES.format(holder=holder), 3150.0), service], holder=holder)[0]
    assert _q7_reading(record) == (*LENDER_SERVICE, "unverified_deposit", "lender_paid_for_services", None)
    for form, read in (("FLOORPLANINT", True), ("FLOORPLANPAYOFF", True), ("FLOORPLANXPRESS", True),
                       ("FLOORPLANADV", True), ("FLOORPLANNER", False), ("FLOORPLANNERS", False),
                       ("FLOOR PLANKS", False), ("FLOORPLANK", False), ("FLOOR PLANER", False)):
        assert bool(true_revenue._FLOOR_PLAN_FORM.search(form)) is read, form


def test_q9_c_the_reason_is_a_counted_reason_of_the_one_reason_table_right_after_factoring_payout():
    from analysis.true_revenue import words

    assert words.LENDER_PAID_FOR_SERVICES == "lender_paid_for_services"
    assert REVENUE_TIER_REASONS["lender_paid_for_services"] == ("counted_flagged", "Lender paid for services")
    codes = list(REVENUE_TIER_REASONS)
    assert codes[codes.index("factoring_payout") + 1] == "lender_paid_for_services"
