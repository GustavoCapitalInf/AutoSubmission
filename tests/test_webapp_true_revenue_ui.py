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
