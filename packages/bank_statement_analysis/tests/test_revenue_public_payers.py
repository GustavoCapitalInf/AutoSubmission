"""Classification 5.5 (true revenue spec §7.6, T12): public-payer remittances, arms A and B, the payer anchored on the
payer name, every veto group, and the duplicate and reversal passes that still win. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction


def _credit(printed: str, *, holder: str | None = "CONTOSO CLINIC LLC"):
    return classify_transaction(printed, 1400.0, account_name=holder, direction="credit")


@pytest.mark.parametrize(("printed", "rule"), [
    ("TREAS 310 DES:DOD MISC ID:1 CCD", "treasury_vendor_payment"),
    ("Orig CO Name:Treas 310 Orig ID:1 Desc Date: CO Entry Descr:Misc Paysec:CCD Trace#:1 RMR IV 1234",
     "treasury_vendor_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("STATE OF OHIO DES:PROV PAY ID:1", "public_payer_vendor_or_provider_payment"),
    ("DEPT OF HEALTH SERVICES DES:EDI PYMNTS ID:1", "public_payer_vendor_or_provider_payment"),
    ("SCHOOL DISTRICT 12 DES:VENDOR PMT ID:1", "public_payer_vendor_or_provider_payment"),
    ("ACH CORP CREDIT CITY OF SAMPLEVILLE VEN PAYMENTS 1234", "public_payer_vendor_or_provider_payment"),
    ("SAMPLE COUNTY DES:VENDOR PAY ADDITIONAL INFORMATION IS AVAILABLE FOR THIS PMT CONTACT A TREASURY SALES "
     "OFFICER FOR ASSISTANCE", "public_payer_vendor_or_provider_payment"),
])
def test_each_arm_verifies(printed, rule):
    record = classify_transaction(printed, 1400.0, account_name="CONTOSO CLINIC", direction="credit")
    assert record.revenue_classification == "verified_revenue"
    assert record.revenue_matched_rule in (rule, "verified_payer_accounts_payable_remittance")


def test_a_county_printed_after_the_payer_is_not_the_payer():
    record = _credit("FABRIKAM PLUMBING DES:VENDOR PAY ID:1 SAMPLE COUNTY")
    assert record.revenue_match_method != "public_payer_remittance"


@pytest.mark.parametrize("printed", [
    "TREAS 310 DES:DOD MISC ID:1 PPD",                               # a consumer entry
    "TRANSFER FROM COUNTY LINE SUPPLY VENDOR PAY",                   # a transfer, and COUNTY LINE is no public payer
    "STATE OF OHIO FUNDING DES:VENDOR PAY ID:1",                     # a financing name
    "STATE OF OHIO DES:VENDOR PAY GRANT ID:1",
    "STATE OF OHIO DES:VENDOR PAY TAX REFUND ID:1",
    "STATE OF OHIO DES:VENDOR PAY STIMULUS ID:1",
    "STATE OF OHIO DES:VENDOR PAY CHILD SUPPORT ID:1",
    "STATE OF OHIO DES:VENDOR PAY CLAIMS ID:1",
    "STATE OF OHIO DES:VENDOR PAY SETTLEMENT ID:1",
    "STATE OF OHIO DES:VENDOR PAY ASSISTANCE ID:1",
    "COMPTROLLER OF MD DES:MDREFUND ID:1",
    "IRS TREAS 310 DES:TAX EIC ID:1",
])
def test_a_veto_or_an_unanchored_payer_never_verifies(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


def test_a_label_less_holder_name_never_supplies_the_public_payer():
    # Wells Fargo prints the receiver with no label: the holder's own words must not make the payer public.
    record = _credit("FABRIKAM SUPPLY VENDOR PAY 540115 SAMPLE COUNTY PLUMBING", holder="SAMPLE COUNTY PLUMBING")
    assert record.revenue_match_method != "public_payer_remittance"


def test_a_verified_public_payment_is_still_demoted_by_a_duplicate_and_its_reversal():
    duplicate = classify_statement_transactions(Statement(account_name="CONTOSO CLINIC", transactions=[
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit", running_balance=5400.0),
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit", running_balance=5400.0),
    ]))
    assert [record.revenue_classification for record in duplicate] == ["verified_revenue", "non_revenue"]
    # Audit B3 (I03): the payer's own reversal of its ACH payment, as Bank of America prints it (the originator's name
    # and a REVERSAL entry), pairs in pass 4. A bank's bare returned item prints no payer's words: it undoes a
    # deposit-channel credit only (tests/test_revenue_reversals.py), never this electronic payment.
    reversed_payment = classify_statement_transactions(Statement(account_name="CONTOSO CLINIC", transactions=[
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit"),
        Transaction(date="2054-03-04", description="SAMPLE COUNTY DES:REVERSAL ID:1", amount=-1400.0,
                    direction="debit"),
    ]))
    assert reversed_payment[0].revenue_classification == "non_revenue"
    assert reversed_payment[0].revenue_match_method == "matched_reversal_pair"
    bare_return = classify_statement_transactions(Statement(account_name="CONTOSO CLINIC", transactions=[
        Transaction(date="2054-03-02", description="SAMPLE COUNTY DES:VENDOR PAY ID:1", amount=1400.0,
                    direction="credit"),
        Transaction(date="2054-03-04", description="RETURNED ITEM", amount=-1400.0, direction="debit"),
    ]))
    assert bare_return[0].revenue_classification == "verified_revenue"


@pytest.mark.parametrize(("text", "expected"), [
    ("ORIG CO NAME TREAS 310 ORIG ID 1 DESC DATE CO ENTRY DESCR MISC PAYSEC CCD TRACE 1 RMR IV 1234", True),
    ("TREAS 310 MISC PAY RMR IV 1234", True),
    ("TREAS 310 RMR IV 1234 MISC PAY", False),
    ("MISC PAY TREAS 310 RMR IV 1234", False),
    ("TREAS 310 X MISC PAY TREAS 999 RMR IV", True),
    ("RMR IV TREAS 310 MISC PAY", False),
    ("TREAS 31 MISC PAY RMR IV", False),
    ("XTREAS 310 MISC PAY RMR IV", False),
    ("TREAS 310 MISC PAYMENT RMR IV", False),
    ("TREAS 310 DES DOD MISC ID 1 CCD", True),
    ("TREAS 310 DES DOD MISC ID 1 PPD", False),
])
def test_arm_a_reads_its_three_codes_in_order(text, expected):
    # Final review M1: arm A's Treasury code, MISC PAY and RMR IV, read by chained searches (the old '.*' pattern).
    from analysis.descriptor import rails

    assert rails._public_payer_arm_a(text) is expected


def test_arm_a_is_linear_on_a_long_row():
    # Final review M1: the old pattern was cubic ('TREAS 123 MISC PAY' repeated, no RMR IV: 492 ms at 3,800
    # characters). A 10,000-character row reads in under 50 ms.
    import time

    from analysis.descriptor import rails

    row = ("TREAS 123 MISC PAY " * 600)[:10000]
    assert len(row) == 10000
    started = time.perf_counter()
    assert rails._public_payer_arm_a(row) is False
    assert time.perf_counter() - started < 0.05
