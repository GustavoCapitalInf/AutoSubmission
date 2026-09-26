"""Contract C2: the regrouped registry and its compatibility names."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis import classification_registry as registry

ROOT = Path(__file__).resolve().parent.parent
GROUP_TABLES = (
    "LENDER_ALIASES",
    "ALTERNATIVE_POSITION_ALIASES",
    "LINE_OF_CREDIT_ALIASES",
    "CARD_ISSUER_ALIASES",
    "CARD_ISSUER_CONTEXT_ALIASES",
    "VEHICLE_FINANCE_ALIASES",
    "MORTGAGE_SERVICER_ALIASES",
    "LEASE_RENTAL_ALIASES",
    "PERSONAL_LOAN_ALIASES",
    "FLOOR_PLAN_ALIASES",
    "FACTORING_ALIASES",
    "PREMIUM_FINANCE_ALIASES",
    "BANK_NAME_ALIASES",
    "POTENTIAL_LENDER_ALIASES",
    "INSURANCE_PROVIDER_ALIASES",
    "OPERATING_REVENUE_SOURCE_ALIASES",
)
LEGACY_NAMES = ("LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES", "LEASE_PROVIDER_ALIASES")


@pytest.mark.parametrize("name", GROUP_TABLES)
def test_every_table_maps_an_entity_to_a_tuple_of_string_aliases(name):
    table = getattr(registry, name)
    assert isinstance(table, dict)
    for entity, aliases in table.items():
        assert isinstance(entity, str) and entity
        assert isinstance(aliases, tuple) and aliases, entity
        assert all(isinstance(alias, str) and alias for alias in aliases), entity


def test_payee_group_registries_follow_the_contract_order_and_are_the_tables_themselves():
    assert list(registry.PAYEE_GROUP_REGISTRIES) == [
        "confirmed_lender",
        "alternative_position",
        "line_of_credit",
        "vehicle_financing",
        "mortgage",
        "personal_loan",
        "floor_plan_financing",
        "factoring",
        "lease_or_rental",
        "credit_card_payment",
    ]
    expected = (
        registry.LENDER_ALIASES,
        registry.ALTERNATIVE_POSITION_ALIASES,
        registry.LINE_OF_CREDIT_ALIASES,
        registry.VEHICLE_FINANCE_ALIASES,
        registry.MORTGAGE_SERVICER_ALIASES,
        registry.PERSONAL_LOAN_ALIASES,
        registry.FLOOR_PLAN_ALIASES,
        registry.FACTORING_ALIASES,
        registry.LEASE_RENTAL_ALIASES,
        registry.CARD_ISSUER_ALIASES,
    )
    assert len(registry.PAYEE_GROUP_REGISTRIES) == len(expected)
    assert all(actual is table for actual, table in zip(registry.PAYEE_GROUP_REGISTRIES.values(), expected))


def test_confirmed_lender_aliases_is_the_compatibility_name_of_the_lender_table():
    assert registry.CONFIRMED_LENDER_ALIASES is registry.LENDER_ALIASES


def test_the_context_bank_potential_and_premium_tables_stay_out_of_the_known_payee_matcher():
    matcher_tables = [id(table) for table in registry.PAYEE_GROUP_REGISTRIES.values()]
    for name in ("CARD_ISSUER_CONTEXT_ALIASES", "BANK_NAME_ALIASES", "POTENTIAL_LENDER_ALIASES",
                 "PREMIUM_FINANCE_ALIASES"):
        assert id(getattr(registry, name)) not in matcher_tables, name


def test_premium_finance_payees_share_no_entity_with_a_group_table():
    premium = registry.PREMIUM_FINANCE_ALIASES
    for table in registry.PAYEE_GROUP_REGISTRIES.values():
        assert not set(premium) & set(table)


def test_the_legacy_lists_are_read_only_by_the_pre_s2_classifier():
    readers = set()
    for path in sorted((ROOT / "analysis").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(re.search(rf"\b{name}\b", text) for name in LEGACY_NAMES):
            readers.add(path.name)
    assert readers <= {"classification_registry.py", "transaction_classifier.py"}
