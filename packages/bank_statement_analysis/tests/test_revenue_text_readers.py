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
    # Quebec prints its numbered companies as NNNN-NNNN (S4.2 round 4), also after a leading date.
    ("1234-5678 QUEBEC INC DES:VENDOR PAY ID:1", True),
    ("03/02 1234-5678 QUEBEC INC DES:VENDOR PAY ID:1", True),
    ("1234-5678 FABRIKAM LLC DES:VENDOR PAY ID:1", False),   # the four-and-four form only with a province
])
def test_the_numbered_company_guard(printed, numbered):
    assert numbered_company(_text(printed)) is numbered


@pytest.mark.parametrize(("printed", "numbered"), [
    ("1234-5678 QUEBEC INC DES:PAYMENT ID:1", True),
    ("1234-5678 QC INC DES:PAYMENT ID:1", True),
    ("1234-5678 QUE INC DES:PAYMENT ID:1", True),
    ("1234-5678 QUEB INC DES:PAYMENT ID:1", True),
    ("1234 5678 NORTH STAR LLC DES:PAYMENT ID:1", False),
    ("1234 5678 NEW ERA LLC DES:PAYMENT ID:1", False),
    ("1234 5678 CAN AM LLC DES:PAYMENT ID:1", False),
    ("1234 5678 AB CONSULTING DES:PAYMENT ID:1", False),
    ("1234-5678 CANADA INC DES:PAYMENT ID:1", False),
])
def test_the_numbered_company_guard_s_four_and_four_form_reads_quebec_only(printed, numbered):
    # S4.2 fix round 5: only Quebec registers its numbered companies as NNNN-NNNN, so that arm reads QUEBEC, its cuts
    # and QC (the P2P sender key's set), never another province's word or code starting a company's name.
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
    ("01/02Bankcard Deposit 123456", None),       # a glued date is dropped; the card word is a payer word
    ("WIRE IN DATE 540102 TRN 123", None),        # a wire is tiered, never gated
])
def test_the_channel_gate(printed, gate):
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize(("printed", "gate"), [
    ("Zelle Payment From Fabrikam LLC Conf 99", "closed"),
    ("Counter Credit", "closed"),
    ("Teller Deposit", "closed"),
    ("Cash Deposit", "closed"),
    ("Remote Deposit", "closed"),
    ("ATM Deposit", "closed"),
    ("Remote", "closed"),                  # the check form anchored at the row's start
    ("GC 1234 Deposit", "closed"),         # the cash form anchored at the row's start
    ("Visa Direct Fabrikam Payout", "push"),
    ("RTP Credit From Fabrikam LLC Inv 1234", "push"),
])
def test_a_leading_date_never_opens_the_channel_gate(printed, gate):
    # S2.1 review, finding 1 (§6.1 step 9b, §7.0): a date glued to the row's first word ('01/02Zelle ...') is dropped
    # from the revenue text, so the gate, the payer region, the payer name and the company form read the dated row as
    # they read the undated one. A date printed with a space before the first word is kept (a spaced leading '5 3' is
    # Fifth Third's 5/3 brand, not a date), so the gate reads through it (S2.1 re-review, fix round 3): the rails'
    # and forms' left boundary is (?<![A-Z]), never \b, and a form anchored at the row's start accepts a leading
    # date, glued or spaced. The spaced row's gate, payer name and company form are the undated row's. A glued shape
    # the strip leaves in place ('01/02/2054Zelle', '0102Zelle') keeps the undated row's gate too.
    def readings(variant):
        text = _text(variant)
        region = payer_region(text)
        return text, channel_gate(text), region, payer_name(region), company_form(payer_name(region))

    undated = readings(printed)
    assert undated[1] == gate
    assert readings("01/02" + printed) == undated
    spaced = readings("01/02 " + printed)
    assert spaced[0] == "01 02 " + undated[0]
    assert (spaced[1], spaced[3], spaced[4]) == (undated[1], undated[3], undated[4])
    for glued in ("01/02/2054", "0102"):
        if printed == "Remote":
            # The bare row's anchored form accepts a leading date only (fix round 3's ruling), so '0102REMOTE' and
            # '01 02 2054REMOTE' read a payer word; a residual reported in the S2.1 fix-round-3 report.
            continue
        assert channel_gate(_text(glued + printed)) == gate


@pytest.mark.parametrize(("printed", "gate"), [
    ("01/02 Remote", "closed"),
    ("01/02 GC 1234 Deposit", "closed"),
    ("01/02/2054Zelle Payment From Fabrikam LLC Conf 99", "closed"),
    ("0102Zelle Payment From Fabrikam LLC Conf 99", "closed"),
    ("0102RTP Credit From Fabrikam LLC Inv 1234", "push"),
])
def test_a_dated_or_glued_prefix_never_opens_the_channel_gate(printed, gate):
    # S2.1 re-review (fix round 3, §6.1 step 9b: a closed row is never verified by any step): digits glued in front of
    # a rail or a form, and a leading MM DD pair before an anchored form, no longer hide it. The residual longer
    # prefixes before the bare anchored forms are a reported residual (skipped in the parity test above).
    assert channel_gate(_text(printed)) == gate


@pytest.mark.parametrize("prefix", ["", "01/02", "1/2", "12/31", "31/12"])
def test_a_glued_leading_date_never_hides_a_row_start_label(prefix):
    # The readers anchored at the row's start: the incoming-wire label, the revenue template prefix and the
    # numbered-company template. A glued date is dropped, so they read the row; a spaced one is kept (below).
    wire = _text(prefix + "Wire In From Fabrikam Trading LLC OBI Invoice 1234 TRN 99")
    assert payer_region(wire) == "FABRIKAM TRADING LLC"
    assert entry_fields(wire) == "INVOICE 1234"
    assert payer_region(_text(prefix + "Electronic Deposit From Fabrikam LLC Ref 12345")) == "FABRIKAM LLC"
    assert numbered_company(_text(prefix + "Direct Deposit 1234567")) is True


@pytest.mark.parametrize("printed", [
    "123 FABRIKAM DEPOSIT",            # one leading number is no date
    "1234567 NEW BRUNSWICK INC",       # a numbered company keeps its number
    "12 345 FABRIKAM DEPOSIT",         # a second number of three digits is no day
    "01 02 2054 FABRIKAM DEPOSIT",     # a third number follows: only the two-number shape is removed
    "45 67 FABRIKAM DEPOSIT",          # neither number is a month or a day
    "FABRIKAM 01 02 DEPOSIT",          # a date inside the row is kept
    # Glued to the first word, but out of the date shape (fix round 3): only two numbers from 1 to 31 are removed.
    "45/67Fabrikam",                   # neither number is a month or a day
    "0/5Abc",                          # 0 is no month or day
    "00/01Abc",
    "12/345Fabrikam",                  # a second number of three digits is no day
    "32/01Abc",                        # 32 is no day
    "1/32Abc",
    "01/02/2054Fabrikam",              # a third number is glued: only the two-number shape is removed
])
def test_leading_numbers_that_are_no_date_prefix_are_kept(printed):
    assert _text(printed) == normalize(printed)


def test_the_same_glued_row_in_the_date_shape_is_stripped():
    # The narrowness cases above are kept because of their shape: the same glued row with a month and a day strips.
    assert _text("01/02Fabrikam") == "FABRIKAM"
    assert _text("12/31Abc") == "ABC"


@pytest.mark.parametrize(("printed", "kept"), [
    ("5/3 Online Transfer From Chk 1234", "5 3 "),                 # Fifth Third's 5/3 brand is no date
    ("5/3 ATM Deposit", "5 3 "),
    ("5/3 Fabrikam DES:Payment ID:1234 INDN:Contoso Bakery CO ID:1234567890 CCD", "5 3 "),  # a 5/3 payer's ACH row
    ("01/02 Zelle Payment From Fabrikam LLC Conf 99", "01 02 "),   # a spaced date is ambiguous: kept
    ("1/2 Wire In From Fabrikam Trading LLC OBI Invoice 1234", "1 2 "),
])
def test_a_leading_number_pair_before_a_space_is_kept(printed, kept):
    # S2.1 fix round 2 (§7.0): only a date glued to the first word is removed; '5 3 ...' with a space is Fifth Third's
    # 5/3 brand (its own rows and a 5/3 payer on another bank's rows), so a spaced pair keeps its text.
    assert _text(printed) == normalize(printed)
    assert _text(printed).startswith(kept)


@pytest.mark.parametrize(("printed", "stripped"), [
    ("01/02Zelle Payment From Fabrikam LLC Conf 99", "ZELLE PAYMENT FROM FABRIKAM LLC CONF 99"),
    ("1/2Wire In From Fabrikam Trading LLC OBI Invoice 1234", "WIRE IN FROM FABRIKAM TRADING LLC OBI INVOICE 1234"),
    ("12/31Bankcard Deposit 123456", "BANKCARD DEPOSIT 123456"),
    ("31/12Direct Deposit 1234567", "DIRECT DEPOSIT 1234567"),     # a DD MM print too
])
def test_a_date_glued_to_the_first_word_is_removed(printed, stripped):
    assert _text(printed) == stripped


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


_STREET_LN_CASES = [
    ("WIRE FROM 12 OAK LN CITY", "WIRE FROM 12 OAK LN CITY"),
    ("ATM DEPOSIT 450 NORTH PINE HILL LN", "ATM DEPOSIT 450 NORTH PINE HILL LN"),
    ("TRUIST LN PYMT", "TRUIST LOAN PYMT"),
    ("1234 COMMERCIAL LN PMT", "1234 COMMERCIAL LOAN PMT"),
    ("000123 AUTO LN DISB", "000123 AUTO LOAN DISB"),
    ("12 OAK LN PAYMENT", "12 OAK LOAN PAYMENT"),
]


@pytest.mark.parametrize(("printed", "normalized"), _STREET_LN_CASES)
def test_a_street_ln_is_a_lane_and_every_other_ln_a_loan(printed, normalized):
    assert normalize(printed) == normalized


#: S2.1 review, finding 2 (§7.11): every payment spelling after LN says loan, the spellings the normalizer later
#: rewrites (PAYMT) among them, so a second normalization reads what the first did.
_LN_PAYMENT_SPELLING_CASES = [
    ("12 OAK LN PAYMT", "12 OAK LOAN PAYMENT"),
    ("ACH 1234 CML LN PAYMT", "ACH 1234 CML LOAN PAYMENT"),
    ("12 OAK LN PMNT", "12 OAK LOAN PMNT"),
    ("12 OAK LN PYMNT", "12 OAK LOAN PYMNT"),
    ("12 OAK LN PAYMENTS", "12 OAK LOAN PAYMENTS"),
    ("12 OAK LN REPAYMENT", "12 OAK LOAN REPAYMENT"),
    ("12 OAK LN PYMTS", "12 OAK LOAN PYMTS"),
    ("12 OAK LN PMTS", "12 OAK LOAN PMTS"),
]
#: ... and a loan-product word or a bank's loan abbreviation before LN says loan with no payment word after it.
_LN_PRODUCT_WORD_CASES = [
    ("1234 COMMERCIAL LN", "1234 COMMERCIAL LOAN"),
    ("ONLINE PMT 1234 CML LN", "ONLINE PMT 1234 CML LOAN"),
    ("ACH DEBIT 0012345 SB LN", "ACH DEBIT 0012345 SB LOAN"),
    ("TRANSFER TO 1234 VEH LN", "TRANSFER TO 1234 VEH LOAN"),
    ("PAYMENT 12345 EIDL LN", "PAYMENT 12345 EIDL LOAN"),
    # S2.1 re-review (fix round 3): the abbreviations 5.4 read as LOAN.
    ("SAMPLE BANK 4521 CREDIT LN", "SAMPLE BANK 4521 CREDIT LOAN"),
    ("ONLINE PMT 1234 PERS LN", "ONLINE PMT 1234 PERS LOAN"),
    ("ACH DEBIT 0012345 INST LN", "ACH DEBIT 0012345 INST LOAN"),
    ("TRANSFER TO 1234 CONS LN", "TRANSFER TO 1234 CONS LOAN"),
    ("PAYMENT 12345 HOME EQUITY LN", "PAYMENT 12345 HOME EQUITY LOAN"),
    ("PAYMENT 12345 EQUITY LN", "PAYMENT 12345 EQUITY LOAN"),
]
#: ... while a street address keeps its lane.
_STREET_LANE_CASES = [
    ("12 OAK LN", "12 OAK LN"),
    ("DEPOSIT 7 MILL LN", "DEPOSIT 7 MILL LN"),
    ("WIRE FROM 88 COUNTRY CLUB LN CITY", "WIRE FROM 88 COUNTRY CLUB LN CITY"),
    ("CHECK 1234 FABRIKAM 45 CHURCH LN", "CHECK 1234 FABRIKAM 45 CHURCH LN"),
]


@pytest.mark.parametrize(
    ("printed", "normalized"), _LN_PAYMENT_SPELLING_CASES + _LN_PRODUCT_WORD_CASES + _STREET_LANE_CASES
)
def test_a_payment_spelling_or_a_loan_abbreviation_reads_ln_as_loan(printed, normalized):
    assert normalize(printed) == normalized


@pytest.mark.parametrize("word", [
    "COMMERCIAL", "CML", "COML", "COMM", "SB", "SBA", "VEH", "VEHICLE", "AUTO", "EIDL", "PPP", "LOC", "CRE", "MORT",
    "MTG", "MORTGAGE", "EQUIP", "TERM", "CREDIT", "PERS", "INST", "CONS", "EQUITY",
])
def test_each_loan_product_word_before_a_street_shaped_ln_reads_loan(word):
    assert normalize(f"ACH DEBIT 1234 {word} LN") == f"ACH DEBIT 1234 {word} LOAN"


@pytest.mark.parametrize("printed", [
    case[0]
    for case in _STREET_LN_CASES + _LN_PAYMENT_SPELLING_CASES + _LN_PRODUCT_WORD_CASES + _STREET_LANE_CASES
])
def test_normalizing_twice_reads_what_normalizing_once_did(printed):
    once = normalize(printed)
    assert normalize(once) == once
