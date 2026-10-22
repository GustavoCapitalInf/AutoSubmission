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
    from analysis.served_view import displayed
    return displayed(payload, settings={"zelle_true_revenue": zelle})


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
  countedControls: (row("MOBILE DEPOSIT").match(/data-revenue-review-action="[a-z]+"/g) || []),
  flaggedControls: (row("WIRE TRANSFER FROM SAMPLE").match(/data-revenue-review-action="[a-z]+"/g) || [])}));
""")
    # The Zelle chip stays beside the one tag; no counted reason line under a True revenue row.
    assert result["zelle"] == ["True revenue", "Zelle"]
    assert result["zelleReasons"] == [] and result["check"] == []
    # A large deposit still asks for its source, without the tier's words.
    assert result["wire"] == ["Large deposit: 92.0% of True revenue. Ask for its source."]
    assert result["held"] == ["Reason: Payer or entry suggests financing. The payer or the entry names funding, a loan or an "
                              "advance."]
    # A held credit keeps Confirm Revenue and Mark Non-Revenue. A counted credit, in True revenue, shows what a verified
    # one shows, Mark Non-Revenue only: a Confirm on a row tagged True revenue would read "in True revenue but not
    # confirmed", the counted tier under another name (review round 1; the server still accepts a confirm).
    assert result["heldControls"] == ['data-revenue-review-action="confirm"', 'data-revenue-review-action="reject"']
    assert result["countedControls"] == ['data-revenue-review-action="reject"']
    # Review round 2: a counted credit flagged as a large deposit to source keeps Confirm Revenue, the reviewer's way to
    # say it is sourced (a confirm takes it out of the flag); its note already asks for its source.
    assert result["flaggedControls"] == ['data-revenue-review-action="confirm"', 'data-revenue-review-action="reject"']


#: Each ledger row tagged True revenue: whether it offers Confirm Revenue, Mark Non-Revenue and a multi-select box (and
#: whether it is the large deposit to source, WIRE TRANSFER FROM SAMPLE); and the held row's (FABRIKAM FUNDING) the same.
ROW_CONTROLS = r"""
const ledgerRows = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1]);
const controlsOf = (row) => ({confirm: row.includes('data-revenue-review-action="confirm"'),
  reject: row.includes('data-revenue-review-action="reject"'), box: row.includes('class="tx-select"'),
  flagged: row.includes("WIRE TRANSFER FROM SAMPLE")});
const trueRows = (html) => ledgerRows(html).filter((row) => row.includes('<span class="chip-text">True revenue</span>'))
  .map(controlsOf);
const heldRows = (html) => ledgerRows(html).filter((row) => row.includes("FABRIKAM FUNDING")).map(controlsOf);
"""


@needs_node
def test_a_row_in_true_revenue_offers_no_confirm_and_no_select_box(tmp_path, monkeypatch):
    """Review round 1 (the owner's request of 2026-10-11): a credit in True revenue, verified or counted, offers Mark
    Non-Revenue only and no multi-select box, on the statement ledger, the statement window and the package ledger;
    a held credit keeps Confirm Revenue, Mark Non-Revenue and its box. Review round 2: one exception, a counted credit
    the served payload flags as a large deposit to source keeps Confirm Revenue and its box (the page's path to clear
    the flag, R3-B24); its note already asks for its source, so the button says nothing of a hidden tier."""
    served = _served(_payload(ROWS))
    statement = run_dashboard(ROW_CONTROLS + _open("s", served) + r"""
showMainRevenueEvidence("all");
const page = {true: trueRows(els.transactionTable.innerHTML), held: heldRows(els.transactionTable.innerHTML)};
modalJobId = "s"; setModalAnalysis(currentAnalysis); renderStatementModal("s", currentAnalysis, "");
showModalRevenueEvidence("all");
const studio = {true: trueRows(els.statementModalTransactions.innerHTML),
                held: heldRows(els.statementModalTransactions.innerHTML)};
console.log(JSON.stringify({page, studio}));
""")
    package = _package({"mar": _payload(ROWS, 3), "apr": _payload(ROWS, 4)}, tmp_path, monkeypatch)
    packaged = run_dashboard(ROW_CONTROLS + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
""" + r"""
showMainRevenueEvidence("all");
console.log(JSON.stringify({true: trueRows(els.transactionTable.innerHTML), held: heldRows(els.transactionTable.innerHTML)}));
""")
    only_reject = {"confirm": False, "reject": True, "box": False, "flagged": False}
    flagged = {"confirm": True, "reject": True, "box": True, "flagged": True}
    held = {"confirm": True, "reject": True, "box": True, "flagged": False}

    def by_kind(rows):
        return sorted(rows, key=lambda row: row["flagged"])

    # The verified credit and the four counted ones of each statement, the wire of 20,000.00 its large deposit.
    assert by_kind(statement["page"]["true"]) == [only_reject] * 4 + [flagged]
    assert by_kind(packaged["true"]) == [only_reject] * 8 + [flagged] * 2
    assert statement["page"]["held"] == [held]
    assert packaged["held"] == [held] * 2
    # The statement window draws no multi-select at all; its rows offer the same buttons.
    assert by_kind(statement["studio"]["true"]) == [only_reject] * 4 + [{**flagged, "box": False}]
    assert statement["studio"]["held"] == [{**held, "box": False}]


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
def test_an_older_statement_page_names_no_tier_either():
    """Review round 1: a statement saved before 5.6 carries no tier and is read under its own rules (T10), in the page's
    words: a credit its rules read as revenue is tagged "Revenue", one awaiting review "Review required" (5.4's
    unverified deposit), and its review view counts the deposits to review. No "Verified" or "Unverified" anywhere.
    (Stored before the tiers, its Zelle deposit was excluded under the policy of its day, and is shown as analysed.)"""
    from tests.test_webapp_true_revenue import _untiered

    served = _served(_untiered(_payload(ROWS)))
    assert served["metrics"]["unverified_deposit_count"] == 4 and served["metrics"]["revenue_review_items"] is None
    result = run_dashboard(PAGE_TEXT + _open("s", served) + STATEMENT_WALK + r"""
navigate("review"); look();
const review = {filter: transactionFilter, count: els.transactionCount.textContent, badge: els.reviewCount.textContent};
console.log(JSON.stringify({text: seen.join("\n"), glyphs: [...seenGlyphs], ledger, review}));
""")
    assert _tier_words(result["text"]) == []
    assert not {"VER", "CNT"} & set(result["glyphs"])
    tag_words = {"revenue": "Revenue", "review_required": "Review required", "non_revenue": "Non-revenue"}
    tags = {description: tag for description, tag in _tags(result["ledger"]) if description in OLDER_TIERS}
    assert tags == {description: tag_words[state] for description, state in OLDER_TIERS.items()}
    assert result["review"] == {"filter": "unverified_deposit", "count": "4 deposits to review", "badge": "4"}
    # With none left to review, the empty view says so in the same words.
    settled = _served(_untiered(_payload([ROWS[0], ROWS[3]])))
    empty = run_dashboard(_open("s", settled) + r"""
navigate("review");
console.log(JSON.stringify({count: els.transactionCount.textContent,
  text: els.transactionTable.innerHTML.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()}));
""")
    assert empty["count"] == "0 deposits to review"
    assert empty["text"] == ("No transactions found No deposit is left to review. Analysed with older classification "
                             "rules: Re-analyze to compute true revenue.")


@needs_node
def test_a_review_refusal_that_names_a_tier_reads_in_the_page_words():
    """Review round 1: the server's two refusal texts that name the tiers (a confirm on a credit a rule verified, a
    review of a credit that is not reviewable) reach the screen in the page's words, in the row's alert and in the
    multi-select's notification; any other refusal reads as the server wrote it. The server's texts are unchanged."""
    from webapp.app import _DECLARED_REVIEW_REFUSALS

    verified, unreviewable = ("a credit a rule verified can only be marked non-revenue",
                              "only automatically unverified deposits can be reviewed")
    assert {verified, unreviewable} <= set(_DECLARED_REVIEW_REFUSALS)
    served = _served(_payload(ROWS))
    responses = {"/analysis/s/revenue-review": {"status": 400, "json": {"error": verified}},
                 "/analysis/s/revenue-reviews": {"status": 400, "json": {"error": unreviewable}}}
    result = run_dashboard(PAGE_TEXT + _open("s", served) + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
""" + r"""
const alerts = []; window.alert = (message) => alerts.push(message);
const said = []; notify = (message, tone) => said.push([message, tone]);
const words = [reviewRefusalWords("a credit a rule verified can only be marked non-revenue"),
  reviewRefusalWords("only automatically unverified deposits can be reviewed"), reviewRefusalWords("fabricated refusal")];
showMainRevenueEvidence("all");
const attrsOf = (tag) => Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
const tags = (pattern) => [...els.transactionTable.innerHTML.matchAll(pattern)].map((m) => attrsOf(m[1]));
const button = fakeElement("row");
Object.assign(button.attributes, tags(/<button class="table-action[^"]*" type="button"([^>]*)>/g)
  .find((attrs) => attrs["data-revenue-review-action"] === "confirm"));
await submitRevenueReview(button); await settle();
const box = fakeElement("box"); box.checked = true; box.closest = () => box;
Object.assign(box.attributes, tags(/<input type="checkbox" class="tx-select"([^>]*)>/g)[0]);
els.transactionTable.listeners.change[0]({target: box});
const press = fakeElement("confirm"); press.attributes["data-bulk-review"] = "confirm"; press.closest = () => press;
els.bulkReviewBar.listeners.click[0]({target: press}); await settle(); await settle();
console.log(JSON.stringify({words, alerts, red: said.filter(([, tone]) => tone === "red").map(([message]) => message)}));
""")
    assert result["words"] == [
        "This deposit is already in True revenue: it can only be marked non-revenue. Open the statement again to see "
        "where it stands.",
        "This deposit can no longer be reviewed. Open the statement again to see where it stands.",
        "fabricated refusal"]
    assert result["alerts"] == [result["words"][0]]
    assert len(result["red"]) == 1 and result["red"][0].endswith(": " + result["words"][1])
    assert _tier_words("\n".join(result["alerts"] + result["red"])) == []


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


# ----------------------------------------------------------------------------------------------- the downloads

#: What names a hidden tier in a download: its figures' and aliases' names, its codes and the words the backend writes
#: about it. A lender's own vocabulary ("No verified lender ... matched", `verified_lender_alias`) is not a revenue tier.
HIDDEN_IN_DOWNLOADS = re.compile(
    r"verified_revenue|unverified_deposit|counted_flagged|potential_revenue|confirmed_true_revenue|\"verified\"|"
    r"verified plus counted|verified classified|Verified revenue|never verified|counted and flagged|counted, not verified|"
    r"zelle_prior:verified|_never_verified|verified_(named|operating|payer|wire|auto)")
TIERS_SHOWN = {"true_revenue", "excluded_pending_review", "non_revenue", ""}
#: The credits of ROWS in True revenue, and the one of them flagged as a large deposit to source.
TRUE_DESCRIPTIONS = ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "MOBILE DEPOSIT", "WIRE TRANSFER FROM SAMPLE TRADING LLC",
                     "ZELLE FROM JOHN SAMPLE", "BRANCH DEPOSIT")
LARGE = "WIRE TRANSFER FROM SAMPLE TRADING LLC"


def _csv(text):
    csv.field_size_limit(10_000_000)
    return list(csv.reader(io.StringIO(text)))


def _hidden_cells(rows):
    return [row for row in rows for cell in row
            if (isinstance(cell, str) and (HIDDEN_IN_DOWNLOADS.search(cell) or cell == "verified"))]


@pytest.fixture
def stored_jobs(tmp_path, monkeypatch):
    """Two fabricated statements stored as done jobs, the way an upload leaves them, read under the default settings (a
    scratch settings folder)."""
    from webapp.app import store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    jobs = []
    for month in (3, 4):
        job = store.create(f"fabricated-{month}.pdf")
        store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=_payload(ROWS, month))
        jobs.append(job.id)
    return jobs


def test_the_statement_csv_and_excel_drop_the_hidden_tiers_and_the_json_keeps_them(stored_jobs):
    from webapp.app import app

    client = app.test_client()
    job = stored_jobs[0]
    rows = _csv(client.get(f"/download/{job}/csv").get_data(as_text=True))
    sheet = _sheet_rows(client.get(f"/download/{job}/xlsx").get_data())
    for name, table in (("csv", rows), ("xlsx", sheet)):
        assert _hidden_cells(table) == [], name
        cells = {(row[0], row[1]): row[2] for row in table if len(row) == 3}
        # True, held and non-revenue stay, with every figure as it was.
        assert float(cells[("metrics", "true_revenue_total")]) == 21750.0, name
        assert float(cells[("metrics", "excluded_pending_review_total")]) == 900.0, name
        assert float(cells[("metrics", "non_revenue_total")]) == 100.0, name
        assert float(cells[("metrics", "maximum_revenue")]) == 22650.0, name
        assert cells[("metrics", "eligible_deposit_definition")] == (
            "true revenue: posted credits minus known non-revenue and the deposits held for review"), name
        # Held reasons and the non-revenue breakdown stay; no counted reason row.
        assert float(cells[("revenue_tier", "excluded_pending_review.financing_named_payer.total")]) == 900.0, name
        assert not any(field.startswith("counted_flagged") for section, field in cells if section == "revenue_tier")
        # Zelle under Yes: its part in True revenue, one figure.
        assert float(cells[("revenue_tier", "zelle_deposits.true_revenue.total")]) == 250.0, name
        assert float(cells[("revenue_tier", "zelle_deposits.true_revenue.count")]) == 1, name
        # A large deposit to source keeps its row, without its counted reason.
        assert ("large_unsourced_deposit_1", "revenue_tier_reason") not in cells, name
        assert float(cells[("large_unsourced_deposit_1", "share_of_true_percent")]) == 92.0, name
        # The posted-credit table: one tier a credit in True revenue, its reason only where it is held or out.
        credits = [row for row in table if row[0] == "posted_credit"]
        assert credits[0][2:] == ["date", "description", "amount", "currency", "tier", "reason", "review_status",
                                  "zelle"], name
        tiers = {row[3]: (row[6], row[7]) for row in credits[1:]}
        assert {tier for tier, _reason in tiers.values()} <= TIERS_SHOWN, name
        assert tiers["NORTHWIND SUPPLY LLC DES:PAYMENT ID:1"] == ("true_revenue", ""), name
        assert tiers["MOBILE DEPOSIT"] == ("true_revenue", ""), name
        assert tiers["FABRIKAM FUNDING LLC DES:PAYMENT ID:1"] == ("excluded_pending_review", "financing_named_payer"), name
        assert sum(float(row[4]) for row in credits[1:] if row[6] == "true_revenue") == 21750.0, name
        # Review round 1: a credit in True revenue awaits no review, verified or counted alike (the served copy keeps a
        # counted credit `pending`); the held credit is still pending. Review round 2: so is the counted credit flagged
        # as a large deposit to source, whose section asks to source it and whose row on the page offers Confirm.
        status = {row[3]: row[8] for row in credits[1:]}
        assert {status[row[3]] for row in credits[1:] if row[6] == "true_revenue" and row[3] != LARGE} == {
            "not_required"}, name
        assert status[LARGE] == "pending", name
        assert cells[("large_unsourced_deposit_1", "description")] == LARGE, name
        assert status["FABRIKAM FUNDING LLC DES:PAYMENT ID:1"] == "pending", name
        # Review round 1: the held and non-revenue evidence keep the rule and the sentence that say why; a credit in
        # True revenue carries neither (the counted one's would say it is not confirmed).
        held = json.loads(cells[("metrics", "excluded_pending_review_evidence")])
        assert [(record["revenue_matched_rule"], record["revenue_reason"]) for record in held] == [
            ("unknown_credit_source_requires_review",
             "The posted credit source is not identified strongly enough to confirm or exclude revenue.")], name
        out = json.loads(cells[("metrics", "non_revenue_evidence")])
        assert [(record["revenue_matched_rule"], record["revenue_reason"]) for record in out] == [
            ("non_operating_credit", "Credit matched identifiable financing, own-account transfer, reward, interest, "
                                     "contribution, or other non-operating proceeds evidence.")], name
        assert out[0]["revenue_classification"] == "non_revenue", name
        in_true = json.loads(cells[("metrics", "true_revenue_evidence")])
        assert len(in_true) == 5 and not any(
            {"revenue_matched_rule", "revenue_reason", "revenue_classification"} & set(record) for record in in_true)
        assert {record["original_description"]: record["revenue_review_status"] for record in in_true} == {
            description: "pending" if description == LARGE else "not_required"
            for description in TRUE_DESCRIPTIONS}, name
        # Review round 1: the lender classifier's default sentence, on most credits, names no verified anything.
        assert not any("No verified lender" in str(cell) for row in table for cell in row), name
        assert {record["reason"] for record in in_true} >= {
            "No lender, insurance, or operational-category rule matched."}, name
    # The JSON download is the backend's: both tiers, every figure and every record field.
    served = client.get(f"/download/{job}/json").get_json()
    assert served["metrics"]["verified_revenue_total"] == 700.0
    assert served["metrics"]["counted_flagged_total"] == 21050.0
    assert served["metrics"]["counted_flagged_by_reason"]["check_deposit"]["total"] == 300.0
    assert {tx["classification"].get("revenue_tier") for tx in served["statement"]["transactions"]} >= {
        "verified", "counted_flagged"}


def test_the_package_csv_and_excel_drop_the_hidden_tiers_and_the_json_keeps_them(stored_jobs):
    from webapp.app import app

    client = app.test_client()
    ids = ",".join(stored_jobs)
    rows = _csv(client.get(f"/package_download/csv?ids={ids}").get_data(as_text=True))
    sheet = _sheet_rows(client.get(f"/package_download/xlsx?ids={ids}").get_data())
    for name, table in (("csv", rows), ("xlsx", sheet)):
        assert _hidden_cells(table) == [], name
        sections = {row[0].rsplit("_", 1)[0] for row in table if row and re.search(r"_\d+$", str(row[0]))}
        assert not sections & {"verified_revenue_evidence", "counted_flagged_evidence", "unverified_deposit_evidence"}
        assert {"true_revenue_evidence", "excluded_pending_review_evidence", "non_revenue_evidence"} <= sections, name
        # The credits in True revenue are one evidence section each: the verified one and the four counted ones of each
        # statement, every one read as True revenue and none naming a counted reason.
        true_sections = {row[0] for row in table if re.fullmatch(r"true_revenue_evidence_\d+", str(row[0]))}
        assert len(true_sections) == 10, name
        assert {row[2] for row in table if row[0] in true_sections and row[1] == "revenue_tier"} == {"true_revenue"}
        assert {row[2] for row in table if row[0] in true_sections and row[1] == "revenue_tier_reason"} == {""}
        cells = {(row[0], row[1]): row[2] for row in table if len(row) == 3}
        assert float(cells[("totals", "true_revenue_total")]) == 43500.0, name
        assert float(cells[("totals", "excluded_pending_review_total")]) == 1800.0, name
        assert float(cells[("totals", "avg_monthly_true_revenue")]) == 21750.0, name
        assert float(cells[("document_1", "true_revenue_total")]) == 21750.0, name
        assert float(cells[("revenue_tier", "zelle_deposits.true_revenue.total")]) == 500.0, name
        ledger = [row for row in table if row[0] == "package_transaction"]
        assert ledger[0][2:] == ["source_document", "source_account", "source_currency", "date", "description",
                                 "amount", "classification", "tier", "reason", "review_status", "zelle"], name
        assert {row[9] for row in ledger[1:]} <= TIERS_SHOWN, name
        held = {row[1]: row[2] for row in table if row[0] == "excluded_pending_review_evidence_1"}
        assert held["revenue_tier"] == "excluded_pending_review" and held["revenue_tier_reason"] == "financing_named_payer"
        # Review round 2: each member's large deposit to source still awaits review (its row offers Confirm); every
        # other credit in True revenue awaits none.
        in_true = [row for row in ledger[1:] if row[9] == "true_revenue"]
        assert {(row[6], row[11]) for row in in_true} == {
            (description, "pending" if description == LARGE else "not_required") for description in TRUE_DESCRIPTIONS}
        assert sum(row[6] == LARGE for row in in_true) == 2, name
        true_records = {}
        for row in table:
            if row and row[0] in true_sections:
                true_records.setdefault(int(str(row[0]).rsplit("_", 1)[1]), {})[row[1]] = row[2]
        assert {(record["original_description"], record["revenue_review_status"]) for record in true_records.values()} == {
            (description, "pending" if description == LARGE else "not_required") for description in TRUE_DESCRIPTIONS}
        # Review round 2: the section reads as one list in date order, as a statement's does, so nothing in it marks
        # where the verified credits end and the counted ones begin.
        dates = [true_records[number]["date"] for number in sorted(true_records)]
        assert dates == sorted(dates) and len(set(dates)) > 2, name
    served = client.get(f"/package_download/json?ids={ids}").get_json()
    assert served["totals"]["verified_revenue_total"] == 1400.0
    assert served["totals"]["counted_flagged_total"] == 42100.0
    assert served["verified_revenue_evidence"] and served["counted_flagged_evidence"]


def test_a_large_deposit_awaits_review_in_its_own_account_only():
    """Review round 2: a location numbers a posting within its account, so each account's `transaction:1` is its own.
    In one document of two accounts, account 2's bare DEPOSIT of 12,000.00 at `transaction:1` is a large deposit to
    source and account 1's MOBILE DEPOSIT at `transaction:1` is counted but not flagged: the statement and the package
    downloads write the first `pending` and the second `not_required`, in the posted-credit table, the package ledger
    and the True evidence alike."""
    from tests.test_large_unsourced_deposits import _package as package_of
    from tests.test_package_matching import NW_A, SENT, TRANSFER_OUT, _rows_b, _two_account_document
    from webapp.export_view import masked
    from webapp.package_export import package_csv
    from webapp.statement_export import analysis_csv

    document = _two_account_document([(1, "MOBILE DEPOSIT", 300.0), (2, NW_A, 20000.0), (3, TRANSFER_OUT, -SENT)],
                                     _rows_b(amount=12000.0))
    served = _served(document)
    records = {(index, tx["description"]): tx["classification"]
               for index, account in enumerate(served["accounts"], start=1) for tx in account["statement"]["transactions"]}
    assert records[(1, "MOBILE DEPOSIT")]["source_location"] == records[(2, "DEPOSIT")]["source_location"]
    assert records[(1, "MOBILE DEPOSIT")]["revenue_tier"] == records[(2, "DEPOSIT")]["revenue_tier"] == "counted_flagged"
    assert [item["description"] for item in served["accounts"][1]["metrics"]["large_unsourced_deposits"]] == ["DEPOSIT"]
    assert not served["accounts"][0]["metrics"].get("large_unsourced_deposits")
    expected = {("1", "MOBILE DEPOSIT"): "not_required", ("1", NW_A): "not_required", ("2", "DEPOSIT"): "pending"}

    statement = _csv(analysis_csv(masked(served)))
    credits = {(row[0].split(".")[0].removeprefix("account_"), row[3]): row[8] for row in statement
               if row[0].endswith("posted_credit") and row[1] != "columns"}
    assert {key: credits[key] for key in expected} == expected

    package = _csv(package_csv(masked(package_of(("doc", document)))))
    ledger = {(row[3], row[6]): row[11] for row in package if row[0] == "package_transaction" and row[1] != "columns"}
    assert {key: ledger[key] for key in expected} == expected
    true_records = {}
    for row in package:
        if re.fullmatch(r"true_revenue_evidence_\d+", str(row[0])):
            true_records.setdefault(row[0], {})[row[1]] = row[2]
    written = {(record["source_account"], record["original_description"]): record["revenue_review_status"]
               for record in true_records.values()}
    assert {key: written[key] for key in expected} == expected


OLDER_TIERS = {"NORTHWIND SUPPLY LLC DES:PAYMENT ID:1": "revenue", "MOBILE DEPOSIT": "review_required",
               "FABRIKAM FUNDING LLC DES:PAYMENT ID:1": "review_required", "INTERNAL TRANSFER FROM SAVINGS": "non_revenue",
               "WIRE TRANSFER FROM SAMPLE TRADING LLC": "review_required", "ZELLE FROM JOHN SAMPLE": "non_revenue",
               "BRANCH DEPOSIT": "review_required"}


def test_an_older_statement_download_names_each_credit_in_the_page_words():
    """Review round 1: a statement saved before 5.6 carries no tier, so its 5.4 state is each credit's only revenue
    reading. The downloads write it in the page's words, never 5.4's names: the ledger's tier column and each record
    read `revenue`, `review_required` (5.4's unverified deposit, the page's "Review required") or `non_revenue`, and the
    deposits to review (the page's review view and badge) are `review_required_count`, `_total` and `_evidence`, beside
    `revenue_evidence` and `non_revenue_evidence`."""
    from tests.test_webapp_true_revenue import _untiered
    from webapp.statement_export import analysis_csv, analysis_xlsx
    from analysis.served_view import displayed

    served = displayed(_untiered(_payload(ROWS)), settings={}, export=True)
    assert served["metrics"]["unverified_deposit_count"] == 4 and served["metrics"]["true_revenue_evidence"] is None
    for name, table in (("csv", _csv(analysis_csv(served))), ("xlsx", _sheet_rows(analysis_xlsx(served)))):
        assert _hidden_cells(table) == [], name
        credits = [row for row in table if row[0] == "posted_credit"]
        assert {row[3]: (row[6], row[7]) for row in credits[1:]} == {
            description: (state, "") for description, state in OLDER_TIERS.items()}, name
        cells = {(row[0], row[1]): row[2] for row in table if len(row) == 3}
        # The count its badge shows; its money is empty, as every revenue figure of a statement whose revenue is not
        # established is (audit B11, I51), the JSON download keeping it.
        assert float(cells[("metrics", "review_required_count")]) == 4.0, name
        assert cells[("metrics", "review_required_total")] == "", name
        for section in ("metrics", "detection"):
            review = json.loads(cells[(section, "review_required_evidence")])
            assert {record["original_description"]: record["revenue_classification"] for record in review} == {
                description: state for description, state in OLDER_TIERS.items() if state == "review_required"}, name
            revenue = json.loads(cells[(section, "revenue_evidence")])
            assert [(record["original_description"], record["revenue_classification"]) for record in revenue] == [
                ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "revenue")], name
            out = json.loads(cells[(section, "non_revenue_evidence")])
            assert [record["revenue_classification"] for record in out] == ["non_revenue", "non_revenue"], name
        # A deposit to review keeps the sentence that says why.
        assert {record["revenue_reason"] for record in review} >= {
            "The posted credit source is not identified strongly enough to confirm or exclude revenue."}, name


def test_a_package_mixing_an_older_statement_writes_every_credit_in_one_section():
    """Review round 1: in a package with a member saved before 5.6 the package's True revenue is N/A, yet every posted
    credit of every member is still written in one evidence section: the 5.6 member's credits in True revenue in
    `true_revenue_evidence_N` (built from the served verified and counted lists), its held ones and both members'
    non-revenue ones as before, and the older member's in `revenue_evidence_N` and `review_required_evidence_N`. Its
    ledger reads each older credit in the page's words."""
    from tests.test_webapp_true_revenue import _package as package_of
    from tests.test_webapp_true_revenue import _untiered
    from webapp.package_export import package_csv, package_xlsx

    package = package_of(_payload(ROWS), _untiered(_payload(ROWS, 4)))
    assert package["true_revenue_evidence"] is None
    assert _hidden_cells(_sheet_rows(package_xlsx(package))) == []
    table = _csv(package_csv(package))
    assert _hidden_cells(table) == []
    sections: dict[str, list[dict]] = {}
    for row in table:
        match = re.fullmatch(r"([a-z_]+_evidence)_(\d+)", str(row[0])) if len(row) == 3 else None
        if match and match[1] in {"true_revenue_evidence", "excluded_pending_review_evidence", "revenue_evidence",
                                  "review_required_evidence", "non_revenue_evidence"}:
            record = sections.setdefault(match[1], {}).setdefault(match[2], {})
            record[row[1]] = row[2]
    described = {section: sorted((record["source_job"], record["original_description"]) for record in records.values())
                 for section, records in sections.items()}
    assert described == {
        "true_revenue_evidence": sorted(("job-1", description) for description in (
            "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "MOBILE DEPOSIT", "WIRE TRANSFER FROM SAMPLE TRADING LLC",
            "ZELLE FROM JOHN SAMPLE", "BRANCH DEPOSIT")),
        "excluded_pending_review_evidence": [("job-1", "FABRIKAM FUNDING LLC DES:PAYMENT ID:1")],
        "revenue_evidence": [("job-2", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1")],
        "review_required_evidence": sorted(("job-2", description) for description, state in OLDER_TIERS.items()
                                           if state == "review_required"),
        "non_revenue_evidence": [("job-1", "INTERNAL TRANSFER FROM SAVINGS"), ("job-2", "INTERNAL TRANSFER FROM SAVINGS"),
                                 ("job-2", "ZELLE FROM JOHN SAMPLE")],
    }
    assert {record["revenue_tier"] for record in sections["true_revenue_evidence"].values()} == {"true_revenue"}
    assert {record["revenue_classification"] for record in sections["review_required_evidence"].values()} == {
        "review_required"}
    ledger = [row for row in table if row[0] == "package_transaction"]
    tiers = {(row[2], row[6]): row[9] for row in ledger[1:] if float(row[7]) > 0}
    assert {description: tier for (document, description), tier in tiers.items() if document == "statement-2.pdf"} == (
        OLDER_TIERS)
    assert {tier for (document, _description), tier in tiers.items() if document == "statement-1.pdf"} == {
        "true_revenue", "excluded_pending_review", "non_revenue"}


def _record(tier, *, state, reason=None, rule=None, sentence=None, status="not_required", signals=(), **extra):
    return {"revenue_classification": state, "revenue_initial_classification": state, "revenue_tier": tier,
            "revenue_initial_tier": tier, "revenue_tier_reason": reason, "revenue_matched_rule": rule,
            "revenue_reason": sentence, "revenue_review_status": status, "revenue_context_signals": list(signals),
            **extra}


#: (record, what the downloads write of it): a key absent from the second dict is left out.
SCRUBBED = [
    # A hold that re-tiers a counted re-statement (R3-53): the hold's own label, no "never verified".
    (_record("excluded_pending_review", state="unverified_deposit", reason="payer_also_debited",
             rule="insurer_customer_payment_requires_review", status="pending",
             sentence="An insurer pays the business for its work (REPAIR): never verified, and held for review (The payer "
                      "is also debited in this statement)."),
     {"revenue_tier": "excluded_pending_review", "revenue_matched_rule": "insurer_customer_payment_requires_review",
      "revenue_reason": "An insurer pays the business for its work (REPAIR): held for review (The payer is also debited "
                        "in this statement).", "revenue_review_status": "pending"}),
    # The $1 floor's hold of a verified credit.
    (_record("excluded_pending_review", state="unverified_deposit", reason="micro_deposit", status="pending",
             rule="credit_under_micro_deposit_floor",
             sentence="A credit under $1 is never verified and never counted (the absolute micro-deposit floor): the rule "
                      "that read it (named_payer_company_form) is overruled, and it is held for review."),
     {"revenue_matched_rule": "credit_under_micro_deposit_floor",
      "revenue_reason": "A credit under $1 is never counted in True revenue (the absolute micro-deposit floor): the rule "
                        "that read it (named_payer_company_form) is overruled, and it is held for review."}),
    # The holder's own push a rule verified: its rule names the tier and is left out; its sentence is kept without it.
    (_record("excluded_pending_review", state="unverified_deposit", reason="holder_name", status="pending",
             rule="holder_own_push_never_verified",
             sentence="The row's originator is its own receiver: the holder moves its own money in, which is never "
                      "revenue and never verified; the rule that read it (x) is overruled, and it is held for review."),
     {"revenue_reason": "The row's originator is its own receiver: the holder moves its own money in, which is never "
                        "revenue; the rule that read it (x) is overruled, and it is held for review."}),
    # A Zelle deposit the policy excluded, which the rules verified or counted: they read it as True revenue.
    (_record("non_revenue", state="non_revenue", reason="zelle_excluded", rule="zelle_policy",
             signals=("credit_direction", "zelle_policy", "zelle_prior:verified:"),
             sentence="A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                      "§19.1); the rules read it as: Verified revenue."),
     {"revenue_classification": "non_revenue", "revenue_initial_classification": "non_revenue",
      "revenue_matched_rule": "zelle_policy",
      "revenue_context_signals": ["credit_direction", "zelle_policy", "zelle_prior:true_revenue"],
      "revenue_reason": "A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                        "§19.1); the rules read it as: True revenue."}),
    (_record("non_revenue", state="non_revenue", reason="zelle_excluded", rule="zelle_policy",
             signals=("zelle_prior:counted_flagged:check_deposit",),
             sentence="A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                      "§19.1); the rules read it as: Check deposit."),
     {"revenue_classification": "non_revenue", "revenue_initial_classification": "non_revenue",
      "revenue_matched_rule": "zelle_policy",
      "revenue_reason": "A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                        "§19.1); the rules read it as: True revenue."}),
    # ... and one the rules held keeps the hold's label.
    (_record("non_revenue", state="non_revenue", reason="zelle_excluded", rule="zelle_policy",
             signals=("zelle_prior:excluded_pending_review:holder_name",),
             sentence="A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                      "§19.1); the rules read it as: From the holder's own name or brand."),
     {"revenue_classification": "non_revenue", "revenue_initial_classification": "non_revenue",
      "revenue_matched_rule": "zelle_policy",
      "revenue_reason": "A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec "
                        "§19.1); the rules read it as: From the holder's own name or brand."}),
    # A verified credit a reviewer rejected: its sentence stays, its rule (named for the tier) does not.
    (_record("non_revenue", state="non_revenue", rule="verified_named_payer_company_form", status="rejected",
             sentence="A named company pays the business by ACH or EFT.", revenue_initial_classification="verified_revenue",
             revenue_initial_tier="verified"),
     {"revenue_classification": "non_revenue", "revenue_initial_tier": "true_revenue",
      "revenue_reason": "A named company pays the business by ACH or EFT.", "revenue_review_status": "rejected"}),
    # A sentence still naming a tier after the rewrites is left out rather than written.
    (_record("non_revenue", state="non_revenue", rule="non_operating_credit",
             sentence="Maintained operating source 'X' printed; the credit is verified as operating revenue."),
     {"revenue_classification": "non_revenue", "revenue_initial_classification": "non_revenue",
      "revenue_matched_rule": "non_operating_credit"}),
    # A counted credit awaits no review in the downloads, and names no rule or sentence; nor does a verified one.
    (_record("counted_flagged", state="unverified_deposit", reason="check_deposit", status="pending",
             rule="deposit_source_requires_review", sentence="The credit is a deposit or incoming transfer without enough "
                                                             "evidence to confirm operating revenue."),
     {"revenue_tier": "true_revenue", "revenue_initial_tier": "true_revenue", "revenue_tier_reason": None,
      "revenue_review_status": "not_required"}),
    (_record("verified", state="verified_revenue", rule="verified_named_payer_company_form",
             sentence="A named company pays the business by ACH or EFT."),
     {"revenue_tier": "true_revenue", "revenue_review_status": "not_required"}),
    # A deposit a package pass took out of True names the tier it had as True revenue.
    (_record("non_revenue", state="non_revenue", rule="returned_deposit_cross_statement",
             package_match={"kind": "returned_deposit", "moved": True, "tier_before": "counted_flagged",
                            "reason_before": "check_deposit"}),
     {"revenue_classification": "non_revenue", "revenue_initial_classification": "non_revenue",
      "revenue_matched_rule": "returned_deposit_cross_statement",
      "revenue_reason": None,
      "package_match": {"kind": "returned_deposit", "moved": True, "tier_before": "true_revenue",
                        "reason_before": None}}),
]


@pytest.mark.parametrize(("record", "written"), SCRUBBED)
def test_a_record_s_reason_is_kept_where_it_names_no_hidden_tier(record, written):
    """Review round 1: the downloads keep a held or non-revenue credit's rule and sentence, the words that say why it is
    out of True revenue, rewriting only the words that name a hidden tier; a rule or sentence still naming one is left
    out. A credit in True revenue carries neither, nor its 5.4 state."""
    from webapp.export_view import downloads_view

    view = downloads_view(record)
    for key in ("revenue_reason", "revenue_matched_rule", "revenue_classification", "revenue_initial_classification"):
        assert (key in view) == (key in written), key
    for key, value in written.items():
        assert view[key] == value, key
    assert not HIDDEN_IN_DOWNLOADS.search(json.dumps(view))


def test_a_download_on_the_verified_basis_names_it_without_the_word():
    from webapp.statement_export import analysis_csv
    from analysis.served_view import displayed

    from analysis.revenue import rebuild_serialized_revenue_views

    payload = _payload(ROWS)
    payload["metrics"]["withholding_denominator_mode"] = "verified_revenue"
    rebuild_serialized_revenue_views(payload)
    served = displayed(payload, settings={}, export=True)
    rows = _csv(analysis_csv(served))
    assert _hidden_cells(rows) == []
    cells = {(row[0], row[1]): row[2] for row in rows if len(row) == 3}
    assert cells[("metrics", "withholding_denominator_mode")] == "narrower_revenue_basis"
    assert cells[("metrics", "withholding_denominator_label")] == "Narrower revenue basis"
    assert cells[("metrics", "eligible_deposit_definition")] == "a part of true revenue only"
    assert float(cells[("metrics", "withholding_denominator")]) == 700.0
    assert float(cells[("metrics", "withholding_rate")]) == served["metrics"]["withholding_rate"]
    # Review round 2: the options list the statement's own mode under its downloads name, in the backend's order (the
    # cell is the list as the flat sheet writes it: a tuple here, a JSON list once a stored job is read back).
    def modes(cell):
        return re.findall(r"[a-z_]+", cell)

    assert modes(cells[("metrics", "withholding_denominator_options")]) == [
        "legacy_eligible_deposits", "narrower_revenue_basis", "true_revenue"]
    # The served copy, which the JSON download writes, is the backend's.
    assert served["metrics"]["withholding_denominator_mode"] == "verified_revenue"
    assert "verified_revenue" in served["metrics"]["withholding_denominator_options"]
    # A statement on any other basis lists no narrower basis: nothing on screen offers it.
    true_basis = {(row[0], row[1]): row[2] for row in _csv(analysis_csv(displayed(_payload(ROWS), settings={},
                                                                                    export=True))) if len(row) == 3}
    assert modes(true_basis[("metrics", "withholding_denominator_options")]) == [
        "legacy_eligible_deposits", "true_revenue"]
    # Review round 1: inside a note the basis is named mid-sentence, in lower case, as the page's rate note names it.
    unpaid = _payload([row for row in ROWS if not row[1].startswith("NORTHWIND")])
    unpaid["metrics"]["withholding_denominator_mode"] = "verified_revenue"
    rebuild_serialized_revenue_views(unpaid)
    assert "withholding rate is unavailable because Verified revenue is zero or missing" in unpaid["metrics"]["notes"]
    unpaid_rows = _csv(analysis_csv(displayed(unpaid, settings={}, export=True)))
    notes = json.loads({(row[0], row[1]): row[2] for row in unpaid_rows if len(row) == 3}[("metrics", "notes")])
    assert "withholding rate is unavailable because the narrower revenue basis is zero or missing" in notes
    assert not any("Verified" in note or "Narrower" in note for note in notes)
