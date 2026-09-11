"""P22-TRUTHTABLE item 1: the layered unresolved-reason taxonomy (L0-L6).

Written BEFORE `telemetry/unresolved_taxonomy.py` existed (TDD order). The
properties, each enforced by a mechanism rather than a comment:

* one code per layer, the PRIMARY reason = the highest-RANKED (most upstream)
  non-empty layer — the W3-2 idiom (`CLASS_PRECEDENCE` "ranked most-upstream
  first; the primary class is the highest-ranked class present"), so a
  `STATEMENT_PARTIAL{missing_pages}` that was also withheld for detail
  coverage is reported by the missing pages (cause) and not by the arithmetic
  that noticed them (symptom) — mutant M1 (the LOWEST-ranked layer wins) is
  killed by `test_the_primary_reason_is_the_most_upstream_non_empty_layer`;
* closed vocabularies per layer, each with an explicit `unmapped` bucket; an
  unknown runner reason lands in `unmapped` at runtime AND fails the drift
  guard that reads the runner's source (mutant M2: a reason injected into a
  SCRATCH copy of `discovery/runner.py` is reported by the pure guard
  function, the tree untouched);
* the precedence table in the module docstring is asserted equal to the code;
* the classifier's `KINDS` / `SUB_KINDS` / `FINDING_CODES`, the W3-2 classes
  and the extraction gate's reasons are each read from their source and
  asserted covered;
* L2 / L3 are populated ONLY from facts the row carries (never inferred).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from telemetry import diagnostics as diagnostics_module
from telemetry.unresolved_taxonomy import (
    EVIDENCE_REASON_CODE,
    L0_CODES,
    L1_KINDS,
    L2_CODES,
    L3_CODES,
    L4_CODES,
    L5_CODES,
    L6_CODES,
    LAYER_NAMES,
    LAYER_PRECEDENCE,
    LAYERS,
    REASON_LAYER,
    UNMAPPED,
    UNRESOLVED_TAXONOMY_VERSION,
    VOCABULARY,
    KindFacts,
    UnresolvedDiagnosis,
    diagnose_unresolved,
    kind_facts_from_document_class,
    parse_l1_code,
    runner_reason_literals,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# fixtures: a row is a mapping (rows.csv) or an attribute object (DocumentRow)
# ---------------------------------------------------------------------------


def _row(**overrides) -> dict:
    row = {
        "outcome_class": "failed", "outcome_reason": "no_parser_matched", "valid_pdf": True,
        "encrypted": False, "evidence_quality": "none", "truncated_pages": 0,
        "failure_class": "B", "dispatch_outcome": "unclaimed",
    }
    row.update(overrides)
    return row


def _diag(primary: str | None, *codes: str, evaluated: bool = True) -> dict:
    return {"evaluated": evaluated, "primary_class": primary, "classes": [primary] if primary else [],
            "codes": list(codes), "diagnostics_version": diagnostics_module.DIAGNOSTICS_VERSION}


COMPLETE = KindFacts(kind="STATEMENT_COMPLETE", sub_kind=None, findings=())
PARTIAL_PAGES = KindFacts(kind="STATEMENT_PARTIAL", sub_kind=None, findings=("missing_pages",))
LOAN = KindFacts(kind="NOT_A_STATEMENT", sub_kind="loan_statement", findings=())


# ---------------------------------------------------------------------------
# the shape
# ---------------------------------------------------------------------------


def test_the_version_is_one_and_travels_in_every_diagnosis():
    assert UNRESOLVED_TAXONOMY_VERSION == 1
    diagnosis = diagnose_unresolved(_row(), None, COMPLETE)
    assert diagnosis.version == UNRESOLVED_TAXONOMY_VERSION
    assert diagnosis.as_row_fields()["unresolved_taxonomy_version"] == 1


def test_layers_are_l0_to_l6_in_order_and_every_layer_is_closed_with_unmapped():
    assert LAYERS == ("l0", "l1", "l2", "l3", "l4", "l5", "l6")
    assert LAYER_PRECEDENCE == LAYERS
    assert set(LAYER_NAMES) == set(LAYERS)
    for layer in LAYERS:
        assert UNMAPPED in VOCABULARY[layer], layer
        assert len(set(VOCABULARY[layer])) == len(VOCABULARY[layer]), f"{layer} repeats a code"
    assert VOCABULARY["l0"] == L0_CODES + (UNMAPPED,)
    assert VOCABULARY["l2"] == L2_CODES + (UNMAPPED,)
    assert VOCABULARY["l3"] == L3_CODES + (UNMAPPED,)
    assert VOCABULARY["l5"] == L5_CODES + (UNMAPPED,)
    assert VOCABULARY["l6"] == L6_CODES + (UNMAPPED,)


def test_the_vocabulary_carries_the_plan_d4_codes():
    """PHASE2_REMAINDER_PLAN §D.4, verbatim members."""
    assert set(L0_CODES) == {"FILE_INVALID", "FILE_ENCRYPTED"}
    assert set(L1_KINDS) == {"NOT_A_STATEMENT", "ACTIVITY_EXPORT", "STATEMENT_PARTIAL",
                             "STATEMENT_ILLEGIBLE", "KIND_UNCERTAIN"}
    assert [code[:2] for code in L2_CODES] == ["E0", "E1", "E2", "E3", "E4", "E5"]
    assert [code[:2] for code in L3_CODES if code[:2] != "B0"] == ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    assert {"q3_sibling_omission_refusal", "currency_package_refusal", "not_a_formal_statement",
            "declined_by_claiming_reader", "pinned_adjudicated_refusal"} == set(L5_CODES)


def test_row_fields_carry_one_code_per_layer_and_the_primary_pair():
    fields = diagnose_unresolved(_row(), None, LOAN).as_row_fields()
    assert list(fields) == [
        "reason_l0", "reason_l1", "reason_l2", "reason_l3", "reason_l4", "reason_l5", "reason_l6",
        "primary_reason_layer", "primary_reason", "unresolved_taxonomy_version",
    ]


# ---------------------------------------------------------------------------
# precedence: the most upstream non-empty layer is the primary reason
# ---------------------------------------------------------------------------


def test_the_primary_reason_is_the_most_upstream_non_empty_layer():
    """M1's killer. L1 (a partial statement) and L4 (detail coverage) are
    both present; the primary is L1 — the cause — never L4."""
    diagnosis = diagnose_unresolved(
        _row(outcome_class="withheld", outcome_reason="withheld_adb", failure_class="C",
             dispatch_outcome="claimed"),
        _diag("detail_coverage", "recon:debit_coverage_short"),
        PARTIAL_PAGES,
    )
    assert diagnosis.reason_l1 == "STATEMENT_PARTIAL{missing_pages}"
    assert diagnosis.reason_l4 == "detail_coverage"
    assert diagnosis.primary_layer == "l1"
    assert diagnosis.primary_code == "STATEMENT_PARTIAL{missing_pages}"


def test_l0_outranks_every_other_layer():
    diagnosis = diagnose_unresolved(
        _row(outcome_class="failed", outcome_reason="invalid_pdf", valid_pdf=False, failure_class=""),
        None, KindFacts(kind="FILE_INVALID", sub_kind=None, findings=()),
    )
    assert diagnosis.reason_l0 == "FILE_INVALID"
    assert (diagnosis.primary_layer, diagnosis.primary_code) == ("l0", "FILE_INVALID")


def test_an_encrypted_file_is_l0_from_the_row_fact():
    diagnosis = diagnose_unresolved(
        _row(outcome_reason="encrypted", encrypted=True, failure_class=""), None, None)
    assert (diagnosis.primary_layer, diagnosis.primary_code) == ("l0", "FILE_ENCRYPTED")


def test_the_precedence_table_in_the_module_docstring_matches_the_code():
    """The W3-2 idiom: the table is asserted equal to the code, order and
    numbering included, so the two cannot drift."""
    import telemetry.unresolved_taxonomy as module

    rows = re.findall(r"^\s*\|\s*(\d+)\s*\|\s*(l\d)\s*\|\s*([A-Z]+)\s*\|", module.__doc__, re.MULTILINE)
    assert rows, "no precedence table found in the module docstring"
    expected = [(str(rank), layer, LAYER_NAMES[layer]) for rank, layer in enumerate(LAYER_PRECEDENCE, 1)]
    assert rows == expected


# ---------------------------------------------------------------------------
# per-layer population, from facts the row already carries
# ---------------------------------------------------------------------------


def test_a_validated_document_carries_no_reason_at_all():
    diagnosis = diagnose_unresolved(
        _row(outcome_class="validated", outcome_reason="approved", failure_class="", dispatch_outcome="claimed"),
        _diag(None, evaluated=False), PARTIAL_PAGES,
    )
    assert diagnosis == UnresolvedDiagnosis(
        reason_l0="", reason_l1="", reason_l2="", reason_l3="", reason_l4="", reason_l5="", reason_l6="",
        primary_layer="", primary_code="", version=UNRESOLVED_TAXONOMY_VERSION,
    )


def test_l1_renders_the_sub_kind_and_the_sorted_findings():
    assert diagnose_unresolved(_row(), None, LOAN).reason_l1 == "NOT_A_STATEMENT{loan_statement}"
    partial = KindFacts(kind="STATEMENT_PARTIAL", sub_kind=None,
                        findings=("table_truncated", "missing_closing", "table_truncated"))
    assert diagnose_unresolved(_row(), None, partial).reason_l1 == "STATEMENT_PARTIAL{missing_closing;table_truncated}"
    assert diagnose_unresolved(_row(), None, KindFacts("ACTIVITY_EXPORT", None, ())).reason_l1 == "ACTIVITY_EXPORT"
    assert diagnose_unresolved(_row(), None, COMPLETE).reason_l1 == ""


def test_a_complete_unclaimed_statement_is_l3_b0_the_coarse_class_b_fact():
    diagnosis = diagnose_unresolved(_row(), None, COMPLETE)
    assert diagnosis.reason_l3 == "B0_no_reader_claimed"
    assert (diagnosis.primary_layer, diagnosis.primary_code) == ("l3", "B0_no_reader_claimed")


def test_a_not_a_statement_that_no_parser_matched_is_primary_l1_with_l3_visible():
    diagnosis = diagnose_unresolved(_row(), None, LOAN)
    assert diagnosis.primary_layer == "l1"
    assert diagnosis.reason_l3 == "B0_no_reader_claimed"


def test_a_declined_document_is_l5_declined_by_claiming_reader():
    diagnosis = diagnose_unresolved(_row(outcome_reason="parser_declined"), None, COMPLETE)
    assert diagnosis.reason_l3 == ""
    assert (diagnosis.primary_layer, diagnosis.primary_code) == ("l5", "declined_by_claiming_reader")


def test_l4_is_the_w3_2_primary_class_and_undiagnosed_when_nothing_was_evaluated():
    withheld = _row(outcome_class="withheld", outcome_reason="withheld_adb", failure_class="C",
                    dispatch_outcome="claimed")
    assert diagnose_unresolved(withheld, _diag("ledger_identity"), COMPLETE).reason_l4 == "ledger_identity"
    assert diagnose_unresolved(withheld, None, COMPLETE).reason_l4 == "undiagnosed"
    assert diagnose_unresolved(withheld, _diag(None, evaluated=False), COMPLETE).reason_l4 == "undiagnosed"
    assert diagnose_unresolved(withheld, _diag("a_class_this_module_never_saw"), COMPLETE).reason_l4 == UNMAPPED


def test_l5_reads_the_doctrine_facts():
    review = _row(outcome_class="review", outcome_reason="integrity_flags", failure_class="C",
                  dispatch_outcome="claimed")
    diagnosis = diagnose_unresolved(review, _diag("advisory_only", "integrity:not_a_formal_statement"), COMPLETE)
    assert diagnosis.reason_l5 == "not_a_formal_statement"
    q3 = diagnose_unresolved(_row(outcome_reason="q3_provenance_refused"), None, COMPLETE)
    assert q3.reason_l5 == "q3_sibling_omission_refusal"
    omission = diagnose_unresolved(_row(outcome_reason="document_omission_unratified"), None, COMPLETE)
    assert omission.reason_l5 == "q3_sibling_omission_refusal"


def test_l2_is_populated_from_the_gate_reasons_and_the_truncation_fact_only():
    unusable = _row(outcome_reason="no_parser_matched", evidence_quality="unusable", failure_class="A")
    assert diagnose_unresolved(unusable, None, COMPLETE, evidence_reasons=("below_char_floor",)).reason_l2 == "E1_coverage_gap"
    assert diagnose_unresolved(unusable, None, COMPLETE, evidence_reasons=("no_text_produced",)).reason_l2 == "E0_no_evidence"
    # both present: the most upstream E-code of the layer wins
    both = diagnose_unresolved(unusable, None, COMPLETE, evidence_reasons=("below_char_floor", "all_pages_empty"))
    assert both.reason_l2 == "E0_no_evidence"
    # unusable with no reason supplied is loud, never guessed
    assert diagnose_unresolved(unusable, None, COMPLETE).reason_l2 == UNMAPPED
    truncated = diagnose_unresolved(_row(truncated_pages=2), None, COMPLETE)
    assert truncated.reason_l2 == "E5_truncation_bleed"
    assert diagnose_unresolved(_row(outcome_class="deferred", outcome_reason="deferred_visual_ocr",
                                    failure_class="", dispatch_outcome=None), None, None).reason_l2 == "E0_no_evidence"
    # usable evidence, no truncation: nothing in L2
    assert diagnose_unresolved(_row(evidence_quality="usable"), None, COMPLETE).reason_l2 == ""


def test_l2_and_l3_are_never_inferred_from_a_kind_or_an_outcome_alone():
    """A `STATEMENT_ILLEGIBLE` kind is an L1 fact; it does not manufacture an
    E-code, and a withheld document does not manufacture a B-code."""
    illegible = diagnose_unresolved(_row(), None, KindFacts("STATEMENT_ILLEGIBLE", None, ()))
    assert illegible.reason_l2 == ""
    withheld = diagnose_unresolved(
        _row(outcome_class="withheld", outcome_reason="withheld_adb", failure_class="C", dispatch_outcome="claimed"),
        _diag("ledger_identity"), COMPLETE)
    assert withheld.reason_l3 == ""


def test_an_unknown_runner_reason_lands_in_l6_unmapped_never_nulled():
    diagnosis = diagnose_unresolved(_row(outcome_reason="a_reason_the_taxonomy_never_saw"), None, COMPLETE)
    assert diagnosis.reason_l6 == UNMAPPED
    assert (diagnosis.primary_layer, diagnosis.primary_code) == ("l6", UNMAPPED)


def test_a_document_fold_reason_is_read_through_its_account_prefix():
    assert diagnose_unresolved(_row(outcome_reason="account_parser_declined"), None, COMPLETE).reason_l5 == "declined_by_claiming_reader"


def test_deferred_and_exception_reasons_map_to_l6_facts():
    assert diagnose_unresolved(_row(outcome_class="deferred", outcome_reason="deferred_scanned", failure_class=""),
                               None, None).primary_code == "not_attempted_by_run"
    assert diagnose_unresolved(_row(outcome_reason="parser_exception"), None, COMPLETE).primary_code == "platform_exception"
    assert diagnose_unresolved(_row(outcome_reason="exception"), None, COMPLETE).primary_code == "platform_exception"


def test_every_reserved_refused_reason_maps_to_a_layer():
    from telemetry.record import REFUSED_REASONS

    for reason in REFUSED_REASONS:
        diagnosis = diagnose_unresolved(_row(outcome_class="refused", outcome_reason=reason, failure_class=""), None, None)
        assert diagnosis.primary_layer, reason
        assert diagnosis.primary_code != UNMAPPED, reason


def test_a_row_object_and_a_row_mapping_diagnose_identically():
    from discovery.runner import DocumentRow

    mapping = _row(outcome_reason="parser_declined")
    row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1,
                      outcome_class="failed", outcome_reason="parser_declined", failure_class="B",
                      dispatch_outcome="unclaimed")
    assert diagnose_unresolved(row, None, COMPLETE) == diagnose_unresolved(mapping, None, COMPLETE)


def test_kind_facts_from_a_real_document_class():
    from layout import DocumentProfileFacts, classify_document

    facts = DocumentProfileFacts(valid_pdf=False, encrypted=False, page_count=0, classification="unknown",
                                 page_text_chars=(), magic=None)
    verdict = classify_document(evidence=None, page_texts=None, profile=facts)
    assert kind_facts_from_document_class(verdict) == KindFacts("FILE_INVALID", None, ())
    assert kind_facts_from_document_class(None) is None


def test_parse_l1_code_round_trips_and_refuses_junk():
    assert parse_l1_code("NOT_A_STATEMENT{cheque_image}") == ("NOT_A_STATEMENT", ("cheque_image",))
    assert parse_l1_code("STATEMENT_PARTIAL{missing_closing;page_gap}") == ("STATEMENT_PARTIAL", ("missing_closing", "page_gap"))
    assert parse_l1_code("KIND_UNCERTAIN") == ("KIND_UNCERTAIN", ())
    for junk in ("STATEMENT_COMPLETE", "NOT_A_STATEMENT{made_up}", "STATEMENT_PARTIAL{}", "nonsense", ""):
        assert parse_l1_code(junk) is None, junk


# ---------------------------------------------------------------------------
# drift guards: every vocabulary is read from its source
# ---------------------------------------------------------------------------


def test_every_reason_the_runner_and_the_record_can_emit_is_in_the_reason_map():
    """The drift guard (M2's killer, with `runner_reason_literals` pure over
    source text). Every outcome reason literal the runner assigns, every
    reason `classify_outcome` / `classify_document` / `_failure_reason`
    return, every deferred reason and every refused reason is a key of
    `REASON_LAYER` — mapped to a layer, or explicitly `None` (the layer comes
    from another fact: the W3-2 diagnostics, or a validated outcome)."""
    from telemetry.record import DEFERRED_REASONS, REFUSED_REASONS

    literals = runner_reason_literals(
        (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8"),
        (ROOT / "telemetry" / "record.py").read_text(encoding="utf-8"),
    )
    assert literals, "the guard found no reason literal at all: it is vacuous"
    assert {"no_parser_matched", "parser_declined", "withheld_adb", "approved", "invalid_pdf"} <= literals
    expected = set(literals) | set(DEFERRED_REASONS) | set(REFUSED_REASONS)
    missing = sorted(expected - set(REASON_LAYER))
    assert not missing, f"runner/record reasons the taxonomy does not know: {missing}"
    stale = sorted(set(REASON_LAYER) - expected)
    assert not stale, f"REASON_LAYER names reasons nothing emits any more: {stale}"


def test_m2_a_reason_injected_into_a_scratch_copy_of_the_runner_is_reported():
    """M2 applied to a SCRATCH copy (the tree is never touched): the guard's
    pure function sees the new literal and it is not in `REASON_LAYER`."""
    runner = (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8")
    planted = runner.replace(
        'row.outcome_class, row.outcome_reason = "failed", "escalation_refused"',
        'row.outcome_class, row.outcome_reason = "failed", "brand_new_reason_nobody_mapped"',
        1,
    )
    assert planted != runner
    literals = runner_reason_literals(planted, (ROOT / "telemetry" / "record.py").read_text(encoding="utf-8"))
    assert "brand_new_reason_nobody_mapped" in literals
    assert "brand_new_reason_nobody_mapped" not in REASON_LAYER


def test_every_reason_map_entry_names_a_layer_code_in_that_layers_vocabulary():
    for reason, target in REASON_LAYER.items():
        if target is None:
            continue
        layer, code = target
        assert layer in LAYERS, reason
        assert code in VOCABULARY[layer] and code != UNMAPPED, (reason, target)


def test_the_classifier_vocabularies_are_covered():
    from layout.refusals import FINDING_CODES, KINDS, SUB_KINDS

    for kind in KINDS:
        if kind == "STATEMENT_COMPLETE":
            continue  # a complete statement is no kind-layer reason
        if kind == "FILE_INVALID":
            assert kind in L0_CODES
            continue
        assert kind in L1_KINDS, kind
    for sub_kind in SUB_KINDS:
        assert parse_l1_code(f"NOT_A_STATEMENT{{{sub_kind}}}") is not None, sub_kind
    for code in FINDING_CODES:
        assert parse_l1_code(f"STATEMENT_PARTIAL{{{code}}}") is not None, code
    # and a kind the classifier could grow that this module lacks is loud
    grown = KindFacts(kind="A_KIND_GROWN_LATER", sub_kind=None, findings=())
    assert diagnose_unresolved(_row(), None, grown).reason_l1 == UNMAPPED


def test_the_w3_2_classes_are_l4_unchanged():
    assert L4_CODES == diagnostics_module.CLASS_PRECEDENCE


def test_the_extraction_gate_reasons_are_covered():
    source = (ROOT / "ocr" / "escalation.py").read_text(encoding="utf-8")
    found = set(re.findall(r'reasons\.append\("([a-z_]+)"\)', source))
    found |= set(re.findall(r'reasons=\("([a-z_]+)",\)', source))
    assert found == {"no_text_produced", "below_char_floor", "all_pages_empty"}
    assert found == set(EVIDENCE_REASON_CODE)
    for code in EVIDENCE_REASON_CODE.values():
        assert code in L2_CODES


def test_the_guard_reads_real_return_shapes_not_only_plain_literals():
    """`_failure_reason` returns an `IfExp` and `classify_outcome` a tuple;
    the guard walks beneath a Return, so both shapes are seen."""
    tree = ast.parse((ROOT / "discovery" / "runner.py").read_text(encoding="utf-8"))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_failure_reason")
    assert any(isinstance(n, ast.IfExp) for n in ast.walk(func)), "the fixture premise moved"
    literals = runner_reason_literals(
        (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8"),
        (ROOT / "telemetry" / "record.py").read_text(encoding="utf-8"),
    )
    assert {"parser_declined", "no_parser_matched", "q3_provenance_refused", "exception", "no_analysis"} <= literals


def test_an_unresolved_row_always_has_a_primary_layer_never_a_nulled_one():
    """Review MINOR-4's killer (M20). The module's stated property — "L6
    UNKNOWN … itself a finding, never nulled" — must hold BY CONSTRUCTION, not
    because `telemetry/record.py` happens to pair every layer-less reason with
    a diagnosable class. This enumerates exactly the pairs the reviewer found
    nulled: every non-validated outcome class against every reason this module
    deliberately maps to no layer of its own."""
    from telemetry.record import OUTCOME_CLASSES

    layerless = sorted(reason for reason, target in REASON_LAYER.items() if target is None)
    assert layerless, "the fixture premise moved: no reason maps to None any more"
    pairs = [(outcome_class, reason)
             for outcome_class in (*OUTCOME_CLASSES, "unknown") if outcome_class != "validated"
             for reason in layerless]
    assert len(pairs) >= 20, f"the reviewer found 20 such pairs; this enumerates {len(pairs)}"
    nulled = []
    for outcome_class, reason in pairs:
        diagnosis = diagnose_unresolved(_row(outcome_class=outcome_class, outcome_reason=reason,
                                             failure_class="", dispatch_outcome=None), None, None)
        if not diagnosis.primary_layer or not diagnosis.primary_code:
            nulled.append((outcome_class, reason))
    assert nulled == [], f"a nulled primary reason for {len(nulled)} pairs: {nulled[:5]}"
    # and the word it lands on is the layer's OWN one, not the drift bucket
    lonely = diagnose_unresolved(
        _row(outcome_class="failed", outcome_reason="withheld_adb", failure_class="",
             dispatch_outcome=None), None, None)
    assert (lonely.primary_layer, lonely.primary_code) == ("l6", "unknown")
    assert "unknown" in L6_CODES and "unknown" != UNMAPPED
    # a VALIDATED document still carries no diagnosis at all — that path is the
    # one deliberate exception and it stays exactly as it was
    validated = diagnose_unresolved(
        _row(outcome_class="validated", outcome_reason="approved", failure_class="",
             dispatch_outcome="claimed"), None, None)
    assert validated == UnresolvedDiagnosis(
        reason_l0="", reason_l1="", reason_l2="", reason_l3="", reason_l4="", reason_l5="",
        reason_l6="", primary_layer="", primary_code="", version=UNRESOLVED_TAXONOMY_VERSION)


@pytest.mark.parametrize("layer", LAYERS)
def test_no_layer_vocabulary_carries_a_money_date_or_name_shape(layer):
    for code in VOCABULARY[layer]:
        assert re.fullmatch(r"[A-Za-z0-9_]+", code), code
