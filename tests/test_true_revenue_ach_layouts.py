"""Audit fix batch B5 (true revenue spec §5.2, §8.1, §8.4, §8.6 Q6, §8.8 Q8, §8.9, §20): the payer readers of the
layouts that print a label, a reference or a code where the payer would stand. Chase's real-time 'RECD FROM ABA/CONTR
BNK-<aba> FROM: <sender>' and PNC's 'CORPORATE ACH <entry> <ref> <payer> <ref>' read the payer after the label (I15);
an empty ACH field label is no payer (I55); a payment reference after DIRECT DEPOSIT, ACCOUNTS PAYABLE, MISC PAYMENT or
BILL PAYMENT is no numbered company (I59); American Express's 'ONLINE TRANSFER PAYMENT CREDIT ... EXTERNAL ...' is an
ACH template (I19); TD Canada Trust's trailing CPA code is an electronic-payment form, and its PAY code is payroll
(I37); Navy Federal's and Symitar's payer after a digit block is read (I26's reader). Fabricated rows only, in the
banks' printed formats; public names only where a bank prints its own or a registry lists them (Intuit)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from tests.zelle_reading import rules_reading

HOLDER = "NORTHWIND LABS INC"


def _records(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _tiers(rows, **kwargs):
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    return [rules_reading(record, method=True)
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


# Audit round 2, R2-B11 (R33; §5.2 numbered company, T11, OQ3; amends B5's I59 line): a province word, its cut or a
# province code after the template's reference names a numbered company only when nothing but a legal form or its cut,
# BMO's code tail, a trade-name marker, a remittance word, a token holding digits, a one- or two-letter token or the
# field's end follows it. A letters-only word of three letters or more after it starts the payer's own name, so the
# reference is dropped and the payer read (NORTH MOUNTAIN, NEW HORIZON, NOVA SCOTIA POWER). A one- or two-letter second
# word ('CAN DO PLUMBING LTD') still reads numbered, the recorded residual.

R33_HOLDER = "FABRIKAM LTD"
REMITTANCE = ("verified", "payer_remittance_descriptor")


def test_r33_an_accounts_payable_payer_named_with_a_province_s_cut_verifies_by_its_remittance():
    rows = [("ACCOUNTS PAYABLE 0123456789 NORTH MOUNTAIN PAVING", 1234.56)]
    assert _tiers(rows, holder=R33_HOLDER, bank="Scotiabank") == [REMITTANCE]


@pytest.mark.parametrize("text", [
    "BILL PAYMENT 0123456789 NEW HORIZON PAVING INC",
    "BILL PAYMENT 0123456789 AB CONSTRUCTION LTD",
    "MISC PAYMENT 0123456789 NOVA SCOTIA POWER",
    "MISC PAYMENT 0123456789 NEW BRUNSWICK POWER",
    "BILL PAYMENT 0123456789 CONTOSO SUPPLY INC",
])
def test_r33_a_payer_named_with_a_province_word_after_a_reference_verifies_on_repeat(text):
    rows = [(text, 1234.56), (text, 1234.57)]
    assert _tiers(rows, holder=R33_HOLDER, bank="Scotiabank") == [REPEATS] * 2
    assert not tc.numbered_company(text)


@pytest.mark.parametrize(("text", "bank"), [
    ("BILL PAYMENT 1234567 ONTARIO INC", "Scotiabank"),
    ("BILL PAYMENT 1234567 ONTARIO LIMI", "Scotiabank"),
    ("BILL PAYMENT 1234567 NOVA SCOTIA LIMITED", "Scotiabank"),
    ("BILL PAYMENT 1234567 NOVA SCOTIA UNLIMITED CO", "Scotiabank"),
    ("BILL PAYMENT 1234567 NEW BRUNSWICK INC", "Scotiabank"),
    ("BILL PAYMENT 1234567 BRITISH COLUMBIA LTD", "Scotiabank"),
    ("DIRECT DEPOSIT 1234567 ONTA AP CC", "BMO"),
    ("DIRECT DEPOSIT 1234567 ONTARIO MSP DIV", "BMO"),
    ("DIRECT DEPOSIT 1234567 ONTARIO EDI EED", "BMO"),
    ("DIRECT DEPOSIT 1234567 B C LTD", "BMO"),
    ("DIRECT DEPOSIT 1234567 CANADA MSP", "BMO"),
    ("BILL PAYMENT 1234567 ONTARIO INC O/A NORTHWIND", "Scotiabank"),
    ("BILL PAYMENT 1234567 ONTARIO DBA NORTHWIND", "Scotiabank"),
    ("ACCOUNT PAYABLE PMT 123456 ONTARIO", "Royal Bank of Canada"),
    # RBC prints its payer in a fifteen-character field and the reference after it: a numbered company cut short.
    ("MISC PAYMENT 1234567 ALBERTA RMOD12345678", "Royal Bank of Canada"),
    ("BILL PAYMENT 1234567 ONTARIO 55512345", "Scotiabank"),
    ("BILL PAYMENT 1234567 ONTARIO INVOICE 1234", "Scotiabank"),
    ("BILL PAYMENT 1234567", "Scotiabank"),
    # The recorded residual: a one- or two-letter second word keeps the number.
    ("BILL PAYMENT 1234567 CAN DO PLUMBING LTD", "Scotiabank"),
])
def test_r33_a_genuine_numbered_company_keeps_its_number(text, bank):
    rows = [(text, 1234.56), (text, 1234.57)]
    assert _tiers(rows, holder=R33_HOLDER, bank=bank) == [NUMBERED] * 2
    assert tc.numbered_company(text)


@pytest.mark.parametrize(("text", "keeps"), [
    ("ONTARIO INC", True),
    ("ONTARIO", True),
    ("NOVA SCOTIA LIMITED", True),
    ("NOVA SCOTIA POWER", False),
    ("NEW BRUNSWICK POWER", False),
    ("NEW HORIZON PAVING", False),
    ("AB CONSTRUCTION LTD", False),
    ("ALBERTA RMOD12345678", True),
    ("ONTARIO PMT 1", True),
    ("ONTARIO REF 1", True),
    ("ONTA AP CC", True),
    ("CAN DO PLUMBING LTD", True),
])
def test_r33_the_guard_reads_the_token_after_the_province(text, keeps):
    assert (tc._KEEPS_ITS_NUMBER.match(text) is not None) is keeps


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


# Audit round 2, R2-B03 (R05; I01, Q2, the registry's note: a bank's name is never the payer's name): a payer region
# that names only a bank names no customer. Relay's 'ACH CREDIT <payer>' layout prints its bank as Thread Bank.

RELAY = "Thread Bank (Relay)"
NO_COUNTERPARTY = ("excluded_pending_review", "transfer_no_counterparty")
CHASE_ONLINE = ("ORIG CO NAME:CHASE ONLINE ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:ONLINE PMTSEC:CTX TRACE#:{n} "
                "EED:540305 IND ID:1234 IND NAME:NORTHWIND LABS INC TRN: {n}")
BANK_BILL_PAY = ("ORIG CO NAME:FABRIKAM BANK ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:INTD SEC:CIE TRACE#:{n} "
                 "EED:540305 IND NAME:NORTHWIND LABS")


@pytest.mark.parametrize(("bank", "texts"), [
    (RELAY, ["ACH CREDIT JPMORGAN CHASE"] * 2),
    (RELAY, ["ACH CREDIT SAMPLE STATE BANK"] * 2),
    (RELAY, ["ACH CREDIT ALLY BANK"]),
    ("U.S. Bank", ["ELECTRONIC DEPOSIT FROM FABRIKAM BANK"]),
    ("Brex", ["FABRIKAM BANK ACH"] * 2),
    ("Bank of America", ["MSPBNA DES:ACH TRNSFR ID:1234 INDN:NORTHWIND LABS INC CO ID:1234567890 PPD"]),
], ids=["relay-sending-bank-x2", "relay-bank-form-x2", "relay-ally", "usbank-bank-form", "brex-bank-ach-x2",
        "bofa-mspbna-transfer"])
def test_a_pull_naming_only_a_bank_is_held_as_a_transfer_with_no_counterparty(bank, texts):
    amounts = (5200.0, 1100.0)
    rows = [(text, amounts[index]) for index, text in enumerate(texts)]
    assert _tiers(rows, bank=bank) == [NO_COUNTERPARTY] * len(rows)


@pytest.mark.parametrize("text", [CHASE_ONLINE, BANK_BILL_PAY], ids=["own-bank-channel", "bank-bill-pay-entry"])
def test_a_bank_named_payer_with_an_entry_is_counted_with_no_payer_and_never_verified(text):
    rows = [(text.format(n=1), 3000.0), (text.format(n=2), 2000.0)]
    assert _tiers(rows, bank="Chase") == [NO_PAYER] * 2


@pytest.mark.parametrize(("bank", "texts", "expected"), [
    # A customer's repeated ACH stays Verified; a bank's merchant deposit and a card settlement keep their readings.
    (RELAY, ["ACH CREDIT CONTOSO SUPPLY LLC"] * 2, [REPEATS] * 2),
    ("Bank of America", ["BANK OF AMERICA DES:DEPOSIT ID:1234 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"] * 2,
     [REPEATS] * 2),
    ("Bank of America", ["SYNCHRONY BANK DES:MTOT DEP ID:1234 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"],
     [("verified", "operating_income_descriptor")]),
    # A company or a food bank whose name holds the bank word is no bank.
    (RELAY, ["ACH CREDIT LEFT BANK BAKERY LLC"] * 2, [REPEATS] * 2),
    (RELAY, ["ACH CREDIT SAMPLE FOOD BANK"] * 2, [REPEATS] * 2),
    # B02's account-description arm and B6's lending bank hold as before; a Zelle sender's bank is no sender.
    ("Brex", ["JPMORGAN CHASE SAVINGS 1234 ACH"], [NO_COUNTERPARTY]),
    ("Bank of America", ["NEWTEK BANK DES:GTL ID:1234 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"],
     [("excluded_pending_review", "financing_named_payer")]),
    ("Chase", ["ZELLE PAYMENT FROM CONTOSO SUPPLY BANK OF AMERICA 1234"], [("counted_flagged", "p2p")]),
    # A person's payment through a bank's P2P service names that bank as the sender's bank, never as a pull (Q4).
    ("Wells Fargo", ["BANK OF AMERICA P2P AB12345CD DEPOSIT", "BANK OF AMERICA P2P 1AB23CD45E PAT SAMPLE"],
     [UNLABELLED] * 2),
], ids=["customer-x2", "bofa-merchant-deposit-x2", "synchrony-mtot", "left-bank-bakery-x2", "food-bank-x2",
        "bank-savings-account", "newtek", "zelle", "bank-p2p-payments"])
def test_the_bank_only_reading_leaves_customers_settlements_and_named_banks_as_they_were(bank, texts, expected):
    amounts = (5200.0, 1100.0)
    rows = [(text, amounts[index]) for index, text in enumerate(texts)]
    assert _tiers(rows, bank=bank) == expected


@pytest.mark.parametrize(("region", "entry", "bank", "kind"), [
    ("JPMORGAN CHASE", "", RELAY, "sending"),
    ("ALLY BANK", "", RELAY, "sending"),
    ("MSPBNA", "ACH TRNSFR", "Bank of America", "sending"),
    ("CHASE ONLINE", "ONLINE PMT", "Chase", "own"),
    ("FABRIKAM BANK ACH", "", "Brex", "form"),
    ("SAMPLE STATE BANK N A", "", RELAY, "form"),
    ("MOUNTAIN SAMPLE CREDIT UNION", "", RELAY, "form"),
    ("SAMPLE BANCORP 1234", "", RELAY, "form"),
    # Not a bank alone: a settlement entry or originator, a company, a food bank, a bank's product word, a long name.
    ("BANK OF AMERICA", "DEPOSIT", "Bank of America", None),
    ("SYNCHRONY BANK", "MTOT DEP", "Bank of America", None),
    ("FABRIKAM MERCHANT BANK", "", RELAY, None),
    ("LEFT BANK BAKERY LLC", "", RELAY, None),
    ("SAMPLE FOOD BANK", "", RELAY, None),
    ("JPMORGAN CHASE SAVINGS", "", RELAY, None),
    ("NORTH SAMPLE VALLEY STATE BANK", "", RELAY, None),
    ("CONTOSO SUPPLY LLC", "", RELAY, None),
    ("", "", RELAY, None),
])
def test_bank_only_payer(region, entry, bank, kind):
    assert tr._bank_only_payer(region, entry, bank) == kind


def test_a_row_printing_a_p2p_label_names_no_bank_only_payer():
    assert tr._bank_only_payer("BANK OF AMERICA", "", "Wells Fargo", row="BANK OF AMERICA P2P AB12345CD DEPOSIT") is None
    assert tr._bank_only_payer("BANK OF AMERICA", "", "Wells Fargo", row="BANK OF AMERICA AB12345CD") == "sending"


def test_a_claimed_or_verified_row_never_takes_the_bank_only_pull():
    [record] = _records([("ACH CREDIT SAMPLE STATE BANK", 2600.0)], bank=RELAY)
    text = tc.revenue_text(record.normalized_description)
    region = tc.payer_region(text)
    assert tr._bank_only_pull(record, text, region)
    assert not tr._bank_only_pull(replace(record, revenue_match_method="recurring_operating_source"), text, region)
    assert not tr._bank_only_pull(replace(record, revenue_classification="verified_revenue"), text, region)


def test_g4_no_counted_or_verified_row_carries_the_bank_only_transfer_fact():
    # The census's G4 (§14.3): a row in True never reads transfer_no_counterparty, the new arm included.
    rows = [("ACH CREDIT JPMORGAN CHASE", 5200.0), ("ACH CREDIT JPMORGAN CHASE", 1100.0),
            ("ACH CREDIT CONTOSO SUPPLY LLC", 900.0), ("ACH CREDIT CONTOSO SUPPLY LLC", 800.0),
            (CHASE_ONLINE.format(n=1), 300.0), (BANK_BILL_PAY.format(n=1), 400.0)]
    for record in _records(rows, bank=RELAY):
        facts = tr.guard_facts(record, tc.revenue_text(record.normalized_description))
        in_true = record.revenue_tier in {"verified", "counted_flagged"}
        assert not (in_true and facts["transfer_no_counterparty"]), record.description


# Audit round 2, R2-B04 (R41): the holder's own push is held on the row alone, even where an earlier rule verified it
# (an accounts-payable entry, step 11) and on American Express's unlabelled receiver block; it never seeds a repeat.

PRODUCT = "BUSINESS CHECKING"
OWN_AP = "CONTOSO HARDWARE INC DES:{entry} ID:0001 INDN:CONTOSO HARDWARE INC CO ID:0000000000 CCD"
OWN_CHASE_AP = (
    "ORIG CO NAME:CONTOSO HARDWARE INC ORIG ID:0000000000 DESC DATE:540302 CO ENTRY DESCR:VENDOR PAYSEC:CCD "
    "TRACE#:000000000000000 EED:540302 IND ID:1 IND NAME:CONTOSO HARDWARE INC TRN: 0000000000TC"
)
AMEX_OWN = (
    "ONLINE TRANSFER PAYMENT CREDIT {originator} {entry} 0001 XXXXX0001 {receiver} EXTERNAL WELLS FARGO BANK "
    "ID 000000000000000"
)


def _reason_and_method(rows, bank):
    return [(record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method)
            for record in _records(rows, holder=PRODUCT, bank=bank) if record.amount > 0]


@pytest.mark.parametrize("text", [
    *(OWN_AP.format(entry=entry) for entry in ("VENDOR PMT", "AP PAYMENT", "ACCOUNTS PAYABLE", "INVOICE PMT")),
    OWN_CHASE_AP,
])
def test_r41_the_holder_s_own_accounts_payable_push_is_never_verified(text):
    bank = "Chase" if text.startswith("ORIG CO NAME") else "Bank of America"
    held = ("excluded_pending_review", "holder_name", "self_originated_holder")
    assert _reason_and_method([(text, 1000.0)], bank) == [held]
    assert _reason_and_method([(text, 1000.0), (text, 1250.0)], bank) == [held, held]


@pytest.mark.parametrize("text", [
    AMEX_OWN.format(originator="CONTOSO HARDWARE INC", entry="PAYMENT", receiver="CONTOSO HARDWARE INC"),
    AMEX_OWN.format(originator="CONTOSO HARDWARE INC", entry="TRANSFER", receiver="CONTOSO HARDWARE INC"),
    AMEX_OWN.format(originator="CONTOSO LLC", entry="PAYMENT", receiver="CONTOSO LLC"),
])
def test_r41_the_holder_funding_its_american_express_account_is_held(text):
    assert _tiers([(text, 1000.0)], holder=PRODUCT, bank="American Express") == [HOLDER_HELD]
    assert _tiers([(text, 1000.0), (text, 1250.0)], holder=PRODUCT, bank="American Express") == [HOLDER_HELD] * 2
    assert tr.self_originated(text, tc.payer_region(text), "American Express")


def test_r41_an_own_push_never_makes_another_row_a_repeat():
    # One payer key: the holder's own accounts-payable push (verified by step 11 before) and a row of that name to
    # another receiver. The own push is held and counts toward no repeat, so the other row is a one-off.
    own = "CONTOSO HARDWARE DES:VENDOR PMT ID:0001 INDN:CONTOSO HARDWARE CO ID:0000000000 CCD"
    other = "CONTOSO HARDWARE DES:PAYMENT ID:0002 INDN:SAMPLE OWNER CO ID:0000000000 CCD"
    tiers = _tiers([(own, 1000.0), (other, 1250.0)], holder=PRODUCT, bank="Bank of America")
    assert tiers == [HOLDER_HELD, ONE_OFF]


@pytest.mark.parametrize(("text", "bank", "expected"), [
    ("FABRIKAM SUPPLY LLC DES:VENDOR PMT ID:0001 INDN:CONTOSO HARDWARE INC CO ID:0000000000 CCD", "Bank of America",
     ("verified", "payer_remittance_descriptor")),
    (AMEX_OWN.format(originator="FABRIKAM SUPPLY LLC", entry="EFT", receiver="CONTOSO HARDWARE INC"),
     "American Express", COMPANY),
    (AMEX_OWN.format(originator="NORTHWIND HARDWARE INC", entry="PAYMENT", receiver="CONTOSO HARDWARE INC"),
     "American Express", COMPANY),
])
def test_r41_a_customer_s_payment_to_the_holder_keeps_its_verification(text, bank, expected):
    assert _tiers([(text, 1000.0)], holder=PRODUCT, bank=bank) == [expected]


def test_r41_a_processor_s_settlement_under_the_merchant_s_own_name_stays_verified():
    text = "SAMPLE MERCHANT DES:NET SETTLE ID:0001 INDN:SAMPLE MERCHANT CO ID:0000000000 CCD"
    rows = [(text, 300.0 + index) for index in range(3)]
    assert {tier[0] for tier in _tiers(rows, holder=PRODUCT, bank="Bank of America")} == {"verified"}


def test_r41_an_own_push_under_one_dollar_takes_the_floor_s_hold():
    [record] = _records([(OWN_AP.format(entry="VENDOR PMT"), 0.5)], holder=PRODUCT, bank="Bank of America")
    assert (record.revenue_tier, record.revenue_tier_reason) == ("excluded_pending_review", "non_sale_purpose")
    assert record.revenue_match_method != "self_originated_holder"


# Audit round 2, R2-B09 (R06): a bank's posting or channel label that prints CREDIT (BMO's EDI EFT CCD CREDIT, INTERNET
# CREDIT, PREAUTH CREDIT, Huntington's HIP CREDIT RCVD FROM, the French AVIS DE CREDIT, AUTOMATED CREDIT) is a template
# prefix, so the payer region starts after it and the label is never a lender's name word; an ACH entry's CREDIT NONE
# after a cut name and a credit union's DIVIDEND CREDIT are no financing root; U.S. Bank's WIRE CREDIT label is a wire
# channel field the financing veto never reads, while the row keeps reading as a wire.

R06_HOLDER = "NORTHWIND BAKERY LLC"
PUBLIC_PAYER = ("verified", "public_or_healthcare_payer")
REPEAT_WIRE = ("verified", "repeat_wire_sender")
US_WIRE = "WIRE CREDIT REF12345{n} SAMPLE BANK 0123B456{n}AB ORG {sender}"


def _us_wires(sender):
    return [(US_WIRE.format(n=1, sender=sender), 1500.0), (US_WIRE.format(n=2, sender=sender), 2500.0)]


@pytest.mark.parametrize(("bank", "rows", "expected"), [
    # A city's vendor payment and a supplier on BMO's EDI layout: Q6 reads the payer after the label.
    ("BMO", [("EDI EFT CCD CREDIT CCD CITY OF SAMPLEVILLE PAYMENT", 1500.0)], [PUBLIC_PAYER]),
    ("BMO", [("EDI EFT CCD CREDIT CCD FABRIKAM SUPPLY INC 1234", 1500.0)], [COMPANY]),
    # A bare label prints no payer.
    ("BMO", [("EDI EFT CCD CREDIT", 120.0)], [NO_PAYER]),
    ("CIBC", [("PREAUTH CREDIT", 120.0)], [NO_PAYER]),
    ("Desjardins", [("I AVIS DE CREDIT 12345", 120.0)], [NO_PAYER]),
    # A named payer after an unlabelled channel's label.
    ("Sample Bank", [("INTERNET CREDIT CONTOSO 1 23 45 ORDER", 2500.0)], [UNLABELLED]),
    ("CIBC", [("PREAUTH CREDIT CONTOSO SUPPLY", 300.0)], [UNLABELLED]),
    ("Fifth Third Bank", [("AUTOMATED CREDIT CONTOSO SUPPLY", 600.0)], [UNLABELLED]),
    # The ACH entry CREDIT NONE printed after a cut originator name.
    ("Sample Bank", [("ACH CREDIT FABRIKAM SUPPLY CREDIT NONE", 2500.0)], [ONE_OFF]),
    # A credit union's dividend is held as no sale, never as a lender's credit.
    ("Sample Federal Credit Union", [("DIVIDEND CREDIT", 2.5)], [("excluded_pending_review", "non_sale_purpose")]),
    # U.S. Bank's two wires from one company verify as a repeat sender.
    ("U.S. Bank", _us_wires("FABRIKAM SUPPLY INC"), [REPEAT_WIRE, REPEAT_WIRE]),
])
def test_r06_a_credit_posting_label_is_no_lender_s_name(bank, rows, expected):
    assert _tiers(rows, holder=R06_HOLDER, bank=bank) == expected


@pytest.mark.parametrize(("bank", "rows"), [
    # A lender named after the label is still held.
    ("BMO", [("EDI EFT CCD CREDIT CCD SAMPLE CAPITAL FUNDING LLC 1234", 9000.0)]),
    ("Sample Bank", [("INTERNET CREDIT SAMPLE LENDING LLC", 2400.0)]),
    ("Sample Bank", [("PREAUTH CREDIT SAMPLE ADVANCE LLC", 900.0)]),
    ("Sample Bank", [("ACH CREDIT SAMPLE CREDIT CORP", 900.0)]),
    ("Sample Bank", [("ACH CREDIT SAMPLE CREDIT UNIO CREDIT NONE", 900.0)]),
    ("U.S. Bank", _us_wires("SAMPLE CREDIT CORP")),
    # A credit union's own cut name as the originator (with the owner, I16) and a bank's name stay held.
    ("Contoso Credit Union", [("ACH CREDIT DIRECT PAY CONTOSO CREDIT ID1234567890 ZZ 123456 INV 123456", 4000.0)]),
    ("Brex", [("CAPITAL ONE ACH", 500.0)]),
])
def test_r06_a_lender_named_after_a_credit_label_is_still_held(bank, rows):
    assert _tiers(rows, holder=R06_HOLDER, bank=bank) == [FINANCING] * len(rows)


@pytest.mark.parametrize(("bank", "text", "expected"), [
    ("Sample Bank", "INTERNET CREDIT NORTHWIND BAKERY LLC", HOLDER_HELD),
    ("Chase", "ONLINE TRANSFER FROM LINE OF CREDIT 1234", ("non_revenue", "strong_non_revenue_rule")),
    ("Sample Federal Credit Union", "INTEREST CREDIT", ("non_revenue", "strong_non_revenue_rule")),
])
def test_r06_the_other_readings_beside_the_labels_are_unchanged(bank, text, expected):
    assert _tiers([(text, 900.0)], holder=R06_HOLDER, bank=bank) == [expected]


@pytest.mark.parametrize(("text", "region"), [
    ("EDI EFT CCD CREDIT CCD FABRIKAM SUPPLY INC 1234", "FABRIKAM SUPPLY INC"),
    ("EDI EFT CCD CREDIT FABRIKAM SUPPLY INC", "FABRIKAM SUPPLY INC"),
    ("INTERNET CREDIT CONTOSO 1 23 45 ORDER", "CONTOSO"),
    ("PREAUTH CREDIT CONTOSO SUPPLY", "CONTOSO SUPPLY"),
    ("HIP CREDIT RCVD FROM CONTOSO HEALTH PLAN", "CONTOSO HEALTH PLAN"),
    ("HIP CREDIT CONTOSO HEALTH PLAN", "CONTOSO HEALTH PLAN"),
    ("AVIS DE CREDIT CONTOSO SUPPLY", "CONTOSO SUPPLY"),
    ("I AVIS DE CREDIT CONTOSO SUPPLY 12345", "CONTOSO SUPPLY"),
    ("AUTOMATED CREDIT CONTOSO SUPPLY", "CONTOSO SUPPLY"),
    ("EDI EFT CCD CREDIT", ""),
    ("PREAUTH CREDIT", ""),
])
def test_r06_the_payer_region_starts_after_the_label(text, region):
    assert tc.payer_region(text) == region


@pytest.mark.parametrize("text", [
    "WIRE CREDIT REF123456 SAMPLE BANK 0123B4567AB ORG FABRIKAM SUPPLY INC",
    "WIRE CREDIT REF 123456 SAMPLE BANK ORG FABRIKAM SUPPLY INC",
    "INCOMING WIRE CREDIT ORG FABRIKAM SUPPLY INC",
    "DOMESTIC WIRE CREDIT ORG FABRIKAM SUPPLY INC",
    "INTL WIRE CREDIT ORG FABRIKAM SUPPLY INC",
])
def test_r06_a_wire_credit_label_is_no_financing_root_and_the_row_stays_a_wire(text):
    assert not tc._names_financing(tc._wire_financing_text(text))
    # The label is removed from the veto's text only: the row still reads as a wire, its sender after ORG.
    assert tc._is_wire_row(text)
    assert tc.payer_region(text) == "FABRIKAM SUPPLY INC"
    # A lender's name after the label still vetoes.
    assert tc._names_financing(tc._wire_financing_text(text.replace("FABRIKAM SUPPLY INC", "SAMPLE CREDIT CORP")))


def test_r06_a_cut_name_s_entry_and_a_dividend_are_no_financing_root():
    assert tr._CUT_NAME_ENTRY_CREDIT.sub("", "FABRIKAM SUPPLY CREDIT NONE") == "FABRIKAM SUPPLY"
    assert tr._CUT_NAME_ENTRY_CREDIT.sub("", "SAMPLE FUNDIN P CREDIT") == "SAMPLE FUNDIN P"
    assert tr._CUT_NAME_ENTRY_CREDIT.sub("", "DIVIDEND CREDIT") == "DIVIDEND"
    # CREDIT inside a lender's name stays.
    assert tr._CUT_NAME_ENTRY_CREDIT.sub("", "SAMPLE CREDIT CORP") == "SAMPLE CREDIT CORP"
    assert tr._CUT_NAME_ENTRY_CREDIT.sub("", "SAMPLE CREDIT UNIO CREDIT NONE") == "SAMPLE CREDIT UNIO"


# R2-B09 review round 1 (R06, a recorded residual, §20): a lender whose own name ends in CREDIT, printed with no entry
# word before the addenda's NONE, loses that word to the CREDIT NONE arm and is counted (0 corpus rows; the corpus's one
# CREDIT NONE row prints a cut sixteen-character name, and the brief's fifteen-character supplier must read the same).
# With an entry word printed it is still held, and a registry lender is read before T4.
@pytest.mark.parametrize(("text", "expected"), [
    ("ACH CREDIT SAMPLE AUTO CREDIT CREDIT NONE", FINANCING),
    ("ACH CREDIT SAMPLE AUTO CREDIT PAYMENT NONE", FINANCING),
    ("ACH CREDIT SAMPLE AUTO CREDIT NONE", ONE_OFF),
])
def test_r06_a_lender_name_ending_in_credit_before_none_is_a_recorded_residual(text, expected):
    assert _tiers([(text, 1000.0)], holder=R06_HOLDER, bank="Sample Bank") == [expected]


@pytest.mark.parametrize("text", ["PREAUTH CREDIT GST CANADA", "EDI EFT CCD CREDIT CCD GST CANADA",
                                  "AUTOMATED CREDIT RQ GST"])
def test_r06_a_government_s_refund_form_after_a_label_is_still_read(text):
    assert _tiers([(text, 900.0)], holder=R06_HOLDER, bank="Sample Bank") == [("non_revenue", "strong_non_revenue_rule")]


# Audit round 2, R2-B09 (R31): American Express's label 'ONLINE TRANSFER PAYMENT CREDIT' is no transfer wording, an
# electronic-payment form and a template prefix only when an originator word follows it; the bare label, or the label
# followed only by FROM, an account word, a masked account, an ID or digits, keeps its transfer reading (Q2: held).

R31_TAILS = (" FROM CHK XXXX1234", " FROM SAVINGS 1234", "", " CHECKING XXXX1234", " XXXX1234", " ID 123456789012345",
             " 1234")


@pytest.mark.parametrize("bank", ["American Express", "Sample Bank"])
@pytest.mark.parametrize("tail", R31_TAILS)
def test_r31_the_label_with_no_originator_after_it_is_a_bare_transfer(bank, tail):
    text = "ONLINE TRANSFER PAYMENT CREDIT" + tail
    assert _tiers([(text, 5000.0)], holder=AMEX_HOLDER, bank=bank) == [
        ("excluded_pending_review", "transfer_no_counterparty")]
    assert tc._TRANSFER_WORDING.search(text)
    assert not tc._REVENUE_TEMPLATE_PREFIX.match(text)


@pytest.mark.parametrize(("text", "expected"), [
    (_amex("CONTOSO SRE INC", "EFT"), COMPANY),
    # Cut before EXTERNAL, or right after the id: the originator still follows the label.
    ("ONLINE TRANSFER PAYMENT CREDIT CONTOSO SRE INC EFT 1234 XXXX5678 NORTHWIND DISTRIBUTION", COMPANY),
    ("ONLINE TRANSFER PAYMENT CREDIT CONTOSO SRE INC EFT 1234", COMPANY),
    (_amex("SAMPLE SUPPLY CO", "PAYMENT"), ONE_OFF),
    ("ONLINE TRANSFER PAYMENT CREDIT NORTHWIND DISTRIBUTION XXXX1234", HOLDER_HELD),
    (_amex("FABRIKAM CAPITAL FUNDING", "PAYMENT"), FINANCING),
    (_amex("IRS TREAS 310", "TAX REF"), ("non_revenue", "strong_non_revenue_rule")),
    ("ONLINE TRANSFER FROM CHK XXXX1234", ("non_revenue", "strong_non_revenue_rule")),
    ("ONLINE TRANSFER CREDIT CONTOSO LLC TRANSFER 1234 CONTOSO LLC CHECKING XXXXXXXX1234 FABRIKAM BANK",
     ("excluded_pending_review", "transfer_account_designation")),
])
def test_r31_the_label_before_an_originator_keeps_its_ach_reading(text, expected):
    assert _tiers([(text, 5000.0)], holder=AMEX_HOLDER, bank="American Express") == [expected]


@pytest.mark.parametrize(("text", "exempt"), [
    ("ONLINE TRANSFER PAYMENT CREDIT CONTOSO SRE INC EFT 1234", True),
    ("ONLINE TRANSFER PAYMENT CREDIT C", True),
    ("ONLINE TRANSFER PAYMENT CREDIT", False),
    ("ONLINE TRANSFER PAYMENT CREDIT TO CONTOSO", False),
    ("ONLINE TRANSFER PAYMENT CREDIT CHECKG 1234", False),
    ("ONLINE TRANSFER PAYMENT CREDIT SVGS 1234", False),
    ("ONLINE TRANSFER PAYMENT CREDIT DDA 1234", False),
    ("ONLINE TRANSFER PAYMENT CREDIT MMA 1234", False),
    ("ONLINE TRANSFER PAYMENT CREDIT ACCOUNT 1234", False),
    ("ONLINE TRANSFER PAYMENT CREDIT XXX1234", False),
    # A word that only starts like an account word is an originator's.
    ("ONLINE TRANSFER PAYMENT CREDIT CHKSTAR LLC EFT 1234", True),
    ("ONLINE TRANSFER PAYMENT CREDIT IDEAL SUPPLY INC EFT 1234", True),
])
def test_r31_the_three_label_exceptions_read_one_originator_gate(text, exempt):
    assert (tc._TRANSFER_WORDING.search(text) is None) is exempt
    assert (tc._REVENUE_TEMPLATE_PREFIX.match(text) is not None) is exempt
    assert bool(tc._ELECTRONIC_PAYMENT_FORM.search(text)) is exempt


def test_r31_the_label_followed_by_from_keeps_its_transfer_wording():
    # 'CREDIT FROM' is an electronic-payment form of its own (unchanged); the label's TRANSFER stays transfer wording.
    text = "ONLINE TRANSFER PAYMENT CREDIT FROM CONTOSO"
    assert tc._TRANSFER_WORDING.search(text)
    assert not tc._REVENUE_TEMPLATE_PREFIX.match(text)
