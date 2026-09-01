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
from pathlib import Path

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
        "profile", "evidence", "triggers", "attempted", "stop",
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
    assert params == ["profile", "evidence", "triggers", "attempted", "stop"]
    for name, parameter in inspect.signature(router_inputs).parameters.items():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only so a call site cannot smuggle a "
            f"sixth positional value past the pinned names"
        )


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
EXPECTED_DECIDE_CALL_SITES = {"discovery/runner.py": 2, "webapp/worker.py": 1}


#: Directories the FILESYSTEM walk never descends into: VCS/tool caches that
#: hold no first-party source, ever. Deliberately NOT `git ls-files` — an
#: untracked scratch file (never `git add`ed) still executes at runtime, and
#: a scan that only trusted the index would miss exactly that attack (found
#: measuring this test against the review's own A2 reproduction: an
#: untracked `tools/_reviewer_attack_callsite.py` was invisible to a
#: `git ls-files`-based scan).
EXCLUDED_DIR_NAMES = {
    ".git", ".github", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv",
}


def _tracked_python_files() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(ROOT).parts):
            continue
        posix = str(path.relative_to(ROOT)).replace("\\", "/")
        if posix in EXCLUDED_FROM_REPO_SCAN:
            continue
        if any(posix.startswith(tree) for tree in EXCLUDED_TREES_FROM_REPO_SCAN):
            continue
        paths.append(path)
    return paths


def _decide_call_sites_repo_wide() -> list[tuple[Path, ast.Call]]:
    sites: list[tuple[Path, ast.Call]] = []
    for path in _tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _DecideCallVisitor()
        visitor.visit(tree)
        for call in visitor.calls:
            sites.append((path, call))
    return sites


def _router_inputs_construction_sites_repo_wide() -> list[tuple[Path, int]]:
    """Every `RouterInputs(` CONSTRUCTOR CALL (not the class reference in a
    type hint) anywhere in the excluded-scope scan — the shape a hand-rolled
    call site uses instead of `router_inputs(...)`."""
    sites: list[tuple[Path, int]] = []
    for path in _tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
    offenders: list[str] = []
    by_file: dict[str, int] = {}
    for path, call in _decide_call_sites_repo_wide():
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        by_file[relative] = by_file.get(relative, 0) + 1
        argument_nodes = list(call.args) + [kw.value for kw in call.keywords]
        if len(argument_nodes) != 1 or not _is_router_inputs_call(argument_nodes[0]):
            offenders.append(
                f"{relative}:{call.lineno} — decide(...) argument is "
                f"not a single `router_inputs(...)` call"
            )
    assert not offenders, "\n".join(offenders)
    assert by_file == EXPECTED_DECIDE_CALL_SITES, (
        f"the set of decide(...) call sites changed: {by_file} != "
        f"{EXPECTED_DECIDE_CALL_SITES} — a new escalation call site anywhere "
        f"in the repository is a reviewed decision, not a silent addition"
    )


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
