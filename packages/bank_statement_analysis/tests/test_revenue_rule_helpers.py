"""Classification 5.5 (true revenue spec §7.0 to §7.11): the family helpers the credit decision and the statement
passes call, read on one fabricated row each: the operating-source reader and its vetoes, the card-settlement forms,
payout context, the reversal and card-credit release rules, book and funds transfers, the glued claim entry, the
payer guards, accounts-payable remittance, public payers, invoice wires and their vetoes, and the cut financing
originator. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.descriptor import credit_words
from analysis.descriptor import payer
from analysis.descriptor import rails
from analysis.descriptor import lexical
from analysis.descriptor import words as descriptor_words
from analysis import classification_registry
from analysis import payee_matcher
from analysis.classification_registry import PROCESSOR_ADVANCE_PRODUCTS, PROCESSORS_WITHOUT_ADVANCE_PRODUCT
from analysis.description_text import normalize_transaction_description as normalize


def _text(printed: str) -> str:
    return lexical.revenue_text(normalize(printed))


def _region(printed: str) -> str:
    return payer.payer_region(_text(printed))


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


_CHASE_FIELDS = "ORIG ID:1234567890 DESC DATE:310102 CO ENTRY DESCR:VENDOR PAYSEC:CCD TRACE#:1 EED:310102 IND ID:1"


@pytest.mark.parametrize(("printed", "entity"), [
    # Bank of America: the holder's name in INDN never names the source; the originator before DES does.
    ("FABRIKAM SUPPLY DES:VENDOR PAY ID:1 INDN:SQUARE INC CO ID:1 CCD", None),
    ("SQUARE INC DES:VENDOR PAY ID:1 INDN:FABRIKAM SUPPLY CO ID:1 CCD", "Square"),
    # Bank of America prints the processor in its PMT INFO addenda, after INDN and CO ID: it still names the source.
    ("BANKCARD SYS DES:MERCH DEP ID:1234567890 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD "
     "PMT INFO:WORLDPAY MERCH DEP TERM 1234", "Worldpay"),
    # Chase: IND ID and IND NAME, up to TRN.
    (f"ORIG CO NAME:FABRIKAM SUPPLY {_CHASE_FIELDS} IND NAME:SQUARE INC TRN: 1234567890TC", None),
    (f"ORIG CO NAME:SQUARE INC {_CHASE_FIELDS} IND NAME:FABRIKAM SUPPLY TRN: 1234567890TC", "Square"),
    # PNC's RECEIVER NAME, at the row's end.
    ("ACH CREDIT FABRIKAM SUPPLY VENDOR PAY RECEIVER NAME SQUARE INC", None),
    # The ledger gate reads the same text: a waiting processor's bare alias in the holder's name never refuses a read.
    ("FABRIKAM - BY STRI DES:PAYOUT ID:1 INDN:JOBBER BY STRI CO ID:1 CCD", "Stripe"),
])
def test_the_operating_alias_never_reads_a_receiver_value(printed, entity):
    # S2.2 review item C (§5.2): the alias reads the row with each receiver field's value removed, the rest kept.
    found = tc._operating_source(_text(printed))
    assert (found and found.entity) == entity


def test_the_receiver_value_goes_and_the_fields_after_it_stay():
    bofa = rails._without_receiver_value(_text(
        "BANKCARD SYS DES:MERCH DEP ID:1 INDN:FABRIKAM BAKERY CO ID:1 CCD PMT INFO:WORLDPAY MERCH DEP"))
    assert "FABRIKAM" not in bofa and "INDN" not in bofa
    assert bofa.split() == "BANKCARD SYS DES MERCH DEP ID 1 CO ID 1 CCD PMT INFO WORLDPAY MERCH DEP".split()
    chase = rails._without_receiver_value(_text(f"ORIG CO NAME:SQUARE INC {_CHASE_FIELDS} IND NAME:FABRIKAM TRN: 1TC"))
    assert "FABRIKAM" not in chase and "IND" not in chase.split() and chase.split()[-2:] == ["TRN", "1TC"]
    assert rails._without_receiver_value(_text("SQUARE INC DES:TRANSFER ID:1")) == _text("SQUARE INC DES:TRANSFER ID:1")



@pytest.mark.parametrize(("printed", "label"), [
    ("MERCHANT BANKCD DES:DEPOSIT ID:123456 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD", "bankcard"),
    ("ORIG CO NAME:BANKCARD DESC DATE: CO ENTRY DESCR:DEPOSIT", "bankcard"),   # S2.2 review: CO of a field label
    ("BANKCARD DES:DEPOSIT CO ID:1234567890 CCD", "bankcard"),
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
    "CAPITAL ONE CREDIT CARD DEPOSIT 1234",       # the card veto: CAPITAL, a financing word, refuses every form
    "BK OF AMER VISA CREDIT CARD DEPOSIT 1234",   # the generic card words beside a card issuer (no veto word)
    "ALLY CC CREDIT CARD DEPOSIT 1234",           # the same, beside another card issuer
])
def test_a_refused_card_form_is_none(printed):
    assert tc._card_settlement_form(_text(printed), bank=None) is None


def test_the_card_issuer_refusal_is_its_own_branch():
    # §7.1 (structural S53): these rows print no card-veto word, so the card-issuer check alone refuses them; the same
    # words without an issuer read generic_card_sales.
    for printed in ("BK OF AMER VISA CREDIT CARD DEPOSIT 1234", "ALLY CC CREDIT CARD DEPOSIT 1234"):
        assert tc._CARD_VETO.search(lexical._before_receiver(_text(printed))) is None
        assert payee_matcher.registry_match(_text(printed), classification_registry.CARD_ISSUER_CONTEXT_ALIASES) is not None
    assert tc._card_settlement_form(_text("FABRIKAM CREDIT CARD DEPOSIT 1234"), bank=None).label == "generic_card_sales"


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


@pytest.mark.parametrize(("printed", "released"), [
    ("POS CREDIT STRIPE PAYOUT 1234", True),     # a merchant processor with a payout word, no push-rail word
    ("POS CREDIT STRIPE 1234", False),           # the same processor without a payout word: a card refund
])
def test_a_processor_card_credit_with_a_payout_word_is_released(printed, released):
    # §7.11: the second release of _card_credit_released (a merchant-processor or invoice source and a payout word).
    text = _text(printed)
    assert credit_words._CARD_CREDIT_PUSH_WORD.search(text) is None
    assert tc._operating_source(text).source_type == "merchant_processor"
    assert tc._card_credit_released(text) is released
    assert tc._reversal_credit(text) is not released


@pytest.mark.parametrize(("printed", "reversal"), [
    ("FABRIKAM SUPPLY DES:RETN ID:1", True),     # a return code the reversal patterns do not print
    ("FABRIKAM SUPPLY DES:RTNS ID:1", False),    # not a return code: the code is only read as a whole word
])
def test_the_return_codes_decide_a_row_on_their_own(printed, reversal):
    # §7.11: _RETURN_CODE_CREDIT_PATTERNS, on a row no reversal or cancellation pattern reads.
    text = _text(printed)
    assert not rails._matches_any(text, descriptor_words._REVERSAL_CANCELLATION_CREDIT_PATTERNS)
    assert rails._matches_any(text, credit_words._RETURN_CODE_CREDIT_PATTERNS) is reversal
    assert tc._reversal_credit(text) is reversal


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
    assert tc._refused_by_payer_guards(text, payer.payer_region(text), "CONTOSO BAKERY LLC") == "holder"
    numbered = _text("1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(numbered, payer.payer_region(numbered), "SAMPLE CAFE LLC") == "numbered"
    clean = _text("FABRIKAM SUPPLY DES:VENDOR PAY ID:1")
    assert tc._refused_by_payer_guards(clean, payer.payer_region(clean), "SAMPLE CAFE LLC") is None


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
    assert tc._payer_remittance(text, payer.payer_region(text), "SAMPLE CAFE LLC") is remittance


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
    assert tc._wire_remittance_purpose(text, payer.payer_region(text), "CONTOSO TRADING LLC") is verifies


@pytest.mark.parametrize(("region", "cut"), [
    ("FABRIKAM MERCHAN", True),         # sixteen characters: a proper prefix of MERCHANT
    ("FABRIKAM MERCHANT", False),       # the whole word is no cut
    ("FABRIKAM CAPITA", True),          # fifteen characters: a proper prefix of CAPITAL
    ("FABRIKAM EXPORTS", False),
])
def test_the_cut_financing_originator(region, cut):
    assert tc._cut_financing_originator(region) is cut


def test_an_alias_read_inside_a_waiting_processor_names_no_source():
    # §7.1, review I4: Stripe's BY STRI cut never reads JOBBER BY STRI while Jobber Payments waits for the ledger; once
    # the ledger clears Jobber (Task S1.5 admitted Jobber Capital), the row names Jobber Payments, never Stripe.
    _bare, product = PROCESSOR_ADVANCE_PRODUCTS["Jobber Payments"]
    cleared = product is not None or "Jobber Payments" in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    jobber = _text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3")
    assert tc._read_inside_a_waiting_processor(jobber, "Stripe", "BY STRI") is not cleared
    source = tc._operating_source(jobber)
    assert (source.entity if source is not None else None) == ("Jobber Payments" if cleared else None)
    assert tc._operating_source(_text("FABRIKAM - BY STRI DES:PAYOUT ID:1")).entity == "Stripe"
    assert tc._operating_source(_text("SHIFT4 PAYMENTS DES:DEPOSIT ID:1")).entity == "Shift4"


def test_a_waiting_processor_s_bare_alias_still_refuses_an_alias_read_inside_it(monkeypatch):
    # §7.1, review I4 (S1.5 review): the refusal path itself, whatever the ledger clears. Jobber is made to wait again
    # (its bare aliases gated, its own aliases unread), so Stripe's BY STRI cut inside JOBBER BY STRI names no source.
    import re

    monkeypatch.setattr(tc, "_GATED_PROCESSOR_PATTERNS", {
        "Jobber Payments": re.compile(r"\b(?:JOBBER BY STRIPE|JOBBER BY STRI|JOBBER BY STR)\b"),
    })
    monkeypatch.setattr(tc, "OPERATING_REVENUE_READ_ALIASES", {
        entity: aliases for entity, aliases in classification_registry.OPERATING_REVENUE_READ_ALIASES.items() if entity != "Jobber Payments"
    })
    jobber = _text("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3")
    assert tc._read_inside_a_waiting_processor(jobber, "Stripe", "BY STRI") is True
    assert tc._operating_source(jobber) is None
    assert tc._operating_source(_text("FABRIKAM - BY STRI DES:PAYOUT ID:1")).entity == "Stripe"


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
    assert tc._wire_vetoed(text, payer.payer_region(text), "NORTHWIND LABS LLC")


@pytest.mark.parametrize(("printed", "vetoed"), [
    ("MANHEIM US DES:ACH PAYMNT NGC ID:1", True), ("MANHEIM US DES:ACH PAYMNT FLOORPLAN ID:1", True),
    ("MANHEIM US DES:ACH PAYMNT ID:1 PPD", True), ("MANHEIM US DES:ACH PAYMNT ID:1", False),
])
def test_the_auction_veto(printed, vetoed):
    # §7.8, §14.1, review C2.
    assert (tc._AUCTION_VETO.search(_text(printed)) is not None) is vetoed


#: S2.2 review (item A): in the 5.5 veto patterns a veto word of four letters or more reads through digits glued on
#: its left ((?<![A-Z]), the owner's card-form convention), while a token of three letters or fewer keeps \b: a digit
#: glued to it is usually an ID's suffix ('ID 1234CB'). Each spelling counts on its own (FEES, not FEE). The card veto's
#: BOOK and DUP spellings keep \b (measured: glued there, they were a company name or an ID fragment). A letter glued
#: on the left blocks every word.
GLUED_VETO_WORDS = [
    ("_CARD_VETO", "CHBK", True), ("_CARD_VETO", "CB", False),
    ("_CARD_VETO", "FEES", True), ("_CARD_VETO", "FEE", False),
    ("_CARD_VETO", "BOOK", False), ("_CARD_VETO", "DUPLICATE", False),
    ("_RECURRENCE_VETO", "PAYROLL", True), ("_RECURRENCE_VETO", "MCA", False),
    ("_FUNDING_WORD", "FUNDING", True),
    ("_OPERATING_PAY_VETO", "SALARY", True),
    ("_OPERATING_FINANCING_VETO", "LOAN", True), ("_OPERATING_FINANCING_VETO", "ADV", False),
    ("_OPERATING_REVERSAL_VETO", "REFUND", True), ("_OPERATING_REVERSAL_VETO", "NSF", False),
    ("_OPERATING_P2P_VETO", "ZELLE", True),
    ("_EMPLOYER_PAY_WORDS", "PAYRL", True),
    ("_TRANSPORT_EXTRA_VETO", "CASHOUT", True), ("_TRANSPORT_EXTRA_VETO", "WT", False),
    ("_AUCTION_VETO", "FLOORPLAN", True), ("_AUCTION_VETO", "NGC", False),
    ("_AUCTION_BUYER_PAYMENT", "PYMT1", True),
    ("_PROPERTY_PLATFORM_GUARD", "DISTRIBUTION", True),
    ("_PROPERTY_MICRO_DEPOSIT", "MICRO DEP", True),
    ("_PROPERTY_PUSH_SHAPE", "VISA DIRECT", True), ("_PROPERTY_PUSH_SHAPE", "RTP", False),
    ("_PAYER_REMITTANCE_VETO", "INSURANCE", True), ("_PAYER_REMITTANCE_VETO", "INS", False),
    ("_PUBLIC_PAYER_NAME_VETO", "TAXATION", True),
    ("_PUBLIC_PAYER_NON_SALE_WORDS", "GRANT", True), ("_PUBLIC_PAYER_NON_SALE_WORDS", "EIC", False),
    ("_PUBLIC_PAYER_OTHER_VETO", "SETTLEMENT", True), ("_PUBLIC_PAYER_OTHER_VETO", "FCU", False),
    ("_PUBLIC_PAYER_ARM_B_TRANSFER", "XFER", True), ("_PUBLIC_PAYER_ARM_B_TRANSFER", "TFR", False),
    ("_WIRE_NON_SALE_PURPOSE", "INVESTMENT", True), ("_WIRE_NON_SALE_PURPOSE", "TAX", False),
    ("_TITLE_OR_ESCROW_ORIGINATOR", "ESCROW", True),
]


@pytest.mark.parametrize(("name", "word", "glued"), GLUED_VETO_WORDS)
def test_a_long_veto_word_reads_through_a_glued_digit(name, word, glued):
    pattern = getattr(tc, name)
    assert pattern.search("FABRIKAM ID " + word) is not None
    assert (pattern.search("FABRIKAM ID 0102" + word) is not None) is glued
    assert pattern.search("FABRIKAM ID X" + word) is None


@pytest.mark.parametrize(("printed", "label"), [
    ("BANKCARD DEPOSIT 0102CHBK", None),           # a chargeback code glued to a date still refuses the form
    ("BANKCARD DEPOSIT CHBK", None),
    ("BANKCARD DEPOSIT ID 1234CB", "bankcard"),    # a two-letter ID suffix is no chargeback
])
def test_a_glued_card_veto_word(printed, label):
    form = tc._card_settlement_form(_text(printed), bank=None)
    assert (form and form.label) == label


def test_the_counter_debit_skip_words_hold_the_channel_vocabulary():
    words = rails._counter_debit_skip_words()
    assert {"CHECKCARD", "OVERDRAFT", "WITHDRAW", "PURCHASES"} <= words
