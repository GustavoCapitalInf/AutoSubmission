"""P20-ROUTER structural tripwires: the ABSENCE of every forbidden edge,
proved by inspecting source (AST / import graph), not by trusting a comment.

Four properties, each enforced by a mechanism a future edit cannot silently
walk past:

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
   construction.
4. Every `EscalationRouter.decide(` call site under `discovery/` and
   `webapp/` passes a `RouterInputs` built by calling `router_inputs(...)` —
   the ONE constructor — never a hand-rolled `RouterInputs(...)` and never a
   pre-built variable smuggled in from somewhere the AST cannot see it was
   built.
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


def _decide_call_sites(root: Path) -> list[tuple[Path, ast.Call]]:
    sites: list[tuple[Path, ast.Call]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _DecideCallVisitor()
        visitor.visit(tree)
        for call in visitor.calls:
            sites.append((path, call))
    return sites


def test_every_decide_call_site_in_discovery_and_webapp_uses_router_inputs():
    offenders: list[str] = []
    checked = 0
    for tree_name in ("discovery", "webapp"):
        for path, call in _decide_call_sites(ROOT / tree_name):
            checked += 1
            argument_nodes = list(call.args) + [kw.value for kw in call.keywords]
            if len(argument_nodes) != 1 or not _is_router_inputs_call(argument_nodes[0]):
                offenders.append(
                    f"{path.relative_to(ROOT)}:{call.lineno} — decide(...) argument is "
                    f"not a single `router_inputs(...)` call"
                )
    assert checked > 0, "expected at least one EscalationRouter.decide(...) call site"
    assert not offenders, "\n".join(offenders)
