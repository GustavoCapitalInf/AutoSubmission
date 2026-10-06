"""The dashboard's view of a statement that holds several accounts (webapp/static/app.js), with fabricated payloads:
the main account a lender funds is shown by default, and the "All accounts" setting lists every account the
statement prints, each with its own figures and none added up across accounts."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
APP_JS = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")


def _function(name):
    return APP_JS[APP_JS.index(f"function {name}("):].split("\nfunction ")[0]


def _constant(name):
    return APP_JS[APP_JS.index(f"const {name} "):].split("\n")[0] + "\n"


def _accounts_block():
    # isDocumentPayload, then every account helper, up to renderAnalysis.
    return APP_JS[APP_JS.index("function isDocumentPayload("):APP_JS.index("function renderAnalysis(")]


def _run(source):
    # The script goes to node on stdin: the extracted block is longer than a Windows command line allows.
    result = subprocess.run([NODE, "-"], input=source, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _harness(view):
    return f"""
const store = {{"bsa-all-accounts": {json.dumps(view)}}};
const localStorage = {{getItem: (key) => store[key] ?? null, setItem: (key, value) => {{ store[key] = value; }}}};
const els = {{accountsPanel: {{innerHTML: "", hidden: true}}}};
""" + _constant("CHIP_TONES") + "\n".join(_function(name) for name in (
        "escapeHtml", "numberOrNull", "formatMoney", "formatNumber", "chipTone", "glassChip",
    )) + _accounts_block()


def _account(name, number, deposits, **statement):
    return {"statement": {"account_name": name, "account_number": number, "currency": "USD",
                          "beginning_balance": 100.0, "ending_balance": 200.0, "transactions": [{}, {}], **statement},
            "metrics": {"effective_total_deposits": deposits, "effective_total_withdrawals": 50.0,
                        "average_daily_balance": 150.0}}


PAYLOAD = {"document": {"account_count": 3, "account_roster": [
    {"title": "FABRICATED SAVINGS", "kind": "savings", "number_last4": "0001", "status": "published",
     "published_index": 0, "balance": None, "reasons": []},
    {"title": "FABRICATED BUSINESS CHECKING", "kind": "checking", "number_last4": "0010", "status": "published",
     "published_index": 1, "balance": None, "reasons": []},
    {"title": "FABRICATED CLUB", "kind": "savings", "number_last4": "0020", "status": "idle",
     "published_index": None, "balance": 25.0, "reasons": []},
    {"title": "FABRICATED MONEY MARKET", "kind": "money_market", "number_last4": "0030", "status": "held",
     "published_index": None, "balance": None, "reasons": ["page_unresolved"]},
]}, "accounts": [_account("FABRICATED SAVINGS", "0001", 9000.0), _account("FABRICATED BUSINESS CHECKING", "0010", 500.0)]}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_main_account_is_the_business_checking_account_with_the_most_deposits():
    source = _harness("off") + """
const cases = [
  [[{statement: {account_name: "Savings"}, metrics: {effective_total_deposits: 9000}},
    {statement: {account_name: "Business Checking"}, metrics: {effective_total_deposits: 500}},
    {statement: {account_name: "Checking"}, metrics: {effective_total_deposits: 20000}}], []],
  [[{statement: {account_name: "Savings"}, metrics: {effective_total_deposits: 9000}},
    {statement: {account_name: "Checking"}, metrics: {effective_total_deposits: 300}},
    {statement: {account_name: "Checking"}, metrics: {effective_total_deposits: 700}}], []],
  [[{statement: {account_name: "Share 01"}, metrics: {effective_total_deposits: 10}},
    {statement: {account_name: "Share 70"}, metrics: {effective_total_deposits: 5}}],
   [{status: "published", published_index: 0, kind: "savings"},
    {status: "published", published_index: 1, kind: "checking", title: "Business Share Draft"}]],
];
console.log(JSON.stringify(cases.map(([accounts, roster]) => mainAccountIndex(accounts, roster))));
"""
    assert _run(source) == [1, 2, 1]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_by_default_only_the_main_account_is_shown_with_a_note_about_the_others():
    source = _harness("off") + f"""
const report = {json.dumps(PAYLOAD)};
const published = publishedAccounts(report), roster = accountRoster(report);
const main = mainAccountIndex(published, roster);
renderAccountsPanel(published, roster, main, main);
console.log(JSON.stringify({{main, html: els.accountsPanel.innerHTML, hidden: els.accountsPanel.hidden}}));
"""
    result = _run(source)
    assert result["main"] == 1 and result["hidden"] is False
    html = " ".join(result["html"].split())
    assert "holds <strong>4 accounts</strong>" in html
    assert "<strong>FABRICATED BUSINESS CHECKING ••0010</strong>" in html
    assert "business checking account with the most deposits" in html
    assert "review the other 3 accounts" in html and "<table" not in html


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_all_accounts_lists_every_account_with_its_own_figures_and_no_unverified_ones():
    source = _harness("on") + f"""
const report = {json.dumps(PAYLOAD)};
const published = publishedAccounts(report), roster = accountRoster(report);
renderAccountsPanel(published, roster, 1, 0);
console.log(JSON.stringify({{html: els.accountsPanel.innerHTML}}));
"""
    html = " ".join(_run(source)["html"].split())
    rows = html.split("<tr")[2:]
    assert len(rows) == 4
    assert 'data-account-index="0" class="is-selected"' in rows[0] and "MAIN" not in rows[0]
    assert "$9,000.00" in rows[0] and "$150.00" in rows[0]
    assert 'data-account-index="1"' in rows[1] and "main-badge" in rows[1] and "$500.00" in rows[1]
    assert "No activity" in rows[2] and rows[2].count("$25.00") == 3 and "data-account-index" not in rows[2]
    assert "Needs review" in rows[3] and "a page could not be verified" in rows[3] and "$" not in rows[3]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_payload_without_a_roster_lists_its_published_accounts():
    payload = {"document": {"account_count": 2}, "accounts": [_account("Checking", "1234", 10.0),
                                                              _account("Savings", "9876", 20.0)]}
    source = _harness("on") + f"""
const report = {json.dumps(payload)};
const published = publishedAccounts(report), roster = accountRoster(report);
renderAccountsPanel(published, roster, mainAccountIndex(published, roster), 0);
console.log(JSON.stringify({{html: els.accountsPanel.innerHTML}}));
"""
    html = " ".join(_run(source)["html"].split())
    assert "Checking ••1234" in html and "Savings ••9876" in html and html.count("Verified") == 2


HELD_MAIN = {"document": {"account_count": 3, "account_roster": [
    {"title": "FABRICATED SAVINGS", "kind": "savings", "number_last4": "0001", "status": "published",
     "published_index": 0, "balance": None, "reasons": []},
    {"title": "FABRICATED BUSINESS CHECKING", "kind": "checking", "number_last4": "0010", "status": "held",
     "published_index": None, "balance": None, "reasons": ["sum_mismatch"]},
    {"title": "FABRICATED CLUB", "kind": "savings", "number_last4": "0020", "status": "published",
     "published_index": 1, "balance": None, "reasons": []},
]}, "accounts": [_account("FABRICATED SAVINGS", "0001", 9000.0), _account("FABRICATED CLUB", "0020", 20.0)]}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_dashboard_ranks_the_main_account_as_the_package_does():
    # Review 9, finding 4: app.js and webapp/app.py decide the unverified main account alike.
    source = _harness("off") + """
const roster = (...entries) => entries.map(([title, kind, status]) => ({title, kind, status}));
const cases = [
  roster(["FABRICATED ADVANTAGE ACCOUNT", null, "held"], ["FABRICATED SAVINGS", "savings", "published"]),
  roster(["FABRICATED VISA", "credit_card", "held"], ["FABRICATED SAVINGS", "savings", "published"]),
  roster(["FABRICATED BUSINESS CHECKING", "checking", "published"], ["FABRICATED ADVANTAGE ACCOUNT", null, "held"]),
  roster(["FABRICATED CHECKING", "checking", "idle"], ["FABRICATED SAVINGS", "savings", "published"]),
  roster(["FABRICATED BUSINESS CHECKING", "checking", "published"], ["FABRICATED BUSINESS MERCHANT SERVICES", null, "held"]),
  roster(["FABRICATED CHECKING", "checking", "held"], ["FABRICATED BUSINESS ADVANTAGE ACCOUNT", null, "published"]),
  roster(["FABRICATED VISA", "credit_card", "held"], ["FABRICATED MASTERCARD", "credit_card", "published"]),
];
console.log(JSON.stringify(cases.map((entries) => (unverifiedMainAccount(entries) || {}).title || null)));
"""
    assert _run(source) == ["FABRICATED ADVANTAGE ACCOUNT", None, None, None, None, "FABRICATED CHECKING", None]


IDLE_MAIN = {"document": {"account_count": 2, "account_roster": [
    {"title": "FABRICATED BUSINESS CHECKING", "kind": "checking", "number_last4": "0010", "status": "idle",
     "published_index": None, "balance": 25.0, "reasons": []},
    {"title": "FABRICATED SAVINGS", "kind": "savings", "number_last4": "0001", "status": "published",
     "published_index": 0, "balance": None, "reasons": []},
]}, "accounts": [_account("FABRICATED SAVINGS", "0001", 9000.0), _account("FABRICATED CLUB", "0020", 20.0)]}


@pytest.mark.parametrize("view", ["off", "on"])
@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_idle_business_checking_account_needs_review_and_the_active_account_stays_shown(view):
    # Owner ruling, 2026-09-23: say that the main business checking account had no activity and needs review, and
    # keep showing the active savings account.
    source = _harness(view) + f"""
const report = {json.dumps(IDLE_MAIN)};
const published = publishedAccounts(report), roster = accountRoster(report);
const idle = idleMainAccount(roster), main = mainAccountIndex(published, roster);
renderAccountsPanel(published, roster, main, main, null, idle);
console.log(JSON.stringify({{idle: idle && idle.title, unverified: unverifiedMainAccount(roster), main,
                            html: els.accountsPanel.innerHTML}}));
"""
    result = _run(source)
    assert result["idle"] == "FABRICATED BUSINESS CHECKING" and result["unverified"] is None and result["main"] == 0
    html = " ".join(result["html"].split())
    if view == "off":
        assert "had no activity this period" in html and "needs review" in html
        assert "Showing the active account, <strong>FABRICATED SAVINGS ••0001</strong>" in html
    else:
        rows = html.split("<tr")[2:]
        assert "main-badge" in rows[0] and "No activity" in rows[0]
        assert "main-badge" not in rows[1] and 'class="is-selected"' in rows[1]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_dashboard_says_the_idle_main_account_needs_review_over_the_active_accounts_figures():
    # Rendered twice, as a settings change or an account selection does: the status is set, never stacked, and the
    # summary box (the actions') is left to the loader and to Generate Summary, which lead with the note.
    helpers = ("setBanner", "setStatusMessage", "kvRowsHtml", "statusRowHtml", "renderAnalysis", "labelize",
               "formatPercent", "potentialLenderDebitTotal", "hasMaterialPotentialLenderDebits", "period",
               # Audit B11 (I07): the summary's revenue sentence (True, Verified and Non-revenue).
               "revenueSummarySentence", "generateSummary",
               # Audit round 2, R2-B15 (R13): the months a statement's period covers, which its monthly figures read.
               "isoDay", "statementMonthsCovered",
               # Owner ruling 2026-10-02, R2-OW03: the excluded Zelle deposits the revenue sentence names; and (the
               # owner's amendment of 2026-10-06, R2-OW17) the served Zelle figures it reads first.
               "zelleExcluded", "zelleDeposits",
               # Owner ruling 2026-10-02 (the underwriter's Q5), R2-OW13: the summary's lender debits, paid and returned.
               "lenderDebitsSummary",
               # The owner's request of 2026-10-06 (R2-OW18): the summary's lender payment changes, and the warning
               # text the package summary lines quote.
               "lenderPaymentChangeWarning", "lenderPaymentChangesSummary")
    # Each function up to its closing brace (top-level code follows some of them).
    source = _harness("off") + "".join(APP_JS[APP_JS.index(f"function {name}("):].split("\n}\n")[0] + "\n}\n"
                                       for name in helpers) + f"""
let currentDocument = null, currentAnalysis = null, selectedAccountIndex = null, shownName = null;
for (const key of ["statusBanner", "statusMark", "statusCopy", "validationValue", "statusHeading", "summaryBox",
                   "decisionPill"]) els[key] = {{textContent: "", className: ""}};
els.statusList = {{innerHTML: "", insertAdjacentHTML(where, html) {{ this.innerHTML = html + this.innerHTML; }}}};
function renderAccount(report) {{
  currentAnalysis = report;
  shownName = report.statement.account_name;
  els.statusList.innerHTML = statusRowHtml(["Validation", "approved"]);
  els.statusHeading.textContent = "OCR completed";
  setBanner("done", "Extraction completed", "Validated");
  els.decisionPill.textContent = "approved";
}}
const report = {json.dumps(IDLE_MAIN)};
els.summaryBox.textContent = "Before.";
renderAnalysis(report);
renderAnalysis(report);
const rendered = {{shownName, heading: els.statusHeading.textContent, banner: els.statusCopy.textContent,
                  meta: els.validationValue.textContent, pill: els.decisionPill.textContent,
                  summary: els.summaryBox.textContent, rows: els.statusList.innerHTML}};
const note = idleMainNote(report, "USD"), none = idleMainNote({json.dumps(PAYLOAD)}, "USD");
generateSummary();
console.log(JSON.stringify({{rendered, note, none, generated: els.summaryBox.textContent}}));
"""
    result = _run(source)
    rendered = result["rendered"]
    assert rendered["shownName"] == "FABRICATED SAVINGS" and rendered["heading"] == "Main account needs review"
    assert rendered["banner"] == "Main account had no activity; showing the active account"
    assert rendered["meta"] == "Review required" and rendered["pill"] == "Review required"
    assert rendered["summary"] == "Before."
    rows = " ".join(rendered["rows"].split())
    assert rows.count("Main account") == 1 and rows.index("No activity; needs review") < rows.index("Validation")
    assert result["note"] == ("Main account FABRICATED BUSINESS CHECKING \u2022\u20220010 had no activity this period "
                              "(balance $25.00) and needs review. ")
    assert result["none"] == ""
    assert result["generated"].startswith(result["note"] + "Figures for the active account, FABRICATED SAVINGS")
    assert result["generated"].count("had no activity") == 1
    assert result["generated"].endswith("Status: review required.")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_held_business_checking_account_is_never_replaced_as_the_main_account():
    # Review 7, finding 5: the table marks the held checking account MAIN, no published account; the statement modal
    # shows no account in its place.
    source = _harness("on") + _function("modalAccountPayload") + f"""
const report = {json.dumps(HELD_MAIN)};
const published = publishedAccounts(report), roster = accountRoster(report);
const unverified = unverifiedMainAccount(roster);
renderAccountsPanel(published, roster, -1, null, unverified);
console.log(JSON.stringify({{title: unverified && unverified.title, html: els.accountsPanel.innerHTML,
                            modal: modalAccountPayload(report)}}));
"""
    result = _run(source)
    assert result["title"] == "FABRICATED BUSINESS CHECKING" and result["modal"] is None
    rows = " ".join(result["html"].split()).split("<tr")[2:]
    assert [("MAIN" in row, "Verified" in row) for row in rows] == [(False, True), (True, False), (False, True)]
    assert "is-selected" not in " ".join(rows)
