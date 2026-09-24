"""Held visual reads remain reviewable without enabling metric publication."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


NODE = shutil.which("node")
APP_JS = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")


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
function fetch(url) {
  return Promise.resolve({ok: true,
    json: () => Promise.resolve({analysis: null, analysis_error: 'visual pair requires human review'}),
    text: () => Promise.resolve('fabricated extraction')});
}
""" + "\n".join(_function(name) for name in (
        "friendlyAnalysisError", "sourceContradiction", "setActions", "renderExtractionReview", "loadResults")) + """
loadResults('synthetic-job');
setImmediate(() => console.log(JSON.stringify({currentAnalysis, currentMarkdown,
  cleared, renderedAnalysis, heading: els.statusHeading.textContent,
  summary: els.summaryBox.textContent, reviewHref: els.openTextBtn.href,
  jsonHref: els.downloadJson.href})));
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
