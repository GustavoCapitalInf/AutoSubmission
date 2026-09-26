"""Flag groups as Settings shows them (lender detection §8.2, plan contract C6). Fabricated payloads only."""
from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS


def test_the_view_reads_the_eleven_contract_groups():
    assert tuple(group.key for group in FLAG_GROUPS) == (
        "alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing",
        "bank_loans", "mortgages", "leases_rentals", "personal_loans",
        "floor_plan", "factoring", "premium_financing",
    )
    assert FLAG_SETTING_KEYS == tuple(f"flag_{group.key}" for group in FLAG_GROUPS)
    # Premium financing is the one group with no state of its own: its rows stay insurance (C1, C4).
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]
