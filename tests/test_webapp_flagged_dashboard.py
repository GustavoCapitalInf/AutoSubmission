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


# ---------------------------------------------------------------- Task 2: the Flagged chip and ledger filter

ROWS = r"""
const rowsOf = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((match) => match[1]);
const datesOf = (html) => rowsOf(html).map((row) => (row.match(/<td class="tx-date">([^<]*)<\/td>/) || [])[1]);
const flaggedOf = (html) => rowsOf(html).map((row) => row.includes('<span class="chip-text">Flagged</span>'));
"""


def _row(location, date, description, amount, state, *, entity=None, group=None, counted=None, shown=None,
         revenue=None):
    """A ledger row as the server serves it: its classification record (C4) and the serving-time flag_shown (C6)."""
    record = {"classification": state, "canonical_entity": entity, "source_location": location, "flagged_group": group,
              "contributes_to_flagged_totals": bool(group) if counted is None else counted,
              "flag_shown": bool(group) if shown is None else shown}
    if revenue:
        record["revenue_classification"] = revenue
    return {"date": date, "description": description, "amount": amount, "classification": record}


LEDGER = [
    _row("transaction:1", "2031-03-03", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages"),
    _row("transaction:2", "2031-03-05", "ONLINE PAYMENT FABRICATED CARD", -300.0, "credit_card_payment",
         group="credit_cards"),
    _row("transaction:3", "2031-03-17", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages"),
    # The same debit printed twice: tagged and shown, never counted (a proven duplicate).
    _row("transaction:4", "2031-03-17", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages", counted=False),
    _row("transaction:5", "2031-03-20", "ACH CREDIT FABRICATED CUSTOMER", 5000.0, "other", revenue="verified_revenue"),
    # A group unticked in Settings: the server served its row with flag_shown false.
    _row("transaction:6", "2031-03-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0, "vehicle_financing",
         entity="FABRICATED AUTO FINANCE", group="vehicle_financing", shown=False),
]

# detection.flagged_positions as S2 serves it (C5): group order, then total, then payee. An unnamed payee is its group.
POSITIONS = [
    {"group": "credit_cards", "payee": "Credit cards", "matched_alias": None, "count": 1, "total_debited": 300.0,
     "cadence": "single", "avg_gap_days": None, "first_date": "2031-03-05", "last_date": "2031-03-05",
     "source_locations": ["transaction:2"]},
    {"group": "mortgages", "payee": "FABRICATED MORTGAGE CO", "matched_alias": "FABRICATED MORTGAGE", "count": 2,
     "total_debited": 2400.0, "cadence": "biweekly", "avg_gap_days": 14.0, "first_date": "2031-03-03",
     "last_date": "2031-03-17", "source_locations": ["transaction:1", "transaction:3"]},
]


def _statement(*, positions=POSITIONS, ledger=LEDGER, currency="CAD", outdated=None):
    """One account as /analysis serves it. `positions=None` is an analysis saved before flagged positions existed."""
    detection = {"known_funders": [], "potential_lenders": [], "insurance_providers": []}
    if positions is not None:
        detection["flagged_positions"] = positions
    payload = {"statement": {"bank": "FABRICATED COMMUNITY BANK", "currency": currency, "period_start": "2031-03-01",
                             "period_end": "2031-03-31", "transactions": ledger},
               "metrics": {"flagged_groups": {"credit_cards": {"count": 1, "total": 300.0, "payees": 1},
                                              "mortgages": {"count": 2, "total": 2400.0, "payees": 1}}},
               "detection": detection}
    if outdated is not None:
        payload["analysis_rules_outdated"] = outdated
    return payload


def _load(job_id, payload):
    """Serve one statement and open it, as a reopen from Recent does."""
    return _serve(**{job_id: payload}) + (f"currentJobId = '{job_id}'; currentJobIds = ['{job_id}'];"
                                         f" loadResults('{job_id}'); await settle();\n")


@needs_node
def test_rows_shown_as_flagged_carry_the_chip_and_the_flagged_filter_keeps_only_them():
    result = run_dashboard(ROWS + _load("s", _statement()) + """
const all = {dates: datesOf(els.transactionTable.innerHTML), flagged: flaggedOf(els.transactionTable.innerHTML)};
transactionFilter = 'flagged'; renderMainTransactions();
console.log(JSON.stringify({all, filtered: {dates: datesOf(els.transactionTable.innerHTML),
  count: els.transactionCount.textContent}}));
""")
    assert result["all"]["dates"] == ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17", "2031-03-20",
                                      "2031-03-24"]
    # Flagged: both mortgage debits, the duplicate and the card payment; never the revenue credit, never a row of a
    # group unticked in Settings.
    assert result["all"]["flagged"] == [True, True, True, True, False, False]
    assert result["filtered"] == {"dates": ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17"],
                                  "count": "4 flagged matches"}


def _insured(row):
    """A row counted in the insurance totals, as the classifier leaves every insurance row (C4)."""
    row["classification"]["contributes_to_insurance_totals"] = True
    return row


# Premium financing (C1, C4) is no state of its own: its rows stay insurance, in the insurance totals, and are flagged
# through flagged_group. A plain insurer's row is not flagged.
PREMIUM_LEDGER = [
    _insured(_row("transaction:1", "2031-03-04", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0, "insurance",
                  entity="FABRICATED PREMIUM FINANCE", group="premium_financing")),
    _insured(_row("transaction:2", "2031-03-09", "ACH DEBIT FABRICATED INSURER", -90.0, "insurance",
                  entity="FABRICATED INSURER")),
    _insured(_row("transaction:3", "2031-03-18", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0, "insurance",
                  entity="FABRICATED PREMIUM FINANCE", group="premium_financing")),
]

PREMIUM_POSITIONS = [
    {"group": "premium_financing", "payee": "FABRICATED PREMIUM FINANCE", "matched_alias": "FABRICATED PREMIUM FINANCE",
     "count": 2, "total_debited": 500.0, "cadence": "biweekly", "avg_gap_days": 14.0, "first_date": "2031-03-04",
     "last_date": "2031-03-18", "source_locations": ["transaction:1", "transaction:3"]},
]


@needs_node
def test_a_premium_financing_row_keeps_its_insurance_tag_and_filter_and_carries_the_chip():
    result = run_dashboard(ROWS + _load("p", _statement(positions=PREMIUM_POSITIONS, ledger=PREMIUM_LEDGER)) + """
const tagged = (text) => rowsOf(els.transactionTable.innerHTML)
  .map((row) => row.includes(`<span class="chip-text">${text}</span>`));
const all = {dates: datesOf(els.transactionTable.innerHTML), tag: tagged('FABRICATED PREMIUM FINANCE'),
  flagged: flaggedOf(els.transactionTable.innerHTML)};
transactionFilter = 'insurance'; renderMainTransactions();
const insurance = datesOf(els.transactionTable.innerHTML);
transactionFilter = 'flagged'; renderMainTransactions();
console.log(JSON.stringify({all, insurance, flagged: datesOf(els.transactionTable.innerHTML)}));
""")
    assert result["all"] == {"dates": ["2031-03-04", "2031-03-09", "2031-03-18"], "tag": [True, False, True],
                             "flagged": [True, False, True]}
    # Still insurance: the Insurance pill keeps every insurance row, the premium-financing ones included.
    assert result["insurance"] == ["2031-03-04", "2031-03-09", "2031-03-18"]
    assert result["flagged"] == ["2031-03-04", "2031-03-18"]


def test_both_ledgers_offer_the_flagged_filter():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert 'data-transaction-filter="flagged">Flagged</button>' in html
    assert 'data-modal-transaction-filter="flagged">Flagged</button>' in html


# ---------------------------------------------------------------- Task 3: the panel on a statement

PANEL = """
console.log(JSON.stringify({rows: cells(els.flaggedTable.innerHTML), count: els.flaggedCount.textContent,
  html: els.flaggedTable.innerHTML}));
"""

# The two rows a panel with no payee draws, as `cells` reads them (tags stripped).
NO_FLAGGED_PAYMENTS = "No flagged paymentsNo group ticked in Settings has payments here."
NOT_AVAILABLE = "Not availableAnalysed before flagged positions existed; re-analyze to see them."


@needs_node
def test_the_statement_panel_lists_each_payee_with_its_group_count_total_and_cadence():
    result = run_dashboard(CELLS + _load("s", _statement()) + PANEL)
    # Money in the statement's own currency (CA$), never the USD default.
    assert result["rows"] == [
        ["Credit cards", "Credit cards", "1", "CA$300.00", "Single payment"],
        ["Mortgages", "FABRICATED MORTGAGE CO", "2", "CA$2,400.00", "Every two weeks2031-03-03 to 2031-03-17"],
    ]
    assert result["count"] == "2 payees"
    assert 'data-lender-evidence-filter="flagged:mortgages"' in result["html"]
    assert 'data-lender-evidence-entity="FABRICATED MORTGAGE CO"' in result["html"]


@needs_node
@pytest.mark.parametrize(("positions", "row", "count"), [
    ([], NO_FLAGGED_PAYMENTS, "0 payees"),
    # Saved before flagged positions existed: the dashboard cannot tell whether any group was paid, and says so.
    (None, NOT_AVAILABLE, "Not available"),
], ids=["no-ticked-group-paid", "saved-before-flagged-positions"])
def test_a_statement_without_flagged_positions_says_why(positions, row, count):
    result = run_dashboard(CELLS + _load("s", _statement(positions=positions)) + PANEL)
    assert result["rows"] == [[row]]
    assert 'colspan="5"' in result["html"] and result["count"] == count


def test_the_panel_sits_after_the_evidence_and_reuses_no_lender_header():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    card = html[html.index('id="flaggedCard"'):]
    card = card[:card.index("</section>")]
    assert re.findall(r"<th[^>]*>([^<]*)</th>", card) == ["Group", "Payee", "Count", "Total", "Cadence", "Statements"]
    assert '<tbody id="flaggedTable">' in card and 'id="flaggedCount"' in card and "Flagged positions</h3>" in card
    for reused in ("Potential Withholding", "Eligible Deposits", "Exposure"):
        assert reused not in card
    assert html.index('aria-label="Evidence"') < html.index('id="flaggedCard"') \
        < html.index('aria-label="Package summary and processing"')
