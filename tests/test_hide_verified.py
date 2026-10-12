"""The owner's request of 2026-10-11 (true revenue spec §2.2, §10, §10.8, §20): "Can you get rid of verified revenue
from the fronted end please and "counted, not verified" still keep them in the backend but don't show it", and his
answers the same day: the CSV and Excel downloads drop them too ("Hide them there too").

Nothing a user sees, or downloads as CSV or Excel, names or shows Verified revenue or "Counted, not verified" (the tiers
`verified` and `counted_flagged`) as a thing of its own: no figure, row, card line, chip, filter, legend, chart segment,
tag, reason line, memo clause, column, section or setting text. True revenue (their sum), Held for review and
Non-revenue stay as they were. The backend keeps both tiers: the served payload, the JSON download and every stored
figure are unchanged.

Fabricated statements only (CONTOSO, NORTHWIND, FABRIKAM, SAMPLE; 2031), whole dollars, analysed by the real analysis
path; the whole webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py)."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import _package, _serve
from tests.test_webapp_true_revenue import _payload, _sheet_rows
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: A verified customer credit (NORTHWIND SUPPLY), counted credits of four reasons (a check, a wire from a named sender
#: that is also a large deposit to source, a Zelle deposit, a branch deposit), a held credit (a financing name), a
#: non-revenue transfer, a card purchase and a confirmed lender's payment.
ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (6, "WIRE TRANSFER FROM SAMPLE TRADING LLC", 20000.0), (7, "ZELLE FROM JOHN SAMPLE", 250.0),
        (8, "BRANCH DEPOSIT", 500.0), (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0),
        (10, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0)]

#: Every visible word of the fake page: each element's text, its innerHTML with the tags taken out, and the words a
#: screen reader or a hover reads (aria-label, title, alt, placeholder); and every chip glyph, which is visible text.
PAGE_TEXT = r"""
const pageText = () => {
  const parts = [];
  for (const el of fakeElements.values()) {
    const html = String(el.innerHTML || "");
    parts.push(html.replace(/<[^>]+>/g, " "));
    for (const m of html.matchAll(/\s(?:aria-label|title|alt|placeholder)="([^"]*)"/g)) parts.push(m[1]);
    parts.push(String(el.textContent || ""));
    for (const key of ["aria-label", "title", "alt", "placeholder"]) if (el.attributes[key]) parts.push(el.attributes[key]);
  }
  return parts.join("\n");
};
const glyphs = () => [...fakeElements.values()].flatMap((el) =>
  [...String(el.innerHTML || "").matchAll(/<span class="chip-glyph"[^>]*>([^<]*)<\/span>/g)].map((m) => m[1]));
const seen = [];
const seenGlyphs = new Set();
const look = () => { seen.push(pageText()); glyphs().forEach((glyph) => seenGlyphs.add(glyph)); };
"""

#: The words that use "verified" or "counted" in their plain sense, never as a revenue tier: an account that could
#: not be verified, the NSF days, the withholding rate counting a payment once, overlapping statements counted in both,
#: the Zelle setting ("With Zelle counted (Yes)", "Zelle deposits counted as True revenue") and a confirmed deposit
#: "counted in True revenue".
PLAIN_SENSES = (
    "counted in true revenue", "counted as true revenue", "with zelle counted (yes)", "counted once", "counted in both",
    "isn't counted as paid", "not counted", "can be counted", "days counted", "counted on different bases",
    "never counted as lenders", "could not be verified", "not verified",
)
TIER_WORD = re.compile(r"verified|counted", re.IGNORECASE)


def _tier_words(text):
    """Each place `text` still says "verified" or "counted" once the plain senses are taken out, with its context."""
    lowered = text.lower()
    for phrase in PLAIN_SENSES:
        lowered = lowered.replace(phrase, " " * len(phrase))
    return [text[max(match.start() - 60, 0):match.end() + 60].replace("\n", " ")
            for match in TIER_WORD.finditer(lowered)]


def _served(payload, zelle=True):
    from webapp.app import _displayed
    return _displayed(payload, settings={"zelle_true_revenue": zelle})


def _open(job_id, payload):
    return _serve(**{job_id: payload}) + f"""
currentJobId = '{job_id}'; currentJobIds = ['{job_id}']; loadResults('{job_id}'); await settle();
"""


STATEMENT_WALK = r"""
look();
for (const filter of ["true_revenue", "excluded_pending_review", "non_revenue", "largeDeposit",
                      "excluded_pending_review:financing_named_payer", "nsf", "lender"]) {
  showMainRevenueEvidence(filter); look();
}
const ledger = (() => { showMainRevenueEvidence("all"); return els.transactionTable.innerHTML; })();
look();
navigate("review"); look();
generateSummary(); look();
const memo = els.summaryBox.textContent;
setModalAnalysis(currentAnalysis); renderStatementModal("s", currentAnalysis, ""); look();
for (const filter of ["true_revenue", "excluded_pending_review", "non_revenue"]) { showModalRevenueEvidence(filter); look(); }
"""


def _tags(ledger_html):
    """Each ledger row's description and its tag (the first chip's text)."""
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", ledger_html)
    out = []
    for row in rows:
        description = re.search(r'<td class="tx-desc">([^<]*)</td>', row)
        tag = re.search(r'<span class="chip-text">([^<]*)</span>', row)
        if description and tag:
            out.append((description.group(1), tag.group(1)))
    return out


# ------------------------------------------------------------------------------------------------- the whole page

@needs_node
def test_the_statement_page_names_no_verified_or_counted_tier():
    served = _served(_payload(ROWS))
    metrics = served["metrics"]
    # The fabricated statement carries both hidden tiers, so the page has something to hide.
    assert metrics["verified_revenue_total"] == 700.0 and metrics["counted_flagged_total"] == 21050.0
    assert metrics["large_unsourced_deposit_count"] == 1
    result = run_dashboard(PAGE_TEXT + _open("s", served) + r"""
const rows = (html) => [...html.matchAll(/<(button|div) class="metric-row([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => (m[3].match(/<span class="metric-label">([^<]*)<\/span>/) || [])[1]);
const credits = rows(els.metricsGrid.innerHTML).slice(0, 5);
const mix = [...els.creditMixRows.innerHTML.matchAll(/<span class="mix-label">([^<]*)<\/span>/g)].map((m) => m[1]);
const evidence = [...els.revenueTable.innerHTML.matchAll(/<button class="evidence-link"[^>]*>([^<]*)<\/button>/g)]
  .map((m) => m[1]);
""" + STATEMENT_WALK + r"""
console.log(JSON.stringify({text: seen.join("\n"), glyphs: [...seenGlyphs], ledger, memo, credits, mix, evidence}));
""")
    assert _tier_words(result["text"]) == []
    assert not {"VER", "CNT"} & set(result["glyphs"])
    # True revenue stays, with Held for review and Non-revenue beside it, exactly as before.
    assert result["credits"] == ["True Revenue", "Held for Review", "Non-Revenue", "Total Credits", "ACH Credits"]
    assert result["mix"] == ["True revenue", "Held for review", "Non-revenue"]
    assert result["evidence"][:3] == ["True Revenue", "Held for Review", "Payer or entry suggests financing"]
    assert "Non-Revenue" in result["evidence"] and "Large deposits to source" in result["evidence"]
    # A deposit in True revenue carries one tag, whether a rule verified it or counted it.
    tags = dict(_tags(result["ledger"]))
    for description in ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "MOBILE DEPOSIT", "WIRE TRANSFER FROM SAMPLE TRADING LLC",
                        "ZELLE FROM JOHN SAMPLE", "BRANCH DEPOSIT"):
        assert tags[description] == "True revenue", description
    assert tags["FABRIKAM FUNDING LLC DES:PAYMENT ID:1"] == "Held: Payer or entry suggests financing"
    assert tags["INTERNAL TRANSFER FROM SAVINGS"] == "Non-revenue"
    # The memo keeps True, held and non-revenue.
    assert "True revenue $21,750.00" in result["memo"] and "held for review $900.00 (1 credit)" in result["memo"]
    assert "non-revenue $100.00" in result["memo"]


@needs_node
def test_a_true_revenue_row_keeps_its_other_chips_and_a_held_row_its_reason(tmp_path, monkeypatch):
    served = _served(_payload(ROWS))
    result = run_dashboard(_open("s", served) + r"""
const rows = [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1]);
const row = (text) => rows.find((html) => html.includes(text)) || "";
const chips = (html) => [...html.matchAll(/<span class="chip-text">([^<]*)<\/span>/g)].map((m) => m[1]);
const reasons = (html) => [...html.matchAll(/<div class="tx-reason[^"]*">([\s\S]*?)<\/div>/g)].map((m) => m[1].replace(/<[^>]+>/g, ""));
console.log(JSON.stringify({zelle: chips(row("ZELLE FROM JOHN SAMPLE")), zelleReasons: reasons(row("ZELLE FROM JOHN SAMPLE")),
  check: reasons(row("MOBILE DEPOSIT")), wire: reasons(row("WIRE TRANSFER FROM SAMPLE")),
  held: reasons(row("FABRIKAM FUNDING")), heldControls: (row("FABRIKAM FUNDING").match(/data-revenue-review-action="[a-z]+"/g) || []),
  countedControls: (row("MOBILE DEPOSIT").match(/data-revenue-review-action="[a-z]+"/g) || [])}));
""")
    # The Zelle chip stays beside the one tag; no counted reason line under a True revenue row.
    assert result["zelle"] == ["True revenue", "Zelle"]
    assert result["zelleReasons"] == [] and result["check"] == []
    # A large deposit still asks for its source, without the tier's words.
    assert result["wire"] == ["Large deposit: 92.0% of True revenue. Ask for its source."]
    assert result["held"] == ["Reason: Payer or entry suggests financing. The payer or the entry names funding, a loan or an "
                              "advance."]
    # Behaviour is unchanged: the review controls are the server's.
    assert result["heldControls"] == ['data-revenue-review-action="confirm"', 'data-revenue-review-action="reject"']
    assert result["countedControls"] == ['data-revenue-review-action="confirm"', 'data-revenue-review-action="reject"']


PACKAGE_WALK = r"""
look();
for (const view of ["both", "true", "total"]) { setMonthlyDepositsView(view); look(); }
const chart = {};
for (const view of ["both", "true", "total"]) {
  setMonthlyDepositsView(view);
  chart[view] = {legend: (els.monthlyChart.innerHTML.match(/<span class="chart-legend">([\s\S]*?)<\/span>\s*<\/div>/) || [])[1] || "",
    values: [...els.monthlyChart.innerHTML.matchAll(/<span class="bar-value([^"]*)">/g)].map((m) => m[1].trim()),
    parts: [...els.monthlyChart.innerHTML.matchAll(/<div class="bar-part([^"]*)"/g)].map((m) => m[1].trim()),
    aria: (els.monthlyChart.innerHTML.match(/aria-label="([^"]*)"/) || [])[1]};
}
setMonthlyDepositsView("both");
for (const filter of ["true_revenue", "excluded_pending_review", "non_revenue", "largeDeposit"]) {
  showMainRevenueEvidence(filter); look();
}
navigate("review"); look();
generateSummary(); look();
const memo = els.summaryBox.textContent;
"""


@needs_node
def test_the_package_page_names_no_verified_or_counted_tier(tmp_path, monkeypatch):
    package = _package({"mar": _payload(ROWS, 3), "apr": _payload(ROWS, 4)}, tmp_path, monkeypatch)
    totals = package["totals"]
    assert totals["verified_revenue_total"] == 1400.0 and totals["counted_flagged_total"] == 42100.0
    result = run_dashboard(PAGE_TEXT + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
""" + PACKAGE_WALK + r"""
const rows = (html) => [...html.matchAll(/<(button|div) class="metric-row([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => (m[3].match(/<span class="metric-label">([^<]*)<\/span>/) || [])[1]);
console.log(JSON.stringify({text: seen.join("\n"), glyphs: [...seenGlyphs], chart, memo,
  revenue: rows(els.metricsGrid.innerHTML).slice(0, 6),
  mix: [...els.creditMixRows.innerHTML.matchAll(/<span class="mix-label">([^<]*)<\/span>/g)].map((m) => m[1]),
  evidence: [...els.revenueTable.innerHTML.matchAll(/<button class="evidence-link"[^>]*>([^<]*)<\/button>/g)].map((m) => m[1])}));
""")
    assert _tier_words(result["text"]) == []
    assert not {"VER", "CNT"} & set(result["glyphs"])
    # The Package revenue card keeps True Revenue, Held for Review and Non-Revenue (and its own other lines).
    assert result["revenue"] == ["True Revenue", "Held for Review", "Non-Revenue", "True Revenue Per Month", "Total Credits",
                                 "Avg Monthly Gross Credits"]
    assert result["mix"] == ["True revenue", "Held for review", "Non-revenue"]
    assert result["evidence"][:2] == ["True Revenue", "Held for Review"]
    # The chart: no verified shade or figure; its bars keep the key's two colours and the views their figures.
    both, true_view, total = (result["chart"][view] for view in ("both", "true", "total"))
    assert both["values"] == ["", "bar-value-true"] * 2 and both["parts"] == ["", ""]
    assert true_view["values"] == ["", ""] and true_view["parts"] == []
    assert total["values"] == ["", ""] and total["parts"] == []
    assert re.sub(r"<[^>]+>", "", both["legend"]) == "Total depositsTrue revenue"
    assert both["aria"] == "Monthly deposits per statement: total deposits and true revenue"
    assert true_view["aria"] == "Monthly deposits per statement: true revenue"
    assert "True revenue $43,500.00" in result["memo"] and "held for review $1,800.00 (2 credits)" in result["memo"]


@needs_node
def test_the_tallest_bar_fits_the_plot_box_with_the_figures_the_chart_now_stacks(tmp_path, monkeypatch):
    """The chart stacks two figures over a Both bar and one over a True or Total bar, so the tallest bar is the plot box
    less those figures (5.6, A4's geometry, the verified figure gone)."""
    package = _package({"mar": _payload(ROWS, 3), "apr": _payload(ROWS, 4)}, tmp_path, monkeypatch)
    result = run_dashboard(f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const tallest = {{}};
for (const view of ["both", "true", "total"]) {{
  setMonthlyDepositsView(view);
  tallest[view] = Math.max(...[...els.monthlyChart.innerHTML.matchAll(/class="bar bar-[a-z]+" style="height: ([0-9.]+)px"/g)]
    .map((m) => Number(m[1])));
}}
console.log(JSON.stringify(tallest));
""")
    # 189px of plot, 16px a figure and 8px a gap each, 6px pulled back by each figure after the first.
    assert result == {"both": 189 - 2 * 24 + 6, "true": 189 - 24, "total": 189 - 24}


# --------------------------------------------------------------------------- the strings that named a hidden tier

@needs_node
def test_a_zelle_deposit_a_review_confirmed_is_counted_in_true_revenue_under_no():
    """R2-OW17 under No: the part a review counted and a legacy account's counted part are one, in True revenue."""
    result = run_dashboard(r"""
const source = {revenue_established: true, true_revenue_total: 1000, non_revenue_total: 300,
  zelle_deposits: {counted_as_true_revenue: false, setting_applied: true, count: 4, total: 900,
    by_tier: {verified: {count: 1, total: 250}, counted_flagged: {count: 1, total: 200},
              excluded_pending_review: {count: 1, total: 150}, non_revenue: {count: 1, total: 300}}}};
console.log(JSON.stringify({fact: zelleFact(source, "USD"),
  memo: revenueSummarySentence(source, "USD", {established: true}, {trueMonthly: 1000, nonRevenueMonthly: 300})}));
""")
    assert result["fact"] == ("Zelle deposits excluded: $300.00 (1) · counted in True revenue: $450.00 (2) · held for "
                              "review: $150.00 (1)")
    assert result["memo"] == ("True revenue $1,000.00 ($1,000.00 a month), non-revenue $300.00 ($300.00 a month), of "
                              "which Zelle deposits excluded $300.00; Zelle deposits counted in True revenue $450.00, "
                              "held for review $150.00.")


@needs_node
def test_the_rules_reading_of_an_excluded_zelle_deposit_says_true_revenue_not_its_tier():
    result = run_dashboard(r"""
const record = (signal) => ({revenue_context_signals: [signal]});
console.log(JSON.stringify([zellePriorSentence(record("zelle_prior:verified")),
  zellePriorSentence(record("zelle_prior:counted_flagged:p2p")),
  zellePriorSentence(record("zelle_prior:excluded_pending_review:holder_name"))]));
""")
    assert result == [" With Zelle counted (Yes), it counts in True revenue.",
                      " With Zelle counted (Yes), it counts in True revenue.",
                      " With Zelle counted (Yes), the rules hold it for review: From the holder's own name or brand."
                      " Confirm Revenue releases it in both settings."]


@needs_node
def test_a_confirmed_release_is_counted_in_true_revenue_and_never_verified():
    """R2-OW16's held transfer: the hold's sentence and the package note say what Confirm Revenue does in the page's
    words; a credit saved before 5.6 that a rule verified reads as revenue."""
    result = run_dashboard(r"""
const moved = {amount: 500, date: "2031-03-04", classification: {revenue_tier: "excluded_pending_review",
  revenue_tier_reason: "own_account_transfer_matched", revenue_classification: "unverified_deposit",
  package_match: {kind: "own_account_transfer", moved: true, gap_days: 1,
    debit: {bank: "CONTOSO BANK", last4: "2020", date: "2031-03-03", filename: "savings.pdf"}}}};
const older = {amount: 700, classification: {revenue_classification: "verified_revenue"}};
console.log(JSON.stringify({reason: revenueReviewReason(moved), notes: packageMatchNotes(moved),
  older: transactionCategory(older)}));
""")
    assert result["reason"].endswith("held so it is not counted twice. Confirm Revenue counts it in True revenue.")
    assert result["notes"] == ["Transfer out of CONTOSO BANK ••2020 on 2031-03-03 (savings.pdf), 1 day earlier. Confirm "
                               "Revenue counts it in True revenue; Mark Non-Revenue keeps it out."]
    assert result["older"] == {"label": "Revenue", "glyph": "REV", "tone": "green"}


@needs_node
def test_no_filter_pill_or_settings_text_names_a_hidden_tier():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert 'data-transaction-filter="verified_revenue"' not in html
    assert 'data-transaction-filter="counted_flagged"' not in html
    assert 'data-modal-transaction-filter="verified_revenue"' not in html
    assert 'data-modal-transaction-filter="counted_flagged"' not in html
    for kept in ("true_revenue", "excluded_pending_review", "non_revenue"):
        assert f'data-transaction-filter="{kept}"' in html and f'data-modal-transaction-filter="{kept}"' in html
    body = html[html.index("<body"):]
    visible = re.sub(r"<!--[\s\S]*?-->|<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", body)
    visible = re.sub(r"<[^>]+>", " ", visible)
    for attribute in re.findall(r'\s(?:aria-label|title|alt|placeholder)="([^"]*)"', body):
        visible += "\n" + attribute
    assert _tier_words(visible) == []


# ------------------------------------------------------------------------------------- the verified withholding basis

def _verified_basis():
    """The fabricated statement analysed on the Verified withholding basis (WITHHOLDING_DENOMINATOR_MODE, R2-OW14:
    the legacy and verified bases stay selectable), as a stored analysis made on it would be served."""
    from analysis.revenue import rebuild_serialized_revenue_views

    payload = _payload(ROWS)
    payload["metrics"]["withholding_denominator_mode"] = "verified_revenue"
    rebuild_serialized_revenue_views(payload)
    assert payload["metrics"]["withholding_denominator_label"] == "Verified revenue"
    return _served(payload)


@needs_node
def test_a_statement_analysed_on_the_verified_basis_names_it_without_the_word():
    served = _verified_basis()
    metrics = served["metrics"]
    rate = metrics["withholding_rate"]
    assert metrics["withholding_denominator"] == 700.0 and rate is not None
    result = run_dashboard(PAGE_TEXT + _open("s", served) + r"""
look(); generateSummary(); look();
setModalAnalysis(currentAnalysis); renderStatementModal("s", currentAnalysis, ""); look();
const notes = Object.fromEntries([...els.metricsGrid.innerHTML.matchAll(/<(button|div) class="metric-row([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => [(m[3].match(/<span class="metric-label">([^<]*)<\/span>/) || [])[1],
               [(m[3].match(/<span class="metric-value[^"]*">([^<]*)<\/span>/) || [])[1],
                (m[3].match(/<span class="metric-note">([^<]*)<\/span>/) || [])[1]]]));
console.log(JSON.stringify({text: seen.join("\n"), basis: notes["Withholding Basis"], rate: notes["Confirmed Withholding"],
  status: els.statusList.innerHTML.replace(/<[^>]+>/g, " ").replace(/\s+/g, " "), memo: els.summaryBox.textContent}));
""")
    assert _tier_words(result["text"]) == []
    # Its figures are unchanged: the basis is the stored $700.00 and the rate the stored one.
    assert result["basis"] == ["$700.00", "Narrower revenue basis: a part of true revenue only"]
    assert result["rate"][0] == f"{rate:.2f}%"
    assert result["rate"][1] == "$250.00 confirmed lender debits divided by $700.00 narrower revenue basis"
    assert "Withholding basis Narrower revenue basis" in result["status"]
    assert "(withholding basis: narrower revenue basis)" in result["memo"]


@needs_node
def test_the_true_basis_names_its_definition_in_the_page_words():
    served = _served(_payload(ROWS))
    assert served["metrics"]["eligible_deposit_definition"] == "true revenue: verified plus counted credits"
    result = run_dashboard(_open("s", served) + r"""
const note = (els.metricsGrid.innerHTML.match(/Withholding Basis<\/span>\s*<span class="metric-note">([^<]*)<\/span>/) || [])[1];
renderMetricSections(emptyMetricSections);
const placeholder = (els.metricsGrid.innerHTML.match(/Withholding Basis<\/span>\s*<span class="metric-note">([^<]*)<\/span>/) || [])[1];
console.log(JSON.stringify({note, placeholder}));
""")
    assert result == {"note": "True revenue: posted credits minus known non-revenue and the deposits held for review",
                      "placeholder": "True revenue by default: posted credits minus known non-revenue and the deposits "
                                     "held for review"}
