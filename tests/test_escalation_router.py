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
    GATE_ASSESSED_SOURCES,
    MODE_SCANNED_VISUAL,
    DiscoveryRunner,
    DocumentRow,
    _evidence_for_row,
    classify_failure,
)
from discovery.inventory import DedupIndex
from ocr.document import StatementMarkdown
from ocr.escalation import (
    ADMITTED_TRIGGERS,
    ALL_TRIGGERS,
    ALNUM_DENSITY_FLOOR,
    A_EXTRACTION,
    BELOW_ALNUM_DENSITY_FLOOR,
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
    TRIGGER_REPORT_PRIORITY,
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
        usable=False, reasons=("no_text_produced",), signals=(),
        chars_total=0, pages_empty=0, pages_total=0,
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


def test_below_the_alnum_density_floor_is_surfaced_but_still_usable():
    """P20-ROUTER review, MAJOR-2 (ruled): the density criterion is
    SURFACE-ONLY, exactly like Trigger T. It is recorded in `.signals` — an
    advisory, never-routed observation — and NEVER moves `.usable` or
    appears in `.reasons`. `ADMITTED_TRIGGERS`' `EXTRACTOR_OUTPUT_UNUSABLE`
    can therefore never fire on density alone; only the parameter-free triad
    (no text / below char floor / all pages empty) may.
    """
    # 300 characters, almost entirely punctuation/noise: clears CHAR_FLOOR but
    # falls below ALNUM_DENSITY_FLOOR.
    noisy = ("." * 250) + ("ab" * 25)
    evidence = ExtractionQualityGate.assess(_Doc([noisy]), None)
    assert evidence.chars_total >= CHAR_FLOOR
    assert evidence.usable is True
    assert evidence.reasons == ()
    assert BELOW_ALNUM_DENSITY_FLOOR in evidence.signals
    assert "below_alnum_density_floor" not in evidence.reasons


def test_the_admitted_criteria_are_the_parameter_free_triad_only():
    """No document, however low its alphanumeric density, is ever made
    unusable by anything but the three named, parameter-free criteria — a
    structural pin against MAJOR-2 quietly returning."""
    almost_all_noise = ("!" * 5000)
    evidence = ExtractionQualityGate.assess(_Doc([almost_all_noise]), None)
    assert evidence.usable is True
    assert evidence.reasons == ()
    assert BELOW_ALNUM_DENSITY_FLOOR in evidence.signals  # 0% alnum: surfaced, not admitted


def test_real_looking_prose_is_usable():
    evidence = ExtractionQualityGate.assess(_Doc([USABLE_UNCLAIMABLE]), None)
    assert evidence.usable
    assert evidence.reasons == ()
    assert evidence.signals == ()  # dense prose: no advisory signal either
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
# `_evidence_for_row` / `GATE_ASSESSED_SOURCES` — BLOCK-1: the gate assesses
# ONLY evidence an extractor produced. Reproduced BEFORE the fix (see the
# P20-ROUTER W3 closure section): a validated native document classified
# `failure_class="A"` 79 times on the run of record, and every committed-
# artifact dry-run row did too, because `ExtractionQualityGate.assess` was
# called unconditionally on every source, including `document=None` for the
# committed-artifact rung (which has real text — just no `StatementMarkdown`
# object behind it).
# ---------------------------------------------------------------------------

def test_gate_assessed_sources_are_exactly_tesseract_and_visual():
    assert GATE_ASSESSED_SOURCES == frozenset({"local_tesseract", "visual"})


def test_a_native_document_is_usable_by_construction_regardless_of_content():
    """A native read — even one the gate WOULD call unusable by its own
    criteria (short, low-density) — is never assessed at all: native
    unclaimed text is a layout problem (Class B), never an extraction
    failure (Class A)."""
    junk = ("." * 250) + ("ab" * 25)  # would fail the density signal if assessed
    evidence = _evidence_for_row(_Doc([junk]), None, "native")
    assert evidence.usable is True
    assert evidence.reasons == ()
    assert evidence.signals == ()  # not merely usable — never even LOOKED AT


def test_a_committed_artifact_row_is_usable_by_construction_even_with_document_none():
    """The dry-run committed-artifact rung: `document` really is `None`
    there (no `StatementMarkdown` object — the markdown came from a
    committed fixture file), which the gate would read as `no_text_produced`
    if it were ever handed this source. `_evidence_for_row` never calls the
    gate at all for this source."""
    evidence = _evidence_for_row(None, None, "committed_artifact")
    assert evidence.usable is True
    assert evidence.reasons == ()


def test_tesseract_and_visual_sources_are_really_gate_assessed():
    junk = "short junk text"
    for source in ("local_tesseract", "visual"):
        evidence = _evidence_for_row(_Doc([junk]), None, source)
        assert evidence.usable is False
        assert "below_char_floor" in evidence.reasons


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


def test_the_most_specific_admitted_trigger_is_reported_not_the_declaration_order():
    """P20-ROUTER review, MINOR-8: when a recovery admits BOTH
    `offline_rungs_produced_no_text` (evidence-level) and
    `image_only_document` (profile-level) at once, the row must report the
    evidence-level fact — the one the whole R population is named after —
    not whichever trigger happens to be declared first in `ALL_TRIGGERS`."""
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({IMAGE_ONLY_DOCUMENT, OFFLINE_RUNGS_PRODUCED_NO_TEXT, OPERATOR_FORCED_VISUAL}),
    ))
    assert decision.trigger == OFFLINE_RUNGS_PRODUCED_NO_TEXT
    # `ALL_TRIGGERS`' declaration order would have picked IMAGE_ONLY_DOCUMENT
    # (declared first) — proving the two orders really are different.
    assert ALL_TRIGGERS.index(IMAGE_ONLY_DOCUMENT) < ALL_TRIGGERS.index(OFFLINE_RUNGS_PRODUCED_NO_TEXT)
    assert (
        TRIGGER_REPORT_PRIORITY.index(OFFLINE_RUNGS_PRODUCED_NO_TEXT)
        < TRIGGER_REPORT_PRIORITY.index(IMAGE_ONLY_DOCUMENT)
    )


def test_recovery_through_the_real_runner_reports_offline_rungs_produced_no_text(
    scan_tree, monkeypatch,
):
    """MINOR-8, end to end: a real recovery (the offline ladder produced
    nothing at all for a scanned document) must report
    `offline_rungs_produced_no_text` on the row, never `image_only_document`
    — the two are always co-admitted for a scanned document, so only the
    reporting priority tells them apart."""
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, None)
    from ocr.config import load_settings

    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: claimable)

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"
    assert row.escalation_trigger == OFFLINE_RUNGS_PRODUCED_NO_TEXT


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


def test_the_router_has_no_endpoint_policy_seam_at_all():
    """P20-ROUTER review, MAJOR-1 (ruled): the router does not consult, nor
    import, any endpoint-policy module — that enforcement lives entirely in
    `ocr_client._build_client` (cell B2), which fails closed before any
    client object exists. `EscalationRouter.decide` picks among its own
    closed `EXTRACTOR_ORDER`, full stop; a real endpoint-refusing module
    installed in `sys.modules` changes nothing about its answer."""
    import sys
    import types

    fake_module = types.ModuleType("ocr.endpoint_policy")
    fake_module.check_endpoint = lambda base_url, *, opt_in: (_ for _ in ()).throw(
        AssertionError("the router must never call an endpoint-policy module")
    )
    sys.modules["ocr.endpoint_policy"] = fake_module
    try:
        decision = EscalationRouter.decide(_inputs(triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE})))
    finally:
        del sys.modules["ocr.endpoint_policy"]
    assert decision.extractor == "local_tesseract"


def test_ocr_escalation_does_not_import_endpoint_policy():
    import ocr.escalation as escalation_module

    assert "endpoint_policy" not in dir(escalation_module)
    assert not hasattr(escalation_module, "_endpoint_policy_allows")


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


def test_both_vocabularies_are_exported_from_the_telemetry_package():
    """P20-ROUTER review, MAJOR-3: exported beside `DEFERRED_REASONS`, not
    reachable only through `telemetry.record`."""
    import telemetry

    assert telemetry.FAILURE_CLASSES == FAILURE_CLASSES
    assert telemetry.EXTRACTION_TRIGGERS == ALL_TRIGGERS
    assert "FAILURE_CLASSES" in telemetry.__all__
    assert "EXTRACTION_TRIGGERS" in telemetry.__all__


def _row(**overrides) -> DocumentRow:
    base = dict(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1)
    base.update(overrides)
    return DocumentRow(**base)


def test_as_dict_refuses_a_failure_class_outside_the_vocabulary():
    """P20-ROUTER review, MAJOR-3: enforced at the row projection, exactly
    the pattern `classify_outcome` uses for `DEFERRED_REASONS`
    (`telemetry/record.py:399`) — a comment is not enforcement."""
    row = _row(failure_class="Z")
    with pytest.raises(ValueError, match="failure_class"):
        row.as_dict()


def test_as_dict_refuses_an_escalation_trigger_outside_the_vocabulary():
    row = _row(escalation_trigger="not_a_real_trigger")
    with pytest.raises(ValueError, match="escalation_trigger"):
        row.as_dict()


def test_as_dict_accepts_every_member_of_both_vocabularies():
    for failure_class in FAILURE_CLASSES:
        _row(failure_class=failure_class).as_dict()
    for trigger in ("",) + ALL_TRIGGERS:
        _row(escalation_trigger=trigger).as_dict()


# ---------------------------------------------------------------------------
# classify_failure — the one function allowed to know claimed/validated.
# Order (P20-ROUTER review, BLOCK-1, ruled): `validated` is checked FIRST.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("claimed", [False, True])
def test_unusable_evidence_is_a_when_not_validated(claimed):
    unusable = EvidenceQuality(usable=False, reasons=("below_char_floor",), signals=(),
                                chars_total=1, pages_empty=0, pages_total=1)
    assert classify_failure(unusable, claimed=claimed, validated=False) == A_EXTRACTION


def test_validated_overrides_unusable_evidence_no_failure():
    """BLOCK-1's central fix, at the unit level: a document the deterministic
    validator proved `validated` is NEVER `A`, however unusable the evidence
    that produced it would otherwise have looked — the validator's verdict is
    authoritative over a structural extraction-quality heuristic, not the
    other way round. This is the exact shape that classified 79 real
    `validated` documents `failure_class="A"` before the fix."""
    unusable = EvidenceQuality(usable=False, reasons=("below_char_floor",), signals=(),
                                chars_total=1, pages_empty=0, pages_total=1)
    assert classify_failure(unusable, claimed=True, validated=True) == NO_FAILURE


def test_usable_and_unclaimed_is_b():
    usable = EvidenceQuality(usable=True, reasons=(), signals=(),
                              chars_total=1000, pages_empty=0, pages_total=1)
    assert classify_failure(usable, claimed=False, validated=False) == B_STRUCTURE


def test_claimed_and_not_validated_is_c():
    usable = EvidenceQuality(usable=True, reasons=(), signals=(),
                              chars_total=1000, pages_empty=0, pages_total=1)
    assert classify_failure(usable, claimed=True, validated=False) == C_VALIDATION


def test_claimed_and_validated_is_no_failure():
    usable = EvidenceQuality(usable=True, reasons=(), signals=(),
                              chars_total=1000, pages_empty=0, pages_total=1)
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


def test_usable_evidence_reports_the_same_refusal_whether_or_not_it_was_claimed(
    scan_tree, monkeypatch, tmp_path,
):
    """P20-ROUTER review, MINOR-9: `escalation_refused` must be COMPARABLE
    across rows. Before the fix, a usable-evidence document that
    `_upgrade_eligible` excluded (a D-3 analysis cache hit that served an
    already-CLAIMED payload — `collector.seen` is False, so eligibility
    collapses to `payload is None`, which is False here) carried an EMPTY
    refusal, while an otherwise-identical usable-evidence document that was
    NOT excluded (CASE 1: genuinely unclaimed) carried `no_admitted_trigger`
    — the column could not be used to compare the two. Both must now read
    `no_admitted_trigger`, because the candidate's OWN verdict — computed
    from evidence alone, before eligibility is even asked — is recorded
    unconditionally."""
    from corpus_artifacts import cached_markdown
    from webapp.artifact_cache import open_cache

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, claimable)
    _forbid_visual(monkeypatch)

    first = _runner(scan_tree, cache=cache, visual_escalation=True).process(
        "BankZ/scan.pdf", "BankZ")
    assert first.parser_id_source == "live_dispatch"
    assert first.dispatch_outcome == "claimed"

    second = _runner(scan_tree, cache=cache, visual_escalation=True).process(
        "BankZ/scan.pdf", "BankZ")
    assert second.cache_analysis == "hit"
    assert second.parser_id_source == "live_detect"  # no live dispatch this run
    assert second.visual_rung == "not_attempted"
    assert second.escalation_refused == "no_admitted_trigger"

    # CASE 1's own row (genuinely unclaimed, never cached) carries the
    # identical refusal string.
    from discovery.inventory import DedupIndex

    unclaimed_tree = scan_tree.parent / "unclaimed"
    (unclaimed_tree / "BankZ").mkdir(parents=True)
    (unclaimed_tree / "BankZ" / "scan.pdf").write_bytes(SCAN_BYTES)
    _tesseract(monkeypatch, USABLE_UNCLAIMABLE)
    third = _runner(unclaimed_tree, visual_escalation=True, dedup=DedupIndex()).process(
        "BankZ/scan.pdf", "BankZ")
    assert third.dispatch_outcome != "claimed"
    assert third.escalation_refused == second.escalation_refused == "no_admitted_trigger"


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


def test_a_refused_endpoint_fails_the_document_closed_with_no_second_attempt(scan_tree, monkeypatch):
    """P20-ROUTER review, MAJOR-1's replacement mutation-table row 5:
    endpoint policy is enforced in exactly ONE place — `ocr_client._build_client`
    (cell B2) — which fails closed BEFORE any client object exists. The
    router never sees this at all; a refused/unreachable endpoint surfaces
    as the visual rung's OWN transport failure, and the document is
    terminal, with exactly one attempt (no retry, no second extractor)."""
    from ocr.config import load_settings

    _tesseract(monkeypatch, None)  # RECOVERY: the offline ladder found nothing
    calls: list = []
    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])

    def refused(settings):
        calls.append(settings)
        raise RuntimeError("endpoint refused: not opted in")

    monkeypatch.setattr("ocr.ocr_client._build_client", refused)

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.visual_rung == "failed"
    assert (row.outcome_class, row.outcome_reason) == ("failed", "ocr_failed")
    assert row.error_type == "RuntimeError"
    assert len(calls) == 1
    assert row.source_path == "none"


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
    """`validated ∩ class-A = 0` over the TESSERACT population, pinned
    directly (not merely trusted from a one-time print of
    `tools/phase2_trigger_split.py`): every validated Tesseract read in the
    run of record must clear the gate, and R∪U's intersection with
    `validated` must stay 0. Post-MAJOR-2, `u_extract` is measured under the
    gate's ADMITTED (parameter-free) criteria alone and is expected to be
    empty; `u_density_surfaced` is the separate, advisory-only population.
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
    # MAJOR-2: the admitted split and the (separate) density-surfaced count.
    assert len(result["u_extract"]) == 0
    assert len(result["u_structure"]) == 123
    assert len(result["u_density_surfaced"]) == 23
    assert len(result["legal_escalation_population"]) == 13  # R alone, post-MAJOR-2


@pytest.mark.corpus
def test_no_validated_document_of_any_source_is_ever_classified_class_a():
    """BLOCK-1's WIDENED pin (ruled 2026-09-01): `validated ∩ class-A = 0`
    over EVERY row of the run of record, not only Tesseract reads. This is
    the exact reproduction that found 79 validated NATIVE documents
    classified `failure_class="A"` before the fix (`classify_failure` graded
    evidence before it checked `validated`, and the gate was assessing
    native/committed-artifact evidence it should never have seen at all).
    Uses the PRODUCTION `classify_failure` / `_evidence_for_row` directly
    (via `tools.phase2_trigger_split.measure_row_level_class_a`), so this
    pin cannot silently drift from what the runner actually publishes.
    """
    from tools.phase2_trigger_split import ColdOcrReader, load_rows, measure_row_level_class_a

    cache_dir, run = _archive()
    rows = load_rows(run)
    reader = ColdOcrReader(cache_dir)
    result = measure_row_level_class_a(rows, reader)

    assert result["validated_class_a"] == set(), (
        f"{len(result['validated_class_a'])} validated document(s) classify "
        f"failure_class='A' — BLOCK-1 is not closed"
    )
    # No native or committed-artifact row may EVER classify A, validated or
    # not — the gate must never have been asked about that source at all.
    non_a_sources = {"native", "committed_artifact"}
    offending = {
        key: shas for key, shas in result["by_source_and_class"].items()
        if key.split(":", 1)[0] in non_a_sources and key.endswith(":A")
    }
    assert offending == {}, f"native/committed-artifact rows classified A: {offending}"
