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
#: MAJOR-2 (PHASE2_P21PADDLE_REVIEW.md): `check_remote_authorization` and
#: `PaddleClient` now RE-DERIVE the remote opt-in from `environ` (default the
#: real `os.environ`, which never carries this test's placeholder literal) —
#: so every call site that wants the PERMITTED path must pass the SAME dict
#: `_settings()` used to build the settings object, as `environ=`. This is
#: that dict, defined once so it cannot drift from `_settings`'s own.
REMOTE_ENVIRON = dict(VAST_ENV, **{PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL})


def _settings(url: str, **overrides) -> PaddleSettings:
    env = dict(REMOTE_ENVIRON, PADDLE_WORKER_URL=url)
    env.update(overrides)
    return load_paddle_settings(env)


def _environ_for(url: str, **overrides) -> dict:
    """The exact environ `_settings(url, **overrides)` was built from — pass
    this as `environ=` wherever a test wants the PERMITTED path through
    `check_remote_authorization` / `PaddleClient` / `probe`."""
    env = dict(REMOTE_ENVIRON, PADDLE_WORKER_URL=url)
    env.update(overrides)
    return env


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
        PaddleClient(_hand_built(fake.url), environ=REMOTE_ENVIRON)  # does not raise


def test_major2_constructor_refuses_a_hand_built_remote_opt_in_without_the_real_env_literal():
    """MAJOR-2: `remote_opt_in=True` on a hand-built `PaddleSettings` is not
    enough — the environment (default `os.environ`, explicitly empty here)
    must ALSO carry the exact literal. A caller that lies about its own
    opt-in flag, or builds settings without going through
    `load_paddle_settings`, cannot construct a remote_paid client."""
    with FakeWorker() as fake:
        settings = _hand_built(fake.url)  # remote_opt_in=True, but no real env literal anywhere
        with pytest.raises(PaddleRefused) as excinfo:
            PaddleClient(settings, environ={})
        assert excinfo.value.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_major2_constructor_refuses_when_settings_flag_disagrees_with_a_present_literal():
    """The reverse asymmetry: the environment carries the literal, but the
    settings object's OWN flag says no — still refused. Both must agree."""
    with FakeWorker() as fake:
        settings = _hand_built(fake.url, remote_opt_in=False)
        with pytest.raises(PaddleRefused) as excinfo:
            PaddleClient(settings, environ=REMOTE_ENVIRON)
        assert excinfo.value.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_local_free_client_needs_no_opt_in_at_all():
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        settings = load_paddle_settings({"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "local_free",
                                         "PADDLE_WORKER_URL": fake.url})
        PaddleClient(settings, environ={})  # does not raise: local_free needs no literal


# ---------------------------------------------------------------------------
# CASE 16 / M2 — per-field identity verification
# ---------------------------------------------------------------------------

def test_case16_matching_identity_verifies_and_records_the_declaration():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
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
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
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
        identity = verify_identity(settings, client=PaddleClient(settings, environ=REMOTE_ENVIRON))
        assert identity["provider"] == "vast.ai" and identity["execution_class"] == "remote_paid"


def test_m10_runtime_material_the_test_asserts_on_carries_no_url():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        identity = verify_identity(settings, client=PaddleClient(settings, environ=REMOTE_ENVIRON))
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
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
        with pytest.raises(PaddleTransportError) as excinfo:
            client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert excinfo.value.reason == "paddle_worker_unreachable"
        if expected_error_type is not None:
            assert excinfo.value.error_type == expected_error_type


def test_case18_timeout_is_a_transport_error():
    with FakeWorker(fail_mode="hang") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, timeout=0.2, environ=REMOTE_ENVIRON)
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
        client = PaddleClient(settings, opener=spy, environ=REMOTE_ENVIRON)
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
        check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC, environ=REMOTE_ENVIRON)  # does not raise
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
        response = client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert response["page_index"] == 0
        assert len(fake.requests) == 1


def test_case20_customer_scope_refused_without_the_second_literal():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        with pytest.raises(PaddleRefused) as excinfo:
            check_remote_authorization(settings, DATA_SCOPE_CUSTOMER, environ=REMOTE_ENVIRON)
        assert excinfo.value.reason == "remote_customer_data_refused"
        assert fake.requests == []


def test_case20_customer_scope_permitted_with_the_second_literal():
    with FakeWorker() as fake:
        env = _environ_for(fake.url, **{PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL})
        settings = _settings(fake.url, **{PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL})
        check_remote_authorization(settings, DATA_SCOPE_CUSTOMER, environ=env)  # does not raise


def test_m1_check_remote_authorization_is_not_skippable_from_the_rung():
    """MINOR-11 (`PHASE2_P21PADDLE_REVIEW.md`): a BEHAVIOURAL killer, not a
    source-substring scan. The prior version grepped
    `inspect.getsource(read_document)` for three names — the M1 mutant's own
    comment ("check_remote_authorization skipped") happened to CONTAIN the
    name it deleted the call to, so the substring scan passed against a rung
    with the real call removed (the two dedicated rung tests still killed
    M1; this test just wasn't one of them, silently). A monkeypatched spy on
    the real function proves it is actually CALLED, before the client is
    even constructed — verified against a document that never leaves this
    process (a synthetic page, a fake worker)."""
    import hashlib

    import ocr.paddle_rung as rung_module
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, render_image_pdf, synthetic_paddle_result

    calls: list[str] = []
    real_check = rung_module.check_remote_authorization

    def spy(settings, data_scope, *, environ=None):
        calls.append("check_remote_authorization")
        return real_check(settings, data_scope, environ=environ)

    page = build_ledger_page(n_rows=1)
    pdf_bytes = render_image_pdf(page, dpi=150)
    sha = hashlib.sha256(pdf_bytes).hexdigest().upper()

    with FakeWorker(result_for=lambda i, b: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
        original = rung_module.check_remote_authorization
        rung_module.check_remote_authorization = spy
        try:
            rung_module.read_document(
                pdf_bytes, document_sha256=sha, data_scope="synthetic",
                settings=settings, client=client, dpi=150, environ=REMOTE_ENVIRON,
            )
        finally:
            rung_module.check_remote_authorization = original
    assert calls == ["check_remote_authorization"], "the rung must call the REAL function exactly once"


# ---------------------------------------------------------------------------
# probe() — never raises
# ---------------------------------------------------------------------------

def test_probe_reports_missing_configuration():
    """MINOR-12: `probe(settings=None)` resolves `settings` via
    `load_paddle_settings()` with NO arguments — the REAL `os.environ` — so
    on a developer machine where the Paddle config happens to be fully set
    this call does not raise `PaddleConfigError` the way an empty
    environment does. Passing an explicit empty `environ=` here closes the
    REMAINING hazard regardless: both `check_remote_authorization` and the
    `PaddleClient` construction downstream re-derive the opt-in from this
    `environ`, which never carries the literal, so `probe()` cannot reach a
    real network call no matter what the ambient environment holds — never
    "if this developer machine happens to have it configured"."""
    with pytest.raises(PaddleConfigError):
        load_paddle_settings({})
    result = probe(settings=None, environ={})
    assert isinstance(result, PaddleWorkerStatus)
    assert result.available is False


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
        status = probe(settings, environ=REMOTE_ENVIRON)
        assert status.available is False
        assert status.reason == "paddle_runtime_mismatch"

    with FakeWorker() as fake:
        settings = _settings(fake.url)
        status = probe(settings, environ=REMOTE_ENVIRON)
        assert status.available is True
        assert status.identity is not None


def test_probe_reports_unreachable():
    with FakeWorker(fail_mode="connection_refused") as fake:
        settings = _settings(fake.url)
        status = probe(settings, environ=REMOTE_ENVIRON)
        assert status.available is False
        assert status.reason == "paddle_worker_unreachable"
        assert status.error_type


def test_identity_check_fields_is_the_documented_closed_list():
    assert set(IDENTITY_CHECK_FIELDS) == {
        "contract", "provider", "execution_class", "paddleocr_version", "paddlepaddle_version",
        "ocr_version", "text_detection_model_name", "text_recognition_model_name", "pipeline_switches",
    }


# ---------------------------------------------------------------------------
# MINOR-9: FakeWorker enforces the SAME contract the real worker does
# ---------------------------------------------------------------------------

def test_minor9_fake_worker_refuses_a_contract_mismatch_like_the_real_one():
    import urllib.error
    import urllib.request

    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
        payload = {
            "contract": 99, "request_id": "r", "page_index": 0,
            "image_png_b64": "bm90IGEgcG5nIGF0IGFsbA==",  # base64("not a png at all")
        }
        import json as _json

        body = _json.dumps(payload).encode("utf-8")
        try:
            urllib.request.urlopen(
                urllib.request.Request(fake.url + "/ocr", data=body, method="POST",
                                       headers={"Content-Type": "application/json"}),
                timeout=5,
            )
            assert False, "the fake must refuse this the same way the real worker does"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            assert _json.loads(exc.read())["error"] == "contract_mismatch"
        assert fake.requests == []


def test_minor9_fake_worker_result_never_carries_input_path():
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=REMOTE_ENVIRON)
        response = client.ocr_page(TINY_PNG_BYTES, page_index=0, request_id="r1")
        assert "input_path" not in response["raw"]
