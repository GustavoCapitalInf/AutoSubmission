"""Classification 5.5 (true revenue spec §7.5): the payer's accounts-payable remittance, its free-text gate, its veto,
the numbered-company and holder refusals, and the counter-debit guard. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    _debit_first_distinctive_word,
    classify_statement_transactions,
    classify_transaction,
)


def _credit(printed: str, *, holder: str | None = "SAMPLE CAFE LLC"):
    return classify_transaction(printed, 1200.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("printed", [
    "FABRIKAM SUPPLY DES:ACCTS PAYABLE ID:1",
    "FABRIKAM SUPPLY DES:ACCOUNTS PAYABLE ID:1",
    "FABRIKAM SUPPLY DES:A P PMTS ID:1",
    "Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:A P Sec:CCD",
    "FABRIKAM SUPPLY DES:CCDACC PAY ID:1",
    "FABRIKAM SUPPLY DES:VENDOR PAY ID:1",
    "Orig CO Name:Fabrikam Supply Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Vendor Pmtsec:CCD",
    "FABRIKAM SUPPLY DES:TRADE PAY ID:1",
    "FABRIKAM SUPPLY DES:PAYABLES ID:1",
    "FABRIKAM SUPPLY DES:PO REMITTANCE ID:1",
    "FABRIKAM SUPPLY AVIDPAY 1234",
    "FABRIKAM SUPPLY DES:PAYMODE ID:1",
    "RAMP FABRIKAM SUPPLY PAYING BILL 1234",
    "FABRIKAM SUPPLY FOR 3 BILLS",
    "FABRIKAM SUPPLY BILL COM INV 1234",
    "FABRIKAM SUPPLY DES:INVOICE PMT ID:1",
    "FABRIKAM SUPPLY PAYMENT OF INVOICES",
    "FABRIKAM SUPPLY DES:CORP PAY ID:1 RMR IV 1234",
    "FABRIKAM SUPPLY ACH PMT INV 1234",
    "FABRIKAM SUPPLY PAIEMENT DE FACTURE 1234",
])
def test_the_payer_remittance_forms_verify(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "verified_revenue", "payer_remittance_descriptor")


@pytest.mark.parametrize("printed", [
    "FABRIKAM FUNDING LLC DES:VENDOR PAY ID:1",
    "FABRIKAM CAPI DES:VENDOR PAY ID:1",
    "FABRIKAM FUN DES:VENDOR PAY ID:1",
    "FABRIKAM FINA DES:VENDOR PAY ID:1",
    "FABRIKAM FINAN DES:VENDOR PAY ID:1",
    "FABRIKAM LOA DES:VENDOR PAY ID:1",
    "FABRIKAM LEASIN DES:VENDOR PAY ID:1",
    "FABRIKAM CAP ADVANTAG DES:VENDOR PAY ID:1",
    "BIZ2CREDIT DES:VENDOR PAY ID:1",
    "FABRIKAM MOTORS DES:PAYABLES ID:1 VIN 1234",
    "FABRIKAM INSURANCE DES:VENDOR PAY ID:1",
    "FABRIKAM HOLDINGS DES:INTERCOMPANY ID:1 VENDOR PAY",
    "ZERO BALANCE TRANSFER CREDIT A P PAYMENTS",
    "ACH RTN VENDOR PAY 1234 R03",
    "BILL COM DES:PAYABLES ID:1",
    "ZELLE PAYMENT FROM JOHN SMITH MEMO PAYING BILLS 1 CONF 99",
    "ZELLE PAYMENT FROM JOHN SMITH INVOICE 1234 CONF 99",
    "DEPOSIT INV 1234",
    "REMOTE ONLINE DEPOSIT 1 INVOICE 55",
    "ONLINE TRANSFER FROM INV 1234567",
])
def test_the_negatives_never_verify(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


@pytest.mark.parametrize("printed", [
    "DIRECT DEPOSIT 7654321 CANA AP CC",
    "1234567 NOVA SCOTIA LTD DES:VENDOR PAY ID:1",
    "7654321 NEW BRUNSWICK INC DES:PAYMENT ID:1",
])
def test_a_numbered_company_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_the_holder_s_own_name_never_verifies():
    record = _credit("CONTOSO BAKERY LLC DES:VENDOR PAY ID:1", holder="CONTOSO BAKERY LLC")
    assert (record.revenue_classification, record.revenue_match_method) == ("unverified_deposit", "holder_named_payer")


def test_a_payer_the_statement_also_debits_goes_back_to_unverified():
    records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
        Transaction(date="2054-03-02", description="NORTHWIND SUPPLY DES:VENDOR PAY ID:1", amount=5000.0,
                    direction="credit"),
        *(Transaction(date=f"2054-03-{day:02d}", description="NORTHWIND SUPPLY DES:DEBIT ID:2", amount=-250.0,
                      direction="debit") for day in (3, 4, 5, 6, 9)),
    ]))
    assert records[0].revenue_classification == "unverified_deposit"
    assert records[0].revenue_match_method == "payer_remittance_with_counter_debit"


def test_a_card_purchase_from_the_payer_is_a_counter_debit_too():
    # S2.4 review: Bank of America's CHECKCARD and its MMDD date are skipped before the debit's first distinctive word.
    credit = Transaction(date="2054-03-02", description="NORTHWIND SUPPLY DES:VENDOR PAY ID:1", amount=5000.0,
                         direction="credit")
    card = Transaction(date="2054-03-03", description="CHECKCARD 0302 NORTHWIND GRILL", amount=-25.0,
                       direction="debit")
    records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[credit, card]))
    assert (records[0].revenue_classification, records[0].revenue_match_method) == (
        "unverified_deposit", "payer_remittance_with_counter_debit")
    [alone] = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[credit]))
    assert (alone.revenue_classification, alone.revenue_match_method) == (
        "verified_revenue", "payer_remittance_descriptor")


def _debit_word(printed: str) -> str | None:
    return _debit_first_distinctive_word(classify_transaction(printed, -25.0, direction="debit"))


@pytest.mark.parametrize(("printed", "word"), [
    # S2.4 re-review: a card purchase's word is its merchant's, read on the merchant's first two words only.
    ("CHECKCARD 0302 NORTHWIND GRILL", "NORTHWIND"),
    ("CHECKCARD 0302 TST* NORTHWIND HOUSTON TX", "NORTHWIND"),
    ("CHECKCARD 0302 SQ *NORTHWIND BAKERY HOUSTON TX", "NORTHWIND"),
    ("CHECKCARD 0302 THE HOME DEPOT #1234 HOUSTON TX", "HOME"),
    # a reference, a short token or a processor code alone never lets the read walk on into the city
    ("CHECKCARD 0302 76 - HOUSTON TX", None),
    ("CHECKCARD 0302 SQ *AB HOUSTON TX", None),
    ("CHECKCARD 0302 BP1234567 HOUSTON TX", None),
    ("CHECKCARD 0302 TST* 12345 HOUSTON TX", None),
    ("CHECKCARD 0302 TST*", None),
    ("CHECKCARD 0302 ABC 1234 HOUSTON TX", None),
    ("PURCHASE AUTHORIZED ON 03/02 QT123 DALLAS TX S123456789 CARD 1234", None),
])
def test_a_card_purchase_s_word_is_its_merchant_s(printed, word):
    assert _debit_word(printed) == word


@pytest.mark.parametrize(("payer", "card"), [
    ("HOUSTON FABRIKAM CLINIC DES:VENDOR PAY ID:1", "CHECKCARD 0302 76 - HOUSTON TX"),
    ("HOUSTON FABRIKAM CLINIC DES:VENDOR PAY ID:1", "CHECKCARD 0302 SQ *AB HOUSTON TX"),
    ("HOUSTON FABRIKAM CLINIC DES:VENDOR PAY ID:1", "CHECKCARD 0302 BP1234567 HOUSTON TX"),
    ("DALLAS COUNTY HOSPITAL DES:VENDOR PAY ID:1",
     "PURCHASE AUTHORIZED ON 03/02 QT123 DALLAS TX S123456789 CARD 1234"),
])
def test_a_card_purchase_in_the_payer_s_city_is_no_counter_debit(payer, card):
    # S2.4 re-review: the city a card purchase prints after its merchant is never the debit's word.
    records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
        Transaction(date="2054-03-02", description=payer, amount=5000.0, direction="credit"),
        Transaction(date="2054-03-03", description=card, amount=-25.0, direction="debit"),
    ]))
    assert (records[0].revenue_classification, records[0].revenue_match_method) == (
        "verified_revenue", "payer_remittance_descriptor")
