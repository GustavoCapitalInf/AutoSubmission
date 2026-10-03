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
    from analysis import transaction_classifier

    assert bool(transaction_classifier._TRANSFER_WORDING.search(text)) is transfer


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

    found = transaction_classifier.credit_transfer_wording(text)
    assert found is not None and found.span() == transaction_classifier._TRANSFER_WORDING.search(text).span()


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
