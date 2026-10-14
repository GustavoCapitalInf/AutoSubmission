"""The dashboard fixes of the code audit of 2026-10-13 (batch A05), driven end to end: the whole webapp/static/app.js
runs in node on the fake page (tests/webapp_js_harness.py). Fabricated statements and answers only.

F1: the statement window draws only the answer for the statement it was last opened for. An answer for a statement
opened earlier (and closed) is dropped, so its rows never sit in the next statement's window, whose review buttons name
that next statement's job. The answers are released by hand, in the order each test names, so no test depends on a
timer."""
import copy
import json

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Two fabricated statements whose deposits awaiting review stand at different row positions: A's after three debits,
# B's from its second row. Whole-dollar fabricated amounts.
ROWS_A = [(3, "CARD PURCHASE FABRICATED SUPPLY", -312.0), (5, "CHECK 1041", -50.0), (7, "SERVICE FEE", -15.0),
          (9, "DEPOSIT FABRICATED ONE", 300.0), (11, "DEPOSIT FABRICATED TWO", 200.0),
          (13, "DEPOSIT FABRICATED THREE", 700.0)]
ROWS_B = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0), (4, "DEPOSIT FABRICATED FOUR", 900.0),
          (6, "DEPOSIT FABRICATED FIVE", 400.0), (27, "SERVICE FEE", -15.0)]


def _statement(rows, month):
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report

    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows, month))


def _confirmed(analysis, location):
    from analysis.revenue import apply_serialized_revenue_review

    return apply_serialized_revenue_review(copy.deepcopy(analysis), source_location=location, decision="confirm")


# The window's GET requests (/analysis/<job>, /markdown/<job>) are held until the test answers them: `answer(n, ...)`
# answers the n-th opening (0-based). `shown()` is what the window holds.
WINDOW = r"""
const attrsOf = (tag) => Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
const buttonsIn = (html) => [...html.matchAll(/<button class="table-action[^"]*" type="button"([^>]*)>/g)]
  .map((m) => attrsOf(m[1])).filter((attrs) => attrs["data-revenue-review-action"]);
const realFetch = globalThis.fetch;
const held = [];
globalThis.fetch = (url, options = {}) => {
  const text = String(url);
  if ((options.method || "GET") === "GET" && /^\/(analysis|markdown)\/[^/]+$/.test(text)) {
    REQUESTS.push({ url: text, method: "GET", body: null });
    return new Promise((resolve) => held.push({ url: text, resolve }));
  }
  return realFetch(url, options);
};
const answer = async (n, analysis, status = 200) => {
  const [first, second] = held.slice(2 * n, 2 * n + 2);
  if (!first.url.startsWith("/analysis/") || !second.url.startsWith("/markdown/")) throw new Error("request order");
  first.resolve(new Response(status === 200 ? JSON.stringify({ analysis, analysis_error: null }) : "not found",
    { status, headers: { "Content-Type": status === 200 ? "application/json" : "text/plain" } }));
  second.resolve(new Response("", { status: 200 }));
  await settle(); await settle();
};
let focused = 0;
els.statementModalClose.focus = () => { focused += 1; };
const shown = () => ({ job: modalJobId, title: els.statementModalTitle.textContent,
  subtitle: els.statementModalSubtitle.textContent, rows: els.statementModalTransactions.innerHTML,
  count: els.statementModalTransactionCount.textContent, json: els.modalJsonDownload.href,
  extraction: els.modalExtractionReview.href, buttons: buttonsIn(els.statementModalTransactions.innerHTML) });
"""


def _window(body, **payloads):
    return run_dashboard(WINDOW + "".join(f"const {name} = {json.dumps(value)};\n" for name, value in payloads.items())
                         + body)


def _alone(payload, job="jobB"):
    """The window opened once for `job`, answered with `payload`: what the other tests' windows must equal."""
    return _window(f"""
openStatementModal("{job}");
await answer(0, P);
console.log(JSON.stringify(shown()));
""", P=payload)


def test_a_statement_window_never_shows_the_answer_for_a_statement_opened_before_it():
    """Statement A opened and closed, then B opened: A's answer, arriving after B's, is not drawn into B's window, and
    a review pressed there posts one of B's own rows to B."""
    a, b = _statement(ROWS_A, 1), _statement(ROWS_B, 2)
    alone = _alone(b)
    result = _window("""
FAKE_RESPONSES["/analysis/jobB/revenue-review"] = { json: { analysis: B } };
openStatementModal("jobA");
closeStatementModal();
openStatementModal("jobB");
await answer(1, B);
const first = shown();
await answer(0, A);
const after = shown();
const pressed = after.buttons[0];
const button = fakeElement("row"); Object.assign(button.attributes, pressed);
await submitRevenueReview(button); await settle();
const posts = REQUESTS.filter((request) => request.method === "POST").map((request) => [request.url, JSON.parse(request.body)]);
console.log(JSON.stringify({ first, after, pressed, posts }));
""", A=a, B=b)
    assert alone["buttons"], "B must have deposits awaiting review"
    assert {button["data-revenue-review-job"] for button in alone["buttons"]} == {"jobB"}
    assert result["first"] == alone
    # A's late answer changes nothing: B's period, B's rows, B's buttons, B's links.
    assert result["after"] == alone
    assert "2031-01" not in result["after"]["subtitle"] and "FABRICATED ONE" not in result["after"]["rows"]
    own = {(button["data-revenue-review-location"], button["data-revenue-review-action"]) for button in alone["buttons"]}
    assert len(result["posts"]) == 1
    url, body = result["posts"][0]
    assert url == "/analysis/jobB/revenue-review"
    assert (body["source_location"], body["decision"]) in own


def test_an_answer_for_a_statement_window_closed_before_it_came_is_dropped():
    """Nothing reopened: the late answer is not drawn into the hidden window and does not take the focus."""
    result = _window("""
openStatementModal("jobA");
const opened = shown();
closeStatementModal();
await answer(0, A);
console.log(JSON.stringify({ opened, after: shown(), analysis: modalAnalysis, focused }));
""", A=_statement(ROWS_A, 1))
    assert result["opened"]["title"] == "Loading statement"
    assert result["after"] == {**result["opened"], "job": None}
    assert result["analysis"] is None and result["focused"] == 0


def test_a_late_failure_for_an_earlier_statement_leaves_the_next_statement_s_window_alone():
    b = _statement(ROWS_B, 2)
    alone = _alone(b)
    result = _window("""
openStatementModal("jobA");
closeStatementModal();
openStatementModal("jobB");
await answer(1, B);
await answer(0, null, 404);
console.log(JSON.stringify(shown()));
""", B=b)
    assert result == alone
    assert result["title"] != "Statement unavailable"


def test_a_statement_reopened_shows_its_newest_answer_whichever_answer_comes_last():
    """The same statement opened twice (a decision saved in between): the second opening's answer stands even when
    the first opening's, older, arrives after it."""
    older = _statement(ROWS_A, 1)
    alone = _alone(older, job="jobA")
    location = alone["buttons"][0]["data-revenue-review-location"]
    newer = _confirmed(older, location)
    alone_newer = _alone(newer, job="jobA")
    assert alone_newer != alone
    result = _window("""
openStatementModal("jobA");
closeStatementModal();
openStatementModal("jobA");
await answer(1, NEWER);
await answer(0, OLDER);
console.log(JSON.stringify(shown()));
""", OLDER=older, NEWER=newer)
    assert result == alone_newer
