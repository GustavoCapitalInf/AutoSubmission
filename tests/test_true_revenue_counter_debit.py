"""Audit fix batch B4 (true revenue spec §8.1 T3, §7.5 pass 6, §20): the counter-debit holds. payer_also_debited
holds a payer the statement also debits only when that debit can be circular money (an own account, an affiliate or a funder
that collects): the bank's own receiving fee, a processor's own fee on its settlements and a bill the holder pays
never hold (I02); payer_debited_as_lender reads a funder's name glued, cut or spaced (I22, I38); a payroll provider's
tax-service credit is the holder's own impound money coming back (I56). Fabricated rows only, in the banks' printed
formats; public names only where a registry lists them (Square, Forward Financing) or a bank prints its own name."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "NORTHWIND LABS INC"


def _records(rows, *, holder: str | None = HOLDER, bank: str | None = None, days=None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{(days[index] if days else index + 2):02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _credits(records):
    return [record for record in records if record.amount > 0]


def _reading(record):
    return record.revenue_classification, record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method


def _same_as_without(rows, debits, **kwargs):
    """The credits read with the debits, and without them (the control)."""
    return ([_reading(record) for record in _credits(_records([*rows, *debits], **kwargs))],
            [_reading(record) for record in _credits(_records(rows, **kwargs))])


# I02 (a): the bank's own receiving fee, which reprints the sender's name.

RBC_WIRE = "FUNDS TRANSFER CREDIT TT CONTOSO PHARMA INC"


def test_rbc_repeat_company_wires_verify_beside_the_bank_s_receiving_fee():
    rows = [(RBC_WIRE, 25000.0), ("FUNDS TRANSFER FEE TT CONTOSO PHARMA INC", -17.0),
            (RBC_WIRE, 26000.0), ("FUNDS TRANSFER FEE TT CONTOSO PHARMA INC", -17.0)]
    credits = _credits(_records(rows, bank="Royal Bank of Canada"))
    assert [(record.revenue_tier, record.revenue_match_method) for record in credits] == [
        ("verified", "repeat_wire_sender"), ("verified", "repeat_wire_sender")]


@pytest.mark.parametrize("fee", [
    "FUNDS TRANSFER FEE TT CONTOSO PHARMA INC",
    "WIRE TRANSFER FEE FROM CONTOSO PHARMA INC",
    "WIRE TRANSFER FEE CONTOSO PHARMA INC 123456",
    "INCOMING WIRE FEE CONTOSO PHARMA INC",
    "DOMESTIC INCOMING WIRE FEE CONTOSO PHARMA INC",
    "WIRE FEE CONTOSO PHARMA INC",
    "WIRE FEE WIRE FEE 1234567890123456 ORG CONTOSO PHARMA INC",
])
def test_a_receiving_fee_never_holds_the_wire_it_names(fee):
    with_fee, control = _same_as_without([(RBC_WIRE, 25000.0)], [(fee, -17.0)], bank="Royal Bank of Canada")
    assert with_fee == control == [("unverified_deposit", "counted_flagged", "wire_named_sender",
                                     "unidentified_posted_credit")]


@pytest.mark.parametrize("fee", [
    "WIRE FEE FOR WIRE TRANSFER TO CONTOSO PHARMA INC",
    "OUTGOING WIRE FEE CONTOSO PHARMA INC",
    "WIRE FEE WIRE FEE 1234567890123456 BNF CONTOSO PHARMA INC",
])
def test_the_fee_for_the_holder_s_own_wire_to_the_payer_still_holds_it(fee):
    # The bank's fee for an outgoing wire names the beneficiary: the holder sent the payer money.
    credits = _credits(_records([(RBC_WIRE, 25000.0), (fee, -17.0)], bank="Royal Bank of Canada"))
    assert (credits[0].revenue_tier, credits[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


WIRE_IN = "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:{orig} ID:99 SND BK:SAMPLE BANK ID:1"
WIRE_OUT = "WIRE TYPE:WIRE OUT DATE:540305 TIME:1200 ET TRN:{n} SERVICE REF:1 BNF:{orig} ID:99"


def test_circular_money_stays_held():
    # Controls: 20,000 back from a company the holder sends 20,000, by transfer or by wire.
    transfer = _records([("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:1", 20000.0),
                         ("ONLINE TRANSFER TO NORTHWIND HOLDINGS LLC REF 1", -20000.0)], holder="CONTOSO BAKERY LLC")
    wires = _records([(WIRE_IN.format(n=1, orig="NORTHWIND HOLDINGS LLC"), 20000.0),
                      (WIRE_OUT.format(n=2, orig="NORTHWIND HOLDINGS LLC"), -20000.0)], holder="CONTOSO BAKERY LLC")
    for records in (transfer, wires):
        assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                             "payer_also_debited")


# I02 (b): a processor's own fee, discount, chargeback, adjustment or returns debit beside its settlements.

PAYOUT = "FABRIKAM PAY DES:PAYOUT ID:MID 1 INDN:NORTHWIND LABS CO ID:1234567890 CCD"
PAYOUTS = [(PAYOUT, amount) for amount in (2215.0, 1985.0, 2415.0, 2055.0)]


@pytest.mark.parametrize("fee", [
    "FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD",
    "FABRIKAM PAY DES:DISCOUNT ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD",
    "FABRIKAM PAY DES:CHBK ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD",
    "FABRIKAM PAY DES:ADJ ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD",
    "FABRIKAM PAY DES:RETURNS ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD",
    "FABRIKAM PAY MERCH FEE 123456 NORTHWIND LABS",
])
def test_an_unregistered_processor_s_own_fee_never_holds_its_settlements(fee):
    with_fee, control = _same_as_without(PAYOUTS, [(fee, -96.0)])
    assert with_fee == control
    assert {reading[3] for reading in with_fee} == {"named_payer_repeats"}


@pytest.mark.parametrize(("entry", "reading"), [
    ("DES:DEPOSIT ID:MID 1", "named_payer_repeats"),      # MID alone marks the settlement
    ("DES:SETTLEMENT ID:1", "named_payer_purpose_refused"),  # SETTLEMENT alone (Q6 refuses the word as proof)
    ("DES:STLMT ID:1", None),
])
def test_each_settlement_word_spares_the_processor_s_fee(entry, reading):
    rows = [(f"FABRIKAM PAY {entry} INDN:NORTHWIND LABS CO ID:1234567890 CCD", amount)
            for amount in (2215.0, 1985.0, 2415.0, 2055.0)]
    with_fee, control = _same_as_without(
        rows, [("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -96.0)])
    assert with_fee == control
    assert all(item[2] != "payer_also_debited" for item in with_fee)
    if reading == "named_payer_repeats":
        assert {item[3] for item in with_fee} == {reading}
    elif reading is not None:
        assert {item[2] for item in with_fee} == {reading}


def test_the_brief_s_settlement_rows_read_as_they_do_without_the_fee():
    settlements = [("FABRIKAM PAY SETTLEMENT MID 1", amount) for amount in (2215.0, 1985.0, 2415.0, 2055.0)]
    with_fee, control = _same_as_without(settlements, [("FABRIKAM PAY FEE", -96.0)])
    assert with_fee == control
    assert {reading[1] for reading in with_fee} == {"counted_flagged"}


def test_merchant_services_rtp_settlements_are_counted_beside_its_merch_fee():
    rows = [("RTP CREDIT FROM MERCHANT SERVI MID 1", 2215.0), ("RTP CREDIT FROM MERCHANT SERVI MID 1", 1985.0)]
    credits = _credits(_records([*rows, ("MERCHANT SERVICE MERCH FEE", -96.0)]))
    assert {record.revenue_tier for record in credits} == {"counted_flagged"}


def test_a_processor_fee_still_holds_a_credit_that_prints_no_settlement_wording():
    # A fee reversal, a reserve release or a dispute credit is no settlement: the fee debit keeps holding it.
    records = _records([("FABRIKAM PAY DES:CREDIT ID:1 INDN:NORTHWIND LABS CO ID:1234567890 CCD", 312.0),
                        ("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -45.0)])
    assert records[0].revenue_tier_reason == "payer_also_debited"


def test_a_fee_or_bill_debit_for_the_credit_s_own_amount_still_holds_it():
    # The credit undoes the debit (a refunded bill, a reversed fee).
    cable = _records([("CONTOSO CABLE DES:PAYMENT ID:1", 475.0), ("CONTOSO CABLE DES:AUTOPAY ID:2", -475.0)])
    assert cable[0].revenue_tier_reason == "payer_also_debited"
    payout = _records([(PAYOUT, 390.0), ("FABRIKAM PAY DES:ADJ ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -390.0)])
    assert payout[0].revenue_tier_reason == "payer_also_debited"
    # A bank's own fee reversal printed with the same amount (its words read as 5.6 read them).
    fee = _records([("SERVICE CHARGE DISCOUNT", 16.0),
                    ("SERVICE CHARGE CAPPED MONTHLY FEE 03 54 RECORD KEEPING", -16.0)])
    assert fee[0].revenue_tier_reason == "payer_also_debited"


def test_recurring_same_amount_fee_or_bill_debits_still_hold():
    fees = _records([*PAYOUTS, *[("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -45.0)] * 2])
    assert {record.revenue_tier_reason for record in _credits(fees)} == {"payer_also_debited"}
    bills = _records([("CONTOSO UTILITIES DES:PAYMENT ID:1", 17500.0), *[("BILL PAY CONTOSO UTILITIES", -94.0)] * 2])
    assert bills[0].revenue_tier_reason == "payer_also_debited"


def test_a_registered_processor_s_settlement_beside_its_fee_stays_verified():
    rows = [("SQUARE INC DES:SQ540302 ID:1 INDN:CONTOSO BAKERY LLC CO ID:9424300002 CCD", 1500.0),
            ("SQUARE INC DES:SQ540303 ID:2 INDN:CONTOSO BAKERY LLC CO ID:9424300002 CCD", 1600.0)]
    with_fee, control = _same_as_without(
        rows, [("SQUARE INC DES:FEE ID:3 INDN:CONTOSO BAKERY LLC CO ID:9424300002 CCD", -45.0)],
        holder="CONTOSO BAKERY LLC")
    assert with_fee == control
    assert {reading[1] for reading in with_fee} == {"verified"}


# I02 (c): a bill the holder pays to the payer.

@pytest.mark.parametrize("bill", [
    "BILL PAY CONTOSO SUPPLY",
    "BILL PAYMENT CONTOSO SUPPLY",
    "BILLPAY CONTOSO SUPPLY",
    "BILL PAID CONTOSO SUPPLY INCO",
    "CONTOSO SUPPLY DES:EBPP PMT ID:2",
    "CONTOSO SUPPLY DES:AUTOPAY ID:2",
    "ORIG CO NAME:CONTOSO SUPPLY ORIG ID:1 DESC DATE:540302 CO ENTRY DESCR:AUTOPAYBUSSEC:PPD TRACE#:1",
    "CONTOSO SUPPLY DES:UTIL PMT ID:2",
    "CONTOSO SUPPLY DES:CABLE SVCS ID:2",
    "CONTOSO SUPPLY DES:WIRELESS ID:2",
    "CONTOSO SUPPLY DES:TELECOM ID:2",
    "CONTOSO SUPPLY DES:VOIP ID:2",
    "CONTOSO SUPPLY DES:SUBSCRIPTION ID:2",
    "BILL PAY CONTOSO UTILITIES",
    "UTILITY BILL PMT CONTOSO UTILITIES",
])
def test_a_bill_the_holder_pays_never_holds_the_payer(bill):
    payer = "CONTOSO UTILITIES" if "UTILITIES" in bill else "CONTOSO SUPPLY"
    with_bill, control = _same_as_without([(f"{payer} DES:PAYMENT ID:1", 17500.0)], [(bill, -94.0)])
    assert with_bill == control
    assert with_bill[0][1] == "counted_flagged"


def test_an_ap_remittance_from_a_utility_the_holder_pays_stays_verified():
    # Pass 6 reads the same debit kinds as pass 7.
    rows = [("CONTOSO UTILITIES DES:VENDOR PAY ID:1", 17500.0), ("CONTOSO UTILITIES DES:VENDOR PAY ID:2", 16400.0)]
    credits = _credits(_records([*rows, ("BILL PAY CONTOSO UTILITIES", -94.0)]))
    assert [(record.revenue_tier, record.revenue_match_method) for record in credits] == [
        ("verified", "payer_remittance_descriptor"), ("verified", "payer_remittance_descriptor")]


def test_an_ap_remittance_from_a_payer_the_holder_pays_by_ach_is_still_demoted():
    records = _records([("CONTOSO SUPPLY DES:VENDOR PAY ID:1", 5000.0), ("CONTOSO SUPPLY DES:INVOICE ID:2", -250.0)])
    assert (records[0].revenue_match_method, records[0].revenue_tier_reason) == (
        "payer_remittance_with_counter_debit", "payer_also_debited")


@pytest.mark.parametrize("debit", [
    "FABRIKAM LIFE DES:INS PREM ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 PPD",
    "FABRIKAM LIFE DES:AUTOPAY ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 PPD",
    "BILL PAY FABRIKAM LIFE",
])
def test_an_insurer_s_credit_beside_its_premium_or_bill_stays_held(debit):
    # Q6: insurers never count. A payer that reads as an insurer (INS, INSUR...) keeps the bill exclusion off.
    records = _records([("FABRIKAM LIFE DES:FL INS ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 PPD", 1500.0), (debit, -105.0)],
                       holder="CONTOSO BAKERY LLC")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


# I02: generic words and banks' names that let unrelated payers match.

@pytest.mark.parametrize("word", [
    "MERCHANT", "UTILITIES", "EXPRESS", "INCOME", "PAIEMENT", "POSTED", "SERVICE", "SERVICES", "TRSFR",
    "CHASE", "TRUIST", "BLUEVINE",
])
def test_the_counter_debit_generic_words(word):
    assert word in tc._COUNTER_DEBIT_GENERIC_WORDS


@pytest.mark.parametrize(("rows", "bank"), [
    # '<initials> EXPRESS INC' against American Express.
    ([("ZELLE PAYMENT FROM XY EXPRESS INC CONF 1", 2000.0),
      ("AMERICAN EXPRESS DES:ACH PMT ID:1 INDN:NORTHWIND LABS CO ID:1 CCD", -800.0)], None),
    # Two companies sharing a generic word.
    ([("XYZ UTILITIES SO 1234567", 17500.0), ("ABC UTILITIES DES:INVOICE ID:1", -900.0)], None),
    ([("INSTANT PMT FROM MERCHANT SERVICES ON 03 02 REF 123P1ABCDE4 MID1234567890", 2215.0),
      ("MERCHANT SERVICE MERCH ADJ 123456 1234567890 NORTHWIND LABS", -96.0)], None),
    # A bank's own online-payment channel against the holder's card payment to the bank.
    ([("ORIG CO NAME:CHASE ONLINE ORIG ID:1234567890 DESC DATE:MAR 02 CO ENTRY DESCR:ONLINE PMTSEC:CTX TRACE#:1 "
       "EED:540302 IND ID:1 IND NAME:NORTHWIND LABS", 2000.0),
      ("PAYMENT TO CHASE CARD ENDING IN 1234", -800.0)], "Chase"),
    # A bank's merchant-services deposit against the holder's ATM withdrawal there.
    ([("DEPOSIT TRUIST MERCHANT CONTOSO DELI CUSTOMER ID 123456789012345", 2000.0),
      ("TRUIST ATM CASH WITHDRAWAL 03 02 54 1234 SAMPLEVILLE BRANCH 1", -200.0)], "Truist"),
])
def test_a_generic_word_or_a_bank_s_name_never_matches_unrelated_payers(rows, bank):
    records = _records(rows, bank=bank)
    assert records[0].revenue_tier == "counted_flagged", records[0].revenue_tier_reason


def test_a_payer_paid_back_by_transfer_keeps_its_hold_whatever_its_words():
    # Guard: a transfer, wire or person-to-person debit matches as 5.6 read it, a generic word included.
    records = _records([("ONLINE TRANSFER FROM XY EXPRESS INC REF 1", 2000.0),
                        ("ONLINE TRANSFER TO XY EXPRESS INC REF 2", -800.0)])
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


def test_a_payer_debited_as_a_lender_keeps_its_hold_whatever_its_words():
    rows = [("EXPRESS NORTHWIND DES:PAYMENT ID:1", 9000.0), *[("EXPRESS NORTHWIND DES:DEBIT ID:2", -300.0)] * 4]
    records = _records(rows, days=[2, 9, 16, 23, 30])
    assert {record.classification for record in records[1:]} == {"potential_lender"}
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_debited_as_lender")


# I22: a funder's name cut, glued or spelled with a reference.

WEEKLY = [2, 9, 16, 23, 30]


def test_a_funder_whose_debits_glue_its_name_is_held():
    wire = _records([("WT FED 01234 SAMPLE BANK ORG CONTOSO UT LLC SRF 123 TRN 456 RFB NORTHWIND", 9000.0),
                     *[("BUSINESS TO BUSINESS ACH DEBIT CONTOSOFUNDING ACHPAYMENT 123456 W123 NORTHWIND LABS",
                        -450.0)] * 4], days=WEEKLY)
    assert (wire[0].revenue_tier, wire[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                   "payer_debited_as_lender")
    deposit = _records([("DEPOSIT WIRE IN FABRIKAM VENTURE", 5000.0),
                        *[("ACH WITHDRAWAL FABRIKAMVENTUREHO ACHPAYMENT GV1234 NORTHWIND LABS", -1600.0)] * 4],
                       days=WEEKLY)
    assert {record.classification for record in deposit[1:]} == {"potential_lender"}
    assert (deposit[0].revenue_tier, deposit[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_debited_as_lender")


def test_a_funding_whose_name_carries_a_glued_reference_is_held():
    # Forward Financing (a registry lender): its funding prints FORWARDFINUSA<digits>, its debits FORWARD FIN USA.
    rows = [("ORIG CO NAME:FORWARDFINUSA1 ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENTS SEC:CCD TRACE#:1 "
             "EED:540302 IND ID: IND NAME:NORTHWIND LABS", 9000.0),
            *[("ORIG CO NAME:FORWARD FIN USA ORIG ID:RPP1234567 DESC DATE:540309 CO ENTRY DESCR:FF SEC:CCD TRACE#:1 "
               "EED:540309 IND ID: IND NAME:NORTHWIND LABS", -300.0)] * 4]
    records = _records(rows, days=WEEKLY)
    assert {record.classification for record in records[1:]} == {"confirmed_lender"}
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_debited_as_lender")


def test_a_customer_whose_name_only_starts_like_a_funder_is_not_held():
    # The prefix must run on into the payer's next word or a financing root (FABRIK + AM is neither).
    records = _records([("FABRIK EVENTS LLC DES:PAYMENT ID:1", 5000.0), *[("FABRIKAM DES:DEBIT ID:2", -300.0)] * 4],
                       days=WEEKLY)
    assert (records[0].revenue_tier, records[0].revenue_match_method) == ("verified", "named_payer_company_form")


def test_a_verified_card_settlement_never_moves_beside_a_funder_sharing_its_prefix():
    rows = [("MERCH BNKCD DEPOSIT 123456", 2500.0), ("MERCH BNKCD DEPOSIT 123457", 2600.0),
            *[("MERCHFUNDING DES:DEBIT ID:2", -300.0)] * 4]
    records = _records(rows, days=[2, 3, 9, 16, 23, 30])
    assert [(record.revenue_tier, record.revenue_match_method) for record in records[:2]] == [
        ("verified", "operating_income_descriptor")] * 2


def test_the_prefix_never_demotes_an_ap_remittance_in_pass_6():
    # Pass 6 demotes a verified row: it compares whole words (and glued forms), never a prefix.
    records = _records([("CONTOSO UT LLC DES:VENDOR PAY ID:1", 9000.0),
                        *[("CONTOSOFUNDING DES:DEBIT ID:2", -450.0)] * 4], days=WEEKLY)
    assert records[0].revenue_match_method == "payer_remittance_descriptor"


# I38: a name glued on one side and spaced on the other.

def test_a_glued_name_matches_a_spaced_one_either_way():
    glued_debit = _records([("CONTOSO RIDGE PY01/02/31 *****1234", 150000.0),
                            ("CONTOSORIDGE INSURANCE A 123DD4L", -3000.0)])
    assert (glued_debit[0].revenue_tier, glued_debit[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                                 "payer_also_debited")
    glued_credit = _records([("CONTOSORIDGE DES:PAYMENT ID:1", 15000.0), ("CONTOSO RIDGE DES:INVOICE ID:2", -3000.0)])
    assert glued_credit[0].revenue_tier_reason == "payer_also_debited"


def test_a_debit_whose_name_carries_a_glued_reference_still_names_the_payer():
    # I22: D11 reads 'CONTOSOSUPPLY1' as a reference; with its digits split off the debit names the payer.
    records = _records([("CONTOSOSUPPLY DES:PAYMENT ID:1", 5000.0), ("CONTOSOSUPPLY1 DES:INVOICE ID:2", -250.0)])
    assert records[0].revenue_tier_reason == "payer_also_debited"


def test_two_different_names_never_match_through_a_glued_form():
    records = _records([("CONTOSO RIDGE DES:PAYMENT ID:1", 15000.0), ("CONTOSOVALE DES:INVOICE ID:2", -3000.0)])
    assert records[0].revenue_tier == "counted_flagged"


# I56: a payroll provider's tax-service credit is the holder's own impound money coming back.

def test_an_adp_tax_credit_beside_adp_tax_debits_is_held():
    records = _records([("ADP TAX DES:ADP TAX ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", 640.0),
                        ("ADP TAX DES:ADP TAX ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", -2100.0)],
                       holder="CONTOSO BAKERY LLC")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


@pytest.mark.parametrize("credit", [
    "PAYCHEX TPS DES:TAXES ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD",
    "PAYCHEX TPS TAXES 123456 12345678901234X",
    "TAXES PAYCHEX TPS SAMPLE CORP CUSTOMER ID 12345678901234X",
    "ADP TAX DES:ADP TAX ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD",
    "ORIG CO NAME:ADP TAX ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:ADP TAX SEC:CCD TRACE#:1",
    "GUSTO DES:TAX 540302 ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD",
    "INTUIT 12345678 DES:TAX ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD",
    "TAX INTUIT 12345678",
])
def test_a_payroll_provider_s_tax_credit_with_no_matching_debit_is_held_as_non_sale(credit):
    records = _records([(credit, 270.0)], holder="CONTOSO BAKERY LLC")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "non_sale_purpose")


@pytest.mark.parametrize("credit", [
    "NORTHWIND TAX SERVICES LLC DES:PAYMENT ID:1",    # a customer named for taxes is no payroll provider
    "ADP DES:SALES ID:1",                             # no tax entry
])
def test_other_tax_words_and_provider_credits_are_not_read_as_payroll_tax(credit):
    records = _records([(credit, 270.0)], holder="CONTOSO BAKERY LLC")
    assert records[0].revenue_tier_reason != "non_sale_purpose"


def test_a_three_letter_word_other_than_a_payroll_provider_is_still_no_counter_debit_word():
    records = _records([("ABC DES:PAYMENT ID:1", 640.0), ("ABC DES:INVOICE ID:2", -2100.0)],
                       holder="CONTOSO BAKERY LLC")
    assert records[0].revenue_tier == "counted_flagged"


# The readers and the matching, one by one.

@pytest.mark.parametrize(("text", "split"), [
    ("FABRIKAMGROUPINC1 DES REF123", "FABRIKAMGROUPINC 1 DES REF 123"),
    ("FABRIKAMUSA12 PAYMENTS", "FABRIKAMUSA 12 PAYMENTS"),
    ("XXXXXX1234 CONTOSO", "XXXXXX1234 CONTOSO"),      # a masked account number is no name
    ("PY01 02 31", "PY01 02 31"),                      # two letters never make a word
    ("AB12CD CONTOSO", "AB12CD CONTOSO"),              # digits inside a token are a reference
])
def test_a_glued_digit_run_is_split_off_a_name(text, split):
    assert tc._split_glued_digits(text) == split


def test_the_payer_reading_keeps_5_6_s_word_and_adds_the_glued_forms():
    reading = tc.counter_debit_payer_reading("CONTOSO RIDGE HILL")
    assert reading.legacy == "CONTOSO"
    assert reading.keys == {"CONTOSO", "CONTOSORIDGE", "CONTOSORIDGEHILL"}
    generic = tc.counter_debit_payer_reading("XY EXPRESS INC")
    assert (generic.legacy, generic.keys) == ("EXPRESS", frozenset())
    glued = tc.counter_debit_payer_reading("FORWARDFINUSA1 PAYMENTS")
    assert (glued.legacy, glued.keys) == (None, frozenset({"FORWARDFINUSA"}))
    assert tc.counter_debit_payer_reading("ADP TAX").keys == {"ADP", "ADPTAX"}


@pytest.mark.parametrize(("text", "kind"), [
    ("FUNDS TRANSFER FEE TT CONTOSO PHARMA INC", "receiving_fee"),
    ("WIRE TRANS SVC CHARGE SEQUENCE 123 CONTOSO", "receiving_fee"),
    ("SERVICE CHARGES INCOMING WIRE FEE CONTOSO", "receiving_fee"),
    ("WIRE FEE FOR WIRE TRANSFER TO CONTOSO PHARMA INC", "circular"),
    ("OUTGOING WIRE FEE CONTOSO PHARMA INC", "circular"),
    ("ONLINE TRANSFER TO CONTOSO SUPPLY LLC REF 1", "circular"),
    ("ZELLE PAYMENT TO CONTOSO SUPPLY CONF 1", "circular"),
    ("CONTOSO BC 03 02 1234 TO CHKG 5678", "circular"),
    ("CONTOSO IFI DDA TO DDA REF1", "circular"),
    ("FABRIKAM PAY DES:DISCOUNT ID:2", "processor_fee"),
    ("FABRIKAM PAY MERCH CHBK 123", "processor_fee"),
    ("BILL PAID CONTOSO UTILITIES INCO", "bill"),
    ("CONTOSO CABLE DES:CABLE SVCS ID:1", "bill"),
    ("CONTOSO UTILITIES DES:EBPP PMT ID:2", "bill"),
    ("CONTOSO SUPPLY DES:INVOICE ID:2", "other"),
    ("CONTOSO MOTORS DES:AUTO PAYMENT ID:2", "other"),  # a car payment is no autopay bill
    ("FABRIKAM LIFE DES:INS PREM ID:2", "other"),
])
def test_the_debit_kinds(text, kind):
    from analysis.true_revenue import _counter_debit_kind

    assert _counter_debit_kind(text) == kind


def _counter(legacy, words, *, entity=None, cents=100000, settlement=False, insurer=False):
    from analysis.true_revenue import CounterCredit

    return CounterCredit(tc._counter_debit_reading(legacy, [words]), cents, entity, settlement, insurer)


def _debits(*, lender=(), other=()):
    from analysis.true_revenue import CounterDebits, _CounterDebit

    return CounterDebits(
        tuple(_CounterDebit(tc._counter_debit_reading(legacy, [words]), "lender", 30000, entity, False)
              for legacy, words, entity in lender),
        tuple(_CounterDebit(tc._counter_debit_reading(legacy, [words]), kind, cents, None, recurring)
              for legacy, words, kind, cents, recurring in other),
    )


def test_a_lender_debit_is_compared_by_registry_entity_when_both_sides_name_one():
    from analysis.true_revenue import debited_as_lender

    # One entity, two spellings that share no word: held.
    same = _debits(lender=[("FABFUND", ["FABFUND", "CAPITAL"], "Sample Lender")])
    assert debited_as_lender(_counter("NORTHWIND", ["NORTHWIND", "ADVANCE"], entity="Sample Lender"), same,
                             prefix=False)
    # Two entities whose words share a prefix that would otherwise hold: not held.
    other = _debits(lender=[("CONTOSOFUNDING", ["CONTOSOFUNDING"], "Second Lender")])
    assert not debited_as_lender(_counter("CONTOSO", ["CONTOSO"], entity="First Lender"), other, prefix=True)
    assert debited_as_lender(_counter("CONTOSO", ["CONTOSO"]), other, prefix=True)
    # 5.6's first-word match still holds whatever the entities.
    assert debited_as_lender(_counter("CONTOSO", ["CONTOSO"], entity="First Lender"),
                             _debits(lender=[("CONTOSO", ["CONTOSO"], "Second Lender")]), prefix=False)


def test_the_prefix_reads_only_with_the_pass_7_switch():
    from analysis.true_revenue import debited_as_lender

    debits = _debits(lender=[("CONTOSOFUNDING", ["CONTOSOFUNDING"], None)])
    assert debited_as_lender(_counter("CONTOSO", ["CONTOSO"]), debits, prefix=True)
    assert not debited_as_lender(_counter("CONTOSO", ["CONTOSO"]), debits, prefix=False)
    # Too short a prefix (four letters) never reads.
    assert not debited_as_lender(_counter("CONT", ["CONT"]), _debits(lender=[("CONTFUNDING", ["CONTFUNDING"], None)]),
                                 prefix=True)


def test_also_debited_reads_each_kind():
    from analysis.true_revenue import also_debited

    def held(kind, *, cents=2500, recurring=False, **credit):
        return also_debited(_counter("CONTOSO", ["CONTOSO"], **credit),
                            _debits(other=[("CONTOSO", ["CONTOSO"], kind, cents, recurring)]))

    assert not held("receiving_fee")
    assert not held("receiving_fee", cents=100000)
    assert held("circular") and held("other")
    assert held("processor_fee") and not held("processor_fee", settlement=True)
    assert held("processor_fee", settlement=True, cents=100000)
    assert held("processor_fee", settlement=True, recurring=True)
    assert not held("bill") and held("bill", insurer=True)
    assert held("bill", cents=100000) and held("bill", recurring=True)
    # A generic word: a transfer matches it as 5.6 read it, any other debit only for the credit's own amount.
    generic = _counter("EXPRESS", ["XY", "EXPRESS", "INC"])
    for kind, cents, expected in (("circular", 2500, True), ("other", 2500, False), ("other", 100000, True),
                                  ("bill", 100000, True)):
        debits = _debits(other=[("EXPRESS", ["AMERICAN", "EXPRESS"], kind, cents, False)])
        assert also_debited(generic, debits) is expected, (kind, cents)
