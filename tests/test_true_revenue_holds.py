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

def test_a_processor_s_recurring_disbursement_payouts_verify():
    rows = [(f"ACH DEPOSIT PSP 800-555-0100 DISBURSMNT {n} NORTHWIND SALON", 500.0 + n) for n in (1, 2, 3)]
    assert _tiers(rows, holder="NORTHWIND SALON LLC") == [REPEATS] * 3


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


def test_a_processor_s_recurring_disbursement_entry_still_verifies():
    rows = [(f"FABRIKAM MERCHANT SOLUTIONS DES:DISBURSEMENT ID:{n} INDN:NORTHWIND GRILL LLC CO ID:1 CCD", 5000.0 + n)
            for n in (1, 2)]
    assert _tiers(rows, holder="NORTHWIND GRILL LLC") == [REPEATS] * 2


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
