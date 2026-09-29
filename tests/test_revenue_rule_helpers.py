"""Classification 5.5 (true revenue spec §7.0 to §7.11): the family helpers the credit decision and the statement
passes call, read on one fabricated row each: the operating-source reader and its vetoes, the card-settlement forms,
payout context, the reversal and card-credit release rules, book and funds transfers, the glued claim entry, the
payer guards, accounts-payable remittance, public payers, invoice wires and their vetoes, and the cut financing
originator. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.description_text import normalize_transaction_description as normalize


def _text(printed: str) -> str:
    return tc.revenue_text(normalize(printed))


def _region(printed: str) -> str:
    return tc.payer_region(_text(printed))


@pytest.mark.parametrize(("printed", "entity", "form"), [
    ("SPOTON VIA ASTRA DES:SETTLEMENT ID:1", "SpotOn", False),
    ("FIRST DATA MERCH DES:SETTLEMENT ID:1", "Fiserv", False),           # the sixteen-character cut
    ("FBO WHATNOT DES:PAYOUT ID:1", "Whatnot", True),                    # a payout form
    ("MANHEIM US DES:ACH PAYMNT ID:1", "Manheim", False),                # an auction, on its originator segment
])
def test_the_operating_source_reader_names_the_source(printed, entity, form):
    found = tc._operating_source(_text(printed))
    assert found is not None and found.entity == entity
    assert found.payout_form is form


@pytest.mark.parametrize("printed", [
    "WHATNOT INC DES:PAYROLL ID:1",          # a pay word on a platform read
    "WHATNOT INC DES:LOAN ID:1",             # a financing word
    "ZELLE PAYMENT FROM WHATNOT INC",        # a person-to-person rail
    "TIKTOK INC DES:DIR DEP ID:1",           # an employer-type alias with DIR DEP
    "SUPER DISPATCH DES:CASHOUT ID:1",       # a transport marketplace's wallet word
    "SAMPLE AUTO MANHEIM FEES",              # an auction name off the originator segment
])
def test_a_vetoed_or_misplaced_read_names_no_source(printed):
    assert tc._operating_source(_text(printed)) is None


def test_a_cut_read_carries_its_alias_vetoes():
    # §7.0, S1.1 review: the cut 'RTP CREDIT AMAZO' reads as its alias 'RTP CREDIT AMAZON COM', vetoes included.
    assert tc._operating_source(_text("RTP CREDIT AMAZO DES:PAYROLL ID:1")) is None
    assert tc._operating_source(_text("RTP CREDIT AMAZO ID:1")).entity == "Amazon Marketplace"


@pytest.mark.parametrize(("printed", "label"), [
    ("MERCHANT BANKCD DES:DEPOSIT ID:123456 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD", "bankcard"),
    ("FABRIKAM MERCH DEP 1234567", "merch_dep"),
    ("VSA DEP12345678", "brand_dep"),
    ("MISC PAYMENT 1234567 VISA GBL VI 1234", "gbl_brand"),
    ("FABRIKAM SUPPLY DES:NET SETTLE ID:1", "net_settle"),
    ("REGLEMENT MARCHAND 1234", "french_card_settlement"),
])
def test_the_card_settlement_forms(printed, label):
    form = tc._card_settlement_form(_text(printed), bank=None)
    assert form is not None and form.label == label


@pytest.mark.parametrize("printed", [
    "FABRIKAM BANKCARD LLC DES:DEPOSIT ID:1",     # a company named BANKCARD
    "BANKCARD DEP CB REV",                        # the card veto: a chargeback reversal
    "FABRIKAM LAW GROUP DES:NET SETTLE ID:1",     # NET SETTLE from a law firm
    "INTUIT 12345678 DES:TAX RFND ID:1",          # Intuit's refund
    "CAPITAL ONE CREDIT CARD DEPOSIT 1234",       # the generic card words beside a card issuer
])
def test_a_refused_card_form_is_none(printed):
    assert tc._card_settlement_form(_text(printed), bank=None) is None


def test_the_square_checking_form_reads_only_on_a_square_statement():
    assert tc._card_settlement_form(_text("CARD PAYMENT SALES"), bank="Square").label == "square_checking_sales"
    assert tc._card_settlement_form(_text("CARD PAYMENT SALES"), bank="Sample Bank") is None


@pytest.mark.parametrize(("printed", "context"), [
    ("SQUARE INC DES:SQ540115 ID:1", True),               # a Square payout id
    ("STRIPE DES:TRANSFER ID:ST-A1B2C3D4E5F6", True),      # Stripe's payout id
    ("SQUARE INC DES:CHARGEBACK SQ540115 ID:1", False),    # the card veto
    ("VAGARO DES:DEPOSIT ID:1", True),                     # the entity's own context word
])
def test_the_payout_context(printed, context):
    text = _text(printed)
    assert tc._has_operating_context(text, tc._operating_source(text), bank=None) is context


@pytest.mark.parametrize(("printed", "reversal"), [
    ("ACH RETURN R01 FABRIKAM", True),
    ("FABRIKAM DES:REVERSAL ID:1", True),
    ("MEDICAID DES:REIMBURSEMENT ID:1", False),            # REIMBURSEMENT with a claim signal
    ("DEBIT CARD CREDIT VISA DIRECT FABRIKAM PAYOUT", False),  # a push payout printed as a card credit
    ("DEBIT CARD CREDIT FABRIKAM STORE", True),            # a card refund
])
def test_the_reversal_rule_and_the_card_credit_release(printed, reversal):
    assert tc._reversal_credit(_text(printed)) is reversal


@pytest.mark.parametrize(("printed", "own"), [
    ("BOOK TRANSFER CREDIT B/O: FABRIKAM EXPORTS LLC SAMPLEVILLE", False),   # a third-party originator
    ("BOOK TRANSFER CREDIT B/O: CONTOSO TRADING LLC SAMPLEVILLE", True),      # the holder
    ("FUNDS TRANSFER FROM 1234", True),                                        # no originator name
    ("ELECTRONIC FUNDS TRANSFER DEPOSIT FABRIKAM", False),                     # the EFT channel
])
def test_a_book_or_funds_transfer_is_own_account_only_without_a_third_party(printed, own):
    assert tc._own_book_or_funds_transfer(_text(printed), "CONTOSO TRADING LLC") is own


def test_a_glued_claim_entry_is_split_for_the_lookups():
    assert tc._split_glued_claim("FABRIKAM HEALTH PLHCCLAIMPMT") == "FABRIKAM HEALTH PL HCCLAIMPMT"


def test_the_payer_guards():
    text = _text("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(text, tc.payer_region(text), "CONTOSO BAKERY LLC") == "holder"
    numbered = _text("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(numbered, tc.payer_region(numbered), "SAMPLE CAFE LLC") == "numbered"
    clean = _text("FABRIKAM SUPPLY DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(clean, tc.payer_region(clean), "SAMPLE CAFE LLC") is None


@pytest.mark.parametrize(("printed", "remittance"), [
    ("FABRIKAM SUPPLY DES:ACCTS PAYABLE ID:1", True),
    ("FABRIKAM SUPPLY ACH PMT INV 1234", True),
    ("FABRIKAM SUPPLY BILL COM INV 1234", True),
    ("BILL COM DES:PAYABLES ID:1", False),                   # Bill.com's own PAYABLES
    ("FABRIKAM INSURANCE DES:VENDOR PAY ID:1", False),       # the veto
    ("DEPOSIT INV 1234", False),                             # no payment-channel word
])
def test_the_payer_remittance(printed, remittance):
    text = _text(printed)
    assert tc._payer_remittance(text, tc.payer_region(text), "SAMPLE CAFE LLC") is remittance


@pytest.mark.parametrize(("printed", "rule"), [
    ("TREAS 310 DES:DOD MISC ID:1 CCD", "treasury_vendor_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("STATE OF OHIO DES:VENDOR PAY GRANT ID:1", None),
    ("FABRIKAM PLUMBING DES:VENDOR PAY ID:1 SAMPLE COUNTY", None),
])
def test_the_public_payer_arms(printed, rule):
    assert tc._public_payer_remittance(_text(printed)) == rule


BOFA = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102001234 SEQ:1234/5678 ORIG:{orig} ID:99887766 "
        "SND BK:SAMPLE BANK ID:0123 PMT DET:{purpose}")


@pytest.mark.parametrize(("orig", "purpose", "verifies"), [
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234", True),
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 INVESTMENT", False),   # a non-sale purpose
    ("FABRIKAM CAPITAL LLC", "INVOICE 1234", False),              # a financing root
    ("CONTOSO HOLDINGS LLC", "INVOICE 1234", False),              # the holder's brand word
    ("FABRIKAM EXPORTS LLC", "MONEY ORDER 1234", False),          # not an order number
])
def test_the_invoice_wire(orig, purpose, verifies):
    text = _text(BOFA.format(orig=orig, purpose=purpose))
    assert tc._wire_remittance_purpose(text, tc.payer_region(text), "CONTOSO TRADING LLC") is verifies


@pytest.mark.parametrize(("region", "cut"), [
    ("FABRIKAM MERCHAN", True),         # sixteen characters: a proper prefix of MERCHANT
    ("FABRIKAM MERCHANT", False),       # the whole word is no cut
    ("FABRIKAM CAPITA", True),          # fifteen characters: a proper prefix of CAPITAL
    ("FABRIKAM EXPORTS", False),
])
def test_the_cut_financing_originator(region, cut):
    assert tc._cut_financing_originator(region) is cut


def test_an_alias_read_inside_a_waiting_processor_names_no_source():
    # §7.1, review I4: Stripe's BY STRI cut never reads JOBBER BY STRI while Jobber Payments waits for the ledger.
    assert tc._read_inside_a_waiting_processor(_text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3"), "Stripe", "BY STRI")
    assert tc._operating_source(_text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3")) is None
    assert tc._operating_source(_text("FABRIKAM - BY STRI DES:PAYOUT ID:1")).entity == "Stripe"
    assert tc._operating_source(_text("SHIFT4 PAYMENTS DES:DEPOSIT ID:1")).entity == "Shift4"


def test_the_wire_financing_text_drops_the_sending_and_originating_banks():
    # §7.9: the roots are read after the sending (Santander) and originating (Chase's OGB) bank fields go.
    santander = _text("USD WIRE IN FROM BANCO DE CREDIT ACCT * 1234 CONTOSO SRL REF INV 10421")
    assert "CREDIT" not in tc._wire_financing_text(santander) and "CONTOSO SRL" in tc._wire_financing_text(santander)
    assert tc._wire_originator_run(santander) == "CONTOSOSRL"
    chips = _text("CHIPS CREDIT VIA SAMPLE BANK 0959 B O CONTOSO SUPPLY LLC REF NBNF NORTHWIND LABS LLC "
                  "OGB SAMPLE MERCHANTS BANK N A OBI INVOICE 10421")
    assert "MERCHANTS" not in tc._wire_financing_text(chips)


def test_a_wire_from_a_title_or_escrow_firm_is_vetoed():
    # Review I6 (§8.5's senders): a title or escrow firm's wire carries sale, closing or escrow money.
    text = _text("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 ORIG:CONTOSO TITLE AGENCY LLC ID:1 "
                 "SND BK:SAMPLE BANK ID:1 PMT DET:INVOICE 1042")
    assert tc._wire_vetoed(text, tc.payer_region(text), "NORTHWIND LABS LLC")


@pytest.mark.parametrize(("printed", "vetoed"), [
    ("MANHEIM US DES:ACH PAYMNT NGC ID:1", True), ("MANHEIM US DES:ACH PAYMNT FLOORPLAN ID:1", True),
    ("MANHEIM US DES:ACH PAYMNT ID:1 PPD", True), ("MANHEIM US DES:ACH PAYMNT ID:1", False),
])
def test_the_auction_veto(printed, vetoed):
    # §7.8, §14.1, review C2.
    assert (tc._AUCTION_VETO.search(_text(printed)) is not None) is vetoed


def test_the_counter_debit_skip_words_hold_the_channel_vocabulary():
    words = tc._counter_debit_skip_words()
    assert {"CHECKCARD", "OVERDRAFT", "WITHDRAW", "PURCHASES"} <= words
