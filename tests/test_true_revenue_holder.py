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
from tests.zelle_reading import rules_reading

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
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    return [rules_reading(record, method=True)
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


def test_an_account_title_never_reaches_the_holder_s_names_or_any_reading():
    """Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW10: Statement.account_title is provenance
    only. The holder's names (holder_reading, _usable_holder_name, holder_words) never read it, and a statement's every
    record, its metrics and its payer readings are the same with or without a title (a payer printing the title's
    words included). R2-OW11: the one reader of the title is the premium-trust rule, which moves only the tier and
    reason of a credit in True (tests/test_true_revenue_premium_trust.py)."""
    rows = [
        ("ZELLE PAYMENT FROM NORTHWIND FISH LLC CONF 1234567890", 900.0),
        ("ACH CREDIT PREMIUM TRUST ACCOUNT SERVICES PAYMENT 1234", 3100.0),
        ("ORIG CO NAME:FABRIKAM INC ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENT SEC:CCD", 2200.0),
        ("ORIG CO NAME:FABRIKAM INC ORIG ID:1234567890 DESC DATE:540309 CO ENTRY DESCR:PAYMENT SEC:CCD", 2350.0),
        ("DEPOSIT", 500.0),
        ("CHECK 1001", -400.0),
    ]
    plain = _statement(rows, account_name="Business Checking", holder_name="NORTHWIND FISH LLC")
    # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: since the premium-trust rule reads the title, the
    # identity is pinned on a title it does not read; a premium trust title moves only the tiers of the credits in True.
    titled = plain.model_copy(update={"account_title": "OPERATING ACCOUNT"})
    assert titled.account_title == "OPERATING ACCOUNT"
    assert classify_statement_transactions(titled) == classify_statement_transactions(plain)
    assert compute_metrics(titled) == compute_metrics(plain)
    trust = plain.model_copy(update={"account_title": "PREMIUM TRUST ACCOUNT"})
    for statement in (titled, trust):
        assert tc.holder_reading(statement.account_name, statement.holder_name) == "NORTHWIND FISH LLC"
        assert "PREMIUM" not in tc.holder_words(tc.holder_reading(statement.account_name, statement.holder_name))
    for old, new in zip(classify_statement_transactions(plain), classify_statement_transactions(trust)):
        if old.revenue_tier in {"verified", "counted_flagged"} and old.amount > 0:
            assert (new.revenue_tier, new.revenue_tier_reason) == ("excluded_pending_review", "premium_trust_account")
            # The holder's reading and every lender reading are the same.
            assert (new.holder_name, new.classification, new.match_method) == (
                old.holder_name, old.classification, old.match_method)
        else:
            assert new == old


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
    "BMO BUS CKG", "GENERAL CHECKING", "Treasury Enterprise Plan", "Virtual Wallet With Performance Spend",
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


# --- Audit B9 review round 1 ----------------------------------------------------------------------------------------

def _revenue(text):
    return tc.revenue_text(tc.normalize_transaction_description(text))


def _own_rows(holder):
    zelle = f"ZELLE PAYMENT FROM {holder} CONF 1234567890"
    push = f"{holder} DES:TRANSFER ID:1 INDN:{holder} CO ID:1234567890 CCD"
    wire = f"WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:{holder} ID:1234567890"
    return zelle, push, wire


# A processor's settlement word is read outside the holder's own name: a holder whose name prints MERCHANT, MERCH or
# BANKCARD keeps its own Zelle, push and wire held.

@pytest.mark.parametrize("holder", ["NORTHWIND MERCHANT GROUP LLC", "CONTOSO MERCH LLC", "SAMPLE BANKCARD SUPPLY INC"])
def test_a_holder_whose_name_prints_a_settlement_word_keeps_its_own_money_held(holder):
    zelle, push, wire = _own_rows(holder)
    assert _tiers([(zelle, 900.0)], holder_name=holder) == [HOLDER_NAME]
    assert _twice(push, 900.0, holder_name=holder) == [HOLDER_NAME, HOLDER_NAME]
    assert _twice(wire, 9000.0, holder_name=holder) == [HOLDER_NAME, HOLDER_NAME]
    # On the row alone: the push's originator is its own receiver field, whatever words the name prints.
    assert _twice(push, 900.0) == [HOLDER_NAME, HOLDER_NAME]


def test_a_person_holder_surnamed_merchant_keeps_its_own_zelle_held():
    text = "ZELLE PAYMENT FROM SAMPLE MERCHANT CONF 1234567890"
    assert _tiers([(text, 900.0)], holder_name="SAMPLE MERCHANT") == [HOLDER_NAME]


@pytest.mark.parametrize("holder_name", [None, "CONTOSO MERCHANT SUPPLY LLC"])
def test_a_processor_s_entry_under_a_merchant_named_holder_is_still_never_held(holder_name):
    text = CHASE_ACH.format(orig="CONTOSO MERCHANT SUPPLY", entry="NETSWEEP ", receiver="CONTOSO MERCHANT SUPPLY LLC")
    tiers = _twice(text, 300.0, holder_name=holder_name)
    assert HOLDER_NAME not in tiers
    assert all(tier[0] in ("verified", "counted_flagged") for tier in tiers)


def test_a_processor_s_word_printed_after_the_holder_s_name_on_an_unlabelled_row_is_never_held():
    # A layout with no entry field prints the processor's word after the merchant's own name.
    text = "CONTOSO TRADING LLC SAMPLE FINTECHEFT 123456"
    tiers = _tiers([(text, 300.0)], holder_name="CONTOSO TRADING LLC")
    assert tiers != [HOLDER_NAME]
    assert tiers[0][0] == "counted_flagged"


def test_the_settlement_words_are_read_outside_the_holder_s_own_name():
    holder = "NORTHWIND MERCHANT GROUP LLC"
    zelle, push, wire = _own_rows(holder)
    for text in (zelle, push, wire):
        assert not tr.merchant_settlement(_revenue(text), (holder,))
    netsweep = CHASE_ACH.format(orig="NORTHWIND MERCHANT GRO", entry="NETSWEEP ", receiver=holder)
    assert tr.merchant_settlement(_revenue(netsweep), (holder,))
    assert tr.merchant_settlement(_revenue(netsweep))
    # A person-to-person or wire row never prints a processor's settlement.
    assert not tr.merchant_settlement(_revenue("ZELLE PAYMENT FROM FABRIKAM MERCHANT SERVICES CONF 1234567890"))
    assert not tr.merchant_settlement(_revenue(_own_rows("FABRIKAM MERCHANT SERVICES")[2]))


# Audit round 3, R3-B10 (R3-90 part A): a bare SETTLEMENT (SETTLMT, STLMT) under the merchant's own name is a
# processor's, a carrier's or an operating settlement, never the holder's own push: the holder holds skip it and it
# takes its own reading, counted, never verified (a verification-only word). Never on a transfer or a person-to-person
# row, and read outside the holder's own names.

R3_90_HAULING = "ACH SETTLEMENT CONTOSO HAULING CONTRACTOR MGMT ACHDD"
R3_90_WELLS = "CONTOSO DESI SETTLEMENT 54011{n} 123456789012345 NORTHWIND PRESS SAMPLEVI"
R3_90_WELLS_HOLDER = "CONTOSO DESIGN INC DBA NORTHWIND PRESS"
R3_90_BALANCE = "SETTLEMENT NORTHWIND FLOWERS 123456789012345CCD"
R3_90_ALONE = "CONTOSO HAULING LLC DES:SETTLEMENT ID:{n} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD"


def _in_true_never_verified(tiers):
    return all(tier[0] == "counted_flagged" for tier in tiers)


def test_r3_90_a_settlement_under_the_holder_s_own_name_is_counted_never_verified():
    assert _in_true_never_verified(_tiers([(R3_90_HAULING, 1500.0)], holder_name="CONTOSO HAULING LLC"))
    wells = [(R3_90_WELLS.format(n=5), 1500.0), (R3_90_WELLS.format(n=6), 1750.0)]
    tiers = _tiers(wells, holder_name=R3_90_WELLS_HOLDER, bank="Wells Fargo")
    assert len(tiers) == 2 and _in_true_never_verified(tiers)
    assert _in_true_never_verified(_tiers([(R3_90_BALANCE, 1500.0)], holder_name="NORTHWIND FLOWERS LLC"))


def test_r3_90_a_the_holder_s_own_account_transfer_never_holds_its_settlement():
    # Audit round 4, R4-27 (re-pinned; standard A1, B1, §4.6 item 5): the exemption lifts the holder hold, and the
    # holder's transfer to its own account (a circular debit printing its whole name before an account designation)
    # proves nothing about a settlement under the merchant's own name, at any amount: counted, never verified. It was
    # held payer_also_debited. A transfer to an affiliate still holds it (test_r4_27_*).
    own_transfer = "ONLINE TRANSFER TO CONTOSO DESIGN INC BUSINESS CHECKING XXXXXX0000 REF IB0000000 ON 05 02 54"
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (own_transfer, -900.0)]
    assert _tiers(rows, holder_name=R3_90_WELLS_HOLDER, bank="Wells Fargo") == [R3_90_REFUSED]


def test_r3_90_a_settlement_pushed_under_its_own_name_is_no_own_push_on_the_row_alone():
    rows = [(R3_90_ALONE.format(n=1), 1500.0), (R3_90_ALONE.format(n=2), 1750.0)]
    tiers = _tiers(rows)
    assert len(tiers) == 2 and _in_true_never_verified(tiers)
    revenue = _revenue(R3_90_ALONE.format(n=1))
    assert not tr.self_originated(revenue, tc.payer_region(revenue))


@pytest.mark.parametrize("text", [
    "ONLINE TRANSFER FROM CONTOSO HAULING LLC SETTLEMENT",
    "ZELLE PAYMENT FROM CONTOSO HAULING LLC SETTLEMENT CONF 1234567890",
])
def test_r3_90_a_transfer_or_a_person_to_person_row_printing_settlement_stays_the_holder_s(text):
    assert _tiers([(text, 1500.0)], holder_name="CONTOSO HAULING LLC") == [HOLDER_NAME]
    assert not tr.merchant_settlement(_revenue(text), ("CONTOSO HAULING LLC",))
    assert not tr.merchant_settlement(_revenue(text))


def test_r3_90_a_holder_whose_name_prints_settlement_keeps_its_own_money_held():
    holder = "NORTHWIND SETTLEMENT SERVICES LLC"
    zelle, push, wire = _own_rows(holder)
    assert _tiers([(zelle, 900.0)], holder_name=holder) == [HOLDER_NAME]
    assert _twice(push, 900.0, holder_name=holder) == [HOLDER_NAME, HOLDER_NAME]
    assert _twice(wire, 9000.0, holder_name=holder) == [HOLDER_NAME, HOLDER_NAME]
    # On the row alone: the word is read outside the row's own receiver and originator names.
    assert _twice(push, 900.0) == [HOLDER_NAME, HOLDER_NAME]
    for text in (zelle, push, wire):
        assert not tr.merchant_settlement(_revenue(text), (holder,))


def test_r3_90_a_claims_administrator_s_settlement_naming_the_holder_stays_held():
    text = "SAMPLE SETTLEMENT ADMINISTRATION DES:CLAIM ID:0001 INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD"
    assert _tiers([(text, 1500.0)], holder_name="CONTOSO HAULING LLC") == [
        ("excluded_pending_review", "non_sale_purpose")
    ]
    # The holder's own name printed before a claims administrator's word: the exemption lifts the holder hold only,
    # and the later holds still read the row.
    led = "CONTOSO HAULING SETTLEMENT ADMIN 540115 1234567"
    [tier] = _tiers([(led, 1500.0)], holder_name="CONTOSO HAULING LLC", bank="Wells Fargo")
    assert tier[0] == "excluded_pending_review"


@pytest.mark.parametrize(("text", "names"), [
    (R3_90_HAULING, ("CONTOSO HAULING LLC",)),
    (R3_90_WELLS.format(n=5), (R3_90_WELLS_HOLDER,)),
    (R3_90_BALANCE, ("NORTHWIND FLOWERS LLC",)),
    ("CONTOSO HAULING DES:SETTLMT ID:1 INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD", ("CONTOSO HAULING LLC",)),
    ("CONTOSO HAULING DES:STLMT ID:1 INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD", ("CONTOSO HAULING LLC",)),
])
def test_r3_90_merchant_settlement_reads_a_bare_settlement_word(text, names):
    assert tr.merchant_settlement(_revenue(text), names)
    assert tr.merchant_settlement(_revenue(text))


# Audit round 3, R3-B10 review round 1 (finding 1): a row the exemption releases is counted and never verified in each
# of the three spellings it reads, with or without a holder name read. Review round 2 (findings 1 and 2): by the pass's
# own release flag (CreditFacts.settlement_released), not by §8.6's verification-only words, which read SETTLEMENT alone
# again, so a third party printing a short spelling reads as before the batch.

R3_90_SPELLINGS = ("SETTLEMENT", "SETTLMT", "STLMT")
R3_90_REFUSED = ("counted_flagged", "named_payer_purpose_refused")
R3_90_BOFA = "{orig} DES:{word} ID:{n} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD"
R3_90_CHASE = (
    "ORIG CO NAME:{orig} ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:{word}SEC:CCD TRACE#:11100002000000{n} "
    "EED:540302 IND ID:1 IND NAME:CONTOSO HAULING LLC TRN: 123456789{n}TC"
)


def _r3_90_pair(layout, **fields):
    return [(layout.format(n=n, **fields), amount) for n, amount in ((1, 1500.0), (2, 1750.0))]


@pytest.mark.parametrize("holder_name", [None, "CONTOSO HAULING LLC"])
@pytest.mark.parametrize(("layout", "bank"), [(R3_90_BOFA, "Bank of America"), (R3_90_CHASE, "Chase")])
@pytest.mark.parametrize("word", R3_90_SPELLINGS)
def test_r3_90_a_the_holder_s_own_settlement_push_is_counted_never_verified_in_each_spelling(
    word, layout, bank, holder_name
):
    rows = _r3_90_pair(layout, orig="CONTOSO HAULING LLC", word=word)
    assert _tiers(rows, holder_name=holder_name, bank=bank) == [R3_90_REFUSED, R3_90_REFUSED]


R3_90_MERCHANT_LAYOUTS = (
    ("ACH {word} CONTOSO HAULING CONTRACTOR MGMT ACHDD {n}", "Woodforest"),
    ("CONTOSO HAULI {word} 54011{n} 123456789012345 CONTOSO HAULING", "Wells Fargo"),
    ("{word} CONTOSO HAULING 12345678901234{n}CCD", None),
)


@pytest.mark.parametrize(("layout", "bank"), R3_90_MERCHANT_LAYOUTS)
@pytest.mark.parametrize("word", R3_90_SPELLINGS)
def test_r3_90_a_a_settlement_under_the_merchant_s_name_reads_alike_in_each_spelling(word, layout, bank):
    rows = _r3_90_pair(layout, word=word)
    assert _tiers(rows, holder_name="CONTOSO HAULING LLC", bank=bank) == [R3_90_REFUSED, R3_90_REFUSED]


# Review round 2 (finding 2): with no holder name read and no receiver field, no hold reads these rows, so the exemption
# releases nothing and each reads as before the batch: SETTLEMENT refused as proof (§8.6), a short spelling as a payer.
@pytest.mark.parametrize(("layout", "bank", "short"), [
    (*R3_90_MERCHANT_LAYOUTS[0], REPEATS),
    (*R3_90_MERCHANT_LAYOUTS[1], ("counted_flagged", "named_payer_unlabelled")),
    (*R3_90_MERCHANT_LAYOUTS[2], ("counted_flagged", "named_payer_unlabelled")),
])
@pytest.mark.parametrize("word", R3_90_SPELLINGS)
def test_r3_b10_r2_a_merchant_named_settlement_with_no_holder_read_reads_as_before_the_batch(word, layout, bank, short):
    reading = R3_90_REFUSED if word == "SETTLEMENT" else short
    assert _tiers(_r3_90_pair(layout, word=word), bank=bank) == [reading, reading]


@pytest.mark.parametrize(("layout", "bank"), [(R3_90_BOFA, "Bank of America"), (R3_90_CHASE, "Chase")])
@pytest.mark.parametrize(("word", "reading"), [("SETTLEMENT", R3_90_REFUSED), ("SETTLMT", REPEATS), ("STLMT", REPEATS)])
def test_r3_b10_r2_a_third_party_s_repeated_settlement_reads_as_before_the_batch(word, reading, layout, bank):
    # Review round 2 (finding 2): §8.6's verification-only words read SETTLEMENT alone again; a third party's short
    # spelling, which no hold reads, verifies by repetition as it did before the batch.
    rows = _r3_90_pair(layout, orig="FABRIKAM FREIGHT INC", word=word)
    assert _tiers(rows, holder_name="CONTOSO HAULING LLC", bank=bank) == [reading, reading]


def test_r3_b10_r2_a_card_form_s_short_spelling_keeps_its_reading():
    # The bankcard form reads STLMT and keeps its own verified reading; SETTLMT, which it does not read, verifies by
    # repetition as before the batch (review round 1's verification-only short spellings counted it, flagged).
    rows = _r3_90_pair(R3_90_BOFA, orig="SAMPLE BANKCARD", word="STLMT")
    assert _tiers(rows, holder_name="CONTOSO HAULING LLC", bank="Bank of America") == [NET_SETTLE, NET_SETTLE]
    rows = _r3_90_pair(R3_90_BOFA, orig="SAMPLE BANKCARD", word="SETTLMT")
    assert _tiers(rows, holder_name="CONTOSO HAULING LLC", bank="Bank of America") == [REPEATS, REPEATS]
    assert tr._VERIFICATION_ONLY.search("SAMPLE BANKCARD SETTLMT 0001") is None
    assert tr._VERIFICATION_ONLY.search("SAMPLE BANKCARD STLMT 0001") is None


# Audit round 3, R3-B10 review round 2 (finding 1): the exemption reads the settlement word anywhere before the receiver
# outside the holder's names, digits glued on or not, where §8.6's verification-only words read only the entry fields
# and the payer region, before a non-word character. A row the bare settlement word alone releases, from the pass-7
# holder hold or the row-alone own-push guard, is never verified and never a repeat, whatever slot or boundary the word
# sits in, with or without a holder name read, in each Zelle reading; one an earlier rule verified leaves verification.

R3_B10_R2_HOLDER = "CONTOSO HAULING LLC"
R3_B10_R2_CHASE = (
    "ORIG CO NAME:{orig} ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:{entry} SEC:CCD TRACE#:11100002000000{n} "
    "EED:540302 IND ID:1 IND NAME:CONTOSO HAULING LLC TRN: 123456789{n}TC"
)
#: The holder's own push, the settlement word in each slot the exemption reads: (name, layout, bank). Each layout pairs
#: its originator with a receiver field, so the row-alone own-push guard reads it with no holder name too.
R3_B10_R2_OWN_PUSH = (
    ("bofa_id_spaced",
     "CONTOSO HAULING LLC DES:PAYMENT ID:{word} 000{n} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD",
     "Bank of America"),
    ("bofa_id_glued",
     "CONTOSO HAULING LLC DES:PAYMENT ID:{word}000{n} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD",
     "Bank of America"),
    ("bofa_des_glued",
     "CONTOSO HAULING LLC DES:{word}0{n} ID:0001 INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD", "Bank of America"),
    ("bofa_after_id",
     "CONTOSO HAULING LLC DES:PAYMENT ID:000{n} {word} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD",
     "Bank of America"),
    ("bofa_originator_digit",
     "CONTOSO HAULING 0412 {word} DES:PAYMENT ID:000{n} INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD",
     "Bank of America"),
    ("chase_entry_glued", R3_B10_R2_CHASE.replace("{orig}", "CONTOSO HAULING LLC").replace("{entry}", "{word}0{n}"),
     "Chase"),
)
#: Layouts that print no receiver field: only the pass-7 holder hold reads them, so only with a holder name read.
R3_B10_R2_HOLDER_ONLY = (
    ("fifth_third_glued", "ACH CREDIT CONTOSO HAULING LLC {word}00{n}", "Fifth Third"),
    ("capital_one_glued", "ACH DEPOSIT CONTOSO HAULING {word}0{n} 1234567{n} CONTOSO HAULING LLC", "Capital One"),
    ("huntington_glued", "ACH DEPOSIT CONTOSO HAULING LLC {word}041{n} CCD", "Huntington"),
)


def _tiers_in(rows, zelle, **kwargs):
    statement = _statement(rows, **kwargs)
    return [rules_reading(record, method=True)
            for record in classify_statement_transactions(statement, zelle_true_revenue=zelle) if record.amount > 0]


def _records_in(rows, zelle, **kwargs):
    statement = _statement(rows, **kwargs)
    return [record for record in classify_statement_transactions(statement, zelle_true_revenue=zelle)
            if record.amount > 0]


@pytest.mark.parametrize("zelle", [False, True])
@pytest.mark.parametrize("holder_name", [None, R3_B10_R2_HOLDER])
@pytest.mark.parametrize(("name", "layout", "bank"), R3_B10_R2_OWN_PUSH, ids=[shape[0] for shape in R3_B10_R2_OWN_PUSH])
@pytest.mark.parametrize("word", R3_90_SPELLINGS)
def test_r3_b10_r2_the_holder_s_own_settlement_push_never_verifies_in_any_slot(word, name, layout, bank, holder_name,
                                                                                zelle):
    rows = _r3_90_pair(layout, word=word)
    assert _tiers_in(rows, zelle, holder_name=holder_name, bank=bank) == [R3_90_REFUSED, R3_90_REFUSED]


@pytest.mark.parametrize("zelle", [False, True])
@pytest.mark.parametrize(("name", "layout", "bank"), R3_B10_R2_HOLDER_ONLY,
                         ids=[shape[0] for shape in R3_B10_R2_HOLDER_ONLY])
@pytest.mark.parametrize("word", R3_90_SPELLINGS)
def test_r3_b10_r2_a_glued_settlement_the_holder_hold_releases_never_verifies(word, name, layout, bank, zelle):
    rows = _r3_90_pair(layout, word=word)
    assert _tiers_in(rows, zelle, holder_name=R3_B10_R2_HOLDER, bank=bank) == [R3_90_REFUSED, R3_90_REFUSED]


@pytest.mark.parametrize("zelle", [False, True])
@pytest.mark.parametrize("holder_name", [None, R3_B10_R2_HOLDER])
@pytest.mark.parametrize("entry", [
    "CARD SALES SETTLEMENT", "MARKETPLACE SETTLEMENT", "SETTLEMENT EDIRPAY", "SETTLEMENT MTOT DEP",
    "HCCLAIMPMT SETTLEMENT", "STLMT0001 MTOT DEP",
])
def test_r3_b10_r2_a_settlement_an_earlier_rule_verified_under_the_merchant_s_own_name_leaves_verification(
    entry, holder_name, zelle
):
    # An operating-income descriptor verified the holder's own push before pass 7; the bare settlement word alone lifts
    # the own-push guard, so the pass overrules the verification: counted and flagged, refused as proof.
    rows = [(R3_90_BOFA.format(orig="CONTOSO HAULING LLC", word=entry, n=1), 1500.0)]
    [record] = _records_in(rows, zelle, holder_name=holder_name, bank="Bank of America")
    assert (record.revenue_tier, record.revenue_tier_reason) == R3_90_REFUSED
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_match_method == "holder_named_settlement"
    assert record.revenue_matched_rule == "holder_named_settlement_never_verified"
    assert "operating_income_descriptor" in record.revenue_reason


@pytest.mark.parametrize("zelle", [False, True])
@pytest.mark.parametrize("holder_name", [None, "CONTOSO HAULING"])
@pytest.mark.parametrize("own", [
    "CONTOSO HAULING DES:SETTLEMENT ID:0001 INDN:CONTOSO HAULING CO ID:1234567890 CCD",
    "CONTOSO HAULING DES:PAYMENT ID:STLMT0001 INDN:CONTOSO HAULING CO ID:1234567890 CCD",
])
def test_r3_b10_r2_a_released_settlement_is_never_a_repeat(own, holder_name, zelle):
    # The holder's own push, released by its settlement word, never counts toward a repeat (as the own push it was held
    # as never did): the same name's lone payment stays one-off, or held as the holder's name where one is read.
    other = "CONTOSO HAULING DES:PAYMENT ID:0009 CO ID:1234567890 CCD"
    expected = ONE_OFF if holder_name is None else HOLDER_NAME
    tiers = _tiers_in([(own, 1500.0), (other, 1750.0)], zelle, holder_name=holder_name, bank="Bank of America")
    assert tiers == [R3_90_REFUSED, expected]


@pytest.mark.parametrize("word", R3_90_SPELLINGS)
@pytest.mark.parametrize("form", ["{word}", "{word}01", "{word}-01", "{word}/01", "01{word}"])
def test_r3_b10_r2_every_spelling_and_boundary_the_exemption_reads_is_never_verified(word, form):
    # In step: wherever and however the exemption reads the word (merchant_settlement), the row it releases is refused
    # as proof; B9's own settlement words alone do not read it.
    printed = form.format(word=word)
    text = f"CONTOSO HAULING LLC DES:{printed} ID:0001 INDN:CONTOSO HAULING LLC CO ID:1234567890 CCD"
    assert tr._HOLDER_NAMED_SETTLEMENT_ENTRY.search(printed) is not None
    assert tr.merchant_settlement(_revenue(text), (R3_B10_R2_HOLDER,))
    assert not tr.merchant_settlement(_revenue(text), (R3_B10_R2_HOLDER,), bare_settlement=False)
    rows = [(text, 1500.0), (text.replace("ID:0001", "ID:0002"), 1750.0)]
    assert _tiers(rows, bank="Bank of America") == [R3_90_REFUSED, R3_90_REFUSED]


# Truist prints '<entry> <company field> <receiver> CUSTOMER ID <id>': the holder's name in the receiver slot after a
# one-word originator is the receiver, never the payer.

TRUIST_HOLDER = "CONTOSO GAMES INC"


@pytest.mark.parametrize(("text", "holder"), [
    ("TRANSFER FABRIKAM INC CONTOSO GAMES CUSTOMER ID SAMPLEPAY1", TRUIST_HOLDER),
    ("TRANSFER SAMPLEBOOK CONTOSO GAMES IN CUSTOMER ID ST A1B2C3D4E5F6", TRUIST_HOLDER),
    ("TRANSFER FABRIKAM INC CONTOSO SAMPLE GAMES CUSTOMER ID SAMPLEPAY1", "CONTOSO SAMPLE GAMES INC"),
])
def test_truist_s_receiver_slot_after_a_one_word_originator_is_never_the_payer(text, holder):
    assert _tiers([(text, 300.0)], holder_name=holder, bank="Truist") == [P2P]
    assert _tiers([(text, 300.0)], account_name="Checking", bank="Truist") == [P2P]


def test_a_platform_printing_the_store_s_descriptor_before_truist_s_receiver_slot_is_never_the_holder():
    text = "FABRIKAMLIVE CONTOSO GAMES SHOP CONTOSO GAMES INC CUSTOMER ID ST A1B2C3D4E5F6"
    tiers = _tiers([(text, 300.0)], holder_name=TRUIST_HOLDER, bank="Truist")
    assert tiers != [HOLDER_NAME]
    assert tiers[0][0] == "counted_flagged"


@pytest.mark.parametrize("text", [
    "ZELLE BUSINESS PAYMENT FROM CONTOSO GAMES INC PAYMENT ID 1234",
    # The holder's own account elsewhere: the company field and the receiver slot both print the holder.
    "TRANSFER CONTOSO GAMES INC CONTOSO GAMES CUSTOMER ID 123456",
    "TRANSFER CONTOSO CONTOSO GAMES CUSTOMER ID 123456",
    # Review round 2: the company field printing the holder's own name glued, or glued with its legal form.
    "TRANSFER CONTOSOGAMES CONTOSO GAMES CUSTOMER ID 123456",
    "TRANSFER CONTOSOGAMESINC CONTOSO GAMES CUSTOMER ID 123456",
])
def test_truist_s_own_money_stays_held(text):
    assert _tiers([(text, 300.0)], holder_name=TRUIST_HOLDER, bank="Truist") == [HOLDER_NAME]


@pytest.mark.parametrize("bank", ["Regions Bank", None])
def test_the_one_word_receiver_slot_is_truist_s_alone(bank):
    # Review round 2: another layout printing CUSTOMER ID keeps the two-word reading of a receiver block.
    text = "TRANSFER FABRIKAM INC CONTOSO GAMES CUSTOMER ID SAMPLEPAY1"
    assert _tiers([(text, 300.0)], holder_name=TRUIST_HOLDER, bank=bank) == [HOLDER_NAME]
    assert tc.holder_receiver_block(_revenue(text), bank) == 2


@pytest.mark.parametrize(("text", "block"), [
    ("TRANSFER FABRIKAM INC CONTOSO GAMES CUSTOMER ID SAMPLEPAY1", 1),
    ("ZELLE PAYMENT FROM SAMPLE PERSON NORTHWIND MARINE LLC CONF 1234567890", None),
    ("ONLINE TRANSFER FROM SAMPLE PERSON NORTHWIND MARINE LLC REF 1234567890", None),
    ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:SAMPLE PERSON NORTHWIND MARINE LLC ID:1",
     None),
    ("FABRIKAM INSURANCE MISC NORTHWIND HARBOR AGENC", 2),
])
def test_the_layout_says_where_a_receiver_block_can_print(text, block):
    assert tc.holder_receiver_block(_revenue(text), "Truist") == block


# A labelled sender (a sender after FROM, a wire's originator field) prints the sender alone: the owner's name printed
# before the holder's is the holder's own money, never another payer's receiver block.

@pytest.mark.parametrize("text", [
    "ZELLE PAYMENT FROM SAMPLE PERSON NORTHWIND MARINE LLC CONF 1234567890",
    "ONLINE TRANSFER FROM SAMPLE PERSON NORTHWIND MARINE LLC REF 1234567890",
    "WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:SAMPLE PERSON NORTHWIND MARINE LLC ID:1",
])
def test_a_labelled_sender_printing_the_owner_and_the_holder_is_the_holder_s_own_money(text):
    assert _tiers([(text, 900.0)], holder_name="NORTHWIND MARINE LLC") == [HOLDER_NAME]


# The wire hold compares the whole sender with the whole beneficiary: two companies sharing two first words are two.

LOOKALIKE_WIRE = (
    "FEDWIRE CREDIT VIA: SAMPLE BANK/012345678 B/O: {bo} SAMPLEVILLE TX 75001 US REF: CHASE "
    "NYC/CTR/BNF={bnf} {city} TX 75001 US/AC-000000001234 RFB=NOTPROVIDED IMAD: 0302MMQFMP2N000123 TRN: 1234567890FF"
)


@pytest.mark.parametrize(("bo", "bnf"), [
    ("NEW SAMPLE CITY HOSPITAL", "NEW SAMPLE MEDICAL SUPPLY LLC"),
    ("THE SAMPLE COMPANY INC", "THE SAMPLE BAKERY LLC"),
    ("SOUTH SAMPLE CONSTRUCTION INC", "SOUTH SAMPLE ELECTRIC LLC"),
])
def test_two_companies_sharing_two_first_words_are_never_one_wire_sender(bo, bnf):
    text = LOOKALIKE_WIRE.format(bo=bo, bnf=bnf, city="SAMPLEVILLE")
    tiers = _twice(text, 6000.0)
    assert HOLDER_NAME not in tiers
    # Q5's own-account veto still refuses them as proof.
    assert all(tier[0] == "counted_flagged" for tier in tiers)
    assert not tr.self_originated(_revenue(text), tc.payer_region(_revenue(text)))


def test_the_holder_s_own_wire_is_held_whatever_town_its_beneficiary_prints():
    text = LOOKALIKE_WIRE.format(bo="NORTHWIND MARINE LLC", bnf="NORTHWIND MARINE LLC", city="OTHERTOWN")
    assert _twice(text, 6000.0) == [HOLDER_NAME, HOLDER_NAME]
    no_form = LOOKALIKE_WIRE.format(bo="NORTHWIND MARINE", bnf="NORTHWIND MARINE LLC", city="OTHERTOWN")
    assert _twice(no_form, 6000.0) == [HOLDER_NAME, HOLDER_NAME]


@pytest.mark.parametrize("name", ["NORTHWIND MARINE", "SAMPLE PERSON"])
def test_the_holder_s_own_wire_with_no_legal_form_is_held_whatever_town_its_beneficiary_prints(name):
    # Review round 2: a name with no legal form is read without the town and state its address prints after it.
    text = LOOKALIKE_WIRE.format(bo=name, bnf=name, city="OTHERTOWN")
    assert _twice(text, 6000.0) == [HOLDER_NAME, HOLDER_NAME]
    assert tr.self_originated(_revenue(text), tc.payer_region(_revenue(text)))


def test_two_names_with_no_legal_form_sharing_two_first_words_are_never_one_wire_sender():
    text = LOOKALIKE_WIRE.format(bo="NORTHWIND MARINE SUPPLY", bnf="NORTHWIND MARINE REPAIR", city="OTHERTOWN")
    tiers = _twice(text, 6000.0)
    assert HOLDER_NAME not in tiers
    assert all(tier[0] == "counted_flagged" for tier in tiers)


@pytest.mark.parametrize(("value", "party"), [
    ("NORTHWIND MARINE SAMPLEVILLE TX", "NORTHWIND MARINE"),
    ("NORTHWIND MARINE SAMPLEVILLE TX US", "NORTHWIND MARINE"),
    ("NORTHWIND MARINE LLC SAMPLEVILLE TX", "NORTHWIND MARINE LLC"),
    ("SAMPLE PERSON 100 SAMPLE ST SAMPLEVILLE TX", "SAMPLE PERSON"),
    # Too short to print a town after the name: read as printed.
    ("SAMPLE PERSON TX", "SAMPLE PERSON TX"),
    ("NORTHWIND MARINE SUPPLY", "NORTHWIND MARINE SUPPLY"),
    # A two-word town leaves its first word, which one name read with a one-word town still starts.
    ("NORTHWIND MARINE SAN SAMPLE TX", "NORTHWIND MARINE SAN"),
])
def test_a_wire_party_is_read_without_its_address(value, party):
    assert tr._wire_party(value) == party


def test_a_two_word_town_on_one_side_still_reads_one_wire_party():
    two_word_town = tr._wire_party("NORTHWIND MARINE SAN SAMPLE TX")
    assert tr._same_name(two_word_town, tr._wire_party("NORTHWIND MARINE OTHERTOWN TX"))


# A person the account-name field prints beside the parser's holder name is a holder's name too.

def test_a_person_in_the_account_name_field_is_read_beside_the_parser_s_holder_name():
    rows = [("ZELLE PAYMENT FROM SAMPLE PERSON CONF 1234567890", 900.0)]
    assert _tiers(rows, account_name="SAMPLE PERSON", holder_name="NORTHWIND MARINE LLC") == [HOLDER_NAME]
    # A product in the account-name field names nobody.
    assert _tiers(rows, account_name="Business Complete Checking", holder_name="NORTHWIND MARINE LLC") == [P2P]


# Review round 2: a product the readers publish in the account-name field (PNC's Treasury Enterprise Plan) never names
# the holder, beside the parser's holder name or alone.

PNC_HOLDER = "CONTOSO TRADING LLC"
PNC_PRODUCT = "Treasury Enterprise Plan"


@pytest.mark.parametrize(("text", "tier"), [
    ("ACH CREDIT US TREASURY 310 MISC PAY 123456789 CCD", REPEATS),
    ("CORPORATE ACH MISC PAY 123456789 US TREASURY 310 123456789", REPEATS),
    ("ACH CREDIT TREASURY SAMPLE GROUP INC 123456789 CCD", REPEATS),
    ("ZELLE PAYMENT FROM ENTERPRISE PLAN SAMPLE LLC CONF 1234567890", P2P),
])
@pytest.mark.parametrize("holder_name", [PNC_HOLDER, None])
def test_a_product_in_the_account_name_field_never_holds_a_payer_sharing_its_words(text, tier, holder_name):
    assert _twice(text, 900.0, account_name=PNC_PRODUCT, holder_name=holder_name, bank="PNC Bank") == [tier, tier]
    assert _twice(text, 900.0, account_name="Business Checking", holder_name=holder_name, bank="PNC Bank") == [
        tier, tier
    ]


def test_the_holder_hold_never_reads_a_product_as_a_second_holder_name():
    record = classify_statement_transactions(_statement(
        [("ACH CREDIT FABRIKAM SUPPLY INC 123456789 CCD", 900.0)], account_name=PNC_PRODUCT, holder_name=PNC_HOLDER,
        bank="PNC Bank",
    ))[0]
    assert tr._holder_names(record) == (PNC_HOLDER,)
    assert tc.holder_words(PNC_PRODUCT) == ()
    assert not tc.holder_named("US TREASURY", PNC_PRODUCT)
    # The holder's own money is still held beside the product.
    own = "ZELLE PAYMENT FROM CONTOSO TRADING LLC CONF 1234567890"
    assert _tiers([(own, 900.0)], account_name=PNC_PRODUCT, holder_name=PNC_HOLDER, bank="PNC Bank") == [HOLDER_NAME]


def test_a_company_whose_name_prints_product_words_still_names_the_holder():
    for holder in ("TREASURY SAMPLE PLAN LLC", "TREASURY ENTERPRISE PLAN LLC"):
        assert tr._usable_holder_name(holder)
        assert tc.holder_words(holder) != ()
    text = "ZELLE PAYMENT FROM TREASURY SAMPLE PLAN LLC CONF 1234567890"
    assert _tiers([(text, 900.0)], holder_name="TREASURY SAMPLE PLAN LLC") == [HOLDER_NAME]
    assert _tiers([(text, 900.0)], account_name="TREASURY SAMPLE PLAN LLC") == [HOLDER_NAME]


def test_no_product_a_holder_reader_publishes_names_a_holder():
    from analysis import pnc

    published = (*pnc._PRODUCTS, "Checking", "TD Business Simple Checking", "Business Chequing Account",
                 "Business Banking II", "Professional Business Checking", "Analysis Business Checking",
                 "Business Checking")
    for product in published:
        assert not tr._usable_holder_name(product), product
    for product in pnc._PRODUCTS:
        assert tc.holder_words(product) == (), product


# A one-word holder left by a dropped lead word (GENERAL, a two-letter initialism) is read with that word.

@pytest.mark.parametrize(("holder", "payer", "named"), [
    ("GENERAL PLUMBING LLC", "PLUMBING SUPPLY HOUSE INC", False),
    ("GENERAL PLUMBING LLC", "GENERAL PLUMBING", True),
    ("GENERAL CONTRACTORS LLC", "CONTRACTORS DEPOT INC", False),
    ("JB TRUCKING LLC", "TRUCKING PARTNERS INC", False),
    ("JB TRUCKING LLC", "JB TRUCKING", True),
    # A one-word holder printed alone keeps the one-word reading.
    ("LANDSCAPING SERVICES LLC", "LANDSCAPING SERVICES", True),
])
def test_a_one_word_holder_left_by_a_dropped_lead_word_must_print_with_it(holder, payer, named):
    assert tc.holder_named(payer, holder) is named


def test_a_customer_leading_with_the_holder_s_industry_word_is_counted():
    text = "ZELLE PAYMENT FROM PLUMBING SUPPLY HOUSE INC CONF 1234567890"
    assert _tiers([(text, 750.0)], holder_name="GENERAL PLUMBING LLC") == [P2P]


# --- Audit round 2, R2-B02 (R18): a processor's payout is known by its payout id, never by its entry word ---------
# A platform's payout can print the merchant's statement descriptor as its ACH originator and entry, with the
# platform's payout id ('ID:ST-<id>', Bank of America's ID field and Chase's IND ID field). The id, not an entry that
# repeats the originator's first word, lifts the holder holds and the counter-debit hold; it never verifies.

BOFA_ST = "{orig} DES:{entry} ID:ST-{payout} INDN:{receiver} CO ID:0000000000 CCD"
CHASE_ST = (
    "ORIG CO NAME:{orig} ORIG ID:0000000000 DESC DATE:310302 CO ENTRY DESCR:{entry}SEC:CCD TRACE#:000000000000000 "
    "EED:310302 IND ID:ST-{payout} IND NAME:{receiver} TRN: 0000000000TC"
)
PAYOUT_IDS = ("A0B0C0D0E1F0", "A0B0C0D0E2F0", "A0B0C0D0E3F0")
PAYOUT_AMOUNTS = (800.0, 900.0, 1000.0)
BAKERY = "CONTOSO BAKERY LLC"
PAYOUT_FIELDS = {"orig": "CONTOSO BAKERY", "receiver": BAKERY}


def _payouts(layout, **fields):
    values = {**PAYOUT_FIELDS, "entry": "CONTOSO BAK " if layout is CHASE_ST else "CONTOSO BAK", **fields}
    return [(layout.format(payout=payout, **values), amount) for payout, amount in zip(PAYOUT_IDS, PAYOUT_AMOUNTS)]


@pytest.mark.parametrize("layout", [BOFA_ST, CHASE_ST])
def test_r18_a_payout_under_the_merchant_s_descriptor_verifies_beside_the_holder_s_name(layout):
    rows = _payouts(layout)
    assert _tiers(rows, holder_name=BAKERY) == [REPEATS] * 3
    assert _tiers(rows) == [REPEATS] * 3
    # The census's holder fact (G3) reads it as pass 7 does: no holder.
    records = classify_statement_transactions(_statement(rows, holder_name=BAKERY))
    for record in records:
        revenue = _revenue(record.normalized_description)
        assert not tr.region_names_holder(record, revenue, tc.payer_region(revenue))
        assert not tr.self_originated(revenue, tc.payer_region(revenue))


def test_r18_a_payout_whose_descriptor_prints_another_entry_is_not_held_as_the_holder():
    rows = _payouts(BOFA_ST, orig="CONTOSO BAKERY B", entry="CN 00000", receiver="SAMPLE OWNER")
    tiers = _tiers(rows, holder_name=BAKERY)
    assert HOLDER_NAME not in tiers
    assert all(tier[0] in ("verified", "counted_flagged") for tier in tiers)


@pytest.mark.parametrize("layout", [BOFA_ST, CHASE_ST])
def test_r18_the_holder_s_own_push_echoing_its_name_is_held_on_the_row_alone(layout):
    # No payout id: the entry repeating the originator's first word no longer passes the self test.
    entry = "NORTHWIND " if layout is CHASE_ST else "NORTHWIND"
    text = layout.format(orig="NORTHWIND MARINE", entry=entry, payout="0000000001",
                         receiver="NORTHWIND MARINE LLC").replace("ST-0000000001", "0000000001")
    assert _twice(text, 900.0) == [HOLDER_NAME, HOLDER_NAME]
    assert tr.self_originated(_revenue(text), tc.payer_region(_revenue(text)))


@pytest.mark.parametrize(("text", "payout"), [
    (BOFA_ST.format(payout="A0B0C0D0E1F0", entry="CONTOSO BAK", **PAYOUT_FIELDS), True),
    (CHASE_ST.format(payout="A0B0C0D0E1F0", entry="CONTOSO BAK ", **PAYOUT_FIELDS), True),
    (BOFA_ST.format(payout="ABCDE12345", entry="CONTOSO BAK", **PAYOUT_FIELDS), True),
    # No payout id, a short one, or a payout id on a wire, a person-to-person or a push rail.
    (BOFA_ST.format(payout="A0B0C0D0E1F0", entry="CONTOSO BAK", **PAYOUT_FIELDS).replace("ST-", ""), False),
    (BOFA_ST.format(payout="A0B0C0", entry="CONTOSO BAK", **PAYOUT_FIELDS), False),
    ("WIRE TYPE:WIRE IN DATE: 310302 TIME:1015 ET TRN:2031030200123456 ORIG:CONTOSO BAKERY LLC ID:ST-A0B0C0D0E1F0",
     False),
    ("ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF ID ST A0B0C0D0E1F0", False),
    ("RTP CREDIT CONTOSO BAKERY LLC ID ST A0B0C0D0E1F0", False),
    # Review round 1 (finding 6a): a payout id holds letters and digits, never a town or a number alone.
    ("CONTOSO SUPPLY DES:PAYMENT ID:ST SAMPLEVILLE INDN:CONTOSO BAKERY LLC CO ID:0000000000 CCD", False),
    (BOFA_ST.format(payout="ABCDEFGHIJKL", entry="CONTOSO BAK", **PAYOUT_FIELDS), False),
    (BOFA_ST.format(payout="123456789012", entry="CONTOSO BAK", **PAYOUT_FIELDS), False),
])
def test_r18_processor_payout_reads_the_payout_id(text, payout):
    assert tr.processor_payout(_revenue(text)) is payout


@pytest.mark.parametrize("text", [
    "ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF ID ST A0B0C0D0E1F0",
    "WIRE TYPE:WIRE IN DATE: 310302 TIME:1015 ET TRN:2031030200123456 ORIG:CONTOSO BAKERY LLC ID:ST-A0B0C0D0E1F0",
])
def test_r18_the_holder_s_own_zelle_or_wire_printing_a_payout_id_is_still_held(text):
    assert _tiers([(text, 900.0)], holder_name=BAKERY) == [HOLDER_NAME]


def test_r18_the_holder_s_own_transfer_push_is_still_held():
    text = BOFA_ST.format(orig="CONTOSO BAKERY LLC", entry="TRANSFER", payout="0", receiver=BAKERY).replace(
        "ST-0", "0")
    assert _tiers([(text, 400.0)]) == [HOLDER_NAME]


def test_r18_a_stripe_originated_payout_on_chase_stays_verified_beside_the_holder_s_name():
    rows = _payouts(CHASE_ST, orig="STRIPE", entry="TRANSFER ")
    assert {tier[0] for tier in _tiers(rows, holder_name=BAKERY)} == {"verified"}


def test_r18_a_platform_s_financing_printing_a_payout_id_is_never_revenue():
    rows = _payouts(BOFA_ST, orig="STRIPE CAPITAL")
    tiers = _tiers(rows, holder_name=BAKERY)
    assert all(tier[0] in ("excluded_pending_review", "non_revenue") for tier in tiers)
    assert HOLDER_NAME not in tiers


# --- Audit round 2, R2-B04 (R19): a holder's name the parser read is a known name, whatever its shape -------------
# A trailing CO, an AND or & partnership, a DBA or 'Operating as' name, a dotted S.E.N.C. and a name of five words or
# more are real holder names: the holder hold reads them already, so the statement never says no holder's name is
# known; and the I47 strip removes them, a cut last word at the row's end included.

UNLABELLED = ("counted_flagged", "named_payer_unlabelled")
NON_SALE = ("excluded_pending_review", "non_sale_purpose")
PAY = ("excluded_pending_review", "payroll_or_salary")


def _pnc_zelles(own):
    return [(f"ZELLE FROM {own} CONF 1", 2500.0), ("ZELLE FROM FABRIKAM DINER LLC CONF 2", 310.0)]


def _unscreened(rows, **kwargs):
    statement = _statement(rows, **kwargs)
    records = classify_statement_transactions(statement)
    return tr.holder_unscreened(records), compute_metrics(statement, classifications=records).holder_unscreened


@pytest.mark.parametrize(("account_name", "holder_name", "own"), [
    ("Business Checking", "CONTOSO TRADING CO.", "CONTOSO TRADING CO"),
    ("Business Checking", "THE NORTHWIND SAMPLE TRADING CO.", "THE NORTHWIND SAMPLE TRADING CO"),
    ("Business Checking", "NORTHWIND AND SAMPLE PARTNERS", "NORTHWIND AND SAMPLE PARTNERS"),
    ("Business Checking", "SAMPLE NORTHWIND & CONTOSO PARTNERS", "SAMPLE NORTHWIND & CONTOSO PARTNERS"),
    ("Business Checking", "SAMPLE PERSON DBA NORTHWIND PLUMBING", "NORTHWIND PLUMBING"),
    ("Business Checking", "NORTHWIND SAMPLE CONTOSO FABRIKAM TRADING", "NORTHWIND SAMPLE CONTOSO FABRIKAM TRADING"),
    ("SAMPLE PERSON Operating as: NORTHWIND PLUMBING", None, "NORTHWIND PLUMBING"),
    ("NORTHWIND CONTOSO S.E.N.C.", None, "NORTHWIND CONTOSO S.E.N.C."),
])
def test_r19_a_holder_s_name_of_any_shape_is_known(account_name, holder_name, own):
    rows = _pnc_zelles(own)
    kwargs = {"account_name": account_name, "holder_name": holder_name, "bank": "PNC"}
    # The holder hold reads the name already: the tiers are unchanged.
    assert _tiers(rows, **kwargs) == [HOLDER_NAME, P2P]
    assert _unscreened(rows, **kwargs) == (False, False)


def test_r19_a_zero_transaction_statement_with_a_holder_s_name_is_screened():
    statement = Statement(account_name="Business Checking", holder_name="NORTHWIND PLUMBING LLC", bank="PNC")
    assert compute_metrics(statement, classifications=[]).holder_unscreened is False
    assert tr.holder_unscreened([], holder_name="NORTHWIND PLUMBING LLC", account_name="Business Checking") is False
    assert tr.holder_unscreened([], account_name="NORTHWIND PLUMBING LLC") is False
    assert tr.holder_unscreened([], account_name="Business Checking") is True


@pytest.mark.parametrize("account_name", [
    None, "Business Complete Checking", "INSTANCES AMOUNT", "SAMPLEVILLE CO", "NORTHWIND CO", "NORTHWINDLTD",
])
def test_r19_a_product_a_city_and_state_or_a_glued_word_still_names_nobody(account_name):
    rows = [("ZELLE FROM FABRIKAM DINER LLC CONF 2", 310.0)]
    assert _unscreened(rows, account_name=account_name, bank="PNC") == (True, True)
    statement = Statement(account_name=account_name, bank="PNC")
    assert compute_metrics(statement, classifications=[]).holder_unscreened is True


@pytest.mark.parametrize(("name", "usable"), [
    ("CONTOSO TRADING CO.", True),
    ("THE NORTHWIND SAMPLE TRADING CO.", True),
    ("NORTHWIND AND SAMPLE PARTNERS", True),
    ("SAMPLE NORTHWIND & CONTOSO PARTNERS", True),
    ("SAMPLE PERSON DBA NORTHWIND PLUMBING", True),
    ("SAMPLE PERSON Operating as: NORTHWIND PLUMBING", True),
    ("NORTHWIND CONTOSO S.E.N.C.", True),
    ("NORTHWIND CONTOSO SENC", True),
    # A city and state, a glued legal form, a product and five words with no form name nobody.
    ("SAMPLEVILLE CO", False),
    ("NORTHWIND CO", False),
    ("NORTHWINDLTD", False),
    ("Business Complete Checking", False),
    ("NORTHWIND SAMPLE CONTOSO FABRIKAM TRADING", False),
])
def test_r19_the_usable_holder_name_reads_a_trailing_co_partners_a_dba_and_senc(name, usable):
    assert tr._usable_holder_name(name) is usable


WF_UNLABELLED = "CONTOSO PTO PAYMENT 540115 1234567 {receiver}"


@pytest.mark.parametrize("parser", [False, True])
@pytest.mark.parametrize(("holder", "receiver", "tier"), [
    ("NORTHWIND DISTRIBUTION CO", "NORTHWIND DISTRIBUTION", UNLABELLED),
    ("NORTHWIND PAYROLL CO", "NORTHWIND PAYROLL", UNLABELLED),
    ("NORTHWIND DISTRIBUTION LLC", "NORTHWIND DISTRIBUTIO", UNLABELLED),
    ("NORTHWIND DISTRIBUTION LLC", "NORTHWIND DISTRIB", UNLABELLED),
    ("SAMPLE PERSON DBA NORTHWIND DISTRIBUTION", "NORTHWIND DISTRIBUTION", UNLABELLED),
    # Audit round 3, R3-B10 (R3-37): the row-end cut is tried before the whole-word runs, so a name of three words or
    # more cut in its third word or later is stripped; a leading THE is no word of a run, read with and without it.
    ("FABRIKAM COASTAL DISTRIBUTION LLC", "FABRIKAM COASTAL DISTRIBUT", UNLABELLED),
    ("FABRIKAM COASTAL DISTRIBUTORS INC", "FABRIKAM COASTAL DISTRIBUTO", UNLABELLED),
    ("NORTHWIND HARBOR RETIREMENT PLANNING LLC", "NORTHWIND HARBOR RETIREM", UNLABELLED),
    ("NORTHWIND SAMPLE INVESTMENTS LLC", "NORTHWIND SAMPLE INVESTMEN", UNLABELLED),
    ("THE NORTHWIND DISTRIBUTION CO", "NORTHWIND DISTRIBUTION", UNLABELLED),
    ("THE NORTHWIND DISTRIBUTION CO", "NORTHWIND DISTRIBUTIO", UNLABELLED),
    ("THE NORTHWIND DISTRIBUTION CO", "THE NORTHWIND DISTRIBUTION", UNLABELLED),
    # A third party's own hold word is no holder's name; a cut name followed by another word is not at the row's end.
    ("NORTHWIND PLUMBING LLC", "CONTOSO DISTRIBUTION", NON_SALE),
    ("NORTHWIND PLUMBING CO", "CONTOSO PAYROLL", PAY),
    ("NORTHWIND DISTRIBUTION LLC", "NORTHWIND DISTRIBUTIO SAMPLE", NON_SALE),
    ("NORTHWIND PLUMBING LLC", "CONTOSO COASTAL DISTRIBUT", NON_SALE),
    ("FABRIKAM COASTAL DISTRIBUTION LLC", "FABRIKAM COASTAL DISTRIBUTIO SAMPLE", NON_SALE),
])
def test_r19_the_holder_s_own_name_never_holds_a_customer_s_unlabelled_payment(holder, receiver, tier, parser):
    kwargs = (
        {"account_name": "Business Checking", "holder_name": holder} if parser else {"account_name": holder}
    )
    assert _tiers([(WF_UNLABELLED.format(receiver=receiver), 4000.0)], bank="Wells Fargo", **kwargs) == [tier]


def test_r3_37_a_leading_the_is_no_word_of_a_holder_run():
    runs = tr._holder_runs("THE NORTHWIND DISTRIBUTION CO", False)
    # No 'THE <one word>' run: a third party printed 'THE NORTHWIND …' keeps its words.
    assert runs.match("THE NORTHWIND PAYROLL") is None
    assert runs.sub(" ", "THE NORTHWIND PAYROLL").split() == ["THE", "NORTHWIND", "PAYROLL"]
    for printed in ("NORTHWIND DISTRIBUTION", "THE NORTHWIND DISTRIBUTION", "NORTHWIND DISTRIBUTION CO"):
        assert runs.search(printed) is not None, printed
    # The row-end cut is tried first at each word: the third word's cut leaves nothing behind.
    cut = tr._holder_runs("FABRIKAM COASTAL DISTRIBUTION LLC", False)
    assert cut.sub(" ", "CONTOSO PTO PAYMENT FABRIKAM COASTAL DISTRIBUT").split() == ["CONTOSO", "PTO", "PAYMENT"]
    assert cut.sub(" ", "FABRIKAM COASTAL DISTRIBUTIO SAMPLE").split() == ["DISTRIBUTIO", "SAMPLE"]


# --- Audit round 4, batch R4-B08 (R4-32) ---
# Audit round 4, R4-32 (R3-37's rule, "a leading THE is no word of a run", applied to the classifier's receiver-block
# strip; standard A4 counts a customer's ACH, B7 holds the holder's own name): the strip reads a THE-led holder's run
# with THE and without it, so a third party printing the holder without THE as its unlabelled receiver is read by its
# own name, as it is for the same holder printed without THE. Fabricated rows only.

R4_32_HOLDER = "THE NORTHWIND BAKERY LLC"
#: (row, bank, credits): the receiver layouts the strip reads (Fifth Third's and PNC's two-word block, Truist's slot).
R4_32_ROWS = [
    ("ACH CREDIT FABRIKAM SUPPLY CO PAYMENT NORTHWIND BAKERY", "Fifth Third", 1),
    ("TRANSFER FABRIKAM INC NORTHWIND BAKERY CUSTOMER ID 0000000000", "Truist", 1),
    ("ACH CORP DEPOSIT FABRIKAM SUPPLY NORTHWIND BAKERY CUSTOMER ID 0000000000", "Truist", 1),
    ("ACH CREDIT FABRIKAM SUPPLY CO VENDOR PMT NORTHWIND BAKERY", "PNC", 2),
]


def _r4_32_tiers(text, bank, credits, holder):
    return (_tiers([(text, 1500.40)], bank=bank, holder_name=holder) if credits == 1
            else _twice(text, 1500.40, bank=bank, holder_name=holder))


@pytest.mark.parametrize(("text", "bank", "credits", "tiers"), [
    (*R4_32_ROWS[0], [ONE_OFF]),
    (*R4_32_ROWS[1], [P2P]),
    (*R4_32_ROWS[2], [COMPANY]),
    (*R4_32_ROWS[3], [REMITTANCE, REMITTANCE]),
])
def test_r4_32_a_the_led_holder_printed_without_the_as_a_receiver_is_never_the_payer(text, bank, credits, tiers):
    assert _r4_32_tiers(text, bank, credits, R4_32_HOLDER) == tiers
    assert _r4_32_tiers(text, bank, credits, R4_32_HOLDER) == _r4_32_tiers(text, bank, credits,
                                                                            "NORTHWIND BAKERY LLC")


@pytest.mark.parametrize("receiver", ["NORTHWIND BAKERY", "THE NORTHWIND BAKERY"])
def test_r4_32_the_strip_reads_the_the_led_run_with_and_without_the(receiver):
    payer = f"FABRIKAM SUPPLY PAYMENT {receiver}"
    assert tc._without_trailing_holder_run(payer, [R4_32_HOLDER]) == "FABRIKAM SUPPLY PAYMENT"


@pytest.mark.parametrize(("text", "bank", "holder", "tier"), [
    # The holder's own money stays held.
    ("ONLINE TRANSFER FROM THE NORTHWIND BAKERY LLC", "Wells Fargo", R4_32_HOLDER, HOLDER_NAME),
    ("NORTHWIND BAKERY DES:PAYMENT ID:0001 INDN:NORTHWIND BAKERY CO ID:0000000001 CCD", "Bank of America", R4_32_HOLDER,
     HOLDER_NAME),
    # Wells Fargo's unlabelled receiver reads as before.
    (WF_UNLABELLED.format(receiver="NORTHWIND BAKERY"), "Wells Fargo", R4_32_HOLDER, UNLABELLED),
    (WF_UNLABELLED.format(receiver="THE NORTHWIND BAKERY"), "Wells Fargo", R4_32_HOLDER, UNLABELLED),
    # A THE-led holder whose bare words leave one test word reads as before.
    ("ACH CREDIT FABRIKAM SUPPLY CO PAYMENT CONTOSO GROUP", "Fifth Third", "THE CONTOSO GROUP LLC", ONE_OFF),
    ("TRANSFER FABRIKAM INC CONTOSO GROUP CUSTOMER ID 0000000000", "Truist", "THE CONTOSO GROUP LLC", P2P),
    (WF_UNLABELLED.format(receiver="CONTOSO GROUP"), "Wells Fargo", "THE CONTOSO GROUP LLC", HOLDER_NAME),
    ("ZELLE PAYMENT FROM CONTOSO GROUP CONF 1234567890", "Chase", "THE CONTOSO GROUP LLC", HOLDER_NAME),
])
def test_r4_32_the_controls_read_as_before(text, bank, holder, tier):
    assert _tiers([(text, 1500.40)], bank=bank, holder_name=holder) == [tier]


# --- Audit round 2, R2-B04 (R20): two shared trade words, or a person's given name, are not the holder ------------

YACHT = "NORTHWIND YACHT SERVICE LLC"
PERSON_HELD = [
    ("ZELLE PAYMENT FROM SAMPLE PERSON NORTHWIND MARINE LLC CONF 1234567890", "Chase", "NORTHWIND MARINE LLC"),
    ("Zel From Northwind Yacht Service WFCT0A0B0C04", "PNC", YACHT),
    ("ZELLE PAYMENT FROM SAMPLEMAN TRUCKING CONF 1234567890", "Chase", "JORDAN SAMPLEMAN TRUCKING LLC"),
    ("CORPORATE ACH PAYROLL 0000012345 Jordan Sampleman 0000012345", "PNC", "JORDAN SAMPLEMAN JR"),
    ("ZELLE PAYMENT FROM ALEXIS NORTHWINDER CONF 1234567890", "Chase", "JORDAN SAMPLEMAN ALEXIS NORTHWINDER"),
    ("ZELLE PAYMENT FROM JORDAN SAMPLEMAN CONF 1234567890", "Chase", "JORDAN SAMPLEMAN"),
    ("ZELLE PAYMENT FROM SAMPLEMAN JORDAN CONF 1234567890", "Chase", "JORDAN SAMPLEMAN"),
    # The holder's own name cut short by the bank's field stays the holder's when both names read as a person's.
    ("ZELLE PAYMENT FROM JORDAN SAMPL CONF 1234567890", "Chase", "JORDAN SAMPLEMAN"),
    (CHASE_ACH.format(orig="CONTOSO HOLDINGS LLC", entry="PAYMENT ", receiver="CONTOSO BAKERY"), "Chase",
     "CONTOSO BAKERY"),
    (CHASE_ACH.format(orig="JORDAN FABRIKAM INC", entry="PAYMENT ", receiver="JORDAN SAMPLEMAN"), "Chase",
     "JORDAN SAMPLEMAN"),
]


@pytest.mark.parametrize(("text", "tier"), [
    # Audit round 3, R3-12 (R3-B12): pass 7 reads PNC's ZEL as its ZELLE twin, a person-to-person credit (counted
    # p2p; it was counted named_payer_unlabelled): still a customer, never the holder.
    ("Zel From First Sample Yacht Service WFCT0A0B0C01", P2P),
    ("Zel From Contoso Yacht Service WFCT0A0B0C02", P2P),
])
def test_r20_another_company_sharing_two_trade_words_is_a_customer(text, tier):
    assert _tiers([(text, 600.0)], bank="PNC", holder_name=YACHT) == [tier]


def test_r20_a_trade_namesake_the_holder_also_pays_is_held_by_its_counter_debit():
    rows = [("Zel From First Sample Yacht Service WFCT0A0B0C01", 600.0),
            ("Zel To First Sample Yacht Service WFCT0A0B0C03", -200.0)]
    assert _tiers(rows, bank="PNC", holder_name=YACHT) == [("excluded_pending_review", "payer_also_debited")]


@pytest.mark.parametrize(("text", "holder", "tier"), [
    (CHASE_ACH.format(orig="FABRIKAM AUTO REPAIR", entry="PAYMENT ", receiver="NORTHWIND AUTO REPAIR INC"),
     "NORTHWIND AUTO REPAIR INC", ONE_OFF),
    ("ZELLE PAYMENT FROM CONTOSO HOME IMPROVEMENT CONF 1234567890", "NORTHWIND HOME IMPROVEMENT LLC", P2P),
    ("ZELLE PAYMENT FROM CONTOSO YACHT SERVICE CONF 1234567890", "QZX YACHT SERVICE LLC", P2P),
])
def test_r20_a_payer_leading_with_another_name_is_never_the_holder_on_trade_words(text, holder, tier):
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=holder) == [tier]


@pytest.mark.parametrize(("text", "bank", "holder"), [
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER CONF 1234567890", "Chase", "JORDAN SAMPLEMAN"),
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER PAYMENT ID 1234", "Truist", "JORDAN SAMPLEMAN"),
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER CONF 1234567890", "Chase", "JORDAN LEE SAMPLEMAN"),
    ("ZELLE PAYMENT FROM ANA NORTHWINDER CONF 1234567890", "Chase", "ANA SAMPLEMAN"),
])
def test_r20_a_person_sharing_only_the_holder_s_given_name_is_another_person(text, bank, holder):
    assert _tiers([(text, 900.0)], bank=bank, holder_name=holder) == [P2P]


@pytest.mark.parametrize(("text", "bank", "holder"), PERSON_HELD)
def test_r20_the_holder_s_own_name_words_still_hold(text, bank, holder):
    assert _tiers([(text, 900.0)], bank=bank, holder_name=holder) == [HOLDER_NAME]


@pytest.mark.parametrize(("text", "person"), [
    ("JORDAN SAMPLEMAN", True),
    ("JORDAN LEE SAMPLEMAN", True),
    ("JORDAN NORTHWINDER 1234", True),
    ("JORDAN SAMPLEMAN ALEXIS NORTHWINDER", True),
    # A company form, a trade-name marker, a noise word, five words or one word read as no person.
    ("JORDAN FABRIKAM INC", False),
    ("JORDAN SAMPLEMAN DBA NORTHWIND", False),
    ("NORTHWIND HOLDINGS", False),
    ("JORDAN LEE ALEXIS SAMPLE NORTHWINDER", False),
    ("JORDAN", False),
])
def test_r20_the_person_name_reading(text, person):
    assert tc._person_name_reading(text) is person


# Audit round 3, R3-B10 (R3-38): two shared trade words name the holder only when the payer's own printed lead word (a
# name-starter, a short word or an initialism included) is a holder word or the holder's abbreviation, or when they
# include the holder's lead; and a holder whose name leads with a name-starter or a two-letter initialism is named,
# by those words or by its brand word, only by a payer that prints that lead.

@pytest.mark.parametrize("lead", ["GOLDEN", "ACE", "ROYAL", "PREMIER", "UNITED", "NORTH", "JB", "AAA", "BAY"])
def test_r3_38_a_payer_leading_with_a_starter_or_a_short_word_is_a_customer(lead):
    text = f"ZELLE PAYMENT FROM {lead} YACHT SERVICE CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=YACHT) == [P2P]


@pytest.mark.parametrize("lead", ["ACE", "GREAT", "PREMIER", "AAA"])
def test_r3_38_a_ccd_from_a_company_leading_with_a_starter_or_a_short_word_is_a_customer(lead):
    text = CHASE_ACH.format(orig=f"{lead} AUTO REPAIR", entry="PAYMENT ", receiver="NORTHWIND AUTO REPAIR INC")
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="NORTHWIND AUTO REPAIR INC") == [ONE_OFF]


@pytest.mark.parametrize(("text", "holder", "tier"), [
    ("ZELLE PAYMENT FROM CONTOSO YACHT SERVICE CONF 1234567890", "GOLDEN YACHT SERVICE LLC", P2P),
    ("ZELLE PAYMENT FROM FABRIKAM YACHT SERVICE CONF 1234567890", "GOLDEN YACHT SERVICE LLC", P2P),
    ("ZELLE PAYMENT FROM ROYAL YACHT SERVICE CONF 1234567890", "GOLDEN YACHT SERVICE LLC", P2P),
    ("ZELLE PAYMENT FROM CONTOSO MARINE REPAIR CONF 1234567890", "JB MARINE REPAIR LLC", P2P),
    (CHASE_ACH.format(orig="CONTOSO AUTO REPAIR", entry="PAYMENT ", receiver="GREAT AUTO REPAIR INC"),
     "GREAT AUTO REPAIR INC", ONE_OFF),
])
def test_r3_38_a_holder_leading_with_a_starter_or_an_initialism_is_named_only_by_a_payer_printing_it(
    text, holder, tier,
):
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=holder) == [tier]


@pytest.mark.parametrize(("text", "holder"), [
    ("ZELLE PAYMENT FROM GOLDEN YACHT SERVICE CONF 1234567890", "GOLDEN YACHT SERVICE LLC"),
    ("ZELLE PAYMENT FROM SAMPLE PERSON GOLDEN YACHT SERVICE LLC CONF 1234567890", "GOLDEN YACHT SERVICE LLC"),
    # A brand affiliate printing the holder's starter lead.
    ("ZELLE PAYMENT FROM GOLDEN YACHT CHARTERS CONF 1234567890", "GOLDEN YACHT SERVICE LLC"),
    ("ZELLE PAYMENT FROM JB MARINE REPAIR CONF 1234567890", "JB MARINE REPAIR LLC"),
    # The holder's own name with its lead abbreviated.
    ("ZELLE PAYMENT FROM NW YACHT SERVICE CONF 1234567890", YACHT),
    ("ZELLE PAYMENT FROM NWD YACHT SERVICE CONF 1234567890", YACHT),
    # The holder's own name without its starter lead.
    ("ZELLE PAYMENT FROM CHOICE PLUMBING CONF 1234567890", "FIRST CHOICE PLUMBING LLC"),
])
def test_r3_38_the_holder_s_own_lead_or_its_abbreviation_still_holds(text, holder):
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=holder) == [HOLDER_NAME]


def test_r3_38_the_narrowed_arm_never_newly_holds():
    text = "ZELLE PAYMENT FROM FIRST RATE PLUMBING SUPPLY CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="FIRST CHOICE PLUMBING LLC") == [P2P]


def test_r3_38_the_printed_lead_and_the_holder_s_abbreviation():
    assert tc._printed_lead(["ACH", "CREDIT", "JB", "YACHT"]) == "JB"
    assert tc._printed_lead(["THE", "GOLDEN", "YACHT"]) == "GOLDEN"
    assert tc._printed_lead(["DEL", "NORTHWIND"]) == "NORTHWIND"
    assert tc._printed_lead(["ACH", "CREDIT"]) is None
    holder = ["NORTHWIND", "YACHT", "SERVICE"]
    for word in ("NW", "NWD", "NYS", "NY"):
        assert tc._holder_abbreviation(word, holder), word
    for word in ("ACE", "AAA", "JB", "NORTHWIND", "NORTH", "WN"):
        assert not tc._holder_abbreviation(word, holder), word


# --- Audit round 4, batch R4-B08 (R4-30) ---
# Audit round 4, R4-30 (§5.2's and R20's stated intent, R3-38's rule for every dropped lead; standard B6, B7 need
# affiliation or the holder's own name, which shared trade words never prove): the printed lead skips only layout and
# channel labels, legal filler and the bank and account words (_PRINTED_LEAD_SKIP), so a name led by a name-like noise
# word (AMERICAN, NATIONAL, ELITE, PREMIUM, ...) keeps that word as its printed lead. A payer led by such a word is a
# customer of a holder that prints another lead; a holder led by one is named, in the shared-word, brand-word and (with a
# company form) one-word arms, only by a payer that prints it. The holder's own name with its lead dropped stays held
# through the payer's own lead (the P arm). The new reading can only release (the abbreviation arm reads the printed
# lead, so the holder's own lead abbreviated stays held).

R4_30_LEADS = ["AMERICAN", "NATIONAL", "GENERAL", "ELITE", "TOTAL", "USA", "AMERICA", "PREMIUM", "STANDARD", "SELECT",
               "COMMERCIAL", "ADVANTAGE", "GROUP", "SOLUTIONS"]
R4_30_NOISE_HOLDERS = ["AMERICAN", "NATIONAL", "GENERAL", "ELITE", "TOTAL", "USA", "AMERICA"]
R4_30_ZELLE = "ZELLE PAYMENT FROM {payer} CONF 0000000000"
R4_30_REPAIR = "NORTHWIND AUTO REPAIR INC"


@pytest.mark.parametrize("lead", R4_30_LEADS)
def test_r4_30_a_payer_led_by_a_name_like_noise_word_is_a_customer(lead):
    zelle = R4_30_ZELLE.format(payer=f"{lead} YACHT SERVICE")
    assert _tiers([(zelle, 900.0)], bank="Chase", holder_name=YACHT) == [P2P]
    ccd = CHASE_ACH.format(orig=f"{lead} AUTO REPAIR", entry="PAYMENT ", receiver=R4_30_REPAIR)
    assert _tiers([(ccd, 900.0)], bank="Chase", holder_name=R4_30_REPAIR) == [ONE_OFF]


def test_r4_30_two_ccds_from_a_noise_led_customer_verify_as_a_starter_led_one_does():
    def rows(orig):
        return [(CHASE_ACH.format(orig=orig, entry="PAYMENT ", receiver=R4_30_REPAIR), amount)
                for amount in (1210.40, 1187.15)]

    assert _tiers(rows("AMERICAN AUTO REPAIR"), bank="Chase", holder_name=R4_30_REPAIR) == [REPEATS, REPEATS]
    assert _tiers(rows("GOLDEN AUTO REPAIR"), bank="Chase", holder_name=R4_30_REPAIR) == [REPEATS, REPEATS]


@pytest.mark.parametrize("payer", ["CONTOSO YACHT SERVICE", "FABRIKAM YACHT SERVICE", "ROYAL YACHT SERVICE"])
@pytest.mark.parametrize("noise", R4_30_NOISE_HOLDERS)
def test_r4_30_a_holder_led_by_a_name_like_noise_word_is_named_only_by_a_payer_printing_it(noise, payer):
    holder = f"{noise} YACHT SERVICE LLC"
    assert _tiers([(R4_30_ZELLE.format(payer=payer), 900.0)], bank="Chase", holder_name=holder) == [P2P]


def test_r4_30_a_ccd_from_another_company_into_a_noise_led_holder_is_a_customer():
    text = CHASE_ACH.format(orig="CONTOSO AUTO REPAIR", entry="PAYMENT ", receiver="AMERICAN AUTO REPAIR INC")
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="AMERICAN AUTO REPAIR INC") == [ONE_OFF]


@pytest.mark.parametrize("payer", ["PLUMBING SUPPLY", "ROYAL ROOFING", "ROOFING SUPPLY"])
@pytest.mark.parametrize("holder", ["AMERICAN PLUMBING LLC", "NATIONAL ROOFING LLC", "ELITE ROOFING LLC",
                                    "TOTAL ROOFING LLC"])
def test_r4_30_a_one_word_holder_led_by_a_name_like_noise_word_with_a_form_must_print_with_it(holder, payer):
    assert _tiers([(R4_30_ZELLE.format(payer=payer), 900.0)], bank="Chase", holder_name=holder) == [P2P]


@pytest.mark.parametrize(("payer", "holder", "field"), [
    # The holder's own name, printed whole, with its lead dropped, or abbreviated (the P arm and R3-38's abbreviation).
    ("AMERICAN YACHT SERVICE", "AMERICAN YACHT SERVICE LLC", "holder_name"),
    ("YACHT SERVICE", "AMERICAN YACHT SERVICE LLC", "holder_name"),
    ("AM YACHT SERVICE", "AMERICAN YACHT SERVICE LLC", "holder_name"),
    # A brand affiliate printing the holder's lead.
    ("AMERICAN YACHT CHARTERS", "AMERICAN YACHT SERVICE LLC", "holder_name"),
    # The one-word holder's own run.
    ("AMERICAN PLUMBING", "AMERICAN PLUMBING LLC", "holder_name"),
    ("ELITE ROOFING", "ELITE ROOFING LLC", "holder_name"),
    # A form-less account-name field keeps the one-word reading (a product word before a nickname): recorded residual.
    ("CONTOSO", "PLATINUM CONTOSO", "account_name"),
    ("CONTOSO LLC", "ELITE CONTOSO", "account_name"),
])
def test_r4_30_the_holder_s_own_names_stay_held(payer, holder, field):
    assert _tiers([(R4_30_ZELLE.format(payer=payer), 900.0)], bank="Chase", **{field: holder}) == [HOLDER_NAME]


@pytest.mark.parametrize(("payer", "holder"), [
    ("FIRST RATE PLUMBING SUPPLY", "FIRST CHOICE PLUMBING LLC"),
    ("AMERICAN RATE PLUMBING SUPPLY", "AMERICAN CHOICE PLUMBING LLC"),
    ("NATIONAL RATE PLUMBING SUPPLY", "ELITE CHOICE PLUMBING LLC"),
    ("ELITE PLUMBING SUPPLY", "AMERICAN PLUMBING LLC"),
])
def test_r4_30_the_narrowed_arms_never_newly_hold(payer, holder):
    assert _tiers([(R4_30_ZELLE.format(payer=payer), 900.0)], bank="Chase", holder_name=holder) == [P2P]


def test_r4_30_the_printed_lead_skips_labels_filler_and_account_words_only():
    assert tc._printed_lead(["AMERICAN", "YACHT", "SERVICE"]) == "AMERICAN"
    assert tc._printed_lead(["ONLINE", "BUSINESS", "CONTOSO"]) == "CONTOSO"
    assert tc._printed_lead(["DEPOSIT", "ACH", "INTERNATIONAL", "CONTOSO"]) == "CONTOSO"
    assert tc._printed_lead(["THE", "ELITE", "ROOFING"]) == "ELITE"
    assert tc._printed_lead(["BMO", "BUS", "CKG", "NORTHWIND"]) == "NORTHWIND"
    # Every skipped word is a holder-test noise word; the name-like noise words are read.
    assert tc._PRINTED_LEAD_SKIP <= tc._HOLDER_TEST_NOISE | tc._HOLDER_RUN_LEGAL_FORMS
    for word in ("AMERICAN", "AMERICA", "NATIONAL", "USA", "CANADA", "GENERAL", "ELITE", "TOTAL", "PREMIUM", "PLATINUM",
                 "SELECT", "ADVANTAGE", "GROUP", "SOLUTIONS", "ONTARIO"):
        assert word in tc._HOLDER_TEST_NOISE and word not in tc._PRINTED_LEAD_SKIP, word
    for word in ("INTERNATIONAL", "DIRECT", "NEW", "BUSINESS", "CHECKING", "BANK", "THE", "LLC", "USD"):
        assert word in tc._PRINTED_LEAD_SKIP, word
    assert tc._dropped_lead_run("AMERICAN PLUMBING LLC", ["PLUMBING"]) == ("AMERICAN", "PLUMBING")
    assert tc._dropped_lead_run("PLATINUM CONTOSO", ["CONTOSO"]) is None


# Audit round 3, R3-B10 (R3-39): a DBA holder whose name leads with a person ('<owner> DBA <trade>') is read whole as
# that person's name against a payer that reads as a person, so another person sharing only the owner's given name is
# counted, whatever the trade side prints; a company payer leading with the given name keeps the brand-word arm.

R3_39_HOLDER = "JORDAN SAMPLEMAN DBA CONTOSO PLUMBING"


@pytest.mark.parametrize(("text", "bank", "tier"), [
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER CONF 1234567890", "Chase", P2P),
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER PAYMENT ID 1234", "Truist", P2P),
    (CHASE_ACH.format(orig="JORDAN NORTHWINDER", entry="PAYMENT ", receiver="CONTOSO PLUMBING"), "Chase", ONE_OFF),
])
@pytest.mark.parametrize("holder", [
    R3_39_HOLDER, "JORDAN SAMPLEMAN D/B/A CONTOSO PLUMBING", "JORDAN SAMPLEMAN DBA CONTOSO PLUMBING LLC",
])
@pytest.mark.parametrize("field", ["holder_name", "account_name"])
def test_r3_39_a_person_sharing_only_a_dba_owner_s_given_name_is_another_person(text, bank, tier, holder, field):
    assert _tiers([(text, 900.0)], bank=bank, **{field: holder}) == [tier]


def test_r3_39_a_short_given_name_is_read_the_same_way():
    text = "ZELLE PAYMENT FROM ANA NORTHWINDER CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="ANA SAMPLEMAN DBA CONTOSO PLUMBING") == [P2P]


@pytest.mark.parametrize("payer", [
    "JORDAN SAMPLEMAN", "SAMPLEMAN JORDAN", "JORDAN SAMPL", "CONTOSO PLUMBING", "JORDAN FABRIKAM INC",
])
def test_r3_39_the_dba_holder_s_own_names_and_a_company_leading_with_the_given_name_stay_held(payer):
    text = f"ZELLE PAYMENT FROM {payer} CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=R3_39_HOLDER) == [HOLDER_NAME]


def test_r3_39_the_reversed_dba_holder_still_counts_another_person():
    text = "ZELLE PAYMENT FROM JORDAN NORTHWINDER CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="CONTOSO PLUMBING DBA JORDAN SAMPLEMAN") == [P2P]


# --- Audit round 4, batch R4-B08 (R4-31) ---
# Audit round 4, R4-31 (R3-39's ruling and standard A8: a different person sharing only the owner's given name is a
# customer): the trade-name markers are one set for the classifier and the revenue pass (DBA, D/B/A, AKA, OPERATING AS,
# TRADING AS, DOING BUSINESS AS), and a printed O/A or T/A after a name of two words or more is read as DBA, so a sole
# proprietor printed '<owner> OPERATING AS <trade>' reads as '<owner> DBA <trade>' does, as holder_name or as
# account_name, on every rail. A spaced 'O A' with no slash is a person's initials, never a marker.

R4_31_MARKERS = ["OPERATING AS", "Operating as:", "TRADING AS", "DOING BUSINESS AS", "O/A", "T/A"]
#: (row, bank, the Zelle Yes reading, the Zelle No reading): the same person-payer rows R3-39 counts.
R4_31_ROWS = [
    ("ZELLE PAYMENT FROM JORDAN NORTHWINDER CONF 1234567890", "Chase", P2P, ("non_revenue", "zelle_excluded")),
    ("E-TRANSFER RECEIVED JORDAN NORTHWINDER 0A0B0C", "Royal Bank of Canada", P2P, P2P),
    (CHASE_ACH.format(orig="JORDAN NORTHWINDER", entry="PAYMENT ", receiver="CONTOSO PLUMBING"), "Chase", ONE_OFF,
     ONE_OFF),
    (FEDWIRE.replace("B/O: NORTHWIND MARINE LLC", "B/O: JORDAN NORTHWINDER").format(bnf="CONTOSO PLUMBING"), "Chase",
     WIRE, WIRE),
]


def _final_in(rows, zelle, **kwargs):
    """The credits' final tier and reason (or method) in one Zelle reading, the Zelle policy's own included."""
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in _records_in(rows, zelle, **kwargs)]


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize("field", ["holder_name", "account_name"])
@pytest.mark.parametrize("marker", R4_31_MARKERS)
@pytest.mark.parametrize(("text", "bank", "yes", "no"), R4_31_ROWS)
def test_r4_31_a_person_sharing_only_the_owner_s_given_name_is_another_person_under_every_marker(
    text, bank, yes, no, marker, field, zelle,
):
    holder = f"JORDAN SAMPLEMAN {marker} CONTOSO PLUMBING"
    assert _final_in([(text, 900.0)], zelle, bank=bank, **{field: holder}) == [yes if zelle else no]
    # Each reading equals R3-39's DBA holder's.
    dba = "JORDAN SAMPLEMAN DBA CONTOSO PLUMBING"
    assert _final_in([(text, 900.0)], zelle, bank=bank, **{field: holder}) == _final_in(
        [(text, 900.0)], zelle, bank=bank, **{field: dba})
    if not zelle:
        assert _tiers_in([(text, 900.0)], zelle, bank=bank, **{field: holder}) == [yes]


def test_r4_31_a_three_letter_given_name_is_read_the_same_way():
    text = "ZELLE PAYMENT FROM ALI NORTHWINDER CONF 1234567890"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name="ALI SAMPLEMAN O/A CONTOSO PLUMBING") == [P2P]


@pytest.mark.parametrize("marker", R4_31_MARKERS)
@pytest.mark.parametrize("payer", ["JORDAN SAMPLEMAN", "CONTOSO PLUMBING", "JORDAN FABRIKAM INC"])
def test_r4_31_the_owner_s_names_and_a_company_leading_with_the_given_name_stay_held(payer, marker):
    text = f"ZELLE PAYMENT FROM {payer} CONF 1234567890"
    holder = f"JORDAN SAMPLEMAN {marker} CONTOSO PLUMBING"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=holder) == [HOLDER_NAME]


def test_r4_31_a_slash_marker_is_read_only_after_a_name_and_spaced_initials_are_no_marker():
    assert tc.account_name_text("JORDAN SAMPLEMAN O/A CONTOSO PLUMBING") == "JORDAN SAMPLEMAN DBA CONTOSO PLUMBING"
    assert tc.account_name_text("JORDAN SAMPLEMAN t/a: CONTOSO PLUMBING") == "JORDAN SAMPLEMAN DBA CONTOSO PLUMBING"
    # No name before the slash (none, or one word): never a marker.
    assert "DBA" not in tc.account_name_text("O/A CONTOSO").split()
    assert "DBA" not in tc.account_name_text("JORDAN O/A CONTOSO").split()
    # A person's initials printed without a slash read as today.
    assert tc.account_name_text("JOHN O A SAMPLEMAN") == "JOHN O A SAMPLEMAN"
    zelle = "ZELLE PAYMENT FROM {payer} CONF 1234567890"
    for payer, tier in (("JOHN NORTHWINDER", P2P), ("JOHN SAMPLEMAN", HOLDER_NAME), ("JOHN O A SAMPLEMAN", HOLDER_NAME)):
        assert _tiers([(zelle.format(payer=payer), 900.0)], bank="Chase", holder_name="JOHN O A SAMPLEMAN") == [tier]


@pytest.mark.parametrize("marker", R4_31_MARKERS)
def test_r4_31_every_marker_names_its_holder_by_either_side(marker):
    assert tr._usable_holder_name(f"JORDAN SAMPLEMAN {marker} CONTOSO PLUMBING")


def test_r4_31_the_two_modules_read_one_marker_set():
    assert tr._HOLDER_NAME_MARKER is tc._HOLDER_TRADE_NAME
    for marker in ("DBA", "D B A", "AKA", "OPERATING AS", "TRADING AS", "DOING BUSINESS AS"):
        assert tc._HOLDER_TRADE_NAME.search(f"JORDAN SAMPLEMAN {marker} CONTOSO PLUMBING"), marker


# --- Audit round 2, R2-B04 (R04 parts 1 and 3): a processor's credit printing the holder's name, Capital One's tails -

R04_HOLDER = "CONTOSO TRADING LLC"


def test_r04_capital_one_s_mercury_tails_never_hide_the_holder_s_own_push():
    text = "ACH DEPOSIT CONTOSO TRADING LLC MERCURYACH 000000 CONTOSO TRADING LLC MRCR G0ABC0"
    assert _tiers([(text, 1500.0)], bank="Capital One") == [HOLDER_NAME]
    assert tr.self_originated(_revenue(text), tc.payer_region(_revenue(text)), "Capital One")
    other = "ACH DEPOSIT FABRIKAM SUPPLY LLC MERCURYACH 000000 CONTOSO TRADING LLC MRCR G0ABC0"
    assert _tiers([(other, 1500.0)], bank="Capital One") != [HOLDER_NAME]


@pytest.mark.parametrize(("text", "bank"), [
    ("CONTOSO DES:CONTOSO ID:ST-AB12CD34EF56 INDN:CONTOSO TRADING LLC CO ID:0000000000 CCD", "Bank of America"),
    ("MISC PAYMENT CONTOSO TRADING LIGHTSPEE", "Scotiabank"),
    ("INTUIT TRANSFER CONTOSO TRADING", "Wells Fargo"),
    ("TECHNOLOGY CONTOSO TRADING INC TECHNOLOGY FEES SAMPLEVILLE", "Mission Valley Bank"),
    ("MARKETING CONTOSO TRADING FRAN 0012 MARKETING FEE 0001 TO 0002 SAMPLEVILLE", "Mission Valley Bank"),
    ("FABRIKAM INC DES:PAYMENT ID:0001 INDN:CONTOSO TRADING LLC CO ID:0000000000 CCD", "Bank of America"),
    ("ZELLE PAYMENT FROM NORTHWIND DINER CONF 1234567890", "Bank of America"),
])
def test_r04_a_processor_s_or_a_franchisor_s_credit_printing_the_holder_s_name_keeps_its_tier(text, bank):
    tiers = _tiers([(text, 1500.0)], bank=bank, holder_name=R04_HOLDER)
    assert tiers == _tiers([(text, 1500.0)], bank=bank)
    assert tiers != [HOLDER_NAME]
    records = classify_statement_transactions(_statement([(text, 1500.0)], bank=bank, holder_name=R04_HOLDER))
    revenue = _revenue(records[0].normalized_description)
    assert not tr.region_names_holder(records[0], revenue, tc.payer_region(revenue))


@pytest.mark.parametrize("text", [
    "ZELLE PAYMENT FROM CONTOSO TRADING LLC CONF 1234567890",
    "WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:CONTOSO TRADING LLC ID:1234567890",
    "RTP CREDIT CONTOSO TRADING LLC MARKETING FEE",
    "CONTOSO TRADING LLC DES:TRANSFER ID:0001 INDN:SAMPLE OWNER CO ID:0000000000 CCD",
])
def test_r04_the_holder_s_own_push_wire_and_rails_keep_the_holder_hold(text):
    assert _tiers([(text, 1500.0)], bank="Bank of America", holder_name=R04_HOLDER) == [HOLDER_NAME]


def test_r04_a_platform_s_word_inside_the_holder_s_own_name_is_the_holder_s():
    holder = "NORTHWIND INTUIT GROUP LLC"
    text = "NORTHWIND INTUIT GROUP LLC DES:TRANSFER ID:0001 INDN:SAMPLE OWNER CO ID:0000000000 CCD"
    assert _tiers([(text, 1500.0)], bank="Bank of America", holder_name=holder) == [HOLDER_NAME]
    revenue = _revenue(text)
    assert not tr.platform_credit(revenue, tc.payer_region(revenue), (holder,))


@pytest.mark.parametrize(("text", "named"), [
    ("MISC PAYMENT CONTOSO TRADING LIGHTSPEE", True),
    ("MISC PAYMENT CONTOSO TRADING LIGHTSPEED", True),
    ("INTUIT TRANSFER CONTOSO TRADING", True),
    ("TECHNOLOGY CONTOSO TRADING INC TECHNOLOGY FEES SAMPLEVILLE", True),
    # A cut keeps seven letters or more; a whole word that starts an alias is no cut.
    ("MISC PAYMENT CONTOSO TRADING LIGHTS", False),
    ("MISC PAYMENT CONTOSO TRADING SHOP", False),
    # A whole word that starts a longer name is no cut of it, nor is a generic word (PAYMENT, for PAYMENTECH).
    ("MISC PAYMENT CONTOSO TRADING BUILDER", False),
    ("ACH CREDIT CONTOSO TRADING RENT PAYMENT", False),
    ("ZELLE PAYMENT FROM CONTOSO TRADING LIGHTSPEED", False),
    ("CONTOSO TRADING LLC DES:TRANSFER ID:0001 INDN:SAMPLE OWNER CO ID:0000000000 CCD", False),
])
def test_r04_platform_credit_reads_the_originator_and_the_fee_words_outside_the_holder_s_names(text, named):
    revenue = _revenue(text)
    assert tr.platform_credit(revenue, tc.payer_region(revenue), (R04_HOLDER,)) is named


# --- Audit round 2, R2-B05 (R04 part 2): the holder's name read from page 1 on the banks that printed none ---------

def _page_one(text: str) -> str:
    from ocr.document import StatementMarkdown

    return StatementMarkdown(source_file="sample.pdf", model="sample", pages=[text]).to_markdown()


def _bofa_holder() -> str | None:
    from analysis import bofa

    return bofa._holder_reading(_page_one(
        "CONTOSO TRADING LLC 100 SAMPLE LN SAMPLEVILLE, TX 75000-0001\nYour Business Advantage Fundamentals Banking\n"
        "for May 1, 2054 to May 31, 2054 Account number: 0000 0000 0000\nCONTOSO TRADING LLC\nAccount summary\n"
    )).name


def _wells_holder() -> str | None:
    from analysis import wells

    return wells._holder_reading(_page_one(
        "Questions?\nAvailable by phone 24 hours a day\n"
        "CONTOSO TRADING LLC 100 SAMPLE PKWY SAMPLEVILLE TX 75000-0001\nWrite: Wells Fargo Bank, N.A. (000)\n"
    )).name


def _rbc_holder() -> str | None:
    from analysis import rbc

    return rbc._holder_reading(_page_one(
        "Business Account Statement\n"
        "RBBDA00000_0000000 E D 00000 00000 CONTOSO TRADING INC. 100 SAMPLE DR SAMPLEVILLE ON X0X 0X0\n"
    )).name


BOFA = "Bank of America"
BOFA_PRODUCT = "Business Advantage Fundamentals Banking"
R2B05_ZELLE = "ZELLE PAYMENT FROM CONTOSO TRADING LLC CONF# 0A0B0C0D0"
R2B05_WIRE = "WIRE TYPE:WIRE IN DATE: 540302 TIME:1015 ET TRN:2054030200123456 ORIG:CONTOSO TRADING LLC ID:0000000000"


def test_r2b05_the_page_one_readers_read_the_holder():
    assert _bofa_holder() == "CONTOSO TRADING LLC"
    assert _wells_holder() == "CONTOSO TRADING LLC"
    assert _rbc_holder() == "CONTOSO TRADING INC."


def test_r2b05_bank_of_america_s_own_zelle_is_held_once_page_one_names_the_holder():
    assert _tiers([(R2B05_ZELLE, 1234.56)], bank=BOFA, account_name=BOFA_PRODUCT) == [P2P]
    assert _tiers([(R2B05_ZELLE, 1234.56)], bank=BOFA, account_name=BOFA_PRODUCT, holder_name=_bofa_holder()) == [
        HOLDER_NAME
    ]


def test_r2b05_bank_of_america_s_own_wires_verified_today_are_held_once_page_one_names_the_holder():
    rows = [(R2B05_WIRE, 9000.0), (R2B05_WIRE.replace("0123456", "0123457"), 9000.0)]
    assert _tiers(rows, bank=BOFA, account_name=BOFA_PRODUCT) == [WIRE_REPEATS, WIRE_REPEATS]
    assert _tiers(rows, bank=BOFA, account_name=BOFA_PRODUCT, holder_name=_bofa_holder()) == [HOLDER_NAME, HOLDER_NAME]


def test_r2b05_wells_fargo_s_own_instant_payment_is_held_once_page_one_names_the_holder():
    text = "INSTANT PMT FROM CONTOSO TRADING LLC ON 05/02 REF # 0000000000"
    assert _tiers([(text, 2500.0)], bank="Wells Fargo") != [HOLDER_NAME]
    assert _tiers([(text, 2500.0)], bank="Wells Fargo", holder_name=_wells_holder()) == [HOLDER_NAME]


def test_r2b05_rbc_s_own_e_transfer_is_held_once_page_one_names_the_holder():
    text = "E-TRANSFER RECEIVED CONTOSO TRADING INC 0A0B0C"
    assert _tiers([(text, 2500.0)], bank="Royal Bank of Canada") != [HOLDER_NAME]
    assert _tiers([(text, 2500.0)], bank="Royal Bank of Canada", holder_name=_rbc_holder()) == [HOLDER_NAME]


@pytest.mark.parametrize(("text", "bank"), [
    ("CONTOSO DES:CONTOSO ID:ST-AB12CD34EF56 INDN:CONTOSO TRADING LLC CO ID:0000000000 CCD", BOFA),
    ("MISC PAYMENT CONTOSO TRADING LIGHTSPEE", "Scotiabank"),
    ("INTUIT TRANSFER CONTOSO TRADING", "Wells Fargo"),
    ("TECHNOLOGY CONTOSO TRADING INC TECHNOLOGY FEES SAMPLEVILLE", "Mission Valley Bank"),
    ("FABRIKAM INC DES:PAYMENT ID:0001 INDN:CONTOSO TRADING LLC CO ID:0000000000 CCD", BOFA),
    ("ZELLE PAYMENT FROM NORTHWIND DINER CONF 1234567890", BOFA),
])
def test_r2b05_the_r2b04_controls_keep_their_tier_once_page_one_names_the_holder(text, bank):
    holder = _bofa_holder()
    assert _tiers([(text, 1500.0)], bank=bank, holder_name=holder) == _tiers([(text, 1500.0)], bank=bank)
    assert _tiers([(text, 1500.0)], bank=bank, holder_name=holder) != [HOLDER_NAME]


def test_r2b05_a_customer_s_ach_naming_the_holder_as_receiver_stays_verified_once_page_one_names_the_holder():
    text = "FABRIKAM INC DES:PAYMENT ID:0001 INDN:CONTOSO TRADING LLC CO ID:0000000000 CCD"
    assert _twice(text, bank=BOFA, holder_name=_bofa_holder()) == [REPEATS, REPEATS] == _twice(text, bank=BOFA)


def test_r2b05_a_northwind_zelle_stays_counted_once_page_one_names_the_holder():
    text = "ZELLE PAYMENT FROM NORTHWIND DINER CONF 1234567890"
    assert _tiers([(text, 1500.0)], bank=BOFA, holder_name=_bofa_holder()) == [P2P]


def test_r2b05_a_page_that_prints_only_a_product_leaves_the_holder_unread():
    from analysis import bofa

    assert bofa._holder_reading(_page_one("Your Business Advantage Fundamentals Banking\nAccount summary\n")) == (
        None, None
    )


# --- Audit round 3, R3-B10 (R3-17): the holder's name read as the payer's -------------------------------------------
# The normaliser turns a possessive's apostrophe into a space ('SAMPLE'S' reads 'SAMPLE S'), and the payer reading
# drops a single letter and a digit token (payer_name): the holder's name is read the same way, so a possessive's S
# never stops the receiver-block strip, nor the run of a two-letter initialism's one-word holder.

R3_17_TRUIST = "EFT FABRIKAM INSURANCE SAMPLE S INSURANCE IN CUSTOMER ID 0000"
R3_17_FIFTH_THIRD = "ACH CREDIT NORTHWIND SUPPLY CO PAYMENT CONTOSO S FLOWER SHOP"
R3_17_JB_PUSH = "JB S TRUCKING LLC DES:SALE ID:{n} INDN:JB S TRUCKING LLC CO ID:0000000001 CCD"
INSURER_FOR_WORK = ("counted_flagged", "insurer_paid_for_services")


def test_r3_17_a_possessive_holder_in_truist_s_receiver_slot_is_the_receiver():
    tiers = _tiers([(R3_17_TRUIST, 1000.0)], holder_name="SAMPLE'S INSURANCE INC", bank="Truist")
    assert tiers == [INSURER_FOR_WORK]
    assert tiers == _tiers([(R3_17_TRUIST, 1000.0)], holder_name="SAMPLES INSURANCE INC", bank="Truist")


def test_r3_17_a_possessive_holder_printed_after_another_payer_is_the_receiver():
    tiers = _tiers([(R3_17_FIFTH_THIRD, 600.0)], holder_name="CONTOSO'S FLOWER SHOP LLC", bank="Fifth Third")
    assert tiers == [ONE_OFF]
    assert tiers == _tiers([(R3_17_FIFTH_THIRD, 600.0)], holder_name="CONTOSOS FLOWER SHOP LLC", bank="Fifth Third")
    assert tc._without_trailing_holder_run(
        "NORTHWIND SUPPLY PAYMENT CONTOSO FLOWER SHOP", ["CONTOSO S FLOWER SHOP LLC"]
    ) == "NORTHWIND SUPPLY PAYMENT"


def test_r3_17_a_labelled_sender_printing_the_possessive_holder_stays_held():
    text = "ONLINE TRANSFER FROM CONTOSO S FLOWER SHOP LLC REF 0001"
    assert _tiers([(text, 600.0)], holder_name="CONTOSO'S FLOWER SHOP LLC", bank="Wells Fargo") == [HOLDER_NAME]


@pytest.mark.parametrize("holder", ["JB'S TRUCKING LLC", "JB TRUCKING LLC"])
def test_r3_17_a_two_letter_possessive_holder_s_own_rows_are_held(holder):
    rows = [(R3_17_JB_PUSH.format(n="0001"), 800.0), (R3_17_JB_PUSH.format(n="0002"), 900.0)]
    assert _tiers(rows, holder_name=holder, bank="Bank of America") == [HOLDER_NAME, HOLDER_NAME]
    transfer = "ONLINE TRANSFER FROM JB S TRUCKING LLC"
    assert _tiers([(transfer, 700.0)], holder_name=holder, bank="Bank of America") == [HOLDER_NAME]


def test_r3_17_a_customer_leading_with_the_industry_word_is_never_the_possessive_holder():
    text = "TRUCKING PARTNERS INC DES:PAYMENT ID:0001 INDN:JB S TRUCKING LLC CO ID:0000000001 CCD"
    assert HOLDER_NAME not in _twice(text, holder_name="JB'S TRUCKING LLC", bank="Bank of America")
    assert tc.holder_named("TRUCKING PARTNERS INC", "JB'S TRUCKING LLC") is False
    assert tc.holder_named("JB TRUCKING LLC", "JB'S TRUCKING LLC") is True


@pytest.mark.parametrize(("name", "words"), [
    ("CONTOSO S FLOWER SHOP LLC", ["CONTOSO", "FLOWER", "SHOP"]),
    ("JOHN Q SAMPLE LLC", ["JOHN", "SAMPLE"]),
    ("A1 NORTHWIND PLUMBING LLC", ["NORTHWIND", "PLUMBING"]),
    ("NORTHWIND HARBOR AGENCY INC", ["NORTHWIND", "HARBOR", "AGENCY"]),
])
def test_r3_17_the_holder_s_run_words_are_the_payer_reading_s(name, words):
    assert tc._holder_run_words(name) == words


@pytest.mark.parametrize(("holder", "receiver"), [
    ("JOHN Q SAMPLE LLC", "JOHN Q SAMPLE"),
    ("A1 NORTHWIND PLUMBING LLC", "A1 NORTHWIND PLUMBING"),
])
def test_r3_17_a_middle_initial_or_a_digit_token_never_stops_the_strip(holder, receiver):
    payer = tc.payer_name(f"FABRIKAM SUPPLY PAYMENT {receiver}")
    assert tc._without_trailing_holder_run(payer, [holder]) == "FABRIKAM SUPPLY PAYMENT"


def test_r3_17_the_dropped_lead_run_skips_a_single_letter():
    assert tc._dropped_lead_run("JB S TRUCKING LLC", ["TRUCKING"]) == ("JB", "TRUCKING")
    assert tc._dropped_lead_run("JB TRUCKING LLC", ["TRUCKING"]) == ("JB", "TRUCKING")


# --- Audit round 4, batch R4-B08 (R4-58) ---
# Audit round 4, R4-58 (standard B1 and B7: the holder's own name is excluded, held and releasable; the owner's
# 2026-10-06 Zelle amendment, "Zelle from the business owner's own name ... held for review"): a name printed with its
# apostrophe is read both as printed (the normalizer's space: 'JOE S PIZZA') and glued ('JOES PIZZA'), on the holder's
# side (_apostrophe_glued, one more name of the holder's) and on the payer's (_possessive_glued: a lone S glued onto the
# word before it, a lone O or D onto the word after it, read when a glued word is a word of the holder's names and only
# with §5.2's shared-word minimum), and the row-alone self test reads both spellings. The strips read the glued name
# too, so a third party printing the holder glued as its receiver stays counted. Fabricated rows only.

#: (the holder's name as printed, the name glued, the name as the normalizer spaces it).
R4_58_NAMES = [
    ("JOE'S PIZZA LLC", "JOES PIZZA LLC", "JOE S PIZZA LLC"),
    ("O'BRIEN ELECTRIC INC", "OBRIEN ELECTRIC INC", "O BRIEN ELECTRIC INC"),
    ("D'ARCY ROOFING INC", "DARCY ROOFING INC", "D ARCY ROOFING INC"),
    ("BETTY'S HOME BAKERY LLC", "BETTYS HOME BAKERY LLC", "BETTY S HOME BAKERY LLC"),
]


def _r4_58_rows(originator, receiver):
    """The holder's own money in each layout: (rows, bank) by layout, the originator or sender printed one way and the
    receiver field (where the layout prints one) the other."""
    receiver_words = receiver.rsplit(" ", 1)[0]
    return {
        "bofa_push": ([(f"{originator} DES:PAYMENT ID:000{n} INDN:{receiver} CO ID:0000000001 CCD", amount)
                       for n, amount in ((1, 1212.40), (2, 1187.15))], "Bank of America"),
        "chase_push": ([(CHASE_ACH.format(orig=originator, entry="PAYMENT ", receiver=receiver), amount)
                        for amount in (1212.40, 1187.15)], "Chase"),
        "chase_zelle": ([(f"ZELLE PAYMENT FROM {originator} CONF 0000000000", 2985.60)], "Chase"),
        "chase_wire": ([(FEDWIRE.replace("B/O: NORTHWIND MARINE LLC", f"B/O: {originator}").format(
            bnf="SAMPLE PERSON"), 6012.40)], "Chase"),
        "wells_unlabelled": ([(f"{originator} PAYMENT 540115 0000000 {receiver_words}", 1500.40)], "Wells Fargo"),
    }


@pytest.mark.parametrize("layout", ["bofa_push", "chase_push", "chase_zelle", "chase_wire", "wells_unlabelled"])
@pytest.mark.parametrize(("holder", "glued", "spaced"), R4_58_NAMES)
def test_r4_58_the_holder_s_apostrophe_name_printed_glued_is_the_holder_s(holder, glued, spaced, layout):
    rows, bank = _r4_58_rows(glued, spaced)[layout]
    assert _tiers(rows, bank=bank, holder_name=holder) == [HOLDER_NAME] * len(rows)


@pytest.mark.parametrize("layout", ["bofa_push", "chase_push", "chase_zelle"])
def test_r4_58_a_glued_holder_s_name_printed_spaced_is_the_holder_s(layout):
    rows, bank = _r4_58_rows("JOE S PIZZA LLC", "JOE S PIZZA LLC")[layout]
    assert _tiers(rows, bank=bank, holder_name="JOES PIZZA LLC") == [HOLDER_NAME] * len(rows)


def test_r4_58_the_self_test_reads_both_spellings_with_no_holder_name():
    rows, bank = _r4_58_rows("JOE S PIZZA LLC", "JOE S PIZZA LLC")["bofa_push"]
    assert _tiers(rows, bank=bank) == [HOLDER_NAME, HOLDER_NAME]
    rows, bank = _r4_58_rows("JOES PIZZA LLC", "JOE S PIZZA LLC")["bofa_push"]
    assert _tiers(rows, bank=bank) == [HOLDER_NAME, HOLDER_NAME]
    rows, bank = _r4_58_rows("JOE S PIZZA LLC", "JOES PIZZA LLC")["bofa_push"]
    assert _tiers(rows, bank=bank) == [HOLDER_NAME, HOLDER_NAME]
    # Another business's push to the holder stays a customer's.
    rows, bank = _r4_58_rows("FABRIKAM SUPPLY LLC", "JOE S PIZZA LLC")["bofa_push"]
    assert _tiers(rows, bank=bank) == [REPEATS, REPEATS]


def test_r4_58_a_third_party_printing_the_possessive_holder_glued_as_its_receiver_stays_counted():
    truist = "EFT FABRIKAM INSURANCE SAMPLES INSURANCE IN CUSTOMER ID 0000"
    bare = "EFT FABRIKAM INSURANCE SAMPLE INSURANCE IN CUSTOMER ID 0000"
    for text in (R3_17_TRUIST, truist, bare):
        tiers = _tiers([(text, 1000.0)], holder_name="SAMPLE'S INSURANCE INC", bank="Truist")
        assert tiers == [INSURER_FOR_WORK]
        assert tiers == _tiers([(text, 1000.0)], holder_name="SAMPLES INSURANCE INC", bank="Truist")
    fifth_third = "ACH CREDIT NORTHWIND SUPPLY CO PAYMENT CONTOSOS FLOWER SHOP"
    assert _tiers([(fifth_third, 600.0)], holder_name="CONTOSO'S FLOWER SHOP LLC", bank="Fifth Third") == [ONE_OFF]


@pytest.mark.parametrize(("payer", "holder", "tier"), [
    # A middle initial is no possessive: the glued reading needs two shared words.
    ("ROBERT S SMITH", "ROBERTS PLUMBING LLC", P2P),
    ("JOHN Q SAMPLE", "JOHN SAMPLE LLC", HOLDER_NAME),
    # A one-word glued name needs its one word.
    ("JOE S LLC", "JOES LLC", HOLDER_NAME),
])
def test_r4_58_the_glued_payer_reading_keeps_the_shared_word_minimum(payer, holder, tier):
    text = f"ZELLE PAYMENT FROM {payer} CONF 0000000000"
    assert _tiers([(text, 900.0)], bank="Chase", holder_name=holder) == [tier]


def test_r4_58_a_hold_word_inside_the_holder_s_glued_name_never_holds_a_third_party():
    text = "FABRIKAM INC PAYMENT 540115 0000000 JOES DISTRIBUTION"
    assert _tiers([(text, 1500.40)], holder_name="JOE'S DISTRIBUTION LLC", bank="Wells Fargo") == [UNLABELLED]
    assert tr._holder_strip_names_of(None, "JOE'S DISTRIBUTION LLC") == ("JOES DISTRIBUTION LLC",)


def test_r4_58_the_glued_readings():
    assert tc._apostrophe_glued("JOE'S PIZZA LLC") == "JOES PIZZA LLC"
    assert tc._apostrophe_glued("JOE’S PIZZA LLC") == "JOES PIZZA LLC"
    assert tc._apostrophe_glued("JOE‘S PIZZA LLC") == "JOES PIZZA LLC"
    assert tc._apostrophe_glued("JOE`S PIZZA LLC") == "JOES PIZZA LLC"
    assert tc._apostrophe_glued("O'BRIEN ELECTRIC INC") == "OBRIEN ELECTRIC INC"
    assert tc._apostrophe_glued("D'ARCY ROOFING") == "DARCY ROOFING"
    assert tc._apostrophe_glued("CONTOSO LLC") is None
    assert tc._apostrophe_glued("CONTOSO ' LLC") is None
    assert tc._apostrophe_glued(None) is None
    assert tc._possessive_glued("JOE S PIZZA LLC") == "JOES PIZZA LLC"
    assert tc._possessive_glued("O BRIEN ELECTRIC") == "OBRIEN ELECTRIC"
    assert tc._possessive_glued("D ARCY ROOFING") == "DARCY ROOFING"
    assert tc._possessive_glued("CONTOSO PIZZA LLC") is None
    assert tr._same_name("JOE S PIZZA LLC", "JOES PIZZA LLC")
    assert tr._same_name("JOES PIZZA LLC", "JOE S PIZZA LLC")
    assert not tr._same_name("JOE S PIZZA LLC", "JOES BAKERY LLC")


# --- Audit round 3, R3-B10 review round 1 (finding 2): the classifier readers of the holder test ------------------
# Beside pass 7's hold, three classifier readers read the holder test: §6.3 narrowing 4 (a book or funds transfer is
# own-account only when its third-party originator is the holder), narrowing 8 (a named sender after an own-account
# designation that is no holder refuses the own-account reading) and steps 11 to 14's holder veto. The batch's test
# moves rows through them both ways: a released customer leaves non_revenue (narrowing 4 counts it as a wire sender,
# narrowing 8 holds it for review) and verifies by its own reading where the veto refused it; the possessive holder's
# own transfer enters non_revenue and its own invoice entry is held.

R3_B10_RELEASED = [
    ("GOLDEN YACHT SERVICE LLC", "CONTOSO YACHT SERVICE"),
    ("NORTHWIND YACHT SERVICE LLC", "ACE YACHT SERVICE"),
    ("JORDAN SAMPLEMAN DBA CONTOSO PLUMBING", "JORDAN NORTHWINDER"),
]
R3_B10_FUNDS_TRANSFER = "FUNDS TRANSFER CREDIT TT {sender}"
R3_B10_DESIGNATION = "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION 1234{n} {sender}"
R3_B10_OWN_ACCOUNT = ("non_revenue", "strong_non_revenue_rule")
R3_B10_DESIGNATED = ("excluded_pending_review", "transfer_account_designation")


def _r3_b10_designations(sender):
    return [(R3_B10_DESIGNATION.format(n=n, sender=sender), amount) for n, amount in ((1, 1500.0), (2, 1750.0))]


def _r3_b10_invoices(orig):
    return [(CHASE_ACH.format(orig=orig, entry=f"INVOICE 1234{n} ", receiver="CONTOSO"), amount)
            for n, amount in ((1, 900.0), (2, 950.0))]


@pytest.mark.parametrize(("holder", "sender"), R3_B10_RELEASED)
def test_r3_b10_r1_a_released_sender_leaves_the_own_account_readings(holder, sender):
    funds = [(R3_B10_FUNDS_TRANSFER.format(sender=sender), 2500.0)]
    assert _tiers(funds, holder_name=holder, bank="Royal Bank of Canada") == [WIRE]
    designations = _r3_b10_designations(sender)
    assert _tiers(designations, holder_name=holder, bank="Wells Fargo") == [R3_B10_DESIGNATED, R3_B10_DESIGNATED]


@pytest.mark.parametrize("sender", ["JB S TRUCKING LLC", "JB S TRUCKING"])
def test_r3_b10_r1_the_possessive_holder_s_own_transfer_enters_the_own_account_readings(sender):
    holder = "JB'S TRUCKING LLC"
    funds = [(R3_B10_FUNDS_TRANSFER.format(sender=sender), 2500.0)]
    assert _tiers(funds, holder_name=holder, bank="Royal Bank of Canada") == [R3_B10_OWN_ACCOUNT]
    designations = _r3_b10_designations(sender)
    assert _tiers(designations, holder_name=holder, bank="Wells Fargo") == [R3_B10_OWN_ACCOUNT, R3_B10_OWN_ACCOUNT]


@pytest.mark.parametrize(("holder", "orig"), R3_B10_RELEASED)
def test_r3_b10_r1_a_released_customer_verifies_by_its_own_reading(holder, orig):
    assert _tiers(_r3_b10_invoices(orig), holder_name=holder, bank="Chase") == [REMITTANCE, REMITTANCE]


def test_r3_b10_r1_the_veto_refuses_the_possessive_holder_s_own_invoice_entry():
    tiers = _tiers(_r3_b10_invoices("JB S TRUCKING LLC"), holder_name="JB'S TRUCKING LLC", bank="Chase")
    assert tiers == [HOLDER_NAME, HOLDER_NAME]


# --- Audit round 3, R3-B10 review round 1 (finding 3): the THE-led strip reads as the name without THE -------------
# R3-37 builds no 'THE <one word>' run and reads a THE-led name's runs bare too, so a THE-led holder's strip is the
# strip of the same name printed without THE. Two recorded effects (0 corpus rows): a receiver printing the holder as
# THE and one word, or cut under four letters into its second word, is not stripped, so a hold word of the holder's
# own name holds the customer's row; and a third party printing the two words after THE loses them, as it does for a
# holder named by those words alone.

@pytest.mark.parametrize(("holder", "receiver"), [
    ("DISTRIBUTION CENTER LLC", "DISTRIBUTION"),
    ("DISTRIBUTION CENTER LLC", "DISTRIBUTION CEN"),
    ("PAYROLL COMPANY INC", "PAYROLL CO"),
    ("RETIREMENT PLANNING GROUP LLC", "RETIREMENT"),
])
def test_r3_b10_r1_a_the_led_holder_s_short_receiver_reads_as_the_name_without_the(holder, receiver):
    def rows(printed):
        return [(WF_UNLABELLED.format(receiver=printed), 4000.0)]

    the = _tiers(rows(f"THE {receiver}"), holder_name=f"THE {holder}", bank="Wells Fargo")
    assert the == _tiers(rows(receiver), holder_name=holder, bank="Wells Fargo")
    assert the[0][0] == "excluded_pending_review"


def test_r3_b10_r1_a_the_led_holder_s_bare_run_strips_a_third_party_as_the_name_without_the():
    text = "FABRIKAM CAPITAL GROUP DES:PAYMENT ID:{n} INDN:{receiver} CO ID:1234567890 CCD"

    def tiers(holder):
        rows = [(text.format(n=n, receiver=holder), amount) for n, amount in ((1, 1500.0), (2, 1750.0))]
        return _tiers(rows, holder_name=holder, bank="Bank of America")

    assert tiers("THE CAPITAL GROUP LLC") == tiers("CAPITAL GROUP LLC")
    assert tr._without_holder_name("FABRIKAM CAPITAL GROUP", "THE CAPITAL GROUP LLC", whole_name=True).split() == [
        "FABRIKAM"
    ]


# --- Audit round 3, R3-B17 (R3-15): the holder's own number after an accounts-payable label -------------------------
# RBC's 'ACCOUNT PAYABLE PMT' and Scotiabank's 'ACCOUNTS PAYABLE' printed before a numbered company's number are
# removed before the payer region is read (as 'MISC PAYMENT' is), so the holder test's digit arm reads the holder's own
# number; a word-named payer after a reference keeps its region. Fabricated numbers and names, 2054 dates.

NUMBERED_HOLDER = "1234567 ONTARIO INC"
NUMBERED = ("counted_flagged", "numbered_company_payer")


@pytest.mark.parametrize(("text", "bank"), [
    ("ACCOUNT PAYABLE PMT 1234567 ONTARIO", "Royal Bank of Canada"),
    ("ACCOUNTS PAYABLE 1234567 ONTARIO", "Scotiabank"),
    ("ACCOUNTS PAYABLE PMT 1234567 ONTARIO INC", "Scotiabank"),
    ("ACCTS PAYABLE 1234567 ONTARIO", "Scotiabank"),
    # Already held: the MISC PAYMENT template is removed before the region.
    ("MISC PAYMENT 1234567 ONTARIO", "Royal Bank of Canada"),
])
def test_r3_15_the_holder_s_own_number_after_an_accounts_payable_label_is_held(text, bank):
    # Today the region was the label alone ('ACCOUNT PAYABLE PMT'), so the credit was counted numbered_company_payer.
    assert _tiers([(text, 12000.0)], holder_name=NUMBERED_HOLDER, bank=bank) == [HOLDER_NAME]
    assert tc.payer_region(tc.revenue_text(tc.normalize_transaction_description(text))).startswith("1234567 ONTARIO")


def test_r3_15_another_numbered_company_after_the_label_stays_counted():
    assert _tiers([("ACCOUNT PAYABLE PMT 7654321 ONTARIO", 12000.0)], holder_name=NUMBERED_HOLDER,
                  bank="Royal Bank of Canada") == [NUMBERED]


@pytest.mark.parametrize(("text", "region"), [
    ("ACCOUNTS PAYABLE 123456 NORTHWIND SUPPLY INC", "ACCOUNTS PAYABLE NORTHWIND SUPPLY INC"),
    ("ACCOUNTS PAYABLE 123456 NORTH MOUNTAIN PAVING", "ACCOUNTS PAYABLE NORTH MOUNTAIN PAVING"),
])
def test_r3_15_a_word_named_payer_after_the_label_keeps_its_region_and_reading(text, region):
    assert tc.payer_region(tc.revenue_text(tc.normalize_transaction_description(text))) == region
    assert _tiers([(text, 12000.0)], holder_name="NORTHWIND BAKERY LTD", bank="Scotiabank") == [REMITTANCE]


# --- Audit round 4, batch R4-B08 (R4-92) ---
# Audit round 4, R4-92 (standard B1/B7 and B6: the merchant's own money or a same-name affiliate is excluded, and the
# product holds it; B5's own intent, the digit block dropped "so the holder ... holds ... read the payer"): the holder
# test reads the payer past Navy Federal's 'DEPOSIT ACH PAID FROM' label (classifier.holder_test_region), so PAID never
# leads the payer's name; the payer region and its key keep the label, as B5 kept it. Fabricated rows only.

NAVY = "Navy Federal Credit Union"
R4_92_PAYMENT = "DEPOSIT ACH PAID FROM CONTOSO OPERATIONS PAYMENT 000000"
R4_92_VENDOR_PAY = "DEPOSIT ACH PAID FROM CONTOSO OPERATIONS VENDOR PAY 000000"
R4_92_CUSTOMER = "DEPOSIT ACH PAID FROM FABRIKAM SUPPLY PAYMENT 000000"


def _r4_92_tiers(rows, holder, zelle=True):
    return _final_in(rows, zelle, bank=NAVY, holder_name=holder)


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize("holder", ["CONTOSO OPERATIONS LLC", "CONTOSO LLC"])
def test_r4_92_a_one_word_holder_s_own_push_after_navy_federal_s_label_is_held(holder, zelle):
    rows = [(R4_92_PAYMENT, 2931.40), (R4_92_PAYMENT, 5000.00), (R4_92_VENDOR_PAY, 1210.40)]
    assert _r4_92_tiers(rows, holder, zelle) == [HOLDER_NAME] * 3


def test_r4_92_a_brand_word_affiliate_after_the_label_is_held_as_on_another_layout():
    navy = "DEPOSIT ACH PAID FROM CONTOSO LOGISTICS PAYROLL 000000"
    assert _r4_92_tiers([(navy, 2931.40)], "CONTOSO TRUCKING LLC") == [HOLDER_NAME]
    plain = "ACH CREDIT CONTOSO LOGISTICS PAYROLL"
    assert _tiers([(plain, 2931.40)], bank="Fifth Third", holder_name="CONTOSO TRUCKING LLC") == [HOLDER_NAME]


@pytest.mark.parametrize(("rows", "holder", "tiers"), [
    # A customer after the label verifies on its repeat, as before.
    ([(R4_92_CUSTOMER, 2931.40), (R4_92_CUSTOMER, 5000.00)], "CONTOSO OPERATIONS LLC", [REPEATS, REPEATS]),
    # A two-word holder's own push, the RTP form and a transfer-worded entry are held, as before.
    ([("DEPOSIT ACH PAID FROM CONTOSO TRUCKING PAYMENT 000000", 2931.40)], "CONTOSO TRUCKING LLC", [HOLDER_NAME]),
    ([("DEPOSIT RTP PAID FROM CONTOSO OPERATIONS PAYMENT 000000", 2931.40)], "CONTOSO OPERATIONS LLC", [HOLDER_NAME]),
    ([("DEPOSIT ACH PAID FROM CONTOSO OPERATIONS TRANSFER 000000", 2931.40)], "CONTOSO OPERATIONS LLC",
     [HOLDER_NAME]),
])
def test_r4_92_the_controls_read_as_before(rows, holder, tiers):
    assert _r4_92_tiers(rows, holder) == tiers


@pytest.mark.parametrize(("text", "region", "key"), [
    (R4_92_PAYMENT, "DEPOSIT ACH PAID FROM CONTOSO OPERATIONS PAYMENT", ("PAID", "CONTOSO", "OPERATIONS")),
    (R4_92_VENDOR_PAY, "DEPOSIT ACH PAID FROM CONTOSO OPERATIONS VENDOR PAY",
     ("PAID", "CONTOSO", "OPERATIONS", "VENDOR")),
    (R4_92_CUSTOMER, "DEPOSIT ACH PAID FROM FABRIKAM SUPPLY PAYMENT", ("PAID", "FABRIKAM", "SUPPLY")),
])
def test_r4_92_the_payer_region_and_its_key_keep_the_label(text, region, key):
    payer = tc.payer_region(_revenue(text))
    assert payer == region
    assert tc._payer_key(payer) == key


def test_r4_92_the_holder_test_region():
    assert tc.holder_test_region("DEPOSIT ACH PAID FROM CONTOSO OPERATIONS PAYMENT") == "CONTOSO OPERATIONS PAYMENT"
    assert tc.holder_test_region("DEPOSIT PAID FROM CONTOSO OPERATIONS") == "CONTOSO OPERATIONS"
    assert tc.holder_test_region("DEPOSIT ACH PAID FROM") == "DEPOSIT ACH PAID FROM"
    assert tc.holder_test_region("ACH CREDIT CONTOSO OPERATIONS") == "ACH CREDIT CONTOSO OPERATIONS"
    assert tr._receiver_holder_named("DEPOSIT ACH PAID FROM CONTOSO OPERATIONS", "CONTOSO OPERATIONS LLC")


# --- Audit round 4, R4-B08 late review ---
# The late review of R4-B08 (standard B1 and B7: the holder's own name is excluded, held and releasable; standard A4 and
# A8: a customer is never the holder by a shared given name or trade word). Finding 1 (R4-58): the payer's glued reading
# turned a customer's middle initial S into a one-test-word holder's name ('ROBERT S CONTOSO' read 'ROBERTS CONTOSO'
# named 'ROBERTS GROUP LLC'); it now names such a name only when its test words are the name's own, or when the glued
# word is followed only by a legal form, a noise word or the end. Finding 2 (R4-30): the printed-lead requirement
# released the holder's own push abbreviating a name-like noise lead with four letters or more (NATL, AMER, GENL, PREM,
# COMML, SLCT); it now reads such an abbreviation (the lead's letters in order from its first) as the lead. Minor 3
# (R4-30's one-word arm): a company-form holder led by a name-like noise word keeps its own one word, printed alone with
# forms or noise beside it, held. Fabricated rows only, both Zelle readings.

R4_B08_LATE_ZELLE = "ZELLE PAYMENT FROM {payer} CONF 0000000000"


def _r4_b08_late_layouts(payer, receiver):
    """The rows a payer can print in each layout the review probed: (rows, bank, a Zelle row) by layout."""
    return {
        "zelle": ([(R4_B08_LATE_ZELLE.format(payer=payer), 912.40)], "Chase", True),
        "wire": ([(FEDWIRE.replace("B/O: NORTHWIND MARINE LLC", f"B/O: {payer}").format(bnf=receiver), 6012.40)],
                 "Chase", False),
        "ccd": ([(CHASE_ACH.format(orig=payer, entry="PAYMENT ", receiver=receiver), amount)
                 for amount in (1212.40, 1187.15)], "Chase", False),
        "rbc_funds": ([(R3_B10_FUNDS_TRANSFER.format(sender=payer), 2500.0)], "Royal Bank of Canada", False),
        "wf_designation": (_r3_b10_designations(payer), "Wells Fargo", False),
    }


def _r4_b08_late_in_both(rows, bank, zelle_row, expected, **kwargs):
    """`expected` is the rules' reading of every credit in both Zelle readings: the final reading under Yes, and under No
    the rules' own reading (rules_reading), a Zelle row's final tier being the policy's exclusion."""
    assert _final_in(rows, True, bank=bank, **kwargs) == [expected] * len(rows)
    assert _tiers_in(rows, False, bank=bank, **kwargs) == [expected] * len(rows)
    final = ("non_revenue", "zelle_excluded") if zelle_row else expected
    assert _final_in(rows, False, bank=bank, **kwargs) == [final] * len(rows)


#: (holder, the customer printing a given name and a middle initial S).
R4_B08_LATE_MIDDLE_INITIAL = [
    ("ROBERTS GROUP LLC", "ROBERT S CONTOSO"),
    ("ROBERTS LLC", "ROBERT S CONTOSO"),
    ("ROBERTS SERVICES INC", "ROBERT S CONTOSO"),
    ("WILLIAMS HOLDINGS LLC", "WILLIAM S CONTOSO"),
    ("ADAMS ENTERPRISES LLC", "ADAM S CONTOSO"),
    ("EDWARDS MANAGEMENT INC", "EDWARD S CONTOSO"),
]
#: The customer's reading in each layout (the reading it had before R4-58).
R4_B08_LATE_CUSTOMER = {
    "zelle": P2P, "wire": WIRE, "ccd": REPEATS, "rbc_funds": WIRE, "wf_designation": R3_B10_DESIGNATED,
}


@pytest.mark.parametrize("layout", list(R4_B08_LATE_CUSTOMER))
@pytest.mark.parametrize(("holder", "payer"), R4_B08_LATE_MIDDLE_INITIAL)
def test_r4_b08_late_a_middle_initial_never_names_a_one_word_holder(holder, payer, layout):
    rows, bank, zelle_row = _r4_b08_late_layouts(payer, holder)[layout]
    _r4_b08_late_in_both(rows, bank, zelle_row, R4_B08_LATE_CUSTOMER[layout], holder_name=holder)


@pytest.mark.parametrize(("payer", "holder"), [
    # The glued reading is the name's own one word, a legal form or a noise word beside it, or two shared words.
    ("JOE S LLC", "JOES LLC"),
    ("JOE S", "JOES LLC"),
    ("JOE S GROUP", "JOES GROUP LLC"),
    ("ROBERT S PLUMBING", "ROBERTS PLUMBING LLC"),
])
@pytest.mark.parametrize("layout", ["zelle", "ccd"])
def test_r4_b08_late_the_one_word_glued_name_alone_stays_the_holder_s(payer, holder, layout):
    rows, bank, zelle_row = _r4_b08_late_layouts(payer, "SAMPLE RECEIVER")[layout]
    _r4_b08_late_in_both(rows, bank, zelle_row, HOLDER_NAME, holder_name=holder)


#: (holder, its own name with its name-like noise lead abbreviated, four letters or more).
R4_B08_LATE_ABBREVIATED = [
    ("NATIONAL YACHT SERVICE LLC", "NATL YACHT SERVICE"),
    ("AMERICAN AUTO REPAIR INC", "AMER AUTO REPAIR"),
    ("GENERAL ROOFING SUPPLY LLC", "GENL ROOFING SUPPLY"),
    ("PREMIUM AUTO REPAIR LLC", "PREM AUTO REPAIR"),
    ("COMMERCIAL ROOFING SUPPLY INC", "COMML ROOFING SUPPLY"),
    ("SELECT AUTO GLASS LLC", "SLCT AUTO GLASS"),
]
#: The holder's own money in each layout: held as the holder's name, or (RBC's funds transfer, Wells Fargo's own-account
#: designation) the own-account non_revenue reading.
R4_B08_LATE_OWN = {
    "zelle": HOLDER_NAME, "ccd": HOLDER_NAME, "rbc_funds": R3_B10_OWN_ACCOUNT, "wf_designation": R3_B10_OWN_ACCOUNT,
}


@pytest.mark.parametrize("layout", list(R4_B08_LATE_OWN))
@pytest.mark.parametrize(("holder", "own"), R4_B08_LATE_ABBREVIATED)
def test_r4_b08_late_the_holder_s_abbreviated_noise_lead_stays_its_own(holder, own, layout):
    rows, bank, zelle_row = _r4_b08_late_layouts(own, "SAMPLE RECEIVER")[layout]
    _r4_b08_late_in_both(rows, bank, zelle_row, R4_B08_LATE_OWN[layout], holder_name=holder)


@pytest.mark.parametrize(("holder", "own"), R4_B08_LATE_ABBREVIATED[0:6:2])
def test_r4_b08_late_the_holder_s_abbreviated_e_transfer_stays_held(holder, own):
    # The e-Transfer sender reading drops AUTO (read as no name word), so the AUTO names are not cases here.
    rows = [(f"E-TRANSFER RECEIVED {own} CA0000000000", 812.40)]
    _r4_b08_late_in_both(rows, "Royal Bank of Canada", False, HOLDER_NAME, holder_name=holder)


@pytest.mark.parametrize(("payer", "holder"), [
    # A third party whose lead is no abbreviation of the holder's noise lead stays a customer (R4-30's release).
    ("ROYAL YACHT SERVICE", "NATIONAL YACHT SERVICE LLC"),
    ("NORTHWIND YACHT SERVICE", "NATIONAL YACHT SERVICE LLC"),
    ("NAPA YACHT SERVICE", "NATIONAL YACHT SERVICE LLC"),
    ("CONTOSO AUTO REPAIR", "AMERICAN AUTO REPAIR INC"),
    ("FABRIKAM ROOFING SUPPLY", "COMMERCIAL ROOFING SUPPLY INC"),
])
def test_r4_b08_late_a_third_party_s_own_lead_is_no_abbreviation(payer, holder):
    rows, bank, zelle_row = _r4_b08_late_layouts(payer, "SAMPLE RECEIVER")["zelle"]
    _r4_b08_late_in_both(rows, bank, zelle_row, P2P, holder_name=holder)


@pytest.mark.parametrize(("holder", "own"), [
    ("PREMIUM CONTOSO INC", "CONTOSO INC"),
    ("ADVANTAGE CONTOSO LLC", "CONTOSO LLC"),
    ("ELITE CONTOSO LLC", "CONTOSO"),
    ("ELITE ROOFING LLC", "ROOFING"),
])
@pytest.mark.parametrize("field", ["holder_name", "account_name"])
def test_r4_b08_late_a_noise_led_one_word_holder_s_own_word_alone_stays_held(holder, own, field):
    rows, bank, zelle_row = _r4_b08_late_layouts(own, "SAMPLE RECEIVER")["ccd"]
    _r4_b08_late_in_both(rows, bank, zelle_row, HOLDER_NAME, **{field: holder})


def test_r4_b08_late_the_readers():
    assert tc._lead_abbreviation("NATL", "NATIONAL") and tc._lead_abbreviation("COMML", "COMMERCIAL")
    assert tc._lead_abbreviation("SLCT", "SELECT") and tc._lead_abbreviation("AM", "AMERICAN")
    for word, lead in (("NATIONAL", "NATIONAL"), ("NORTHWIND", "NATIONAL"), ("ROYAL", "NATIONAL"),
                       ("N", "NATIONAL"), ("NAPA", "NATIONAL")):
        assert not tc._lead_abbreviation(word, lead), word
    # Only a name-like noise lead is read through its abbreviation: a name-starter's or a word's is printed whole.
    assert tc._prints_printed_lead(["NATL", "YACHT"], "NATIONAL")
    assert not tc._prints_printed_lead(["GLDN", "YACHT"], "GOLDEN")
    assert tc._prints_printed_lead(["GOLDEN", "YACHT"], "GOLDEN")


# --- Audit round 4, batch R4-B12 ---
# R4-26 (standard B7: the holder's own name is excluded; fail closed: when the settlement word is the holder's own name
# word, nothing on the row shows a processor paid it; standard A1 still counts a processor's settlement under the
# merchant's name): a settlement word that any of the holder's names prints (either trade-name side, any spelling of its
# family: SETTLEMENT, NET SETTLE, MERCHANT, BANKCARD, NETSWEEP, FINTECHEFT) is never read as a settlement for that
# holder, whatever form its name prints, so its own push stays held as holder_name, in both Zelle readings and with the
# name as holder_name or account_name; a settlement of another family printed beside its name is still a settlement.
# Fabricated rows only.

def _r4_b12_both(rows, expected, **kwargs):
    """The credits' final reading in both Zelle readings (no Zelle row here)."""
    for zelle in (True, False):
        assert _final_in(rows, zelle, **kwargs) == expected, zelle


#: (holder, rows): the holder's own push printing its own settlement word; the amounts uneven.
R4_26_SETTLEMENT_HOLDERS = [
    ("NORTHWIND SETTLEMENT SERVICES",
     ["{ach} NORTHWIND SETTLEMENT REF 0000", "{ach} NORTHWIND SETTLEMENT REF 0000",
      "{ach} NORTHWIND SETTLEMENT SVCS REF 0000", "{ach} NORTHWIND SETTLEMENT SVCS REF 0000"]),
    ("CONTOSO HAULING LLC DBA NORTHWIND SETTLEMENT SERVICES",
     ["{ach} NORTHWIND SETTLEMENT REF 0000", "{ach} NORTHWIND SETTLEMENT REF 0000",
      "{ach} NORTHWIND SETTLEMENT SVCS REF 0000", "{ach} NORTHWIND SETTLEMENT SVCS REF 0000",
      "{ach} NORTHWIND SETTLEMENT SERV REF 0000"]),
    ("ACE SETTLEMENT SERVICES", ["{ach} ACE SETTLEMENT S PAYMENT 0000"]),
    ("SETTLEMENT SERVICES LLC", ["{ach} SETTLEMENT SERV REF 0000"]),
    ("NORTHWIND STLMT SERVICES", ["{ach} NORTHWIND STLMT REF 0000"]),
    ("CONTOSO HAULING LLC DBA THE SETTLEMENT TAPHOUSE AND GRILL", ["{ach} THE SETTLEMENT TAP PAYMENT 0000"]),
]
R4_26_BANKS = [("Fifth Third", "ACH CREDIT"), ("Huntington", "ACH DEPOSIT")]
R4_26_AMOUNTS = (1210.40, 1387.15, 990.75, 1105.60, 1312.20)


def _r4_26_rows(templates, ach, repeat=1):
    texts = [template.format(ach=ach) for template in templates] * repeat
    return [(text, R4_26_AMOUNTS[index % len(R4_26_AMOUNTS)] + index) for index, text in enumerate(texts)]


@pytest.mark.parametrize("field", ["holder_name", "account_name"])
@pytest.mark.parametrize(("bank", "ach"), R4_26_BANKS)
@pytest.mark.parametrize(("holder", "templates"), R4_26_SETTLEMENT_HOLDERS)
def test_r4_26_a_holder_named_for_settlement_keeps_its_own_push_held(holder, templates, bank, ach, field):
    rows = _r4_26_rows(templates, ach)
    _r4_b12_both(rows, [HOLDER_NAME] * len(rows), bank=bank, **{field: holder})


#: (holder, row, repeats): the holder's own push printing its own MERCHANT or BANKCARD word, verified by repetition
#: before (named_payer_repeats).
R4_26_MERCHANT_HOLDERS = [
    ("CONTOSO HAULING LLC DBA NORTHWIND MERCHANT SERVICES", "{ach} NORTHWIND MERCHANT REF 0000", 3),
    ("NORTHWIND MERCHANT SERVICES", "{ach} NORTHWIND MERCHANT REF 0000", 3),
    ("CONTOSO HAULING LLC DBA NORTHWIND BANKCARD SERVICES", "{ach} NORTHWIND BANKCARD REF 0000", 2),
    ("CONTOSO HAULING LLC DBA THE MERCHANT TAVERN AND GRILL", "{ach} THE MERCHANT TAV PAYMENT 0000", 2),
]


@pytest.mark.parametrize("field", ["holder_name", "account_name"])
@pytest.mark.parametrize(("bank", "ach"), R4_26_BANKS)
@pytest.mark.parametrize(("holder", "template", "repeats"), R4_26_MERCHANT_HOLDERS)
def test_r4_26_a_holder_named_for_a_processor_s_word_never_verifies_its_own_push(
    holder, template, repeats, bank, ach, field,
):
    rows = _r4_26_rows([template], ach, repeats)
    if bank == "Huntington" and "BANKCARD" in template:
        # Recorded residual (not this pass's reading): the classifier's card-settlement rule verifies Huntington's
        # 'ACH DEPOSIT <name> BANKCARD' before pass 7 reads the holder (operating_income_descriptor), as before.
        _r4_b12_both(rows, [NET_SETTLE] * repeats, bank=bank, **{field: holder})
        return
    _r4_b12_both(rows, [HOLDER_NAME] * repeats, bank=bank, **{field: holder})


def test_r4_26_a_settlement_of_another_family_beside_the_holder_s_name_is_still_a_settlement():
    bankcard = _revenue("BANKCARD DEPOSIT 000000 000000000000000 NORTHWIND MERCHANT SERV")
    assert tr.merchant_settlement(bankcard, ("NORTHWIND MERCHANT SERVICES LLC",))
    netsweep = _revenue(CHASE_ACH.format(orig="NORTHWIND MERCHANT SERV", entry="NETSWEEP ",
                                         receiver="NORTHWIND MERCHANT SERVICES LLC"))
    assert tr.merchant_settlement(netsweep, ("NORTHWIND MERCHANT SERVICES LLC",))
    net_settle = _revenue(CHASE_ACH.format(orig="NORTHWIND SETTLEMENT SERV", entry="NET SETLMT ",
                                           receiver="NORTHWIND SETTLEMENT SERVICES"))
    assert tr.merchant_settlement(net_settle, ("NORTHWIND SETTLEMENT SERVICES",))
    # MERCHANDISE is no family word: the MERCH deposit form is still a settlement under the holder's name.
    merch = _revenue("MERCH DEP 0000000000 NORTHWIND MERCHANDISE")
    assert tr.merchant_settlement(merch, ("NORTHWIND MERCHANDISE LLC",))
    assert tr._holder_settlement_families(("NORTHWIND MERCHANDISE LLC",)) == frozenset()


@pytest.mark.parametrize(("holder", "text"), [
    # The same shape with no settlement word, and a usable form-less name that builds its runs: held, as before.
    ("NORTHWIND SAMPLING SERVICES", "ACH CREDIT NORTHWIND SAMPLING REF 0000"),
    ("NORTHWIND SETTLEMENT AGENCY", "ACH CREDIT NORTHWIND SETTLEMENT REF 0000"),
])
def test_r4_26_the_controls_stay_held(holder, text):
    rows = [(text, 1210.40), (text, 1387.15)]
    _r4_b12_both(rows, [HOLDER_NAME] * 2, bank="Fifth Third", holder_name=holder)


def test_r4_26_the_settlement_families():
    assert tr._holder_settlement_families(("CONTOSO HAULING LLC DBA NORTHWIND MERCHANT SERVICES",)) == {"MERCHANT"}
    assert tr._holder_settlement_families(("NORTHWIND STLMT SERVICES", "SAMPLE BNKCRD LLC")) == {
        "SETTLEMENT", "BANKCARD"}
    assert tr._holder_settlement_families(("CONTOSO MERCH LLC",)) == {"MERCHANT"}
    assert tr._holder_settlement_families(("CONTOSO HAULING LLC",)) == frozenset()
    assert tr._holder_settlement_families(()) == frozenset()
    for matched, family in (("SETTLEMENT", "SETTLEMENT"), ("SETTLMT", "SETTLEMENT"), ("STLMT", "SETTLEMENT"),
                            ("NET SETTLE", "NET SETTLE"), ("NET SETL", "NET SETTLE"), ("NET STLMT", "NET SETTLE"),
                            ("MERCH", "MERCHANT"), ("MERCHPAYOUT", "MERCHANT"), ("MRCHNTSRVS", "MERCHANT"),
                            ("BANKCARDSEC", "BANKCARD"), ("BKCRD", "BANKCARD"), ("NETSWEEP", "NETSWEEP"),
                            ("FINTECHEFT", "FINTECHEFT")):
        assert tr._settlement_family(matched) == family, matched
    text = _revenue("ACH CREDIT NORTHWIND MERCHANT REF 0000")
    assert not tr.merchant_settlement(text, ("NORTHWIND MERCHANT SERVICES",))
    assert tr.merchant_settlement(text, ())


# R4-27 (standard A1: processor settlements count; B1 excludes own-account transfers on the credit side only; §4.6
# item 5: an outflow to the holder's own account is a flag, not a revenue change; R3-90 A's own reading: counted, never
# verified): the holder's transfer to its own account (a circular debit printing the holder's whole name before an
# account designation, a masked number, a reference or the end) never holds a settlement, payout or platform credit
# under the merchant's own name, at any amount; a transfer to an affiliate sharing only the holder's first word or
# first two words still does, and every other credit reads as before. Fabricated rows only.

R4_27_OWN_TRANSFER = "ONLINE TRANSFER TO CONTOSO DESIGN INC BUSINESS CHECKING XXXXXX0000 REF IB0000000 ON 05 02 54"
R4_27_AFFILIATE = "ONLINE TRANSFER TO CONTOSO SOLUTIONS LLC REF IB0000000 ON 05 02 54"
R4_27_STUDIO = "ONLINE TRANSFER TO CONTOSO DESIGN STUDIO LLC BUSINESS CHECKING XXXXXX0000"
R4_27_BANKCARD = "CONTOSO DESI BANKCARD 540115 000000000000000 NORTHWIND PRESS SAMPLEVI"


def _r4_27_tiers(rows, days, zelle=True):
    """The credits' final readings, each row posted on its own day of March 2054 (`days`)."""
    statement = Statement(holder_name=R3_90_WELLS_HOLDER, bank="Wells Fargo", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for (text, amount), day in zip(rows, days)
    ])
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in classify_statement_transactions(statement, zelle_true_revenue=zelle) if record.amount > 0]


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize(("amount", "days"), [(-900.0, (2, 3)), (-1500.0, (2, 2))])
def test_r4_27_the_holder_s_own_account_transfer_never_holds_its_settlement(amount, days, zelle):
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (R4_27_OWN_TRANSFER, amount)]
    assert _r4_27_tiers(rows, days, zelle) == [R3_90_REFUSED]


@pytest.mark.parametrize("zelle", [True, False])
def test_r4_27_the_bankcard_twin_reads_as_without_the_own_transfer(zelle):
    alone = _r4_27_tiers([(R4_27_BANKCARD, 1500.0)], (2,), zelle)
    assert alone[0][0] == "counted_flagged"
    assert _r4_27_tiers([(R4_27_BANKCARD, 1500.0), (R4_27_OWN_TRANSFER, -900.0)], (2, 3), zelle) == alone


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize(("debit", "amount"), [(R4_27_AFFILIATE, -76.40), (R4_27_STUDIO, -900.0)])
def test_r4_27_a_transfer_to_an_affiliate_still_holds_the_settlement(debit, amount, zelle):
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (debit, amount)]
    assert _r4_27_tiers(rows, (2, 3), zelle) == [("excluded_pending_review", "payer_also_debited")]
    # Beside the own-account transfer too, the affiliate's transfer holds it.
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (R4_27_OWN_TRANSFER, -1500.0), (debit, amount)]
    assert _r4_27_tiers(rows, (2, 2, 3), zelle) == [("excluded_pending_review", "payer_also_debited")]


def test_r4_27_a_third_party_paid_back_by_transfer_stays_held():
    credit = "FABRIKAM SUPPLY LLC DES:PAYMENT ID:0001 INDN:CONTOSO DESIGN INC CO ID:0000000001 CCD"
    debit = "ONLINE TRANSFER TO FABRIKAM SUPPLY LLC BUSINESS CHECKING XXXXXX0000 REF IB0000000"
    statement = {"holder_name": R3_90_WELLS_HOLDER, "bank": "Bank of America"}
    assert _tiers([(credit, 1500.0), (debit, -900.0)], **statement) == [
        ("excluded_pending_review", "payer_also_debited")]


# R4-B12 review round 1 (finding 3; R4-27; §8.1's stated purpose, "an own account, an affiliate"): the holder's name is
# its own account only as the transfer's payee (after TO, or at the start of the text) and before an account
# designation, an X-masked number, a reference or the end, so a transfer FROM the holder's own account TO an affiliate,
# and a transfer to an affiliate named with the holder's words and a number, still hold the settlement, at any amount.

@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize(("amount", "days"), [(-900.0, (2, 3)), (-1500.0, (2, 2))])
@pytest.mark.parametrize("debit", [
    "ONLINE TRANSFER FROM CONTOSO DESIGN INC CHECKING 0000 TO CONTOSO SOLUTIONS LLC",
    "ONLINE TRANSFER TO CONTOSO DESIGN 360 LLC REF IB0000000",
])
def test_r4_b12_r1_a_transfer_from_the_own_account_or_to_a_numbered_affiliate_still_holds(debit, amount, days, zelle):
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (debit, amount)]
    assert _r4_27_tiers(rows, days, zelle) == [("excluded_pending_review", "payer_also_debited")]


# R4-B12 review round 1 (finding 2; R4-26, standard B7, fail closed; recorded residual): a holder whose own name prints a
# settlement family's word has that family read as no settlement on its rows wherever the word prints, the row's own
# entry field (BofA's DES, Chase's CO ENTRY DESCR) included, so a card settlement printing that family's form under the
# merchant's own name (MERCH DEP under a MERCH or MERCHANT holder) is held as the holder's own push, never verified, in
# both Zelle readings; a holder whose name prints no family word (MERCHANDISE) keeps the verified card settlement.

R4_B12_R1_BOFA_MERCH = "{orig} DES:MERCH DEP ID:000{n} INDN:{receiver} CO ID:0000000001 CCD"


@pytest.mark.parametrize(("holder", "template", "orig", "receiver", "bank", "expected"), [
    pytest.param("CONTOSO MERCH LLC", R4_B12_R1_BOFA_MERCH, "CONTOSO MERCH", "CONTOSO MERCH LLC", "Bank of America",
                 HOLDER_NAME, id="bofa-merch-holder"),
    pytest.param("CONTOSO MERCH LLC", CHASE_ACH, "CONTOSO MERCH", "CONTOSO MERCH", "Chase", HOLDER_NAME,
                 id="chase-merch-holder"),
    pytest.param("NORTHWIND MERCHANT SERVICES LLC", R4_B12_R1_BOFA_MERCH, "NORTHWIND MERCHANT",
                 "NORTHWIND MERCHANT SERVICES LLC", "Bank of America", HOLDER_NAME, id="bofa-merchant-holder"),
    pytest.param("CONTOSO MERCHANDISE LLC", R4_B12_R1_BOFA_MERCH, "CONTOSO MERCHANDISE", "CONTOSO MERCHANDISE LLC",
                 "Bank of America", NET_SETTLE, id="bofa-merchandise-holder"),
])
def test_r4_b12_r1_the_holder_s_own_family_settlement_entry_is_held(holder, template, orig, receiver, bank, expected):
    rows = [(template.format(orig=orig, entry="MERCH DEP ", receiver=receiver, n=index), amount)
            for index, amount in enumerate((1210.40, 1387.15, 990.75))]
    _r4_b12_both(rows, [expected] * 3, bank=bank, holder_name=holder)

