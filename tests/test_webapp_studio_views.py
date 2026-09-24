"""The dashboard of the multi-account branch inside the Statement Studio shell, driven end to end: the whole
webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). Fabricated statements only, analysed
by the real analysis path (analysis.pipeline.analyze_statement) and packaged by the real package code."""
import copy
import json
import os
import re

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

BANK = "FABRICATED COMMUNITY BANK"
# Whole-dollar fabricated amounts: a figure with cents could coincide with a real statement's (the privacy canaries).
CHECKING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0), (3, "CARD PURCHASE FABRICATED SUPPLY", -312.0),
                 (5, "CHECK 1041", -950.0), (9, "ACH DEBIT FABRICATED FUNDING LLC", -1250.0),
                 (12, "WIRE TRANSFER OUT FABRICATED VENDOR", -5600.0), (13, "DEPOSIT FABRICATED", 3900.0),
                 (27, "SERVICE FEE", -15.0)]
SAVINGS_ROWS = [(4, "TRANSFER FROM CHECKING", 500.0), (15, "INTEREST PAID", 2.0), (22, "TRANSFER TO CHECKING", -300.0)]


def _report(name, number, opening, rows, month=3):
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    txns, balance = [], opening
    for day, description, amount in rows:
        balance = round(balance + amount, 2)
        txns.append(Transaction(date=f"2031-{month:02d}-{day:02d}", description=description, amount=amount,
                                direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(bank=BANK, account_name=name, account_number=number, period_start=f"2031-{month:02d}-01",
                          period_end=f"2031-{month:02d}-28", beginning_balance=opening, ending_balance=balance,
                          currency="USD", currency_source="printed", transactions=txns)
    return analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                             model_used="fabricated-test")


def _single(month=3):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, CHECKING_ROWS, month))


def _document(main_status):
    """Business checking (the main account) published, idle or held, beside a verified savings account."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, CHECKING_ROWS).accounts[0]
    savings = _report("FABRICATED SAVINGS", "000000002020", 9000.0, SAVINGS_ROWS).accounts[0]
    reports = [checking, savings] if main_status == "published" else [savings]
    main = {"published": AccountRosterEntry("FABRICATED BUSINESS CHECKING", "checking", "1010", "published",
                                            published_index=0),
            "idle": AccountRosterEntry("FABRICATED BUSINESS CHECKING", "checking", "1010", "idle", balance=25.0),
            "held": AccountRosterEntry("FABRICATED BUSINESS CHECKING", "checking", "1010", "held",
                                       reasons=("page_unresolved",))}[main_status]
    roster = [main, AccountRosterEntry("FABRICATED SAVINGS", "savings", "2020", "published",
                                       published_index=len(reports) - 1)]
    transfers, notes = identify_internal_transfers(reports)
    return document_report_to_dict(DocumentReport(accounts=reports, document_period=("2031-03-01", "2031-03-28"),
                                                  internal_transfers=transfers, integrity_notes=notes,
                                                  account_roster=roster))


def _serve(**jobs):
    """FAKE_RESPONSES for /analysis/<id> and /markdown/<id>, and the ids a Recent list needs."""
    responses = {}
    for job_id, payload in jobs.items():
        responses[f"/analysis/{job_id}"] = {"json": {"analysis": payload, "analysis_error": None}}
        responses[f"/markdown/{job_id}"] = {"text": ""}
    return f"Object.assign(FAKE_RESPONSES, {json.dumps(responses)});\n"


def _all_accounts(view):
    return f"localStorage.setItem('bsa-all-accounts', {json.dumps(view)});\n"


def _select(index):
    # What a click on an account row does (selectAccountFrom reads the row's index off the event's target).
    return (f"(() => {{ const row = fakeElement('row-{index}'); row.attributes['data-account-index'] = '{index}';"
            f" row.closest = () => row; selectAccountFrom({{target: row}}); }})();\n")


def test_a_statement_whose_main_account_was_not_verified_withholds_every_metric_panel():
    result = run_dashboard(_all_accounts("off") + _serve(single=_single(), held=_document("held")) + """
currentJobId = 'single'; currentJobIds = ['single']; loadResults('single'); await settle();
const reviewBefore = [els.reviewCount.hidden, els.reviewCount.textContent];
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
const held = {withheld: els.resultsContent.classList.contains('is-withheld'), chips: els.heroChips.innerHTML,
              kicker: els.heroKicker.innerHTML, panel: els.accountsPanel.innerHTML, hidden: els.accountsPanel.hidden,
              message: els.statusMessage.textContent, review: els.statusMessage.classList.contains('review'),
              pill: els.decisionPill.textContent, crumbs: analysisCrumbs, reviewCount: els.reviewCount.hidden};
currentJobId = 'single'; currentJobIds = ['single']; loadResults('single'); await settle();
console.log(JSON.stringify({reviewBefore, held, after: els.resultsContent.classList.contains('is-withheld')}));
""")
    held = result["held"]
    assert held["withheld"] is True and result["after"] is False
    assert "Main account · Not verified" in held["chips"] and "2 accounts" in held["kicker"]
    assert held["hidden"] is False and "could not be verified" in held["panel"] and 'data-nav="settings"' in held["panel"]
    assert "No metrics are shown for it" in held["message"] and held["review"] is True
    assert held["pill"] == "Review required" and BANK in held["crumbs"]
    # The previous statement's deposits to review never stay on the sidebar for one that shows no account.
    assert result["reviewBefore"][0] is False and held["reviewCount"] is True


def test_a_verified_account_picked_on_that_statement_is_never_shown_as_approved_on_its_own():
    result = run_dashboard(_all_accounts("on") + _serve(held=_document("held")) + """
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
const before = {withheld: els.resultsContent.classList.contains('is-withheld'), selected: selectedAccountIndex};
""" + _select(0) + """
generateSummary();
console.log(JSON.stringify({before, withheld: els.resultsContent.classList.contains('is-withheld'),
  pill: els.decisionPill.textContent, heading: els.statusHeading.textContent, chips: els.heroChips.innerHTML,
  rows: els.processingList.innerHTML, summary: els.summaryBox.textContent}));
""")
    assert result["before"] == {"withheld": True, "selected": None}
    assert result["withheld"] is False and result["pill"] == "Review required"
    assert result["heading"] == "Main account needs review" and "Main account · Not verified" in result["chips"]
    rows = " ".join(re.sub(r"<[^>]+>", " ", result["rows"]).split())
    assert rows.startswith("Main account Not verified")
    assert result["summary"].startswith("Main account FABRICATED BUSINESS CHECKING")
    assert "could not be verified" in result["summary"] and "Figures for the selected account, FABRICATED SAVINGS" \
        in result["summary"] and result["summary"].endswith("Status: review required.")


def test_an_idle_main_account_is_named_on_the_header_and_both_processing_lists():
    result = run_dashboard(_all_accounts("off") + _serve(idle=_document("idle")) + """
currentJobId = 'idle'; currentJobIds = ['idle']; loadResults('idle'); await settle();
console.log(JSON.stringify({chips: els.heroChips.innerHTML, status: els.statusList.innerHTML,
  processing: els.processingList.innerHTML, kicker: els.heroKicker.innerHTML}));
""")
    assert result["chips"].count("Main account · No activity") == 1 and "FABRICATED SAVINGS" in result["kicker"]
    for rows in (result["status"], result["processing"]):
        assert " ".join(re.sub(r"<[^>]+>", " ", rows).split()).startswith("Main account No activity; needs review")


def test_reopening_from_recent_never_carries_an_account_choice_and_a_failed_reopen_restores_the_one_on_screen():
    result = run_dashboard(_all_accounts("on") + _serve(multi=_document("published"), held=_document("held")) + """
rememberAnalysis({kind: 'statement', key: 'held', ids: ['held'], label: 'Held', meta: '', tone: 'amber'});
rememberAnalysis({kind: 'statement', key: 'gone', ids: ['gone'], label: 'Gone', meta: '', tone: 'amber'});
currentJobId = 'multi'; currentJobIds = ['multi']; loadResults('multi'); await settle();
// The main account (index 0) is on screen: index 0 also exists on the statement reopened next (its savings account),
// which is exactly where a carried choice would show another statement's account.
const onScreen = selectedAccountIndex;
openRecent('held'); await settle();
const reopened = {selected: selectedAccountIndex, withheld: els.resultsContent.classList.contains('is-withheld')};
currentJobId = 'multi'; currentJobIds = ['multi']; loadResults('multi'); await settle();
""" + _select(1) + """
const recorded = shownAnalysis.selectedAccountIndex;
openRecent('gone'); await settle();
console.log(JSON.stringify({onScreen, recorded, reopened, restored: {selected: selectedAccountIndex,
  job: currentJobId, kicker: els.heroKicker.innerHTML}}));
""")
    assert result["onScreen"] == 0 and result["recorded"] == 1
    assert result["reopened"] == {"selected": None, "withheld": True}
    assert result["restored"]["selected"] == 1 and result["restored"]["job"] == "multi"
    assert "FABRICATED SAVINGS" in result["restored"]["kicker"]


def test_the_recent_entry_names_the_statement_and_keeps_its_dot_whichever_account_is_on_screen():
    result = run_dashboard(_all_accounts("on") + _serve(multi=_document("published"), held=_document("held")) + """
const entry = (key) => { const item = recentAnalyses.find((each) => each.key === key); return [item.label, item.tone]; };
currentJobId = 'multi'; currentJobIds = ['multi']; loadResults('multi'); await settle();
const multiFirst = entry('multi');
""" + _select(1) + """
loadResults('multi', {reveal: false}); await settle();
const multiRefreshed = entry('multi');
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
const heldFirst = entry('held');
""" + _select(0) + """
loadResults('held', {reveal: false}); await settle();
console.log(JSON.stringify({multiFirst, multiRefreshed, heldFirst, heldRefreshed: entry('held')}));
""")
    assert result["multiFirst"] == result["multiRefreshed"]
    assert result["multiFirst"][0] == f"March 2031 · {BANK}"
    # The statement whose main account was not verified stays a review, even with a verified account on screen.
    assert result["heldFirst"] == result["heldRefreshed"] == [f"March 2031 · {BANK}", "amber"]


MARKED = """
const marked = () => [...els.recentStatements.innerHTML.matchAll(/<button class="side-link recent-item( active)?"[^>]*data-recent-key="([^"]+)"[^>]*?(aria-current="true")?>/g)]
  .filter((match) => match[1] || match[3]).map((match) => match[2]);
const order = () => recentAnalyses.map((item) => item.key);
"""


def test_the_recent_list_marks_the_open_statement_and_keeps_its_place_on_reopen():
    result = run_dashboard(_serve(jan=_single(1), feb=_single(2), mar=_single(3)) + MARKED + """
for (const id of ['jan', 'feb', 'mar']) {
  currentJobId = id; currentJobIds = [id]; loadResults(id); await settle();
}
const afterUploads = {order: order(), marked: marked()};
openRecent('jan'); await settle();
const reopenedJan = {order: order(), marked: marked(), title: els.resultsTitle.textContent};
openRecent('feb'); await settle();
const reopenedFeb = {order: order(), marked: marked(), title: els.resultsTitle.textContent};
uploadFiles([{name: 'fabricated-next.pdf', type: 'application/pdf', size: 1}]); await settle();
console.log(JSON.stringify({afterUploads, reopenedJan, reopenedFeb, duringUpload: marked()}));
""")
    assert result["afterUploads"] == {"order": ["mar", "feb", "jan"], "marked": ["mar"]}
    # A reopen marks the entry clicked and leaves the list where it was.
    assert result["reopenedJan"]["order"] == ["mar", "feb", "jan"] and result["reopenedJan"]["marked"] == ["jan"]
    assert result["reopenedJan"]["title"] == "January 2031 statement"
    assert result["reopenedFeb"]["order"] == ["mar", "feb", "jan"] and result["reopenedFeb"]["marked"] == ["feb"]
    assert result["reopenedFeb"]["title"] == "February 2031 statement"
    assert result["duringUpload"] == []


def test_a_held_or_contradicted_statement_is_listed_and_reopens_on_its_explanation():
    held = {"/analysis/held": {"json": {"analysis": None, "analysis_error": "visual pair requires human review"}},
            "/markdown/held": {"text": ""},
            "/analysis/fail": {"json": {"analysis": None, "analysis_error":
                                        "Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction"}},
            "/markdown/fail": {"text": ""}}
    result = run_dashboard(f"Object.assign(FAKE_RESPONSES, {json.dumps(held)});\n" + _serve(ok=_single()) + MARKED + """
const entry = (key) => { const item = recentAnalyses.find((each) => each.key === key); return item && [item.label, item.tone]; };
for (const [id, name] of [['held', 'fabricated-held.pdf'], ['fail', 'fabricated-fail.pdf']]) {
  currentFile = {name, size: 1}; currentJobId = id; currentJobIds = [id]; loadResults(id); await settle();
}
currentFile = null; currentJobId = 'ok'; currentJobIds = ['ok']; loadResults('ok'); await settle();
const onResults = {view: currentView, marked: marked()};
openRecent('held'); await settle();
console.log(JSON.stringify({held: entry('held'), fail: entry('fail'), onResults,
  reopened: {view: currentView, nav: activeNav, marked: marked(), message: els.statusMessage.textContent}}));
""")
    assert result["held"] == ["fabricated-held.pdf", "amber"] and result["fail"] == ["fabricated-fail.pdf", "red"]
    assert result["onResults"] == {"view": "results", "marked": ["ok"]}
    reopened = result["reopened"]
    assert reopened["view"] == "new" and reopened["nav"] == "new" and reopened["marked"] == ["held"]
    assert "No metrics have been published" in reopened["message"]


def test_enter_on_the_settings_link_in_the_accounts_panel_is_left_to_the_link():
    result = run_dashboard(_all_accounts("on") + _serve(multi=_document("published")) + """
currentJobId = 'multi'; currentJobIds = ['multi']; loadResults('multi'); await settle();
const keydown = els.accountsPanel.listeners.keydown[0];
const link = fakeElement('settings-link'); link.closest = () => null;
let linkPrevented = false;
keydown({key: 'Enter', target: link, preventDefault() { linkPrevented = true; }});
const row = fakeElement('row'); row.attributes['data-account-index'] = '1'; row.closest = () => row;
let rowPrevented = false;
keydown({key: ' ', target: row, preventDefault() { rowPrevented = true; }});
console.log(JSON.stringify({linkPrevented, rowPrevented, selected: selectedAccountIndex}));
""")
    assert result == {"linkPrevented": False, "rowPrevented": True, "selected": 1}


def test_summary_and_copy_on_a_withheld_statement_carry_the_statement():
    result = run_dashboard(_all_accounts("off") + _serve(held=_document("held")) + """
let copied = null;
copyText = (text) => { copied = text; };
els.summaryPanel.hidden = true;  // as the page starts (index.html) and as every new analysis closes it
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
const closedBefore = els.summaryPanel.hidden;
els.summaryBtn.listeners.click[0]();
els.copyDataBtn.listeners.click[0]();
console.log(JSON.stringify({closedBefore, panelHidden: els.summaryPanel.hidden, summary: els.summaryBox.textContent,
  copied: JSON.parse(copied)}));
""")
    assert result["closedBefore"] is True
    assert result["panelHidden"] is False and "could not be verified" in result["summary"]
    assert [entry["status"] for entry in result["copied"]["document"]["account_roster"]] == ["held", "published"]


def test_a_withheld_statement_counts_as_open_and_is_fetched_again_by_a_settings_change():
    result = run_dashboard(_all_accounts("off") + _serve(held=_document("held")) + """
rememberAnalysis({kind: 'statement', key: 'other', ids: ['other'], label: 'Other', meta: '', tone: 'amber'});
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
FETCHED.length = 0;
navigate('statements'); await settle();
const onNavigate = FETCHED.slice();
refreshShownResults(); await settle();
console.log(JSON.stringify({onNavigate, onRefresh: FETCHED.slice(onNavigate.length), job: currentJobId}));
""")
    assert result["onNavigate"] == [] and result["job"] == "held"
    assert "/analysis/held" in result["onRefresh"]


def test_nsf_basis_labels_and_the_queue_rows_words():
    result = run_dashboard("""
console.log(JSON.stringify({legacy: nsfSourceLabel('classified_line_items'), printed: nsfSourceLabel('negative_printed_days'),
  queue: queueState({jobId: 'x', status: 'processing', stage: 'visual_pair_proposing:2/8:batch:1/3'}).detail,
  banner: processingStageLabel('visual_pair_proposing:2/8:batch:1/3')}));
""")
    assert result["legacy"] == "Returned items (saved before the negative-day count)"
    assert result["printed"] == "Negative-ending days (printed days only)"
    assert result["queue"] == result["banner"] and ":" not in result["queue"]


def test_a_package_that_mixes_nsf_bases_names_each_rows_basis(tmp_path, monkeypatch):
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)  # the settings file of a scratch folder
    jobs = []
    for month in (1, 2):
        payload = _single(month)
        if month == 1:  # a result saved before the printed-day basis existed keeps its own basis
            payload["metrics"]["nsf_source"] = "classified_line_items"
        jobs.append(Job(id=f"m{month}", filename=f"fabricated-{month}.pdf", status="done", analysis=payload,
                        content_sha256=f"m{month}"))
    package = _package_analysis(jobs)
    assert package["totals"]["nsf_source"] == "mixed"
    result = run_dashboard(f"""
currentJobIds = ['m1', 'm2']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{rows: els.monthlyTable.innerHTML}}));
""")
    assert result["rows"].count('class="table-cell-detail"') >= 2
    assert "Returned items (saved before the negative-day count)" in result["rows"]
    assert "Negative-ending days (printed days only)" in result["rows"]


def _package(analyses, tmp_path, monkeypatch):
    """The real package payload for fabricated statements (job id -> analysis)."""
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)  # the NSF setting of a scratch folder
    return _package_analysis([Job(id=job_id, filename=f"fabricated-{job_id}.pdf", status="done", analysis=analysis,
                                  content_sha256=job_id) for job_id, analysis in analyses.items()])


CELLS = r"""
const cells = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
  .map((row) => [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((cell) => cell[1].replace(/<[^>]+>/g, "").trim()));
const monthly = () => ({head: cells(els.monthlyHead.innerHTML)[0], rows: cells(els.monthlyTable.innerHTML),
                        count: els.monthlyCount.textContent});
"""


def test_the_monthly_statements_show_total_true_or_both_deposits(tmp_path, monkeypatch):
    package = _package({"jan": _single(1), "feb": _single(2)}, tmp_path, monkeypatch)
    documents = {doc["id"]: doc for doc in package["documents"]}
    assert all(doc["credits"] != doc["verified_revenue_total"] for doc in documents.values())
    result = run_dashboard(CELLS + f"""
localStorage.setItem('bsa-monthly-deposits', 'no-such-view');  // anything unknown reads as Both
currentJobIds = ['jan', 'feb']; renderPackageAnalysis({json.dumps(package)});
const both = monthly();
setMonthlyDepositsView('true');
const trueOnly = {{...monthly(), stored: localStorage.getItem('bsa-monthly-deposits')}};
setMonthlyDepositsView('total');
console.log(JSON.stringify({{both, trueOnly, totalOnly: monthly()}}));
""")
    whole = lambda value: f"{round(value):,}"  # noqa: E731  the table's whole-number format
    both, true_only, total_only = result["both"], result["trueOnly"], result["totalOnly"]
    assert both["head"] == ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)",
                            "True Deposits Per Month", "Ledger ($)", "NSF", "Action"]
    assert both["count"] == "2 statements"
    january = documents["jan"]
    assert both["rows"][0][2:6] == [whole(january["credits"]), str(january["deposit_count"]),
                                    whole(january["verified_revenue_total"]), str(january["verified_revenue_count"])]
    # One basis alone keeps the CRM's own headers and names the basis beside the count.
    for view, shown, amount, count in ((true_only, "True monthly deposits: revenue only", "verified_revenue_total",
                                        "verified_revenue_count"),
                                       (total_only, "Total monthly deposits: everything going in", "credits",
                                        "deposit_count")):
        assert view["head"] == ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month", "Ledger ($)", "NSF",
                                "Action"]
        assert view["count"] == f"2 statements · {shown}"
        assert view["rows"][0][2:4] == [whole(january[amount]), str(january[count])]
    assert true_only["stored"] == "true"


CHART = r"""
const chart = () => ({
  legend: els.monthlyChart.innerHTML.match(/<span class="chart-legend">([\s\S]*?)<\/span>\s*<\/div>/)[1],
  values: [...els.monthlyChart.innerHTML.matchAll(/<span class="bar-value( bar-value-true)?">([^<]*)<\/span>/g)]
    .map((m) => [m[1] ? "true" : "shown", m[2]]),
});
"""


def test_the_monthly_chart_follows_the_basis_and_the_choice_holds_with_storage_blocked(tmp_path, monkeypatch):
    """One page never shows two different figures as a month's deposits: the chart above the table plots the basis
    the table shows. Where the browser refuses storage, the choice still takes effect for the page."""
    package = _package({"jan": _single(1), "feb": _single(2)}, tmp_path, monkeypatch)
    documents = {doc["id"]: doc for doc in package["documents"]}
    result = run_dashboard(CELLS + CHART + f"""
localStorage.getItem = () => {{ throw new Error("storage blocked"); }};
localStorage.setItem = () => {{ throw new Error("storage blocked"); }};
currentJobIds = ['jan', 'feb']; renderPackageAnalysis({json.dumps(package)});
const both = {{...monthly(), chart: chart()}};
setMonthlyDepositsView('true');
const trueOnly = {{...monthly(), chart: chart(), select: els.monthlyDepositsView.value}};
setMonthlyDepositsView('total');
console.log(JSON.stringify({{both, trueOnly, totalOnly: {{...monthly(), chart: chart()}}}}));
""")
    whole = lambda value: f"{round(value):,}"  # noqa: E731
    jan, feb = documents["jan"], documents["feb"]
    both, true_only, total_only = result["both"], result["trueOnly"], result["totalOnly"]
    assert len(both["head"]) == 9
    assert both["chart"]["values"] == [["shown", whole(jan["credits"])], ["true", whole(jan["verified_revenue_total"])],
                                       ["shown", whole(feb["credits"])], ["true", whole(feb["verified_revenue_total"])]]
    assert "Total deposits" in both["chart"]["legend"] and "True deposits (revenue only)" in both["chart"]["legend"]
    # Storage refused the choice; the page still took it.
    assert true_only["select"] == "true" and true_only["head"][2] == "Monthly Deposits ($)"
    assert true_only["count"] == "2 statements · True monthly deposits: revenue only"
    assert true_only["chart"]["values"] == [["shown", whole(jan["verified_revenue_total"])],
                                            ["shown", whole(feb["verified_revenue_total"])]]
    assert "True deposits (revenue only) and ledger" in true_only["chart"]["legend"]
    assert total_only["chart"]["values"] == [["shown", whole(jan["credits"])], ["shown", whole(feb["credits"])]]
    assert "Total deposits (everything going in) and ledger" in total_only["chart"]["legend"]


def test_the_all_accounts_choice_holds_with_storage_blocked():
    result = run_dashboard("""
localStorage.getItem = () => { throw new Error("storage blocked"); };
localStorage.setItem = () => { throw new Error("storage blocked"); };
const before = allAccountsView();
setAllAccountsView(true);
console.log(JSON.stringify({before, after: allAccountsView(), toggle: els.allAccountsToggle.checked}));
""")
    assert result == {"before": False, "after": True, "toggle": True}


def test_true_deposits_not_established_and_a_failed_statement_read_n_a(tmp_path, monkeypatch):
    package = _package({"jan": _single(1), "feb": _single(2)}, tmp_path, monkeypatch)
    jan, feb = sorted(package["documents"], key=lambda doc: doc["id"] != "jan")
    feb["verified_revenue_established"] = False  # e.g. a credit the classifier left without a revenue state
    jan["status"] = "failed"
    result = run_dashboard(CELLS + CHART + f"""
currentJobIds = ['jan', 'feb']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...monthly(), chart: chart()}}));
""")
    failed, unknown = result["rows"]
    # A failed statement has no figures at all, not a month of zeros.
    assert failed[2:8] == ["N/A"] * 6 and failed[8] == "Unavailable"
    assert unknown[2] == f"{round(feb['credits']):,}" and unknown[4:6] == ["N/A", "N/A"]
    # The chart says what the table says: nothing for the failed month, no True deposits for the other.
    assert result["chart"]["values"] == [["shown", "N/A"], ["true", "N/A"],
                                         ["shown", f"{round(feb['credits']):,}"], ["true", "N/A"]]


def test_true_deposits_of_a_payload_that_does_not_say_read_n_a(tmp_path, monkeypatch):
    """A package row without `verified_revenue_established` (none the server sends today) is not taken as
    established: True deposits read N/A, Total deposits stand."""
    package = _package({"jan": _single(1)}, tmp_path, monkeypatch)
    del package["documents"][0]["verified_revenue_established"]
    result = run_dashboard(CELLS + CHART + f"""
currentJobIds = ['jan']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{...monthly(), chart: chart()}}));
""")
    row = result["rows"][0]
    assert row[2] == f"{round(package['documents'][0]['credits']):,}" and row[4:6] == ["N/A", "N/A"]
    assert result["chart"]["values"][1] == ["true", "N/A"]


PENDING_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0), (4, "DEPOSIT FABRICATED ONE", 300.0),
                (6, "DEPOSIT FABRICATED TWO", 200.0), (27, "SERVICE FEE", -15.0)]


def _pending(month):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, PENDING_ROWS,
                                           month))


def _decided(analysis, locations, decision):
    from analysis.revenue import apply_serialized_revenue_review
    for location in locations:
        analysis = apply_serialized_revenue_review(copy.deepcopy(analysis), source_location=location,
                                                   decision=decision)
    return analysis


def test_the_bulk_bar_shows_only_while_deposits_are_ticked_and_saves_one_batch_per_statement(tmp_path, monkeypatch):
    before = {"a": _pending(1), "b": _pending(2)}
    after = {"a": _decided(before["a"], ["transaction:2", "transaction:3"], "confirm"),
             "b": _decided(before["b"], ["transaction:2"], "confirm")}
    package_before = _package(before, tmp_path, monkeypatch)
    package_after = _package(after, tmp_path, monkeypatch)
    responses = {"/package_analysis": {"json": package_after},
                 "/analysis/a/revenue-reviews": {"json": {"analysis": after["a"], "applied": 2}},
                 "/analysis/b/revenue-reviews": {"json": {"analysis": after["b"], "applied": 1}}}
    result = run_dashboard(CELLS + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
localStorage.setItem('bsa-monthly-deposits', 'true');
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package_before)});
const table = els.transactionTable.innerHTML;
const start = {{hidden: els.bulkReviewBar.hidden, boxes: (table.match(/data-bulk-job=/g) || []).length,
               trueBefore: monthly().rows.map((row) => row[2])}};
const tick = (job, location) => {{
  const box = fakeElement(`box-${{job}}-${{location}}`); box.checked = true;
  box.attributes['data-bulk-job'] = job; box.attributes['data-bulk-location'] = location; box.closest = () => box;
  els.transactionTable.listeners.change[0]({{target: box}});
}};
tick('a', 'transaction:2'); tick('a', 'transaction:3'); tick('b', 'transaction:2');
const ticked = {{hidden: els.bulkReviewBar.hidden, count: els.bulkReviewCount.textContent}};
const confirm = fakeElement('confirm'); confirm.attributes['data-bulk-review'] = 'confirm'; confirm.closest = () => confirm;
els.bulkReviewBar.listeners.click[0]({{target: confirm}}); await settle(); await settle();
const posts = REQUESTS.filter((request) => request.method === 'POST')
  .map((request) => [request.url, JSON.parse(request.body).decisions]);
console.log(JSON.stringify({{start, ticked, posts, after: {{hidden: els.bulkReviewBar.hidden,
  selected: bulkSelection.size, trueAfter: monthly().rows.map((row) => row[2]),
  boxes: (els.transactionTable.innerHTML.match(/data-bulk-job=/g) || []).length}}}}));
""")
    start, ticked, after = result["start"], result["ticked"], result["after"]
    assert start["hidden"] is True and start["boxes"] == 4  # two deposits awaiting review on each statement
    assert ticked == {"hidden": False, "count": "3 selected"}
    assert result["posts"] == [
        ["/analysis/a/revenue-reviews", [{"source_location": "transaction:2", "decision": "confirm"},
                                         {"source_location": "transaction:3", "decision": "confirm"}]],
        ["/analysis/b/revenue-reviews", [{"source_location": "transaction:2", "decision": "confirm"}]]]
    # Saved: the bar goes away, the deposits no longer await review, and True deposits take them in.
    assert after["hidden"] is True and after["selected"] == 0 and after["boxes"] == 1
    trues = {doc["id"]: f"{round(doc['verified_revenue_total']):,}" for doc in package_after["documents"]}
    assert after["trueAfter"] == [trues["a"], trues["b"]] and after["trueAfter"] != start["trueBefore"]


def test_a_refused_batch_keeps_its_ticks_and_says_why(tmp_path, monkeypatch):
    before = {"a": _pending(1)}
    responses = {"/analysis/a/revenue-reviews": {"status": 400, "json": {"error": "fabricated refusal"}},
                 "/analysis/a": {"json": {"analysis": before["a"], "analysis_error": None}},
                 "/markdown/a": {"text": ""}}
    result = run_dashboard(f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
const said = [];
notify = (message, tone) => said.push([message, tone]);
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
const box = fakeElement('box'); box.checked = true; box.attributes['data-bulk-job'] = 'a';
box.attributes['data-bulk-location'] = 'transaction:2'; box.closest = () => box;
els.transactionTable.listeners.change[0]({{target: box}});
const reject = fakeElement('reject'); reject.attributes['data-bulk-review'] = 'reject'; reject.closest = () => reject;
els.bulkReviewBar.listeners.click[0]({{target: reject}}); await settle();
console.log(JSON.stringify({{said: said.filter(([, tone]) => tone === 'red'), selected: bulkSelection.size,
  hidden: els.bulkReviewBar.hidden}}));
""")
    assert result["said"] == [["Not saved: fabricated refusal", "red"]]
    assert result["selected"] == 1 and result["hidden"] is False


def test_the_page_carries_the_branch_s_controls_in_the_new_shell(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path))
    from webapp.app import app

    page = app.test_client().get("/").get_data(as_text=True)
    settings = page[page.index('id="settingsView"'):page.index('id="statementModalBackdrop"')]
    assert 'id="allAccountsToggle"' in settings and "Statements</h2>" in settings
    assert 'id="accountsPanel"' in page and 'id="openTextBtn"' in page and 'id="modalExtractionReview"' in page
    assert ".status-message.review" in page and ".results-content.is-withheld" in page
    assert 'id="settingsBtn"' not in page  # the old header popover is gone
    assert os.path.basename(__file__)  # keeps the module importable under any runner
