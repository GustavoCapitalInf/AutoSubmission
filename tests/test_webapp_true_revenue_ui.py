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


def _served(payload, zelle=True):
    """The served copy, on an explicit settings snapshot: every default, the Zelle choice `zelle` (R2-OW17)."""
    from webapp.app import _displayed
    return _displayed(payload, settings={"zelle_true_revenue": zelle})


def _zelle_package(analyses, tmp_path, monkeypatch, zelle):
    """The real package payload under the Zelle choice `zelle` (saved in the scratch settings folder _package reads)."""
    from webapp.settings import save_settings

    save_settings(tmp_path, {"zelle_true_revenue": zelle})
    return _package(analyses, tmp_path, monkeypatch)


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


def test_the_dashboard_reason_table_keeps_the_analysis_order_and_names_the_customer_financing_reasons():
    """Owner ruling 2026-10-02 (Q8), R2-OW04: the mirror keeps REVENUE_TIER_REASONS' order, and its sentences say what
    a lease-to-own or patient financier's payout and its one-off lump sum are."""
    from analysis.revenue import REVENUE_TIER_REASONS

    assert list(_js_reasons()) == list(REVENUE_TIER_REASONS)
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert ("A lease-to-own or patient-financing company paid a one-off lump sum ($10,000 or more; by wire, in whole "
            "thousands or half the statement's credits; not one of three or more payouts of its size): held until its "
            "source is confirmed.") in source
    assert ("A lease-to-own or patient-financing company paid the business for a customer's financed purchase: "
            "counted, never verified.") in source


def test_the_dashboard_reason_table_names_a_lender_paid_for_services():
    """Owner ruling 2026-10-02 (the underwriter's Q9, part (c')), R2-OW05: the mirror carries lender_paid_for_services
    right after factoring_payout, with its one-line sentence."""
    reasons = list(_js_reasons())
    assert reasons[reasons.index("factoring_payout") + 1] == "lender_paid_for_services"
    assert _js_reasons()["lender_paid_for_services"] == ("counted_flagged", "Lender paid for services")
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert ("A lender paid the business for its services (a repair, a recovery, a commission): counted, never "
            "verified.") in source


def test_the_dashboard_reason_table_names_a_premium_trust_account_deposit():
    """Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the mirror carries premium_trust_account at the end of
    the held group, with its sentence; since the underwriter's Q4 (R2-OW16) own_account_transfer_matched follows it,
    directly before wire_named_sender."""
    reasons = list(_js_reasons())
    assert reasons[reasons.index("premium_trust_account") + 1] == "own_account_transfer_matched"
    assert reasons[reasons.index("own_account_transfer_matched") + 1] == "wire_named_sender"
    assert reasons[reasons.index("premium_trust_account") - 1] == "p2p_round_repeat"
    assert _js_reasons()["premium_trust_account"] == ("excluded_pending_review", "Deposit into a premium trust account")
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert ("The account is titled as an insurance premium trust account: its deposits are insureds' premiums held for "
            "the carriers, not the agency's revenue. Only commissions paid to the operating account count.") in source


@needs_node
def test_the_true_card_says_a_premium_trust_account_holds_its_deposits(tmp_path, monkeypatch):
    """Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the statement's True card says its deposits that would
    count are held and its non-revenue stays excluded; a package names how many of its statements are premium trust
    accounts."""
    payload = _served(_payload())
    payload["metrics"]["premium_trust_account"] = True
    statement = run_dashboard(METRIC_ROWS + _open("s", payload) + """
console.log(JSON.stringify(metricRows(els.metricsGrid.innerHTML)));
""")
    note = {row["label"]: row["note"] for row in statement}["True Revenue"].replace("&#39;", "'")
    assert note == ("Posted credits minus known non-revenue and the deposits held for review · Premium trust account: "
                    "deposits that would count are held (insureds' premiums, not revenue); non-revenue deposits stay "
                    "excluded")
    trust = _payload(month=4)
    trust["metrics"]["premium_trust_account"] = True
    package = _package({"mar": _payload(), "apr": trust}, tmp_path, monkeypatch)
    assert package["totals"]["premium_trust_documents"] == ["apr"]
    rows = run_dashboard(METRIC_ROWS + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{rows: metricRows(els.metricsGrid.innerHTML),
  two: packageRevenueFacts({{premium_trust_documents: ['a', 'b#2', 'b#1']}}),
  none: statementRevenueFacts({{premium_trust_account: false}})}}));
""")
    assert {row["label"]: row["note"] for row in rows["rows"]}["True Revenue"].endswith(
        "1 statement of a premium trust account: deposits that would count are held")
    # Two accounts of one document are one statement.
    assert rows["two"] == ["2 statements of a premium trust account: deposits that would count are held"]
    assert rows["none"] == []


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
    assert '<script src="/static/app.js?v=true-revenue-5"></script>' in html


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
    # R2-OW03: the note names the Zelle deposits the owner's policy excludes (the underwriter's Q3).
    assert {row["label"]: row for row in out["reconciled"]["rows"]}["Non-Revenue"]["note"] == (
        "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included")
    assert figures["Non-Revenue"]["note"] == (
        "Captured rows only: own-account transfers, funding, refunds and other known non-revenue, Zelle deposits "
        "included")


@needs_node
def test_yes_the_non_revenue_note_drops_the_zelle_clause_where_zelle_counts():
    """R2-OW17 (§10.5): where the served account or package says its Zelle deposits count in True revenue, the note no
    longer names them; a payload without the figures cannot say the mode and keeps today's note."""
    notes = run_dashboard("""
const note = (source, established) => revenueCardItems(source, 'USD', {established, verifiedEstablished: true})[4][2];
const counted = {zelle_deposits: {counted_as_true_revenue: true, setting_applied: true, count: 1, total: 5,
  by_tier: {counted_flagged: {count: 1, total: 5}}}};
const excluded = {zelle_deposits: {...counted.zelle_deposits, counted_as_true_revenue: false}};
console.log(JSON.stringify([note(counted, true), note(counted, false), note(excluded, true), note({}, true)]));
""")
    assert notes == [
        "Own-account transfers, funding, refunds and other known non-revenue",
        "Captured rows only: own-account transfers, funding, refunds and other known non-revenue",
        "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included",
        "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included",
    ]


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
    Verified note claims confirmed platform payouts only; the legacy basis is named gross deposits less lender funding
    and (R2-OW14, Q7) the withholding placeholders name the withholding basis, True revenue by default."""
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
    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: the placeholders name the withholding basis, True revenue
    # by default, and the verified basis's note names its label before its definition.
    assert result["verified"] == "Verified revenue: verified classified revenue"
    figures = {row["label"]: row["note"] for row in result["rows"]}
    assert figures.get("Confirmed Withholding", "Confirmed lender debits as a share of the withholding basis (True "
                       "revenue by default)") == (
        "Confirmed lender debits as a share of the withholding basis (True revenue by default)")
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert '"Confirmed lender debits as a share of the withholding basis (True revenue by default)"' in source
    assert '"Possible lender debits as a share of the withholding basis (True revenue by default)"' in source
    assert "Confirmed lender debits as a share of revenue" not in source
    assert "as a share of eligible deposits" not in source


#: The Withholding Basis card and the two rate notes beside it, read off the statement view, the package and the modal.
BASIS_ROWS = r"""
const card = (html, label) => {
  const m = html.match(new RegExp('<div class="metric-label">' + label + '<\\/div>[\\s\\S]*?<div class="metric-value">([^<]*)<\\/div>\\s*<div class="metric-sub">([^<]*)<\\/div>'));
  return m ? {value: m[1], note: m[2]} : null;
};
const basis = (rows) => Object.fromEntries(rows.filter((row) => ["Withholding Basis", "Eligible Deposits",
  "Confirmed Withholding", "Potential Withholding Exposure"].includes(row.label)).map((row) => [row.label,
  {value: row.value, note: row.note}]));
"""


@needs_node
def test_the_withholding_basis_card_names_true_revenue_by_default_and_the_legacy_basis_when_selected(
        tmp_path, monkeypatch):
    """Owner ruling 2026-10-02 (the underwriter's Q7, audit I34), R2-OW14: the 'Eligible Deposits' card is the
    'Withholding Basis' card on the statement, the package and the modal, its value unchanged and its note the basis's
    label and definition; the legacy basis keeps its own note; the rate notes divide by the basis's label."""
    monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    default = _served(_payload())
    assert default["metrics"]["withholding_denominator_mode"] == "true_revenue"
    package = _package({"mar": _payload()}, tmp_path, monkeypatch)
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("s", default) + f"""
const statement = basis(metricRows(els.metricsGrid.innerHTML));
openStatementModal('s'); await settle();
const modal = card(els.statementModalMetrics.innerHTML, 'Withholding Basis');
const modalOld = card(els.statementModalMetrics.innerHTML, 'Eligible Deposits');
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{statement, modal, modalOld, package: basis(metricRows(els.metricsGrid.innerHTML)),
  missing: activeDenominatorNote({{eligible_deposit_definition: 'true revenue: verified plus counted credits'}})}}));
""")
    statement = result["statement"]
    assert "Eligible Deposits" not in statement and result["modalOld"] is None
    assert statement["Withholding Basis"] == {"value": "$1,000.00", "note": "True revenue: verified plus counted credits"}
    assert result["modal"] == statement["Withholding Basis"]
    assert statement["Confirmed Withholding"]["note"] == "$0.00 confirmed lender debits divided by $1,000.00 true revenue"
    assert statement["Potential Withholding Exposure"]["note"] == (
        "$0.00 potential lender debits divided by $1,000.00 true revenue")
    assert result["package"]["Withholding Basis"] == {"value": "$1,000.00",
                                                     "note": "True revenue: verified plus counted credits"}
    assert "Eligible Deposits" not in result["package"]
    # U3: a stored payload with no mode keeps the legacy basis's note.
    assert result["missing"] == "Gross deposits less lender funding (not True revenue)"

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "legacy_eligible_deposits")
    legacy = _served(_payload())
    assert legacy["metrics"]["withholding_denominator_mode"] == "legacy_eligible_deposits"
    rows = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("l", legacy) + """
console.log(JSON.stringify(basis(metricRows(els.metricsGrid.innerHTML))));
""")
    assert rows["Withholding Basis"] == {"value": "$2,000.00",
                                         "note": "Gross deposits less lender funding (not True revenue)"}
    assert rows["Confirmed Withholding"]["note"] == (
        "$0.00 confirmed lender debits divided by $2,000.00 legacy eligible deposits")


@needs_node
def test_a_basis_of_zero_names_the_basis_it_misses():
    """R2-OW14 (Q7, U5): with True revenue $0.00 the rate notes name the basis that is missing."""
    result = run_dashboard("""
const metrics = {withholding_review_required: true, withholding_denominator_mode: 'true_revenue',
  withholding_denominator_label: 'True revenue', withholding_numerator: 850, withholding_denominator: 0,
  potential_lender_debit_total: 120, potential_withholding_denominator: 0};
console.log(JSON.stringify({audit: withholdingAuditNote(metrics, 'USD'),
  potential: potentialWithholdingAuditNote(metrics, 'USD')}));
""")
    assert result["audit"] == "The withholding basis (true revenue) is unavailable; analyst review is required"
    assert result["potential"] == ("$120.00 potential lender debits; the withholding basis (true revenue) is "
                                   "unavailable; analyst review is required")


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
def test_the_notice_names_a_longer_printout_left_out_and_an_overlap_in_its_own_currency(tmp_path, monkeypatch):
    """R2-B14 review round 1: a printout of more than a month left out in favour of the monthly statements that print
    its rows is named with its own words, as a job and as an account of a document; a pair of overlapping statements
    gives its shared credits in the pair's own currency."""
    from tests.test_webapp_app import (_ACCOUNT, _APRIL, _FEB, _JAN, _MAR_Q1, _document_with, _first_quarter,
                                       _listed, _period, _printed)
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    quarter = _period("q1", _JAN + _FEB + _MAR_Q1, "2031-01-01", "2031-03-31")
    january, february, _march = _first_quarter()
    document = _document_with(_ACCOUNT, _JAN + _FEB, start="2031-01-01", end="2031-02-28", opening=1500.0)

    def cad(payload):
        payload["statement"]["currency"] = "CAD"
        return payload

    april = _listed("apr", cad(_printed(_ACCOUNT, _APRIL, start="2031-04-01", end="2031-04-30", opening=21000.0)),
                    content="apr")
    interim = _listed("int", cad(_printed(_ACCOUNT, [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1",
                                                                  6000.0)],
                                          start="2031-04-15", end="2031-05-10", opening=30000.0)), content="int")
    overlap = _package_analysis([april, interim, _listed("usd", _printed("000000002020"), content="usd")])
    # The pair names its own currency: the notice reads it even where a member's row does not say one.
    for document_row in overlap["documents"]:
        document_row.pop("currency", None)
    packages = [_package_analysis([*_first_quarter(), quarter]),
                _package_analysis([january, february, _listed("doc", document, content="doc")]), overlap]
    result = run_dashboard("const shown = [];\n" + "".join(f"""
renderPackageAnalysis({json.dumps(package)});
shown.push(els.duplicateNoticeText.innerHTML.replace(/<[^>]+>/g, ""));
""" for package in packages) + "console.log(JSON.stringify(shown));")
    words = "a printout of more than a month whose every row other statements of the account print"
    assert result[0] == (f"1 repeated statement left out of every figure. q1.pdf repeats jan.pdf ({words}). "
                         "The package needs review.")
    assert result[1] == (f"1 repeated statement left out of every figure. account 2 of doc.pdf repeats jan.pdf "
                         f"({words}). The package needs review.")
    assert result[2] == ("1 pair of overlapping statements shares credits. int.pdf and apr.pdf share 1 credit "
                         "(CA$5,000.00) in the days both cover, counted in both. The package needs review.")


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


# ---------------------------------------------------------------- Audit round 2, R2-B15: months, exclusions, counts

#: Every surface of the package page as text: the hero, the status rows, the summary card, the Monthly Statements
#: count, the notices, the processing note and the copied memo (generateSummary).
PACKAGE_VIEW = r"""
const kv = (el) => Object.fromEntries([...el.innerHTML.matchAll(
  /<span class="kv-key">([^<]*)<\/span>\s*<span class="kv-value"[^>]*>([^<]*)<\/span>/g)].map((m) => [m[1], m[2]]));
const strip = (html) => String(html).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const view = (pkg, ids) => {
  for (const el of fakeElements.values()) { el.innerHTML = ""; el.textContent = ""; el.hidden = false; }
  currentJobIds = ids; renderPackageAnalysis(pkg); generateSummary();
  const metrics = els.metricsGrid.innerHTML;
  return {kicker: strip(els.heroKicker.innerHTML), chips: [...els.heroChips.innerHTML.matchAll(
      /<span class="hero-chip[^"]*">([^<]*)<\/span>/g)].map((m) => m[1]),
    label: els.creditsLabel.textContent, meta: strip(els.creditsMeta.innerHTML), status: kv(els.statusList),
    card: kv(els.packageSummaryList), count: els.monthlyCount.textContent, memo: els.summaryBox.textContent,
    processing: els.packageProcessingNote.textContent,
    note: (metrics.match(/\d+ of \d+ statements? (?:has|have) no established revenue/) || [""])[0],
    cards: Object.fromEntries([...metrics.matchAll(/<span class="metric-label">([^<]*)<\/span>[\s\S]*?<span class="metric-value[^"]*">([^<]*)<\/span>/g)].map((m) => [m[1], m[2]])),
    buttons: [...els.monthlyTable.innerHTML.matchAll(/<button class="statement-open"[^>]*>([^<]*)/g)].map((m) => m[1].trim()),
    excluded: els.excludedNotice ? [els.excludedNotice.hidden, strip(els.excludedNoticeText.innerHTML)] : null,
    duplicates: [els.duplicateNotice.hidden, strip(els.duplicateNoticeText.innerHTML)],
    all: [...fakeElements.values()].map((el) => strip(el.innerHTML || el.textContent)).join(" | ")};
};
"""


def _views(*packages):
    """Each package rendered on its own page (its counted jobs on screen), as PACKAGE_VIEW reads it."""
    calls = ", ".join(
        f"view({json.dumps(package)}, {json.dumps(sorted({doc['id'].split('#')[0] for doc in package['documents']}))})"
        for package in packages)
    return run_dashboard(PACKAGE_VIEW + f"console.log(JSON.stringify([{calls}]));")


def _never_more_of_than_there_are(text):
    """No surface prints "X of Y" (or "X completed of Y", "X / Y") with X above Y."""
    pairs = re.findall(r"\b(\d+) (?:completed )?(?:of|/) (\d+)\b", text)
    return [pair for pair in pairs if int(pair[0]) > int(pair[1])]


@needs_node
def test_a_long_statement_and_a_mid_month_cycle_read_their_months_on_the_page(tmp_path, monkeypatch):
    """R13: the 59-day statement's memo says $10,000.00 a month (its two months), on the statement page and in the
    package; the 16th cycle's package reads 3 statements and 3 months, its rows still January, March, March."""
    from tests.test_webapp_true_revenue import _SIXTEENTH_CYCLE, _period_payload

    long_statement = _period_payload("2031-01-01", "2031-02-28", 20000.0)
    statement = run_dashboard(_open("long", _served(long_statement)) + """
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "True revenue $20,000.00 ($10,000.00 a month)" in statement
    one_month = run_dashboard(_open("mar", _served(_payload())) + """
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "True revenue $1,000.00 ($1,000.00 a month)" in one_month  # 28 days: one month, the total (unchanged)
    long_package = _package({"long": long_statement}, tmp_path, monkeypatch)
    cycle = _package({f"c{index}": _period_payload(start, end) for index, (start, end) in enumerate(_SIXTEENTH_CYCLE)},
                     tmp_path, monkeypatch)
    long_view, cycle_view = _views(long_package, cycle)
    assert long_view["label"] == "Total credits · 1 statement · 2 months"
    assert "True revenue $20,000.00 ($10,000.00 a month)" in long_view["memo"]
    assert cycle_view["label"] == "Total credits · 3 statements · 3 months"
    assert cycle_view["meta"].endswith("True revenue $30,000.00 · True per month $10,000.00")
    rows = run_dashboard(CELLS + f"""
renderPackageAnalysis({json.dumps(cycle)}); console.log(JSON.stringify(monthly().rows.map((row) => row[0])));
""")
    # The two March rows name their files under the month (two statements of one month), as before.
    assert rows == ["January", "Marchfabricated-c1.pdf", "Marchfabricated-c2.pdf"]


@needs_node
def test_an_account_left_out_of_the_package_is_named_and_the_true_line_says_what_it_covers(tmp_path, monkeypatch):
    """R15: the notice names each account left out (not a repeat) and why, the package needs review, and the True line
    says how many statements it covers; a package that counted none reads N/A and never Balanced (R54)."""
    from tests.test_webapp_app import _r15_document, _r15_month
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    withheld = _package_analysis([_r15_month(1), _r15_document(2, main="held"), _r15_month(3)])
    ambiguous = _package_analysis([_r15_month(1), _r15_document(2, notes=("ambiguous_internal_transfer",))])
    alone = _package_analysis([_r15_document(3, main="held")])
    idle = _package_analysis([_r15_month(1), _r15_document(2, main="idle")])
    clean = _package_analysis([_r15_month(1), _r15_month(2), _r15_month(3)])
    withheld_view, ambiguous_view, alone_view, idle_view, clean_view = _views(withheld, ambiguous, alone, idle, clean)
    assert withheld_view["excluded"] == [False, "1 account left out of every figure. The package needs review. "
                                                "doc2.pdf (main account not verified)."]
    assert "True revenue $20,000.00 · covers 2 of 3 statements · True per month $10,000.00" in withheld_view["meta"]
    assert withheld_view["duplicates"][0] is True  # the repeats' notice stays for repeats
    assert ambiguous_view["excluded"][1] == (
        "2 accounts left out of every figure. The package needs review. doc2.pdf, account 1 of 2 (transfers between "
        "its accounts could not be paired); doc2.pdf, account 2 of 2 (transfers between its accounts could not be "
        "paired).")
    assert "covers 1 of 2 statements" in ambiguous_view["meta"]
    assert idle_view["excluded"][1].endswith("doc2.pdf (main account printed no activity).")
    assert "Revenue · Balanced" not in alone_view["chips"] and "Revenue · Review required" in alone_view["chips"]
    assert "True revenue N/A · covers 0 of 1 statement ·" in alone_view["meta"]
    assert alone_view["status"]["Revenue reconciliation"] == "Review required"
    assert alone_view["cards"]["True Revenue"] == "N/A"
    assert clean_view["excluded"] == [True, ""] and "covers" not in clean_view["meta"]
    assert "Revenue · Balanced" in clean_view["chips"]


@needs_node
def test_the_other_exclusion_labels(tmp_path, monkeypatch):
    from tests.test_webapp_app import _r15_document

    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    unratified = [{"label": "CONTOSO SECTION B", "reason": "absence_of_parsed_rows", "posting_count": 0}]
    omitted = _package_analysis([_r15_document(2, omitted=unratified)])
    unvalidated_doc = _r15_document(3)
    unvalidated_doc.analysis["accounts"][1]["quality"]["corporate_use"] = "manual_review"
    unvalidated = _package_analysis([unvalidated_doc])
    omitted_view, unvalidated_view = _views(omitted, unvalidated)
    assert omitted_view["excluded"][1].endswith("doc2.pdf, account 2 of 2 (a section left out without proof).")
    assert unvalidated_view["excluded"][1] == ("1 account left out of every figure. The package needs review. "
                                               "doc3.pdf, account 2 of 2 (account not validated).")


@needs_node
def test_a_package_with_nothing_analysed_reads_n_a_and_names_what_is_still_processing(tmp_path, monkeypatch):
    """R54: no Balanced, no $0.00 and no invented "1 statement · 1 month" where nothing was analysed; a queued or
    processing job reads Processing, never Failed."""
    from tests.test_webapp_app import _listed, _r15_month
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    failed = _package_analysis([_listed("sample", status="error", filename="sample.pdf")])
    queued = _package_analysis([_listed("sample", status="queued", filename="sample.pdf")])
    mixed = _package_analysis([_r15_month(1), _listed("sample", status="error", content="s", filename="s.pdf")])
    failed_view, queued_view, mixed_view = _views(failed, queued, mixed)
    for page in (failed_view, queued_view):
        assert "Revenue · Balanced" not in page["chips"]
        assert page["label"] == "Total credits · No statements analysed"
        assert "1 statement · 1 month" not in page["all"]
        assert page["cards"]["True Revenue"] == "N/A" and page["cards"]["True Revenue Per Month"] == "N/A"
        assert "True revenue N/A" in page["memo"]
    assert failed_view["processing"] == "1 statement failed" and failed_view["buttons"] == ["Unavailable"]
    assert queued_view["processing"] == "1 still processing" and queued_view["buttons"] == ["Processing"]
    assert queued_view["status"]["Processing errors"] == "0"
    # An analysed month beside a failed one keeps its figures and its chip (spec §10.4).
    assert "Revenue · Balanced" in mixed_view["chips"]
    assert "True revenue $10,000.00 · True per month $10,000.00" in mixed_view["meta"]


@needs_node
def test_the_package_counts_name_statements_and_accounts_apart(tmp_path, monkeypatch):
    """R50: a repeat is no statement of the package on any surface, and a document of two accounts is one statement
    and two accounts, never "2 statements" or "2 of 1"."""
    from tests.test_webapp_app import _listed, _r15_document
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)

    def contoso(job_id):
        return _listed(job_id, _payload(), content="contoso-march", filename="march.pdf")

    twice = _package_analysis([contoso("a"), contoso("b")])
    thrice = _package_analysis([contoso("a"), contoso("b"), contoso("c")])
    fabrikam = _package_analysis([_r15_document(3, job_id="fabrikam")])
    with_april = _package_analysis([_r15_document(3, job_id="fabrikam"),
                                    _listed("april", _payload(month=4), content="april", filename="april.pdf")])
    with_queued = _package_analysis([_r15_document(3, job_id="fabrikam"),
                                     _listed("later", status="queued", content="later", filename="later.pdf")])
    twice_view, thrice_view, fabrikam_view, april_view, queued_view = _views(
        twice, thrice, fabrikam, with_april, with_queued)
    assert twice_view["card"]["Statements"] == "1 completed of 1"
    assert twice_view["status"]["Statements completed"] == "1 / 1"
    assert "1 of 1 statements completed, 1 repeated statement left out" in twice_view["memo"]
    assert thrice_view["card"]["Statements"] == "1 completed of 1"
    assert fabrikam_view["kicker"].startswith("Package · 1 statement · 2 accounts")
    assert fabrikam_view["status"]["Accounts completed"] == "2 / 2" and "Statements completed" not in fabrikam_view[
        "status"]
    assert fabrikam_view["card"]["Statements"] == "1 statement · 2 of 2 accounts completed"
    assert fabrikam_view["count"] == "1 statement · 2 accounts"
    assert "): 2 of 2 accounts completed." in fabrikam_view["memo"]
    assert fabrikam_view["label"] == "Total credits · 1 statement · 1 month"
    assert april_view["kicker"].startswith("Package · 2 statements · 3 accounts")
    assert april_view["status"]["Accounts completed"] == "3 / 3"
    assert april_view["card"]["Statements"] == "2 statements · 3 of 3 accounts completed"
    assert queued_view["status"]["Accounts completed"] == "2 / 3"
    for page in (twice_view, thrice_view, fabrikam_view, april_view, queued_view):
        assert _never_more_of_than_there_are(page["all"]) == []
    assert "2 statements" not in fabrikam_view["all"]


@needs_node
def test_the_unestablished_note_counts_statements_over_statements():
    """R50: two unestablished accounts of one document are one statement of one, never "1 of 2"."""
    result = run_dashboard("""
const docs = [{id: "doc#account_1", status: "done"}, {id: "doc#account_2", status: "done"}];
console.log(JSON.stringify([
  packageUnestablishedNote({completed: 2, revenue_unestablished_documents: ["doc#account_1", "doc#account_2"]}, docs),
  packageUnestablishedNote({completed: 2, revenue_unestablished_documents: ["doc#account_2"]}, docs),
  packageUnestablishedNote({completed: 2, revenue_unestablished_documents: ["apr"]},
                           [{id: "mar", status: "done"}, {id: "apr", status: "done"}])]));
""")
    assert result == ["1 of 1 statement has no established revenue", "1 of 1 statement has no established revenue",
                      "1 of 2 statements has no established revenue"]


@needs_node
def test_two_single_statements_read_as_before(tmp_path, monkeypatch):
    """R50 controls: a package of single-account statements keeps every count string (two done; one failed of two)."""
    from tests.test_webapp_app import _listed
    from webapp.app import _package_analysis, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    singles = _package_analysis([_listed("mar", _payload(), content="mar", filename="march.pdf"),
                                 _listed("apr", _payload(month=4), content="apr", filename="april.pdf")])
    one_failed = _package_analysis([_listed("mar", _payload(), content="mar", filename="march.pdf"),
                                    _listed("apr", status="error", content="apr", filename="april.pdf")])
    singles_view, failed_view = _views(singles, one_failed)
    assert singles_view["kicker"].startswith("Package · 2 statements")
    assert singles_view["status"]["Statements completed"] == "2 / 2"
    assert singles_view["card"]["Statements"] == "2 completed of 2"
    assert singles_view["count"] == "2 statements"
    assert "2 of 2 statements completed." in singles_view["memo"]
    assert failed_view["status"]["Statements completed"] == "1 / 2"
    assert failed_view["card"]["Statements"] == "1 completed of 2"
    assert "1 of 2 statements completed." in failed_view["memo"]
    assert failed_view["processing"] == "1 statement failed"


# ---------------------------------------------------------------- Owner ruling 2026-10-02, R2-OW03: the non-revenue
# breakdown, the statement of the Zelle exclusion and the Zelle confirm (the underwriter's Q3; spec §10.1, §10.2,
# §10.5 to §10.7). CONTOSO's fabricated March: a company payer (700), a check deposit (300) and three Zelle deposits
# (1,000, 400 and 100), so True is 1,000 and the excluded Zelle deposits 1,500.

_ZELLE_ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
               (4, "ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 1000.0),
               (5, "ZELLE PAYMENT FROM SAMPLE CATERING CONF 2", 400.0),
               (6, "ZELLE PAYMENT FROM FABRIKAM SUPPLY CONF 3", 100.0)]
_ZELLE_LABEL = "Zelle deposit (excluded by policy)"
_ZELLE_SENTENCE = ("A Zelle deposit, excluded from true revenue by policy; confirm it if this business takes customer "
                   "payments by Zelle.")
_GOVERNMENT_LABEL = "Government payment, no purpose printed"
_GOVERNMENT_SENTENCE = ("A government payment that prints no purpose (MN State MMB, the VA's 36 TREAS 310 MISC PAY, "
                        "Wisconsin DCF WIDCF DD, BC provincial payment, WSIB, Gouv. Quebec MSP, North Dakota Workforce "
                        "Safety): excluded by the owner's ruling of 2026-10-02 (Q12).")

LEDGER = r"""
const ledger = () => [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
  .map((row) => [(row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || "",
    [...row.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1])]);
const zelleDetails = () => [...els.monthlyTable.innerHTML.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) =>
  [...m[1].matchAll(/<div class="table-cell-detail">Zelle excluded ([^<]*)<\/div>/g)].map((d) => d[1]));
"""
#: CELLS' Monthly Statements reader, for a run that already has METRIC_ROWS' `cells`.
MONTHLY = r"""
const monthly = () => ({head: cells(els.monthlyHead.innerHTML)[0], rows: cells(els.monthlyTable.innerHTML),
                        count: els.monthlyCount.textContent});
"""


def test_the_js_reviewable_non_revenue_codes_mirror_the_analysis():
    from analysis.revenue import REVIEWABLE_NON_REVENUE_REASONS

    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    found = re.search(r"const REVIEWABLE_NON_REVENUE_REASONS = Object\.freeze\(\[([^\]]*)\]\);", source)
    assert found and set(re.findall(r'"([a-z_0-9]+)"', found[1])) == set(REVIEWABLE_NON_REVENUE_REASONS)


@needs_node
def test_a_statement_states_its_excluded_zelle_deposits():
    """Under No (R2-OW17: "Mark Zelle Payments as True Revenue", the exclusion's own choice): today's display."""
    result = run_dashboard(METRIC_ROWS + LEDGER + _open("z", _served(_payload(_ZELLE_ROWS), zelle=False)) + """
const rows = metricRows(els.metricsGrid.innerHTML);
const evidenceHtml = els.revenueTable.innerHTML;
const evidence = cells(evidenceHtml);
showMainRevenueEvidence('non_revenue:zelle_excluded');
const header = els.transactionCount.textContent;
const filtered = ledger();
generateSummary();
console.log(JSON.stringify({rows, evidenceHtml, evidence, header, filtered, memo: els.summaryBox.textContent}));
""")
    figures = {row["label"]: row for row in result["rows"]}
    assert figures["True Revenue"]["value"] == "$1,000.00" and figures["Non-Revenue"]["value"] == "$1,500.00"
    assert figures["True Revenue"]["note"] == ("Posted credits minus known non-revenue and the deposits held for review"
                                               " · Zelle deposits excluded: $1,500.00 (3)")
    assert figures["Non-Revenue"]["note"] == (
        "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included")
    # The evidence table breaks Non-Revenue down by its reason codes, as it does Counted and Held.
    assert [row[:3] for row in result["evidence"]][-2:] == [["Non-Revenue", "3", "$1,500.00"],
                                                           [_ZELLE_LABEL, "3", "$1,500.00"]]
    assert 'data-revenue-filter="non_revenue:zelle_excluded"' in result["evidenceHtml"]
    assert f'aria-label="Show the excluded {_ZELLE_LABEL} transactions"' in result["evidenceHtml"]
    # Its filter lists only those rows, each with Confirm Revenue only.
    assert result["header"] == "3 excluded: zelle deposit (excluded by policy)"
    assert result["filtered"] == [["ZELLE PAYMENT FROM PAT SAMPLE CONF 1", ["confirm"]],
                                  ["ZELLE PAYMENT FROM SAMPLE CATERING CONF 2", ["confirm"]],
                                  ["ZELLE PAYMENT FROM FABRIKAM SUPPLY CONF 3", ["confirm"]]]
    assert ("non-revenue $1,500.00 ($1,500.00 a month), of which Zelle deposits excluded $1,500.00.") in result["memo"]


@needs_node
def test_yes_a_statement_counts_its_zelle_deposits():
    """The twin under Yes (the owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17, the default): the three
    Zelle deposits count (person-to-person), the True card says so, the Non-Revenue note names no Zelle deposits, and
    each Zelle row carries the Zelle chip and Confirm Revenue / Mark Non-Revenue."""
    result = run_dashboard(METRIC_ROWS + LEDGER + _open("z", _served(_payload(_ZELLE_ROWS))) + """
const rows = metricRows(els.metricsGrid.innerHTML);
const zelleRows = [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\\s\\S]*?)<\\/tr>/g)].map((m) => m[1])
  .filter((row) => /<span class="chip-text">Zelle<\\/span>/.test(row))
  .map((row) => (row.match(/<td class="tx-desc">([^<]*)<\\/td>/) || [])[1]);
const all = ledger();
generateSummary();
console.log(JSON.stringify({rows, zelleRows, all, memo: els.summaryBox.textContent}));
""")
    figures = {row["label"]: row for row in result["rows"]}
    assert figures["True Revenue"]["value"] == "$2,500.00" and figures["Non-Revenue"]["value"] == "$0.00"
    assert figures["True Revenue"]["note"] == ("Posted credits minus known non-revenue and the deposits held for review"
                                               " · Zelle deposits in True revenue: $1,500.00 (3)")
    assert figures["Non-Revenue"]["note"] == "Own-account transfers, funding, refunds and other known non-revenue"
    assert result["zelleRows"] == [text for _day, text, _amount in _ZELLE_ROWS[2:]]
    assert [actions for text, actions in result["all"] if text.startswith("ZELLE")] == [["confirm", "reject"]] * 3
    assert "; Zelle deposits counted as True revenue $1,500.00." in result["memo"]


@needs_node
def test_a_statement_without_a_zelle_deposit_says_nothing_of_it():
    result = run_dashboard(METRIC_ROWS + _open("s", _served(_payload())) + """
generateSummary();
console.log(JSON.stringify({rows: metricRows(els.metricsGrid.innerHTML), evidence: cells(els.revenueTable.innerHTML),
  memo: els.summaryBox.textContent}));
""")
    note = {row["label"]: row["note"] for row in result["rows"]}["True Revenue"]
    assert "Zelle" not in note and "Zelle" not in result["memo"]
    assert result["evidence"][-1][:3] == ["Non-Revenue", "1", "$100.00"]


@needs_node
def test_a_coded_non_revenue_row_is_tagged_with_its_reason_and_only_a_zelle_deposit_may_be_confirmed():
    rows = [_record("non_revenue", reason="zelle_excluded"),
            _record("verified", reason="zelle_excluded", initial="non_revenue", status="confirmed"),
            _record("non_revenue", reason="government_no_purpose"),
            _record("non_revenue", reason="check_deposit", initial="unverified_deposit", status="rejected"),
            _record("non_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const found = (filter) => filterTransactions(rows, filter).map((tx) => rows.indexOf(tx));
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
console.log(JSON.stringify({{tags: rows.map((tx) => transactionCategory(tx).label), reasons: rows.map(revenueReviewReason),
  controls: rows.map((tx) => actions(revenueReviewControls(tx))), confirm: revenueReviewControls(rows[0]),
  pickable: rows.map((tx) => pendingReviewTarget(tx) !== null), kinds: rows.map((tx) => revenueReviewKind(tx.classification)),
  filters: Object.fromEntries(["non_revenue:zelle_excluded", "non_revenue:government_no_purpose", "non_revenue",
    "non_revenue:check_deposit"].map((f) => [f, found(f)])),
  labels: ["non_revenue:zelle_excluded", "non_revenue:government_no_purpose"].map((f) => revenueFilterLabel(f, 1))}}));
""")
    assert result["tags"] == [f"Non-revenue: {_ZELLE_LABEL}", "Verified revenue", f"Non-revenue: {_GOVERNMENT_LABEL}",
                              "Non-revenue", "Non-revenue"]
    assert result["reasons"] == [f"{_ZELLE_LABEL}. {_ZELLE_SENTENCE}", "",
                                 f"{_GOVERNMENT_LABEL}. {_GOVERNMENT_SENTENCE}", "", ""]
    # A Zelle deposit shows Confirm Revenue only (the server refuses a reject); a confirmed one its decision and Reset;
    # a government payment, a reviewer's rejection and an uncoded non-revenue row are as before.
    assert result["kinds"] == ["confirm", "confirm", "", "both", ""]
    assert result["controls"] == [["confirm"], ["reset"], [], ["reset"], []]
    assert "Mark Non-Revenue" not in result["confirm"] and ">Confirm Revenue</button>" in result["confirm"]
    assert result["pickable"] == [False] * 5  # never pending, never in the multi-select
    assert result["filters"] == {"non_revenue:zelle_excluded": [0], "non_revenue:government_no_purpose": [2],
                                 "non_revenue": [0, 2, 3, 4], "non_revenue:check_deposit": [3]}
    assert result["labels"] == [f"excluded: {_ZELLE_LABEL.lower()}", f"excluded: {_GOVERNMENT_LABEL.lower()}"]


# ---------------------------------------------------------------- Owner ruling 2026-10-02, R2-OW06 (the underwriter's
# Q11): a builder's progress draw is counted (its own reason), and a non-dealer's asset sale is non_revenue with its
# reason code, tagged on its row and broken out under Non-Revenue (the R2-OW03 breakdown), with no review path.
# CONTOSO's fabricated bakery March: a company payer (700), a check deposit (300), a car buyer's payout (1,850) and an
# equipment auction's seller payment (15,000), so True is 1,000 and the asset sales 16,850.

_ASSET_SALE_ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
                    (4, "CARVANA PAYOUT DES:CVNA 12345 ID:1234567 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
                     1850.0),
                    (5, "RITCHIE BROS DES:SELLER PMT ID:1234567 INDN:CONTOSO BAKERY LLC CO ID:1234567890 CCD",
                     15000.0)]
_ASSET_SALE_LABEL = "Sale of equipment or vehicles (not a dealer)"
_ASSET_SALE_SENTENCE = ("An equipment auction's or a car buyer's seller payout, or a printed sale of a truck, trailer, "
                        "vehicle or equipment, on a statement that shows no dealer: excluded (owner ruling of "
                        "2026-10-02, Q11).")


def test_the_dashboard_reason_table_names_q11_s_two_codes():
    """R2-OW06 (CR5): construction_progress_draw right after lender_paid_for_services, asset_sale_proceeds last, each
    with its one-line sentence."""
    reasons = list(_js_reasons())
    assert reasons[reasons.index("lender_paid_for_services") + 1] == "construction_progress_draw"
    assert reasons[-1] == "asset_sale_proceeds"
    assert _js_reasons()["construction_progress_draw"] == ("counted_flagged", "Builder's progress draw")
    assert _js_reasons()["asset_sale_proceeds"] == ("non_revenue", _ASSET_SALE_LABEL)
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert "A builder paid the business a progress draw for its work: counted, never verified." in source
    assert _ASSET_SALE_SENTENCE in source


def test_the_dashboard_reason_table_names_an_insurer_paid_for_the_business_s_work():
    """Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08 (CR5): insurer_paid_for_services right after
    construction_progress_draw, with its one-line sentence; insurer_payer and insurer_named_payer are kept."""
    reasons = list(_js_reasons())
    assert reasons[reasons.index("construction_progress_draw") + 1] == "insurer_paid_for_services"
    assert _js_reasons()["insurer_paid_for_services"] == ("counted_flagged", "Insurer paid for the business's work")
    assert {"insurer_payer", "insurer_named_payer"} <= set(reasons)
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert ("An insurer paid the business for its work: a repair, a commission, or claims it billed. Counted, never "
            "Verified. Check it is not a claim on the business's own policy.") in source


def test_the_dashboard_reason_table_names_the_q9_releases():
    """Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b)), R2-OW09 (CR5): finance_named_customer, then lessor_rent,
    right after insurer_paid_for_services, each with its one-line sentence."""
    reasons = list(_js_reasons())
    index = reasons.index("insurer_paid_for_services")
    assert reasons[index + 1: index + 3] == ["finance_named_customer", "lessor_rent"]
    assert _js_reasons()["finance_named_customer"] == (
        "counted_flagged", "Customer with a finance word in its name, paying an invoice")
    assert _js_reasons()["lessor_rent"] == ("counted_flagged", "Rent received by a leasing or property business")
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert ("A customer whose name carries a finance word paid an invoice or a vendor payment, and no debit names it: "
            "counted, never verified.") in source
    assert ("A tenant paid lease rent to a leasing or property business, and no debit names the payer: counted, never "
            "verified.") in source


@needs_node
def test_the_q9_releases_are_tagged_with_their_reasons():
    rows = [_record("counted_flagged", reason="finance_named_customer"), _record("counted_flagged", reason="lessor_rent")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{reasons: rows.map(revenueReviewReason)}}));
""")
    assert result["reasons"][0].startswith("Customer with a finance word in its name, paying an invoice. A customer")
    assert result["reasons"][1].startswith("Rent received by a leasing or property business. A tenant paid")


@needs_node
def test_an_insurer_paid_for_the_business_s_work_is_tagged_with_its_reason():
    rows = [_record("counted_flagged", reason="insurer_paid_for_services")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{tags: rows.map((tx) => transactionCategory(tx).label), reasons: rows.map(revenueReviewReason)}}));
""")
    assert result["reasons"][0].startswith("Insurer paid for the business's work. An insurer paid the business for its")


@needs_node
def test_a_statement_breaks_out_its_non_dealer_asset_sales_under_non_revenue():
    result = run_dashboard(METRIC_ROWS + LEDGER + _open("a", _served(_payload(_ASSET_SALE_ROWS))) + """
const rows = metricRows(els.metricsGrid.innerHTML);
const evidenceHtml = els.revenueTable.innerHTML;
const evidence = cells(evidenceHtml);
showMainRevenueEvidence('non_revenue:asset_sale_proceeds');
console.log(JSON.stringify({rows, evidenceHtml, evidence, header: els.transactionCount.textContent, filtered: ledger()}));
""")
    figures = {row["label"]: row for row in result["rows"]}
    assert figures["True Revenue"]["value"] == "$1,000.00" and figures["Non-Revenue"]["value"] == "$16,850.00"
    assert [row[:3] for row in result["evidence"]][-2:] == [["Non-Revenue", "2", "$16,850.00"],
                                                           [_ASSET_SALE_LABEL, "2", "$16,850.00"]]
    assert 'data-revenue-filter="non_revenue:asset_sale_proceeds"' in result["evidenceHtml"]
    assert result["header"] == f"2 excluded: {_ASSET_SALE_LABEL.lower()}"
    # Each row is listed with no review control (no confirm-dealer path: the Q11 card's open point 4).
    assert [actions for _text, actions in result["filtered"]] == [[], []]
    assert [text.split(" DES")[0] for text, _actions in result["filtered"]] == ["CARVANA PAYOUT", "RITCHIE BROS"]


@needs_node
def test_an_asset_sale_row_is_tagged_with_its_reason_and_has_no_review_control():
    rows = [_record("non_revenue", reason="asset_sale_proceeds"),
            _record("counted_flagged", reason="construction_progress_draw"), _record("non_revenue")]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
const found = (filter) => filterTransactions(rows, filter).map((tx) => rows.indexOf(tx));
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
console.log(JSON.stringify({{tags: rows.map((tx) => transactionCategory(tx).label), reasons: rows.map(revenueReviewReason),
  controls: rows.map((tx) => actions(revenueReviewControls(tx))),
  filters: Object.fromEntries(["non_revenue:asset_sale_proceeds", "non_revenue"].map((f) => [f, found(f)])),
  label: revenueFilterLabel("non_revenue:asset_sale_proceeds", 1)}}));
""")
    assert result["tags"][0] == f"Non-revenue: {_ASSET_SALE_LABEL}" and result["tags"][2] == "Non-revenue"
    assert result["reasons"][0] == f"{_ASSET_SALE_LABEL}. {_ASSET_SALE_SENTENCE}"
    assert result["reasons"][1].startswith("Builder's progress draw. A builder paid the business a progress draw")
    assert result["controls"][0] == [] and result["controls"][2] == []
    assert result["filters"] == {"non_revenue:asset_sale_proceeds": [0], "non_revenue": [0, 2]}
    assert result["label"] == f"excluded: {_ASSET_SALE_LABEL.lower()}"


def test_a_package_sums_its_members_asset_sales(tmp_path, monkeypatch):
    package = _package({"mar": _payload(_ASSET_SALE_ROWS), "apr": _payload(month=4)}, tmp_path, monkeypatch)
    assert package["totals"]["non_revenue_by_reason"] == {"asset_sale_proceeds": {"count": 2, "total": 16850.0}}


@needs_node
def test_a_package_states_its_excluded_zelle_deposits_and_each_month_its_own(tmp_path, monkeypatch):
    package = _zelle_package({"mar": _payload(_ZELLE_ROWS), "apr": _payload(month=4)}, tmp_path, monkeypatch, False)
    assert package["totals"]["non_revenue_by_reason"] == {"zelle_excluded": {"count": 3, "total": 1500.0}}
    result = run_dashboard(METRIC_ROWS + MONTHLY + LEDGER + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const rows = metricRows(els.metricsGrid.innerHTML);
const evidence = cells(els.revenueTable.innerHTML);
const both = {{...monthly(), details: zelleDetails()}};
setMonthlyDepositsView('true');
const trueOnly = {{...monthly(), details: zelleDetails()}};
setMonthlyDepositsView('total');
const totalOnly = zelleDetails();
generateSummary();
console.log(JSON.stringify({{rows, evidence, both, trueOnly, totalOnly, memo: els.summaryBox.textContent}}));
""")
    note = {row["label"]: row["note"] for row in result["rows"]}["True Revenue"]
    assert note.endswith(" · Zelle deposits excluded: $1,500.00 (3)")
    assert [_ZELLE_LABEL, "3", "$1,500.00"] in [row[:3] for row in result["evidence"]]
    # The Monthly Statements' True cell names the month's excluded Zelle deposits, only where there are some, in the
    # both and true views (never in the total view, which shows no True cell).
    assert result["both"]["details"] == [["1,500"], []]
    assert result["both"]["rows"][0][4] == "1,000Zelle excluded 1,500" and result["both"]["rows"][1][4] == "1,000"
    assert result["trueOnly"]["details"] == [["1,500"], []]
    assert result["trueOnly"]["rows"][0][2] == "1,000Zelle excluded 1,500"
    assert result["totalOnly"] == [[], []]
    assert ", of which Zelle deposits excluded $1,500.00." in result["memo"]


@needs_node
def test_yes_a_package_counts_its_zelle_deposits_and_each_month_its_own(tmp_path, monkeypatch):
    package = _zelle_package({"mar": _payload(_ZELLE_ROWS), "apr": _payload(month=4)}, tmp_path, monkeypatch, True)
    assert package["totals"]["non_revenue_by_reason"] == {}
    assert package["totals"]["zelle_deposits"]["count"] == 3
    result = run_dashboard(METRIC_ROWS + MONTHLY + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const rows = metricRows(els.metricsGrid.innerHTML);
const details = [...els.monthlyTable.innerHTML.matchAll(/<tr[^>]*>([\\s\\S]*?)<\\/tr>/g)].map((m) =>
  [...m[1].matchAll(/<div class="table-cell-detail">(Zelle[^<]*)<\\/div>/g)].map((d) => d[1]));
generateSummary();
console.log(JSON.stringify({{rows, details, memo: els.summaryBox.textContent}}));
""")
    note = {row["label"]: row["note"] for row in result["rows"]}["True Revenue"]
    assert note.endswith(" · Zelle deposits in True revenue: $1,500.00 (3)")
    assert result["details"] == [["Zelle in True 1,500"], []]
    assert "; Zelle deposits counted as True revenue $1,500.00." in result["memo"]


@needs_node
def test_yes_a_mixed_currency_package_counts_the_refused_zelle_money(tmp_path, monkeypatch):
    cad = _payload(_ZELLE_ROWS, month=4)
    cad["statement"]["currency"] = "CAD"
    package = _zelle_package({"usd": _payload(_ZELLE_ROWS), "cad": cad}, tmp_path, monkeypatch, True)
    totals = package["totals"]
    assert totals["zelle_deposits"]["total"] is None and totals["zelle_deposits"]["count"] == 6
    result = run_dashboard(CELLS + f"""
currentJobIds = ['usd', 'cad']; renderPackageAnalysis({json.dumps(package)});
const details = [...els.monthlyTable.innerHTML.matchAll(/<tr[^>]*>([\\s\\S]*?)<\\/tr>/g)].map((m) =>
  [...m[1].matchAll(/<div class="table-cell-detail">(Zelle[^<]*)<\\/div>/g)].map((d) => d[1]));
console.log(JSON.stringify({{details, facts: packageRevenueFacts({json.dumps(totals)}, null)}}));
""")
    assert result["details"] == [["Zelle in True 1,500"], ["Zelle in True 1,500 CAD"]]
    assert result["facts"] == ["Zelle deposits in True revenue: 6"]


@needs_node
def test_a_mixed_currency_package_names_each_month_s_unit_and_counts_the_refused_zelle_money(tmp_path, monkeypatch):
    cad = _payload(_ZELLE_ROWS, month=4)
    cad["statement"]["currency"] = "CAD"
    package = _zelle_package({"usd": _payload(_ZELLE_ROWS), "cad": cad}, tmp_path, monkeypatch, False)
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert totals["non_revenue_by_reason"] == {"zelle_excluded": {"count": 6, "total": None}}
    result = run_dashboard(CELLS + LEDGER + f"""
currentJobIds = ['usd', 'cad']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{details: zelleDetails(), evidence: cells(els.revenueTable.innerHTML),
  facts: packageRevenueFacts({json.dumps(totals)}, null),
  statementFacts: statementRevenueFacts({{non_revenue_by_reason: {{zelle_excluded: {{count: 3, total: 1500}}}}}}, 'CAD')}}));
""")
    # Each row is in its own statement's currency (a non-USD row names its unit), and the package's money is refused.
    assert result["details"] == [["1,500"], ["1,500 CAD"]]
    assert [_ZELLE_LABEL, "6", "N/A"] in [row[:3] for row in result["evidence"]]
    assert result["facts"] == ["Zelle deposits excluded: 6"]
    assert result["statementFacts"] == ["Zelle deposits excluded: CA$1,500.00 (3)"]


# ---------------------------------------------------------------- Owner ruling 2026-10-02, R2-OW12 (the underwriter's
# Q1, "look at the day $ amount got deposited and see if there is a frequent payment following the deposit"; spec
# §8.5, §10.7): a held wire with no sender names, one line under its reason, each lender's series that starts after it
# (revenue_funding_series). A review aid only: a decided row, any other row and an older payload show none, and the
# badge, the Held for Review grouping and the gate never read it. The statements are the funding-aid tests' (CONTOSO
# GRILL LLC's fabricated March 2054).

_FUNDING_OBSERVED = ("Recurring payments start after this deposit: possible funding. Weekly $1,250.00 to Fabrikam "
                     "Funding LLC from 2054-03-11 (2 days after, 3 payments).")
_FUNDING_CAVEAT = ("Recurring payments follow this deposit: possible funding. Weekly $900.00 to KAPITUS from 2054-03-04 "
                   "(2 days after, 4 payments); the statement begins too close to this deposit to show whether they "
                   "ran before it.")
_WIRE_REASON = "Wire, no sender printed. A wire with no sender printed."
FUNDING_ROWS = r"""
const fundingRows = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
  .map((row) => ({desc: (row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || "",
    reason: (row.match(/<div class="tx-reason"><strong>Reason:<\/strong> ([^<]*)<\/div>/) || [])[1] || "",
    funding: [...row.matchAll(/<div class="tx-reason tx-funding">([^<]*)<\/div>/g)].map((m) => m[1])}));
"""


@needs_node
def test_a_held_wire_with_no_sender_shows_the_series_that_starts_after_it():
    from tests.test_true_revenue_funding_aid import WIRE, funding_aid_payload

    result = run_dashboard(FUNDING_ROWS + _open("w", _served(funding_aid_payload())) + """
const ledger = fundingRows(els.transactionTable.innerHTML);
navigate('review');
console.log(JSON.stringify({ledger, review: fundingRows(els.transactionTable.innerHTML),
  badge: els.reviewCount.textContent}));
""")
    [wire] = [row for row in result["ledger"] if row["desc"] == WIRE]
    assert wire["reason"] == _WIRE_REASON
    assert wire["funding"] == [_FUNDING_OBSERVED]
    assert [row["funding"] for row in result["ledger"] if row["desc"] != WIRE] == [[], [], []]
    # The Held for Review view lists the held wire with its aid; the badge counts the held row as before.
    assert [row["funding"] for row in result["review"]] == [[_FUNDING_OBSERVED]]
    assert result["badge"] == "1"


@needs_node
def test_a_wire_near_the_statement_s_start_says_the_statement_cannot_show_the_series_before_it():
    from tests.test_true_revenue_funding_aid import SCENARIOS, WIRE, funding_aid_payload

    result = run_dashboard(FUNDING_ROWS + _open("w", _served(funding_aid_payload(SCENARIOS["A3"][0]))) + """
console.log(JSON.stringify(fundingRows(els.transactionTable.innerHTML)));
""")
    [wire] = [row for row in result if row["desc"] == WIRE]
    assert wire["funding"] == [_FUNDING_CAVEAT]


@needs_node
def test_a_decided_row_another_row_and_an_older_payload_show_no_aid():
    from tests.test_true_revenue_funding_aid import funding_aid_payload

    payload = _served(funding_aid_payload())
    held = json.loads(json.dumps(payload["statement"]["transactions"][0]))
    confirmed = copy.deepcopy(held)
    confirmed["classification"].update(revenue_classification="verified_revenue", revenue_tier="verified",
                                       revenue_review_status="confirmed")
    rejected = copy.deepcopy(held)
    rejected["classification"].update(revenue_classification="non_revenue", revenue_tier="non_revenue",
                                      revenue_review_status="rejected")
    older = copy.deepcopy(held)
    older["classification"].pop("revenue_funding_series")
    other = copy.deepcopy(held)
    other["classification"]["revenue_tier_reason"] = "transfer_no_counterparty"
    result = run_dashboard(FUNDING_ROWS + f"""
const rows = {json.dumps([held, confirmed, rejected, older, other])};
const table = fakeElement('funding-table'), count = fakeElement('funding-count');
renderTransactionRows(table, count, rows, 'all', 'USD', {{sort: 'none'}});
console.log(JSON.stringify({{notes: rows.map((tx) => fundingSeriesNotes(tx, 'USD')),
  cad: fundingSeriesNotes(rows[0], 'CAD'), drawn: fundingRows(table.innerHTML).map((row) => row.funding)}}));
""")
    assert result["notes"] == [[_FUNDING_OBSERVED], [], [], [], []]
    assert result["drawn"] == [[_FUNDING_OBSERVED], [], [], [], []]
    # The money is the row's currency's.
    assert result["cad"] == [_FUNDING_OBSERVED.replace("$1,250.00", "CA$1,250.00")]


@needs_node
def test_the_package_ledger_shows_the_aid_on_its_held_wire(tmp_path, monkeypatch):
    from tests.test_true_revenue_funding_aid import WIRE, funding_aid_payload

    package = _package({"w": funding_aid_payload()}, tmp_path, monkeypatch)
    result = run_dashboard(FUNDING_ROWS + f"""
currentJobIds = ['w']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify(fundingRows(els.transactionTable.innerHTML)));
""")
    [wire] = [row for row in result if row["desc"] == WIRE]
    assert wire["funding"] == [_FUNDING_OBSERVED]


def test_the_funding_aid_adds_no_reason_code():
    from analysis.revenue import REVENUE_TIER_REASONS

    assert _js_reasons() == {code: tuple(entry) for code, entry in REVENUE_TIER_REASONS.items()}
    assert not [code for code in REVENUE_TIER_REASONS if "funding_series" in code or "possible_funding" in code]


# ---------------------------------------------------------------- Owner ruling 2026-10-02, R2-OW13 (the underwriter's
# Q5, "Keep the funder in the lender count, and show a "returned funder payment" warning"; spec §10.1, §10.6): a
# confirmed funder's payment the bank returned unpaid is out of paid and in the withholding rate. The lender table warns
# one line per payment (the bank's words quoted) and marks the funder; the cards, the withholding note and the summary
# say what paid leaves out; the ledger marks the debit and the return names the payment it returns. The statements are
# tests/test_returned_funder_payments.py's (CONTOSO PLUMBING LLC's fabricated March 2054).

_RETURNED_WARNING = ('Returned funder payment: KAPITUS $850.00 debited 2054-03-03, returned 2054-03-05 ("RETURN OF '
                     'POSTED CHECK ITEM RECEIVED ON 03/03 03/05"). Not counted as paid; still in the withholding rate.')
LENDER_ROWS = r"""
const unescape = (text) => text.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
const lenderRows = (html) => [...html.matchAll(/<tr([^>]*)>([\s\S]*?)<\/tr>/g)].map((m) => ({cls: m[1].trim(),
  cells: [...m[2].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((c) => unescape(c[1].replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ").trim()))}));
const ledgerRows = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
  .map((row) => ({desc: unescape((row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || ""),
    chips: [...row.matchAll(/<span class="chip-text">([^<]*)<\/span>/g)].map((m) => m[1]),
    returned: [...row.matchAll(/<div class="tx-reason tx-returned">([^<]*)<\/div>/g)].map((m) => unescape(m[1]))}));
"""


@needs_node
def test_a_returned_funder_payment_is_warned_marked_and_kept_in_the_withholding_note():
    from tests.test_returned_funder_payments import BOFA_RETURN, KAPITUS, T1_RETURN, t1_payload

    payload = _served(t1_payload())
    result = run_dashboard(METRIC_ROWS + LENDER_ROWS + _open("r", payload) + """
const metrics = currentAnalysis.metrics;
console.log(JSON.stringify({lenders: lenderRows(els.lenderTable.innerHTML), ledger: ledgerRows(els.transactionTable.innerHTML),
  audit: withholdingAuditNote(metrics, 'USD'), paid: paidLendersNote(metrics, 'USD'),
  summary: els.summaryBox.textContent, count: els.lenderCount.textContent}));
""")
    [warning, kapitus] = result["lenders"]
    assert warning["cls"] == 'class="lender-warning"'
    assert warning["cells"] == [f"! Returned {_RETURNED_WARNING}"]
    assert kapitus["cells"][:4] == ["KAPITUS", "Confirmed lender", "2", "$1,700.00 1 returned payment, $850.00, not in paid"]
    assert kapitus["cells"][5] == "LEN Confirmed ↩ Returned"
    assert result["count"] == "1 confirmed, 0 potential"
    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: True revenue is the default basis.
    assert result["audit"] == ("$2,550.00 confirmed lender debits (incl. $850.00 returned unpaid) divided by $20,000.00 "
                               "true revenue")
    assert result["paid"] == "Total paid to confirmed lenders; $850.00 returned unpaid not included"
    assert "$1,700.00 confirmed lender debits paid (1 returned funder payment, $850.00), and" in result["summary"]
    rows = {row["desc"] + str(index): row for index, row in enumerate(result["ledger"])}
    returned = [row for row in rows.values() if "Returned" in row["chips"]]
    assert [row["desc"] for row in returned] == [KAPITUS]
    [credit] = [row for row in result["ledger"] if row["desc"] == T1_RETURN]
    assert credit["returned"] == ["Returns the 2054-03-03 payment to KAPITUS"]
    assert all(not row["returned"] for row in result["ledger"] if row["desc"] != T1_RETURN)
    assert BOFA_RETURN in T1_RETURN


@needs_node
def test_without_a_returned_payment_the_lender_sentences_read_as_before():
    result = run_dashboard("""
const metrics = {lender_debits: 1700, withholding_numerator: 1700, withholding_denominator: 20000,
  withholding_denominator_label: 'Legacy eligible deposits', returned_funder_payment_total: 0,
  returned_funder_payment_count: 0};
const older = {lender_debits: 1700, withholding_numerator: 1700, withholding_denominator: 20000,
  withholding_denominator_label: 'Legacy eligible deposits'};
console.log(JSON.stringify({audit: [withholdingAuditNote(metrics, 'USD'), withholdingAuditNote(older, 'USD')],
  paid: [paidLendersNote(metrics, 'USD'), paidLendersNote(older, 'USD'),
         paidLendersNote({returned_funder_payment_total: null}, 'USD')],
  summary: [lenderDebitsSummary(metrics, 'USD'), lenderDebitsSummary(older, 'USD'),
            lenderDebitsSummary({lender_debits: 0, returned_funder_payment_count: 2, returned_funder_payment_total: 900},
                                'CAD')],
  chip: returnedFunderChip({amount: -850, classification: {returned_funder_payment_by: null}}),
  note: returnedFunderNotes({amount: 850, classification: {returns_funder_payment: 'transaction:9'}}, [])}));
""")
    assert result["audit"] == ["$1,700.00 confirmed lender debits divided by $20,000.00 legacy eligible deposits"] * 2
    assert result["paid"] == ["Total paid to confirmed lenders"] * 3
    assert result["summary"][:2] == ["$1,700.00 confirmed lender debits"] * 2
    assert result["summary"][2] == "CA$0.00 confirmed lender debits paid (2 returned funder payments, CA$900.00)"
    assert result["chip"] == ""
    assert result["note"] == ["Returns a confirmed funder's payment (transaction:9)"]


@needs_node
def test_a_package_warns_each_returned_payment_in_its_own_unit(tmp_path, monkeypatch):
    from tests.test_returned_funder_payments import NAMED_RETURN, t1_payload, t4_payload

    package = _package({"mar": t1_payload(), "apr": t4_payload()}, tmp_path, monkeypatch)
    result = run_dashboard(METRIC_ROWS + LENDER_ROWS + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{lenders: lenderRows(els.lenderTable.innerHTML),
  rows: metricRows(els.metricsGrid.innerHTML), ledger: ledgerRows(els.transactionTable.innerHTML)}}));
""")
    warnings = [row["cells"][0] for row in result["lenders"] if row["cls"] == 'class="lender-warning"']
    assert warnings == [
        f"! Returned {_RETURNED_WARNING}",
        f'! Returned Returned funder payment: KAPITUS $850.00 debited 2054-03-02, returned 2054-03-04 ("{NAMED_RETURN}"). '
        "Not counted as paid; still in the withholding rate.",
    ]
    [kapitus] = [row for row in result["lenders"] if row["cls"] != 'class="lender-warning"']
    assert kapitus["cells"][2:4] == ["2", "$1,700.00 2 returned payments, $1,700.00, not in paid"]
    # The package ledger names, in each member, the payment its return returns.
    assert sorted(note for row in result["ledger"] for note in row["returned"]) == [
        "Returns the 2054-03-02 payment to KAPITUS", "Returns the 2054-03-03 payment to KAPITUS"]
    returned_debits = [row for row in result["ledger"] if "Returned" in row["chips"]]
    assert len(returned_debits) == 2


# ---------------------------------------------------------------- Owner ruling 2026-10-02 (the underwriter's Q6), R2-OW15

#: The package ledger's rows with the package passes' notes and their review controls, the True card's note and the
#: package-match notice, as text.
PACKAGE_MATCH_VIEW = r"""
const unescapeHtml = (text) => text.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
const stripHtml = (html) => unescapeHtml(String(html).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
const matchRows = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
  .map((row) => ({desc: unescapeHtml((row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || ""),
    notes: [...row.matchAll(/<div class="tx-reason tx-package-match">([^<]*)<\/div>/g)].map((m) => unescapeHtml(m[1])),
    confirm: /data-revenue-review-action="confirm"/.test(row), reject: /data-revenue-review-action="reject"/.test(row)}))
  .filter((row) => row.desc);
const trueNote = () => unescapeHtml((metricRows(els.metricsGrid.innerHTML).find((row) => row.label === "True Revenue")
  || {}).note || "");
const filtered = (filter) => { showMainRevenueEvidence(filter);
  return {count: els.transactionCount.textContent, rows: matchRows(els.transactionTable.innerHTML).map((row) => row.desc)}; };
const flagRows = () => [...els.revenueTable.innerHTML.matchAll(/data-revenue-filter="(debitFlag:[a-z_]+)"[^>]*>([^<]*)</g)]
  .map((m) => [m[1], m[2]]);
"""


def _matching_package(*members):
    from tests.test_package_matching import _package
    return _package(*members)


@needs_node
def test_a_bounced_deposit_matched_across_statements_reads_on_its_rows_the_notice_and_the_true_card():
    """Owner ruling 2026-10-02 (the underwriter's Q6, R2-OW15): the March deposit April returned shows its note and
    still offers Confirm Revenue and Mark Non-Revenue (Confirm overrides the match); the return names the deposit; the
    notice lists the pair with its dates and money and shows its rows; the True card lists the flags only where their
    keys exist, the chargeback line saying "and adjustments"; each flag's evidence row filters the ledger to it."""
    from tests.test_package_matching import APRIL, CHARGEBACK_ROWS, _owners_example

    march, april = _owners_example([*APRIL, *CHARGEBACK_ROWS[1:2]])
    package = _matching_package(("mar", march), ("apr", april))
    result = run_dashboard(METRIC_ROWS + PACKAGE_MATCH_VIEW + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const ledger = matchRows(els.transactionTable.innerHTML);
console.log(JSON.stringify({{ledger, note: trueNote(), flags: flagRows(),
  notice: [els.packageMatchNotice.hidden, stripHtml(els.packageMatchNoticeText.innerHTML)],
  noticeFilter: (els.packageMatchNoticeText.innerHTML.match(/data-revenue-filter="([^"]+)"/) || [])[1],
  matched: filtered('packageMatch:returned_deposit'), chargebacks: filtered('debitFlag:processor_chargeback')}}));
""")
    [deposit] = [row for row in result["ledger"] if row["desc"] == "DEPOSIT"]
    assert deposit["notes"] == ["Returned on 2031-04-01 (apr.pdf): not counted. Confirm Revenue overrides the match."]
    assert deposit["confirm"] and deposit["reject"]
    [returned] = [row for row in result["ledger"] if row["desc"] == "DEPOSITED ITEM RETURNED"]
    assert returned["notes"] == ["Returns the 2031-03-26 deposit in mar.pdf."]
    assert all(not row["notes"] for row in result["ledger"] if row["desc"] not in ("DEPOSIT", "DEPOSITED ITEM RETURNED"))
    assert result["notice"] == [False, (
        "Matched across statements: 1 bounced deposit taken out of True ($100,000.00). mar.pdf 2031-03-26 deposit "
        "$100,000.00 returned 2031-04-01 (apr.pdf). Show them")]
    assert result["noticeFilter"] == "packageMatch:returned_deposit"
    assert result["note"].endswith(" · Processor chargebacks and adjustments: 1 · $350.00 (not deducted)")
    assert "Returned deposits not matched" not in result["note"]
    assert result["flags"] == [["debitFlag:processor_chargeback", "Processor chargebacks and adjustments"]]
    assert result["matched"] == {"count": "2 bounced deposits matched across statements",
                                 "rows": ["DEPOSIT", "DEPOSITED ITEM RETURNED"]}
    assert result["chargebacks"] == {"count": "1 processor chargebacks and adjustments",
                                     "rows": ["HRTLAND PMT SYS CHARGEBACK 123456"]}


@needs_node
def test_an_unmatched_return_names_the_deposit_you_confirmed_and_the_notice_names_the_unread_statements():
    from analysis.revenue import apply_serialized_revenue_review

    from tests.test_package_matching import _owners_example
    from tests.test_webapp_true_revenue import _untiered

    march, april = _owners_example()
    confirmed = apply_serialized_revenue_review(copy.deepcopy(march), source_location="transaction:2",
                                                decision="confirm")
    decided = _matching_package(("mar", confirmed), ("apr", april))
    older = _matching_package(("mar", _untiered(march)), ("apr", april))
    plain = _matching_package(("mar", march))
    result = run_dashboard(METRIC_ROWS + PACKAGE_MATCH_VIEW + f"""
const read = (pkg) => {{ currentJobIds = pkg.documents.map((doc) => doc.id); renderPackageAnalysis(pkg);
  return {{ledger: matchRows(els.transactionTable.innerHTML), note: trueNote(), flags: flagRows(),
    notice: [els.packageMatchNotice.hidden, stripHtml(els.packageMatchNoticeText.innerHTML)]}}; }};
console.log(JSON.stringify({{decided: read({json.dumps(decided)}), older: read({json.dumps(older)}),
  plain: read({json.dumps(plain)})}}));
""")
    [returned] = [row for row in result["decided"]["ledger"] if row["desc"] == "DEPOSITED ITEM RETURNED"]
    assert returned["notes"] == ["Matches the 2031-03-26 deposit you confirmed in mar.pdf; review."]
    assert result["decided"]["notice"][0] is True
    assert result["decided"]["note"].endswith(" · Returned deposits not matched: 1 · $100,000.00 (not deducted)")
    assert result["older"]["notice"] == [False, (
        "Not matched across statements: 1 statement analysed with older rules or with no currency.")]
    assert result["older"]["flags"] == [["debitFlag:unmatched_deposit_return", "Returned deposits not matched"]]
    # Without a flag the True card and the evidence table read as before, and the notice stays hidden.
    assert "not deducted" not in result["plain"]["note"]
    assert result["plain"]["flags"] == [] and result["plain"]["notice"][0] is True


@needs_node
def test_a_transfer_between_the_business_s_accounts_reads_on_its_rows_and_the_notice():
    """Owner ruling 2026-10-02 (the underwriter's Q4, R2-OW16): B's DEPOSIT pass 2 held names the transfer out of A and
    how its release works, and still offers Confirm Revenue and Mark Non-Revenue; B's already-held TRANSFER CREDIT
    names the transfer it also matches (no control moves); each transfer out names its deposit; the notice lists the
    pairs with their dates and money, shows their rows, and names the statement it could not check (no account number
    read); a deposit two days after its transfer says so."""
    from tests.test_package_matching import _account_a, _account_b, _payload

    a = _account_a(extra=[(4, "ONLINE TRANSFER TO CHK 2020", -640.33)])
    b = _account_b(extra=[(4, "TRANSFER CREDIT", 640.33)])
    c = _payload([(6, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:3", 700.0)], month=3, opening=300.0, number="XXXX")
    package = _matching_package(("a", a), ("b", b), ("c", c))
    later = _matching_package(("a", _account_a()), ("b", _account_b(day=5)))
    result = run_dashboard(METRIC_ROWS + PACKAGE_MATCH_VIEW + f"""
const read = (pkg) => {{ currentJobIds = pkg.documents.map((doc) => doc.id); renderPackageAnalysis(pkg);
  return {{ledger: matchRows(els.transactionTable.innerHTML),
    notice: [els.packageMatchNotice.hidden, stripHtml(els.packageMatchNoticeText.innerHTML)],
    noticeFilter: (els.packageMatchNoticeText.innerHTML.match(/data-revenue-filter="([^"]+)"/) || [])[1],
    matched: filtered('packageMatch:own_account_transfer')}}; }};
console.log(JSON.stringify({{package: read({json.dumps(package)}), later: read({json.dumps(later)})}}));
""")
    ledger = result["package"]["ledger"]
    [deposit] = [row for row in ledger if row["desc"] == "DEPOSIT"]
    assert deposit["notes"] == ["Transfer out of Sample Bank ••1010 on 2031-03-03 (a.pdf), the same day. Confirm "
                                "Revenue releases it into True and marks it Verified; Mark Non-Revenue keeps it out."]
    assert deposit["confirm"] and deposit["reject"]
    [held] = [row for row in ledger if row["desc"] == "TRANSFER CREDIT"]
    assert held["notes"] == ["Also matches a transfer out of Sample Bank ••1010 on 2031-03-04 (a.pdf)."]
    [sent] = [row for row in ledger if row["desc"] == "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521"]
    assert sent["notes"] == ["Matched to the 2031-03-03 deposit into ••2020 (held)."]
    [also] = [row for row in ledger if row["desc"] == "ONLINE TRANSFER TO CHK 2020"]
    assert also["notes"] == ["Matched to the 2031-03-04 deposit into ••2020 (already held)."]
    assert not [row for row in ledger if row["notes"] and row["desc"] not in (
        "DEPOSIT", "TRANSFER CREDIT", "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", "ONLINE TRANSFER TO CHK 2020")]
    assert result["package"]["notice"] == [False, (
        "Matched across statements: 1 transfer between the business's accounts held ($12,340.17) · 1 already-held "
        "deposit also matches a transfer ($640.33). b.pdf 2031-03-03 deposit $12,340.17 matches the transfer out of "
        "a.pdf on 2031-03-03; b.pdf 2031-03-04 deposit $640.33 matches the transfer out of a.pdf on 2031-03-04 "
        "(already held). Show them Transfers between accounts not checked for 1 statement: no account number read.")]
    assert result["package"]["noticeFilter"] == "packageMatch:own_account_transfer"
    assert result["package"]["matched"]["count"] == "4 rows of transfers between the business's accounts"
    assert sorted(result["package"]["matched"]["rows"]) == sorted([
        "DEPOSIT", "TRANSFER CREDIT", "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", "ONLINE TRANSFER TO CHK 2020"])
    [late] = [row for row in result["later"]["ledger"] if row["desc"] == "DEPOSIT"]
    assert late["notes"][0].startswith("Transfer out of Sample Bank ••1010 on 2031-03-03 (a.pdf), 2 days earlier. ")


@needs_node
def test_the_notice_lists_both_kinds_of_match_with_a_button_each():
    """R2-OW16: a package whose passes made both kinds of match heads the notice with both, in the order transfers
    held, already held, bounced deposits, each list with its own button."""
    from tests.test_package_matching import APRIL, _account_b, _owners_example, _payload

    march, april = _owners_example()
    b = _account_b(extra=[(8, "DEPOSIT", 456.78)])
    sender = _payload([(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 900.0),
                       (7, "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", -456.78)], month=3, opening=1500.0,
                      number="000000003030")
    package = _matching_package(("mar", march), ("apr", april), ("b", b), ("s", sender))
    assert APRIL[0][1] == "DEPOSITED ITEM RETURNED"
    result = run_dashboard(METRIC_ROWS + PACKAGE_MATCH_VIEW + f"""
currentJobIds = {json.dumps([doc["id"] for doc in package["documents"]])}; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{notice: stripHtml(els.packageMatchNoticeText.innerHTML),
  filters: [...els.packageMatchNoticeText.innerHTML.matchAll(/data-revenue-filter="([^"]+)"[^>]*>([^<]*)</g)]
    .map((m) => [m[1], m[2]])}}));
""")
    assert result["notice"].startswith(
        "Matched across statements: 1 transfer between the business's accounts held ($456.78) · 1 bounced deposit "
        "taken out of True ($100,000.00). b.pdf 2031-03-08 deposit $456.78 matches the transfer out of s.pdf on "
        "2031-03-07. Show the transfers mar.pdf 2031-03-26 deposit $100,000.00 returned 2031-04-01 (apr.pdf). Show "
        "the bounced deposits")
    assert result["filters"] == [["packageMatch:own_account_transfer", "Show the transfers"],
                                 ["packageMatch:returned_deposit", "Show the bounced deposits"]]


@needs_node
def test_a_statement_viewed_alone_flags_its_unmatched_return_and_keeps_its_figures():
    from tests.test_package_matching import _owners_example

    _march, april = _owners_example()
    result = run_dashboard(METRIC_ROWS + PACKAGE_MATCH_VIEW + _open("apr", _served(april)) + """
console.log(JSON.stringify({note: trueNote(), flags: flagRows(), returns: filtered('debitFlag:unmatched_deposit_return'),
  value: (metricRows(els.metricsGrid.innerHTML).find((row) => row.label === "True Revenue") || {}).value}));
""")
    assert result["note"].endswith(" · Returned deposits not matched: 1 · $100,000.00 (not deducted)")
    assert result["value"] == "$50,000.00"
    assert result["flags"] == [["debitFlag:unmatched_deposit_return", "Returned deposits not matched"]]
    assert result["returns"] == {"count": "1 returned deposits not matched", "rows": ["DEPOSITED ITEM RETURNED"]}
