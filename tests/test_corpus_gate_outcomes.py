"""The corpus gate's per-document verdict check (WIRING-1 card D).

`corpus_gate.check_outcomes` proves 105 PASS / 3 WITHHELD / 1 REFUSED out of the two
committed audit CSVs. Neither CSV carries a `flags`, `notes`, `risk_level` or
`possible_document_issue` column, so both oracles are structurally blind to
three kinds of truth-set movement, and all three are real:

* a pinned statement moving review<->validated, which lives entirely inside the
  audits' single PASS class (W3 §PIPEFIX P4b.5: two pinned documents made that
  move at `b8013d5` with the gate reporting GREEN over it);
* a pinned statement gaining or losing a PUBLISHED integrity flag without
  changing class — measured when the page-declaration check was activated, which
  withdrew `missing_declared_statement_page` from the pinned BMO January
  statement, withheld before and withheld after (the movement that stopped
  WIRING-1, since a class-only check would have seen nothing);
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
import sys
from pathlib import Path

import pytest

import corpus_gate

ROOT = Path(corpus_gate.__file__).resolve().parent


# --- the declaration that keeps the harness honest ---------------------------


#: `analyze_document` joined this set at L-1 stage 2, and the reason is the
#: gap rather than the tool that found it. It is the DOCUMENT entry point —
#: already a declared call site in `corpus_gate.ANALYSIS_CALL_SITES` — and the
#: seams reach it in the stage that teaches the payload readers the document
#: shape. A sweep watching only the account entry point would therefore go
#: blind to every production caller at exactly the moment they moved, which is
#: the drift this declaration exists to make loud. It costs nothing today:
#: `analysis/pipeline.py` is already swept through the `analyze_markdown` call
#: inside `analyze_document`, and the only other callers are two read-only
#: probes that were already excused.
#: `_analyse` joined it at L-1 stage 4, and for the same reason one layer down.
#: Both entry points now go through one internal analysis — the account seam
#: cannot be allowed to answer something different from the document seam about
#: the same document — so `_analyse` is what actually forwards `sheets` into
#: the pipeline, and a sweep that watched only its two callers would be blind to
#: the function whose signature the page-declaration check hangs off.
WATCHED = {"analyze_markdown", "analyze_document", "cached_analysis", "_analyse"}

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


# --- the two guards above, proven to bite (audit 2026-10-13, HYG-03) ---------
#
# Both guards read the tree through this module's `ROOT`, so each proof below
# copies every module the sweep finds into a scratch folder, points `ROOT` at
# it, plants ONE change in the copy and runs the guard itself. The working tree
# is never touched, and the guard that catches the mutant here is the very
# function that guards the repository.


def _without_sheets(source: str, function: str) -> str:
    """`source` with every `sheets=` dropped from the analysis calls inside
    `function`."""
    tree = ast.parse(source)
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function
    )
    dropped = 0
    for node in ast.walk(target):
        if isinstance(node, ast.Call) and _called_name(node) in WATCHED:
            kept = [keyword for keyword in node.keywords if keyword.arg != "sheets"]
            dropped += len(node.keywords) - len(kept)
            node.keywords = kept
    assert dropped, f"{function} passes no sheets to drop"
    return ast.unparse(tree)


def _with_sheets_splatted(source: str) -> str:
    """`source` with every analysis call's `sheets=x` rewritten as
    `**{"sheets": x}`: the same call, unreadable to a static reader."""
    tree = ast.parse(source)
    rewritten = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node) in WATCHED:
            for index, keyword in enumerate(node.keywords):
                if keyword.arg == "sheets":
                    node.keywords[index] = ast.keyword(
                        arg=None, value=ast.Dict(keys=[ast.Constant("sheets")], values=[keyword.value])
                    )
                    rewritten += 1
    assert rewritten, "no analysis call passes sheets to splat"
    return ast.unparse(tree)


@pytest.fixture
def scratch_callers(tmp_path, monkeypatch):
    """A scratch tree holding a copy of every module the sweep finds in the
    repository, with this module's `ROOT` pointed at it for one test."""
    for relative in _callers():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    return tmp_path


def test_the_unmutated_scratch_copy_passes_both_guards(scratch_callers):
    """The control: every mutant below differs from this copy by one change."""
    test_every_production_caller_of_the_analysis_is_classified()
    test_the_gate_harness_analyses_the_way_production_does()


def test_a_new_unclassified_caller_turns_the_sweep_red(scratch_callers):
    planted = scratch_callers / "webapp" / "contoso_new_caller.py"
    planted.write_text(
        "from analysis.pipeline import analyze_document\n\n\n"
        "def publish(markdown):\n"
        '    return analyze_document(markdown, parse_mode="deterministic")\n',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="contoso_new_caller"):
        test_every_production_caller_of_the_analysis_is_classified()


@pytest.mark.parametrize("relative, function", [
    ("webapp/worker.py", "_analyze_doc"),
])
def test_a_declared_caller_that_drops_sheets_turns_the_harness_red(scratch_callers, relative, function):
    """Why a production caller is DECLARED rather than excused: only a declared
    site is held to the page partition. Were the web app worker's own analysis
    excused, this mutant would stay green. (The mutant ran on the two
    visual-pair callers until they were removed with the pair in slice S4 of
    the model-code removal; the worker is the declared site the dashboard's
    every job goes through.)"""
    path = scratch_callers / relative
    path.write_text(_without_sheets(path.read_text(encoding="utf-8"), function), encoding="utf-8")
    with pytest.raises(AssertionError, match="PRODUCTION_SUPPLIES_SHEETS"):
        test_the_gate_harness_analyses_the_way_production_does()


@pytest.mark.parametrize("relative", ["tools/revenue_census.py"])
def test_an_excused_research_tool_that_splats_its_arguments_turns_the_harness_red(scratch_callers, relative):
    path = scratch_callers / relative
    path.write_text(_with_sheets_splatted(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(AssertionError, match="splats"):
        test_the_gate_harness_analyses_the_way_production_does()


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
    """102 validated / 3 review / 3 withheld / 1 refused, derived rather than
    restated.

    100/6/3 until WIRING-2 executed the approved ceremony: Texas Bank and
    Regions moved review -> validated on withdrawn FALSE
    `missing_declared_statement_page` flags. 102/4/3 until W3 §REPAIRDOC, whose
    approved ceremony took the Columbia statement out of the published set
    altogether: with the two amount-rewriting repairs gone it publishes
    nothing, so it carries a `PINNED_REFUSALS` entry instead of a verdict. The
    audits' PASS class moved with it, 106 -> 105, which is the one movement of
    this ceremony the two oracles CAN see.
    """
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    counts: dict[str, int] = {}
    for rel in manifest:
        if rel in corpus_gate.PINNED_REFUSALS:
            counts["refused"] = counts.get("refused", 0) + 1
            continue
        verdict = corpus_gate.PINNED_OUTCOMES.get(rel, corpus_gate.PUBLISHED_OUTCOME)
        counts[verdict.outcome] = counts.get(verdict.outcome, 0) + 1
    assert counts == {"validated": 102, "review": 3, "withheld": 3, "refused": 1}
    assert counts["validated"] + counts["review"] == corpus_gate.EXPECTED_PASS
    assert counts["withheld"] == corpus_gate.EXPECTED_WITHHELD
    assert counts["refused"] == corpus_gate.EXPECTED_REFUSED
    assert sum(counts.values()) == corpus_gate.EXPECTED_PDF_COUNT


def test_a_pinned_refusal_is_pinned_exactly_once_and_nowhere_else():
    """W3 §REPAIRDOC. A refusal is a fact about a document that publishes
    NOTHING, so every map that describes a published document must not name it:
    a verdict, a currency, or an audit PASS row for a refusal would each be an
    assertion about output that does not exist.
    """
    manifest = set(corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV)))
    assert set(corpus_gate.PINNED_REFUSALS) <= manifest
    assert len(corpus_gate.PINNED_REFUSALS) == corpus_gate.EXPECTED_REFUSED
    for rel, reason in corpus_gate.PINNED_REFUSALS.items():
        assert rel not in corpus_gate.PINNED_OUTCOMES, rel
        assert rel not in corpus_gate.PINNED_CURRENCY, rel
        assert reason and reason == reason.strip(), rel

    # Both audit CSVs carry the document with the REFUSED status and no audited
    # figure — the row stays so the refusal keeps an audit trail.
    balance = {row["path"]: row for row in corpus_gate.read_csv(corpus_gate.BALANCE_CSV)}
    for rel, reason in corpus_gate.PINNED_REFUSALS.items():
        row = balance[rel]
        assert row["status"] == corpus_gate.REFUSED_STATUS
        assert row["root_cause"] == reason
        for column in ("production_opening", "production_ending",
                       "production_highest", "production_lowest", "transactions"):
            assert row[column] == "", (rel, column)


def test_the_ceremony_documents_publish_no_integrity_flag():
    """The three approved movements, pinned as expectations rather than prose.

    Texas Bank and Regions are `PUBLISHED_OUTCOME` — no flag, no note, risk
    clear — and the BMO January statement is still withheld while no longer
    accusing itself of a missing page. Anything else on these three is
    unapproved truth-set movement.
    """
    for rel in ("Misc/Texas Bank.pdf", "Regions/Regions.pdf"):
        assert rel not in corpus_gate.PINNED_OUTCOMES, (
            f"{rel} moved to validated in the approved ceremony, so it must "
            f"publish PUBLISHED_OUTCOME rather than carry an entry"
        )
    bmo = corpus_gate.PINNED_OUTCOMES["Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf"]
    assert bmo.outcome == "withheld"
    assert "missing_declared_statement_page" not in bmo.flags
    assert not any("are absent from the supplied PDF" in note for note in bmo.notes)
    assert len(bmo.flags) == 6 and len(bmo.notes) == 7
    assert bmo.risk_level == "high" and bmo.possible_document_issue is True

    # ...and the remaining flag-carriers keep theirs: the fix is not blunt.
    # `Misc/Columbia May 26 complete.pdf` was a third until W3 §REPAIRDOC; it
    # publishes nothing now, so it carries a refusal rather than a flag.
    for rel in (
        "Misc/Builder June 2026.pdf",
        "Misc/Link Bank April statement.pdf",
    ):
        assert corpus_gate.PINNED_OUTCOMES[rel].flags == (
            "missing_declared_statement_page",
        ), rel
    assert "Misc/Columbia May 26 complete.pdf" in corpus_gate.PINNED_REFUSALS


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
#
# The probe has to be a document that still publishes a non-empty integrity
# block, or the "lost flag" and "changed note" mutations would have nothing to
# mutate. It was Texas Bank until WIRING-2's approved ceremony moved that one to
# `validated` with no flags at all. Builder June 2026 has the identical shape
# Texas Bank had — review, one `missing_declared_statement_page`, one note
# naming the pages — and keeps it honestly: it supplies 4 sheets for the 5 pages
# it declares, so a page really is unaccounted for. It also resolves through a
# committed OCR artifact, so these proofs exercise the page-list read as well.

PROBE = "Misc/Builder June 2026.pdf"


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
    approved Texas Bank ceremony moved it review -> clear, so it is pinned.
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
        notes=("statement declares 5 bank page(s), but page label(s) 2 are absent "
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


# ---------------------------------------------------------------------------
# The pinned CURRENCY surface (RBC-CAD card, Gustavo 2026-08-16).
#
# Currency was the fourth thing the gate could not see: it is in neither audit
# CSV, in no expectation file, and `corpus_gate.py` did not mention it — while
# `webapp/static/app.js` threads `statement.currency` into `Intl.NumberFormat`,
# so it decides whether every figure an analyst reads is `$` or `CA$`. The RBC
# ceremony moved 151 published currencies, four of them pinned, with every
# financial field byte-identical; that movement was gate-invisible and this
# surface is what makes the next one RED.
#
# `check_currency` consumes payloads rather than documents, so its mutation
# proofs need no corpus and stay in the default suite. One corpus-marked test
# below closes the loop against the real product on the ceremony document.
# ---------------------------------------------------------------------------

#: The four documents the approved ceremony moves, and nothing else.
CEREMONY_CAD = {
    "RBC/Chequing Statement-DEC+.pdf",
    "RBC/Chequing Statement-JAN+.pdf",
    "RBC/Chequing Statement-FEB+.pdf",
    "RBC/Chequing Statement-MAR+.pdf",
}

#: The ten documents that already published CAD before this card, each from its
#: own parser's explicit assignment — measured on the base tree, not assumed.
PRE_EXISTING_CAD = {
    "CIBC French/Account Statement 1.pdf",
    "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf",
    "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf",
    "ScotiaBank/Scotiabank -2.pdf",
    "TD Can/Dec_31-Jan_30_2026 (6).pdf",
    "TD Can/Feb_27-Mar_31_2026 (2).pdf",
    "TD Can/Jan_30-Feb_27_2026 (3).pdf",
    "TD Can/Mar_31-Apr_30_2026.pdf",
    "TD Can/Nov_28-Dec_31_2025 (7).pdf",
    "TD Can/TD Bank Bank Statement.pdf",
}


def _manifest() -> list[str]:
    return corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))


def test_the_currency_surface_is_total_over_the_denominated_manifest():
    """Every pinned document that PUBLISHES states a currency, and no entry
    names anything else. Totality is the difference between a surface and a
    spot check: an exception map would let a new corpus document arrive with no
    currency stated at all.

    The subtraction is the pinned refusals (W3 §REPAIRDOC): a document that
    publishes no statement publishes no denomination, so a pin for one would
    assert a fact the product never states. It is enforced in both directions
    here and in `check_currency`, so the omission cannot silently widen."""
    manifest = set(_manifest())
    denominated = manifest - set(corpus_gate.PINNED_REFUSALS)
    pinned = set(corpus_gate.PINNED_CURRENCY)
    assert pinned == denominated, {
        "unstated": sorted(denominated - pinned),
        "unknown": sorted(pinned - denominated),
    }
    assert len(corpus_gate.PINNED_CURRENCY) == (
        corpus_gate.EXPECTED_PDF_COUNT - corpus_gate.EXPECTED_REFUSED
    )
    for rel, code in corpus_gate.PINNED_CURRENCY.items():
        assert len(code) == 3 and code.isupper() and code.isalpha(), (rel, code)


def test_the_pinned_currency_split_is_the_measured_one():
    """94 USD / 14 CAD, derived from the map rather than restated — and the 14
    CAD are exactly the ten that already published CAD plus the four the RBC
    ceremony moved. A fifteenth CAD would be unapproved truth-set movement.

    95 USD until W3 §REPAIRDOC withdrew the Columbia pin: that document is a
    refusal now, so its USD is not a published denomination any more. The CAD
    side is untouched, which is what says the two ceremonies do not overlap."""
    cad = {rel for rel, code in corpus_gate.PINNED_CURRENCY.items() if code == "CAD"}
    usd = {rel for rel, code in corpus_gate.PINNED_CURRENCY.items() if code == "USD"}
    assert cad == PRE_EXISTING_CAD | CEREMONY_CAD
    assert len(cad) == 14 and len(usd) == 94
    assert len(cad) + len(usd) == (
        corpus_gate.EXPECTED_PDF_COUNT - corpus_gate.EXPECTED_REFUSED
    )


def test_the_pinned_french_rbc_statement_is_not_part_of_the_ceremony():
    """It published CAD from the French reader before this card and is
    byte-identical after it, so it is a pre-existing value and not a mover."""
    french = "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf"
    assert french in PRE_EXISTING_CAD
    assert french not in CEREMONY_CAD
    assert corpus_gate.PINNED_CURRENCY[french] == "CAD"


def _payloads(currencies: dict[str, str]) -> dict[str, dict]:
    return {rel: {"statement": {"currency": code}} for rel, code in currencies.items()}


def _run_currency(manifest, payloads) -> corpus_gate.Check:
    result = corpus_gate.Result()
    corpus_gate.check_currency(result, manifest, payloads)
    return result.checks[0]


def test_the_currency_check_is_green_when_the_product_agrees_with_the_pins():
    manifest = _manifest()
    check = _run_currency(manifest, _payloads(dict(corpus_gate.PINNED_CURRENCY)))
    assert check.ok, check.details
    assert "108/108" in check.summary
    assert "1 pinned refusal(s)" in check.summary


def test_a_moved_currency_turns_the_gate_red():
    """The mutation the whole surface exists for: one document's denomination
    moves and every financial field stays byte-identical."""
    manifest = _manifest()
    published = dict(corpus_gate.PINNED_CURRENCY)
    published["RBC/Chequing Statement-DEC+.pdf"] = "USD"
    check = _run_currency(manifest, _payloads(published))
    assert not check.ok
    assert any(
        "publishes currency 'USD', pinned 'CAD'" in detail for detail in check.details
    ), check.details

    # ...and both directions: a USD document silently becoming CAD is the same
    # class of movement and equally red.
    published = dict(corpus_gate.PINNED_CURRENCY)
    published["ATB/ATB August 2023.pdf"] = "CAD"
    check = _run_currency(manifest, _payloads(published))
    assert not check.ok
    assert any(
        "publishes currency 'CAD', pinned 'USD'" in detail for detail in check.details
    ), check.details


def test_an_unstated_or_unknown_pin_turns_the_gate_red(monkeypatch):
    """A pinned document with no currency recorded, and a recorded currency for
    a document that is not pinned, are both failures — otherwise the map could
    silently stop covering the corpus."""
    manifest = _manifest()
    thinned = dict(corpus_gate.PINNED_CURRENCY)
    dropped = thinned.pop("Chase/Chase Apr.pdf")
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY", thinned)
    check = _run_currency(manifest, _payloads(dict(corpus_gate.PINNED_CURRENCY)))
    assert not check.ok
    assert any("no expected currency is recorded" in d for d in check.details), check.details

    widened = dict(thinned)
    widened["Chase/Chase Apr.pdf"] = dropped
    widened["Nowhere/not-a-corpus-document.pdf"] = "USD"
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY", widened)
    check = _run_currency(manifest, _payloads(dict(corpus_gate.PINNED_CURRENCY)))
    assert not check.ok
    assert any(
        "not a denominated pinned document" in d for d in check.details
    ), check.details

    # ...and a currency pinned for a document that publishes NOTHING is the
    # same failure: it is in the manifest, and it still has no denomination.
    refusal = next(iter(corpus_gate.PINNED_REFUSALS))
    widened = dict(corpus_gate.PINNED_CURRENCY)
    widened[refusal] = "USD"
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY", widened)
    check = _run_currency(manifest, _payloads(dict(corpus_gate.PINNED_CURRENCY)))
    assert not check.ok
    assert any(
        refusal in d and "not a denominated pinned document" in d for d in check.details
    ), check.details


def test_a_document_with_no_payload_is_red_not_skipped():
    """Fail-closed, the same rule the verdict check follows: a currency we
    could not read is never a pass."""
    manifest = _manifest()
    payloads = _payloads(dict(corpus_gate.PINNED_CURRENCY))
    payloads.pop("Misc/Texas Bank.pdf")
    check = _run_currency(manifest, payloads)
    assert not check.ok
    assert any("its currency is unverified" in d for d in check.details), check.details


@pytest.mark.corpus
def test_the_ceremony_document_publishes_cad_end_to_end(monkeypatch):
    """The loop closed against the real product: the DEC statement
    (A26ECE4F32488CECDD59EA5BCF13B4947786456038CBDD17AC52C0F3D9F38EE5) resolves
    through the production intake ladder and publishes CAD, while its verdict
    stays `PUBLISHED_OUTCOME` — currency moved, nothing else did.

    `check_currency` is TOTAL over the manifest it is given, so driving it with
    a one-document manifest requires a one-document map: with the committed 109
    in place it would (correctly) report the other 108 pins as naming paths
    outside that manifest. The full 109-vs-109 comparison is
    `python corpus_gate.py`, not this proof.
    """
    rel = "RBC/Chequing Statement-DEC+.pdf"
    verdict, payload = corpus_gate.production_verdict(
        corpus_gate.CORPUS / Path(rel), corpus_gate.DEFAULT_CACHE
    )
    assert payload["statement"]["currency"] == "CAD"
    assert payload["statement"]["bank"] == "Royal Bank of Canada"
    assert verdict == corpus_gate.PUBLISHED_OUTCOME
    assert corpus_gate.PINNED_CURRENCY[rel] == "CAD"

    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY", {rel: "CAD"})
    assert _run_currency([rel], {rel: payload}).ok

    # ...and the same document against the pre-ceremony value is RED, so the
    # green above is the product agreeing rather than the check being inert.
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY", {rel: "USD"})
    check = _run_currency([rel], {rel: payload})
    assert not check.ok
    assert any("publishes currency 'CAD', pinned 'USD'" in d for d in check.details)


# ---------------------------------------------------------------------------
# The pinned currency PROVENANCE surface (§CURRSRC)
#
# `check_currency` above is blind to the failure this one exists for: a reader
# that stops reading the code its document prints and falls back to an
# institution constant publishes the identical three letters. Every audit CSV,
# every verdict and the currency surface itself stay green; the platform's
# knowledge of the document got worse and nothing said so. These are the
# mutation proofs for the second map, in the same shape as the first — payloads
# rather than documents, so they need no corpus and stay in the default suite.
# ---------------------------------------------------------------------------

#: The 19 pinned documents whose currency a parser read or defaulted rather
#: than leaving it on the schema default, grouped by the class that produced
#: it. Measured on this branch before the map was pinned, and written out here
#: so the split is reviewable as names rather than as a count.
PINNED_PRINTED = {"Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf"}
PINNED_PRODUCT = {
    "Misc/USD FEB 2026.pdf",
    "TD Can/Dec_31-Jan_30_2026 (6).pdf",
    "TD Can/Feb_27-Mar_31_2026 (2).pdf",
    "TD Can/Jan_30-Feb_27_2026 (3).pdf",
    "TD Can/Mar_31-Apr_30_2026.pdf",
    "TD Can/Nov_28-Dec_31_2025 (7).pdf",
    "TD Can/TD Bank Bank Statement.pdf",
}
PINNED_INSTITUTION = {
    "CIBC French/Account Statement 1.pdf",
    "Chase/Chase Business.pdf",
    "Misc/Ace_Auto_Final_Cut.pdf",
    "Misc/Builder June 2026.pdf",
    "Misc/KLR.May 31,2026 (1).pdf",
    "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf",
    "ScotiaBank/Scotiabank -2.pdf",
}


def _source_payloads(sources: dict[str, str]) -> dict[str, dict]:
    return {
        rel: {"statement": {"currency_source": source}}
        for rel, source in sources.items()
    }


def _run_currency_source(manifest, payloads) -> corpus_gate.Check:
    result = corpus_gate.Result()
    corpus_gate.check_currency_source(result, manifest, payloads)
    return result.checks[0]


def test_the_currency_source_surface_is_total_over_the_denominated_manifest():
    """Total over the manifest MINUS the pinned refusals, both ways - the same
    shape as the currency surface: a refused document publishes no statement
    and so has no provenance to pin (composed at the batch-7 train)."""
    manifest = set(_manifest())
    denominated = manifest - set(corpus_gate.PINNED_REFUSALS)
    pinned = set(corpus_gate.PINNED_CURRENCY_SOURCE)
    assert pinned == denominated, {
        "unstated": sorted(denominated - pinned),
        "unknown": sorted(pinned - denominated),
    }
    assert len(corpus_gate.PINNED_CURRENCY_SOURCE) == (
        corpus_gate.EXPECTED_PDF_COUNT - corpus_gate.EXPECTED_REFUSED
    )
    assert set(corpus_gate.PINNED_CURRENCY_SOURCE.values()) <= set(
        corpus_gate.CURRENCY_SOURCES
    )


def test_the_pinned_provenance_split_is_the_measured_one():
    """90 schema_default / 7 institution_default / 7 product / 4
    jurisdiction_default / 1 printed, derived from the map rather than restated
    — and it reconciles to batch 6's own census of the same 109: 10 pre-existing
    parser CAD (1 printed + 6 product + 3 institution) plus the 4 ceremony
    documents, and 5 parser USD (1 Desjardins product + 4 institution)."""
    pinned = corpus_gate.PINNED_CURRENCY_SOURCE
    by_class = {
        name: {rel for rel, source in pinned.items() if source == name}
        for name in corpus_gate.CURRENCY_SOURCES
    }
    assert by_class["printed"] == PINNED_PRINTED
    assert by_class["product"] == PINNED_PRODUCT
    assert by_class["institution_default"] == PINNED_INSTITUTION
    assert by_class["jurisdiction_default"] == CEREMONY_CAD
    assert by_class["model_extracted"] == set()
    # 90 at batch 6; 89 since the batch-7 REPAIR-DOCTRINE ceremony pinned the
    # Columbia document as a REFUSAL (it publishes no statement, so no source).
    assert len(by_class["schema_default"]) == 90 - corpus_gate.EXPECTED_REFUSED
    assert sum(len(names) for names in by_class.values()) == (
        corpus_gate.EXPECTED_PDF_COUNT - corpus_gate.EXPECTED_REFUSED
    )

    # The provenance of every CAD, cross-checked against the currency map: the
    # two surfaces must describe the same documents or one of them is stale.
    usd_by_evidence = {
        "Misc/USD FEB 2026.pdf",
        "Chase/Chase Business.pdf",
        "Misc/Ace_Auto_Final_Cut.pdf",
        "Misc/Builder June 2026.pdf",
        "Misc/KLR.May 31,2026 (1).pdf",
    }
    cad = {rel for rel, code in corpus_gate.PINNED_CURRENCY.items() if code == "CAD"}
    assert cad == (
        PINNED_PRINTED | PINNED_PRODUCT | PINNED_INSTITUTION | CEREMONY_CAD
    ) - usd_by_evidence
    assert cad == PRE_EXISTING_CAD | CEREMONY_CAD

    # ...and the five ATB documents are schema_default, which is the whole
    # reason the class is published: they are a Canadian provincial bank's
    # statements wearing a field default, named as future movers in batch 6.
    assert {rel for rel in pinned if rel.startswith("ATB/")} <= by_class["schema_default"]


def test_the_currency_source_check_is_green_when_the_product_agrees():
    manifest = _manifest()
    check = _run_currency_source(
        manifest, _source_payloads(dict(corpus_gate.PINNED_CURRENCY_SOURCE))
    )
    assert check.ok, check.details
    assert "108/108" in check.summary
    assert "+1 pinned refusal(s)" in check.summary


def test_a_provenance_pinned_for_a_refusal_turns_the_gate_red(monkeypatch):
    """The mirror of the currency surface's rule: a pinned refusal publishes no
    statement, so pinning a provenance for it asserts something the product
    never states - and the composed surface must say so rather than report the
    document as 'no payload was produced'."""
    manifest = _manifest()
    refusal = next(iter(corpus_gate.PINNED_REFUSALS))
    widened = dict(corpus_gate.PINNED_CURRENCY_SOURCE)
    widened[refusal] = "schema_default"
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY_SOURCE", widened)
    check = _run_currency_source(
        manifest, _source_payloads(dict(corpus_gate.PINNED_CURRENCY_SOURCE))
    )
    assert not check.ok
    assert any(
        refusal in d and "not a denominated pinned document" in d for d in check.details
    ), check.details


def test_a_read_that_degrades_to_a_default_turns_the_gate_red():
    """THE mutation this surface exists for, and the one `check_currency` cannot
    see: BMO stops reading its own printed `Currency:` line and falls back to the
    institution constant. The published code is `CAD` either way."""
    manifest = _manifest()
    published = dict(corpus_gate.PINNED_CURRENCY_SOURCE)
    published["Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf"] = (
        "institution_default"
    )
    check = _run_currency_source(manifest, _source_payloads(published))
    assert not check.ok
    assert any(
        "publishes currency source 'institution_default', pinned 'printed'" in detail
        for detail in check.details
    ), check.details

    # ...and the other direction: a reader newly CLAIMING to have read evidence
    # it did not earn is equally red. A promotion is a ceremony too.
    published = dict(corpus_gate.PINNED_CURRENCY_SOURCE)
    published["ATB/ATB August 2023.pdf"] = "jurisdiction_default"
    check = _run_currency_source(manifest, _source_payloads(published))
    assert not check.ok
    assert any(
        "publishes currency source 'jurisdiction_default', pinned 'schema_default'"
        in detail
        for detail in check.details
    ), check.details


def test_an_unstated_or_unknown_provenance_pin_turns_the_gate_red(monkeypatch):
    manifest = _manifest()
    thinned = dict(corpus_gate.PINNED_CURRENCY_SOURCE)
    dropped = thinned.pop("Chase/Chase Apr.pdf")
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY_SOURCE", thinned)
    check = _run_currency_source(manifest, _source_payloads(dict(thinned)))
    assert not check.ok
    assert any("no expected currency source is recorded" in d for d in check.details)

    widened = dict(thinned)
    widened["Chase/Chase Apr.pdf"] = dropped
    widened["Nowhere/not-a-corpus-document.pdf"] = "schema_default"
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY_SOURCE", widened)
    check = _run_currency_source(manifest, _source_payloads(dict(widened)))
    assert not check.ok
    assert any(
        "not a denominated pinned document" in d for d in check.details
    ), check.details


def test_a_provenance_outside_the_vocabulary_turns_the_gate_red(monkeypatch):
    """Free text would pass every other assertion in this file while meaning
    nothing, so the gate holds its own copy of the closed set."""
    manifest = _manifest()
    invented = dict(corpus_gate.PINNED_CURRENCY_SOURCE)
    invented["Chase/Chase Apr.pdf"] = "because_chase"
    monkeypatch.setattr(corpus_gate, "PINNED_CURRENCY_SOURCE", invented)
    check = _run_currency_source(manifest, _source_payloads(dict(invented)))
    assert not check.ok
    assert any("not in the published vocabulary" in d for d in check.details)


def test_a_document_with_no_payload_is_red_not_skipped_for_provenance():
    manifest = _manifest()
    payloads = _source_payloads(dict(corpus_gate.PINNED_CURRENCY_SOURCE))
    payloads.pop("Misc/Texas Bank.pdf")
    check = _run_currency_source(manifest, payloads)
    assert not check.ok
    assert any("its currency source is unverified" in d for d in check.details)


@pytest.mark.corpus
def test_the_ceremony_documents_publish_their_provenance_end_to_end(monkeypatch):
    """The loop closed against the real product on the one class whose whole
    correctness is the doctrine: the four ceremony statements publish CAD from
    `jurisdiction_default` and not from an institution constant, and the pinned
    French RBC statement — a CAD the reader ASSERTS — publishes
    `institution_default` beside it."""
    for rel in sorted(CEREMONY_CAD):
        _verdict, payload = corpus_gate.production_verdict(
            corpus_gate.CORPUS / Path(rel), corpus_gate.DEFAULT_CACHE
        )
        assert payload["statement"]["currency"] == "CAD"
        assert payload["statement"]["currency_source"] == "jurisdiction_default"
        assert corpus_gate.PINNED_CURRENCY_SOURCE[rel] == "jurisdiction_default"

    french = "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf"
    _verdict, payload = corpus_gate.production_verdict(
        corpus_gate.CORPUS / Path(french), corpus_gate.DEFAULT_CACHE
    )
    assert payload["statement"]["currency"] == "CAD"
    assert payload["statement"]["currency_source"] == "institution_default"

    # ...and the check really is comparing: the same payload against the
    # promoted class is RED.
    monkeypatch.setattr(
        corpus_gate, "PINNED_CURRENCY_SOURCE", {french: "jurisdiction_default"}
    )
    check = _run_currency_source([french], {french: payload})
    assert not check.ok
    assert any(
        "publishes currency source 'institution_default', pinned "
        "'jurisdiction_default'" in d
        for d in check.details
    )
