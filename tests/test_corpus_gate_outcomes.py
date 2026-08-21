"""The corpus gate's per-document verdict check (WIRING-1 card D).

`corpus_gate.check_outcomes` proves 106 PASS / 3 WITHHELD out of the two
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
    """102 validated / 4 review / 3 withheld, derived rather than restated.

    100/6/3 until WIRING-2 executed the approved ceremony: Texas Bank and
    Regions moved review -> validated on withdrawn FALSE
    `missing_declared_statement_page` flags. The audits' PASS class is
    unchanged at 106, which is exactly why this split has to be pinned
    separately — the two oracles cannot see the movement.
    """
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    counts: dict[str, int] = {}
    for rel in manifest:
        verdict = corpus_gate.PINNED_OUTCOMES.get(rel, corpus_gate.PUBLISHED_OUTCOME)
        counts[verdict.outcome] = counts.get(verdict.outcome, 0) + 1
    assert counts == {"validated": 102, "review": 4, "withheld": 3}
    assert counts["validated"] + counts["review"] == corpus_gate.EXPECTED_PASS
    assert counts["withheld"] == corpus_gate.EXPECTED_WITHHELD


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

    # ...and the other three flag-carriers keep theirs: the fix is not blunt.
    for rel in (
        "Misc/Builder June 2026.pdf",
        "Misc/Columbia May 26 complete.pdf",
        "Misc/Link Bank April statement.pdf",
    ):
        assert corpus_gate.PINNED_OUTCOMES[rel].flags == (
            "missing_declared_statement_page",
        ), rel


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


def test_the_currency_surface_is_total_over_the_pinned_manifest():
    """Every pinned document states a currency, and no entry names a document
    that is not pinned. Totality is the difference between a surface and a spot
    check: an exception map would let a new corpus document arrive with no
    currency stated at all."""
    manifest = set(_manifest())
    pinned = set(corpus_gate.PINNED_CURRENCY)
    assert pinned == manifest, {
        "unstated": sorted(manifest - pinned),
        "unknown": sorted(pinned - manifest),
    }
    assert len(corpus_gate.PINNED_CURRENCY) == corpus_gate.EXPECTED_PDF_COUNT
    for rel, code in corpus_gate.PINNED_CURRENCY.items():
        assert len(code) == 3 and code.isupper() and code.isalpha(), (rel, code)


def test_the_pinned_currency_split_is_the_measured_one():
    """95 USD / 14 CAD, derived from the map rather than restated — and the 14
    CAD are exactly the ten that already published CAD plus the four the
    ceremony moves. A fifteenth CAD would be unapproved truth-set movement."""
    cad = {rel for rel, code in corpus_gate.PINNED_CURRENCY.items() if code == "CAD"}
    usd = {rel for rel, code in corpus_gate.PINNED_CURRENCY.items() if code == "USD"}
    assert cad == PRE_EXISTING_CAD | CEREMONY_CAD
    assert len(cad) == 14 and len(usd) == 95
    assert len(cad) + len(usd) == corpus_gate.EXPECTED_PDF_COUNT


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
    assert "109/109" in check.summary


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
    assert any("not in the manifest" in d for d in check.details), check.details


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
