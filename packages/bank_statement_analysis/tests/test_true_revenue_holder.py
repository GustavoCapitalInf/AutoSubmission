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
from analysis.descriptor import lexical
from analysis import description_text
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
    text = lexical.revenue_text(description_text.normalize_transaction_description(FEDWIRE.format(bnf="NORTHWIND MARINE LLC")))
    region = tc.payer_region(text)
    assert tc.wire_sender_is_beneficiary(text, region)
    other = lexical.revenue_text(description_text.normalize_transaction_description(FEDWIRE.format(bnf="CONTOSO DINER LLC")))
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
    revenue = lexical.revenue_text(description_text.normalize_transaction_description(text))
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
    return lexical.revenue_text(description_text.normalize_transaction_description(text))


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


def test_r3_90_a_later_hold_still_reads_a_settlement_under_the_holder_s_own_name():
    # The exemption lifts the holder hold only: a statement whose holder also pays its own name (a transfer to its own
    # other account) holds the settlement by the counter-debit hold, as every other payer debited by name.
    own_transfer = "ONLINE TRANSFER TO CONTOSO DESIGN INC BUSINESS CHECKING XXXXXX1234 REF IB0ABCDEF ON 05/02/54"
    rows = [(R3_90_WELLS.format(n=5), 1500.0), (own_transfer, -900.0)]
    assert _tiers(rows, holder_name=R3_90_WELLS_HOLDER, bank="Wells Fargo") == [
        ("excluded_pending_review", "payer_also_debited")
    ]


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
    payer = lexical.payer_name(f"FABRIKAM SUPPLY PAYMENT {receiver}")
    assert tc._without_trailing_holder_run(payer, [holder]) == "FABRIKAM SUPPLY PAYMENT"


def test_r3_17_the_dropped_lead_run_skips_a_single_letter():
    assert tc._dropped_lead_run("JB S TRUCKING LLC", ["TRUCKING"]) == ("JB", "TRUCKING")
    assert tc._dropped_lead_run("JB TRUCKING LLC", ["TRUCKING"]) == ("JB", "TRUCKING")


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
    assert tc.payer_region(lexical.revenue_text(description_text.normalize_transaction_description(text))).startswith("1234567 ONTARIO")


def test_r3_15_another_numbered_company_after_the_label_stays_counted():
    assert _tiers([("ACCOUNT PAYABLE PMT 7654321 ONTARIO", 12000.0)], holder_name=NUMBERED_HOLDER,
                  bank="Royal Bank of Canada") == [NUMBERED]


@pytest.mark.parametrize(("text", "region"), [
    ("ACCOUNTS PAYABLE 123456 NORTHWIND SUPPLY INC", "ACCOUNTS PAYABLE NORTHWIND SUPPLY INC"),
    ("ACCOUNTS PAYABLE 123456 NORTH MOUNTAIN PAVING", "ACCOUNTS PAYABLE NORTH MOUNTAIN PAVING"),
])
def test_r3_15_a_word_named_payer_after_the_label_keeps_its_region_and_reading(text, region):
    assert tc.payer_region(lexical.revenue_text(description_text.normalize_transaction_description(text))) == region
    assert _tiers([(text, 12000.0)], holder_name="NORTHWIND BAKERY LTD", bank="Scotiabank") == [REMITTANCE]
