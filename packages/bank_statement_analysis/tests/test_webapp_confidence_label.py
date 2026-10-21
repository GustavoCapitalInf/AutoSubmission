"""OQ9: the fabricated "OCR confidence" is gone for good.

`webapp/static/app.js`'s `confidenceFrom` / `packageConfidence` used to return a
hard-coded score from four buckets, re-encoding the validator's own `quality`
verdict under a label that would mislead an operator the day a second
extractor exists (review MAJOR-4). Gustavo ruled: remove the label, do not
replace it with another fabricated score (OQ9). `analysis/pipeline.py`'s `Quality` dataclass and
`webapp/app.py`'s package `totals` are the only sources the replacement,
`validationLabel` / `packageValidationLabel`, may read from.

This module is TWO layers:

* a text/AST guard over every `webapp/static/*.js` and `webapp/templates/*.html`
  file, run unconditionally (no external binary needed) — the mutation table's
  killer for "a renamed function still returns a score" and "the string comes
  back under another name";
* a rendering check that actually EXECUTES `validationLabel` /
  `packageValidationLabel` as shipped, via Node (skipped when Node is not on
  the host — the same `skipif(shutil.which(...) is None)` idiom this suite
  already uses for the live Tesseract tests), proving the results table shows
  WORDS for a validated and a needs-review fixture and never a number.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC_JS_FILES = sorted((ROOT / "webapp/static").glob("*.js"))
TEMPLATE_HTML_FILES = sorted((ROOT / "webapp/templates").glob("*.html"))
APP_JS_PATH = ROOT / "webapp/static/app.js"
APP_JS = APP_JS_PATH.read_text(encoding="utf-8")

assert STATIC_JS_FILES and TEMPLATE_HTML_FILES, "the glob found nothing to guard"

# ---------------------------------------------------------------------------
# the guard: no fabricated confidence survives under any name
# ---------------------------------------------------------------------------

#: A 60-99-shaped literal, in every spelling this guard recognises: the bare
#: two-digit integer every one of `confidenceFrom` / `packageConfidence`'s six
#: branches used (`94`), its float form (`94.0`), and the 0-1 fraction form a
#: percentage is sometimes carried in (`0.94`). MINOR-3 widened this from integers only.
_SCORE_LITERAL = r"(?:6[0-9]|7[0-9]|8[0-9]|9[0-9])(?:\.[0-9]+)?|0\.(?:6[0-9]|7[0-9]|8[0-9]|9[0-9])\b"

#: `return <literal>;`, wherever a function body puts it. Not scoped to a
#: function name: the mutation this must kill is exactly a RENAMED function
#: that still does this.
_BARE_SCORE_RETURN_RE = re.compile(r"return\s+(?:" + _SCORE_LITERAL + r")\s*;")

#: `NAME = <literal>;` anywhere in the file -- catches `const S = 94; return
#: S;` (MINOR-3's named example) without needing to trace which variable a
#: later `return` reads, by treating ASSIGNING a score-shaped literal to
#: anything as suspicious as returning one directly.
_SCORE_LITERAL_ASSIGNED_RE = re.compile(r"[A-Za-z_$][\w$]*\s*=\s*(?:" + _SCORE_LITERAL + r")\s*;")

#: What this STATIC pair does not and cannot kill, honestly: a value computed
#: by ARBITRARY ARITHMETIC (`return 100 - 6;`, `return 47 * 2;`, ...) never
#: appears in the source as a 60-99-shaped literal at all, and defending
#: against every such expression textually is not tractable. The residual
#: catch for that class is DYNAMIC, not static: `test_validation_label_
#: renders_the_verdict_words_and_never_a_number` below executes
#: `validationLabel` via Node against every one of its branches and asserts
#: the OUTPUT contains no digit -- an arithmetic mutant that changed a branch
#: to `return 100 - 6` would return the number `94`, not a word, and that
#: test would fail. That dynamic check is skipped when Node is absent (this
#: host has Node v24; CI does not), which is the one gap this file does not
#: close: a purely static CI run has no defence against a numeric result
#: reached by arithmetic rather than by a literal.

#: Defence in depth beside the blanket ban above: no 60-99 literal sitting
#: within shouting distance of the word "confidence" anywhere in a guarded
#: file, however it got there (a template literal, a status-row label, a CSS
#: comment).
_NUMBER_NEAR_CONFIDENCE_RE = re.compile(
    r"(confidence.{0,160}?\b(?:6[0-9]|7[0-9]|8[0-9]|9[0-9])\b"
    r"|\b(?:6[0-9]|7[0-9]|8[0-9]|9[0-9])\b.{0,160}?confidence)",
    re.IGNORECASE | re.DOTALL,
)


@pytest.mark.parametrize("path", STATIC_JS_FILES + TEMPLATE_HTML_FILES, ids=lambda p: p.name)
def test_no_ocr_confidence_string_survives(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "OCR confidence" not in text, path


@pytest.mark.parametrize("path", STATIC_JS_FILES, ids=lambda p: p.name)
def test_no_confidence_scoring_function_survives_under_its_old_name(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "confidenceFrom" not in text, path
    assert "packageConfidence" not in text, path


@pytest.mark.parametrize("path", STATIC_JS_FILES, ids=lambda p: p.name)
def test_no_bare_60_99_return_literal_anywhere_in_a_static_js_file(path: Path):
    """The numeric-literal guard. Kills `return 94`, `return 94.0` and
    `return 0.94` even under a renamed function -- the mutation table's own
    example -- because it is not scoped to a function name at all: nothing in
    a guarded file may ever `return` a score-shaped literal, named
    `confidenceFrom` or otherwise. MINOR-2:
    parametrized over every file the card's own words promised
    (`webapp/static/*.js`), not just the module-level `app.js` global -- one
    file today, so no behaviour changes, but a second static file would have
    been silently unguarded before this."""
    text = path.read_text(encoding="utf-8")
    match = _BARE_SCORE_RETURN_RE.search(text)
    assert match is None, f"{path}: a score-shaped return survives: {match.group(0)!r}"


@pytest.mark.parametrize("path", STATIC_JS_FILES, ids=lambda p: p.name)
def test_no_score_shaped_literal_assigned_anywhere_in_a_static_js_file(path: Path):
    """MINOR-3's named example, `const S = 94; return S;`: the literal never
    appears after `return` at all, so the return-scoped guard above cannot see
    it. This one is not scoped to `return` either -- assigning a score-shaped
    literal to anything is the suspicious act, wherever it is later read."""
    text = path.read_text(encoding="utf-8")
    match = _SCORE_LITERAL_ASSIGNED_RE.search(text)
    assert match is None, f"{path}: a score-shaped assignment survives: {match.group(0)!r}"


@pytest.mark.parametrize("path", STATIC_JS_FILES + TEMPLATE_HTML_FILES, ids=lambda p: p.name)
def test_no_numeric_literal_60_99_adjacent_to_the_word_confidence(path: Path):
    text = path.read_text(encoding="utf-8")
    match = _NUMBER_NEAR_CONFIDENCE_RE.search(text)
    assert match is None, f"{path}: {match.group(0)!r}" if match else None


def test_the_validation_slot_carries_no_percent_sign_template():
    """A softer but real mutant: a percentage re-introduced under the new
    label (`${validation}%`) without restoring the old name or string at all.
    Every place `validationLabel(` or `packageValidationLabel(` is USED must
    not be immediately wrapped in a template literal ending `%`."""
    for call in ("validationLabel(report)", "packageValidationLabel(pkg)"):
        for match in re.finditer(re.escape(call), APP_JS):
            tail = APP_JS[match.end():match.end() + 80]
            assert "%" not in tail.split(";")[0], (call, tail)


# ---------------------------------------------------------------------------
# the rendering check: the shipped function, executed, on real fixtures
# ---------------------------------------------------------------------------

NODE = shutil.which("node")


def _extract_function(name: str) -> str:
    """The same slice-until-the-next-`function`-keyword idiom
    `tests/test_webapp_security.py::test_upload_failures_surface_the_server_
    message_not_just_a_status_code` already uses to test one function's body
    in isolation, without loading the rest of the DOM-bound module."""
    marker = f"function {name}("
    assert marker in APP_JS, f"{name} is not defined in app.js"
    start = APP_JS.index(marker)
    rest = APP_JS[start:]
    return rest.split("\nfunction ")[0]


def _run_node(js_source: str) -> str:
    result = subprocess.run(
        [NODE, "-e", js_source], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


#: `labelize` is `packageValidationLabel`'s only helper dependency, and it is
#: tiny and stable enough to inline rather than slice out of the file a
#: second time.
_LABELIZE_JS = 'function labelize(value) { return String(value || "N/A").replace(/_/g, " "); }'


@pytest.mark.skipif(NODE is None, reason="node is not installed on this host")
@pytest.mark.parametrize("report,expected", [
    ({"quality": {"corporate_use": "approved", "transaction_detail_reliable": True,
                  "level": "transaction_level"}}, "approved"),
    ({"quality": {"corporate_use": "review", "level": "needs_review"}}, "review"),
    ({"quality": {"corporate_use": "manual_review_required", "level": "needs_review"}},
     "manual review required"),
    ({"quality": {"corporate_use": "summary_only", "level": "summary_aggregate"}},
     "summary only"),
], ids=["approved", "review", "manual-review", "summary-only"])
def test_validation_label_renders_the_verdict_words_and_never_a_number(report, expected):
    """MINOR-4: the word rendered is the
    PAYLOAD's own `quality.corporate_use` token, `labelize`d exactly like
    every other status label in this file (`decisionPill`,
    `packageValidationLabel`) -- never promoted to a stronger invented word
    ("Validated" for "approved")."""
    source = _LABELIZE_JS + "\n" + _extract_function("validationLabel") + (
        f"\nconsole.log(JSON.stringify(validationLabel({json.dumps(report)})));\n"
    )
    output = json.loads(_run_node(source))
    assert output == expected
    assert not re.search(r"\d", output)


@pytest.mark.skipif(NODE is None, reason="node is not installed on this host")
@pytest.mark.parametrize("pkg,expected_words", [
    ({"totals": {"decision": "approved"}}, ["approved"]),
    ({"totals": {"decision": "review_required", "completeness": "partial"}},
     ["review required", "completeness: partial"]),
    ({"totals": {"decision": "approved", "cross_account_averages_refused": True}},
     ["approved", "cross-account averages refused"]),
], ids=["approved", "partial-completeness", "cross-account-refused"])
def test_package_validation_label_renders_completeness_words_and_never_a_number(pkg, expected_words):
    source = _LABELIZE_JS + "\n" + _extract_function("packageValidationLabel") + (
        f"\nconsole.log(JSON.stringify(packageValidationLabel({json.dumps(pkg)})));\n"
    )
    output = json.loads(_run_node(source))
    for word in expected_words:
        assert word in output
    assert not re.search(r"\d", output)


@pytest.mark.skipif(NODE is None, reason="node is not installed on this host")
def test_the_results_table_row_pairs_use_the_same_rendered_label():
    """The status-row entry (`["Validation", validation]`) and the banner meta
    (`setBanner(..., validation)`) both read the SAME variable in
    `renderAccount` (the one-account renderer `renderAnalysis` hands each
    shown account to) -- so proving the function's output is enough to prove
    both surfaces agree; this pins that they are still the same variable
    rather than two independently-drifting copies."""
    body = _extract_function("renderAccount")
    assert body.count("validationLabel(report)") == 1
    assert '["Validation", validation]' in body
    assert "setBanner(\"done\", \"Extraction completed\", validation)" in body
