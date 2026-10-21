"""P22-FENCE (Phase 2.2 cell F; ruling R9; Ruling A in code), after slice S3
of the model-code removal (owner ruling 2026-10-13: the product uses no model).

This file was committed FIRST as a characterisation (commit 034a855): every
test in it PASSED at the cell's base (`train12` `b23cb50`, code tree
`4f7d798`) on the behaviour the doctrine forbids, and each was inverted in the
commit that removed the edge it characterised:

* **Edge 1 — the selection (REMOVED, commit c5e28d8).** `analysis/pipeline.py`'s
  escalation block ran a SECOND hosted extraction with
  `settings.escalation_model` whenever the first failed reconciliation,
  reconciled the alternate, and "prefer[red] whichever extraction's summary
  reconciles, falling back to fewer overall issues" (`REPO_VALIDATOR_MEMO.md`
  §9 row 8) — Gustavo's R9 verbatim: "multiple extractions -> compare
  financial reconciliation -> prefer whichever extraction reconciles".
* **Edge 2 — the Class-B -> hosted hop (FENCED by P22-FENCE, then REMOVED in
  slice S3).** In the webapp's default `parse_mode="auto"`, a dispatch that is
  `unclaimed`, `parser_exception` or `ambiguous` fell through to the hosted
  extractor; P22-FENCE put the hop behind an exact operator opt-in literal,
  and slice S3 deleted the extractor (`analysis/extract.py`), the opt-in and
  the `hosted_extraction` refusal record together. Auto mode now raises
  EXACTLY what deterministic mode raises (the anchor tests at the end).

The hosted-path tests (the inverted edge-1 characterisation, the per-outcome
fence and opt-in tests, the exact-literal and read-at-call-site tests, the
literal-in-no-tracked-file scan, the fence-position pin and the opted-in
webapp test) were deleted with their subject in slice S3; git history keeps
them (last held at `3dc2e17`).

The tripwires that stay, each named after what it forbids rather than after a
gate: (a) NO `extract_statement` call anywhere in the module (it was "at most
one"); (b) no comparison of, or selection between, two `reconcile(...)`
results ANYWHERE in `analysis/pipeline.py` — defined CONCRETELY below as three
layers of AST rules over the module text (name integrity N1–N6, selection
B1–B7, re-invocation O1–O2), each layer's block comment naming what it does and
what it deliberately does not; `extract_statement` stays a GUARDED name with
no canonical import, so re-importing, naming or calling it in the module, or
defining it anywhere under `analysis/`, turns red; (d) auto mode equals
deterministic mode for every dispatch that produces no statement.

Hygiene: no network and no model (there is none to call); every fixture is
synthetic furniture with invented figures and dates in 2054.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import pipeline

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SOURCE = ROOT / "analysis" / "pipeline.py"

#: The removed opt-in's environment name and literal, kept here only to prove
#: they are inert. The literal is spelled from two halves so no tracked file
#: carries it whole (the deleted tripwire (c)'s rule, kept in spirit).
RETIRED_OPT_IN_ENV = "HOSTED_EXTRACTION_OPT_IN"
RETIRED_OPT_IN_LITERAL = "I_ACCEPT_" + "HOSTED_MODEL_EXTRACTION"

#: The deterministic refusal `webapp/worker.py` allow-lists and
#: `tests/test_escalation_router.py` pins.
NO_PARSER_MATCHED = "no deterministic parser matched this statement"

#: A document NO registration claims — the shape `tests/test_q3_native_only.py`
#: already uses for the same purpose.
UNCLAIMED_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\ncompletely unrecognisable text, no template furniture\n"
)

#: Documents claimed only by the synthetic registrations registered below,
#: for exactly the duration of one test.
CRASHING_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\nP22FENCE SYNTHETIC CRASHING REGISTRATION PROBE\n"
)
AMBIGUOUS_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\nP22FENCE SYNTHETIC AMBIGUOUS REGISTRATION PROBE\n"
)


@contextmanager
def _crashing_registration():
    """One registration that claims `CRASHING_MARKDOWN` and raises in `parse`
    -> `dispatch.outcome == "parser_exception"`. Popped in `finally`."""
    def explode(markdown: str):
        raise AttributeError("synthetic crash")

    registration = pr.register(pr.Registration(
        id="_p22fence_synthetic_crash",
        bank="P22FENCE Synthetic Crash",
        markers=(pr.required(
            "probe", lambda t: "P22FENCE SYNTHETIC CRASHING REGISTRATION PROBE" in t,
        ),),
        parse=explode,
    ))
    try:
        yield
    finally:
        pr._REGISTRY.pop(registration.id, None)


@contextmanager
def _ambiguous_registrations():
    """Two registrations that both claim `AMBIGUOUS_MARKDOWN` ->
    `dispatch.outcome == "ambiguous"` (decided before any parse runs)."""
    def never_reached(markdown: str):
        raise AssertionError("an ambiguous dispatch parses nothing")

    ids = ("_p22fence_synthetic_ambiguous_a", "_p22fence_synthetic_ambiguous_b")
    registered = [pr.register(pr.Registration(
        id=identifier,
        bank=f"P22FENCE Synthetic Ambiguous {identifier[-1].upper()}",
        markers=(pr.required(
            "probe", lambda t: "P22FENCE SYNTHETIC AMBIGUOUS REGISTRATION PROBE" in t,
        ),),
        parse=never_reached,
    )) for identifier in ids]
    try:
        yield
    finally:
        for registration in registered:
            pr._REGISTRY.pop(registration.id, None)


@contextmanager
def _no_registration():
    yield


#: The three dispatch outcomes that produce no statement (the ones that reached
#: the removed hosted call site), each with the fixture that produces it, the
#: exception deterministic mode raises for it, and the page text the fixture's
#: one sheet carries (for the worker's own seam).
OUTCOMES = {
    "unclaimed": (UNCLAIMED_MARKDOWN, _no_registration, RuntimeError,
                  "completely unrecognisable text, no template furniture"),
    "parser_exception": (CRASHING_MARKDOWN, _crashing_registration, pr.ParserCrashError,
                         "P22FENCE SYNTHETIC CRASHING REGISTRATION PROBE"),
    "ambiguous": (AMBIGUOUS_MARKDOWN, _ambiguous_registrations, pr.AmbiguousParserError,
                  "P22FENCE SYNTHETIC AMBIGUOUS REGISTRATION PROBE"),
}


# ---------------------------------------------------------------------------
# `escalated` is pinned False (M6), and tripwire (a): no extraction call at all
# ---------------------------------------------------------------------------


def test_escalated_is_assigned_only_the_constant_false_in_the_module():
    """Static half of M6: every binding of the name `escalated` in
    `analysis/pipeline.py` is the constant `False` — never a tuple unpack, an
    augmented assignment, a walrus, or a computed value. (Its dynamic half ran
    on the hosted path and was deleted with it in slice S3; the field stays on
    every payload for shape stability.)"""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    bindings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and name.id == "escalated":
                        bindings.append((node, target))
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            if isinstance(node, ast.AnnAssign) and node.value is None:
                continue  # a bare annotation (`Report.escalated: bool`) declares, it does not bind
            target = node.target
            if isinstance(target, ast.Name) and target.id == "escalated":
                bindings.append((node, target))
    assert bindings, "the pinned `escalated = False` is gone"
    for node, target in bindings:
        assert isinstance(node, ast.Assign) and isinstance(target, ast.Name), ast.unparse(node)
        assert isinstance(node.value, ast.Constant) and node.value.value is False, ast.unparse(node)


def _calls_to(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    ]


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not a top-level function of analysis/pipeline.py")


def test_no_extract_statement_call_in_the_module():
    """Tripwire (a), tightened in slice S3 from "at most ONE call, inside the
    body `analyze_markdown` delegates to" to NONE: the hosted extractor is
    deleted, so any call — guarded however it likes — fails here (and the name
    rules below refuse the name before it can be called). The delegation
    `analyze_markdown` -> `_analyse` is still pinned."""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    assert _calls_to(tree, "extract_statement") == []
    assert _calls_to(_function(tree, "analyze_markdown"), "_analyse"), (
        "analyze_markdown no longer delegates to _analyse"
    )
    assert not hasattr(pipeline, "extract_statement")


# ---------------------------------------------------------------------------
# Tripwire (b): no comparison of, or selection between, two reconcile results —
# and no way to walk around the check by SCOPE, by NAME (review F1), by LOOP,
# by the sibling exemption, or by re-invoking the analysis (re-review N2)
# ---------------------------------------------------------------------------
#
# THE CHECK, CONCRETELY. Three layers over the whole text of `analysis/pipeline.py`.
#
# NAME INTEGRITY (`name_integrity_violations`): the identifier `reconcile` is
# the ONLY handle to its function; it is bound exactly once, by its canonical
# import, and is used only to CALL. `extract_statement` stays a GUARDED name
# with NO canonical import since slice S3 of the model-code removal deleted
# its module: it may not be imported, named or called at all (a RETIRED name):
#   N1  `from .reconcile import reconcile` is the only binding of `reconcile` —
#       exactly one `ImportFrom`, relative level 1, no `asname`; the module
#       `reconcile` is named by no other `Import` / `ImportFrom`, and the module
#       `extract` and the retired name `extract_statement` by none at all; the
#       retired name appears nowhere in the module, not even as a call;
#   N2  neither name is ever a Store/Del target, a parameter, a `global` /
#       `nonlocal`, a walrus, `for`, `with` or comprehension target, or an
#       import alias;
#   N3  a Load of either name is legal ONLY as the `func` of a `Call`;
#   N4  no `Attribute` anywhere has `attr` equal to either name;
#   N5  no string constant anywhere equals either name;
#   N6  the module never calls `getattr` / `setattr` / `globals` / `locals` /
#       `vars` / `__import__` / `eval` / `exec` / `compile`, never imports
#       `importlib` or `builtins`, and never reads `sys.modules`.
#   The same rules bind the orchestration entry `_analyse` (N2/N3): it is
#   never rebound, aliased or passed — only called.
#
# SELECTION (`reconcile_selection_violations`), over UNITS — a top-level function
# TOGETHER WITH every function, lambda and comprehension nested in it, plus the
# module body outside functions. A RECONCILE-BOUND NAME of a unit is either a name
# the unit BINDS from a `reconcile(...)` call (`Name = reconcile(...)`, or a
# walrus) or a parameter the unit is HANDED one in — annotated `ReconResult` (the
# annotation is in the tree whatever `from __future__ import annotations` does at
# runtime) or named `recon`, which is what every such parameter in this module is
# called today. Re-review 2's P1: `_account_report(stmt, recon, …)` receives its
# result as a PARAMETER, so before this clause its unit held no reconcile-bound
# name at all, nothing in it could be compared against, and a second
# `reconcile(...)` bound there was the unit's first — X11:
#   B1  at most ONE reconcile-bound name in the unit;
#   B2  such a name is bound exactly once in the unit — never re-bound, never a
#       tuple-unpack target, never shadowed by a nested parameter or target;
#   B3  every `reconcile(...)` call sits in one of exactly two syntactic
#       positions: the value of a single-target `Name = reconcile(...)`, or the
#       SIBLING SHAPE — a direct positional argument of `_account_report(...)`
#       that is itself the direct argument of `accounts.append(...)`, that
#       statement standing directly in the body of a `for` loop of the unit
#       `_analyse`. Any other parent, and any `_account_report(...)` elsewhere
#       that receives a `reconcile(...)`, is refused (re-review E11);
#   B4  no `Compare`, `BoolOp` or `IfExp` anywhere in the unit reads attributes
#       of two DIFFERENT reconcile-bound names of that unit;
#   B5  a reconcile-bound name is neither BOUND nor READ inside any loop body —
#       `for`, `async for`, `while`, or a comprehension / generator — of its
#       unit (re-review E10: the idiomatic "try candidates until one
#       reconciles" re-binds one name inside a loop and passed B1–B4);
#   B6  the attribute `reconciliation` (`Report.reconciliation`, the field a
#       reconcile result becomes) is READ nowhere in the module — a result
#       consumed through a `Report` or an `_Analysed` is a result compared
#       (re-review E8/E11);
#   B7  a `reconcile(...)` call may stand ONLY in a unit these rules permit —
#       today `_analyse` ALONE, which holds both of the module's calls (the one
#       binding and the sibling loop's positional call). `_account_report` is
#       handed its result and contains no `reconcile(` at all, and neither does
#       any other unit (`assess_quality`, `assess_document_integrity`, the module
#       body). B7 is the general form of re-review 2's P1: the card's tripwire (b)
#       is "no comparison of two `reconcile(...)` results ANYWHERE in
#       `analysis/pipeline.py`", and a per-unit rule set can only see a comparison
#       in a unit where a second result can be MADE.
#
# RE-INVOCATION (`orchestration_shape_violations`) — EXACTLY two rules, and this
# comment names what they do NOT check:
#   O1  `_analyse`, `analyze_markdown` and `analyze_document` are top-level
#       functions and carry NO decorators;
#   O2  `_analyse` is called by name exactly TWICE in the module — once from
#       `analyze_markdown` and once from `analyze_document`, the module's two
#       entry points — each call a plain statement-level call, never inside a
#       loop, a `try`, a lambda or a nested function.
# NOT checked, deliberately: what else is defined at module level. An earlier
# draft of this comment claimed "no other function or lambda is defined at module
# level between the three (a wrapper needs a home)"; nothing implemented it
# (re-review 2, P3), and Ocean's ruling is that the clause adds nothing — a
# module-level function or lambda that never calls `_analyse` is INERT (it
# changes no behaviour of any entry point), and one that does call it is either a
# THIRD caller, which O2 refuses, or a rebinding / aliasing / passing of the name
# `_analyse`, which N2/N3 refuse. Both halves are pinned by tests below.
# Re-review E8b was a decorator on `_analyse` re-invoking it and keeping the
# result whose `.reconciliation` passed; it is caught by O1 and by B6. (The
# re-review direction pinned "one caller, `analyze_markdown`"; the module's real
# shape has two — the document entry calls `_analyse` too — and the pin states
# the shape as it is.)
#
# What no single-module scan can see: a helper whose body lives in ANOTHER
# module — hence the module-wide guard below over every module under
# `analysis/`, INCLUDING the definer (re-review N4: its own `def` is the one
# binding it may carry; since slice S3 `reconcile.py` is the only definer, and
# a module under `analysis/` that defines `extract_statement` again is refused).

#: Both stay GUARDED: `extract_statement` (the removed hosted extractor) is kept
#: here on purpose, so that any reintroduction — an import, a name, a call, an
#: attribute, a string, a definition anywhere under `analysis/` — turns red.
GUARDED_NAMES = frozenset({"reconcile", "extract_statement"})
#: guarded name -> (the relative module it is imported from, the names that
#: canonical `ImportFrom` may carry). `extract_statement` has NO entry since
#: slice S3: there is no permitted import of it, and so no permitted use.
CANONICAL_IMPORTS = {
    "reconcile": ("reconcile", frozenset({"reconcile", "ReconResult"})),
}
#: The guarded names with no canonical import: not even a call is permitted.
RETIRED_NAMES = GUARDED_NAMES - frozenset(CANONICAL_IMPORTS)
GUARDED_MODULES = frozenset({"reconcile", "extract"})
DYNAMIC_DOORS = frozenset({
    "getattr", "setattr", "globals", "locals", "vars", "__import__", "eval", "exec", "compile",
})
FORBIDDEN_IMPORTS = frozenset({"importlib", "builtins"})
ORCHESTRATION = ("_analyse", "analyze_markdown", "analyze_document")
LOOP_NODES = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
#: The type a `reconcile(...)` result HAS, as `analysis/pipeline.py` annotates it,
#: and the name every parameter carrying one has in the module today. Either mark
#: makes a parameter a reconcile-bound name of its unit (B1/B2/B4/B5) — the
#: annotation because that is what the module writes, the name as well because an
#: annotation can be dropped, stringified or widened and the walk-around must not
#: reopen with it (re-review 2, P1).
RECON_RESULT_TYPE = "ReconResult"
RECON_RESULT_PARAMETER = "recon"
#: B7: the units in which a `reconcile(...)` call may stand at all.
UNITS_THAT_MAY_CALL_RECONCILE = frozenset({"_analyse"})


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_reconcile_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "reconcile"


def _carries_a_reconcile_result(arg: ast.arg) -> bool:
    """A PARAMETER handed a `reconcile(...)` result (re-review 2, P1).

    True when the parameter is annotated `ReconResult` — including
    `ReconResult | None`, and including the string form, since a stringified
    annotation is still a `Constant` in the tree — or is named `recon`, which is
    what every such parameter in `analysis/pipeline.py` is called today.
    """
    if arg.arg == RECON_RESULT_PARAMETER:
        return True
    if arg.annotation is None:
        return False
    text = ast.unparse(arg.annotation)
    return RECON_RESULT_TYPE in {
        part.strip().strip("'\"") for part in text.replace("|", " ").split()
    }


def _module_of(node: ast.ImportFrom) -> str:
    return (node.module or "").split(".")[-1]


def _ancestors(node: ast.AST, parents: dict[ast.AST, ast.AST], stop: ast.AST | None = None):
    while node in parents and node is not stop:
        node = parents[node]
        yield node


def name_integrity_violations(source: str) -> list[str]:
    """N1–N6 over the whole module (plus `_analyse` under N2/N3): a list of
    violations, empty when clean."""
    tree = ast.parse(source)
    parents = _parents(tree)
    violations: list[str] = []
    canonical_count = {name: 0 for name in CANONICAL_IMPORTS}
    only_called = GUARDED_NAMES | {"_analyse"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _module_of(node)
            for alias in node.names:
                if alias.asname in only_called:
                    violations.append(f"N2 `{alias.name}` imported as guarded name `{alias.asname}`")
                if alias.name in RETIRED_NAMES:
                    violations.append(
                        f"N1 `{alias.name}` imported from {'.' * node.level}{node.module}: it has no permitted import"
                    )
                elif alias.name in GUARDED_NAMES:
                    wanted_module, _allowed = CANONICAL_IMPORTS[alias.name]
                    if alias.asname is not None:
                        violations.append(f"N1 `{alias.name}` imported as `{alias.asname}`")
                    elif node.level == 1 and (node.module or "") == wanted_module:
                        canonical_count[alias.name] += 1
                    else:
                        violations.append(f"N1 `{alias.name}` imported from {'.' * node.level}{node.module}")
                elif alias.name in GUARDED_MODULES and (node.module in (None, "", "analysis") or module == "analysis"):
                    violations.append(f"N1 module `{alias.name}` imported via `from {'.' * node.level}{node.module or ''} import`")
            if module in GUARDED_MODULES and (node.module or "") in GUARDED_MODULES | {f"analysis.{m}" for m in GUARDED_MODULES}:
                guarded = next((name for name, (mod, _a) in CANONICAL_IMPORTS.items() if mod == module), None)
                if guarded is None:
                    # The module of a retired name (`extract`, slice S3): no
                    # import from it is canonical, whatever it names.
                    violations.append(f"N1 `{ast.unparse(node)}`: the module `{module}` has no permitted import")
                else:
                    allowed = CANONICAL_IMPORTS[guarded][1]
                    for alias in node.names:
                        if alias.name not in allowed or alias.asname is not None:
                            violations.append(f"N1 `from {'.' * node.level}{node.module} import {alias.name}` is not the canonical import")
                    if node.level != 1:
                        violations.append(f"N1 `{node.module}` imported at level {node.level}")
            if any(alias.name.split(".")[0] in FORBIDDEN_IMPORTS for alias in node.names) or (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
                violations.append(f"N6 import of a dynamic door: {ast.unparse(node)}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                leaf = alias.name.split(".")[-1]
                if root in FORBIDDEN_IMPORTS:
                    violations.append(f"N6 import of a dynamic door: {ast.unparse(node)}")
                if leaf in GUARDED_MODULES or alias.asname in only_called:
                    violations.append(f"N1 `{ast.unparse(node)}`")
        elif isinstance(node, ast.Name) and node.id in only_called:
            if node.id in RETIRED_NAMES:
                violations.append(f"N1 the retired name `{node.id}` appears: {ast.unparse(parents[node])}")
            if not isinstance(node.ctx, ast.Load):
                violations.append(f"N2 `{node.id}` bound: {ast.unparse(parents[node])}")
            else:
                parent = parents.get(node)
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    violations.append(f"N3 `{node.id}` used other than as a call: {ast.unparse(parent)}")
        elif isinstance(node, ast.arg) and node.arg in only_called:
            violations.append(f"N2 `{node.arg}` is a parameter")
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and set(node.names) & only_called:
            violations.append(f"N2 {ast.unparse(node)}")
        elif isinstance(node, ast.Attribute) and node.attr in only_called:
            violations.append(f"N4 attribute access `{ast.unparse(node)}`")
        elif isinstance(node, ast.Attribute) and node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            violations.append("N6 `sys.modules` read")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in only_called:
            violations.append(f"N5 string constant {node.value!r}: {ast.unparse(parents[node])}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in DYNAMIC_DOORS:
            violations.append(f"N6 dynamic door `{ast.unparse(node)}`")
    for name, count in canonical_count.items():
        if count != 1:
            violations.append(f"N1 `{name}` has {count} canonical imports (expected exactly 1)")
    return violations


def _units(tree: ast.Module):
    """`(label, nodes)` per unit: every top-level function (and every method of a
    top-level class) with EVERYTHING nested in it, plus the module body outside
    those functions."""
    outside: list[ast.AST] = []
    units: list[tuple[str, list[ast.AST]]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            units.append((node.name, list(ast.walk(node))))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    units.append((f"{node.name}.{item.name}", list(ast.walk(item))))
                else:
                    outside.extend(ast.walk(item))
        else:
            outside.extend(ast.walk(node))
    units.append(("<module>", outside))
    return units


def _bound_names(target: ast.AST) -> list[str]:
    return [node.id for node in ast.walk(target) if isinstance(node, ast.Name)]


def _binding_sites(nodes: list[ast.AST], name: str) -> int:
    sites = 0
    for node in nodes:
        if isinstance(node, ast.Assign):
            sites += sum(name in _bound_names(t) for t in node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr, ast.For, ast.comprehension)):
            sites += name in _bound_names(node.target)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            sites += name in _bound_names(node.optional_vars)
        elif isinstance(node, ast.arg) and node.arg == name:
            sites += 1
    return sites


def _is_sibling_shape(call: ast.AST, parents: dict[ast.AST, ast.AST], unit_root: ast.AST | None) -> bool:
    """B3's one exemption, exactly: `reconcile(...)` -> positional arg of
    `_account_report(...)` -> the sole argument of `accounts.append(...)` ->
    an expression statement directly in a `for` body of `_analyse`."""
    report_call = parents.get(call)
    if not (isinstance(report_call, ast.Call) and isinstance(report_call.func, ast.Name)
            and report_call.func.id == "_account_report" and call in report_call.args):
        return False
    append_call = parents.get(report_call)
    if not (isinstance(append_call, ast.Call) and isinstance(append_call.func, ast.Attribute)
            and append_call.func.attr == "append" and isinstance(append_call.func.value, ast.Name)
            and append_call.func.value.id == "accounts" and append_call.args == [report_call]):
        return False
    statement = parents.get(append_call)
    loop = parents.get(statement)
    return (
        isinstance(statement, ast.Expr) and isinstance(loop, ast.For) and statement in loop.body
        and isinstance(unit_root, ast.FunctionDef) and unit_root.name == "_analyse"
    )


def reconcile_selection_violations(source: str) -> list[str]:
    """B1–B7 over every UNIT of the module (see the block comment above): a
    list of violations, empty when the module is clean. A pure function of the
    module text, so the mutation table can call it on a mutant without touching
    the tree."""
    tree = ast.parse(source)
    parents = _parents(tree)
    violations: list[str] = []
    for label, nodes in _units(tree):
        unit_root = nodes[0] if nodes and isinstance(nodes[0], (ast.FunctionDef, ast.AsyncFunctionDef)) else None
        reconcile_bound: list[str] = []
        for node in nodes:
            if isinstance(node, ast.Assign) and _is_reconcile_call(node.value):
                for target in node.targets:
                    reconcile_bound.extend(_bound_names(target))
            elif isinstance(node, ast.NamedExpr) and _is_reconcile_call(node.value):
                reconcile_bound.extend(_bound_names(node.target))
            elif isinstance(node, ast.arg) and _carries_a_reconcile_result(node):
                # HANDED a result rather than making one: `_account_report`'s
                # `recon: ReconResult`. Without this the unit held no
                # reconcile-bound name and B1/B4/B5 had nothing to bind to
                # (re-review 2, P1 — mutant X11).
                reconcile_bound.append(node.arg)
        if len(reconcile_bound) > 1:
            violations.append(f"B1 {label}: {len(reconcile_bound)} names bound from reconcile(): {reconcile_bound}")
        for name in reconcile_bound:
            sites = _binding_sites(nodes, name)
            if sites != 1:
                violations.append(f"B2 {label}: `{name}` is bound {sites} times")
        for node in nodes:
            if not _is_reconcile_call(node):
                continue
            if label not in UNITS_THAT_MAY_CALL_RECONCILE:
                violations.append(
                    f"B7 {label}: reconcile() called in a unit that may not call it: {ast.unparse(node)}"
                )
            parent = parents.get(node)
            single_assignment = (
                isinstance(parent, ast.Assign) and parent.value is node
                and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name)
            )
            if not (single_assignment or _is_sibling_shape(node, parents, unit_root)):
                violations.append(f"B3 {label}: reconcile() in a refused position: {ast.unparse(parent)}")
        bound = set(reconcile_bound)
        for node in nodes:
            if isinstance(node, (ast.Compare, ast.BoolOp, ast.IfExp)):
                roots = {
                    leaf.value.id for leaf in ast.walk(node)
                    if isinstance(leaf, ast.Attribute) and isinstance(leaf.value, ast.Name)
                    and leaf.value.id in bound
                }
                if len(roots) > 1:
                    violations.append(f"B4 {label}: two reconcile results read together: {ast.unparse(node)}")
            if isinstance(node, ast.Name) and node.id in bound:
                if any(isinstance(a, LOOP_NODES) for a in _ancestors(node, parents, unit_root)):
                    violations.append(f"B5 {label}: `{node.id}` {'bound' if not isinstance(node.ctx, ast.Load) else 'read'} inside a loop")
            if isinstance(node, ast.Attribute) and node.attr == "reconciliation":
                violations.append(f"B6 {label}: a reconciliation result read through an object: {ast.unparse(node)}")
    return violations


def orchestration_shape_violations(source: str) -> list[str]:
    """The re-invocation pins: no decorators on the three orchestration
    functions; `_analyse` called by name exactly twice, once each from
    `analyze_markdown` and `analyze_document`, at statement level."""
    tree = ast.parse(source)
    parents = _parents(tree)
    violations: list[str] = []
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ORCHESTRATION:
        node = functions.get(name)
        if node is None:
            violations.append(f"O1 `{name}` is not a top-level function")
        elif node.decorator_list:
            violations.append(f"O1 `{name}` is decorated: {[ast.unparse(d) for d in node.decorator_list]}")
    callers: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_analyse":
            owner = next((a for a in _ancestors(node, parents) if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))), None)
            label = getattr(owner, "name", "<lambda>") if owner is not None else "<module>"
            callers.append(label)
            if any(isinstance(a, LOOP_NODES + (ast.Try, ast.Lambda)) for a in _ancestors(node, parents, owner)):
                violations.append(f"O2 `_analyse` called inside a loop, try or lambda in `{label}`")
            if owner is not None and owner is not functions.get(label):
                violations.append(f"O2 `_analyse` called from a nested function `{label}`")
    if sorted(callers) != ["analyze_document", "analyze_markdown"]:
        violations.append(f"O2 `_analyse` callers are {sorted(callers)}, expected exactly ['analyze_document', 'analyze_markdown']")
    return violations


def test_name_integrity_holds_on_the_module():
    assert name_integrity_violations(PIPELINE_SOURCE.read_text(encoding="utf-8")) == []


def test_no_two_reconcile_results_are_compared_or_selected_between():
    assert reconcile_selection_violations(PIPELINE_SOURCE.read_text(encoding="utf-8")) == []


def test_the_orchestration_functions_are_undecorated_and_analyse_has_exactly_its_two_callers():
    assert orchestration_shape_violations(PIPELINE_SOURCE.read_text(encoding="utf-8")) == []


def _mutant(*edits: tuple[str, str]) -> str:
    """The CURRENT module text with each `(anchor, replacement)` applied once."""
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    for anchor, replacement in edits:
        assert source.count(anchor) == 1, anchor
        source = source.replace(anchor, replacement)
    return source


ANCHOR_ESCALATED = "    escalated = False\n"
ANCHOR_RECON = "    recon = reconcile(stmt, parser_id=claiming)\n"
ANCHOR_IMPORT_RECONCILE = "from .reconcile import reconcile, ReconResult\n"
#: Was the anchor `from .extract import extract_statement`; that import left with
#: the module in slice S3, so the import mutants below anchor on the reconcile
#: import, and re-adding the removed import is itself a mutant.
REMOVED_IMPORT_EXTRACT = "from .extract import extract_statement\n"
ANCHOR_DEF_ANALYSE = "def _analyse(markdown: str, *, settings: Settings | None = None,\n"


def test_the_reconcile_selection_check_catches_the_base_selection_verbatim():
    """The check must fail on what the base actually had, or it guards
    nothing. The base's escalation block, re-inserted into the CURRENT module
    text after the pinned `escalated = False`, trips B1, B2 and B3 (and B4 on
    its `alt_recon.summary_ok == recon.summary_ok`). This is mutant M2 in its
    fullest form, applied in memory."""
    base_block = (
        "    if not recon.ok and settings.escalation_model != settings.model:\n"
        "        alt = normalize_statement(extract_statement(markdown, settings=settings, model=settings.escalation_model))\n"
        "        alt_recon = reconcile(alt, parser_id=claiming)\n"
        "        better_summary = bool(alt_recon.summary_ok) and not recon.summary_ok\n"
        "        fewer_issues = alt_recon.summary_ok == recon.summary_ok and len(alt_recon.issues) < len(recon.issues)\n"
        "        if alt_recon.ok or better_summary or fewer_issues:\n"
        "            stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True\n"
    )
    violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + base_block)))
    assert any(v.startswith("B1 _analyse") for v in violations), violations
    assert any(v.startswith("B2 _analyse") and "`recon`" in v for v in violations), violations
    assert any(v.startswith("B4 _analyse") for v in violations), violations


@pytest.mark.parametrize("mutant_line", [
    "    if reconcile(stmt, parser_id=claiming).ok:\n        pass\n",
    "    recon = _better(recon, reconcile(stmt, parser_id=claiming))\n",
    "    recon = reconcile(stmt, parser_id=claiming) if reconcile(stmt).ok else recon\n",
    "    return reconcile(stmt, parser_id=claiming)\n",
], ids=["inline-test", "helper-argument", "conditional-expression", "returned"])
def test_the_reconcile_selection_check_refuses_every_other_position(mutant_line):
    violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + mutant_line)))
    assert any(v.startswith(("B2", "B3")) for v in violations), violations


def test_the_reviewers_nested_closure_selection_is_caught_across_scopes():
    """Review F1, mutant R6 verbatim: a closure inside `_analyse` binds its own
    `reconcile(...)` result and reads the enclosing `recon`. Over units it
    trips B1 (two reconcile-bound names in `_analyse`) and B4."""
    closure = (
        "    def _prefer(candidate):\n"
        "        alt_recon = reconcile(candidate, parser_id=claiming)\n"
        "        return candidate if alt_recon.ok and not recon.ok else stmt\n"
        "    stmt = _prefer(normalize_statement(stmt))\n"
    )
    violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + closure)))
    assert any(v.startswith("B1 _analyse") for v in violations), violations
    assert any(v.startswith("B4 _analyse") for v in violations), violations


def test_a_nested_parameter_shadowing_the_reconcile_result_is_caught():
    shadow = (
        "    def _judge(recon):\n"
        "        return recon.ok\n"
        "    _judge(recon)\n"
    )
    violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + shadow)))
    assert any(v.startswith("B2 _analyse") and "`recon`" in v for v in violations), violations


E10_LOOP = (
    "    for _candidate in (stmt, normalize_statement(stmt)):\n"
    "        recon = reconcile(_candidate, parser_id=claiming)\n"
    "        if recon.ok:\n"
    "            stmt = _candidate\n"
    "            break\n"
)
E11_SIBLING_ROUTE = (
    "    _alt = _account_report(\n"
    "        normalize_statement(stmt), reconcile(normalize_statement(stmt), parser_id=claiming),\n"
    "        dispatch=dispatch, settings=settings, markdown=markdown, source_markdown=markdown,\n"
    "        sheets=sheets, repair_failure=repair_failure, model_used=model_used, escalated=False,\n"
    "    )\n"
    "    if _alt.reconciliation.ok and not recon.ok:\n"
    "        stmt = normalize_statement(stmt)\n"
)
E8B_DECORATOR = (
    "def _twice(fn):\n"
    "    def wrapper(markdown, **kwargs):\n"
    "        first = fn(markdown, **kwargs)\n"
    "        if first.accounts[0].model_used.endswith(\"-deterministic\"):\n"
    "            second = fn(markdown, **kwargs)\n"
    "            if second.accounts[0].reconciliation.ok and not first.accounts[0].reconciliation.ok:\n"
    "                return second\n"
    "        return first\n"
    "    return wrapper\n"
    "\n"
    "\n"
    "@_twice\n"
)


def test_the_reviewers_loop_form_is_caught_by_b5():
    """Re-review E10 verbatim: the one `recon = reconcile(...)` line moved into a
    `for` over candidates with `if recon.ok: stmt = _candidate; break` — one
    bound name, one textual binding site, a permitted position, one root: it
    passed B1–B4 and the whole killer set at 5c59524. B5 refuses a
    reconcile-bound name bound or read inside any loop body."""
    violations = reconcile_selection_violations(_mutant((ANCHOR_RECON, E10_LOOP)))
    assert any(v.startswith("B5 _analyse") and "bound" in v for v in violations), violations
    assert any(v.startswith("B5 _analyse") and "read" in v for v in violations), violations


def test_the_reviewers_account_report_route_is_caught_by_b3_and_b6():
    """Re-review E11 verbatim: a second `reconcile(...)` consumed through
    `_account_report(...)` outside the sibling loop, its result read as
    `.reconciliation.ok` beside `recon.ok`. The narrowed B3 refuses the
    position; B6 refuses the read."""
    violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + E11_SIBLING_ROUTE)))
    assert any(v.startswith("B3 _analyse") for v in violations), violations
    assert any(v.startswith("B6 _analyse") for v in violations), violations


def test_the_reviewers_decorator_reinvocation_is_caught():
    """Re-review E8b verbatim: a decorator on `_analyse` re-invoking it only on
    deterministic results and keeping the one whose `.reconciliation.ok`
    passes — invisible to every dynamic test. Caught by the decorator pin,
    by the caller pin (the wrapper's `fn(...)` is not `_analyse` by name, but
    the decorator is), and by B6 on the module."""
    mutant = _mutant((ANCHOR_DEF_ANALYSE, E8B_DECORATOR + ANCHOR_DEF_ANALYSE))
    shape = orchestration_shape_violations(mutant)
    assert any(v.startswith("O1 `_analyse` is decorated") for v in shape), shape
    assert any(v.startswith("B6 _twice") for v in reconcile_selection_violations(mutant))


# --- re-review 2, P1: the unit that is HANDED a reconcile result

ANCHOR_QUALITY = "    quality = assess_quality(stmt, recon, dispatch=dispatch)\n"
X11_ACCOUNT_REPORT_UNIT = (
    "    _alt = normalize_statement(stmt)\n"
    "    _alt_recon = reconcile(_alt, parser_id=claiming_parser_id(dispatch))\n"
    "    if _alt_recon.ok and not recon.ok:\n"
    "        stmt, recon = _alt, _alt_recon\n"
)


def test_a_parameter_handed_a_reconcile_result_is_a_reconcile_bound_name():
    """The two marks, on synthetic parameters: the module's own annotation
    (plain, unioned, or stringified — `from __future__ import annotations`
    changes the runtime, not the tree) and the name `recon`, so that dropping
    or widening the annotation does not reopen the hole. A parameter carrying
    anything else is not one."""
    def _arg(source: str) -> ast.arg:
        return ast.parse(f"def _f({source}): pass").body[0].args.args[0]

    assert _carries_a_reconcile_result(_arg("recon: ReconResult"))
    assert _carries_a_reconcile_result(_arg("result: ReconResult"))
    assert _carries_a_reconcile_result(_arg("result: ReconResult | None"))
    assert _carries_a_reconcile_result(_arg("result: 'ReconResult'"))
    assert _carries_a_reconcile_result(_arg("recon"))
    assert not _carries_a_reconcile_result(_arg("stmt: Statement"))
    assert not _carries_a_reconcile_result(_arg("markdown: str"))


def test_reconcile_is_called_only_in_the_unit_the_rules_permit():
    """B7 on the real module: both `reconcile(` calls sit in `_analyse` — the
    one binding and the sibling loop's positional call — and NO other unit
    contains one. `_account_report` in particular is HANDED its result."""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    callers = {
        label: [ast.unparse(node) for node in nodes if _is_reconcile_call(node)]
        for label, nodes in _units(tree)
    }
    assert sorted(label for label, calls in callers.items() if calls) == ["_analyse"], callers
    assert len(callers["_analyse"]) == 2, callers["_analyse"]
    assert callers["_account_report"] == []


def test_the_re_reviewers_account_report_unit_selection_is_caught():
    """RE-REVIEW 2, P1, mutant X11 verbatim: a fresh `reconcile(...)` bound
    INSIDE `_account_report` and preferred over the passed-in `recon` — "prefer
    whichever candidate reconciles", in the protected module, on a path that
    runs in EVERY parse mode for EVERY account (deterministic included, where
    E8b / E10 / E11 could only bite in auto mode). At the closure-2 tree it
    returned `[]` from all three checkers and SURVIVED the whole killer set
    (431 / 0).

    Four rules refuse it now: B7 (a `reconcile(` call in a unit that may not
    call one), B1 (two reconcile-bound names in the unit — the parameter and
    the new binding), B2 (`recon` bound twice: the parameter and the tuple
    re-bind) and B4 (a `BoolOp` reading attributes of both)."""
    violations = reconcile_selection_violations(
        _mutant((ANCHOR_QUALITY, X11_ACCOUNT_REPORT_UNIT + ANCHOR_QUALITY)),
    )
    assert any(v.startswith("B7 _account_report") for v in violations), violations
    assert any(v.startswith("B1 _account_report") for v in violations), violations
    assert any(v.startswith("B2 _account_report") and "`recon`" in v for v in violations), violations
    assert any(v.startswith("B4 _account_report") for v in violations), violations


@pytest.mark.parametrize("unit,anchor", [
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): the unit's first line reads both readings.
    ("_account_report", "    classifications, counted = classify_statement_readings(stmt)\n"),
    ("assess_quality",
     "    aggregate_rows = sum(1 for t in stmt.transactions if \"UNCAPTURED\" in t.description.upper())\n"),
], ids=["account-report", "assess-quality"])
def test_a_bare_second_reconcile_in_a_unit_that_may_not_call_one_is_caught_by_b7(unit, anchor):
    """B7 in its general form: even a `reconcile(...)` that compares nothing —
    a single-target assignment in a permitted POSITION — is refused outside
    `_analyse`, because a unit that can make a second result is a unit where
    the comparison can be added later without a rule seeing it."""
    violations = reconcile_selection_violations(
        _mutant((anchor, "    _alt_recon = reconcile(stmt, parser_id='x')\n" + anchor)),
    )
    assert any(v.startswith(f"B7 {unit}") for v in violations), violations


# --- re-review 2, P3: what the re-invocation layer does NOT check

ANCHOR_DEF_ANALYZE_DOCUMENT = (
    "def analyze_document(markdown: str, *, settings: Settings | None = None,\n"
)
MODULE_LEVEL_HELPER = "def _module_level_helper():\n    return None\n\n\n"
MODULE_LEVEL_LAMBDA = "_module_level_lambda = lambda: None\n\n\n"
MODULE_LEVEL_WRAPPER = (
    "def _module_level_wrapper(markdown, **kwargs):\n"
    "    return _analyse(markdown, **kwargs)\n\n\n"
)


@pytest.mark.parametrize("definition", [MODULE_LEVEL_HELPER, MODULE_LEVEL_LAMBDA],
                         ids=["def", "lambda"])
def test_a_module_level_definition_that_calls_nothing_is_inert_and_deliberately_uncaught(definition):
    """RE-REVIEW 2, P3 — the premise of Ocean's ruling, proven rather than
    asserted. A `def` and a lambda inserted at module level between `_analyse`
    and `analyze_document` that call nothing ADD NOTHING to any of the three
    layers' verdicts (the deleted comment clause claimed otherwise) — and they
    are INERT: removing the inserted top-level statement from the mutant's tree
    gives the module tree back exactly, so nothing else in the module refers to
    the new name and no entry point can behave differently. A rule against them
    would forbid a shape that cannot do anything.

    Both halves are stated RELATIVELY, against whatever the module text says
    now, so that this test reports on the DEFINITION and never on the module: a
    test whose subject were the module's own cleanliness would fail under every
    mutant of the module and name the wrong rule in a mutation table. That the
    pristine module has no violations at all is the three headline tests'
    claim, not this one's."""
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    mutant = _mutant((ANCHOR_DEF_ANALYZE_DOCUMENT, definition + ANCHOR_DEF_ANALYZE_DOCUMENT))
    assert reconcile_selection_violations(mutant) == reconcile_selection_violations(source)
    assert name_integrity_violations(mutant) == name_integrity_violations(source)
    assert orchestration_shape_violations(mutant) == orchestration_shape_violations(source)

    original_tree = ast.parse(source)
    mutant_tree = ast.parse(mutant)
    inserted = ast.parse(definition).body
    assert len(inserted) == 1
    kept = [node for node in mutant_tree.body if ast.dump(node) != ast.dump(inserted[0])]
    assert len(kept) == len(mutant_tree.body) - 1
    mutant_tree.body = kept
    assert ast.dump(mutant_tree) == ast.dump(original_tree), (
        "the inserted definition changed something else — it is not inert"
    )


def test_a_module_level_wrapper_that_calls_analyse_is_caught_by_o2():
    """The other half of P3's premise: the same shape becomes a violation the
    moment it does anything — a module-level wrapper that CALLS `_analyse` is a
    third caller (O2), whatever it is named and wherever it sits. Nothing has
    to call the wrapper for the rule to bite."""
    mutant = _mutant((ANCHOR_DEF_ANALYZE_DOCUMENT, MODULE_LEVEL_WRAPPER + ANCHOR_DEF_ANALYZE_DOCUMENT))
    violations = orchestration_shape_violations(mutant)
    assert any(v.startswith("O2 `_analyse` callers are") for v in violations), violations
    assert "_module_level_wrapper" in " ".join(violations), violations


def test_a_module_level_lambda_that_calls_analyse_is_caught_too():
    """And through a lambda, which has no name to inspect: the caller pin
    counts the CALL, so `<lambda>` joins the caller list and O2 refuses it."""
    mutant = _mutant((
        ANCHOR_DEF_ANALYZE_DOCUMENT,
        "_module_level_lambda = lambda md, **kw: _analyse(md, **kw)\n\n\n" + ANCHOR_DEF_ANALYZE_DOCUMENT,
    ))
    violations = orchestration_shape_violations(mutant)
    assert any(v.startswith("O2") and "<lambda>" in v for v in violations), violations


@pytest.mark.parametrize("edits,rule", [
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _r = reconcile\n    alt_recon = _r(stmt, parser_id=claiming)\n"),), "N3"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "from .reconcile import reconcile as verify\n"),), "N1"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _hosted = extract_statement\n"),), "N3"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + REMOVED_IMPORT_EXTRACT),), "N1"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    stmt = extract_statement(markdown)\n"),), "N1"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "from .extract import extract_statement as _second\n"),), "N1"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "from . import extract as _extract_module\n"),), "N1"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "from . import extract as _ex\n"),
      (ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _ex.extract_statement\n")), "N4"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _f = getattr(os, \"extract_statement\")\n"),), "N5"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _f = getattr(os, \"path\")\n"),), "N6"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _f = globals()[\"extract_statement\"]\n"),), "N6"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "import importlib\n"),), "N6"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "import analysis.extract\n"),), "N1"),
    (((ANCHOR_IMPORT_RECONCILE, ANCHOR_IMPORT_RECONCILE + "from .config import Settings as reconcile\n"),), "N2"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    reconcile = None\n"),), "N2"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _m = __import__(\"sys\").modules\n"),), "N6"),
    (((ANCHOR_ESCALATED, ANCHOR_ESCALATED + "    _run = _analyse\n"),), "N3"),
], ids=["alias-reconcile", "import-as-reconcile", "alias-extract", "reimport-removed-extract",
        "call-removed-extract", "import-as-extract",
        "module-import-as", "module-attribute", "getattr-string", "getattr-any", "globals-lookup",
        "importlib", "absolute-module-import", "asname-shadow", "rebinding", "dunder-import",
        "alias-analyse"])
def test_every_alias_and_dynamic_door_is_refused(edits, rule):
    violations = name_integrity_violations(_mutant(*edits))
    assert any(v.startswith(rule) for v in violations), (rule, violations)


def test_a_reconcile_inside_a_comprehension_or_while_is_caught():
    for shape in (
        "    _oks = [reconcile(s, parser_id=claiming).ok for s in (stmt,)]\n",
        "    while not (recon := reconcile(stmt, parser_id=claiming)).ok:\n        break\n",
    ):
        violations = reconcile_selection_violations(_mutant((ANCHOR_ESCALATED, ANCHOR_ESCALATED + shape)))
        assert any(v.startswith(("B2", "B3", "B5")) for v in violations), (shape, violations)


# --- the module-wide guard: every module under analysis/, the definer included


ANALYSIS_ROOT = ROOT / "analysis"
#: `analysis/extract.py` -> `extract_statement` left this map in slice S3 with
#: the module: no module under `analysis/` may define `extract_statement` now.
DEFINERS = {"analysis/reconcile.py": "reconcile"}


def module_guard_violations(relative: str, source: str) -> list[str]:
    """For one module under `analysis/` other than `pipeline.py`: it may not
    import, alias, bind or reach `reconcile` / `extract_statement`. A definer
    may carry exactly its own `def` (and call itself) and nothing else of
    either name — re-review N4 closed the wholesale exemption. Since slice S3
    no module may define `extract_statement` at all."""
    tree = ast.parse(source)
    parents = _parents(tree)
    own = DEFINERS.get(relative)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _module_of(node)
            if any(alias.name in GUARDED_NAMES or alias.asname in GUARDED_NAMES for alias in node.names):
                offenders.append(f"{relative}: {ast.unparse(node)}")
            elif module in GUARDED_MODULES and (node.module or "") in GUARDED_MODULES | {f"analysis.{m}" for m in GUARDED_MODULES}:
                if any(alias.name != "ReconResult" for alias in node.names):
                    offenders.append(f"{relative}: {ast.unparse(node)}")
            elif any(alias.name in GUARDED_MODULES for alias in node.names) and node.module in (None, "", "analysis"):
                offenders.append(f"{relative}: {ast.unparse(node)}")
        elif isinstance(node, ast.Import):
            if any(alias.name in {"analysis.reconcile", "analysis.extract"} for alias in node.names):
                offenders.append(f"{relative}: {ast.unparse(node)}")
        elif isinstance(node, ast.Attribute) and node.attr in GUARDED_NAMES:
            offenders.append(f"{relative}: {ast.unparse(node)}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in GUARDED_NAMES:
            if node.name != own or not isinstance(parents.get(node), ast.Module):
                offenders.append(f"{relative}: defines `{node.name}`")
        elif isinstance(node, ast.Name) and node.id in GUARDED_NAMES:
            parent = parents.get(node)
            called_self = node.id == own and isinstance(node.ctx, ast.Load) and isinstance(parent, ast.Call) and parent.func is node
            if not called_self:
                offenders.append(f"{relative}: `{node.id}` {ast.unparse(parent)}")
        elif isinstance(node, ast.arg) and node.arg in GUARDED_NAMES:
            offenders.append(f"{relative}: parameter `{node.arg}`")
    return offenders


def test_no_other_module_under_analysis_imports_reconcile_or_extract_statement():
    """The module-wide guard (review F1 item 3; re-review N4): no module under
    `analysis/` other than `pipeline.py` may bind, import, alias or reach
    `reconcile` / `extract_statement` — the definer included, allowed exactly
    its own top-level `def`; and `analysis/extract.py` is gone."""
    import importlib.util

    offenders: list[str] = []
    for path in sorted(ANALYSIS_ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative == "analysis/pipeline.py":
            continue
        offenders.extend(module_guard_violations(relative, path.read_text(encoding="utf-8")))
    assert offenders == [], offenders
    assert not (ANALYSIS_ROOT / "extract.py").exists()
    assert importlib.util.find_spec("analysis.extract") is None


@pytest.mark.parametrize("relative,edit", [
    ("analysis/reconcile.py", "from .extract import extract_statement\n"),
    ("analysis/reconcile.py", "_alias = reconcile\n"),
], ids=["reconcile-imports-extract", "reconcile-aliases-itself"])
def test_a_definer_reaching_the_other_name_or_aliasing_its_own_is_caught(relative, edit):
    """Re-review N4's probe: a `reconcile` import added to `extract.py` passed
    the wholesale exemption. The definer is scanned like every other module,
    its own `def` being the one binding allowed. (The two `extract.py` cases
    left with that module in slice S3; the next test replaces them.)"""
    source = (ROOT / relative).read_text(encoding="utf-8")
    assert module_guard_violations(relative, source) == []
    assert module_guard_violations(relative, source + "\n" + edit) != []


@pytest.mark.parametrize("relative,source", [
    ("analysis/extract.py", "def extract_statement(markdown, *, settings=None, model=None):\n    return None\n"),
    ("analysis/hosted.py", "def extract_statement(markdown):\n    return None\n"),
    ("analysis/hosted.py", "from .reconcile import reconcile\n"),
], ids=["the-deleted-definer-restored", "a-new-definer", "a-new-module-imports-reconcile"])
def test_restoring_or_moving_the_hosted_extractor_under_analysis_is_caught(relative, source):
    """Slice S3: `extract_statement` has no definer. Restoring
    `analysis/extract.py` with its `def`, defining the name in any other module
    under `analysis/`, or a new module reaching `reconcile`, is refused by the
    same module-wide guard."""
    assert module_guard_violations(relative, source) != []


# ---------------------------------------------------------------------------
# THE ANCHOR (model-code removal, slice S3; plan D2): auto equals deterministic
# ---------------------------------------------------------------------------


def _raised(markdown: str, parse_mode: str, entry: str) -> BaseException:
    analyse = pipeline.analyze_document if entry == "document" else pipeline.analyze_markdown
    with pytest.raises(RuntimeError) as raised:
        analyse(markdown, parse_mode=parse_mode)
    return raised.value


@pytest.mark.parametrize("retired_opt_in", [None, RETIRED_OPT_IN_LITERAL, "1"],
                         ids=["opt-in-unset", "old-opt-in-literal", "opt-in-truthy"])
@pytest.mark.parametrize("entry", ["markdown", "document"])
@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_auto_equals_deterministic(outcome, entry, retired_opt_in, monkeypatch):
    """Adapted from P22-FENCE's card-item-5 test (auto without the literal ==
    deterministic). For every dispatch that produces no statement — `unclaimed`,
    `parser_exception`, `ambiguous` — auto mode raises the SAME class with the
    SAME message (and the same args) as deterministic mode, through both entry
    points, and neither carries a `hosted_extraction` record: there is no
    hosted path left to refuse. The removed opt-in, set to its old exact
    literal or to anything else, changes nothing (declared: until slice S3 the
    exact literal sent auto mode to the hosted extractor)."""
    markdown, registrations, expected, _page = OUTCOMES[outcome]
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)
    monkeypatch.delenv("RECONSTRUCTION_MODE", raising=False)
    if retired_opt_in is None:
        monkeypatch.delenv(RETIRED_OPT_IN_ENV, raising=False)
    else:
        monkeypatch.setenv(RETIRED_OPT_IN_ENV, retired_opt_in)

    with registrations():
        deterministic = _raised(markdown, "deterministic", entry)
        auto = _raised(markdown, "auto", entry)

    assert type(deterministic) is expected
    assert type(auto) is type(deterministic)
    assert str(auto) == str(deterministic)
    assert auto.args == deterministic.args
    assert not hasattr(auto, "hosted_extraction")
    assert not hasattr(deterministic, "hosted_extraction")
    assert auto.__context__ is None and auto.__cause__ is None
    if outcome == "unclaimed":
        assert str(auto) == NO_PARSER_MATCHED


def _document(page: str):
    from ocr.document import StatementMarkdown

    return StatementMarkdown(source_file="s.pdf", model="native-pdf-text", pages=[page])


@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_the_webapp_worker_seam_publishes_no_payload_for_each_outcome(outcome, monkeypatch):
    """Card item 5, through `webapp.worker._analyze_doc`, the seam `run_job`
    calls: no payload for each outcome, and for the unclaimed synthetic the
    declared refusal `webapp/worker.py` allow-lists (the one analysis error a
    user can act on). The old opt-in literal in the environment changes
    nothing."""
    from webapp import worker

    _markdown, registrations, _expected, page = OUTCOMES[outcome]
    monkeypatch.setenv(RETIRED_OPT_IN_ENV, RETIRED_OPT_IN_LITERAL)
    with registrations():
        _md, _html, analysis, analysis_error = worker._analyze_doc(_document(page), "s.pdf")

    assert analysis is None
    assert analysis_error
    if outcome == "unclaimed":
        assert analysis_error == NO_PARSER_MATCHED


def hosted_sdk_imports(source: str) -> list[str]:
    """Every import of the hosted extractor's SDK in `source`:
    `import google.genai`, `from google.genai import ...`, `from google import
    genai`. Empty when clean."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names
                      if alias.name == "google.genai" or alias.name.startswith("google.genai.")]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module == "google.genai" or module.startswith("google.genai."):
                found.append(module)
            elif module == "google" and any(alias.name == "genai" for alias in node.names):
                found.append("google.genai")
    return found


def test_no_python_file_in_the_tree_imports_the_hosted_sdk():
    """Slice S3 removed the last importer of `google.genai`
    (`analysis/extract.py`). No Python file in this repository imports it now,
    in any of its three spellings; a planted import of each is caught. (The
    `google-genai` requirement line left in slice S6; N6 in
    `tests/test_no_model_clients.py` keeps it out of every requirements file.)"""
    import subprocess

    try:
        listing = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, capture_output=True,
                                 check=True).stdout.decode("utf-8")
        tracked = sorted(path for path in listing.split("\0") if path)
    except (OSError, subprocess.CalledProcessError):  # an extracted tree without git: every file is tracked
        tracked = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.py")
                         if "__pycache__" not in path.parts)
    assert len(tracked) > 100, "not looking at the repository"
    offenders = []
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            hits = hosted_sdk_imports(source)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise AssertionError(f"{relative} could not be scanned: {type(exc).__name__}")
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == [], offenders
    for planted in ("import google.genai\n", "from google.genai import types\n", "from google import genai\n"):
        assert hosted_sdk_imports(planted), planted


