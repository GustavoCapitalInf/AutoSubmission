"""Contract C1: the flagged obligation groups (spec section 4.2, amended 2026-09-24)."""
from __future__ import annotations

import ast
from pathlib import Path

from analysis.flag_groups import (
    FINANCING_STATES,
    FLAG_GROUP_BY_KEY,
    FLAG_GROUP_BY_STATE,
    FLAG_GROUPS,
    FLAG_SETTING_KEYS,
    FlagGroup,
)

EXPECTED = (
    ("alternative_position", "alternative_positions", "flag_alternative_positions", "Alternative positions"),
    ("line_of_credit", "lines_of_credit", "flag_lines_of_credit", "Lines of credit"),
    ("credit_card_payment", "credit_cards", "flag_credit_cards", "Credit cards"),
    ("vehicle_financing", "vehicle_financing", "flag_vehicle_financing", "Vehicle loans & leases"),
    ("bank_loan", "bank_loans", "flag_bank_loans", "Bank loans"),
    ("mortgage", "mortgages", "flag_mortgages", "Mortgages"),
    ("lease_or_rental", "leases_rentals", "flag_leases_rentals", "Leases & rentals"),
    ("personal_loan", "personal_loans", "flag_personal_loans", "Personal loans"),
    ("floor_plan_financing", "floor_plan", "flag_floor_plan", "Floor plan"),
    ("factoring", "factoring", "flag_factoring", "Factoring"),
    (None, "premium_financing", "flag_premium_financing", "Premium financing"),
)


def test_the_eleven_groups_match_the_spec_table_in_order():
    assert tuple((g.state, g.key, g.setting, g.label) for g in FLAG_GROUPS) == EXPECTED
    assert all(isinstance(g, FlagGroup) for g in FLAG_GROUPS)


def test_premium_financing_is_the_one_group_without_a_state():
    assert [g.key for g in FLAG_GROUPS if g.state is None] == ["premium_financing"]


def test_lookups_and_setting_keys_are_derived_from_the_one_tuple():
    assert FLAG_GROUP_BY_STATE == {g.state: g for g in FLAG_GROUPS if g.state is not None}
    assert None not in FLAG_GROUP_BY_STATE
    assert len(FLAG_GROUP_BY_STATE) == 10
    assert FLAG_GROUP_BY_KEY == {g.key: g for g in FLAG_GROUPS}
    assert FLAG_SETTING_KEYS == tuple(row[2] for row in EXPECTED)


def test_financing_states_are_the_d1_groups_and_never_cards_leases_or_premium_financing():
    assert FINANCING_STATES == frozenset({
        "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan",
        "vehicle_financing", "mortgage", "personal_loan", "floor_plan_financing", "factoring",
    })
    assert "credit_card_payment" not in FINANCING_STATES
    assert "lease_or_rental" not in FINANCING_STATES
    assert "insurance" not in FINANCING_STATES


def test_flag_groups_imports_nothing_from_the_analysis_package():
    source = Path(__file__).resolve().parent.parent / "analysis" / "flag_groups.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append((node.level, node.module or ""))
        elif isinstance(node, ast.Import):
            imported.extend((0, alias.name) for alias in node.names)
    assert all(level == 0 and not module.startswith("analysis") for level, module in imported), imported
