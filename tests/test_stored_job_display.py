"""A job stored before the visual readers were retired still displays: its held read keeps its source actions, its
sub-page progress labels still read, and a statement contradiction it was refused with is still shown as the
statement's failure (owner ruling, 2026-09-23). The dashboard code these pin (`setActions`, `loadResults`,
`processingStageLabel`'s visual_pair_* stages, `sourceContradiction`) stays for those stored jobs.

Moved here from tests/test_visual_pair_ui.py and tests/test_source_contradiction.py when the visual pair left the
webapp (model-code removal, slice S1); the messages are fabricated literals of the stored shapes, and nothing here
imports a model module. Driven through node."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


NODE = shutil.which("node")
APP_JS = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

#: The analysis error a held visual-pair read was stored with, and a verified source contradiction's message: both
#: shapes of `analysis_error` that only stored jobs carry now.
HELD_READ = "visual pair requires human review"
CONTRADICTION = "Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction"


def _function(name):
    return APP_JS[APP_JS.index(f"function {name}("):].split("\nfunction ")[0]


def _run(source):
    result = subprocess.run([NODE, "-e", source], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


_ELEMENTS = """
function element() {
  return {href: '#', disabled: true, textContent: '', className: '', attributes: {},
          classList: {add() {}, remove() {}, toggle() {}},
          setAttribute(key, value) { this.attributes[key] = value; }};
}
const els = Object.fromEntries(['downloadJson', 'downloadCsv', 'downloadExcel',
  'exportText', 'openTextBtn', 'copyDataBtn', 'summaryBtn', 'copyTextBtn',
  'statusHeading', 'decisionPill', 'summaryBox'].map(key => [key, element()]));
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_held_read_enables_source_actions_but_keeps_metric_exports_disabled():
    result = _run(_ELEMENTS + _function("setActions") + """
setActions('synthetic-job', false, true);
console.log(JSON.stringify(els));
""")
    assert result["openTextBtn"]["href"] == "/result/synthetic-job"
    assert result["exportText"]["href"] == "/download/synthetic-job/md"
    assert result["copyTextBtn"]["disabled"] is False
    for key in ("downloadJson", "downloadCsv", "downloadExcel"):
        assert result[key]["href"] == "#"
        assert result[key]["attributes"]["aria-disabled"] == "true"
    for key in ("copyDataBtn", "summaryBtn"):
        assert result[key]["disabled"] is True


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_completed_held_load_preserves_reading_and_clears_previous_metrics():
    source = _ELEMENTS + """
let currentJobId = 'synthetic-job';
let currentAnalysis = {metrics: {stale: true}};
let currentMarkdown = 'previous reading';
let cleared = false;
let renderedAnalysis = false;
function setInitialState() { cleared = true; }
function setProgress() {}
function setBanner() {}
function setStatusRows() {}
function renderAnalysis() { renderedAnalysis = true; }
function renderError(message) { throw new Error(message); }
// The sidebar's Recent list and page navigation (tests/test_webapp_studio_views.py drives them end to end).
let openAnalysisKey = null, remembered = null, navigatedTo = null;
function rememberHeldStatement(jobId, message) { remembered = [jobId, message]; }
function navigate(target) { navigatedTo = target; }
function fetch(url) {
  return Promise.resolve({ok: true,
    json: () => Promise.resolve({analysis: null, analysis_error: %s}),
    text: () => Promise.resolve('fabricated extraction')});
}
// The status card's message line, where a result that never reaches the results page is explained.
els.statusMessage = {textContent: '', hidden: true, links: '',
                     insertAdjacentHTML(where, html) { this.links += html; }};
""" % json.dumps(HELD_READ) + "\n".join(_function(name) for name in (
        "escapeHtml", "sentenceCase", "setStatusMessage", "appendStatusLink", "noUsableText",
        "friendlyAnalysisError", "sourceContradiction", "setActions", "renderExtractionReview",
        "loadResults")) + """
loadResults('synthetic-job');
setImmediate(() => console.log(JSON.stringify({currentAnalysis, currentMarkdown,
  cleared, renderedAnalysis, heading: els.statusHeading.textContent,
  summary: els.summaryBox.textContent, reviewHref: els.openTextBtn.href,
  jsonHref: els.downloadJson.href, message: els.statusMessage.textContent,
  messageHidden: els.statusMessage.hidden, messageLinks: els.statusMessage.links})));
"""
    result = _run(source)
    assert result["currentAnalysis"] is None
    assert result["currentMarkdown"] == "fabricated extraction"
    assert result["cleared"] is True
    assert result["renderedAnalysis"] is False
    assert result["heading"] == "Extraction needs review"
    assert "No metrics have been published" in result["summary"]
    assert result["reviewHref"] == "/result/synthetic-job"
    assert result["jsonHref"] == "#"
    # The New analysis page explains the hold and links to the review, since no results page opens.
    assert "No metrics have been published" in result["message"] and result["messageHidden"] is False
    assert 'href="/result/synthetic-job"' in result["messageLinks"] and "Review extraction" in result["messageLinks"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_subpage_progress_is_readable():
    source = _function("labelize") + _function("processingStageLabel") + """
console.log(JSON.stringify([
  'visual_pair_reviewing:2/8:batch:3/4',
  'visual_pair_reviewing:2/8:discovery',
  'visual_pair_proposing:1/8:crop:2/2'
].map(processingStageLabel)));
"""
    assert _run(source) == ["Checking page 2 of 8, part 3 of 4",
                            "Checking page 2 of 8 for missing rows",
                            "Reading page 1 of 8 again, region 2 of 2"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_dashboard_shows_the_contradiction_as_the_statements_failure():
    def function(name):
        return APP_JS[APP_JS.index(f"function {name}("):].split("\n}\n")[0] + "\n}\n"

    harness = """
let currentAnalysis = null;
const els = {};
for (const key of ["statusBanner", "statusMark", "statusCopy", "validationValue", "statusHeading", "summaryBox",
                   "decisionPill", "statusList"]) els[key] = {textContent: "", className: "", innerHTML: ""};
// The New analysis page's status card line, where a result that opens no results page is explained.
const toned = new Set();
els.statusMessage = {textContent: "", hidden: true,
                     classList: {toggle(name, on) { if (on) toned.add(name); else toned.delete(name); }}};
function setInitialState() {}
function setProgress() {}
function escapeHtml(value) { return String(value); }
""" + "".join(function(name) for name in ("setBanner", "setStatusMessage", "kvRowsHtml", "statusRowHtml",
                                          "setStatusRows", "sentenceCase", "noUsableText",
                                          "friendlyAnalysisError", "sourceContradiction",
                                          "renderExtractionReview"))
    results = []
    for message in (CONTRADICTION, "visual pair gate refused the document"):
        script = harness + f"""
renderExtractionReview({json.dumps(message)});
console.log(JSON.stringify({{heading: els.statusHeading.textContent, banner: els.statusCopy.textContent,
                            pill: els.decisionPill.textContent, state: els.statusBanner.className,
                            message: els.statusMessage.textContent, shown: !els.statusMessage.hidden,
                            review: toned.has("review")}}));
"""
        run = subprocess.run([NODE, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert run.returncode == 0, run.stderr
        results.append(json.loads(run.stdout))
    failed, held = results
    assert failed["heading"] == CONTRADICTION
    assert failed["pill"] == "Fail" and "error" in failed["state"] and "does not add up" in failed["banner"]
    # A failure of the statement is explained where the page shows it, in the failure's tone (not "review").
    assert failed["shown"] and "failure of the statement, not of the reading" in failed["message"]
    assert failed["review"] is False
    assert held["heading"] == "Extraction needs review" and held["pill"] == "Review required"
    # A held read needs review: its reason reads as a sentence of its own, in the review tone.
    assert held["shown"] and held["review"] is True
    assert held["message"].startswith("Visual pair gate refused the document. Open Review extraction")


def test_this_module_imports_no_model_module():
    """The display of a stored job needs no model code: this file names none in an import."""
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not {name for name in imported if name.split(".")[0] in {"vlm", "openai", "google"}}
