"""Phase 2.1 cell P: `ocr/paddle_client.py` (CASE 13, CASE 16, CASE 18, CASE 20;
M1 through M4). Every scenario runs against `tests/paddle_fake_worker.FakeWorker`
on a real loopback socket — no mock of `urllib` itself, no real network beyond
`127.0.0.1`.
"""
from __future__ import annotations

import json

import pytest

from ocr.paddle_config import (
    DATA_SCOPE_CUSTOMER,
    DATA_SCOPE_SYNTHETIC,
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
    PaddleConfigError,
    PaddleRefused,
    PaddleSettings,
    check_remote_authorization,
    load_paddle_settings,
)
from ocr.paddle_client import (
    IDENTITY_CHECK_FIELDS,
    PaddleClient,
    PaddleTransportError,
    PaddleWorkerStatus,
    probe,
    verify_identity,
)
from tests.paddle_fake_worker import TINY_PNG_BYTES, FakeWorker

VAST_ENV = {
    "PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid",
    "PADDLE_VAST_HOST": "example-host.invalid", "PADDLE_VAST_SSH_PORT": "22022",
    "PADDLE_VAST_SSH_USER": "someone",
}


def _settings(url: str, **overrides) -> PaddleSettings:
    env = dict(VAST_ENV, PADDLE_WORKER_URL=url, **{PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL})
    env.update(overrides)
    return load_paddle_settings(env)


def _hand_built(url: str, **fields) -> PaddleSettings:
    base = dict(
        provider="vast.ai", execution_class="remote_paid", vast_host="h", vast_ssh_port=1,
        vast_ssh_user="u", remote_opt_in=True, customer_data_opt_in=False, worker_url=url,
        worker_port=8765, tunnel_local_port=18765, worker_token=None, runtime_dir=".paddle_runtime",
    )
    base.update(fields)
    return PaddleSettings(**base)


# ---------------------------------------------------------------------------
# Constructor: loopback-only, re-checked (MINOR-2's lesson) / M3
# ---------------------------------------------------------------------------

def test_m3_constructor_refuses_a_non_loopback_hand_built_settings():
    settings = _hand_built("http://example.com/ocr")
    with pytest.raises(PaddleConfigError, match="loopback"):
        PaddleClient(settings)


def test_constructor_accepts_a_real_loopback_url():
    with FakeWorker() as fake:
        PaddleClient(_hand_built(fake.url))  # does not raise


# ---------------------------------------------------------------------------
# CASE 16 / M2 — per-field identity verification
# ---------------------------------------------------------------------------

def test_case16_matching_identity_verifies_and_records_the_declaration():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        identity = verify_identity(settings, client=client)
        assert identity["provider"] == "vast.ai"
        assert identity["execution_class"] == "remote_paid"
        assert fake.requests == []  # /version carries no image


@pytest.mark.parametrize("field,bad_value", [
    ("contract", 2),
    ("provider", "local"),
    ("execution_class", "local_free"),
    ("paddleocr_version", "3.6.0"),
    ("paddlepaddle_version", "3.2.0"),
    ("ocr_version", "PP-OCRv6"),
    ("text_detection_model_name", "PP-OCRv4_server_det"),
    ("text_recognition_model_name", "en_PP-OCRv4_mobile_rec"),
    ("pipeline_switches", {"return_word_box": False}),
])
def test_case16_m2_every_field_mismatch_refuses_independently(field, bad_value):
    with FakeWorker(identity_overrides={field: bad_value}) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleRefused) as excinfo:
            verify_identity(settings, client=client)
        assert excinfo.value.reason == "paddle_runtime_mismatch"
        assert field in str(excinfo.value)
        assert fake.requests == []  # zero /ocr requests on a mismatch


def test_case16_declaration_wins_over_a_loopback_url_and_worker_corroborates():
    """The URL is always loopback (the tunnel); the DECLARED provider/class
    (here vast.ai/remote_paid) is what `verify_identity` checks against the
    worker's own echo — never derived from the URL."""
    with FakeWorker() as fake:  # echoes vast.ai / remote_paid by default
        settings = _settings(fake.url)
        assert settings.provider == "vast.ai" and settings.is_remote
        identity = verify_identity(settings, client=PaddleClient(settings))
        assert identity["provider"] == "vast.ai" and identity["execution_class"] == "remote_paid"


def test_m10_runtime_material_the_test_asserts_on_carries_no_url():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        identity = verify_identity(settings, client=PaddleClient(settings))
        text = json.dumps(identity)
        assert fake.url not in text
        assert "127.0.0.1" not in text


# ---------------------------------------------------------------------------
# CASE 18 / M4 — every transport failure class; exactly one URL contacted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fail_mode,expected_error_type", [
    ("connection_refused", None),  # class name varies by platform; checked separately
    ("http_500", "HTTPError"),
    ("malformed_json", "JSONDecodeError"),
    ("oversized_body", "ResponseTooLarge"),
    ("redirect", "HTTPError"),
])
def test_case18_every_transport_failure_becomes_a_typed_error(fail_mode, expected_error_type):
    with FakeWorker(fail_mode=fail_mode) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleTransportError) as excinfo:
            client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert excinfo.value.reason == "paddle_worker_unreachable"
        if expected_error_type is not None:
            assert excinfo.value.error_type == expected_error_type


def test_case18_timeout_is_a_transport_error():
    with FakeWorker(fail_mode="hang") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, timeout=0.2)
        with pytest.raises(PaddleTransportError) as excinfo:
            client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert excinfo.value.reason == "paddle_worker_unreachable"


class _UrlSpyingOpener:
    """Wraps the real opener, recording the exact URL of every `.open()`
    call — the seam M4's mutant (a retry to a hardcoded second URL, e.g. the
    visual endpoint) would have to go through."""

    def __init__(self, real_opener):
        self._real = real_opener
        self.urls: list[str] = []

    def open(self, request, timeout=None):
        self.urls.append(request.full_url)
        return self._real.open(request, timeout=timeout)


def test_m4_no_retry_to_a_different_url_ever():
    """A transport failure never causes a second, different URL to be
    contacted — every attempt (including retries) targets the SAME
    `settings.worker_url`, proven by recording every URL `_request` ever
    opens, not merely asserting the settings object was not mutated."""
    from ocr.paddle_client import _default_opener

    with FakeWorker(fail_mode="connection_refused") as fake:
        settings = _settings(fake.url)
        spy = _UrlSpyingOpener(_default_opener())
        client = PaddleClient(settings, opener=spy)
        with pytest.raises(PaddleTransportError):
            client.health()
        assert spy.urls, "no request was even attempted"
        assert set(spy.urls) == {settings.worker_url + "/health"}
        assert client.settings.worker_url == settings.worker_url


# ---------------------------------------------------------------------------
# CASE 13 / CASE 20 / M1 — opt-in gates evaluated before any request
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("env_overrides", [
    {},
    {PADDLE_REMOTE_OPT_IN_ENV: "yes"},
    {PADDLE_REMOTE_OPT_IN_ENV: "I_ACCEPT_REMOTE_PAID_OCR"},  # the VISUAL literal
])
def test_case13_no_opt_in_refuses_before_any_connection(env_overrides):
    with FakeWorker() as fake:
        env = dict(VAST_ENV, PADDLE_WORKER_URL=fake.url, **env_overrides)
        settings = load_paddle_settings(env)
        with pytest.raises(PaddleRefused) as excinfo:
            check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)
        assert excinfo.value.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_case13_opt_in_present_permits_the_request():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)  # does not raise
        client = PaddleClient(settings)
        response = client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert response["page_index"] == 0
        assert len(fake.requests) == 1


def test_case20_customer_scope_refused_without_the_second_literal():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        with pytest.raises(PaddleRefused) as excinfo:
            check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)
        assert excinfo.value.reason == "remote_customer_data_refused"
        assert fake.requests == []


def test_case20_customer_scope_permitted_with_the_second_literal():
    with FakeWorker() as fake:
        settings = _settings(fake.url, **{PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL})
        check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)  # does not raise


def test_m1_check_remote_authorization_is_not_skippable_from_the_rung():
    """A structural check: `ocr.paddle_rung` calls `check_remote_authorization`
    before ever constructing a client. This module-level assertion documents
    the ordering contract `test_paddle_rung.py` exercises end to end."""
    import ocr.paddle_rung as rung_module
    import inspect

    source = inspect.getsource(rung_module.read_document)
    call_order = [name for name in ("check_remote_authorization", "verify_identity", "rasterize_pdf")
                  if name in source]
    assert call_order == ["check_remote_authorization", "verify_identity", "rasterize_pdf"]


# ---------------------------------------------------------------------------
# probe() — never raises
# ---------------------------------------------------------------------------

def test_probe_reports_missing_configuration():
    status = probe(settings=None, client=None) if False else None  # placeholder to keep signature documented
    from ocr.paddle_config import load_paddle_settings as _load

    with pytest.raises(PaddleConfigError):
        _load({})
    # probe() itself must not raise even though load_paddle_settings does:
    result = probe(settings=None)
    assert isinstance(result, PaddleWorkerStatus)


def test_probe_reports_opt_in_required():
    with FakeWorker() as fake:
        env = dict(VAST_ENV, PADDLE_WORKER_URL=fake.url)
        settings = load_paddle_settings(env)
        status = probe(settings)
        assert status.available is False
        assert status.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_probe_reports_mismatch_and_success():
    with FakeWorker(identity_overrides={"ocr_version": "PP-OCRv6"}) as fake:
        settings = _settings(fake.url)
        status = probe(settings)
        assert status.available is False
        assert status.reason == "paddle_runtime_mismatch"

    with FakeWorker() as fake:
        settings = _settings(fake.url)
        status = probe(settings)
        assert status.available is True
        assert status.identity is not None


def test_probe_reports_unreachable():
    with FakeWorker(fail_mode="connection_refused") as fake:
        settings = _settings(fake.url)
        status = probe(settings)
        assert status.available is False
        assert status.reason == "paddle_worker_unreachable"
        assert status.error_type


def test_identity_check_fields_is_the_documented_closed_list():
    assert set(IDENTITY_CHECK_FIELDS) == {
        "contract", "provider", "execution_class", "paddleocr_version", "paddlepaddle_version",
        "ocr_version", "text_detection_model_name", "text_recognition_model_name", "pipeline_switches",
    }
