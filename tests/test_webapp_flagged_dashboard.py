"""The dashboard's flagged positions (webapp/static/app.js, webapp/templates/index.html), driven end to end in node on
a fake page (tests/webapp_js_harness.py): the tags of the new classification states, the Flagged chip and ledger
filter, the Flagged positions panel on a statement, a package and the statement window, the Settings switches, and the
notice on a statement analysed with older lender rules. The payloads follow the service contract
(docs/superpowers/plans/2026-09-24-lender-detection.md, C5, C6 and C8); every descriptor, payee and amount is
fabricated, and every amount is whole dollars."""
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import CELLS, _serve
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


# ---------------------------------------------------------------- Task 1: tags of the new states

@needs_node
def test_every_new_state_has_its_own_tag_and_the_retired_state_keeps_one():
    states = [
        ("alternative_position", "FABRICATED PLATFORM CAPITAL", "FABRICATED PLATFORM CAPITAL (Alternative position)"),
        ("line_of_credit", None, "Line of credit"),
        ("vehicle_financing", "FABRICATED AUTO FINANCE", "FABRICATED AUTO FINANCE (Vehicle loan / lease)"),
        ("bank_loan", None, "Bank loan"),
        ("mortgage", "FABRICATED MORTGAGE CO", "FABRICATED MORTGAGE CO (Mortgage)"),
        ("lease_or_rental", None, "Lease / rental"),
        ("personal_loan", "FABRICATED PERSONAL LENDER", "FABRICATED PERSONAL LENDER (Personal loan)"),
        ("floor_plan_financing", "FABRICATED FLOORING CAPITAL", "FABRICATED FLOORING CAPITAL (Floor plan)"),
        ("factoring", None, "Factoring"),
        # Retired on 2026-09-24; an analysis saved before then still carries it.
        ("lease_or_equipment_financing", "FABRICATED LEASING", "Lease / Equipment"),
        # The Credit cards group names its card issuer, as the Flagged positions panel does.
        ("credit_card_payment", "FABRICATED CARD ISSUER", "FABRICATED CARD ISSUER (Credit card)"),
        ("credit_card_payment", None, "Credit Card Payment"),
    ]
    debits = [{"amount": -100.0, "classification": {"classification": state, "canonical_entity": entity}}
              for state, entity, _ in states]
    credit = {"amount": 900.0, "classification": {"classification": "other", "canonical_entity": "FABRICATED LINE LENDER",
                                                  "revenue_classification": "non_revenue"}}
    # Premium financing is no state of its own: the row stays insurance and is flagged through flagged_group (C4).
    premium = {"amount": -250.0, "classification": {"classification": "insurance",
                                                    "canonical_entity": "FABRICATED PREMIUM FINANCE",
                                                    "flagged_group": "premium_financing"}}
    result = run_dashboard(f"""
const debits = {json.dumps(debits)};
console.log(JSON.stringify({{labels: debits.map((tx) => transactionCategory(tx).label),
  credit: transactionCategory({json.dumps(credit)}).label, premium: transactionCategory({json.dumps(premium)})}}));
""")
    assert result["labels"] == [label for _, _, label in states]
    # A credit shows its revenue state first, whoever paid it.
    assert result["credit"] == "Non-Revenue"
    # A premium-financing row keeps its insurance tag, unchanged.
    assert result["premium"] == {"label": "FABRICATED PREMIUM FINANCE", "glyph": "INS", "tone": "blue"}
