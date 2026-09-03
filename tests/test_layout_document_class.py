"""The deterministic document classifier (Phase 2.2 cell C; umbrella cases
1–5 and 24; `P22-CLASSIFY.md` §5–§6).

Every synthetic kind fixture in `tests/layout_fixtures` is classified in
BOTH input modes — words with boxes (`evidence`) and page strings only
(DEGRADED) — and owes the verdict its generator states: kind, sub-kind,
tier, the signal names that must be present, the ones that must be absent,
the completeness findings. The mutation table's killers are named in the
test docstrings (M1–M8, M10, M11); M9 and M12 live in the signals and
boundary files.
"""
from __future__ import annotations

import dataclasses
import random
import re
import time

import pytest

from evidence.canonical import ExtractionEvidence
from layout import (
    CLASSIFIER_VERSION,
    KINDS,
    DocumentClass,
    DocumentProfileFacts,
    EvidenceRef,
    Finding,
    classify_document,
)
from layout.refusals import ACCOUNT_KINDS, FINDING_CODES, LANGUAGES, MODALITIES, PRODUCED_SUB_KINDS, SUB_KINDS, TIERS
from layout.signals import SIGNALS
from tests.layout_fixtures import FIXTURES, Expect, LayoutFixture, build, names

MODES = ("evidence", "text")
BOX_DEPENDENT_SIGNALS = frozenset({"table_alignment", "micr_band", "cheque_aspect", "screenshot_frame"})
#: `Finding.detail` is a closed little grammar of `key=number` pairs — it
#: cannot carry a document word by construction (umbrella §"Classifier").
DETAIL_GRAMMAR = re.compile(r"^(?:[a-z_]+=[0-9./-]+(?:;[a-z_]+=[0-9./-]+)*)?$")


@pytest.fixture(scope="module")
def fixtures() -> dict[str, LayoutFixture]:
    return {name: build(name) for name in names()}


def _classify(fx: LayoutFixture, mode: str) -> DocumentClass:
    if mode == "evidence":
        assert fx.evidence is not None
        return classify_document(evidence=fx.evidence, page_texts=None, profile=fx.profile)
    return classify_document(evidence=None, page_texts=fx.page_texts, profile=fx.profile)


def _expectation(fx: LayoutFixture, mode: str) -> Expect | None:
    return fx.expect_evidence if mode == "evidence" else fx.expect_text


def _signal_names(verdict: DocumentClass) -> set[str]:
    return {ref.signal for ref in verdict.evidence}


def _finding_codes(verdict: DocumentClass) -> set[str]:
    return {finding.code for finding in verdict.completeness}


def _cases() -> list[tuple[str, str]]:
    return [(name, mode) for name in names() for mode in MODES]


# ---------------------------------------------------------------------------
# case 1 — every synthetic kind classifies with named evidence (both modes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,mode", _cases())
def test_every_fixture_owes_its_stated_verdict(fixtures, name, mode):
    fx = fixtures[name]
    expect = _expectation(fx, mode)
    if expect is None:
        pytest.skip(f"{name} has no {mode} form")
    verdict = _classify(fx, mode)
    signals = _signal_names(verdict)
    findings = _finding_codes(verdict)
    assert verdict.kind == expect.kind, (name, mode, verdict)
    assert verdict.sub_kind == expect.sub_kind, (name, mode, verdict)
    assert verdict.tier == expect.tier, (name, mode, verdict)
    missing = expect.signals - signals
    assert not missing, f"{name}/{mode}: expected signals missing {missing}; got {sorted(signals)}"
    present = expect.absent_signals & signals
    assert not present, f"{name}/{mode}: forbidden signals present {present}"
    missing_findings = expect.findings - findings
    assert not missing_findings, f"{name}/{mode}: expected findings missing {missing_findings}; got {sorted(findings)}"
    forbidden_findings = expect.absent_findings & findings
    assert not forbidden_findings, f"{name}/{mode}: forbidden findings present {forbidden_findings}"
    if expect.language is not None:
        assert verdict.language == expect.language, (name, mode, verdict.language)
    if expect.account_kind is not None:
        assert verdict.account_kind == expect.account_kind, (name, mode, verdict.account_kind)
    if expect.modality is not None:
        assert verdict.modality == expect.modality, (name, mode, verdict.modality)
    assert verdict.version == CLASSIFIER_VERSION == 1


@pytest.mark.parametrize("name,mode", _cases())
def test_every_verdict_is_well_formed_and_carries_only_closed_vocabulary(fixtures, name, mode):
    fx = fixtures[name]
    if _expectation(fx, mode) is None:
        pytest.skip(f"{name} has no {mode} form")
    verdict = _classify(fx, mode)
    assert verdict.kind in KINDS
    assert verdict.tier in TIERS
    assert verdict.modality in MODALITIES
    assert verdict.language in LANGUAGES
    assert verdict.account_kind in ACCOUNT_KINDS
    assert verdict.sub_kind is None or verdict.sub_kind in PRODUCED_SUB_KINDS
    if verdict.kind != "NOT_A_STATEMENT":
        assert verdict.sub_kind is None, "sub_kind is a NOT_A_STATEMENT refinement only"
    if verdict.kind != "STATEMENT_PARTIAL":
        assert verdict.completeness == (), "completeness findings belong to STATEMENT_PARTIAL alone"
    else:
        assert verdict.completeness, "STATEMENT_PARTIAL without a finding is not a partial"
    page_count = len(fx.pages) if fx.pages else 0
    for ref in verdict.evidence:
        assert isinstance(ref, EvidenceRef)
        assert ref.signal in SIGNALS, ref.signal
        assert ref.page >= 0
        if ref.signal != "file_invalid_fact":
            assert ref.page < max(1, page_count)
        if mode == "evidence" and ref.word_ids is not None:
            known = {w.word_id for page in fx.evidence.pages for w in page.words}
            assert set(ref.word_ids) <= known, ref
        if mode == "text" and ref.span is not None:
            assert ref.word_ids is None
            page_text = fx.page_texts[ref.page]
            assert 0 <= ref.span[0] < ref.span[1] <= len(page_text), ref
    for finding in verdict.completeness:
        assert isinstance(finding, Finding)
        assert finding.code in FINDING_CODES
        assert DETAIL_GRAMMAR.match(finding.detail), f"detail carries free text: {finding.detail!r}"
        assert finding.page is None or 0 <= finding.page < max(1, page_count)


@pytest.mark.parametrize("name", [n for n in names()])
def test_degraded_mode_never_emits_a_box_dependent_signal_and_never_a_structural_tier_for_one(fixtures, name):
    """Mutant M7's killer, over every fixture: with page strings only, the
    box-dependent signals cannot exist, and a `structural` tier may rest only
    on a fact that needs no box (a page-marker gap, the file facts)."""
    fx = fixtures[name]
    if fx.expect_text is None:
        pytest.skip("no text form")
    verdict = _classify(fx, "text")
    assert not (_signal_names(verdict) & BOX_DEPENDENT_SIGNALS), verdict
    if verdict.tier == "structural":
        assert verdict.kind == "FILE_INVALID" or (
            _finding_codes(verdict) & {"page_gap", "missing_pages", "missing_first_page"}
        ), f"{name}: a structural tier in degraded mode must rest on a page fact: {verdict}"


def test_the_text_only_complete_statement_is_lexical_never_structural(fixtures):
    """M7, the card's named form: the complete EN statement fed as text."""
    fx = fixtures["statement_complete_en"]
    verdict = _classify(fx, "text")
    assert verdict.kind == "STATEMENT_COMPLETE"
    assert verdict.tier == "lexical"
    assert "table_alignment" not in _signal_names(verdict)


# ---------------------------------------------------------------------------
# case 2 — KIND_UNCERTAIN is first-class, reachable, and the conflict verdict
# ---------------------------------------------------------------------------

def test_kind_uncertain_is_in_the_closed_vocabulary_and_reachable(fixtures):
    assert "KIND_UNCERTAIN" in KINDS
    assert _classify(fixtures["nothing_fires"], "evidence").kind == "KIND_UNCERTAIN"
    assert _classify(fixtures["nothing_fires"], "text").kind == "KIND_UNCERTAIN"


@pytest.mark.parametrize("name", ["conflict_table_and_cheque", "conflict_card_and_running_balance"])
@pytest.mark.parametrize("mode", MODES)
def test_conflicting_signals_refuse_to_guess(fixtures, name, mode):
    """Mutant M6's killer: a table signal beside a cheque signal, and a card
    lexicon beside a running balance, are `KIND_UNCERTAIN` — never resolved
    by priority. Both signals are still LISTED, so the adjudicator sees the
    conflict rather than a shrug."""
    verdict = _classify(fixtures[name], mode)
    assert verdict.kind == "KIND_UNCERTAIN", verdict
    assert verdict.tier == "uncertain"
    assert verdict.sub_kind is None
    signals = _signal_names(verdict)
    if name == "conflict_table_and_cheque":
        assert "table_run" in signals and (signals & {"micr_band", "micr_shape"})
    else:
        assert {"card_lexicon", "running_balance"} <= signals


def test_a_letter_whose_dated_lines_do_not_align_is_not_a_statement(fixtures):
    """Mutant M5's killer: six prose lines each with a date and a figure at
    drifting x positions. With boxes, no aligned money column → no table →
    the letter lexicon decides. Without boxes, honesty is `KIND_UNCERTAIN`."""
    fx = fixtures["letter_with_unaligned_dated_lines"]
    with_boxes = _classify(fx, "evidence")
    assert with_boxes.kind == "NOT_A_STATEMENT" and with_boxes.sub_kind == "letter_or_notice"
    assert "table_run" not in _signal_names(with_boxes)
    text_only = _classify(fx, "text")
    assert text_only.kind == "KIND_UNCERTAIN"
    assert "table_run" in _signal_names(text_only)


# ---------------------------------------------------------------------------
# case 3 — the cheque image: MICR band + aspect → structural; without MICR never
# ---------------------------------------------------------------------------

def test_cheque_image_is_structural_only_with_micr_in_the_band_and_a_cheque_aspect(fixtures):
    """Mutant M1's killer (drop the MICR rule → no longer structural) and
    M2's (drop the aspect bound → a portrait page with a MICR line would
    become a structural cheque)."""
    cheque = _classify(fixtures["cheque_image"], "evidence")
    assert (cheque.kind, cheque.sub_kind, cheque.tier) == ("NOT_A_STATEMENT", "cheque_image", "structural")
    assert {"micr_band", "cheque_aspect"} <= _signal_names(cheque)

    no_micr = _classify(fixtures["cheque_no_micr"], "evidence")
    assert no_micr.tier != "structural"
    assert no_micr.kind in ("KIND_UNCERTAIN", "NOT_A_STATEMENT")
    assert "micr_band" not in _signal_names(no_micr)

    bare = _classify(fixtures["cheque_shape_nothing_else"], "evidence")
    assert bare.kind == "KIND_UNCERTAIN"

    portrait = _classify(fixtures["cheque_portrait_micr"], "evidence")
    assert portrait.tier != "structural"
    assert "cheque_aspect" not in _signal_names(portrait)


def test_voided_cheque_needs_the_void_lexicon_on_a_cheque_page(fixtures):
    voided = _classify(fixtures["voided_cheque"], "evidence")
    assert (voided.kind, voided.sub_kind, voided.tier) == ("NOT_A_STATEMENT", "voided_cheque", "structural")
    assert "void_lexicon" in _signal_names(voided)
    plain = _classify(fixtures["cheque_image"], "evidence")
    assert plain.sub_kind == "cheque_image"
    assert "void_lexicon" not in _signal_names(plain)


def test_cheque_fixture_files_are_an_image_only_pdf_of_cheque_proportions(fixtures):
    import fitz

    fx = fixtures["cheque_image"]
    image_pdf = fx.image_pdf()
    assert image_pdf and image_pdf.startswith(b"%PDF")
    doc = fitz.open(stream=image_pdf, filetype="pdf")
    try:
        assert doc.page_count == 1
        page = doc[0]
        assert 2.0 <= page.rect.width / page.rect.height <= 2.6
        assert page.get_text("words") == []   # no text layer: the raster is all there is
    finally:
        doc.close()
    native = fitz.open(stream=fx.native_pdf, filetype="pdf")
    try:
        assert native.page_count == 1 and native[0].get_text("words")
    finally:
        native.close()


# ---------------------------------------------------------------------------
# case 4 — partial statements carry the finding that names what is missing
# ---------------------------------------------------------------------------

def test_a_page_gap_is_a_partial_with_the_page_gap_finding(fixtures):
    """Mutant M3's killer (drop `Page X of Y` gap detection)."""
    for mode in MODES:
        verdict = _classify(fixtures["partial_page_removed"], mode)
        assert verdict.kind == "STATEMENT_PARTIAL"
        codes = _finding_codes(verdict)
        assert "page_gap" in codes, (mode, verdict)
        gap = next(f for f in verdict.completeness if f.code == "page_gap")
        assert gap.detail and "declared=3" in gap.detail and "observed=2" in gap.detail


@pytest.mark.parametrize("name,code", [
    ("partial_opening_removed", "missing_opening"),
    ("partial_closing_removed", "missing_closing"),
    ("partial_period_removed", "missing_period"),
])
@pytest.mark.parametrize("mode", MODES)
def test_a_removed_anchor_is_a_partial_never_a_complete_statement(fixtures, name, code, mode):
    """Mutant M4's killer: `STATEMENT_COMPLETE` needs ALL THREE anchors. A
    mutant accepting two of three would call each of these complete."""
    verdict = _classify(fixtures[name], mode)
    assert verdict.kind == "STATEMENT_PARTIAL", (name, mode, verdict)
    assert code in _finding_codes(verdict)
    other = {"missing_opening", "missing_closing", "missing_period"} - {code}
    assert not (other & _finding_codes(verdict)), (name, mode, verdict)


def test_a_running_balance_discontinuity_at_a_page_break_is_a_partial(fixtures):
    for mode in MODES:
        verdict = _classify(fixtures["partial_balance_discontinuity"], mode)
        assert verdict.kind == "STATEMENT_PARTIAL", (mode, verdict)
        finding = next(f for f in verdict.completeness if f.code == "balance_discontinuity_at_page_break")
        assert finding.page == 1
        assert "page_break=0/1" in finding.detail
    complete = _classify(fixtures["statement_complete_en"], "evidence")
    assert "balance_discontinuity_at_page_break" not in _finding_codes(complete)


def test_missing_last_and_first_pages_are_named_by_the_marker_facts(fixtures):
    last = _classify(fixtures["partial_last_page_removed"], "evidence")
    assert {"missing_pages", "missing_closing"} <= _finding_codes(last)
    assert "page_gap" not in _finding_codes(last)
    first = _classify(fixtures["partial_first_page_removed"], "evidence")
    assert {"missing_first_page", "missing_period", "missing_opening"} <= _finding_codes(first)


# ---------------------------------------------------------------------------
# the remaining kinds, explicitly
# ---------------------------------------------------------------------------

def test_the_activity_export_rule_never_requires_an_anchor(fixtures):
    """Mutant M11's killer: the export fixture carries NO period, opening or
    closing anchor and must still be `ACTIVITY_EXPORT`."""
    for mode in MODES:
        verdict = _classify(fixtures["activity_export"], mode)
        assert verdict.kind == "ACTIVITY_EXPORT", (mode, verdict)
        signals = _signal_names(verdict)
        assert not (signals & {"period_expression", "opening_balance_label", "closing_balance_label"})
        assert {"reverse_chronology", "pending_row"} <= signals


def test_the_java_magic_file_is_invalid_before_any_text_signal_is_read(fixtures):
    """Mutant M10's killer: the fixture hands the classifier a COMPLETE
    statement's page texts beside an invalid profile; the profile decides."""
    fx = fixtures["file_invalid_java"]
    verdict = classify_document(evidence=None, page_texts=fx.page_texts, profile=fx.profile)
    assert verdict.kind == "FILE_INVALID"
    assert verdict.tier == "structural"
    assert verdict.modality == "unknown"
    assert _signal_names(verdict) == {"file_invalid_fact"}
    assert verdict.completeness == ()
    assert fx.extra["file_bytes"][:4].hex().upper() == fx.profile.magic == "ACED0005"


@pytest.mark.parametrize("facts", [
    dict(valid_pdf=False, encrypted=False, page_count=3, classification="unknown"),
    dict(valid_pdf=True, encrypted=True, page_count=3, classification="unknown"),
    dict(valid_pdf=True, encrypted=False, page_count=0, classification="unknown"),
    dict(valid_pdf=True, encrypted=False, page_count=3, classification="digital", magic="ACED0005"),
])
def test_file_invalid_derives_from_the_facts_alone(fixtures, facts):
    statement = fixtures["statement_complete_en"]
    facts = {"magic": statement.profile.magic, "page_text_chars": statement.profile.page_text_chars, **facts}
    profile = DocumentProfileFacts(**facts)
    verdict = classify_document(evidence=statement.evidence, page_texts=None, profile=profile)
    assert verdict.kind == "FILE_INVALID", (facts, verdict)


def test_a_valid_profile_with_a_complete_statement_is_not_file_invalid(fixtures):
    assert _classify(fixtures["statement_complete_en"], "evidence").kind == "STATEMENT_COMPLETE"


def test_the_illegible_placeholder_fires_only_below_the_usable_floor(fixtures):
    from layout.document_class import ILLEGIBLE_EXPECTED_WORDS_PER_PAGE, ILLEGIBLE_FLOOR_VERSION, ILLEGIBLE_RATIO

    assert ILLEGIBLE_FLOOR_VERSION == 1
    assert 0.0 < ILLEGIBLE_RATIO < 1.0 and ILLEGIBLE_EXPECTED_WORDS_PER_PAGE > 0
    verdict = _classify(fixtures["statement_illegible"], "text")
    assert verdict.kind == "STATEMENT_ILLEGIBLE"
    assert "illegible_floor" in _signal_names(verdict)
    # The zero-activity statement is just as thin, but its printed
    # declaration stands in for the table — it must stay COMPLETE.
    zero = _classify(fixtures["statement_zero_activity"], "text")
    assert zero.kind == "STATEMENT_COMPLETE"


def test_the_rotated_statement_classifies_from_hand_built_display_frame_evidence(fixtures):
    import fitz

    fx = fixtures["statement_rotated"]
    assert all(page.frame.rotation_deg == 90 for page in fx.evidence.pages)
    verdict = _classify(fx, "evidence")
    assert (verdict.kind, verdict.tier) == ("STATEMENT_COMPLETE", "structural")
    doc = fitz.open(stream=fx.native_pdf, filetype="pdf")
    try:
        assert doc.page_count == 1 and doc[0].rotation == 90
        # The display rect is landscape — the frame the evidence was built in.
        assert doc[0].rect.width > doc[0].rect.height
    finally:
        doc.close()


def test_generalization_across_the_three_languages(fixtures):
    for name, language in (("statement_complete_en", "en"), ("statement_complete_fr", "fr"), ("statement_complete_es", "es")):
        for mode in MODES:
            verdict = _classify(fixtures[name], mode)
            assert verdict.kind == "STATEMENT_COMPLETE", (name, mode, verdict)
            assert verdict.language == language, (name, mode, verdict.language)
            assert verdict.account_kind == "deposit"


def test_the_two_layout_archetypes_both_classify_complete(fixtures):
    for name in ("statement_two_money_columns", "statement_single_signed_column"):
        for mode in MODES:
            verdict = _classify(fixtures[name], mode)
            assert verdict.kind == "STATEMENT_COMPLETE", (name, mode, verdict)
            assert "running_balance" in _signal_names(verdict)


def test_the_native_pdf_of_the_complete_statement_round_trips_through_the_platform_native_reader(fixtures):
    """The fixture's hand-built boxes are not the only path: the rendered
    PDF read back through the one native reader the platform has today
    (`analysis/structurer/geometry.py::native_evidence_from_pdf`, Phase 2.1)
    yields the SAME verdict — the classifier works on real reader output,
    not only on the generator's idea of it. (A test-side import of
    `analysis`; the classifier itself never imports it.)"""
    from analysis.structurer.geometry import native_evidence_from_pdf

    fx = fixtures["statement_complete_en"]
    evidence = native_evidence_from_pdf(fx.native_pdf)
    assert isinstance(evidence, ExtractionEvidence)
    verdict = classify_document(evidence=evidence, page_texts=None, profile=fx.profile)
    assert (verdict.kind, verdict.tier) == ("STATEMENT_COMPLETE", "structural"), verdict
    assert "table_alignment" in _signal_names(verdict)


def test_screenshot_needs_a_frame(fixtures):
    fx = fixtures["screenshot_image"]
    framed = _classify(fx, "evidence")
    assert (framed.kind, framed.sub_kind, framed.tier) == ("NOT_A_STATEMENT", "screenshot", "structural")
    text = _classify(fx, "text")
    assert text.kind == "KIND_UNCERTAIN"
    import fitz

    doc = fitz.open(stream=fx.image_pdf(), filetype="pdf")
    try:
        assert doc.page_count == 1 and doc[0].get_text("words") == []
        assert doc[0].rect.width / 72.0 > 15.0   # inches: no paper size is this wide
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# case 5 — purity; the contract's shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,mode", _cases())
def test_classify_document_is_pure(fixtures, name, mode, monkeypatch):
    """Mutant M8's killer: two calls on the same inputs are equal, and any
    clock or randomness consulted raises (every such function is replaced
    with a bomb for the duration of the call)."""
    fx = fixtures[name]
    if _expectation(fx, mode) is None:
        pytest.skip(f"{name} has no {mode} form")

    def boom(*args, **kwargs):
        raise AssertionError("classify_document consulted a clock or a random source")

    for target, attr in ((random, "random"), (random, "randint"), (random, "choice"), (random, "shuffle"),
                         (time, "time"), (time, "monotonic"), (time, "perf_counter"), (time, "time_ns")):
        monkeypatch.setattr(target, attr, boom)
    first = _classify(fx, mode)
    second = _classify(fx, mode)
    assert first == second
    assert hash(first) == hash(second)


def test_the_contract_types_are_frozen_and_the_vocabulary_is_closed():
    assert KINDS == ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
                     "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN")
    assert CLASSIFIER_VERSION == 1
    for cls in (DocumentClass, DocumentProfileFacts, Finding, EvidenceRef):
        assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen, cls
    assert [f.name for f in dataclasses.fields(DocumentProfileFacts)] == [
        "valid_pdf", "encrypted", "page_count", "classification", "page_text_chars", "magic"]
    assert [f.name for f in dataclasses.fields(DocumentClass)] == [
        "kind", "sub_kind", "modality", "language", "account_kind", "completeness", "evidence", "tier", "version"]
    assert [f.name for f in dataclasses.fields(Finding)] == ["code", "page", "detail"]
    assert [f.name for f in dataclasses.fields(EvidenceRef)] == ["page", "word_ids", "span", "signal"]
    assert FINDING_CODES == ("missing_pages", "missing_opening", "missing_closing", "missing_period",
                             "missing_first_page", "table_truncated", "page_gap", "balance_discontinuity_at_page_break")
    assert set(PRODUCED_SUB_KINDS) <= set(SUB_KINDS)
    assert TIERS == ("structural", "lexical", "uncertain")
    assert MODALITIES == ("digital", "scanned", "mixed", "image_backed_text", "unknown")
    assert LANGUAGES == ("en", "fr", "es", "unknown")
    assert ACCOUNT_KINDS == ("deposit", "card", "loan", "brokerage", "unknown")


def test_the_contract_refuses_a_value_outside_its_vocabulary():
    with pytest.raises(ValueError):
        DocumentClass(kind="STATEMENT_MAYBE", sub_kind=None, modality="digital", language="en", account_kind="unknown",
                      completeness=(), evidence=(), tier="lexical", version=CLASSIFIER_VERSION)
    with pytest.raises(ValueError):
        Finding(code="missing_everything", page=None, detail="")
    with pytest.raises(ValueError):
        Finding(code="missing_pages", page=None, detail="Ending Balance 500.00")
    with pytest.raises(ValueError):
        EvidenceRef(page=0, word_ids=None, span=None, signal="a signal that is not closed")
    with pytest.raises(ValueError):
        DocumentProfileFacts(valid_pdf=True, encrypted=False, page_count=1, classification="native",
                             page_text_chars=(1,), magic=None)


def test_classify_document_is_keyword_only_and_refuses_both_inputs_at_once(fixtures):
    fx = fixtures["statement_complete_en"]
    with pytest.raises(TypeError):
        classify_document(fx.evidence, None, fx.profile)  # type: ignore[misc]
    with pytest.raises(ValueError):
        classify_document(evidence=fx.evidence, page_texts=fx.page_texts, profile=fx.profile)


def test_no_inputs_at_all_is_uncertain_not_a_crash(fixtures):
    profile = fixtures["statement_complete_en"].profile
    verdict = classify_document(evidence=None, page_texts=None, profile=profile)
    assert verdict.kind == "KIND_UNCERTAIN" and verdict.tier == "uncertain"
    verdict = classify_document(evidence=None, page_texts=("", ""), profile=profile)
    assert verdict.kind == "KIND_UNCERTAIN"


def test_every_produced_sub_kind_has_a_fixture(fixtures):
    produced = set()
    for fx in fixtures.values():
        for mode in MODES:
            if _expectation(fx, mode) is None:
                continue
            verdict = _classify(fx, mode)
            if verdict.sub_kind:
                produced.add(verdict.sub_kind)
    assert produced == set(PRODUCED_SUB_KINDS), produced


def test_every_kind_has_a_fixture(fixtures):
    seen = set()
    for fx in fixtures.values():
        for mode in MODES:
            if _expectation(fx, mode) is not None:
                seen.add(_classify(fx, mode).kind)
    assert seen == set(KINDS), seen
