"""P20-ROUTER: `ocr.escalation` unit proof, the CASE 1-4 behavioural proof,
and the corpus-measured pin that the extraction-quality gate never calls a
validated Tesseract read unusable.

Nothing here reaches a server. Cases 1-4 are proved twice: once as a pure
unit test of `EscalationRouter.decide` (fast, exact), and once as an
integration test through `DiscoveryRunner` for the cases that matter most
operationally (Class B and Class C never scheduling the visual rung).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from discovery.runner import (
    MODE_SCANNED_VISUAL,
    DiscoveryRunner,
    classify_failure,
)
from discovery.inventory import DedupIndex
from ocr.document import StatementMarkdown
from ocr.escalation import (
    ADMITTED_TRIGGERS,
    ALL_TRIGGERS,
    ALNUM_DENSITY_FLOOR,
    A_EXTRACTION,
    B_STRUCTURE,
    C_VALIDATION,
    CHAR_FLOOR,
    EXTRACTOR_FAILED,
    EXTRACTOR_ORDER,
    EXTRACTOR_OUTPUT_UNUSABLE,
    IMAGE_ONLY_DOCUMENT,
    MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
    NO_FAILURE,
    OFFLINE_RUNGS_PRODUCED_NO_TEXT,
    OPERATOR_FORCED_VISUAL,
    TRUNCATION_FLAGGED,
    Escalation,
    EscalationRouter,
    EvidenceQuality,
    ExtractionQualityGate,
    FAILURE_CLASSES,
    RouterInputs,
    router_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Bank Statements"
SCANNED = "Misc/First Farmers 2026 01-document.pdf"
SCAN_BYTES = (CORPUS / SCANNED).read_bytes()

#: A long, well-formed, real-prose page — genuinely USABLE evidence by every
#: criterion the gate checks (well above the char floor, no empty pages, high
#: alphanumeric density) — that no registered parser recognises. This is the
#: fixture CASE 1 needs: a Class-B document, not a short/garbled one.
USABLE_UNCLAIMABLE = (
    "This is a long, entirely legible page of prose that no bank statement "
    "parser in this registry has ever been written to recognise. It repeats "
    "ordinary sentences so that its total character count and alphanumeric "
    "density comfortably clear every floor the extraction quality gate "
    "checks, while never once taking the shape of a dated ledger row, an "
    "account number block, or a running balance column. " * 6
)


def _tesseract(monkeypatch, text: str | None):
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


def _forbid_visual(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("the visual rung must not run"))


def _runner(root: Path, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    kwargs.setdefault("sink", None)
    kwargs.setdefault("cache", None)
    return DiscoveryRunner(root, mode=MODE_SCANNED_VISUAL, run_id="test-run", **kwargs)


@pytest.fixture
def scan_tree(tmp_path: Path) -> Path:
    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(SCAN_BYTES)
    return tmp_path


# ---------------------------------------------------------------------------
# ExtractionQualityGate
# ---------------------------------------------------------------------------

class _Doc:
    def __init__(self, pages):
        self.pages = pages
        self.model = "local-tesseract-ocr"


def test_no_document_is_unusable_no_text_produced():
    evidence = ExtractionQualityGate.assess(None, None)
    assert evidence == EvidenceQuality(
        usable=False, reasons=("no_text_produced",), chars_total=0, pages_empty=0, pages_total=0,
    )


def test_below_the_char_floor_is_unusable():
    evidence = ExtractionQualityGate.assess(_Doc(["short junk text"]), None)
    assert not evidence.usable
    assert "below_char_floor" in evidence.reasons
    assert evidence.chars_total < CHAR_FLOOR


def test_every_page_empty_is_unusable():
    evidence = ExtractionQualityGate.assess(_Doc(["", "   ", ""]), None)
    assert not evidence.usable
    assert "all_pages_empty" in evidence.reasons
    assert evidence.pages_empty == evidence.pages_total == 3


def test_below_the_alnum_density_floor_is_unusable_even_above_the_char_floor():
    # 300 characters, almost entirely punctuation/noise: clears CHAR_FLOOR but
    # not ALNUM_DENSITY_FLOOR.
    noisy = ("." * 250) + ("ab" * 25)
    evidence = ExtractionQualityGate.assess(_Doc([noisy]), None)
    assert evidence.chars_total >= CHAR_FLOOR
    assert not evidence.usable
    assert "below_alnum_density_floor" in evidence.reasons


def test_real_looking_prose_is_usable():
    evidence = ExtractionQualityGate.assess(_Doc([USABLE_UNCLAIMABLE]), None)
    assert evidence.usable
    assert evidence.reasons == ()
    assert evidence.chars_total >= CHAR_FLOOR


def test_the_gate_is_a_pure_function_of_document_and_profile():
    """P20-ROUTER item 2c: the same (document, profile) always produces the
    same verdict, independent of anything that might happen in between two
    calls — this is what makes 'computed before `_analyse`, applied after'
    sound: nothing about the verdict depends on when it is asked."""
    doc = _Doc([USABLE_UNCLAIMABLE])
    before = ExtractionQualityGate.assess(doc, None)

    def unrelated_work():
        return {"pretend": "an analysis stage ran here"}

    unrelated_work()
    after = ExtractionQualityGate.assess(doc, None)
    assert before == after


# ---------------------------------------------------------------------------
# RouterInputs / router_inputs — the field pin and the ONE constructor
# ---------------------------------------------------------------------------

def test_router_inputs_field_set_is_pinned():
    assert set(RouterInputs.__dataclass_fields__) == {
        "profile", "evidence", "triggers", "attempted", "stop",
    }


def test_router_inputs_constructor_normalises_and_is_keyword_only():
    evidence = ExtractionQualityGate.assess(None, None)
    inputs = router_inputs(
        profile=None, evidence=evidence, triggers={OFFLINE_RUNGS_PRODUCED_NO_TEXT},
        attempted=["local_tesseract"], stop=0,
    )
    assert isinstance(inputs, RouterInputs)
    assert inputs.triggers == frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT})
    assert inputs.attempted == ("local_tesseract",)
    assert inputs.stop is False
    with pytest.raises(TypeError):
        router_inputs(None, evidence, frozenset(), (), False)  # positional: refused


# ---------------------------------------------------------------------------
# EscalationRouter.decide — the closed vocabulary and the four rules in order
# ---------------------------------------------------------------------------

def _inputs(**overrides) -> RouterInputs:
    base = dict(
        profile=None,
        evidence=ExtractionQualityGate.assess(None, None),
        triggers=frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT}),
        attempted=(),
        stop=False,
    )
    base.update(overrides)
    return router_inputs(**base)


def test_stop_refuses_regardless_of_any_trigger():
    """CASE 4 (stop): a validated document cannot be re-escalated by ANY
    trigger, including the operator's own flag."""
    decision = EscalationRouter.decide(_inputs(
        stop=True, triggers=frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT, OPERATOR_FORCED_VISUAL}),
    ))
    assert decision == Escalation(extractor=None, trigger=None, refused=("stopped_by_validated",))


def test_no_admitted_trigger_refuses():
    decision = EscalationRouter.decide(_inputs(triggers=frozenset()))
    assert decision.extractor is None
    assert decision.refused == ("no_admitted_trigger",)


def test_truncation_flagged_alone_is_refused_oq4():
    """T is DEFINED, and REFUSED: its population is measured, never routed."""
    assert TRUNCATION_FLAGGED not in ADMITTED_TRIGGERS
    decision = EscalationRouter.decide(_inputs(triggers=frozenset({TRUNCATION_FLAGGED})))
    assert decision.extractor is None
    assert decision.refused == ("no_admitted_trigger",)


def test_extractor_output_unusable_admits_the_first_unattempted_extractor():
    """CASE 3: a read below the floor -> A, the router names the first
    allowed extractor not yet attempted."""
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
    ))
    assert decision.extractor == EXTRACTOR_ORDER[0] == "local_tesseract"
    assert decision.trigger == EXTRACTOR_OUTPUT_UNUSABLE
    assert decision.refused == ()


def test_every_extractor_already_attempted_refuses_case_3b():
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=tuple(EXTRACTOR_ORDER),
    ))
    assert decision.extractor is None
    assert decision.refused == ("no_allowed_extractor_remains",)


def test_a_partially_attempted_ladder_names_the_next_extractor():
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=("local_tesseract",),
    ))
    assert decision.extractor == "visual"


def test_no_paddle_slot_in_the_extractor_order_yet():
    """Phase 2.0 exclusion: no PaddleOCR id anywhere in the fixed order."""
    assert EXTRACTOR_ORDER == ("local_tesseract", "visual")
    assert not any("paddle" in extractor.lower() for extractor in EXTRACTOR_ORDER)


def test_no_page_level_or_remote_extractor_id_is_ever_produced():
    for extractor in EXTRACTOR_ORDER:
        decision = EscalationRouter.decide(_inputs(
            triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        ))
        assert decision.extractor in (None, *EXTRACTOR_ORDER)


def test_endpoint_policy_refuses_when_a_future_policy_module_says_no(monkeypatch):
    """Endpoint-policy guard: with `ocr.endpoint_policy` present (cell B2's
    file, absent from this branch's base — see `_endpoint_policy_allows`'s
    import guard) and refusing, the router never names an extractor."""
    import sys
    import types

    fake_module = types.ModuleType("ocr.endpoint_policy")
    fake_module.extractor_allowed = lambda extractor: (False, "remote_endpoint_not_opted_in")
    monkeypatch.setitem(sys.modules, "ocr.endpoint_policy", fake_module)

    decision = EscalationRouter.decide(_inputs(triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE})))
    assert decision.extractor is None
    assert decision.refused == ("remote_endpoint_not_opted_in",)


def test_endpoint_policy_absent_lets_the_local_extractor_through(monkeypatch):
    """The composition ORDER named in the umbrella card is B2 -> B1 -> A -> C
    -> D; until B2 composes, `ocr/endpoint_policy.py` does not exist and every
    allowed extractor passes through unchanged."""
    import sys

    monkeypatch.delitem(sys.modules, "ocr.endpoint_policy", raising=False)
    decision = EscalationRouter.decide(_inputs(triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE})))
    assert decision.extractor == "local_tesseract"


def test_decide_is_pure_same_inputs_same_answer():
    """P20-ROUTER item 2c, at the router's own level: the decision computed
    from a `RouterInputs` never changes because something else happened in
    between two calls (there is nothing in `RouterInputs` an analysis stage
    could mutate — it is frozen)."""
    inputs = _inputs(triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}))
    first = EscalationRouter.decide(inputs)

    def pretend_analysis_ran():
        return object()

    pretend_analysis_ran()
    second = EscalationRouter.decide(inputs)
    assert first == second


# ---------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------

def test_failure_classes_are_exactly_four():
    assert FAILURE_CLASSES == (A_EXTRACTION, B_STRUCTURE, C_VALIDATION, NO_FAILURE)
    assert FAILURE_CLASSES == ("A", "B", "C", "")


def test_all_triggers_and_admitted_triggers():
    assert ALL_TRIGGERS == (
        IMAGE_ONLY_DOCUMENT, MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
        OFFLINE_RUNGS_PRODUCED_NO_TEXT, EXTRACTOR_OUTPUT_UNUSABLE, EXTRACTOR_FAILED,
        OPERATOR_FORCED_VISUAL, TRUNCATION_FLAGGED,
    )
    assert ADMITTED_TRIGGERS == frozenset(ALL_TRIGGERS) - {TRUNCATION_FLAGGED}


def test_the_mirrored_telemetry_vocabulary_matches_exactly():
    from telemetry.record import EXTRACTION_TRIGGERS, FAILURE_CLASSES as TELEMETRY_FAILURE_CLASSES

    assert TELEMETRY_FAILURE_CLASSES == FAILURE_CLASSES
    assert EXTRACTION_TRIGGERS == ALL_TRIGGERS


# ---------------------------------------------------------------------------
# classify_failure — the one function allowed to know claimed/validated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("claimed,validated", [(False, False), (True, False), (True, True)])
def test_unusable_evidence_is_always_a_regardless_of_downstream(claimed, validated):
    unusable = EvidenceQuality(usable=False, reasons=("below_char_floor",),
                                chars_total=1, pages_empty=0, pages_total=1)
    assert classify_failure(unusable, claimed, validated) == A_EXTRACTION


def test_usable_and_unclaimed_is_b():
    usable = EvidenceQuality(usable=True, reasons=(), chars_total=1000, pages_empty=0, pages_total=1)
    assert classify_failure(usable, claimed=False, validated=False) == B_STRUCTURE


def test_claimed_and_not_validated_is_c():
    usable = EvidenceQuality(usable=True, reasons=(), chars_total=1000, pages_empty=0, pages_total=1)
    assert classify_failure(usable, claimed=True, validated=False) == C_VALIDATION


def test_claimed_and_validated_is_no_failure():
    usable = EvidenceQuality(usable=True, reasons=(), chars_total=1000, pages_empty=0, pages_total=1)
    assert classify_failure(usable, claimed=True, validated=True) == NO_FAILURE


# ---------------------------------------------------------------------------
# CASE 1-4, through the real DiscoveryRunner
# ---------------------------------------------------------------------------

def test_case1_usable_unclaimed_tesseract_text_never_escalates(scan_tree, monkeypatch):
    """The governing invariant's central proof: a Class-B Tesseract read
    (long, legible, alphanumeric-dense — nothing an extraction-quality gate
    would ever call unusable) that no parser claims must NEVER schedule the
    visual rung, in `--scanned-visual` mode, with escalation on."""
    _tesseract(monkeypatch, USABLE_UNCLAIMABLE)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.visual_rung == "not_attempted"
    assert row.evidence_quality == "usable"
    assert row.failure_class == B_STRUCTURE
    assert row.escalation_refused == "no_admitted_trigger"
    assert row.escalation_trigger == ""


def test_case2_claimed_but_financially_failing_never_escalates(scan_tree, monkeypatch):
    """CASE 2: a claimed parse whose reconciliation fails is Class C — no
    visual call, regardless of the underlying evidence quality."""
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)
    _forbid_visual(monkeypatch)

    import telemetry.record as record_module

    real_classify = record_module.classify_document

    def force_c(payload, **kwargs):
        klass, reason = real_classify(payload, **kwargs)
        if klass == "validated":
            return "review", "forced_for_case2_test"
        return klass, reason

    # `discovery/runner.py::process` does `from telemetry.record import
    # classify_document` INSIDE the function, so it re-resolves this
    # attribute on every call — patching the source module's name is enough.
    monkeypatch.setattr(record_module, "classify_document", force_c)
    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.dispatch_outcome == "claimed"
    assert row.outcome_class != "validated"
    assert row.visual_rung == "not_attempted"
    assert row.failure_class == C_VALIDATION


def test_case3_a_below_floor_read_is_the_legal_class_a_trigger(scan_tree, monkeypatch):
    """CASE 3: a read below the floor -> A, the router names visual with
    trigger `extractor_output_unusable`. The visual read here ALSO fails to
    claim (a different flavour of noise), so the original tesseract read
    stays of record — proving the ROUTER's decision (the escalation actually
    ran) independent of whether the second read happens to be adopted."""
    _tesseract(monkeypatch, "scan noise\nlllll ooooo\n0000 ....\nno recognisable statement structure")

    from ocr.config import load_settings

    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())
    monkeypatch.setattr(
        "ocr.ocr_client.ocr_page",
        lambda image, *, settings, client, on_delta=None: "different noise, still unclaimable",
    )

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.evidence_quality == "unusable"
    assert row.escalation_trigger == EXTRACTOR_OUTPUT_UNUSABLE
    assert row.visual_rung == "no_upgrade"
    assert row.source_path == "local_tesseract"


def test_case4_stop_a_validated_document_is_never_re_escalated(scan_tree, monkeypatch):
    """CASE 4 (stop): the offline read already claims and validates; the
    upgrade candidate is never even built (source path already excludes a
    claimed, non-tesseract-relevant read is not this case — this is the
    'already produced a payload' shape) and `_forbid_visual` proves it."""
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.dispatch_outcome == "claimed"
    assert row.visual_rung == "not_attempted"


# ---------------------------------------------------------------------------
# The escalation-budget counter refusal
# ---------------------------------------------------------------------------

def test_the_escalation_budget_refuses_past_its_ceiling(scan_tree, monkeypatch):
    _tesseract(monkeypatch, None)  # RECOVERY: unconditionally Class A
    from ocr.config import load_settings

    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: "junk that claims nothing")

    runner = _runner(scan_tree, visual_escalation=True, escalation_budget=0)
    row = runner.process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "not_attempted"
    assert row.outcome_class == "failed"
    assert row.outcome_reason == "escalation_refused"
    assert row.escalation_refused == "escalation_budget_exhausted"
    assert runner.escalations_used == 0


def test_the_escalation_budget_permits_exactly_its_ceiling(scan_tree, monkeypatch):
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, None)
    from ocr.config import load_settings

    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: claimable)

    runner = _runner(scan_tree, visual_escalation=True, escalation_budget=1)
    row = runner.process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"
    assert runner.escalations_used == 1


# ---------------------------------------------------------------------------
# webapp/worker.py's `_force_ocr_decision` — item 3's own router call site
# ---------------------------------------------------------------------------

def test_force_ocr_decision_admits_when_the_offline_ladder_produced_nothing():
    """START case (i): `doc is None` (R-shape) — the operator's flag plus the
    offline-ladder-produced-nothing fact both admit."""
    from webapp.worker import _force_ocr_decision

    decision = _force_ocr_decision(None, None, None)
    assert decision.extractor == "visual"


def test_force_ocr_decision_admits_when_analysis_did_not_claim():
    """START case (ii): `doc` exists (a Tesseract read), analysis raised (no
    claim) — the operator's flag alone is the trigger here, deliberately
    (see `_force_ocr_decision`'s docstring)."""
    from webapp.worker import _force_ocr_decision

    decision = _force_ocr_decision(_Doc([USABLE_UNCLAIMABLE]), None, None)
    assert decision.extractor == "visual"
    assert decision.trigger == OPERATOR_FORCED_VISUAL


def test_force_ocr_decision_stops_the_moment_analysis_exists():
    """CASE 4 (stop), at this call site: ANY payload — even one that will go
    on to fail financial validation (Class C) — refuses the flag."""
    from webapp.worker import _force_ocr_decision

    decision = _force_ocr_decision(_Doc([USABLE_UNCLAIMABLE]), None, {"quality": {}})
    assert decision.extractor is None
    assert decision.refused == ("stopped_by_validated",)


def test_cli_run_computes_and_publishes_the_escalation_budget(tmp_path, monkeypatch):
    """P20-ROUTER item 2f, end to end through `discovery.cli.run()`: the
    budget is computed once, before any document is processed, threaded into
    the runner, and reported in `summary.json` — and it is `None` (unbounded)
    for every mode other than `--scanned-visual`."""
    import discovery.cli as cli

    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(SCAN_BYTES)
    _tesseract(monkeypatch, None)  # RECOVERY for the one scanned document
    from ocr.config import load_settings
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: claimable)

    summary = cli.run(
        tmp_path, MODE_SCANNED_VISUAL, tmp_path / "out",
        skip_baseline=True, use_cache=False, visual_escalation=True,
    )
    assert summary["escalation_budget"] == 1  # one scanned-profile document
    assert summary["escalations_used"] == 1

    digital_summary = cli.run(
        tmp_path, "digital", tmp_path / "out2", skip_baseline=True, use_cache=False,
    )
    assert digital_summary["escalation_budget"] is None
    assert digital_summary["escalations_used"] == 0


# ---------------------------------------------------------------------------
# Corpus pin: `validated ∩ class-A = 0`, measured against the batch-9 run of
# record's own cold cache. `tools/phase2_trigger_split.py` is the instrument
# that produces the headline numbers this test PINS.
# ---------------------------------------------------------------------------

COLD_CACHE = (".claude", "recovery", "webapp_data_train9_cold")
RUN_POINTER = ("discovery_reports", "train9-logs", "train9_run_dir.txt")


def _checkout_ancestor(*relative: str) -> Path | None:
    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


def _archive():
    cache = _checkout_ancestor(*COLD_CACHE)
    pointer = _checkout_ancestor(*RUN_POINTER)
    if cache is None or pointer is None:
        pytest.skip(
            "the train9 cold cache and run-of-record pointer were not found "
            "in this checkout or any ancestor; run from the repository tree "
            "or a worktree beneath .claude/worktrees/."
        )
    run = pointer.parent.parent.parent / pointer.read_text(encoding="utf-8").strip()
    if not run.exists():
        pytest.skip(f"the run of record named by {pointer.name} is not present")
    return cache, run


@pytest.mark.corpus
def test_validated_tesseract_reads_are_never_classified_class_a():
    """`validated ∩ class-A = 0`, pinned directly (not merely trusted from a
    one-time print of `tools/phase2_trigger_split.py`): every validated
    Tesseract read in the run of record must clear the gate, and R∪U's
    intersection with `validated` must stay 0.
    """
    from tools.phase2_trigger_split import ColdOcrReader, load_rows, measure

    cache_dir, run = _archive()
    rows = load_rows(run)
    reader = ColdOcrReader(cache_dir)
    result = measure(rows, reader)

    assert len(result["R"]) == 13
    assert len(result["U"]) == 123
    assert result["overlap"] == set()
    assert result["validated_intersect_R_or_U"] == set()
    assert result["validated_unusable"] == set(), (
        "a validated Tesseract read classified unusable by "
        "ExtractionQualityGate would break the validated-never-class-A pin"
    )
    assert len(result["u_extract"]) + len(result["u_structure"]) == len(result["U"])
    assert result["u_missing_artifact"] == set()
