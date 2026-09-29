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
