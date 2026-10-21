"""P23-EGATE item 3: the extraction-quality metrics are ADMITTED AS NOTHING.

Ruling B's discipline is labelled evidence FIRST, review SECOND, admission
THIRD. Phase 2.3 measures; it admits nothing. That claim is worth exactly as
much as its enforcement, so it is enforced three ways:

* **by implementation pin** — every top-level class and function of
  `ocr/escalation.py`, dumped as a syntax tree, hashes to one pinned digest.
  Not "`ADMITTED_TRIGGERS` is unchanged" (a set can be rebuilt from the same
  names while the router around it moves), but every name, string, operator
  and statement of the router's implementation. Comments, blank lines and
  line endings are outside the pin; so is the interpreter (the dump is made
  the same on Python 3.12 and 3.14) and the locale (the source is read as
  UTF-8);
* **by vocabulary** — the admitted trigger set, the extractor order and the
  router's field set restated here independently of that module's own tests,
  so a change has to defeat two files;
* **by AST** — no module of the router, the analysis layer or the webapp
  imports `ocr.extraction_quality`, names an `eq_*` column, or reads one off
  anything. The guard is a pure function over source text, so M6 (an `eq_*`
  value read inside the router) is planted in a SCRATCH COPY and killed
  without the working tree ever being touched.

The fourth way is structural and lives elsewhere: `RouterInputs` has six
fields and none of them can hold a metric, `ocr/extraction_quality.py`
imports nothing but the standard library, `evidence` and `layout.signals`,
and `discovery/runner.py` writes the columns to the ROW at the row's single
exit, after the analysis has already finished.
"""
from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from ocr.escalation import (
    ADMITTED_TRIGGERS,
    ALL_TRIGGERS,
    EXTRACTOR_ORDER,
    TRUNCATION_FLAGGED,
    RouterInputs,
)
from ocr.extraction_quality import EQ_ROW_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
ESCALATION = ROOT / "ocr" / "escalation.py"

#: The SHA-256 of the router's implementation, as `router_implementation_digest`
#: reads it: code only, so a docstring or comment edit leaves it. It reads the
#: same on every checkout this repository runs: CRLF on Windows and LF on the
#: Linux runner, Python 3.12 on CI and the hosting image and 3.14 on the
#: development host, the file read as UTF-8. Measured identical on 3.12.13 and
#: 3.14.8, with LF and CRLF line endings.
ROUTER_IMPLEMENTATION_SHA256 = "02f34c856c207d2a07d7b8ee8fe1e5928819dedefae489ada79a2834735940d9"

#: Where an extraction-quality figure must never appear. `ocr/escalation.py`
#: is the router itself; `analysis/` is the layer that produces a financial
#: verdict; `webapp/` is the one that serves it.
GUARDED = ("ocr/escalation.py", "analysis", "webapp")

EQ_COLUMNS = tuple(column for column, _, _ in EQ_ROW_COLUMNS)


def _without_docstrings(node: ast.AST) -> ast.AST:
    for child in ast.walk(node):
        if (isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and child.body
                and isinstance(child.body[0], ast.Expr) and isinstance(child.body[0].value, ast.Constant)
                and isinstance(child.body[0].value.value, str)):
            child.body = child.body[1:] or [ast.Pass()]
    return node


def router_implementation_digest(source: str) -> str:
    """The router's implementation, hashed: every top-level class and function
    of the module, without its docstrings, dumped without positions, in source
    order.

    `ast.dump` stopped printing empty fields (an empty `decorator_list`, a
    `None` return annotation) in Python 3.13; `show_empty=True` prints them
    again there, so 3.12 and 3.14 dump the same text. The digest is a pure
    function of the SOURCE TEXT, so a mutant can be planted in a copy held in
    this process rather than in the tree."""
    nodes = (node for node in ast.parse(source).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)))
    same_on_every_version = {"show_empty": True} if sys.version_info >= (3, 13) else {}
    implementation = "\n".join(
        ast.dump(_without_docstrings(node), include_attributes=False, **same_on_every_version) for node in nodes
    )
    return hashlib.sha256(implementation.encode("utf-8")).hexdigest()


def offences(source: str, label: str) -> list[str]:
    """Every way a module could read this cell's work, found by AST.

    A pure function of the TEXT so a mutant can be planted in a scratch copy
    (M6) rather than in the tree: a harness that edits the working tree to
    prove a static rule cannot tell its own mutant from a real edit."""
    found: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "extraction_quality" in alias.name:
                    found.append(f"{label}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "extraction_quality" in module:
                found.append(f"{label}: imports from {module}")
            for alias in node.names:
                if alias.name in EQ_COLUMNS or "extraction_quality" in alias.name:
                    found.append(f"{label}: imports the name {alias.name}")
        elif isinstance(node, ast.Attribute) and node.attr in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: reads .{node.attr}")
        elif isinstance(node, ast.Name) and node.id in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: names {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: spells {node.value!r}")
    return found


def guarded_modules() -> list[Path]:
    modules: list[Path] = []
    for entry in GUARDED:
        path = ROOT / entry
        modules.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return modules


# ---------------------------------------------------------------------------
# by implementation pin
# ---------------------------------------------------------------------------

def test_router_implementation_preserves_phase2_extraction_quality_exclusion():
    # Phase 3.1 expressly adds two webapp pair triggers and one extractor.
    # Preserve the stronger invariant on every class/function implementation:
    # extraction-quality measurements still cannot silently change admission.
    digest = router_implementation_digest(ESCALATION.read_text(encoding="utf-8"))
    assert digest == ROUTER_IMPLEMENTATION_SHA256, (
        f"ocr/escalation.py's implementation moved (Python "
        f"{'.'.join(map(str, sys.version_info[:3]))}): {digest}"
    )


def test_the_router_pin_reads_the_same_on_every_checkout():
    """CRLF (a Windows checkout) and LF (the Linux runner) are one router."""
    raw = ESCALATION.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    assert router_implementation_digest(lf.decode("utf-8")) == ROUTER_IMPLEMENTATION_SHA256
    assert router_implementation_digest(crlf.decode("utf-8")) == ROUTER_IMPLEMENTATION_SHA256


@pytest.mark.parametrize("before, after, note", [
    ('refused=("no_admitted_trigger",)', 'refused=("no_admitted_triggers",)', "a refusal literal"),
    ("e not in inputs.attempted", "e in inputs.attempted", "a membership test flipped"),
    ("extractor = remaining[0]\n", "extractor = remaining[-1]\n", "the preference order reversed"),
])
def test_a_router_change_planted_in_a_scratch_copy_moves_the_pin(before, after, note):
    """The pin is not vacuous: one changed literal, operator or index in the
    router's decision moves it. Planted in a copy of the source held in this
    process; the tree is never touched."""
    source = ESCALATION.read_text(encoding="utf-8")
    assert source.count(before) == 1, note
    assert router_implementation_digest(source.replace(before, after, 1)) != ROUTER_IMPLEMENTATION_SHA256, note


def test_a_comment_planted_in_a_scratch_copy_leaves_the_pin():
    """And it is a pin on the implementation, not on the text: a comment and a
    blank line change no node."""
    source = ESCALATION.read_text(encoding="utf-8")
    anchor = "        extractor = remaining[0]\n"
    assert source.count(anchor) == 1
    planted = source.replace(anchor, anchor + "\n        # a reviewer's note, not code\n", 1)
    assert planted != source
    assert router_implementation_digest(planted) == ROUTER_IMPLEMENTATION_SHA256


def test_a_docstring_edit_planted_in_a_scratch_copy_leaves_the_pin():
    source = ESCALATION.read_text(encoding="utf-8")
    decide = next(node for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.FunctionDef) and node.name == "decide")
    first = decide.body[0]
    planted_docstring = " " * first.col_offset + '"""A planted docstring, not code."""\n'
    lines = source.splitlines(keepends=True)
    if ast.get_docstring(decide) is None:
        lines.insert(first.lineno - 1, planted_docstring)
    else:
        lines[first.lineno - 1:first.end_lineno] = [planted_docstring]
    planted = "".join(lines)
    assert planted != source
    assert router_implementation_digest(planted) == ROUTER_IMPLEMENTATION_SHA256


# ---------------------------------------------------------------------------
# by vocabulary
# ---------------------------------------------------------------------------

def test_the_admitted_trigger_set_is_unchanged():
    assert ADMITTED_TRIGGERS == frozenset(ALL_TRIGGERS) - {TRUNCATION_FLAGGED}
    assert sorted(ADMITTED_TRIGGERS) == [
        "deterministic_parse_unvalidated",
        "extractor_failed",
        "extractor_output_unusable",
        "image_only_document",
        "mixed_document_pages_without_native_text",
        "offline_rungs_produced_no_text",
        "operator_forced_paddle",
        "operator_forced_visual",
        "operator_forced_visual_pair",
    ]
    assert TRUNCATION_FLAGGED not in ADMITTED_TRIGGERS
    # no E-class, no metric name, nothing this cell produced is a trigger
    assert not [name for name in ALL_TRIGGERS if name.startswith("eq_") or name in EQ_COLUMNS]


def test_the_extractor_order_and_the_router_field_set_are_unchanged():
    assert EXTRACTOR_ORDER == ("local_tesseract", "paddle", "visual", "visual_pair")
    assert tuple(RouterInputs.__dataclass_fields__) == (
        "profile", "evidence", "triggers", "attempted", "stop", "enabled",
    )
    assert RouterInputs.__subclasses__() == []


# ---------------------------------------------------------------------------
# by AST
# ---------------------------------------------------------------------------

def test_no_router_analysis_or_webapp_module_reads_an_extraction_quality_figure():
    modules = guarded_modules()
    assert len(modules) > 50, "the guard scans a package, not a handful of files"
    assert ESCALATION in modules
    found: list[str] = []
    for path in modules:
        found.extend(offences(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT))))
    assert found == [], found


#: Where a planted mutant is inserted: inside the router's one decision, and
#: at the module's import block.
_DECIDE = "    def decide(inputs: RouterInputs) -> Escalation:\n"
_IMPORTS = "from dataclasses import dataclass\n"


@pytest.mark.parametrize("anchor, mutant, note", [
    (_DECIDE, "        quality = inputs.evidence.eq_class\n", "an eq_ value read off the router's inputs"),
    (_IMPORTS, "from ocr.extraction_quality import e_class\n", "the module imported by the router"),
    (_IMPORTS, "import ocr.extraction_quality\n", "the module imported by name"),
    (_DECIDE, '        name = "eq_money_rate"\n', "a column named as a string"),
])
def test_m6_an_extraction_quality_read_planted_in_a_scratch_router_is_caught(anchor, mutant, note):
    """M6's killer. The mutant is inserted into a COPY of the router's source
    held in this process; the tree is never touched, and the guard that would
    catch it in the repository is the same function that catches it here."""
    source = ESCALATION.read_text(encoding="utf-8")
    assert source.count(anchor) == 1
    planted = source.replace(anchor, anchor + mutant, 1)
    assert offences(planted, "scratch"), note
    # and the unmutated source is clean, so the test above is not vacuous
    assert offences(source, "scratch") == []


def tracked_python_files() -> list[str]:
    """Every `.py` file GIT knows about, repository-relative and sorted.

    The tree's own answer to "what is in it", so a net built on it cannot
    drift from the repository as the repository grows — and it excludes the
    untracked scratch and worktree directories for free."""
    listing = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return sorted(line.strip() for line in listing.splitlines() if line.strip())


#: The only files outside the tests that may name an `eq_*` column, and why.
#: The first four are the column's own life: the module that computes it, the
#: row that carries it, the CSV that lists it, the census that reads it. The
#: last two are this cell's committed PROOF INSTRUMENTS, which name the
#: columns because naming them is their job — the mutation harness mutates
#: the column list by spelling it, and the fake-partition builder prints a
#: row's columns beside the census's figures. Neither is a reader in the
#: sense that matters: the layers that must never read one
#: (`ocr/escalation.py`, `analysis/`, `webapp/`) are scanned BY AST in
#: `test_no_router_analysis_or_webapp_module_reads_an_extraction_quality_figure`,
#: and this census is the second, coarser net around them.
#:
#: Model-code removal, slice S5: the census and the two proof instruments
#: (`tools/extraction_quality_census.py`, `tools/p23egate_mutation_table.py`,
#: `tools/p23egate_fake_partition.py`) left with the PaddleOCR rung whose
#: research partition they measured, so they left this allowlist too. Narrowing
#: an allowlist is not weakening it, and the rot check at the end of the test
#: below would fail on a named allowance that names nothing.
ALLOWED_NAMERS = {
    "ocr/extraction_quality.py", "discovery/runner.py", "discovery/report.py",
}


def test_the_report_is_the_only_thing_outside_the_module_that_names_the_columns():
    """Nothing reads `eq_*` but the report and this cell's own instruments —
    by MEASUREMENT over the tree, not by assertion. The list is closed here,
    and every guarded layer is separately required to be absent from it."""
    tracked = tracked_python_files()
    # A depth-limited glob is a net with a hole in it: the previous spelling
    # (`*/*.py` and `*/*/*.py`) missed all eleven modules at the repository
    # ROOT — `corpus_gate.py`, `parse.py`, `analyze.py`, `batch.py` and the
    # rest — and any module four directories deep (review MINOR-4). `git
    # ls-files` is the tree's own answer to "what is in it", so the net cannot
    # drift from the repository as it grows.
    assert len(tracked) > 200, "the census scans the tree, not a handful of files"
    assert "corpus_gate.py" in tracked, "the repository root is inside the net"
    readers: set[str] = set()
    for relative in tracked:
        if relative.startswith("tests/") or relative.startswith(".claude/"):
            continue
        text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        if any(column in text for column in EQ_COLUMNS):
            readers.add(relative)
    assert readers <= ALLOWED_NAMERS, sorted(readers - ALLOWED_NAMERS)
    # and the direction that matters, stated as its own claim: not one module
    # of the router's layer, the analysis layer, the webapp, telemetry or the
    # neutral layout package names a column at all.
    guarded = {name for name in readers
               if name.startswith(("analysis/", "webapp/", "telemetry/", "layout/"))
               or (name.startswith("ocr/") and name != "ocr/extraction_quality.py")}
    assert guarded == set(), sorted(guarded)
    # a named allowance that names nothing is an allowlist rotting quietly
    missing = [name for name in ALLOWED_NAMERS if not (ROOT / name).exists()]
    assert missing == [], missing
