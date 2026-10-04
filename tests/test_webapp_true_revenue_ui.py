"""True revenue spec §10 (S6): the dashboard's revenue cards and their N/A rules, the credit mix and the Held for Review
view, the ledger's tags, chips, filters and review controls, the Monthly Statements and the chart. The whole
webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated statements only, analysed
by the real analysis path; every amount is whole dollars."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import CELLS, _package, _serve
from tests.test_webapp_true_revenue import _payload, _summary_only, _untiered
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
    # Audit B11 (I53): Counted is broken down by reason, as Held is.
    assert [row[0] for row in evidence] == ["True Revenue", "Verified Revenue", "Counted, Not Verified",
                                            "Check deposit", "Held for Review", "Payer or entry suggests financing",
                                            "Non-Revenue"]
    assert evidence[3][1:3] == ["1", "$300.00"]
    assert evidence[5][1:3] == ["1", "$900.00"]


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
    # The server marks the member analysed with older rules (§12); nothing is set by hand.
    assert [doc["analysis_rules_outdated"] for doc in package["documents"]] == [False, True]
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


@needs_node
def test_a_package_note_offers_re_analysis_only_to_its_older_members(tmp_path, monkeypatch):
    # §12: re-analysis computes an older member's true revenue. A summary-only member's revenue stays not established
    # after it, so the note names no remedy for that member.
    packages = {
        "summary": _package({"new": _payload(), "partial": _summary_only(4)}, tmp_path, monkeypatch),
        "both": _package({"new": _payload(), "old": _untiered(_payload(month=4)), "partial": _summary_only(5)},
                         tmp_path, monkeypatch),
    }
    result = run_dashboard(f"""
const packages = {json.dumps(packages)};
const out = {{}};
for (const [name, pkg] of Object.entries(packages)) {{
  currentJobIds = pkg.documents.map((doc) => doc.id); renderPackageAnalysis(pkg);
  out[name] = (els.metricsGrid.innerHTML.match(/\\d+ statements? · \\d+ months?[^<]*/) || [""])[0];
}}
console.log(JSON.stringify(out));
""")
    # Audit B11 (I07, I33): the section names its statements and the calendar months they cover.
    assert result["summary"] == "2 statements · 2 months · 1 of 2 statements has no established revenue"
    assert result["both"] == ("3 statements · 3 months · 2 of 3 statements have no established revenue · Re-analyze 1 "
                              "of them to compute true revenue")


@needs_node
def test_a_mixed_currency_package_shows_n_a_money_and_keeps_its_counts(tmp_path, monkeypatch):
    # CURRENCY DOCTRINE §F refuses a mixed package's money and keeps its counts (tests/test_package_currency.py), and
    # the counts of an established package still stand. A member not established still reads N/A everywhere (§10.4).
    cad = _payload(month=4)
    cad["statement"]["currency"] = "CAD"
    mixed = _package({"usd": _payload(), "cad": cad}, tmp_path, monkeypatch)
    older = _package({"new": _payload(), "old": _untiered(_payload(month=4))}, tmp_path, monkeypatch)
    assert mixed["totals"]["cross_currency_totals_refused"] is True
    result = run_dashboard(METRIC_ROWS + f"""
const view = () => ({{cards: metricRows(els.metricsGrid.innerHTML).slice(0, 4).map((row) => row.value),
  evidence: cells(els.revenueTable.innerHTML).map((row) => row.slice(0, 3)),
  mix: [...els.creditMixRows.innerHTML.matchAll(/<span class="mix-count">([^<]*)<\\/span>/g)].map((m) => m[1]),
  badge: [els.reviewCount.hidden, els.reviewCount.textContent]}});
currentJobIds = ['usd', 'cad']; renderPackageAnalysis({json.dumps(mixed)}); const refused = view();
currentJobIds = ['new', 'old']; renderPackageAnalysis({json.dumps(older)});
console.log(JSON.stringify({{refused, older: view()}}));
""")
    refused, older_view = result["refused"], result["older"]
    assert refused["cards"] == ["N/A"] * 4
    assert refused["evidence"] == [["True Revenue", "4", "N/A"], ["Verified Revenue", "2", "N/A"],
                                   ["Counted, Not Verified", "2", "N/A"], ["Check deposit", "2", "N/A"],
                                   ["Held for Review", "2", "N/A"],
                                   ["Payer or entry suggests financing", "2", "N/A"], ["Non-Revenue", "2", "N/A"]]
    assert refused["mix"] == ["2", "2", "2", "2"]
    assert refused["badge"] == [False, "2"]
    assert older_view["cards"] == ["N/A", "$1,400.00", "N/A", "N/A"]
    assert older_view["evidence"] == [["True Revenue", "N/A", "N/A"], ["Verified Revenue", "2", "$1,400.00"],
                                      ["Counted, Not Verified", "N/A", "N/A"], ["Held for Review", "N/A", "N/A"],
                                      ["Non-Revenue", "2", "$200.00"]]
    assert older_view["mix"] == ["2", "N/A", "N/A", "2"]
    assert older_view["badge"] == [False, "N/A"]


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
def test_a_credit_marked_unread_shows_the_payer_blocks_the_reader_could_not_attribute():
    """Audit round 2, R2-B07 (R07): the review card prints a marked credit's unread payer blocks
    (`unread_payer_text`), so a reviewer can release a customer's row that a lender's block in the same run held."""
    held = _record("excluded_pending_review", reason="unread_run_names_financing")
    held["unread_payer_text"] = "CONTOSO INC. PAYABLES 1 NORTHWIND CCD KAPITUS LLC FUNDING 2 NORTHWIND CCD"
    counted = _record("counted_flagged", reason="payer_text_not_read")
    counted["unread_payer_text"] = "FABRIKAM INC. PAYABLES 3 NORTHWIND CCD SAMPLE INC 4 NORTHWIND CCD"
    plain = _record("counted_flagged", reason="payer_text_not_read")
    result = run_dashboard(f"""
const rows = {json.dumps([held, counted, plain])};
console.log(JSON.stringify({{reasons: rows.map(revenueReviewReason),
  tags: rows.map((tx) => transactionCategory(tx).label)}}));
""")
    label = "A lender is printed among this credit's unread payer blocks"
    assert result["tags"] == [f"Held: {label}", "Counted: Payer text not read", "Counted: Payer text not read"]
    unread_sentence = ("Payer text not read. The statement prints a payer for this row that the reader could not read: "
                       "counted without proof of the sale.")
    assert result["reasons"] == [
        f"{label}. The statement prints a lender's or a lending bank's block among payer blocks the reader could not "
        "attribute to one row: held until you confirm whose credit this is. Unread payer blocks: "
        "CONTOSO INC. PAYABLES 1 NORTHWIND CCD KAPITUS LLC FUNDING 2 NORTHWIND CCD",
        f"{unread_sentence} Unread payer blocks: FABRIKAM INC. PAYABLES 3 NORTHWIND CCD SAMPLE INC 4 NORTHWIND CCD",
        unread_sentence,
    ]


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


REVIEW_VIEW = r"""
navigate('review');
const reviewRows = [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1]);
console.log(JSON.stringify({filter: transactionFilter, count: els.transactionCount.textContent,
  badge: els.reviewCount.textContent,
  rows: reviewRows.map((row) => [(row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || "",
    [...row.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1])]),
  text: els.transactionTable.innerHTML.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()}));
"""


@needs_node
def test_an_older_analysis_opens_its_review_on_its_unverified_deposits():
    # T10, §10.7: an analysis saved before 5.6 carries no tier and is reviewed under the rules it was analysed with,
    # so its review view lists the deposits it left unverified (what its badge counts), each with Confirm and Mark.
    older = run_dashboard(_open("o", _served(_untiered(_payload()))) + REVIEW_VIEW)
    assert older["filter"] == "unverified_deposit"
    assert older["count"] == "2 unverified deposits" and older["badge"] == "2"
    assert older["rows"] == [["MOBILE DEPOSIT", ["confirm", "reject"]],
                             ["FABRIKAM FUNDING LLC DES:PAYMENT ID:1", ["confirm", "reject"]]]
    # With none left, the empty view names the way to true revenue.
    settled = _served(_untiered(_payload([(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0),
                                          (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0)])))
    none_left = run_dashboard(_open("s", settled) + REVIEW_VIEW)
    assert none_left["filter"] == "unverified_deposit" and none_left["count"] == "0 unverified deposits"
    assert "Analysed with older classification rules: Re-analyze to compute true revenue." in none_left["text"]
    # A 5.6 analysis is unchanged: its held credits.
    current = run_dashboard(_open("c", _served(_payload())) + REVIEW_VIEW)
    assert current["filter"] == "excluded_pending_review" and current["count"] == "1 held for review"
    assert current["rows"] == [["FABRIKAM FUNDING LLC DES:PAYMENT ID:1", ["confirm", "reject"]]]


@needs_node
def test_the_ledger_header_names_a_revenue_filter_in_the_page_words():
    # §10.6: the tier labels of the credit mix and the held reasons' labels, never a filter's value.
    result = run_dashboard(_open("s", _served(_payload())) + r"""
const out = {};
for (const filter of ['true_revenue', 'verified_revenue', 'counted_flagged', 'excluded_pending_review',
                      'excluded_pending_review:financing_named_payer', 'non_revenue', 'all']) {
  showMainRevenueEvidence(filter); out[filter] = els.transactionCount.textContent;
}
console.log(JSON.stringify(out));
""")
    assert result == {"true_revenue": "2 in true revenue", "verified_revenue": "1 verified revenue",
                      "counted_flagged": "1 counted, not verified", "excluded_pending_review": "1 held for review",
                      "excluded_pending_review:financing_named_payer": "1 held: payer or entry suggests financing",
                      "non_revenue": "1 non-revenue", "all": "5 transactions"}


def test_the_package_evidence_dots_follow_the_tiers():
    html = " ".join((ROOT / "webapp/templates/index.html").read_text(encoding="utf-8").split())
    for selector, token in (('="true_revenue"', "accent"), ('="verified_revenue"', "accent"),
                            ('="counted_flagged"', "teal"), ('="excluded_pending_review"', "amber"),
                            ('^="excluded_pending_review:"', "amber")):
        assert (f".is-package .revenue-panel [data-revenue-filter{selector}]::before {{ background: var(--{token}); }}"
                in html)
    assert 'data-revenue-filter="unverified_deposit"' not in html


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


@needs_node
def test_the_tallest_bar_its_figures_and_the_baseline_fit_the_plot_box_in_every_view(tmp_path, monkeypatch):
    # A4: the Verified figure is a third figure in the Both view and a second in the True view, so the tallest bar is
    # the plot box less its stacked figures (each a 16px line and an 8px gap, every one after the first pulled up
    # 6px): 129px, 147px and 165px, which sit exactly on the baseline.
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert re.search(r"\.bar-chart \{[^}]*height: 190px;[^}]*border-bottom: 1px", html)
    assert re.search(r"\.bar-col \{[^}]*gap: 8px;", html)
    assert re.search(r"\.bar-value \{[^}]*line-height: 16px;", html)
    assert re.search(r"\.bar-value-true \{ margin-top: -6px;", html)
    assert re.search(r"\.bar-value-verified \{ margin-top: -6px;", html)
    package = _package({"mar": _payload(), "apr": _payload(month=4)}, tmp_path, monkeypatch)
    result = run_dashboard(CELLS + f"""
const bars = () => [...els.monthlyChart.innerHTML.matchAll(/<div class="bar[^"]*" style="height: ([0-9.]+)px">/g)]
  .map((m) => Number(m[1]));
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const both = bars();
setMonthlyDepositsView('true');
const trueOnly = bars();
setMonthlyDepositsView('total');
console.log(JSON.stringify({{both, trueOnly, total: bars()}}));
""")
    assert max(result["both"]) == 129.0 and max(result["trueOnly"]) == 147.0 and max(result["total"]) == 165.0
    for figures, tallest in ((3, 129.0), (2, 147.0), (1, 165.0)):
        assert tallest + figures * 16 + figures * 8 - (figures - 1) * 6 == 189


def test_the_settings_say_what_true_revenue_is():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    text = " ".join(html.split())
    assert ("<strong>True revenue:</strong> every posted credit except known non-revenue (own-account transfers, "
            "funding, refunds) and the deposits held for review. The verified part, with positive proof, is shown "
            "beside it.") in text
    assert '<script src="/static/app.js?v=true-revenue-3"></script>' in html


# ---------------------------------------------------------------- Audit B11: the package page, the copy and the exports

HERO = r"""
const hero = () => ({chips: [...els.heroChips.innerHTML.matchAll(/<span class="hero-chip[^"]*">([^<]*)<\/span>/g)]
    .map((m) => m[1]),
  status: Object.fromEntries([...els.statusList.innerHTML.matchAll(
    /<span class="kv-key">([^<]*)<\/span>\s*<span class="kv-value"[^>]*>([^<]*)<\/span>/g)].map((m) => [m[1], m[2]])),
  label: els.creditsLabel.textContent, meta: els.creditsMeta.innerHTML.replace(/<[^>]+>/g, "")});
"""


@needs_node
def test_the_revenue_chip_reads_balanced_only_where_the_statement_reconciles_and_revenue_is_established():
    """I31: the four tiers summing to the posted credits held on every tiered statement, so the chip said "Balanced"
    beside a short capture or an unreconciled ledger."""
    reconciled = _served(_payload())
    assert reconciled["reconciliation"]["ok"] is True and reconciled["metrics"]["revenue_established"] is True
    unreconciled = _served(_payload())
    unreconciled["reconciliation"]["ok"] = False
    short = _served(_summary_only(3))
    assert short["metrics"]["revenue_tiers_sum_to_posted"] is True  # the identity holds; the chip no longer reads it
    out = {}
    for name, payload in (("reconciled", reconciled), ("unreconciled", unreconciled), ("short", short)):
        out[name] = run_dashboard(METRIC_ROWS + HERO + _open(name, payload) + """
console.log(JSON.stringify({...hero(), rows: metricRows(els.metricsGrid.innerHTML)}));
""")
    assert "Revenue · Balanced" in out["reconciled"]["chips"]
    assert out["reconciled"]["status"]["Revenue reconciliation"] == "Balanced"
    for name in ("unreconciled", "short"):
        assert "Revenue · Review required" in out[name]["chips"], name
        assert out[name]["status"]["Revenue reconciliation"] == "Review required", name
    # I51: where revenue is not established, Non-Revenue stays a figure and says it covers the captured rows only.
    figures = {row["label"]: row for row in out["short"]["rows"]}
    assert figures["Non-Revenue"]["value"] == "$100.00"
    assert figures["Non-Revenue"]["note"].startswith("Captured rows only")
    assert {row["label"]: row for row in out["reconciled"]["rows"]}["Non-Revenue"]["note"] == (
        "Own-account transfers, funding, refunds and other known non-revenue")


@needs_node
def test_the_package_hero_prints_statements_months_and_true_per_month(tmp_path, monkeypatch):
    """I07, I33: two accounts uploaded as two files for March are 2 statements and 1 month; the gross monthly figure is
    named gross, and True per month sits beside the package's True."""
    from tests.test_webapp_true_revenue import _SECOND_ACCOUNT_ROWS, _account_payload

    package = _package({"chk": _payload(), "sav": _account_payload("000000002020", _SECOND_ACCOUNT_ROWS)},
                       tmp_path, monkeypatch)
    result = run_dashboard(METRIC_ROWS + HERO + f"""
currentJobIds = ['chk', 'sav']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...hero(), rows: metricRows(els.metricsGrid.innerHTML),
  sub: (els.metricsGrid.innerHTML.match(/\\d+ statements? · \\d+ months?[^<]*/) || [""])[0]}}));
""")
    assert result["label"] == "Total credits · 2 statements · 1 month"
    # Gross: the two accounts' posted credits, held and non-revenue included (2,000 + 2,500).
    assert result["meta"] == ("Avg monthly gross credits $4,500.00 · True revenue $3,500.00 · True per month "
                              "$3,500.00")
    assert result["sub"] == "2 statements · 1 month"
    figures = {row["label"]: row for row in result["rows"]}
    assert figures["True Revenue Per Month"]["value"] == "$3,500.00"
    assert figures["Verified Revenue Per Month"]["value"] == "$2,700.00"
    assert figures["Avg Monthly Gross Credits"]["note"] == "Gross posted credits per calendar month (not True revenue)"
    assert "Avg Monthly Credits" not in figures


@needs_node
def test_the_copy_names_every_counted_kind_and_the_withholding_basis():
    """I53, I34: the Counted note names every kind of counted credit and says the missing proof is of the sale; the
    Verified note claims confirmed platform payouts only; the withholding placeholders name eligible deposits, gross
    deposits less lender funding."""
    result = run_dashboard(METRIC_ROWS + """
setInitialState();
console.log(JSON.stringify({copy: REVENUE_METRIC_COPY, rows: metricRows(els.metricsGrid.innerHTML),
  payout: REVENUE_TIER_REASONS.payout_credit_entity,
  legacy: activeDenominatorNote({withholding_denominator_mode: 'legacy_eligible_deposits',
    eligible_deposit_definition: 'effective total deposits minus recognized lender funding credits'}),
  verified: activeDenominatorNote({withholding_denominator_mode: 'verified_revenue',
    eligible_deposit_definition: 'verified classified revenue'})}));
""")
    copy = result["copy"]
    assert copy["countedFlagged"] == (
        "Counted in true revenue without proof of the sale: cash, checks, person-to-person, wires, one-off, "
        "unlabelled and numbered-company payers, factoring and platform payouts")
    assert copy["verifiedRevenue"] == ("Revenue with proof: card settlements, confirmed platform payouts, repeat or "
                                       "institutional payers, invoices, and deposits you confirmed")
    assert result["payout"][1] == "BNPL or marketplace settlement (payer also lends)"
    assert result["legacy"] == "Gross deposits less lender funding (not True revenue)"
    assert result["verified"] == "verified classified revenue"
    figures = {row["label"]: row["note"] for row in result["rows"]}
    assert figures.get("Confirmed Withholding", "Confirmed lender debits as a share of eligible deposits") == (
        "Confirmed lender debits as a share of eligible deposits")
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert '"Confirmed lender debits as a share of eligible deposits"' in source
    assert "Confirmed lender debits as a share of revenue" not in source


@needs_node
def test_the_credit_mix_share_is_of_posted_credits_and_counted_has_its_reasons():
    result = run_dashboard(_open("s", _served(_payload())) + """
showMainRevenueEvidence('counted_flagged:check_deposit');
console.log(JSON.stringify({bar: els.creditMixBar.getAttribute('aria-label'), mix: els.creditMixRows.innerHTML,
  evidence: els.revenueTable.innerHTML, header: els.transactionCount.textContent}));
""")
    assert result["bar"].startswith("Credit mix, as a share of posted credits: ")
    assert '<p class="mix-caption">Shares of posted credits</p>' in result["mix"]
    assert 'title="35.0% of posted credits"' in result["mix"]
    assert 'data-revenue-filter="counted_flagged:check_deposit"' in result["evidence"]
    assert result["header"] == "1 counted: check deposit"


@needs_node
def test_the_true_card_names_an_unscreened_holder_and_unread_payer_text(tmp_path, monkeypatch):
    payload = _served(_payload())
    payload["metrics"].update(holder_unscreened=True, payer_text_unread=True, payer_text_unread_count=3)
    statement = run_dashboard(METRIC_ROWS + _open("s", payload) + """
console.log(JSON.stringify(metricRows(els.metricsGrid.innerHTML)));
""")
    note = {row["label"]: row["note"] for row in statement}["True Revenue"].replace("&#39;", "'")
    assert note == ("Posted credits minus known non-revenue and the deposits held for review · No holder name read: the "
                    "holder's own deposits are not screened · 3 credits' payer text not read")
    unscreened = _payload(month=4)
    unscreened["metrics"]["holder_unscreened"] = True
    package = _package({"mar": _payload(), "apr": unscreened}, tmp_path, monkeypatch)
    rows = run_dashboard(METRIC_ROWS + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify(metricRows(els.metricsGrid.innerHTML)));
""")
    assert {row["label"]: row["note"] for row in rows}["True Revenue"].endswith("1 statement with no holder name read")


@needs_node
def test_a_mixed_currency_chart_scales_and_peaks_within_each_currency():
    """I54: CAD 100,000 and USD 80,000 each fill the tallest bar of their own currency, and every bar names its unit,
    USD included; CAD beside a member that declared none is refused, and scaled apart too."""
    def doc(job, currency, credits):
        row = {"id": job, "filename": f"{job}.pdf", "status": "done", "period_start": "2031-03-01",
               "period_end": "2031-03-28", "credits": credits, "deposit_count": 1, "revenue_established": False,
               "verified_revenue_established": False, "average_daily_balance": None, "nsf_count": 0}
        if currency is not False:
            row["currency"] = currency
        return row

    def package(docs, currencies, refused):
        return {"documents": docs, "totals": {"cross_currency_totals_refused": refused},
                "currency": {"currencies": currencies, "cross_currency_totals_refused": refused}}

    mixed = package([doc("cad", "CAD", 100000.0), doc("usd", "USD", 80000.0)], ["CAD", "USD"], True)
    undeclared = package([doc("cad", "CAD", 100000.0), doc("raw", None, 80000.0)], ["CAD"], True)
    single = package([doc("a", "USD", 100000.0), doc("b", "USD", 80000.0)], ["USD"], False)
    result = run_dashboard(f"""
setMonthlyDepositsView('total');
const view = (pkg) => {{ renderMonthlyStatements(pkg); const html = els.monthlyChart.innerHTML; return {{
  heights: [...html.matchAll(/<div class="bar([^"]*)" style="height: ([0-9.]+)px">/g)].map((m) => [m[1].trim(), Number(m[2])]),
  labels: [...html.matchAll(/<span class="bar-value">([^<]*)<\\/span>/g)].map((m) => m[1])}}; }};
console.log(JSON.stringify({{mixed: view({json.dumps(mixed)}), undeclared: view({json.dumps(undeclared)}),
  single: view({json.dumps(single)})}}));
""")
    tallest = 165.0  # the Total view's tallest bar (test_the_tallest_bar_its_figures_and_the_baseline_fit_the_plot_box…)
    assert result["mixed"]["heights"] == [["peak", tallest], ["peak", tallest]]
    assert result["mixed"]["labels"] == ["100,000 CAD", "80,000 USD"]
    assert result["undeclared"]["heights"] == [["peak", tallest], ["peak", tallest]]
    assert result["undeclared"]["labels"] == ["100,000 CAD", "80,000"]
    # One currency: one scale, one peak, no unit (the table's "($)" convention).
    assert result["single"]["heights"] == [["peak", tallest], ["", tallest * 0.8]]
    assert result["single"]["labels"] == ["100,000", "80,000"]


@needs_node
def test_a_repeated_statement_is_named_once_and_left_out_of_the_months(tmp_path, monkeypatch):
    """I06: the server leaves a repeat out of every figure; the page says which, and the Monthly Statements, the
    chart, the title and the counts never show it as a month."""
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    package = _package_analysis([
        Job(id="mar", filename="mar.pdf", status="done", analysis=_payload(), content_sha256="h1"),
        Job(id="copy", filename="mar-copy.pdf", status="done", analysis=_payload(), content_sha256="h1"),
        Job(id="redl", filename="mar-download.pdf", status="done", analysis=_payload(), content_sha256="h2"),
        Job(id="apr", filename="apr.pdf", status="done", analysis=_payload(month=4), content_sha256="h3"),
    ])
    result = run_dashboard(CELLS + HERO + f"""
currentJobIds = ['mar', 'copy', 'redl', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...monthly(), ...hero(), notice: [els.duplicateNotice.hidden,
  els.duplicateNoticeText.innerHTML.replace(/<[^>]+>/g, "")], title: els.resultsTitle.textContent,
  kicker: els.heroKicker.innerHTML.replace(/<[^>]+>/g, "")}}));
""")
    assert result["notice"] == [False, (
        "2 repeated statements left out of every figure. mar-copy.pdf repeats mar.pdf (the same file); "
        "mar-download.pdf repeats mar.pdf (the same statement, downloaded again). The package needs review.")]
    assert [row[0] for row in result["rows"]] == ["March", "April"]
    assert result["count"] == "2 statements"
    assert result["label"] == "Total credits · 2 statements · 2 months"
    assert result["status"]["Statements completed"] == "2 / 2"
    assert result["kicker"].startswith("Package · 2 statements")
    clean = run_dashboard(f"""
renderPackageAnalysis({json.dumps(_package({"mar": _payload()}, tmp_path, monkeypatch))});
console.log(JSON.stringify(els.duplicateNotice.hidden));
""")
    assert clean is True


#: Audit round 2, R2-B14 (R49): the upload queue as it reads a batch: each entry as uploadFiles keeps it, after the
#: /upload reply (`jobId`, `duplicateOf` and `contentSha256` from it), and the queue's meta line and row details.
QUEUE = r"""
const queue = (entries) => { queueEntries = entries; renderQueue(); return {meta: els.queueMeta.textContent,
  details: [...els.queueList.innerHTML.matchAll(/<span class="queue-detail">([^<]*)<\/span>/g)].map((m) => m[1]),
  repeatOf: queueEntries.map((entry) => (queueRepeatOf(entry) || {}).jobId || null)}; };
"""


def _entry(name, job_id, sha, duplicate_of=None):
    return {"name": name, "size": 1000, "jobId": job_id, "status": "queued", "stage": None, "pageCount": 2,
            "duplicateOf": duplicate_of, "contentSha256": sha}


def _queue(*batches):
    return run_dashboard(QUEUE + "console.log(JSON.stringify([" + ", ".join(
        f"queue({json.dumps(batch)})" for batch in batches) + "]));")


@needs_node
def test_the_upload_queue_names_a_file_repeated_in_its_batch():
    """R49: the server's `duplicate_of` names the EARLIEST job holding the bytes anywhere in the store, so a file uploaded
    in an earlier batch and twice in this one points both entries outside the batch. The queue matches its own entries
    on the content hash the /upload reply carries."""
    shapes = _queue(
        # (a) both copies point at a job of an earlier batch ("old"), as the store answers.
        [_entry("contoso-mar.pdf", "a", "H1", "old"), _entry("contoso-mar-copy.pdf", "b", "H1", "old")],
        # (b) fresh bytes: the second copy points at the first.
        [_entry("fabrikam-apr.pdf", "c", "H2"), _entry("fabrikam-apr.pdf", "d", "H2", "c")],
        # (c) one file uploaded before: no repeat of this batch.
        [_entry("northwind-may.pdf", "e", "H3", "old")],
        # (d) three copies: both later copies name the first.
        [_entry("sample-jun.pdf", "f", "H4", "old"), _entry("sample-jun.pdf", "g", "H4", "old"),
         _entry("sample-jun.pdf", "h", "H4", "old")],
        # (e) two different files.
        [_entry("contoso-jul.pdf", "i", "H5"), _entry("contoso-aug.pdf", "j", "H6")],
    )
    a, b, c, d, e = shapes
    assert a["meta"] == "2 files · 4 pages · 1 repeated file, counted once"
    assert not a["details"][0].startswith("Same file as")
    assert a["details"][1].startswith("Same file as contoso-mar.pdf: left out of the package figures")
    assert b["meta"] == "2 files · 4 pages · 1 repeated file, counted once"
    assert b["details"][1] == "Same file as fabrikam-apr.pdf: left out of the package figures · Waiting · 2 pages · 1.0 KB"
    assert not b["details"][0].startswith("Same file as")
    assert c["meta"] == "1 file · 2 pages" and not c["details"][0].startswith("Same file as")
    assert d["meta"] == "3 files · 6 pages · 2 repeated files, counted once"
    assert d["repeatOf"] == [None, "f", "f"]
    assert [detail.startswith("Same file as sample-jun.pdf: left out") for detail in d["details"]] == [False, True, True]
    assert e["meta"] == "2 files · 4 pages" and e["repeatOf"] == [None, None]


@needs_node
def test_the_upload_queue_matches_no_entry_before_the_upload_reply():
    """An entry still uploading (no job id) or a reply that carries no hash names no repeat."""
    uploading = [{**_entry("contoso-mar.pdf", None, "H1"), "status": "uploading"},
                 {**_entry("contoso-mar.pdf", None, "H1"), "status": "uploading"}]
    no_hash = [_entry("contoso-mar.pdf", "a", None), _entry("contoso-mar.pdf", "b", None, "a")]
    first, second = _queue(uploading, no_hash)
    assert first["repeatOf"] == [None, None] and "repeated" not in first["meta"]
    assert second["repeatOf"] == [None, None] and "repeated" not in second["meta"]


@needs_node
def test_a_file_uploaded_before_and_twice_in_a_new_batch_reads_as_a_repeat(tmp_path, monkeypatch):
    """R49 end to end: the real /upload route on a scratch store, then its reply fed to uploadFiles."""
    import io
    import uuid

    import webapp.app as webapp_app
    from webapp.jobs import JobStore
    from webapp.storage import Storage

    monkeypatch.setattr(webapp_app, "store", JobStore(Storage(tmp_path)))
    monkeypatch.setattr(webapp_app, "_enqueue_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(webapp_app, "pdf_page_count", lambda pdf_bytes: 2)
    client = webapp_app.app.test_client()

    def post(batch):
        response = client.post("/upload", data={"files": [(io.BytesIO(raw), name) for name, raw in batch]},
                               content_type="multipart/form-data")
        assert response.status_code == 200
        return response.get_json()["jobs"]

    content = b"%PDF-fake-" + uuid.uuid4().hex.encode()
    earlier = post([("contoso-mar.pdf", content)])
    batch = post([("contoso-mar.pdf", content), ("contoso-mar-copy.pdf", content)])
    assert [job["duplicate_of"] for job in batch] == [earlier[0]["id"], earlier[0]["id"]]
    assert batch[0]["content_sha256"] == batch[1]["content_sha256"] == earlier[0]["content_sha256"]
    names = json.dumps([job["filename"] for job in batch])
    result = run_dashboard(f"""
FAKE_RESPONSES["/upload"] = {{status: 200, json: {{jobs: {json.dumps(batch)}}}}};
FAKE_RESPONSES["/status/"] = {{status: 200, json: {{status: "queued", stage: "queued", page_count: 2}}}};
uploadFiles({names}.map((name) => new File([new Uint8Array(1000)], name, {{type: "application/pdf"}})));
await settle(); await settle(); await settle();
const out = {{meta: els.queueMeta.textContent,
  details: [...els.queueList.innerHTML.matchAll(/<span class="queue-detail">([^<]*)<\\/span>/g)].map((m) => m[1])}};
process.stdout.write(JSON.stringify(out) + "\\n", () => process.exit(0));
""")
    assert result["meta"] == "2 files · 4 pages · 1 repeated file, counted once"
    assert not result["details"][0].startswith("Same file as")
    assert result["details"][1].startswith("Same file as contoso-mar.pdf: left out of the package figures")


@needs_node
def test_the_queue_names_the_copy_the_package_left_out(tmp_path, monkeypatch):
    """R16: once the batch's package arrives, the queue says 'left out of the package figures' only of the row the
    package marks `is_duplicate`: a failed first copy, not the completed copy kept in its place."""
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    package = _package_analysis([
        Job(id="f", filename="contoso-mar.pdf", status="error", error="fabricated failure", content_sha256="H1"),
        Job(id="a", filename="contoso-mar-copy.pdf", status="done", analysis=_payload(), content_sha256="H1"),
    ])
    entries = [{**_entry("contoso-mar.pdf", "f", "H1"), "status": "error"},
               {**_entry("contoso-mar-copy.pdf", "a", "H1", "f"), "status": "done"}]
    result = run_dashboard(QUEUE + f"""
const before = queue({json.dumps(entries)});
FAKE_RESPONSES["/package_analysis"] = {{status: 200, json: {json.dumps(package)}}};
currentJobIds = ["f", "a"]; loadPackage(["f", "a"], {{reveal: false, announce: false}}); await settle();
const after = {{meta: els.queueMeta.textContent,
  details: [...els.queueList.innerHTML.matchAll(/<span class="queue-detail">([^<]*)<\\/span>/g)].map((m) => m[1])}};
console.log(JSON.stringify({{before, after, notice: els.duplicateNoticeText.innerHTML.replace(/<[^>]+>/g, "")}}));
""")
    assert result["before"]["details"][1].startswith("Same file as contoso-mar.pdf: left out of the package figures")
    assert result["after"]["meta"] == "2 files · 4 pages · 1 repeated file, counted once"
    assert result["after"]["details"][0].startswith("Same file as contoso-mar-copy.pdf: left out of the package figures")
    assert not result["after"]["details"][1].startswith("Same file as")
    assert result["notice"] == ("1 repeated statement left out of every figure. contoso-mar.pdf left out: "
                                "contoso-mar-copy.pdf is the same file and has a completed analysis. "
                                "The package needs review.")


@needs_node
def test_the_notice_says_why_the_kept_copy_was_kept(tmp_path, monkeypatch):
    """R16: a repeat left out in favour of a later copy names that copy and why: its completed analysis, its current
    rules or its review decisions; copies alike keep the 'repeats' sentence."""
    from tests.test_webapp_app import _decided
    from tests.test_webapp_true_revenue import _untiered
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)

    def notice(jobs):
        return run_dashboard(f"""
renderPackageAnalysis({json.dumps(_package_analysis(jobs))});
console.log(JSON.stringify(els.duplicateNoticeText.innerHTML.replace(/<[^>]+>/g, "")));
""")

    def job(job_id, analysis, sha="H1"):
        return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=analysis, content_sha256=sha)

    assert notice([job("old", _untiered(_payload())), job("new", _payload(), "H2")]) == (
        "1 repeated statement left out of every figure. old.pdf left out: new.pdf is the same statement and has "
        "current rules. The package needs review.")
    assert notice([job("plain", _payload()), job("decided", _decided(_payload()))]) == (
        "1 repeated statement left out of every figure. plain.pdf left out: decided.pdf is the same file and has the "
        "review decisions. The package needs review.")
    assert notice([job("first", _payload()), job("second", _payload())]) == (
        "1 repeated statement left out of every figure. second.pdf repeats first.pdf (the same file). The package "
        "needs review.")


@needs_node
def test_the_notice_names_an_interim_left_out_and_an_overlap_sharing_credits(tmp_path, monkeypatch):
    """R14: a shorter printout of days another statement covers is named with its words; a pair of overlapping
    statements that share credits is named with the count and dollars they share, counted in both."""
    from tests.test_webapp_app import _APRIL, _ACCOUNT, _april, _document_with, _listed, _march, _period
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    mtd = _period("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
    interim = _period("int", [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)],
                      "2031-04-15", "2031-05-10", opening=30000.0)
    document = _document_with(_ACCOUNT, _APRIL[:2], start="2031-04-01", end="2031-04-20", opening=21000.0)
    packages = [_package_analysis([_march(), _april(), mtd]), _package_analysis([_april(), interim]),
                _package_analysis([_april(), _listed("doc", document, content="doc")]),
                _package_analysis([_march(), _april()])]
    result = run_dashboard("const shown = [];\n" + "".join(f"""
renderPackageAnalysis({json.dumps(package)});
shown.push([els.duplicateNotice.hidden, els.duplicateNoticeText.innerHTML.replace(/<[^>]+>/g, "")]);
""" for package in packages) + "console.log(JSON.stringify(shown));")
    assert result[0] == [False, "1 repeated statement left out of every figure. mtd.pdf repeats apr.pdf (a shorter "
                                "printout of days another statement covers). The package needs review."]
    assert result[1] == [False, "1 pair of overlapping statements shares credits. int.pdf and apr.pdf share 1 credit "
                                "($5,000.00) in the days both cover, counted in both. The package needs review."]
    assert result[2] == [False, "1 repeated statement left out of every figure. account 2 of doc.pdf repeats apr.pdf "
                                "(a shorter printout of days another statement covers). The package needs review."]
    assert result[3][0] is True


@needs_node
def test_the_copied_summaries_carry_true_verified_and_non_revenue(tmp_path, monkeypatch):
    """I07: the credit-memo text carries True, Verified and Non-revenue, in total and per month, and names the gross
    monthly figure gross."""
    statement = run_dashboard(_open("s", _served(_payload())) + """
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert ("True revenue $1,000.00 ($1,000.00 a month), verified revenue $700.00 ($700.00 a month), non-revenue "
            "$100.00 ($100.00 a month).") in statement
    short = run_dashboard(_open("s", _served(_summary_only(3))) + """
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "True revenue N/A, verified revenue N/A, non-revenue $100.00 ($100.00 a month, captured rows only)." in short
    package = _package({"mar": _payload(), "apr": _payload(month=4)}, tmp_path, monkeypatch)
    text = run_dashboard(f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)}); generateSummary();
console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert text.startswith("Package 2031-03-01 to 2031-04-28 (2 statements · 2 months): 2 of 2 statements completed. ")
    assert ("True revenue $2,000.00 ($1,000.00 a month), verified revenue $1,400.00 ($700.00 a month), non-revenue "
            "$200.00 ($100.00 a month).") in text
    assert "average monthly gross credits" in text and "average monthly credits" not in text
