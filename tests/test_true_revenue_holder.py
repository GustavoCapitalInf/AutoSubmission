"""Audit fix batch B9 (true revenue spec §5.2, §8.1, §20): the holder's identity. The statement carries the holder's
name as its own field (Statement.holder_name, read from the header or the address block), apart from the product name
(account_name), and the holder tests read it (I13); a row whose ACH or EFT originator is its own receiver field, or
whose incoming wire's sender is its beneficiary, is the holder's own money and is held as holder_name, a processor's
settlement or payout under the merchant's own name aside (I13); a statement with no holder name says so
(holder_unscreened, I13); First Citizens' DBA lump sums are the holder's (I38); a short initialism and a one-word holder
read as names, never as industry words (I58). Fabricated rows only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE and invented
initialisms), in the banks' printed formats; public names only where a bank prints its own (Mercury's MERCURYACH,
Chase's Fedwire) or a processor's form (NET SETTLE, NETSWEEP, FINTECHEFT, BANKCARD)."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER_NAME = ("excluded_pending_review", "holder_name")
REPEATS = ("verified", "named_payer_repeats")
COMPANY = ("verified", "named_payer_company_form")
ONE_OFF = ("counted_flagged", "named_payer_one_off")
WIRE = ("counted_flagged", "wire_named_sender")
WIRE_REPEATS = ("verified", "repeat_wire_sender")
P2P = ("counted_flagged", "p2p")
REMITTANCE = ("verified", "payer_remittance_descriptor")
NET_SETTLE = ("verified", "operating_income_descriptor")


def _statement(rows, *, account_name=None, holder_name=None, bank=None):
    return Statement(account_name=account_name, holder_name=holder_name, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ])


def _tiers(rows, **kwargs):
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in classify_statement_transactions(_statement(rows, **kwargs)) if record.amount > 0]


def _twice(text, amount=1500.0, **kwargs):
    return _tiers([(text, amount), (text, amount + 250.0)], **kwargs)


# --- I13: the statement's holder field ---------------------------------------------------------------------------

def test_the_statement_carries_the_holder_s_name_apart_from_the_product():
    statement = Statement(account_name="Business Complete Checking", holder_name="NORTHWIND FISH LLC")
    assert statement.holder_name == "NORTHWIND FISH LLC"
    assert Statement().holder_name is None
    assert "holder" not in (Statement.model_fields["account_name"].description or "").lower()
    assert "holder" in (Statement.model_fields["holder_name"].description or "").lower()


@pytest.mark.parametrize("account_name", [None, "Checking", "TD Business Simple Checking", "INSTANCES AMOUNT"])
def test_the_holder_s_name_field_holds_the_holder_s_own_zelle_whatever_the_product(account_name):
    text = "ZELLE PAYMENT FROM NORTHWIND FISH LLC CONF 1234567890"
    assert _tiers([(text, 900.0)], account_name=account_name, holder_name="NORTHWIND FISH LLC") == [HOLDER_NAME]
    assert _tiers([(text, 900.0)], account_name=account_name) == [P2P]


def test_the_holder_s_name_field_holds_the_holder_s_own_wire_and_transfer():
    wire = "WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:NORTHWIND FISH LLC ID:1234567890"
    transfer = "ONLINE TRANSFER FROM NORTHWIND FISH LLC REF 1234567890"
    for text in (wire, transfer):
        assert _tiers([(text, 4000.0)], holder_name="NORTHWIND FISH LLC") == [HOLDER_NAME]
        assert _tiers([(text, 4000.0)], holder_name=None)[0] != HOLDER_NAME


def test_the_holder_reading_prefers_the_printed_holder_name():
    assert tc.holder_reading("Business Complete Checking", "NORTHWIND FISH LLC") == "NORTHWIND FISH LLC"
    assert tc.holder_reading("NORTHWIND FISH LLC", None) == "NORTHWIND FISH LLC"
    assert tc.holder_reading(None, "  ") is None
    assert tc.holder_reading(None, None) is None


@pytest.mark.parametrize("name", [
    "INSTANCES AMOUNT", "AMOUNT", "INSTANCES AMOUNT BEGINNING BALANCE 1,234.56", "Business Complete Checking",
    "BMO BUS CKG", "GENERAL CHECKING",
])
def test_a_grid_header_or_a_product_never_names_the_holder(name):
    assert not tr._usable_holder_name(name)
    assert tc.holder_words(name) == ()


@pytest.mark.parametrize(("name", "usable", "names_the_holder"), [
    ("NORTHWIND FISH LLC", True, True),
    ("SAMPLE NORTHWIND FISHERIES", True, True),
    # A bare two-word fragment (no legal form) needs corroboration: it never switches the receiver fields off.
    ("NORTHWIND FISH", True, False),
])
def test_a_bare_two_word_fragment_needs_corroboration(name, usable, names_the_holder):
    assert tr._usable_holder_name(name) is usable
    assert tr._holder_name_known(name) is names_the_holder


def test_a_bare_two_word_fragment_leaves_the_receiver_fields_read():
    rows = [
        ("FABRIKAM SUPPLY DES PAYMENT ID 1 INDN NORTHWIND FISH LLC CO ID 1234567890 CCD", 700.0),
        ("CONTOSO DINER DES PAYMENT ID 2 INDN NORTHWIND FISH LLC CO ID 1234567891 CCD", 800.0),
        ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:NORTHWIND FISH LLC ID:1", 4000.0),
    ]
    assert _tiers(rows, account_name="SAMPLE FISHERY")[2] == HOLDER_NAME
    # A name that names the holder switches the receiver fields off; the wire is then a named sender's.
    assert _tiers(rows, account_name="SAMPLE FISHERY LLC")[2] == WIRE


# --- I13: the row-level self test ----------------------------------------------------------------------------------

MERCURY = (
    "NORTHWIND MARINE LLC DES:MERCURYACH ID:MRCR ABCDE12345 INDN:NORTHWIND MARINE LLC CO ID:1234567890 CCD "
    "PMT INFO:FROM NORTHWIND MARINE LLC VIA MERCURY"
)
FEDWIRE = (
    "FEDWIRE CREDIT VIA: SAMPLE BANK/012345678 B/O: NORTHWIND MARINE LLC SAMPLEVILLE TX 75001 US REF: CHASE "
    "NYC/CTR/BNF={bnf} SAMPLEVILLE TX 75001 US/AC-000000001234 RFB=NOTPROVIDED IMAD: 0302MMQFMP2N000123 TRN: 1234567890FF"
)
CHASE_ACH = (
    "ORIG CO NAME:{orig} ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:{entry}SEC:CCD TRACE#:111000020000001 "
    "EED:540302 IND ID:1 IND NAME:{receiver} TRN: 1234567890TC"
)


@pytest.mark.parametrize("account_name", [None, "Checking", "Business Complete Checking"])
def test_the_holder_s_own_ach_push_is_held_with_no_holder_name_known(account_name):
    assert _twice(MERCURY, account_name=account_name) == [HOLDER_NAME, HOLDER_NAME]


def test_a_third_party_s_ach_to_the_holder_still_verifies_on_repeat():
    text = MERCURY.replace("INDN:NORTHWIND MARINE LLC", "INDN:CONTOSO DINER LLC")
    assert _twice(text) == [REPEATS, REPEATS]


@pytest.mark.parametrize("entry", ["ACH PUSH ", "PAYMENT ", "ACH PMT "])
def test_chase_s_receiver_field_names_the_holder_s_own_push(entry):
    text = CHASE_ACH.format(orig="NORTHWIND MARINE", entry=entry, receiver="NORTHWIND MARINE LLC")
    assert _twice(text)[0] == HOLDER_NAME
    other = CHASE_ACH.format(orig="FABRIKAM SUPPLY", entry=entry, receiver="NORTHWIND MARINE LLC")
    assert _twice(other)[0] != HOLDER_NAME


@pytest.mark.parametrize("account_name", [None, "Chase Total Business Checking"])
def test_a_wire_whose_sender_is_its_beneficiary_is_held(account_name):
    text = FEDWIRE.format(bnf="NORTHWIND MARINE LLC")
    assert _twice(text, 6000.0, account_name=account_name) == [HOLDER_NAME, HOLDER_NAME]


def test_a_wire_to_the_holder_from_another_company_is_q5_s():
    text = FEDWIRE.format(bnf="CONTOSO DINER LLC")
    assert _twice(text, 6000.0) == [WIRE_REPEATS, WIRE_REPEATS]
    assert _tiers([(text, 6000.0)]) == [WIRE]


def test_the_wire_veto_and_the_hold_read_one_beneficiary_test():
    text = tc.revenue_text(tc.normalize_transaction_description(FEDWIRE.format(bnf="NORTHWIND MARINE LLC")))
    region = tc.payer_region(text)
    assert tc.wire_sender_is_beneficiary(text, region)
    other = tc.revenue_text(tc.normalize_transaction_description(FEDWIRE.format(bnf="CONTOSO DINER LLC")))
    assert not tc.wire_sender_is_beneficiary(other, tc.payer_region(other))


def test_capital_one_s_trailing_receiver_names_the_holder_s_own_deposit():
    own = "ACH DEPOSIT NORTHWIND MARINE TRANSFER 123456 NORTHWIND MARINE LLC"
    other = "ACH DEPOSIT FABRIKAM SUPPLY PAYMENT 123456 NORTHWIND MARINE LLC"
    # One shared first word is not the holder's name.
    first_word = "ACH DEPOSIT NORTHWIND SUPPLY PAYMENT 123456 NORTHWIND MARINE LLC"
    assert _tiers([(own, 2500.0)], bank="Capital One") == [HOLDER_NAME]
    assert _tiers([(other, 2500.0)], bank="Capital One") != [HOLDER_NAME]
    assert _tiers([(first_word, 2500.0)], bank="Capital One") != [HOLDER_NAME]
    # Another bank's row is never read for Capital One's unlabelled receiver.
    assert _tiers([(own, 2500.0)], bank="Wells Fargo") != [HOLDER_NAME]


def test_a_personal_transfer_from_the_holder_s_name_is_held():
    text = "NORTHWIND MARINE LLC DES:TRANSFER ID: INDN:NORTHWIND MARINE LLC CO ID:1234567890 CCD"
    assert _tiers([(text, 400.0)]) == [HOLDER_NAME]


# Processor settlement and payout forms print the merchant's own name as their originator: never the holder's push.

def test_net_settle_under_the_merchant_s_own_name_stays_verified():
    text = CHASE_ACH.format(orig="CONTOSO TRADING C", entry="NET SETTLE", receiver="CONTOSO TRADING CO LLC")
    rows = [(text, 300.0 + index) for index in range(3)]
    assert _tiers(rows) == [NET_SETTLE] * 3
    assert _tiers(rows, holder_name="CONTOSO TRADING CO LLC") == [NET_SETTLE] * 3


@pytest.mark.parametrize("entry", ["NETSWEEP ", "FINTECHEFT ", "BANKCARD DEP ", "MERCH DEP "])
@pytest.mark.parametrize("holder_name", [None, "CONTOSO TRADING CO LLC"])
def test_a_processor_s_form_under_the_merchant_s_own_name_is_never_held_as_the_holder(entry, holder_name):
    text = CHASE_ACH.format(orig="CONTOSO TRADING CO", entry=entry, receiver="CONTOSO TRADING CO LLC")
    tiers = _twice(text, 300.0, holder_name=holder_name)
    assert HOLDER_NAME not in tiers
    assert all(tier[0] in ("verified", "counted_flagged") for tier in tiers)


@pytest.mark.parametrize("merchant", ["NORTHWIND BAKERY LLC", "3SAMPLE ENTERPRISES"])
def test_a_processor_s_payout_under_the_merchant_s_descriptor_is_never_held_as_the_holder(merchant):
    descriptor = merchant[:10]
    text = f"{merchant} DES:{descriptor} ID:ST-ABCDE12345 INDN:{merchant} CO ID:1234567890 CCD"
    assert HOLDER_NAME not in _twice(text, 450.0)


@pytest.mark.parametrize(("text", "own"), [
    (MERCURY, True),
    (FEDWIRE.format(bnf="NORTHWIND MARINE LLC"), True),
    (CHASE_ACH.format(orig="NORTHWIND MARINE", entry="ACH PUSH ", receiver="NORTHWIND MARINE LLC"), True),
    (CHASE_ACH.format(orig="CONTOSO TRADING C", entry="NET SETTLE", receiver="CONTOSO TRADING CO LLC"), False),
    (CHASE_ACH.format(orig="CONTOSO TRADING CO", entry="NETSWEEP ", receiver="CONTOSO TRADING CO LLC"), False),
    (CHASE_ACH.format(orig="CONTOSO TRADING CO", entry="FINTECHEFT ", receiver="CONTOSO TRADING CO LLC"), False),
    (MERCURY.replace("INDN:NORTHWIND MARINE LLC", "INDN:CONTOSO DINER LLC"), False),
    (FEDWIRE.format(bnf="CONTOSO DINER LLC"), False),
    # One shared first word is not the holder's name.
    ("NORTHWIND DES:TRANSFER ID:1 INDN:NORTHWIND MARINE LLC CO ID:1 CCD", False),
])
def test_the_self_test_reads_the_row_alone(text, own):
    revenue = tc.revenue_text(tc.normalize_transaction_description(text))
    assert tr.self_originated(revenue, tc.payer_region(revenue)) is own


# --- I13: a statement that names no holder says so ----------------------------------------------------------------

@pytest.mark.parametrize(("account_name", "holder_name", "unscreened"), [
    (None, None, True),
    ("INSTANCES AMOUNT", None, True),
    ("Business Complete Checking", None, True),
    (None, "NORTHWIND FISH LLC", False),
    ("NORTHWIND FISH LLC", None, False),
    ("SAMPLE NORTHWIND FISHERIES", None, False),
])
def test_holder_unscreened_says_when_no_holder_name_is_known(account_name, holder_name, unscreened):
    statement = _statement([("ZELLE PAYMENT FROM CONTOSO DINER LLC CONF 1", 500.0)],
                           account_name=account_name, holder_name=holder_name)
    records = classify_statement_transactions(statement)
    assert tr.holder_unscreened(records) is unscreened
    assert compute_metrics(statement, classifications=records).holder_unscreened is unscreened


def test_the_receiver_fields_are_still_read_beside_a_parser_holder_name():
    # The bank prints the owner as the receiver; the parser reads the business from the mailing block. The owner's own
    # money stays held as the holder's, as it was before the parser read the business's name.
    rows = [
        ("FABRIKAM SUPPLY DES PAYMENT ID 1 INDN SAMPLE PERSON OWNER CO ID 1234567890 CCD", 700.0),
        ("CONTOSO DINER DES PAYMENT ID 2 INDN SAMPLE PERSON OWNER CO ID 1234567891 CCD", 800.0),
        ("ZELLE PAYMENT FROM SAMPLE PERSON OWNER CONF 1234567890", 900.0),
    ]
    assert _tiers(rows, holder_name="NORTHWIND LIMO INC")[2] == HOLDER_NAME
    assert _tiers(rows)[2] == HOLDER_NAME


def test_the_holder_s_name_printed_after_another_payer_is_its_unlabelled_receiver():
    # A carrier's credit prints the agency's trade name after its own, with no label: the payer is the carrier.
    holder = "CONTOSO LLC DBA NORTHWIND HARBOR AGENCY, LLC"
    text = "FABRIKAM INSURANCE MISC NORTHWIND HARBOR AGENC"
    assert _tiers([(text, 900.0)], holder_name=holder) != [HOLDER_NAME]
    assert not tc.holder_named(text, holder)
    # The holder's own name alone, or leading the row, is still the holder's.
    assert tc.holder_named("NORTHWIND HARBOR", holder)
    assert tc.holder_named("NORTHWIND HARBOR AGENCY LLC FABRIKAM BANK", holder)
    # A holding company leading with the holder's brand word stays the holder's.
    assert tc.holder_named("CONTOSO HOLDINGS LLC CONTOSO BAKERY", "CONTOSO BAKERY LLC")
    # A layout's labels before the holder's own name name no other payer.
    assert tc.holder_named("DEPOSIT ACH PAID FROM 1234 NORTHWIND HARBOR AGENCY", holder)


@pytest.mark.parametrize("region", [
    # Truist's company field runs on into the receiver block: the holder's name, cut or followed by a person's name.
    "INVOICES SAMPLE CHURC NORTHWIND HARBOR SAMPLE P",
    "PAYOUT FABRIKAM LLC NORTHWIND HARBOR CORPORATIO",
    "INS PREM FABRIKAM MUTUAL NORTHWIND HARBOR CORPORATI",
])
def test_the_holder_s_name_inside_another_payer_s_receiver_block_is_never_the_payer(region):
    assert not tc.holder_named(region, "NORTHWIND HARBOR CORP")
    assert tc.holder_named("NORTHWIND HARBOR CORP PAYMENT", "NORTHWIND HARBOR CORP")


def test_the_receiver_fields_name_the_holder_of_a_statement_that_prints_none():
    statement = _statement([
        ("FABRIKAM SUPPLY DES PAYMENT ID 1 INDN NORTHWIND FISH LLC CO ID 1234567890 CCD", 700.0),
        ("CONTOSO DINER DES PAYMENT ID 2 INDN NORTHWIND FISH LLC CO ID 1234567891 CCD", 800.0),
    ])
    records = classify_statement_transactions(statement)
    assert tr.holder_unscreened(records) is False


# --- I38: First Citizens' DBA lump sums are the holder's ----------------------------------------------------------

FIRST_CITIZENS_HOLDER = "CONTOSO LLC DBA NORTHWIND AGENCY, LLC"


def test_a_dba_holder_s_words_include_its_trade_name():
    assert "NORTHWIND" in tc.holder_words(FIRST_CITIZENS_HOLDER)


@pytest.mark.parametrize("text", [
    "NORTHWIND PY01/02/31 *****1234",
    "NORTHWIND AGENCY PY01/02/31 *****1234",
    "CONTOSO PY01/02/31 *****1234",
])
def test_the_holder_s_own_dba_lump_sum_is_held(text):
    assert _tiers([(text, 250000.0)], account_name="Business Banking", holder_name=FIRST_CITIZENS_HOLDER) == [
        HOLDER_NAME
    ]
    assert _tiers([(text, 250000.0)], account_name="Business Banking") != [HOLDER_NAME]


def test_a_dba_holder_never_holds_a_customer_sharing_no_name_word():
    text = "FABRIKAM INSURANCE PAYMENTS 1234"
    assert _tiers([(text, 900.0)], holder_name=FIRST_CITIZENS_HOLDER) != [HOLDER_NAME]


# --- I58: a short initialism and a one-word holder -----------------------------------------------------------------

def _vendor_pay(payer):
    return f"{payer} DES:VENDOR PAY ID:1234 INDN:QZX TRUCKING LLC CO ID:1234567890 CCD"


def test_another_company_sharing_the_holder_s_industry_word_is_a_customer():
    assert _twice(_vendor_pay("BKS TRUCKING INC"), account_name="QZX TRUCKING LLC") == [REMITTANCE, REMITTANCE]


def test_the_same_initialism_is_a_likely_affiliate():
    text = "QZX LOGISTICS LLC DES:PAYMENT ID:1234 INDN:QZX TRUCKING LLC CO ID:1234567890 CCD"
    assert _twice(text, account_name="QZX TRUCKING LLC") == [HOLDER_NAME, HOLDER_NAME]


def test_a_one_word_holder_must_start_the_payer_s_name():
    text = "CONTOSO LANDSCAPING SUPPLY DES:PAYMENT ID:1234 INDN:LANDSCAPING SERVICES LLC CO ID:1234567890 CCD"
    assert _twice(text, account_name="LANDSCAPING SERVICES LLC") == [REPEATS, REPEATS]
    own = "LANDSCAPING SERVICES LLC DES:PAYMENT ID:1234 INDN:FABRIKAM CO ID:1234567890 CCD"
    assert _twice(own, account_name="LANDSCAPING SERVICES LLC") == [HOLDER_NAME, HOLDER_NAME]


def test_a_product_word_left_alone_in_the_account_name_holds_no_customer():
    text = "ZELLE PAYMENT FROM FABRIKAM GENERAL SERVICES INC CONF 1234567890"
    assert _tiers([(text, 80.0)], account_name="GENERAL CHECKING") == [P2P]


@pytest.mark.parametrize(("holder", "payer", "named"), [
    # The brand-word affiliate of §5.2 stays the holder's.
    ("CONTOSO BAKERY LLC", "CONTOSO HOLDINGS LLC", True),
    ("QZX MANAGEMENT LLC", "QZX PROPERTIES LLC", True),
    ("QZX TRUCKING LLC", "QZX LOGISTICS LLC", True),
    # A different initialism is a different company; so is an industry word alone.
    ("QZX TRUCKING LLC", "VWK TRUCKING INC", False),
    ("QZX TRUCKING LLC", "TRUCKING PARTNERS INC", False),
    ("NORTHWIND TRUCKING LLC", "VWK NORTHWIND INC", False),
    ("PLUMBING SOLUTIONS LLC", "FABRIKAM PLUMBING SUPPLY", False),
    ("PLUMBING SOLUTIONS LLC", "PLUMBING SOLUTIONS LLC", True),
    # Bank and product abbreviations never lead the holder's name.
    ("BMO BUS CKG NORTHWIND FISH", "NORTHWIND FISH LLC", True),
    ("ADV BUS CKG", "FABRIKAM ADV SUPPLY", False),
    # A long first word keeps the four-letter reading.
    ("NORTHWIND TRUCKING LLC", "NORTHWIND HOLDINGS LLC", True),
    ("NORTHWIND TRUCKING LLC", "CONTOSO TRUCKING INC", False),
    # A particle is never a brand initialism.
    ("DEL NORTHWIND FARMS LLC", "DEL CONTOSO FOODS INC", False),
])
def test_the_holder_test_reads_names_not_industry_words(holder, payer, named):
    assert tc.holder_named(payer, holder) is named
