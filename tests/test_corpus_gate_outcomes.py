"""The corpus gate's per-document verdict check (WIRING-1 card D).

`corpus_gate.check_outcomes` proves 106 PASS / 3 WITHHELD out of the two
committed audit CSVs. Neither CSV carries a `flags`, `notes`, `risk_level` or
`possible_document_issue` column, so both oracles are structurally blind to
three kinds of truth-set movement, and all three are real:

* a pinned statement moving review<->validated, which lives entirely inside the
  audits' single PASS class (W3 §PIPEFIX P4b.5: two pinned documents made that
  move at `b8013d5` with the gate reporting GREEN over it);
* a pinned statement gaining or losing a PUBLISHED integrity flag without
  changing class — measured on this branch, where wiring the page-declaration
  check withdraws `missing_declared_statement_page` from the pinned BMO January
  statement, which is withheld before and withheld after;
* `risk_level` / `possible_document_issue` moving with class, reason and flags
  all byte-identical, because they key on `continuity_breaks >= 3` while the
  `running_balance_breaks` flag keys on the same counter being non-zero.

`check_outcome_classes` closes all three by pinning the whole published
integrity block. These tests prove it, by mutation rather than by assertion:
the gate must go RED for a moved class, a lost flag, a gained flag, a changed
note, a moved risk_level and a moved possible_document_issue, and GREEN again
when the expectation is restored. Mutations are applied to an in-memory copy of
the map — nothing on disk is touched.

The map's 109 entries are NOT verified here: `_run` drives one document so the
proofs stay fast. Only `python corpus_gate.py` (or `pytest -m corpus`) compares
all 109 against the product.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import corpus_gate

ROOT = Path(corpus_gate.__file__).resolve().parent


# --- the declaration that keeps the harness honest ---------------------------


WATCHED = {"analyze_markdown", "cached_analysis"}

#: Directories that are not production code, so their callers are out of scope.
NON_PRODUCTION_DIRS = ("tests", "docs", ".claude", ".git", "build")


def _called_name(node: ast.Call) -> str | None:
    return getattr(node.func, "id", None) or getattr(node.func, "attr", None)


def _supplies_sheets(call: ast.Call) -> bool:
    """Does this call pass a real `sheets=`?

    Conservative on both edges. A literal `sheets=None` is NOT supplying one —
    it is the fail-closed default written out — and a `**kwargs` splat is
    unreadable from here, so it is treated as UNKNOWN by the caller sweep
    rather than quietly as False.
    """
    for keyword in call.keywords:
        if keyword.arg != "sheets":
            continue
        if isinstance(keyword.value, ast.Constant) and keyword.value.value is None:
            return False
        return True
    return False


def _has_kwargs_splat(call: ast.Call) -> bool:
    return any(keyword.arg is None for keyword in call.keywords)


def _production_modules() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in NON_PRODUCTION_DIRS for part in path.relative_to(ROOT).parts)
    ]


def _callers() -> dict[str, list[ast.Call]]:
    """Every production module that calls the analysis, path -> its calls."""
    found: dict[str, list[ast.Call]] = {}
    for path in _production_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _called_name(node) in WATCHED
        ]
        if calls:
            found[path.relative_to(ROOT).as_posix()] = calls
    return found


def test_every_production_caller_of_the_analysis_is_classified():
    """No analysis caller may exist unclassified.

    The declaration below is only as good as its coverage: a helper extracted
    out of a listed function, or a brand-new caller, would leave
    `PRODUCTION_SUPPLIES_SHEETS` truthfully describing the sites it names while
    production as a whole had moved on. So the repository is swept, and every
    module that calls `analyze_markdown` or `cached_analysis` must be either a
    declared call site or an explicitly excused one.
    """
    swept = set(_callers())
    declared = {relative for relative, _function in corpus_gate.ANALYSIS_CALL_SITES}
    excluded = set(corpus_gate.EXCLUDED_ANALYSIS_CALLERS)

    unclassified = sorted(swept - declared - excluded)
    assert not unclassified, (
        f"these modules call the analysis but are in neither "
        f"corpus_gate.ANALYSIS_CALL_SITES nor EXCLUDED_ANALYSIS_CALLERS: "
        f"{unclassified}. Decide each one: does it publish a verdict a user or "
        f"a downstream record sees? Then it must be wired at activation."
    )
    stale = sorted((declared | excluded) - swept - {"corpus_gate.py"})
    assert not stale, f"declared analysis callers that no longer call it: {stale}"
    assert not (declared & excluded), "a caller cannot be both declared and excused"


def test_the_gate_harness_analyses_the_way_production_does():
    """`PRODUCTION_SUPPLIES_SHEETS` is not a preference; it is a measurement.

    The gate's verdict check must call `analyze_markdown` the way the product
    calls it. If production starts handing over the intake page list and this
    harness does not, the gate keeps reproducing the OLD verdict and goes
    silently blind on exactly the fraud-relevant flag it was added to watch —
    so the drift is a red test here rather than a quiet pass there.

    A `**kwargs` splat into one of these calls is treated as "might be
    supplying sheets" and fails unless the site is already declared as wired:
    the harness must never be more optimistic than the source it is reading.
    """
    callers = _callers()
    declared = dict(corpus_gate.ANALYSIS_CALL_SITES)
    assert declared, "no production analysis call sites were declared"

    verdicts: dict[str, bool] = {}
    for relative, function in corpus_gate.ANALYSIS_CALL_SITES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        target = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function
            ),
            None,
        )
        assert target is not None, f"{relative} has no function {function!r}"
        calls = [
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call) and _called_name(node) in WATCHED
        ]
        assert calls, f"{relative}::{function} no longer calls the analysis"
        # Every declared site must agree, so an extracted helper that stops
        # passing sheets cannot hide behind a sibling call that still does.
        verdicts[f"{relative}::{function}"] = all(_supplies_sheets(c) for c in calls)

    assert set(verdicts.values()) == {corpus_gate.PRODUCTION_SUPPLIES_SHEETS}, (
        f"corpus_gate.PRODUCTION_SUPPLIES_SHEETS is "
        f"{corpus_gate.PRODUCTION_SUPPLIES_SHEETS} but the call sites say "
        f"{verdicts}. Wiring production means wiring this harness in the same "
        f"commit — and that moves pinned verdicts, which is a truth-set ceremony."
    )

    # A keyword splat is unreadable statically, so it may not sit in an
    # excluded module pretending to be unwired.
    for relative, calls in callers.items():
        if relative in corpus_gate.EXCLUDED_ANALYSIS_CALLERS and any(
            _has_kwargs_splat(call) for call in calls
        ):
            raise AssertionError(
                f"{relative} splats **kwargs into the analysis, so whether it "
                f"supplies sheets cannot be read from the source. Declare it in "
                f"ANALYSIS_CALL_SITES instead of excusing it."
            )


def test_every_pinned_expectation_names_a_pinned_document():
    """The expectation map cannot drift off the manifest."""
    manifest = set(corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV)))
    unknown = sorted(set(corpus_gate.PINNED_OUTCOMES) - manifest)
    assert not unknown, f"PINNED_OUTCOMES names documents that are not pinned: {unknown}"


def test_the_pinned_withheld_three_agree_with_the_audit_gate():
    """The two vocabularies stay tied: the gate's WITHHELD three are these three."""
    withheld = {
        Path(rel).name
        for rel, verdict in corpus_gate.PINNED_OUTCOMES.items()
        if verdict.outcome == "withheld"
    }
    assert withheld == corpus_gate.WITHHELD_STATEMENTS


def test_the_expected_split_is_the_documented_one():
    """100 validated / 6 review / 3 withheld, derived rather than restated."""
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    counts: dict[str, int] = {}
    for rel in manifest:
        verdict = corpus_gate.PINNED_OUTCOMES.get(rel, corpus_gate.PUBLISHED_OUTCOME)
        counts[verdict.outcome] = counts.get(verdict.outcome, 0) + 1
    assert counts == {"validated": 100, "review": 6, "withheld": 3}
    assert counts["validated"] + counts["review"] == corpus_gate.EXPECTED_PASS
    assert counts["withheld"] == corpus_gate.EXPECTED_WITHHELD


def test_every_map_entry_is_a_state_the_product_can_actually_reach():
    """The map may only record verdicts `classify_outcome` can produce.

    Deliberately NOT "a non-validated entry must carry a flag". A flagless
    `review` is reachable — `classify_outcome` returns `quality_needs_review`
    when the flag list is empty and `corporate_use` is not approved — and a
    check that refused to record one would red the gate while forbidding the
    only correct remedy. What is genuinely impossible is a `validated` entry
    (validated means no flags, which is `PUBLISHED_OUTCOME`, which lives
    outside the map) and a class the classifier never emits for an analysed
    document.
    """
    assert corpus_gate.PUBLISHED_OUTCOME == corpus_gate._Verdict(
        "validated", (), (), "clear", False
    )
    reachable = {"review", "withheld"}
    for rel, verdict in corpus_gate.PINNED_OUTCOMES.items():
        assert verdict.outcome in reachable, (
            f"{rel}: {verdict.outcome!r} is not a class an analysed pinned "
            f"document reaches; validated belongs outside the map"
        )
        assert verdict.risk_level in {"clear", "review", "high"}, rel
        # risk_level is derived, so the entry must be internally consistent or
        # it could never match: high iff possible_document_issue, else review
        # iff flags, else clear (analysis/pipeline.py).
        if verdict.possible_document_issue:
            expected_risk = "high"
        elif verdict.flags:
            expected_risk = "review"
        else:
            expected_risk = "clear"
        assert verdict.risk_level == expected_risk, (
            f"{rel}: risk_level {verdict.risk_level!r} is unreachable alongside "
            f"flags={list(verdict.flags)} and "
            f"possible_document_issue={verdict.possible_document_issue}"
        )


def test_the_outcome_reason_adds_no_discrimination_over_class_and_flags():
    """Why the pinned verdict carries no `reason` leg.

    `classify_outcome` selects the reason from the class and the flag list and
    from nothing else: `withheld` here is always `withheld_adb`, `validated` is
    always `approved`, and every `review` reason is chosen by a named flag
    (`parser_ambiguous`, `parser_exception`, `integrity_check_exception`), by
    the flag list being non-empty (`integrity_flags`), or by it being empty
    (`quality_needs_review`). Pinning it would duplicate the flags leg.
    Asserted here so that a future reason which is NOT so determined shows up
    as a red test rather than as a silently unpinned field.
    """
    from telemetry.record import classify_outcome

    def reason_for(flags: list[str]) -> str:
        payload = {
            "metrics": {"average_daily_balance": 1.0},
            "quality": {"corporate_use": "approved"},
            "integrity": {"flags": flags},
        }
        return classify_outcome(payload)[1]

    seen: dict[tuple[str, ...], set[str]] = {}
    for verdict in corpus_gate.PINNED_OUTCOMES.values():
        if verdict.outcome != "review":
            continue
        seen.setdefault(verdict.flags, set()).add(reason_for(list(verdict.flags)))
    for flags, reasons in seen.items():
        assert len(reasons) == 1, f"{list(flags)} yields several reasons: {reasons}"


# --- the mutation proofs ------------------------------------------------------
#
# Each drives `check_outcome_classes` over ONE pinned document with a mutated
# expectation, so the proof costs one analysis rather than 109.

PROBE = "Misc/Texas Bank.pdf"


def _run(expectations: dict) -> corpus_gate.Check:
    result = corpus_gate.Result()
    corpus_gate.check_outcome_classes(
        result, corpus_gate.CORPUS, [PROBE], corpus_gate.DEFAULT_CACHE
    )
    return result.checks[0]


@pytest.fixture()
def expectations(monkeypatch):
    """A mutable in-memory copy of the expectation map. Nothing on disk moves."""
    copy = dict(corpus_gate.PINNED_OUTCOMES)
    monkeypatch.setattr(corpus_gate, "PINNED_OUTCOMES", copy)
    return copy


@pytest.mark.corpus
def test_the_verdict_check_is_green_on_the_committed_expectation(expectations):
    check = _run(expectations)
    assert check.ok, check.details
    assert check.details == []


@pytest.mark.corpus
def test_a_moved_outcome_class_turns_the_gate_red(expectations):
    """The b8013d5 regression, reproduced: review -> validated must be visible."""
    committed = expectations[PROBE]
    expectations[PROBE] = corpus_gate.PUBLISHED_OUTCOME
    check = _run(expectations)
    assert not check.ok
    assert any("outcome class moved validated -> review" in d for d in check.details), (
        check.details
    )
    # ...and restoring it is green again, so the RED is the mutation and not
    # some ambient failure.
    expectations[PROBE] = committed
    assert _run(expectations).ok


@pytest.mark.corpus
def test_a_lost_integrity_flag_turns_the_gate_red(expectations):
    """The BMO shape: same class, one fewer published flag."""
    committed = expectations[PROBE]
    expectations[PROBE] = committed._replace(
        flags=committed.flags + ("conflicting_statement_summaries",)
    )
    check = _run(expectations)
    assert not check.ok
    assert any(
        "no longer publishes pinned integrity flag 'conflicting_statement_summaries'" in d
        for d in check.details
    ), check.details


@pytest.mark.corpus
def test_a_gained_integrity_flag_turns_the_gate_red(expectations):
    """A newly accused pinned document is movement too, and in the direction
    that matters most: the platform must not start flagging what it published."""
    expectations[PROBE] = expectations[PROBE]._replace(flags=())
    check = _run(expectations)
    assert not check.ok
    assert any(
        "newly publishes integrity flag 'missing_declared_statement_page'" in d
        for d in check.details
    ), check.details


@pytest.mark.corpus
def test_a_moved_risk_level_turns_the_gate_red(expectations):
    """D1's counterexample: risk_level moves independently of class and flags.

    `possible_document_issue` keys on `continuity_breaks >= 3` while the
    `running_balance_breaks` flag keys on the same counter being non-zero, so a
    document can go 2 breaks -> 3 with class, reason and flags byte-identical
    while risk_level goes review -> high. It is served to users, and the
    approved Texas Bank ceremony moves it too, so it is pinned.
    """
    expectations[PROBE] = expectations[PROBE]._replace(risk_level="high")
    check = _run(expectations)
    assert not check.ok
    assert any("risk_level moved high -> review" in d for d in check.details), check.details


@pytest.mark.corpus
def test_a_moved_possible_document_issue_turns_the_gate_red(expectations):
    expectations[PROBE] = expectations[PROBE]._replace(possible_document_issue=True)
    check = _run(expectations)
    assert not check.ok
    assert any(
        "possible_document_issue moved True -> False" in d for d in check.details
    ), check.details


@pytest.mark.corpus
def test_a_changed_integrity_note_turns_the_gate_red(expectations):
    """The notes name the specific pages, so the five page_coverage documents
    share one (class, flags) state while publishing five different notes. The
    old triple could not tell them apart; this can."""
    expectations[PROBE] = expectations[PROBE]._replace(
        notes=("statement declares 4 bank page(s), but page label(s) 2 are absent "
               "from the supplied PDF",)
    )
    check = _run(expectations)
    assert not check.ok
    assert any("newly publishes integrity note" in d for d in check.details), check.details
    assert any(
        "no longer publishes pinned integrity note" in d for d in check.details
    ), check.details


@pytest.mark.corpus
def test_a_document_that_cannot_be_analysed_is_red_not_skipped(expectations, tmp_path):
    """Fail-closed: a verdict we cannot compute is never a pass."""
    result = corpus_gate.Result()
    corpus_gate.check_outcome_classes(
        result, tmp_path, [PROBE], corpus_gate.DEFAULT_CACHE
    )
    check = result.checks[0]
    assert not check.ok
    assert any("could not be analysed" in d for d in check.details), check.details
