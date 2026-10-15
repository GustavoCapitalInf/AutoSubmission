"""P20-ROUTER: `ocr.escalation` unit proof, the CASE 1-4 behavioural proof,
and the corpus-measured pin that the extraction-quality gate never calls a
validated Tesseract read unusable.

Nothing here reaches a server. Cases 1-4 are proved twice: once as a pure
unit test of `EscalationRouter.decide` (fast, exact), and once as an
integration test through `DiscoveryRunner` for the cases that matter most
operationally (Class B and Class C never scheduling an escalation read).

Model-code removal, slice S2: the integration tests ran in the retired
`--scanned-visual` mode with the visual OCR client faked; they moved to
`--scanned-paddle`, and the three whose subject was the visual client itself
(a visual recovery read, a visual upgrade read, the client's endpoint refusal)
were deleted with it. Slice S5: the Paddle and research modes, and with them
the runner's last `decide(` sites, were removed. The integration tests now run
in `--scanned` (no escalation exists to schedule) and pin what they always
pinned about the ROW: the deterministic projection (`evidence_quality`,
`failure_class`, both rungs `not_attempted`, no trigger and no router refusal
recorded). The tests whose subject was the escalation itself (the MINOR-9
refusal comparability, the escalation budget and its CLI computation) were
deleted with it. The router's own unit tests stay: `ocr/escalation.py` is kept
(pinned) for its vocabulary and its gate.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from discovery.runner import (
    GATE_ASSESSED_SOURCES,
    MODE_SCANNED,
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

#: MAJOR-4 (P20-ROUTER re-review, closure 49fe3fe). A Tesseract read that is
#: USABLE under the admitted triad (well above the char floor, no empty
#: pages) but falls BELOW `ALNUM_DENSITY_FLOOR` — a wide, padded tabular
#: layout, not noise. `ExtractionQualityGate.assess` on this text measures
#: `usable=True, reasons=(), signals=('below_alnum_density_floor',),
#: chars_total=1043` (verified directly). This is the fixture the surfaced-
#: vs-admitted rule (MAJOR-2) must be proved against: CASE 1's own
#: `USABLE_UNCLAIMABLE` carries no density signal at all (dense prose), so it
#: cannot catch a mutant that re-admits the SIGNAL as a trigger.
PADDED_TABULAR = (
    "\n".join(
        "DATE" + " " * 14 + "DESCRIPTION" + " " * 26 + "AMOUNT" + " " * 18 + "BALANCE"
        for _ in range(12)
    )
    + "\n"
)


def _tesseract(monkeypatch, text: str | None):
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


def _forbid_visual(monkeypatch):
    """No escalation read can run: the visual OCR client and the Paddle rung no
    longer exist at all (slices S2 and S5), and the runner has no escalation
    read to call."""
    for module in ("ocr.ocr_client", "ocr.paddle_rung", "ocr.paddle_client"):
        assert importlib.util.find_spec(module) is None, module
    for name in ("_read_paddle", "_read_visual", "_upgrade_eligible", "_apply_budget"):
        assert not hasattr(DiscoveryRunner, name), name


def _runner(root: Path, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    kwargs.setdefault("sink", None)
    kwargs.setdefault("cache", None)
    return DiscoveryRunner(root, mode=MODE_SCANNED, run_id="test-run", **kwargs)


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

def test_gate_assessed_sources_are_exactly_tesseract_visual_and_paddle():
    assert GATE_ASSESSED_SOURCES == frozenset({"local_tesseract", "visual", "paddle"})


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
        "profile", "evidence", "triggers", "attempted", "stop", "enabled",
    }


def test_router_inputs_constructor_normalises_and_is_keyword_only():
    evidence = ExtractionQualityGate.assess(None, None)
    inputs = router_inputs(
        profile=None, evidence=evidence, triggers={OFFLINE_RUNGS_PRODUCED_NO_TEXT},
        attempted=["local_tesseract"], stop=0, enabled=["visual"],
    )
    assert isinstance(inputs, RouterInputs)
    assert inputs.triggers == frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT})
    assert inputs.attempted == ("local_tesseract",)
    assert inputs.stop is False
    assert inputs.enabled == frozenset({"visual"})
    with pytest.raises(TypeError):
        router_inputs(None, evidence, frozenset(), (), False, frozenset())  # positional: refused


# ---------------------------------------------------------------------------
# EscalationRouter.decide — the closed vocabulary and the four rules in order
# ---------------------------------------------------------------------------

def _inputs(**overrides) -> RouterInputs:
    # Unit-level default: every extractor "enabled", so these pure tests of
    # `decide`'s ORDER / ATTEMPTED logic are unaffected by D4's mode
    # narrowing unless a test deliberately overrides `enabled` to exercise
    # it. Production callers never do this (each mode enables at most one
    # extractor) — see the D4-specific tests below and the CASE 1-4 tests,
    # which go through the real `DiscoveryRunner` and therefore a real,
    # narrow `enabled` set.
    base = dict(
        profile=None,
        evidence=ExtractionQualityGate.assess(None, None),
        triggers=frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT}),
        attempted=(),
        stop=False,
        enabled=frozenset(EXTRACTOR_ORDER),
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
    """Phase 2.1 (D4): with every extractor enabled, the next one after
    `local_tesseract` in `EXTRACTOR_ORDER` is `paddle` — it now sits between
    `local_tesseract` and `visual`."""
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=("local_tesseract",),
    ))
    assert decision.extractor == "paddle"


def test_a_partially_attempted_ladder_names_the_next_after_paddle_too():
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}),
        attempted=("local_tesseract", "paddle"),
    ))
    assert decision.extractor == "visual"


# ---------------------------------------------------------------------------
# D4: `enabled` narrows which allowed extractor `decide` may pick — the
# fixture every real mode actually uses (exactly one member, or none).
# ---------------------------------------------------------------------------

def test_enabled_narrows_to_paddle_only():
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        enabled=frozenset({"paddle"}),
    ))
    assert decision.extractor == "paddle"


def test_enabled_narrows_to_visual_only():
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        enabled=frozenset({"visual"}),
    ))
    assert decision.extractor == "visual"


def test_an_admitted_trigger_with_nothing_enabled_refuses():
    """M2's own negative control at the unit level: an admitted trigger with
    `enabled=frozenset()` (no mode has authorised any extractor at all) must
    refuse — never silently pick the fixed order's first member regardless
    of what the mode allows."""
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        enabled=frozenset(),
    ))
    assert decision.extractor is None
    assert decision.refused == ("no_allowed_extractor_remains",)


def test_enabled_does_not_add_an_extractor_the_order_does_not_already_name():
    """`enabled` only ever NARROWS `EXTRACTOR_ORDER`; naming an unknown
    extractor id in `enabled` grants it nothing."""
    decision = EscalationRouter.decide(_inputs(
        triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        enabled=frozenset({"unlimited_ocr"}),
    ))
    assert decision.extractor is None
    assert decision.refused == ("no_allowed_extractor_remains",)


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


# `test_recovery_through_the_real_runner_reports_offline_rungs_produced_no_text`
# drove a visual recovery read; it was deleted with the visual OCR client
# (slice S2). The same end-to-end trigger report on a recovery is pinned for the
# Paddle rung by `tests/test_paddle_routing.py::test_case1_recovery_names_paddle_and_local_free_recovers`,
# and the reporting priority itself by the unit test above.


def test_the_paddle_slot_is_filled_between_tesseract_and_visual():
    """Phase 2.1 (D4, OQ5): PaddleOCR takes the SLOT Phase 2.0 left named but
    empty, in the documented position."""
    assert EXTRACTOR_ORDER == ("local_tesseract", "paddle", "visual", "visual_pair")


def test_no_page_level_or_remote_extractor_id_is_ever_produced():
    for extractor in EXTRACTOR_ORDER:
        decision = EscalationRouter.decide(_inputs(
            triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE}), attempted=(),
        ))
        assert decision.extractor in (None, *EXTRACTOR_ORDER)


def test_the_router_has_no_endpoint_policy_seam_at_all(monkeypatch):
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
    # (`ocr.endpoint_policy` itself was removed in slice S5 of the model-code
    # removal; the fake below still proves the router consults no such seam.)
    # Composition (Ocean, train10): the REAL `ocr.endpoint_policy` (cell B2)
    # is imported by `ocr_client._build_client` and pinned by class identity
    # in tests/test_ocr_endpoint_policy.py. A bare `del sys.modules[...]`
    # here evicted the real module when it was already loaded, so every later
    # `from ocr.endpoint_policy import EndpointRefused` produced a SECOND class
    # object and `pytest.raises(EndpointRefused)` stopped matching — 4
    # order-dependent failures at the composed tree. `monkeypatch.setitem`
    # restores whatever was there before, real module included.
    monkeypatch.setitem(sys.modules, "ocr.endpoint_policy", fake_module)
    decision = EscalationRouter.decide(_inputs(triggers=frozenset({EXTRACTOR_OUTPUT_UNUSABLE})))
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
    # P22-TRUTHTABLE (D8) appends ONE member, `OPERATOR_FORCED_PADDLE`: the
    # research run mode's trigger, a run-mode fact exactly like
    # `OPERATOR_FORCED_VISUAL` beside it. Its mode-only reachability is
    # `tests/test_research_mode.py`'s subject, not this pin's — this line is
    # the closed-vocabulary pin and nothing else.
    from ocr.escalation import (OPERATOR_FORCED_PADDLE, OPERATOR_FORCED_VISUAL_PAIR, DETERMINISTIC_PARSE_UNVALIDATED)

    assert ALL_TRIGGERS == (
        IMAGE_ONLY_DOCUMENT, MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
        OFFLINE_RUNGS_PRODUCED_NO_TEXT, EXTRACTOR_OUTPUT_UNUSABLE, EXTRACTOR_FAILED,
        OPERATOR_FORCED_VISUAL, OPERATOR_FORCED_VISUAL_PAIR,
        DETERMINISTIC_PARSE_UNVALIDATED, OPERATOR_FORCED_PADDLE, TRUNCATION_FLAGGED,
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
    would ever call unusable) that no parser claims never schedules an
    escalation read. Since slice S5 no mode can (none exists), and the row
    records the deterministic projection with no router decision at all
    (`escalation_refused` was `no_admitted_trigger` in the retired modes)."""
    _tesseract(monkeypatch, USABLE_UNCLAIMABLE)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")

    assert (row.visual_rung, row.paddle_rung) == ("not_attempted", "not_attempted")
    assert row.evidence_quality == "usable"
    assert row.failure_class == B_STRUCTURE
    assert row.escalation_refused == ""
    assert row.escalation_trigger == ""


def test_a_density_surfaced_but_usable_tesseract_read_never_escalates(scan_tree, monkeypatch):
    """MAJOR-4 (P20-ROUTER re-review, closure 49fe3fe). MAJOR-2 ruled that the
    density SIGNAL never admits a trigger — but nothing before this test
    proved that at the RUNNER's own call site, only inside the gate: CASE 1's
    fixture (`USABLE_UNCLAIMABLE`) is dense prose and carries no density
    signal at all, so a one-line runner mutant that re-admits
    `evidence.signals` as a trigger source is invisible to it. `PADDED_TABULAR`
    IS usable under the triad AND carries the density signal
    (`below_alnum_density_floor`), so this is the one fixture that can catch
    that specific edge: the visual rung must stay `not_attempted` even though
    the read is both unclaimed AND density-surfaced."""
    _tesseract(monkeypatch, PADDED_TABULAR)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")

    assert (row.visual_rung, row.paddle_rung) == ("not_attempted", "not_attempted")
    assert row.evidence_quality == "usable"
    assert row.escalation_refused == "" and row.escalation_trigger == ""


# `test_usable_evidence_reports_the_same_refusal_whether_or_not_it_was_claimed`
# (MINOR-9) pinned that the UPGRADE candidate's own refusal was recorded on
# claimed and unclaimed rows alike; it left with the upgrade decision (slice
# S5). Every row now records no router decision at all, which
# `test_case1_...` above pins.


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
    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")

    assert row.dispatch_outcome == "claimed"
    assert row.outcome_class != "validated"
    assert row.visual_rung == "not_attempted"
    assert row.failure_class == C_VALIDATION


# `test_case3_a_below_floor_read_is_the_legal_class_a_trigger` drove a visual
# upgrade read (the router naming visual on `extractor_output_unusable`); it was
# deleted with the visual OCR client (slice S2). The Paddle rung's upgrade on
# the same trigger is `tests/test_paddle_routing.py::test_case1_u_extract_shape_upgrade_also_names_paddle`.


def test_case4_stop_a_validated_document_is_never_re_escalated(scan_tree, monkeypatch):
    """CASE 4 (stop): the offline read already claims and validates; the
    upgrade candidate is never even built (source path already excludes a
    claimed, non-tesseract-relevant read is not this case — this is the
    'already produced a payload' shape) and `_forbid_visual` proves it."""
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.dispatch_outcome == "claimed"
    assert row.visual_rung == "not_attempted"
    assert row.paddle_rung == "not_attempted"


# `test_a_refused_endpoint_fails_the_document_closed_with_no_second_attempt`
# pinned the visual OCR client's endpoint refusal (`ocr_client._build_client`);
# it was deleted with the client (slice S2). The Paddle rung's transport
# failures are `tests/test_paddle_routing.py::test_case18_transport_failures_fail_closed_with_no_second_attempt`.


# ---------------------------------------------------------------------------
# The escalation budget (`test_the_escalation_budget_refuses_past_its_ceiling`,
# `..._permits_exactly_its_ceiling`, `test_cli_run_computes_and_publishes_the_
# escalation_budget`) left with the Paddle mode's RECOVERY read it bounded
# (slice S5). The summary keeps `escalation_budget` None and `escalations_used`
# 0 (`tests/test_discovery_no_models.py`). webapp/worker.py's
# `_force_ocr_decision` left in slice S1: a forced job is refused before
# preflight (tests/test_webapp_worker.py). The router's own vocabulary is
# unchanged.
# ---------------------------------------------------------------------------


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
