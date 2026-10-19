"""The flagged obligation groups (spec section 4.2): one Settings checkbox each, never lender math.

This module imports nothing from the rest of ``analysis``: the classifier, the serving layer and the
dashboard test all read the groups from here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagGroup:
    state: str | None  # classification state, e.g. "alternative_position"; None = set by rule (premium financing)
    key: str        # flagged_group value and payload key, e.g. "alternative_positions"
    setting: str    # webapp Settings key, e.g. "flag_alternative_positions"
    label: str      # human label, e.g. "Alternative positions"


FLAG_GROUPS: tuple[FlagGroup, ...] = (
    FlagGroup("alternative_position", "alternative_positions", "flag_alternative_positions", "Alternative positions"),
    FlagGroup("line_of_credit", "lines_of_credit", "flag_lines_of_credit", "Lines of credit"),
    FlagGroup("credit_card_payment", "credit_cards", "flag_credit_cards", "Credit cards"),
    FlagGroup("vehicle_financing", "vehicle_financing", "flag_vehicle_financing", "Vehicle loans & leases"),
    FlagGroup("bank_loan", "bank_loans", "flag_bank_loans", "Bank loans"),
    FlagGroup("mortgage", "mortgages", "flag_mortgages", "Mortgages"),
    FlagGroup("lease_or_rental", "leases_rentals", "flag_leases_rentals", "Leases & rentals"),
    FlagGroup("personal_loan", "personal_loans", "flag_personal_loans", "Personal loans"),
    FlagGroup("floor_plan_financing", "floor_plan", "flag_floor_plan", "Floor plan"),
    FlagGroup("factoring", "factoring", "flag_factoring", "Factoring"),
    # Premium financing: rows keep classification "insurance" (and their insurance totals); the classifier
    # sets flagged_group="premium_financing" when the insurance match is a PREMIUM_FINANCE_ALIASES payee.
    FlagGroup(None, "premium_financing", "flag_premium_financing", "Premium financing"),
    # Owner ruling 2026-09-27 (classification 5.3): debt-settlement account processors and debtor-side debt-relief
    # firms. Never lender math, and not in FINANCING_STATES: its payees never lend.
    FlagGroup("debt_relief", "debt_relief", "flag_debt_relief", "Debt relief"),
)
FLAG_GROUP_BY_STATE: dict[str, FlagGroup] = {g.state: g for g in FLAG_GROUPS if g.state is not None}
FLAG_GROUP_BY_KEY: dict[str, FlagGroup] = {g.key: g for g in FLAG_GROUPS}
FLAG_SETTING_KEYS: tuple[str, ...] = tuple(g.setting for g in FLAG_GROUPS)
# D1: a credit from a payee of these states is financing proceeds (non_revenue + lender credit exclusion),
# except a PAYOUT_CREDIT_ENTITIES entity's credit (revenue) and a factoring payee's credit (owner ruling
# 2026-09-26: revenue, and flagged as factoring).
FINANCING_STATES: frozenset[str] = frozenset({
    "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan",
    "vehicle_financing", "mortgage", "personal_loan", "floor_plan_financing", "factoring",
})
