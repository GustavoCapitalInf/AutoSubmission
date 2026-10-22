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
from analysis.transaction_classifier import classify_statement_transactions, prints_internal_transfer_designation
from analysis.descriptor.lexical import revenue_text
from analysis.description_text import normalize_transaction_description

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
    # Q4: CIBC's glued e-transfer is the e-transfer rail's own form, never the glued TRANSFER I21 reads. Audit round 2,
    # R2-B11 (R44): the revenue text splits the reference off the rail, so the rail reads it as a person-to-person row.
    ("CIBC", "E TRANSFER123456789012 PAT SAMPLE 1234 567", (COUNTED, "p2p")),
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
    # Audit round 3, R3-B07 (R3-14; §8.5's bank words): a payer whose name holds BANKING is no bank's name here (the
    # payer keeps its reading), but Q6 never verifies it by its company form: counted once.
    ("Brex", "FABRIKAM BANKING SOLUTIONS LLC ACH", (COUNTED, "named_payer_one_off")),
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


# Audit round 2, R2-B11 (R29; no behaviour change, §20's B2 I21 line): Square prints an outside sender in Details
# before its activity type ('<sender> TRANSFER IN', read like any named transfer), so only a folder move prints
# TRANSFER IN first, and a folder named for a person, or any custom folder name, is still the holder's own money.
@pytest.mark.parametrize(("bank", "text", "reading"), [
    # A person's name or a custom name after TRANSFER IN is a folder of the holder's (the B02 brief's person test is
    # not applied).
    ("Square", "TRANSFER IN PAT SAMPLE", (HELD, "transfer_account_designation")),
    ("Square", "TRANSFER IN SAMPLE HOME", (HELD, "transfer_account_designation")),
    # The layout: an outside sender prints before the activity type.
    ("Square", "PAT SAMPLE TRANSFER IN", (COUNTED, "p2p")),
    ("Square", "FABRIKAM INC TRANSFER IN", (COUNTED, "p2p")),
    # Controls: a company form after TRANSFER IN, the known folders, the tax folder, and other banks.
    ("Square", "TRANSFER IN CONTOSO SUPPLY LLC", (COUNTED, "p2p")),
    ("Square", "TRANSFER IN RAINY DAY", (HELD, "transfer_account_designation")),
    ("Square", "TRANSFER IN RENT", (HELD, "transfer_account_designation")),
    ("Square", "TRANSFER IN GENERAL SAVINGS", (HELD, "transfer_account_designation")),
    ("Square", "TRANSFER IN TAX", (HELD, "transfer_no_counterparty")),
    ("Wealthsimple", "TRANSFER IN PAT SAMPLE", (COUNTED, "p2p")),
    ("Fabrikam Bank", "TRANSFER IN PAT SAMPLE", (COUNTED, "p2p")),
])
def test_r29_square_prints_an_outside_sender_before_transfer_in(bank, text, reading):
    assert _tier(_one(text, bank, amount=750.0)) == reading


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


# Audit round 2, R2-B09 (R45): a glued ONLINETRANSFER, MOBILETRANSFER or INTERNETTRANSFER is transfer wording, and
# CHCKING, CHKING and CKG designate an account, so the holder's own-account transfer is held on its own text (T13, Q2),
# not by an accident of the account-name field.

def _reading(record):
    return record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method


R45_HOLDER = "CONTOSO TRADING LLC"
R45_ROW = "COMM ONLINETRANSFER FROM COMM BUS CHCKING 00000000 ON 1 12 31 AT 9 30"


def _rows(rows, *, bank="Fabrikam Bank", holder=R45_HOLDER):
    return classify_statement_transactions(Statement(bank=bank, account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


@pytest.mark.parametrize("holder", [R45_HOLDER, None])
def test_r45_a_glued_online_transfer_from_a_product_account_is_held_on_its_own_text(holder):
    assert _reading(_one(R45_ROW, amount=5000.0, holder=holder)) == (HELD, "transfer_account_designation")


def test_r45_a_product_account_name_still_reads_as_the_holder():
    assert _reading(_one(R45_ROW, amount=5000.0, holder="COMM BUS CHCKING")) == (HELD, "holder_name")


@pytest.mark.parametrize("text", ["MOBILETRANSFER FROM BUS CKG 00000000", "INTERNETTRANSFER FROM CHKING 00000000"])
def test_r45_a_glued_transfer_from_an_account_abbreviation_names_no_counterparty(text):
    assert _reading(_one(text, amount=5000.0, holder=R45_HOLDER)) == (HELD, "transfer_no_counterparty")


def test_r45_the_matching_debit_holds_the_credit_and_is_itself_unchanged():
    credit, debit = _rows([(R45_ROW, 5000.0), ("COMM ONLINETRANSFER TO COMM BUS CHCKING 00000000", -5000.0)])
    assert _reading(credit) == (HELD, "payer_also_debited")
    assert (debit.classification, debit.canonical_entity, debit.contributes_to_lender_count,
            debit.contributes_to_potential_lender_count, debit.contributes_to_lender_totals,
            debit.contributes_to_withholding_rate, debit.reversed_by, debit.revenue_tier) == (
        "other", None, False, False, False, False, None, None)


# R2-B09 review round 1 (R45, a recorded residual, §20): the glued wording is read on credits; the debit reader's payee
# keys do not yet read past a glued ONLINETRANSFER, so a glued transfer debit to a named payer does not hold that payer's
# credit as the spaced form does (0 corpus rows: no other bank prints the glued spellings).
@pytest.mark.parametrize(("debit", "reading"), [
    ("ONLINE TRANSFER TO FABRIKAM SUPPLY LLC 00000000", (HELD, "payer_also_debited")),
    ("ONLINETRANSFER TO FABRIKAM SUPPLY LLC 00000000", ("verified", "named_payer_company_form")),
])
def test_r45_a_glued_transfer_debit_to_a_named_payer_is_a_recorded_residual(debit, reading):
    credit, _ = _rows([("FABRIKAM SUPPLY LLC DES PAYMENT ID 1 INDN CONTOSO TRADING LLC CO ID 1 CCD", 1000.0),
                       (debit, -700.0)], bank="Bank of America")
    assert _reading(credit) == reading


@pytest.mark.parametrize(("text", "reading"), [
    ("ONLINETRANSFER FROM FABRIKAM SUPPLY LLC 00000000", (COUNTED, "p2p")),
    ("ONLINE TRANSFER FROM BUSINESS CHECKING 00000000", (HELD, "transfer_no_counterparty")),
    ("ONLINE TRANSFER PAYMENT CREDIT NORTHWIND", (COUNTED, "named_payer_one_off")),
    ("NORTHWIND SUPPLY DES:PAYMENT ID:1 INDN:CONTOSO TRADING LLC CO ID:1 CCD", (COUNTED, "named_payer_one_off")),
])
def test_r45_the_controls_keep_their_readings(text, reading):
    assert _reading(_one(text, amount=5000.0, holder=R45_HOLDER)) == reading


@pytest.mark.parametrize(("text", "transfer"), [
    ("COMM ONLINETRANSFER FROM COMM BUS CHCKING", True),
    ("MOBILETRANSFER FROM BUS CKG", True),
    ("INTERNETTRANSFERS 1234", True),
    # The glued AmEx label keeps the label's rule: exempt only before an originator.
    ("ONLINETRANSFER PAYMENT CREDIT CONTOSO SRE INC EFT 1234", False),
    ("ONLINETRANSFER PAYMENT CREDIT", True),
    ("CONTOSOTRANSFER LLC", False),
    ("ONLINETRANSFERX", False),
])
def test_r45_the_glued_transfer_wording(text, transfer):
    from analysis import description_text

    assert bool(description_text._TRANSFER_WORDING.search(text)) is transfer


@pytest.mark.parametrize(("text", "designation"), [
    ("FROM COMM BUS CHCKING 1234", True),
    ("FROM CHKING 1234", True),
    ("FROM BUS CKG 1234", True),
    ("FROM CKGROUP LLC", False),
    ("FROM CONTOSO CHKINGS", False),
])
def test_r45_the_account_abbreviations(text, designation):
    assert true_revenue._account_designation(text) is designation


# Audit round 2, R2-B09 (R28): transfer wording inside a company-formed ACH originator's name (before DES, after ORIG CO
# NAME) is the company's name, never a transfer: the row is an ACH payment Q6 reads. The entry field's transfer wording
# (DES:TRANSFER, CO ENTRY DESCR:BANK XFER) is still read, and a name with no company form keeps the transfer reading.

R28_HOLDER = "NORTHWIND PLUMBING LLC"
R28_BOFA = "{name} DES {entry} ID 1 INDN NORTHWIND PLUMBING CO ID 1 CCD"
R28_CHASE = ("ORIG CO NAME {name} ORIG ID 1234567890 DESC DATE CO ENTRY DESCR {entry} SEC CCD TRACE NO 1 EED 540302 "
             "IND ID 1 IND NAME NORTHWIND PLUMBING LLC TRN 1 TC")
VERIFIED_COMPANY = ("verified", "named_payer_company_form")


def _r28(layout, name, entry, amounts=(1234.56,)):
    bank = "Chase" if layout is R28_CHASE else "Bank of America"
    return [_reading(record) for record in _rows(
        [(layout.format(name=name, entry=entry), amount) for amount in amounts], bank=bank, holder=R28_HOLDER)]


@pytest.mark.parametrize(("layout", "name"), [
    (R28_BOFA, "CONTOSO TRF LLC"),
    (R28_BOFA, "CONTOSO TRANSFER INC"),
    (R28_BOFA, "TRF INDUSTRIES INC"),
    (R28_CHASE, "CONTOSO XFR LLC"),
])
def test_r28_a_company_whose_name_prints_a_transfer_word_verifies_by_its_form(layout, name):
    assert _r28(layout, name, "PAYMENT") == [VERIFIED_COMPANY]


def test_r28_such_a_company_paying_twice_verifies_as_a_repeat():
    assert _r28(R28_BOFA, "CONTOSO TRF LLC", "PAYMENT", (2000.0, 3000.0)) == [("verified", "named_payer_repeats")] * 2


@pytest.mark.parametrize(("layout", "name", "entry", "reading"), [
    (R28_BOFA, "CONTOSO SEAFOOD CORP", "PAYMENT", VERIFIED_COMPANY),
    (R28_BOFA, "CONTOSO TRANSFORM LLC", "PAYMENT", VERIFIED_COMPANY),
    # The entry field's transfer wording is still read.
    (R28_BOFA, "CONTOSO BAKERY LLC", "TRANSFER", (COUNTED, "p2p")),
    (R28_BOFA, "FABRIKAM TRF LLC", "TRANSFER", (COUNTED, "p2p")),
    (R28_CHASE, "CONTOSO SEAFOOD CORP", "TRANSFER", (COUNTED, "p2p")),
    (R28_CHASE, "SAMPLE CASH", "BANK XFER", (COUNTED, "p2p")),
    # A name with no company form keeps its transfer reading (CO is no form).
    (R28_BOFA, "SAMPLE BANK XFER", "PAYMENT", (COUNTED, "p2p")),
    (R28_BOFA, "TRANSFER AND STORAGE CO", "PAYMENT", (COUNTED, "p2p")),
    (R28_BOFA, "ONLINE TRANSFER", "PAYMENT", (HELD, "transfer_no_counterparty")),
    # The holds read the original text.
    (R28_BOFA, "NORTHWIND PLUMBING TRF LLC", "PAYMENT", (HELD, "holder_name")),
])
def test_r28_the_controls_keep_their_readings(layout, name, entry, reading):
    assert _r28(layout, name, entry) == [reading]


@pytest.mark.parametrize("text", ["INTERNET XFR FRM CHECKG 1234", "TRF CT INTERNET D123"])
def test_r28_rows_with_no_originator_field_keep_their_transfer_wording(text):
    from analysis import transaction_classifier
    from analysis import description_text

    found = transaction_classifier.credit_transfer_wording(text)
    assert found is not None and found.span() == description_text._TRANSFER_WORDING.search(text).span()


def test_r28_the_helper_blanks_only_the_originator_name_s_transfer_tokens():
    from analysis import transaction_classifier

    assert transaction_classifier.credit_transfer_wording("CONTOSO TRF LLC DES PAYMENT ID 1") is None
    row = "CONTOSO TRF LLC DES TRANSFER ID 1"
    found = transaction_classifier.credit_transfer_wording(row)
    assert found is not None and found.group(0) == "TRANSFER" and found.start() == row.index("DES TRANSFER") + 4
    # No company form once the token is out: the name's own word is read.
    assert transaction_classifier.credit_transfer_wording("SAMPLE BANK XFER DES PAYMENT ID 1").group(0) == "XFER"


# Audit round 2, R2-B09 review round 1 (R28): a transfer's phrase (FROM, FRM, FR, TO, BETWEEN) is never a company's own
# name, and a DES with none of Bank of America's fields after its entry is no originator field (a town's word: DES
# MOINES, DES PLAINES), so a named transfer keeps its transfer reading: counted and flagged, never verified (Q4), held
# with an account designation (T13) or as a repeated round sum (Q4).
R28_LOOK = "TRANSFER FROM CONTOSO LLC DES MOINES IA"


@pytest.mark.parametrize(("bank", "text", "reading"), [
    ("Fabrikam Bank", R28_LOOK, (COUNTED, "p2p")),
    ("Fabrikam Bank", "ONLINE TRANSFER FROM CONTOSO LLC DES MOINES IA 1234", (COUNTED, "p2p")),
    ("Fabrikam Bank", "XFER FROM CONTOSO HOLDINGS LLC DES PLAINES IL", (COUNTED, "p2p")),
    # No phrase word: the DES before a town opens no originator field.
    ("Fabrikam Bank", "TRANSFER CONTOSO LLC DES MOINES IA", (COUNTED, "p2p")),
    ("Fabrikam Bank", "ONLINE TRANSFER CONTOSO LLC DES MOINES IA", (COUNTED, "p2p")),
    ("Fabrikam Bank", "XFER CONTOSO LLC DES PLAINES IL", (COUNTED, "p2p")),
    ("Fabrikam Bank", R28_LOOK + " CHECKING 1234", (HELD, "transfer_account_designation")),
    # Bank of America's and Chase's real fields, the originator's (cut) name a transfer's phrase.
    ("Bank of America", "XFER FROM CONTOSO LLC DES PAYMENT ID 1 INDN NORTHWIND PLUMBING CO ID 1 CCD", (COUNTED, "p2p")),
    ("Bank of America", "TRANSFER FR CONTOSO LLC DES PAYMENT ID 1 INDN NORTHWIND PLUMBING CO ID 1 CCD", (COUNTED, "p2p")),
    ("Bank of America", "TRF TO CONTOSO INC DES PAYMENT ID 1 INDN NORTHWIND PLUMBING CO ID 1 CCD", (COUNTED, "p2p")),
    ("Chase", R28_CHASE.format(name="TRANSFER FROM CONTOSO LLC", entry="PAYMENT"), (COUNTED, "p2p")),
])
def test_r28_a_named_transfer_s_phrase_or_town_never_reads_as_an_originator_name(bank, text, reading):
    [record] = _rows([(text, 1234.56)], bank=bank, holder=R28_HOLDER)
    assert _reading(record) == reading


def test_r28_a_named_transfer_s_round_repeats_printing_a_town_stay_held():
    records = _rows([(R28_LOOK, 2000.0), (R28_LOOK, 3000.0)], holder=R28_HOLDER)
    assert [_reading(record) for record in records] == [(HELD, "p2p_round_repeat")] * 2


@pytest.mark.parametrize(("row", "wording"), [
    (R28_LOOK, "TRANSFER"),
    ("TRANSFER CONTOSO LLC DES MOINES IA", "TRANSFER"),
    ("XFER FROM CONTOSO LLC DES PAYMENT ID 1", "XFER"),
    ("ORIG CO NAME TRANSFER FROM CONTOSO LLC ORIG ID 1 CO ENTRY DESCR PAYMENT", "TRANSFER"),
    # A cut row with no field after DES's entry keeps the transfer reading it had before R28.
    ("CONTOSO TRF LLC DES PAYMENT", "TRF"),
    # Bank of America's layout after DES (an ID, a receiver field or a class code, the entry a few words): the name's
    # token is blanked.
    ("CONTOSO TRF LLC DES PAYMENT CCD", None),
    ("CONTOSO TRF LLC DES A P PMT ID 1", None),
    ("CONTOSO TRF LLC DES CORP PAY INDN NORTHWIND PLUMBING LLC", None),
])
def test_r28_the_helper_reads_a_phrase_or_a_town_s_des_as_transfer_wording(row, wording):
    from analysis import transaction_classifier

    found = transaction_classifier.credit_transfer_wording(row)
    assert (found.group(0) if found is not None else None) == wording


# Audit round 3, R3-B08 (R3-88 (i); T13, Q4 of 2026-09-28; amends R2-B09's R28 line): a town's DES never opens the
# originator field, whatever field word follows the town within five words (DES MOINES, DES PLAINES, DES PERES, DES
# ALLEMANDS, DES LACS): a named transfer from a company in such a town keeps its transfer reading, counted and flagged,
# never verified, and held as a repeated round sum.
R388_TOWNS = (
    "TRANSFER CONTOSO LLC DES MOINES IA TEL 5150000000",
    "TRANSFER CONTOSO LLC DES MOINES IA ID 4711",
    "XFER CONTOSO INC DES PLAINES IL WEB 84700000",
)


@pytest.mark.parametrize("text", R388_TOWNS)
def test_r3_88_a_town_s_des_before_a_field_word_keeps_the_transfer_reading(text):
    [record] = _rows([(text, 1234.56)], holder=R28_HOLDER)
    assert _reading(record) == (COUNTED, "p2p")
    records = _rows([(text, 3000.0), (text, 3000.0)], holder=R28_HOLDER)
    assert [_reading(record) for record in records] == [(HELD, "p2p_round_repeat")] * 2


@pytest.mark.parametrize(("row", "field"), [
    ("TRANSFER CONTOSO LLC DES MOINES IA TEL 5150000000", False),
    ("XFER CONTOSO INC DES PLAINES IL WEB 84700000", False),
    ("TRANSFER CONTOSO LLC DES PERES MO ID 1", False),
    ("TRANSFER CONTOSO LLC DES ALLEMANDS LA ID 1", False),
    ("TRANSFER CONTOSO LLC DES LACS ND ID 1", False),
    # Bank of America's own DES fields are still read.
    ("CONTOSO TRF LLC DES PAYMENT ID 1", True),
    ("CONTOSO TRF LLC DES PAYMENT CCD", True),
    ("CONTOSO TRF LLC DES MOINESCO PAYMENT ID 1", True),
])
def test_r3_88_the_originator_field_never_opens_on_a_town_s_des(row, field):
    from analysis import transaction_classifier

    assert (transaction_classifier._ORIGINATOR_NAME_FIELD.search(row) is not None) is field


@pytest.mark.parametrize(("text", "reading"), [
    (R28_BOFA.format(name="CONTOSO TRF LLC", entry="PAYMENT"), VERIFIED_COMPANY),
    ("TRANSFER FROM CONTOSO LLC DES MOINES IA TEL 5150000000", (COUNTED, "p2p")),
])
def test_r3_88_the_town_controls_keep_their_readings(text, reading):
    bank = "Bank of America" if " INDN " in text else "Fabrikam Bank"
    [record] = _rows([(text, 1234.56)], bank=bank, holder=R28_HOLDER)
    assert _reading(record) == reading


# Audit round 2, R2-B09 (R25): a teller, branch or counter transfer that prints no explicit deposit form names its
# counterparty only by FROM and a sender, or by a company form; a reference and a town (the booking branch) name nobody
# (M4, Q2: held).

R25_HOLDER = "NORTHWIND BAKERY LLC"


@pytest.mark.parametrize("text", [
    "BRANCH TRANSFER 00123 SAMPLEVILLE",
    "BRANCH TRANSFER SAMPLEVILLE",
    "BRANCH TRANSFER 00123 NORTH SAMPLEVILLE",
    "BRANCH TRANSFER 00123 SAMPLEVILLE NY",
    "IN BRANCH TRANSFER 00123 SAMPLEVILLE",
    "TELLER TRANSFER SAMPLEVILLE",
    "COUNTER CREDIT TRANSFER 00123 SAMPLEVILLE",
    "BRANCH TRANSFER 123 OAK AVE SAMPLEVILLE NY",
    # The deliberate trade-off: two name words with no FROM and no company form are held for review.
    "BRANCH TRANSFER CONTOSO BAKERY",
])
def test_r25_a_branch_transfer_printing_a_reference_and_a_town_is_held(text):
    assert _reading(_one(text, holder=R25_HOLDER)) == (HELD, "transfer_no_counterparty")


@pytest.mark.parametrize(("text", "reading"), [
    ("BRANCH TRANSFER", (HELD, "transfer_no_counterparty")),
    ("TELLER TRANSFER", (HELD, "transfer_no_counterparty")),
    ("TELLER TRANSFER MAIN OFFICE", (HELD, "transfer_no_counterparty")),
    ("BRANCH TRANSFER DEPOSIT", (HELD, "transfer_no_counterparty")),
    ("COUNTER CREDIT TRANSFER", (HELD, "transfer_no_counterparty")),
    ("BRANCH TRANSFER 00123", (HELD, "transfer_no_counterparty")),
    ("BRANCH TRANSFER 00123 MAIN ST", (HELD, "transfer_no_counterparty")),
    ("BRANCH TRANSFER FROM CONTOSO BAKERY LLC", (COUNTED, "p2p")),
    ("TELLER TRANSFER FROM CONTOSO BAKERY LLC", (COUNTED, "p2p")),
    ("BRANCH TRANSFER 00123 CONTOSO BAKERY LLC", (COUNTED, "p2p")),
    ("BRANCH TRANSFER FROM SAMPLE PERSON", (COUNTED, "p2p")),
    ("BRANCH TRANSFER FROM SAMPLEVILLE", (COUNTED, "p2p")),
    ("BRANCH TRANSFER FROM CHECKING 1234", ("non_revenue", "strong_non_revenue_rule")),
    ("CASH DEPOSIT TRANSFER IN", (COUNTED, "no_payer_printed")),
    ("BRANCH DEPOSIT 00123 SAMPLEVILLE", (COUNTED, "no_payer_printed")),
    ("MOBILE CHECK DEPOSIT TRANSFER", (COUNTED, "check_deposit")),
    # The generic transfer path keeps T13's reading.
    ("ONLINE TRANSFER 00123 SAMPLEVILLE", (COUNTED, "p2p")),
    ("ONLINE TRANSFER 00123", (HELD, "transfer_no_counterparty")),
])
def test_r25_the_controls_keep_their_readings(text, reading):
    record = _one(text, holder=R25_HOLDER)
    assert (record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) == reading


# Audit round 2, R2-B11 (R44; §7.0, §8.4, Q4): CIBC prints its e-Transfer reference glued to the rail word
# ('E-TRANSFER<reference> <sender> <card>'). The revenue text splits a reference glued after a consumer rail, so the
# rail reads the row as a person-to-person credit on every bank, as the spaced twin reads: the sender is read, Q4's
# holder and round-repeat holds and the financing hold run, and the row is never verified. Debits keep their text.

R44_HOLDER = "NORTHWIND PLUMBING LTD"
R44_GLUED = "E-TRANSFER10000000000{n} {sender} 4500*********100"
R44_SPACED = "E-TRANSFER 10000000000{n} {sender} 4500*********100"
ROUND_REPEAT = (HELD, "p2p_round_repeat")
P2P = (COUNTED, "p2p")
#: The owner's ruling of 2026-10-02 (the underwriter's Q3): every Zelle deposit is non_revenue, its reading kept.
ZELLE_EXCLUDED = ("non_revenue", "zelle_excluded")


def _statement(rows, *, bank, holder=None):
    return classify_statement_transactions(Statement(bank=bank, account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _cibc(layout, sender, amounts, *, holder=None):
    rows = [(layout.format(n=index + 1, sender=sender), amount) for index, amount in enumerate(amounts)]
    return [_tier(record) for record in _statement(rows, bank="CIBC", holder=holder)]


@pytest.mark.parametrize("layout", [R44_GLUED, R44_SPACED])
@pytest.mark.parametrize(("sender", "amounts", "holder", "readings"), [
    ("JANE SAMPLE", (5000.0, 5000.0, 5000.0), None, [ROUND_REPEAT] * 3),
    ("JANE SAMPLE", (3000.0, 2000.0), None, [ROUND_REPEAT] * 2),
    ("JANE SAMPLE", (1234.56,), None, [P2P]),
    ("NORTHWIND PLUMBING LTD", (1234.56,), R44_HOLDER, [(HELD, "holder_name")]),
    ("CONTOSO FUNDING LLC", (1234.56,), None, [(HELD, "financing_named_payer")]),
    # A platform's or a company's name sent over the rail is a person-to-person credit: counted, never verified.
    ("SHOPIFY PAYMENTS CANADA", (1234.56, 1234.57, 1234.58), None, [P2P] * 3),
    ("CONTOSO SUPPLY INC", (1234.56, 1234.57, 1234.58), None, [P2P] * 3),
])
def test_r44_a_cibc_e_transfer_reads_as_its_spaced_twin(layout, sender, amounts, holder, readings):
    assert _cibc(layout, sender, amounts, holder=holder) == readings


def test_r44_a_glued_zelle_reference_is_split_on_every_bank():
    rows = [("ZELLE1234567 PAYMENT FROM JANE SAMPLE", 5000.0)] * 2
    records = _statement(rows, bank="Chase")
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): the rules' reading is kept beside the Zelle policy's.
    assert [true_revenue.zelle_prior_reading(record) for record in records] == [ROUND_REPEAT] * 2
    assert [_tier(record) for record in records] == [ZELLE_EXCLUDED] * 2


@pytest.mark.parametrize(("text", "expected"), [
    ("E TRANSFER100000000001 JANE SAMPLE 4500 100", "E TRANSFER 100000000001 JANE SAMPLE 4500 100"),
    ("ZELLE1234567 PAYMENT FROM JANE SAMPLE", "ZELLE 1234567 PAYMENT FROM JANE SAMPLE"),
    ("01 02ETRANSFER123 PAT SAMPLE", "ETRANSFER 123 PAT SAMPLE"),
    # Only a consumer rail's word is split: a glued TRANSFER after another word stays as printed.
    ("CMO TRANSFER123456789012 CONTOSO LTD", "CMO TRANSFER123456789012 CONTOSO LTD"),
    ("INTERNET TRANSFER000000123456", "INTERNET TRANSFER000000123456"),
    ("ONLINE TRANSFER123", "ONLINE TRANSFER123"),
    ("E TRANSFER RECLAIM123456", "E TRANSFER RECLAIM123456"),
])
def test_r44_the_revenue_text_splits_a_reference_glued_after_a_rail(text, expected):
    assert revenue_text(text) == expected


def test_r44_the_rail_is_built_from_its_word_list_unchanged():
    from analysis.descriptor import words

    assert words._CONSUMER_P2P_RAIL.pattern == (
        r"(?<![A-Z])(?:ZELLE|INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|VIREMENT|VFC|AUTODEPOSIT|VENMO|CASH ?APP|SQUARE CASH"
        r"|APPLE CASH|POPMONEY)\b"
    )


@pytest.mark.parametrize(("text", "reading"), [
    ("INTERNET TRANSFER000000123456", (HELD, "transfer_no_counterparty")),
    ("CMO TRANSFER123456789012 CONTOSO LTD", P2P),
    ("E-TRANSFER RECLAIM123456", ("non_revenue", "reversal_cancellation_exclusion")),
])
def test_r44_the_controls_keep_their_readings(text, reading):
    record = _statement([(text, 1234.56)], bank="CIBC")[0]
    assert (record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) == reading


def test_r44_a_glued_e_transfer_debit_is_unchanged():
    [debit] = _statement([("E-TRANSFER100000000001 FABRIKAM CAPITAL INC 4500*********100", -1234.56)], bank="CIBC")
    assert (debit.classification, debit.canonical_entity, debit.contributes_to_lender_count,
            debit.contributes_to_potential_lender_count, debit.contributes_to_lender_totals,
            debit.contributes_to_withholding_rate, debit.revenue_tier) == (
        "other", None, False, False, False, False, None)
    assert debit.normalized_description == "E TRANSFER100000000001 FABRIKAM CAPITAL INC 4500 100"


# Audit round 2, R2-B11 (R24; §8.2, §8.4 T13, §7.11 T5): a short own-account source after FROM (CHK, CHECKG, CK, SAV,
# SV, MMA, DDA, PCA, CL, LOC, LN, CRD) designates the holder's own account only before an account number, a masked
# account, ACCOUNT or ACCT, or at the row's end; a company whose name starts with one of those letters is a named
# transfer's counterparty (T13, Q4, Q5). The long spellings (CHECKING, SAVINGS, SHARES, CREDIT CARD ...) read as before.

R24_HOLDER = "NORTHWIND PLUMBING LLC"


@pytest.mark.parametrize(("text", "reading"), [
    ("ONLINE TRANSFER FROM CL FABRIKAM INC", P2P),
    ("TRANSFER FROM LOC CONTOSO LLC", P2P),
    ("TFR FRM CRD FABRIKAM LLC", P2P),
    ("ONLINE TRANSFER FROM CK CONTOSO LLC", P2P),
    # DDA and CHK are §8.4's account-type words: the named transfer is held as naming an account.
    ("ONLINE TRANSFER FROM DDA FABRIKAM INC", (HELD, "transfer_account_designation")),
    ("ONLINE TRANSFER FROM CHK CONTOSO LLC", (HELD, "transfer_account_designation")),
    ("WIRE TRANSFER FROM CL FABRIKAM INC", (COUNTED, "wire_named_sender")),
])
def test_r24_a_company_named_with_a_short_source_s_letters_is_a_named_counterparty(text, reading):
    assert _tier(_one(text, holder=R24_HOLDER)) == reading


def test_r24_a_zelle_transfer_from_a_company_named_with_a_short_source_s_letters():
    # The rules read a named counterparty (p2p); the owner's Zelle policy of 2026-10-02 (the underwriter's Q3) then
    # excludes the Zelle deposit, the rules' reading kept.
    record = _one("ZELLE TRANSFER FROM CL CONTOSO LLC", holder=R24_HOLDER)
    assert true_revenue.zelle_prior_reading(record) == P2P
    assert _tier(record) == ZELLE_EXCLUDED


@pytest.mark.parametrize("text", [
    "ONLINE TRANSFER FROM CL 1234567",
    "ONLINE TRANSFER FROM SV 1234567",
    "ONLINE TRANSFER FROM CK 1234 REF 1234",
    "ONLINE TRANSFER FROM LOC XXXXXX1234",
    "FUNDS TRANSFER FROM LOC ACCOUNT 1234",
    "ONLINE TRANSFER FROM CRD 1234 CONFIRMATION 1",
    "ONLINE TRANSFER FROM CK ACCT 1234",
    "ONLINE TRANSFER FROM CL",
    "TRANSFER FROM SHARES CONTOSO",
    "OVERDRAFT XFER FROM CREDIT CARD OR LINE",
    # LN reads LOAN before any pattern (description_text); audit round 3, R3-B07 (R3-46) reads a company name that
    # holds LN only on a row with no transfer wording, so this own-account designation stays non_revenue.
    "ONLINE TRANSFER FROM LN CONTOSO LLC",
])
def test_r24_the_own_account_designations_stay_non_revenue(text):
    record = _one(text, holder=R24_HOLDER)
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


def _r346(rows, *, bank="Bank of America", holder="NORTHWIND LABS INC"):
    return classify_statement_transactions(Statement(bank=bank, account_name=holder, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


# Audit round 3, R3-B07 (R3-46; §7.11, the owner's standing rule that loans never become revenue): a company whose
# name holds LN ('LN TRUCKING LLC', 'CONTOSO LN HOLDINGS LLC'), with no loan word around it and no transfer wording, is
# held for review as a finance-named payer (financing_named_payer), never counted or verified on its own, where the
# normalizer's LOAN made it unreviewable non-revenue.
R346_CHASE = ("ORIG CO NAME:LN TRUCKING LLC ORIG ID:0000000001 DESC DATE: CO ENTRY DESCR:PAYMENT SEC:CCD "
              "TRACE#:0000001 EED:000000 IND ID: IND NAME:NORTHWIND LABS INC TRN: 0000000001TC")
R346_BOFA = "{name} DES:{entry} ID:0001 INDN:NORTHWIND LABS INC CO ID:0000000001 CCD"


@pytest.mark.parametrize(("bank", "text"), [
    ("Fabrikam Bank", "ACH CREDIT LN TRUCKING LLC"),
    ("Chase", R346_CHASE),
    ("Bank of America", R346_BOFA.format(name="LN TRUCKING LLC", entry="PAYMENT")),
    ("Chase", "FEDWIRE CREDIT VIA FABRIKAM BANK B/O LN TRUCKING LLC REF 1234"),
    ("Fabrikam Bank", "INCOMING WIRE ORG LN TRUCKING LLC REF 123456"),
    ("Bank of America", R346_BOFA.format(name="CONTOSO LN HOLDINGS LLC", entry="PAYMENT")),
])
def test_r3_46_a_company_named_ln_is_held_for_review_as_a_finance_named_payer(bank, text):
    [record] = _r346([(text, 2345.67)], bank=bank)
    assert _tier(record) == (HELD, "financing_named_payer")
    # A held credit is reviewable (revenue.record_serialized_revenue_review reads an unverified deposit).
    assert record.revenue_classification == "unverified_deposit"


def test_r3_46_a_company_named_ln_paying_three_times_stays_held_never_verified():
    text = R346_BOFA.format(name="LN TRUCKING LLC", entry="PAYMENT")
    records = _r346([(text, 2345.67), (text, 3456.78), (text, 4567.89)])
    assert [_tier(record) for record in records] == [(HELD, "financing_named_payer")] * 3


@pytest.mark.parametrize("entry", ["VENDOR PMT", "INVOICE PMT"])
def test_r3_46_with_accounts_payable_wording_the_q9_release_counts_it_flagged_never_verified(entry):
    # The underwriter's Q9 (2026-10-02): a finance-named customer paying an invoice is counted and flagged; LOAN is a
    # lender's name word, so the release's label is lender_paid_for_services (R2-OW09's label rule).
    text = R346_BOFA.format(name="LN TRUCKING LLC", entry=entry)
    records = _r346([(text, 2345.67), (text, 3456.78)])
    assert [_tier(record) for record in records] == [(COUNTED, "lender_paid_for_services")] * 2


@pytest.mark.parametrize("text", [
    "ONLINE TRANSFER FROM LN CONTOSO LLC",
    "COMMERCIAL LN PMT",
    "CONTOSO BANK LN ADV",
    "AUTO LN 0001",
    "ACH CREDIT LOAN STAR LOGISTICS LLC",
    "WIRE TRANSFER FROM LN TRUCKING LLC",
])
def test_r3_46_controls_a_loan_and_a_transfer_stay_non_revenue(text):
    [record] = _r346([(text, 2345.67)], bank="Fabrikam Bank")
    assert _tier(record)[0] == "non_revenue"


def test_r3_46_controls_an_sba_disbursement_and_a_street_lane_keep_their_reading():
    [sba] = _r346([("SBA LN DISB", 2345.67)], bank="Fabrikam Bank")
    assert (sba.revenue_tier, sba.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    [lane] = _r346([("DEPOSIT 1234 OAK LN", 2345.67)], bank="Fabrikam Bank")
    assert lane.normalized_description == "DEPOSIT 1234 OAK LN"
    assert _tier(lane) == (COUNTED, "named_payer_unlabelled")


def test_r3_46_the_helper_reads_names_only_and_the_normalizer_never_moves():
    from analysis.description_text import ln_name_spans, ln_name_word

    assert ln_name_word("ACH CREDIT LN TRUCKING LLC")
    assert ln_name_spans("CONTOSO LN HOLDINGS LLC DES:PAYMENT") == (("LOAN HOLDINGS LLC", "     HOLDINGS LLC"),)
    assert ln_name_spans("CONTOSO LN LLC") == (("CONTOSO LOAN LLC", "CONTOSO      LLC"),)
    for text in ("ONLINE TRANSFER FROM LN CONTOSO LLC", "COMMERCIAL LN PMT", "CONTOSO BANK LN ADV", "SBA LN DISB",
                 "AUTO LN 0001", "1234 OAK LN", "STUDENT LN CONTOSO LLC", "LN PMT CONTOSO LLC", "LN 1234 CONTOSO LLC"):
        assert not ln_name_word(text), text
    assert normalize_transaction_description("LN TRUCKING LLC DES:PAYMENT") == "LOAN TRUCKING LLC DES PAYMENT"


def test_r3_46_a_debit_to_a_company_named_ln_keeps_its_reading():
    [debit] = _r346([(R346_BOFA.format(name="LN TRUCKING LLC", entry="PAYMENT"), -2345.67)])
    assert debit.normalized_description.startswith("LOAN TRUCKING LLC")
    assert (debit.classification, debit.revenue_tier) == ("other", None)


def test_r24_the_named_sender_layouts_after_a_designation_stay_held():
    for bank, text in (
        ("Bank of America", "ONLINE TRANSFER FROM CHK 1234 CONFIRMATION AB12CD34E CONTOSO SUPPLY LLC"),
        ("Fabrikam Credit Union", "TFR FROM XXXXXX1234 TRANSFER DEPOSIT CONTOSO SUPPLY LLC"),
    ):
        assert _tier(_one(text, bank, holder=R24_HOLDER)) == (HELD, "transfer_account_designation"), text


def test_r24_the_package_pairing_designation_reads_the_same_sources():
    assert prints_internal_transfer_designation("ONLINE TRANSFER FROM CL 1234567")
    assert not prints_internal_transfer_designation("ONLINE TRANSFER FROM CL FABRIKAM INC")


def test_r24_the_short_and_long_sources_are_the_whole_source_list():
    from analysis.descriptor import words

    sources = words._INTERNAL_ACCOUNT_SOURCE
    assert sources.startswith("(?:") and sources.endswith(")")
    short = words._SHORT_ACCOUNT_SOURCES.split("|")
    long = words._LONG_ACCOUNT_SOURCES.split("|")
    assert not set(short) & set(long)
    assert sorted(short + long) == sorted(sources[3:-1].split("|"))


# Audit round 2, R2-B11 (R09 part A; §5.2, §8.4, Q4): TD Canada Trust prints an incoming e-Transfer with a per-transfer
# code after its masked asterisks ('E-TRANSFER ***<code>', 'E-TFR ***<code> ...'), never a sender: pass 7 drops the
# code from the text it reads, so a code that spells a word (PAY, CAP, MTG) holds nothing and the row reads no sender
# and no key. The reversal and cancel rules stay first. Whether a keyless row's repeated round sums are held (R09 part
# B) is the owner's call.

TD_BANK = "TD Canada Trust"
TD_HOLDER = "CONTOSO BAKERY LLC"


def _td(rows, *, holder=TD_HOLDER):
    return _statement(rows, bank=TD_BANK, holder=holder)


@pytest.mark.parametrize("code", ["PAY", "CAP", "MTG", "aBc", "Zs4"])
def test_r09_a_td_e_transfer_code_names_no_payer(code):
    assert [_tier(record) for record in _td([(f"E-TRANSFER ***{code}", 1234.56)])] == [P2P]


def test_r09_a_td_e_transfer_code_is_no_round_repeat_key():
    records = _td([("E-TRANSFER ***BFD", 3000.0)] * 3)
    assert [_tier(record) for record in records] == [P2P] * 3
    facts = true_revenue.credit_facts(
        records[0], true_revenue.without_transfer_code(records[0], revenue_text(records[0].normalized_description)),
        debits=true_revenue.counter_debits(records, set()),
    )
    assert (facts.region, facts.key, facts.channel) == ("", (), "person_to_person")


@pytest.mark.parametrize("word", ["EPAY", "CONTOSO"])
def test_r09_a_td_e_tfr_code_before_another_word_names_no_payer(word):
    # The word TD prints after the code is no sender either: two transfers never group as one sender's round sums.
    rows = [(f"E-TFR ***aBc {word}", 3000.0), (f"E-TFR ***xYz {word}", 3000.0)]
    assert [_tier(record) for record in _td(rows)] == [P2P] * 2


def test_r09_a_the_word_after_a_td_code_is_no_counter_debit_key():
    rows = [("E-TFR ***aBc CONTOSO", 3000.0), ("TRANSFER TO CONTOSO 1234", -500.0)]
    assert [_tier(record) for record in _td(rows) if record.amount > 0] == [P2P]


@pytest.mark.parametrize(("rows", "readings"), [
    # The cancel rule stays first.
    ([("CANCEL E TFR ***ABC", 3000.0)], [("non_revenue", "reversal_cancellation_exclusion")]),
    # A sender TD prints is still read, and its repeated round sums held (Q4).
    ([("INTERAC e-Transfer Received NORTHWIND TRADERS", 3000.0)] * 2, [ROUND_REPEAT] * 2),
])
def test_r09_a_the_controls_keep_their_readings(rows, readings):
    assert [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in _td(rows) if record.amount > 0] == readings


@pytest.mark.parametrize("bank", ["Fabrikam Bank", "Royal Bank of Canada"])
@pytest.mark.parametrize("code", ["CAP", "MTG"])
def test_r09_a_reads_td_canada_trust_s_code_only(bank, code):
    # Another bank's '***<word>' after the rail keeps its reading (the financing hold reads it).
    [record] = _statement([(f"E-TRANSFER ***{code}", 1234.56)], bank=bank, holder=TD_HOLDER)
    assert _tier(record) == (HELD, "financing_named_payer")


@pytest.mark.parametrize(("credit", "debit"), [
    ("E-TRANSFER ***PAY", ("PAY ACH", -1234.56)),
    ("E-TRANSFER ***PAY", ("SEND E-TFR ***PAY", -500.0)),
    # A four-character code reads as a counter-debit payer word when it is read at all.
    ("E-TRANSFER ***CONT", ("TRANSFER TO CONT 1234", -500.0)),
    ("E-TRANSFER ***CONT", ("CONT ACH", -1234.56)),
])
def test_r09_a_td_code_is_never_a_counter_debit_key(credit, debit):
    assert [_tier(record) for record in _td([(credit, 1234.56), debit]) if record.amount > 0] == [P2P]


def test_r09_a_the_census_reads_the_pass_s_text():
    [record] = _td([("E-TRANSFER ***PAY", 1234.56)])
    facts = true_revenue.guard_facts(record, revenue_text(record.normalized_description))
    assert facts["pay_or_personal"] is False
    assert facts["financing_root"] is False
