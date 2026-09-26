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


# ---------------------------------------------------------------- Task 4: a payee click filters the ledger

PAYEE_CLICK = """
const clickPayee = (table, group, payee) => {
  const button = fakeElement('payee'); button.closest = () => button;
  button.attributes['data-lender-evidence-filter'] = `flagged:${group}`;
  button.attributes['data-lender-evidence-entity'] = payee;
  table.listeners.click[0]({target: button});
};
"""


@needs_node
def test_a_payee_click_filters_the_ledger_to_the_rows_behind_it():
    result = run_dashboard(ROWS + PAYEE_CLICK + _load("s", _statement()) + """
const shown = () => ({filter: transactionFilter, entity: transactionEntityFilter,
  count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML)});
clickPayee(els.flaggedTable, 'mortgages', 'FABRICATED MORTGAGE CO');
const mortgage = shown();
clickPayee(els.flaggedTable, 'credit_cards', 'Credit cards');
console.log(JSON.stringify({mortgage, card: shown()}));
""")
    # The rows the panel counted: the duplicate is tagged but not behind the payee's count.
    assert result["mortgage"] == {"filter": "flagged:mortgages", "entity": "FABRICATED MORTGAGE CO",
                                  "count": "2 FABRICATED MORTGAGE CO", "dates": ["2031-03-03", "2031-03-17"]}
    # An unnamed payee is its group, as the server names it.
    assert result["card"] == {"filter": "flagged:credit_cards", "entity": "Credit cards", "count": "1 Credit cards",
                              "dates": ["2031-03-05"]}


@needs_node
def test_a_premium_financing_payee_is_listed_under_its_group_and_its_click_shows_its_insurance_rows():
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK
                           + _load("p", _statement(positions=PREMIUM_POSITIONS, ledger=PREMIUM_LEDGER)) + """
const panel = cells(els.flaggedTable.innerHTML);
clickPayee(els.flaggedTable, 'premium_financing', 'FABRICATED PREMIUM FINANCE');
console.log(JSON.stringify({panel, filter: transactionFilter, count: els.transactionCount.textContent,
  dates: datesOf(els.transactionTable.innerHTML)}));
""")
    assert result["panel"] == [["Premium financing", "FABRICATED PREMIUM FINANCE", "2", "CA$500.00",
                                "Every two weeks2031-03-04 to 2031-03-18"]]
    # Keyed on flagged_group, not on the state: the rows stay insurance, and the plain insurer's row is left out.
    assert result["filter"] == "flagged:premium_financing"
    assert result["count"] == "2 FABRICATED PREMIUM FINANCE"
    assert result["dates"] == ["2031-03-04", "2031-03-18"]


# ---------------------------------------------------------------- Task 5: the panel on a package

PACKAGE = {
    "totals": {"decision": "approved", "flagged_position_count": 8, "flagged_position_total": 5450.0},
    "currency": {"currency": "CAD", "currencies": ["CAD"]},
    "documents": [], "transactions": [], "funders": [], "potential_lenders": [], "insurance_providers": [],
    # The package roll-up (C6): one list per ticked group, keyed by group, in no particular key order. It holds the
    # three groups of the owner's amendment (floor plan, factoring, premium financing) beside two older ones.
    "flagged_positions": {
        "factoring": [{"payee": "FABRICATED FACTOR FUNDING", "documents": 1, "count": 1, "total_debited": 150.0,
                       "cadence": "single", "first_date": "2031-02-10", "last_date": "2031-02-10"}],
        "premium_financing": [{"payee": "FABRICATED PREMIUM FINANCE", "documents": 1, "count": 2,
                               "total_debited": 500.0, "cadence": "biweekly", "first_date": "2031-02-04",
                               "last_date": "2031-02-18"}],
        "vehicle_financing": [{"payee": "FABRICATED AUTO FINANCE", "documents": 2, "count": 2, "total_debited": 800.0,
                               "cadence": "monthly", "first_date": "2031-01-24", "last_date": "2031-02-24"}],
        "floor_plan": [{"payee": "FABRICATED FLOORING CAPITAL", "documents": 2, "count": 2, "total_debited": 3000.0,
                        "cadence": "monthly", "first_date": "2031-01-15", "last_date": "2031-02-15"}],
        "alternative_positions": [{"payee": "FABRICATED PLATFORM CAPITAL", "documents": 1, "count": 1,
                                   "total_debited": 1000.0, "cadence": "single", "first_date": "2031-02-03",
                                   "last_date": "2031-02-03"}],
    },
}


def _in_statement(job_id, row):
    """A row of the package's combined ledger: the member's row, with the statement it came from."""
    return {**row, "source_job": job_id, "source_currency": "CAD"}


# The combined ledger behind PACKAGE's flagged positions. It holds the auto-finance debits of two statements, one of
# them printed twice (tagged, never counted), payees of two other groups, a revenue credit, and the premium-financing
# debits, which stay insurance, beside a plain insurer's debit.
PACKAGE_LEDGER = [
    _in_statement("a", _row("transaction:1", "2031-01-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing")),
    _in_statement("a", _row("transaction:2", "2031-01-27", "ACH CREDIT FABRICATED CUSTOMER", 5000.0, "other",
                            revenue="verified_revenue")),
    _in_statement("b", _row("transaction:1", "2031-02-03", "ACH DEBIT FABRICATED PLATFORM CAPITAL", -1000.0,
                            "alternative_position", entity="FABRICATED PLATFORM CAPITAL",
                            group="alternative_positions")),
    _in_statement("b", _row("transaction:2", "2031-02-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing")),
    _in_statement("b", _row("transaction:3", "2031-02-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing",
                            counted=False)),
    _in_statement("b", _row("transaction:4", "2031-02-10", "ACH DEBIT FABRICATED FACTOR FUNDING", -150.0, "factoring",
                            entity="FABRICATED FACTOR FUNDING", group="factoring")),
    _in_statement("b", _insured(_row("transaction:5", "2031-02-04", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0,
                                     "insurance", entity="FABRICATED PREMIUM FINANCE", group="premium_financing"))),
    _in_statement("b", _insured(_row("transaction:6", "2031-02-11", "ACH DEBIT FABRICATED INSURER", -90.0, "insurance",
                                     entity="FABRICATED INSURER"))),
    _in_statement("b", _insured(_row("transaction:7", "2031-02-18", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0,
                                     "insurance", entity="FABRICATED PREMIUM FINANCE", group="premium_financing"))),
]


def _package_page(package):
    return CELLS + f"""
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{rows: cells(els.flaggedTable.innerHTML), count: els.flaggedCount.textContent,
  html: els.flaggedTable.innerHTML, pill: els.decisionPill.textContent}}));
"""


@needs_node
def test_the_package_panel_lists_payees_group_by_group_with_their_statements():
    result = run_dashboard(_package_page(PACKAGE))
    # In FLAG_GROUPS order, whatever the order of the roll-up's keys: the amendment's three groups come last.
    assert result["rows"] == [
        ["Alternative positions", "FABRICATED PLATFORM CAPITAL", "1", "CA$1,000.00", "Single payment", "1"],
        ["Vehicle loans &amp; leases", "FABRICATED AUTO FINANCE", "2", "CA$800.00", "Monthly2031-01-24 to 2031-02-24",
         "2"],
        ["Floor plan", "FABRICATED FLOORING CAPITAL", "2", "CA$3,000.00", "Monthly2031-01-15 to 2031-02-15", "2"],
        ["Factoring", "FABRICATED FACTOR FUNDING", "1", "CA$150.00", "Single payment", "1"],
        ["Premium financing", "FABRICATED PREMIUM FINANCE", "2", "CA$500.00",
         "Every two weeks2031-02-04 to 2031-02-18", "1"],
    ]
    assert result["count"] == "5 payees"
    # Flagged positions never touch the package decision (D7).
    assert result["pill"] == "Package decision · Approved"


@needs_node
def test_a_package_that_refused_its_currency_pools_no_flagged_money():
    refused = {**PACKAGE,
               "currency": {"currency": None, "currencies": ["CAD", "USD"], "cross_currency_totals_refused": True,
                            "refusal_reason": "multiple_currencies"},
               "flagged_positions": {"vehicle_financing": [{**PACKAGE["flagged_positions"]["vehicle_financing"][0],
                                                            "total_debited": None}]}}
    result = run_dashboard(_package_page(refused))
    assert result["rows"] == [["Vehicle loans &amp; leases", "FABRICATED AUTO FINANCE", "2", "N/A",
                               "Monthly2031-01-24 to 2031-02-24", "2"]]


@needs_node
@pytest.mark.parametrize(("positions", "row"), [({}, NO_FLAGGED_PAYMENTS), (None, NOT_AVAILABLE)],
                         ids=["no-ticked-group-paid", "server-before-flagged-positions"])
def test_a_package_without_flagged_positions_says_why(positions, row):
    package = {key: value for key, value in PACKAGE.items() if key != "flagged_positions"}
    if positions is not None:
        package["flagged_positions"] = positions
    result = run_dashboard(_package_page(package))
    assert result["rows"] == [[row]]
    assert 'colspan="6"' in result["html"]


@needs_node
def test_a_package_payee_click_shows_the_combined_ledger_rows_behind_its_count():
    package = {**PACKAGE, "transactions": PACKAGE_LEDGER}
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK + f"""
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
const panel = cells(els.flaggedTable.innerHTML);
const click = (group, payee) => {{
  clickPayee(els.flaggedTable, group, payee);
  return {{filter: transactionFilter, count: els.transactionCount.textContent,
    dates: datesOf(els.transactionTable.innerHTML)}};
}};
const vehicle = click('vehicle_financing', 'FABRICATED AUTO FINANCE');
console.log(JSON.stringify({{panel, vehicle, premium: click('premium_financing', 'FABRICATED PREMIUM FINANCE')}}));
""")
    [vehicle] = [row for row in result["panel"] if "FABRICATED AUTO FINANCE" in row]
    [premium] = [row for row in result["panel"] if "FABRICATED PREMIUM FINANCE" in row]
    # The ledger shows exactly the rows the panel counted, across both statements: never the duplicate, never the
    # other groups' payees, never the credit.
    assert result["vehicle"] == {"filter": "flagged:vehicle_financing",
                                 "count": f"{vehicle[2]} FABRICATED AUTO FINANCE",
                                 "dates": ["2031-01-24", "2031-02-24"]}
    assert vehicle[2] == "2"
    # Premium financing keys on flagged_group: its rows stay insurance, and the plain insurer's row is left out.
    assert result["premium"] == {"filter": "flagged:premium_financing",
                                 "count": f"{premium[2]} FABRICATED PREMIUM FINANCE",
                                 "dates": ["2031-02-04", "2031-02-18"]}
    assert (premium[0], premium[2]) == ("Premium financing", "2")


# ---------------------------------------------------------------- Task 6: the panel in the statement window

@needs_node
def test_the_statement_window_shows_the_flagged_positions_and_a_payee_click_filters_its_ledger():
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK + _serve(m=_statement(), old=_statement(positions=None)) + """
openStatementModal('m');
const loading = els.statementModalFlagged.innerHTML;
await settle();
const rows = cells(els.statementModalFlagged.innerHTML);
clickPayee(els.statementModalFlagged, 'mortgages', 'FABRICATED MORTGAGE CO');
const filtered = {filter: modalTransactionFilter, count: els.statementModalTransactionCount.textContent,
  dates: datesOf(els.statementModalTransactions.innerHTML)};
openStatementModal('old'); await settle();
const old = cells(els.statementModalFlagged.innerHTML);
openStatementModal('gone'); await settle();
console.log(JSON.stringify({loading, rows, filtered, old, failed: els.statementModalFlagged.innerHTML}));
""")
    assert "<strong>Loading</strong>" in result["loading"]
    assert result["rows"] == [
        ["Credit cards", "Credit cards", "1", "CA$300.00", "Single payment"],
        ["Mortgages", "FABRICATED MORTGAGE CO", "2", "CA$2,400.00", "Every two weeks2031-03-03 to 2031-03-17"],
    ]
    assert result["filtered"] == {"filter": "flagged:mortgages", "count": "2 FABRICATED MORTGAGE CO",
                                  "dates": ["2031-03-03", "2031-03-17"]}
    # Saved before flagged positions existed: the window says so, never that no ticked group was paid.
    assert result["old"] == [[NOT_AVAILABLE]]
    assert "<strong>Unable to load statement</strong>" in result["failed"]


def test_the_statement_window_has_its_own_flagged_table():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    modal = html[html.index('id="statementModalBackdrop"'):]
    table = modal[:modal.index('<tbody id="statementModalFlagged">')]
    table = table[table.rindex("<table"):]
    assert re.findall(r"<th[^>]*>([^<]*)</th>", table) == ["Group", "Payee", "Count", "Total", "Cadence"]


# ---------------------------------------------------------------- Task 7: the Settings switches

GROUP_KEYS = ["alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing", "bank_loans",
              "mortgages", "leases_rentals", "personal_loans", "floor_plan", "factoring", "premium_financing"]

SWITCHES = r"""
const switches = () => [...els.flagSettingsList.innerHTML.matchAll(
  /<input type="checkbox" role="switch" id="flagSetting-([a-z_]+)" data-flag-setting="([^"]+)"([^>]*)>/g)]
  .map((m) => ({group: m[1], key: m[2], checked: / checked/.test(m[3]), disabled: / disabled/.test(m[3])}));
"""


def _settings(**overrides):
    """GET/POST /api/settings's `settings` (C7): every flag key on unless overridden."""
    return {"nsf_carry_over": False, **{f"flag_{group}": True for group in GROUP_KEYS}, **overrides}


def _answer(url, answer):
    return f"FAKE_RESPONSES[{json.dumps(url)}] = {json.dumps(answer)};\n"


def test_the_flag_settings_sit_between_analysis_and_statements_with_their_own_status_line():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert html.index('id="analysisSettingsTitle"') < html.index('id="flagSettingsSection"') \
        < html.index('id="statementsSettingsTitle"')
    section = html[html.index('id="flagSettingsSection"'):]
    section = section[:section.index("</section>")]
    assert "Flagged positions</h2>" in section and 'id="flagSettingsList"' in section
    assert '<p class="setting-status" id="flagSettingsStatus" role="status" aria-live="polite"></p>' in section
    # The NSF switch keeps its own line.
    assert html.count('id="settingsStatus"') == 1 and 'id="settingsStatus"' not in section


@needs_node
def test_the_switches_start_held_and_follow_the_saved_settings_once_loaded():
    result = run_dashboard(SWITCHES + """
const atStart = switches();
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_credit_cards=False)}}) + """
loadSettings();
const loading = switches();
await settle();
console.log(JSON.stringify({atStart, loading, loaded: switches(), html: els.flagSettingsList.innerHTML}));
""")
    assert [switch["group"] for switch in result["atStart"]] == GROUP_KEYS
    assert all(switch["key"] == f"flag_{switch['group']}" for switch in result["atStart"])
    assert all(switch["checked"] and switch["disabled"] for switch in result["atStart"] + result["loading"])
    assert [(switch["group"], switch["checked"], switch["disabled"]) for switch in result["loaded"]] == \
        [(group, group != "credit_cards", False) for group in GROUP_KEYS]
    for label in ("Alternative positions", "Lines of credit", "Vehicle loans &amp; leases", "Leases &amp; rentals",
                  "Floor plan", "Factoring", "Premium financing"):
        assert f">{label}</label>" in result["html"]


# ---------------------------------------------------------------- Task 8: saving a switch

TOGGLE = """
const toggle = (key, on) => {
  const box = fakeElement('switch'); box.checked = on; box.attributes['data-flag-setting'] = key; box.closest = () => box;
  els.flagSettingsList.dispatch('change', {target: box});
};
const posts = () => REQUESTS.filter((request) => request.method === 'POST')
  .map((request) => [request.url, JSON.parse(request.body)]);
"""


def _settings_page_with(job_id, payload):
    """A statement open, then the Settings page loaded with every flag on."""
    return (SWITCHES + TOGGLE + _load(job_id, payload)
            + _answer("/api/settings", {"json": {"settings": _settings()}})
            + "loadSettings(); await settle(); REQUESTS.length = 0; FETCHED.length = 0;\n")


@needs_node
def test_a_change_saves_its_key_alone_holds_the_group_and_refreshes_what_is_open():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"json": {"settings": _settings(flag_factoring=False)}}) + """
toggle('flag_factoring', false);
const saving = {switches: switches(), status: els.flagSettingsStatus.textContent};
await settle(); await settle();
console.log(JSON.stringify({saving, posts: posts(), fetched: FETCHED.slice(), saved: switches(),
  status: els.flagSettingsStatus.textContent, state: els.flagSettingsStatus.getAttribute('data-state'),
  nsfStatus: els.settingsStatus.textContent}));
""")
    saving = result["saving"]
    assert all(switch["disabled"] for switch in saving["switches"]) and saving["status"] == "Saving..."
    assert [switch["checked"] for switch in saving["switches"]] == [group != "factoring" for group in GROUP_KEYS]
    assert result["posts"] == [["/api/settings", {"flag_factoring": False}]]
    assert "/analysis/s" in result["fetched"]
    assert [(switch["checked"], switch["disabled"]) for switch in result["saved"]] == \
        [(group != "factoring", False) for group in GROUP_KEYS]
    # Worded to read right for every label, plural ("Mortgages") or not ("Factoring", "Floor plan").
    assert result["status"] == "Saved. Factoring: no longer flagged." and result["state"] is None
    assert result["nsfStatus"] == ""


@needs_node
def test_a_refused_save_puts_the_switch_back_and_says_why_on_its_own_line():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"status": 503, "json": {"error": "fabricated save failure"}})
                           + """
toggle('flag_bank_loans', false);
await settle(); await settle();
console.log(JSON.stringify({posts: posts(), fetched: FETCHED.slice(), saved: switches(),
  status: els.flagSettingsStatus.textContent, state: els.flagSettingsStatus.getAttribute('data-state'),
  nsfStatus: els.settingsStatus.textContent}));
""")
    assert result["posts"] == [["/api/settings", {"flag_bank_loans": False}]]
    assert not any(url.startswith("/analysis/") for url in result["fetched"])
    assert all(switch["checked"] and not switch["disabled"] for switch in result["saved"])
    assert result["status"] == "fabricated save failure" and result["state"] == "error"
    assert result["nsfStatus"] == ""


@needs_node
def test_a_second_change_while_one_is_saving_is_not_sent():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}}) + """
toggle('flag_mortgages', false);
toggle('flag_credit_cards', false);
await settle(); await settle();
console.log(JSON.stringify({posts: posts()}));
""")
    assert result["posts"] == [["/api/settings", {"flag_mortgages": False}]]


# ---------------------------------------------------------------- Task 9: unticking the group being filtered

def _unticked(group):
    """The statement as the server serves it once `group` is unticked (C6): its rows no longer shown as flagged, its
    positions gone."""
    ledger = [{**row, "classification": {**row["classification"], "flag_shown": False}}
              if row["classification"]["flagged_group"] == group else row for row in LEDGER]
    return _statement(positions=[entry for entry in POSITIONS if entry["group"] != group], ledger=ledger)


@needs_node
def test_unticking_the_group_the_ledger_is_filtered_to_shows_every_row_again():
    result = run_dashboard(ROWS + PAYEE_CLICK + _settings_page_with("s", _statement()) + """
clickPayee(els.flaggedTable, 'mortgages', 'FABRICATED MORTGAGE CO');
const before = {filter: transactionFilter, count: els.transactionCount.textContent};
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}})
        + _answer("/analysis/s", {"json": {"analysis": _unticked("mortgages"), "analysis_error": None}}) + """
toggle('flag_mortgages', false);
await settle(); await settle();
console.log(JSON.stringify({before, after: {filter: transactionFilter, entity: transactionEntityFilter,
  count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML)}}));
""")
    assert result["before"] == {"filter": "flagged:mortgages", "count": "2 FABRICATED MORTGAGE CO"}
    assert result["after"] == {"filter": "all", "entity": None, "count": "6 transactions",
                               "dates": ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17", "2031-03-20",
                                         "2031-03-24"]}


@needs_node
def test_unticking_another_group_keeps_the_filter():
    result = run_dashboard(ROWS + PAYEE_CLICK + _settings_page_with("s", _statement()) + """
clickPayee(els.flaggedTable, 'credit_cards', 'Credit cards');
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}})
        + _answer("/analysis/s", {"json": {"analysis": _unticked("mortgages"), "analysis_error": None}}) + """
toggle('flag_mortgages', false);
await settle(); await settle();
console.log(JSON.stringify({filter: transactionFilter, count: els.transactionCount.textContent}));
""")
    assert result == {"filter": "flagged:credit_cards", "count": "1 Credit cards"}
