"""5.3 (2026-09-27): payroll providers and benefit administrators are payroll, read on the originator only, never in a
receiver field, and never on a row that names financing. Fabricated descriptors only."""
from __future__ import annotations

import pytest

from analysis.transaction_classifier import classify_transaction
from tests.flag_group_fixtures import fake_payees  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    "description",
    [
        "PATRIOT SOFTWARE DES:PAYROLLTAX ID:0001 INDN:FAB HOLDER CO ID:0002 CCD",
        "ACH DEBIT DATAPAY IN 1234 C 5678 BILLING 9",
        "HEALTHEQUITY INC HEALTHEQUI 1234",
        "ONPAY INC PAYROLLTS 1234",
        "PAYCOR INC PAYCOR 123456",
        "Paie Pat Example",
    ],
)
def test_payroll_providers_and_benefit_administrators_are_payroll(description):
    assert classify_transaction(description, -100.0).classification == "payroll"


@pytest.mark.parametrize(
    "description",
    [
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD",
        "Orig CO Name:Fabricated Lender Orig ID:0001 CO Entry Descr:Payment Ind Name:Human Interest Media LLC",
        "FABRICATED LENDER DEBIT CCD 0105 TASC BUILDERS INC",
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:FAB 401K ADVISORS LLC CO ID:0002 CCD",
    ],
)
def test_a_holder_named_like_a_provider_never_hides_its_lender(fake_payees, description):
    assert classify_transaction(description, -100.0).classification == "confirmed_lender"


def test_the_lenders_proceeds_credit_keeps_its_treatment(fake_payees):
    record = classify_transaction("FABRICATED LENDER DES:PAYMENT ID:0001 INDN:TASC BUILDERS INC CO ID:0002 CCD", 5000.0)
    assert record.revenue_match_method == "financing_proceeds_credit"


@pytest.mark.parametrize(
    "description",
    ["TASC INC LOAN PAYMENT", "HEALTH EQUITY CAPITAL LLC DEBIT CCD", "PAYCOR FUNDING DES:PAYMENT ID:0001",
     "ACH DEBIT FAB WIDGETS 401K 0001"],
)
def test_a_provider_word_beside_financing_or_a_bare_401k_is_not_payroll(description):
    assert classify_transaction(description, -100.0).classification != "payroll"
