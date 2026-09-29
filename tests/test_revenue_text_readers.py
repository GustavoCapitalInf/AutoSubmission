"""Classification 5.5 (true revenue spec §5.2, §6.1 step 9b, §7.0, §7.11): the credit revenue readers. Fabricated rows
only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.transaction_classifier import (
    _joined_text,
    channel_gate,
    company_form,
    entry_fields,
    holder_named,
    holder_words,
    is_round_sum,
    numbered_company,
    payer_name,
    payer_region,
    revenue_text,
)


def _text(printed: str) -> str:
    return revenue_text(normalize(printed))


def test_revenue_text_splits_chase_glued_sec_code_inside_the_entry_field_only():
    glued = normalize("Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD")
    assert revenue_text(glued).endswith("CO ENTRY DESCR HCCLAIMPMT SEC CCD")
    two_words = normalize("Orig CO Name:Fabrikam Orig ID:1 Desc Date: CO Entry Descr:Vhcl Purchsec:CCD Trace#:1")
    assert "CO ENTRY DESCR VHCL PURCH SEC CCD" in revenue_text(two_words)
    # A word that ends in SEC outside the entry field is untouched.
    assert revenue_text(normalize("FABRIKAM INSEC CCD PAYMENT")) == "FABRIKAM INSEC CCD PAYMENT"


def test_the_joined_text_puts_the_originator_and_the_entry_side_by_side():
    assert _joined_text(normalize("MERCHANT BANKCD DES:DEPOSIT ID:123456")) == "MERCHANT BANKCD DEPOSIT ID 123456"
    chase = _text("Orig CO Name:Merchant Bankcd Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Merch Depsec:CCD")
    assert _joined_text(chase) == "ORIG CO NAME MERCHANT BANKCD MERCH DEP SEC CCD"
    no_date = _text("Orig CO Name:Fabrikam Orig ID:1234567890 Desc Date: CO Entry Descr:Payments Sec:CCD")
    assert _joined_text(no_date) == "ORIG CO NAME FABRIKAM PAYMENTS SEC CCD"


@pytest.mark.parametrize(("printed", "region"), [
    # ACH: template prefixes removed, the receiver fields never read, a leading digit token kept.
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:123 INDN:CONTOSO BAKERY CO ID:1234567890 CCD", "FABRIKAM SUPPLY"),
    ("7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1", "7654321 NEW BRUNSWICK INC"),
    ("ELECTRONIC DEPOSIT FROM FABRIKAM LLC REF 12345", "FABRIKAM LLC"),
    ("Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Payment Sec:CCD",
     "FABRIKAM SUPPLY"),
    # A layout with no entry label: the entry words sit in the region.
    ("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "FABRIKAM INC DIR DEP"),
    # A wire: the originator after its label, up to the next wire field.
    ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102 SEQ:1/2 ORIG:FABRIKAM TRADING LLC ID:99 "
     "SND BK:SAMPLE BANK ID:1 PMT DET:INV 1234", "FABRIKAM TRADING LLC"),
    ("FEDWIRE CREDIT VIA: SAMPLE BANK/123 B/O: FABRIKAM TRADING LLC REF: CHASE NYC/CTR/BNF=CONTOSO",
     "FABRIKAM TRADING LLC"),
    # A person-to-person or transfer sender.
    ("ZELLE PAYMENT FROM JOHN SMITH CONF 99", "JOHN SMITH"),
    ("ONLINE TRANSFER FROM SMITH J EVERYDAY CHECKING XXXXXX1234 REF IB0ABCD", "SMITH J EVERYDAY CHECKING"),
    # Check, cash, branch, ATM and bare rows print no payer.
    ("MOBILE DEPOSIT", ""),
    ("COUNTER CREDIT", ""),
    ("DEPOSIT", ""),
])
def test_the_payer_region_is_read_by_channel(printed, region):
    assert payer_region(_text(printed)) == region


def test_the_payer_name_drops_digit_tokens_and_single_letters():
    assert payer_name("7654321 NEW BRUNSWICK INC") == "NEW BRUNSWICK INC"
    assert payer_name("SMITH J EVERYDAY CHECKING") == "SMITH EVERYDAY CHECKING"


@pytest.mark.parametrize(("printed", "entry"), [
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:123 INDN:CONTOSO BAKERY CO ID:1 CCD", "VENDOR PAY"),
    ("Orig CO Name:Fabrikam Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1",
     "HCCLAIMPMT"),
    ("WIRE IN FROM FABRIKAM LLC OBI INVOICE 1234 TRN 99", "INVOICE 1234"),
    ("ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99", "INVOICE PAYMENT"),
])
def test_the_entry_fields(printed, entry):
    assert entry_fields(_text(printed)) == entry


def test_the_holder_words_drop_noise_digits_and_short_words():
    assert holder_words("CONTOSO BAKERY LLC") == ("CONTOSO", "BAKERY")
    assert holder_words("BUSINESS ADVANTAGE FUNDAMENTALS") == ()
    assert holder_words(None) == ()


@pytest.mark.parametrize(("region", "holder", "matches"), [
    ("CONTOSO HOLDINGS LLC", "CONTOSO BAKERY LLC", True),       # the brand-word affiliate
    ("CONTOSO BAKERY LLC", "CONTOSO BAKERY LLC", True),         # the holder itself
    ("FABRIKAM PLUMBING SUPPLY", "SAMPLE PLUMBING LLC", False),  # a supplier sharing a trade word
    ("FIRST FABRIKAM LLC", "FIRST CONTOSO LLC", False),         # a common name-starter is never distinctive
    ("1234567 ONTARIO INC", "1234567 ONTARIO INC", True),       # a numbered company's own number
    ("FABRIKAM LLC", "BUSINESS CHECKING", False),               # a product name holds no holder word
    ("", "CONTOSO BAKERY LLC", False),                          # no payer region, no test
])
def test_the_holder_test(region, holder, matches):
    assert holder_named(region, holder) is matches


@pytest.mark.parametrize(("printed", "numbered"), [
    ("DIRECT DEPOSIT 7654321 CANA AP CC", True),
    ("DIRECT DEPOSIT 1234567", True),
    ("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1", True),
    ("7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1", True),
    ("1234567 ONTA DES:PAYMENT ID:1", True),
    ("1234567 ONTARIOS DES:PAYMENT ID:1", False),
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:1234567", False),
])
def test_the_numbered_company_guard(printed, numbered):
    assert numbered_company(_text(printed)) is numbered


@pytest.mark.parametrize(("name", "form"), [
    ("FABRIKAM SUPPLY LLC", True), ("FABRIKAM SUPPLY L L C", True), ("SAMPLE UNIVERSITY", True),
    ("FABRIKAM SUPPLY CO", False), ("FABRIKAM FAMILY TRUST", False), ("LLC FABRIKAM", False), ("JOHN SMITH", False),
])
def test_the_company_form(name, form):
    assert company_form(name) is form


def test_a_round_sum_is_a_whole_hundred_of_at_least_one_hundred():
    assert is_round_sum(500.0) and is_round_sum(100.0)
    assert not is_round_sum(50.0) and not is_round_sum(150.0) and not is_round_sum(500.01)


@pytest.mark.parametrize(("printed", "gate"), [
    ("ZELLE PAYMENT FROM FABRIKAM LLC CONF 99", "closed"),
    ("INTERAC E-TRANSFER FROM JOHN SMITH", "closed"),
    ("MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234", "closed"),
    ("CUSTOMER DEPOSIT", "closed"),
    ("BRANCH DEPOSIT", "closed"),
    ("DEPOSIT", "closed"),
    ("RTP CREDIT FROM FABRIKAM LLC INV 1234", "push"),
    ("VISA DIRECT FABRIKAM PAYOUT", "push"),
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:1", None),
    ("01/02Bankcard Deposit 123456", None),       # a glued date keeps the card word a payer word
    ("WIRE IN DATE 540102 TRN 123", None),        # a wire is tiered, never gated
])
def test_the_channel_gate(printed, gate):
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize(("printed", "region"), [
    ("CONTOSO BAKERY LLC DES:TRANSFER ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", "CONTOSO BAKERY LLC"),
    ("NORTHWIND BAKERY DES:XFER ID:1", "NORTHWIND BAKERY"),
    ("ORIG CO NAME:CONTOSO BAKERY LLC ORIG ID:1 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:CCD", "CONTOSO BAKERY LLC"),
    ("ONLINE TRANSFER FROM JOHN SMITH CONF 1", "JOHN SMITH"),
    ("VENMO DES:CASHOUT ID:1", ""),
])
def test_a_transfer_worded_ach_row_with_no_sender_reads_its_originator(printed, region):
    # Review C3: with no FROM sender, the ACH originator is the payer, so the holder test and the counter-debit
    # hold read it; a consumer rail's cash-out still prints no sender.
    assert payer_region(_text(printed)) == region


def test_santander_prints_its_sending_bank_before_the_originator():
    # §5.2, §7.9: 'USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>' (review I5's own account).
    printed = "USD WIRE IN FROM SAMPLE BANK EUROPE ACCT * 1234 CONTOSO GROUP SP REF PO 4521"
    assert payer_region(_text(printed)) == "CONTOSO GROUP SP"


@pytest.mark.parametrize(("printed", "gate"), [
    ("DEPOT MARCHAND GLOBAL PAIEMENTS 1234567", None),
    ("DEPOT DIRECT FABRIKAM INC", None),
    ("DEPOT 1234 SUCCURSALE", "closed"),
])
def test_a_merchant_or_direct_deposit_depot_is_no_branch_deposit(printed, gate):
    # Review M3: §7.1's DEPOT MARCHAND form and a direct deposit are electronic.
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize(("printed", "normalized"), [
    ("WIRE FROM 12 OAK LN CITY", "WIRE FROM 12 OAK LN CITY"),
    ("ATM DEPOSIT 450 NORTH PINE HILL LN", "ATM DEPOSIT 450 NORTH PINE HILL LN"),
    ("TRUIST LN PYMT", "TRUIST LOAN PYMT"),
    ("1234 COMMERCIAL LN PMT", "1234 COMMERCIAL LOAN PMT"),
    ("000123 AUTO LN DISB", "000123 AUTO LOAN DISB"),
    ("12 OAK LN PAYMENT", "12 OAK LOAN PAYMENT"),
])
def test_a_street_ln_is_a_lane_and_every_other_ln_a_loan(printed, normalized):
    assert normalize(printed) == normalized
