"""True revenue spec §7.0 to §7.10 and §7.4 (S1): the operating registry, its sixteen-character cuts, the payout and
card forms, the payer tables and the validator that checks them."""
from __future__ import annotations

import re

import pytest

from analysis import classification_registry as registry
from tools import operating_registry


def test_the_registry_has_no_problem():
    assert operating_registry.problems() == []
    assert operating_registry.main(["--check"]) == 0


def test_every_new_type_is_one_of_the_known_source_types():
    assert set(registry.OPERATING_REVENUE_SOURCE_TYPES.values()) == {
        "known_operating_counterparty", "merchant_processor", "ecommerce_marketplace", "customer_payment_platform",
        "delivery_marketplace", "invoice_and_receivables", "ecommerce_platform", "booking_marketplace",
        "transport_marketplace", "wholesale_auto_auction", "property_management_payments",
    }


@pytest.mark.parametrize(("alias", "cut"), [
    ("FIRST DATA MERCHANT", "FIRST DATA MERCH"),
    ("QUICKBOOKS PAYMENTS", "QUICKBOOKS PAYME"),
    ("AMAZON MARKETPLACE", "AMAZON MARKETPLA"),
    ("HEARTLAND PMT SYS TXNS", None),     # the cut's last word would have two letters
    ("GODADDY PAYMENTS", None),           # sixteen characters: no cut
])
def test_the_sixteen_character_cut(alias, cut):
    assert registry._operating_alias_cut(alias) == cut


def test_a_bare_processor_name_is_not_in_the_registry_until_the_ledger_clears_it():
    read = {alias for aliases in registry.OPERATING_REVENUE_SOURCE_ALIASES.values() for alias in aliases}
    for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items():
        if product is None and processor not in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT:
            assert not set(bare) & read, processor


def test_the_validator_refuses_a_bare_alias_ahead_of_its_advance_product(monkeypatch):
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Shift4": ("SHIFT4", "SHIFT4 PAYMENTS")}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    assert any("SHIFT4" in problem and "advance product" in problem for problem in operating_registry.problems())


def test_the_validator_refuses_an_untyped_entity_and_a_financing_collision(monkeypatch):
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Fabrikam Pay": ("FABRIKAM PAY",),
               "Square": (*registry.OPERATING_REVENUE_SOURCE_ALIASES["Square"], "SQUARE CAPITAL")}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    found = operating_registry.problems()
    assert "operating entity 'Fabrikam Pay' has no source type" in found
    assert any("'SQUARE CAPITAL'" in problem and "financing alias" in problem for problem in found)


def test_a_waiting_processor_s_bare_aliases_are_gated_and_never_read():
    # §7.1, review I4: the gate lists every processor the ledger has not cleared, and none of its bare aliases reads.
    admitted = {entity for group in registry.PAYEE_GROUP_REGISTRIES.values() for entity in group}
    waiting = {
        processor: bare for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items()
        if not (product in admitted or processor in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT)
    }
    assert registry.GATED_PROCESSOR_ALIASES == waiting
    read = {alias for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases}
    assert not read & {alias for bare in waiting.values() for alias in bare}


def test_the_structural_lens_processors_wait_for_a_printed_spelling():
    # §7.1: none of the seventeen prints a credit spelling in the corpus or the tryout dump (Task S1.1, Step 1).
    read = {word for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases
            for word in alias.split()}
    for name in ("TSYS", "TRANSFIRST", "VANTIV", "PAYSAFE", "PAYANYWHERE", "PAYROC", "CARDCONNECT", "FATTMERCHANT",
                 "STAX", "REPAY", "PAYA", "NMI", "FINIX", "WEPAY", "TDMS", "MONETICO", "QUICKACCEPT"):
        assert name not in read, name


def test_every_form_compiles_and_names_a_typed_entity():
    for entity, forms in registry.OPERATING_SOURCE_PAYOUT_FORMS.items():
        assert entity in registry.OPERATING_REVENUE_SOURCE_TYPES
        for label, pattern in forms:
            assert re.compile(pattern) and label.endswith("_form")
    labels = [form.label for form in registry.CARD_SETTLEMENT_CREDIT_FORMS]
    assert len(labels) == len(set(labels))
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        assert form.entity is None or form.entity in registry.OPERATING_REVENUE_SOURCE_TYPES


#: §7.0, §7.1 (owner ruling 2026-09-29): one fabricated row for each branch of every card form, each row beginning with
#: the branch's leading token, so a prefix glued on the left lands on that token's boundary.
CARD_FORM_ROWS = [
    ("bankcard", "BANKCARD DEPOSIT"),
    ("merch_dep", "MERCH DEP"),
    ("mrchntsrvs", "DESCR MRCHNTSRVS"),
    ("merch_svcs_setl_code", "MERCH SVCS DES DAILYSETL"),
    ("merchant_services_mid", "MERCHANT SERVICES TRANS SLIP"),
    ("brand_dep", "VISA DEP 1"),
    ("brand_dep", "MISC PAYMENT VISA DEP 1"),
    ("brand_dep", "VISA DEP MERCH SVC"),
    ("dep_brand", "DEP VISA 1"),
    ("dep_brand", "COMPTE DIVERS DEP VISA 1"),
    ("dep_brand", "DEP VISA MSP"),
    ("gbl_brand", "GBL VI"),
    ("net_settle", "DESCR NET SETTLE"),
    ("batch_total", "BTOT DEP"),
    ("intuit_deposit", "INTUIT 123456 DEPOSIT"),
    ("intuit_deposit", "DEPOSIT FROM INTUIT 123456"),
    ("intuit_deposit", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "QBOOKS DEPOSIT"),
    ("intuit_deposit", "ORIG CO NAME INTUIT 123456 CO ENTRY DESCR DEPOSIT"),
    ("square_checking_sales", "CARD PAYMENT SALES"),
    ("network_settlement", "AMERICAN EXPRESS SETTLEMENT"),
    ("network_settlement", "AMEXO GBL"),
    ("network_settlement", "MISC PAYMENT AMEX BANK OF CANADA"),
    ("generic_card_sales", "VISA MC DEPOSIT"),
    ("generic_card_sales", "CREDIT CARD DEPOSIT"),
    ("french_card_settlement", "REGLEMENT CARTE"),
    ("french_card_settlement", "DEPOT MARCHAND"),
]
#: Row-anchored layouts keep their `^`: the ruling moves left boundaries, not anchors, so these rows are left out of
#: the glued-date case (the row-start branch of `brand_dep` and `dep_brand`, and Square's whole-row Activity type).
ROW_ANCHORED_CARD_ROWS = {
    ("brand_dep", "VISA DEP 1"),
    ("dep_brand", "DEP VISA 1"),
    ("square_checking_sales", "CARD PAYMENT SALES"),
}


def _card_form_pattern(label):
    return next(form.pattern for form in registry.CARD_SETTLEMENT_CREDIT_FORMS if form.label == label)


def test_every_card_form_has_a_fabricated_row():
    assert {label for label, _ in CARD_FORM_ROWS} == {form.label for form in registry.CARD_SETTLEMENT_CREDIT_FORMS}


@pytest.mark.parametrize(("label", "row"), [pair for pair in CARD_FORM_ROWS if pair not in ROW_ANCHORED_CARD_ROWS])
def test_a_card_form_reads_its_row_with_a_date_glued_on_the_left(label, row):
    # §7.0: '01/02Bankcard Deposit' normalizes to '01 02BANKCARD DEPOSIT'; the left boundary is (?<![A-Z]), never \b.
    pattern = _card_form_pattern(label)
    assert re.search(pattern, row)
    assert re.search(pattern, "01 02" + row)


@pytest.mark.parametrize(("label", "row"), CARD_FORM_ROWS)
def test_a_letter_glued_on_the_left_still_blocks_a_card_form(label, row):
    # The boundary lets a digit through, not a letter: the form's leading token is still a whole word on its left.
    pattern = _card_form_pattern(label)
    assert re.search(pattern, row)
    assert not re.search(pattern, "X" + row)


def test_the_payer_tables_collide_with_no_ledger_or_insurer_alias(monkeypatch):
    monkeypatch.setattr(registry, "HEALTHCARE_PAYER_ALIASES", {"Fabrikam Care": ("BCBSM",)})
    assert any("insurer alias" in problem for problem in operating_registry.problems())


def test_the_bnpl_settlements_are_payout_credit_entities():
    assert {"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"} <= set(registry.PAYOUT_CREDIT_ENTITIES)
