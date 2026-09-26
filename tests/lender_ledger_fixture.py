"""A fabricated curated ledger (contract C10) and the hand-kept inputs its validator reads.

Every company name, spelling and URL here is invented; none comes from a statement."""
from __future__ import annotations

import copy

from tools.lender_ledger import Rules


def entity(name, group, aliases, *, status="admitted", business_type="mca_or_revenue_based_funder",
           short_alias_reason=None, evidence=None, verdicts=None, where_looked=None, notes=""):
    slug = name.split()[0].lower()
    return {
        "entity": name,
        "group": group,
        "business_type": business_type,
        "aliases": list(aliases),
        "status": status,
        "short_alias_reason": short_alias_reason,
        "evidence": ([{"source": f"https://{slug}.example/", "note": "fabricated company site"}]
                     if evidence is None else evidence),
        "verdicts": ([{"round": "r1", "verdict": "upheld", "confirmed": True}] if verdicts is None else verdicts),
        "where_looked": [f"https://{slug}.example/"] if where_looked is None else where_looked,
        "notes": notes,
    }


UNRESOLVED = [{"round": "r2", "verdict": "unresolved", "confirmed": False}]

#: Index, name: 0 Quillon Funding, 1 Oldco Funding, 2 Ruledco, 3 Brambleway Capital, 4 Oxbow Card, 5 Oxbow,
#: 6 Rivett Motor Credit, 7 Penwick Mortgage, 8 Westfen Leasing, 9 Kelder Loans, 10 Gantry Floorplan Credit,
#: 11 Loxley Factoring, 12 Hollin Premium Finance, 13 Brisk Mutual Funding, 14 Brambleway Bank,
#: 15 Heldco Advance, 16 Marsh Recovery, 17 Tarnmoor Capital.
ENTITIES = [
    entity("Quillon Funding", "confirmed_lender", ["QUILLON FUNDING", "QUILLONFUND"]),
    entity("Oldco Funding", "confirmed_lender", ["OLDCO FUNDING", "OLDCO"]),
    entity("Ruledco", "alternative_position", ["RULEDCO CAPITAL"], business_type="platform_embedded_financing",
           notes="Move: fabricated owner ruling, an alternative position."),
    entity("Brambleway Capital", "line_of_credit", ["BRAMBLEWAY CAPITAL"], business_type="business_loc_provider"),
    entity("Oxbow Card", "credit_card_payment", ["OXBOW CARD PMT"], business_type="credit_card_payment"),
    entity("Oxbow", "card_issuer_context", ["OXBOW"], business_type="credit_card_payment"),
    entity("Rivett Motor Credit", "vehicle_financing", ["RIVETT MOTOR CREDIT"],
           business_type="auto_or_vehicle_finance"),
    entity("Penwick Mortgage", "mortgage", ["PENWICK MTG"], business_type="mortgage_servicer"),
    entity("Westfen Leasing", "lease_or_rental", ["WESTFEN LEASING"], business_type="lease_to_own"),
    entity("Kelder Loans", "personal_loan", ["KELDER LOANS"], business_type="personal_or_consumer_loan"),
    entity("Gantry Floorplan Credit", "floor_plan_financing", ["GANTRY FLOORPLAN"],
           business_type="floor_plan_financing"),
    entity("Loxley Factoring", "factoring", ["LOXLEY FACTORING"], business_type="factoring"),
    entity("Hollin Premium Finance", "premium_financing", ["HOLLIN PREMIUM FIN"], business_type="premium_finance"),
    entity("Brisk Mutual Funding", "premium_financing", ["BRISK MUTUAL FUNDING"], business_type="premium_finance"),
    entity("Brambleway Bank", "bank_name", ["BRAMBLEWAY BANK"], business_type="bank_loan_or_bank_loc"),
    entity("Heldco Advance", "confirmed_lender", ["HELDCO ADVANCE"], status="review", evidence=[],
           verdicts=UNRESOLVED, where_looked=["https://registry.example/heldco", "https://heldco.example/"],
           notes="Fabricated: identity unconfirmed."),
    entity("Marsh Recovery", "potential_lender", ["MARSH RECOVERY"], status="owner_ruling",
           business_type="servicer_or_processor_for_funders", evidence=[], verdicts=UNRESOLVED,
           where_looked=["https://marsh.example/", "https://registry.example/marsh"],
           notes="Fabricated: a collector whose funder is unknown; the owner decides."),
    entity("Tarnmoor Capital", "confirmed_lender", ["TARNMOOR CAP"], status="rejected",
           evidence=[{"source": "https://tarnmoor.example/", "note": "fabricated: a bakery"}],
           verdicts=[{"round": "r2", "verdict": "refuted", "confirmed": False}],
           where_looked=["https://registry.example/tarnmoor"], notes="Fabricated: a bakery, not a funder."),
]

#: Today's three lists, as the validator reads them from git (fabricated).
BASELINE = {
    "CONFIRMED_LENDER_ALIASES": {"Oldco Funding": ("OLDCO FUNDING", "OLDCO"), "Ruledco": ("RULEDCO CAPITAL",)},
    "POTENTIAL_LENDER_ALIASES": {"Heldco Advance": ("HELDCO ADVANCE",)},
    "LEASE_PROVIDER_ALIASES": {"Westfen Leasing": ("WESTFEN LEASING",)},
}

OWNER_NAMED = {
    "confirmed_lender": (("Quillon", "QUILLON FUNDING"),),
    "alternative_position": (("Ruledco", "RULEDCO CAPITAL"),),
    "line_of_credit": (("Brambleway", "BRAMBLEWAY CAPITAL"),),
    "credit_card_payment": (("Oxbow", "OXBOW CARD PMT"),),
    "floor_plan_financing": (("Gantry", "GANTRY FLOORPLAN"),),
    "factoring": (("Loxley", "LOXLEY FACTORING"),),
    "premium_financing": (("Hollin", "HOLLIN PREMIUM FIN"),),
    "bank_name": (("Brambleway Bank", "BRAMBLEWAY BANK LN PYMT"),),
}

HAND_KEPT = {
    "INSURANCE_PROVIDER_ALIASES": {"Brisk Mutual": ("BRISK MUTUAL",)},
    "OPERATING_REVENUE_SOURCE_ALIASES": {"Zanthos Pay": ("ZANTHOS PAY", "ZANTHOS")},
}

RULES = Rules(
    owner_named=OWNER_NAMED,
    platforms=frozenset({"ZANTHOS", "VELLUM"}),
    brands=frozenset({"RIVETT"}),
    hand_kept=HAND_KEPT,
    baseline=BASELINE,
    premium_insurer_aliases=frozenset(),
    merged={},
    payout_credit=(),
)


def ledger(*changes):
    """The fabricated ledger, with ``(index, field, value)`` changes applied to a deep copy."""
    entities = copy.deepcopy(ENTITIES)
    for index, field_name, value in changes:
        entities[index][field_name] = value
    return {"schema": 1, "entities": entities}
