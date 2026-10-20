"""The dashboard fixes of the code audit of 2026-10-13 (batch A05), driven end to end: the whole webapp/static/app.js
runs in node on the fake page (tests/webapp_js_harness.py). Fabricated statements and answers only.

F1: the statement window draws only the answer for the statement it was last opened for. An answer for a statement
opened earlier (and closed) is dropped, so its rows never sit in the next statement's window, whose review buttons name
that next statement's job. The answers are released by hand, in the order each test names, so no test depends on a
timer.

F2: formatMoney keeps its number formatters instead of building one or two on every call (a ledger row formats two
or three amounts), and every string is the one a freshly built formatter writes.

F3: a job the server marked `interrupted` (it restarted while the job was queued or processing) ends the poll like an
`error`: a single upload shows the server's note, and a package counts the member as finished and failed, then loads.
The poll tests run the poller's waits at once and record what it asked for, so they too depend on no timer.

F5: a status request that fails for a moment (a dropped connection, a proxy's 5xx, 408 or 429) is asked again, each
wait longer, up to five times in a row before the page reports it; any other failure (404: the server does not know
the job) is reported at once, and a failure that comes back for an upload no longer on screen is not drawn at all.

F9: a refused save of the NSF switch whose body is not JSON (a proxy's error page) reads "Save failed (<status>)", as
the Zelle and flag saves do, instead of a JSON parser's complaint."""
import copy
import inspect
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


# ------------------------------------------------------------------------------------------------- F2: formatMoney
# The formatter as it was before F2, built afresh on every call: the reference every string is held to.
FRESH = r"""
const fresh = (value, currency = "USD") => {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  const amount = n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (!currency) return amount;
  try { return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n); } catch { return `$${amount}`; }
};
"""

# Every sign and rounding edge (cents ties, a negative that rounds to zero, -0), large and tiny magnitudes, the
# strings and non-numbers a payload can carry; the currencies the parsers publish (USD, CAD), others a statement could
# declare, the unit-less null and empty forms, codes written in lower case and codes Intl refuses.
VALUES = r"""[0, -0, 0.004, -0.004, 0.005, -0.005, 0.015, -0.015, 1.005, 2.675, -2.675, 10, -10, 1234.5, -1234.56,
  999999.995, -999999.995, 123456789.125, 1e15, -1e15, 1e21, -1e21, 5e-7, "12.5", "-12.50", "+3", " 7 ", "1e3", "",
  null, undefined, "abc", NaN, Infinity, -Infinity, true, false, [], {}]"""
CURRENCIES = r"""["USD", "CAD", "EUR", "GBP", "MXN", "JPY", "CHF", "usd", "cad", null, "", 0, false, "US$", "DOLLARS",
  "ZZ", "NOTACODE", 5, {}, [], ["CAD"]]"""


def test_money_reads_as_a_fresh_formatter_writes_it():
    """Every value in every currency, in both orders and twice, and with the currency left out (the USD default), reads
    exactly as a newly built formatter writes it; a code Intl refuses still reads `$<amount>`."""
    result = run_dashboard(FRESH + f"""
const values = {VALUES};
const currencies = {CURRENCIES};
const differences = [];
let pairs = 0;
for (const order of [currencies, [...currencies].reverse()]) {{
  for (const currency of order) for (const value of values) for (let twice = 0; twice < 2; twice += 1) {{
    pairs += 1;
    if (formatMoney(value, currency) !== fresh(value, currency)) differences.push([String(value), String(currency)]);
  }}
}}
for (const value of values) {{
  pairs += 2;
  if (formatMoney(value) !== fresh(value)) differences.push([String(value), "default"]);
  if (formatMoney(value, undefined) !== fresh(value, undefined)) differences.push([String(value), "undefined"]);
}}
console.log(JSON.stringify({{ differences, pairs, samples: [formatMoney(-1234.5, "USD"), formatMoney(-1234.5, "CAD"),
  formatMoney(-1234.5, null), formatMoney(-1234.5, "NOTACODE"), formatMoney(-0.004, "USD"), formatMoney(5)] }}));
""")
    assert result["differences"] == []
    assert result["pairs"] > 3000
    assert result["samples"] == ["-$1,234.50", "-CA$1,234.50", "-1,234.50", "$-1,234.50", "-$0.00", "$5.00"]


def test_money_builds_each_formatter_once():
    """A thousand amounts over USD, CAD, no unit and a refused code build at most one formatter for the bare figure
    and one per code, and never fall back to a per-call toLocaleString."""
    result = run_dashboard(r"""
const RealNumberFormat = Intl.NumberFormat;
let built = 0;
Intl.NumberFormat = new Proxy(RealNumberFormat, { construct(target, args) { built += 1; return Reflect.construct(target, args); } });
const realLocale = Number.prototype.toLocaleString;
let localeCalls = 0;
Number.prototype.toLocaleString = function (...args) { localeCalls += 1; return realLocale.apply(this, args); };
const codes = ["USD", "CAD", null, "NOTACODE"];
for (let index = 0; index < 1000; index += 1) formatMoney(index * 37 - 4000, codes[index % codes.length]);
console.log(JSON.stringify({ built, localeCalls }));
""")
    assert result["built"] <= 4
    assert result["localeCalls"] == 0


# ------------------------------------------------------------------------------------------ F3: the end of a poll
def _interrupted_note():
    """The server's own words for a job it marked interrupted (webapp/jobs.py JobStore.mark_interrupted)."""
    from webapp.jobs import JobStore

    return inspect.signature(JobStore.mark_interrupted).parameters["note"].default


# /status/<job> answers from a plan per job (`PLANS`, set by the test): each step a status reply, {http: <code>} for
# an error page, "network" for a request that never reached the server, or "hold" for one that waits until the test
# drops it (`dropHeld`); the last step repeats. The poller's waits
# (1 s or more) run at once and are recorded in `waits`; `finish()` lets anything pending run, then stops the poll.
POLL = r"""
const realSetTimeout = globalThis.setTimeout;
const waits = [];
let stopped = false;
globalThis.setTimeout = (callback, ms, ...rest) => {
  if (ms >= 1000) {
    if (stopped) return 0;
    waits.push(ms);
    return realSetTimeout(callback, 1, ...rest);
  }
  return realSetTimeout(callback, ms, ...rest);
};
const asked = {};
const heldStatus = [];
// A held status request ("hold") that now fails as a dropped connection does.
const dropHeld = async (job) => {
  heldStatus.filter((entry) => entry.job === job).forEach((entry) => entry.reject(new TypeError("Failed to fetch")));
  await settle();
};
globalThis.fetch = ((realFetch) => (url, options = {}) => {
  const match = /^\/status\/([^/?]+)$/.exec(String(url));
  if (!match) return realFetch(url, options);
  const job = match[1];
  REQUESTS.push({ url: String(url), method: "GET", body: null });
  asked[job] = (asked[job] || 0) + 1;
  const plan = PLANS[job];
  const step = plan[Math.min(asked[job] - 1, plan.length - 1)];
  if (step === "network") return Promise.reject(new TypeError("Failed to fetch"));
  if (step === "hold") return new Promise((resolve, reject) => heldStatus.push({ job, reject }));
  if (step.http) return Promise.resolve(new Response(step.text || "<html>error</html>",
    { status: step.http, headers: { "Content-Type": "text/html" } }));
  return Promise.resolve(new Response(JSON.stringify(step), { status: 200, headers: { "Content-Type": "application/json" } }));
})(globalThis.fetch);
const said = [];
notify = (message, tone) => said.push([message, tone]);
const pdf = (name) => new File([new Uint8Array(64)], name, { type: "application/pdf" });
const upload = (...ids) => {
  FAKE_RESPONSES["/upload"] = { json: { jobs: ids.map((id) => ({ id, page_count: 2 })) } };
  uploadFiles(ids.map((id) => pdf(`fabricated-${id}.pdf`)));
};
const until = async (done, limit = 150) => { for (let i = 0; i < limit && !done(); i += 1) await settle(); };
const finish = async () => {
  for (let i = 0; i < 10; i += 1) await settle();
  stopped = true;
  if (pollTimer) clearTimeout(pollTimer);
  await settle();
};
const page = () => ({ heading: els.statusHeading.textContent, message: els.statusMessage.textContent,
  busy: els.progressTrack.classList.contains("show"), asked, waits,
  fetched: REQUESTS.filter((request) => !request.url.startsWith("/status/")).map((request) => request.url.split("?")[0]),
  red: said.filter(([, tone]) => tone === "red").map(([message]) => message) });
"""


def _poll(plans, body, **payloads):
    return run_dashboard(POLL + f"const PLANS = {json.dumps(plans)};\n"
                         + "".join(f"const {name} = {json.dumps(value)};\n" for name, value in payloads.items()) + body)


def _status(status, **extra):
    return {"status": status, "stage": status, "page_count": 2, **extra}


def _package_payload(tmp_path, monkeypatch, members):
    """The package as /package_analysis serves it, for (job id, status, analysis or None, error or None) members."""
    from webapp.app import _package_analysis, store
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)  # the NSF setting of a scratch folder
    return _package_analysis([Job(id=job_id, filename=f"fabricated-{job_id}.pdf", status=status, analysis=analysis,
                                  error=error, content_sha256=job_id)
                              for job_id, status, analysis, error in members])


def test_a_job_the_server_marked_interrupted_ends_the_poll_and_says_so():
    note = _interrupted_note()
    result = _poll({"j": [_status("interrupted", error=note)]}, """
upload("j");
await until(() => els.statusHeading.textContent === "Processing failed");
await finish();
console.log(JSON.stringify(page()));
""")
    assert result["asked"] == {"j": 1} and result["waits"] == []
    assert result["heading"] == "Processing failed" and result["message"] == note
    assert result["busy"] is False
    assert result["red"] == [f"Processing failed: {note}"]


def test_an_interrupted_job_the_server_gave_no_words_for_says_it_was_interrupted():
    result = _poll({"j": [_status("interrupted")]}, """
upload("j");
await until(() => els.statusHeading.textContent === "Processing failed");
await finish();
console.log(JSON.stringify(page()));
""")
    assert result["asked"] == {"j": 1}
    assert result["message"] == "Processing was interrupted"


def test_a_restart_the_page_never_saw_ends_the_poll_at_the_interrupted_answer():
    note = _interrupted_note()
    result = _poll({"j": [_status("processing"), _status("processing"), _status("interrupted", error=note)]}, """
upload("j");
await until(() => els.statusHeading.textContent === "Processing failed");
await finish();
console.log(JSON.stringify(page()));
""")
    assert result["asked"] == {"j": 3} and result["waits"] == [1400, 1400]
    assert result["message"] == note and result["busy"] is False


def test_after_an_interrupted_job_a_recent_statement_opens_again():
    """The poll's end clears the progress bar, which otherwise keeps every Recent statement from opening."""
    b = _statement(ROWS_B, 2)
    result = _poll({"j": [_status("interrupted", error=_interrupted_note())]}, """
FAKE_RESPONSES["/analysis/kept"] = { json: { analysis: B, analysis_error: null } };
FAKE_RESPONSES["/markdown/kept"] = { text: "" };
rememberAnalysis({ kind: "statement", key: "kept", ids: ["kept"], label: "Fabricated statement", meta: "", tone: "green" });
upload("j");
await until(() => els.statusHeading.textContent === "Processing failed");
await finish();
openRecent("kept");
await settle(); await settle();
console.log(JSON.stringify({ ...page(), current: currentJobId, view: currentView }));
""", B=b)
    assert "/analysis/kept" in result["fetched"]
    assert result["current"] == "kept" and result["view"] == "results"


def test_a_package_with_an_interrupted_member_stops_polling_and_loads(tmp_path, monkeypatch):
    note = _interrupted_note()
    package = _package_payload(tmp_path, monkeypatch, [("p1", "done", _statement(ROWS_B, 2), None),
                                                      ("p2", "interrupted", None, note)])
    result = _poll({"p1": [_status("done")], "p2": [_status("interrupted", error=note)]}, """
FAKE_RESPONSES["/package_analysis"] = { json: PACKAGE };
upload("p1", "p2");
await until(() => REQUESTS.some((request) => request.url.startsWith("/package_analysis")));
await finish();
console.log(JSON.stringify({ ...page(), view: [currentView, activeNav] }));
""", PACKAGE=package)
    assert result["asked"] == {"p1": 1, "p2": 1} and result["waits"] == []
    assert result["fetched"].count("/package_analysis") == 1
    assert result["busy"] is False and result["view"] == ["results", "packages"]


def test_the_poll_still_ends_on_done_and_error_as_before(tmp_path, monkeypatch):
    """Controls: a finished job loads its results, a failed one reports the server's error, and a package with a
    failed member loads, each after one status request."""
    b = _statement(ROWS_B, 2)
    package = _package_payload(tmp_path, monkeypatch, [("p1", "done", b, None),
                                                      ("p2", "error", None, "fabricated failure")])
    done = _poll({"j": [_status("done")]}, """
FAKE_RESPONSES["/analysis/j"] = { json: { analysis: B, analysis_error: null } };
FAKE_RESPONSES["/markdown/j"] = { text: "" };
upload("j");
await until(() => currentView === "results");
await finish();
console.log(JSON.stringify({ ...page(), view: currentView }));
""", B=b)
    assert done["asked"] == {"j": 1} and "/analysis/j" in done["fetched"] and done["view"] == "results"
    failed = _poll({"j": [_status("error", error="fabricated failure")]}, """
upload("j");
await until(() => els.statusHeading.textContent === "Processing failed");
await finish();
console.log(JSON.stringify(page()));
""")
    assert failed["asked"] == {"j": 1} and failed["message"] == "fabricated failure"
    member = _poll({"p1": [_status("done")], "p2": [_status("error", error="fabricated failure")]}, """
FAKE_RESPONSES["/package_analysis"] = { json: PACKAGE };
upload("p1", "p2");
await until(() => activeNav === "packages");
await finish();
console.log(JSON.stringify({ ...page(), view: [currentView, activeNav] }));
""", PACKAGE=package)
    assert member["asked"] == {"p1": 1, "p2": 1} and member["fetched"].count("/package_analysis") == 1
    assert member["view"] == ["results", "packages"]


# --------------------------------------------------------------------------- F5: a status request that fails briefly
SINGLE_LOADS = """
FAKE_RESPONSES["/analysis/j"] = { json: { analysis: B, analysis_error: null } };
FAKE_RESPONSES["/markdown/j"] = { text: "" };
upload("j");
await until(() => currentView === "results" || els.statusHeading.textContent === "Processing failed", 400);
await finish();
console.log(JSON.stringify({ ...page(), view: currentView, recent: recentAnalyses.map((item) => item.key) }));
"""


def test_a_status_request_that_fails_for_a_moment_is_asked_again_and_the_results_load():
    """A dropped connection, then a proxy's 502, then the answer: three requests, each wait longer, and the results
    load (and the statement is in Recent) instead of a failure the server never had."""
    result = _poll({"j": ["network", {"http": 502}, _status("done")]}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 3} and result["waits"] == [1400, 2800]
    assert result["view"] == "results" and "/analysis/j" in result["fetched"]
    assert result["red"] == [] and result["recent"] == ["j"]


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_every_transient_status_failure_is_asked_again(code):
    result = _poll({"j": [{"http": code}, _status("done")]}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 2} and result["waits"] == [1400]
    assert result["view"] == "results" and result["red"] == []


@pytest.mark.parametrize("code", [400, 403, 404])
def test_a_status_failure_that_is_not_transient_is_reported_at_once(code):
    result = _poll({"j": [{"http": code}, _status("done")]}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 1} and result["waits"] == []
    assert result["heading"] == "Processing failed" and result["message"] == f"Status failed ({code})"
    assert "/analysis/j" not in result["fetched"]


def test_status_failures_that_go_on_are_reported_after_five_retries():
    """Six 502s in a row: the first request and five retries, waiting 1.4 s more each time (21 s in all), then the
    failure is reported with its status; the progress bar is cleared."""
    result = _poll({"j": [{"http": 502}] * 6 + [_status("done")]}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 6} and result["waits"] == [1400, 2800, 4200, 5600, 7000]
    assert result["heading"] == "Processing failed" and result["message"] == "Status failed (502)"
    assert result["busy"] is False and result["red"] == ["Processing failed: Status failed (502)"]


def test_a_connection_that_stays_down_is_reported_after_the_retries():
    result = _poll({"j": ["network"]}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 6}
    assert result["heading"] == "Processing failed" and result["message"] == "Status failed (Failed to fetch)"


def test_only_failures_in_a_row_count_toward_the_retries():
    """Five failures, an answer, five more failures, then done: the count starts again after each answer."""
    plan = [{"http": 502}] * 5 + [_status("processing")] + [{"http": 503}] * 5 + [_status("done")]
    result = _poll({"j": plan}, SINGLE_LOADS, B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 12} and result["view"] == "results" and result["red"] == []
    assert result["waits"] == [1400, 2800, 4200, 5600, 7000, 1400, 1400, 2800, 4200, 5600, 7000]


def test_a_restart_inside_the_retries_ends_at_the_interrupted_answer():
    """The proxy answers 502 while the server restarts, then the new process answers `interrupted`: the poll ends
    with the server's note (F3), never an endless spinner."""
    note = _interrupted_note()
    result = _poll({"j": [{"http": 502}, {"http": 502}, _status("interrupted", error=note)]}, SINGLE_LOADS,
                   B=_statement(ROWS_B, 2))
    assert result["asked"] == {"j": 3} and result["waits"] == [1400, 2800]
    assert result["heading"] == "Processing failed" and result["message"] == note and result["busy"] is False


def test_a_package_member_whose_status_fails_for_a_moment_recovers(tmp_path, monkeypatch):
    b = _statement(ROWS_B, 2)
    package = _package_payload(tmp_path, monkeypatch, [("p1", "done", b, None), ("p2", "done", b, None)])
    result = _poll({"p1": [{"http": 502}, _status("done")], "p2": [_status("processing"), _status("done")]}, """
FAKE_RESPONSES["/package_analysis"] = { json: PACKAGE };
upload("p1", "p2");
await until(() => activeNav === "packages" || els.statusHeading.textContent === "Processing failed");
await finish();
console.log(JSON.stringify({ ...page(), view: [currentView, activeNav] }));
""", PACKAGE=package)
    assert result["asked"] == {"p1": 2, "p2": 2} and result["waits"] == [1400]
    assert result["fetched"].count("/package_analysis") == 1 and result["view"] == ["results", "packages"]
    assert result["red"] == []


@pytest.mark.parametrize("earlier", [["old"], ["old1", "old2"]], ids=["statement", "package"])
def test_a_late_status_failure_from_an_earlier_upload_is_not_drawn_over_the_next_one(earlier):
    """A status request of the previous upload (a statement or a package) fails after the next upload started: the
    next upload's page stays as it is, with no failure and no red notification."""
    plans = {job: ["hold"] for job in [*earlier, "new"]}
    result = _poll(plans, f"""
upload(...{json.dumps(earlier)});
await settle();
upload("new");
await settle();
const before = page();
for (const job of {json.dumps(earlier)}) await dropHeld(job);
await settle();
const after = page();
await finish();
console.log(JSON.stringify({{ before, after, current: currentJobId }}));
""")
    assert result["before"]["heading"] == "Processing statement"
    assert result["after"]["heading"] == "Processing statement" and result["after"]["busy"] is True
    assert result["after"]["red"] == [] and result["current"] == "new"
    assert result["after"]["waits"] == []


# ------------------------------------------------------------------------------------------ F9: the NSF switch save
def _nsf_save(answer):
    """Settings loaded (the switch off), then the switch turned on and the save answered with `answer`."""
    loaded = {"json": {"settings": {"nsf_carry_over": False, "zelle_true_revenue": True}}}
    return run_dashboard(f"""
FAKE_RESPONSES["/api/settings"] = {json.dumps(loaded)};
loadSettings(); await settle();
FAKE_RESPONSES["/api/settings"] = {json.dumps(answer)};
els.nsfCarryOverToggle.checked = true;
els.nsfCarryOverToggle.dispatch("change", {{}});
await settle(); await settle();
console.log(JSON.stringify({{ status: els.settingsStatus.textContent,
  state: els.settingsStatus.getAttribute("data-state"), checked: els.nsfCarryOverToggle.checked,
  disabled: els.nsfCarryOverToggle.disabled,
  posts: REQUESTS.filter((request) => request.method === "POST").map((request) => JSON.parse(request.body)) }}));
""")


@pytest.mark.parametrize("status, body", [(502, "<html><head><title>502 Bad Gateway</title></head></html>"),
                                          (500, "<!doctype html><title>500 Internal Server Error</title>"),
                                          (503, ""), (200, "<html>fabricated sign-in page</html>")])
def test_a_refused_nsf_setting_save_names_its_status_not_a_parser_error(status, body):
    """A body that is not JSON reads "Save failed (<status>)" (a 200 one too: no save the server did not confirm),
    and the switch is put back and can be used again."""
    result = _nsf_save({"status": status, "text": body})
    assert result == {"status": f"Save failed ({status})", "state": "error", "checked": False, "disabled": False,
                      "posts": [{"nsf_carry_over": True}]}


def test_the_nsf_setting_save_still_reads_the_server_s_refusal_and_its_confirmation():
    refused = _nsf_save({"status": 400, "json": {"error": "invalid settings update"}})
    assert refused["status"] == "invalid settings update" and refused["state"] == "error"
    assert refused["checked"] is False and refused["disabled"] is False
    saved = _nsf_save({"json": {"settings": {"nsf_carry_over": True, "zelle_true_revenue": True}}})
    assert saved["status"] == "Saved. NSF counts now carry the balance over inactive days."
    assert saved["state"] is None and saved["checked"] is True and saved["disabled"] is False
