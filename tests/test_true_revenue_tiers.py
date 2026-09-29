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
    # §15, §19 OQ4 (review I6a): the deferred items stay counted and flagged until the owner rules.
    assert _tier(_one(text, 700.0)) == ("counted_flagged", "named_payer_one_off")
    repeated = _records([(text + " CCD", 700.0), (text.replace("ID:1", "ID:2") + " CCD", 710.0)])
    assert {record.revenue_classification for record in repeated} == {"unverified_deposit"}


def test_a_healthcare_payer_s_bare_x12_trace_stays_counted():
    # §7.7: a bare X12 TRN*1* with no entry description is out (counted and flagged); with an entry it verifies.
    assert _tier(_one("ACH CREDIT AETNA TRN*1*123456789*1234567890", 700.0)) == ("counted_flagged",
                                                                                  "named_payer_one_off")
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


@pytest.mark.xfail(strict=True, reason=(
    "Pre-existing on 167c83d, outside pass 7: §7.5's payer remittance (payer_remittance_descriptor) verifies it "
    "before pass 7, as its veto reads no platform name; pass 7 never demotes a verified row. Awaits a ruling."
))
def test_schwab_s_accounts_payable_wording_stays_held_by_the_platform_list():
    assert _tier(_one("CHARLES SCHWAB & CO INC DES:PAYABLES ID:1", 3000.0)) == (
        "excluded_pending_review", "non_sale_purpose")


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
