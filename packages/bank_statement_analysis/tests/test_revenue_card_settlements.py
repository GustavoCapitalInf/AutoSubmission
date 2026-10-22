"""Classification 5.5 (true revenue spec §7.0, §7.1): card-processor settlements, the card veto, the processor payout
context and the processor registry additions. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.classification_registry import (
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_TRUNCATIONS,
    PROCESSOR_ADVANCE_PRODUCTS,
    PROCESSORS_WITHOUT_ADVANCE_PRODUCT,
)
from analysis.transaction_classifier.row import classify_transaction


def _credit(printed: str, *, holder: str | None = None, bank: str | None = None, amount: float = 250.0):
    return classify_transaction(printed, amount, account_name=holder, bank=bank, direction="credit")


@pytest.mark.parametrize(("printed", "label"), [
    ("MERCHANT BANKCD DES:DEPOSIT ID:123456 INDN:FABRIKAM BAKERY CO ID:1234567890 CCD", "bankcard"),
    ("Orig CO Name:Merchant Bankcd Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Merch Depsec:CCD Trace#:1",
     "bankcard"),
    ("01/02Bankcard Deposit 123456", "bankcard"),
    ("BKCD DEPST 1234567", "bankcard"),
    ("BANKCARD BTOT DEP 123456", "bankcard"),
    ("FABRIKAM MERCH DEP 1234567", "merch_dep"),
    ("MERCH SETL 1234567 FABRIKAM", "merch_dep"),
    ("MERCH SVCS DEP 1234567", "merch_dep"),
    ("CO ENTRY DESCR MRCHNTSRVS SEC CCD", "mrchntsrvs"),
    ("MERCHANT SVCS DES 123SETL ID:1", "merch_svcs_setl_code"),
    ("MERCHANT SERVICES MID 1234567 FABRIKAM", "merchant_services_mid"),
    ("VSA DEP12345678", "brand_dep"),
    ("MC DEP 12345678", "brand_dep"),
    ("MISC PAYMENT VSA DEP12345678 FABRIKAM SOLUTIONS", "brand_dep"),
    ("MC VI DEP SAMPLE MERCH SVC FABRIKAM", "brand_dep"),
    ("DEP VSA12345678 DIV", "dep_brand"),
    ("COMPTE DIVERS DEP VSA12345678", "dep_brand"),
    ("MISC PAYMENT 1234567 VISA GBL VI 1234", "gbl_brand"),
    ("BTOT DEP 123456", "batch_total"),
    ("INTUIT 12345678 DES:DEPOSIT ID:1", "intuit_deposit"),
    ("AMERICAN EXPRESS DES:SETTLEMENT ID:1", "network_settlement"),
    ("VISA MC DEPOSIT 1234", "generic_card_sales"),
    ("FABRIKAM CAFE CREDIT CARD DEPOSIT 1234", "generic_card_sales"),
    ("REGLEMENT MARCHAND 1234", "french_card_settlement"),
])
def test_each_card_settlement_form_verifies_one_row(printed, label):
    record = _credit(printed)
    assert record.revenue_classification == "verified_revenue", record.revenue_match_method
    assert record.revenue_matched_rule in (f"card_settlement_form_{label}", "verified_operating_source_credit")


def test_a_form_names_its_processor_and_records_its_label():
    record = _credit("MISC PAYMENT 1234567 IDP GBL IDP1234")
    assert (record.revenue_canonical_entity, record.revenue_matched_alias) == ("Global Payments", "gbl_brand")
    square = _credit("CARD PAYMENT SALES", bank="Square")
    assert (square.revenue_classification, square.revenue_canonical_entity) == ("verified_revenue", "Square")
    assert _credit("CARD PAYMENT SALES", bank="Sample Bank").revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("printed", [
    "FABRIKAM BANKCARD LLC DES:ADV ID:1",
    "FABRIKAM BANKCARD LLC DES:DEPOSIT ID:1",
    "MISC PAYMENT FABRIKAM CAP ADV",
    "TRANSFER FROM SV01",
    "BANKCARD DEP CB REV",
    "OWNER CONTRIB MERCH DEP",
    "ELAN BANKCARD SETTLEMENT CREDIT",
    "VISA DEP JOHN SMITH",
    "CREDIT CARD DEPOSIT 1234",            # every word generic: no payer printed, closed by the channel gate
    "CAPITAL ONE CREDIT CARD DEPOSIT 1234",  # a card issuer is named
    "MOBILE DEP VISA",
    "MERCHANT SERVICES DEPOSIT FABRIKAM",
    "STRIPE DES:CLAIM PAYM ID:ST-A1B2C3D4E5",
    "INTUIT 12345678 DES:TAX RFND ID:1",
])
def test_the_verifiers_negatives_never_verify(printed):
    assert _credit(printed).revenue_classification != "verified_revenue"


@pytest.mark.parametrize("printed", [
    "FABRIKAM LAW GROUP DES:NET SETTLE ID:1",
    "Orig CO Name:Fabrikam Title Co Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Net Settlesec:CCD Trace#:1",
])
def test_net_settle_from_a_law_or_title_firm_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


@pytest.mark.parametrize(("printed", "entity", "state"), [
    ("HRTLAND PMT SYS TXNS", "Heartland Payment Systems", "unverified_deposit"),  # recurrence decides it
    ("SPOTON VIA ASTRA SETTLEMENT", "SpotOn", "verified_revenue"),
    ("CLEARENT LLC DES:SETTLEMENT ID:1", "Clearent", "verified_revenue"),
    ("SHIFT4 PAYMENTS DES:PAYOUT ID:1", "Shift4", "verified_revenue"),
    ("SMARTTAB PAY DES:BKCD DEP ID:1", "SmartTab", "verified_revenue"),
    ("TGPAYMENTS DES:SETTLEMENT ID:1", "TapGoods Payments", "verified_revenue"),
    ("TRYCENTS COM DES:PAYOUT ID:1", "Cents", "verified_revenue"),
    ("MISC PAYMENT 12345678901 DP FIRST DATA CANADA J 12", "Fiserv", "verified_revenue"),
])
def test_the_processor_registry_additions_name_the_processor(printed, entity, state):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == (state, entity)


@pytest.mark.parametrize(("processor", "printed"), [
    ("Shift4", "SHIFT4 DES:DEPOSIT ID:1"),
    ("SumUp", "SUMUP DES:PAYOUT ID:1"),
    ("Braintree", "BRAINTREE DES:PAYOUT ID:1"),
])
def test_a_bare_processor_name_waits_for_its_advance_product(processor, printed):
    # §7.1: the bare name reads as the processor only once the lender ledger admits its advance product, or records
    # that it has none (Task S1.5); until then it names no source.
    _bare, product = PROCESSOR_ADVANCE_PRODUCTS[processor]
    cleared = product is not None or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    assert (_credit(printed).revenue_canonical_entity == processor) is cleared


def test_the_sixteen_character_cuts_are_read():
    assert "FIRST DATA MERCH" in OPERATING_REVENUE_TRUNCATIONS["Fiserv"]
    assert "QUICKBOOKS PAYME" in OPERATING_REVENUE_READ_ALIASES["QuickBooks Payments"]
    record = _credit("FIRST DATA MERCH DES:SETTLEMENT ID:1")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Fiserv")


def test_stripe_connect_s_cut_reads_as_stripe():
    record = _credit("FABRIKAM - BY STRI DES:PAYOUT ID:1")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Stripe")


def test_a_waiting_processor_s_row_never_reads_as_stripe():
    # §7.1, review I4: JOBBER BY STRI is Jobber Payments' bare alias, which waits for Jobber Capital in the ledger;
    # Stripe's BY STRI cut inside it never reads the row while Jobber waits.
    _bare, product = PROCESSOR_ADVANCE_PRODUCTS["Jobber Payments"]
    cleared = product is not None or "Jobber Payments" in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    record = _credit("JOBBER BY STRI DES:TRANSFER ID:ST-A1B2C3D4E5F6")
    assert record.revenue_canonical_entity == ("Jobber Payments" if cleared else None)
    assert record.revenue_classification == ("verified_revenue" if cleared else "unverified_deposit")


def test_the_french_merchant_deposit_verifies_through_global_payments():
    # §7.1, review M3: DEPOT MARCHAND is a card settlement, never a branch deposit.
    record = _credit("DEPOT MARCHAND GLOBAL PAIEMENTS 1234567", bank="Desjardins")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", "Global Payments")


@pytest.mark.parametrize(("printed", "verified"), [
    ("SQUARE INC DES:SQ540115 ID:1", True),          # a Square payout id is processor payout context
    ("STRIPE DES:TRANSFER ID:ST-A1B2C3D4E5F6", True),  # Stripe's ST- payout id
    ("PAYPAL DES:MSP DIV ID:1", False),               # never for a customer-payment platform
    ("SQUARE INC DES:CHARGEBACK SQ540115 ID:1", False),  # the card veto refuses the context
])
def test_the_processor_payout_context(printed, verified):
    assert (_credit(printed).revenue_classification == "verified_revenue") is verified
