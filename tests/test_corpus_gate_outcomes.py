"""The corpus gate's per-document verdict check (WIRING-1 card D).

`corpus_gate.check_outcomes` proves 106 PASS / 3 WITHHELD out of the two
committed audit CSVs. Neither CSV carries a `flags`, `notes` or `risk_level`
column, so both oracles are structurally blind to two kinds of truth-set
movement, and both have actually happened:

* a pinned statement moving review<->validated, which lives entirely inside the
  audits' single PASS class (W3 §PIPEFIX P4b.5: two pinned documents made that
  move at `b8013d5` with the gate reporting GREEN over it);
* a pinned statement gaining or losing a PUBLISHED integrity flag without
  changing class — measured on this branch, where wiring the page-declaration
  check withdraws `missing_declared_statement_page` from the pinned BMO January
  statement, which is withheld before and withheld after.

`check_outcome_classes` closes both. These tests prove it closes them, by
mutation rather than by assertion: the gate must go RED for a moved class, for
a lost flag and for a gained flag, and GREEN again when the expectation is
restored. The mutations are applied to an in-memory copy of the expectation
map — nothing on disk is touched.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import corpus_gate

ROOT = Path(corpus_gate.__file__).resolve().parent


# --- the declaration that keeps the harness honest ---------------------------


def _call_sites_supplying_sheets() -> dict[str, bool]:
    """Does each production analysis call site pass `sheets=`?

    Read out of the source with `ast` rather than by importing and inspecting:
    the question is about the call as written, and a keyword argument is a
    syntactic fact. Any `analyze_markdown(...)` or `cached_analysis(...)` call
    inside the named function counts.
    """
    watched = {"analyze_markdown", "cached_analysis"}
    found: dict[str, bool] = {}
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
        supplies = False
        for node in ast.walk(target):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in watched and any(kw.arg == "sheets" for kw in node.keywords):
                supplies = True
        found[f"{relative}::{function}"] = supplies
    return found


def test_the_gate_harness_analyses_the_way_production_does():
    """`PRODUCTION_SUPPLIES_SHEETS` is not a preference; it is a measurement.

    The gate's verdict check must call `analyze_markdown` the way the product
    calls it. If production starts handing over the intake page list and this
    harness does not, the gate keeps reproducing the OLD verdict and goes
    silently blind on exactly the fraud-relevant flag it was added to watch —
    so the drift is a red test here rather than a quiet pass there.
    """
    sites = _call_sites_supplying_sheets()
    assert sites, "no production analysis call sites were inspected"
    assert set(sites.values()) == {corpus_gate.PRODUCTION_SUPPLIES_SHEETS}, (
        f"corpus_gate.PRODUCTION_SUPPLIES_SHEETS is "
        f"{corpus_gate.PRODUCTION_SUPPLIES_SHEETS} but the call sites say {sites}. "
        f"Wiring production means wiring this harness in the same commit — and "
        f"that moves pinned verdicts, which is a truth-set ceremony."
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
        for rel, (outcome, _reason, _flags) in corpus_gate.PINNED_OUTCOMES.items()
        if outcome == "withheld"
    }
    assert withheld == corpus_gate.WITHHELD_STATEMENTS


def test_the_expected_split_is_the_documented_one():
    """100 validated / 6 review / 3 withheld, derived rather than restated."""
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    counts: dict[str, int] = {}
    for rel in manifest:
        outcome = corpus_gate.PINNED_OUTCOMES.get(rel, corpus_gate.PUBLISHED_OUTCOME)[0]
        counts[outcome] = counts.get(outcome, 0) + 1
    assert counts == {"validated": 100, "review": 6, "withheld": 3}
    assert counts["validated"] + counts["review"] == corpus_gate.EXPECTED_PASS
    assert counts["withheld"] == corpus_gate.EXPECTED_WITHHELD


def test_a_validated_document_is_one_with_no_integrity_flags():
    """The universal rule the map relies on to stay total over 109 without
    listing 109: `classify_outcome` only returns validated when the flag list
    is empty, so "absent from the map" is a real expectation and not a gap."""
    assert corpus_gate.PUBLISHED_OUTCOME == ("validated", "approved", ())
    for rel, (outcome, _reason, flags) in corpus_gate.PINNED_OUTCOMES.items():
        assert outcome != "validated", (
            f"{rel}: a validated document belongs outside the map, not in it"
        )
        assert flags or outcome == "validated", f"{rel}: non-validated with no evidence"


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
    expectations[PROBE] = ("validated", "approved", ())
    check = _run(expectations)
    assert not check.ok
    assert any("outcome class moved validated -> review" in d for d in check.details), (
        check.details
    )
    # ...and restoring it is green again, so the RED is the mutation and not
    # some ambient failure.
    expectations[PROBE] = ("review", "integrity_flags", ("missing_declared_statement_page",))
    assert _run(expectations).ok


@pytest.mark.corpus
def test_a_lost_integrity_flag_turns_the_gate_red(expectations):
    """The BMO shape: same class, one fewer published flag."""
    outcome, reason, flags = expectations[PROBE]
    expectations[PROBE] = (outcome, reason, flags + ("conflicting_statement_summaries",))
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
    outcome, reason, _flags = expectations[PROBE]
    expectations[PROBE] = (outcome, reason, ())
    check = _run(expectations)
    assert not check.ok
    assert any(
        "newly publishes integrity flag 'missing_declared_statement_page'" in d
        for d in check.details
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
