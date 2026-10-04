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

from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, normalize_transaction_description, revenue_text

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
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
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
    # A lessor's LEASE rent printed on a deposit keeps its hold: the owner's ruling on audit I16 is awaited.
    ("CHECK DEPOSIT LEASE PMT UNIT 2", "Wells Fargo"),
])
def test_a_funder_s_formed_name_on_a_payer_less_deposit_still_holds(text, bank):
    assert _one(text, 4000.0, bank=bank) == FINANCING


def test_the_deposit_reading_keeps_only_a_funder_s_words():
    # Unit: the words a payer-less deposit's roots are read on (B7 review round 2).
    read = tr._deposit_location_reading
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
    from analysis import transaction_classifier as tc

    assert tc.payer_region(R38_TRUIST.format(sender="PAT SAMPLELENDEZ TRANSPORT")) == "PAT SAMPLELENDEZ TRANSPORT"
    assert tc.payer_region("ZELLE PAYMENT FROM PAT SAMPLE PAYMENT INFO RENT") == "PAT SAMPLE"


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
    assert tr._p2p_person_name("PAT LENDSAMPLE")
    assert not tr._p2p_person_name("FABRIKAM FUNDING")
    assert not tr._p2p_person_name("CONTOSO FINANCE")
    assert not tr._p2p_person_name("CONTOSO CAPITALCO")
    assert not tr._p2p_person_name("FABRIKAM LLC")
    assert not tr._p2p_person_name("LENDSAMPLE")
    assert "CAPITAL ONE" not in tr._root_reading("PAT SAMPLE CAPITAL ONE", None, None, p2p=True)
    assert "CAPITAL ONE" in tr._root_reading("PAT SAMPLE CAPITAL ONE", None, None, p2p=False)


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
    facts = tr.guard_facts(record, revenue_text(record.normalized_description))
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
    facts = tr.guard_facts(record, revenue_text(record.normalized_description))
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
    # A builder's progress draw stays where the owner's section-15 ruling leaves it.
    "DRAW12 FABRIKAM BUILD GROUP INC PROJECT CONTOSO HOUSING DRAW 12",
])
def test_a_non_sale_purpose_still_holds(text):
    assert _one(text, 1600.0, holder="NORTHWIND GRILL LLC", bank="Wells Fargo") == NON_SALE


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
    assert tr._without_holder_name("BUSINESS REWARDS REDEMPTION", "BUSINESS REWARDS CHECKING") == (
        "BUSINESS REWARDS REDEMPTION")
    assert _one("REWARDS REDEMPTION CREDIT", 25.0, holder="BUSINESS REWARDS CHECKING")[0] == "excluded_pending_review"
    # The run and its prefixes of two words or more, the legal form printed or not.
    assert tr._without_holder_name("PAY NORTHWIND DISTRIBUTION LLC X", "NORTHWIND DISTRIBUTION LLC").split() == [
        "PAY", "X"]
    assert tr._without_holder_name("PAY NORTHWIND X", "NORTHWIND DISTRIBUTION LLC").split() == ["PAY", "NORTHWIND", "X"]


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
        return tr.guard_facts(record, revenue_text(normalize_transaction_description(text)))["pay_or_personal"]

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
        assert tr._CREDIT_UNION_PAYER.search(acronym)
    for word in ("CUSTOM", "CUBE", "ACCUPAY"):
        assert not tr._CREDIT_UNION_PAYER.search(word)


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
    assert tr.guard_facts(record, revenue)["hold_rule"] != "personal_trust"
    held = _CHIPS.format(sender="PAT SAMPLE TTEE", obi="")
    record = _records([(held, 12000.0)], holder=_SCHOOL)[0]
    assert tr.guard_facts(record, revenue_text(normalize_transaction_description(held)))["hold_rule"] == (
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
    assert tr.guard_facts(records[0], revenue)["hold_rule"] == "lending_bank"


@pytest.mark.parametrize(("text", "expected"), [
    # The ledger's SBA repayment spelling stays its financing proceeds, and its wire stays a bank's own wire.
    ("NORTHEAST BANK DES:SBA PYMT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 CCD",
     ("non_revenue", "financing_proceeds_credit")),
    ("FEDWIRE CREDIT VIA SAMPLE BANK N A 123456789 B/O NORTHEAST BANK SAMPLEVILLE ME 12345 US REF SAMPLE NYC CTR BNF "
     "NORTHWIND PLUMBING LLC OBI 1234", FINANCING),
    # A payer whose name only starts like the lending bank is no lending bank.
    ("NORTHEAST BANKING SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 CCD", COMPANY),
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
    assert tr._holder_strip_names(record) == names


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
    assert tr.guard_facts(record, revenue_text(record.normalized_description))["pay_or_personal"] is fact


def test_r42_the_td_payer_field_s_width_is_fifteen_characters():
    assert tr._TD_PAYER_WIDTH == 15
    # Q7 reads no bank, so TD's cut never spares a word there (fail closed); an operator's word still does.
    assert tr._personal_income("CONTOSO RETIREM MSP", "CONTOSO RETIREM MSP")
    assert not tr._personal_income("CONTOSO RETIREM MSP", "CONTOSO RETIREM MSP", TD)


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
    from analysis import transaction_classifier as classifier

    region = classifier.payer_region(text)
    assert tr._payer_name_proper(text, region) == (region if proper is None else proper)


def test_r34_the_formed_name_s_word_before_and_the_numbered_street():
    for word in ("EARNINGS", "EARNING", "LIQUIDATING", "LIQUIDATION", "PRORATA"):
        assert word in tr._NOT_A_NAME_WORD_BEFORE
    for code in ("JAN54", "SEP2054", "SEPT54", "DEC54", "15JAN", "1JAN54", "2054MAR", "Q4", "K1", "2054Q4", "4TH"):
        assert tr._PERIOD_CODE.fullmatch(code), code
    for word in ("A1", "H2O", "JANE", "MAYO", "DECK1", "JAN", "J4N"):
        assert not tr._PERIOD_CODE.fullmatch(word), word
    street = tr._NUMBERED_STREET_NAME
    assert street.sub(r"\g<number> ", "ATM CHECK DEPOSIT 1 GRANT AVE SAMPLEVILLE").split() == [
        "ATM", "CHECK", "DEPOSIT", "1", "AVE", "SAMPLEVILLE"]
    assert street.sub(r"\g<number> ", "ATM DEPOSIT 123 N GRANT ST").split() == ["ATM", "DEPOSIT", "123", "N", "ST"]
    assert street.sub(r"\g<number> ", "ATM DEPOSIT 12B EQUITY DR").split() == ["ATM", "DEPOSIT", "12B", "DR"]
    for text in ("FABRIKAM HOLDINGS DISTRIBUTION ST A1B2C3D4", "CONTOSO EQUITY DR 12345", "AB12 GRANT AVE",
                 "1 OLD SAMPLE GRANT AVE"):
        assert street.sub(r"\g<number> ", text) == text, text
    # B7's street name (no number needed) is unchanged: the deposit reading still removes it.
    assert tr._STREET_NAME.sub(" ", "ATM DEPOSIT SAMPLE ST SAMPLEVILLE").split() == ["ATM", "DEPOSIT", "ST",
                                                                                      "SAMPLEVILLE"]
    assert tr._deposit_location_reading("ATM CASH DEPOSIT CAPITAL BLVD", HOLDER, "Wells Fargo") == ""


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
    read = tr._deposit_location_reading
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
        assert word in tr._DEPOSIT_LEAD_WORDS
    # The numbered street's suffixes are B7's street name's, kept in step.
    assert tr._STREET_NAME.pattern == (r"(?<![A-Z])[A-Z]+(?= (?:" + tr._STREET_SUFFIXES + r")\b)")


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
    name = tr._FLOOR_PLAN_LENDER_NAME
    for text in ("CONTOSO FINE WHOLESALE LLC", "CAPE WHOLESALE FOODS INC", "FABRIKAM WHOLESALE FINCH LLC",
                 "SAMPLE AUTOMATION WHOLESALE LLC", "CAPTAIN WHOLESALE SEAFOOD", "CONTOSO DEALERSHIP WHOLESALE INC",
                 "CONTOSO WHOLESALE GROCERS INC", "CONTOSO FLOORING LLC"):
        assert not name.search(text), text
    for text in ("CONTOSO WHOLESALE AUTO LLC", "SAMPLE AUTO WHOLESALE INC", "CONTOSO WHOLESALERS CAPITAL LLC",
                 "FABRIKAM FLOORPLAN LLC", "FABRIKAM FLOOR PLAN SERVICES", "CONTOSO WHOLESALE DEALERS INC",
                 "CONTOSO WHOLESALE CREDIT LLC"):
        assert name.search(text), text
    # The Q7 veto's floor-plan words are unchanged.
    assert tr._DEALER_FLOOR_PLAN_WORDS.pattern == r"(?<![A-Z])(?:FLOOR\w*|WHOLESALE\w*)"


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
    assert tr.guard_facts(record, revenue_text(record.normalized_description))["pay_or_personal"] is fact


def test_r23_the_business_receiver():
    def business(receiver, holder=ROUTES):
        text = f"FABRIKAM SVC DES:DIR DEP ID:1 {receiver}CO ID:1234567890 PPD"
        return tr._business_receiver(revenue_text(normalize_transaction_description(text)), holder)

    assert business("INDN:CONTOSO HAULING LLC ")
    assert business("INDN:NORTHWIND ROUTES ")
    assert business("INDN:NORTHWIND ROUTES L ")
    assert not business("INDN:CONTOSO HAULING ")
    assert not business("INDN:JOHN SAMPLE ", "JOHN SAMPLE")
    assert not business("INDN:JOHN SAMPLE ", "JOHN SAMPLE DBA SAMPLE PLUMBING")
    assert not business("")
