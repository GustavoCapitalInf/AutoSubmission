"""The Re-analyze button of the outdated-rules notice (spec §8.6; the interface contract's C8 and C9), driven end to
end: the whole webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). The notice's markup and
when it shows belong to the dashboard's own plan (C8); this file drives the button. Fabricated statements only."""
import json

import pytest

from tests.test_webapp_review_ui import DRAWN
from tests.test_webapp_studio_views import CHECKING_ROWS, _pending, _report, _serve
from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# One more deposit read under the new rules, so the page drawn from the answer is told apart from the one before.
LATE_ROW = (20, "DEPOSIT FABRICATED LATE", 100.0)


def _statement(rows, month=3):
    """A fabricated business checking statement, analysed by the real analysis path."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows, month))


def _answer(analysis, replayed=0, not_replayed=0, decided_by_rules=0):
    """What POST /analysis/<job>/reanalyze answers."""
    return {"json": {"analysis": analysis, "reviews_replayed": replayed, "reviews_not_replayed": not_replayed,
                     "reviews_decided_by_rules": decided_by_rules}}


def _open_stale(answer):
    """The statement `stale` open as a reopen from Recent shows it, its re-analysis answering `answer`. The button
    carries the label the dashboard draws, the notifications are closed, and the requests so far are forgotten."""
    return (_serve(stale=_statement(CHECKING_ROWS))
            + f"Object.assign(FAKE_RESPONSES, {json.dumps({'/analysis/stale/reanalyze': answer})});\n" + """
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale'); await settle();
const button = document.getElementById('reanalyzeButton');
button.textContent = 'Re-analyze';
els.notificationsPopover.hidden = true;
REQUESTS.length = 0;
""")


CLICK = """
button.dispatch('click', {});
const during = {disabled: button.disabled, label: button.textContent};
await settle();
"""


def test_the_button_reanalyzes_the_statement_shown_and_draws_the_answer():
    fresh = _statement([*CHECKING_ROWS, LATE_ROW])
    result = run_dashboard(_open_stale(_answer(fresh, replayed=2, not_replayed=1, decided_by_rules=1)) + CLICK + """
console.log(JSON.stringify({
  requests: REQUESTS.map((request) => [request.method, request.url, request.body]),
  during, after: {disabled: button.disabled, label: button.textContent},
  rows: currentAnalysis.statement.transactions.length,
  notice: notifications[0], opened: !els.notificationsPopover.hidden}));
""")
    # One request: the page is drawn from the answer, not fetched again.
    assert result["requests"] == [["POST", "/analysis/stale/reanalyze", "{}"]]
    assert result["rows"] == len(CHECKING_ROWS) + 1
    # Held while the statement is re-analyzed, and given its label back after.
    assert result["during"] == {"disabled": True, "label": "Re-analyzing..."}
    assert result["after"] == {"disabled": False, "label": "Re-analyze"}
    # A review that could not be replayed is not left to a dot: the notifications open on it.
    assert result["notice"]["text"] == ("Re-analyzed with the current rules; 1 review needs redoing; "
                                        "1 review is now decided by the rules")
    assert result["notice"]["tone"] == "amber" and result["opened"] is True


def test_the_notification_counts_the_reviews_kept_redone_and_decided_by_the_rules():
    result = run_dashboard("""
console.log(JSON.stringify([[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [4, 3, 0], [0, 0, 1], [2, 1, 2]].map(
  ([kept, redo, ruled]) => reanalysisNotice(
    {reviews_replayed: kept, reviews_not_replayed: redo, reviews_decided_by_rules: ruled}))));
""")
    done = "Re-analyzed with the current rules"
    assert result == [
        [done, "green"], [f"{done}; 1 review kept", "green"], [f"{done}; 2 reviews kept", "green"],
        [f"{done}; 1 review needs redoing", "amber"], [f"{done}; 3 reviews need redoing", "amber"],
        [f"{done}; 1 review is now decided by the rules", "amber"],
        [f"{done}; 1 review needs redoing; 2 reviews are now decided by the rules", "amber"]]


def test_a_reanalysis_that_kept_every_review_is_a_quiet_success():
    result = run_dashboard(_open_stale(_answer(_statement(CHECKING_ROWS), replayed=2)) + CLICK + """
console.log(JSON.stringify({notice: notifications[0], opened: !els.notificationsPopover.hidden}));
""")
    assert result["notice"]["text"] == "Re-analyzed with the current rules; 2 reviews kept"
    assert result["notice"]["tone"] == "green" and result["opened"] is False


@pytest.mark.parametrize("answer, text", [
    ({"status": 409, "json": {"error": "the original PDF is not stored"}},
     "Not re-analyzed: the original PDF is not stored"),
    ({"status": 422, "json": {"error": "no new analysis was saved; the saved analysis is unchanged",
                              "reason": "no deterministic parser matched this statement"}},
     "Not re-analyzed: no new analysis was saved; the saved analysis is unchanged "
     "(no deterministic parser matched this statement)"),
    ({"status": 502, "text": "bad gateway"}, "Not re-analyzed: status 502"),
])
def test_a_refusal_keeps_the_statement_on_screen_and_says_why(answer, text):
    result = run_dashboard(_open_stale(answer) + CLICK + """
console.log(JSON.stringify({rows: currentAnalysis.statement.transactions.length, notice: notifications[0],
  opened: !els.notificationsPopover.hidden, after: {disabled: button.disabled, label: button.textContent}}));
""")
    assert result["rows"] == len(CHECKING_ROWS)
    assert (result["notice"]["text"], result["notice"]["tone"]) == (text, "red")
    assert result["opened"] is True
    assert result["after"] == {"disabled": False, "label": "Re-analyze"}


def test_the_statement_keeps_its_place_in_recent():
    fresh = _statement([*CHECKING_ROWS, LATE_ROW])
    result = run_dashboard(_serve(other=_statement(CHECKING_ROWS, month=4)) + _open_stale(_answer(fresh)) + """
currentJobId = 'other'; currentJobIds = ['other']; loadResults('other'); await settle();
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale', {reveal: false}); await settle();
const before = recentAnalyses.map((item) => item.key);
""" + CLICK + """
console.log(JSON.stringify({before, after: recentAnalyses.map((item) => item.key),
  rows: currentAnalysis.statement.transactions.length}));
""")
    assert result["before"] == result["after"] == ["other", "stale"]
    assert result["rows"] == len(CHECKING_ROWS) + 1


def test_one_click_sends_one_request_and_a_package_sends_none():
    result = run_dashboard(_open_stale(_answer(_statement(CHECKING_ROWS))) + """
button.dispatch('click', {}); button.dispatch('click', {});
await settle();
const single = REQUESTS.filter((request) => request.method === 'POST').length;
currentJobIds = ['stale', 'other'];
button.dispatch('click', {});
await settle();
console.log(JSON.stringify({single, package: REQUESTS.filter((request) => request.method === 'POST').length - single}));
""")
    assert result == {"single": 1, "package": 0}


def test_reviews_wait_while_the_statement_is_being_reanalyzed():
    """A decision made while the re-analysis is in flight would name a row of the analysis it is about to replace:
    neither the bulk bar's batch nor a row's own button sends anything until it answers."""
    answer = json.dumps({"/analysis/stale/reanalyze": _answer(_pending(3))})
    result = run_dashboard(DRAWN + _serve(stale=_pending(3)) + f"Object.assign(FAKE_RESPONSES, {answer});\n" + """
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale'); await settle();
const reanalyze = document.getElementById('reanalyzeButton');
tick(boxesIn(els.transactionTable.innerHTML)[0]);
const row = fakeElement('row'); Object.assign(row.attributes, buttonsIn(els.transactionTable.innerHTML)[0]);
REQUESTS.length = 0;
reanalyze.dispatch('click', {});
press('confirm');
await submitRevenueReview(row);
await settle();
console.log(JSON.stringify({posts: posts().map(([url]) => url), selected: bulkSelection.size,
  busy: [reanalysisBusy, bulkBusy, rowReviewsInFlight]}));
""")
    # The re-analysis answered: its new rows took the tick away, and every flag is down again.
    assert result == {"posts": ["/analysis/stale/reanalyze"], "selected": 0, "busy": [False, False, 0]}
