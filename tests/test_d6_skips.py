"""5.3 (2026-09-27): what D6 no longer takes (spec D6, clarified 2026-09-27 for 5.3). Fabricated descriptors only:
each keeps the bank's printed shape with invented names, amounts and dates."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier import (
    _d6_skip,
    _unknown_payee_tokens,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn

WEEKLY = (2, 9, 16, 23)
D6 = {("potential_lender", "recurring_fixed_debit")}
OTHER = {("other", "default")}


def _states(description: str, amount: float = -100.0, *, bank: str | None = None, account_name: str | None = None,
            days: tuple[int, ...] = WEEKLY) -> set[tuple[str, str]]:
    statement = Statement(
        bank=bank,
        account_name=account_name,
        transactions=[txn(f"2054-01-{day:02d}", description, amount) for day in days],
    )
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


def _reason(description: str, amount: float = -100.0) -> str | None:
    record = classify_transaction(description, amount)
    return _d6_skip(record, _unknown_payee_tokens(record.normalized_description))


@pytest.mark.parametrize(
    ("description", "reason"),
    [
        ("TRANSFER TO PAT EXAMPLE", "transfer_word"),
        ("ACH DEBIT FABRICATED COMMISSION", "compensation"),
        ("TST*FABRICATED GRILL AUSTIN TX", "card_purchase_posting"),
        ("ACH DEBIT FABRICATED WIDGETS LLC", None),
    ],
)
def test_the_5_2_skips_keep_their_reasons(description, reason):
    assert _reason(description) == reason


CHANNEL_ONLY = [
    "WITHDRAWAL MADE IN A BRANCH/STORE",
    "CASH WITHDRAWAL",
    "TELLER WITHDRAWAL",
    "ATM DEBIT 1234 FAB MAIN ST",
    "ONLINE BILL PAYMENT 1234567",
    "RECURRING PAYMENT",
    "AUTOPAY",
    "MISCELLANEOUS DEBIT",
    "DEBIT CARD PURCH CARD ENDING IN 1234 FAB MART",
    "COUNTER WITHDRAWAL",
]


@pytest.mark.parametrize("description", CHANNEL_ONLY)
def test_a_group_whose_payee_words_are_all_channel_words_is_no_payee(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "Other Debit",           # the intake lost the payee: the hunt could not tell (c00033's shape)
        "Bank Debit",            # a bank template with no payee: unclear (c00136's shape)
        "Preauthorized Wd",      # prints no payee at all: unclear (c00242's shape)
        "RECURRING PAYMENT 0105 FAB CAPITAL",  # channel words only, but the row names financing
        # D6's key stops at the first reference, so it is the template; the payee region names an organisation
        "Recurring Payment authorized on 01/02 Fab Holdings LLC Card 4321",
        "ONLINE BILL PAYMENT 1234567 TO FAB HOLDINGS LLC",
        "MOBILE PAYMENT 1234 FAB HOLDINGS GROUP LLC",
        "DEBIT CARD PURCH CARD ENDING IN 1234 FAB HOLDINGS LLC",
        "ACH DEBIT PAT EXAMPLE",
    ],
)
def test_unclear_templates_and_vetoed_rows_stay_in_review(description):
    assert _states(description) == D6


# --- A1: card postings the POS rule does not read -----------------------------------------------------------------

CARD_POSTINGS = [
    ("Fabricated Donuts Card spend", None),                                        # Square Checking
    ("DEBIT CARD RECURRING PYMT FAB.COM/BILL 01-05 CA 4321", None),                # Truist
    ("Debit Card Debit", None),
    ("Card", None),                                                                # a type-only export row
    ("FAB MART 1234 01/05 1234567890 PURCHASE FAB MIAMI FL", None),                # BofA merchant-first
    ("DBT CRD 0105 01/05/54 FAB C12345", None),
    ("Recurring Payment authorized on 01/02 Fab Web S123456789012345 Card 4321", None),  # Wells Fargo (c00148's shape)
    ("PIN DEBIT FAB MART SPRINGFIELD IL", None),
    ("RECURRING DEBIT CARD FAB STREAMING 800-555-0100 CA", None),                  # PNC
    ("DEBIT CARD TRANSACTION FAB MART SPRINGFIELD IL", None),                      # Regions
    ("VISA DDA PUR AP FAB MART SPRINGFIELD IL", None),                             # TD Bank without its star
    ("FAB DINER42, SPRINGFIELD, IL", "Bluevine"),
    ("Fab Mart 1234567, TOWNVILLE , CA , USA", "Lead Bank (Found)"),
    ("Fabricated Donuts", "Wealthsimple"),                                          # a bare merchant
]


@pytest.mark.parametrize(("description", "bank"), CARD_POSTINGS)
def test_card_postings_in_every_bank_format_are_never_a_d6_recurrence(description, bank):
    assert _states(description, bank=bank) == OTHER


@pytest.mark.parametrize(
    ("description", "bank"),
    [
        ("Capital Fuel Card spend", None),                                           # a financing root
        ("Fabricated Holdings LLC Card spend", None),                                # an organisation word
        ("DEBIT CARD RECURRING PYMT FAB EQUITIES LLC 800-555-0100 NY 4321", "Truist"),
        ("Recurring Payment authorized on 01/02 Fabcreditacceptance NY S123456789012345 Card 4321", None),
        ("FABCO RECOVERY LLC, BROOKLYN, NY", "Bluevine"),
        ("FAB DEBT SETTLEMENT, BROOKLYN, NY", "Bluevine"),                         # a settlement payee
        ("FAB DEBT SETTLEMENT Card spend", None),
        ("CREDIBLYCO, BROOKLYN, NY", "Bluevine"),                                  # a CRED-prefixed name
        ("FABRICATED, INC., NEW YORK, NY", "Bluevine"),
        ("FAB NATIONAL A BANK OF TULSA, TULSA, OK", "Bluevine"),                     # a bank: stays reviewed
        ("FAB DINER42, SPRINGFIELD, IL", "Wells Fargo"),                             # the suffix is read on two banks only
        ("Pre-authorized Debit to FABRICATED WIDGETS", "Wealthsimple"),              # a Wealthsimple channel label
        ("Fab Credit Union", "Wealthsimple"),
        ("ACH DEBIT FABRICATED WIDGETS LLC", None),
        ("FABRICATED WIDGETS DES:PURCHASE ID:0000 INDN:PAT EXAMPLE CO ID:0000 CCD", None),
        ("PURCHASE FABRICATED FUNDING", None),                                       # an ACH entry description first
    ],
)
def test_card_formats_never_hide_a_row_that_names_financing_or_an_organisation(description, bank):
    assert _states(description, bank=bank) == D6


def test_a_card_posting_leaves_the_recurring_debit_view():
    from analysis.detect import find_recurring_debits

    statement = Statement(transactions=[txn(f"2054-01-{day:02d}", "Fabricated Donuts Card spend", -100.0)
                                        for day in WEEKLY])
    assert find_recurring_debits(statement) == []


# --- A2: person-to-person, wallet and card-push rails -------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Virement envoye Pat Example",
        "Virement par Banque en direct - 1234",                    # RBC's French online-banking transfer
        "Zel To Pat Example PNCAA0X7654321",
        "PMNT SENT 0105 APPLE CASH 1234 CA",
        "Payment Sent 01/05 Pat Example CA Card 4321",            # Chase's card push (c00022's shape)
        "FAB GOODS IAT PAYPAL",
        "WISE US INC DES:WISE ID:0001",
        "GREENLIGHT DES:APP ID:0001",
    ],
)
def test_person_to_person_and_wallet_rails_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "Virement envoye Fabrique Funding Inc",
        "Zel To Fabricated Global Funding PNCAA0X7654321",
        "PMNT SENT 0105 FABRICATED FUNDING LLC",
        "WISE CHOICE LLC",                                         # bare WISE is never a rail
        "ZEL TO FAB SETTLEMENT PNCAA0X7654321",                    # a settlement payee paid by Zelle
        "FINWISE DES:LOANPMT ID:0001",
    ],
)
def test_a_rail_that_names_financing_stays_in_review(description):
    assert _states(description) == D6


# --- A3: transfer templates -----------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "TRF DT INTERNET 12345",
        "INTERNET XFR TO CHECKG x1234",
        "Internet/Phone Trsfr",
        "EXT TRNSFR 12345",
        "INTERNET TRANSFER123456789012 TO: 12345",               # CIBC, transfer word glued to its reference
        "E-TRANSFER104567890123 Pat Example",
        "BKOFAMERICA BC 01/05 12345 TO CHKG 12345 FAB ST",        # P2: owner may strike it
        "Internet Withdrawal",
        "ACH Web Smartsave 12345 Atlasfinancial 999",
        "RTP SENT PAT EXAMPLE",
        "Real Time Payment To Pat Example",
    ],
)
def test_transfer_templates_of_an_unnamed_payee_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "E-TRANSFER104567890123 Fabrique Capital Inc",
        "INTERNET XFR TO FABRICATED CAPITAL LLC",
        "OUTGOING WIRE TRF FABRICATED CAPITAL LLC",
        "FABRICATED CAPITAL DES:TRF ID:0001 CCD",                  # a funder's own entry description
        "SMART SAVE FUNDING LLC",
        "RTP SENT FABCO LLC",                                      # an organisation: stays reviewed
    ],
)
def test_a_transfer_template_never_hides_a_named_or_financing_payee(description):
    assert _states(description) == D6


# --- A4: cash, own ACH-batch offsets, school and childcare ---------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "BKOFAMERICA ATM 01/05 #000123 WITHDRWL FAB BRANCH",
        "ATM NETWORK CASH WITHDRAWAL",
        "ABM WITHDRAWAL FAB TOWN ON",
        "GC 1234-CASH WITHDRA",
        "G/RETRAIT",
        "RETRAIT PAR GA 1234",
        "ACH SETTLMT REL DATE_FUND HNB HVACH PAT EXAMPLE",
        "BUS ONLINE ACH SETTLEMENT",
        "FAB SCHOOL DES:FACTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB",
        "KINDERCARE 1234567",
        "FAB ACADEMY TUITION 1234",
    ],
)
def test_cash_own_batches_and_school_billing_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    [
        "FAKE QUICK CASH WITHDRAWAL",
        "ABM FUNDING WITHDRAWAL",
        "ATM FAKE CAPITAL WITHDRAWAL",
        "WITHDRAWAL ABM FAKE CAPITAL",
        "RETRAIT GA FAKE CAPITAL",
        "ACH SETTLEMENT ACH BATCH FAKE CAPITAL LLC",
    ],
)
def test_a_payee_name_never_fills_a_cash_template(description):
    assert _states(description) == D6


# --- A5: named savings and investing originators --------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Orig CO Name:Stash Capital (S Orig ID:0001 Desc Date: CO Entry Descr:ACH Sec:Web Ind ID:0002 Ind Name:Pat Example",
        "Orig CO Name:Alinea Orig ID:0001 CO Entry Descr:Payment Sec:PPD",
        "Fid Bkg Svc LLC Moneyline 1234567 Pat Example",
        "Paid To - Albert Edi Pymnts Chk 1234567",
        "ALBERT DES:EDI PYMNTS ID:0001 INDN:PAT EXAMPLE CO ID:0002 WEB",
        "ACORNS INVEST DES:1234 ID:0001",
        "ROBINHOOD DEBITS 1234",
        "COINBASE INC 1234",
        "BETTERMENT 1234",
        "WEALTHFRONT 1234",
    ],
)
def test_named_savings_and_investing_originators_are_not_d6_payees(description):
    assert _states(description) == OTHER


def test_a_savings_brand_beside_financing_words_stays_in_review():
    assert _states("ALINEA CAPITAL DAILY PMT") == D6


def test_the_savings_names_never_reach_a_registered_payee():
    # The admitted Albert Corporation alias is a known payee (step 7), and a potential alias with EDI PYMNTS stays
    # a candidate: the skip only reads rows no rule claimed.
    assert classify_transaction("ALBERT GENIUS EDI PYMNTS", -100.0).classification == "personal_loan"
    assert classify_transaction("GLOBAL MER EDI PYMNTS", -100.0).match_method == "candidate_lender_alias"


# --- A6: vendors and other named non-lender payees -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("description", "account_name"),
    [
        ("FAB BOOKKEEPING LLC DES:BILL ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", None),
        ("CINTAS CORP 123 DES:CINTAS ID:0001", None),
        ("FABRIKAM MFG INC INVOICES 1234567", None),                 # the originator segment, ended by its reference
        ("FAB FOODSERVICE VENDOR PAY 0001", None),
        ("UNIFIRST", None),                                          # one word: the vendor word is the first
        ("FAB FOODSERVICE VENDOR PAY", "FABRIKAM TRADING LLC"),      # a run of words, the holder known
        ("FACEBK ADS 12345", None),
        ("Bill.com Fab Supplies Inc - Inv 1234", None),
        ("ARAMARK UNIFORM SERVICES 1234567", None),
        ("SUBWAY ROYALTY DES:ROYALTY ID:0001", None),
        ("PUSHPAY 1234567", None),
        ("E ZPASS 1234567", None),
        ("DRAFTKINGS 1234567", None),
        ("FAB MARKETING FUND LLC 0001", None),
    ],
)
def test_vendors_and_named_non_lenders_are_not_d6_payees(description, account_name):
    assert _states(description, account_name=account_name) == OTHER


@pytest.mark.parametrize(
    ("description", "account_name"),
    [
        ("PMTS FABLEASE FACEBK", None),                            # an ad word after a lessor's name
        ("Bill.com Fab Credit Corp - Inv 1234", None),
        ("FAB FINANCIAL INVOICE 12345", None),
        ("FAB GRP FUNDIN INVOICE", None),
        ("FAB CAPITA INVOICES", None),
        ("MFG LLC DES:PAYMENT ID:0001 CCD", None),                  # a funder's own abbreviation
        ("FAB WHOLESALE PMT", None),
        ("FAB FACTORING INVOICE", None),
        ("FAB LLC DAILY INVOICE", None),
        ("FAB LLC RTR INVOICE", None),
        ("BUSINESS PAD FAB INVOICES", None),
        ("PAYMENT FABRIKAM CCD FAB DISTRIBUTING LLC", "FAB DISTRIBUTING LLC"),  # the holder's own trade word
        # label-less rows that are one run of words, the holder unknown: the receiver may be the holder
        ("KAPIFAB LLC ACHPMT FAB UNIFORMS LLC", None),                # Regions
        ("KAPIFAB ACHPMT FAB UNIFORMS LLC", None),
        ("KAPIFAB PAY PAYMENT TO FAB LANDSCAPING LLC", None),         # Bluevine
        ("FAB FOODSERVICE VENDOR PAY", None),
    ],
)
def test_a_vendor_word_never_hides_a_financing_payee_or_reads_the_holder(description, account_name):
    assert _states(description, account_name=account_name) == D6


# --- A7: tax and government payees -------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "Online Payment 1234 To United States Treasury",
        "PAD CCRA CANADA",
        "STATE OF FABSTATE SOS EFT",
        "NYS DTF WT DES:NYS DTF WT ID:0001 INDN:FABRIKAM CORP CO ID:0002 CCD",
        "MI TREASURY 1234",
        "PAD WSIB",
        "EFTPS PAYMENT 1234",
    ],
)
def test_tax_and_government_payees_are_not_d6_payees(description):
    assert _states(description) == OTHER


@pytest.mark.parametrize(
    "description",
    ["TREASURY CAPITAL GROUP LLC", "ACH DEBIT CCRA HOLDINGS LLC", "FABRICATED WIDGETS DES:CCRA ID:0001"],
)
def test_a_government_word_never_hides_a_named_payee_or_reads_an_entry_field(description):
    assert _states(description) == D6


@pytest.mark.parametrize(
    "description",
    ["BUSINESS PAD FABTOWN MIN OF FINANCE", "FAB CITY DEPT OF FINANCE PARKING ACH DEBIT", "ADVANCE AUTO PARTS ACH DEBIT"],
)
def test_government_finance_departments_and_a_named_retailer_are_no_keyword_recurrence(description):
    assert _states(description) == {("other", "financing_keyword_review")}


def test_a_financing_keyword_payee_still_recurs():
    assert _states("ACH DEBIT FABRICATED FUNDING LLC") == {("potential_lender", "recurring_financing_counterparty")}


# --- A8: family support ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "FS CHILD SUPPORT DES:PAYMENT ID:0001",
        "CO FAM SUPP REG 1234",
        "FB SDU DES:CHILD SUPP ID:0001 INDN:FABRIKAM CORP CO ID:0002 CCD",
        "Orig CO Name:Fab SDU Orig ID:0001 Desc Date: CO Entry Descr:Chld Supp Sec:CCD",
        "STATE DISBURSEMENT UNIT ACH DEBIT",
    ],
)
def test_family_support_payments_are_not_d6_payees(description):
    assert _states(description) == OTHER


def test_family_support_words_in_a_financing_row_stop_the_keyword_recurrence():
    assert _states("ACH DEBIT CHILD SUPPORT ADVANCE 0000") == {("other", "financing_keyword_review")}


@pytest.mark.parametrize(
    "description",
    [
        "FABRICATED RIVER CAPITAL DES:PAYMENT ID:0001 INDN:CHILD SUPPORT SVCS LLC CO ID:0002 CCD",  # the holder
        "ACH DEBIT FAMILY SUPPORT CAPITAL LLC",
        "ACH DEBIT CHILDS CAPITAL LLC",
    ],
)
def test_a_family_support_word_never_hides_a_funder(description):
    assert _states(description) == D6
