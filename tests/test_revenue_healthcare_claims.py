"""Classification 5.5 (true revenue spec §7.7, T18): healthcare claim payments, the NACHA entry glued on either side,
and the claim-first switch. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.transaction_classifier import classify_transaction


def _credit(printed: str):
    return classify_transaction(printed, 250.0, direction="credit")


@pytest.mark.parametrize("printed", [
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmt Sec:CCD Trace#:1",
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1",
    "FABRIKAM HEALTH PHCCLAIMPMT 1234567 TRN 1*123",
    "123456789 HCCLAIMPMT 1234567",
    "FABRIKAM HLTH DES:HECLAIMPMT ID:1",
])
def test_the_nacha_claim_entry_verifies_glued_or_spaced(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "verified_revenue", "operating_income_descriptor")


@pytest.mark.parametrize("printed", [
    "FABRIKAM HEALTHHCLAIMPMT 1234567",
    "FABRIKAM HEALTH DES:HCCLAIMPMT0001 ID:1",
    "FABRIKAM HEALTH DES:HHSPAYMENTSEC ID:1",
    "ASSURANCE OF THECLAIMPMT 123456789 CLAIM 123",
    "Orig CO Name:Fabrikam Health Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Theclaimpmt Sec:CCD",
])
def test_a_token_that_is_not_the_nacha_entry_stays_unverified(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_a_blue_plan_claim_verifies_with_claim_first_on(monkeypatch):
    printed = "Orig CO Name:BCBSM Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Hcclaimpmtsec:CCD Trace#:1"
    monkeypatch.setattr(transaction_classifier, "HCCLAIMPMT_CLAIM_FIRST", True)
    assert _credit(printed).revenue_classification == "verified_revenue"
    monkeypatch.setattr(transaction_classifier, "HCCLAIMPMT_CLAIM_FIRST", False)
    held = _credit(printed)
    assert (held.revenue_classification, held.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")
    # Off, an alias-escaping Blue-plan spelling is held with the insurer's credits too.
    spaced = _credit("BCBSF HCCLAIMPMT 123456 123456789012345")
    assert (spaced.revenue_classification, spaced.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")


def test_a_funder_glued_to_the_claim_entry_stays_financing_proceeds():
    record = _credit("RAPID FINANCE HCCLAIMPMT 1234567")
    assert (record.revenue_classification, record.revenue_match_method) == (
        "non_revenue", "financing_proceeds_credit")


@pytest.mark.parametrize("printed", [
    "FABRIKAM HEALTH DES:HCCLAIMPMT MERCHANT CASH ADVANCE ID:1",
    "FABRIKAM HEALTH DES:HCCLAIMPMT LOAN PROCEEDS ID:1",
])
def test_a_claim_entry_with_financing_words_stays_non_revenue(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


def test_an_insurer_s_customer_payment_leaves_non_revenue_for_review():
    record = _credit("STATE FARM DES:DRP PAYMENT ID:1")
    assert (record.revenue_classification, record.revenue_match_method) == (
        "unverified_deposit", "insurer_customer_payment")
    assert _credit("STATE FARM DES:CLAIM PAYMT ID:1").revenue_classification == "non_revenue"
