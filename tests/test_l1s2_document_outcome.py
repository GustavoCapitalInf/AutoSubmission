"""The Q10 tripwire: one resolver for the DOCUMENT's outcome, and a guard that
forces S3 to extend the pins the moment a document-level fold exists.

Gustavo's Q10 ruling (2026-08-30, `BATCH9_TRANSITION.md` §8.7) says an explicit
sibling omission beside an independently valid account does NOT demote it. The
first version of L-1 stage 2's pins asserted that on the ACCOUNT leg only, and
the independent re-review showed what that misses: a `classify_document` added
to `telemetry/record.py` returning `("review", "sibling_section_omitted")` on any
omission demoted all 15 protected carriers **while every pin stayed green**. A
docstring saying "S3: extend these when your classifier lands" is a hand-off, not
a mechanism, and the failure mode Q10 was written against is precisely a stage
landing a fold that nobody's test notices.

THE MECHANISM, IN THREE PARTS

1. `document_fold()` — discovery. `analysis/` and `telemetry/` are scanned by AST
   for a symbol named like a document-level outcome (`classify_document*`,
   `document_outcome*`); the module that declares one is imported and the
   callable returned. Discovery is by SCAN and not by a hard-coded module list,
   so a fold landing in a module nobody has thought of yet is still found.
2. `document_outcome(report)` — resolution. If a fold exists, the document's
   verdict comes from it; if none exists, the document's verdict IS the published
   account's, which is true at this tree by construction (one account, no fold)
   and is what the pins have always asserted. **The pin files call only this**, so
   the day a fold lands the same assertions start reading it — without anyone
   remembering to extend them.
3. The tests below — the tripwire. They pin that this tree declares no fold and
   that the resolver agrees; they fail loudly, naming Q10, if a fold is declared
   that the resolver cannot import or whose verdict it cannot interpret; and they
   fail if production ever produces the SUPERSEDED reason string
   `sibling_section_omitted`, which is the exact demotion Q10 reversed.

Fail closed, and self-tested: the last three cases doctor a synthetic module and
a synthetic verdict to show the scanner and the interpreter can SEE what they
ban. A guard nobody has watched fail is a guard nobody has tested.

No production change, and nothing here reads a document.
"""
from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Trees a document-level fold could plausibly live in. Both are production.
SEARCHED_TREES = ("analysis", "telemetry")

#: What a document-level outcome is called. Deliberately a PATTERN and not a
#: name: S3 has not written it yet, and the two stems below are the design's own
#: vocabulary (§1.5 "the document outcome", `classify_outcome`'s sibling).
DOCUMENT_FOLD_PATTERN = re.compile(r"^(classify_document|document_outcome)\w*$")

#: The reason string design §1.5 originally folded to, and which Q10 supersedes.
#: Its appearance in production means the superseded demotion has been built.
SUPERSEDED_REASON = "sibling_section_omitted"


def _module_paths() -> list[Path]:
    return [path for tree in SEARCHED_TREES
            for path in sorted((ROOT / tree).rglob("*.py"))
            if path.name != "__init__.py"]


def _declared_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id


def _docstring_ids(tree: ast.AST) -> set[int]:
    """The string constants that are DOCSTRINGS, by identity.

    Prose may discuss the superseded reason; production may not emit it. A
    docstring is the first statement of a module, class or function and nothing
    else, which is the same rule `tests/test_no_statement_hardcodes.py` uses.
    """
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            found.add(id(body[0].value))
    return found


def superseded_reason_sites(tree: ast.AST) -> list[int]:
    """Line numbers where the superseded reason appears as a VALUE."""
    docstrings = _docstring_ids(tree)
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings and SUPERSEDED_REASON in node.value]


def declared_document_folds() -> list[str]:
    """`analysis/x.py::classify_document`-style entries, one per declaration."""
    found: list[str] = []
    for path in _module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _declared_names(tree):
            if DOCUMENT_FOLD_PATTERN.match(name):
                found.append(f"{path.relative_to(ROOT).as_posix()}::{name}")
    return sorted(found)


def document_fold():
    """`(where, callable)` for this tree's document-level fold, or None."""
    for entry in declared_document_folds():
        relative, _, name = entry.partition("::")
        module = importlib.import_module(relative[:-3].replace("/", "."))
        value = getattr(module, name, None)
        if callable(value):
            return entry, value
    return None


def _as_outcome(verdict, where: str) -> tuple[str, str]:
    if isinstance(verdict, str):
        return verdict, ""
    if isinstance(verdict, (tuple, list)) and verdict:
        return str(verdict[0]), (str(verdict[1]) if len(verdict) > 1 else "")
    raise AssertionError(
        f"the document fold {where} returned {type(verdict).__name__}, which this "
        f"resolver cannot read as an outcome. Q10 requires the 15 protected "
        f"carriers to be pinned against it: teach "
        f"tests/test_l1s2_document_outcome.py::_as_outcome this shape."
    )


def document_outcome(report) -> tuple[str, str]:
    """The DOCUMENT's outcome for a `DocumentReport`, however this tree decides it.

    With no fold declared, a document publishes one account and its outcome is
    that account's — which is what `discovery/runner.py` files today. With a fold
    declared, the fold decides, and every Q10 pin reads it through here.
    """
    from analysis.serialization import document_report_to_dict, report_to_dict
    from telemetry.record import classify_outcome

    found = document_fold()
    if found is None:
        return tuple(classify_outcome(report_to_dict(report.accounts[0])))
    where, fold = found
    refusals = []
    for argument in (report, document_report_to_dict(report)):
        try:
            verdict = fold(argument)
        except TypeError as exc:  # not this call shape; try the other
            refusals.append(f"{type(argument).__name__}: {exc}")
            continue
        return _as_outcome(verdict, where)
    raise AssertionError(
        f"the document fold {where} accepted neither a DocumentReport nor its "
        f"published payload ({'; '.join(refusals)}). Q10 requires the 15 "
        f"protected carriers to be pinned against it: teach "
        f"tests/test_l1s2_document_outcome.py::document_outcome this call shape."
    )


# ---------------------------------------------------------------------------
# the tripwire
# ---------------------------------------------------------------------------

_EXTEND = (
    "A DOCUMENT-LEVEL OUTCOME FOLD HAS LANDED, and Gustavo's Q10 ruling "
    "(BATCH9_TRANSITION §8.7) says it may NOT demote the 15 protected carriers "
    "that surface a sibling omission. Wire it into "
    "tests/test_l1s2_document_outcome.py::document_outcome so that "
    "tests/test_l1s2_protected_carriers.py and tests/test_l1s2_omission_ruling.py "
    "assert its verdict on all fifteen."
)


def test_every_declared_document_fold_is_reachable_by_the_resolver():
    """The tripwire. While no fold exists this pins that fact — so the pins are
    known to read the account leg deliberately rather than by accident — and the
    moment one is declared it must be importable and callable, which is what
    makes the Q10 assertions start reading it."""
    declared = declared_document_folds()
    found = document_fold()
    if not declared:
        assert found is None, (
            f"the resolver found {found[0] if found else None} but no module "
            f"under {SEARCHED_TREES} declares it — the scan and the resolver "
            f"disagree, and the Q10 pins rest on them agreeing"
        )
        return
    assert found is not None, f"{_EXTEND} Declared but not resolvable: {declared}."


def test_production_does_not_produce_the_superseded_omission_reason():
    """`sibling_section_omitted` is design §1.5's ORIGINAL fold reason, the exact
    demotion Q10 reversed. Prose may discuss it; production may not emit it."""
    offenders = []
    for path in _module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders += [f"{path.relative_to(ROOT).as_posix()}:{line}"
                      for line in superseded_reason_sites(tree)]
    assert not offenders, (
        f"{SUPERSEDED_REASON!r} is produced as a value at {offenders}. Q10 "
        f"superseded that fold: the document is not demoted, the omission is "
        f"surfaced beside it."
    )


def test_this_tree_declares_no_document_fold_yet():
    """Today's answer, pinned so that tomorrow's is visible. S3 landing the fold
    turns this red, which is the whole point: it is the reminder the previous
    version of these pins left to a docstring."""
    assert declared_document_folds() == []


# ---------------------------------------------------------------------------
# the tripwire, tested — a guard nobody has watched fail is untested
# ---------------------------------------------------------------------------


def test_the_scanner_sees_a_fold_when_one_is_declared(tmp_path):
    """Both spellings, and a plain assignment, on a synthetic module — and the
    account classifier beside them is NOT mistaken for one."""
    module = tmp_path / "record.py"
    module.write_text(
        "def classify_document(document):\n    return ('review', 'x')\n"
        "document_outcome_v2 = classify_document\n"
        "def classify_outcome(payload):\n    return ('validated', 'approved')\n",
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))
    caught = sorted(name for name in _declared_names(tree)
                    if DOCUMENT_FOLD_PATTERN.match(name))
    assert caught == ["classify_document", "document_outcome_v2"]
    assert "classify_outcome" not in caught


def test_the_interpreter_reads_the_shapes_a_fold_might_return():
    assert _as_outcome(("review", "sibling_account_omission_detected"), "x") == (
        "review", "sibling_account_omission_detected")
    assert _as_outcome(["validated"], "x") == ("validated", "")
    assert _as_outcome("validated", "x") == ("validated", "")
    with pytest.raises(AssertionError, match="Q10"):
        _as_outcome({"class": "review"}, "x")


def test_the_superseded_reason_scan_ignores_prose_and_catches_a_value(tmp_path):
    """The scan reads string CONSTANTS with docstrings excluded, so a module that
    explains the ruling is not an offender and one that emits the reason is."""
    prose = tmp_path / "prose.py"
    prose.write_text(f'"""Q10 superseded {SUPERSEDED_REASON}."""\nX = 1\n', encoding="utf-8")
    emitter = tmp_path / "emitter.py"
    emitter.write_text(f'REASON = "{SUPERSEDED_REASON}"\n', encoding="utf-8")
    assert superseded_reason_sites(ast.parse(prose.read_text(encoding="utf-8"))) == []
    assert superseded_reason_sites(ast.parse(emitter.read_text(encoding="utf-8"))) == [1]
