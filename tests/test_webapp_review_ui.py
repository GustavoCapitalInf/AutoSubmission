"""The dashboard's revenue review, one row or many at once, driven end to end: the whole webapp/static/app.js runs in
node on a fake page (tests/webapp_js_harness.py). What each check pins came out of the audit of the multi-select:
a decision names the account its row belongs to, the selection is what is ticked on screen, a batch and a row's own
button never run at once, and a refused or half-saved batch says so. Fabricated statements only."""
import copy
import json

import pytest

from tests.test_webapp_revenue_batch import _two_accounts
from tests.test_webapp_studio_views import _all_accounts, _package, _pending, _select, _serve
from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The checkboxes and review buttons as drawn: their attributes, read back out of the table's HTML.
DRAWN = r"""
const attrsOf = (tag) => Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
const boxesIn = (html) => [...html.matchAll(/<input type="checkbox" class="tx-select"([^>]*)>/g)]
  .map((m) => ({...attrsOf(m[1]), checked: m[1].trimEnd().endsWith(" checked")}));
const buttonsIn = (html) => [...html.matchAll(/<button class="table-action[^"]*" type="button"([^>]*)>/g)]
  .map((m) => attrsOf(m[1])).filter((attrs) => attrs["data-revenue-review-action"]);
const tick = (attrs) => {
  const box = fakeElement("box"); box.checked = true; box.closest = () => box;
  ["data-bulk-job", "data-bulk-location", "data-bulk-account"].forEach((name) => {
    if (attrs[name] !== undefined) box.attributes[name] = attrs[name]; });
  els.transactionTable.listeners.change[0]({target: box});
};
const press = (action) => {
  const button = fakeElement(action); button.attributes["data-bulk-review"] = action; button.closest = () => button;
  els.bulkReviewBar.listeners.click[0]({target: button});
};
const posts = () => REQUESTS.filter((request) => request.method === "POST")
  .map((request) => [request.url, JSON.parse(request.body)]);
const said = [];
notify = (message, tone) => said.push([message, tone]);
"""


def _decided(analysis, decisions):
    """The analysis after the server applied `decisions`: (location, decision, account)."""
    from analysis.revenue import apply_serialized_revenue_review
    for location, decision, account in decisions:
        analysis = apply_serialized_revenue_review(copy.deepcopy(analysis), source_location=location,
                                                   decision=decision, account=account)
    return analysis


def test_a_tick_on_the_second_account_names_that_account_and_stays_with_it():
    """Both accounts print a `transaction:2` awaiting review. The savings account's is ticked and confirmed: the
    batch names account 2, and picking the checking account shows its own `transaction:2` unticked."""
    before = _two_accounts()
    after = _decided(before, [("transaction:2", "confirm", 2)])
    responses = {"/analysis/doc/revenue-reviews": {"json": {"analysis": after, "applied": 1}}}
    result = run_dashboard(DRAWN + _serve(doc=before) + _all_accounts("on") + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobId = 'doc'; currentJobIds = ['doc']; loadResults('doc'); await settle();
""" + _select(1) + """
const savings = {boxes: boxesIn(els.transactionTable.innerHTML), buttons: buttonsIn(els.transactionTable.innerHTML)};
tick(savings.boxes.find((box) => box["data-bulk-location"] === "transaction:2"));
const ticked = {selected: bulkSelection.size, hidden: els.bulkReviewBar.hidden};
""" + _select(0) + """
const checking = {boxes: boxesIn(els.transactionTable.innerHTML), selected: bulkSelection.size,
                  hidden: els.bulkReviewBar.hidden};
""" + _select(1) + """
tick(boxesIn(els.transactionTable.innerHTML).find((box) => box["data-bulk-location"] === "transaction:2"));
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({savings, ticked, checking, posts: posts()}));
""")
    savings = result["savings"]
    assert {box["data-bulk-account"] for box in savings["boxes"]} == {"2"}
    assert {button["data-revenue-review-account"] for button in savings["buttons"]} == {"2"}
    assert result["ticked"] == {"selected": 1, "hidden": False}
    # Another account starts with nothing ticked, whatever its rows are numbered.
    checking = result["checking"]
    assert checking["selected"] == 0 and checking["hidden"] is True
    assert {box["data-bulk-account"] for box in checking["boxes"]} == {"1"}
    assert not any(box["checked"] for box in checking["boxes"])
    assert result["posts"] == [["/analysis/doc/revenue-reviews",
                                {"decisions": [{"source_location": "transaction:2", "decision": "confirm",
                                                "account": 2}]}]]


def test_a_row_button_on_the_second_account_names_that_account():
    before = _two_accounts()
    after = _decided(before, [("transaction:2", "reject", 2)])
    responses = {"/analysis/doc/revenue-review": {"json": {"analysis": after}}}
    result = run_dashboard(DRAWN + _serve(doc=before) + _all_accounts("on") + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobId = 'doc'; currentJobIds = ['doc']; loadResults('doc'); await settle();
""" + _select(1) + """
const attrs = buttonsIn(els.transactionTable.innerHTML)
  .find((b) => b["data-revenue-review-location"] === "transaction:2" && b["data-revenue-review-action"] === "reject");
const button = fakeElement("row"); Object.assign(button.attributes, attrs);
await submitRevenueReview(button); await settle();
console.log(JSON.stringify({posts: posts()}));
""")
    assert result["posts"] == [["/analysis/doc/revenue-review",
                                {"source_location": "transaction:2", "decision": "reject", "account": 2}]]


def test_a_package_row_of_a_multi_account_statement_is_reviewed_in_its_account(tmp_path, monkeypatch):
    """In a package the rows of a multi-account statement carry their account (webapp/app.py `source_account`): the
    savings deposit's box and batch name account 2, a one-account statement's name none."""
    two, one = _two_accounts(), _pending(2)
    package = _package({"doc": two, "one": one}, tmp_path, monkeypatch)
    responses = {"/analysis/doc/revenue-reviews": {"json": {"analysis": two, "applied": 1}},
                 "/analysis/one/revenue-reviews": {"json": {"analysis": one, "applied": 1}},
                 "/package_analysis": {"json": package}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobIds = ['doc', 'one']; renderPackageAnalysis({json.dumps(package)});
const boxes = boxesIn(els.transactionTable.innerHTML);
boxes.forEach(tick);
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({{boxes, posts: posts()}}));
""")
    accounts = {(box["data-bulk-job"], box.get("data-bulk-account")) for box in result["boxes"]}
    assert accounts == {("doc", "1"), ("doc", "2"), ("one", None)}
    by_url = dict((url, body["decisions"]) for url, body in result["posts"])
    assert {decision.get("account") for decision in by_url["/analysis/doc/revenue-reviews"]} == {1, 2}
    assert all("account" not in decision for decision in by_url["/analysis/one/revenue-reviews"])


def test_the_statement_window_of_a_package_row_shows_and_reviews_that_account(tmp_path, monkeypatch):
    """A package row of one account is named `<job>#account_<n>`: its window fetches the statement's own job, shows
    account n, and its review buttons name the job and the account."""
    two = _two_accounts()
    result = run_dashboard(DRAWN + _serve(doc=two) + """
openStatementModal('doc#account_2'); await settle();
console.log(JSON.stringify({urls: REQUESTS.map((request) => request.url),
  subtitle: els.statementModalSubtitle.textContent, buttons: buttonsIn(els.statementModalTransactions.innerHTML),
  json: els.modalJsonDownload.href}));
""")
    assert "/analysis/doc" in result["urls"] and not any("#" in url for url in result["urls"])
    assert result["subtitle"].startswith("Account 2 of 2 - ")
    assert result["buttons"] and {(b["data-revenue-review-job"], b["data-revenue-review-account"])
                                  for b in result["buttons"]} == {("doc", "2")}
    assert result["json"] == "/download/doc/json"


def test_the_selection_is_what_is_ticked_on_screen():
    """A tick whose row leaves the screen (another filter) is dropped with it: the bar never acts on a deposit the
    analyst cannot see, and never shows with no box ticked."""
    result = run_dashboard(DRAWN + _serve(a=_pending(1)) + """
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
boxesIn(els.transactionTable.innerHTML).forEach(tick);
const ticked = {selected: bulkSelection.size, hidden: els.bulkReviewBar.hidden};
transactionFilter = 'non_revenue'; renderMainTransactions();
const filtered = {selected: bulkSelection.size, hidden: els.bulkReviewBar.hidden,
                  boxes: boxesIn(els.transactionTable.innerHTML).length};
transactionFilter = 'all'; renderMainTransactions();
console.log(JSON.stringify({ticked, filtered, back: boxesIn(els.transactionTable.innerHTML)}));
""")
    assert result["ticked"] == {"selected": 2, "hidden": False}
    assert result["filtered"] == {"selected": 0, "hidden": True, "boxes": 0}
    assert len(result["back"]) == 2 and not any(box["checked"] for box in result["back"])


def test_another_analysis_starts_with_no_ticks_even_where_it_shows_the_same_deposit(tmp_path, monkeypatch):
    first = _package({"a": _pending(1), "b": _pending(2)}, tmp_path, monkeypatch)
    second = _package({"a": _pending(1), "c": _pending(3)}, tmp_path, monkeypatch)
    result = run_dashboard(DRAWN + f"""
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(first)});
tick(boxesIn(els.transactionTable.innerHTML).find((box) => box["data-bulk-job"] === "a"));
const before = bulkSelection.size;
currentJobIds = ['a', 'c']; renderPackageAnalysis({json.dumps(second)});
console.log(JSON.stringify({{before, after: bulkSelection.size, hidden: els.bulkReviewBar.hidden,
  checked: boxesIn(els.transactionTable.innerHTML).filter((box) => box.checked).length}}));
""")
    assert result == {"before": 1, "after": 0, "hidden": True, "checked": 0}


def test_a_refused_statement_keeps_its_ticks_the_saved_one_is_redrawn_and_the_notifications_open(
        tmp_path, monkeypatch):
    before = {"a": _pending(1), "b": _pending(2)}
    after = {"a": _decided(before["a"], [("transaction:2", "confirm", None)]), "b": before["b"]}
    package_before = _package(before, tmp_path, monkeypatch)
    package_after = _package(after, tmp_path, monkeypatch)
    responses = {"/analysis/a/revenue-reviews": {"json": {"analysis": after["a"], "applied": 1}},
                 "/analysis/b/revenue-reviews": {"status": 400, "json": {"error": "fabricated refusal"}},
                 "/package_analysis": {"json": package_after}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
els.notificationsPopover.hidden = true;
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package_before)});
const boxes = boxesIn(els.transactionTable.innerHTML);
tick(boxes.find((box) => box["data-bulk-job"] === "a" && box["data-bulk-location"] === "transaction:2"));
tick(boxes.find((box) => box["data-bulk-job"] === "b" && box["data-bulk-location"] === "transaction:2"));
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({{said, selected: [...bulkSelection], hidden: els.bulkReviewBar.hidden,
  opened: !els.notificationsPopover.hidden, boxes: boxesIn(els.transactionTable.innerHTML)}}));
""")
    assert ["1 deposit confirmed as revenue", "green"] in result["said"]
    assert ["Not saved for February 2031: fabricated refusal", "red"] in result["said"]
    assert result["opened"] is True and result["hidden"] is False
    assert result["selected"] == [json.dumps(["b", None, "transaction:2"], separators=(",", ":"))]
    ticked = {(box["data-bulk-job"], box["data-bulk-location"]) for box in result["boxes"] if box["checked"]}
    assert ticked == {("b", "transaction:2")}
    assert ("a", "transaction:2") not in {(box["data-bulk-job"], box["data-bulk-location"]) for box in result["boxes"]}


def test_saved_decisions_whose_page_cannot_refresh_are_unticked_and_said_to_be_saved(tmp_path, monkeypatch):
    before = {"a": _pending(1), "b": _pending(2)}
    package_before = _package(before, tmp_path, monkeypatch)
    after_a = _decided(before["a"], [("transaction:2", "confirm", None)])
    responses = {"/analysis/a/revenue-reviews": {"json": {"analysis": after_a, "applied": 1}},
                 "/package_analysis": {"status": 500, "json": {"error": "fabricated outage"}}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
els.notificationsPopover.hidden = true;
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package_before)});
tick(boxesIn(els.transactionTable.innerHTML).find((box) => box["data-bulk-job"] === "a"));
renderMainTransactions({{keepLimit: true}});  // the page as the analyst sees it: the box drawn ticked
const drawn = boxesIn(els.transactionTable.innerHTML).filter((box) => box.checked).length;
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({{said, drawn, selected: bulkSelection.size, hidden: els.bulkReviewBar.hidden,
  opened: !els.notificationsPopover.hidden,
  checked: boxesIn(els.transactionTable.innerHTML).filter((box) => box.checked).length}}));
""")
    # Saved: nothing stays ticked, although the page could not be drawn from the saved package.
    assert result["drawn"] == 1
    assert result["selected"] == 0 and result["hidden"] is True and result["checked"] == 0
    assert ["1 deposit confirmed as revenue", "green"] in result["said"]
    red = [message for message, tone in result["said"] if tone == "red"]
    assert len(red) == 1 and red[0].startswith("Saved, but the page could not be refreshed (500)")
    assert result["opened"] is True


def test_a_batch_and_a_row_button_never_run_at_once():
    result = run_dashboard(DRAWN + _serve(a=_pending(1)) + """
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
const attrs = buttonsIn(els.transactionTable.innerHTML)[0];
const button = fakeElement("row"); Object.assign(button.attributes, attrs);
bulkBusy = true;
await submitRevenueReview(button);
bulkBusy = false;
tick(boxesIn(els.transactionTable.innerHTML)[0]);
rowReviewsInFlight = 1; syncBulkReview();
await submitBulkReview("confirm");
console.log(JSON.stringify({posts: posts(), selected: bulkSelection.size}));
""")
    assert result == {"posts": [], "selected": 1}


def test_each_box_names_its_deposit_and_an_error_page_reads_as_a_status():
    responses = {"/analysis/a/revenue-reviews": {"status": 502, "text": "<html>fabricated gateway</html>"}}
    result = run_dashboard(DRAWN + _serve(a=_pending(1)) + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
const labels = boxesIn(els.transactionTable.innerHTML).map((box) => box["aria-label"]);
tick(boxesIn(els.transactionTable.innerHTML)[0]);
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({{labels, said: said.filter(([, tone]) => tone === "red")}}));
""")
    labels = result["labels"]
    assert len(labels) == 2 and len(set(labels)) == 2
    assert all(label.startswith("Select the deposit of $") and "DEPOSIT FABRICATED" in label for label in labels)
    assert result["said"] == [["Not saved: Revenue review failed (502)", "red"]]


def _many(count, month=3):
    """A fabricated statement of `count` deposits awaiting review, five a day: more than one page of rows."""
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report
    rows = [(1 + index // 5, f"DEPOSIT FABRICATED NUMBER {index + 1}", 100.0) for index in range(count)]
    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows, month))


# Rows past the first page: what Show more drew, ticked, and the first page's locations.
BEYOND = r"""
const firstPage = new Set(boxesIn(els.transactionTable.innerHTML).map((box) => box["data-bulk-job"] + box["data-bulk-location"]));
transactionLimit = 300; renderMainTransactions({keepLimit: true});
const beyond = boxesIn(els.transactionTable.innerHTML)
  .filter((box) => !firstPage.has(box["data-bulk-job"] + box["data-bulk-location"]));
const ticked = (html, box) => (boxesIn(html).find((b) => b["data-bulk-job"] === box["data-bulk-job"]
  && b["data-bulk-location"] === box["data-bulk-location"]) || {}).checked;
"""


def test_a_row_review_keeps_the_ticks_beyond_the_first_page():
    before = _many(110)
    after = _decided(before, [("transaction:1", "confirm", None)])
    responses = {"/analysis/many/revenue-review": {"json": {"analysis": after}}}
    result = run_dashboard(DRAWN + _serve(many=before) + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobId = 'many'; currentJobIds = ['many']; loadResults('many'); await settle();
""" + BEYOND + """
const far = beyond[beyond.length - 1];
tick(far);
const attrs = buttonsIn(els.transactionTable.innerHTML)
  .find((b) => b["data-revenue-review-location"] === "transaction:1" && b["data-revenue-review-action"] === "confirm");
const button = fakeElement("row"); Object.assign(button.attributes, attrs);
await submitRevenueReview(button); await settle();
console.log(JSON.stringify({beyond: beyond.length, selected: bulkSelection.size, hidden: els.bulkReviewBar.hidden,
  farTicked: ticked(els.transactionTable.innerHTML, far), posts: posts().length}));
""")
    assert result["beyond"] == 10 and result["posts"] == 1
    assert result == {**result, "selected": 1, "hidden": False, "farTicked": True}


def test_a_refused_statement_keeps_its_ticks_beyond_the_first_page(tmp_path, monkeypatch):
    before = {"a": _many(60, 1), "b": _many(60, 2)}
    after_a = _decided(before["a"], [("transaction:1", "confirm", None)])
    package_before = _package(before, tmp_path, monkeypatch)
    package_after = _package({"a": after_a, "b": before["b"]}, tmp_path, monkeypatch)
    responses = {"/analysis/a/revenue-reviews": {"json": {"analysis": after_a, "applied": 1}},
                 "/analysis/b/revenue-reviews": {"status": 400, "json": {"error": "fabricated refusal"}},
                 "/package_analysis": {"json": package_after}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package_before)});
""" + BEYOND + """
tick(boxesIn(els.transactionTable.innerHTML).find((box) => box["data-bulk-job"] === "a"
  && box["data-bulk-location"] === "transaction:1"));
const far = beyond.filter((box) => box["data-bulk-job"] === "b").pop();
tick(far);
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({selected: [...bulkSelection], farKey: JSON.stringify(["b", null, far["data-bulk-location"]]),
  farTicked: ticked(els.transactionTable.innerHTML, far), hidden: els.bulkReviewBar.hidden}));
""")
    assert result["selected"] == [result["farKey"]]
    assert result["farTicked"] is True and result["hidden"] is False


def test_row_buttons_drawn_during_a_batch_are_held():
    """A sort or the statement window can draw rows while a batch is being saved: their buttons are drawn held, like
    the ones already on screen, not live-looking buttons whose click does nothing."""
    result = run_dashboard(DRAWN + _serve(a=_pending(1)) + """
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
const held = (html) => [...html.matchAll(/<button class="table-action[^"]*" type="button"([^>]*)>/g)]
  .filter((m) => m[1].includes("data-revenue-review-action")).map((m) => /\\sdisabled\\b/.test(m[1]));
bulkBusy = true; renderMainTransactions();
const during = held(els.transactionTable.innerHTML);
bulkBusy = false; renderMainTransactions();
console.log(JSON.stringify({during, after: held(els.transactionTable.innerHTML)}));
""")
    assert result["during"] and all(result["during"])
    assert result["after"] and not any(result["after"])


def test_a_saved_decision_whose_page_cannot_refresh_keeps_its_button_held(tmp_path, monkeypatch):
    """Pressed again, the button of a decision already saved would record the decision twice."""
    before = {"a": _pending(1), "b": _pending(2)}
    package = _package(before, tmp_path, monkeypatch)
    after_a = _decided(before["a"], [("transaction:2", "confirm", None)])
    responses = {"/analysis/a/revenue-review": {"json": {"analysis": after_a}},
                 "/package_analysis": {"status": 500, "json": {"error": "fabricated outage"}}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
const alerts = []; window.alert = (message) => alerts.push(message);
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
const attrs = buttonsIn(els.transactionTable.innerHTML).find((b) => b["data-revenue-review-job"] === "a"
  && b["data-revenue-review-location"] === "transaction:2" && b["data-revenue-review-action"] === "confirm");
const button = fakeElement("row"); Object.assign(button.attributes, attrs);
await submitRevenueReview(button); await settle();
console.log(JSON.stringify({{alerts, disabled: button.disabled}}));
""")
    assert result["disabled"] is True
    assert len(result["alerts"]) == 1 and result["alerts"][0].startswith("Saved, but the page could not be refreshed")


def test_a_refusal_names_the_file_when_two_statements_share_a_month(tmp_path, monkeypatch):
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import PENDING_ROWS, _report

    # Audit B11 (I06): two statements of one month are two accounts' (the same statement twice is one, left out).
    before = {"a": _pending(3), "b": document_report_to_dict(
        _report("FABRICATED BUSINESS SAVINGS", "000000002020", 1500.0, PENDING_ROWS, 3))}
    package = _package(before, tmp_path, monkeypatch)
    responses = {"/analysis/b/revenue-reviews": {"status": 400, "json": {"error": "fabricated refusal"}}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
tick(boxesIn(els.transactionTable.innerHTML).find((box) => box["data-bulk-job"] === "b"));
press("confirm"); await settle(); await settle();
console.log(JSON.stringify({{red: said.filter(([, tone]) => tone === "red").map(([message]) => message)}}));
""")
    assert result["red"] == ["Not saved for March 2031 (fabricated-b.pdf): fabricated refusal"]


def test_an_analysis_opened_while_the_page_refreshes_is_left_as_it_is(tmp_path, monkeypatch):
    """The package is fetched again after a batch; opening another analysis meanwhile must not have the old package
    drawn over it, nor the old analysis's ticks (here a refused one) carried into it."""
    first = {"a": _pending(1), "b": _pending(2)}
    after_a = _decided(first["a"], [("transaction:2", "confirm", None)])
    package_first = _package(first, tmp_path, monkeypatch)
    package_after = _package({"a": after_a, "b": first["b"]}, tmp_path, monkeypatch)
    package_second = _package({"b": first["b"], "c": _pending(3)}, tmp_path, monkeypatch)
    responses = {"/analysis/a/revenue-reviews": {"json": {"analysis": after_a, "applied": 1}},
                 "/analysis/b/revenue-reviews": {"status": 400, "json": {"error": "fabricated refusal"}},
                 "/package_analysis": {"json": package_after}}
    result = run_dashboard(DRAWN + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
const realFetch = fetch;
fetch = (url, options) => String(url).startsWith("/package_analysis")
  ? new Promise((resolve) => setTimeout(() => resolve(realFetch(url, options)), 80)) : realFetch(url, options);
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package_first)});
const boxes = boxesIn(els.transactionTable.innerHTML);
tick(boxes.find((box) => box["data-bulk-job"] === "a" && box["data-bulk-location"] === "transaction:2"));
tick(boxes.find((box) => box["data-bulk-job"] === "b" && box["data-bulk-location"] === "transaction:2"));
press("confirm"); await settle();
currentJobIds = ['b', 'c']; renderPackageAnalysis({json.dumps(package_second)});
await new Promise((resolve) => setTimeout(resolve, 150));
console.log(JSON.stringify({{shown: currentAnalysis.package.documents.map((doc) => doc.id), selected: bulkSelection.size,
  hidden: els.bulkReviewBar.hidden, checked: boxesIn(els.transactionTable.innerHTML).filter((box) => box.checked).length}}));
""")
    assert result == {"shown": ["b", "c"], "selected": 0, "hidden": True, "checked": 0}


def test_a_review_keeps_the_rows_opened_with_show_more():
    before = _pending(1)
    after = _decided(before, [("transaction:2", "confirm", None)])
    responses = {"/analysis/a/revenue-review": {"json": {"analysis": after}}}
    result = run_dashboard(DRAWN + _serve(a=before) + f"""
Object.assign(FAKE_RESPONSES, {json.dumps(responses)});
currentJobId = 'a'; currentJobIds = ['a']; loadResults('a'); await settle();
transactionLimit = 300;
const attrs = buttonsIn(els.transactionTable.innerHTML)[0];
const button = fakeElement("row"); Object.assign(button.attributes, attrs);
await submitRevenueReview(button); await settle();
console.log(JSON.stringify({{limit: transactionLimit, posts: posts().length}}));
""")
    assert result == {"limit": 300, "posts": 1}
