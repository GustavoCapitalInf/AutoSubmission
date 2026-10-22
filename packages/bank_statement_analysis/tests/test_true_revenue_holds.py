"""Audit fix batch B7 (true revenue spec §8.1, §8.7, §8.8, §18.2 item 6, §20): the hold words' precision. The financing
roots are never read on text that names no payer (I16: an ATM's or a branch's location, a bank's branch label, a
person-to-person sender's bank or a person's surname, a layout's entry word, the banks' page furniture, a buyer's
advance payment, a fundraising purpose, a processor's payout entry); the non-sale words read only as a purpose (I18);
the holder's own name never holds a third party's payment (I47); the direct-deposit words are pay wording only with a
sign of a person's pay (I09); a credit union's other dealer-funding entries verify beside its VHCL PURCH credits, its
glued acronym is a credit union, and a named non-lender's wire memo is no dealer funding (I36); a personal trust's
payment citing the holder's service is counted (the orchestrator's delegated ruling on audit I57). Fabricated rows
only, in the banks' printed formats; public names only where a bank prints its own or a registry lists them (Wave
Payments, the operating registry's invoice-and-receivables processor; ADP, the classifier's payroll provider)."""
from __future__ import annotations

import pytest

from analysis.true_revenue import asset_sale
from analysis.true_revenue import facts as true_revenue_facts
from analysis.true_revenue import guards
from analysis.true_revenue import dealer as true_revenue_dealer
from analysis.true_revenue import finance_release
from analysis.true_revenue import purpose as true_revenue_purpose
from analysis.true_revenue import zelle as true_revenue_zelle
from analysis.true_revenue import counter_debit_pairing
from analysis.true_revenue import tiers
from analysis.true_revenue import financing_roots
from analysis.true_revenue import payroll
from analysis.true_revenue import public_payers
from analysis.true_revenue import self_originated_credits
from analysis.true_revenue import channel as true_revenue_channel
from analysis.true_revenue import hold_text
from analysis.true_revenue import holder_names
from analysis.true_revenue import words as true_revenue_words
from analysis import revenue as analysis_revenue
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.descriptor.lexical import revenue_text
from analysis.description_text import normalize_transaction_description
from tests.zelle_reading import rules_reading

HOLDER = "NORTHWIND BAKERY LLC"

FINANCING = ("excluded_pending_review", "financing_named_payer")
NON_SALE = ("excluded_pending_review", "non_sale_purpose")
PAY = ("excluded_pending_review", "payroll_or_salary")
NO_PAYER = ("counted_flagged", "no_payer_printed")
P2P = ("counted_flagged", "p2p")
CHECK = ("counted_flagged", "check_deposit")
UNLABELLED = ("counted_flagged", "named_payer_unlabelled")
ONE_OFF = ("counted_flagged", "named_payer_one_off")
WIRE = ("counted_flagged", "wire_named_sender")
REFUSED = ("counted_flagged", "named_payer_purpose_refused")
REPEATS = ("verified", "named_payer_repeats")
COMPANY = ("verified", "named_payer_company_form")
DEALER = ("verified", "auto_lender_dealer_funding")


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


def _one(text: str, amount: float = 1200.0, **kwargs):
    return _tiers([(text, amount)], **kwargs)[0]


def _counted(tier) -> bool:
    return tier[0] in ("counted_flagged", "verified")


# I16: the financing roots are read only on text that can name the payer.

@pytest.mark.parametrize("text", [
    "BKOFAMERICA ATM 0101 DEPOSIT 123 GLENDALE AZ",
    "ATM DEPOSIT CONTOSO FIN CU 123 SAMPLE ST SAMPLEVILLE FLUS",
    "1 2 ATM DEPOSIT BF1234 1234 CAPITAL BLVD SAMPLEVILLE NC ON 010254 FROM CARD XXXXXXXXXXXX1234X",
])
def test_an_atm_s_location_is_never_read_for_a_financing_root(text):
    assert _one(text, 500.0, bank="Bank of America") == NO_PAYER


@pytest.mark.parametrize(("text", "bank"), [
    # B7 review round 1: a payer-less check, cash, counter or ATM row is read once its location is removed (a street,
    # a credit union's or a branch's name), so a funder's name printed on it still holds.
    ("MOBILE DEPOSIT FABRIKAM FUNDING LLC", "Wells Fargo"),
    ("COUNTER CREDIT FABRIKAM MERCHANT FUNDING", "Bank of America"),
    ("ATM CHECK DEPOSIT 1 FABRIKAM MERCHANT FUNDING", "Wells Fargo"),
    ("REMOTE ONLINE DEPOSIT 1 FABRIKAM CAPITAL ADVANCE", "Chase"),
])
def test_a_funder_s_name_on_a_payer_less_deposit_row_still_holds(text, bank):
    assert _one(text, 4000.0, bank=bank) == FINANCING


@pytest.mark.parametrize("text", [
    "ATM DEPOSIT CONTOSO FIN CTR 123 SAMPLE ST SAMPLEVILLE CA",
    "ATM DEPOSIT 1 SAMPLE FINANCIAL CENTER SAMPLEVILLE CA",
    "ATM CASH DEPOSIT 1 FABRIKAM CREDIT UNION 12 SAMPLE RD SAMPLEVILLE",
])
def test_a_deposit_s_branch_or_credit_union_location_is_no_root(text):
    assert _one(text, 500.0, bank="Wells Fargo") == NO_PAYER


@pytest.mark.parametrize(("text", "bank", "expected"), [
    # B7 review round 2: a town printed with its state at the row's end (or before a ZIP or a reference).
    ("ATM DEPOSIT 123 MAIN ST CAPITAL HEIGHTS MD", "Wells Fargo", NO_PAYER),
    ("ATM CASH DEPOSIT 1 ADVANCE NC", "Wells Fargo", NO_PAYER),
    ("ATM CASH DEPOSIT ON 01 02 1 SAMPLE RD CAPITAL HEIGHTS MD 1234567 ATM ID 1234D CARD 1234", "Wells Fargo",
     NO_PAYER),
    # A place a suffix names, and a branch's name before BRANCH.
    ("ATM DEPOSIT 1 FINANCIAL PLAZA SAMPLEVILLE CA", "Wells Fargo", NO_PAYER),
    ("ATM DEPOSIT 1 FINANCIAL DISTRICT SAMPLEVILLE CA", "Wells Fargo", NO_PAYER),
    ("CASH DEPOSIT BRANCH 123 CAPITAL CIR SAMPLEVILLE", "Wells Fargo", NO_PAYER),
    ("CASH DEPOSIT BRANCH 123 CAPITAL PLAZA SAMPLEVILLE", "Wells Fargo", NO_PAYER),
    ("ATM DEPOSIT 1 CAPITAL MALL SAMPLEVILLE", "Wells Fargo", NO_PAYER),
    ("COUNTER CREDIT CAPITAL CITY BRANCH", "Bank of America", NO_PAYER),
    # The statement's own bank, or a listed bank, owning the ATM.
    ("ATM CASH DEPOSIT CAPITAL ONE 123 SAMPLE ST SAMPLEVILLE", "Capital One", NO_PAYER),
    ("ATM CASH DEPOSIT CAPITAL ONE 123 SAMPLE ST SAMPLEVILLE", "Wells Fargo", NO_PAYER),
    # A hold notice's FUNDS, and a buyer's advance purchase, are no funder's name.
    ("MOBILE DEPOSIT FUNDS ON HOLD", "Wells Fargo", CHECK),
    ("REMOTE DEPOSIT FUNDS HELD 2 DAYS", "Chase", CHECK),
    ("CHECK DEPOSIT FUNDS AVAIL NEXT DAY", "Chase", CHECK),
    ("CASH DEPOSIT ADVANCE TICKET SALES", "Wells Fargo", NO_PAYER),
])
def test_a_deposit_s_town_place_branch_bank_or_notice_is_no_root(text, bank, expected):
    assert _one(text, 500.0, bank=bank) == expected


@pytest.mark.parametrize(("text", "bank"), [
    # B7 review round 2: a funder's name with a company form still holds past the location's removal.
    ("MOBILE DEPOSIT FABRIKAM FUNDS LLC", "Wells Fargo"),
    ("ATM CHECK DEPOSIT 1 FABRIKAM CAPITAL LLC SAMPLEVILLE CA", "Wells Fargo"),
    ("ATM CHECK DEPOSIT CAPITAL ONE 1 FABRIKAM FUNDING LLC", "Capital One"),
    # A LEASE rent printed on a deposit keeps its hold: the holder shows no leasing or property business (Q9 (b)).
    ("CHECK DEPOSIT LEASE PMT UNIT 2", "Wells Fargo"),
])
def test_a_funder_s_formed_name_on_a_payer_less_deposit_still_holds(text, bank):
    assert _one(text, 4000.0, bank=bank) == FINANCING


def test_the_deposit_reading_keeps_only_a_funder_s_words():
    # Unit: the words a payer-less deposit's roots are read on (B7 review round 2).
    read = financing_roots._deposit_location_reading
    assert read("ATM DEPOSIT 123 MAIN ST CAPITAL HEIGHTS MD", HOLDER, "Wells Fargo") == ""
    assert read("ATM CASH DEPOSIT CAPITAL ONE 123 SAMPLE ST SAMPLEVILLE", HOLDER, "Capital One") == ""
    assert read("MOBILE DEPOSIT FUNDS ON HOLD", HOLDER, "Wells Fargo") == ""
    assert read("MOBILE DEPOSIT FABRIKAM FUNDING LLC", HOLDER, "Wells Fargo") == "FUNDING"
    assert read("MOBILE DEPOSIT FABRIKAM FUNDS LLC", HOLDER, "Wells Fargo") == "FUNDS"
    # CO is a company form, never read as Colorado's code.
    assert read("MOBILE DEPOSIT FABRIKAM FUNDING CO", HOLDER, "Wells Fargo") == "FUNDING"


@pytest.mark.parametrize("text", [
    "BOFA FIN CTR DEPOSIT",
    "BOFA FIN CTR 01 02 000123456 DEPOSIT 123PINEST SAMPLEVILLE OK",
])
def test_a_bank_s_branch_label_is_no_financing_root(text):
    tier = _one(text, 900.0, bank="Bank of America")
    assert tier[0] == "counted_flagged" and tier != FINANCING


@pytest.mark.parametrize("text", [
    "ZELLE PAYMENT FROM COF1 PAT SAMPLE CAPITAL ONE ID 1",
    "ZELLE PAYMENT FROM ABC1 PAT SAMPLE FABRIKAM CREDIT UNION ID 123456789012345",
    "ZELLE PAYMENT FROM ABC1 PAT SAMPLE NAVY FEDERAL CREDIT UNION ID 123456789012345",
    "ZELLE PAYMENT FROM ABC1 PAT SAMPLE CONTOSO FINANCIAL CREDIT UNION ID 123456789012345",
])
def test_a_zelle_sender_s_bank_is_never_the_sender(text):
    assert _one(text, 150.0, bank="American Express") == P2P


@pytest.mark.parametrize("text", [
    "ZELLE PAYMENT FROM PAT LENDSAMPLE CONF 1",
    "ZELLE PAYMENT FROM PAT SAMPLE FUNDERSON FOR GRACIAS CONF 1",
    "ZELLE CREDIT PAT LENDSAMPLE 1234567890",
])
def test_a_root_inside_a_person_s_surname_is_never_read(text):
    assert _one(text, 150.0) == P2P


@pytest.mark.parametrize("text", [
    # A sender whose own name is a financing word, or a company form, is still read.
    "ZELLE PAYMENT FROM FABRIKAM FUNDING CONF 1",
    "ZELLE PAYMENT FROM FABRIKAM CAPITAL LLC CONF 1",
    "RTP CREDIT FABRIKAM FINANCE SAMPLEVILLE CA 12345 AB12CD",
    # A memo that says funding still holds a person's payment.
    "ZELLE PAYMENT FROM PAT SAMPLE FOR FUNDING CONF 1",
    # A credit union paying by ACH is no sending bank: its name is still read.
    "FABRIKAM CREDIT UNION DES:PAYMENT ID:1",
])
def test_a_financing_sender_or_memo_on_a_person_to_person_or_ach_row_still_holds(text):
    assert _one(text, 150.0, bank="American Express") == FINANCING


# Audit round 2, R2-B11 (R38; §5.2's sender ends, B7's I16 line): Truist's business-Zelle layout prints 'FROM <sender>
# PAYMENT ID <reference>'. The sender ends at its PAYMENT ID label, so the label's PAYMENT never joins the sender and a
# person's name (a sole proprietor's trade word after it too) is read as a person's: a root inside the surname holds
# nothing. A funder's name, a glued funder, a root at a name word's start, a holder-noise trade word, a company form or
# a funding memo still holds.

R38_TRUIST = "ZELLE BUSINESS PAYMENT FROM {sender} PAYMENT ID BAC1X2Y3Z"


@pytest.mark.parametrize(("layout", "sender", "bank"), [
    (R38_TRUIST, "PAT SAMPLELENDEZ TRANSPORT", "Truist"),
    (R38_TRUIST, "PAT SAMPLELENDEZ", "Truist"),
    ("ZELLE PAYMENT FROM {sender} PAYMENT ID BAC1X2Y3Z", "DANA SAMPLEFUNDORA", "Truist"),
    (R38_TRUIST, "PAT SAMPLELENDEZ TRANSPORT", "Huntington National Bank"),
])
def test_r38_a_root_inside_a_surname_on_the_payment_id_layout_holds_nothing(layout, sender, bank):
    assert _one(layout.format(sender=sender), 1234.56, bank=bank) == P2P


def test_r38_a_surname_s_repeated_round_sums_are_held_as_round_repeats():
    rows = [(R38_TRUIST.format(sender="PAT SAMPLELENDEZ TRANSPORT"), 200.0)] * 2
    assert _tiers(rows, bank="Truist") == [("excluded_pending_review", "p2p_round_repeat")] * 2


@pytest.mark.parametrize("text", [
    R38_TRUIST.format(sender="FAST FUNDING LLC"),
    R38_TRUIST.format(sender="CONTOSO CAPITAL"),
    R38_TRUIST.format(sender="QUICKFUND LLC"),
    R38_TRUIST.format(sender="PAT LENDER TRANSPORT"),
    R38_TRUIST.format(sender="PAT SAMPLELENDEZ SERVICES"),
    R38_TRUIST.format(sender="SAMPLELENDEZ TRANSPORT LLC"),
    "ZELLE BUSINESS PAYMENT FROM PAT SAMPLELENDEZ PAYMENT ID BAC1X2Y3Z FOR FUNDING",
])
def test_r38_a_funder_or_a_funding_memo_on_the_payment_id_layout_still_holds(text):
    assert _one(text, 1234.56, bank="Truist") == FINANCING


@pytest.mark.parametrize(("text", "bank", "expected"), [
    (R38_TRUIST.format(sender="NORTHWIND BAKERY LLC"), "Truist", ("excluded_pending_review", "holder_name")),
    (R38_TRUIST.format(sender="PAT SAMPLEMAN"), "Truist", P2P),
    (R38_TRUIST.format(sender="FABRIKAM LANDSCAPING LLC"), "Truist", P2P),
    ("ZELLE PAYMENT FROM PAT SAMPLELENDEZ CONF 123456", "Bank of America", P2P),
])
def test_r38_the_controls_keep_their_readings(text, bank, expected):
    assert _one(text, 1234.56, bank=bank) == expected


def test_r38_the_sender_ends_at_the_payment_id_label():
    from analysis.descriptor import payer

    assert payer.payer_region(R38_TRUIST.format(sender="PAT SAMPLELENDEZ TRANSPORT")) == "PAT SAMPLELENDEZ TRANSPORT"
    assert payer.payer_region("ZELLE PAYMENT FROM PAT SAMPLE PAYMENT INFO RENT") == "PAT SAMPLE"


def test_a_layout_s_entry_word_after_a_cut_name_is_no_credit_root():
    assert _one("CONTOSO BOOKS P CREDIT", 1000.0) == UNLABELLED
    # A lender's whole-word CREDIT inside its name, and a glued CREDIT, still hold.
    assert _one("FABRIKAM AUTO CREDIT", 1000.0) == FINANCING
    assert _one("FABRIKAM CREDITLINE DES:DRAW ID:1", 1000.0) == FINANCING


@pytest.mark.parametrize("text", [
    "12345678901 EFT DEPOSIT CONTOSO MEDICAL GROUP CREDITS",
    "SBB MDEPOSIT MEMBER FDIC EQUAL HOUSING LENDER",
    "MOBILE DEPOSIT PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE PAGE 1 PAGE 1 OF 1 BUSINESS CHECKING FOR XXXXXX 123 "
    "4 CONTINUED DEPOSITS AND CREDITS CONTINUED DATE AMOUNT DESCRIPTION",
    "NOW NETWORK CREDIT ZELLE CREDIT NOW NET ID 123456A7BCDE EPP ID US12345678901234 ZELLE PAT SAMPLE 1234567890 PLEASE "
    "SEE ADDITIONAL INFORMATION ON NEXT PAGE PAGE 1 OF 1 CONTINUED DEPOSITS AND CREDITS CONTINUED DATE",
])
def test_page_furniture_and_the_plural_credits_are_no_root(text):
    tier = _one(text, 400.0)
    assert _counted(tier) and tier != FINANCING


def test_a_payer_named_with_the_plural_credits_and_a_company_form_still_holds():
    # B7 review round 1: CREDITS before a company form is a lender's name word, read as the whole-word CREDIT is.
    assert _one("FABRIKAM CREDITS LLC DES:PAYMENT ID:1 INDN:NORTHWIND BAKERY LLC CO ID:1 CCD", 900.0) == FINANCING
    assert _one("FABRIKAM CREDIT LLC DES:PAYMENT ID:1 INDN:NORTHWIND BAKERY LLC CO ID:1 CCD", 900.0) == FINANCING


@pytest.mark.parametrize("purpose", ["ADVANCE PAYMENT", "ADVANCE PAYMEN", "ADVANCE PMT", "PREPAYMENT 12 FOR ORDE"])
def test_a_buyer_s_advance_payment_wire_is_counted(purpose):
    text = f"USD WIRE IN FROM BANK OF FABRIKAM ACCT 1234 CONTOSO EXPORTS LTD REF {purpose}"
    assert _one(text, 7000.0, bank="Santander Bank") == WIRE


def test_an_advance_still_holds_a_lender_s_wire_and_an_ach_entry():
    assert _one("USD WIRE IN FROM BANK OF FABRIKAM ACCT 1234 CONTOSO CAPITAL LTD REF ADVANCE PAYMENT", 7000.0,
                bank="Santander Bank") == FINANCING
    assert _one("CONTOSO GROUP DES:ADVANCE PMT ID:1", 7000.0) == FINANCING


# Audit round 3, R3-B07 (R3-18; §8.1, T4): a buyer's advance payment printed cut or abbreviated on a wire's purpose
# (ADV PAYM, ADV PAYMENT, ADV PMT, ADV PYMT, ADVANCE PYMT) is no financing either, never after MERCHANT, CASH or MCA.
R318_BOFA = ("WIRE TYPE:WIRE IN DATE:000000 TIME:0000 ET TRN:0000000000000001 ORIG:{orig} ID:AE0000000000000000000 "
             "SND BK:SAMPLE BANK LIMITED ID:0000 PMT DET:WIRES 000000000 ROUTING 000000000 {purpose}")


@pytest.mark.parametrize("purpose", [
    "ADV PAYM", "ADV PAYMENT FOR PO 1234", "ADV PMT", "ADV PYMT", "ADV PMT INV 1234", "ADVANCE PYMT",
])
def test_r3_18_a_buyer_s_abbreviated_advance_payment_wire_is_counted(purpose):
    text = R318_BOFA.format(orig="FABRIKAM SEAFOOD TRADING", purpose=purpose)
    assert _one(text, 23456.78, bank="Bank of America") == WIRE


@pytest.mark.parametrize("purpose", ["MERCHANT ADV PMT", "CASH ADV PMT", "MERCHANT ADVANCE PAYMENT"])
def test_r3_18_a_merchant_or_cash_advance_payment_on_a_wire_still_holds(purpose):
    text = R318_BOFA.format(orig="FABRIKAM SEAFOOD TRADING", purpose=purpose)
    assert _one(text, 23456.78, bank="Bank of America") == FINANCING


def test_r3_18_controls_a_funder_s_wire_an_ach_entry_and_an_mca_advance():
    # The payer region's financing name comes first; the purpose removal is wire-only.
    assert _one(R318_BOFA.format(orig="CONTOSO CAPITAL FUNDING LLC", purpose="ADV PMT"), 23456.78,
                bank="Bank of America") == FINANCING
    assert _one("CONTOSO GROUP DES:ADV PMT ID:1", 23456.78, bank="Bank of America") == FINANCING
    assert _one(R318_BOFA.format(orig="FABRIKAM SEAFOOD TRADING", purpose="MCA ADV PMT"), 23456.78,
                bank="Bank of America")[0] == "non_revenue"


def test_r3_18_the_pattern_is_shared_with_the_payer_less_deposit_reading():
    assert _one("MOBILE DEPOSIT ADV PMT", 2345.67, bank="Bank of America") == CHECK
    assert _one("ATM CASH DEPOSIT 1234 ADV PMT", 2345.67, bank="Bank of America") == NO_PAYER
    assert _one("MOBILE DEPOSIT CONTOSO FUNDING LLC", 2345.67, bank="Bank of America") == FINANCING
    assert financing_roots._WIRE_TRADE_PURPOSE.search("ADV PAYM") and not financing_roots._WIRE_TRADE_PURPOSE.search("MERCHANT ADV PMT")


def test_a_fundraising_purpose_is_no_financing():
    text = ("WIRE TYPE WIRE IN DATE 540102 TIME 1234 ET TRN 1234567890123456 SEQ 1234567890123456 123456 ORIG CONTOSO "
            "FOR SAMPLE ID 1234567890 SND BK FABRIKAM BANK ID 123456789 PMT DET 12345 1234567890 INVOICE "
            "FUNDRAISING EVENT SPONSOR")
    assert _one(text, 6000.0, bank="Bank of America") == WIRE


def test_wave_payments_payout_entry_is_no_financing_and_a_funder_named_wave_still_holds():
    assert _one("PAYMENT RECEIVED 01 02 WAVE AB1T FUNDIN WAVE 123 1234567 CO CARD 1234", 300.0) == P2P
    assert _one("WAVE FUNDING LLC DES:PAYMENT ID:1", 300.0) == FINANCING
    # The transfer form keeps the masked account number's own hold: no longer a financing root.
    assert _one("INTERBANK TRANSFER TO AB1 XXXXXX1234 123456 WAVE FUNDING INSTRU SAMPLEVILLE CO", 400.0) == (
        "excluded_pending_review", "transfer_account_designation")


def test_a_named_funder_is_still_held():
    assert _one("FABRIKAM CAPITAL DES:FUNDING ID:1 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 CCD", 5000.0) == FINANCING


def test_the_root_readers_strip_only_what_names_no_payer():
    # Unit: the root reading of a person-to-person sender (the sending bank and the person's name removed).
    assert holder_names._p2p_person_name("PAT LENDSAMPLE")
    assert not holder_names._p2p_person_name("FABRIKAM FUNDING")
    assert not holder_names._p2p_person_name("CONTOSO FINANCE")
    assert not holder_names._p2p_person_name("CONTOSO CAPITALCO")
    assert not holder_names._p2p_person_name("FABRIKAM LLC")
    assert not holder_names._p2p_person_name("LENDSAMPLE")
    assert "CAPITAL ONE" not in financing_roots._root_reading("PAT SAMPLE CAPITAL ONE", None, None, p2p=True)
    assert "CAPITAL ONE" in financing_roots._root_reading("PAT SAMPLE CAPITAL ONE", None, None, p2p=False)


# I18: the non-sale words read only as a purpose.

def test_a_processor_s_recurring_disbursement_payouts_are_counted_never_verified():
    # Audit round 2, R2-B12 (R17; amends B7's I18 pin, which verified them): a spared disbursement entry is counted and
    # flagged as a refused purpose, as §8.6 counts an unregistered payer's SETTLEMENT; repetition proves nothing.
    rows = [(f"ACH DEPOSIT PSP 800-555-0100 DISBURSMNT {n} NORTHWIND SALON", 500.0 + n) for n in (1, 2, 3)]
    assert _tiers(rows, holder="NORTHWIND SALON LLC") == [REFUSED] * 3


def test_a_one_off_or_a_loan_escrow_or_lender_disbursement_keeps_its_hold():
    assert _one("ACH DEPOSIT PSP 800-555-0100 DISBURSMNT 1 NORTHWIND SALON", 501.0, holder="NORTHWIND SALON LLC") == (
        NON_SALE)
    escrow = [(f"CONTOSO ESCROW DES:DISBURSEMENT ID:{n}", 500.0 + n) for n in (1, 2)]
    assert _tiers(escrow) == [NON_SALE] * 2
    loan = [(f"CONTOSO HOLDINGS DES:LOAN DISBURS ID:{n}", 500.0 + n) for n in (1, 2)]
    assert all(tier != REPEATS and not tier[0] == "counted_flagged" for tier in _tiers(loan))
    lender = [(f"FABRIKAM FUNDING DES:DISBURSEMENT ID:{n}", 500.0 + n) for n in (1, 2)]
    assert _tiers(lender) == [FINANCING] * 2
    lawyer = [(f"SAMPLE LAW FIRM DES:DISBURSEMENT ID:{n}", 500.0 + n) for n in (1, 2)]
    assert _tiers(lawyer) == [NON_SALE] * 2


@pytest.mark.parametrize("payer", [
    "CONTOSO HOLDINGS", "FABRIKAM PARTNERS LP", "CONTOSO VENTURES", "SAMPLE FAMILY OFFICE", "SAMPLE ESTATE",
    "FABRIKAM LIMITED PARTNERSHIP", "CONTOSO GROUP LLP",
    # B7 review round 2 (accepted, fail closed): an owner-shaped word holds beside a trade word too.
    "FABRIKAM PAYMENTS HOLDINGS", "FABRIKAM FAMILY DENTAL",
])
def test_an_owner_shaped_payer_s_recurring_disbursement_keeps_its_hold(payer):
    # B7 review round 1: a holding, partnership, venture, family or estate payer's disbursement is owner money.
    rows = [(f"{payer} DES:DISBURSEMENT ID:{n} INDN:NORTHWIND GRILL LLC CO ID:1 CCD", 500.0 + n) for n in (1, 2)]
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == [NON_SALE] * 2


def test_a_processor_s_recurring_disbursement_entry_is_counted_never_verified():
    # Audit round 2, R2-B12 (R17; amends B7's I18 pin, which verified it).
    rows = [(f"FABRIKAM MERCHANT SOLUTIONS DES:DISBURSEMENT ID:{n} INDN:NORTHWIND GRILL LLC CO ID:1 CCD", 5000.0 + n)
            for n in (1, 2)]
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == [REFUSED] * 2


# Audit round 2, R2-B12 (R17): a spared disbursement entry is counted, never verified, whoever repeats it; a retirement
# account's disbursement is never spared.

def _grill(payer, entry, times=2):
    return [(f"{payer} DES:{entry} ID:{n} INDN:NORTHWIND GRILL LLC CO ID:1 CCD", 5000.0 + n) for n in range(1, times + 1)]


@pytest.mark.parametrize(("payer", "entry", "times", "expected"), [
    ("CONTOSO ADVISORS", "DISBURSEMT", 2, REFUSED),
    ("SAMPLE 529 PLAN", "DISBURSEMT", 2, REFUSED),
    ("SAMPLE 401K PLAN", "DISBURSEMT", 2, NON_SALE),
    ("SAMPLE IRA CUSTODIAN", "DISBURSEMT", 2, NON_SALE),
    ("SAMPLE ROTH SERVICES", "DISBURSEMENT", 2, NON_SALE),
    # Controls: a payout entry verifies; a bare SETTLEMENT is counted (§8.6); a one-off disbursement, an owner-shaped
    # or escrow payer's, a lender's and a loan's keep their readings.
    ("FABRIKAM MERCHANT SOLUTIONS", "PAYOUT", 2, REPEATS),
    ("CONTOSO PAYMENTS", "SETTLEMENT", 2, REFUSED),
    ("FABRIKAM MERCHANT SOLUTIONS", "DISBURSEMENT", 1, NON_SALE),
    ("CONTOSO HOLDINGS", "DISBURSEMENT", 2, NON_SALE),
    ("CONTOSO ESCROW", "DISBURSEMENT", 2, NON_SALE),
    ("FABRIKAM FUNDING", "DISBURSEMENT", 2, FINANCING),
])
def test_r17_a_spared_disbursement_entry_is_counted_never_verified(payer, entry, times, expected):
    assert _tiers(_grill(payer, entry, times), holder="NORTHWIND GRILL LLC") == [expected] * times


def test_r17_a_loan_disbursement_stays_non_revenue():
    records = _records(_grill("CONTOSO", "LOAN DISBURS"), holder="NORTHWIND GRILL LLC")
    assert [record.revenue_tier for record in records] == ["non_revenue", "non_revenue"]


@pytest.mark.parametrize(("payer", "entry", "fact"), [
    ("FABRIKAM MERCHANT SOLUTIONS", "DISBURSEMENT", True),
    ("FABRIKAM MERCHANT SOLUTIONS", "DISBURSEMENT ACCOUNT", False),
    ("FABRIKAM MERCHANT SOLUTIONS", "PAYOUT", False),
    ("SAMPLE 401K PLAN", "DISBURSEMT", False),
    ("CONTOSO HOLDINGS", "DISBURSEMENT", False),
    ("CONTOSO ESCROW", "DISBURSEMENT", False),
    ("CONTOSO", "LOAN DISBURS", False),
])
def test_r17_the_census_reads_the_spared_disbursement_fact(payer, entry, fact):
    record = _records(_grill(payer, entry, 1), holder="NORTHWIND GRILL LLC")[0]
    facts = guards.guard_facts(record, revenue_text(record.normalized_description))
    assert facts["spared_disbursement"] is fact


# Audit round 2, R2-B12 review round 1 (R17): the refused disbursement word is the entry's, read outside the payer's own
# name field (an ACH originator, a wire's sender, a transfer's sender), as B7 reads DISTRIB... and STOCK; a row that
# prints no name field is read whole (fail closed).

CHASE_GRILL = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry}SEC:CCD "
               "TRACE#:12345678901234{n} EED:540102 IND ID:12345 IND NAME:NORTHWIND GRILL LLC TRN: 123456789{n}TC")


@pytest.mark.parametrize(("rows", "expected"), [
    # A payer named for disbursement services keeps the reading B7's spare gave it.
    (_grill("SAMPLE DISBURSEMENT SERVICES LLC", "PAYMENT"), [REPEATS, REPEATS]),
    ([(CHASE_GRILL.format(payer="SAMPLE DISBURSEMENT SERVICES LLC", entry="PAYMENT", n=n), 5000.0 + n)
      for n in (1, 2)], [REPEATS, REPEATS]),
    # Its disbursement entry, and an entry a row with no name field prints, count and never prove.
    (_grill("SAMPLE DISBURSEMENT SERVICES LLC", "DISBURSEMENT"), [REFUSED, REFUSED]),
    ([(f"ACH CREDIT FABRIKAM MERCHANT SOLUTIONS DISBURSEMENT 123{n}", 5000.0 + n) for n in (1, 2)],
     [REFUSED, REFUSED]),
    # A one-off keeps B7's hold.
    (_grill("SAMPLE DISBURSEMENT SERVICES LLC", "PAYMENT", 1), [NON_SALE]),
])
def test_r17_review_a_disbursement_word_in_the_payer_s_own_name_is_no_refused_entry(rows, expected):
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == expected


@pytest.mark.parametrize(("payer", "entry", "fact"), [
    ("SAMPLE DISBURSEMENT SERVICES LLC", "PAYMENT", False),
    ("SAMPLE DISBURSEMENT SERVICES LLC", "DISBURSEMENT", True),
])
def test_r17_review_the_spared_disbursement_fact_reads_the_entry(payer, entry, fact):
    record = _records(_grill(payer, entry, 1), holder="NORTHWIND GRILL LLC")[0]
    facts = guards.guard_facts(record, revenue_text(record.normalized_description))
    assert facts["spared_disbursement"] is fact


def test_the_payer_s_own_disbursement_account_is_no_purpose():
    text = ("WIRE TYPE INTL IN DATE 540102 TIME 1234 ET TRN 1234 SNDR REF 1 ORIG CONTOSO IMPORTS LLC DISBURSEMENT "
            "ACCOUNT ID 1234")
    assert _one(text, 4000.0, bank="Bank of America") == WIRE


def test_the_ordering_platform_owner_com_is_no_owner_money():
    rows = [(f"OWNER COM DES:OWNER COM ID:ST-K{n} INDN:NORTHWIND GRILL LLC CO ID:1234567890 CCD", 240.0 + n)
            for n in (1, 2, 3)]
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == [REPEATS] * 3


def test_an_owners_association_is_no_owner_money():
    assert _one("CONTOSO OWNERS ASSOCIATION DES:VENDOR PAY ID:1 INDN:NORTHWIND GRILL LLC CO ID:1234567890 CCD",
                450.0, holder="NORTHWIND GRILL LLC") == COMPANY
    cut = ("ORIG CO NAME:CONTOSO OWNERS A ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:VENDOR PAYSEC:CCD "
           "TRACE#:1 EED:540102 IND ID:1 IND NAME:NORTHWIND RESTORATION")
    assert _one(cut, 450.0, holder="NORTHWIND RESTORATION LLC") == ONE_OFF


@pytest.mark.parametrize(("text", "expected"), [
    ("ATM CHECK DEPOSIT 1 1234 GRANT AVE", CHECK),
    ("ATM CHECK DEPOSIT ON 01 02 1 GRANT AVE SAMPLEVILLE CA 1234567 ATM ID 1234A CARD 1234", CHECK),
    ("ATM CASH DEPOSIT ON 01 02 1 GRANT AVE SAMPLEVILLE CA 1234567 ATM ID 1234D CARD 1234", NO_PAYER),
])
def test_a_street_named_like_a_non_sale_word_is_an_address(text, expected):
    assert _one(text, 800.0, bank="Wells Fargo") == expected


def test_a_distributor_s_name_is_no_distribution():
    rows = [(f"CONTOSO DISTRIBUTION INC DES:PAYMENT ID:{n} INDN:NORTHWIND GRILL LLC CO ID:1234567890 CCD", 800.0 + n)
            for n in (1, 2, 3)]
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == [REPEATS] * 3
    # A name its originator field cut, with no company form; a formed name on a row with no name field.
    cut = ("ORIG CO NAME:CONTOSO DISTRIBUTIO ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:ACH PMT SEC:PPD "
           "TRACE#:1 EED:540102 IND ID:1 IND NAME:NORTHWIND GRILL")
    assert _one(cut, 800.0, holder="NORTHWIND GRILL LLC")[0] == "counted_flagged"
    assert _one("CONTOSO DISTRIBUTION INC 1", 800.0, holder="NORTHWIND GRILL LLC") == UNLABELLED
    assert _one("USD WIRE IN FROM FABRIKAM BANK ACCT 1234 CONTOSO DISTRIB REF", 4000.0,
                holder="NORTHWIND GRILL LLC", bank="Santander Bank") == WIRE


@pytest.mark.parametrize("text", [
    # A distribution as the purpose, an ACH entry or a row that prints no name field.
    "FABRIKAM PARTNERS LP DES:DISTRIB ID:1",
    "QUARTERLY DISTRIBUTION FROM CONTOSO HOLDINGS LLC",
    "CONTOSO VENDOR AB12CD34 QUARTERLY PARTNER DISTRIBUTION",
    # A liquidation marketplace's credit with no name field (seller proceeds or a buyer's refund): unchanged.
    "FABRIKAM STOCK MARKETPLACE SD1234 M1B2S3Y4 NORTHWIND DISTRIBUTIO",
    # Owner money still holds.
    "ZELLE PAYMENT FROM PAT SAMPLE FOR OWNER INVESTMENT CONF 1",
    "FEDWIRE CREDIT VIA CONTOSO BANK 123456789 B O PAT SAMPLE SAMPLEVILLE CA REF CHASE NYC OBI OWNER DRAW",
    # The owner's ruling of 2026-10-02 (the underwriter's Q11 (a)): a builder's progress draw ('DRAW12 FABRIKAM BUILD
    # GROUP INC PROJECT CONTOSO HOUSING DRAW 12') left this list; it is counted (test_a_builder_s_progress_draw_...).
])
def test_a_non_sale_purpose_still_holds(text):
    assert _one(text, 1600.0, holder="NORTHWIND GRILL LLC", bank="Wells Fargo") == NON_SALE


# The owner's ruling of 2026-10-02 (the underwriter's Q11 (a), "Count as true revenue and flag it"; audit I18): a
# builder's progress draw is counted and flagged as construction_progress_draw, never verified, when the payer is a
# builder, no lender and not the business's own loan; the lender, own-loan and holder guards run first, any other hold
# wins, and a DRAW printed only in the payer's own name or on a Zelle row keeps today's reading. Each case is a one-month
# Bank of America statement (a mobile deposit, then the rows), holder NORTHWIND SOLAR LLC.

SOLAR = "NORTHWIND SOLAR LLC"
DRAW_COUNTED = ("counted_flagged", "construction_progress_draw")


def _q11_bofa(payer: str, entry: str, holder: str = SOLAR, ref: str = "1234567") -> str:
    return f"{payer} DES:{entry} ID:{ref} INDN:{holder} CO ID:1234567890 CCD"


def _q11_chase(payer: str, entry: str, holder: str = SOLAR) -> str:
    return (f"ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry} SEC:CCD "
            f"TRACE#:123456789012345 EED:540102 IND ID:1234 IND NAME:{holder} TRN: 1234567890TC")


def _q11_wire(orig: str, purpose: str) -> str:
    return ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200012345 SEQ:123456/000001 ORIG:"
            f"{orig} ID:1234 SND BK:SAMPLE BANK ID:123456789 PMT DET:{purpose}")


def _q11_records(rows, holder: str = SOLAR, *, bank: str = "Bank of America", zelle_true_revenue: bool = False):
    """One month (Bank of America unless `bank` says otherwise; the Zelle setting `zelle_true_revenue`, No by
    default): a mobile deposit, then `rows`; the records of the credits after the deposit."""
    records = classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date="2054-03-01", description="MOBILE DEPOSIT", amount=500.0, direction="credit"),
        *(Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                      direction="credit" if amount > 0 else "debit")
          for index, (text, amount) in enumerate(rows)),
    ]), zelle_true_revenue=zelle_true_revenue)
    return [record for record in records[1:] if record.amount > 0]


def _q11(rows, holder: str = SOLAR, **statement):
    return [rules_reading(record, method=True) for record in _q11_records(rows, holder, **statement)]


@pytest.mark.parametrize(("rows", "holder"), [
    # A1: a builder's ACH DRAW.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3"), 9000.0)], SOLAR),
    # A3: a construction firm's wire.
    ([(_q11_wire("FABRIKAM CONSTRUCTION LLC", "PROGRESS DRAW 4 FRAMING"), 25000.0)], SOLAR),
    # A4: a homebuilder on Chase's layout.
    ([(_q11_chase("CONTOSO HOMEBUILDERS", "DRAW 2"), 12000.0)], SOLAR),
    # A5: the corpus shape, an unlabelled row that prints the builder's BUILD GROUP name.
    ([("DRAW12 FABRIKAM BUILD GROUP INC PROJECT NAME CONTOSO HOUSING PHASE B DRAW 12", 45000.0)], SOLAR),
    # A6: a name a sixteen-character field cut to CONST.
    ([(_q11_bofa("CONTOSO CONST", "DRAW"), 7000.0)], SOLAR),
    # A7: a general contractor's wire.
    ([(_q11_wire("SAMPLE GENERAL CONTRACTORS INC", "DRAW 5 JOB 12"), 30000.0)], SOLAR),
    # H1: a homebuilder named HOMES.
    ([(_q11_bofa("CONTOSO HOMES INC", "DRAW 3"), 9000.0)], SOLAR),
    # N4: a builder whose own name prints DRAW, paying a DRAW: the entry's DRAW is the draw.
    ([(_q11_bofa("QUICK DRAW CONSTRUCTION LLC", "DRAW 3"), 9000.0)], SOLAR),
    # Z3: a transfer from a builder, its sender cut at its company form (R2-B13's _payer_name_proper).
    ([("ONLINE TRANSFER FROM CONTOSO BUILDERS INC DRAW 3", 9000.0)], SOLAR),
])
def test_a_builder_s_progress_draw_is_counted_and_flagged(rows, holder):
    records = _q11_records(rows, holder)
    assert [rules_reading(record, method=True) for record in records] == [DRAW_COUNTED]
    assert records[0].revenue_classification == "unverified_deposit" and records[0].contributes_to_true_revenue
    assert not records[0].revenue_review_required


def test_the_held_list_s_old_progress_draw_pin_is_now_counted():
    # Was test_a_non_sale_purpose_still_holds's last row (section 15 deferred construction draws until the ruling).
    assert _one("DRAW12 FABRIKAM BUILD GROUP INC PROJECT CONTOSO HOUSING DRAW 12", 1600.0, holder="NORTHWIND GRILL LLC",
                bank="Wells Fargo") == DRAW_COUNTED


def test_a_builder_s_repeated_progress_draws_are_counted_never_verified():
    # A2: the same builder twice: Q6 never verifies a progress draw, nor counts it toward a repeat.
    records = _q11_records([(_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3"), 9000.0),
                            (_q11_bofa("CONTOSO BUILDERS INC", "DRAW 4", ref="7654321"), 9500.0)])
    assert [rules_reading(record, method=True) for record in records] == [DRAW_COUNTED, DRAW_COUNTED]
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}


@pytest.mark.parametrize(("rows", "holder", "expected"), [
    # C1, C2: a construction lender's or a builders' capital firm's DRAW (the financing guards run first).
    ([(_q11_bofa("FABRIKAM CONSTRUCTION LENDING LLC", "DRAW 3"), 9000.0)], SOLAR, [FINANCING]),
    ([(_q11_bofa("CONTOSO BUILDERS CAPITAL LLC", "DRAW"), 9000.0)], SOLAR, [("non_revenue", "financing_proceeds_credit")]),
    # C3, C4, C8: a builder's LOAN, OWNER or EQUITY DRAW is the business's own loan or money.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "LOAN DRAW"), 9000.0)], SOLAR, [("non_revenue", "strong_non_revenue_rule")]),
    ([(_q11_bofa("CONTOSO BUILDERS INC", "OWNER DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO BUILDERS INC", "EQUITY DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    # C5, C6: a hard-money lender's and an address-named project LLC's draw (no builder; §17.1's follow-up).
    ([(_q11_wire("SAMPLE HARD MONEY LLC", "FRAMING DRAW 3"), 30000.0)], SOLAR, [NON_SALE]),
    ([(_q11_wire("5678 N SAMPLE LLC", "5678 N SAMPLE ROOF DRAW"), 18000.0)], "NORTHWIND DEVELOPMENT LLC",
     [NON_SALE]),
    # C7: a builders' trust (an owner-shaped payer).
    ([(_q11_bofa("CONTOSO BUILDERS TRUST", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    # C10: the holder's own affiliate.
    ([(_q11_bofa("NORTHWIND CONSTRUCTION LLC", "DRAW 3", holder="NORTHWIND BUILDERS LLC"), 9000.0)],
     "NORTHWIND BUILDERS LLC", [("excluded_pending_review", "holder_name")]),
    # C11: a builder's payments without DRAW keep Q6.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "PAYMENT"), 9000.0),
      (_q11_bofa("CONTOSO BUILDERS INC", "PAYMENT", ref="7654321"), 9500.0)], SOLAR, [REPEATS, REPEATS]),
    # C12: a title firm's construction draw.
    ([(_q11_bofa("SAMPLE TITLE CO", "CONSTRUCTION DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    # C13: DRAWDOWN keeps its financing reading.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "DRAWDOWN"), 9000.0)], SOLAR, [NON_SALE]),
    # C14: BUILDING is no builder word (a building-supply firm).
    ([(_q11_bofa("CONTOSO BUILDING SUPPLY INC", "DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    # C15: PROGRESS BILLING stays a section 15 deferred source.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "PROGRESS BILLING"), 9000.0)], SOLAR, [REFUSED]),
    # H2, H3: a nursing home and a mobile-home seller are no homebuilder; H4: a homebuilder's OWNER DRAW.
    ([(_q11_bofa("CONTOSO NURSING HOMES INC", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("SAMPLE MOBILE HOMES LLC", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO HOMES INC", "OWNER DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    # N1: a DRAW printed only in the payer's own name keeps today's name-word hold, never a progress draw.
    ([(_q11_bofa("QUICK DRAW CONSTRUCTION LLC", "PAYMENT"), 9000.0),
      (_q11_bofa("QUICK DRAW CONSTRUCTION LLC", "PAYMENT", ref="7654321"), 9500.0)], SOLAR, [NON_SALE, NON_SALE]),
    # A draw on the business's line, and a builders' supplier's DRAW.
    ([(_q11_bofa("CONTOSO BUILDERS INC", "DRAW ON LINE"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("BUILDERS FIRSTSOURCE INC", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    # Review round 1: a realty firm whose name prints HOMES or BUILDERS is no builder (the brief's MUST NOT CHANGE (a)),
    # and a commission draw is a salesperson's advance against its commissions, never a progress draw.
    ([(_q11_bofa("CONTOSO HOMES REALTY LLC", "DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO HOMES REAL ESTATE LLC", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO BUILDERS REALTY INC", "DRAW 3"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO HOMES INC", "COMM DRAW"), 9000.0)], SOLAR, [NON_SALE]),
    ([(_q11_bofa("CONTOSO BUILDERS INC", "COMMISSION DRAW"), 9000.0)], SOLAR, [NON_SALE]),
])
def test_a_draw_that_is_no_builder_s_progress_draw_keeps_its_reading(rows, holder, expected):
    assert _q11(rows, holder) == expected


@pytest.mark.parametrize("entry", ["A P PMT DRAW 3", "VENDOR PAY DRAW 3", "PAYABLES DRAW 3"])
def test_a_builder_s_progress_draw_a_remittance_descriptor_verified_is_counted_never_verified(entry):
    # Review round 1: the ruling's "never verified" reaches a builder's DRAW that §7.5's accounts-payable descriptor
    # verified before pass 7, as it reaches a factor's or a financier's: counted and flagged, the rule it overrules named.
    record, = _q11_records([(_q11_bofa("CONTOSO BUILDERS INC", entry), 9000.0)])
    assert rules_reading(record, method=True) == DRAW_COUNTED
    assert record.revenue_classification == "unverified_deposit" and record.contributes_to_true_revenue
    assert record.revenue_match_method == true_revenue_words.CONSTRUCTION_PROGRESS_DRAW_REASON
    assert record.revenue_matched_rule == "construction_progress_draw_never_verified"
    assert record.revenue_confidence_score == 0.50 and not record.revenue_review_required
    assert "payer_remittance_descriptor" in record.revenue_reason and "Q11" in record.revenue_reason
    assert true_revenue_words.CONSTRUCTION_PROGRESS_DRAW_REASON in record.revenue_context_signals


def test_a_non_builder_s_remittance_descriptor_draw_keeps_its_verification():
    # Control: a developer is no builder (§17.1's follow-up), so §7.5's verification of its DRAW stands.
    assert _q11([(_q11_bofa("CONTOSO DEVELOPMENT LLC", "A P PMT DRAW 3"), 9000.0)]) == [
        ("verified", "payer_remittance_descriptor")]


def test_a_later_hold_still_wins_over_a_builder_s_progress_draw():
    # C9: the account also pays the builder: the payer-also-debited hold (a later hold) names the row, now that DRAW
    # holds nothing.
    assert _q11([(_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3"), 9000.0),
                 ("CONTOSO BUILDERS INC DES:PAYMENT ID:1 CO ID:1 PPD", -2000.0)]) == [
        ("excluded_pending_review", "payer_also_debited")]


def test_a_zelle_draw_from_a_builder_is_q3_s_never_a_progress_draw():
    # Z1 (CR7): the rules hold it as a non-sale purpose (never a progress draw); Q3's policy excludes it.
    records = _q11_records([("ZELLE PAYMENT FROM CONTOSO BUILDERS INC FOR DRAW 3 CONF ABC123", 9000.0)])
    assert [rules_reading(record, method=True) for record in records] == [NON_SALE]
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("non_revenue", "zelle_excluded")


@pytest.mark.parametrize(("text", "region", "expected"), [
    (_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3"), "CONTOSO BUILDERS INC", True),
    (_q11_bofa("CONTOSO BUILDERS INC", "DRAWDOWN"), "CONTOSO BUILDERS INC", False),
    (_q11_bofa("CONTOSO BUILDERS INC", "LOAN DRAW"), "CONTOSO BUILDERS INC", False),
    (_q11_bofa("CONTOSO BUILDERS INC", "DRAW ON THE LINE"), "CONTOSO BUILDERS INC", False),
    (_q11_bofa("CONTOSO BUILDERS INC", "PAYMENT"), "CONTOSO BUILDERS INC", False),
    (_q11_bofa("QUICK DRAW CONSTRUCTION LLC", "PAYMENT"), "QUICK DRAW CONSTRUCTION LLC", False),
    (_q11_bofa("CONTOSO BUILDERS SUPPLY INC", "DRAW 3"), "CONTOSO BUILDERS SUPPLY INC", False),
    (_q11_bofa("CONTOSO BUILDERS INSURANCE CO", "DRAW 3"), "CONTOSO BUILDERS INSURANCE CO", False),
    (_q11_bofa("CONTOSO FUNERAL HOMES INC", "DRAW 3"), "CONTOSO FUNERAL HOMES INC", False),
    (_q11_bofa("CONTOSO HOMES FOR SALE LLC", "DRAW 3"), "CONTOSO HOMES FOR SALE LLC", False),
    (_q11_bofa("CONTOSO BUILDING CO", "DRAW 3"), "CONTOSO BUILDING CO", False),
    (_q11_bofa("CONTOSO DEVELOPMENT LLC", "DRAW 3"), "CONTOSO DEVELOPMENT LLC", False),
    (_q11_bofa("CONTOSO CONSTRUCTION LENDING LLC", "DRAW 3"), "CONTOSO CONSTRUCTION LENDING LLC", False),
    (_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3"), "", False),
    ("ZELLE PAYMENT FROM CONTOSO BUILDERS INC FOR DRAW 3 CONF ABC123", "CONTOSO BUILDERS INC", False),
    # Review round 1: a realty firm, and a commission draw.
    (_q11_bofa("CONTOSO HOMES REALTY LLC", "DRAW"), "CONTOSO HOMES REALTY LLC", False),
    (_q11_bofa("CONTOSO BUILDERS REAL ESTATE LLC", "DRAW 3"), "CONTOSO BUILDERS REAL ESTATE LLC", False),
    (_q11_bofa("CONTOSO HOMES INC", "COMM DRAW"), "CONTOSO HOMES INC", False),
    (_q11_bofa("CONTOSO HOMES INC", "COMMISSIONS DRAW"), "CONTOSO HOMES INC", False),
])
def test_the_progress_draw_reader(text, region, expected):
    assert true_revenue_purpose.construction_progress_draw(revenue_text(normalize_transaction_description(text)), region) is expected


def test_a_builder_s_progress_draw_spares_draw_alone_in_the_non_sale_test():
    text = revenue_text(normalize_transaction_description(_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3")))
    assert true_revenue_purpose.non_sale_purpose(text, "CONTOSO BUILDERS INC")
    assert not true_revenue_purpose.non_sale_purpose(text, "CONTOSO BUILDERS INC", progress_draw=True)
    # Every other non-sale word still holds the row.
    refund = revenue_text(normalize_transaction_description(_q11_bofa("CONTOSO BUILDERS INC", "DRAW 3 REFUND")))
    assert true_revenue_purpose.non_sale_purpose(refund, "CONTOSO BUILDERS INC", progress_draw=True)
    assert analysis_revenue.REVENUE_TIER_REASONS["construction_progress_draw"] == ("counted_flagged", "Builder's progress draw")


# Audit round 3, R3-B15 (R3-08; the underwriter's Q11 (a) of 2026-10-02, "a builder's progress draw (ACME BUILDERS DRAW
# 3) counts, flagged, when the payer is a builder, not a lender and not the business's own loan"; §2.1's Q11 row, "a
# DRAW printed only inside the payer's own name ... keep(s) today's reading"): a row that prints no payer-name field (no
# DES, ORIG CO NAME, wire or FROM label: Wells Fargo, Citizens, TD Bank and Huntington print the originator and the
# entry in one run, Truist the receiver too) prints its entry inside the payer region. There the entry's CONST DRAW or
# CONSTRUCTION DRAW is the draw's purpose, never the payer's builder word; DRAW is read only after the builder word (one
# printed before it is inside the payer's name); and the holder's own builder word is never the payer's. A row these
# refuse keeps its reading before the ruling, held non_sale_purpose as its Bank of America DES twin is. The lender names
# are fabricated: a root-less lender's cut name (FABRIKAM AMERICA), a private-money lender's (SAMPLE PRIVATE M).

R3_08_BANKS = ("Wells Fargo", "Citizens Bank", "TD Bank", "Huntington National Bank", "Truist", "Sample Community Bank")
R3_08_AMOUNT = 31750.0


@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize("text", [
    # A root-less lender, a private-money lender, a developer, a property firm and a county, each with the entry CONST
    # DRAW in a sixteen-character name field's row (§17.1: a developer's and a county's draws are held).
    "FABRIKAM AMERICA CONST DRAW 540503 7788 NORTHWIND SOLAR",
    "SAMPLE PRIVATE M CONST DRAW 540503 7788 NORTHWIND SOLAR",
    "CONTOSO DEVELOPM CONST DRAW 540503 7788 NORTHWIND SOLAR",
    "CONTOSO PROPERTI CONST DRAW 540503 7788 NORTHWIND SOLAR",
    "SAMPLE COUNTY CONST DRAW 540503 7788 NORTHWIND SOLAR",
    # The entry printed whole (TD prints CONSTRUCTION DRAW), and TD's own layout.
    "FABRIKAM AMERICA CONSTRUCTION DRAW 540503 7788 NORTHWIND SOLAR",
    "CCD DEPOSIT, FABRIKAM AMERICA CONST DRAW 7788",
])
def test_r3_08_a_label_less_construction_draw_names_no_builder(text, bank):
    # Today counted as construction_progress_draw: the entry's CONST or CONSTRUCTION made any payer a builder.
    assert _q11([(text, R3_08_AMOUNT)], bank=bank) == [NON_SALE]


@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize(("label_less", "des_twin"), [
    # A DRAW printed before the builder word is inside the payer's name: the row reads as its Bank of America DES twin.
    ("QUICK DRAW CONST PAYMENT 540503 7788 NORTHWIND SOLAR", _q11_bofa("QUICK DRAW CONST", "PAYMENT")),
    ("SURE DRAW CONTRACTORS INC PAYMENT 540503 7788 NORTHWIND SOLAR",
     _q11_bofa("SURE DRAW CONTRACTORS INC", "PAYMENT")),
])
def test_r3_08_a_draw_inside_a_label_less_payer_s_name_reads_as_its_des_twin(label_less, des_twin, bank):
    assert _q11([(des_twin, R3_08_AMOUNT)]) == [NON_SALE]
    assert _q11([(label_less, R3_08_AMOUNT)], bank=bank) == [NON_SALE]


def test_r3_08_the_holder_s_own_builder_word_is_never_the_payer_s():
    # Truist prints the entry, the originator and the receiver in one run: the holder's CONSTRUCTION names no builder.
    text = "DRAW FABRIKAM AMERICA NORTHWIND CONSTRUCTION LLC CUSTOMER ID 0000"
    assert _q11([(text, R3_08_AMOUNT)], "NORTHWIND CONSTRUCTION LLC", bank="Truist") == [NON_SALE]
    assert not true_revenue_purpose.construction_progress_draw(
        revenue_text(normalize_transaction_description(text)), "DRAW FABRIKAM AMERICA NORTHWIND CONSTRUCTION LLC",
        "NORTHWIND CONSTRUCTION LLC")


@pytest.mark.parametrize("bank", (*R3_08_BANKS, "Mission Valley Bank"))
@pytest.mark.parametrize("text", [
    # Controls: a builder named before its DRAW on a label-less row still counts.
    "CONTOSO BUILDERS INC DRAW 4 540503 7788 NORTHWIND SOLAR",
    "CONTOSO HOMEBUILDERS DRAW 2 540503 7788 NORTHWIND SOLAR",
    "CONTOSO CONSTRUCTION LLC CONST DRAW 540503 7788 NORTHWIND SOLAR",
    # The corpus pin (A5): the builder's BUILD GROUP name, its DRAW after it.
    "DRAW12 FABRIKAM BUILD GROUP INC PROJECT NAME CONTOSO HOUSING PHASE B DRAW 12",
])
def test_r3_08_a_label_less_builder_s_draw_still_counts(text, bank):
    assert _q11([(text, R3_08_AMOUNT)], bank=bank) == [DRAW_COUNTED]


def test_r3_08_a_lender_the_account_also_debits_stays_held_as_one():
    rows = [("FABRIKAM AMERICA CONST DRAW 540503 7788 NORTHWIND SOLAR", R3_08_AMOUNT),
            ("FABRIKAM AMERICA LOAN PMT 540601 7788 NORTHWIND SOLAR", -2100.0)]
    assert _q11(rows, bank="Wells Fargo") == [("excluded_pending_review", "payer_debited_as_lender")]


@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize(("name", "entry"), [
    ("CONTOSO CONSTRUCTION", "DRAW 3"),
    # R3-B15 review round 1 (finding 3): the cut spellings a sixteen-character originator field prints.
    ("CONTOSO CONST", "DRAW 2"), ("CONTOSO CONSTR", "DRAW 2"),
    # R3-B15 review round 1 (finding 4): BUILD before DRAW is the entry's purpose phrase too.
    ("CONTOSO BUILD", "DRAW 2"),
])
def test_r3_08_residual_a_label_less_builder_named_with_a_phrase_word_and_a_bare_draw_is_held(name, entry, bank):
    # Recorded residual (§8.1, §20; 0 corpus rows): on a label-less row '<NAME> CONSTRUCTION', '<NAME> CONST',
    # '<NAME> CONSTR' or '<NAME> BUILD' with no company form before a bare DRAW cannot be told from the entry's purpose
    # phrase, so it is held (conservative, reviewable); its Bank of America DES twin, which prints the name field,
    # counts.
    assert _q11([(f"{name} {entry} 540503 7788 NORTHWIND SOLAR", R3_08_AMOUNT)], bank=bank) == [NON_SALE]
    assert _q11([(_q11_bofa(name, entry), R3_08_AMOUNT)]) == [DRAW_COUNTED]


# R3-B15 review round 1 (finding 2; Q11 (a), "Count as true revenue and flag it"): Truist prints the entry first
# ('<entry> <company field> <receiver> CUSTOMER ID'), so a builder's entry CONST DRAW prints before the builder's name.
# The DRAW of a purpose phrase printed before the builder word is the entry's, never inside the payer's name, so the
# builder's draw counts, as it did before R3-08; a payer with no builder word of its own stays held.

@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize("text", [
    "CONST DRAW CONTOSO BUILDERS INC NORTHWIND SOLAR LLC CUSTOMER ID 0000",
    "CONSTRUCTION DRAW CONTOSO HOMEBUILDERS NORTHWIND SOLAR LLC CUSTOMER ID 0000",
    "CONSTR DRAW CONTOSO CONSTRUCTION LLC NORTHWIND SOLAR LLC CUSTOMER ID 0000",
    "BUILD DRAW CONTOSO BUILDERS INC NORTHWIND SOLAR LLC CUSTOMER ID 0000",
])
def test_r3_08_review_round_1_a_builder_s_draw_on_the_entry_first_layout_counts(text, bank):
    assert _q11([(text, R3_08_AMOUNT)], bank=bank) == [DRAW_COUNTED]


@pytest.mark.parametrize(("text", "holder"), [
    # A root-less lender's entry-first draw: the holder's own builder word, whole or cut, is never the payer's.
    ("CONST DRAW FABRIKAM AMERICA NORTHWIND CONSTRUCTION LLC CUSTOMER ID 0000", "NORTHWIND CONSTRUCTION LLC"),
    ("CONST DRAW FABRIKAM AMERICA NORTHWIND CONSTR CUSTOMER ID 0000", "NORTHWIND CONSTRUCTION LLC"),
    # A county names no builder.
    ("CONST DRAW SAMPLE COUNTY NORTHWIND SOLAR LLC CUSTOMER ID 0000", SOLAR),
])
def test_r3_08_review_round_1_an_entry_first_draw_with_no_builder_stays_held(text, holder):
    assert _q11([(text, R3_08_AMOUNT)], holder, bank="Truist") == [NON_SALE]


@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize("text", [
    # R3-B15 review round 1 (finding 4): a root-less lender's entry BUILD DRAW names no builder either.
    "FABRIKAM AMERICA BUILD DRAW 540503 7788 NORTHWIND SOLAR",
    "FABRIKAM AMERICA BUILD DRAWS 540503 7788 NORTHWIND SOLAR",
])
def test_r3_08_review_round_1_a_label_less_build_draw_names_no_builder(text, bank):
    assert _q11([(text, R3_08_AMOUNT)], bank=bank) == [NON_SALE]


@pytest.mark.parametrize(("region", "builder"), [
    ("FABRIKAM AMERICA CONST DRAW", None),
    ("FABRIKAM AMERICA CONSTRUCTION DRAWS", None),
    ("CONTOSO CONSTR DRAW", None),
    ("CONTOSO CONSTRUCTION LLC CONST DRAW", "CONSTRUCTION"),
    ("CONTOSO BUILDERS INC DRAW", "BUILDERS"),
    ("QUICK DRAW CONST PAYMENT", "CONST"),
    # R3-B15 review round 1 (findings 2 and 4).
    ("FABRIKAM AMERICA BUILD DRAW", None),
    ("CONTOSO BUILD GROUP INC DRAW", "BUILD"),
    ("BUILD DRAW CONTOSO BUILDERS INC", "BUILDERS"),
    ("CONST DRAW CONTOSO BUILDERS INC", "BUILDERS"),
])
def test_r3_08_the_label_less_builder_word(region, builder):
    found = true_revenue_purpose._label_less_builder_word(region)
    assert (found.group(0) if found is not None else None) == builder


@pytest.mark.parametrize(("row", "draw"), [
    # R3-B15 review round 1 (finding 2): the purpose reads a DRAW after the builder word, or one of a purpose phrase
    # printed before it; never one inside the payer's name.
    ("CONTOSO BUILDERS INC DRAW 4", True),
    ("CONST DRAW CONTOSO BUILDERS INC NORTHWIND SOLAR LLC", True),
    ("CONSTRUCTION DRAWS CONTOSO HOMES NORTHWIND SOLAR LLC", True),
    ("QUICK DRAW CONST PAYMENT", False),
    ("SURE DRAW CONTRACTORS INC PAYMENT", False),
    ("DRAW FABRIKAM CONTOSO BUILDERS INC", False),
    # R3-B15 review round 2 (finding 2): only a phrase that starts the region is the entry-first entry; one printed
    # after the payer's name lends no DRAW to a later builder word.
    ("  CONST DRAW CONTOSO BUILDERS INC NORTHWIND SOLAR LLC", True),
    ("FABRIKAM AMERICA CONST DRAW CONTRACTOR PMT", False),
    ("SAMPLE COUNTY CONST DRAW BUILDER PMT", False),
    ("FABRIKAM AMERICA BUILD DRAW CONTRACTOR", False),
])
def test_r3_08_the_label_less_draw_purpose(row, draw):
    builder = true_revenue_purpose._label_less_builder_word(row)
    assert (true_revenue_purpose._DRAW_WORD.search(true_revenue_purpose._label_less_draw_purpose(row, row, builder)) is not None) is draw


# R3-B15 review round 2 (finding 2; R3-08's own target payers): the entry-first reading of review round 1 reads only a
# draw's purpose phrase that starts the payer region (Truist's '<entry> <company field> <receiver> CUSTOMER ID'). A
# root-less lender's, a county's or a developer's '<NAME> CONST DRAW' followed by any later builder word in the payer
# region names no builder: the phrase is that payer's entry, the later word no builder's name, so the row keeps its
# reading before the ruling, held non_sale_purpose, as its Bank of America DES twin does.

@pytest.mark.parametrize("bank", R3_08_BANKS)
@pytest.mark.parametrize("text", [
    "FABRIKAM AMERICA CONST DRAW CONTRACTOR PMT 540503 7788 NORTHWIND SOLAR",
    "SAMPLE COUNTY CONST DRAW BUILDER PMT 540503 7788 NORTHWIND SOLAR",
    "CONTOSO DEVELOPM CONST DRAW BUILDERS 540503 7788 NORTHWIND SOLAR",
    "FABRIKAM AMERICA CONST DRAW NORTHWIND HOMES 540503 7788 NORTHWIND SOLAR",
    "FABRIKAM AMERICA BUILD DRAW CONTRACTOR 540503 7788 NORTHWIND SOLAR",
])
def test_r3_08_review_round_2_a_phrase_after_the_payer_s_name_lends_no_draw_to_a_later_builder_word(text, bank):
    assert _q11([(text, R3_08_AMOUNT)], bank=bank) == [NON_SALE]


# Audit round 3, R3-B15 (R3-59; the underwriter's Q11 (b) of 2026-10-02, "Don't count as true revenue and go straight to
# non-revenue"; standard G6 and §4.2, deposits arrive net of fees): a fee or a commission printed beside a sale with a
# netting word (withheld, deducted, netted; net of, less, after, minus) is what the seller's proceeds are net of, never
# a broker's earned fee, so a non-dealer's printed sale is non_revenue / asset_sale_proceeds as its plain twin is. A
# bare commission or fee next to the sale stays a broker's revenue (R2-OW06 review round 1).

FLORIST = "NORTHWIND FLORIST LLC"
ASSET_SALE = ("non_revenue", "asset_sale_proceeds")
R3_59_AMOUNT = 27500.0


def _r3_59_chase_wire(purpose: str, holder: str = FLORIST) -> str:
    return ("FEDWIRE CREDIT VIA CONTOSO BANK/123456789 B/O: FABRIKAM FREIGHT LLC SAMPLEVILLE CA 12345 REF: CHASE NYC/"
            f"CTR/BNF={holder} SAMPLEVILLE WA 12345-1234 US/AC-000000001234 RFB=NOTPROVIDED "
            f"OBI={purpose} IMAD: 0102ABCDEF12000123 TRN: 1234567890FF")


def _r3_59(purpose: str, layout: str, zelle: bool, holder: str = FLORIST):
    """A one-credit month (a florist's unless `holder` says otherwise): FABRIKAM FREIGHT LLC's wire printing `purpose`,
    on Bank of America's PMT DET or Chase's Fedwire OBI layout, under the Zelle setting `zelle`."""
    if layout == "bofa":
        return _q11([(_q11_wire("FABRIKAM FREIGHT LLC", purpose), R3_59_AMOUNT)], holder, zelle_true_revenue=zelle)
    return _q11([(_r3_59_chase_wire(purpose, holder), R3_59_AMOUNT)], holder, bank="Chase", zelle_true_revenue=zelle)


@pytest.mark.parametrize("zelle", [False, True], ids=["zelle-no", "zelle-yes"])
@pytest.mark.parametrize("layout", ["bofa", "chase"])
@pytest.mark.parametrize("purpose", [
    "TRUCK SALE FEES WITHHELD", "TRAILER SALE FEES DEDUCTED", "TRUCK SALE FEES NETTED", "LESS FEES TRUCK SALE",
    "NET OF FEES TRUCK SALE", "NET FEES TRUCK SALE", "AFTER FEES TRUCK SALE", "TRUCK SALE COMMISSION DEDUCTED",
    "TRUCK SALE COMM WITHHELD", "LESS COMMISSION TRUCK SALE", "NET OF COMMISSION TRUCK SALE",
])
def test_r3_59_a_sale_printed_net_of_a_fee_or_commission_is_still_a_sale(purpose, layout, zelle):
    # Today counted (named_payer_purpose_refused, or wire_named_sender for COMM WITHHELD).
    assert _r3_59(purpose, layout, zelle) == [ASSET_SALE]


@pytest.mark.parametrize("zelle", [False, True], ids=["zelle-no", "zelle-yes"])
@pytest.mark.parametrize("layout", ["bofa", "chase"])
@pytest.mark.parametrize(("purpose", "expected"), [
    # A broker's or an agent's commission or fee next to the sale stays its earned revenue.
    ("TRUCK SALE COMMISSION", REFUSED), ("COMMISSION ON TRUCK SALE", REFUSED), ("TRUCK SALE FEE", REFUSED),
    ("FEE FOR TRUCK SALE", REFUSED),
    # A fee or a commission printed apart, and the plain sale, stay asset-sale proceeds.
    ("TRUCK SALE NET OF FEES", ASSET_SALE), ("TRUCK SALE LESS COMMISSION", ASSET_SALE), ("TRUCK SALE", ASSET_SALE),
])
def test_r3_59_a_broker_s_commission_and_a_fee_printed_apart_keep_their_readings(purpose, expected, layout, zelle):
    assert _r3_59(purpose, layout, zelle) == [expected]


@pytest.mark.parametrize("zelle", [False, True], ids=["zelle-no", "zelle-yes"])
@pytest.mark.parametrize("layout", ["bofa", "chase"])
@pytest.mark.parametrize("purpose", [
    # R3-B15 review round 1 (finding 1; R2-OW06 review round 1's broker carve-out, standard A11): a broker's or an
    # agent's net commission is its own earned commission after splits, never what a seller's proceeds are net of, and
    # so is a bare NET FEE.
    "NET COMMISSION ON TRUCK SALE", "NET COMMISSION TRUCK SALE", "NET COMMISSIONS FOR EQUIPMENT SALE",
    "AGENT NET COMMISSION TRUCK SALE", "BROKER NET COMMISSION ON EQUIPMENT SALE",
    "NET COMMISSION ON SALE OF 2050 TRUCK", "NET COMMISSION CAR SALE", "NET FEE FOR TRUCK SALE",
])
def test_r3_59_review_round_1_a_net_commission_stays_a_broker_s_revenue(purpose, layout, zelle):
    assert _r3_59(purpose, layout, zelle) == [REFUSED]


def test_r3_59_a_platform_seller_payout_printing_net_of_fees_stays_asset_sale_proceeds():
    assert _q11([(_q11_bofa("RITCHIE BROS", "SELLER PMT NET OF FEES", holder=FLORIST), R3_59_AMOUNT)], FLORIST) == [
        ASSET_SALE]


@pytest.mark.parametrize(("after", "before", "vetoed"), [
    (" FEES WITHHELD", "", False), (" COMMISSION DEDUCTED", "", False), (" COMM WITHHELD", "", False),
    (" FEES DEDUCTIONS", "", False), (" FEES NETTED", "", False),
    ("", "LESS FEES ", False), ("", "NET OF COMMISSION ", False), ("", "MINUS FEES ON ", False),
    (" COMMISSION", "", True), (" FEE", "", True), (" FEES PAID", "", True),
    ("", "COMMISSION ON ", True), ("", "FEE FOR ", True), ("", "NETWORK FEES ", True),
    # R3-B15 review round 1 (finding 1): a bare NET reads only before FEES.
    ("", "NET FEES ", False), ("", "NET FEES FOR ", False),
    ("", "NET COMMISSION ON ", True), ("", "NET COMMISSION ", True), ("", "NET COMMISSIONS FOR ", True),
    ("", "AGENT NET COMMISSION ", True), ("", "NET FEE FOR ", True), ("", "NET FEE ", True),
    # R3-B15 review round 2 (finding 1): a commission word directly before the netting phrase, or the fees taken from
    # or off a commission, is a broker's own commission; a commission that is itself netted is not.
    ("", "COMMISSION LESS FEES ON ", True), ("", "COMMISSION NET OF FEES ", True), ("", "COMM LESS FEES ", True),
    ("", "AGENT COMMISSION AFTER FEES FOR ", True), ("", "NET COMMISSION LESS FEES ", True),
    ("", "COMMISSIONS MINUS FEES ", True), ("", "COMMISSION NET FEES ", True),
    (" FEES WITHHELD FROM COMMISSION", "", True), (" FEES DEDUCTED FROM COMMISSION", "", True),
    (" FEE DEDUCTED OFF COMM", "", True), (" FEES NETTED FROM AGENT COMMISSION", "", True),
    ("", "NET OF COMMISSION LESS FEES ", False), ("", "LESS COMMISSION AFTER FEES ", False),
    ("", "MINUS COMMISSIONS NET OF FEES ", False), (" FEES WITHHELD FROM PROCEEDS", "", False),
])
def test_r3_59_the_netting_words(after, before, vetoed):
    assert asset_sale._asset_sale_commission(after, before) is vetoed


R3_59_AGENCY = "NORTHWIND SALES AGENCY LLC"


@pytest.mark.parametrize("zelle", [False, True], ids=["zelle-no", "zelle-yes"])
@pytest.mark.parametrize("layout", ["bofa", "chase"])
@pytest.mark.parametrize("holder", [FLORIST, R3_59_AGENCY])
@pytest.mark.parametrize("purpose", [
    # R3-B15 review round 2 (finding 1; R2-OW06 review round 1's broker carve-out, standard A11): a seller's proceeds
    # never lead with or come out of a commission. A commission word printed directly before the netting phrase (a
    # broker's or an agent's commission less its fees) or the fees taken from a commission is the broker's own earned
    # commission, so the veto stays, as for the mirrors printed after the sale.
    "COMMISSION LESS FEES ON TRUCK SALE", "COMMISSION NET OF FEES TRUCK SALE", "COMM LESS FEES TRUCK SALE",
    "AGENT COMMISSION AFTER FEES FOR TRUCK SALE", "NET COMMISSION LESS FEES TRUCK SALE",
    "TRUCK SALE FEES WITHHELD FROM COMMISSION", "TRUCK SALE FEES DEDUCTED FROM COMMISSION",
    "TRUCK SALE COMMISSION LESS FEES", "TRUCK SALE COMMISSION NET OF FEES",
])
def test_r3_59_review_round_2_a_commission_the_fees_come_out_of_stays_a_broker_s_revenue(
        purpose, holder, layout, zelle):
    assert _r3_59(purpose, layout, zelle, holder) == [REFUSED]


@pytest.mark.parametrize("zelle", [False, True], ids=["zelle-no", "zelle-yes"])
@pytest.mark.parametrize("layout", ["bofa", "chase"])
@pytest.mark.parametrize("purpose", [
    # Controls: a commission that is itself netted, and fees withheld from the proceeds, are what a seller's proceeds
    # are net of, so the sale is read.
    "NET OF COMMISSION LESS FEES TRUCK SALE", "LESS COMMISSION AFTER FEES TRUCK SALE",
    "TRUCK SALE FEES WITHHELD FROM PROCEEDS",
])
def test_r3_59_review_round_2_a_netted_commission_is_still_a_seller_s_sale(purpose, layout, zelle):
    assert _r3_59(purpose, layout, zelle) == [ASSET_SALE]


@pytest.mark.parametrize(("text", "bank"), [
    # B7 review round 1: a purpose word before DISTRIB... is no name word, whatever formed name follows it.
    ("QUARTERLY DISTRIBUTION CONTOSO LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO DISTRIBUTION SAMPLE LLC Q1", None),
    ("WIRE TYPE WIRE IN DATE 540102 TIME 1234 ET TRN 1234 SEQ 1234 ORIG FABRIKAM HOLDINGS LLC ID 1 SND BK CONTOSO "
     "BANK ID 1 PMT DET 123 MEMBER DISTRIBUTION SAMPLE INC", "Bank of America"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO 12 DISTRIBUTION SAMPLE LLC", None),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO PARTNER DISTRIBUTION", None),
    # B7 review round 2: a tax, year-end, month, partnership or preferred distribution, and a period code.
    ("TAX DISTRIBUTION CONTOSO LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO YEAR END DISTRIBUTION SAMPLE LLC", None),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO DEC DISTRIBUTION SAMPLE LLC", None),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO PARTNERSHIP DISTRIBUTION SAMPLE LLC", None),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO SEMIANNUAL DISTRIBUTION SAMPLE LLC", None),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO PREFERRED DISTRIBUTION SAMPLE LLC", None),
    ("Q4 DISTRIBUTION SAMPLE LLC 540115 1234567", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO AB1234 DISTRIBUTION SAMPLE LLC", None),
])
def test_a_distribution_purpose_before_a_formed_name_still_holds(text, bank):
    assert _one(text, 1600.0, holder="NORTHWIND GRILL LLC", bank=bank) == NON_SALE


def test_a_distributor_s_formed_name_with_a_trade_word_is_still_a_name():
    assert _one("CONTOSO FOOD DISTRIBUTION GROUP LLC 1", 800.0, holder="NORTHWIND GRILL LLC") == UNLABELLED


@pytest.mark.parametrize("text", ["A1 DISTRIBUTION LLC 540115 1234567", "H2O DISTRIBUTION INC 540115 1234567"])
def test_a_distributor_s_name_word_with_a_digit_is_still_a_name(text):
    # B7 review round 2: a name word that holds a letter and is no period code (Q4, K1, FY...) is a name word.
    assert _one(text, 1600.0, holder="NORTHWIND GRILL LLC", bank="Wells Fargo") == UNLABELLED


def test_owner_money_and_loans_stay_out_of_true():
    for text in ("ONLINE TRANSFER FROM PAT SAMPLE OWNER CONTRIBUTION",
                 "CONTOSO BANK DES:LOAN DISBURSEMENT ID:1 INDN:NORTHWIND GRILL LLC CO ID:1234567890 CCD"):
        assert _records([(text, 5000.0)], holder="NORTHWIND GRILL LLC")[0].revenue_tier == "non_revenue"


def test_a_joint_stock_bank_or_company_is_no_stock():
    text = ("BOOK TRANSFER CREDIT B O CONTOSO JOINT STOCK COMPANY SAMPLEVILLE VN ORG FABRIKAM TRADING CO LTD OBI "
            "PAYMENT FOR GOODS")
    assert _one(text, 900.0) == WIRE


def test_stock_on_an_invoice_is_goods():
    assert _one("ZELLE PAYMENT FROM CONTOSO SUPPLY LLC INV 1234 STOCK AND FREIGHT", 900.0) == P2P
    assert _one("ZELLE PAYMENT FROM CONTOSO SUPPLY LLC FOR STOCK PURCHASE", 900.0) == NON_SALE


# I47: the holder's own name never holds a third party's payment.

@pytest.mark.parametrize("name", [
    "NORTHWIND DISTRIBUTION", "NORTHWIND CAPITAL", "NORTHWIND PAYROLL SERVICES", "NORTHWIND RETURNS",
    "NORTHWIND RETIREMENT HOMES", "NORTHWIND INVESTMENTS",
])
def test_the_holder_s_name_printed_without_a_label_holds_nothing(name):
    text = f"CONTOSO ACADEMY PAYMENT 540115 1234567 {name}"
    assert _one(text, 1500.0, holder=f"{name} LLC") == UNLABELLED


def test_the_holder_s_name_removal_never_reads_a_product_name():
    # An account name that is a product name names no holder: a bank's rewards credit stays held.
    assert holder_names._without_holder_name("BUSINESS REWARDS REDEMPTION", "BUSINESS REWARDS CHECKING") == (
        "BUSINESS REWARDS REDEMPTION")
    assert _one("REWARDS REDEMPTION CREDIT", 25.0, holder="BUSINESS REWARDS CHECKING")[0] == "excluded_pending_review"
    # The run and its prefixes of two words or more, the legal form printed or not.
    assert holder_names._without_holder_name("PAY NORTHWIND DISTRIBUTION LLC X", "NORTHWIND DISTRIBUTION LLC").split() == [
        "PAY", "X"]
    assert holder_names._without_holder_name("PAY NORTHWIND X", "NORTHWIND DISTRIBUTION LLC").split() == ["PAY", "NORTHWIND", "X"]


def test_a_payer_s_own_distribution_still_holds_beside_the_holder_s_name():
    assert _one("CONTOSO PARTNERS DES:DISTRIB ID:1 INDN:NORTHWIND DISTRIBUTION LLC CO ID:1 CCD", 1500.0,
                holder="NORTHWIND DISTRIBUTION LLC") == NON_SALE


# I09: DIR DEP is pay wording only with a sign of a person's pay.

def _payroll_debit():
    return ("CONTOSO PAYROLL SVC DES:PAYROLL ID:1", -1450.0)


def test_a_company_s_direct_deposit_settlement_to_a_business_is_counted():
    rows = [(f"FABRIKAM SVC DIR DEP 5401{day:02d} C1234567", 3500.0 + day) for day in (5, 12, 19, 26)]
    assert _tiers(rows, holder="NORTHWIND ROUTES LLC") == [UNLABELLED] * 4
    # The account reads as a business's by its own payroll when its name is a product name.
    assert _tiers([*rows, _payroll_debit()], holder="UNLIMITED CHECKING") == [UNLABELLED] * 4
    assert _tiers(rows, holder="BUSINESS CHECKING") == [UNLABELLED] * 4


def test_a_direct_deposit_payer_with_an_ach_form_verifies_under_q6():
    rows = [(f"FABRIKAM SVC DES:DIR DEP ID:{n} INDN:NORTHWIND ROUTES LLC CO ID:1234567890 CCD", 3500.0 + n)
            for n in (1, 2)]
    assert _tiers(rows, holder="NORTHWIND ROUTES LLC") == [REPEATS] * 2
    entry = "CONTOSO DES:DIRECT DEPOSIT ID:1 INDN:NORTHWIND ROUTES LLC CO ID:1234567890 CCD"
    assert _one(entry, 2500.0, holder="NORTHWIND ROUTES LLC")[0] == "counted_flagged"


@pytest.mark.parametrize(("text", "holder"), [
    # A person named after the deposit's references (Wells Fargo's layout).
    ("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "CONTOSO BAKERY LLC"),
    # B7 review round 1: a reference, or a trace label and its number, printed after the person's name.
    ("FABRIKAM INC DIR DEP 540115 1234567 PAT SAMPLE 123456", "NORTHWIND ROUTES LLC"),
    ("FABRIKAM INC DIR DEP 540115 1234567 PAT SAMPLE TRN 1234", "NORTHWIND ROUTES LLC"),
    ("FABRIKAM INC DIR DEP 540115 1234567 PAT SAMPLE TRACE 1234 REF 12", "NORTHWIND ROUTES LLC"),
    # A person in the receiver field, on a consumer (PPD) entry.
    ("CONTOSO HEALTH DES:DIR DEP ID:1 INDN:PAT SAMPLE CO ID:1234567890 PPD", "NORTHWIND ROUTES LLC"),
    ("CONTOSO DES:DIRECT DEPOSIT ID:1 INDN:PAT SAMPLE CO ID:1234567890 PPD", "NORTHWIND ROUTES LLC"),
    # A payroll provider.
    ("ADP DIR DEP 540105 C1234567", "NORTHWIND ROUTES LLC"),
    # An account that reads as a person's (no legal form, no business product, no payroll of its own).
    ("CONTOSO DIR DEP 540105 C1234567", "PAT SAMPLE"),
    ("CONTOSO DIR DEP 540105 C1234567", "UNLIMITED CHECKING"),
    ("CONTOSO DIR DEP 540105 C1234567", None),
])
def test_a_direct_deposit_to_a_person_is_still_pay(text, holder):
    assert _one(text, 1700.0, holder=holder) == PAY


def test_the_holder_s_own_name_after_the_references_is_no_person():
    assert _one("FABRIKAM INC DIR DEP 540115 1234567 NORTHWIND ROUTES", 2500.0, holder="NORTHWIND ROUTES LLC") == (
        UNLABELLED)
    assert _one("FABRIKAM INC DIR DEP 540115 1234567 NORTHWIND ROUTES 123456", 2500.0,
                holder="NORTHWIND ROUTES LLC") == UNLABELLED
    # A company's settlement with its trace label after the references is no person either.
    assert _one("FABRIKAM SVC DIR DEP 540105 C1234567 TRN 1234", 2500.0, holder="NORTHWIND ROUTES LLC") == UNLABELLED


def test_g11_reads_the_direct_deposit_words_with_the_row_s_own_sign():
    def fact(text, holder):
        record = _records([(text, 1700.0)], holder=holder)[0]
        return guards.guard_facts(record, revenue_text(normalize_transaction_description(text)))["pay_or_personal"]

    assert fact("FABRIKAM SVC DIR DEP 540105 C1234567", "NORTHWIND ROUTES LLC") is False
    assert fact("FABRIKAM INC DIR DEP 540115 1234567 JOHN SMITH", "NORTHWIND ROUTES LLC") is True
    assert fact("FABRIKAM INC DES:PAYROLL ID:1", "NORTHWIND ROUTES LLC") is True


def test_q7_still_refuses_a_direct_deposit_word():
    record = _records([("WESTLAKE FINANCI DES:PAYABLES DIR DEP ID:1", 15000.0)], holder="SAMPLE MOTORS LLC")[0]
    assert record.revenue_match_method != "auto_lender_dealer_funding"


# I36: a credit union's dealer funding.

_CHASE_CU = ("ORIG CO NAME:{cu} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry}SEC:CCD "
             "TRACE#:123456789012345 EED:540102 IND ID:{deal} IND NAME:NORTHWIND TRUCKS {words} TRN: 1234567890TC")
_TRUCKS = "NORTHWIND TRUCKS LLC"


def _cu(cu, entry, deal, words="VEHICLE PURCHASE"):
    return _CHASE_CU.format(cu=cu, entry=entry, deal=deal, words=words)


def test_a_credit_union_s_admin_fee_verifies_beside_its_verified_vehicle_purchases():
    rows = [
        (_cu("CONTOSO CU", "VHCL PURCH", "DL0001AB"), 6100.0),
        (_cu("CONTOSO CU", "VADMIN FEE", "DL0001AB", "VEHICLE ADMIN FEE"), 180.0),
        (_cu("CONTOSO CU", "VHCL PURCH", "DL0002AB"), 5300.0),
        (_cu("CONTOSO CU", "VADMIN FEE", "DL0003AB", "VEHICLE ADMIN FEE"), 150.0),
    ]
    assert _tiers(rows, holder=_TRUCKS) == [DEALER] * 4


def test_an_admin_fee_matching_a_verified_deal_s_id_verifies():
    # The credit union prints its name another way on the fee; the deal's ID is the verified purchase's.
    rows = [
        (_cu("CONTOSO CU", "VHCL PURCH", "DL0001AB"), 6100.0),
        (_cu("FABRIKAM FCU", "VHCL PURCH", "DL0002AB"), 5300.0),
        (_cu("CONTOSO FCU", "VADMIN FEE", "DL0001AB", "VEHICLE ADMIN FEE"), 180.0),
    ]
    assert _tiers(rows, holder=_TRUCKS) == [DEALER] * 3
    # A name that reads as no credit union is never the arm's, whatever its ID.
    cut = [*rows[:2], (_cu("CONTOSO CREDIT UNI", "VADMIN FEE", "DL0001AB", "VEHICLE ADMIN FEE"), 180.0)]
    assert _tiers(cut, holder=_TRUCKS) == [DEALER, DEALER, FINANCING]


def test_an_admin_fee_with_no_verified_vehicle_purchase_stays_held():
    lone = [(_cu("CONTOSO CU", "VADMIN FEE", "DL0001AB", "VEHICLE ADMIN FEE"), 180.0)]
    assert _tiers(lone, holder=_TRUCKS) == [FINANCING]
    one_purchase = [(_cu("CONTOSO CU", "VHCL PURCH", "DL0001AB"), 6100.0),
                    (_cu("CONTOSO CU", "VADMIN FEE", "DL0001AB", "VEHICLE ADMIN FEE"), 180.0)]
    assert _tiers(one_purchase, holder=_TRUCKS) == [FINANCING, FINANCING]
    # Another credit union's admin fee with another deal's ID.
    other = [(_cu("CONTOSO CU", "VHCL PURCH", "DL0001AB"), 6100.0),
             (_cu("CONTOSO CU", "VHCL PURCH", "DL0002AB"), 5300.0),
             (_cu("FABRIKAM CU", "VADMIN FEE", "DL0009AB", "VEHICLE ADMIN FEE"), 180.0)]
    assert _tiers(other, holder=_TRUCKS) == [DEALER, DEALER, FINANCING]


def test_a_glued_credit_union_acronym_is_a_credit_union():
    rows = [
        (_cu("CONTOSO CU", "VHCL PURCH", "DL0001AB"), 6100.0),
        (_cu("FABRIKAM FCU", "VHCL PURCH", "DL0002AB"), 5300.0),
        (_cu("BECU", "VHCL PURCH", "DL0004CD"), 3200.0),
    ]
    assert _tiers(rows, holder=_TRUCKS) == [DEALER] * 3
    assert _tiers([(_cu("BECU", "VHCL PURCH", "DL0004CD"), 3200.0)], holder=_TRUCKS) == [FINANCING]
    for acronym in ("BECU", "SECU", "PSECU", "GECU", "DCU", "ABFCU"):
        assert true_revenue_words._CREDIT_UNION_PAYER.search(acronym)
    for word in ("CUSTOM", "CUBE", "ACCUPAY"):
        assert not true_revenue_words._CREDIT_UNION_PAYER.search(word)


_FEDWIRE = ("FEDWIRE CREDIT VIA CONTOSO CREDIT UNION/123456789 B/O: {sender} SAMPLEVILLE CA 12345 REF: CHASE NYC/CTR/"
            "BNF=NORTHWIND TRUCKS LLC SAMPLEVILLE WA 12345-1234 US/AC-000000001234 RFB=NOTPROVIDED OBI=UR I VEHICLE "
            "PURCHASE VIN 1 IMAD: 0102ABCDEF12000123 TRN: 1234567890FF")


def test_a_customer_s_vehicle_purchase_wire_is_counted():
    assert _one(_FEDWIRE.format(sender="PAT SAMPLE"), 3700.0, holder=_TRUCKS) == REFUSED
    assert _one(_FEDWIRE.format(sender="FABRIKAM MOTORS LLC"), 3700.0, holder=_TRUCKS) == REFUSED


@pytest.mark.parametrize("sender", ["FABRIKAM FLOORING LLC", "CONTOSO FLOORS AND MORE", "SAMPLE WHOLESALE GROCERS INC"])
def test_a_flooring_or_wholesale_trade_customer_s_vehicle_wire_is_counted(sender):
    # B7 review round 2: only a floor-plan form, or WHOLESALE beside a lender's or a vehicle trade's word, is a
    # floor-plan lender's name.
    assert _one(_FEDWIRE.format(sender=sender), 3700.0, holder=_TRUCKS) == REFUSED


@pytest.mark.parametrize("sender", [
    "FABRIKAM AUTO FINANCE LLC", "FABRIKAM CREDIT UNION",
    # B7 review round 1: a floor-plan (wholesale) lender's wire, whatever its name lacks of a root.
    "FABRIKAM FLOORPLAN LLC", "FABRIKAM WHOLESALE AUTO LLC",
])
def test_a_lender_s_or_credit_union_s_vehicle_purchase_wire_stays_held(sender):
    assert _one(_FEDWIRE.format(sender=sender), 3700.0, holder=_TRUCKS) == FINANCING
    dealer_payment = _FEDWIRE.format(sender=sender).replace("UR I VEHICLE PURCHASE", "DLR PMT")
    assert _one(dealer_payment, 3700.0, holder=_TRUCKS) == FINANCING


def test_an_unlisted_originator_s_dealer_entry_stays_held():
    assert _one("FABRIKAM AUTO DES:DEALER PAY ID:1", 15000.0, holder="SAMPLE MOTORS LLC") == FINANCING


# The orchestrator's delegated ruling (audit I57): a trust's payment citing the holder's service.

_SCHOOL = "NORTHWIND PREPARATORY SCHOOL"
_CHIPS = "CHIPS CREDIT VIA CITIBANK N A/0008 B/O: {sender} IL REF: NBNF=NORTHWIND PREPARATORY SCHOOL NEW YORK NY 10001{obi}"


@pytest.mark.parametrize("obi", [
    " OBI=URI SAMPLE CHILD TUITION",
    " OBI=URI SAMPLE CHILD TUITIO N BBI CHGS",
    " OBI=STUDENT ID 12345",
    " OBI=URI STUDENT ID 12345678 FOR SAMPLE",
])
def test_a_trust_s_tuition_wire_is_counted(obi):
    assert _one(_CHIPS.format(sender="PAT SAMPLE TTEE", obi=obi), 12000.0, holder=_SCHOOL) == WIRE
    assert _one(_CHIPS.format(sender="PAT SAMPLE FAMILY TRUST", obi=obi), 12000.0, holder=_SCHOOL) == WIRE


@pytest.mark.parametrize("obi", ["", " OBI=URI SSN 1234", " OBI=GIFT FOR SAMPLE"])
def test_a_trust_s_wire_with_no_service_purpose_stays_held(obi):
    assert _one(_CHIPS.format(sender="PAT SAMPLE TTEE", obi=obi), 12000.0, holder=_SCHOOL) == NON_SALE


_ACADEMY = "NORTHWIND ACADEMY LLC"
_TRUST_CHIPS = ("CHIPS CREDIT VIA CITIBANK N A/0008 B/O: SAMPLE FAMILY TRUST IL REF: NBNF=NORTHWIND ACADEMY LLC NEW YORK "
                "NY 10001{obi}")


@pytest.mark.parametrize("obi", [
    # Audit round 2, R2-B08 (R47 (c)): the ruling names TUITION and STUDENT ID only. The letters of TUITION inside
    # another word (INTUITION, a cross-word join INTUIT IONA) and STUDENT before IDEAS are no such purpose.
    " OBI=INTUITION RETREAT",
    " OBI=INTUIT IONA",
    " OBI=STUDENT IDEAS WORKSHOP",
    # Controls: a gift and no purpose stay held.
    " OBI=GIFT FOR SAMPLE",
    "",
])
def test_r47_a_trust_s_wire_citing_no_tuition_or_student_id_is_held(obi):
    assert _one(_TRUST_CHIPS.format(obi=obi), 12000.0, holder=_ACADEMY) == NON_SALE


@pytest.mark.parametrize("obi", [
    " OBI=TUITION SPRING",
    # A line wrap's split, and TUITION glued after a word, still cite it.
    " OBI=TUITIO N SPRING",
    " OBI=PAYMENT FORTUITION",
    " OBI=STUDENT ID 12345",
    " OBI=STUDENTID12345",
])
def test_r47_a_trust_s_wire_citing_tuition_or_a_student_id_is_still_counted(obi):
    assert _one(_TRUST_CHIPS.format(obi=obi), 12000.0, holder=_ACADEMY) == WIRE


@pytest.mark.parametrize("obi", [
    # Audit round 2, R2-B08 review round 1 (R47 (c); the I57 ruling reads the purpose with a line wrap's split joined):
    # a split inside STUDENT or ID, as TUITION's reader joins one, still cites a student ID.
    " OBI=STUDEN T ID 12345",
    " OBI=STU DENT ID 12345",
    " OBI=STUDENT I D 12345",
])
def test_r2_b08_review_a_trust_s_student_id_split_by_a_line_wrap_is_still_counted(obi):
    assert _one(_TRUST_CHIPS.format(obi=obi), 12000.0, holder=_ACADEMY) == WIRE


@pytest.mark.parametrize("obi", [
    # The ends stay whole words: a split never makes STUDENT IDEAS or STUDENT IDENTIFICATION a student ID.
    " OBI=STUDENT I DEAS WORKSHOP",
    " OBI=STUDENT IDENTIFICATION 12345",
    " OBI=STUDENTS ID 12345",
])
def test_r2_b08_review_a_split_never_makes_another_word_a_student_id(obi):
    assert _one(_TRUST_CHIPS.format(obi=obi), 12000.0, holder=_ACADEMY) == NON_SALE


def test_a_parent_s_tuition_wire_is_counted_as_before():
    assert _one(_CHIPS.format(sender="PAT SAMPLE", obi=" OBI=URI SAMPLE CHILD TUITION"), 12000.0,
                holder=_SCHOOL) == WIRE


def test_the_census_reads_a_released_trust_as_no_personal_trust():
    text = _CHIPS.format(sender="PAT SAMPLE TTEE", obi=" OBI=URI SAMPLE CHILD TUITION")
    record = _records([(text, 12000.0)], holder=_SCHOOL)[0]
    revenue = revenue_text(normalize_transaction_description(text))
    assert guards.guard_facts(record, revenue)["hold_rule"] != "personal_trust"
    held = _CHIPS.format(sender="PAT SAMPLE TTEE", obi="")
    record = _records([(held, 12000.0)], holder=_SCHOOL)[0]
    assert guards.guard_facts(record, revenue_text(normalize_transaction_description(held)))["hold_rule"] == (
        "personal_trust")


# Audit round 2, R2-B03 (R05 part C; Q6 "lenders never count", standard C2/C3): Northeast Bank, a national SBA lender
# the ledger lists by its repayment spellings only, is a lending bank on the credit side too (the registry's
# LENDING_BANK_CREDIT_PAYERS): its credit is held as financing, so a statement it dominates is sent to review.

_NORTHEAST = "PREAUTHORIZED CREDIT NORTHEAST BANK GTL 1234567 NORTHWIND PLUMBING LLC CCD"
_PLUMBER = "NORTHWIND PLUMBING LLC"


def test_a_northeast_bank_credit_is_held_as_financing_and_gates_its_statement():
    from analysis.metrics import compute_metrics

    statement = Statement(account_name=_PLUMBER, bank="", currency="USD", transactions=[
        Transaction(date="2054-03-02", description=_NORTHEAST, amount=250000.0, direction="credit"),
        Transaction(date="2054-03-03", description="ORIG CO NAME:CONTOSO SUPPLY LLC CO ENTRY DESCR:PAYMENT SEC:CCD",
                    amount=3000.0, direction="credit"),
    ])
    records = classify_statement_transactions(statement)
    assert [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) for record in records] == [
        FINANCING, COMPANY]
    assert compute_metrics(statement, classifications=records).revenue_review_required
    revenue = revenue_text(normalize_transaction_description(_NORTHEAST))
    assert guards.guard_facts(records[0], revenue)["hold_rule"] == "lending_bank"


@pytest.mark.parametrize(("text", "expected"), [
    # The ledger's SBA repayment spelling stays its financing proceeds, and its wire stays a bank's own wire.
    ("NORTHEAST BANK DES:SBA PYMT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 CCD",
     ("non_revenue", "financing_proceeds_credit")),
    ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHEAST BANK SAMPLEVILLE ME 12345 US REF SAMPLE NYC CTR BNF "
     "NORTHWIND PLUMBING LLC OBI 1234", FINANCING),
    # A payer whose name only starts like the lending bank is no lending bank. Audit round 3, R3-B07 (R3-14): its
    # BANKING is one of §8.5's bank words, so Q6 never verifies it by its company form: counted once.
    ("NORTHEAST BANKING SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 CCD", ONE_OFF),
])
def test_northeast_bank_s_other_spellings_keep_their_readings(text, expected):
    [record] = _records([(text, 50000.0)], holder=_PLUMBER, bank="Bank of America")
    assert (record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) == expected


# Audit round 2, R2-B04 (R40): the I47 strip reads every business name of the holder's (the account field's business
# beside the parser's holder name, each side of a DBA name), never a person's.

HOLDER_HELD = ("excluded_pending_review", "holder_name")
PERSONAL = ("excluded_pending_review", "personal_income")
VERIFIED = ("verified", "named_payer_company_form")
TRUIST_DEP = "ACH CORP DEP {payer} CUSTOMER ID 00012"
WF_PAYMENT = "FABRIKAM INC PAYMENT 000000 0000000 {receiver}"


def _r40(text, *, account_name, holder_name, bank):
    [record] = classify_statement_transactions(Statement(
        account_name=account_name, holder_name=holder_name, bank=bank,
        transactions=[Transaction(date="2054-03-02", description=text, amount=4200.0, direction="credit")],
    ))
    return record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method


@pytest.mark.parametrize("holder_name", ["JOHN SAMPLE", "JOHN SAMPLE DBA NORTHWIND CAPITAL LLC"])
def test_r40_the_account_field_s_business_is_stripped_beside_the_owner_s_name(holder_name):
    text = TRUIST_DEP.format(payer="FABRIKAM INC NORTHWIND CAPITAL")
    assert _r40(text, account_name="NORTHWIND CAPITAL LLC", holder_name=holder_name, bank="Truist") == VERIFIED


@pytest.mark.parametrize("business", ["NORTHWIND DISTRIBUTION", "NORTHWIND PAYROLL SERVICES",
                                      "NORTHWIND RETIREMENT ADVISORS"])
def test_r40_a_customer_paying_the_account_field_s_business_is_counted(business):
    text = WF_PAYMENT.format(receiver=business)
    assert _r40(text, account_name=f"{business} LLC", holder_name="JOHN SAMPLE", bank="Wells Fargo") == UNLABELLED


def test_r40_a_sole_proprietor_s_trade_name_is_stripped():
    text = TRUIST_DEP.format(payer="FABRIKAM INC NORTHWIND DISTRIBUTION")
    assert _r40(text, account_name="Checking", holder_name="JOHN SAMPLE DBA NORTHWIND DISTRIBUTION",
                bank="Truist") == VERIFIED
    text = WF_PAYMENT.format(receiver="NORTHWIND PAYROLL SERVICES")
    assert _r40(text, account_name="BUSINESS BANKING", holder_name="JOHN SAMPLE DBA NORTHWIND PAYROLL SERVICES",
                bank="First Citizens Bank")[0] == "counted_flagged"


@pytest.mark.parametrize(("text", "account_name", "holder_name", "bank", "expected"), [
    # A lender's own name keeps its financing word; a payroll payer and the owner's pay keep the pay hold.
    (TRUIST_DEP.format(payer="CONTOSO CAPITAL FUNDING"), "Checking", "JOHN SAMPLE DBA NORTHWIND DISTRIBUTION",
     "Truist", FINANCING),
    ("DIRECT DEP FABRIKAM INC PAYROLL JOHN SAMPLE CUSTOMER ID 00012", "Checking",
     "JOHN SAMPLE DBA NORTHWIND DISTRIBUTION", "Truist", PAY),
    ("FABRIKAM INC PAYROLL 000000 0000000 NORTHWIND DISTRIBUTION", "BUSINESS BANKING",
     "JOHN SAMPLE DBA NORTHWIND DISTRIBUTION", "First Citizens Bank", PAY),
    # The holder's own deposit stays the holder's.
    (TRUIST_DEP.format(payer="NORTHWIND DISTRIBUTION"), "Checking", "JOHN SAMPLE DBA NORTHWIND DISTRIBUTION",
     "Truist", HOLDER_HELD),
    # No parser holder: B7's strip of the account name, as before.
    (TRUIST_DEP.format(payer="FABRIKAM INC NORTHWIND CAPITAL"), "NORTHWIND CAPITAL LLC", None, "Truist", VERIFIED),
    # A person's name is never stripped beside the owner's own (the owner's pay from another company, Q8).
    ("DIRECT DEP FABRIKAM INC JOHN SAMPLE CUSTOMER ID 00012", "NAVIGATE BUSINESS CHECKING", "JOHN SAMPLE", "Truist",
     UNLABELLED),
])
def test_r40_controls_keep_their_holds(text, account_name, holder_name, bank, expected):
    assert _r40(text, account_name=account_name, holder_name=holder_name, bank=bank) == expected


@pytest.mark.parametrize(("account_name", "holder_name", "names"), [
    ("NORTHWIND CAPITAL LLC", "JOHN SAMPLE", ("NORTHWIND CAPITAL LLC",)),
    ("Checking", "JOHN SAMPLE DBA NORTHWIND DISTRIBUTION", ("NORTHWIND DISTRIBUTION",)),
    ("Checking", "CONTOSO LLC DBA NORTHWIND DISTRIBUTION", ("NORTHWIND DISTRIBUTION", "CONTOSO LLC")),
    # A person-shaped account field, a product and a one-word trade name add nothing.
    ("JANE SAMPLE", "JOHN SAMPLE", ()),
    ("Checking", "JOHN SAMPLE", ()),
    ("Checking", "JOHN SAMPLE DBA NORTHWIND", ()),
    ("NORTHWIND CAPITAL LLC", None, ()),
])
def test_r40_the_strip_names_are_the_holder_s_business_names(account_name, holder_name, names):
    [record] = classify_statement_transactions(Statement(
        account_name=account_name, holder_name=holder_name, bank="Truist",
        transactions=[Transaction(date="2054-03-02", description="CONTOSO DINER", amount=100.0, direction="credit")],
    ))
    assert holder_names._holder_strip_names(record) == names


# Audit round 2, R2-B12 (R42): RETIRE... inside a payer's own name is no personal income when an operator's word follows
# it (a retirement residence, community, village or home paying its vendor), or on TD Canada Trust when it ends the
# fifteen-character payer field TD cuts before an electronic-payment CPA code; a pension, an annuity, an entry or
# purpose word, a recordkeeper's or advisor's name and every other bank keep the hold.

TD = "TD Canada Trust"
ONE_OFF_CREDIT = ("counted_flagged", "named_payer_one_off")
_R42_BOFA = "{payer} DES:{entry} ID:1234 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 CCD"
_R42_CHASE = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540301 CO ENTRY DESCR:PAYMENT SEC:CCD "
              "TRACE#:123456789012345 EED:540301 IND ID:1234 IND NAME:NORTHWIND BAKERY LLC TRN: 1234567890TC")


def _r42(texts, bank):
    return _tiers([(text, 1500.0) for text in texts], bank=bank)


@pytest.mark.parametrize(("texts", "bank", "expected"), [
    (["CONTOSO RETIREM MSP"], TD, [ONE_OFF_CREDIT]),
    (["CONTOSO RETIREM MSP"] * 2, TD, [REPEATS, REPEATS]),
    (["SAMPLE RETIREME AP"], TD, [ONE_OFF_CREDIT]),
    ([_R42_BOFA.format(payer="SAMPLE RETIREMENT COMMUNITY LLC", entry="VENDOR")], "Bank of America", [COMPANY]),
    ([_R42_CHASE.format(payer="CONTOSO RETIREMENT VILLAGE CORP")], "Chase", [COMPANY]),
    ([_R42_BOFA.format(payer="FABRIKAM RETIREMENT HOMES", entry="PAYMENT")], "Bank of America", [ONE_OFF_CREDIT]),
])
def test_r42_a_retirement_operator_s_or_a_cut_payer_s_name_is_no_personal_income(texts, bank, expected):
    assert _r42(texts, bank) == expected


@pytest.mark.parametrize(("text", "bank"), [
    ("ABC RETIREMENT MSP", TD),
    ("CONTOSO RETIREM", TD),
    ("CONTOSO RETIREM MSP", "Bank of America"),
    ("CONTOSO PENSION MSP", TD),
    ("FABRIKAM ANNUITY SERVICES LTD MSP", TD),
    (_R42_BOFA.format(payer="CONTOSO RETIREMENT SERVICES LLC", entry="PAYMENT"), "Bank of America"),
    (_R42_BOFA.format(payer="FABRIKAM STATE RETIREMENT SYS", entry="ANNUITY"), "Bank of America"),
    (_R42_BOFA.format(payer="CONTOSO RETIREMENT ADVISORS INC", entry="INVOICE"), "Bank of America"),
    (_R42_BOFA.format(payer="CONTOSO INC", entry="RETIREMENT HOME"), "Bank of America"),
    (_R42_BOFA.format(payer="CONTOSO INC", entry="RETIREMENT"), "Bank of America"),
    ("SSA TREAS 310 DES:XXSOC SEC ID:123456789A INDN:PAT SAMPLE CO ID:1234567890 PPD", "Bank of America"),
])
def test_r42_controls_keep_the_personal_income_hold(text, bank):
    assert _r42([text], bank) == [PERSONAL]


def test_r42_the_pay_code_and_the_holder_s_own_name_keep_their_readings():
    assert _r42(["CONTOSO RETIREM PAY"], TD) == [PAY]
    text = "FABRIKAM SUPPLY INC DES:PAYMENT ID:1234 INDN:SAMPLE RETIREMENT HOMES LLC CO ID:1234567890 CCD"
    assert _tiers([(text, 1500.0)], holder="SAMPLE RETIREMENT HOMES LLC", bank="Bank of America") == [COMPANY]


@pytest.mark.parametrize(("text", "bank", "fact"), [
    ("CONTOSO RETIREM MSP", TD, False),
    ("SAMPLE RETIREME AP", TD, False),
    (_R42_BOFA.format(payer="SAMPLE RETIREMENT COMMUNITY LLC", entry="VENDOR"), "Bank of America", False),
    ("ABC RETIREMENT MSP", TD, True),
    ("CONTOSO RETIREM MSP", "Bank of America", True),
    ("CONTOSO PENSION MSP", TD, True),
    (_R42_BOFA.format(payer="CONTOSO RETIREMENT SERVICES LLC", entry="PAYMENT"), "Bank of America", True),
    (_R42_BOFA.format(payer="CONTOSO INC", entry="RETIREMENT HOME"), "Bank of America", True),
])
def test_r42_g11_reads_the_hold_s_own_spare(text, bank, fact):
    [record] = _records([(text, 1500.0)], bank=bank)
    assert guards.guard_facts(record, revenue_text(record.normalized_description))["pay_or_personal"] is fact


def test_r42_the_td_payer_field_s_width_is_fifteen_characters():
    assert public_payers._TD_PAYER_WIDTH == 15
    # Q7 reads no bank, so TD's cut never spares a word there (fail closed); an operator's word still does.
    assert public_payers._personal_income("CONTOSO RETIREM MSP", "CONTOSO RETIREM MSP")
    assert not public_payers._personal_income("CONTOSO RETIREM MSP", "CONTOSO RETIREM MSP", TD)


# Audit round 2, R2-B13 (R34): B7's I18 spares read DISTRIB... and STOCK as a name word only inside the payer's name
# proper (a wire's or an ACH originator's whole field; a transfer's FROM sender up to its company form, or, with no
# form, only when a label or a reference closes it), never after an earnings, liquidation or pro-rata word or a
# month-year code, and a street's name only after a street number: an owner's distribution printed as the purpose is
# held, a distributor's name is still a customer.

@pytest.mark.parametrize(("text", "bank"), [
    ("ONLINE TRANSFER FROM CONTOSO HOLDINGS LLC PROFIT DISTRIBUTION", "Wells Fargo"),
    ("ONLINE TRANSFER FROM CONTOSO HOLDINGS LLC DISTRIBUTION", "Wells Fargo"),
    ("TRANSFER FROM CONTOSO HOLDINGS LLC STOCK SALE PROCEEDS", "Mercury"),
    ("ONLINE TRANSFER FROM PAT SAMPLE DISTRIBUTION", "Wells Fargo"),
    ("TRANSFER IN FROM PAT SAMPLE PROFIT DISTRIBUTION", "Wealthsimple"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO EARNINGS DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO JAN54 DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    ("WIRE TYPE WIRE IN DATE 540102 TIME 1200 ET TRN 2054010200001 ORIG FABRIKAM HOLDINGS LLC ID 123 PMT DET EARNINGS "
     "DISTRIBUTION SAMPLE LLC", "Bank of America"),
    ("FABRIKAM HOLDINGS DISTRIBUTION ST-A1B2C3D4", "Wells Fargo"),
    ("FABRIKAM GRANT ST-A1B2C3D4", "Wells Fargo"),
    ("CONTOSO EQUITY DR 12345", "Wells Fargo"),
    ("SAMPLE REWARDS WAY 12345", "Wells Fargo"),
    # The stop-list's other new words and the month-year code's other spellings.
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO LIQUIDATING DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO PRORATA DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO SEPT54 DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO 15JAN DISTRIBUTION SAMPLE LLC", "Wells Fargo"),
    # A company form ends the sender's name proper, a closing label or not.
    ("ONLINE TRANSFER FROM CONTOSO LLC DISTRIBUTION REF IB0ABCDEF", "Wells Fargo"),
])
def test_r34_an_owner_distribution_outside_the_payer_s_name_proper_is_held(text, bank):
    assert _one(text, 5000.0, bank=bank) == NON_SALE


@pytest.mark.parametrize(("text", "bank", "expected"), [
    ("TRANSFER FROM CONTOSO DISTRIBUTION LLC", "Mercury", P2P),
    ("ZELLE PAYMENT FROM CONTOSO DISTRIBUTION CONF AB1234", "Bank of America", P2P),
    # The recorded residue: a sender a label closes is read as the account's name.
    ("ONLINE TRANSFER FROM CONTOSO PARTNERS DISTRIBUTION REF IB0ABCDEF ON 01 02 54", "Wells Fargo", P2P),
    ("ORIG CO NAME:CONTOSO DISTRIBUTIO ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:PAYMENT SEC:CCD "
     "TRACE#:123456789012345 EED:540102 IND ID:1 IND NAME:NORTHWIND BAKERY", "Chase", ONE_OFF),
    ("WT FED#01234 SAMPLE BANK /ORG=CONTOSO DISTRIBUTION SRF# 2054010200000 TRN#540102000001 RFB# INV 1234",
     "Wells Fargo", WIRE),
    ("ACH CREDIT FABRIKAM DISTRIBUTION INC PAYMENT", "Wells Fargo", COMPANY),
    ("ACH CREDIT FABRIKAM A1 DISTRIBUTION LLC PAYMENT", "Wells Fargo", ONE_OFF),
    ("STRIPE TRANSFER ST-A1B2C3D4 NORTHWIND BAKERY", "Wells Fargo", ("verified", "operating_source_with_credit_context")),
    ("ATM CHECK DEPOSIT ON 01/02 1 GRANT AVE SAMPLETOWN CA 1234567 ATM ID 1234A CARD 1234", "Wells Fargo", CHECK),
    ("EDEPOSIT IN BRANCH 01/02/54 10:30:00 AM 100 GRANT AVE SAMPLETOWN CA", "Wells Fargo", NO_PAYER),
    ("ATM CASH DEPOSIT ON 01 02 1 N GRANT AVE SAMPLEVILLE CA 1234567 ATM ID 1234D CARD 1234", "Wells Fargo", NO_PAYER),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO QUARTERLY DISTRIBUTION SAMPLE LLC", "Wells Fargo", NON_SALE),
    ("CONTOSO FOOD DISTRIBUTION GROUP LLC 1", "Wells Fargo", UNLABELLED),
    ("A1 DISTRIBUTION LLC 540115 1234567", "Wells Fargo", UNLABELLED),
    ("TRANSFER IN FROM CONTOSO DISTRIBUTION LLC", "Wealthsimple", P2P),
    ("CASH BACK ST A1B2C3D4", "Wells Fargo", ("non_revenue", "strong_non_revenue_rule")),
])
def test_r34_controls_keep_their_readings(text, bank, expected):
    assert _one(text, 5000.0, bank=bank) == expected


def test_r34_a_distributor_with_no_form_on_an_open_ended_sender_is_held():
    # The recorded risk: on a layout that prints the sender's memo straight after its name with no label (Wealthsimple's
    # 'TRANSFER IN FROM <sender> <memo>'), a distributor printing no company form is held (fail closed).
    assert _one("TRANSFER IN FROM CONTOSO DISTRIBUTION", 5000.0, bank="Wealthsimple") == NON_SALE


@pytest.mark.parametrize(("text", "proper"), [
    # A wire's or an ACH originator's whole field.
    ("WT FED 01234 SAMPLE BANK ORG CONTOSO DISTRIBUTION SRF 2054010200000 TRN 540102000001 RFB INV 1234",
     "CONTOSO DISTRIBUTION"),
    ("CONTOSO PARTNERS DES:DISTRIB ID:1 INDN:NORTHWIND GRILL LLC CO ID:1 CCD", None),
    # A transfer's sender: up to and including its first company form.
    ("ONLINE TRANSFER FROM CONTOSO HOLDINGS LLC PROFIT DISTRIBUTION", "CONTOSO HOLDINGS LLC"),
    ("TRANSFER FROM CONTOSO DISTRIBUTION LLC", "CONTOSO DISTRIBUTION LLC"),
    # With no form: the whole sender when a label or a reference closes it, else nothing.
    ("ZELLE PAYMENT FROM CONTOSO DISTRIBUTION CONF AB1234", "CONTOSO DISTRIBUTION"),
    ("ONLINE TRANSFER FROM CONTOSO DISTRIBUTION 12345", "CONTOSO DISTRIBUTION"),
    ("ONLINE TRANSFER FROM PAT SAMPLE DISTRIBUTION", ""),
    ("TRANSFER IN FROM CONTOSO DISTRIBUTION", ""),
])
def test_r34_the_payer_s_name_proper(text, proper):
    from analysis.descriptor import payer

    region = payer.payer_region(text)
    assert hold_text._payer_name_proper(text, region) == (region if proper is None else proper)


def test_r34_the_formed_name_s_word_before_and_the_numbered_street():
    for word in ("EARNINGS", "EARNING", "LIQUIDATING", "LIQUIDATION", "PRORATA"):
        assert word in hold_text._NOT_A_NAME_WORD_BEFORE
    for code in ("JAN54", "SEP2054", "SEPT54", "DEC54", "15JAN", "1JAN54", "2054MAR", "Q4", "K1", "2054Q4", "4TH"):
        assert hold_text._PERIOD_CODE.fullmatch(code), code
    for word in ("A1", "H2O", "JANE", "MAYO", "DECK1", "JAN", "J4N"):
        assert not hold_text._PERIOD_CODE.fullmatch(word), word
    street = hold_text._NUMBERED_STREET_NAME
    assert street.sub(r"\g<number> ", "ATM CHECK DEPOSIT 1 GRANT AVE SAMPLEVILLE").split() == [
        "ATM", "CHECK", "DEPOSIT", "1", "AVE", "SAMPLEVILLE"]
    assert street.sub(r"\g<number> ", "ATM DEPOSIT 123 N GRANT ST").split() == ["ATM", "DEPOSIT", "123", "N", "ST"]
    assert street.sub(r"\g<number> ", "ATM DEPOSIT 12B EQUITY DR").split() == ["ATM", "DEPOSIT", "12B", "DR"]
    for text in ("FABRIKAM HOLDINGS DISTRIBUTION ST A1B2C3D4", "CONTOSO EQUITY DR 12345", "AB12 GRANT AVE",
                 "1 OLD SAMPLE GRANT AVE"):
        assert street.sub(r"\g<number> ", text) == text, text
    # B7's street name (no number needed) is unchanged: the deposit reading still removes it.
    assert true_revenue_words._STREET_NAME.sub(" ", "ATM DEPOSIT SAMPLE ST SAMPLEVILLE").split() == ["ATM", "DEPOSIT", "ST",
                                                                                      "SAMPLEVILLE"]
    assert financing_roots._deposit_location_reading("ATM CASH DEPOSIT CAPITAL BLVD", HOLDER, "Wells Fargo") == ""


# Audit round 2, R2-B13 (R35; B7 review round 3, minor 1): a deposit's location removal keeps a funder's financing word
# that a name word stands before ('MOBILE DEPOSIT <NAME> FUNDING <town> <ST>'); a location whose first word alone is a
# financing word after the deposit's own words, a number or the row's start is still a place ('1 ADVANCE NC').

@pytest.mark.parametrize("text", [
    "MOBILE DEPOSIT FABRIKAM FUNDING SAMPLEVILLE CA",
    "MOBILE DEPOSIT FABRIKAM FUNDING NY",
    "MOBILE DEPOSIT CONTOSO CAPITAL PA",
    "MOBILE DEPOSIT FABRIKAM CAPITAL PLAZA",
    "ATM CHECK DEPOSIT 1 FABRIKAM CAPITAL CENTER",
    "REMOTE ONLINE DEPOSIT 1 FABRIKAM CAPITAL BRANCH",
    "DEPOSIT FABRIKAM CAPITAL CITY BRANCH",
    "COUNTER CREDIT CONTOSO LENDING PARK",
    "MOBILE DEPOSIT FABRIKAM MERCHANT FUNDING SAMPLEVILLE CA 12345",
])
def test_r35_a_funder_s_name_before_a_location_still_holds(text):
    assert _one(text, 4000.0, bank="Wells Fargo") == FINANCING


@pytest.mark.parametrize(("text", "expected"), [
    ("ATM CHECK DEPOSIT 1 CAPITAL HEIGHTS MD 1234567 ATM ID 1234", CHECK),
    ("ATM CASH DEPOSIT CAPITAL HEIGHTS MD", NO_PAYER),
    ("MOBILE DEPOSIT 1 ADVANCE NC", CHECK),
    ("EDEPOSIT IN BRANCH 1 FINANCIAL PLAZA", NO_PAYER),
    ("DEPOSIT CAPITAL CITY BRANCH", NO_PAYER),
    ("BRANCH DEPOSIT FINANCIAL DISTRICT BRANCH", NO_PAYER),
    ("CASH DEPOSIT BRANCH 12 CAPITAL CIR", NO_PAYER),
    ("ABM DEPOSIT SAMPLE SQUARE SAMPLEVILLE BC", NO_PAYER),
    ("MOBILE DEPOSIT FABRIKAM SAMPLEVILLE CA", CHECK),
    ("MOBILE DEPOSIT FUNDS ON HOLD SAMPLEVILLE CA", CHECK),
    # A word inside a deposit form ('NIGHT DROP'), or Wells Fargo's ATM layout, whose address and town sit between
    # DEPOSIT and its trailing ATM ID (the form's DEPOSIT ... ATM arm), and the street suffix ending a numbered address.
    ("NIGHT DROP CAPITAL PLAZA", NO_PAYER),
    ("ATM CHECK DEPOSIT ON 01 02 SAMPLE CAPITAL PLAZA SAMPLEVILLE CA 1234567 ATM ID 1234A CARD 1234", CHECK),
    ("ATM DEPOSIT 123 MAIN ST CAPITAL HEIGHTS MD", NO_PAYER),
    ("ATM DEPOSIT 123 N MAIN ST CAPITAL HEIGHTS MD", NO_PAYER),
    # The recorded residuals: a one-word glued funder's name right after DEPOSIT, before a place word, and a name word
    # inside the DEPOSIT ... ATM arm's gap, still count.
    ("MOBILE DEPOSIT CAPITALFAB PLAZA", CHECK),
    ("DEPOSIT FABRIKAM CAPITAL PLAZA ATM 1234", NO_PAYER),
    # A street suffix with no number before it ends no address.
    ("MOBILE DEPOSIT FABRIKAM WAY CAPITAL PLAZA", FINANCING),
    # Unchanged controls.
    ("MOBILE DEPOSIT FABRIKAM FUNDING LLC", FINANCING),
    ("MOBILE DEPOSIT FABRIKAM FUNDING", FINANCING),
    ("MOBILE DEPOSIT FABRIKAM CAPITAL ADVANCE SAMPLEVILLE CA", FINANCING),
    ("MOBILE DEPOSIT FORA FINANCIAL SAMPLEVILLE CA", ("non_revenue", "financing_proceeds_credit")),
    # The recorded risk (fail closed): a place whose financing word follows another place word is held.
    ("ATM DEPOSIT US BANK EASTGATE ADVANCE NC", FINANCING),
])
def test_r35_a_deposit_s_location_controls(text, expected):
    assert _one(text, 4000.0, bank="Wells Fargo") == expected


def test_r35_the_guarded_location_removal():
    read = financing_roots._deposit_location_reading
    assert read("MOBILE DEPOSIT FABRIKAM FUNDING SAMPLEVILLE CA", HOLDER, "Wells Fargo") == "FUNDING"
    assert read("MOBILE DEPOSIT FABRIKAM CAPITAL PLAZA", HOLDER, "Wells Fargo") == "CAPITAL"
    assert read("DEPOSIT FABRIKAM CAPITAL CITY BRANCH", HOLDER, "Wells Fargo") == "CAPITAL"
    assert read("MOBILE DEPOSIT 1 ADVANCE NC", HOLDER, "Wells Fargo") == ""
    assert read("ATM CASH DEPOSIT CAPITAL HEIGHTS MD", HOLDER, "Wells Fargo") == ""
    assert read("CAPITAL HEIGHTS MD", HOLDER, "Wells Fargo") == ""
    assert read("ATM DEPOSIT 1# CAPITAL PLAZA", HOLDER, "Wells Fargo") == ""
    assert read("TELLER CAPITAL PLAZA", HOLDER, "Wells Fargo") == ""
    # Two financing words in one match: never removed.
    assert read("MOBILE DEPOSIT CAPITAL FUNDING NY", HOLDER, "Wells Fargo") == "CAPITAL FUNDING"
    for word in ("DEPOSIT", "ATM", "ABM", "BRANCH", "COUNTER", "CREDIT", "TELLER", "MOBILE", "REMOTE", "IN", "AT"):
        assert word in financing_roots._DEPOSIT_LEAD_WORDS
    # The numbered street's suffixes are B7's street name's, kept in step.
    assert true_revenue_words._STREET_NAME.pattern == (r"(?<![A-Z])[A-Z]+(?= (?:" + true_revenue_words._STREET_SUFFIXES + r")\b)")


# Audit round 2, R2-B13 (R39; B7 review round 3, minor 3): a floor-plan lender's name is a floor-plan form or WHOLESALE
# beside a lender's or a vehicle trade's whole word, never a customer's FINE, CAPE, FINCH or AUTOMATION.

_R39_WF = "WT FED#01234 SAMPLE BANK /ORG={sender} SRF# 2054010200000 TRN#540102000001 RFB# VEHICLE PURCHASE"


@pytest.mark.parametrize("sender", [
    "CONTOSO FINE WHOLESALE LLC", "CAPE WHOLESALE FOODS INC", "SAMPLE AUTOMATION WHOLESALE LLC",
    "FABRIKAM WHOLESALE FINCH LLC", "CAPTAIN WHOLESALE SEAFOOD INC", "CONTOSO MOTORSPORTS WHOLESALE INC",
    # DEALERSHIP is no lender's word (the card: an over-match).
    "CONTOSO DEALERSHIP WHOLESALE INC",
    # Never held before: a grocer, a flooring contractor, a person.
    "CONTOSO WHOLESALE GROCERS INC", "CONTOSO FLOORING LLC", "PAT SAMPLE",
])
def test_r39_a_customer_named_with_a_lender_word_s_letters_is_counted(sender):
    assert _one(_FEDWIRE.format(sender=sender), 1000.0, holder=_TRUCKS) == REFUSED


@pytest.mark.parametrize("sender", [
    "CONTOSO WHOLESALE AUTO LLC", "CONTOSO WHOLESALE AUTOS LLC", "SAMPLE AUTO WHOLESALE INC",
    "NORTHWIND WHOLESALE MOTORS LLC", "FABRIKAM WHOLESALE FUNDING LLC", "FABRIKAM WHOLESALE FINANCE LLC",
    "CONTOSO DEALER WHOLESALE INC", "FABRIKAM FLOORPLAN FUNDING LLC", "FABRIKAM FLOOR PLAN SERVICES",
    # Held by the financing root's unanchored FUND, a separate reach.
    "FUNDAMENTAL WHOLESALE LLC",
])
def test_r39_a_floor_plan_lender_s_vehicle_wire_stays_held(sender):
    assert _one(_FEDWIRE.format(sender=sender), 1000.0, holder=_TRUCKS) == FINANCING


def test_r39_the_same_sender_s_invoice_wire_and_the_wells_fargo_layout():
    invoice = _FEDWIRE.format(sender="CAPE WHOLESALE FOODS INC").replace("UR I VEHICLE PURCHASE VIN 1", "INV 1234")
    assert _one(invoice, 1000.0, holder=_TRUCKS) == ("verified", "wire_remittance_purpose")
    for sender in ("CAPE WHOLESALE FOODS INC", "CONTOSO WHOLESALE GROCERS INC"):
        assert _one(_R39_WF.format(sender=sender), 1000.0, holder=_TRUCKS, bank="Wells Fargo") == WIRE
    assert _one(_R39_WF.format(sender="CONTOSO WHOLESALE AUTO LLC"), 1000.0, holder=_TRUCKS,
                bank="Wells Fargo") == FINANCING


def test_r39_the_floor_plan_lender_name_reads_whole_words():
    name = true_revenue_dealer._FLOOR_PLAN_LENDER_NAME
    for text in ("CONTOSO FINE WHOLESALE LLC", "CAPE WHOLESALE FOODS INC", "FABRIKAM WHOLESALE FINCH LLC",
                 "SAMPLE AUTOMATION WHOLESALE LLC", "CAPTAIN WHOLESALE SEAFOOD", "CONTOSO DEALERSHIP WHOLESALE INC",
                 "CONTOSO WHOLESALE GROCERS INC", "CONTOSO FLOORING LLC"):
        assert not name.search(text), text
    for text in ("CONTOSO WHOLESALE AUTO LLC", "SAMPLE AUTO WHOLESALE INC", "CONTOSO WHOLESALERS CAPITAL LLC",
                 "FABRIKAM FLOORPLAN LLC", "FABRIKAM FLOOR PLAN SERVICES", "CONTOSO WHOLESALE DEALERS INC",
                 "CONTOSO WHOLESALE CREDIT LLC"):
        assert name.search(text), text
    # The Q7 veto's floor-plan words are unchanged.
    assert true_revenue_dealer._DEALER_FLOOR_PLAN_WORDS.pattern == r"(?<![A-Z])(?:FLOOR\w*|WHOLESALE\w*)"


# Audit round 2, R2-B13 (R23): a company's direct deposit on a consumer (PPD or WEB) entry is pay only when its receiver
# is no company: a receiver field that prints a company form, or names a company-formed holder, is the business.

ROUTES = "NORTHWIND ROUTES LLC"
PLATFORM = ("counted_flagged", "platform_unconfirmed")
_R23_BOFA = "{payer} DES:{entry} ID:{n} INDN:{indn} CO ID:1234567890 {sec}"
_R23_CHASE = ("ORIG CO NAME:FABRIKAM SVC ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:DIR DEPSEC:{sec} "
              "TRACE#:123456789012345 EED:540102 IND ID:{n} IND NAME:{indn} TRN: 1234567890TC")


def _r23(layout, holder=ROUTES, **fields):
    rows = [(layout.format(n=1, **fields), 3500.0), (layout.format(n=2, **fields), 3600.0)]
    return _tiers(rows, holder=holder)


@pytest.mark.parametrize(("layout", "fields", "expected"), [
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, ONE_OFF),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "WEB"}, ONE_OFF),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES", "sec": "PPD"}, ONE_OFF),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES L", "sec": "PPD"}, ONE_OFF),
    (_R23_CHASE, {"indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, ONE_OFF),
    (_R23_BOFA, {"payer": "UBER USA", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, PLATFORM),
])
def test_r23_a_company_s_direct_deposit_to_a_business_receiver_is_counted(layout, fields, expected):
    assert _r23(layout, **fields) == [expected] * 2


@pytest.mark.parametrize(("layout", "fields", "holder"), [
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "JOHN SAMPLE", "sec": "PPD"}, ROUTES),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "JOHN SAMPLE", "sec": "WEB"}, ROUTES),
    (_R23_CHASE, {"indn": "JOHN SAMPLE", "sec": "PPD"}, ROUTES),
    ("FABRIKAM SVC DES:DIR DEP ID:{n} CO ID:1234567890 PPD", {}, ROUTES),
    (_R23_BOFA, {"payer": "ADP", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, ROUTES),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "PAYROLL", "indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, ROUTES),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "CONTOSO HAULING", "sec": "PPD"}, ROUTES),
    # A person holder, or a DBA holder with no form, on a business product's account.
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "JOHN SAMPLE", "sec": "PPD"}, "JOHN SAMPLE"),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "JOHN SAMPLE", "sec": "PPD"},
     "JOHN SAMPLE DBA SAMPLE PLUMBING"),
])
def test_r23_a_direct_deposit_to_a_person_stays_pay(layout, fields, holder):
    assert _r23(layout, holder=holder, **fields) == [PAY] * 2


def test_r23_a_person_holder_on_a_business_product_s_account_stays_pay():
    text = _R23_BOFA.format(n=1, payer="FABRIKAM SVC", entry="DIR DEP", indn="JOHN SAMPLE", sec="PPD")
    for holder_name in ("JOHN SAMPLE", "JOHN SAMPLE DBA SAMPLE PLUMBING"):
        [record] = classify_statement_transactions(Statement(
            account_name="NAVIGATE BUSINESS CHECKING", holder_name=holder_name, bank="Bank of America",
            transactions=[Transaction(date="2054-03-02", description=text, amount=3500.0, direction="credit")]))
        assert (record.revenue_tier, record.revenue_tier_reason) == PAY


@pytest.mark.parametrize(("layout", "fields", "expected"), [
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "CCD"}, REPEATS),
    (_R23_BOFA, {"payer": "FABRIKAM SVC", "entry": "PAYMENT", "indn": "NORTHWIND ROUTES LLC", "sec": "PPD"}, ONE_OFF),
    (_R23_BOFA, {"payer": "DOORDASH INC", "entry": "DIR DEP", "indn": "NORTHWIND ROUTES LLC", "sec": "CCD"}, PLATFORM),
])
def test_r23_controls_that_were_never_held(layout, fields, expected):
    assert _r23(layout, **fields) == [expected] * 2


@pytest.mark.parametrize(("indn", "holder", "fact"), [
    ("NORTHWIND ROUTES LLC", ROUTES, False),
    ("NORTHWIND ROUTES", ROUTES, False),
    ("CONTOSO HAULING LLC", ROUTES, False),
    ("JOHN SAMPLE", ROUTES, True),
    ("CONTOSO HAULING", ROUTES, True),
    ("JOHN SAMPLE", "JOHN SAMPLE", True),
])
def test_r23_g11_reads_the_business_receiver(indn, holder, fact):
    text = _R23_BOFA.format(n=1, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec="PPD")
    [record] = _records([(text, 3500.0)], holder=holder)
    assert guards.guard_facts(record, revenue_text(record.normalized_description))["pay_or_personal"] is fact


def test_r23_the_business_receiver():
    def business(receiver, holder=ROUTES):
        text = f"FABRIKAM SVC DES:DIR DEP ID:1 {receiver}CO ID:1234567890 PPD"
        return payroll._business_receiver(revenue_text(normalize_transaction_description(text)), holder)

    assert business("INDN:CONTOSO HAULING LLC ")
    assert business("INDN:NORTHWIND ROUTES ")
    assert business("INDN:NORTHWIND ROUTES L ")
    assert not business("INDN:CONTOSO HAULING ")
    assert not business("INDN:JOHN SAMPLE ", "JOHN SAMPLE")
    assert not business("INDN:JOHN SAMPLE ", "JOHN SAMPLE DBA SAMPLE PLUMBING")
    assert not business("")


# Audit round 2, R2-B13 review round 1 (R23): the holder arm reads the business only when the receiver prints every
# word of the holder's company-formed name, its form left off, printed or cut ('<NAME> ROUTES', '<NAME> ROUTES L'), or
# that name with its last word cut by the bank's field (R2-B04's end cut). A shorter run of it (the owner's own name
# leading '<person> PLUMBING LLC'), a DBA's person side, a middle initial or a reversed order is a person: the consumer
# entry keeps its pay reading (Q8).

_R23_PERSON_SHAPES = [
    ("JOHN SAMPLE PLUMBING LLC", "JOHN SAMPLE"),
    ("JOHN SAMPLE DBA SAMPLE PLUMBING LLC", "JOHN SAMPLE"),
    ("JOHN SAMPLE LLC", "JOHN Q SAMPLE"),
    ("JOHN SAMPLE LLC", "SAMPLE JOHN"),
    ("NORTHWIND ROUTES LLC", "NORTHWIND"),
]


@pytest.mark.parametrize(("layout", "sec"), [(_R23_BOFA, "PPD"), (_R23_BOFA, "WEB"), (_R23_CHASE, "PPD")])
@pytest.mark.parametrize(("holder", "indn"), _R23_PERSON_SHAPES)
def test_r23_review_a_person_inside_the_holder_s_name_stays_pay(layout, sec, holder, indn):
    assert _r23(layout, holder=holder, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec=sec) == [PAY] * 2


@pytest.mark.parametrize("holder_name", ["JOHN SAMPLE PLUMBING LLC", "JOHN SAMPLE DBA SAMPLE PLUMBING LLC"])
def test_r23_review_a_parser_holder_name_s_person_run_stays_pay(holder_name):
    text = _R23_BOFA.format(n=1, payer="FABRIKAM SVC", entry="DIR DEP", indn="JOHN SAMPLE", sec="PPD")
    [record] = classify_statement_transactions(Statement(
        account_name="NAVIGATE BUSINESS CHECKING", holder_name=holder_name, bank="Bank of America",
        transactions=[Transaction(date="2054-03-02", description=text, amount=3500.0, direction="credit")]))
    assert (record.revenue_tier, record.revenue_tier_reason) == PAY


@pytest.mark.parametrize(("holder", "indn"), [
    # The holder's whole name with its form cut, or its last word cut by the bank's field.
    ("NORTHWIND ROUTES LLC", "NORTHWIND ROUTES LL"),
    ("NORTHWIND TRANSPORTATION LLC", "NORTHWIND TRANSPORTAT"),
    ("NORTHWIND ROUTES L.L.C.", "NORTHWIND ROUTES"),
    ("THE NORTHWIND ROUTES LLC", "NORTHWIND ROUTES"),
    # A DBA holder's formed side printed with its form (the company-form arm).
    ("JOHN SAMPLE DBA SAMPLE PLUMBING LLC", "SAMPLE PLUMBING LLC"),
    # The recorded residual, an owner item beside Q8: a holder whose formed name is a person's name with a form, its
    # receiver printing that name whole with the form left off, reads as the business (nothing in the text tells it
    # from '<NAME> ROUTES' on '<NAME> ROUTES LLC').
    ("JOHN SAMPLE LLC", "JOHN SAMPLE"),
])
def test_r23_review_the_holder_s_whole_name_is_the_business(holder, indn):
    assert _r23(_R23_BOFA, holder=holder, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec="PPD") == [ONE_OFF] * 2


def test_r23_review_the_holder_arm():
    def business(receiver, holder):
        text = f"FABRIKAM SVC DES:DIR DEP ID:1 INDN:{receiver} CO ID:1234567890 PPD"
        return payroll._business_receiver(revenue_text(normalize_transaction_description(text)), holder)

    for holder, indn in _R23_PERSON_SHAPES:
        assert not business(indn, holder), (holder, indn)
    # A word after the holder's name that is no form, or a last word cut to fewer than four letters, names no business.
    assert not business("NORTHWIND ROUTES OPS", ROUTES)
    assert not business("NORTHWIND TRA", "NORTHWIND TRANSPORTATION LLC")
    # A holder with no company form, or a DBA holder's person side, never reads as the business by this arm.
    assert not business("JOHN SAMPLE", "JOHN SAMPLE DBA SAMPLE PLUMBING LLC")
    assert not business("SAMPLE PLUMBING", "JOHN SAMPLE DBA SAMPLE PLUMBING LLC")
    for indn in ("NORTHWIND ROUTES", "NORTHWIND ROUTES L", "NORTHWIND ROUTES LLC"):
        assert business(indn, ROUTES), indn
    assert business("NORTHWIND TRANSPORTAT", "NORTHWIND TRANSPORTATION LLC")
    assert business("NORTHWIND AND SONS", "NORTHWIND & SONS LLC")
    # Audit round 3, R3-B10 (R3-89): a cut form is read only as one of the holder's own forms, and a one-word holder's
    # name is never read cut.
    assert not business("JOHN SAMPLE L", "JOHN SAMPLE CORP")
    assert not business("NORTHWIND ROUTES C", ROUTES)
    assert not business("NORT", "NORTHWIND LLC")
    for indn in ("NORTHWIND ROUTES LL", "NORTHWIND ROUTES INC"):
        assert business(indn, ROUTES), indn
    assert business("JOHN SAMPLE C", "JOHN SAMPLE CORP")
    assert business("JOHN SAMPLE CO", "JOHN SAMPLE CORP")


# Audit round 3, R3-B10 (R3-89): a receiver whose cut last word starts no form the holder prints ('L' on '<NAME>
# CORP', 'C' on '<NAME> LLC'), or a one-word holder's name cut ('NORT' on 'NORTHWIND LLC'), is no business: the
# employer's consumer direct deposit keeps its pay reading (Q8).

@pytest.mark.parametrize(("layout", "sec"), [(_R23_BOFA, "PPD"), (_R23_BOFA, "WEB"), (_R23_CHASE, "PPD")])
@pytest.mark.parametrize(("holder", "indn"), [
    ("JOHN SAMPLE CORP", "JOHN SAMPLE L"),
    ("NORTHWIND ROUTES LLC", "NORTHWIND ROUTES C"),
    ("NORTHWIND LLC", "NORT"),
])
def test_r3_89_a_cut_form_the_holder_never_prints_or_a_cut_one_word_holder_stays_pay(layout, sec, holder, indn):
    assert _r23(layout, holder=holder, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec=sec) == [PAY] * 2


@pytest.mark.parametrize(("holder", "indn"), [
    # The holder's own cut form, and its name's last word cut (two name words or more).
    ("NORTHWIND ROUTES LLC", "NORTHWIND ROUTES"),
    ("NORTHWIND ROUTES LLC", "NORTHWIND ROUTES L"),
    ("NORTHWIND ROUTES LLC", "NORTHWIND ROUTES LL"),
    ("NORTHWIND TRANSPORTATION LLC", "NORTHWIND TRANSPORTAT"),
    # The widened recorded residual, an owner item beside Q8 (§17.1): a holder whose formed name is a person's name
    # with a form reads as the business when the receiver prints that name whole, with its own form cut, or with its
    # last word cut.
    ("JOHN SAMPLE CORP", "JOHN SAMPLE C"),
    ("JOHN SAMPLESON LLC", "JOHN SAMP"),
    ("JOHN SAMPLESON LLC", "JOHN SAMPLE"),
])
def test_r3_89_the_holder_s_own_cut_form_and_cut_name_are_still_the_business(holder, indn):
    assert _r23(_R23_BOFA, holder=holder, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec="PPD") == [ONE_OFF] * 2


@pytest.mark.parametrize(("indn", "holder", "fact"), [
    ("JOHN SAMPLE", "JOHN SAMPLE PLUMBING LLC", True),
    ("JOHN Q SAMPLE", "JOHN SAMPLE LLC", True),
    ("NORTHWIND TRANSPORTAT", "NORTHWIND TRANSPORTATION LLC", False),
])
def test_r23_review_g11_reads_the_narrowed_holder_arm(indn, holder, fact):
    text = _R23_BOFA.format(n=1, payer="FABRIKAM SVC", entry="DIR DEP", indn=indn, sec="PPD")
    [record] = _records([(text, 3500.0)], holder=holder)
    assert guards.guard_facts(record, revenue_text(record.normalized_description))["pay_or_personal"] is fact


# Audit round 2, R2-B13 review round 1 (R34 c): a payer-less check, cash, branch or ATM deposit keeps B7's number-free
# street reading (its location is a street, never a purpose); a row that names a payer reads a street only after a
# street number.

@pytest.mark.parametrize("text", [
    "ATM CASH DEPOSIT GRANT ST SAMPLEVILLE",
    "ATM CASH DEPOSIT 1234 OLD SAMPLE GRANT RD SAMPLEVILLE",
    "ATM CASH DEPOSIT 1234 E OLD GRANT RD SAMPLEVILLE",
    "BRANCH DEPOSIT GRANT AVE SAMPLETOWN CA",
])
def test_r34_review_a_payer_less_deposit_s_street_is_no_purpose(text):
    assert _one(text, 900.0, bank="Wells Fargo") == NO_PAYER


@pytest.mark.parametrize(("text", "bank", "expected"), [
    # A named row's street needs its number (the brief's trace shape stays held).
    ("FABRIKAM GRANT ST-A1B2C3D4", "Wells Fargo", NON_SALE),
    # Recorded residuals: on a named row, a street with two words between its number and its name is read as a purpose
    # (fail closed), and a year or a one-digit token before a purpose word still reads as a street's number.
    ("CONTOSO SUPPLY 1234 OLD SAMPLE GRANT RD SAMPLEVILLE", "Wells Fargo", NON_SALE),
    ("FABRIKAM HOLDINGS 2054 DISTRIBUTION ST A1B2C3D4", "Wells Fargo", UNLABELLED),
    ("FABRIKAM HOLDINGS PMT 1 DIVIDEND PL 12345", "Wells Fargo", UNLABELLED),
])
def test_r34_review_a_named_row_s_street_and_its_residuals(text, bank, expected):
    assert _one(text, 5000.0, bank=bank) == expected


@pytest.mark.parametrize(("text", "bank", "expected"), [
    # Recorded residuals of the name proper, failing closed: a company form inside a distributor's name ends the name
    # proper, and a sender with no form and no label after it, on any layout, spares nothing.
    ("ZELLE PAYMENT FROM CONTOSO AND CO DISTRIBUTION CONF AB1234", "Bank of America", NON_SALE),
    ("ONLINE TRANSFER FROM CONTOSO LTD DISTRIBUTION CENTER REF IB0ABCDEF ON 01 02 54", "Wells Fargo", NON_SALE),
    ("ZELLE PAYMENT FROM CONTOSO DISTRIBUTION", "Chase", NON_SALE),
    ("TRANSFER FROM CONTOSO DISTRIBUTION", "Mercury", NON_SALE),
    ("INTERAC E-TRANSFER FROM CONTOSO DISTRIBUTION", "Scotiabank", NON_SALE),
    # A glued month code reads a lookalike name word as a period.
    ("ACH CREDIT DEC10 DISTRIBUTION INC PAYMENT", "Wells Fargo", NON_SALE),
    # Still counted: a closed sender's purpose word, and a purpose word outside the brief's five.
    ("ONLINE TRANSFER FROM PAT SAMPLE QUARTERLY DISTRIBUTION REF IB0ABCDEF ON 01 02 54", "Wells Fargo", P2P),
    ("ONLINE TRANSFER FROM FABRIKAM HOLDINGS LLC MEMO OPERATING DISTRIBUTION SAMPLE LLC", "Wells Fargo", P2P),
])
def test_r34_review_the_name_proper_s_recorded_residuals(text, bank, expected):
    assert _one(text, 5000.0, bank=bank) == expected


# Audit round 2, R2-B13 review round 1 (R35): Wells Fargo's own deposit furniture 'DEPOSIT MADE IN A BRANCH/STORE' leads
# a place as the deposit's other words do; STORE alone does not.

@pytest.mark.parametrize(("text", "expected"), [
    ("DEPOSIT MADE IN A BRANCH/STORE CAPITAL PLAZA", NO_PAYER),
    ("DEPOSIT MADE IN A BRANCH/STORE", NO_PAYER),
    ("MOBILE DEPOSIT FABRIKAM STORE CAPITAL PLAZA", FINANCING),
])
def test_r35_review_the_branch_store_form_leads_a_place(text, expected):
    assert _one(text, 4000.0, bank="Wells Fargo") == expected


# Audit round 2, R2-B13 review round 1 (R39): a finance company's glued spellings that the financing root does not read
# (FINCO, FINCORP, CAPCO, CAPCORP, AUTOFIN) are floor-plan lender words.

@pytest.mark.parametrize("sender", [
    "CONTOSO WHOLESALE FINCO LLC", "CONTOSO WHOLESALE FINCORP", "CONTOSO WHOLESALE CAPCO LLC",
    "CONTOSO WHOLESALE CAPCORP", "CONTOSO WHOLESALE AUTOFIN LLC", "CONTOSO AUTOFIN WHOLESALE INC",
])
def test_r39_review_a_finance_company_s_glued_spelling_stays_held(sender):
    assert _one(_FEDWIRE.format(sender=sender), 1000.0, holder=_TRUCKS) == FINANCING
    assert true_revenue_dealer._FLOOR_PLAN_LENDER_NAME.search(sender), sender


# ---------------------------------------------------------------------------------------------------------------------
# Owner ruling 2026-10-02 (the underwriter's Q9, "Keep them as true revenue", option 2), R2-OW09: T4's financing-root
# hold is lifted, counted and flagged, never verified and never a Q5 or Q6 repeat, for (a) finance_named_customer: the
# payer's own name carries a finance word and the line prints invoice, accounts-payable or vendor-payment wording (a
# commission too: the orchestrator's extension under the underwriter's Q10); (b) lessor_rent: a rent LEASE received by a
# business in leasing or property; (c) lender_paid_for_services: a lender paying the business for its services. The
# hidden-loan guard stays (any posted debit naming the payer holds; the bank's receiving fee and a card purchase aside:
# a documented over-hold). Every other financing arm and every later hold still read a released row. Fabricated rows;
# the holder NORTHWIND BAKERY LLC and Bank of America's DES layout unless a row names another.
# ---------------------------------------------------------------------------------------------------------------------
FINANCE_NAMED = ("counted_flagged", "finance_named_customer")
LENDER_SERVICES = ("counted_flagged", "lender_paid_for_services")
LESSOR = ("counted_flagged", "lessor_rent")
_PLUMBING = "SAMPLE PLUMBING LLC"
_RECOVERY = "SAMPLE RECOVERY LLC"
_PROPERTIES = "SAMPLE PROPERTIES LLC"
_CAFE_LEASE = "CONTOSO CAFE LLC DES:LEASE PMT ID:1"
_NW_PAYABLES = "NORTHWIND FINANCIAL GROUP DES:PAYABLES ID:{n}"
_CHASE_VENDOR = (
    "ORIG CO NAME:FABRIKAM FINANCIAL ORIG ID:1234567890 DESC DATE:540301 CO ENTRY DESCR:VENDOR PAYSEC:CCD "
    "TRACE#:021000021234567 EED:540301 IND ID:12345 IND NAME:NORTHWIND BAKERY LLC"
)
_POOL_LEASE = "BOOK TRANSFER CREDIT B/O: CONTOSO SWIM SCHOOL INC SAMPLEVILLE NY 12345 US REF: POOL LEASE MARCH"
_WIRE_IN = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:2054030200001 SEQ:1/2 ORIG:FABRIKAM FINANCIAL INC ID:99 "
            "SND BK:SAMPLE BANK ID:1 PMT DET:INVOICE 1234")


def _q9_credits(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    return [record for record in _records(rows, holder=holder, bank=bank) if record.amount > 0]


def _released(record, expected):
    """A row the release lifted: its tier and reason, an unverified deposit counted in True, never verified, never a
    required review, its classifier method kept."""
    assert rules_reading(record) == expected, record.normalized_description
    assert record.revenue_classification == "unverified_deposit"
    assert record.contributes_to_true_revenue and not record.contributes_to_verified_revenue
    assert not record.revenue_review_required


def _pass_facts(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    """Each credit's pass-7 payer facts, read again as the pass reads them (the statement's debits and lessor reading),
    with the tier and reason the row would take without the release's relabel."""
    from dataclasses import replace

    records = _records(rows, holder=holder, bank=bank)
    credits = [index for index, record in enumerate(records) if record.amount > 0 and record.revenue_classification]
    debits = counter_debit_pairing.counter_debits(records, set())
    lessor = finance_release._lessor_business(records, set(), credits)
    found = []
    for index in credits:
        record = records[index]
        text = true_revenue_channel.without_transfer_code(record, revenue_text(record.normalized_description))
        facts = true_revenue_facts.credit_facts(record, text, debits=debits, lessor=lessor)
        found.append((facts, tiers._tier_reason(record, text, replace(facts, q9=None), False)))
    return found


@pytest.mark.parametrize(("text", "amount", "holder", "bank", "expected"), [
    # (a) finance_named_customer: a finance word in the payer's own name, invoice, payables or vendor wording.
    (_NW_PAYABLES.format(n=1) + " INDN:SAMPLE PLUMBING LLC CO ID:1 CCD", 4200.0, _PLUMBING, None, FINANCE_NAMED),
    ("ADVANCED CONTOSO SUPPLY DES:VENDOR PMT ID:1", 3100.0, HOLDER, None, FINANCE_NAMED),
    ("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0, HOLDER, None, FINANCE_NAMED),
    (_CHASE_VENDOR, 2500.0, HOLDER, "Chase", FINANCE_NAMED),
    # An entry-first layout with no label; COMMISSION is the orchestrator's extension under the underwriter's Q10.
    ("COMMISSION FABRIKAM FIN", 610.0, "SAMPLE INSURANCE AGENCY INC", "Royal Bank of Canada", FINANCE_NAMED),
    # An incoming wire whose payment detail cites an invoice (it would be counted as wire_named_sender).
    (_WIRE_IN, 4200.0, _PLUMBING, None, FINANCE_NAMED),
    # (c) lender_paid_for_services: the payer's name reads as a lender's.
    ("FABRIKAM FUNDING DES:VENDORPMTS ID:1 INDN:SAMPLE RECOVERY LLC CO ID:1 CCD", 1800.0, _RECOVERY, None,
     LENDER_SERVICES),
    ("FABRIKAM ADVANCE DES:INVOICE PMT ID:1", 25000.0, HOLDER, None, LENDER_SERVICES),
    # A funder paying an ISO its commission.
    ("FABRIKAM FUNDING DES:COMMISSION ID:1", 1800.0, "SAMPLE BUSINESS ADVISORS LLC", None, LENDER_SERVICES),
    # A layout with no entry label, one root in the payer's name before the payables wording.
    ("FABRIKAM FUNDING PAYABLES 123456 F WFI1234567", 21000.0, _PLUMBING, "Wells Fargo", LENDER_SERVICES),
    # Documented limit: a single root such a layout prints cannot tell a name from a purpose and is read as the name.
    ("NORTHWIND SUPPLY FUNDING PAYABLES 123456", 3000.0, _PLUMBING, "Wells Fargo", LENDER_SERVICES),
    # Documented label limit: a whole-word ADVANCE reads as a lender's word; the tier is the same.
    ("ADVANCE AUTO PARTS DES:VENDOR PMT ID:1", 800.0, HOLDER, None, LENDER_SERVICES),
    # A whole-word CREDIT name (the special payer arm) with vendor wording.
    ("FABRIKAM CREDIT GROUP DES:VENDOR PMT ID:1", 2500.0, HOLDER, None, LENDER_SERVICES),
])
def test_q9_a_c_a_finance_named_payer_paying_an_invoice_is_counted_never_verified(text, amount, holder, bank,
                                                                                  expected):
    _released(_q9_credits([(text, amount)], holder=holder, bank=bank)[0], expected)


def test_q9_a_two_rows_of_one_finance_named_customer_never_make_a_repeat():
    records = _q9_credits([(_NW_PAYABLES.format(n=1), 4200.0), (_NW_PAYABLES.format(n=2), 3900.0)], holder=_PLUMBING)
    for record in records:
        _released(record, FINANCE_NAMED)
        assert record.revenue_match_method == "unidentified_posted_credit"
    assert [facts.q9 for facts, _base in _pass_facts([(_NW_PAYABLES.format(n=1), 4200.0)], holder=_PLUMBING)] == [
        "finance_named_customer"]


def test_q9_a_the_wording_is_read_per_line():
    # The same payer's line that prints no invoice or vendor wording keeps its hold (a documented split).
    released, held = _q9_credits([("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0),
                                  ("FABRIKAM FINANCIAL DES:PAYMENT ID:2", 2500.0)])
    _released(released, FINANCE_NAMED)
    assert rules_reading(held) == FINANCING


def test_q9_b_a_lease_rent_at_a_property_business_is_lessor_rent():
    _released(_q9_credits([(_CAFE_LEASE, 5200.0)], holder=_PROPERTIES)[0], LESSOR)


def test_q9_b_two_rent_payers_make_a_lessor_and_the_other_payer_keeps_its_reading():
    lease, yoga = _q9_credits([(_CAFE_LEASE, 5200.0), ("FABRIKAM YOGA LLC DES:RENT ID:2", 2400.0)])
    _released(lease, LESSOR)
    assert (yoga.revenue_tier, yoga.revenue_match_method) == ("verified", "named_payer_company_form")


def test_q9_b_check_channel_rent_rows_are_rent_payers_and_stay_check_deposits():
    rows = [("MOBILE DEPOSIT RENT UNIT 1", 1200.0), ("MOBILE DEPOSIT RENT UNIT 3", 1300.0), (_CAFE_LEASE, 5200.0)]
    first, second, lease = _q9_credits(rows, bank="Wells Fargo")
    assert [rules_reading(first), rules_reading(second)] == [CHECK, CHECK]
    _released(lease, LESSOR)


@pytest.mark.parametrize(("rows", "holder", "bank", "expected", "base"), [
    # A memo the region swallowed: LEASE PMT after the payer's company form, on a layout with no entry label.
    ([("CONTOSO CAFE LLC LEASE PMT 123456", 5200.0)], _PROPERTIES, "Wells Fargo", [LESSOR], [UNLABELLED]),
    # A payer-less check deposit's rent, at a realty business: it would be counted as a check deposit.
    ([("CHECK DEPOSIT LEASE PMT UNIT 2", 4000.0)], "SAMPLE REALTY LLC", "Wells Fargo", [LESSOR], [CHECK]),
    # A property-management platform's credit (Buildium) makes the lessor: the wire would be wire_named_sender and
    # Buildium's own payout stays platform_unconfirmed.
    ([(_POOL_LEASE, 9000.0), ("BUILDIUM DES:PAYMENT ID:5", 3000.0)], "SAMPLE AQUATIC CENTER LLC", "Chase",
     [LESSOR, ("counted_flagged", "platform_unconfirmed")], [WIRE, ("counted_flagged", "platform_unconfirmed")]),
])
def test_q9_b_the_release_relabels_the_counted_reason(rows, holder, bank, expected, base):
    records = _q9_credits(rows, holder=holder, bank=bank)
    assert [rules_reading(record) for record in records] == expected
    _released(records[0], LESSOR)
    assert [found_base for _facts, found_base in _pass_facts(rows, holder=holder, bank=bank)] == base


@pytest.mark.parametrize(("rows", "holder", "bank"), [
    # (b) with no leasing or property business: one rent payer and no trade word on the holder's name.
    ([(_CAFE_LEASE, 5200.0)], HOLDER, None),
    # A payer named LEASE before its company form is no rent memo.
    ([("LEASE HOLDINGS LLC DES:LEASE PMT ID:1", 5200.0)], _PROPERTIES, None),
    # A lease-to-own fund (Q8's) and the LEASING root are never rent.
    ([("FABRIKAM LEASE FUND 1234567-1 SAMPLE CUSTOMER", 1500.0)], _PROPERTIES, "Wells Fargo"),
    ([("NORTHWIND LEASING DES:LEASE PMT ID:1", 5200.0)], _PROPERTIES, None),
    ([("CONTOSO LLC DES:LEASE FUNDING ID:1", 5200.0)], _PROPERTIES, None),
    ([("CONTOSO LLC DES:LEASE PROCEEDS ID:1", 5200.0)], _PROPERTIES, None),
    ([("FABRIKAM AUTO FINANCE DES:LEASE PAYOFF ID:1", 18000.0)], _PROPERTIES, None),
    # (a), (c) with no invoice or vendor wording, or a root in the entry.
    ([("FABRIKAM CAPITAL DES:CORP PAY ID:1", 25000.0)], HOLDER, None),
    ([("NORTHWIND SUPPLY DES:FUNDING PAYABLES ID:1", 3000.0)], HOLDER, None),
    # A layout with no entry label: two roots, or a root after the payer's company form.
    ([("FABRIKAM CAPITAL ADVANCE VENDOR PMT 123456", 25000.0)], _PLUMBING, "Wells Fargo"),
    ([("FABRIKAM CAPITAL FUNDING PAYABLES 123456 LAG", 25000.0)], _PLUMBING, "Citizens Bank"),
    ([("FABRIKAM CAPITAL FUNDING AP PAYMENT", 25000.0)], _PLUMBING, "TD Bank"),
    ([("FABRIKAM LLC FUNDING PAYABLES 123456", 25000.0)], _PLUMBING, "Wells Fargo"),
    # Proceeds beside vendor wording.
    ([("FABRIKAM CAPITAL DES:VENDOR PMT PROCEEDS ID:1", 25000.0)], HOLDER, None),
    # The hidden-loan guard: a posted debit names the payer.
    ([(_NW_PAYABLES.format(n=1), 4200.0), ("NORTHWIND FINANCIAL DES:ACH DEBIT ID:2", -500.0)], _PLUMBING, None),
    ([("FABRIKAM FINANCIAL DES:VENDOR PMT ID:1", 4200.0), ("FABRIKAM FINANCIAL DES:LOAN PMT ID:2", -900.0)],
     _PLUMBING, None),
    # A documented over-hold: a bill the business pays the same payer holds it too.
    ([(_NW_PAYABLES.format(n=1), 4200.0), ("NORTHWIND FINANCIAL GROUP DES:BILL PAY ID:2", -50.0)], _PLUMBING, None),
    # Not prototyped (R2-B03's call): a payer region that names only a bank, with vendor wording.
    ([("FABRIKAM FINANCIAL BANK DES:VENDOR PMT ID:1", 2500.0)], HOLDER, None),
])
def test_q9_rows_that_stay_held_as_financing_named_payer(rows, holder, bank):
    assert rules_reading(_q9_credits(rows, holder=holder, bank=bank)[0]) == FINANCING


def test_q9_b_payer_less_transfers_never_make_a_lessor():
    rows = [("TRANSFER IN RENT", 1200.0), ("TRANSFER IN RENT", 1200.0), (_CAFE_LEASE, 5200.0)]
    assert [rules_reading(record) for record in _q9_credits(rows)] == [
        ("excluded_pending_review", "p2p_round_repeat"), ("excluded_pending_review", "p2p_round_repeat"), FINANCING]


def test_q9_b_a_zelle_tenant_s_rent_is_never_lessor_evidence():
    # The underwriter's Q3 excludes every Zelle deposit, so its rent never makes a lessor (read before the Zelle step).
    lease, zelle = _q9_credits([(_CAFE_LEASE, 5200.0), ("ZELLE FROM CONTOSO TENANT LLC RENT", 1100.0)])
    assert rules_reading(lease) == FINANCING
    assert rules_reading(zelle) == P2P


def test_q9_the_guard_passes_over_a_card_purchase_and_the_bank_s_receiving_fee():
    rows = [(_NW_PAYABLES.format(n=1), 4200.0), ("CHECKCARD 0302 NORTHWIND FINANCIAL GROUP SAMPLEVILLE CA", -50.0)]
    _released(_q9_credits(rows, holder=_PLUMBING)[0], FINANCE_NAMED)
    rows = [("FABRIKAM FINANCIAL DES:VENDOR PMT ID:1", 4200.0), ("INCOMING WIRE FEE FABRIKAM FINANCIAL", -15.0)]
    _released(_q9_credits(rows, holder=_PLUMBING)[0], FINANCE_NAMED)
    rows = [(_WIRE_IN, 4200.0), ("WIRE TRANSFER FEE FROM FABRIKAM FINANCIAL INC", -17.0)]
    _released(_q9_credits(rows, holder=_PLUMBING)[0], FINANCE_NAMED)


def test_q9_a_released_row_takes_every_later_hold_and_keeps_no_q9_mark():
    rows = [("NORTHWIND FINANCIAL GROUP DES:PAYABLES PAYROLL ID:1", 4200.0)]
    assert rules_reading(_q9_credits(rows, holder=_PLUMBING)[0]) == PAY
    [(facts, _base)] = _pass_facts(rows, holder=_PLUMBING)
    assert (facts.hold, facts.q9) == ("payroll_or_salary", None)


@pytest.mark.parametrize("text", ["GM FINANCIAL DES:VENDOR PMT ID:1", "GM FINANCIAL DES:INVOICE PMT ID:1"])
def test_q9_registered_lender_s_vendor_wording_open_owner_question_17_1(text):
    # A limitation, not the ruling's outcome: a registered lender's vendor-worded credit stays D1's financing proceeds
    # (non-revenue first); releasing it would move the lender-credit exclusion (a G7 move), so the owner is asked
    # (spec §17.1). The same lender's PAYABLES at a repossession agency counts as lender_paid_for_services (R2-OW05).
    record = _q9_credits([(text, 1500.0)], holder=_RECOVERY)[0]
    assert (record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method) == (
        "non_revenue", None, "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion
    payables = _q9_credits([("GM FINANCIAL DES:PAYABLES ID:1 INDN:SAMPLE RECOVERY LLC CO ID:1 CCD", 1500.0)],
                           holder=_RECOVERY)[0]
    assert rules_reading(payables) == LENDER_SERVICES


def test_q9_a_claimed_financier_s_payout_keeps_its_own_reading():
    # Q8's lease-to-own or patient financier claims its row before the financing hold: never released, never relabelled.
    record = _q9_credits([("TERRACE FINANCE DES:VENDOR PMT ID:1", 2500.0)], holder="NORTHWIND FURNITURE LLC")[0]
    assert rules_reading(record) == ("counted_flagged", "customer_financing_payout")
    [(facts, _base)] = _pass_facts([("TERRACE FINANCE DES:VENDOR PMT ID:1", 2500.0)], holder="NORTHWIND FURNITURE LLC")
    assert facts.claimed and facts.q9 is None


def test_q9_a_zelle_row_the_release_lifted_is_still_excluded():
    # The underwriter's Q3 (R2-OW02, CR7): the Zelle step runs after the tiers; the rules' reading is the release's.
    record = _q9_credits([("ZELLE FROM FABRIKAM FINANCIAL LLC ON 03/02 INVOICE 1234", 900.0)])[0]
    assert (record.revenue_tier, record.revenue_tier_reason) == ("non_revenue", "zelle_excluded")
    assert true_revenue_zelle.zelle_prior_reading(record) == FINANCE_NAMED
    assert rules_reading(record) == FINANCE_NAMED


@pytest.mark.parametrize(("reason", "relabelled"), [
    ("named_payer_one_off", True), ("named_payer_unlabelled", True), ("wire_named_sender", True),
    ("check_deposit", True), ("p2p", True), ("named_payer_purpose_refused", True), ("no_payer_printed", True),
    # The counted reasons a released row keeps (_Q9_KEEPS).
    ("numbered_company_payer", False), ("factoring_payout", False), ("payout_credit_entity", False),
    ("platform_unconfirmed", False), ("payer_text_not_read", False), ("customer_financing_payout", False),
    ("construction_progress_draw", False), ("insurer_paid_for_services", False), ("lender_paid_for_services", False),
])
def test_q9_the_relabel_is_last_and_keeps_the_specific_counted_reasons(monkeypatch, reason, relabelled):
    from dataclasses import replace

    [(facts, _base)] = _pass_facts([("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0)])
    record = _q9_credits([("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0)])[0]
    monkeypatch.setattr(tiers, "_tier_reason_read", lambda *args: ("counted_flagged", reason))
    assert tiers._tier_reason(record, "", facts, False) == (
        "counted_flagged", "finance_named_customer" if relabelled else reason)
    # A held reason is never overridden.
    monkeypatch.setattr(tiers, "_tier_reason_read", lambda *args: ("excluded_pending_review", "payer_also_debited"))
    assert tiers._tier_reason(record, "", facts, False) == ("excluded_pending_review", "payer_also_debited")
    # With no release nothing is relabelled.
    monkeypatch.setattr(tiers, "_tier_reason_read", lambda *args: ("counted_flagged", reason))
    assert tiers._tier_reason(record, "", replace(facts, q9=None), False) == ("counted_flagged", reason)


def test_q9_the_relabel_follows_the_unread_branch(monkeypatch):
    from dataclasses import replace

    [(facts, _base)] = _pass_facts([("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0)])
    record = _q9_credits([("FABRIKAM FINANCIAL DES:INV PMT ID:1", 2500.0)])[0]
    facts = replace(facts, channel="other")
    monkeypatch.setattr(tiers, "_tier_reason_read", lambda *args: ("counted_flagged", "no_payer_printed"))
    # R2-B07's unread branch keeps precedence: payer_text_not_read is kept, a lender in the unread run holds.
    assert tiers._tier_reason(record, "", facts, False, unread=True) == ("counted_flagged", "payer_text_not_read")
    assert tiers._tier_reason(record, "", facts, False, unread=True, unread_text="ONDECK CAPITAL") == (
        "excluded_pending_review", "unread_run_names_financing")
    # Off the unread branch the counted reason takes the release's.
    assert tiers._tier_reason(record, "", facts, False) == ("counted_flagged", "finance_named_customer")


# Units: where the roots fire (_financing_root_places), the label-less refusal, the rent readings, the lessor.

def _places(raw: str, *, holder: str | None = HOLDER, bank: str | None = None):
    from analysis.descriptor import payer

    text = revenue_text(normalize_transaction_description(raw))
    region, entry = payer.payer_region(text), payer.entry_fields(text)
    places = financing_roots._financing_root_places(text, region, entry, holder, bank=bank)
    assert bool(places) == financing_roots.financing_named(text, region, entry, holder, bank=bank)
    return places


@pytest.mark.parametrize(("raw", "bank", "expected"), [
    ("NORTHWIND FINANCIAL GROUP DES:PAYABLES ID:1", None,
     {"payer": "NORTHWIND FINANCIAL GROUP"}),
    ("NORTHWIND SUPPLY DES:FUNDING PAYABLES ID:1", None, {"entry": "FUNDING PAYABLES"}),
    # A whole-word CREDIT payer (the special arm) beside an entry root: both places are reported.
    ("FABRIKAM CREDIT GROUP DES:ADVANCE ID:1", None,
     {"payer": "FABRIKAM CREDIT GROUP", "payer_arm": True, "entry": "ADVANCE"}),
    ("MOBILE DEPOSIT FABRIKAM FUNDING LLC", "Wells Fargo", {"row": "FUNDING"}),
    ("TRANSFER IN FABRIKAM ADVANCE", None, {"row": "TRANSFER IN FABRIKAM ADVANCE"}),
    ("CONTOSO SUPPLY DES:VENDOR PMT ID:1", None, {}),
])
def test_q9_the_root_places(raw, bank, expected):
    places = _places(raw, bank=bank)
    assert places == financing_roots._RootPlaces(**expected)
    assert bool(places) == bool(expected)


@pytest.mark.parametrize(("raw", "bank", "named"), [
    # financing_named's reading, arm by arm, which bool(_financing_root_places) is (T4, audit B7: I16, A3).
    ("BKOFAMERICA ATM 0101 DEPOSIT 123 GLENDALE AZ", "Bank of America", False),
    ("MOBILE DEPOSIT FABRIKAM FUNDING LLC", "Wells Fargo", True),
    ("ATM CHECK DEPOSIT 1 FABRIKAM MERCHANT FUNDING", "Wells Fargo", True),
    ("ATM DEPOSIT 123 MAIN ST CAPITAL HEIGHTS MD", "Wells Fargo", False),
    ("MOBILE DEPOSIT FUNDS ON HOLD", "Wells Fargo", False),
    ("CHECK DEPOSIT LEASE PMT UNIT 2", "Wells Fargo", True),
    ("CONTOSO PARTNERS LLC DES:FUNDING ID:1", None, True),
    ("FABRIKAM CAPITAL DES:CORP PAY ID:1", None, True),
    ("FABRIKAM CREDIT GROUP DES:VENDOR PMT ID:1", None, True),
    ("FABRIKAM P CREDIT DES:PAYMENT ID:1", None, False),
    ("CONTOSO CAFE LLC DES:LEASE PMT ID:1", None, True),
    ("CONTOSO SUPPLY DES:VENDOR PMT ID:1", None, False),
    ("TRANSFER IN FABRIKAM ADVANCE", None, True),
    ("FABRIKAM LEASE FUND 1234567-1 SAMPLE CUSTOMER", "Wells Fargo", True),
])
def test_q9_financing_named_is_whether_any_place_fired(raw, bank, named):
    assert bool(_places(raw, bank=bank)) is named


def test_q9_the_label_less_refusal_and_the_rent_readings():
    assert finance_release._labelless_root_refusal("FABRIKAM CAPITAL ADVANCE VENDOR PMT 123456")
    assert finance_release._labelless_root_refusal("FABRIKAM LLC FUNDING PAYABLES 123456")
    assert not finance_release._labelless_root_refusal("FABRIKAM FUNDING PAYABLES 123456 F WFI1234567")
    assert not finance_release._labelless_root_refusal("NORTHWIND SUPPLY FUNDING PAYABLES 123456")
    assert not finance_release._labelless_root_refusal("COMMISSION FABRIKAM FIN")
    assert finance_release._rent_only("LEASE PMT") and finance_release._rent_only("POOL LEASE MARCH") and finance_release._rent_only("LEASE")
    for words in ("LEASE FUNDING", "LEASE FUND", "LEASE PROCEEDS", "LEASE TO OWN", "LEASE PURCHASE", "LEASE BUYOUT",
                  "LEASING PMT", "LEASE PMT ADVANCE", "RENT"):
        assert not finance_release._rent_only(words), words
    assert finance_release._rent_memo_payer("CONTOSO CAFE LLC LEASE PMT")
    assert not finance_release._rent_memo_payer("LEASE HOLDINGS LLC")
    assert not finance_release._rent_memo_payer("CONTOSO CAFE LEASE PMT")
    assert not finance_release._rent_memo_payer("FABRIKAM CAPITAL LLC LEASE PMT")
    assert finance_release._RENT_RECEIVED.search("RENT UNIT 2") and finance_release._RENT_RECEIVED.search("RENTALS")
    assert not finance_release._RENT_RECEIVED.search("CONTOSO RENT A CAR") and not finance_release._RENT_RECEIVED.search("RENTACAR")
    assert finance_release._LENDER_NAME_WORD.search("FABRIKAM FUNDING") and finance_release._LENDER_NAME_WORD.search("FABRICREDIT")
    assert not finance_release._LENDER_NAME_WORD.search("FABRIKAM FINANCIAL GROUP")
    assert not finance_release._LENDER_NAME_WORD.search("ADVANCED CONTOSO SUPPLY")


def _lessor(rows, *, holder: str | None = HOLDER, bank: str | None = None, unverify: tuple[int, ...] = ()):
    from dataclasses import replace

    records = _records(rows, holder=holder, bank=bank)
    records = [replace(record, revenue_classification="unverified_deposit") if index in unverify else record
               for index, record in enumerate(records)]
    credits = [index for index, record in enumerate(records) if record.amount > 0 and record.revenue_classification]
    return finance_release._lessor_business(records, set(), credits)


def test_q9_b_the_lessor_reading_arm_by_arm():
    yoga = ("FABRIKAM YOGA LLC DES:RENT ID:2", 2400.0)
    # The holder's trade word.
    assert _lessor([("CONTOSO SUPPLY DES:VENDOR PMT ID:1", 100.0)], holder=_PROPERTIES)
    assert _lessor([("CONTOSO SUPPLY DES:VENDOR PMT ID:1", 100.0)], holder="SAMPLE SELF STORAGE LLC")
    assert not _lessor([("CONTOSO SUPPLY DES:VENDOR PMT ID:1", 100.0)])
    # A property-management platform's credit.
    assert _lessor([("BUILDIUM DES:PAYMENT ID:5", 3000.0)])
    # Two distinct rent payers; one payer twice is one.
    assert _lessor([(_CAFE_LEASE, 5200.0), yoga])
    assert not _lessor([(_CAFE_LEASE, 5200.0)])
    assert not _lessor([yoga, ("FABRIKAM YOGA LLC DES:RENT ID:3", 2400.0)])
    # A car rental's RENT A CAR, the holder's own name and a card credit are no rent payer.
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("CONTOSO RENT A CAR DES:PAYMENT ID:3", 300.0)])
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("NORTHWIND BAKERY LLC DES:RENT ID:3", 300.0)])
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("POS CREDIT CONTOSO RENTALS 1234", 300.0)], unverify=(1,))
    # A non_revenue row is no rent payer.
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("POS CREDIT CONTOSO RENTALS 1234", 300.0)])
    # Payer-less rows: a check deposit counts as its own payer, a transfer never.
    assert _lessor([("MOBILE DEPOSIT RENT UNIT 1", 1200.0), ("MOBILE DEPOSIT RENT UNIT 3", 1300.0)], bank="Wells Fargo")
    assert not _lessor([("TRANSFER IN RENT", 1200.0), ("TRANSFER IN RENT", 1300.0)])
    # A Zelle deposit (the underwriter's Q3) never counts, whatever its reading at that step.
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("ZELLE FROM CONTOSO TENANT LLC RENT", 1100.0)], unverify=(1,))
    # Audit round 3, R3-B14 (R3-60): an own-account transfer whose region is an account designation (an empty payer
    # key) is no rent payer, nor is a payer whose own name prints RENTALS; rent words outside the payer's name still
    # read (a DES entry, a memo after the payer's company form, a wire's REF).
    designation = ("ONLINE BANKING TRANSFER FROM CHK 0000 CONFIRMATION# 0000000000 RENT", 1450.0)
    assert not _lessor([(_CAFE_LEASE, 5200.0), designation])
    assert not _lessor([designation, ("ONLINE BANKING TRANSFER FROM SAV 0000 CONFIRMATION# 0000000000 RENT", 1450.0)])
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("BLUEJAY PARTY RENTALS INC DES:VENDOR PMT ID:1", 900.0)])
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("SAMPLE AUTO RENTALS INC ACH PAYMNT 000000", 900.0)],
                       bank="Wells Fargo")
    assert not _lessor([(_CAFE_LEASE, 5200.0), ("PAYMENT SAMPLE RENTALS 0000AMI EQUIPMENT AND CUSTOMER ID 000000000",
                                                900.0)], bank="Truist")
    assert _lessor([(_CAFE_LEASE, 5200.0), ("BLUEJAY PARTY RENTALS INC DES:RENT ID:1", 900.0)])
    assert _lessor([("CONTOSO CAFE LLC LEASE PMT 123456", 5200.0), ("FABRIKAM TENANT LLC DES:RENT ID:2", 2400.0)],
                   bank="Wells Fargo")
    assert _lessor([(_CAFE_LEASE, 5200.0), (_R3_60_TENANT_WIRE, 2400.0)], bank="Chase")


def test_r3_60_the_rent_reading_names_the_payer_s_own_name():
    from analysis.classification import counter_debit_reading

    def name(raw, bank=None):
        text = revenue_text(normalize_transaction_description(raw))
        channel = true_revenue_channel._channel(text, bank)
        return finance_release._rent_payer_name(text, self_originated_credits._facts_region(text, channel, bank))

    # A payer-name field: the name proper (an ACH originator's or a wire's whole region).
    assert name("BLUEJAY PARTY RENTALS INC DES:VENDOR PMT ID:1") == "BLUEJAY PARTY RENTALS INC"
    # No payer-name field: the region up to the end of its first company form, or the whole region with none.
    assert name("SAMPLE AUTO RENTALS INC ACH PAYMNT 000000", "Wells Fargo") == "SAMPLE AUTO RENTALS INC"
    assert name("CONTOSO CAFE LLC LEASE PMT 123456", "Wells Fargo") == "CONTOSO CAFE LLC"
    assert name("PAYMENT SAMPLE RENTALS 0000AMI EQUIPMENT AND CUSTOMER ID 000000000", "Truist") == (
        "PAYMENT SAMPLE RENTALS")
    # A payer-less row names nobody.
    assert name("MOBILE DEPOSIT RENT UNIT 1", "Wells Fargo") == ""
    assert counter_debit_reading._payer_key("CHK") == ()


#: Audit round 3, R3-B14 (R3-60): a tenant's book transfer whose REF memo prints the rent.
_R3_60_TENANT_WIRE = "BOOK TRANSFER CREDIT B/O: FABRIKAM TENANT LLC SAMPLEVILLE NY 12345 US REF: APRIL RENTALS"
_R3_60_LEASE = ("CONTOSO CAFE LLC DES:LEASE PMT ID:0001 INDN:NORTHWIND BAKERY LLC CO ID:0000000001 CCD", 4100.0)


@pytest.mark.parametrize(("row", "bank"), [
    (("ONLINE BANKING TRANSFER FROM CHK 0000 CONFIRMATION# 0000000000 RENT", 1450.0), None),
    (("ONLINE BANKING TRANSFER FROM SAV 0000 CONFIRMATION# 0000000000 RENT", 1450.0), None),
    (("BLUEJAY PARTY RENTALS INC DES:VENDOR PMT ID:0001 INDN:NORTHWIND BAKERY LLC CO ID:0000000001 CCD", 900.0), None),
    (("PAYMENT SAMPLE RENTALS 0000AMI EQUIPMENT AND CUSTOMER ID 000000000", 900.0), "Truist"),
    (("SAMPLE AUTO RENTALS INC ACH PAYMNT 000000", 900.0), "Wells Fargo"),
])
def test_r3_60_an_own_transfer_or_a_rentals_name_never_makes_a_lessor(row, bank):
    # Today the LEASE row is counted as lessor_rent: the second row made the bakery a lessor.
    lease = _q9_credits([_R3_60_LEASE, row], bank=bank)[0]
    assert rules_reading(lease) == FINANCING


@pytest.mark.parametrize(("rows", "bank", "holder"), [
    # Two tenants whose rent words print outside their names.
    ([_R3_60_LEASE, ("FABRIKAM TENANT LLC DES:RENT ID:0002 INDN:NORTHWIND BAKERY LLC CO ID:1 CCD", 1500.0),
      ("CONTOSO TENANT INC DES:RENT ID:0003 INDN:NORTHWIND BAKERY LLC CO ID:1 CCD", 1600.0)], None, HOLDER),
    # A tenant's wire whose REF memo prints the rent.
    ([_R3_60_LEASE, (_R3_60_TENANT_WIRE, 2400.0)], "Chase", HOLDER),
    # A label-less LEASE PMT memo after the payer's company form, with a named tenant's RENT.
    ([("CONTOSO CAFE LLC LEASE PMT 123456", 5200.0), ("FABRIKAM TENANT LLC DES:RENT ID:2", 2400.0)], "Wells Fargo",
     HOLDER),
    # The holder's property-management name (the first arm).
    ([_R3_60_LEASE], None, "SAMPLE PROPERTY MANAGEMENT LLC"),
])
def test_r3_60_the_controls_still_make_a_lessor(rows, bank, holder):
    _released(_q9_credits(rows, bank=bank, holder=holder)[0], LESSOR)


# Audit round 3, R3-B14 (R3-52, the Q11 (b) side): the narrowed dealer evidence feeds _dealer_statement too, so a
# non-dealer's asset sale beside a row that is no dealer evidence is asset-sale proceeds (the owner's Q11 (b)).
@pytest.mark.parametrize("row", [
    ("CHECKCARD 0302 CONTOSO DINER MANHEIM PA 0000", -38.50),
    ("CONTOSO FLOORPLANNER DES:SUBSCRIPT ID:1 INDN:NORTHWIND LANDSCAPING LLC CO ID:1 CCD", -19.99),
])
def test_r3_52_a_non_dealer_s_asset_sale_beside_no_dealer_evidence_is_non_revenue(row):
    # Today counted (named_payer_purpose_refused): the row read as dealer evidence.
    sale = ("RITCHIE BROS DES:SELLER PAYOUT ID:1 INDN:NORTHWIND LANDSCAPING LLC CO ID:1 CCD", 24000.0)
    record = _q9_credits([sale, row], holder="NORTHWIND LANDSCAPING LLC")[0]
    assert (record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method) == (
        "non_revenue", "asset_sale_proceeds", "asset_sale_proceeds")
    # Beside a dealer's own evidence (an auction purchase by ACH) the sale keeps its reading.
    dealer = _q9_credits([sale, ("MANHEIM US DES:ACH PAYMNT ID:1", -8400.0)], holder="NORTHWIND LANDSCAPING LLC")[0]
    assert rules_reading(dealer) == ("counted_flagged", "named_payer_purpose_refused")


# Audit round 3, R3-B14 review round 1 (finding 3): on a row that prints no payer-name field the payer region swallows
# the entry description, so the third arm reads the rent words outside the payer's name proper: Truist's leading entry
# word, a rent memo after a name with no company form and a RENTAL INCOME memo still read; only a rent word inside a
# company-formed name, or RENTAL(S) used as a trade noun after a name word, is the payer's own name.
@pytest.mark.parametrize(("rows", "bank"), [
    # Truist prints the entry description first: '<entry> <company field> <receiver> CUSTOMER ID <id>'.
    ([("RENT FABRIKAM DELI LLC 0000AMI CUSTOMER ID 000000000", 1500.0)], "Truist"),
    ([("RENT FABRIKAM DELI LLC 0000AMI CUSTOMER ID 000000000", 1500.0),
      ("RENT CONTOSO DELI INC 0000AMI CUSTOMER ID 000000001", 1600.0)], "Truist"),
    ([("PAYMENT FABRIKAM TENANT RENT 0000AMI CUSTOMER ID 000000000", 1500.0)], "Truist"),
    # Tenants with no company form, the rent memo after the name (Wells Fargo, TD, a generic ACH CREDIT).
    ([("FABRIKAM DELI RENT 540301 1234 NORTHWIND BAKERY", 1500.0),
      ("CONTOSO DELI RENT 540301 1234 NORTHWIND BAKERY", 1600.0)], "Wells Fargo"),
    ([("JOHN SAMPLE RENT 540301 1234 NORTHWIND BAKERY", 1500.0)], "Wells Fargo"),
    ([("ACH DEPOSIT FABRIKAM TENANT RENT", 1500.0)], "TD Bank"),
    ([("ACH CREDIT FABRIKAM TENANT RENT PAYMENT", 1500.0)], None),
    ([("ACH CREDIT FABRIKAM TENANT RENTAL PAYMENT", 1500.0)], None),
    ([("RENTAL INCOME FABRIKAM TENANT", 1500.0)], None),
])
def test_r3_b14_r1_a_label_less_tenant_s_rent_memo_still_makes_a_lessor(rows, bank):
    # At 3939f5c each LEASE row was held financing_named_payer: the whole region, memo included, was removed.
    _released(_q9_credits([_R3_60_LEASE, *rows], bank=bank)[0], LESSOR)


@pytest.mark.parametrize(("row", "bank"), [
    # A payer named RENTALS with no company form, on a label-less row: the trade noun is its name.
    (("SAMPLE AUTO RENTALS ACH PAYMNT 000000", 900.0), "Wells Fargo"),
    (("SAMPLE AUTO RENTALS 540301 1234 NORTHWIND BAKERY", 900.0), "Wells Fargo"),
    (("ACH CREDIT SAMPLE PARTY RENTALS PAYMENT", 900.0), None),
])
def test_r3_b14_r1_a_payer_named_rentals_with_no_form_still_makes_no_lessor(row, bank):
    lease = _q9_credits([_R3_60_LEASE, row], bank=bank)[0]
    assert rules_reading(lease) == FINANCING


def test_r3_b14_r1_the_rent_reading_names_only_the_payer_s_name_proper():
    def name(raw, bank=None):
        text = revenue_text(normalize_transaction_description(raw))
        return finance_release._rent_payer_name(text, self_originated_credits._facts_region(text, true_revenue_channel._channel(text, bank), bank))

    # A leading rent word is the entry description a label-less layout printed first (Truist's), never the name.
    assert name("RENT FABRIKAM DELI LLC 0000AMI CUSTOMER ID 000000000", "Truist") == "FABRIKAM DELI LLC"
    assert name("LEASE PMT FABRIKAM DELI LLC 0000AMI CUSTOMER ID 000000000", "Truist") == "PMT FABRIKAM DELI LLC"
    # No company form: no name is removed unless RENTAL(S) is a trade noun after a name word (RENTALS anywhere,
    # RENTAL at the region's end).
    assert name("FABRIKAM DELI RENT 540301 1234 NORTHWIND BAKERY", "Wells Fargo") == ""
    assert name("RENTAL INCOME FABRIKAM TENANT") == ""
    assert name("ACH CREDIT FABRIKAM TENANT RENTAL PAYMENT") == ""
    assert name("ACH CREDIT FABRIKAM TENANT RENTAL") == "FABRIKAM TENANT RENTAL"
    assert name("SAMPLE AUTO RENTALS ACH PAYMNT 000000", "Wells Fargo") == "SAMPLE AUTO RENTALS"
    assert name("DEPOSIT RENT") == ""
    # A payer-name field keeps the name proper.
    assert name("SAMPLE RENTALS DES:PAYMENT ID:1") == "SAMPLE RENTALS"


# Audit round 3, R3-B14 review round 1 (findings 4 and 5, the Q11 (b) side): a VIN-bearing floor-plan advance whose
# unlabelled receiver is the holder's own name printing a service word, and a wire or ACH purchase at the auction that
# prints the beneficiary's state and country, are still dealer evidence, so a non-dealer's asset sale beside one keeps
# its reading (at 3939f5c each was non_revenue / asset_sale_proceeds).
@pytest.mark.parametrize(("row", "holder"), [
    (("NEXTGEAR CAPITAL FLOORPLAN ADV 1FAKE0000000000001 CONTOSO AUTO RECOVERY", 18000.0), "CONTOSO AUTO RECOVERY LLC"),
    (("OUTGOING WIRE MANHEIM REMARKETING ATLANTA GA USA", -12000.0), "NORTHWIND LANDSCAPING LLC"),
    (("ACH DEBIT MANHEIM AUCTIONS ATLANTA GA USA", -12000.0), "NORTHWIND LANDSCAPING LLC"),
])
def test_r3_b14_r1_a_dealer_s_evidence_keeps_an_asset_sale_beside_it_counted(row, holder):
    sale = (f"RITCHIE BROS DES:SELLER PAYOUT ID:1 INDN:{holder} CO ID:1 CCD", 24000.0)
    record = _q9_credits([sale, row], holder=holder, bank="Wells Fargo")[0]
    assert rules_reading(record) == ("counted_flagged", "named_payer_purpose_refused")


# Audit round 3, R3-B09 (R3-75; standard D1, D3, A8; the owner's "refunds and owner money never become revenue"): a
# credit printing an outgoing e-Transfer label (TD Canada Trust's SEND E-TFR, EQ Bank's 'e-Transfer sent', any bank
# printing a sent transfer as a credit), the French send, its reversal or its redeposit (TD's Envoi, Contr. and
# Redepot - VFC) or a French fee adjustment is the holder's own money coming back, whichever leg the parser signed: held
# as a possible return, never counted. Fabricated rows in the banks' formats, every row of a case on one day.
POSSIBLE_RETURN = ("excluded_pending_review", "possible_return")
REVERSAL_PAIR = ("non_revenue", "matched_reversal_pair")


def _same_day(rows, bank):
    records = classify_statement_transactions(Statement(account_name=HOLDER, bank=bank, transactions=[
        Transaction(date="2054-03-02", description=text, amount=amount, direction="credit" if amount > 0 else "debit")
        for text, amount in rows
    ]))
    return [rules_reading(record, method=True) for record in records if record.amount > 0]


@pytest.mark.parametrize(("bank", "rows", "expected"), [
    # TD Canada Trust: the send leg signed as the credit beside its reclaim.
    ("TD Canada Trust", [("SEND E-TFR ***ABC", 1200.0), ("RECLAIM E-TFR ***ABC", -1200.0)], [POSSIBLE_RETURN]),
    # TD's French reader: the send beside its reversal, the send fee, the send beside its redeposit.
    ("TD Canada Trust", [("Envoi-VFC *KLM SAMPLE", 150.0), ("Contr. - VFC ***KLM", -150.0),
                         ("Envoi - FRAIS - VFC", 2.0), ("Contr.- FRAIS - VFC", -2.0),
                         ("Envoi - VFC ***RST", 40.0), ("Redepot - VFC ***RST", -40.0)], [POSSIBLE_RETURN] * 3),
    # A lone French fee reversal and a French fee adjustment.
    ("TD Canada Trust", [("Contr.- FRAIS - VFC", 2.0), ("AJUST FRAIS SERVICE", 12.0)], [POSSIBLE_RETURN] * 2),
    ("TD Canada Trust", [("AJUSTEMENT DE FRAIS", 12.0), ("Redepot - VFC ***RST", 40.0)], [POSSIBLE_RETURN] * 2),
    # EQ Bank: the reversal of a sent transfer, printed with the same wording, between two equal sends.
    ("EQ Bank", [("Interac e-Transfer sent to SAMPLE", -900.0), ("Interac e-Transfer sent to SAMPLE", 900.0),
                 ("Interac e-Transfer sent to SAMPLE", -900.0)], [POSSIBLE_RETURN]),
    ("Royal Bank of Canada", [("E-TRANSFER SENT SAMPLE 1234", 50.0), ("SEND ETFR 1234", 60.0)], [POSSIBLE_RETURN] * 2),
])
def test_r3_75_a_credit_printing_an_outgoing_e_transfer_label_is_a_possible_return(bank, rows, expected):
    assert _same_day(rows, bank) == expected


@pytest.mark.parametrize(("bank", "rows", "expected"), [
    # An incoming e-Transfer stays a counted push, 'SENT BY' (an incoming wording) included.
    ("TD Canada Trust", [("INTERAC E-TRANSFER RECEIVED CONTOSO CAFE", 300.0)], [P2P]),
    ("TD Canada Trust", [("E-TRANSFER FROM CONTOSO CAFE", 310.0)], [P2P]),
    ("CIBC", [("E-TRANSFER SENT BY CONTOSO CAFE", 320.0)], [P2P]),
    # A customer whose name holds the French fee words keeps its reading (no legal-form word later on the row).
    ("TD Canada Trust", [("CONTOSO AJUSTEMENT FRAIS INC", 340.0)], [UNLABELLED]),
    # A TD RECLAIM E-TFR credit stays non_revenue (R2-B08); a CANCEL or Annul. pair stays pass 4's reversal pair.
    ("TD Canada Trust", [("RECLAIM E-TFR ***XYZ", 330.0)], [("non_revenue", "reversal_cancellation_exclusion")]),
    ("TD Canada Trust", [("SEND E-TFR ***QQQ", 2500.0), ("CANCEL E-TFR ***QQQ", -2500.0)], [REVERSAL_PAIR]),
    ("TD Canada Trust", [("Envoi-VFC *KKK", 90.0), ("Annul. - VFC ***KKK", -90.0)], [REVERSAL_PAIR]),
    # A word holding the letters is no send: SENDER, RESEND, ENVOIS, CONTRAT.
    ("TD Canada Trust", [("E-TRANSFER FROM SENDER E TFR CO", 70.0)], [P2P]),
    ("TD Canada Trust", [("CONTRAT VFC CONTOSO", 80.0)], [P2P]),
])
def test_r3_75_the_controls_keep_their_readings(bank, rows, expected):
    assert _same_day(rows, bank) == expected


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize(("bank", "text", "expected"), [
    # R3-B09 review round 1: an incoming e-Transfer whose memo prints the send wording after its incoming wording
    # (RECEIVED, FROM, AUTODEPOSIT, the French RECEPT and DEPOT) stays a counted push.
    ("Scotiabank", "INTERAC E-TRANSFER RECEIVED CONTOSO CAFE MEMO E-TRANSFER SENT FOR INV 12", P2P),
    ("Scotiabank", "INTERAC E-TRANSFER RECEIVED CONTOSO SEND E-TRANSFER CO", P2P),
    ("Royal Bank of Canada", "E-TRANSFER - AUTODEPOSIT CONTOSO CAFE SEND E-TFR REMINDER", P2P),
    ("TD Canada Trust", "E-TRANSFER FROM CONTOSO CAFE E-TRANSFER SENT FOR ORDER 12", P2P),
    ("TD Canada Trust", "Recept - VFC ***ABC CONTOSO E-TRANSFER SENT", P2P),
    ("TD Canada Trust", "Depot - VFC ***ABC CONTOSO SEND E-TFR", P2P),
    # An ACH originator's name holding the send or fee-adjustment words is a payer's name, never the bank's label.
    ("Chase", "ORIG CO NAME:SEND ETRANSFER LLC ORIG ID:1234 DESC DATE: CO ENTRY DESCR:PAYMENT", P2P),
    ("Chase", "ORIG CO NAME:AJUST FRAIS CONSEIL ORIG ID:1234 CO ENTRY DESCR:PAYMENT", ONE_OFF),
])
def test_r3_75_review_an_incoming_wording_keeps_the_send_words_counted(bank, text, expected, zelle):
    records = classify_statement_transactions(Statement(account_name=HOLDER, bank=bank, transactions=[
        Transaction(date="2054-03-02", description=text, amount=320.0, direction="credit"),
    ]), zelle_true_revenue=zelle)
    assert [rules_reading(record) for record in records] == [expected]


@pytest.mark.parametrize("zelle", [True, False])
@pytest.mark.parametrize(("bank", "text"), [
    # The send labels at the row's head (after a printed date) still hold, in both Zelle readings.
    ("TD Canada Trust", "03-02 SEND E-TFR ***ABC"),
    ("EQ Bank", "Interac e-Transfer sent to SAMPLE"),
    ("Royal Bank of Canada", "E-TRANSFER SENT SAMPLE 1234"),
    ("TD Canada Trust", "SEND E-TFR ***ABC SAMPLE"),
])
def test_r3_75_review_the_send_labels_still_hold_in_both_zelle_readings(bank, text, zelle):
    records = classify_statement_transactions(Statement(account_name=HOLDER, bank=bank, transactions=[
        Transaction(date="2054-03-02", description=text, amount=320.0, direction="credit"),
    ]), zelle_true_revenue=zelle)
    assert [rules_reading(record) for record in records] == [POSSIBLE_RETURN]
