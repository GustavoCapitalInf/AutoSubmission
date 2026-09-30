"""True revenue spec §10 (S6): the dashboard's revenue cards and their N/A rules, the credit mix and the Held for Review
view, the ledger's tags, chips, filters and review controls, the Monthly Statements and the chart. The whole
webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated statements only, analysed
by the real analysis path; every amount is whole dollars."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import CELLS, _package, _serve
from tests.test_webapp_true_revenue import _payload, _untiered
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

METRIC_ROWS = r"""
const metricRows = (html) => [...html.matchAll(/<(button|div) class="metric-row([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => ({headline: m[2].includes("metric-headline"),
    label: (m[3].match(/<span class="metric-label">([^<]*)<\/span>/) || [])[1],
    value: (m[3].match(/<span class="metric-value[^"]*">([^<]*)<\/span>/) || [])[1],
    note: (m[3].match(/<span class="metric-note">([^<]*)<\/span>/) || [])[1] || ""}));
const cells = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
  .map((row) => [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((cell) => cell[1].replace(/<[^>]+>/g, "").trim()));
"""


def _served(payload):
    from webapp.app import _displayed
    return _displayed(payload, settings={})


def _open(job_id, payload):
    return _serve(**{job_id: payload}) + f"""
currentJobId = '{job_id}'; currentJobIds = ['{job_id}']; loadResults('{job_id}'); await settle();
"""


# ---------------------------------------------------------------- S6.1: cards, N/A, credit mix, Held for Review view

def _js_reasons():
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    block = source[source.index("const REVENUE_TIER_REASONS = Object.freeze({"):]
    block = block[:block.index("});")]
    return {code: (tier, label) for code, tier, label, _sentence in re.findall(
        r'^\s*([a-z_0-9]+): \["([a-z_]+)", "([^"]+)", "([^"]+)"\],$', block, re.M)}


def test_the_dashboard_reason_table_mirrors_the_analysis():
    from analysis.revenue import REVENUE_TIER_REASONS

    assert _js_reasons() == {code: tuple(entry) for code, entry in REVENUE_TIER_REASONS.items()}


@needs_node
def test_a_statement_shows_true_revenue_first_and_its_parts():
    result = run_dashboard(METRIC_ROWS + _open("s", _served(_payload())) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML), meta: els.creditsMeta.innerHTML,
  badge: [els.reviewCount.hidden, els.reviewCount.textContent], evidence: cells(els.revenueTable.innerHTML)}));
""")
    rows = result["rows"]
    labels = [row["label"] for row in rows]
    assert labels[:7] == ["True Revenue", "Verified Revenue", "Counted, Not Verified", "Held for Review", "Non-Revenue",
                          "Total Credits", "ACH Credits"]
    assert "Unverified Deposits" not in labels and "Revenue Upper Bound" not in labels
    figures = {row["label"]: row for row in rows}
    assert figures["True Revenue"]["headline"] and not figures["Verified Revenue"]["headline"]
    assert [figures[label]["value"] for label in ("True Revenue", "Verified Revenue", "Counted, Not Verified",
                                                  "Held for Review", "Non-Revenue")] == [
        "$1,000.00", "$700.00", "$300.00", "$900.00", "$100.00"]
    assert figures["Verified Revenue"]["note"].startswith("70.0% of true revenue · Revenue with proof")
    assert figures["True Revenue"]["note"] == "Posted credits minus known non-revenue and the deposits held for review"
    assert "True revenue" in result["meta"] and "$1,000.00" in result["meta"]
    assert result["badge"] == [False, "1"]  # the held credit, not every unverified deposit
    evidence = result["evidence"]
    assert [row[0] for row in evidence] == ["True Revenue", "Verified Revenue", "Counted, Not Verified",
                                            "Held for Review", "Payer or entry suggests financing", "Non-Revenue"]
    assert evidence[4][1:3] == ["1", "$900.00"]


@needs_node
def test_an_older_statement_reads_n_a_for_true_counted_and_held():
    older = {**_served(_untiered(_payload())), "analysis_rules_outdated": True}
    result = run_dashboard(METRIC_ROWS + _open("o", older) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML), mix: els.creditMixRows.innerHTML,
  bar: els.creditMixBar.getAttribute('aria-label'), badge: els.reviewCount.textContent}));
""")
    figures = {row["label"]: row for row in result["rows"]}
    assert [figures[label]["value"] for label in ("True Revenue", "Counted, Not Verified", "Held for Review")] == [
        "N/A"] * 3
    assert figures["True Revenue"]["note"] == "Re-analyze to compute true revenue"
    assert figures["Verified Revenue"]["value"] == "$700.00"  # the stored figure, under the outdated notice
    assert result["bar"] == "Credit mix unavailable"
    assert result["badge"] == "2"  # before 5.6 the badge counts the deposits left unverified


@needs_node
def test_a_statement_whose_credits_are_not_its_total_reads_n_a():
    payload = _served(_payload())
    payload["metrics"]["revenue_established"] = payload["metrics"]["verified_revenue_established"] = False
    result = run_dashboard(METRIC_ROWS + _open("n", payload) + """
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML),
  badge: [els.reviewCount.hidden, els.reviewCount.textContent]}));
""")
    figures = {row["label"]: row["value"] for row in result["rows"]}
    assert [figures[label] for label in ("True Revenue", "Verified Revenue", "Counted, Not Verified",
                                         "Held for Review")] == ["N/A"] * 4
    assert figures["Non-Revenue"] == "$100.00"
    # The held count is kept (revenue_review_items), but it is not an established figure: the badge says N/A, never
    # a count the page cannot stand behind.
    assert payload["metrics"]["revenue_review_items"] == 1
    assert result["badge"] == [False, "N/A"]


@needs_node
def test_a_package_with_an_older_member_names_it_and_reads_n_a(tmp_path, monkeypatch):
    package = _package({"new": _payload(), "old": _untiered(_payload(month=4))}, tmp_path, monkeypatch)
    package["analysis_rules_outdated"] = True
    result = run_dashboard(METRIC_ROWS + f"""
currentJobIds = ['new', 'old']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{grid: els.metricsGrid.innerHTML, rows: metricRows(els.metricsGrid.innerHTML),
  badge: [els.reviewCount.hidden, els.reviewCount.textContent]}}));
""")
    figures = {row["label"]: row["value"] for row in result["rows"]}
    assert [figures[label] for label in ("True Revenue", "Counted, Not Verified", "Held for Review")] == ["N/A"] * 3
    assert figures["Verified Revenue"] == "$1,400.00"
    assert "1 of 2 statements has no established revenue · Re-analyze to compute true revenue" in result["grid"]
    # The package's revenue_review_items counts only its established member's held credit: a partial count, so the
    # badge reads N/A with the Held figure.
    assert package["totals"]["revenue_review_items"] == 1
    assert result["badge"] == [False, "N/A"]


# ---------------------------------------------------------------- S6.2: tags, chips, filters, review controls

def _record(tier, *, reason=None, state=None, initial=None, status="not_required", signals=()):
    state = state or {"verified": "verified_revenue", "non_revenue": "non_revenue"}.get(tier, "unverified_deposit")
    record = {"classification": "other", "revenue_classification": state, "revenue_tier": tier,
              "revenue_tier_reason": reason, "revenue_initial_classification": initial or state,
              "revenue_review_status": status, "source_location": "transaction:1",
              "contributes_to_true_revenue": tier in ("verified", "counted_flagged"),
              "revenue_context_signals": list(signals)}
    if tier is None:
        for key in ("revenue_tier", "revenue_tier_reason", "contributes_to_true_revenue"):
            record.pop(key)
    return {"date": "2031-03-02", "description": "FABRICATED ROW", "amount": 500.0, "source_job": "j",
            "classification": record}


@needs_node
def test_each_tier_has_its_tag_and_a_middle_tier_names_its_reason():
    rows = [_record("verified"), _record("counted_flagged", reason="check_deposit"),
            _record("excluded_pending_review", reason="financing_named_payer"), _record("non_revenue"),
            _record(None, state="unverified_deposit")]
    # A decided row keeps its tier reason for the audit while its tier changes: it is tagged, filtered and reviewed by
    # its tier, never by the reason it kept. A lender's dealer funding (Q7) and a credit under the one-dollar floor
    # show what their records carry; the page never reads a tier off a match method.
    q7 = _record("verified")
    q7["classification"].update(revenue_match_method="auto_lender_dealer_funding",
                                revenue_canonical_entity="ALLY FINANCIAL")
    micro = _record("excluded_pending_review", reason="non_sale_purpose")
    micro["classification"]["revenue_match_method"] = "micro_deposit_floor"
    decided = [_record("verified", reason="financing_named_payer", initial="unverified_deposit", status="confirmed"),
               _record("non_revenue", reason="check_deposit", initial="unverified_deposit", status="rejected"),
               q7, micro]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const decided = {json.dumps(decided)};
const found = (filter) => filterTransactions(decided, filter).map((tx) => decided.indexOf(tx));
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
console.log(JSON.stringify({{tags: rows.map(transactionCategory), reasons: rows.map(revenueReviewReason),
  decided: {{tags: decided.map((tx) => transactionCategory(tx).label), reasons: decided.map(revenueReviewReason),
    controls: decided.map((tx) => actions(revenueReviewControls(tx))),
    filters: Object.fromEntries(["true_revenue", "verified_revenue", "counted_flagged", "non_revenue",
      "excluded_pending_review:financing_named_payer", "excluded_pending_review:non_sale_purpose"]
      .map((f) => [f, found(f)]))}}}}));
""")
    assert result["tags"] == [
        {"label": "Verified revenue", "glyph": "VER", "tone": "green"},
        {"label": "Counted: Check deposit", "glyph": "CNT", "tone": "teal"},
        {"label": "Held: Payer or entry suggests financing", "glyph": "?", "tone": "amber"},
        {"label": "Non-revenue", "glyph": "X", "tone": "neutral"},
        {"label": "Unverified deposit", "glyph": "?", "tone": "amber"},
    ]
    assert result["reasons"][1] == "Check deposit. A check deposit: the payer is not printed."
    assert result["reasons"][2] == ("Payer or entry suggests financing. The payer or the entry names funding, a loan or "
                                    "an advance.")
    assert result["reasons"][0] == result["reasons"][3] == ""
    assert result["reasons"][4] == "Unable to determine whether this deposit represents operating revenue."
    held_non_sale = "Not a sale: owner money, investment, grant, refund, claim or interest"
    assert result["decided"]["tags"] == ["Verified revenue", "Non-revenue", "Verified revenue", f"Held: {held_non_sale}"]
    assert result["decided"]["reasons"] == ["", "", "", f"{held_non_sale}. The entry names owner money, an investment, "
                                                       "a grant, a refund, a claim or interest."]
    assert result["decided"]["controls"] == [["reset"], ["reset"], ["reject"], ["confirm", "reject"]]
    assert result["decided"]["filters"] == {
        "true_revenue": [0, 2], "verified_revenue": [0, 2], "counted_flagged": [], "non_revenue": [1],
        "excluded_pending_review:financing_named_payer": [], "excluded_pending_review:non_sale_purpose": [3]}


@needs_node
def test_the_revenue_filters_find_their_rows():
    rows = [_record("verified"), _record("counted_flagged", reason="p2p"),
            _record("excluded_pending_review", reason="holder_name"),
            _record("excluded_pending_review", reason="wire_no_sender"), _record("non_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const found = (filter) => filterTransactions(rows, filter).map((tx) => rows.indexOf(tx));
console.log(JSON.stringify(Object.fromEntries(["true_revenue", "verified_revenue", "counted_flagged",
  "excluded_pending_review", "non_revenue", "excluded_pending_review:wire_no_sender"].map((f) => [f, found(f)]))));
""")
    assert result == {"true_revenue": [0, 1], "verified_revenue": [0], "counted_flagged": [1],
                      "excluded_pending_review": [2, 3], "non_revenue": [4],
                      "excluded_pending_review:wire_no_sender": [3]}


@needs_node
def test_the_review_controls_follow_the_server_rules():
    rows = [_record("excluded_pending_review", reason="holder_name"), _record("counted_flagged", reason="p2p"),
            _record("verified"), _record("verified", initial="unverified_deposit", status="confirmed"),
            _record("non_revenue", initial="verified_revenue", status="rejected"), _record("non_revenue"),
            _record(None, state="verified_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
console.log(JSON.stringify({{controls: rows.map((tx) => actions(revenueReviewControls(tx))),
  pickable: rows.map((tx) => pendingReviewTarget(tx) !== null)}}));
""")
    assert result["controls"] == [["confirm", "reject"], ["confirm", "reject"], ["reject"], ["reset"], ["reset"], [],
                                  []]
    # The multi-select offers the credits left unverified and not yet decided.
    assert result["pickable"] == [True, True, False, False, False, False, False]


@needs_node
def test_a_property_management_payout_carries_its_chip():
    row = _record("verified", signals=["recurring_source_3_credits", "property_management_collections"])
    result = run_dashboard(f"""
console.log(JSON.stringify({{chip: revenueSourceChip({json.dumps(row)}),
  none: revenueSourceChip({json.dumps(_record("verified"))})}}));
""")
    assert "Property-management collections" in result["chip"] and result["none"] == ""


@needs_node
def test_the_review_view_opens_on_the_held_credits():
    result = run_dashboard(_open("s", _served(_payload())) + """
navigate('review');
console.log(JSON.stringify({filter: transactionFilter}));
""")
    assert result["filter"] == "excluded_pending_review"


def test_the_page_carries_the_true_revenue_words():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert 'title="Deposits held for review"' in html
    assert "Deposits held for review, and counted deposits, can be confirmed or excluded from the Review column." in html
    assert "Analysed with older classification rules." in html
    for value, label in (("true_revenue", "True Revenue"), ("verified_revenue", "Verified"),
                         ("counted_flagged", "Counted"), ("excluded_pending_review", "Held for Review"),
                         ("non_revenue", "Non-Revenue")):
        assert f'data-transaction-filter="{value}">{label}</button>' in html
        assert f'data-modal-transaction-filter="{value}">{label}</button>' in html
    assert 'data-transaction-filter="unverified_deposit"' not in html


# ---------------------------------------------------------------- S6.3: Monthly Statements and the chart

CHART_PARTS = r"""
const chartParts = () => ({
  labels: [...els.monthlyChart.innerHTML.matchAll(/<span class="bar-value( bar-value-true| bar-value-verified)?">([^<]*)<\/span>/g)]
    .map((m) => [m[1] ? m[1].trim() : "bar-value", m[2]]),
  parts: [...els.monthlyChart.innerHTML.matchAll(/<div class="bar-part( bar-part-verified)?" style="height: ([0-9.]+)%">/g)]
    .map((m) => [m[1] ? "verified" : "true", m[2]]),
  legend: els.monthlyChart.innerHTML.match(/<span class="chart-legend">([\s\S]*?)<\/span>\s*<\/div>/)[1],
});
"""


@needs_node
def test_the_monthly_statements_show_true_revenue_and_its_verified_part(tmp_path, monkeypatch):
    package = _package({"mar": _payload()}, tmp_path, monkeypatch)
    result = run_dashboard(CELLS + CHART_PARTS + f"""
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
const both = {{...monthly(), chart: chartParts()}};
setMonthlyDepositsView('true');
console.log(JSON.stringify({{both, trueOnly: {{...monthly(), chart: chartParts()}}}}));
""")
    both, true_only = result["both"], result["trueOnly"]
    # 2,000 posted: 1,000 True (700 verified, 300 counted), 900 held and 100 non-revenue.
    assert both["rows"][0][2:7] == ["2,000", "4", "1,000", "2", "700"]
    assert true_only["head"][2:5] == ["Monthly Deposits ($)", "Deposits Per Month", "Verified ($)"]
    assert true_only["rows"][0][2:5] == ["1,000", "2", "700"]
    assert both["chart"]["labels"] == [["bar-value", "2,000"], ["bar-value-true", "1,000"],
                                       ["bar-value-verified", "700"]]
    assert both["chart"]["parts"] == [["true", "50.0"], ["verified", "35.0"]]
    assert all(word in both["chart"]["legend"] for word in ("Total deposits", "True revenue", "of which verified"))
    assert true_only["chart"]["parts"] == [["verified", "70.0"]]


@needs_node
def test_a_month_without_established_revenue_draws_no_true_or_verified_part(tmp_path, monkeypatch):
    package = _package({"old": _untiered(_payload())}, tmp_path, monkeypatch)
    result = run_dashboard(CELLS + CHART_PARTS + f"""
currentJobIds = ['old']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...monthly(), chart: chartParts()}}));
""")
    assert result["rows"][0][4:7] == ["N/A", "N/A", "700"]  # Verified stands on its own condition
    assert result["chart"]["parts"] == []
    assert result["chart"]["labels"][1:] == [["bar-value-true", "N/A"], ["bar-value-verified", "N/A"]]


def test_the_settings_say_what_true_revenue_is():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    text = " ".join(html.split())
    assert ("<strong>True revenue:</strong> every posted credit except known non-revenue (own-account transfers, "
            "funding, refunds) and the deposits held for review. The verified part, with positive proof, is shown "
            "beside it.") in text
    assert '<script src="/static/app.js?v=true-revenue-1"></script>' in html
