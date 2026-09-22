"""Synthetic seam checks; no model requests or customer fixtures."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from ocr.document import StatementMarkdown
from ocr.visual_pair_config import (
    CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL,
    VisualPairAuthorizationError, VisualPairConfigError, VisualPairSettings,
    check_remote_authorization, load_visual_pair_settings,
)
from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import _pair_fallback_needed, _read_visual_pair, run_job


def test_customer_authorization_defaults_closed_even_for_loopback():
    settings = load_visual_pair_settings({})
    assert settings.execution_class == "remote_paid"
    assert settings.review_policy == "always_review"
    with pytest.raises(VisualPairAuthorizationError, match="remote_customer_data_refused"):
        check_remote_authorization(settings, environ={})
    check_remote_authorization(settings, data_scope="synthetic", environ={})


def test_customer_opt_in_requires_both_settings_and_current_environment():
    env = {CUSTOMER_DATA_OPT_IN_ENV: CUSTOMER_DATA_OPT_IN_LITERAL}
    authorized = load_visual_pair_settings(env)
    check_remote_authorization(authorized, environ=env)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(authorized, environ={})
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(VisualPairSettings(), environ=env)
    with pytest.raises(VisualPairAuthorizationError):
        check_remote_authorization(authorized, data_scope="uploaded-synthetic", environ=env)


@pytest.mark.parametrize("changes", [
    {"proposer_revision": "main"}, {"reviewer_revision": "main"},
    {"proposer_url": "https://remote.invalid/v1"},
    {"reviewer_url": "http://127.0.0.1:18022/v1?token=secret"},
    {"execution_class": "loopback"}, {"execution_class": "local_free"}, {"review_policy": "auto"},
])
def test_pins_and_closed_configuration(changes):
    with pytest.raises(VisualPairConfigError):
        VisualPairSettings(**changes)


def test_pair_fence_precedes_cache_lookup(monkeypatch, tmp_path):
    # Import is intentionally satisfied by the actual pipeline: no request is made.
    monkeypatch.delenv(CUSTOMER_DATA_OPT_IN_ENV, raising=False)
    monkeypatch.setattr("webapp.worker._cached_ocr_timed", lambda *a, **k: pytest.fail("cache lookup before authorization"))
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("synthetic.pdf")
    with pytest.raises(VisualPairAuthorizationError):
        _read_visual_pair(job.id, store, store.cache, b"synthetic", "synthetic.pdf",
                          SimpleNamespace(content_sha256="0" * 64), timer=None)


@pytest.mark.parametrize("mode", ["auto", "deterministic"])
@pytest.mark.parametrize("matched", [True, False])
def test_narrow_automatic_fallback_only_after_deterministic_failure(monkeypatch, tmp_path, mode, matched):
    monkeypatch.setenv("OCR_ALLOW_VISUAL_PAIR", "1")
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("synthetic.pdf")
    doc = StatementMarkdown("synthetic.pdf", "native-pdf-text", ["synthetic text"])
    calls = []
    def read(*args, **kwargs):
        calls.append(("native", kwargs["allow_visual_ocr"]))
        return doc
    def analyze(document, filename, parse_mode, *args, **kwargs):
        calls.append(("analysis", parse_mode))
        result = {"quality": {"level": "transaction_level"}} if matched or len(calls) > 3 else None
        return "synthetic", "synthetic", result, None
    monkeypatch.setattr("webapp.worker.parse_statement", read)
    monkeypatch.setattr("webapp.worker._analyze_doc", analyze)
    monkeypatch.setattr("webapp.worker._read_visual_pair", lambda *a, **k: calls.append(("pair", True)) or doc)
    run_job(job.id, b"%PDF-fake", "synthetic.pdf", store, parse_mode=mode)
    assert store.get(job.id).status == "done"
    assert calls[:2] == [("native", False), ("analysis", "deterministic")]
    assert any(call[0] == "pair" for call in calls) is not matched


def test_narrow_does_not_turn_withheld_into_an_implicit_gpu_request():
    payload = {"statement": {}, "metrics": {"average_daily_balance": None}}
    assert not _pair_fallback_needed(payload, "narrow")
    assert _pair_fallback_needed(payload, "broad")
    assert _pair_fallback_needed(None, "narrow")


@pytest.mark.parametrize("second_adb,expected", [(10.0, False), (None, True)])
def test_broad_fallback_checks_every_account_without_failing_document_shape(second_adb, expected):
    def account(adb):
        return {"statement": {}, "metrics": {"average_daily_balance": adb},
                "quality": {"corporate_use": "approved"}, "integrity": {"flags": []}}

    document = {"document": {}, "accounts": [account(10.0), account(second_adb)]}
    assert _pair_fallback_needed(document, "broad") is expected
    assert _pair_fallback_needed(document, "narrow") is False


def test_pair_cache_is_partitioned_and_restores_review_evidence(monkeypatch, tmp_path):
    from webapp.artifact_cache import cached_ocr, ocr_settings_key
    from ocr.config import load_settings
    monkeypatch.setattr("vlm.pair.visual_pair_manifest", lambda: {"synthetic_contract": 1})
    settings = load_settings()
    original = ocr_settings_key(ocr_settings=settings)
    assert original == ocr_settings_key(ocr_settings=replace(settings, allow_visual_pair=True))
    pair_key = ocr_settings_key(allow_visual_pair=True, ocr_settings=settings)
    assert pair_key != original
    monkeypatch.setattr("vlm.pair.visual_pair_manifest", lambda: {"synthetic_contract": 2})
    assert pair_key != ocr_settings_key(allow_visual_pair=True, ocr_settings=settings)
    store = JobStore(Storage(tmp_path / "data"))
    evidence = {"version": 1, "gate": {"admitted": False, "reasons": ["no_rows"]}, "confidence": {"counts": {}}}
    doc = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["synthetic"], visual_pair=evidence)
    flags = dict(cache=store.cache, source_file="synthetic.pdf", force_ocr=True,
                 allow_visual_ocr=False, allow_visual_pair=True)
    first = cached_ocr(b"synthetic", compute=lambda: doc, **flags)
    second = cached_ocr(b"synthetic", compute=lambda: pytest.fail("re-read cached input"), **flags)
    assert not first.cached and second.cached
    assert second.value.visual_pair == evidence


def test_pair_admission_is_checked_before_any_normal_analysis(monkeypatch, tmp_path):
    from vlm.pair_adapter import VisualPairAdmissionError
    from webapp.worker import _analyze_doc
    doc = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["synthetic"],
                            visual_pair={"version": 1, "gate": {"admitted": False}})
    monkeypatch.setattr("webapp.worker.analyze_document", lambda *a, **k: pytest.fail("bank parser bypassed pair gate"))
    def refuse(*args, **kwargs):
        raise VisualPairAdmissionError("visual pair requires human review")
    monkeypatch.setattr("vlm.pair_adapter.analyze_visual_pair", refuse)
    _, _, payload, error = _analyze_doc(doc, "synthetic.pdf", "auto")
    assert payload is None
    assert error == "visual pair requires human review"


def test_pair_telemetry_counts_two_actual_models_and_no_invented_analysis_call():
    from telemetry.record import model_calls_for, source_path_for, source_path_unrecognized_model
    doc = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["synthetic"],
        extraction_telemetry={"execution_class": "remote_paid", "customer_data_opt_in": False,
            "pages": [{"stage": "proposer", "prompt_tokens": 10, "completion_tokens": 15},
                      {"stage": "reviewer", "prompt_tokens": 20, "completion_tokens": 25}]})
    assert source_path_for(doc.model) == "visual_pair"
    assert not source_path_unrecognized_model(doc.model)
    calls = model_calls_for(doc, {"model_used": "visual-pair-dots-qwen-generic"})
    assert len(calls) == 2
    assert [call["calls"] for call in calls] == [1, 1]
    assert [call["completion_tokens"] for call in calls] == [15, 25]
    assert all(call["endpoint_class"] == "remote_paid" for call in calls)
    doc.extraction_telemetry = None
    assert [call["calls"] for call in model_calls_for(doc, None)] == [0, 0]


def test_held_confidence_banner_uses_counts_without_changing_analysis_input(monkeypatch):
    from vlm.pair_adapter import VisualPairAdmissionError
    from webapp.worker import _analyze_doc
    doc = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["synthetic text"],
        visual_pair={"gate": {"admitted": True}, "confidence": {"score": 0.75,
                    "counts": {"agreed": 3, "corrected": 1, "added": "<script>bad</script>"}}})
    def hold(*args, **kwargs):
        raise VisualPairAdmissionError("visual pair requires human review")
    monkeypatch.setattr("vlm.pair_adapter.analyze_visual_pair", hold)
    markdown, rendered, payload, error = _analyze_doc(doc, "synthetic.pdf", "auto")
    assert "Provisional extraction confidence: 75.0%" in rendered
    assert "3 confirmed, 1 corrected, 0 added" in rendered
    assert "Human review required" in rendered
    assert "<script>bad</script>" not in rendered
    assert markdown == doc.to_markdown()
    assert payload is None and error == "visual pair requires human review"
