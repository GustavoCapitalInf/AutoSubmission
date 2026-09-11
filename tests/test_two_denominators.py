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


# ---------------------------------------------------------------------------
# item 4 / case 6 / M6: the classifier is a RECORDED FACT and NOTHING ELSE.
# item 7 / M15: the geometry seam is INERT while `reconstruction_mode == off`.
# Both are proved on a real run of the real runner over a SYNTHETIC document —
# a stubbed pipeline could not tell either of them.
# ---------------------------------------------------------------------------


@pytest.fixture
def analysis_spy(monkeypatch):
    """Every `analyze_document` call the runner makes: the markdown, the
    keyword arguments, and the RESULT — the serialized payload, or the
    exception class when the deterministic mode refused (which is what an
    unclaimed document produces, and is a result like any other).

    The entry is appended BEFORE the call, so a raising analysis is still
    recorded: an identity proof that only saw the calls that succeeded would
    be blind to exactly the population this card reports on.
    """
    import discovery.runner as runner_module
    from analysis.serialization import document_report_to_dict

    real = runner_module.analyze_document
    calls: list[dict] = []

    def spy(markdown, **kwargs):
        entry = {"markdown": markdown, "kwargs": sorted(kwargs), "result": None}
        calls.append(entry)
        try:
            report = real(markdown, **kwargs)
        except Exception as exc:
            entry["result"] = f"raised:{type(exc).__name__}"
            raise
        entry["result"] = json.dumps(
            document_report_to_dict(report), sort_keys=True, default=str)
        return report

    monkeypatch.setattr(runner_module, "analyze_document", spy)
    return calls


def _synthetic_document(tmp_path):
    from tests.paddle_synthetic import build_ledger_page, render_native_pdf

    root = tmp_path / "root"
    (root / "SynthC").mkdir(parents=True)
    (root / "SynthC" / "ledger.pdf").write_bytes(render_native_pdf(build_ledger_page(12)))
    return root


def _run_one(root, monkeypatch=None):
    from discovery.inventory import DedupIndex
    from discovery.runner import DiscoveryRunner

    runner = DiscoveryRunner(root, mode=MODE_DIGITAL, run_id="t", dedup=DedupIndex(),
                             sink=None, cache=None)
    return runner.process("SynthC/ledger.pdf", "SynthC")


def test_the_classifier_is_never_passed_to_the_analysis_and_changes_no_payload(
    tmp_path, monkeypatch, analysis_spy,
):
    """M6's killer. The same document analysed twice — once with the
    classifier live, once with it raising on every call — hands
    `analyze_document` a BYTE-IDENTICAL input and gets a byte-identical result
    back, and neither run passes a classification, a geometry or anything else
    new into it.

    The payload leg over REAL payloads is the union cohort replay at closure,
    which compares the published payload of every document in the archive with
    the classifier live; this is the mechanism the replay confirms."""
    import discovery.runner as runner_module

    root = _synthetic_document(tmp_path)
    live = _run_one(root)
    assert live.class_version == 1 and live.classifier_exception == ""

    def exploding(**kwargs):
        raise RuntimeError("the classifier is a reporting consumer")

    monkeypatch.setattr(runner_module, "classify_document_kind", exploding)
    stubbed = _run_one(root)

    # the classifier's own columns differ (that is the point of stubbing it)
    assert stubbed.classifier_exception == "RuntimeError"
    assert stubbed.class_version == 0
    # ... and NOTHING else does: same outcome, same reason, same payload
    assert (stubbed.outcome_class, stubbed.outcome_reason) == (live.outcome_class, live.outcome_reason)
    assert len(analysis_spy) == 2
    assert analysis_spy[0] == analysis_spy[1], "the classifier changed the analysis"
    assert analysis_spy[0]["kwargs"] == ["on_dispatch", "parse_mode", "sheets"]
    # and a defect in a reporting consumer never fails a run
    assert stubbed.content_sha256 == live.content_sha256


def test_the_geometry_seam_passes_nothing_while_the_reconstruction_mode_is_off(
    tmp_path, monkeypatch, analysis_spy,
):
    """M15's killer: with `reconstruction_mode == off` the analysis call is
    the call it always was — no `document_geometry` keyword, and no evidence
    sha in the cache key. A mutant that passes geometry unconditionally adds a
    keyword here and dies."""
    monkeypatch.setenv("RECONSTRUCTION_MODE", "off")
    root = _synthetic_document(tmp_path)
    _run_one(root)
    assert analysis_spy, "the analysis never ran; the fixture premise moved"
    for call in analysis_spy:
        assert call["kwargs"] == ["on_dispatch", "parse_mode", "sheets"], call["kwargs"]
        assert "document_geometry" not in call["kwargs"]


def test_the_geometry_seam_is_reached_when_the_mode_is_not_off(tmp_path, monkeypatch, analysis_spy):
    """The other half of M15: the seam is WIRED, not dead. With the mode set
    to `research` the same run passes `document_geometry` — so the inertness
    above is a property of the MODE and not of a branch nothing can reach."""
    monkeypatch.setenv("RECONSTRUCTION_MODE", "research")
    root = _synthetic_document(tmp_path)
    _run_one(root)
    assert analysis_spy
    assert any("document_geometry" in call["kwargs"] for call in analysis_spy), [
        call["kwargs"] for call in analysis_spy
    ]


def test_the_extraction_stage_tells_never_read_apart_from_read_and_empty(monkeypatch):
    """Review MINOR-5's killer (M21). `source_path` defaults to the literal
    `none`, so before this a document refused BEFORE the ladder ran and one the
    ladder ran for and got nothing from were the same token. On the run of
    record that mislabelled 16 of 29, and every row of a profile-only run."""
    from discovery.runner import NO_READ_ATTEMPTED_REASONS, STAGE_VOCABULARY, DiscoveryRunner

    def stage_extract(**overrides) -> str:
        row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64,
                          byte_size=1, **overrides)
        DiscoveryRunner._project_funnel(row, {})
        return row.stage_extract

    # refused before the ladder ever ran -> not_attempted, every reason
    for reason in sorted(NO_READ_ATTEMPTED_REASONS):
        assert stage_extract(source_path="none", outcome_reason=reason) == "not_attempted", reason
    # the ladder RAN and produced nothing -> none, which is the honest word
    assert stage_extract(source_path="none", outcome_reason="deferred_visual_ocr") == "none"
    assert stage_extract(source_path="none", outcome_reason="ocr_failed") == "none"
    # and a real read still reports its own extractor
    assert stage_extract(source_path="native", outcome_reason="approved") == "native"
    assert stage_extract(source_path="local_tesseract", outcome_reason="no_parser_matched") == "local_tesseract"
    # the vocabulary the two facts live in is closed and holds both words
    assert {"not_attempted", "none"} <= STAGE_VOCABULARY["stage_extract"]


def test_the_no_read_vocabulary_names_only_reasons_the_tree_can_emit():
    """A closed tuple that drifts out of the reason vocabulary would silently
    stop firing. Every member must be a reason something in this tree emits."""
    from discovery.runner import NO_READ_ATTEMPTED_REASONS
    from telemetry.unresolved_taxonomy import REASON_LAYER

    unknown = sorted(NO_READ_ATTEMPTED_REASONS - set(REASON_LAYER))
    assert unknown == [], f"reasons no emitter produces: {unknown}"


def test_peak_rss_is_measured_when_psutil_is_importable_and_a_word_when_it_is_not(monkeypatch):
    """Case 25, both branches. The degraded value is a WORD, never `0` and
    never empty: a column that reads as a figure is a measurement somebody
    made, and nobody made this one."""
    import sys
    import types

    from discovery.runner import PEAK_RSS_NOT_MEASURED, peak_rss_mb

    # Review MINOR-6 (reproduced): `psutil` is installed nowhere — not on this
    # host, not in `requirements.txt`, so not in CI — and the measuring arm had
    # therefore never executed anywhere. Injecting a STUB module exercises it
    # for real without installing anything and without making the suite depend
    # on an optional native package.
    stub = types.ModuleType("psutil")

    class _Process:
        def memory_info(self):
            return types.SimpleNamespace(rss=123 * 1024 * 1024)

    stub.Process = _Process
    monkeypatch.setitem(sys.modules, "psutil", stub)
    assert peak_rss_mb() == "123.0"
    assert float(peak_rss_mb()) > 0.0

    # a library present but refusing (a permission or platform failure) is not
    # a run failure: the column degrades, the document does not
    class _Refusing:
        def memory_info(self):
            raise OSError("access denied")

    stub.Process = _Refusing
    assert peak_rss_mb() == PEAK_RSS_NOT_MEASURED

    # and the absent arm: `None` in sys.modules makes `import psutil` raise
    # ImportError exactly as a missing distribution does
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert peak_rss_mb() == PEAK_RSS_NOT_MEASURED
    assert PEAK_RSS_NOT_MEASURED == "not measured"


# ---------------------------------------------------------------------------
# item 9: `tools/truth_report.py` — the join across the firewall.
# ---------------------------------------------------------------------------


def _write_rows_csv(path: Path, rows: list) -> Path:
    write_rows(path, rows)
    return path


def test_truth_report_prints_both_denominators_and_no_sha(tmp_path):
    """Item 9 / case 11. With no sealed store it still prints the RAW
    denominator and the classifier's PROPOSAL, labelled as a proposal, and
    says outright that nothing was adjudicated — D10: adjudication is not a
    gate. No full content sha reaches stdout."""
    from tools.truth_report import join, read_rows, render

    rows_csv = _write_rows_csv(tmp_path / "rows.csv", _rows())
    documents = read_rows(rows_csv)
    assert len(documents) == 7
    report = join(documents, None)
    assert report["raw"] == {"population": 7, "validated": 3, "coverage": pytest.approx(3 / 7)}
    assert report["ccl_adjudicated"]["population"] == 0
    assert report["ccl_classifier_proposed"] == {
        "population": 3, "validated": 3, "coverage": pytest.approx(1.0)}
    assert report["disjoint_sum"] == 7
    assert report["by_source"] == {"classifier_proposed": 7}
    text = render(report, store_note="no sealed store read (test)")
    assert text.isascii()
    assert "RAW" in text and "CCL adjudicated" in text and "CCL classifier-proposed" in text
    assert text.index("RAW") < text.index("CCL adjudicated")
    for row in _rows():
        assert row.content_sha256 not in text
    assert "never replaced" in text


def test_truth_report_prefers_the_sealed_verdict_and_labels_every_document(tmp_path):
    """A sealed record OUTRANKS the classifier's proposal for the same
    document, and every document says which of the two named it — a proposal
    never masquerades as truth (D10)."""
    from tools.truth_report import join, read_rows, render_private

    rows = _rows()
    documents = read_rows(_write_rows_csv(tmp_path / "rows.csv", rows))
    sha = _sha(4)  # the row calls it NOT_A_STATEMENT{loan_statement}
    sealed = {sha: {"kind": "STATEMENT_COMPLETE", "account_kind": "deposit", "legible": True}}
    report = join(documents, sealed)
    assert report["by_source"] == {"adjudicated": 1, "classifier_proposed": 6}
    assert report["ccl_adjudicated"]["population"] == 1
    assert report["ccl_adjudicated"]["validated"] == 0   # that document failed
    assert report["disjoint_sum"] == 7                    # still exactly one kind each
    private = render_private(report)
    assert sha[:16] in private and sha not in private     # sha16 is the finest grain
    assert "adjudicated" in private and "classifier_proposed" in private


def test_truth_report_refuses_a_tracked_out_path(tmp_path):
    from tools.truth_report import main

    tracked = Path(__file__).resolve().parents[1] / "docs" / "truth_report_should_never_land_here.md"
    with pytest.raises(SystemExit, match="not git-ignored"):
        main(["--rows", str(tmp_path / "rows.csv"), "--out", str(tracked)])
    assert not tracked.exists()


def test_truth_report_carries_no_cost_price_rate_usd_or_billing_key(tmp_path):
    """M9 again, on the second instrument: the tool that joins the two
    denominators must not grow a third that nobody asked for."""
    from tools.truth_report import join, read_rows

    report = join(read_rows(_write_rows_csv(tmp_path / "rows.csv", _rows())), None)
    keys = set(_keys(report)) | {"per_document"}
    offenders = sorted(key for key in keys
                       if FORBIDDEN_TOKENS & set(key.lower().replace(".", "_").split("_")))
    assert offenders == [], offenders
