"""Audit round 3, R3-B24 (R3-16; true revenue spec §10.1, §10.6, §10.7; standard G7, P22): the dashboard names a large
unsourced counted deposit, for information only. The True card adds "Large deposits to source: N · $X (each $10,000 or
more and over 25% of True)" (the owner's request of 2026-10-11 took out its "counted, not verified"); the Revenue
evidence table adds one row, after the held reasons, whose "Source it" button filters the ledger to the flagged rows ("largeDeposit"); each flagged row's reason
cell asks for its source on the statement page, the statement window and the package ledger; both copied memos carry a
clause after the revenue sentence. The review badge, the Held for Review view, the pill and the decisions do not read
it.

The whole webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated statements only:
tests/test_large_unsourced_deposits' CONTOSO CAFE LLC months (2033), analysed by the real per-account path."""
from __future__ import annotations

import json

import pytest

from tests.test_large_unsourced_deposits import (
    CHECK, DEPOSIT, L1, SQUARE, WIRE, _months, _package, _payload, _served, _squares, _without_flag,
)
from tests.test_webapp_true_revenue_ui import METRIC_ROWS, PACKAGE_MATCH_VIEW, _open
from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

FACT = "Large deposits to source: 2 · $270,000.00 (each $10,000.00 or more and over 25% of True)"
NOTE_39 = "Large deposit: 39.0% of True revenue. Ask for its source."
NOTE_31 = "Large deposit: 31.2% of True revenue. Ask for its source."

#: Each ledger row's description and its large-deposit note, if any.
LEDGER = PACKAGE_MATCH_VIEW + r"""
const largeRows = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
  .map((row) => ({desc: unescapeHtml((row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1] || ""),
    large: [...row.matchAll(/<div class="tx-reason tx-large-deposit">([^<]*)<\/div>/g)].map((m) => unescapeHtml(m[1])),
    review: [/data-revenue-review-action="confirm"/.test(row), /data-revenue-review-action="reject"/.test(row)],
    box: /class="tx-select"/.test(row), decided: (row.match(/<span>(Confirmed as revenue|Marked non-revenue)<\/span>/) || [])[1] || null}))
  .filter((row) => row.desc);
const evidence = () => cells(els.revenueTable.innerHTML);
const evidenceFilters = () => [...els.revenueTable.innerHTML.matchAll(/data-revenue-filter="([^"]+)"/g)].map((m) => m[1]);
"""


def _statement_view(served, extra=""):
    return run_dashboard(METRIC_ROWS + LEDGER + _open("s", served) + extra)


@needs_node
def test_u1_u2_u3_the_statement_page_names_the_flag_on_its_card_its_evidence_row_and_its_rows():
    served = _served(_payload(L1))
    result = _statement_view(served, """
const all = largeRows(els.transactionTable.innerHTML);
const evidenceRows = evidence();
const filters = evidenceFilters();
const large = filtered('largeDeposit');
console.log(JSON.stringify({note: trueNote(), evidenceRows, filters, large, all,
  flaggedRows: largeRows(els.transactionTable.innerHTML)}));
""")
    # U1: the True card's fact, before the debit flags (none here).
    assert result["note"].endswith(" · " + FACT)
    # U2: one evidence row after the counted and held reasons and before Non-Revenue, with its chip.
    filters = result["filters"]
    assert filters.index("largeDeposit") > filters.index("excluded_pending_review")
    assert filters.index("largeDeposit") < filters.index("non_revenue")
    assert all(not item.startswith(("counted_flagged:", "excluded_pending_review:"))
               for item in filters[filters.index("largeDeposit"):])
    row = next(row for row in result["evidenceRows"] if row[0] == "Large deposits to source")
    assert row[1:3] == ["2", "$270,000.00"] and "Source it" in row[3]
    assert result["large"] == {"count": "2 large deposits to source", "rows": [DEPOSIT, WIRE]}
    # U3: each flagged row asks for its source; every other row reads as before. A flagged row keeps Confirm Revenue,
    # Mark Non-Revenue and its multi-select box: the reviewer sources it, then confirms it, and it leaves the flag. The
    # owner's request of 2026-10-11 (spec §10's head, its review rounds 1 and 2) took Confirm and the box off every
    # other credit in True revenue, a counted one included (CHECK, counted and under 25% of True, so not flagged).
    notes = {row["desc"]: row["large"] for row in result["all"]}
    assert notes[DEPOSIT] == [NOTE_39] and notes[WIRE] == [NOTE_31]
    assert all(not notes[desc] for desc in notes if desc not in (DEPOSIT, WIRE))
    flagged = [row for row in result["flaggedRows"] if row["desc"] in (DEPOSIT, WIRE)]
    assert len(flagged) == 2 and all(row["review"] == [True, True] and row["box"] for row in flagged)
    check = next(row for row in result["all"] if row["desc"] == CHECK)
    assert check["review"] == [False, True] and not check["box"]
    assert all(row["review"] == [False, True] and not row["box"] for row in result["all"] if row["desc"] == SQUARE)


@needs_node
def test_review_round_2_confirm_on_a_flagged_row_clears_its_flag(tmp_path, monkeypatch):
    """Review round 2 of the owner's request of 2026-10-11: the page's path to clear a large deposit to source is kept.
    The reviewer sources the deposit and presses its Confirm Revenue; the server (the real review route) confirms it,
    and the redrawn page lists one flag fewer: the evidence row's count and total, the True card's fact and the row's
    note follow, the confirmed row reads its decision, and the other flagged row keeps its controls. With both
    confirmed, no "Large deposits to source" is left anywhere on the page."""
    from webapp.app import app, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    job = store.create("fabricated-large.pdf")
    store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=_payload(L1))
    client = app.test_client()
    served = client.get(f"/analysis/{job.id}").get_json()["analysis"]
    url = f"/analysis/{job.id}/revenue-review"
    first = client.post(url, json={"source_location": "transaction:4", "decision": "confirm"})
    second = client.post(url, json={"source_location": "transaction:12", "decision": "confirm"})
    assert first.status_code == 200 and second.status_code == 200
    # The backend moves the flag (the count and total of the served copy) and no revenue figure.
    one_left, none_left = first.get_json()["analysis"]["metrics"], second.get_json()["analysis"]["metrics"]
    assert served["metrics"]["large_unsourced_deposit_count"] == 2 and one_left["large_unsourced_deposit_count"] == 1
    assert "large_unsourced_deposit_count" not in none_left or not none_left["large_unsourced_deposit_count"]
    assert one_left["true_revenue_total"] == none_left["true_revenue_total"] == served["metrics"]["true_revenue_total"]
    press = r"""
const pressConfirm = async (desc) => {
  const row = [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((m) => m[1])
    .find((html) => html.includes(`<td class="tx-desc">${desc}</td>`));
  const attrs = Object.fromEntries([...row.match(/<button[^>]*data-revenue-review-action="confirm"[^>]*>/)[0]
    .matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
  const button = fakeElement("confirm"); Object.assign(button.attributes, attrs);
  await submitRevenueReview(button); await settle();
};
const snapshot = () => ({note: trueNote(), evidence: evidence(), rows: largeRows(els.transactionTable.innerHTML)});
"""
    result = run_dashboard(METRIC_ROWS + LEDGER + _open(job.id, served) + press + f"""
showMainRevenueEvidence("all");
const before = snapshot();
FAKE_RESPONSES[{json.dumps(url)}] = {{json: {json.dumps(first.get_json())}}};
await pressConfirm({json.dumps(DEPOSIT)});
const afterOne = snapshot();
FAKE_RESPONSES[{json.dumps(url)}] = {{json: {json.dumps(second.get_json())}}};
await pressConfirm({json.dumps(WIRE)});
const afterBoth = snapshot();
console.log(JSON.stringify({{before, afterOne, afterBoth, posts: REQUESTS.filter((r) => r.method === "POST")
  .map((r) => JSON.parse(r.body))}}));
""")
    assert result["posts"] == [{"source_location": "transaction:4", "decision": "confirm"},
                               {"source_location": "transaction:12", "decision": "confirm"}]

    def flag_row(snapshot):
        return next((row[1:3] for row in snapshot["evidence"] if row[0] == "Large deposits to source"), None)

    def row_of(snapshot, desc):
        return next(row for row in snapshot["rows"] if row["desc"] == desc)

    assert flag_row(result["before"]) == ["2", "$270,000.00"]
    assert result["before"]["note"].endswith(" · " + FACT)
    # One confirmed: one flag left, the confirmed row reads its decision and asks for nothing.
    assert flag_row(result["afterOne"]) == ["1", "$120,000.00"]
    assert result["afterOne"]["note"].endswith(
        " · Large deposits to source: 1 · $120,000.00 (each $10,000.00 or more and over 25% of True)")
    deposit = row_of(result["afterOne"], DEPOSIT)
    assert deposit["large"] == [] and deposit["decided"] == "Confirmed as revenue" and not deposit["box"]
    wire = row_of(result["afterOne"], WIRE)
    assert wire["large"] == [NOTE_31] and wire["review"] == [True, True] and wire["box"]
    # Both confirmed: no flag anywhere on the page.
    assert flag_row(result["afterBoth"]) is None
    assert "Large deposits" not in result["afterBoth"]["note"]
    assert all(row["large"] == [] for row in result["afterBoth"]["rows"])
    assert row_of(result["afterBoth"], WIRE)["decided"] == "Confirmed as revenue"


@needs_node
def test_u2_the_evidence_row_carries_its_chip_class():
    served = _served(_payload(L1))
    html = run_dashboard(_open("s", served) + "console.log(JSON.stringify(els.revenueTable.innerHTML));")
    row = next(part for part in html.split("<tr") if 'data-revenue-filter="largeDeposit"' in part)
    assert row.lstrip().startswith('class="evidence-flag-row"')
    assert "Source it" in row and 'aria-label="Show the large deposits to source"' in row


@needs_node
def test_u3_the_statement_window_names_its_rows_too():
    from tests.test_webapp_studio_views import _serve

    served = _served(_payload(L1))
    result = run_dashboard(METRIC_ROWS + LEDGER + _serve(s=served) + """
openStatementModal('s'); await settle();
const before = largeRows(els.statementModalTransactions.innerHTML);
showModalRevenueEvidence('largeDeposit');
console.log(JSON.stringify({before, after: largeRows(els.statementModalTransactions.innerHTML),
  header: els.statementModalTransactionCount.textContent,
  evidence: [...els.statementModalRevenue.innerHTML.matchAll(/data-modal-revenue-filter="([^"]+)"/g)].map((m) => m[1])}));
""")
    notes = {row["desc"]: row["large"] for row in result["before"]}
    assert notes[DEPOSIT] == [NOTE_39] and notes[WIRE] == [NOTE_31]
    assert [row["desc"] for row in result["after"]] == [DEPOSIT, WIRE]
    assert result["header"] == "2 large deposits to source"
    assert "largeDeposit" in result["evidence"]


@needs_node
def test_u3_u4_the_package_page_names_each_member_s_flags_and_its_memo_its_clause():
    march, april = _months()
    package = _package(("mar", march), ("apr", april))
    result = run_dashboard(METRIC_ROWS + LEDGER + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const all = largeRows(els.transactionTable.innerHTML);
const large = filtered('largeDeposit');
generateSummary();
console.log(JSON.stringify({{note: trueNote(), all, large, memo: els.summaryBox.textContent, evidence: evidence()}}));
""")
    assert result["note"].endswith(
        " · Large deposits to source: 3 · $300,000.00 (each $10,000.00 or more and over 25% of its statement's True)")
    notes = {row["desc"]: row["large"] for row in result["all"] if row["large"]}
    assert notes == {
        DEPOSIT: ["Large deposit: 50.8% of its statement's True revenue. Ask for its source."],
        WIRE: ["Large deposit: 40.7% of its statement's True revenue. Ask for its source."],
        CHECK: ["Large deposit: 54.5% of its statement's True revenue. Ask for its source."],
    }
    assert result["large"]["count"] == "3 large deposits to source"
    assert sorted(result["large"]["rows"]) == sorted([DEPOSIT, WIRE, CHECK])
    row = next(row for row in result["evidence"] if row[0] == "Large deposits to source")
    assert row[1:3] == ["3", "$300,000.00"]
    assert " 3 large deposits to source: $300,000.00 (each over 25% of its statement's True revenue). " in result["memo"]
    # After the revenue sentence, before the gross credits.
    memo = result["memo"]
    assert memo.index("large deposits to source") > memo.index("non-revenue")
    assert memo.index("large deposits to source") < memo.index("average monthly gross credits")


MEMO = "generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));"


@needs_node
def test_u4_the_statement_memo_carries_its_clause_after_the_revenue_sentence():
    many = run_dashboard(_open("s", _served(_payload(L1))) + MEMO)
    assert ("non-revenue $0.00 ($0.00 a month). 2 large deposits to source: $270,000.00 (each over 25% of True "
            "revenue). Average daily balance") in many
    one = _served(_payload([*_squares(range(1, 12)), (12, SQUARE, 2496.0), (14, DEPOSIT, 10000.0)]))
    assert one["metrics"]["large_unsourced_deposit_count"] == 1
    single = run_dashboard(_open("s", one) + MEMO)
    assert ". 1 large deposit to source: $10,000.00, 25.0% of True revenue. Average daily balance" in single
    none = run_dashboard(_open("s", _served(_payload([*_squares(), (6, DEPOSIT, 4000.0)]))) + MEMO)
    assert "large deposit" not in none


def _money(value):
    assert value >= 0
    return f"${value:,.2f}"


@needs_node
@pytest.mark.parametrize("flagged", [False, True], ids=["no-flag", "flagged"])
def test_review_round_1_the_package_memo_keeps_its_gross_credits_sentence(flagged):
    """R3-B24 review round 1 (finding 1): the clause is inserted before the gross credits, and the package memo's
    "average monthly gross credits, $Y average monthly cash flow, " keeps its space, with or without a flag; the flag's
    clause is the only difference from the memo of the same package without the keys."""
    if flagged:
        march, april = _months()
    else:
        march = _payload([*_squares(), (6, DEPOSIT, 4000.0)], month=3)
        april = _payload([*_squares(), (6, DEPOSIT, 3000.0)], month=4)
    package = _package(("mar", march), ("apr", april))
    assert ("large_unsourced_deposits" in package) is flagged
    totals = package["totals"]
    render = "currentJobIds = ['mar', 'apr']; renderPackageAnalysis({}); " + MEMO
    memo = run_dashboard(render.format(json.dumps(package)))
    gross = f"{_money(totals['avg_monthly_credits'])} average monthly gross credits, "
    assert gross + f"{_money(totals['avg_monthly_cash_flow'])} average monthly cash flow, " in memo
    assert "gross credits,$" not in memo
    plain = run_dashboard(render.format(json.dumps(_without_flag(package))))
    assert plain.count(gross) == 1 and plain.index(gross) > plain.index("non-revenue")
    clause = "3 large deposits to source: $300,000.00 (each over 25% of its statement's True revenue). "
    assert memo == (plain.replace(gross, clause + gross, 1) if flagged else plain)


#: What the flag must never move on a page: the review badge, the credit cards other than True, the pill and the
#: decision.
UNMOVED = METRIC_ROWS + r"""
const unmoved = () => ({badge: [els.reviewCount.hidden, els.reviewCount.textContent], pill: els.decisionPill.textContent,
  cards: metricRows(els.metricsGrid.innerHTML).filter((row) => row.label !== "True Revenue"),
  decision: currentAnalysis && !currentAnalysis.package ? accountDecision(currentAnalysis) : null,
  held: tierReasonEntries(currentAnalysis && currentAnalysis.package ? packageRevenueFlags(currentAnalysis.package.totals)
    : (currentAnalysis || {}).metrics, "excluded_pending_review")});
"""


@needs_node
@pytest.mark.parametrize("rows", [L1, [*_squares(), (24, SQUARE, 150000.0),
                                       (6, "WIRE TRANSFER IN REF 000000000", 150000.0), (16, DEPOSIT, 150000.0)]])
def test_u5_the_badge_the_held_view_the_pill_and_the_decision_do_not_read_the_flag(rows):
    served = _served(_payload(rows))
    assert served["metrics"]["large_unsourced_deposit_count"] >= 1
    plain = _without_flag(served)
    script = UNMOVED + _open("s", served) + "const flagged = unmoved();\n" + _open("t", plain) + """
console.log(JSON.stringify({flagged, plain: unmoved()}));
"""
    result = run_dashboard(script)
    assert result["flagged"] == result["plain"]


@needs_node
def test_u5_the_package_decision_and_badge_do_not_read_the_flag():
    march, april = _months()
    package = _package(("mar", march), ("apr", april))
    assert package["totals"]["large_unsourced_deposit_count"] == 3
    result = run_dashboard(UNMOVED + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const flagged = unmoved();
renderPackageAnalysis({json.dumps(_without_flag(package))});
console.log(JSON.stringify({{flagged, plain: unmoved()}}));
""")
    assert result["flagged"] == result["plain"]


@needs_node
def test_u6_a_refused_package_shows_the_count_alone():
    march, april = _months("CAD")
    package = _package(("mar", march), ("apr", april))
    assert package["totals"]["large_unsourced_deposit_total"] is None
    result = run_dashboard(METRIC_ROWS + LEDGER + f"""
const pkg = {json.dumps(package)};
currentJobIds = ['mar', 'apr']; renderPackageAnalysis(pkg);
generateSummary();
console.log(JSON.stringify({{facts: packageRevenueFacts(pkg.totals, null), memo: els.summaryBox.textContent,
  evidence: evidence()}}));
""")
    # Audit round 3, final review (R3-FF), F6: a refused package's members differ in unit, so the floor has none.
    assert "Large deposits to source: 3 (each 10,000.00 or more and over 25% of its statement's True)" in result["facts"]
    assert " 3 large deposits to source (each over 25% of its statement's True revenue). " in result["memo"]
    row = next(row for row in result["evidence"] if row[0] == "Large deposits to source")
    assert row[1:3] == ["3", "N/A"]


@needs_node
def test_a_payload_without_the_flag_shows_nothing_new():
    served = _served(_payload([*_squares(), (6, DEPOSIT, 4000.0)]))
    result = _statement_view(served, """
console.log(JSON.stringify({note: trueNote(), filters: evidenceFilters(), large: filtered('largeDeposit'),
  memo: (generateSummary(), els.summaryBox.textContent)}));
""")
    assert "Large deposits" not in result["note"] and "largeDeposit" not in result["filters"]
    assert result["large"] == {"count": "0 large deposits to source", "rows": []}
    assert "large deposit" not in result["memo"]


def test_the_words_live_in_one_place():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    assert 'const LARGE_DEPOSIT_WORDS = "Large deposits to source";' in script
    assert 'const LARGE_DEPOSIT_FILTER = "largeDeposit";' in script
    assert script.count('"Large deposits to source"') == 1
    # The badge, the Held view and the decisions never read the served keys.
    for function in ("function reviewBadgeValue(", "function accountDecision(", "function heldReasonEntries("):
        start = script.index(function)
        body = script[start:script.index("\n}\n", start)]
        assert "large_unsourced" not in body and "LARGE_DEPOSIT" not in body, function


# ------------------------------------------- audit round 3, final review (R3-FF), F6: the floor in the statement's unit
#
# The floor (LARGE_UNSOURCED_DEPOSIT_FLOOR) is compared in the statement's own unit, and the sentence printed "$10,000"
# on every statement, a CAD one included (CURRENCY DOCTRINE: never a '$' on a CAD statement). It is now formatted as the
# withholding floor's note formats its floor: formatMoney in the statement's unit, a package's unit where its members
# share one, no unit where they differ.


@needs_node
def test_ff_f6_the_card_writes_the_floor_in_a_cad_statement_s_unit():
    served = _served(_payload(L1, currency="CAD"))
    assert served["metrics"]["large_unsourced_deposit_count"] == 2
    result = _statement_view(served, "console.log(JSON.stringify({note: trueNote()}));")
    assert result["note"].endswith(" · Large deposits to source: 2 · CA$270,000.00 (each CA$10,000.00 or more and over "
                                   "25% of True)")
    assert "$10,000 " not in result["note"].replace("CA$10,000", "")


@needs_node
def test_ff_f6_the_fact_formats_the_floor_in_each_unit():
    result = run_dashboard("""
const one = {large_unsourced_deposit_count: 1, large_unsourced_deposit_total: 12000};
const refused = {large_unsourced_deposit_count: 3, large_unsourced_deposit_total: null};
console.log(JSON.stringify({usd: largeDepositFacts(one, "USD"), cad: largeDepositFacts(one, "CAD"),
  none: largeDepositFacts(one, null), pkg: largeDepositFacts(one, "CAD", {package: true}),
  mixed: largeDepositFacts(refused, null, {package: true}), floor: LARGE_UNSOURCED_DEPOSIT_FLOOR}));
""")
    tail = "or more and over 25% of True)"
    assert result["usd"] == [f"Large deposits to source: 1 · $12,000.00 (each $10,000.00 {tail}"]
    assert result["cad"] == [f"Large deposits to source: 1 · CA$12,000.00 (each CA$10,000.00 {tail}"]
    assert result["none"] == [f"Large deposits to source: 1 · 12,000.00 (each 10,000.00 {tail}"]
    assert result["pkg"] == ["Large deposits to source: 1 · CA$12,000.00 (each CA$10,000.00 or more and over 25% of its "
                             "statement's True)"]
    assert result["mixed"] == ["Large deposits to source: 3 (each 10,000.00 or more and over 25% of its statement's "
                               "True)"]
    assert result["floor"] == 10000


def test_ff_f6_the_dashboard_s_floor_mirrors_the_python_constant():
    import re
    from pathlib import Path

    from analysis.revenue_view import LARGE_UNSOURCED_DEPOSIT_FLOOR

    script = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    (value,) = re.findall(r"^const LARGE_UNSOURCED_DEPOSIT_FLOOR = (\d+);$", script, re.M)
    assert int(value) == LARGE_UNSOURCED_DEPOSIT_FLOOR
    assert "$10,000" not in script[script.index("function largeDepositFacts("):][:1200]
