from pathlib import Path

from analysis.schema import Statement
from analysis.pipeline import DocumentIntegrity, Report, Quality
from analysis.reconcile import ReconResult
from analysis.metrics import Metrics
from analysis.detect import DetectionResult
from ocr.document import StatementMarkdown

import deterministic_coverage_audit as audit


def test_audit_file_reports_no_native_text(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(audit, "native_statement", lambda pdf_bytes, source_file="": None)

    row = audit.audit_file(pdf, tmp_path)

    assert row["native_status"] == "no_native_text"
    assert row["deterministic_status"] == "not_attempted"
    assert row["corporate_use"] == "manual_review_required"
    assert row["integrity_flags"] == "text_unavailable"


def test_audit_file_reports_no_deterministic_parser(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        audit,
        "native_statement",
        lambda pdf_bytes, source_file="": StatementMarkdown(source_file=source_file, model="native-pdf-text", pages=["hello"]),
    )

    def fail_analyze(markdown, parse_mode="auto"):
        raise RuntimeError("no deterministic parser matched this statement")

    monkeypatch.setattr(audit, "analyze_markdown", fail_analyze)

    row = audit.audit_file(pdf, tmp_path)

    assert row["native_status"] == "native_text"
    assert row["deterministic_status"] == "no_parser"
    assert row["native_model"] == "native-pdf-text"
    assert row["corporate_use"] == "manual_review_required"
    assert row["integrity_flags"] == "unsupported_statement_format"
    assert "no deterministic parser" in row["reconciliation_issues"]


def test_audit_file_reports_successful_deterministic_parse(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        audit,
        "native_statement",
        lambda pdf_bytes, source_file="": StatementMarkdown(source_file=source_file, model="native-pdf-text", pages=["hello"]),
    )
    stmt = Statement(bank="Test Bank", account_number="1234", period_start="2054-01-01", period_end="2054-01-31")
    report = Report(
        statement=stmt,
        reconciliation=ReconResult(ok=True, summary_ok=True, issues=[]),
        metrics=Metrics(),
        detection=DetectionResult(known_funders=[], recurring_debits=[]),
        quality=Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=True,
            corporate_use="approved",
        ),
        integrity=DocumentIntegrity(risk_level="review", flags=["debit_detail_coverage_mismatch"], notes=[]),
        model_used="test-bank-deterministic",
        escalated=False,
    )
    monkeypatch.setattr(audit, "analyze_markdown", lambda markdown, parse_mode="auto": report)

    row = audit.audit_file(pdf, tmp_path)

    assert row["deterministic_status"] == "parsed"
    assert row["parser_model"] == "test-bank-deterministic"
    assert row["bank"] == "Test Bank"
    assert row["integrity_risk"] == "review"
    assert row["integrity_flags"] == "debit_detail_coverage_mismatch"


def test_audit_file_includes_review_notes_for_parsed_reports(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        audit,
        "native_statement",
        lambda pdf_bytes, source_file="": StatementMarkdown(source_file=source_file, model="native-pdf-text", pages=["hello"]),
    )
    stmt = Statement(bank="Test Bank")
    report = Report(
        statement=stmt,
        reconciliation=ReconResult(ok=False, summary_ok=False, issues=["summary mismatch"]),
        metrics=Metrics(),
        detection=DetectionResult(known_funders=[], recurring_debits=[]),
        quality=Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            corporate_use="manual_review_required",
            notes=["quality reason"],
        ),
        integrity=DocumentIntegrity(
            risk_level="high",
            flags=["summary_math_inconsistent"],
            notes=["integrity reason"],
            possible_document_issue=True,
        ),
        model_used="test-bank-deterministic",
        escalated=False,
    )
    monkeypatch.setattr(audit, "analyze_markdown", lambda markdown, parse_mode="auto": report)

    row = audit.audit_file(pdf, tmp_path)

    assert row["integrity_notes"] == "integrity reason"
    assert row["quality_notes"] == "quality reason"
    assert row["reconciliation_issues"] == "summary mismatch"
