"""P22-FENCE (Phase 2.2 cell F; ruling R9; Ruling A in code).

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
  financial reconciliation -> prefer whichever extraction reconciles". The
  characterisation reproduced it on a fake extractor whose PRIMARY fails and
  whose ALTERNATE reconciles (the base adopted the alternate: two calls,
  `model_used == settings.escalation_model`, `escalated is True`); the
  inverted test proves the alternate is never asked for.
* **Edge 2 — the Class-B -> hosted hop (FENCED, this commit).** In the webapp's
  default `parse_mode="auto"`, a dispatch that is `unclaimed`,
  `parser_exception` or `ambiguous` fell through to `extract_statement` with
  NO opt-in of any kind in the environment — the hop Ruling A refused as
  doctrine ("No 'parser failure -> hosted model' hop"). The card names the
  first two outcomes; the third reaches the SAME call site (measured at base,
  commit 034a855) and is fenced by the same gate. Without the exact literal
  `HOSTED_EXTRACTION_OPT_IN == <literal>` in the live process environment,
  auto mode now raises EXACTLY what deterministic mode raises for that
  dispatch, with `hosted_extraction == "refused_no_opt_in"` recorded on the
  exception; with it, the ONE hosted extraction runs.

The tripwires (card item 4), each named after what it forbids rather than
after a gate: (a) at most ONE `extract_statement` call in the module, inside
the body `analyze_markdown` delegates to; (b) no comparison of, or selection
between, two `reconcile(...)` results — defined CONCRETELY below as four AST
rules over `analysis/pipeline.py`; (c) the opt-in literal is in no tracked
file but its definition; (d) deterministic mode cannot reach the hosted call,
opt-in or not (the dynamic PRIVACY-3 tests in
`tests/test_privacy3_boundaries.py` stay green beside the static half here).

Mutation table (the cell's W3 section records every run): M1 a second
`extract_statement` call -> (a); M2 `if alt_recon.ok: stmt = alt` -> (b) and
the inverted edge-1 test; M3 a truthy comparison -> the exact-literal test;
M4 the literal read at import -> the set-after-import test; M5 auto mode
reaching the extractor without the literal -> the per-outcome fence tests;
M6 `escalated` derived from anything -> the pinned-False tests; M7
deterministic mode reaching the hosted call -> (d).

Hygiene: no network (the extractor is a monkeypatched fake at the
`analysis.pipeline` import site); `GEMINI_API_KEY` is asserted absent; every
fixture is synthetic furniture with invented figures and dates in 2054; the
literal is never spelled here — it is read off the module.
"""
from __future__ import annotations

import ast
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import pipeline
from analysis.config import Settings, load_settings
from analysis.schema import Statement, Transaction

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SOURCE = ROOT / "analysis" / "pipeline.py"

OPT_IN_ENV = pipeline.HOSTED_EXTRACTION_OPT_IN_ENV
OPT_IN_LITERAL = pipeline.HOSTED_EXTRACTION_OPT_IN_LITERAL
REFUSED_NO_OPT_IN = pipeline.HOSTED_EXTRACTION_REFUSED_NO_OPT_IN

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


def _statement(amount: float) -> Statement:
    """One posting of `amount` between a 1,000.00 opening and a 1,500.00
    closing, no stated totals. `reconcile`'s only check that can fire is the
    sum identity (`ok = not issues`; `summary_ok` stays `None` without stated
    totals), so `amount == 500.0` reconciles and anything else does not."""
    return Statement(
        bank=None,
        period_start="2054-01-01",
        period_end="2054-01-31",
        beginning_balance=1000.00,
        ending_balance=1500.00,
        transactions=[Transaction(
            date="2054-01-05",
            description="A POSTING",
            amount=amount,
            direction="credit",
        )],
    )


def _failing_statement() -> Statement:
    return _statement(100.00)


def _reconciling_statement() -> Statement:
    return _statement(500.00)


class _FakeExtractor:
    """Stands in for `analysis.pipeline.extract_statement` and COUNTS: `calls`
    is the list of `model=` arguments in call order. `by_model` maps a model
    name to a factory so every call returns a fresh Statement; a model with
    no factory is an unexpected call and fails loudly."""

    def __init__(self, by_model):
        self.by_model = by_model
        self.calls: list[str | None] = []

    def __call__(self, markdown, *, settings=None, model=None):
        self.calls.append(model)
        if model not in self.by_model:
            raise AssertionError(f"unexpected hosted extraction with model {model!r}")
        return self.by_model[model]()


def _settings() -> Settings:
    """Two DIFFERENT model names: the removed selection required
    `escalation_model != model`, so this is the setting under which it WOULD
    fire if it were ever re-added."""
    return Settings(api_key="", model="model-a", escalation_model="model-b")


@pytest.fixture
def clean_environment(monkeypatch):
    """No hosted key, no opt-in of any kind, no structurer: the environment an
    ordinary webapp process has."""
    assert "GEMINI_API_KEY" not in os.environ, "GEMINI_API_KEY must never be set"
    monkeypatch.delenv(OPT_IN_ENV, raising=False)
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)


@pytest.fixture
def opted_in(clean_environment, monkeypatch):
    """The operator's deliberate act: the exact literal, in the environment,
    set AFTER `analysis.pipeline` was imported (which it was, at collection)."""
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_LITERAL)


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


#: The three dispatch outcomes that reach the hosted call site, each with the
#: fixture that produces it, the exception deterministic mode raises for it,
#: and the review flag the hosted path carries it as.
OUTCOMES = {
    "unclaimed": (UNCLAIMED_MARKDOWN, _no_registration, RuntimeError, None),
    "parser_exception": (CRASHING_MARKDOWN, _crashing_registration, pr.ParserCrashError, "parser_exception"),
    "ambiguous": (AMBIGUOUS_MARKDOWN, _ambiguous_registrations, pr.AmbiguousParserError, "parser_ambiguous"),
}


# ---------------------------------------------------------------------------
# Edge 1 — the reconciliation-based selection between two hosted extractions
# ---------------------------------------------------------------------------


def test_the_alternate_extraction_that_reconciles_is_never_adopted(opted_in, monkeypatch):
    """THE INVERTED CHARACTERISATION (R9). At the base tree this test, under
    its former name `test_characterisation_base_adopts_the_alternate_
    extraction_that_reconciles` (commit 034a855), PASSED on the unsafe
    behaviour: the primary extraction failed reconciliation, so the base
    extracted AGAIN with `settings.escalation_model`, reconciled that, and
    ADOPTED it because its reconciliation passed — two hosted calls,
    `model_used == settings.escalation_model`, `escalated is True`.

    Now the same fixture — an alternate that WOULD reconcile if asked for —
    is never asked for. Exactly ONE hosted call, with `settings.model`; the
    primary's failed reconciliation STANDS (a failing validator is a finding,
    not a search objective); `escalated` is pinned False. Mutant M2 (re-adding
    `if alt_recon.ok: stmt = alt`) turns the call count back to two and the
    adopted amount back to the alternate's, and fails here."""
    fake = _FakeExtractor({
        "model-a": _failing_statement,
        "model-b": _reconciling_statement,
    })
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    report = pipeline.analyze_markdown(
        UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings,
    )

    assert fake.calls == [settings.model], (
        "a second hosted extraction ran — the R9 selection is back"
    )
    assert settings.escalation_model not in fake.calls
    assert report.model_used == settings.model
    assert report.escalated is False
    assert report.reconciliation.ok is False, (
        "the primary's failed reconciliation must stand; nothing may be "
        "adopted because it reconciles"
    )
    assert [t.amount for t in report.statement.transactions] == [100.00]


# ---------------------------------------------------------------------------
# Edge 2 — the auto-mode Class-B -> hosted hop, fenced (M5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_without_the_literal_auto_mode_takes_the_deterministic_outcome(
    outcome, clean_environment, monkeypatch,
):
    """THE INVERTED CHARACTERISATION of edge 2 (Ruling A). At base each of
    these dispatches reached the hosted extractor in auto mode with nothing
    set (commit 034a855). Now, with the variable ABSENT, auto mode raises the
    SAME class with the SAME message deterministic mode raises for the
    dispatch — the document takes the deterministic-mode outcome
    (`failed / no_parser_matched`, `review / parser_exception`,
    `review / parser_ambiguous` in the telemetry vocabulary, exactly as
    deterministic mode is classified today) — the extractor is never called,
    and the refusal is recorded on the exception object, where the
    deterministic-mode exception carries no such record."""
    markdown, registrations, expected, _flag = OUTCOMES[outcome]
    fake = _FakeExtractor({})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    with registrations():
        with pytest.raises(expected) as deterministic:
            pipeline.analyze_markdown(markdown, parse_mode="deterministic", settings=settings)
        with pytest.raises(expected) as auto:
            pipeline.analyze_markdown(markdown, parse_mode="auto", settings=settings)

    assert fake.calls == [], "auto mode reached the hosted extractor with no opt-in"
    assert type(auto.value) is type(deterministic.value)
    assert str(auto.value) == str(deterministic.value)
    assert auto.value.hosted_extraction == REFUSED_NO_OPT_IN
    assert not hasattr(deterministic.value, "hosted_extraction")
    if outcome == "unclaimed":
        assert str(auto.value) == NO_PARSER_MATCHED


@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_with_the_literal_the_single_hosted_extraction_runs(outcome, opted_in, monkeypatch):
    """The operator opted in: the ONE hosted extraction runs, with
    `settings.model`, once; the dispatch's finding is carried as its review
    flag exactly as the base carried it; nothing escalates."""
    markdown, registrations, _expected, flag = OUTCOMES[outcome]
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    with registrations():
        report = pipeline.analyze_markdown(markdown, parse_mode="auto", settings=settings)

    assert fake.calls == [settings.model]
    assert report.model_used == settings.model
    assert report.escalated is False
    if flag is not None:
        assert flag in report.integrity.flags


# ---------------------------------------------------------------------------
# The literal: exact, read at the call site, never widening deterministic mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    "1", "true", "yes", "TRUE",
    OPT_IN_LITERAL.lower(),
    OPT_IN_LITERAL + "\n",
    " " + OPT_IN_LITERAL,
    OPT_IN_LITERAL + " ",
    "I_ACCEPT_REMOTE_PAID_OCR",       # the OCR rung's literal does not stand in
], ids=["1", "true", "yes", "TRUE", "lowercase", "trailing-newline",
        "leading-space", "trailing-space", "the-ocr-literal"])
def test_only_the_exact_literal_opts_in(value, clean_environment, monkeypatch):
    """M3: a truthy comparison (`if os.environ.get(...)`) admits "1" and every
    other value here; the exact `==` admits none of them."""
    fake = _FakeExtractor({})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    monkeypatch.setenv(OPT_IN_ENV, value)

    with pytest.raises(RuntimeError, match=NO_PARSER_MATCHED) as refused:
        pipeline.analyze_markdown(UNCLAIMED_MARKDOWN, parse_mode="auto", settings=_settings())

    assert fake.calls == []
    assert refused.value.hosted_extraction == REFUSED_NO_OPT_IN
    assert pipeline.hosted_extraction_opted_in() is False


def test_the_literal_is_read_at_the_call_site_not_at_import(clean_environment, monkeypatch):
    """M4: `analysis.pipeline` was imported at collection with the variable
    absent. A module-level read would have frozen `False`; the call-site read
    sees the variable set NOW, and sees it unset again in the same process."""
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_LITERAL)
    pipeline.analyze_markdown(UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings)
    assert fake.calls == [settings.model]

    monkeypatch.delenv(OPT_IN_ENV)
    with pytest.raises(RuntimeError, match=NO_PARSER_MATCHED):
        pipeline.analyze_markdown(UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings)
    assert fake.calls == [settings.model], "a call happened with the variable unset"


def test_the_injection_seam_compares_exactly():
    assert pipeline.hosted_extraction_opted_in({}) is False
    assert pipeline.hosted_extraction_opted_in({OPT_IN_ENV: OPT_IN_LITERAL}) is True
    assert pipeline.hosted_extraction_opted_in({OPT_IN_ENV: "1"}) is False
    assert pipeline.hosted_extraction_opted_in({OPT_IN_ENV: OPT_IN_LITERAL.lower()}) is False


@pytest.mark.parametrize("outcome", list(OUTCOMES))
def test_deterministic_mode_never_reaches_the_hosted_call_even_when_opted_in(
    outcome, opted_in, monkeypatch,
):
    """Tripwire (d), dynamic half, M7. The opt-in widens AUTO mode only:
    deterministic mode — every run of record, discovery, the gate, the corpus
    slice — raises before the fence is even evaluated, literal or no literal.
    (`tests/test_privacy3_boundaries.py` proves the same with the structurer
    on; both must stay green.)"""
    markdown, registrations, expected, _flag = OUTCOMES[outcome]
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)

    with registrations():
        with pytest.raises(expected) as refused:
            pipeline.analyze_markdown(markdown, parse_mode="deterministic", settings=_settings())

    assert fake.calls == []
    assert not hasattr(refused.value, "hosted_extraction"), (
        "deterministic mode reached the fence: it must raise before it"
    )


# ---------------------------------------------------------------------------
# `escalated` is pinned False (M6)
# ---------------------------------------------------------------------------


def test_escalated_is_false_on_the_hosted_path_whose_primary_fails(opted_in, monkeypatch):
    """The one shape the removed block escalated on: a hosted result that
    fails reconciliation with an alternate model configured. Pinned False, and
    the alternate model is never consulted."""
    fake = _FakeExtractor({"model-a": _failing_statement, "model-b": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    report = pipeline.analyze_markdown(UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings)

    assert report.escalated is False
    assert report.model_used == settings.model
    assert fake.calls == [settings.model]


def test_escalated_is_assigned_only_the_constant_false_in_the_module():
    """Static half of M6: every binding of the name `escalated` in
    `analysis/pipeline.py` is the constant `False` — never a tuple unpack, an
    augmented assignment, a walrus, or a computed value."""
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


# ---------------------------------------------------------------------------
# Tripwire (a): at most ONE `extract_statement` call, where `analyze_markdown` delegates
# ---------------------------------------------------------------------------


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


def test_at_most_one_extract_statement_call_in_the_module_inside_the_analysis_body():
    """M1: a second call anywhere — guarded however it likes — fails here.
    `analyze_markdown` is a thin call onto `_analyse`, which is where the one
    call lives; the card's "analyze_markdown contains at most ONE" is read
    over that delegation, and the delegation itself is pinned."""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    calls = _calls_to(tree, "extract_statement")
    assert len(calls) <= 1, f"{len(calls)} extract_statement calls in analysis/pipeline.py"
    assert len(_calls_to(_function(tree, "analyze_markdown"), "extract_statement")) == 0
    assert _calls_to(_function(tree, "analyze_markdown"), "_analyse"), (
        "analyze_markdown no longer delegates to _analyse"
    )
    if calls:
        assert _calls_to(_function(tree, "_analyse"), "extract_statement") == calls


def test_the_one_hosted_call_sits_behind_the_deterministic_raise_and_the_fence():
    """Static half of tripwires (d) and M5: in the statement list that holds
    the one `extract_statement` call, an `if parse_mode == 'deterministic':
    raise ...` precedes it, and `if not hosted_extraction_opted_in(): raise
    ...` sits between that raise and the call. Nothing else may stand between
    the fence and the call."""
    tree = ast.parse(PIPELINE_SOURCE.read_text(encoding="utf-8"))
    [call] = _calls_to(tree, "extract_statement")
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    statement = call
    while not isinstance(statement, ast.stmt):
        statement = parents[statement]
    block = parents[statement]
    siblings = next(
        field for field in ("body", "orelse", "finalbody")
        if isinstance(getattr(block, field, None), list) and statement in getattr(block, field)
    )
    stmts = getattr(block, siblings)
    index = stmts.index(statement)
    before = stmts[:index]

    def _guard(node, test_source):
        return (
            isinstance(node, ast.If)
            and ast.unparse(node.test) == test_source
            and len(node.body) == 1 and isinstance(node.body[0], ast.Raise)
            and not node.orelse
        )

    deterministic = [i for i, node in enumerate(before) if _guard(node, "parse_mode == 'deterministic'")]
    fence = [i for i, node in enumerate(before) if _guard(node, "not hosted_extraction_opted_in()")]
    assert deterministic, "the deterministic-mode raise no longer precedes the hosted call"
    assert fence, "the fence no longer precedes the hosted call"
    assert deterministic[-1] < fence[-1] == index - 1, (
        "the fence must be the statement immediately before the hosted call, "
        "after the deterministic-mode raise"
    )


# ---------------------------------------------------------------------------
# Tripwire (b): no comparison of, or selection between, two reconcile results
# ---------------------------------------------------------------------------
#
# THE CHECK, CONCRETELY. Over every function scope of `analysis/pipeline.py`
# (nested functions and lambdas are their own scopes):
#
#   B1  at most ONE name is bound from a `reconcile(...)` call in the scope;
#   B2  a name bound from `reconcile(...)` is bound EXACTLY ONCE in its scope —
#       never re-bound, never a tuple-unpack target (the base's
#       `stmt, recon, model_used, escalated = alt, alt_recon, ...` was that);
#   B3  every `reconcile(...)` call sits in one of exactly two syntactic
#       positions: the value of a single-target `Name = reconcile(...)`
#       assignment, or a direct POSITIONAL argument of `_account_report(...)`.
#       Any other parent — a comparison, an `if`/`while`/conditional-expression
#       test, a boolean operation, an attribute access on the call, a return,
#       any other function's argument list — is refused;
#   B4  no `Compare`, `BoolOp` or `IfExp` node reads attributes of two DIFFERENT
#       reconcile-bound names (belt for B1: two scopes cannot share a name, but
#       a reviewer can read this rule on its own).
#
# What this catches: `alt_recon = reconcile(alt)` (B1); `recon = alt_recon`
# or a tuple re-bind (B2); `if reconcile(alt).ok:` / `_pick(recon,
# reconcile(alt))` / `x = reconcile(a) if reconcile(b).ok else ...` (B3);
# `alt_recon.ok == recon.ok` (B4). What it deliberately permits: the one
# `recon = reconcile(stmt, parser_id=claiming)` per analysis, and the sibling
# loop's `_account_report(sibling, reconcile(sibling, parser_id=claiming), ...)`,
# where the result is consumed, never compared.


def _is_reconcile_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == "reconcile")
        or (isinstance(node.func, ast.Attribute) and node.func.attr == "reconcile")
    )


_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _scopes(tree: ast.Module):
    """Every function scope, with its OWN nodes (nested scopes excluded) and a
    child -> parent map over those nodes."""
    for scope in ast.walk(tree):
        if not isinstance(scope, _SCOPE_NODES):
            continue
        own: list[ast.AST] = []
        parents: dict[ast.AST, ast.AST] = {}
        stack = [scope]
        while stack:
            node = stack.pop()
            own.append(node)
            for child in ast.iter_child_nodes(node):
                parents[child] = node
                if isinstance(child, _SCOPE_NODES):
                    continue
                stack.append(child)
        yield scope, own, parents


def _bound_names(target: ast.AST) -> list[str]:
    return [node.id for node in ast.walk(target) if isinstance(node, ast.Name)]


def reconcile_selection_violations(source: str) -> list[str]:
    """The rule set above, as a pure function of the module text: a list of
    violations, empty when the module is clean. Exposed as a function so the
    mutation table can call it on a mutant without touching the tree."""
    tree = ast.parse(source)
    violations: list[str] = []
    for scope, own, parents in _scopes(tree):
        label = getattr(scope, "name", "<lambda>")
        reconcile_bound: list[str] = []
        for node in own:
            if isinstance(node, ast.Assign) and _is_reconcile_call(node.value):
                for target in node.targets:
                    reconcile_bound.extend(_bound_names(target))
        if len(reconcile_bound) > 1:
            violations.append(f"B1 {label}: {len(reconcile_bound)} names bound from reconcile(): {reconcile_bound}")
        for name in reconcile_bound:
            sites = 0
            for node in own:
                if isinstance(node, ast.Assign):
                    sites += sum(name in _bound_names(t) for t in node.targets)
                elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr, ast.For, ast.comprehension)):
                    sites += name in _bound_names(node.target)
                elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                    sites += name in _bound_names(node.optional_vars)
            if sites != 1:
                violations.append(f"B2 {label}: `{name}` is bound {sites} times")
        for node in own:
            if not _is_reconcile_call(node):
                continue
            parent = parents.get(node)
            single_assignment = (
                isinstance(parent, ast.Assign) and parent.value is node
                and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name)
            )
            account_report_argument = (
                isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name)
                and parent.func.id == "_account_report" and node in parent.args
            )
            if not (single_assignment or account_report_argument):
                violations.append(f"B3 {label}: reconcile() in a refused position: {ast.unparse(parent)}")
        bound = set(reconcile_bound)
        for node in own:
            if isinstance(node, (ast.Compare, ast.BoolOp, ast.IfExp)):
                roots = {
                    leaf.value.id for leaf in ast.walk(node)
                    if isinstance(leaf, ast.Attribute) and isinstance(leaf.value, ast.Name)
                    and leaf.value.id in bound
                }
                if len(roots) > 1:
                    violations.append(f"B4 {label}: two reconcile results read together: {ast.unparse(node)}")
    return violations


def test_no_two_reconcile_results_are_compared_or_selected_between():
    assert reconcile_selection_violations(PIPELINE_SOURCE.read_text(encoding="utf-8")) == []


def test_the_reconcile_selection_check_catches_the_base_selection_verbatim():
    """The check must fail on what the base actually had, or it guards
    nothing. The base's escalation block, re-inserted into the CURRENT module
    text after the pinned `escalated = False`, trips B1, B2 and B3 (and B4 on
    its `alt_recon.summary_ok == recon.summary_ok`). This is mutant M2 in its
    fullest form, applied in memory."""
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    anchor = "    escalated = False\n"
    assert source.count(anchor) == 1
    base_block = (
        "    if not recon.ok and settings.escalation_model != settings.model:\n"
        "        alt = normalize_statement(extract_statement(markdown, settings=settings, model=settings.escalation_model))\n"
        "        alt_recon = reconcile(alt, parser_id=claiming)\n"
        "        better_summary = bool(alt_recon.summary_ok) and not recon.summary_ok\n"
        "        fewer_issues = alt_recon.summary_ok == recon.summary_ok and len(alt_recon.issues) < len(recon.issues)\n"
        "        if alt_recon.ok or better_summary or fewer_issues:\n"
        "            stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True\n"
    )
    mutant = source.replace(anchor, anchor + base_block)
    violations = reconcile_selection_violations(mutant)
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
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")
    anchor = "    escalated = False\n"
    violations = reconcile_selection_violations(source.replace(anchor, anchor + mutant_line))
    assert any(v.startswith(("B2", "B3")) for v in violations), violations


# ---------------------------------------------------------------------------
# Tripwire (c): the literal is in no tracked file but its definition
# ---------------------------------------------------------------------------


def _tracked_files() -> list[str]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True,
    ).stdout
    return [path for path in listing.decode("utf-8").split("\0") if path]


def test_the_opt_in_literal_appears_in_no_tracked_file_but_its_definition():
    """Every TRACKED file outside `docs/`, of every type, read as bytes: the
    literal occurs exactly once in the whole tree, in `analysis/pipeline.py`
    (its definition). A `.env`, a workflow, a script, a settings file, a
    fixture or a test that spelled it would be a tracked opt-in, which is the
    one thing an opt-in must never be.

    `docs/` is prose — the cards that RULED the literal name it, and a document
    cannot set an environment variable — but nothing under `docs/` that could
    be executed or sourced may carry it either: only `.md` files there may.

    `git ls-files`, not a filesystem walk, on purpose: an untracked local
    `.env` carrying the literal is exactly the operator's deliberate act this
    fence exists to require, not a violation."""
    tracked = _tracked_files()
    assert len(tracked) > 100, "not looking at the repository"
    needle = OPT_IN_LITERAL.encode("utf-8")
    hits: dict[str, int] = {}
    docs_hits: list[str] = []
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file():
            continue
        count = path.read_bytes().count(needle)
        if not count:
            continue
        if relative.startswith("docs/"):
            if not relative.endswith(".md"):
                docs_hits.append(relative)
            continue
        hits[relative] = count
    assert hits == {"analysis/pipeline.py": 1}, hits
    assert docs_hits == [], docs_hits


def test_this_file_never_spells_the_literal():
    assert OPT_IN_LITERAL.encode("utf-8") not in Path(__file__).read_bytes()


# ---------------------------------------------------------------------------
# The webapp's auto mode, through the worker's own analysis seam
# ---------------------------------------------------------------------------


def _document():
    from ocr.document import StatementMarkdown

    return StatementMarkdown(
        source_file="s.pdf",
        model="native-pdf-text",
        pages=["completely unrecognisable text, no template furniture"],
    )


def test_webapp_auto_mode_without_the_literal_equals_deterministic_mode_on_an_unclaimed_synthetic(
    clean_environment, monkeypatch,
):
    """Card item 5: `webapp.worker._analyze_doc` — the seam `run_job` calls in
    both modes — returns the SAME (markdown, html, analysis, analysis_error)
    for an unclaimed synthetic in `auto` as in `deterministic`: no payload,
    the declared refusal `webapp/worker.py` allow-lists, and the extractor
    never reached. This is the user-facing change: a webapp user in auto mode
    without the literal now gets the deterministic refusal where the base gave
    them a hosted extraction."""
    from webapp import worker

    fake = _FakeExtractor({})
    monkeypatch.setattr(pipeline, "extract_statement", fake)

    auto = worker._analyze_doc(_document(), "s.pdf", "auto")
    deterministic = worker._analyze_doc(_document(), "s.pdf", "deterministic")

    assert auto == deterministic
    markdown, html, analysis, analysis_error = auto
    assert analysis is None
    assert analysis_error == NO_PARSER_MATCHED
    assert fake.calls == []


def test_webapp_auto_mode_with_the_literal_runs_the_single_hosted_extraction(opted_in, monkeypatch):
    """Card item 5: with the literal, the worker's auto mode runs ONE hosted
    extraction on the fake and publishes it with `escalated` False."""
    from webapp import worker

    model = load_settings().model
    fake = _FakeExtractor({model: _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)

    markdown, html, analysis, analysis_error = worker._analyze_doc(_document(), "s.pdf", "auto")

    assert analysis_error is None
    assert analysis is not None
    assert fake.calls == [model]
    assert analysis["escalated"] is False
    assert analysis["model_used"] == model
    assert analysis["parse_mode"] == "auto"
