"""The owner's request of 2026-10-10 (active positions by month; true revenue spec §2.2, §9.1, §9.2, §10, §20), where
it shows. The owner, a minute after the request: "it should be included in the monthly statement chart before
witholding": the Monthly Statements table gains an "Active Positions" column immediately before "Withholding Rate"
(one cell per row: "2", "2 (+1 possible)", "0", "N/A"); the copied summaries name the active positions (the package by
month); the statement downloads and the package rows carry `active_positions` and `possible_positions`; the CLI prints
one line and the batch CSV gains the two columns; app.js is asked for as `true-revenue-12`.

The whole webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated data only:
CONTOSO, FABRIKAM, NORTHWIND and SAMPLE names, KAPITUS and ONDECK (public funders) as descriptors, the tests' 2054
dates, whole amounts and made-up job ids."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

HEADER_BOTH = ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)",
               "True Deposits Per Month", "Active Positions", "Withholding Rate", "Ledger ($)", "NSF", "Action"]
HEADER_ONE = ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month", "Active Positions", "Withholding Rate",
              "Ledger ($)", "NSF", "Action"]


# ---------------------------------------------------------------------------------------------- the page and app.js
def test_the_page_s_table_header_names_the_column_before_withholding_rate_and_asks_for_the_new_app_js():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    head = html[html.index('<thead id="monthlyHead">'):html.index("</thead>", html.index('<thead id="monthlyHead">'))]
    assert re.findall(r"<th>([^<]*)</th>", head) == HEADER_BOTH
    # The owner's own design (2026-10-11, display only) moved the page on to -13; -12 was this request's release.
    assert '<script src="/static/app.js?v=true-revenue-13"></script>' in html
    assert "true-revenue-11" not in html and "true-revenue-12" not in html


MONTHLY = r"""
const cells = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
  .map((row) => [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((cell) => cell[1].replace(/<[^>]+>/g, "").trim()));
const views = (pkg) => Object.fromEntries(["both", "total", "true"].map((view) => {
  setMonthlyDepositsView(view); renderMonthlyStatements(pkg);
  return [view, {head: cells(els.monthlyHead.innerHTML)[0], rows: cells(els.monthlyTable.innerHTML)}];
}));
"""


def _row(job, month, **fields):
    return {"id": job, "filename": f"{job}.pdf", "status": "done", "period_start": f"2054-{month:02d}-01",
            "period_end": f"2054-{month:02d}-28", "credits": 100000.0, "deposit_count": 4,
            "true_revenue_total": 60000.0, "true_revenue_count": 2, "verified_revenue_total": 20000.0,
            "revenue_established": True, "verified_revenue_established": True, "average_daily_balance": 5000.0,
            "nsf_count": 1, "currency": "USD", "withholding_rate": 10.0, "withholding_numerator": 6000.0,
            "withholding_denominator": 60000.0, **fields}


@needs_node
def test_the_monthly_table_shows_the_active_positions_right_before_the_withholding_rate():
    rows = [_row("contoso", 1, active_positions=2, possible_positions=0),
            _row("fabrikam", 2, active_positions=2, possible_positions=1),
            _row("northwind", 3, active_positions=0, possible_positions=0),
            # The lender reading is not available (an analysis without the rows): N/A, never 0.
            _row("sample", 4, active_positions=None, possible_positions=None),
            # A statement that did not complete reads N/A whatever its row carries.
            _row("failed", 5, status="failed", active_positions=1, possible_positions=0),
            _row("possible", 6, active_positions=0, possible_positions=1),
            # A row served before the column existed carries neither key.
            _row("older", 7),
            _row("several", 8, active_positions=1, possible_positions=2)]
    package = {"documents": rows, "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(MONTHLY + f"console.log(JSON.stringify(views({json.dumps(package)})));")
    assert result["both"]["head"] == HEADER_BOTH
    assert result["total"]["head"] == result["true"]["head"] == HEADER_ONE
    expected = ["2", "2 (+1 possible)", "0", "N/A", "N/A", "0 (+1 possible)", "N/A", "1 (+2 possible)"]
    assert [row[6] for row in result["both"]["rows"]] == expected
    assert [row[4] for row in result["total"]["rows"]] == expected
    assert [row[4] for row in result["true"]["rows"]] == expected
    # The other columns keep their order: the Withholding Rate follows, then the ledger, NSF and the action.
    assert result["both"]["rows"][0] == ["January", "2054", "100,000", "4", "60,000", "2", "2", "10.00%", "5,000",
                                         "1", "Open"]
    assert all(len(row) == len(HEADER_BOTH) for row in result["both"]["rows"])


@needs_node
def test_an_empty_package_s_row_keeps_one_cell_per_column():
    package = {"documents": [], "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(MONTHLY + f"console.log(JSON.stringify(views({json.dumps(package)})));")
    [row] = result["both"]["rows"]
    assert len(row) == len(HEADER_BOTH) and row[6] == "N/A" and row[7] == "N/A"


# ------------------------------------------------------------------------------------------------------- the memos
def _three_months_package():
    from tests import test_active_positions as tap
    from tests import test_lender_payment_changes_package as pkg

    march, april, may = tap.three_months()
    return (march, april, may), pkg.package(pkg.job("march", march), pkg.job("april", april), pkg.job("may", may))


@needs_node
def test_the_package_memo_names_the_active_positions_by_month():
    _payloads, built = _three_months_package()
    memo = run_dashboard(f"""
currentJobIds = ['march', 'april', 'may']; renderPackageAnalysis({json.dumps(built)}); generateSummary();
console.log(JSON.stringify(els.summaryBox.textContent));
""")
    sentence = "Active positions by month: Mar 2054 1, Apr 2054 2, May 2054 2 (+1 possible)."
    assert sentence in memo
    assert memo.index("confirmed lender detections. ") < memo.index(sentence) < memo.index("Decision: ")
    # A month the lender reading is not available for reads N/A.
    built["active_positions_by_month"][1].update(active_positions=None, possible_positions=None)
    memo = run_dashboard(f"""
currentJobIds = ['march', 'april', 'may']; renderPackageAnalysis({json.dumps(built)}); generateSummary();
console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "Active positions by month: Mar 2054 1, Apr 2054 N/A, May 2054 2 (+1 possible)." in memo


@needs_node
def test_the_statement_memo_names_its_active_positions():
    from tests.test_webapp_studio_views import _serve
    from webapp.app import _displayed

    (march, _april, may), _built = _three_months_package()
    texts = []
    for payload in (march, may):
        texts.append(run_dashboard(_serve(s=_displayed(payload, settings={})) + """
currentJobId = 's'; currentJobIds = ['s']; loadResults('s'); await settle();
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
"""))
    assert "1 confirmed lender detections, 1 active position, " in texts[0]
    assert "2 confirmed lender detections, 2 active positions (+1 possible), " in texts[1]


# ---------------------------------------------------------------------------------------------------- the downloads
def _csv_rows(text):
    return list(csv.reader(io.StringIO(text)))


def test_the_statement_downloads_carry_both_figures():
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed, _masked

    (_march, _april, may), _built = _three_months_package()
    exported = _masked(_displayed(may, settings={}, export=True))
    assert (exported["metrics"]["active_positions"], exported["metrics"]["possible_positions"]) == (2, 1)
    rows = _csv_rows(_analysis_csv(exported))
    assert ["metrics", "active_positions", "2"] in rows and ["metrics", "possible_positions", "1"] in rows
    with zipfile.ZipFile(io.BytesIO(_analysis_xlsx(exported))) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "active_positions" in sheet and "possible_positions" in sheet
    # N/A is an empty cell, as the downloads write every figure that is not available.
    older = json.loads(json.dumps(may))
    from tests.test_lender_payment_changes_package import _account

    del _account(older)["detection"]["lender_payment_changes"]
    rows = _csv_rows(_analysis_csv(_masked(_displayed(older, settings={}, export=True))))
    assert ["metrics", "active_positions", ""] in rows and ["metrics", "possible_positions", ""] in rows


def test_the_package_downloads_carry_each_row_s_figures_and_the_months():
    from webapp.app import _masked, _package_csv, _package_for_export, _package_xlsx

    _payloads, built = _three_months_package()
    exported = _masked(_package_for_export(built))
    rows = _csv_rows(_package_csv(exported))
    found = {(section, field): value for section, field, value in (row[:3] for row in rows if len(row) >= 3)}
    names = {found[(f"document_{index}", "id")]: index for index in (1, 2, 3)}
    assert [(found[(f"document_{names[job]}", "active_positions")],
             found[(f"document_{names[job]}", "possible_positions")]) for job in ("march", "april", "may")] == [
        ("1", "0"), ("2", "0"), ("2", "1")]
    assert [(found[(f"active_positions_month_{index}", "month")],
             found[(f"active_positions_month_{index}", "active_positions")],
             found[(f"active_positions_month_{index}", "possible_positions")]) for index in (1, 2, 3)] == [
        ("2054-03", "1", "0"), ("2054-04", "2", "0"), ("2054-05", "2", "1")]
    with zipfile.ZipFile(io.BytesIO(_package_xlsx(exported))) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "active_positions_month_1" in sheet


# ------------------------------------------------------------------------------------------------ the CLI and batch
def test_the_cli_prints_one_line_and_the_batch_csv_gains_two_columns():
    import analyze
    import batch
    from tests.test_lender_payment_changes_pipeline import M, NAMED, SALE, _analysed, bdays, every

    kapitus = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
    ondeck = "ONDECK CAPITAL DES:PAYMENT ID:000000003 INDN:CONTOSO PLUMBING LLC CO ID:0000000004 CCD"
    rows = ([(M(2), SALE, 50000.0)] + [(day, kapitus, -1000.0) for day in every(M(4), M(25))]
            + [(day, ondeck, -300.0) for day in bdays(M(2), M(31))]
            + [(day, NAMED, -1500.0) for day in every(M(4), M(25))])
    report = _analysed(rows).accounts[0]
    lines = analyze._render(report).splitlines()
    assert "  Active positions      : 2 (+1 possible)" in lines
    assert lines.index("  Active positions      : 2 (+1 possible)") == lines.index("  Lender payment changes: none") - 1
    row = batch._row(Path("fabricated.md"), report)
    assert (row["active_positions"], row["possible_positions"]) == (2, 1)
    start = batch.FIELDS.index("lender_payment_changes") + 1
    assert batch.FIELDS[start:start + 2] == ["active_positions", "possible_positions"]
    quiet = analyze._render(_analysed([(M(1), SALE, 10000.0)]).accounts[0]).splitlines()
    assert "  Active positions      : 0" in quiet


# ---------------------------------------------------------------------------------------------------------- the docs
def test_the_spec_and_the_readme_record_the_request():
    """The spec's §2.2 carries the owner's request of 2026-10-10 with his three answers, §9.1 and §9.2 the served keys,
    §9.3 the version line, §10 the column and the memos, §10.8 the downloads and §20 one line naming the code's commits
    and the measurement; the README's dashboard paragraph names the column."""
    spec = " ".join((ROOT / "docs/superpowers/specs/2026-09-28-true-revenue-design.md").read_text(encoding="utf-8").split())
    requests = spec[spec.index("### 2.2 Owner requests (2026-10-06)"):spec.index("## 3. Goals and non-goals")]
    for words in ("| Active positions by month (2026-10-10) |",
                  "it should also be included in the demo website is the active Position count by month.",
                  "it should be included in the monthly statement chart before witholding",
                  "1. What counts: **confirmed lenders**", "2. Same funder, two payment schedules: **2 positions**.",
                  "3. Active in a month: **a payment cleared** that month."):
        assert words in requests, words
    contract = spec[spec.index("### 9.1 Per account"):spec.index("## 11. Withholding")]
    for words in ("`apply_active_positions_view`", "`active_positions` and `possible_positions`", "`series_positions`",
                  "`active_positions_by_month`", "`_package_active_positions`", "`true-revenue-12`",
                  "\"Active Positions\" immediately before \"Withholding Rate\"", "`active_positions_month_<n>`",
                  "` Active positions : 2 (+1 possible)`"):
        assert words in contract, words
    amendments = spec[spec.index("## 20. Implementation amendments"):]
    line = amendments[amendments.index("- **Active positions by month** ("):]
    for words in ("a0376f8", "e423c01", "this commit", "the lender census (cached) and the revenue census (cached",
                  "0 console errors"):
        assert words in line, words
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "adds an \"Active Positions\" column to the Monthly Statements table, right before Withholding Rate" in readme
