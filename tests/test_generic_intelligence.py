from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.config import Settings, load_settings as load_analysis_settings
from analysis.extract import ExtractionAttempt, estimate_extraction_cost, extract_statement
from analysis.parser_registry import PARSER_REGISTRY, parse_deterministic_statement
from analysis.pipeline import analyze_markdown
from analysis.schema import Statement, Transaction
from analysis.serialization import report_to_dict
from webapp.jobs import JobStore
from webapp.app import _package_analysis
from webapp.worker import run_job


def _settings(*, max_attempts: int = 2) -> Settings:
    return Settings(
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        escalation_model="gemini-3.5-flash",
        max_external_extraction_attempts=max_attempts,
    )


def test_external_provider_timeout_and_retry_defaults_are_bounded(monkeypatch):
    monkeypatch.delenv("GEMINI_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("GEMINI_HTTP_ATTEMPTS", raising=False)
    settings = load_analysis_settings()

    assert settings.request_timeout_ms == 90_000
    assert settings.http_attempts == 1


def test_external_provider_timeout_and_retry_limits_are_configurable(monkeypatch):
    monkeypatch.setenv("GEMINI_TIMEOUT_MS", "30000")
    monkeypatch.setenv("GEMINI_HTTP_ATTEMPTS", "2")
    settings = load_analysis_settings()

    assert settings.request_timeout_ms == 30_000
    assert settings.http_attempts == 2


def test_external_extraction_can_be_disabled_globally(monkeypatch):
    monkeypatch.setenv("GEMINI_MAX_EXTRACTION_ATTEMPTS", "0")

    assert load_analysis_settings().max_external_extraction_attempts == 0


def _unknown_bank_statement() -> Statement:
    return Statement(
        bank="Old Dominion Community Bank",
        account_name="Business Checking",
        account_number="9876",
        document_account_count=1,
        account_selection_status="single_account",
        period_start="2026-04-01",
        period_end="2026-04-30",
        beginning_balance=1000.0,
        ending_balance=1250.0,
        stated_total_credits=500.0,
        stated_total_debits=250.0,
        transactions=[
            Transaction(
                date="2026-04-03",
                description="CUSTOMER DEPOSIT",
                amount=500.0,
                direction="credit",
                running_balance=1500.0,
                source_page=1,
            ),
            Transaction(
                date="2026-04-20",
                description="ACH PAYMENT",
                amount=-250.0,
                direction="debit",
                running_balance=1250.0,
                source_page=1,
            ),
        ],
    )


def _unknown_bank_markdown() -> str:
    return """
    --- Page 1 ---
    OLD DOMINION COMMUNITY BANK
    Account 9876
    Business Checking Statement 04/01/2026 through 04/30/2026
    Beginning Balance $1,000.00
    Total Credits $500.00
    Total Debits $250.00
    04/03 CUSTOMER DEPOSIT 500.00 1,500.00
    04/20 ACH PAYMENT 250.00 1,250.00
    Ending Balance $1,250.00
    """


def test_extraction_records_tokens_thinking_cost_and_latency(monkeypatch):
    response = SimpleNamespace(
        parsed=_unknown_bank_statement(),
        text="",
        usage_metadata=SimpleNamespace(
            prompt_token_count=10_000,
            candidates_token_count=4_000,
            thoughts_token_count=1_000,
            total_token_count=15_000,
        ),
    )
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kwargs: response)
    )
    monkeypatch.setattr("analysis.extract._get_client", lambda settings: client)
    attempts = []

    statement = extract_statement(
        "statement markdown",
        settings=_settings(),
        attempt_sink=attempts.append,
    )

    assert statement.bank == "Old Dominion Community Bank"
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.status == "success"
    assert attempt.prompt_tokens == 10_000
    assert attempt.response_tokens == 5_000
    assert attempt.thinking_tokens == 1_000
    assert attempt.total_tokens == 15_000
    assert attempt.estimated_cost_usd == pytest.approx(0.0155)
    assert attempt.latency_ms >= 0


def test_extraction_records_failed_attempt_without_error_message(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("secret provider response")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    monkeypatch.setattr("analysis.extract._get_client", lambda settings: client)
    attempts = []

    with pytest.raises(RuntimeError, match="secret provider response"):
        extract_statement(
            "statement markdown",
            settings=_settings(),
            attempt_sink=attempts.append,
        )

    assert attempts[0].status == "error"
    assert attempts[0].error_type == "RuntimeError"
    assert not hasattr(attempts[0], "error_message")


def test_unknown_model_reports_tokens_without_inventing_a_cost():
    assert estimate_extraction_cost(
        "future-model",
        prompt_tokens=1000,
        response_tokens=1000,
    ) is None


def test_gemini_document_fallback_transcribes_pages_and_records_cost(monkeypatch):
    from ocr.gemini_document import parse_gemini_document

    response = SimpleNamespace(
        text="""
        --- Page 1 ---
        FIRST PAGE 100.00
        --- Page 2 ---
        SECOND PAGE 200.00
        """,
        usage_metadata=SimpleNamespace(
            prompt_token_count=1000,
            candidates_token_count=400,
            thoughts_token_count=100,
            total_token_count=1500,
        ),
    )

    class _Models:
        @staticmethod
        def generate_content(**kwargs):
            assert kwargs["model"] == "gemini-3.5-flash-lite"
            assert len(kwargs["contents"]) == 2
            return response

    class _Client:
        models = _Models()

    monkeypatch.setattr("ocr.gemini_document.genai.Client", lambda **kwargs: _Client())

    document = parse_gemini_document(
        b"%PDF-synthetic",
        source_file="synthetic.pdf",
        settings=_settings(max_attempts=2),
    )

    assert document.model == "gemini-document-ocr:gemini-3.5-flash-lite"
    assert document.pages == ["FIRST PAGE 100.00", "SECOND PAGE 200.00"]
    assert len(document.external_attempts) == 1
    assert document.external_attempts[0].source_kind == "pdf_visual_ocr"
    assert document.external_attempts[0].estimated_cost_usd == pytest.approx(0.00155)


def test_parser_registry_has_unique_stable_keys():
    keys = [registration.key for registration in PARSER_REGISTRY]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 40


def test_unseen_bank_uses_generic_extraction_and_reconciles(monkeypatch):
    markdown = """
    --- Page 1 ---
    OLD DOMINION COMMUNITY BANK
    Account 9876
    Business Checking Statement 04/01/2026 through 04/30/2026
    Beginning Balance $1,000.00
    Total Credits $500.00
    Total Debits $250.00
    04/03 CUSTOMER DEPOSIT 500.00 1,500.00
    04/20 ACH PAYMENT 250.00 1,250.00
    Ending Balance $1,250.00
    """
    assert parse_deterministic_statement(markdown) is None

    def fake_extract(markdown, *, settings, model, attempt_sink):
        attempt_sink(
            ExtractionAttempt(
                provider="google_gemini",
                model=model,
                source_kind="ocr_markdown",
                status="success",
                latency_ms=12,
                prompt_tokens=2000,
                response_tokens=3000,
                total_tokens=5000,
                estimated_cost_usd=0.0081,
                pricing_version="test-pricing",
            )
        )
        return _unknown_bank_statement()

    monkeypatch.setattr("analysis.pipeline.extract_statement", fake_extract)

    report = analyze_markdown(markdown, settings=_settings(max_attempts=1))
    payload = report_to_dict(report)

    assert report.model_used == "gemini-3.5-flash-lite"
    assert report.reconciliation.ok
    assert report.quality.corporate_use == "approved"
    assert report.source_validation.ok
    assert payload["statement"]["bank"] == "Old Dominion Community Bank"
    assert payload["metrics"]["authoritative"] is True
    assert payload["extraction"]["attempt_count"] == 1
    assert payload["extraction"]["estimated_cost_usd"] == pytest.approx(0.0081)


def test_generic_transaction_page_is_preserved_in_review_evidence(monkeypatch):
    statement = _unknown_bank_statement()
    statement.transactions[0].source_page = 3

    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: statement,
    )

    report = analyze_markdown("UNSEEN BANK", settings=_settings(max_attempts=1))

    assert report.classifications[0].source_page == 3
    assert report.classifications[0].source_location == "page:3:transaction:1"


def test_ambiguous_multi_account_generic_result_fails_closed(monkeypatch):
    statement = _unknown_bank_statement()
    statement.document_account_count = 3
    statement.account_selection_status = "ambiguous"
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: statement,
    )

    report = analyze_markdown(_unknown_bank_markdown(), settings=_settings(max_attempts=1))
    payload = report_to_dict(report)

    assert report.quality.corporate_use == "manual_review_required"
    assert "ambiguous_account_selection" in report.integrity.flags
    assert report.integrity.possible_document_issue
    assert payload["metrics"]["average_daily_balance"] is None
    assert payload["metrics"]["authoritative"] is False
    assert payload["metrics"]["unavailable_reason"] == "ambiguous_account_selection"
    assert payload["statement"]["transactions"] == []
    assert payload["statement"]["ending_balance"] is None


def test_batch_csv_withholds_untrusted_generic_financial_values(monkeypatch):
    from batch import _row

    statement = _unknown_bank_statement()
    statement.transactions[0].source_page = None
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: statement,
    )

    report = analyze_markdown(_unknown_bank_markdown(), settings=_settings(max_attempts=1))
    row = _row(Path("unknown.pdf"), report)

    assert row["average_daily_balance"] == ""
    assert row["total_deposits"] == ""
    assert row["verified_revenue_total"] == ""
    assert row["needs_review"] == "REVIEW"
    assert row["error"] == "generic_source_grounding_failed"


def test_withheld_document_does_not_dilute_mixed_package_averages(monkeypatch):
    valid_statement = _unknown_bank_statement()
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: valid_statement,
    )
    valid_payload = report_to_dict(
        analyze_markdown(_unknown_bank_markdown(), settings=_settings(max_attempts=1))
    )

    invalid_statement = _unknown_bank_statement()
    invalid_statement.transactions[0].source_page = None
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: invalid_statement,
    )
    invalid_payload = report_to_dict(
        analyze_markdown(_unknown_bank_markdown(), settings=_settings(max_attempts=1))
    )

    package = _package_analysis([
        SimpleNamespace(
            id="valid",
            filename="valid.pdf",
            status="done",
            analysis=valid_payload,
            analysis_error=None,
            error=None,
        ),
        SimpleNamespace(
            id="withheld",
            filename="withheld.pdf",
            status="done",
            analysis=invalid_payload,
            analysis_error=None,
            error=None,
        ),
    ])

    assert package["totals"]["authoritative_documents"] == 1
    assert package["totals"]["months"] == 1
    assert package["totals"]["avg_monthly_credits"] == pytest.approx(500.0)
    assert package["totals"]["decision"] == "review_required"
    assert package["documents"][1]["financial_values_available"] is False


def test_grounded_but_incomplete_generic_ledger_is_withheld(monkeypatch):
    from batch import _row

    statement = _unknown_bank_statement()
    statement.beginning_balance = None
    statement.ending_balance = None
    statement.stated_total_credits = None
    statement.stated_total_debits = None
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: statement,
    )

    report = analyze_markdown(_unknown_bank_markdown(), settings=_settings(max_attempts=1))
    payload = report_to_dict(report)
    row = _row(Path("incomplete.pdf"), report)

    assert report.source_validation.ok
    assert not report.reconciliation.ok
    assert payload["metrics"]["authoritative"] is False
    assert payload["metrics"]["unavailable_reason"] == "generic_financial_reconciliation_failed"
    assert payload["statement"]["transactions"] == []
    assert row["total_deposits"] == ""
    assert row["error"] == "generic_financial_reconciliation_failed"


def test_explicit_zero_activity_unknown_statement_remains_authoritative(monkeypatch):
    statement = Statement(
        bank="Old Dominion Community Bank",
        account_number="9876",
        document_account_count=1,
        account_selection_status="single_account",
        period_start="2026-04-01",
        period_end="2026-04-30",
        beginning_balance=1000.0,
        ending_balance=1000.0,
        stated_total_credits=0.0,
        stated_total_debits=0.0,
        transactions=[],
    )
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: statement,
    )
    markdown = """
    --- Page 1 ---
    OLD DOMINION COMMUNITY BANK
    Account 9876
    Statement Period 04/01/2026 through 04/30/2026
    Beginning Balance 1,000.00
    Total Credits 0.00
    Total Debits 0.00
    Ending Balance 1,000.00
    """

    report = analyze_markdown(markdown, settings=_settings(max_attempts=1))
    payload = report_to_dict(report)

    assert report.source_validation.zero_activity_supported is True
    assert report.reconciliation.ok
    assert report.quality.corporate_use == "approved"
    assert payload["metrics"]["authoritative"] is True
    assert payload["metrics"]["average_daily_balance"] == pytest.approx(1000.0)


def test_self_reconciling_but_ungrounded_generic_result_is_withheld(monkeypatch):
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda markdown, **kwargs: _unknown_bank_statement(),
    )
    markdown = """
    --- Page 1 ---
    OLD DOMINION COMMUNITY BANK
    Account 9876
    Beginning Balance 900.00
    04/03 DIFFERENT SOURCE ROW 40.00 940.00
    Ending Balance 940.00
    """

    report = analyze_markdown(markdown, settings=_settings(max_attempts=1))
    payload = report_to_dict(report)

    assert report.reconciliation.ok
    assert not report.source_validation.ok
    assert report.quality.corporate_use == "manual_review_required"
    assert "generic_source_grounding_failed" in report.integrity.flags
    assert payload["metrics"]["authoritative"] is False
    assert payload["metrics"]["average_daily_balance"] is None
    assert payload["metrics"]["verified_revenue_total"] is None
    assert payload["statement"]["beginning_balance"] is None
    assert payload["statement"]["ending_balance"] is None
    assert payload["statement"]["transactions"] == []
    assert payload["classifications"] == []
    assert payload["detection"]["manual_review"] == []

    package = _package_analysis([
        SimpleNamespace(
            id="job-1",
            filename="unknown.pdf",
            status="done",
            analysis=payload,
            analysis_error=None,
            error=None,
        )
    ])
    assert package["documents"][0]["financial_values_available"] is False
    assert package["documents"][0]["credits"] is None
    assert package["totals"]["authoritative_documents"] == 0
    assert package["totals"]["total_credits"] is None
    assert package["totals"]["verified_revenue_total"] is None
    assert package["totals"]["decision"] == "review_required"


def test_grounding_failure_uses_one_bounded_stronger_extraction(monkeypatch):
    calls = []
    valid = _unknown_bank_statement()
    invalid = valid.model_copy(deep=True)
    invalid.transactions[0].source_page = None

    def fake_extract(markdown, *, settings, model, attempt_sink):
        calls.append(model)
        attempt_sink(
            ExtractionAttempt(
                provider="google_gemini",
                model=model,
                source_kind="ocr_markdown",
                status="success",
                latency_ms=1,
            )
        )
        return invalid if len(calls) == 1 else valid

    monkeypatch.setattr("analysis.pipeline.extract_statement", fake_extract)
    markdown = """
    --- Page 1 ---
    OLD DOMINION COMMUNITY BANK
    Account 9876
    Statement Period 04/01/2026 through 04/30/2026
    Beginning Balance 1,000.00
    Total Credits 500.00
    Total Debits 250.00
    04/03 CUSTOMER DEPOSIT 500.00 1,500.00
    04/20 ACH PAYMENT 250.00 1,250.00
    Ending Balance 1,250.00
    """

    report = analyze_markdown(markdown, settings=_settings(max_attempts=2))

    assert calls == ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
    assert report.escalated
    assert report.source_validation.ok
    assert report.quality.corporate_use == "approved"


def test_external_attempt_cap_prevents_unbounded_escalation(monkeypatch):
    calls = []

    def fake_extract(markdown, *, settings, model, attempt_sink):
        calls.append(model)
        attempt_sink(
            ExtractionAttempt(
                provider="google_gemini",
                model=model,
                source_kind="ocr_markdown",
                status="success",
                latency_ms=1,
            )
        )
        statement = _unknown_bank_statement()
        statement.ending_balance = 9999.0
        statement.stated_total_credits = None
        statement.stated_total_debits = None
        return statement

    monkeypatch.setattr("analysis.pipeline.extract_statement", fake_extract)

    report = analyze_markdown("UNKNOWN BANK", settings=_settings(max_attempts=1))

    assert calls == ["gemini-3.5-flash-lite"]
    assert not report.reconciliation.ok
    assert report.escalated is False


def test_zero_remaining_budget_still_allows_deterministic_parser(monkeypatch):
    statement = _unknown_bank_statement()
    monkeypatch.setattr("analysis.pipeline._deterministic_statement", lambda markdown: statement)
    monkeypatch.setattr(
        "analysis.pipeline.extract_statement",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model should not run")),
    )

    report = analyze_markdown("KNOWN LAYOUT", external_attempt_budget=0)

    assert report.reconciliation.ok
    assert report.extraction_attempts == []


class _Doc:
    def __init__(self, model: str, marker: str, *, external_attempts=None):
        self.model = model
        self.marker = marker
        self.pages = [marker]
        self.external_attempts = list(external_attempts or [])
        self.metadata = {}

    def to_markdown(self):
        return self.marker


def _analysis_payload(*, approved: bool, flags: list[str] | None = None) -> dict:
    return {
        "statement": {"transactions": [{"amount": 1.0}]},
        "reconciliation": {"ok": approved, "summary_ok": approved},
        "quality": {
            "level": "transaction_level" if approved else "needs_review",
            "corporate_use": "approved" if approved else "manual_review_required",
            "transaction_detail_reliable": approved,
        },
        "integrity": {
            "risk_level": "clear" if approved else "review",
            "possible_document_issue": False,
            "flags": flags or [],
        },
        "metrics": {"adb_ok": approved},
        "extraction": {"attempt_count": 0, "attempts": [], "estimated_cost_usd": 0.0},
    }


def test_auto_route_retries_weak_local_text_and_selects_validated_visual_ocr(monkeypatch):
    store = JobStore()
    job = store.create("unknown-scan.pdf")
    local = _Doc("local-tesseract-ocr", "weak-local-read")
    visual = _Doc("baidu/Unlimited-OCR", "strong-visual-read")
    visual_calls = []

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf, filename: None)
    monkeypatch.setattr("webapp.worker._local_ocr_statement", lambda pdf, filename: local)

    def visual_parse(*args, **kwargs):
        visual_calls.append(kwargs.get("force_ocr"))
        return visual

    monkeypatch.setattr("webapp.worker.parse_statement", visual_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": markdown)
    monkeypatch.setattr(
        "webapp.worker.report_to_json",
        lambda marker: _analysis_payload(approved=marker == "strong-visual-read"),
    )

    run_job(job.id, b"%PDF-fake", "unknown-scan.pdf", store)

    result = store.get(job.id)
    assert result.status == "done"
    assert result.parse_model == "baidu/Unlimited-OCR"
    assert result.analysis["quality"]["corporate_use"] == "approved"
    assert result.analysis["processing"]["candidate_count"] == 2
    assert result.analysis["processing"]["selected_source_model"] == "baidu/Unlimited-OCR"
    assert visual_calls == [True]


def test_auto_route_preserves_model_budget_after_free_tesseract_preflight(monkeypatch):
    store = JobStore()
    job = store.create("unknown-scan.pdf")
    local = _Doc("local-tesseract-ocr", "weak-local-read")
    visual = _Doc("baidu/Unlimited-OCR", "strong-visual-read")
    budgets = []

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf, filename: None)
    monkeypatch.setattr("webapp.worker._local_ocr_statement", lambda pdf, filename: local)
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *args, **kwargs: visual)
    monkeypatch.setattr(
        "webapp.worker.load_analysis_settings",
        lambda: _settings(max_attempts=2),
    )

    def analyze(markdown, *, parse_mode="auto", external_attempt_budget=None):
        budgets.append(external_attempt_budget)
        return markdown

    def serialize(marker):
        payload = _analysis_payload(approved=marker == "strong-visual-read")
        if marker == "weak-local-read":
            return payload
        payload["extraction"] = {
            "attempt_count": 1,
            "attempts": [
                {
                    "model": "gemini-3.5-flash-lite",
                    "status": "success",
                    "estimated_cost_usd": 0.02,
                }
            ],
            "estimated_cost_usd": 0.02,
            "cost_complete": True,
        }
        return payload

    monkeypatch.setattr("webapp.worker.analyze_markdown", analyze)
    monkeypatch.setattr("webapp.worker.report_to_json", serialize)

    run_job(job.id, b"%PDF-fake", "unknown-scan.pdf", store)

    result = store.get(job.id)
    assert budgets == [0, 2]
    assert result.analysis["extraction"]["attempt_count"] == 1
    assert result.analysis["extraction"]["attempt_limit"] == 2
    assert result.analysis["extraction"]["estimated_cost_usd"] == pytest.approx(0.02)
    assert result.analysis["extraction"]["attempts"][0]["document_source_model"] == "baidu/Unlimited-OCR"


def test_unavailable_unlimited_ocr_uses_one_budgeted_document_fallback(monkeypatch):
    store = JobStore()
    job = store.create("unknown-scan.pdf")
    local = _Doc("local-tesseract-ocr", "weak-local-read")
    document_attempt = ExtractionAttempt(
        provider="google_gemini",
        model="gemini-3.5-flash-lite",
        source_kind="pdf_visual_ocr",
        status="success",
        latency_ms=10,
        estimated_cost_usd=0.01,
        pricing_version="test-pricing",
    )
    visual = _Doc(
        "gemini-document-ocr:gemini-3.5-flash-lite",
        "strong-visual-read",
        external_attempts=[document_attempt],
    )
    budgets = []

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf, filename: None)
    monkeypatch.setattr("webapp.worker._local_ocr_statement", lambda pdf, filename: local)
    monkeypatch.setattr(
        "webapp.worker.parse_statement",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("endpoint unavailable")),
    )
    monkeypatch.setattr(
        "ocr.gemini_document.parse_gemini_document",
        lambda *args, **kwargs: visual,
    )
    monkeypatch.setattr(
        "webapp.worker.load_analysis_settings",
        lambda: _settings(max_attempts=2),
    )

    def analyze(markdown, *, parse_mode="auto", external_attempt_budget=None):
        budgets.append(external_attempt_budget)
        return markdown

    def serialize(marker):
        payload = _analysis_payload(approved=marker == "strong-visual-read")
        if marker == "strong-visual-read":
            payload["metrics"]["authoritative"] = True
            payload["source_validation"] = {"ok": True}
            payload["extraction"] = {
                "attempt_count": 1,
                "attempts": [{
                    "provider": "google_gemini",
                    "model": "gemini-3.5-flash-lite",
                    "source_kind": "ocr_markdown",
                    "status": "success",
                    "estimated_cost_usd": 0.02,
                }],
                "estimated_cost_usd": 0.02,
                "cost_complete": True,
            }
        return payload

    monkeypatch.setattr("webapp.worker.analyze_markdown", analyze)
    monkeypatch.setattr("webapp.worker.report_to_json", serialize)

    run_job(job.id, b"%PDF-fake", "unknown-scan.pdf", store)

    result = store.get(job.id)
    assert result.status == "done"
    assert result.parse_model == "gemini-document-ocr:gemini-3.5-flash-lite"
    assert budgets == [0, 1]
    assert result.analysis["extraction"]["attempt_count"] == 2
    assert result.analysis["extraction"]["estimated_cost_usd"] == pytest.approx(0.03)
    assert result.analysis["processing"]["candidates"][1]["primary_ocr_error_type"] == "RuntimeError"
    assert result.analysis["extraction"]["attempt_limit"] == 2


def test_auto_route_shares_one_external_attempt_budget_across_native_and_visual(monkeypatch):
    store = JobStore()
    job = store.create("unknown-digital.pdf")
    native = _Doc("native-pdf-text", "weak-native-read")
    visual = _Doc("baidu/Unlimited-OCR", "strong-visual-read")
    budgets = []

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf, filename: native)
    monkeypatch.setattr(
        "webapp.worker._local_ocr_statement",
        lambda pdf, filename: (_ for _ in ()).throw(AssertionError("local OCR should not run")),
    )
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *args, **kwargs: visual)
    monkeypatch.setattr(
        "webapp.worker.load_analysis_settings",
        lambda: _settings(max_attempts=2),
    )

    def analyze(markdown, *, parse_mode="auto", external_attempt_budget=None):
        budgets.append(external_attempt_budget)
        return markdown

    def serialize(marker):
        payload = _analysis_payload(approved=marker == "strong-visual-read")
        payload["extraction"] = {
            "attempt_count": 1,
            "attempts": [
                {
                    "model": "gemini-3.5-flash-lite",
                    "status": "success",
                    "estimated_cost_usd": 0.02,
                }
            ],
            "estimated_cost_usd": 0.02,
            "cost_complete": True,
        }
        return payload

    monkeypatch.setattr("webapp.worker.analyze_markdown", analyze)
    monkeypatch.setattr("webapp.worker.report_to_json", serialize)

    run_job(job.id, b"%PDF-fake", "unknown-digital.pdf", store)

    result = store.get(job.id)
    assert budgets == [2, 1]
    assert result.analysis["extraction"]["attempt_count"] == 2
    assert result.analysis["extraction"]["attempt_limit"] == 2
    assert result.analysis["extraction"]["estimated_cost_usd"] == pytest.approx(0.04)
    assert {
        attempt["document_source_model"]
        for attempt in result.analysis["extraction"]["attempts"]
    } == {"native-pdf-text", "baidu/Unlimited-OCR"}


def test_auto_route_does_not_spend_ocr_on_source_contradiction(monkeypatch):
    store = JobStore()
    job = store.create("contradictory.pdf")
    native = _Doc("native-pdf-text", "contradictory-read")

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf, filename: native)
    monkeypatch.setattr(
        "webapp.worker._local_ocr_statement",
        lambda pdf, filename: (_ for _ in ()).throw(AssertionError("local OCR should not run")),
    )
    monkeypatch.setattr(
        "webapp.worker.parse_statement",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("visual OCR should not run")),
    )
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": markdown)
    monkeypatch.setattr(
        "webapp.worker.report_to_json",
        lambda marker: _analysis_payload(
            approved=False,
            flags=["summary_math_inconsistent"],
        ),
    )

    run_job(job.id, b"%PDF-fake", "contradictory.pdf", store)

    result = store.get(job.id)
    assert result.status == "done"
    assert result.parse_model == "native-pdf-text"
    assert result.analysis["quality"]["corporate_use"] == "manual_review_required"
    assert result.analysis["processing"]["visual_retry_performed"] is False
