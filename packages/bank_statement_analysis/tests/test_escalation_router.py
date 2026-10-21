"""P20-ROUTER: `ocr.escalation`'s failure-class vocabulary and extraction-quality
gate, and the CASE 1-4 behavioural proof through `DiscoveryRunner`.

Nothing here reaches a server. The escalation router these cases were first
written against was removed with the model rungs; the integration tests run in
`--scanned` and pin what they always pinned about the ROW: the deterministic
projection (`evidence_quality`, `failure_class`, both rungs `not_attempted`,
no trigger and no router refusal recorded).
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
from ocr.escalation import (
    ALNUM_DENSITY_FLOOR,
    A_EXTRACTION,
    BELOW_ALNUM_DENSITY_FLOOR,
    B_STRUCTURE,
    C_VALIDATION,
    CHAR_FLOOR,
    NO_FAILURE,
    EvidenceQuality,
    ExtractionQualityGate,
    FAILURE_CLASSES,
)
from telemetry.record import EXTRACTION_TRIGGERS
from tests.statements import statements_dir
from tests.helpers import _tesseract

ROOT = Path(__file__).resolve().parents[1]
SCANNED = "Misc/First Farmers 2026 01-document.pdf"


def _scan_bytes() -> bytes:
    return (statements_dir() / SCANNED).read_bytes()


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
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(_scan_bytes())
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
    appears in `.reasons`: only the parameter-free triad (no text / below
    char floor / all pages empty) makes a read unusable.
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
# The closed vocabularies
# ---------------------------------------------------------------------------

def test_failure_classes_are_exactly_four():
    assert FAILURE_CLASSES == (A_EXTRACTION, B_STRUCTURE, C_VALIDATION, NO_FAILURE)
    assert FAILURE_CLASSES == ("A", "B", "C", "")


def test_the_mirrored_telemetry_vocabulary_matches_exactly():
    from telemetry.record import FAILURE_CLASSES as TELEMETRY_FAILURE_CLASSES

    assert TELEMETRY_FAILURE_CLASSES == FAILURE_CLASSES


def test_both_vocabularies_are_exported_from_the_telemetry_package():
    """P20-ROUTER review, MAJOR-3: exported beside `DEFERRED_REASONS`, not
    reachable only through `telemetry.record`."""
    import telemetry

    assert telemetry.FAILURE_CLASSES == FAILURE_CLASSES
    assert telemetry.EXTRACTION_TRIGGERS == EXTRACTION_TRIGGERS
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
    for trigger in ("",) + EXTRACTION_TRIGGERS:
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

    claimable = cached_markdown(_scan_bytes(), ROOT / "tests" / "corpus_cache")
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

    claimable = cached_markdown(_scan_bytes(), ROOT / "tests" / "corpus_cache")
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
# preflight (tests/test_webapp_worker.py).
# ---------------------------------------------------------------------------
