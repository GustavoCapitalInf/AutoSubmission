"""Audit fix batch B4 (true revenue spec §8.1 T3, §7.5 pass 6, §20): the counter-debit holds. payer_also_debited
holds a payer the statement also debits only when that debit can be circular money (an own account, an affiliate or a funder
that collects): the bank's own receiving fee, a processor's own fee on its settlements and a bill the holder pays
never hold (I02); payer_debited_as_lender reads a funder's name glued, cut or spaced (I22, I38); a payroll provider's
tax-service credit is the holder's own impound money coming back (I56). Fabricated rows only, in the banks' printed
formats; public names only where a registry lists them (Square, Forward Financing) or a bank prints its own name."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.classification import counter_debit_reading
from analysis.classification import record as classification_record
from analysis.descriptor import payer as descriptor_payer
from analysis.descriptor import lexical
from analysis import description_text
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from tests.zelle_reading import rules_reading

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


def test_recurring_same_amount_bill_debits_still_hold():
    # A bill paid at one amount again and again can be a collector's draw: it keeps holding.
    bills = _records([("CONTOSO UTILITIES DES:PAYMENT ID:1", 17500.0), *[("BILL PAY CONTOSO UTILITIES", -94.0)] * 2])
    assert bills[0].revenue_tier_reason == "payer_also_debited"
    weekly = _records([("CONTOSO UTILITIES DES:PAYMENT ID:1", 17500.0),
                       *[("CONTOSO UTILITIES DES:AUTOPAY ID:2", -94.0)] * 3], days=[2, 9, 16, 23])
    assert weekly[0].revenue_tier_reason == "payer_also_debited"


@pytest.mark.parametrize("fees", [
    [("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -45.0)] * 2,
    [("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", -45.0)] * 4,
])
def test_a_processor_s_fixed_fee_at_one_amount_never_holds_its_settlements(fees):
    # Review round 1 (finding 4; standard §4.2): a processor's fixed monthly or per-batch fee posts at one amount, so
    # printed twice in a two-month statement (or once a batch) it is still the processor's own fee.
    with_fees, control = _same_as_without(PAYOUTS, fees)
    assert with_fees == control
    assert {reading[3] for reading in with_fees} == {"named_payer_repeats"}


def test_the_brief_s_settlements_beside_a_fee_printed_twice_read_as_they_do_without_it():
    settlements = [("FABRIKAM PAY SETTLEMENT MID 1", amount) for amount in (2215.0, 1985.0, 2415.0, 2055.0)]
    with_fees, control = _same_as_without(settlements, [("FABRIKAM PAY FEE", -96.0)] * 2)
    assert with_fees == control
    assert {reading[1] for reading in with_fees} == {"counted_flagged"}


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


@pytest.mark.parametrize("provider", ["ADP", "PAYCHEX", "FABRIKAM"])
def test_a_payroll_provider_s_remittance_beside_the_holder_s_fee_to_it_reads_as_any_payer_s(provider):
    # Review round 1 (finding 5): ADP is a counter-debit word like PAYCHEX and any four-letter name, so its
    # remittance beside the holder's payroll fee to it is demoted as theirs always was (no settlement wording).
    records = _records([(f"{provider} INC DES:VENDOR PAY ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", 5000.0),
                        (f"{provider} PAYROLL FEES DES:{provider} FEES ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", -85.0)],
                       holder="CONTOSO BAKERY LLC")
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


# Review round 1 (finding 1): the debit's kind is read without its receiver field's value, the holder's own name.

@pytest.mark.parametrize("holder", [
    "CONTOSO CABLE LLC", "CONTOSO UTILITY SERVICES INC", "CONTOSO WIRELESS LLC", "CONTOSO TELECOM INC",
    "CONTOSO VOIP LLC", "CONTOSO SUBSCRIPTIONS LLC", "CONTOSO AUTOPAY LLC",
])
def test_a_holder_named_for_a_bill_word_never_turns_an_affiliate_s_debit_into_a_bill(holder):
    rows = [(f"NORTHWIND HOLDINGS LLC DES:PAYMENT ID:1 INDN:{holder} CO ID:1 CCD", 20000.0),
            (f"NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:{holder} CO ID:1 CCD", -5000.0)]
    records = _records(rows, holder=holder)
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


def test_a_holder_named_for_a_bill_word_in_chase_s_ind_name_field_keeps_the_affiliate_held():
    rows = [("ORIG CO NAME:NORTHWIND HOLDINGS ORIG ID:1 DESC DATE:540302 CO ENTRY DESCR:PAYMENT SEC:CCD TRACE#:1 "
             "EED:540302 IND ID:1 IND NAME:CONTOSO CABLE LLC", 20000.0),
            ("ORIG CO NAME:NORTHWIND HOLDINGS ORIG ID:1 DESC DATE:540303 CO ENTRY DESCR:PAYMENT SEC:CCD TRACE#:1 "
             "EED:540303 IND ID:1 IND NAME:CONTOSO CABLE LLC", -5000.0)]
    records = _records(rows, holder="CONTOSO CABLE LLC")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


def test_a_funder_collecting_from_a_holder_named_for_a_bill_word_keeps_its_funding_held():
    rows = [("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:1 INDN:CONTOSO CABLE LLC CO ID:1 CCD", 20000.0),
            *[("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO CABLE LLC CO ID:1 CCD", -500.0 - cents)
              for cents in range(3)]]
    records = _records(rows, holder="CONTOSO CABLE LLC")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


@pytest.mark.parametrize("holder", ["CONTOSO RETURNS LLC", "CONTOSO FEES LLC", "CONTOSO ADJ INC", "CONTOSO DISC INC"])
def test_a_holder_named_for_a_fee_word_never_turns_an_affiliate_s_debit_into_a_processor_fee(holder):
    # Audit round 2, R2-B02 (R01): a one-off debit of the payer's no longer holds a settlement-worded credit whatever
    # its kind, so the affiliate's debit recurs at one amount here: a recurring 'other' debit holds the settlement,
    # while a recurring processor's fee would not.
    rows = [(f"NORTHWIND HOLDINGS LLC DES:SETTLEMENT ID:1 INDN:{holder} CO ID:1 CCD", 20000.0),
            *[(f"NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:{holder} CO ID:1 CCD", -5000.0)] * 2]
    records = _records(rows, holder=holder)
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("excluded_pending_review",
                                                                         "payer_also_debited")


@pytest.mark.parametrize(("text", "kind"), [
    # The kind word only in the receiver field's value (the holder's name) reads no kind.
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO CABLE LLC CO ID:1 CCD", "other"),
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO UTILITY SERVICES INC CO ID:1 CCD", "other"),
    ("ORIG CO NAME:NORTHWIND HOLDINGS ORIG ID:1 DESC DATE:540303 CO ENTRY DESCR:PAYMENT SEC:CCD TRACE#:1 "
     "EED:540303 IND ID:1 IND NAME:CONTOSO TELECOM INC", "other"),
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO RETURNS LLC CO ID:1 CCD", "other"),
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 RECEIVER NAME:CONTOSO FEES LLC CO ID:1 CCD", "other"),
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO INCOMING WIRE FEES LLC CO ID:1 CCD", "other"),
    ("NORTHWIND HOLDINGS LLC DES:PAYMENT ID:2 INDN:CONTOSO TRANSFER LLC CO ID:1 CCD", "other"),
    # The kind word in the payer's own fields, or in the addenda after the receiver, still reads.
    ("FABRIKAM PAY DES:FEE ID:2 INDN:NORTHWIND LABS CO ID:1234567890 CCD", "processor_fee"),
    ("CONTOSO SUPPLY DES:CABLE SVCS ID:2 INDN:NORTHWIND LABS CO ID:1 CCD", "bill"),
    ("NORTHWIND HOLDINGS DES:PAYMENT ID:2 INDN:CONTOSO BAKERY CO ID:1 CCD PMT INFO:CABLE SVCS", "bill"),
    ("NORTHWIND HOLDINGS DES:TRANSFER ID:2 INDN:CONTOSO BAKERY CO ID:1 CCD", "circular"),
])
def test_the_debit_kind_is_read_without_the_receiver_s_value(text, kind):
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(text) == kind


# I02: generic words and banks' names that let unrelated payers match.

@pytest.mark.parametrize("word", [
    "MERCHANT", "UTILITIES", "EXPRESS", "INCOME", "PAIEMENT", "POSTED", "SERVICE", "SERVICES", "TRSFR",
    "CHASE", "TRUIST", "BLUEVINE",
])
def test_the_counter_debit_generic_words(word):
    assert word in counter_debit_reading._COUNTER_DEBIT_GENERIC_WORDS


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
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    assert rules_reading(records[0])[0] == "counted_flagged", records[0].revenue_tier_reason


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
    # Audit B6 (I08): the ledger's FORWARDFINUSA alias, read with the reference glued on, names the funding first, so
    # it is the funder's financing proceeds (non_revenue), no longer only held beside its debits.
    rows = [("ORIG CO NAME:FORWARDFINUSA1 ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENTS SEC:CCD TRACE#:1 "
             "EED:540302 IND ID: IND NAME:NORTHWIND LABS", 9000.0),
            *[("ORIG CO NAME:FORWARD FIN USA ORIG ID:RPP1234567 DESC DATE:540309 CO ENTRY DESCR:FF SEC:CCD TRACE#:1 "
               "EED:540309 IND ID: IND NAME:NORTHWIND LABS", -300.0)] * 4]
    records = _records(rows, days=WEEKLY)
    assert {record.classification for record in records[1:]} == {"confirmed_lender"}
    assert (records[0].revenue_tier, records[0].revenue_match_method) == ("non_revenue", "financing_proceeds_credit")


@pytest.mark.parametrize("credit", [
    # Audit round 2, R2-B08 (R47 (b); Q6 "lenders never count", standard C1): Forward's run-together name with a digit
    # run and a letter tail glued on, on Bank of America's and Chase's layouts, is its financing proceeds too.
    "FORWARDFINUSA1X DES:PAYMENTS ID:ACH123456 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "FORWARDFINUSA12AB DES:PAYMENTS ID:ACH123456 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "ORIG CO NAME:FORWARDFINUSA1X ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENTS SEC:CCD TRACE#:1 "
    "EED:540302 IND ID: IND NAME:NORTHWIND LABS",
])
def test_r47_a_funding_whose_glued_reference_ends_in_letters_is_financing_proceeds(credit):
    debit = ("ORIG CO NAME:FORWARD FIN USA ORIG ID:RPP1234567 DESC DATE:540309 CO ENTRY DESCR:FF SEC:CCD TRACE#:1 "
             "EED:540309 IND ID: IND NAME:NORTHWIND LABS")
    for rows in ([(credit, 27000.0), *[(debit, -300.0)] * 4], [(credit, 27000.0)]):
        records = _records(rows, days=WEEKLY[:len(rows)])
        assert (records[0].revenue_tier, records[0].revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
        assert {record.classification for record in records[1:]} <= {"confirmed_lender"}


def test_r47_a_payer_no_alias_names_keeps_its_letter_tail_reading():
    records = _records([("FABRIKAMSUPPLY1X DES:PAYMENTS ID:ACH123456 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
                         2700.0)])
    assert records[0].revenue_tier == "counted_flagged"


def test_an_unregistered_funding_whose_name_carries_a_glued_reference_is_held():
    # The B4 reading the test above pinned, for a funder no alias lists: the credit's glued reference split off, its
    # name matches the lender debits' (a fabricated potential lender, its fixed weekly pulls, D6).
    rows = [("ORIG CO NAME:FABRIKAMFINCO1 ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENTS SEC:CCD TRACE#:1 "
             "EED:540302 IND ID: IND NAME:NORTHWIND LABS", 9000.0),
            *[("ORIG CO NAME:FABRIKAMFINCO ORIG ID:RPP1234567 DESC DATE:540309 CO ENTRY DESCR:DEBIT SEC:CCD TRACE#:1 "
               "EED:540309 IND ID: IND NAME:NORTHWIND LABS", -300.0)] * 4]
    records = _records(rows, days=WEEKLY)
    assert {record.classification for record in records[1:]} == {"potential_lender"}
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


@pytest.mark.parametrize("debit", ["CONTOSOFUNDING DES:DEBIT ID:2", "CONTOSO FUNDING DES:DEBIT ID:2"])
def test_the_funder_prefix_holds_a_q6_payer_before_q6_as_the_spaced_name_does(debit):
    # Review round 1 (finding 3): "for unverified credits only" means a credit no rule verified, as 5.6's exact-word
    # hold reads it: like that hold, the prefix hold comes before Q5 and Q6, so a glued funder name holds a
    # company-form or repeat payer exactly as the spaced name does (the census declares it,
    # q5_q6_held_lender_counter_debit).
    one = _records([("CONTOSO EVENTS LLC DES:PAYMENT ID:1", 5000.0), *[(debit, -300.0)] * 4], days=WEEKLY)
    repeat = _records([("CONTOSO EVENTS DES:PAYMENT ID:1", 5000.0), ("CONTOSO EVENTS DES:PAYMENT ID:3", 4000.0),
                       *[(debit, -300.0)] * 4], days=[2, 3, 9, 16, 23, 30])
    assert {record.classification for record in one[1:]} == {"potential_lender"}
    for record in (one[0], *repeat[:2]):
        assert (record.revenue_tier, record.revenue_tier_reason) == ("excluded_pending_review",
                                                                     "payer_debited_as_lender")


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
    "ACH TAXES 123456 PAYCHEX TPS 12345",   # review round 1: the entry printed before the provider's name
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


@pytest.mark.parametrize("credit", [
    "INTUIT PYMT SOLN DEPOSIT 540302 ABC123 CONTOSO TAX SERVICES LLC",
    "GUSTO CONTRACTOR 540302 ABC123 CONTOSO TAX SERVICES LLC",
    "ADP INC VENDOR PAY 540302 ABC123 CONTOSO TAX SERVICES LLC",
])
def test_a_payroll_provider_paying_a_holder_named_for_taxes_on_a_label_less_row_is_counted(credit):
    # Review round 1 (finding 2): a layout that prints the holder's name inline, with no receiver label, puts the
    # holder's TAX inside the row; the tax word is read on the payer region and the entry fields only.
    records = _records([(credit, 1500.0)], holder="CONTOSO TAX SERVICES LLC")
    assert records[0].revenue_tier_reason != "non_sale_purpose"
    assert records[0].revenue_tier in {"verified", "counted_flagged"}


@pytest.mark.parametrize(("text", "expected"), [
    ("ADP TAX ADP TAX 123456 CONTOSO BAKERY", True),
    ("ACH DEPOSIT PAYCHEX TPS TAXES 123456 CONTOSO BAKERY AUTO 1 LLC", True),
    ("PAYCHEX TPS DES:TAXES ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", True),
    ("INTUIT 12345678 DES:TAX ID:1 INDN:CONTOSO TAX SERVICES CO ID:1 CCD", True),
    ("ACH TAXES 123456 PAYCHEX TPS 12345", True),   # the entry printed first reads as the payer region
    ("INTUIT PYMT SOLN DEPOSIT 540302 ABC123 CONTOSO TAX SERVICES LLC", False),
    ("ADP INC VENDOR PAY 540302 ABC123 CONTOSO TAX SERVICES LLC", False),
    ("ADP DES:SALES ID:1 INDN:CONTOSO TAX SERVICES CO ID:1 CCD", False),
])
def test_the_payroll_tax_word_is_read_on_the_payer_region_and_the_entry_fields(text, expected):
    from analysis.true_revenue.finance_release import payroll_tax_credit

    revenue = lexical.revenue_text(description_text.normalize_transaction_description(text))
    assert payroll_tax_credit(revenue, descriptor_payer.payer_region(revenue)) is expected


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
    assert counter_debit_reading._split_glued_digits(text) == split


def test_the_payer_reading_keeps_5_6_s_word_and_adds_the_glued_forms():
    reading = counter_debit_reading.counter_debit_payer_reading("CONTOSO RIDGE HILL")
    assert reading.legacy == "CONTOSO"
    assert reading.keys == {"CONTOSO", "CONTOSORIDGE", "CONTOSORIDGEHILL"}
    generic = counter_debit_reading.counter_debit_payer_reading("XY EXPRESS INC")
    assert (generic.legacy, generic.keys) == ("EXPRESS", frozenset())
    glued = counter_debit_reading.counter_debit_payer_reading("FORWARDFINUSA1 PAYMENTS")
    assert (glued.legacy, glued.keys) == (None, frozenset({"FORWARDFINUSA"}))
    assert counter_debit_reading.counter_debit_payer_reading("ADP TAX").keys == {"ADP", "ADPTAX"}


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
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(text) == kind


def _counter(legacy, words, *, entity=None, cents=100000, settlement=False, insurer=False, released_insurer=False):
    from analysis.true_revenue.model import CounterCredit

    # Audit round 3, R3-B16 (R3-03): `released_insurer` is CounterCredit's last field, passed only when set.
    extra = {"released_insurer": True} if released_insurer else {}
    return CounterCredit(counter_debit_reading._counter_debit_reading(legacy, [words]), cents, entity, settlement, insurer, **extra)


def _debits(*, lender=(), other=()):
    """Each other debit is (legacy, words, kind, cents, recurring), or (..., recurring, premium): audit round 3,
    R3-B16 (R3-03), `premium` is _CounterDebit's last field, passed only when set."""
    from analysis.true_revenue.model import CounterDebits, _CounterDebit

    return CounterDebits(
        tuple(_CounterDebit(counter_debit_reading._counter_debit_reading(legacy, [words]), "lender", 30000, entity, False)
              for legacy, words, entity in lender),
        tuple(_CounterDebit(counter_debit_reading._counter_debit_reading(legacy, [words]), kind, cents, None, recurring,
                            **({"premium": True} if rest and rest[0] else {}))
              for legacy, words, kind, cents, recurring, *rest in other),
    )


def test_a_lender_debit_is_compared_by_registry_entity_when_both_sides_name_one():
    from analysis.true_revenue.counter_debit_pairing import debited_as_lender

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
    from analysis.true_revenue.counter_debit_pairing import debited_as_lender

    debits = _debits(lender=[("CONTOSOFUNDING", ["CONTOSOFUNDING"], None)])
    assert debited_as_lender(_counter("CONTOSO", ["CONTOSO"]), debits, prefix=True)
    assert not debited_as_lender(_counter("CONTOSO", ["CONTOSO"]), debits, prefix=False)
    # Too short a prefix (four letters) never reads.
    assert not debited_as_lender(_counter("CONT", ["CONT"]), _debits(lender=[("CONTFUNDING", ["CONTFUNDING"], None)]),
                                 prefix=True)


def test_also_debited_reads_each_kind():
    from analysis.true_revenue.counter_debit_pairing import also_debited

    def held(kind, *, cents=2500, recurring=False, **credit):
        return also_debited(_counter("CONTOSO", ["CONTOSO"], **credit),
                            _debits(other=[("CONTOSO", ["CONTOSO"], kind, cents, recurring)]))

    assert not held("receiving_fee")
    assert not held("receiving_fee", cents=100000)
    assert held("circular") and held("other")
    assert held("processor_fee") and not held("processor_fee", settlement=True)
    assert held("processor_fee", settlement=True, cents=100000)
    # Review round 1 (finding 4): a processor's fee at one amount, again and again, is still its fee.
    assert not held("processor_fee", settlement=True, recurring=True)
    assert held("processor_fee", recurring=True)
    assert not held("bill") and held("bill", insurer=True)
    assert held("bill", cents=100000) and held("bill", recurring=True)
    # A generic word: a transfer matches it as 5.6 read it, any other debit only for the credit's own amount.
    generic = _counter("EXPRESS", ["XY", "EXPRESS", "INC"])
    for kind, cents, expected in (("circular", 2500, True), ("other", 2500, False), ("other", 100000, True),
                                  ("bill", 100000, True)):
        debits = _debits(other=[("EXPRESS", ["AMERICAN", "EXPRESS"], kind, cents, False)])
        assert also_debited(generic, debits) is expected, (kind, cents)


# --- Audit round 2, R2-B02 ------------------------------------------------------------------------------------------
# R18: a platform's payout under the merchant's descriptor, beside the platform's own pull under the same descriptor
# (each printing its own payout id), is no circular money; a pull for the payout's own amount still holds it.
# R01: a processor's or a platform's payout (its settlement wording, its payout forms or a merchant-ID field read
# anywhere on the row) is held only by a circular debit, a debit for its own amount or a recurring non-card debit: a
# card charge or a one-off debit of the processor's own never holds it. R48 part 1: the bank's receiving fee reprints
# the sender after TT or FROM, and words of that sender's name are never read as the fee's outgoing words.

HELD_ALSO = ("excluded_pending_review", "payer_also_debited")
BOFA_PAYOUT = "{orig} DES:{entry} ID:ST-{payout} INDN:{receiver} CO ID:0000000000 CCD"


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


def _bakery(payout, amount):
    return (BOFA_PAYOUT.format(orig="CONTOSO BAKERY", entry="CONTOSO BAK", payout=payout,
                               receiver="CONTOSO BAKERY LLC"), amount)


BAKERY_PAYOUTS = [_bakery("A0B0C0D0E1F0", 800.0), _bakery("A0B0C0D0E2F0", 900.0), _bakery("A0B0C0D0E3F0", 1000.0)]


def test_r18_a_platform_s_own_pull_under_the_descriptor_never_holds_its_payouts():
    records = _credits(_records([*BAKERY_PAYOUTS, _bakery("B0C0D0E0F1A0", -250.0)], holder=None))
    assert [(record.revenue_tier, record.revenue_match_method) for record in records] == [
        ("verified", "named_payer_repeats")] * 3


def test_r18_a_pull_for_a_payout_s_own_amount_still_holds_that_payout():
    records = _credits(_records([*BAKERY_PAYOUTS, _bakery("B0C0D0E0F1A0", -900.0)], holder=None))
    assert _tier(records[1]) == HELD_ALSO
    assert [_tier(record) != HELD_ALSO for record in (records[0], records[2])] == [True, True]


def test_r18_a_transfer_to_the_descriptor_still_holds_every_payout():
    records = _credits(_records([*BAKERY_PAYOUTS, ("ONLINE BANKING TRANSFER TO CONTOSO BAKERY", -250.0)], holder=None))
    assert [_tier(record) for record in records] == [HELD_ALSO] * 3


def test_r18_a_town_after_an_id_label_is_no_payout_id():
    # Review round 1 (finding 6a): a payout id holds letters and digits; a town after an ID label ('ID:ST <town>')
    # is none, so the customer's own debit still holds its payment.
    row = "CONTOSO SUPPLY DES:PAYMENT ID:ST SAMPLEVILLE INDN:NORTHWIND LABS INC CO ID:0000000000 CCD"
    records = _credits(_records([(row, 900.0), (row, -200.0)], bank="Bank of America"))
    assert _tier(records[0]) == HELD_ALSO


CHASE_MID = (
    "ORIG CO NAME:CONTOSOPAY SV1T ORIG ID:0000000000 DESC DATE:310302 CO ENTRY DESCR:0000000000SEC:PPD "
    "TRACE#:000000000000000 EED:310302 IND ID: IND NAME:FABRIKAM ACADEMY MID:12345678-CONTOSOPAY 0000000000000 "
    "TRN: 0000000000TC"
)
# Payment Brands (a card payment facilitator: a registered ISO / member service provider of Fifth Third Bank,
# paymentbrands.com; its card services agreement credits the merchant's settlement account with its card sales and
# debits it for refunds, chargebacks and processing fees) prints its Truist settlements with this originator.
TRUIST_PAYMENT_BRANDS = "0000000000 PymntBrdMin SV1T XXXX NORTHWIND"


@pytest.mark.parametrize(("rows", "bank"), [
    # Chase: the merchant-ID field prints after the receiver; one same-text debit of the processor's.
    ([(CHASE_MID, 2400.0), (CHASE_MID, 2600.0), (CHASE_MID, -30.0)], "Chase"),
    # Truist: the payout form alone, beside the processor's monthly debit.
    ([(TRUIST_PAYMENT_BRANDS, 1200.0), (TRUIST_PAYMENT_BRANDS, 1400.0), (TRUIST_PAYMENT_BRANDS, 1600.0),
      (TRUIST_PAYMENT_BRANDS, -48.0)], "Truist"),
    # A platform's payout beside the platform's card charge (CARD PMT), or its charges printed '<city> <ST> USA'.
    ([("CONTOSOFIELD INC PAYOUT", 1800.0), ("CONTOSOFIELD INC PAYOUT", 2100.0), ("CONTOSOFIELD CARD PMT", -97.0)],
     None),
    ([("FABRIKAMCARE PAYOUT 0000 ST A1B2C3D4E5F6", 900.0), ("FABRIKAMCARE NEW YORK NY USA", -125.0),
      ("FABRIKAMCARE NEW YORK NY USA", -125.0)], None),
    # A bank's merchant deposit beside a card purchase from a merchant sharing its word.
    ([("DEPOSIT TRUIST MERCHANT CONTOSO HARDWARE CUSTOMER ID 123456789012345", 2000.0),
      ("DEBIT CARD PURCHASE CONTOSO HARDWARE SE 0302 SAMPLEVILLE", -500.0)], "Truist"),
    # A processor's combined deposit beside its FEES debit.
    ([("FABRIKAMMERCHANT COMB DEP 123456", 1500.0), ("FABRIKAMMERCHANT FEES 123456", -40.0)], None),
    # RBC's glued merchant-services payment beside a same-text debit.
    ([("MISC PAYMENT 123456 MRCHNTSVCS", 600.0), ("MISC PAYMENT 123457 MRCHNTSVCS", -40.0)], "Royal Bank of Canada"),
])
def test_r01_a_processor_s_payout_is_counted_beside_its_own_non_circular_debit(rows, bank):
    records = _credits(_records(rows, bank=bank))
    assert [record.revenue_tier for record in records] == ["counted_flagged"] * len(records)
    without = _credits(_records([row for row in rows if row[1] > 0], bank=bank))
    assert [_tier(record) for record in records] == [_tier(record) for record in without]


@pytest.mark.parametrize(("rows", "bank"), [
    ([("NORTHWIND STUDIO DES:NORTHWIND ID:ST-A1B2C3D4E5F6 INDN:SAMPLE OWNER CO ID:0000000000 CCD", 1300.0),
      ("NORTHWIND STUDIO DES:NORTHWIND ID:ST-A1B2C3D4E5F7 INDN:SAMPLE OWNER CO ID:0000000000 CCD", 1500.0),
      ("NORTHWIND STUDIO DES:NORTHWIND ID:ST-B1C2D3E4F5G6 INDN:SAMPLE OWNER CO ID:0000000000 CCD", -250.0)],
     "Bank of America"),
    # QuickBooks Payments in Canada beside Intuit's per-payout fee debit (Intuit Canada ULC).
    ([("ACCOUNTS PAYABLE INTUIT 123456 INTUIT CANADA PAYMENTS INC", 1000.0),
      ("ACCOUNTS PAYABLE INTUIT 123456 INTUIT CANADA ULC", -29.0)], "Scotiabank"),
    ([("ACCOUNT PAYABLE PMT INTUIT CANADA P INTUIT 123456", 1000.0),
      ("ACCOUNT PAYABLE PMT INTUIT CANADA U INTUIT 123457", -29.0)], "Royal Bank of Canada"),
])
def test_r01_a_payout_that_verifies_without_the_debit_verifies_beside_it(rows, bank):
    records = _credits(_records(rows, bank=bank))
    assert {record.revenue_tier for record in records} == {"verified"}


def test_r01_a_pull_for_the_payout_s_own_amount_still_holds_it():
    rows = [("NORTHWIND STUDIO DES:NORTHWIND ID:ST-A1B2C3D4E5F6 INDN:SAMPLE OWNER CO ID:0000000000 CCD", 1300.0),
            ("NORTHWIND STUDIO DES:NORTHWIND ID:ST-A1B2C3D4E5F7 INDN:SAMPLE OWNER CO ID:0000000000 CCD", 1500.0),
            ("NORTHWIND STUDIO DES:NORTHWIND ID:ST-B1C2D3E4F5G6 INDN:SAMPLE OWNER CO ID:0000000000 CCD", -1300.0)]
    records = _credits(_records(rows, bank="Bank of America"))
    assert _tier(records[0]) == HELD_ALSO


@pytest.mark.parametrize(("rows", "bank"), [
    # A debit for the payout's own amount.
    ([("CONTOSOFIELD INC PAYOUT", 500.0), ("CONTOSOFIELD CARD PMT", -500.0)], None),
    # A transfer to the payer (circular, at any size).
    ([("CONTOSOFIELD INC PAYOUT", 500.0), ("ONLINE TRANSFER TO CONTOSOFIELD INC REF 1", -200.0)], None),
    # The processor's own debit recurring at one amount.
    ([("CONTOSO MERCHANT SERVICES DES:DEPOSIT ID:1 INDN:NORTHWIND LABS CO ID:1 CCD", 2215.0),
      *[("CONTOSO MERCHANT SERVICES DES:BILLING ID:2 INDN:NORTHWIND LABS CO ID:1 CCD", -30.0)] * 2], None),
    # A customer's ACH beside a card purchase or a wire to it: no payout form, so the card holds as any debit does.
    ([("FABRIKAM TOOLS DES:PAYMENT ID:1", 1500.0), ("POS DB FABRIKAM TOOLS 0302 SAMPLEVILLE", -60.0)], None),
    ([("FABRIKAM TOOLS DES:PAYMENT ID:1", 1500.0), ("WIRE TO FABRIKAM TOOLS NEW YORK NY USA", -600.0)], None),
    # A payment platform's E SERVICE credit (no payout form) beside its RETURNS debit.
    ([("CONTOSO PAYMENT DES:E SERVICE ID:0001 INDN:NORTHWIND LABS CO ID:0000000000 CCD", 500.0),
      ("CONTOSO PAYMENT DES:RETURNS ID:0002 INDN:NORTHWIND LABS CO ID:0000000000 CCD", -30.0)], None),
])
def test_r01_circular_same_amount_recurring_and_non_payout_holds_stay(rows, bank):
    records = _credits(_records(rows, bank=bank))
    assert _tier(records[0]) == HELD_ALSO


def test_r01_three_equal_debits_of_the_processor_s_keep_its_settlement_held():
    # Three debits at one amount also read as a potential lender's pulls (D6): the lender hold names the row first.
    rows = [("CONTOSO MERCHANT SERVICES DES:DEPOSIT ID:1 INDN:NORTHWIND LABS CO ID:1 CCD", 2215.0),
            *[("CONTOSO MERCHANT SERVICES DES:BILLING ID:2 INDN:NORTHWIND LABS CO ID:1 CCD", -30.0)] * 3]
    records = _credits(_records(rows))
    assert _tier(records[0]) == ("excluded_pending_review", "payer_debited_as_lender")


def test_r01_a_card_credit_beside_a_card_purchase_stays_held():
    records = _credits(_records([("POS CR CONTOSO MART 0302", 40.0), ("POS DB CONTOSO MART 0302", -60.0)]))
    assert records[0].revenue_tier == "excluded_pending_review"


def test_r01_intuit_s_push_beside_its_transfer_fee_stays_held():
    rows = [("MONEY TRANSFER AUTHORIZED ON 03/02 FROM INTUIT INC SAMPLEVILLE CA S000000000000000 CARD 0000", 2600.0),
            ("BUSINESS TO BUSINESS ACH DEBIT INTUIT 000000 TRAN FEE 000000 NORTHWIND LABS", -26.0)]
    records = _credits(_records(rows, bank="Wells Fargo"))
    assert records[0].revenue_tier == "excluded_pending_review"


def test_r01_intuit_canada_payroll_stays_pay():
    rows = [("ACCOUNT PAYABLE PMT INTUIT CANADA PAYROLL 123456", 1000.0),
            ("ACCOUNT PAYABLE PMT INTUIT CANADA U INTUIT 123457", -29.0)]
    records = _credits(_records(rows, bank="Royal Bank of Canada"))
    assert _tier(records[0]) == ("excluded_pending_review", "payroll_or_salary")


@pytest.mark.parametrize(("text", "settlement"), [
    ("ORIG CO NAME CONTOSOPAY SV1T IND NAME FABRIKAM ACADEMY MID 12345678 CONTOSOPAY", True),
    ("0000000000 PYMNTBRDMIN SV1T XXXX NORTHWIND", True),
    ("ORIG CO NAME PAYMNTBRAND SV1T CO ENTRY DESCR 0000000000", True),
    ("MISC PAYMENT 123456 MRCHNTSVCS", True),
    ("FABRIKAM MRCH SVCS 123456", True),
    ("FABRIKAMMERCHANT COMB DEP 123456", True),
    ("FABRIKAM COMBINED DEPOSIT 123456", True),
    ("DEPOSIT TRUIST MERCHANT CONTOSO DELI CUSTOMER ID 123456789012345", True),
    ("ACCOUNTS PAYABLE INTUIT 123456 INTUIT CANADA PAYMENTS INC", True),
    ("ACCOUNT PAYABLE PMT INTUIT CANADA P INTUIT 123456", True),
    ("NORTHWIND STUDIO DES NORTHWIND ID ST A1B2C3D4E5F6 INDN SAMPLE OWNER", True),
    # No payout form: Intuit's payroll, a reference of letters or digits alone, a merchant-ID field of five digits
    # after the receiver.
    ("ACCOUNT PAYABLE PMT INTUIT CANADA PAYROLL 123456", False),
    ("NORTHWIND STUDIO DES NORTHWIND ID ST ABCDEFGHIJKL", False),
    ("NORTHWIND STUDIO DES NORTHWIND ID ST 123456789012", False),
    ("CONTOSO SUPPLY DES PAYMENT INDN NORTHWIND LABS MID 12345", False),
    ("CONTOSO PAYMENT DES E SERVICE ID 0001", False),
])
def test_r01_the_credit_s_payout_forms(text, settlement):
    from analysis.true_revenue.counter_debit_pairing import counter_credit

    record = tc.classify_transaction(text, 500.0, direction="credit")
    revenue = lexical.revenue_text(record.normalized_description)
    assert counter_credit(record, revenue, descriptor_payer.payer_region(revenue)).settlement is settlement


@pytest.mark.parametrize(("text", "kind", "card"), [
    ("DEBIT CARD PURCHASE CONTOSO HARDWARE SE 0302 SAMPLEVILLE", "other", True),
    ("DBCRD PUR AP CONTOSO HARDWARE 0302", "other", True),
    ("POS DB CONTOSO MART 0302 SAMPLEVILLE", "other", True),
    ("POS DEBIT CONTOSO MART 0302", "other", True),
    ("POS PURCHASE CONTOSO MART 0302", "other", True),
    ("POINT OF SALE CONTOSO MART 0302", "other", True),
    ("PURCHASE0302123456 CONTOSO TIRE SAMPLEVILLE", "other", True),
    ("FABRIKAMCARE NEW YORK NY USA", "other", True),
    ("FABRIKAM WEBSITES SAMPLEVILLE BC CAN", "other", True),
    # Review round 1 (finding 4): the card form keeps the debit's own kind (a bill, a fee) and marks it a card charge.
    ("BILL PAY CONTOSO UTILITIES NEW YORK NY USA", "bill", True),
    ("CONTOSO SOFTWARE SUBSCRIPTION SAMPLEVILLE CA USA", "bill", True),
    ("POS DB FABRIKAMMERCHANT FEES 0302", "processor_fee", True),
    # A card form never turns circular money or the bank's receiving fee into a card charge.
    ("WIRE TO NORTHWIND TOOLS NEW YORK NY USA", "circular", False),
    ("ONLINE TRANSFER TO CONTOSO MART NY USA", "circular", False),
    ("FUNDS TRANSFER FEE TT CONTOSO NY USA", "receiving_fee", False),
    # No card form: the kind is unchanged.
    ("CONTOSOFIELD CARD PMT", "other", False),
    ("FABRIKAMMERCHANT FEES 123456", "processor_fee", False),
])
def test_r01_a_card_purchase_in_another_bank_s_form_is_marked_a_card_charge(text, kind, card):
    from analysis.true_revenue.counter_debit_pairing import counter_debits

    record = tc.classify_transaction(text, -60.0, direction="debit")
    debits = counter_debits([record], set())
    assert [(debit.kind, debit.card) for debit in debits.other] == [(kind, card)]


def test_r01_a_card_charge_recurs_with_the_other_debits():
    from analysis.true_revenue.counter_debit_pairing import counter_debits

    records = [tc.classify_transaction(text, -125.0, direction="debit")
               for text in ("FABRIKAMCARE NEW YORK NY USA", "FABRIKAMCARE NEW YORK NY USA")]
    assert [(debit.kind, debit.card, debit.recurring) for debit in counter_debits(records, set()).other] == [
        ("other", True, True)] * 2


def test_r01_also_debited_reads_a_card_charge_and_a_settlement():
    from analysis.true_revenue.counter_debit_pairing import also_debited
    from analysis.true_revenue.model import CounterDebits, _CounterDebit

    def held(kind, *, settlement, card=False, cents=2500, recurring=False, insurer=False):
        debit = _CounterDebit(counter_debit_reading._counter_debit_reading("CONTOSO", [["CONTOSO"]]), kind, cents, None, recurring,
                              card=card)
        return also_debited(_counter("CONTOSO", ["CONTOSO"], settlement=settlement, insurer=insurer),
                            CounterDebits((), (debit,)))

    # A payout is never held by a card charge or a one-off other debit; a recurring other debit still holds it.
    assert not held("other", card=True, settlement=True) and not held("other", card=True, settlement=True,
                                                                      recurring=True)
    assert not held("bill", card=True, settlement=True, recurring=True)
    assert not held("other", settlement=True) and held("other", settlement=True, recurring=True)
    # The payout's own amount, a circular debit and a credit with no payout form keep holding.
    assert held("other", card=True, settlement=True, cents=100000) and held("other", settlement=True, cents=100000)
    assert held("circular", settlement=True)
    assert held("other", card=True, settlement=False) and held("other", settlement=False)
    assert held("processor_fee", card=True, settlement=False)
    # Review round 1 (finding 4): beside a credit with no payout form a card-form bill reads the bill rule (B4): it
    # holds only an insurer, a debit for the credit's own amount or a recurring one.
    assert not held("bill", card=True, settlement=False)
    assert held("bill", card=True, settlement=False, insurer=True)
    assert held("bill", card=True, settlement=False, cents=100000)
    assert held("bill", card=True, settlement=False, recurring=True)


@pytest.mark.parametrize(("credit", "debit"), [
    ("CONTOSO UTILITIES DES:VENDOR PAY ID:1", "BILL PAY CONTOSO UTILITIES NEW YORK NY USA"),
    ("CONTOSO SOFTWARE DES:VENDOR PAY ID:1", "CONTOSO SOFTWARE SUBSCRIPTION SAMPLEVILLE CA USA"),
])
def test_r01_a_bill_printed_in_a_card_form_never_holds_a_customer_s_remittance(credit, debit):
    with_debit, without = _same_as_without([(credit, 900.0)], [(debit, -120.0)])
    assert with_debit == without
    assert with_debit[0][1:4:2] == ("verified", "payer_remittance_descriptor")


# R48 part 1: the bank's receiving fee reprints the sender, whose name may hold TO, OUT or BNF.

@pytest.mark.parametrize(("sender", "cut"), [
    ("CONTOSO TO GO INC", "CONTOSO TO G"),
    ("SAMPLE TO TABLE FOODS INC", "SAMPLE TO TA"),
    ("SAMPLE OUT WEST LTD", "SAMPLE OUT W"),
])
def test_r48_a_sender_whose_name_holds_an_outgoing_word_still_verifies_on_repeat(sender, cut):
    wire = f"FUNDS TRANSFER CREDIT TT {sender}"
    fee = f"FUNDS TRANSFER FEE TT {cut}"
    rows = [(wire, 5000.0), (fee, -17.0), (wire, 5200.0), (fee, -17.0)]
    records = _credits(_records(rows, bank="Royal Bank of Canada"))
    assert [(record.revenue_tier, record.revenue_match_method) for record in records] == [
        ("verified", "repeat_wire_sender")] * 2
    one = _credits(_records([(wire, 5000.0), (fee, -17.0)], bank="Royal Bank of Canada"))
    assert _tier(one[0]) == ("counted_flagged", "wire_named_sender")


def test_r48_a_wire_from_a_sender_named_with_to_verifies_beside_the_fee_from_it():
    wire = "WIRE FROM SAMPLE TO TABLE FOODS INC"
    fee = "WIRE TRANSFER FEE FROM SAMPLE TO TABLE FOODS INC"
    records = _credits(_records([(wire, 5000.0), (fee, -15.0), (wire, 5200.0), (fee, -15.0)], bank="Mercury"))
    assert {record.revenue_tier for record in records} == {"verified"}


@pytest.mark.parametrize(("text", "kind"), [
    ("FUNDS TRANSFER FEE TT CONTOSO TO G", "receiving_fee"),
    ("FUNDS TRANSFER FEE TT SAMPLE OUT W", "receiving_fee"),
    ("WIRE TRANSFER FEE FROM SAMPLE TO TABLE FOODS INC", "receiving_fee"),
    # The fee's own outgoing words, before any sender, keep it circular.
    ("WIRE TRANSFER FEE TO CONTOSO LLC", "circular"),
    ("WIRE FEE FOR WIRE TRANSFER TO CONTOSO LAW GROUP", "circular"),
    ("WIRE TRANSFER FEE DOMESTIC OUTGOING ID 1234", "circular"),
    ("WIRE FEE (OUTGOING)", "circular"),
    ("WIRE FEE 1234 BNF:CONTOSO", "circular"),
    ("OUTGOING WIRE FEE CONTOSO PHARMA INC", "circular"),
    # Review round 1 (finding 5): FROM before the holder's own account is the wire's source, never a sender's name,
    # so the words after it are the fee's own; an outgoing word no name prints (OUTGOING, BNF, BENEFICIARY) is read
    # after the sender too.
    ("WIRE TRANSFER FEE FROM CHECKING TO CONTOSO LLC", "circular"),
    ("WIRE TRANSFER FEE FROM CHK 1234 TO CONTOSO LLC", "circular"),
    ("FUNDS TRANSFER FEE FROM XXXXXX1234 TO CONTOSO", "circular"),
    ("FUNDS TRANSFER FEE TT CONTOSO BNF FABRIKAM", "circular"),
])
def test_r48_the_receiving_fee_reads_its_outgoing_words_before_the_sender(text, kind):
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(description_text.normalize_transaction_description(text)) == kind


def test_r48_the_fee_for_the_holder_s_wire_from_its_account_still_holds_the_payer():
    wire = "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:CONTOSO TOOLS INC ID:99 SND BK:SAMPLE BANK ID:1"
    rows = [(wire.format(n=1), 5000.0), (wire.format(n=2), 5200.0),
            ("WIRE TRANSFER FEE FROM CHECKING TO CONTOSO TOOLS INC", -25.0)]
    assert [_tier(record) for record in _credits(_records(rows))] == [HELD_ALSO] * 2


def test_r48_a_lead_bank_fee_for_the_holder_s_wire_to_the_payer_still_holds_its_repeat():
    wire = "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:CONTOSO TOOLS INC ID:99 SND BK:SAMPLE BANK ID:1"
    rows = [(wire.format(n=1), 5000.0), (wire.format(n=2), 5200.0),
            ("WIRE FEE FOR WIRE TRANSFER TO CONTOSO TOOLS INC", -25.0)]
    records = _credits(_records(rows))
    assert [_tier(record) for record in records] == [HELD_ALSO] * 2


# --- Owner ruling 2026-10-02 (the underwriter's Q9), R2-OW05: the hidden-loan guard (_payer_collects) ----------------
# "The hidden-loan guard stays: a payer that also debits the account like a lender stays held." Read broadly by design:
# a lender or financing debit naming the payer, or any other posted debit naming it (the B4 forms, 5.6's first word or
# a cut or glued spelling), the bank's receiving fee and a card charge aside. Stricter than also_debited: no bill,
# processor-fee, settlement or payout-pair exemption, and no amount or recurrence test.

def test_ow05_payer_collects_on_a_lender_debit_naming_the_payer():
    from analysis.true_revenue.counter_debit_pairing import _payer_collects

    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"]), _debits(lender=[("CONTOSO", ["CONTOSO"], None)]))
    # A cut or glued spelling of the payer on a lender debit (the pass-7 prefix).
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                           _debits(lender=[("CONTOSOFUNDING", ["CONTOSOFUNDING"], None)]))
    assert not _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                               _debits(lender=[("FABRIKAM", ["FABRIKAM"], None)]))


@pytest.mark.parametrize("kind", ["other", "circular", "bill", "processor_fee"])
def test_ow05_payer_collects_on_any_other_debit_naming_the_payer_whatever_its_amount(kind):
    from analysis.true_revenue.counter_debit_pairing import _payer_collects, also_debited

    debits = _debits(other=[("CONTOSO", ["CONTOSO"], kind, 2500, False)])
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"], settlement=True), debits)
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"]), debits)
    # The documented over-hold: also_debited spares a one-off bill and a settlement's fee or one-off debit.
    if kind in {"bill", "processor_fee"}:
        assert not also_debited(_counter("CONTOSO", ["CONTOSO"], settlement=True), debits)


def test_ow05_payer_collects_reads_5_6_s_first_word_and_a_cut_spelling_on_another_debit():
    from analysis.true_revenue.counter_debit_pairing import _payer_collects

    # 5.6's first distinctive word alone (legacy), whatever the other words.
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO", "GROUP"]),
                           _debits(other=[("CONTOSO", ["CONTOSO", "TOOLS"], "other", 2500, False)]))
    # A glued spelling of the payer's name.
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                           _debits(other=[("CONTOSOFUNDING", ["CONTOSOFUNDING"], "other", 2500, False)]))
    assert not _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                               _debits(other=[("FABRIKAM", ["FABRIKAM"], "other", 2500, False)]))


def test_ow05_payer_collects_never_reads_the_bank_s_receiving_fee_or_a_card_charge():
    from analysis.true_revenue.counter_debit_pairing import _payer_collects
    from analysis.true_revenue.model import CounterDebits, _CounterDebit

    reading = counter_debit_reading._counter_debit_reading("CONTOSO", [["CONTOSO"]])
    assert not _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                               _debits(other=[("CONTOSO", ["CONTOSO"], "receiving_fee", 100000, False)]))
    for kind in ("other", "bill", "processor_fee"):
        card = _CounterDebit(reading, kind, 100000, None, True, card=True)
        assert not _payer_collects(_counter("CONTOSO", ["CONTOSO"]), CounterDebits((), (card,)))
    # The same debit without its card mark holds.
    assert _payer_collects(_counter("CONTOSO", ["CONTOSO"]),
                           CounterDebits((), (_CounterDebit(reading, "other", 100000, None, True),)))


def test_ow05_payer_collects_on_the_statement_s_own_debits():
    from analysis.true_revenue.counter_debit_pairing import _payer_collects, counter_credit, counter_debits

    def collects(debit, holder="NORTHWIND LABS INC"):
        records = _records([("NORTHWIND FINANCIAL GROUP DES:PAYABLES ID:1", 4200.0), debit], holder=holder)
        text = lexical.revenue_text(records[0].normalized_description)
        return _payer_collects(counter_credit(records[0], text, descriptor_payer.payer_region(text)), counter_debits(records, set()))

    # A same-payer debit the classifier reads as no lender ('other'), and a lender's debit.
    assert collects(("NORTHWIND FINANCIAL DES:ACH DEBIT ID:2", -500.0))
    assert collects(("NORTHWIND FINANCIAL DES:LOAN PMT ID:2", -500.0))
    # The bank's receiving fee reprinting the sender, and an unrelated debit, never hold.
    assert not collects(("FUNDS TRANSFER FEE TT NORTHWIND FINANCIAL", -25.0))
    assert not collects(("FABRIKAM SUPPLY DES:VENDOR PAY ID:2", -500.0))
    # A card purchase the classifier names is never among the debits.
    assert not collects(("CHECKCARD 0302 NORTHWIND FINANCIAL SAMPLEVILLE NY", -60.0))


# --- Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b), (c)), R2-OW09: the release of T4's financing-root hold
# reads the same guard last (finance_named_release): a released credit whose payer the statement debits stays held as
# financing_named_payer, whatever kind the debit is (no bill, processor-fee or settlement exemption: a documented
# over-hold), the bank's receiving fee and a card purchase aside.

@pytest.mark.parametrize(("debit", "released"), [
    (None, True),
    ("FABRIKAM FINANCIAL DES:ACH DEBIT ID:2", False),
    ("FABRIKAM FINANCIAL DES:LOAN PMT ID:2", False),
    ("FABRIKAM FINANCIAL GROUP DES:SVC FEE ID:2", False),
    ("FABRIKAM FINANCIAL GROUP DES:BILL PAY ID:2", False),
    ("FUNDS TRANSFER FEE TT FABRIKAM FINANCIAL", True),
    ("CHECKCARD 0302 FABRIKAM FINANCIAL SAMPLEVILLE NY", True),
    ("CONTOSO SUPPLY DES:VENDOR PAY ID:2", True),
])
def test_ow09_the_release_reads_the_hidden_loan_guard_last(debit, released):
    rows = [("FABRIKAM FINANCIAL GROUP DES:PAYABLES ID:1", 4200.0)] + ([(debit, -50.0)] if debit else [])
    credit = _credits(_records(rows))[0]
    assert rules_reading(credit) == (
        ("counted_flagged", "finance_named_customer") if released else ("excluded_pending_review", "financing_named_payer"))
    # The guard is the release's last step: the credit's reading (a customer's name, payables wording) is the same.
    from analysis.true_revenue import finance_release
    from analysis.true_revenue import counter_debit_pairing

    records = _records(rows)
    text = lexical.revenue_text(records[0].normalized_description)
    region, entry = descriptor_payer.payer_region(text), descriptor_payer.entry_fields(text)
    reason = finance_release.finance_named_release(records[0], text, region=region, entry=entry,
                                      debits=counter_debit_pairing.counter_debits(records, set()))
    assert reason == ("finance_named_customer" if released else None)
    assert counter_debit_pairing._payer_collects(counter_debit_pairing.counter_credit(records[0], text, region), counter_debit_pairing.counter_debits(records, set())) is (
        not released)


# --- Audit round 3, R3-B16 --------------------------------------------------------------------------------------------
# R3-35 (standard A1, A2, §4.2; §20 B4 review round 1): Chase glues the SEC code onto the entry ('CO ENTRY
# DESCR:FEESSEC CCD'), so the processor's fee and the bill words are read on the entry with the code split off, and a
# fee word glued after another word at the entry's end ('MONTHLYFEESEC') is the processor's fee too; the receiving-fee
# and circular tests keep reading the row as printed. R3-03: a debit naming a credit the Q2 release counted (an insurer
# paid for the business's work) holds it only when it is circular money, is for the credit's own amount, or recurs at
# one amount printing no premium or retry word. R3-33: the fee for the holder's own outgoing wire 'FROM <product name>
# TO <payee>' names its source account, never a sender.

CHASE_ENTRY = ("ORIG CO NAME:CONTOSO MERCHANT SERVICES ORIG ID:0000000001 DESC DATE:540303 CO ENTRY DESCR:{entry} "
               "TRACE#:0000001 EED:540303 IND ID:0000001 IND NAME:NORTHWIND LABS")


@pytest.mark.parametrize(("entry", "kind"), [
    ("FEESSEC CCD", "processor_fee"),
    ("FEESEC CCD", "processor_fee"),
    ("MTHLY DISCSEC CCD", "processor_fee"),
    ("DISCOUNTSEC CCD", "processor_fee"),
    ("CHARGEBACKSEC CCD", "processor_fee"),
    # A fee word glued after another word at the end of the entry the SEC code follows.
    ("MONTHLYFEESEC CCD", "processor_fee"),
    ("SERVICEFEESEC WEB", "processor_fee"),
    ("PAYCORFEESSEC CCD", "processor_fee"),
    ("BILLPAYFEESEC WEB", "processor_fee"),
    ("BILL PAYMTSEC WEB", "bill"),
    ("PLANT UTILSEC PPD", "bill"),
    ("VZ BILLPAYSEC WEB", "bill"),
    # Controls: no fee or bill word, COFFEE is no fee, and a glued TRANSFERSEC keeps today's kind.
    ("COFFEESEC PPD", "other"),
    ("PAYMENTSEC CCD", "other"),
    ("TRANSFERSEC PPD", "other"),
    ("FEES SEC CCD", "processor_fee"),
])
def test_r3_35_chase_s_glued_fee_and_bill_entries_read_their_kind(entry, kind):
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(description_text.normalize_transaction_description(CHASE_ENTRY.format(entry=entry))) == kind


R3_35_SETTLEMENTS = [(CHASE_ENTRY.format(entry="DEPOSITSEC CCD"), amount) for amount in (2215.0, 1985.0, 2415.0)]
R3_35_DAYS = [2, 9, 16, 5, 19]


@pytest.mark.parametrize("entry", ["FEESSEC CCD", "DISCOUNTSEC CCD", "CHARGEBACKSEC CCD", "FEES SEC CCD"])
def test_r3_35_an_unclaimed_processor_s_settlements_read_as_without_its_glued_fees(entry):
    # Two equal fees (a processor's fixed fee) beside three settlements: today the glued ones read 'other' and,
    # recurring, hold every settlement; read as the processor's fee they hold none (B4 review round 1).
    fees = [(CHASE_ENTRY.format(entry=entry), -45.0)] * 2
    with_fees, control = _same_as_without(R3_35_SETTLEMENTS, fees, bank="Chase", days=R3_35_DAYS)
    assert with_fees == control
    assert {reading[2] for reading in with_fees} != {"payer_also_debited"}
    assert {reading[1] for reading in control} == {"verified"}


def test_r3_35_two_equal_glued_debits_that_print_no_fee_word_still_hold_the_settlements():
    debits = [(CHASE_ENTRY.format(entry="PAYMENTSEC CCD"), -45.0)] * 2
    records = _credits(_records([*R3_35_SETTLEMENTS, *debits], bank="Chase", days=R3_35_DAYS))
    assert [_tier(record) for record in records] == [HELD_ALSO] * 3


AIL_ENTRY = ("ORIG CO NAME:AM INCOME LIFE ORIG ID:0000000001 DESC DATE:540305 CO ENTRY DESCR:{entry} TRACE#:0000001 "
             "EED:540305 IND ID:0000001 IND NAME:NORTHWIND PARTNERS")


@pytest.mark.parametrize(("text", "kind", "premium"), [
    (AIL_ENTRY.format(entry="INS PREMSEC PPD"), "other", True),
    (AIL_ENTRY.format(entry="INS PREMSEC:PPD"), "other", True),
    (AIL_ENTRY.format(entry="INS PREM"), "other", True),
    (AIL_ENTRY.format(entry="RETRY PYMT"), "other", True),
    ("FABRIKAM LIFE DES:INS PREM ID:2", "other", True),
    ("ELECTRONIC WITHDRAWAL TO FABRIKAM LIFE PREMIUM PAYMENT", "other", True),
    ("FABRIKAM LIFE DES:PREMIUMS ID:2", "other", True),
    ("BILL PAY FABRIKAM LIFE PREMIUM", "bill", True),
    # No premium or retry word: an agent's debit, a payee whose name only starts like one.
    (AIL_ENTRY.format(entry="AGENT DEBIT"), "other", False),
    ("PAID TO - FABRIKAM INS EFT PYMT CHK 0000000", "other", False),
    ("FABRIKAM PREMIER FOODS DES:INVOICE ID:2", "other", False),
    ("ONLINE TRANSFER TO FABRIKAM LIFE REF 0001", "circular", False),
])
def test_r3_03_each_non_lender_debit_records_a_premium_or_retry_word(text, kind, premium):
    # The premium is a flag, never a kind: the kinds are unchanged.
    from analysis.true_revenue.counter_debit_pairing import counter_debits

    record = tc.classify_transaction(text, -8.0, direction="debit")
    assert [(debit.kind, debit.premium) for debit in counter_debits([record], set()).other] == [(kind, premium)]


def test_r3_03_a_lender_debit_never_records_a_premium():
    from analysis.true_revenue.counter_debit_pairing import counter_debits

    record = tc.classify_transaction("FORWARD FINANCING DES:PREM ID:2 INDN:NORTHWIND LABS CO ID:0000000001 CCD", -500.0,
                                     direction="debit")
    debits = counter_debits([record], set())
    assert [debit.premium for debit in debits.lender] == [False] and not debits.other


def test_r3_03_also_debited_reads_a_released_insurer_s_carrier_debits():
    from analysis.true_revenue.counter_debit_pairing import also_debited

    def held(kind, *, cents=2500, recurring=False, premium=False, released=True):
        return also_debited(_counter("CONTOSO", ["CONTOSO"], released_insurer=released),
                            _debits(other=[("CONTOSO", ["CONTOSO"], kind, cents, recurring, premium)]))

    # A released credit: a one-off debit at another amount never holds it; a recurring one holds it unless it prints a
    # premium or retry word; circular money and a debit for its own amount always hold it.
    assert not held("other") and not held("bill") and not held("processor_fee")
    assert held("other", recurring=True) and not held("other", recurring=True, premium=True)
    assert held("bill", recurring=True) and not held("bill", recurring=True, premium=True)
    assert held("circular") and held("circular", premium=True) and held("circular", recurring=True, premium=True)
    for kind in ("other", "bill", "processor_fee", "circular"):
        assert held(kind, cents=100000) and held(kind, cents=100000, premium=True), kind
    assert not held("receiving_fee") and not held("receiving_fee", cents=100000)
    # A credit that is not released keeps today's answers, premium or not.
    for premium in (False, True):
        assert held("other", released=False, premium=premium)
        assert held("other", released=False, recurring=True, premium=premium)
        assert not held("bill", released=False, premium=premium)
        assert held("bill", released=False, recurring=True, premium=premium)
        assert held("circular", released=False, premium=premium)


def test_r3_03_the_released_insurer_fact():
    from analysis.true_revenue.counter_debit_pairing import counter_credit
    from analysis.true_revenue.model import CounterCredit

    assert CounterCredit.__dataclass_fields__["released_insurer"].default is False
    assert list(CounterCredit.__dataclass_fields__)[-1] == "released_insurer"
    released = _records([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0)], holder="CONTOSO AUTO REPAIR LLC")[0]
    held = _records([("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", 1234.0)],
                    holder="CONTOSO BAKERY LLC")[0]
    for record, flags in ((released, (False, True)), (held, (True, False))):
        text = lexical.revenue_text(record.normalized_description)
        credit = counter_credit(record, text, descriptor_payer.payer_region(text))
        assert (credit.insurer, credit.released_insurer) == flags


@pytest.mark.parametrize("text", [
    "WIRE TRANSFER FEE FROM BUSINESS CHECKING TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM OPERATING TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM PRIMARY CHECKING TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM BUS CHK TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM MONEY MARKET TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM *0000 TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM ...0000 TO CONTOSO LLC",
    "WIRE TRANSFER FEE FROM COMMERCIAL ANALYZED CHECKING TO CONTOSO LLC",
])
def test_r3_33_the_fee_for_the_holder_s_wire_from_a_named_account_is_circular(text):
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(description_text.normalize_transaction_description(text)) == "circular"


@pytest.mark.parametrize("text", [
    "WIRE TRANSFER FEE FROM SAMPLE TO TABLE FOODS INC",
    "WIRE TRANSFER FEE FROM CONTOSO TO GO INC",
    "FUNDS TRANSFER FEE TT CONTOSO TO G",
    "WIRE TRANSFER FEE FROM OPERATING ENGINEERS LOCAL 0",
    "WIRE TRANSFER FEE FROM 3M COMPANY",
    # The holder-name form: the documented residual (its debit reads the holder's name, so it holds nothing).
    "WIRE TRANSFER FEE FROM NORTHWIND LABS LLC TO CONTOSO LLC",
])
def test_r3_33_a_sender_named_after_from_still_reads_a_receiving_fee(text):
    from analysis.true_revenue.counter_debit_pairing import _counter_debit_kind

    assert _counter_debit_kind(description_text.normalize_transaction_description(text)) == "receiving_fee"


def test_r3_33_the_fee_for_the_holder_s_wire_from_its_checking_still_holds_the_payer_s_wires():
    wire = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:{n} SEQ:1/2 ORIG:CONTOSO LLC ID:99 SND BK:SAMPLE BANK "
            "ID:1")
    rows = [(wire.format(n=1), 7450.0), (wire.format(n=2), 7620.0)]
    fee = [("WIRE TRANSFER FEE FROM BUSINESS CHECKING TO CONTOSO LLC", -30.0)]
    assert [_tier(record) for record in _credits(_records([*rows, *fee], holder="NORTHWIND LABS LLC"))] == [
        HELD_ALSO] * 2
    assert [_tier(record) for record in _credits(_records(rows, holder="NORTHWIND LABS LLC"))] == [
        ("verified", None)] * 2


# --- Audit round 3, R3-B17 --------------------------------------------------------------------------------------------
# R3-77 (owner ruling 2026-10-02, the underwriter's Q2; standard A9; the hold's purpose, B6): a statement's bank's own
# posting-type label names no party, so on RBC (INSURANCE, INVESTMENT, FEES DUES, EQUIPMENT RENT, PAY EMPLOYEE VENDOR)
# and Scotiabank (INVESTMENT) the counter-debit readings read the party after it, on credits and debits alike; any
# other bank reads as before. R3-74 (the underwriter's Q9 of 2026-10-02, "a payer that also debits the account like a
# lender stays held"; §17.1 (5); standard C1, C2): a leading pre-authorized-debit label is cut from a debit and
# Scotiabank's ACHDEBIT is a label word, so a funder collecting under them is read by its name. R3-15 (standard C1,
# B6, A17; Q9; OQ3): a numbered company is compared by its number, read only where the numbered-company form prints.
# Fabricated rows (FABRIKAM, WOODGROVE, NORTHWIND, CONTOSO; numbers 1234567, 7654321, 1234-5678), 2054 dates.

RBC = "Royal Bank of Canada"
R3_B17_HOLDER = "NORTHWIND BAKERY LTD"
HELD_FINANCING = ("excluded_pending_review", "financing_named_payer")
HELD_LENDER = ("excluded_pending_review", "payer_debited_as_lender")
LENDER_SERVICES = ("counted_flagged", "lender_paid_for_services")
NUMBERED = ("counted_flagged", "numbered_company_payer")


def _r3_b17(rows, bank, *, holder=R3_B17_HOLDER):
    """The rows on consecutive days from 2054-03-02, as one statement of `bank`."""
    return _records(rows, holder=holder, bank=bank)


def _funding_and_ten(credit, debit, bank, *, amount=30000.0):
    """A funding (or any credit) and ten daily debits of 450.00: the credit's tier and reason."""
    records = _r3_b17([(credit, amount), *[(debit, -450.0)] * 10], bank)
    return [_tier(record) for record in _credits(records)]


def _debit_reading(text, bank, *, keep_places=False):
    record = _r3_b17([(text, -450.0)], bank)[0]
    return counter_debit_reading.counter_debit_debit_reading(record, keep_places=keep_places)[0]


@pytest.mark.parametrize("bank", [RBC, "RBC", "Banque Royale du Canada", "RBC Royal Bank", "royal bank of canada"])
def test_r3_77_rbc_s_insurance_label_names_no_payer(bank):
    reading = counter_debit_reading.counter_debit_payer_reading("INSURANCE SUNLIFE MED INS", bank=bank)
    assert reading.legacy == "SUNLIFE"
    assert "SUNLIFE" in reading.keys and not any(key.startswith("INSURANCE") for key in reading.keys)
    lender = counter_debit_reading.counter_debit_payer_reading("INSURANCE SUNLIFE MED INS", bank=bank, keep_places=True)
    assert lender.legacy == "SUNLIFE"


@pytest.mark.parametrize("bank", [None, "", "Chase", "Royal Bank of Scotland", "CIBC"])
def test_r3_77_another_bank_reads_a_leading_insurance_word_as_before(bank):
    reading = counter_debit_reading.counter_debit_payer_reading("INSURANCE SUNLIFE MED INS", bank=bank)
    assert reading.legacy == "INSURANCE" and "INSURANCE" in reading.keys


def test_r3_77_the_label_is_cut_once_and_only_before_a_word():
    assert counter_debit_reading._without_posting_type_label("INSURANCE SUNLIFE GRP", RBC) == "SUNLIFE GRP"
    assert counter_debit_reading._without_posting_type_label("INSURANCE", RBC) == "INSURANCE"
    assert counter_debit_reading._without_posting_type_label("INSURANCE INSURANCE SAMPLE", RBC) == "INSURANCE SAMPLE"
    assert counter_debit_reading._without_posting_type_label("FEES DUES SAMPLE ASSOCIATION", RBC) == "SAMPLE ASSOCIATION"
    assert counter_debit_reading._without_posting_type_label("PAY EMPLOYEE VENDOR CONTOSO", RBC) == "CONTOSO"
    assert counter_debit_reading._without_posting_type_label("SAMPLE INSURANCE CO", RBC) == "SAMPLE INSURANCE CO"
    assert counter_debit_reading._without_posting_type_label("INVESTMENT FABRIKAM CAPITAL INC", "Scotiabank") == "FABRIKAM CAPITAL INC"
    assert counter_debit_reading._without_posting_type_label("INSURANCE SAMPLE", "The Bank of Nova Scotia") == "INSURANCE SAMPLE"
    assert counter_debit_reading._without_posting_type_label("INVESTMENT FABRIKAM", "Chase") == "INVESTMENT FABRIKAM"


def test_r3_77_the_label_table_is_normalized():
    from analysis.classification_registry import BANK_POSTING_TYPE_LABELS

    for markers, labels in BANK_POSTING_TYPE_LABELS:
        assert markers and labels
        for word in (*markers, *labels):
            assert description_text.normalize_transaction_description(word) == word, word
        assert len(set(labels)) == len(labels)


def test_r3_77_rbc_s_debit_reads_the_party_after_its_label():
    reading = _debit_reading("Insurance THE PERSONAL", RBC)
    assert reading.legacy == "PERSONAL" and "INSURANCE" not in reading.keys
    # The same insurer's premium still names it.
    assert "SUNLIFE" in _debit_reading("Insurance SUNLIFE GRP", RBC).keys
    # Another bank's debit keeps the word.
    assert _debit_reading("INSURANCE THE PERSONAL", "Chase").legacy == "INSURANCE"


def test_r3_77_a_chase_credit_named_insurance_keeps_its_word():
    from analysis.true_revenue.counter_debit_pairing import counter_credit

    record = _credits(_records([("INSURANCE AUTO AUCTIONS DES:SELLER PMT ID:0001", 2400.0)], bank="Chase"))[0]
    text = lexical.revenue_text(record.normalized_description)
    credit = counter_credit(record, text, descriptor_payer.payer_region(text))
    assert credit.reading.legacy == "INSURANCE" and "INSURANCE" in credit.reading.keys


# R3-74: a funder collecting under a pre-authorized-debit label or RBC's and Scotiabank's INVESTMENT form.

@pytest.mark.parametrize(("credit", "debit", "bank"), [
    pytest.param("ACCOUNT PAYABLE PMT FABRIKAM CAPITAL", "INVESTMENT FABRIKAM PAD", RBC, id="rbc-investment"),
    pytest.param("ACCOUNTS PAYABLE FABRIKAM CAPITAL", "INVESTMENT FABRIKAM CAPITAL INC", "Scotiabank",
                 id="scotia-investment"),
    pytest.param("ACCOUNTS PAYABLE FABRIKAM CAPITAL", "MISC PAYMENT ACHDEBIT FABRIKAM CAPITAL CA", "Scotiabank",
                 id="scotia-achdebit"),
    pytest.param("MISC PAYMENT FABRIKAM CAPITAL VENDOR PMT", "PRE-AUTH DEBIT 0000000 FABRIKAM CAPITAL BUSINESS PAD",
                 "CIBC", id="cibc-pre-auth-reference"),
    pytest.param("MISC PAYMENT FABRIKAM CAPITAL VENDOR PMT", "PRE-AUTH DEBIT FABRIKAM CAPITAL", "CIBC",
                 id="cibc-pre-auth"),
])
def test_r3_74_a_funder_collecting_under_a_canadian_label_keeps_its_funding_held(credit, debit, bank):
    # Today the label word (INVESTMENT, ACHDEBIT, AUTH) is read as the payee and the Q9 release counts the funding.
    assert _funding_and_ten(credit, debit, bank) == [HELD_FINANCING]


def test_r3_74_a_payer_with_no_financing_root_collecting_under_rbc_s_investment_form_is_held():
    # Today verified payer_remittance_descriptor.
    assert _funding_and_ten("ACCOUNT PAYABLE PMT FABRIKAM TRADING", "INVESTMENT FABRIKAM PAD", RBC) == [HELD_LENDER]


@pytest.mark.parametrize("debit", [
    "BUSINESS PAD FABRIKAM CAPITAL", "MISC PAYMENT FABRIKAM CAPITAL", "LOAN FABRIKAM CAPITAL",
    "PRE-AUTHORIZED DEBIT FABRIKAM CAPITAL",
])
def test_r3_74_the_labels_that_already_read_the_funder_hold_as_today(debit):
    assert _funding_and_ten("ACCOUNT PAYABLE PMT FABRIKAM CAPITAL", debit, RBC) == [HELD_FINANCING]


def test_r3_74_the_funding_alone_stays_released():
    records = _r3_b17([("ACCOUNT PAYABLE PMT FABRIKAM CAPITAL", 30000.0)], RBC)
    assert [_tier(record) for record in _credits(records)] == [LENDER_SERVICES]


@pytest.mark.parametrize(("text", "bank", "keep_places", "legacy"), [
    # No Canadian bank: a leading INVESTMENT is the payee's own word.
    ("INVESTMENT PROPERTY GROUP LLC DES:RENT ID:0001", "Chase", False, "INVESTMENT"),
    ("Investment MERCH PAD", RBC, True, "MERCH"),
    ("Investment MERCH PAD", RBC, False, "MERCH"),
    ("PRE-AUTH DEBIT 0000000 WOODGROVE CAPITAL BUSINESS PAD", "CIBC", False, "WOODGROVE"),
    ("PRE-AUTH DEBIT WOODGROVE CAPITAL", "CIBC", False, "WOODGROVE"),
    ("PREAUTHORIZED DEBIT 0000000 0000000 WOODGROVE CAPITAL", "CIBC", False, "WOODGROVE"),
    ("PRE-AUTHORISED DEBIT WOODGROVE CAPITAL", None, False, "WOODGROVE"),
    ("MISC PAYMENT ACHDEBIT WOODGROVE CAPITAL CA", "Scotiabank", False, "WOODGROVE"),
])
def test_r3_74_the_debit_readings_read_the_payee_after_the_label(text, bank, keep_places, legacy):
    assert _debit_reading(text, bank, keep_places=keep_places).legacy == legacy


def test_r3_74_the_pad_label_keeps_a_numbered_company_s_number():
    assert counter_debit_reading._PAD_LABEL_BEFORE_PAYEE.sub("", "PRE AUTH DEBIT 0000000 1234567 ONTARIO INC BUSINESS PAD") == (
        "1234567 ONTARIO INC BUSINESS PAD")
    assert _debit_reading("PRE-AUTH DEBIT 0000000 1234567 ONTARIO INC BUSINESS PAD", "CIBC").number == "1234567"
    assert _debit_reading("PRE-AUTH DEBIT 1234-5678 QUEBEC INC", "CIBC").number == "12345678"
    # A label alone names nobody.
    assert _debit_reading("PRE-AUTH DEBIT 0000000", "CIBC") == classification_record._NO_COUNTER_DEBIT_READING


@pytest.mark.parametrize(("debit", "entity"), [
    ("PRE-AUTH DEBIT 0000000 FABRIKAM CAPITAL BUSINESS PAD", "Unidentified lender obligation"),
    ("PRE-AUTH DEBIT FABRIKAM CAPITAL", "Pre Auth Fabrikam Capital"),
])
def test_r3_74_the_d6_potential_lender_names_are_unchanged(debit, entity):
    # The cut lives only in the counter-debit readers (Not fixed: the D6 names, a lender-side batch).
    records = _r3_b17([("MISC PAYMENT FABRIKAM CAPITAL VENDOR PMT", 30000.0), *[(debit, -450.0)] * 10], "CIBC")
    assert {(record.classification, record.canonical_entity) for record in records if record.amount < 0} == {
        ("potential_lender", entity)}


# R3-15: numbered companies are compared by their number.

@pytest.mark.parametrize(("region", "number", "keys"), [
    ("1234567 ONTARIO", "1234567", set()),
    ("1234567 ONTARIO INC", "1234567", set()),
    ("1234 5678 QUEBEC INC", "12345678", set()),
    ("7654321 ONTA AP CC", "7654321", set()),
    ("1234567 ONTARIO INC O A NORTHWIND BAKERY", "1234567", {"NORTHWIND", "NORTHWINDBAKERY"}),
    ("1234567 NORTHWIND SUPPLY INC", "1234567", {"NORTHWIND", "NORTHWINDSUPPLY"}),
    ("NORTHWIND SUPPLY INC", None, {"NORTHWIND", "NORTHWINDSUPPLY"}),
])
def test_r3_15_a_credit_s_numbered_company_reads_its_number(region, number, keys):
    for keep_places in (False, True):
        reading = counter_debit_reading.counter_debit_payer_reading(region, keep_places=keep_places)
        assert (reading.number, set(reading.keys)) == (number, keys)


@pytest.mark.parametrize(("text", "number"), [
    ("BUSINESS PAD 1234567 ONTARIO INC", "1234567"),
    ("MISC PAYMENT 1234567 ONTARIO 55512", "1234567"),
    ("E-TRANSFER SENT 1234567 ALBERTA LTD - CONTOSO", "1234567"),
    ("ONLINE BILL PAYMENT 7654321 ONTARIO INC", "7654321"),
    ("TRANSFER TO 7654321 ONTA", "7654321"),
    ("1234-5678 QUEBEC INC", "12345678"),
    # Any digits alone are no number: a cheque, a reference before a name word.
    ("CHEQUE 1234567", None),
    ("BILL PAYMENT 1234567 NORTHWIND SUPPLY INC", None),
    ("MISC PAYMENT 123456 NORTH MOUNTAIN PAVING", None),
    ("MISC PAYMENT 12345678901 ONTARIO", None),
])
def test_r3_15_a_debit_reads_a_number_only_where_the_numbered_form_prints(text, number):
    assert _debit_reading(text, RBC).number == number


def test_r3_15_the_debit_s_word_readings_are_unchanged():
    reading = _debit_reading("BUSINESS PAD 1234567 ONTARIO INC", RBC)
    assert (reading.legacy, reading.keys, reading.heads) == (None, frozenset(), ())
    assert _debit_reading("TRANSFER TO 7654321 ONTA", RBC).legacy == "ONTA"


def test_r3_15_same_payer_reads_equal_numbers():
    from analysis.true_revenue.counter_debit_pairing import _same_payer

    def reading(number, words=()):
        return counter_debit_reading._counter_debit_reading(words[0] if words else None, [list(words)], number=number)

    for legacy in (False, True):
        assert _same_payer(reading("1234567"), reading("1234567"), legacy=legacy)
        assert not _same_payer(reading("1234567"), reading("7654321"), legacy=legacy)
        assert not _same_payer(reading(None), reading(None), legacy=legacy)
        assert not _same_payer(reading("1234567"), reading(None), legacy=legacy)
    # The words still match without a number.
    assert _same_payer(reading(None, ["CONTOSO"]), reading("1234567", ["CONTOSO"]), legacy=False)


def test_r3_15_the_number_is_the_reading_s_last_field():
    from analysis.classification.record import CounterDebitReading

    assert list(CounterDebitReading.__dataclass_fields__)[-1] == "number"
    assert CounterDebitReading.__dataclass_fields__["number"].default is None


@pytest.mark.parametrize(("credit", "debit"), [
    ("MISC PAYMENT 1234567 ONTARIO", "BUSINESS PAD 1234567 ONTARIO INC"),
    ("MISC PAYMENT 1234-5678 QUEBEC INC", "BUSINESS PAD 1234-5678 QUEBEC INC"),
])
def test_r3_15_a_numbered_funder_collecting_daily_keeps_its_funding_held(credit, debit):
    # Today counted numbered_company_payer: both readings were empty and the debits were dropped.
    records = _r3_b17([(credit, 30000.0), *[(debit, -450.0)] * 10], RBC)
    assert {record.classification for record in records if record.amount < 0} == {"potential_lender"}
    assert [_tier(record) for record in _credits(records)] == [HELD_LENDER]


def test_r3_15_another_number_never_holds_a_numbered_payer():
    assert _funding_and_ten("MISC PAYMENT 1234567 ONTARIO", "BUSINESS PAD 7654321 ONTARIO INC", RBC) == [NUMBERED]


def test_r3_15_a_numbered_affiliate_s_round_trip_is_held():
    rows = [("MISC PAYMENT 1234567 ONTARIO", 5000.0), ("ONLINE BANKING TRANSFER TO 1234567 ONTARIO INC", -5000.0)]
    assert [_tier(record) for record in _credits(_r3_b17(rows, RBC))] == [HELD_ALSO]
    assert [_tier(record) for record in _credits(_r3_b17(rows[:1], RBC))] == [NUMBERED]


@pytest.mark.parametrize(("debit", "expected"), [
    # Today counted: the bill payment to the same number read no word.
    pytest.param(("ONLINE BILL PAYMENT 7654321 ONTARIO INC", -4000.0), HELD_ALSO, id="same-number"),
    # Today held by the ONTA key, whatever number the debit prints.
    pytest.param(("TRANSFER TO 1111111 ONTA", -500.0), NUMBERED, id="another-number"),
])
def test_r3_15_bmo_s_cut_numbered_credit_is_compared_by_its_number(debit, expected):
    records = _r3_b17([("DIRECT DEPOSIT 7654321 ONTA AP CC", 4000.0), debit], "BMO")
    assert [_tier(record) for record in _credits(records)] == [expected]


def test_r3_15_a_numbered_company_s_debits_are_kept_and_recur_by_their_number():
    from analysis.true_revenue.counter_debit_pairing import _head_word, counter_debits

    # Each row read alone (no statement's lender reading), so they are the holder's other debits.
    rows = ["ONLINE BILL PAYMENT 1234567 ONTARIO INC"] * 2 + ["ONLINE BILL PAYMENT 7654321 ONTARIO INC"]
    debits = counter_debits([tc.classify_transaction(text, -450.0, direction="debit") for text in rows], set())
    assert not debits.lender
    assert [(debit.reading.number, debit.recurring) for debit in debits.other] == [
        ("1234567", True), ("1234567", True), ("7654321", False)]
    assert _head_word(counter_debit_reading._counter_debit_reading(None, [[]], number="1234567")) == "1234567"
    assert _head_word(counter_debit_reading._counter_debit_reading("CONTOSO", [["CONTOSO"]], number="1234567")) == "CONTOSO"
    assert _head_word(counter_debit_reading._counter_debit_reading(None, [[]])) is None
