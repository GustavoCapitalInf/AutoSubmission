"""Audit fix batch B5 (true revenue spec §5.2, §8.1, §8.4, §8.6 Q6, §8.8 Q8, §8.9, §20): the payer readers of the
layouts that print a label, a reference or a code where the payer would stand. Chase's real-time 'RECD FROM ABA/CONTR
BNK-<aba> FROM: <sender>' and PNC's 'CORPORATE ACH <entry> <ref> <payer> <ref>' read the payer after the label (I15);
an empty ACH field label is no payer (I55); a payment reference after DIRECT DEPOSIT, ACCOUNTS PAYABLE, MISC PAYMENT or
BILL PAYMENT is no numbered company (I59); American Express's 'ONLINE TRANSFER PAYMENT CREDIT ... EXTERNAL ...' is an
ACH template (I19); TD Canada Trust's trailing CPA code is an electronic-payment form, and its PAY code is payroll
(I37); Navy Federal's and Symitar's payer after a digit block is read (I26's reader). Fabricated rows only, in the
banks' printed formats; public names only where a bank prints its own or a registry lists them (Intuit)."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "NORTHWIND LABS INC"


def _records(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _tiers(rows, **kwargs):
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in _records(rows, **kwargs) if record.amount > 0]


FINANCING = ("excluded_pending_review", "financing_named_payer")
HOLDER_HELD = ("excluded_pending_review", "holder_name")
ONE_OFF = ("counted_flagged", "named_payer_one_off")
UNLABELLED = ("counted_flagged", "named_payer_unlabelled")
NO_PAYER = ("counted_flagged", "no_payer_printed")
NUMBERED = ("counted_flagged", "numbered_company_payer")
REPEATS = ("verified", "named_payer_repeats")
COMPANY = ("verified", "named_payer_company_form")


# I15: Chase's real-time layout prints the contra bank's label before the sender.

def _rtp(sender: str) -> str:
    return f"REAL TIME TRANSFER RECD FROM ABA/CONTR BNK-021000021 FROM: {sender} REF 1A2B3C INFO TEXT"


def test_chase_real_time_reads_the_sender_after_the_contra_bank_label():
    assert tc.payer_region(tc.revenue_text(tc.normalize_transaction_description(
        _rtp("FABRIKAM CAPITAL FUNDING LLC")))) == "FABRIKAM CAPITAL FUNDING LLC"


@pytest.mark.parametrize(("sender", "expected"), [
    ("FABRIKAM CAPITAL FUNDING LLC", FINANCING),
    ("NORTHWIND LABS INC", HOLDER_HELD),
    ("CONTOSO PAVING LLC", ("counted_flagged", "p2p")),
])
def test_chase_real_time_holds_read_the_real_sender(sender, expected):
    assert _tiers([(_rtp(sender), 2400.0)], bank="Chase") == [expected]


def test_two_customers_round_sums_by_real_time_are_two_senders():
    rows = [(_rtp("CONTOSO PAVING LLC"), 500.0), (_rtp("SAMPLE ROOFING LLC"), 700.0)]
    assert _tiers(rows, bank="Chase") == [("counted_flagged", "p2p"), ("counted_flagged", "p2p")]


def test_one_sender_s_repeated_round_sums_by_real_time_stay_held():
    rows = [(_rtp("CONTOSO PAVING LLC"), 500.0), (_rtp("CONTOSO PAVING LLC"), 700.0)]
    assert _tiers(rows, bank="Chase") == [("excluded_pending_review", "p2p_round_repeat")] * 2


# I15: PNC's CORPORATE ACH prints its entry and a reference before the payer.

def _pnc(entry: str, payer: str, n: int = 1) -> str:
    return f"CORPORATE ACH {entry} 000260010000000{n:02d} {payer} 12345678901234{n}"


def test_pnc_reads_the_payer_after_the_reference():
    assert tc.payer_region(_pnc("PAYMENTS", "CONTOSO PAVING")) == "CONTOSO PAVING"
    assert tc.payer_region(_pnc("EDI PAYMNT", "CONTOSO PAVING")) == "CONTOSO PAVING"
    assert tc.payer_region("CORPORATE ACH TLR 123456 00026001000000001 CONTOSO PAVING 1A2B") == "CONTOSO PAVING"
    # PNC's entry stays an entry field the holds and Q6 read.
    assert tc.entry_fields(_pnc("BILL PAY", "CONTOSO PAVING")) == "BILL PAY"


def test_pnc_reads_an_entry_of_ten_characters_at_most():
    # A payer printed first, longer than PNC's entry field, keeps its reading: its words are no entry.
    assert tc.payer_region("CORPORATE ACH CONTOSO PAVING 00026001000000001 SAMPLE 12345") == "CONTOSO PAVING"
    assert tc.pnc_corporate_ach("CORPORATE ACH CONTOSO PAVING 00026001000000001 SAMPLE 12345") is None


def test_pnc_four_different_payers_are_never_pooled():
    rows = [(_pnc("PAYMENTS", payer, n), 1000.0 + n)
            for n, payer in enumerate(("CONTOSO PAVING", "FABRIKAM ROOFING", "SAMPLE FOODS", "CONTOSO FOODS"))]
    assert _tiers(rows, bank="PNC Bank") == [ONE_OFF] * 4


def test_pnc_four_different_companies_verify_by_their_own_form():
    rows = [(_pnc("PAYMENTS", payer, n), 1000.0 + n)
            for n, payer in enumerate(("CONTOSO PAVING INC", "FABRIKAM ROOFING LLC", "SAMPLE FOODS CORP",
                                       "CONTOSO FOODS LTD"))]
    assert _tiers(rows, bank="PNC Bank") == [COMPANY] * 4


def test_pnc_one_payer_twice_verifies_as_a_repeat():
    rows = [(_pnc("PAYMENTS", "CONTOSO PAVING", 1), 1000.0), (_pnc("PAYMENTS", "CONTOSO PAVING", 2), 1200.0)]
    assert _tiers(rows, bank="PNC Bank") == [REPEATS, REPEATS]


@pytest.mark.parametrize(("entry", "payer", "expected"), [
    ("PAYMENTS", "NORTHWIND LABS", HOLDER_HELD),
    ("PAYMENTS", "FABRIKAM CAPITAL", FINANCING),
    ("FUNDING", "CONTOSO PAVING", FINANCING),
    ("SETTLEMENT", "CONTOSO PAVING", ("counted_flagged", "named_payer_purpose_refused")),
])
def test_pnc_holds_read_the_payer_and_the_entry(entry, payer, expected):
    assert _tiers([(_pnc(entry, payer), 1000.0)], bank="PNC Bank") == [expected]


def test_pnc_layout_with_no_reference_after_its_entry_keeps_its_reading():
    text = "CORPORATE ACH PAYROLL CONTOSO PAVING 00026001000000001"
    assert tc.payer_region(text) == "PAYROLL CONTOSO PAVING"
    assert _tiers([(text, 1000.0)], bank="PNC Bank") == [("excluded_pending_review", "payroll_or_salary")]


def test_pnc_intuit_merchant_deposits_are_not_held_beside_intuit_s_fees_and_financing():
    rows = [
        ("CORPORATE ACH DEPOSIT 00026001000000001 INTUIT 12345601 123456789012345", 1500.0),
        ("CORPORATE ACH DEPOSIT 00026001000000002 INTUIT 12345602 123456789012345", 2500.0),
        ("CORPORATE ACH TRAN FEE 00026001000000003 INTUIT 12345603 123456789012345", -45.0),
        ("CORPORATE ACH QBC PMTS INTUIT FINANCING 00026001000000004", -140.0),
    ]
    tiers = _tiers(rows, bank="PNC Bank")
    assert all(tier in {"verified", "counted_flagged"} for tier, _ in tiers), tiers


def test_pnc_intuit_deposits_are_quickbooks_payments_settlements_beside_the_holder_s_quickbooks_card_charge():
    # The audit brief's landing check (I15): once the payer reads INTUIT, the holder's own QuickBooks subscription,
    # charged to its PNC debit card, names the same word. PNC's 'CORPORATE ACH DEPOSIT <ref> INTUIT' is Intuit's
    # QuickBooks Payments merchant deposit, which every other layout verifies by the card-settlement form
    # ('INTUIT <ref> DEPOSIT'), so a registry entity claims it and no counter-debit hold reads it.
    rows = [
        ("CORPORATE ACH DEPOSIT 00026001000000001 INTUIT 12345601 123456789012345", 1500.0),
        ("CORPORATE ACH DEPOSIT 00026001000000002 INTUIT 12345602 123456789012345", 2500.0),
        ("1234 RECURRING DEBIT CARD INTUIT QBOOKS ONLINE 12345678901234567890 CL INTUIT C CA", -80.0),
        ("1234 RECURRING DEBIT CARD INTUIT QBOOKS ONLINE 12345678901234567891 CL INTUIT C CA", -80.0),
        ("CORPORATE ACH TRAN FEE 00026001000000003 INTUIT 12345603 123456789012345", -45.0),
    ]
    records = [record for record in _records(rows, bank="PNC Bank") if record.amount > 0]
    assert [(record.revenue_tier, record.revenue_match_method, record.revenue_canonical_entity)
            for record in records] == [("verified", "operating_income_descriptor", "QuickBooks Payments")] * 2


@pytest.mark.parametrize("word", ["QBC", "LOAN", "CAPITAL", "REFUND", "TAX"])
def test_pnc_intuit_rows_printing_a_financing_or_refund_word_are_no_settlement(word):
    text = f"CORPORATE ACH DEPOSIT 00026001000000001 INTUIT 12345601 {word}"
    assert [record.revenue_match_method for record in _records([(text, 1500.0)], bank="PNC Bank")] != [
        "operating_income_descriptor"]


# I55: an ACH field label printed with no value is no payer.

@pytest.mark.parametrize("rows", [
    [("ORIG CO ACH credit", 1500.0), ("ORIG CO ACH credit", 2000.0), ("ORIG CO ACH credit", 2500.0)],
    [("ORIG CO ACH credit", 1500.0)],
    [("ORIG CO DEPOSIT", 1500.0)],
    [("CO ENTRY DESCR ACH CREDIT", 1500.0), ("CO ENTRY DESCR ACH CREDIT", 2000.0)],
])
def test_an_empty_ach_field_label_names_no_payer(rows):
    assert _tiers(rows, bank="Chase Transaction Export") == [NO_PAYER] * len(rows)


def test_an_orig_co_label_is_never_part_of_the_payer():
    assert tc.payer_region("ORIG CO CONTOSO PAVING LLC ACH CREDIT") == tc.payer_region(
        "CONTOSO PAVING LLC ACH CREDIT")


def test_co_alone_stays_a_name_word():
    rows = [("CONTOSO PAVING CO DES:PAYMENT ID:1", 1500.0), ("CONTOSO PAVING CO DES:PAYMENT ID:2", 2000.0)]
    assert _tiers(rows, bank="Bank of America") == [REPEATS, REPEATS]


def test_chase_s_labelled_originator_still_repeats():
    row = ("ORIG CO NAME:CONTOSO PAVING ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENT SEC:CCD "
           "TRACE#:1 EED:540302 IND ID: IND NAME:NORTHWIND LABS")
    assert _tiers([(row, 1500.0), (row, 2000.0)], bank="Chase") == [REPEATS, REPEATS]


# I59: a payment reference before a named payer is no numbered company.

SCOTIA_HOLDER = "CONTOSO BAKERY LLC"


def test_scotiabank_bill_payment_reference_then_a_repeating_named_payer_verifies():
    rows = [(f"BILL PAYMENT 012345678{n} NORTHWIND SUPPLY INC", 1000.0 + n) for n in range(3)]
    assert _tiers(rows, holder=SCOTIA_HOLDER, bank="Scotiabank") == [REPEATS] * 3
    assert tc.payer_region("BILL PAYMENT 0123456789 NORTHWIND SUPPLY INC") == "NORTHWIND SUPPLY INC"


def test_a_town_after_a_misc_payment_reference_is_a_one_off_payer():
    rows = [("MISC PAYMENT 000123456 TOWN OF CONTOSOVILLE", 570.0)]
    assert _tiers(rows, holder=SCOTIA_HOLDER, bank="CIBC") == [ONE_OFF]


@pytest.mark.parametrize(("text", "bank"), [
    ("DIRECT DEPOSIT 1234567 ONTA AP CC", "BMO"),
    ("DIRECT DEPOSIT 1234567890 ONTARIO MSP DIV", "BMO"),
    ("DIRECT DEPOSIT 1234567 ONTARIO EDI EED", "BMO"),
    ("DIRECT DEPOSIT 1234567", "BMO"),
    ("MISC PAYMENT 1234567 ALBERTA LTD", "Royal Bank of Canada"),
    ("ACCOUNT PAYABLE PMT 123456 ONTARIO", "Royal Bank of Canada"),
    ("BILL PAYMENT 1234567890 ONTARIO INC", "Scotiabank"),
])
def test_a_genuine_numbered_company_stays_numbered(text, bank):
    assert _tiers([(text, 5000.0)], holder=SCOTIA_HOLDER, bank=bank) == [NUMBERED]


@pytest.mark.parametrize(("text", "entity"), [
    ("MISC PAYMENT 12345678901 MC GBL MC 1234567", "Global Payments"),
    ("MISC PAYMENT 12345678901 VISA GBL VI 1234567", "Global Payments"),
    ("MISC PAYMENT 12345678901 SAMPLE FIRST DATA CANADA LTD", "Fiserv"),
])
def test_scotiabank_card_settlements_in_the_reference_slot_stay_verified(text, entity):
    # The brief's guard: the template slot's card settlements stay claimed by their card form or the registry.
    [record] = _records([(text, 650.0)], holder=SCOTIA_HOLDER, bank="Scotiabank")
    assert record.revenue_tier == "verified"
    assert record.revenue_canonical_entity == entity


def test_bmo_s_fifteen_digit_reference_before_its_code_names_no_payer():
    assert _tiers([("DIRECT DEPOSIT 123456789012345 MSP DIV", 350.0)], holder=SCOTIA_HOLDER, bank="BMO") == [NO_PAYER]


def test_the_numbered_company_number_is_capped_at_ten_digits():
    assert not tc.numbered_company("DIRECT DEPOSIT 12345678901 MSP DIV")
    assert not tc.numbered_company("12345678901 ONTARIO INC", "12345678901 ONTARIO INC")
    assert tc.numbered_company("1234567890 ONTARIO INC", "1234567890 ONTARIO INC")


# I19: American Express's incoming ACH template.

AMEX_HOLDER = "NORTHWIND DISTRIBUTION"


def _amex(originator: str, entry: str, receiver: str = "XXXX5678 NORTHWIND DISTRIBUTION") -> str:
    return (f"ONLINE TRANSFER PAYMENT CREDIT {originator} {entry} 1234 {receiver} EXTERNAL FABRIKAM BANK "
            "ID 123456789012345")


def test_amex_template_reads_the_originator_and_cuts_the_receiver():
    text = _amex("CONTOSO SRE INC", "EFT")
    assert tc.payer_region(text) == "CONTOSO SRE INC EFT"
    assert "NORTHWIND" not in tc._before_receiver(text)


def test_amex_company_paying_twice_verifies_as_a_repeat():
    rows = [(_amex("CONTOSO SRE INC", "EFT"), 1500.0), (_amex("CONTOSO SRE INC", "EFT"), 2500.0)]
    assert _tiers(rows, holder=AMEX_HOLDER, bank="American Express") == [REPEATS, REPEATS]


def test_amex_company_paying_once_verifies_by_its_form():
    assert _tiers([(_amex("CONTOSO SRE INC", "EFT"), 1500.0)], holder=AMEX_HOLDER,
                  bank="American Express") == [COMPANY]


def test_amex_named_payer_once_is_a_one_off_ach_payer():
    assert _tiers([(_amex("CONTOSO PAVING", "ACH PAYMEN", "XXX1234 NORTHWIND DISTRIBUTION"), 1500.0)],
                  holder=AMEX_HOLDER, bank="American Express") == [ONE_OFF]


def test_amex_holder_s_own_pull_stays_held():
    assert _tiers([(_amex("NORTHWIND DISTRIB", "ACH PMT"), 1500.0)], holder=AMEX_HOLDER,
                  bank="American Express") == [HOLDER_HELD]


def test_amex_originator_s_transfer_entry_reads_as_the_same_entry_in_an_ach_des_layout():
    # The originator's own entry word TRANSFER (PayPal's, another business's) is transfer wording, as Bank of
    # America's 'DES:TRANSFER' is: a named transfer (T13, counted p2p), never Q6's repeat, and never a transfer with no
    # counterparty (the census's G4).
    amex = [(_amex("CONTOSO PAVING", "TRANSFER"), 1512.0), (_amex("CONTOSO PAVING", "TRANSFER"), 2534.0)]
    bofa = [("CONTOSO PAVING DES:TRANSFER ID:1 INDN:NORTHWIND DISTRIBUTION CO ID:1 CCD", 1512.0),
            ("CONTOSO PAVING DES:TRANSFER ID:2 INDN:NORTHWIND DISTRIBUTION CO ID:1 CCD", 2534.0)]
    assert _tiers(amex, holder=AMEX_HOLDER, bank="American Express") == _tiers(
        bofa, holder=AMEX_HOLDER, bank="Bank of America") == [("counted_flagged", "p2p")] * 2
    records = _records(amex, holder=AMEX_HOLDER, bank="American Express")
    text = tc.revenue_text(records[0].normalized_description)
    assert not tr.guard_facts(records[0], text)["transfer_no_counterparty"]
    # The payer region still reads the originator and its entry, never the transfer reader's FROM sender (none).
    assert tc.payer_region(text) == "CONTOSO PAVING TRANSFER"


@pytest.mark.parametrize(("text", "transfer"), [
    ("ONLINE TRANSFER PAYMENT CREDIT CONTOSO SRE INC EFT 1234", False),
    # Only American Express's label at the row's start: the words elsewhere stay transfer wording.
    ("CONTOSO TRANSFER PAYMENT CREDIT", True),
    ("XONLINE TRANSFER PAYMENT CREDIT", True),
    ("ONLINE TRANSFER FROM CHK 1234", True),
    ("ONLINE TRANSFER PAYMENT DEBIT CONTOSO", True),
])
def test_only_american_express_s_incoming_ach_label_is_no_transfer_wording(text, transfer):
    assert bool(tc._TRANSFER_WORDING.search(text)) is transfer


def test_amex_entry_wording_is_still_read():
    text = "ONLINE TRANSFER PAYMENT CREDIT CONTOSO GROUP 1234 DISBURSEME 0012 EXTERNAL SAMPLE BANK ID 123456789012345"
    assert _tiers([(text, 1500.0)], holder=AMEX_HOLDER, bank="American Express") == [
        ("excluded_pending_review", "non_sale_purpose")]


# I37: TD Canada Trust's trailing CPA code.

@pytest.mark.parametrize(("rows", "expected"), [
    ([("CONTOSO PLUMBING LTD AP", 1500.0), ("CONTOSO PLUMBING LTD AP", 2500.0)], [REPEATS, REPEATS]),
    ([("CONTOSO FOODS MSP", 1500.0), ("CONTOSO FOODS MSP", 2500.0)], [REPEATS, REPEATS]),
    ([("CONTOSO CONDO CORP BPY", 1500.0)], [COMPANY]),
    ([("CONTOSO FOODS APY", 1500.0)], [ONE_OFF]),
    ([("CONTOSO HOLDINGS DIV", 1500.0), ("CONTOSO HOLDINGS DIV", 2500.0)], [UNLABELLED, UNLABELLED]),
    ([("FABRIKAM STAFFING PAY", 1500.0)], [("excluded_pending_review", "payroll_or_salary")]),
])
def test_td_canada_trust_reads_its_trailing_cpa_code(rows, expected):
    assert _tiers(rows, bank="TD Canada Trust") == expected


@pytest.mark.parametrize(("rows", "expected"), [
    ([("CONTOSO PLUMBING LTD AP", 1500.0), ("CONTOSO PLUMBING LTD AP", 2500.0)], [UNLABELLED, UNLABELLED]),
    ([("FABRIKAM STAFFING PAY", 1500.0)], [UNLABELLED]),
])
def test_a_us_bank_s_trailing_words_are_no_cpa_code(rows, expected):
    assert _tiers(rows, bank="TD Bank") == expected


# I26's reader: the payer after Navy Federal's and Symitar's digit block.

@pytest.mark.parametrize(("text", "bank"), [
    ("DEPOSIT ACH PAID FROM 1234 {payer} 1000000001 030254", "Navy Federal Credit Union"),
    ("EXTERNAL DEPOSIT 1234 {payer} 1000000001 12345678901234 TRACER 123456789012345", "Symitar Credit Union"),
])
@pytest.mark.parametrize(("payer", "expected"), [
    ("FABRIKAM CAPITAL FUNDING", FINANCING),
    ("NORTHWIND LABS", HOLDER_HELD),
    ("FABRIKAM INSURANCE", ("excluded_pending_review", "insurer_named_payer")),
])
def test_the_payer_after_a_digit_block_is_read(text, bank, payer, expected):
    row = text.format(payer=payer)
    assert payer in tc.payer_region(row)
    assert _tiers([(row, 2500.0)], bank=bank) == [expected]


def test_navy_federal_payer_printed_without_a_digit_block_keeps_its_region():
    assert tc.payer_region("DEPOSIT ACH PAID FROM CONTOSO PAVING LLC 030254") == (
        "DEPOSIT ACH PAID FROM CONTOSO PAVING LLC")


# The census fact (tools/revenue_census.py: a Q5 or Q6 repeat that a label, an entry or a reference keyed).

@pytest.mark.parametrize(("text", "layout"), [
    (_rtp("CONTOSO PAVING LLC"), True),
    ("CORPORATE ACH PAYMENTS 00026001000000001 CONTOSO PAVING 123456789012345", True),
    ("ORIG CO ACH CREDIT", True),
    ("CO ENTRY DESCR ACH CREDIT", True),
    ("BILL PAYMENT 0123456789 NORTHWIND SUPPLY INC", True),
    ("DEPOSIT ACH PAID FROM 1234 CONTOSO PAVING 1000000001 030254", True),
    ("EXTERNAL DEPOSIT 1234 CONTOSO PAVING 1000000001", True),
    (_amex("CONTOSO SRE INC", "EFT"), True),
    # Not these layouts: a labelled originator, a numbered company's number, a payer printed without a reference.
    ("ORIG CO NAME CONTOSO PAVING ORIG ID 1234567890 CO ENTRY DESCR PAYMENT SEC CCD", False),
    ("DIRECT DEPOSIT 1234567 ONTA AP CC", False),
    ("DEPOSIT ACH PAID FROM CONTOSO PAVING LLC 030254", False),
    ("CONTOSO PAVING LLC DES PAYMENT ID 1", False),
    ("CORPORATE ACH PAYROLL CONTOSO PAVING 00026001000000001", False),
])
def test_payer_label_layout(text, layout):
    assert tc.payer_label_layout(tc.revenue_text(tc.normalize_transaction_description(text))) is layout
