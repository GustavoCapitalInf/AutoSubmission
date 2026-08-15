"""There is exactly ONE native-text rung ladder, and everybody calls it.

History this guard is the residue of. The ladder used to exist twice (O-1:
inline in `ocr/pipeline.py` and privately in `webapp/worker.py`, drifted in rung
ORDER), and then six times — production plus five oracle/cache consumers. Batch
4 caught the six drifting: GEOM-1 wired `parse_native_woodforest` into the
production ladder while the five oracle copies still lacked it, which would have
made the forensic oracles read Woodforest documents with the generic rung while
production used geometry. An oracle that reads different bytes than production
is not an oracle.

Batch 4's answer was an AST guard comparing the six copies. RUNG-SEAM deleted
the copies instead: `ocr/native_text.py::native_statement` is the ladder, and
the six consumers BIND that function rather than reproduce it. So the drift
comparison is retired and replaced by the assertion it was approximating —
single source:

  1. every consumer's ladder name IS the one function object (identity, not
     equality of an extracted call list);
  2. nothing outside `ocr/native_text.py` calls a rung directly, so a seventh
     copy cannot appear without failing here;
  3. every extractor the module defines is actually wired into the ladder, and
     the generic rung is still last.

Clause 2 is the completeness scan carried over from the AST guard, rekeyed:
the old scan looked for the text `or parse_native_pdf_text(`, which a delegating
consumer no longer contains.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

from ocr import native_text

REPO = Path(__file__).resolve().parent.parent

#: module -> the attribute its call sites use for the ladder. Production first.
#: The names differ because the call sites predate the seam and were not
#: touched; what matters is that each resolves to the same object.
LADDER_BINDINGS = {
    "ocr.pipeline": "_native_statement",
    "adb_debug": "_native_statement",
    "adb_forensic_audit": "native_statement",
    "balance_forensic_audit": "native_document",
    "build_corpus_cache": "native_document",
    "deterministic_coverage_audit": "native_statement",
}

#: `tests/` calls individual extractors on purpose (a rung is unit-tested by
#: calling it); `.claude/` holds worktrees of this same repository.
_SKIP_PREFIXES = (".claude/", "tests/")
_LADDER_HOME = "ocr/native_text.py"


def _ladder_rungs() -> list[str]:
    """The ordered rung names inside `ocr/native_text.py::native_statement`."""
    tree = ast.parse((REPO / _LADDER_HOME).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "native_statement":
            return [
                call.func.id
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id.startswith("parse_native_")
            ]
    raise AssertionError(f"{_LADDER_HOME} has no native_statement")


def _repo_modules():
    for path in sorted(REPO.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(_SKIP_PREFIXES) or "site-packages" in rel or rel == _LADDER_HOME:
            continue
        try:
            yield rel, ast.parse(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError, SyntaxError):
            continue


def test_every_consumer_binds_the_one_ladder():
    """Identity, not similarity: there is nothing left that could drift."""
    bound = {
        module: getattr(importlib.import_module(module), attribute, None)
        for module, attribute in LADDER_BINDINGS.items()
    }
    wrong = {
        module: obj for module, obj in bound.items() if obj is not native_text.native_statement
    }
    assert not wrong, (
        "these modules do not bind ocr.native_text.native_statement — a copy of "
        f"the ladder has come back: {sorted(wrong)}"
    )


def test_nothing_outside_the_ladder_home_calls_a_rung():
    """A seventh copy would have to call the extractors; nothing else may."""
    rungs = set(_ladder_rungs())
    offenders: dict[str, list[str]] = {}
    for rel, tree in _repo_modules():
        called = sorted(
            {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in rungs
            }
        )
        if called:
            offenders[rel] = called
    assert not offenders, (
        "the native rungs are composed in ocr/native_text.py::native_statement and "
        f"nowhere else; these modules call them directly: {offenders}"
    )


def test_every_extractor_the_module_defines_is_wired_into_the_ladder():
    """The other half of the GEOM-1 drift: a new rung that nobody calls.

    Batch 4's failure mode was a rung wired into one copy and not the others.
    With one copy that is impossible, and the remaining failure mode is a rung
    added to `ocr/native_text.py` and never put in the ladder at all — which
    looks like working code and reads nothing.
    """
    tree = ast.parse((REPO / _LADDER_HOME).read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("parse_native_")
    }
    ladder = _ladder_rungs()
    assert set(ladder) == defined, (
        f"ocr/native_text.py defines {sorted(defined)} but the ladder calls "
        f"{sorted(set(ladder))}"
    )
    assert len(ladder) == len(set(ladder)), f"a rung is called twice: {ladder}"
    assert ladder[-1] == "parse_native_pdf_text", (
        "the generic rung claims every document with enough native text, so it "
        f"must stay last; the ladder ends with {ladder[-1]}"
    )
