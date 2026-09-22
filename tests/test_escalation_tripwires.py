"""P20-ROUTER structural tripwires: the ABSENCE of every forbidden edge,
proved by inspecting source (AST / import graph), not by trusting a comment.

Properties, each enforced by a mechanism a future edit cannot silently walk
past:

1. `ocr/escalation.py` and `ocr/pipeline.py` import nothing from `analysis`,
   `discovery`, `webapp` or `telemetry` — the ladder and the router cannot
   see a validator.
2. No module under `analysis/` imports `ocr.escalation`, `ocr.pipeline`,
   `ocr.ocr_client` or `discovery` — the validator cannot reach an extractor.
   The measured, pinned allowlist of `analysis/` -> `ocr` imports is EMPTY
   (measured 2026-09-01: `grep -rn "^from ocr\\|^import ocr" analysis/` finds
   nothing but comments).
3. `RouterInputs.__dataclass_fields__` equals the pinned five-field set — a
   sixth field (a payload, an outcome, a validated flag) fails this test by
   construction. `RouterInputs.__subclasses__() == []` closes the gap that
   pin alone leaves open (P20-ROUTER review, MINOR-6): a subclass ADDS a
   field and would still satisfy the base-class field check, since
   `decide()` only ever reads the five base attributes off whatever object
   it is handed.
4. Every `EscalationRouter.decide(` call site in the ENTIRE tracked repo
   (excluding `ocr/escalation.py`, where `decide` is DEFINED and
   `router_inputs`'s own `RouterInputs(...)` construction legitimately
   lives, and `tests/`, which builds fixtures) passes a `RouterInputs` built
   by calling `router_inputs(...)` — the ONE constructor — never a
   hand-rolled `RouterInputs(...)` and never a pre-built variable smuggled
   in from somewhere the AST cannot see it was built. The set of call sites
   found is asserted to be EXACTLY the three known ones (P20-ROUTER review,
   MINOR-6: a scan scoped only to `discovery/` and `webapp/` missed both a
   `RouterInputs` subclass and a hand-rolled call site under `tools/`).
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from ocr.escalation import RouterInputs, router_inputs

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_FOR_OCR_LADDER = ("analysis", "discovery", "webapp", "telemetry")

#: Measured 2026-09-01: no module under `analysis/` imports anything from
#: `ocr` at all (the handful of `ocr/...` mentions in that tree's source are
#: prose inside docstrings/comments, never an `import`). A future, deliberate
#: widening of this allowlist is a reviewed decision, not a silent drift.
ANALYSIS_TO_OCR_ALLOWLIST: frozenset[str] = frozenset()

#: The ocr modules a validator must never reach (checked alongside the
#: allowlist above and independently of it, per the card's explicit list).
FORBIDDEN_OCR_IMPORTS_FOR_ANALYSIS = ("ocr.escalation", "ocr.pipeline", "ocr.ocr_client")


def _imported_top_level_names(path: Path) -> set[str]:
    """Every `X` from `import X...` / `from X import ...` at any depth in the
    module (not just module level) — a lazy import inside a function is
    exactly the shape `ocr/pipeline.py` itself uses for `ocr.ocr_client`, so
    a guard that only looked at module-level imports would miss it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_ocr_document_imports_only_evidence_config_and_truncation():
    """P21-ROUTING design item 3: `ocr/document.py` gains an `evidence`
    import (the ONE cross-package import this module needs — `evidence/` is
    neutral and stdlib-only, so this widens no pinned boundary; see D1) but
    nothing else new: it may import `evidence` (canonical), its own
    `.config` and `.truncation`, `dataclasses`, and `__future__` — never
    `analysis`, `discovery`, `webapp`, `telemetry`, or any other `ocr.*`
    module."""
    imported = _imported_top_level_names(ROOT / "ocr" / "document.py")
    allowed = {"evidence", "evidence.canonical", "config", "truncation", "dataclasses", "__future__"}
    offenders = {name for name in imported if name not in allowed}
    assert not offenders, f"ocr/document.py imports beyond its pinned set: {sorted(offenders)}"


def test_escalation_and_pipeline_import_nothing_forbidden():
    for relative in ("ocr/escalation.py", "ocr/pipeline.py"):
        imported = _imported_top_level_names(ROOT / relative)
        offenders = {
            name for name in imported
            if any(name == pkg or name.startswith(pkg + ".") for pkg in FORBIDDEN_FOR_OCR_LADDER)
        }
        assert not offenders, f"{relative} imports forbidden package(s): {sorted(offenders)}"


def _analysis_files() -> list[Path]:
    return sorted((ROOT / "analysis").rglob("*.py"))


def test_analysis_ocr_imports_match_the_pinned_allowlist_exactly():
    found: set[str] = set()
    for path in _analysis_files():
        for name in _imported_top_level_names(path):
            if name == "ocr" or name.startswith("ocr."):
                found.add(name)
    assert found == ANALYSIS_TO_OCR_ALLOWLIST, (
        f"analysis/ -> ocr imports drifted from the pinned allowlist "
        f"{sorted(ANALYSIS_TO_OCR_ALLOWLIST)}: found {sorted(found)}. A "
        f"deliberate widening is a reviewed decision — update the pin "
        f"in the same commit that adds the import, with the justification."
    )


def test_no_analysis_module_imports_the_forbidden_ocr_or_discovery_modules():
    offenders: dict[str, set[str]] = {}
    for path in _analysis_files():
        imported = _imported_top_level_names(path)
        hit = {
            name for name in imported
            if name in FORBIDDEN_OCR_IMPORTS_FOR_ANALYSIS
            or name == "discovery" or name.startswith("discovery.")
        }
        if hit:
            offenders[str(path.relative_to(ROOT))] = hit
    assert not offenders, f"the validator must not reach an extractor: {offenders}"


def test_router_inputs_field_set_is_pinned():
    assert set(RouterInputs.__dataclass_fields__) == {
        "profile", "evidence", "triggers", "attempted", "stop", "enabled",
    }


def test_router_inputs_has_no_subclass():
    """P20-ROUTER review, MINOR-6 (attack A1): a subclass that ADDS a field
    (`payload`, `dispatch_outcome`, ...) is accepted by `EscalationRouter.decide`
    — which only reads the five base attributes off whatever it is handed —
    and would defeat the field pin above without ever tripping it, since
    `__dataclass_fields__` on the SUBCLASS includes the base's five names
    plus its own. No subclass may exist at all."""
    assert RouterInputs.__subclasses__() == []


def test_router_inputs_constructor_parameters_are_pinned_by_name():
    params = list(inspect.signature(router_inputs).parameters)
    assert params == ["profile", "evidence", "triggers", "attempted", "stop", "enabled"]
    for name, parameter in inspect.signature(router_inputs).parameters.items():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only so a call site cannot smuggle a "
            f"seventh positional value past the pinned names"
        )


# ---------------------------------------------------------------------------
# D4: every `enabled=` argument at a `decide(` call site is a MODE fact —
# `self.<attribute>` or a module-level constant — never a per-document
# expression (a call, a comprehension, a subscript, a conditional).
# ---------------------------------------------------------------------------

def _enabled_keyword_value(router_inputs_call: ast.Call) -> ast.AST | None:
    for kw in router_inputs_call.keywords:
        if kw.arg == "enabled":
            return kw.value
    return None


def _is_self_attribute(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_module_level_constant_name(node: ast.AST) -> bool:
    # Convention, not introspection: a SCREAMING_SNAKE_CASE bare name is the
    # shape every module-level constant in this tree already uses
    # (`WORKER_ENABLED_EXTRACTORS`, `ADMITTED_TRIGGERS`, ...). Anything else
    # (a lowercase local, a parameter) is refused by this predicate, which is
    # the point: a per-document local variable does not get to masquerade as
    # a "constant" merely by sitting in a bare Name node.
    return isinstance(node, ast.Name) and node.id.isupper() and "_" in node.id


def test_every_enabled_argument_is_a_mode_fact_never_a_per_document_expression():
    """D4: `enabled=` may be `self.<attribute>` (an instance field the mode
    set once, in `__init__`) or a module-level SCREAMING_SNAKE_CASE constant
    — never a call, a comprehension, a subscript, a conditional expression,
    or any other per-document computation. This is what keeps a per-document
    fact from being smuggled into the router through a field that is
    supposed to be a pure run/mode fact known before any document is read."""
    offenders: list[str] = []
    for relative, call in _decide_call_sites_repo_wide():
        argument_nodes = list(call.args) + [kw.value for kw in call.keywords]
        if len(argument_nodes) != 1 or not _is_router_inputs_call(argument_nodes[0]):
            continue  # the other test already fails this shape
        enabled_value = _enabled_keyword_value(argument_nodes[0])
        if enabled_value is None:
            offenders.append(f"{relative}:{call.lineno} — decide(...) call has no enabled= argument")
            continue
        if not (_is_self_attribute(enabled_value) or _is_module_level_constant_name(enabled_value)):
            offenders.append(
                f"{relative}:{call.lineno} — enabled= is {ast.dump(enabled_value)}, "
                f"not a self.<attribute> or a module-level constant"
            )
    assert not offenders, "\n".join(offenders)


def test_discovery_runner_enabled_extractors_is_assigned_only_in_init():
    """P21-ROUTING closure (MINOR-6). `_is_self_attribute` above accepts ANY
    `self.<attr>` reference regardless of where that attribute was LAST
    assigned — a per-document reassignment of `self.enabled_extractors`
    inside `DiscoveryRunner.process()` would still satisfy the `enabled=`
    tripwire's shape check (reproduced: mutant RX4, `self.enabled_extractors
    = frozenset({"paddle"})` inserted at the top of `process()`, SURVIVES the
    test above). This pin closes that independently, by AST, over the
    DiscoveryRunner class as a whole: `self.enabled_extractors` may be
    ASSIGNED (`=`, augmented, or annotated) ONLY inside `__init__` — nowhere
    else in the class body. `enabled` can only ever narrow what `decide`
    picks (admission already happened before it is consulted), so this is a
    belt on an already-safe design, not a closure of an exploitable gap —
    recorded precisely so a later card does not mistake the tripwire for
    more than that.

    P21-ROUTING closure-2 (MINOR-C): the first version of this pin walked
    only `Assign`/`AnnAssign`/`AugAssign` targets, only `self.<attr>`, only
    inside the CLASS body — six re-spellings survived it (`setattr`,
    `self.__dict__[...]`, `vars(self)[...]`, a tuple-unpack target, a
    `for` target, a module-level helper). The pin is now
    `_enabled_extractors_pin_offenders`: every STORE/DEL-context attribute
    named `enabled_extractors` on ANY object anywhere in the module outside
    `__init__` (which covers tuple/list/starred unpacking, `for`/`with`/
    comprehension targets, `AugAssign`, `AnnAssign`, module-level functions
    and helper methods alike, because the AST marks every target position
    with `Store`), plus a refusal of the string `"enabled_extractors"` in
    any non-docstring string constant or f-string outside `__init__`
    (which kills `setattr`, `__dict__` and `vars` at once). Each spelling
    is planted and proved caught by
    `test_enabled_extractors_pin_catches_every_reassignment_spelling`."""
    import discovery.runner as runner_module

    offenders = _enabled_extractors_pin_offenders(inspect.getsource(runner_module))
    assert offenders == [], (
        f"enabled_extractors assigned or named outside DiscoveryRunner.__init__: {offenders}"
    )


ENABLED_EXTRACTORS_ATTR = "enabled_extractors"


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """The `id()` of every Constant that is a module/class/function
    docstring — the one place prose may legitimately name the attribute."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _enabled_extractors_pin_offenders(source: str) -> list[str]:
    """MINOR-C. Every way `discovery/runner.py`'s SOURCE could assign, delete
    or name `enabled_extractors` outside `DiscoveryRunner.__init__`, as a
    list of `line: reason` strings (empty = the pin holds). Pure function of
    the source text so the planted-spelling tests below can feed it a
    mutated copy without touching the tree."""
    tree = ast.parse(source)
    init: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DiscoveryRunner":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    init = item
    assert init is not None, "DiscoveryRunner.__init__ not found in the source"
    init_first, init_last = init.lineno, init.end_lineno or init.lineno
    docstrings = _docstring_node_ids(tree)
    offenders: list[str] = []
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is None or init_first <= lineno <= init_last:
            continue
        if (
            isinstance(node, ast.Attribute) and node.attr == ENABLED_EXTRACTORS_ATTR
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            offenders.append(f"{lineno}: `{ast.unparse(node)}` is a store/delete target outside __init__")
        elif (
            isinstance(node, ast.Constant) and isinstance(node.value, str)
            and ENABLED_EXTRACTORS_ATTR in node.value and id(node) not in docstrings
        ):
            offenders.append(f"{lineno}: a non-docstring string constant names {ENABLED_EXTRACTORS_ATTR!r}")
        elif isinstance(node, ast.JoinedStr) and ENABLED_EXTRACTORS_ATTR in _fstring_text(node):
            offenders.append(f"{lineno}: an f-string names {ENABLED_EXTRACTORS_ATTR!r}")
    return offenders


def _plant_in_process(
    source: str, lines: str, module_suffix: str = "", before_process: str = "",
) -> str:
    """The reviewer's mutant shape: `lines` (already indented for a method
    body) inserted as the first statement(s) of `DiscoveryRunner.process()`
    after its docstring; `before_process` (a sibling METHOD, indented for
    the class body) inserted immediately above `def process(`;
    `module_suffix` appended at module level."""
    tree = ast.parse(source)
    process = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "process"
    )
    first = process.body[0]
    has_docstring = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
    insert_before = (process.body[1] if has_docstring else first).lineno
    src_lines = source.splitlines(keepends=True)
    return (
        "".join(src_lines[: process.lineno - 1])
        + before_process
        + "".join(src_lines[process.lineno - 1: insert_before - 1])
        + lines
        + "".join(src_lines[insert_before - 1:])
        + module_suffix
    )


#: The re-review's surviving spellings (RX4b/c/e/f/g/h), the two it killed
#: (RX4a, RX4d) as controls, and the remaining target forms the fix names.
#: Each value: (lines planted inside process(), module-level suffix,
#: sibling method planted above process()).
ENABLED_EXTRACTORS_SPELLINGS: dict[str, tuple[str, str, str]] = {
    "RX4a plain attribute": ('        self.enabled_extractors = frozenset({"paddle"})\n', "", ""),
    "RX4b setattr": ('        setattr(self, "enabled_extractors", frozenset({"paddle"}))\n', "", ""),
    "RX4c self.__dict__": ('        self.__dict__["enabled_extractors"] = frozenset({"paddle"})\n', "", ""),
    "RX4d helper method": (
        '        self._tune()\n', "",
        '    def _tune(self):\n        self.enabled_extractors = frozenset({"paddle"})\n\n',
    ),
    "RX4e tuple-unpack target": ('        self.enabled_extractors, _unused = frozenset({"paddle"}), None\n', "", ""),
    "RX4f for target": ('        for self.enabled_extractors in (frozenset({"paddle"}),):\n            pass\n', "", ""),
    "RX4g vars(self)": ('        vars(self)["enabled_extractors"] = frozenset({"paddle"})\n', "", ""),
    "RX4h module-level helper": (
        '        _tune_runner(self)\n',
        '\n\ndef _tune_runner(runner):\n    runner.enabled_extractors = frozenset({"paddle"})\n', "",
    ),
    "with target": ('        with open(__file__) as self.enabled_extractors:\n            pass\n', "", ""),
    "comprehension target": ('        [0 for self.enabled_extractors in (frozenset(),)]\n', "", ""),
    "starred/list unpack target": ('        [*self.enabled_extractors, _x] = [frozenset(), 0]\n', "", ""),
    "AugAssign": ('        self.enabled_extractors |= frozenset({"paddle"})\n', "", ""),
    "AnnAssign": ('        self.enabled_extractors: frozenset[str] = frozenset()\n', "", ""),
    "del target": ('        del self.enabled_extractors\n', "", ""),
    "adjacent-literal string": ('        setattr(self, "enabled_" "extractors", frozenset())\n', "", ""),
    "f-string attribute name": ('        setattr(self, f"enabled_extractors{\'\'}", frozenset())\n', "", ""),
    "__dict__.update in a helper": (
        '        _poke(self)\n',
        '\n\ndef _poke(runner):\n    runner.__dict__.update({"enabled_extractors": frozenset()})\n', "",
    ),
}


@pytest.mark.parametrize("spelling", sorted(ENABLED_EXTRACTORS_SPELLINGS))
def test_enabled_extractors_pin_catches_every_reassignment_spelling(spelling):
    """MINOR-C: each spelling planted into a COPY of `discovery/runner.py`'s
    source (the tree is never touched) is reported by the pin. The
    adjacent-literal spelling (`"enabled_" "extractors"` is ONE constant to
    the parser) is included so the string rule is shown to see through the
    one concatenation the compiler folds."""
    import discovery.runner as runner_module

    lines, suffix, before = ENABLED_EXTRACTORS_SPELLINGS[spelling]
    planted = _plant_in_process(inspect.getsource(runner_module), lines, suffix, before)
    offenders = _enabled_extractors_pin_offenders(planted)
    assert offenders, f"the pin did not see the spelling {spelling!r}"


def test_enabled_extractors_pin_is_not_vacuous_on_the_real_source():
    """The negative control for the parametrized test above: the pin's
    reporting is what changes when a spelling is planted, not a constant
    failure — the unmodified source yields no offender at all."""
    import discovery.runner as runner_module

    assert _enabled_extractors_pin_offenders(inspect.getsource(runner_module)) == []


# ---------------------------------------------------------------------------
# Every `decide(` call site's argument was built by `router_inputs(...)`.
# ---------------------------------------------------------------------------

class _DecideCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - ast API name
        func = node.func
        is_decide = (
            (isinstance(func, ast.Attribute) and func.attr == "decide")
            or (isinstance(func, ast.Name) and func.id == "decide")
        )
        if is_decide:
            self.calls.append(node)
        self.generic_visit(node)


def _is_router_inputs_call(node: ast.AST | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "router_inputs"
    if isinstance(func, ast.Attribute):
        return func.attr == "router_inputs"
    return False


#: The scan excludes `ocr/escalation.py` itself (where `decide` is DEFINED
#: and where `router_inputs`'s own `RouterInputs(...)` construction
#: legitimately lives) and `tests/` (fixtures). Every OTHER tracked `.py`
#: file in the repository is in scope — not merely `discovery/` and
#: `webapp/` (P20-ROUTER review, MINOR-6: a scan scoped to those two trees
#: missed a hand-rolled call site planted under `tools/`).
EXCLUDED_FROM_REPO_SCAN = ("ocr/escalation.py",)
EXCLUDED_TREES_FROM_REPO_SCAN = ("tests/",)

#: The exact, reviewed set of legitimate `decide(` call sites, by file and
#: count — 2 in `discovery/runner.py` (RECOVERY, UPGRADE), 1 in
#: `webapp/worker.py` (`_force_ocr_decision`). A new site anywhere changes
#: this and must be a reviewed decision, not a silent addition.
# Phase 3.1 adds the explicit webapp-only pair admission seam.
EXPECTED_DECIDE_CALL_SITES = {"discovery/runner.py": 2, "webapp/worker.py": 2}


#: Directories the FILESYSTEM walk never descends into: VCS/tool caches that
#: hold no first-party source, ever. Deliberately NOT `git ls-files` — an
#: untracked scratch file (never `git add`ed) still executes at runtime, and
#: a scan that only trusted the index would miss exactly that attack (found
#: measuring this test against the review's own A2 reproduction: an
#: untracked `tools/_reviewer_attack_callsite.py` was invisible to a
#: `git ls-files`-based scan).
#: `.claude` (P20-ROUTER re-review, closure 49fe3fe, MAJOR-5): the main
#: checkout holds many nested worktree checkouts under `.claude/worktrees/`
#: (this is exactly where THIS worktree itself lives). Running the suite
#: from the main checkout — which is what Ocean does at the train, and what
#: `tools/train/floor.sh` / `corpus_gate.py` do — is this scan's normal
#: operating environment, not an edge case, so a scan that walks into those
#: nested checkouts and finds their OWN copies of `discovery/runner.py` /
#: `ocr/escalation.py` breaks for a reason unrelated to what it guards.
EXCLUDED_DIR_NAMES = {
    ".git", ".github", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", ".claude",
}


def _is_nested_checkout(directory: Path) -> bool:
    """Belt-and-braces alongside `EXCLUDED_DIR_NAMES` (MAJOR-5): a directory
    that itself carries a `.git` entry (a full clone's `.git` DIRECTORY, or a
    worktree's `.git` FILE pointing back at the main repo) is a SEPARATE
    checkout, under any name, not only the ones the name-based exclusion
    above happens to list. Never applied to `ROOT` itself, which legitimately
    carries its own `.git` (this worktree's own gitdir pointer) — only to
    directories strictly BELOW it, which is what the caller enforces by
    never checking anything but discovered subdirectories."""
    return (directory / ".git").exists()


def _tracked_python_files() -> list[Path]:
    import os

    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name in EXCLUDED_DIR_NAMES:
                continue
            if _is_nested_checkout(current / name):
                continue
            kept.append(name)
        dirnames[:] = kept  # os.walk contract: prune in place, top-down
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = current / filename
            posix = str(path.relative_to(ROOT)).replace("\\", "/")
            if posix in EXCLUDED_FROM_REPO_SCAN:
                continue
            if any(posix.startswith(tree) for tree in EXCLUDED_TREES_FROM_REPO_SCAN):
                continue
            paths.append(path)
    return paths


#: P21-ROUTING closure (MAJOR-2). A repo-wide AST scan over `path.read_text()`
#: alone is blind to executable code living inside a STRING CONSTANT that is
#: itself later `exec`'d or run in a subprocess — `tools/train/provenance.py`'s
#: `_TREE_PROBE` is exactly this shape: a triple-quoted string holding a whole
#: program, passed to `python -c` in a subprocess with the checkout on
#: `sys.path`. A `decide(` or `allow_paddle_ocr=True` written inside such a
#: string is invisible to `ast.parse(path.read_text())`'s own tree, even
#: though the code genuinely runs. This is the counter-example MAJOR-2 found:
#: `test_case12_allow_paddle_ocr_true_appears_only_at_the_one_reviewed_call_site`
#: (`tests/test_paddle_routing.py`) asserted a false property because its scan
#: never looked inside `_TREE_PROBE`.
#:
#: The fix generalises rather than special-cases the one known string: ANY
#: string constant anywhere in a tracked file that (a) is long enough and
#: multi-line to plausibly be a program, not a one-line docstring fragment,
#: and (b) `ast.parse`s CLEANLY on its own, is treated as an embedded
#: program and scanned exactly like the file's own top-level tree. Ordinary
#: prose essentially never satisfies (b): English sentences are not valid
#: Python syntax. Measured over the whole tracked tree (2026-09-02): the
#: ONLY string in the entire repository that satisfies both conditions is
#: `tools/train/provenance.py::_TREE_PROBE` itself.
#:
#: P21-ROUTING closure-2 (MINOR-B). The first version parsed each string
#: VERBATIM and looked at `ast.Constant` only, so an INDENTED program (the
#: `textwrap.dedent` style — `IndentationError` is a `SyntaxError`) and an
#: f-string program (`ast.JoinedStr`, not `Constant`) were invisible. Now
#: every candidate is `textwrap.dedent`ed before parsing, and an f-string is
#: read as its constant parts joined with the placeholder NAME
#: `_FSTRING_HOLE_` standing in for each `{...}` — a program with holes in
#: expression position still parses. An f-string whose constant parts name
#: one of `EMBEDDED_PROGRAM_KEYWORDS` but which still cannot be parsed FAILS
#: CLOSED (`EmbeddedProgramUnreadable`, an `AssertionError`): the scan
#: refuses to certify what it cannot read. Still NOT covered, recorded so a
#: later card does not mistake the scan for more: `%`-format templates
#: assembled at runtime, bytes literals, and a program nested inside an
#: embedded program (the walk is one level deep).
_FSTRING_HOLE = "_FSTRING_HOLE_"
EMBEDDED_PROGRAM_KEYWORDS = ("allow_paddle_ocr", "decide(", "router_inputs(", "RouterInputs(")


class EmbeddedProgramUnreadable(AssertionError):
    """An f-string names a guarded keyword but cannot be parsed as a program
    even with placeholders — the scan fails closed rather than certify it."""


def _fstring_text(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append(_FSTRING_HOLE)
    return "".join(parts)


def _embedded_program_texts(tree: ast.AST) -> list[tuple[str, bool]]:
    """Every string constant and every f-string (as placeholder text) in
    `tree`, tagged `is_fstring`."""
    texts: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            texts.append((node.value, False))
        elif isinstance(node, ast.JoinedStr):
            texts.append((_fstring_text(node), True))
    return texts


def _embedded_program_asts(source: str) -> list[ast.AST]:
    embedded: list[ast.AST] = []
    tree = ast.parse(source)
    for text, is_fstring in _embedded_program_texts(tree):
        if len(text) < 40 or "\n" not in text:
            continue  # too short/one-line to plausibly be a program
        try:
            embedded.append(ast.parse(textwrap.dedent(text)))
        except (SyntaxError, ValueError):
            if is_fstring and any(keyword in text for keyword in EMBEDDED_PROGRAM_KEYWORDS):
                raise EmbeddedProgramUnreadable(
                    f"an f-string names {[k for k in EMBEDDED_PROGRAM_KEYWORDS if k in text]} "
                    f"but cannot be parsed as a program: the scan will not certify it"
                )
            continue
    return embedded


def _all_asts_for_source(source: str) -> list[ast.AST]:
    """The source's own AST, plus one AST per embedded program string found
    inside it (see `_embedded_program_asts`) — what every repo-wide scan in
    this module walks, instead of the top-level tree alone."""
    return [ast.parse(source), *_embedded_program_asts(source)]


def _all_asts_for_file(path: Path) -> list[ast.AST]:
    return _all_asts_for_source(path.read_text(encoding="utf-8"))


def _tree_sources() -> list[tuple[str, str]]:
    """`(posix-relative path, source text)` for every file in the repo-wide
    scan's scope. The scans below take such a list so a test can hand them
    a PLANTED copy of a file without touching the tree (MINOR-B)."""
    return [
        (str(path.relative_to(ROOT)).replace("\\", "/"), path.read_text(encoding="utf-8"))
        for path in _tracked_python_files()
    ]


@pytest.mark.parametrize("shape", ["indented", "fstring", "fstring_indented"])
def test_embedded_program_scan_reads_indented_and_fstring_programs(shape):
    """MINOR-B (E2b, E3b): a `decide(` site inside an indented or f-string
    program is now visible to the scan; verbatim-parse blindness is gone."""
    program = (
        "router.decide(router_inputs(profile=p, evidence=e, triggers=t, attempted=a, "
        "stop=False, enabled=E))\nprint('done')\n"
    )
    if shape == "indented":
        source = 'import textwrap\nP = textwrap.dedent("""\n    ' + program.replace("\n", "\n    ") + '""")\n'
    elif shape == "fstring":
        source = 'X = 1\nP = f"""\n' + program + 'print({X})\n"""\n'
    else:
        source = 'X = 1\nP = f"""\n    ' + program.replace("\n", "\n    ") + 'print({X})\n"""\n'
    sites = _decide_call_sites([("planted.py", source)])
    assert len(sites) == 1, "the embedded decide( site was not seen"


def test_embedded_program_scan_fails_closed_on_an_unreadable_fstring_naming_a_keyword():
    source = 'X = 1\nP = f"""\nthis is not python but it says allow_paddle_ocr=True {X}\nand more prose\n"""\n'
    with pytest.raises(EmbeddedProgramUnreadable):
        _embedded_program_asts(source)


def test_the_tree_probe_is_detected_as_an_embedded_program_string():
    """Measurement, corrected from an earlier over-strict version of this
    test: several pre-existing `tools/*mutation*.py` / `tools/*census*.py`
    instruments ALSO embed source-code snippets as string literals for their
    OWN mutation-testing purposes (unrelated to this closure, and none of
    them set `allow_paddle_ocr=True` or call `decide(` — confirmed by the
    scans below finding no NEW offenders there) — so `_embedded_program_asts`
    finding many files is expected, not a regression. What matters here is
    only that `tools/train/provenance.py`'s `_TREE_PROBE` — the ONE embedded
    program this closure's finding is about — is genuinely detected."""
    path = ROOT / "tools" / "train" / "provenance.py"
    count = len(_embedded_program_asts(path.read_text(encoding="utf-8")))
    assert count >= 1, "the _TREE_PROBE string was not detected as an embedded program"


def _decide_call_sites(sources: list[tuple[str, str]]) -> list[tuple[str, ast.Call]]:
    """Every `decide(` call in `sources` (file trees AND embedded program
    strings), as `(relative path, call)`."""
    sites: list[tuple[str, ast.Call]] = []
    for relative, source in sources:
        for tree in _all_asts_for_source(source):
            visitor = _DecideCallVisitor()
            visitor.visit(tree)
            for call in visitor.calls:
                sites.append((relative, call))
    return sites


def _decide_call_sites_repo_wide() -> list[tuple[str, ast.Call]]:
    return _decide_call_sites(_tree_sources())


def _check_decide_call_sites(
    sources: list[tuple[str, str]], expected: dict[str, int] = EXPECTED_DECIDE_CALL_SITES,
) -> None:
    """The `decide(` call-site pin as a pure function of `sources`: every
    site's argument is a single `router_inputs(...)` call, and the sites
    COUNT PER FILE equals `expected` exactly — a second site inside an
    already-expected file fails (MINOR-B). Raises `AssertionError`."""
    offenders: list[str] = []
    by_file: dict[str, int] = {}
    for relative, call in _decide_call_sites(sources):
        by_file[relative] = by_file.get(relative, 0) + 1
        argument_nodes = list(call.args) + [kw.value for kw in call.keywords]
        if len(argument_nodes) != 1 or not _is_router_inputs_call(argument_nodes[0]):
            offenders.append(
                f"{relative}:{call.lineno} — decide(...) argument is "
                f"not a single `router_inputs(...)` call"
            )
    assert not offenders, "\n".join(offenders)
    assert by_file == expected, (
        f"the set of decide(...) call sites changed: {by_file} != "
        f"{expected} — a new escalation call site anywhere "
        f"in the repository is a reviewed decision, not a silent addition"
    )


_PLANTED_DECIDE_SITE = (
    "\n\ndef _planted(self):\n"
    "    return self.router.decide(router_inputs(profile=None, evidence=None, triggers=(), "
    "attempted=(), stop=False, enabled=self.enabled_extractors))\n"
)


@pytest.mark.parametrize(
    "shape",
    ["plain", "indented_string", "fstring", "dict_unpacked_argument"],
)
def test_a_second_decide_site_in_an_expected_file_fails_the_per_file_count(shape):
    """MINOR-B (E7 for the `decide(` scan): the pin counts sites PER FILE,
    so a second site planted into a COPY of `discovery/runner.py` — as plain
    code, inside an indented program string, inside an f-string program, or
    hand-fed a `**{...}` argument — fails the check even though the file is
    already in the expected set. The tree is never touched."""
    runner_source = (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8")
    if shape == "plain":
        planted = runner_source + _PLANTED_DECIDE_SITE
    elif shape == "indented_string":
        planted = runner_source + '\nPROBE = """\n    ' + _PLANTED_DECIDE_SITE.strip("\n").replace("\n", "\n    ") + '\n"""\n'
    elif shape == "fstring":
        planted = runner_source + '\nX = 1\nPROBE = f"""\n' + _PLANTED_DECIDE_SITE.strip("\n") + '\nprint({X})\n"""\n'
    else:
        planted = runner_source + "\n\ndef _planted(self):\n    return self.router.decide(**{'inputs': None})\n"
    with pytest.raises(AssertionError):
        _check_decide_call_sites([("discovery/runner.py", planted)], expected={"discovery/runner.py": 2})


def test_the_decide_per_file_check_is_not_vacuous():
    runner_source = (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8")
    _check_decide_call_sites([("discovery/runner.py", runner_source)], expected={"discovery/runner.py": 2})


def _router_inputs_construction_sites_repo_wide() -> list[tuple[Path, int]]:
    """Every `RouterInputs(` CONSTRUCTOR CALL (not the class reference in a
    type hint) anywhere in the excluded-scope scan (file trees AND embedded
    program strings) — the shape a hand-rolled call site uses instead of
    `router_inputs(...)`."""
    sites: list[tuple[Path, int]] = []
    for path in _tracked_python_files():
        for tree in _all_asts_for_file(path):
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else None
                )
                if name == "RouterInputs":
                    sites.append((path, node.lineno))
    return sites


def test_every_decide_call_site_in_the_repository_uses_router_inputs():
    _check_decide_call_sites(_tree_sources())


def test_no_hand_rolled_router_inputs_construction_anywhere_in_the_repo():
    """P20-ROUTER review, MINOR-6 (attack A2): a foreign call site that
    hand-rolls `RouterInputs(...)` directly (deriving `triggers` from a
    dispatch outcome, `stop` from a reconciliation flag) never calls
    `router_inputs(...)` at all, so the previous test's `decide(...)`
    argument check cannot see it if it does not ALSO call `decide(`
    somewhere the scan reaches. This test closes that independently: zero
    `RouterInputs(` constructions anywhere but `ocr/escalation.py` itself
    (`router_inputs`'s own body) and `tests/`."""
    sites = _router_inputs_construction_sites_repo_wide()
    assert sites == [], (
        f"RouterInputs(...) constructed outside ocr/escalation.py and tests/: "
        f"{[(str(p.relative_to(ROOT)), n) for p, n in sites]}"
    )


# ---------------------------------------------------------------------------
# P22-TRUTHTABLE (Phase 2.2, D8): the research trigger's pins, APPENDED.
#
# `operator_forced_paddle` is a RUN-MODE fact, admitted by the router like
# every other admitted trigger — so what has to be proved is not that the
# router treats it specially (it does not, and must not), but that exactly ONE
# place in the tree can ever supply it, that that place is a mode constant,
# and that no `decide(` call site anywhere can name it inline.
# ---------------------------------------------------------------------------

#: The one module allowed to name the research trigger outside
#: `ocr/escalation.py`, where it is DEFINED, and `tests/`, which asserts on it.
RESEARCH_TRIGGER_SUPPLIER = "discovery/runner.py"

#: The one NAME in that module that may hold it.
RESEARCH_TRIGGER_CONSTANT = "RESEARCH_TRIGGERS"


def _research_trigger_mentions() -> dict[str, list[int]]:
    """Every tracked module that names `operator_forced_paddle` — as a string
    literal or through the escalation module's constant — and where."""
    mentions: dict[str, list[int]] = {}
    for relative, source in _tree_sources():
        if relative.replace("\\", "/").startswith("tests/"):
            continue
        lines = [
            number for number, line in enumerate(source.splitlines(), 1)
            if "operator_forced_paddle" in line or "OPERATOR_FORCED_PADDLE" in line
        ]
        if lines:
            mentions[relative.replace("\\", "/")] = lines
    return mentions


def test_only_the_escalation_module_and_one_runner_constant_name_the_research_trigger():
    """D8's structural half. The escalation module DEFINES it; the discovery
    runner names it once, to build its mode constant; the telemetry record
    mirrors the vocabulary. Nothing else in the tree may spell it — not the
    webapp worker (whose `decide(` site would otherwise be one keystroke from
    a hosted research read), not `analysis/`, not `tools/`."""
    allowed = {
        RESEARCH_TRIGGER_SUPPLIER,
        "telemetry/record.py",
        # The mutation harness's JOB is to spell forbidden shapes verbatim: it
        # carries the reviewer's N9 as a real textual edit, which is the
        # literal. It is a `tools/` instrument that executes nothing in
        # production, it is never imported by any production module, and the
        # narrower pin below (`test_no_module_spells_the_research_trigger_as_a
        # _string_constant`, scoped to `discovery/` and `telemetry/`) does not
        # exempt it at all. Building the literal by concatenation to dodge this
        # scan would be obfuscation, which is worse than an exemption with a
        # reason attached.
        "tools/p22truthtable_mutation_table.py",
    }
    mentions = _research_trigger_mentions()
    unexpected = {name: lines for name, lines in mentions.items() if name not in allowed}
    assert unexpected == {}, f"the research trigger is named outside {sorted(allowed)}: {unexpected}"
    assert RESEARCH_TRIGGER_SUPPLIER in mentions
    # `_tree_sources()` deliberately excludes `ocr/escalation.py` (the module
    # where `decide` is DEFINED), so its definition is asserted directly
    # rather than through the scan — otherwise a vanished definition would
    # read as a clean scan.
    escalation = (ROOT / "ocr" / "escalation.py").read_text(encoding="utf-8")
    assert 'OPERATOR_FORCED_PADDLE = "operator_forced_paddle"' in escalation


def test_the_research_trigger_constant_is_a_module_level_frozenset_of_one():
    """It must be a MODULE-LEVEL constant of exactly one member, assigned
    once. A per-document expression here would smuggle a document fact into
    the router through `triggers` — the same attack the `enabled=` pin above
    closes one field over — and a second member would let one flag admit two
    extractors at once."""
    import discovery.runner as runner_module

    tree = ast.parse(inspect.getsource(runner_module))
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == RESEARCH_TRIGGER_CONSTANT
                for t in node.targets)
    ]
    assert len(assignments) == 1, (
        f"{RESEARCH_TRIGGER_CONSTANT} must be assigned exactly once, at module level; "
        f"found {len(assignments)}"
    )
    call = assignments[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    assert call.func.id == "frozenset", ast.dump(call)
    assert len(call.args) == 1 and isinstance(call.args[0], ast.Set)
    assert len(call.args[0].elts) == 1, "one trigger, one extractor"
    assert getattr(runner_module, RESEARCH_TRIGGER_CONSTANT) == frozenset(
        {"operator_forced_paddle"})


#: The ONE file allowed to hold the trigger as a STRING CONSTANT outside
#: `ocr/escalation.py`: the telemetry record's mirrored vocabulary, which is a
#: tuple of literals by construction and is held equal to `ALL_TRIGGERS` by its
#: own test.
RESEARCH_TRIGGER_LITERAL_ALLOWED = "telemetry/record.py"


def test_no_module_spells_the_research_trigger_as_a_string_constant():
    """The reviewer's N9, closed statically.

    N9 escaped every pin above by spelling the trigger as a STRING LITERAL at a
    second site inside the one module the name-based pins allow — the AST pins
    look for `ast.Name` nodes, and a literal is not one. It died behaviourally,
    which is the protection that matters; this is the static half, so the shape
    cannot come back and rely on a behavioural test happening to cover the path
    it lives on (which is exactly how M11 survived once already).

    The rule: no module under `discovery/` or `telemetry/` may hold the trigger
    as a string constant, except the telemetry record's mirrored vocabulary.
    `RESEARCH_TRIGGERS` must therefore read `ocr.escalation`'s constant BY
    NAME, which is asserted alongside — a constant built from a literal would
    satisfy the shape pin and fail this one.
    """
    offenders: dict[str, list[int]] = {}
    for relative, source in _tree_sources():
        normalised = relative.replace("\\", "/")
        if not (normalised.startswith("discovery/") or normalised.startswith("telemetry/")):
            continue
        if normalised == RESEARCH_TRIGGER_LITERAL_ALLOWED:
            continue
        for tree in _all_asts_for_source(source):
            lines = [node.lineno for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and node.value == "operator_forced_paddle"]
            if lines:
                offenders.setdefault(normalised, []).extend(lines)
    assert offenders == {}, (
        "the research trigger is spelled as a string constant outside "
        f"{RESEARCH_TRIGGER_LITERAL_ALLOWED}: {offenders} — it must be read from "
        "ocr.escalation by NAME, so that the name-based pins can see every use"
    )

    import discovery.runner as runner_module

    tree = ast.parse(inspect.getsource(runner_module))
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == RESEARCH_TRIGGER_CONSTANT for t in node.targets)
    )
    members = assignment.value.args[0].elts
    assert all(isinstance(member, ast.Name) and member.id == "OPERATOR_FORCED_PADDLE"
               for member in members), (
        f"{RESEARCH_TRIGGER_CONSTANT} must be built from ocr.escalation's constant by NAME, "
        f"not from a literal: {ast.dump(assignment.value)}"
    )


def test_no_decide_call_site_names_the_research_trigger_inline():
    """A `decide(` site that built `triggers={"operator_forced_paddle"}` in
    place would satisfy every pin above — the constant would still exist and
    still be a frozenset of one — while supplying the trigger from somewhere
    the mode never decided. Every site's `triggers=` argument is therefore
    checked for the literal, wherever in the expression it sits."""
    offenders: list[str] = []
    for relative, call in _decide_call_sites_repo_wide():
        for node in ast.walk(call):
            if isinstance(node, ast.Constant) and node.value == "operator_forced_paddle":
                offenders.append(f"{relative}:{call.lineno}")
    assert offenders == [], (
        f"a decide(...) call site names the research trigger inline: {offenders}"
    )
