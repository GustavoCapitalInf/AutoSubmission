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
  2. `LADDER_BINDINGS` is not a hand-maintained list that could go stale — the
     repository is scanned for the modules that import the ladder, and both the
     module set and the name each one binds it under must match;
  3. no module outside `ocr/native_text.py` imports or calls a rung, so the
     obvious ways to grow a seventh copy fail here (see the honesty note);
  4. every extractor the module defines is wired into the ladder, and the
     generic rung is still last.

**Honesty note on clauses 2 and 3.** These are AST scans of source text, and an
AST scan cannot see dynamic access: `getattr(native_text, "parse_native_pdf_text")`
or an `importlib` lookup composes a ladder no clause here will notice. What is
proven is narrower than "a seventh copy cannot appear" — it is that no module
imports a rung from the ladder home under any alias, and none calls one by
plain name or by attribute. Aliased imports and attribute-style calls were holes
in the batch-4 guard, which matched `ast.Name` only; they are closed. Dynamic
access is not, and no scan of this kind can close it — clause 1 is the one that
holds regardless, because it checks objects rather than text.

Clause 3 is the completeness scan carried over from the AST guard, rekeyed: the
old scan looked for the text `or parse_native_pdf_text(`, which a delegating
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
#: touched; what matters is that each resolves to the same object. Pinned
#: against the repository by `test_the_binding_list_is_the_repository`, so this
#: dict cannot quietly fall behind the code the way a hand-kept list does.
LADDER_BINDINGS = {
    "ocr.pipeline": "_native_statement",
    "adb_debug": "_native_statement",
    "adb_forensic_audit": "native_statement",
    "balance_forensic_audit": "native_document",
    "build_corpus_cache": "native_document",
    "deterministic_coverage_audit": "native_statement",
    # An INSTRUMENT, and it binds the ladder for the same reason the five
    # oracles do: W3 §DESCCOLS measures what the new extraction rung changes,
    # and a measurement taken through a privately composed ladder would be
    # measuring something production does not run — GEOM-1's lesson, one
    # directory over.
    "tools.desccols_movement": "native_statement",
    "tools.desccols_proofs": "native_statement",
}

#: `tests/` calls individual extractors on purpose (a rung is unit-tested by
#: calling it); `.claude/` holds worktrees of this same repository.
_SKIP_PREFIXES = (".claude/", "tests/")
_LADDER_HOME = "ocr/native_text.py"
#: How `from ... import native_statement` can spell this module absolutely.
#: `native_text` alone is NOT in here: `ocr` is a package, so a bare
#: `from native_text import ...` resolves to some other module entirely.
_LADDER_HOME_MODULES = {"ocr.native_text"}


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
    """(posix path, module dotted name, AST) for every scanned source file."""
    for path in sorted(REPO.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(_SKIP_PREFIXES) or "site-packages" in rel or rel == _LADDER_HOME:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError, SyntaxError):
            continue
        yield rel, rel[: -len(".py")].replace("/", "."), tree


def _is_ladder_home(node: ast.ImportFrom, rel: str) -> bool:
    """Does this `from X import ...` name `ocr/native_text.py`?

    Absolute (`from ocr.native_text import ...`) and relative
    (`from .native_text import ...` inside the `ocr` package) both count. A
    RELATIVE import of that name from outside the package is a different module
    and must not be mistaken for this one — the negative test below caught this
    branch getting it wrong.
    """
    if node.level:
        return rel.startswith("ocr/") and (node.module or "") == "native_text"
    return (node.module or "") in _LADDER_HOME_MODULES


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


def _ladder_binding(rel: str, tree: ast.AST) -> str | None:
    """The name this module binds `native_statement` to, if it imports it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not _is_ladder_home(node, rel):
            continue
        for alias in node.names:
            if alias.name == "native_statement":
                return alias.asname or alias.name
    return None


def _rungs_reached(tree: ast.AST, rungs: set[str]) -> list[str]:
    """Every way this module reaches a rung directly, import or call."""
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            reached |= {
                f"imports {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                for alias in node.names
                if alias.name in rungs
            }
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in rungs:
                reached.add(f"calls {name}")
    return sorted(reached)


def test_the_binding_list_is_the_repository():
    """LADDER_BINDINGS is derived from the code, not trusted to keep up.

    A new consumer that imports the ladder, or a consumer that renames its
    binding, fails here rather than quietly sitting outside the identity check
    above — which would otherwise pass while being blind to it.
    """
    found = {
        module_name: binding
        for rel, module_name, tree in _repo_modules()
        if (binding := _ladder_binding(rel, tree)) is not None
    }
    assert found == LADDER_BINDINGS, (
        "the modules importing ocr.native_text.native_statement, and the names "
        f"they bind it under, are {found}; LADDER_BINDINGS says {LADDER_BINDINGS}"
    )


def test_the_binding_scan_sees_a_new_consumer_and_a_renamed_binding():
    """The pin above is only worth its assertion if the scan can find things."""
    absolute = ast.parse("from ocr.native_text import native_statement\n")
    assert _ladder_binding("newthing.py", absolute) == "native_statement"

    aliased = ast.parse("from ocr.native_text import native_statement as ladder\n")
    assert _ladder_binding("newthing.py", aliased) == "ladder"

    relative = ast.parse("from .native_text import native_statement as _n\n")
    assert _ladder_binding("ocr/newthing.py", relative) == "_n"
    # ... and a relative import of that name from OUTSIDE the ocr package is a
    # different module entirely, so it must not be mistaken for the ladder.
    assert _ladder_binding("newthing.py", relative) is None

    unrelated = ast.parse("from ocr.document import StatementMarkdown\n")
    assert _ladder_binding("newthing.py", unrelated) is None


def test_the_rung_scan_catches_the_two_spellings_the_old_guard_missed():
    """Aliased imports and attribute calls — the `ast.Name`-only blind spots.

    Batch 4's guard read `ast.Name` calls only, so a seventh ladder written
    either of these ways would have passed it silently.
    """
    rungs = set(_ladder_rungs())

    plain = ast.parse("x = parse_native_pdf_text(raw)\n")
    assert _rungs_reached(plain, rungs) == ["calls parse_native_pdf_text"]

    aliased = ast.parse("from ocr.native_text import parse_native_pdf_text as generic\n")
    assert _rungs_reached(aliased, rungs) == [
        "imports parse_native_pdf_text as generic"
    ]

    attribute = ast.parse("x = native_text.parse_native_pdf_text(raw)\n")
    assert _rungs_reached(attribute, rungs) == ["calls parse_native_pdf_text"]

    # The honesty note's admitted hole, asserted so it stays admitted rather
    # than being believed closed.
    dynamic = ast.parse("x = getattr(native_text, 'parse_native_pdf_text')(raw)\n")
    assert _rungs_reached(dynamic, rungs) == []

    innocent = ast.parse("x = _parse_native_summary(text, stmt)\n")
    assert _rungs_reached(innocent, rungs) == []


def test_nothing_outside_the_ladder_home_imports_or_calls_a_rung():
    """A seventh copy would have to reach the extractors; nothing else may.

    Both spellings the batch-4 guard missed are covered: an ALIASED import
    (`from ocr.native_text import parse_native_pdf_text as generic`) is caught
    at the import, and an ATTRIBUTE call (`native_text.parse_native_pdf_text(…)`)
    is caught at the call. Dynamic access is not — see the module docstring.
    """
    rungs = set(_ladder_rungs())
    offenders = {
        rel: reached
        for rel, _module_name, tree in _repo_modules()
        if (reached := _rungs_reached(tree, rungs))
    }
    assert not offenders, (
        "the native rungs are composed in ocr/native_text.py::native_statement and "
        f"nowhere else; these modules reach them directly: {offenders}"
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
