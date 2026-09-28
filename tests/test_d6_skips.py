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
