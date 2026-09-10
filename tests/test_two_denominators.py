"""P22-TRUTHTABLE items 3, 4, 5 (R11 / R12 / D2 / cases 6-8, 11, 25): the two
denominators in the discovery report, the disjoint primary classification, the
diagnostic labels reported beside it and never summed with it, the funnel and
technical-telemetry columns, and the no-cost grep.

Rows here are CONSTRUCTED `DocumentRow`s (no document, no archive): the
report is a pure function of rows and these tests assert its arithmetic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from discovery.report import ROW_FIELDS, render_report, summarize, write_rows, write_summary
from discovery.runner import MODE_DIGITAL, MODE_RESEARCH_PADDLE, DocumentRow
from layout.refusals import KINDS, MODALITIES, TIERS

FORBIDDEN_TOKENS = {"cost", "price", "rate", "usd", "billing"}


def _row(sha: str, **overrides) -> DocumentRow:
    base = dict(relative_path=f"F/{sha[:4]}.pdf", folder_label="F", content_sha256=sha, byte_size=1,
                document_class="STATEMENT_COMPLETE", class_modality="digital", class_tier="structural",
                class_account_kind="deposit", outcome_class="validated", outcome_reason="approved",
                dispatch_outcome="claimed", parser_id="chase", source_path="native")
    base.update(overrides)
    return DocumentRow(**base)


def _sha(i: int) -> str:
    return f"{i:064X}"


def _rows() -> list[DocumentRow]:
    rows = [
        _row(_sha(1)),
        _row(_sha(1), relative_path="F/dup.pdf", dedup_status="duplicate"),  # the same bytes twice: ONE sha
        _row(_sha(2)),
        _row(_sha(3), document_class="STATEMENT_PARTIAL", class_tier="lexical",
             outcome_class="failed", outcome_reason="no_parser_matched", dispatch_outcome="unclaimed",
             parser_id=None, failure_class="B", source_path="local_tesseract"),
        _row(_sha(4), document_class="NOT_A_STATEMENT", class_sub_kind="loan_statement", class_tier="lexical",
             class_account_kind="loan", outcome_class="failed", outcome_reason="no_parser_matched",
             dispatch_outcome="unclaimed", parser_id=None, failure_class="B", truncated_pages=1),
        _row(_sha(5), document_class="STATEMENT_COMPLETE", class_account_kind="card",
             outcome_class="withheld", outcome_reason="withheld_adb", failure_class="C"),
        _row(_sha(6), document_class="KIND_UNCERTAIN", class_modality="scanned", class_tier="uncertain",
             class_account_kind="unknown", outcome_class="deferred", outcome_reason="deferred_visual_ocr",
             dispatch_outcome=None, parser_id=None, source_path="none"),
        _row(_sha(7), document_class="STATEMENT_COMPLETE", outcome_class="validated"),
    ]
    return rows


def test_raw_coverage_is_validated_over_distinct_shas_and_is_printed_first():
    """Case 11 / M17: the raw denominator is the distinct-sha count of the
    archive (3,380 on the run of record — here 7 shas over 8 rows), printed
    FIRST and never replaced by a CCL figure."""
    summary = summarize(_rows(), mode=MODE_DIGITAL, run_id="r")
    assert summary["raw_coverage"] == {"validated": 3, "denominator": 7, "coverage": pytest.approx(3 / 7)}
    assert summary["ccl_adjudicated"] == "not available in this process"
    text = render_report(summary)
    lines = text.splitlines()
    raw = next(i for i, line in enumerate(lines) if line.startswith("raw coverage"))
    ccl_a = next(i for i, line in enumerate(lines) if "ccl_adjudicated" in line)
    ccl_p = next(i for i, line in enumerate(lines) if "ccl_classifier_proposed" in line)
    assert raw < ccl_a and raw < ccl_p
    assert "3 / 7" in lines[raw]
    assert text.isascii()


def test_the_classifier_proposed_ccl_is_deposit_complete_statements_and_other_kinds_are_separate_rows():
    """R12: the primary CCL is the deposit-account statement kinds; card /
    loan / brokerage are reported as their own rows, never folded in."""
    summary = summarize(_rows(), mode=MODE_DIGITAL, run_id="r")
    proposed = summary["ccl_classifier_proposed"]
    # deposit STATEMENT_COMPLETE: shas 1, 2, 7 (validated) — sha 5 is a card
    assert proposed["proposed_ccl"] == 3
    assert proposed["validated_in_proposed_ccl"] == 3
    assert proposed["coverage"] == pytest.approx(1.0)
    assert proposed["by_account_kind"]["card"] == {"proposed_complete": 1, "validated": 0}
    assert proposed["by_account_kind"]["deposit"] == {"proposed_complete": 3, "validated": 3}
    assert "loan" in proposed["by_account_kind"] and "brokerage" in proposed["by_account_kind"]
    # the raw denominator is untouched by the CCL figure
    assert summary["raw_coverage"]["denominator"] == 7


def test_the_primary_classification_is_disjoint_and_sums_to_the_population():
    """Case 8 / M7: one kind per sha; the sum over the archive equals the
    distinct-sha count, the sum over the unresolved set equals the
    non-validated distinct-sha count, and both are SHOWN."""
    summary = summarize(_rows(), mode=MODE_DIGITAL, run_id="r")
    archive = summary["document_class"]["archive"]
    unresolved = summary["document_class"]["unresolved"]
    assert archive["population"] == archive["sum"] == 7 and archive["disjoint"] is True
    assert unresolved["population"] == unresolved["sum"] == 4 and unresolved["disjoint"] is True
    assert archive["by_kind"] == {"STATEMENT_COMPLETE": 4, "STATEMENT_PARTIAL": 1, "NOT_A_STATEMENT": 1, "KIND_UNCERTAIN": 1}
    assert unresolved["by_kind"] == {"STATEMENT_COMPLETE": 1, "STATEMENT_PARTIAL": 1, "NOT_A_STATEMENT": 1, "KIND_UNCERTAIN": 1}
    triples = {(k, m, t): n for k, m, t, n in archive["kind_modality_tier"]}
    assert triples[("STATEMENT_COMPLETE", "digital", "structural")] == 4
    assert sum(triples.values()) == 7
    for kind, modality, tier in triples:
        assert kind in KINDS and modality in MODALITIES and tier in TIERS
    text = render_report(summary)
    assert "disjoint sum over archive: 7 == 7" in text
    assert "disjoint sum over unresolved: 4 == 4" in text


def test_a_row_cannot_carry_two_kinds():
    """M7's structural half: the row refuses anything but one member of KINDS."""
    with pytest.raises(ValueError, match="document_class"):
        _row(_sha(9), document_class="STATEMENT_COMPLETE|NOT_A_STATEMENT").as_dict()
    with pytest.raises(ValueError, match="document_class"):
        _row(_sha(9), document_class="").as_dict()
    with pytest.raises(ValueError, match="class_tier"):
        _row(_sha(9), class_tier="both").as_dict()


def test_diagnostic_labels_overlap_and_are_never_summed_into_the_primary_table():
    """Case 8 / M8: R / U / failure-class / truncation labels live in their
    own table; a document may carry several (sha 4 is U AND Class B AND
    truncation-flagged), and no total is printed for that table."""
    rows = _rows()
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    labels = summary["diagnostic_labels"]
    assert labels["note"] == "overlapping; never summed"
    assert labels["R"] == 1                      # sha 6: deferred_visual_ocr
    assert labels["U"] == 1                      # sha 3: local_tesseract and unclaimed
    assert labels["failure_class"] == {"A": 0, "B": 2, "C": 1}
    assert labels["truncation_flagged"] == 1
    assert labels["refused"] == 0
    assert labels["density_surfaced"] == "not carried on rows"
    overlapping_total = labels["R"] + labels["U"] + sum(labels["failure_class"].values()) + labels["truncation_flagged"]
    assert overlapping_total > summary["document_class"]["unresolved"]["sum"] - 1  # a sum of these would over-count
    assert "sum" not in labels and "total" not in labels
    text = render_report(summary)
    heading = next(i for i, line in enumerate(text.splitlines()) if "diagnostic labels (overlapping; never summed)" in line)
    block = text.splitlines()[heading + 1: heading + 12]
    assert not any(re.search(r"\b(sum|total)\b", line) for line in block), block


def test_validated_exceptions_are_counted_by_kind_and_never_by_sha_in_the_summary():
    rows = _rows() + [_row(_sha(8), document_class="STATEMENT_PARTIAL", class_tier="lexical")]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["validated_exceptions"] == {"count": 1, "by_kind": {"STATEMENT_PARTIAL": 1}}
    dumped = json.dumps(summary)
    assert _sha(8) not in dumped and _sha(8)[:16] not in dumped


def test_refused_rows_count_in_the_outcome_lines_and_never_in_the_ladder():
    rows = _rows() + [_row(_sha(8), outcome_class="refused", outcome_reason="not_a_statement",
                           document_class="NOT_A_STATEMENT", class_sub_kind="letter_or_notice",
                           dispatch_outcome=None, parser_id=None)]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["outcome"]["refused"] == 1
    assert summary["diagnostic_labels"]["refused"] == 1
    assert summary["raw_coverage"] == {"validated": 3, "denominator": 8, "coverage": pytest.approx(3 / 8)}
    assert "refused" in render_report(summary)


# ---------------------------------------------------------------------------
# funnel + technical telemetry (case 25), and the no-cost grep (M9)
# ---------------------------------------------------------------------------


def test_the_new_columns_are_appended_at_the_end_of_row_fields_in_the_card_order():
    tail = ROW_FIELDS[ROW_FIELDS.index("stage_extract"):]
    assert tail == [
        "stage_extract", "stage_evidence", "stage_geometry", "stage_layout", "stage_candidate", "stage_verdict",
        "bytes_up", "bytes_down", "inference_ms", "vram_mb", "peak_rss_mb", "research_partition",
        "reason_l0", "reason_l1", "reason_l2", "reason_l3", "reason_l4", "reason_l5", "reason_l6",
        "primary_reason_layer", "primary_reason", "unresolved_taxonomy_version",
        "document_class", "class_sub_kind", "class_modality", "class_account_kind", "class_tier",
        "class_signals", "class_version", "completeness_findings", "classifier_exception",
    ]
    assert ROW_FIELDS[:ROW_FIELDS.index("stage_extract")][-2:] == ["cache_finding", "paddle_refusal_reason"]
    assert "escalation_trigger" in ROW_FIELDS[:ROW_FIELDS.index("stage_extract")]


def test_the_defaults_are_not_attempted_and_empty(tmp_path):
    row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1)
    fields = row.as_dict()
    for stage in ("stage_extract", "stage_evidence", "stage_geometry", "stage_layout", "stage_candidate", "stage_verdict"):
        assert fields[stage] == "not_attempted", stage
    for empty in ("bytes_up", "bytes_down", "inference_ms", "vram_mb", "research_partition"):
        assert fields[empty] == "", empty
    assert fields["peak_rss_mb"] == "not measured"
    assert fields["document_class"] == "KIND_UNCERTAIN" and fields["class_tier"] == "uncertain"
    assert fields["class_version"] == 0  # no classifier ran on a bare row
    write_rows(tmp_path / "rows.csv", [row])
    header = (tmp_path / "rows.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == ROW_FIELDS


def test_stage_vocabularies_are_closed_at_the_row_projection():
    for field, bad in (("stage_extract", "gemini"), ("stage_evidence", "maybe"), ("stage_geometry", "yes"),
                       ("stage_layout", "done"), ("stage_candidate", "won"), ("stage_verdict", "ok")):
        with pytest.raises(ValueError, match=field):
            _row(_sha(9), **{field: bad}).as_dict()


def test_a_malformed_research_partition_is_refused_at_the_row(tmp_path):
    with pytest.raises(ValueError, match="research_partition"):
        _row(_sha(9), research_partition="has a space").as_dict()
    _row(_sha(9), research_partition="paddle-wave-2031.01").as_dict()


def _keys(value, prefix=""):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield f"{prefix}{key}"
            yield from _keys(inner, f"{prefix}{key}.")


def test_no_cost_price_rate_usd_or_billing_key_anywhere(tmp_path):
    """M9's killer: the row fields and every summary.json key, recursively."""
    rows = _rows() + [_row(_sha(8), research_partition="p1", outcome_class="deferred",
                           outcome_reason="research_skipped_not_in_population", dispatch_outcome=None, parser_id=None)]
    summary = summarize(rows, mode=MODE_RESEARCH_PADDLE, run_id="r", research_partition="p1")
    write_summary(tmp_path / "summary.json", summary)
    keys = set(ROW_FIELDS) | set(_keys(json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))))
    offenders = sorted(key for key in keys if FORBIDDEN_TOKENS & set(key.lower().replace(".", "_").split("_")))
    assert offenders == [], offenders
    offenders = sorted(key for key in keys if any(token in key.lower() for token in ("cost", "price", "billing", "usd")))
    assert offenders == [], offenders


def test_research_rows_are_excluded_from_the_headline_and_get_their_own_table():
    rows = _rows() + [
        _row(_sha(8), research_partition="p1", escalation_trigger="operator_forced_paddle", paddle_rung="research",
             stage_extract="paddle", stage_evidence="present", stage_candidate="unclaimed", stage_verdict="failed",
             outcome_class="failed", outcome_reason="no_parser_matched", dispatch_outcome="unclaimed",
             parser_id=None, source_path="paddle", failure_class="B", evidence_quality="usable"),
        _row(_sha(9), research_partition="p1", outcome_class="deferred",
             outcome_reason="research_skipped_not_in_population", dispatch_outcome=None, parser_id=None),
    ]
    summary = summarize(rows, mode=MODE_RESEARCH_PADDLE, run_id="r", research_partition="p1")
    assert summary["raw_coverage"]["denominator"] == 7            # the two research rows are not in the headline
    assert summary["document_class"]["archive"]["population"] == 7
    research = summary["research"]
    assert research["partition"] == "p1"
    assert research["rows"] == 2 and research["attempted"] == 1 and research["skipped_not_in_population"] == 1
    assert research["evidence"] == {"present": 1}
    assert research["e_gate"] == {"usable": 1}
    assert research["stages"]["stage_geometry"] == {"not_attempted": 1}
    assert research["stages"]["stage_verdict"] == {"failed": 1}
    text = render_report(summary)
    assert "research partition p1" in text


def test_mixed_taxonomy_versions_are_warned_about():
    rows = _rows()
    rows[0].unresolved_taxonomy_version = 99
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["unresolved_taxonomy_versions"] == {"1": 7, "99": 1}
    assert "WARNING mixed unresolved-taxonomy versions" in render_report(summary)
