"""Classification 5.6 (true revenue spec §6.3, §8.2, §8.4 T13, §20; audit fix batch B2: I01, I21, I20, I48): own-account
transfers and the bare-transfer counterparty reading. A bank's name, an online-banking channel code or an account
description never names a transfer's counterparty (Q2: such a transfer is held, transfer_no_counterparty); the
holder's own-account forms (overdraft sweeps, card and credit-line transfers, the own-account designations a bank
prints with FRM, XFR, DDA or CHECKG) are non-revenue; a named sender printed after an own-account designation is held
for review (T13, §6.3 narrowing 8); an explicit cash, ATM or check deposit form is counted (Q2, Q3). Fabricated rows
only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import true_revenue
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    classify_statement_transactions,
    normalize_transaction_description,
    prints_internal_transfer_designation,
    revenue_text,
)

HOLDER = "NORTHWIND PLUMBING LLC"
HELD = "excluded_pending_review"
COUNTED = "counted_flagged"


def _one(text: str, bank: str | None = "Fabrikam Bank", amount: float = 1000.0, *, holder: str | None = HOLDER):
    return classify_statement_transactions(Statement(bank=bank, account_name=holder, transactions=[
        Transaction(date="2054-03-02", description=text, amount=amount, direction="credit"),
    ]))[0]


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


# I01: a bank's name, a channel code or an account description is never a transfer's counterparty (Q2).
@pytest.mark.parametrize(("bank", "text"), [
    # Truist's own name before its online-transfer layout; MOBILE is a channel word, not a sender.
    ("Truist", "TRUIST ONLINE TRANSFER MOBILE FROM 5678"),
    # Citi Business Online, Chase's external-transfer code, online banking, telephone banking.
    ("Citibank", "CBUSOL TRANSFER CREDIT ONLINE REFERENCE 654321"),
    ("Mission Valley Bank", "JPMORGAN CHASE EXT TRNSFR 12345678901"),
    ("Fabrikam Bank", "TRNSFR CREDIT OLB XFER FROM 5678"),
    ("Royal Bank of Canada", "TELEPHONE BANKING TRANSFER REFERENCE 1"),
    ("U.S. Bank", "EXT TFR DEPOSIT TRN AB12CD3EFG45678"),
    ("Fabrikam Bank", "TELEPHONE TRF DEP"),
    # A credit union's institution name (one word before CU or FCU) and a bank's glued name.
    ("Shopify Balance", "ACH TRANSFER FROM FABRIKAM CU"),
    ("Fabrikam Bank", "ACH TRANSFER FROM CONTOSO FCU"),
    ("Fabrikam Bank", "TRANSFER USAAFSBTRNSFER"),
    # FUNDING beside TRANSFER is the bank's channel, not a funder's name.
    ("Fabrikam Bank", "FUNDING TRANSFER CREDIT TRANSFER FROM 12345678901234"),
    # The statement's own bank, printed before a transfer.
    ("Northwind Community Bank", "NORTHWIND COMMUNITY BANK ONLINE TRANSFER 123456"),
    # TRF is transfer wording; CT and a reference name nobody.
    (None, "TRF CT INTERNET D123"),
    # The glued and spelled-out transfer wording I21 adds; PHONE and CMO are channel words.
    ("Fabrikam Bank", "INTERNET PHONE TRSFR"),
    ("CIBC", "CMO TRANSFER123456789012"),
    (None, "TRANSF FONDS CT 123"),
    # The control: a bare online transfer was held before.
    ("Fabrikam Bank", "ONLINE TRANSFER REFERENCE 123456"),
])
def test_a_transfer_whose_only_words_are_a_bank_or_a_channel_is_held(bank, text):
    record = _one(text, bank)
    assert _tier(record) == (HELD, "transfer_no_counterparty")
    assert record.revenue_classification == "unverified_deposit"


@pytest.mark.parametrize(("bank", "text"), [
    # A real company or a person after FROM stays a named transfer: counted, flagged, never verified (Q4).
    ("Fabrikam Bank", "ONLINE TRANSFER FROM CONTOSO SEAFOOD CORP"),
    ("Truist", "TRUIST ONLINE TRANSFER FROM CONTOSO SEAFOOD LLC"),
    ("Fabrikam Bank", "ONLINE TRANSFER FROM PAT SAMPLE FABRIKAM CU"),
    ("Fabrikam Bank", "ONLINE TRANSFER FROM SAMPLE FABRIKAM CU"),
    ("Fabrikam Bank", "ONLINE TRANSFER FROM PAT SAMPLE WELLS FARGO"),
    # A credit union's own-name transfer from a person keeps the person.
    ("Fabrikam Bank", "FABRIKAM CU TRANSFER PAT SAMPLE"),
    # Unconfirmed (I01, I28): a custodian's name is not stripped; the row keeps its reading.
    ("Chase", "ORIG CO NAME BNY MELLON NA ORIG ID 1234567890 DESC DATE 540302 CO ENTRY DESCR TRANSFER SEC PPD "
              "TRACE 123456789012345"),
    # Wealthsimple prints its memo after TRANSFER IN: no savings folder there.
    ("Wealthsimple", "TRANSFER IN SAMPLE SUPPLIES"),
    # Square: a company named after TRANSFER IN is no savings folder.
    ("Square", "TRANSFER IN CONTOSO SEAFOOD LLC"),
])
def test_a_named_counterparty_keeps_the_named_transfer_reading(bank, text):
    assert _tier(_one(text, bank)) == (COUNTED, "p2p")


@pytest.mark.parametrize(("bank", "text"), [
    # Truist's own-account layout repeats its channel word between TRANSFER and FROM.
    ("Truist", "TRUIST ONLINE TRANSFER ONLINE FROM 5678"),
    ("Truist", "TRUIST ONLINE TRANSFER FROM 5678"),
    # TD's credit-line source, like its savings and checking siblings.
    ("TD Bank", "ETRANSFER CREDIT ONLINE XFER TRANSFER FROM CL 1234567890"),
    ("TD Bank", "ETRANSFER CREDIT ONLINE XFER TRANSFER FROM SV 1234567890"),
    ("TD Bank", "ETRANSFER CREDIT ONLINE XFER TRANSFER FROM CK 1234567890"),
    # I21: overdraft sweeps, card and credit-line transfers, Regions' electronic banking from checking.
    ("Wells Fargo", "OVERDRAFT PROTECTION FROM 9999999999"),
    ("Fabrikam Bank", "OVERDRAFT PROTECTION TRANSFER FROM SAVINGS 1234"),
    ("Huntington National Bank", "OD PROTECTION TRANSFER FROM CREDIT CARD"),
    ("Wells Fargo", "OVERDRAFT XFER FROM CREDIT CARD OR LINE"),
    ("Fabrikam Bank", "ODP TRANSFER 1234"),
    ("Bank of America", "ONLINE BANKING TRANSFER FROM CRD 1111 CONFIRMATION 1234567890"),
    ("Fabrikam Bank", "ONLINE TRANSFER FROM LINE OF CREDIT 1234"),
    ("Fabrikam Bank", "TRANSFER FROM CREDIT LINE 1234"),
    ("Fabrikam Bank", "XFER FROM LOC 1234"),
    ("Fabrikam Bank", "TRANSFER FROM LOC 1234"),
    ("Regions Bank", "EB FROM CHECKING 9999999999 REF 123456 1234567"),
    ("Regions Bank", "EB FROM SAVINGS 9999999999"),
    # The own-account designations spelled FRM, XFR, DDA and CHECKG.
    ("Fabrikam Bank", "INTERNET XFR FRM CHECKG 1111"),
    ("Fabrikam Bank", "DEPOSIT INTERNET XFR FRM CHECKG X1111"),
    ("Zions Bank", "ONLINE XFER FROM DDA 1111 ID 123456789"),
    ("Huntington National Bank", "TFR FRM CHECKING 1111"),
])
def test_the_holder_s_own_account_forms_are_non_revenue(bank, text):
    record = _one(text, bank)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert record.revenue_tier == "non_revenue"


@pytest.mark.parametrize(("bank", "text", "reading"), [
    # Q4: CIBC's glued e-transfer is the e-transfer rail's own form, never the glued TRANSFER I21 reads.
    ("CIBC", "E TRANSFER123456789012 PAT SAMPLE 1234 567", (COUNTED, "named_payer_unlabelled")),
    # Audit B8 (I46): TRANSFERS is transfer wording once revenue_text cuts a TD footer's FUNDS TRANSFERS; with a named
    # counterparty it is a named transfer (T13, Q4).
    ("Fabrikam Bank", "CONTOSO SEAFOOD TRANSFERS", (COUNTED, "p2p")),
    # A company that holds a word of the strip lists keeps its name.
    ("Fabrikam Bank", "ONLINE TRANSFER FROM CONTOSO OVERDRAFT SERVICES LLC", (COUNTED, "p2p")),
    # A teller or branch transfer still prints no counterparty (M4).
    ("Fabrikam Bank", "TELLER TRANSFER", (HELD, "transfer_no_counterparty")),
    ("Fabrikam Bank", "BRANCH TRANSFER", (HELD, "transfer_no_counterparty")),
    ("Fabrikam Bank", "COUNTER CREDIT TRANSFER", (HELD, "transfer_no_counterparty")),
])
def test_the_strip_lists_read_no_further_than_their_forms(bank, text, reading):
    assert _tier(_one(text, bank)) == reading


# I01 (the ACH payer reader): a payer region that is only a bank's name and an account description names no payer.
@pytest.mark.parametrize(("bank", "text", "reading"), [
    ("Brex", "FABRIKAM BANK SAVINGS 1234 ACH", (HELD, "transfer_no_counterparty")),
    ("Brex", "SAMPLE BUSINESS BANKING OPERATING ACCOUNT ACH", (HELD, "transfer_no_counterparty")),
    ("Brex", "BANK OF AMERICA SAVINGS 1234 ACH", (HELD, "transfer_no_counterparty")),
    # A company's ACH keeps Q6's company-form verification; a person's one-off payment stays counted.
    ("Brex", "CONTOSO SEAFOOD CORP ACH", ("verified", None)),
    ("Brex", "FABRIKAM BANKING SOLUTIONS LLC ACH", ("verified", None)),
    ("Brex", "PAT SAMPLE ACH", (COUNTED, "named_payer_one_off")),
    # A company's own savings account is no bank's name: the payer keeps its reading.
    ("Brex", "CONTOSO SEAFOOD SAVINGS 1234 ACH", (COUNTED, "named_payer_one_off")),
])
def test_a_bank_account_description_names_no_ach_payer(bank, text, reading):
    assert _tier(_one(text, bank)) == reading


@pytest.mark.parametrize(("text", "reading"), [
    # T13 (I01): a bare 'FROM <digits>' designates an account, so a named transfer printing it is held.
    ("TRANSFER FROM 1234 CONTOSO SEAFOOD CORP", (HELD, "transfer_account_designation")),
    ("XFER FROM 1234 PAT SAMPLE", (HELD, "transfer_account_designation")),
    # A numbered company's number after FROM is its name (§5.2, T11; OQ3: counted, never verified).
    ("TRANSFER FROM 1234567 ONTARIO INC", (COUNTED, "p2p")),
    ("TRANSFER FROM 1234 5678 QUEBEC INC", (COUNTED, "p2p")),
])
def test_a_bare_from_account_number_designates_an_account(text, reading):
    assert _tier(_one(text)) == reading


def test_two_pulls_from_one_bank_account_are_never_verified_by_repetition():
    records = classify_statement_transactions(Statement(bank="Brex", account_name=HOLDER, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description="FABRIKAM BANK SAVINGS 1234 ACH", amount=1000.0,
                    direction="credit") for day in (2, 9)
    ]))
    assert {_tier(record) for record in records} == {(HELD, "transfer_no_counterparty")}


# I21: Square's savings folders are the holder's own money, held like GENERAL SAVINGS.
@pytest.mark.parametrize("text", ["TRANSFER IN RAINY DAY", "TRANSFER IN RENT", "TRANSFER IN GENERAL SAVINGS"])
def test_a_square_savings_folder_is_held(text):
    assert _tier(_one(text, "Square")) == (HELD, "transfer_account_designation")


def test_a_square_folder_is_held_even_when_its_round_sums_repeat():
    records = classify_statement_transactions(Statement(bank="Square", account_name=HOLDER, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description="TRANSFER IN RAINY DAY", amount=500.0, direction="credit")
        for day in (2, 9)
    ]))
    assert {_tier(record) for record in records} == {(HELD, "transfer_account_designation")}


# I20, §6.3 narrowing 8: a named sender printed after an own-account designation is held for review (T13).
@pytest.mark.parametrize(("bank", "text"), [
    ("Bank of America", "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E CONTOSO SEAFOOD CORP"),
    ("Bank of America", "MOBILE TRANSFER FROM SAV 1234 CONFIRMATION ABCDEFGHI PAT SAMPLE"),
    ("Fabrikam Credit Union", "TFR FROM XXXXXX1234 TRANSFER DEPOSIT CONTOSO LAWN CARE LLC"),
    # A payout entity named there claims nothing: the narrowing only ever holds the row.
    ("Bank of America", "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E SEZZLE"),
])
def test_a_named_sender_after_an_own_account_designation_is_held(bank, text):
    record = _one(text, bank)
    assert _tier(record) == (HELD, "transfer_account_designation")
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_review_required is True


@pytest.mark.parametrize(("bank", "text", "holder"), [
    # No name after the designation: the holder's own transfer.
    ("Bank of America", "ONLINE BANKING TRANSFER FROM CHK 1234 CONFIRMATION 1234567890", HOLDER),
    ("Bank of America", "MOBILE TRANSFER FROM SAV 1234 CONFIRMATION 1234567890", HOLDER),
    ("Fabrikam Credit Union", "TFR FROM XXXXXX1234 TRANSFER DEPOSIT", HOLDER),
    # The holder's own name after the designation.
    ("Bank of America", "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E NORTHWIND PLUMBING LLC", HOLDER),
    # Another non-revenue rule reads the row too.
    ("Bank of America", "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E CONTOSO LOAN SERVICES", HOLDER),
    # Navy Federal's SHARES form is outside the two layouts (its holder test is blind).
    ("Navy Federal Credit Union", "TRANSFER FROM SHARES PAT SAMPLE", HOLDER),
    ("Navy Federal Credit Union", "TRANSFER FROM CHECKING PAT SAMPLE", HOLDER),
])
def test_an_own_account_designation_without_another_sender_stays_non_revenue(bank, text, holder):
    record = _one(text, bank, holder=holder)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_tier == "non_revenue"


def test_the_package_pairing_designation_is_unchanged_for_the_named_form():
    # R-d (prints_internal_transfer_designation) reads no holder; the named form still designates an account there.
    assert prints_internal_transfer_designation(
        "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E CONTOSO SEAFOOD CORP")
    assert prints_internal_transfer_designation("TFR FROM XXXXXX1234 TRANSFER DEPOSIT CONTOSO LAWN CARE LLC")


# I48: an explicit cash, ATM or check deposit form is counted (Q2, Q3); a teller or branch transfer stays held (M4).
@pytest.mark.parametrize(("bank", "text", "reading"), [
    ("Square", "CASH DEPOSIT TRANSFER IN", (COUNTED, "no_payer_printed")),
    ("Fabrikam Bank", "ATM DEPOSIT TRANSFER ATM DEPOSIT", (COUNTED, "no_payer_printed")),
    ("Fabrikam Bank", "MOBILE CHECK DEPOSIT TRANSFER", (COUNTED, "check_deposit")),
    ("Fabrikam Bank", "REMOTE DEPOSIT TRANSFER", (COUNTED, "check_deposit")),
    ("Fabrikam Bank", "TELLER TRANSFER", (HELD, "transfer_no_counterparty")),
    # A cash or branch transfer that names its counterparty follows T13.
    ("Fabrikam Bank", "BRANCH TRANSFER FROM CONTOSO BAKERY LLC", (COUNTED, "p2p")),
    ("Fabrikam Bank", "TELLER TRANSFER FROM CONTOSO BAKERY LLC", (COUNTED, "p2p")),
    ("Fabrikam Bank", "BRANCH TRANSFER FROM CONTOSO BAKERY LLC CHECKING 1234", (HELD, "transfer_account_designation")),
])
def test_an_explicit_deposit_form_beats_bare_transfer_wording(bank, text, reading):
    assert _tier(_one(text, bank)) == reading


def test_the_census_reads_the_same_transfer_fact_as_the_pass():
    # G4 (§14.3): the census's transfer_no_counterparty fact is the pass's own, with the statement's bank.
    for bank, text, expected in (
        ("Truist", "TRUIST ONLINE TRANSFER MOBILE FROM 5678", True),
        ("Square", "CASH DEPOSIT TRANSFER IN", False),
        ("Fabrikam Bank", "TELLER TRANSFER", True),
        ("Fabrikam Bank", "ONLINE TRANSFER FROM CONTOSO SEAFOOD CORP", False),
        ("Brex", "FABRIKAM BANK SAVINGS 1234 ACH", True),
        ("Northwind Community Bank", "NORTHWIND COMMUNITY BANK ONLINE TRANSFER 123456", True),
    ):
        record = _one(text, bank)
        facts = true_revenue.guard_facts(record, revenue_text(normalize_transaction_description(text)))
        assert facts["transfer_no_counterparty"] is expected, text
