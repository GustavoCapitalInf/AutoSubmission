"""P20-SEAM: OQ3 = ALLOWLIST — the $0 / no-paid-vendor endpoint policy, in code.

`OCR_BASE_URL` was a plain env read with no allowlist (F-4(a)): one env var
repointed the image-bearing request at any host, and
`ocr/availability.py:5-6`'s "no paid vendor is involved and none may be" was a
convention nothing enforced. `ocr.endpoint_policy` is the enforcement:
loopback and private endpoints are allowed by default; a remote endpoint is
allowed ONLY with the exact opt-in literal `OCR_REMOTE_OPT_IN=
I_ACCEPT_REMOTE_PAID_OCR`; refusal happens before any client is built or
anything is sent. No test here ever performs a real network call — every
client is a fake or the refusal path never reaches `openai` at all.
"""
from __future__ import annotations

import pytest

from ocr.config import Settings
from ocr.endpoint_policy import (
    OCR_REMOTE_OPT_IN_ENV,
    OCR_REMOTE_OPT_IN_LITERAL,
    EndpointDecision,
    EndpointRefused,
    check_endpoint,
    classify_endpoint,
    remote_opt_in_from_env,
)
from ocr.ocr_client import _build_client


# ---------------------------------------------------------------------------
# classify_endpoint: every endpoint class tested
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:8000/v1", "loopback"),
        ("http://localhost/v1", "loopback"),
        ("http://LOCALHOST:8000/v1", "loopback"),
        ("http://127.0.0.1:8000/v1", "loopback"),
        ("http://127.255.255.255/v1", "loopback"),
        ("http://[::1]:8000/v1", "loopback"),
        ("http://192.168.1.5:8000/v1", "private"),
        ("http://10.0.0.1:8000/v1", "private"),
        ("http://172.16.0.1:8000/v1", "private"),
        ("http://169.254.1.1:8000/v1", "private"),
        ("http://[fe80::1]:8000/v1", "private"),
        ("http://[fc00::1]:8000/v1", "private"),
        ("http://myworkstation.local:8000/v1", "private"),
        ("http://MyBox.LOCAL:8000/v1", "private"),
        ("https://foo.runpod.net/v1", "remote"),
        ("http://8.8.8.8:8000/v1", "remote"),
        ("https://api.openai.com/v1", "remote"),
        ("http://example.com/v1", "remote"),
        ("not a url", "invalid"),
        ("ftp://localhost/v1", "invalid"),
        ("", "invalid"),
        ("http://", "invalid"),
        ("http:///v1", "invalid"),
        # MAJOR-1 (PHASE2_P20SEAM_REVIEW.md): look-alike hostnames that a
        # substring/prefix/suffix check (rather than exact-match /
        # true-suffix) would misclassify as local. The real code already
        # checks `host == "localhost"` and `host.endswith(".local")`, so
        # these pass today; they exist to KILL mutants R2/R9 below, which
        # widen those checks to `in`.
        ("http://localhost.evil.com/v1", "remote"),
        ("http://evil.com.localhost/v1", "remote"),
        ("http://x.local.evil.com/v1", "remote"),
        ("http://10.0.0.1@evil.com/v1", "remote"),
        ("http://localhost@evil.com/v1", "remote"),
        # MINOR-5: the cloud metadata endpoint (IMDS) is a standing SSRF
        # target; excluded from `private` regardless of the general
        # link-local/ULA rule, so it always needs the explicit opt-in.
        ("http://169.254.169.254/latest/meta-data/", "remote"),
        ("http://[fd00:ec2::254]/v1", "remote"),
        # MINOR-7: CGNAT (RFC 6598) is not private — routed by the ISP, not
        # exclusive to the caller's network — regardless of what a given
        # interpreter's `ipaddress.IPv4Address.is_private` says (this moved
        # across 3.12 patch releases). IPv6-mapped IPv4 is normalised
        # explicitly rather than left to interpreter-version delegation.
        ("http://100.64.0.1:8000/v1", "remote"),
        ("http://[::ffff:127.0.0.1]/v1", "loopback"),
        ("http://[::ffff:10.0.0.1]/v1", "private"),
        # MINOR-6: a raw tab/CR/LF anywhere in the URL is refused before
        # parsing — `urlsplit` silently drops these, so classifying the
        # stripped string would answer for a different string than the one
        # a client is actually handed.
        ("http://loc\talhost/v1", "invalid"),
        ("http://localhost\r\n/v1", "invalid"),
        ("http://localhost/v1\t", "invalid"),
    ],
)
def test_classify_endpoint(url, expected):
    assert classify_endpoint(url) == expected


def test_classify_endpoint_rejects_non_string():
    assert classify_endpoint(None) == "invalid"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# remote_opt_in_from_env: the exact literal, nothing else
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (OCR_REMOTE_OPT_IN_LITERAL, True),
        ("1", False),
        ("true", False),
        ("True", False),
        ("yes", False),
        ("I_ACCEPT_REMOTE_PAID_OCR ", False),  # trailing space: not exact
        (" I_ACCEPT_REMOTE_PAID_OCR", False),
        ("i_accept_remote_paid_ocr", False),  # case matters
        ("", False),
    ],
)
def test_remote_opt_in_requires_the_exact_literal(value, expected):
    assert remote_opt_in_from_env({OCR_REMOTE_OPT_IN_ENV: value}) is expected


def test_remote_opt_in_absent_env_is_false():
    assert remote_opt_in_from_env({}) is False


def test_remote_opt_in_reads_the_real_environment_by_default(monkeypatch):
    monkeypatch.delenv(OCR_REMOTE_OPT_IN_ENV, raising=False)
    assert remote_opt_in_from_env() is False
    monkeypatch.setenv(OCR_REMOTE_OPT_IN_ENV, OCR_REMOTE_OPT_IN_LITERAL)
    assert remote_opt_in_from_env() is True


# ---------------------------------------------------------------------------
# check_endpoint: the enforcement decision, every class
# ---------------------------------------------------------------------------


def test_loopback_and_private_allowed_without_opt_in():
    for url in ("http://localhost:8000/v1", "http://192.168.1.5:8000/v1"):
        decision = check_endpoint(url, opt_in=False)
        assert decision.allowed is True
        assert decision.klass in ("loopback", "private")


def test_remote_without_opt_in_is_refused():
    """CASE 8: remote/paid endpoint without explicit opt-in -> refused."""
    decision = check_endpoint("https://foo.runpod.net/v1", opt_in=False)
    assert decision.allowed is False
    assert decision.klass == "remote"


def test_remote_with_opt_in_is_allowed():
    decision = check_endpoint("https://foo.runpod.net/v1", opt_in=True)
    assert decision.allowed is True
    assert decision.klass == "remote"


def test_invalid_is_never_allowed_even_with_opt_in():
    for opt_in in (False, True):
        decision = check_endpoint("not a url", opt_in=opt_in)
        assert decision.allowed is False
        assert decision.klass == "invalid"


# ---------------------------------------------------------------------------
# _build_client: refusal happens BEFORE any client is built or sent
# ---------------------------------------------------------------------------


def _settings(base_url: str, *, remote_opt_in: bool = False) -> Settings:
    return Settings(
        base_url=base_url, model="baidu/Unlimited-OCR", api_key="EMPTY", timeout=5,
        retries=1, ngram_size=35, window_size=128, max_workers=1,
        remote_opt_in=remote_opt_in,
    )


def test_build_client_refuses_remote_before_importing_openai(monkeypatch):
    """CASE 7 / the refusal-before-request test: no client, no import, no send."""
    import sys

    had_openai = "openai" in sys.modules
    with pytest.raises(EndpointRefused) as excinfo:
        _build_client(_settings("https://foo.runpod.net/v1"))
    assert excinfo.value.decision.klass == "remote"
    assert excinfo.value.decision.allowed is False
    # openai was never imported as a side effect of the refusal (unless some
    # unrelated earlier test already imported it — this only tightens the
    # claim when it is meaningful to make).
    if not had_openai:
        assert "openai" not in sys.modules


def test_build_client_constructs_nothing_after_a_refusal(monkeypatch):
    """MINOR-3 (PHASE2_P20SEAM_REVIEW.md): order-independent, unlike the
    `had_openai` check above (which degrades to "an exception was raised"
    once some earlier test has already imported `openai`). A construction-
    counting sentinel proves the stronger, order-independent claim directly:
    zero `OpenAI(...)` constructions happen after a refusal, regardless of
    whether the module was already imported."""
    constructions = []

    class _CountingOpenAI:
        def __init__(self, **kwargs):
            constructions.append(kwargs)

    import openai
    monkeypatch.setattr(openai, "OpenAI", _CountingOpenAI)

    with pytest.raises(EndpointRefused):
        _build_client(_settings("https://foo.runpod.net/v1"))
    assert constructions == []


def test_build_client_allows_loopback_and_constructs_a_client(monkeypatch):
    calls = []

    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key, timeout):
            calls.append(base_url)
            self.base_url = base_url

    import openai
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = _build_client(_settings("http://localhost:8000/v1"))
    assert isinstance(client, _FakeOpenAI)
    assert calls == ["http://localhost:8000/v1"]


def test_build_client_allows_remote_with_opt_in(monkeypatch):
    """MINOR-2: the opt-in is re-derived from the real env var, not trusted
    from `settings.remote_opt_in` — so the REAL literal must be set, not
    merely the field, for this to succeed."""
    calls = []

    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key, timeout):
            calls.append(base_url)

    import openai
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv(OCR_REMOTE_OPT_IN_ENV, OCR_REMOTE_OPT_IN_LITERAL)

    client = _build_client(_settings("https://foo.runpod.net/v1", remote_opt_in=True))
    assert calls == ["https://foo.runpod.net/v1"]


def test_endpoint_class_field_cannot_spoof_the_real_check(monkeypatch):
    """`Settings.endpoint_class` is descriptive only. A hand-built Settings
    that CLAIMS `endpoint_class="loopback"` for a remote `base_url` must
    still be refused — the enforcement re-derives the class from
    `base_url`, never trusting the field."""
    monkeypatch.delenv(OCR_REMOTE_OPT_IN_ENV, raising=False)
    settings = Settings(
        base_url="https://foo.runpod.net/v1", model="baidu/Unlimited-OCR",
        api_key="EMPTY", timeout=5, retries=1, ngram_size=35, window_size=128,
        max_workers=1, endpoint_class="loopback", remote_opt_in=False,
    )
    with pytest.raises(EndpointRefused):
        _build_client(settings)


def test_remote_opt_in_field_cannot_spoof_the_real_check(monkeypatch):
    """MINOR-2 (PHASE2_P20SEAM_REVIEW.md): `Settings.remote_opt_in` is
    descriptive only, exactly like `endpoint_class` above. A hand-built
    `Settings(..., remote_opt_in=True)` for a remote `base_url` must still
    be refused when the REAL env var is not set — before this fix, only
    `endpoint_class` was re-derived, so this exact construction reached a
    remote endpoint with the opt-in literal never having been set anywhere."""
    monkeypatch.delenv(OCR_REMOTE_OPT_IN_ENV, raising=False)
    settings = Settings(
        base_url="https://foo.runpod.net/v1", model="baidu/Unlimited-OCR",
        api_key="EMPTY", timeout=5, retries=1, ngram_size=35, window_size=128,
        max_workers=1, remote_opt_in=True,
    )
    assert settings.remote_opt_in is True  # the field IS set...
    with pytest.raises(EndpointRefused):
        _build_client(settings)  # ...but the enforcement does not trust it


# ---------------------------------------------------------------------------
# Single endpoint per process: a failing local rung never hops
# ---------------------------------------------------------------------------


def test_probe_never_retries_against_a_second_host(monkeypatch):
    """CASE 8's other half: a failing loopback endpoint yields the rung's
    failure and never a request elsewhere. `_build_client` takes exactly one
    `settings.base_url` and constructs exactly one client for it; there is no
    fallback list anywhere in this module."""
    from ocr.availability import probe_visual_ocr

    contacted = []

    class _FailingModels:
        def list(self):
            raise ConnectionError("refused")

    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key, timeout):
            contacted.append(base_url)
            self.models = _FailingModels()

    import openai
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    settings = _settings("http://localhost:8000/v1")
    status = probe_visual_ocr(settings=settings)
    assert status.available is False
    assert status.base_url == "http://localhost:8000/v1"
    # The client was constructed exactly once, and only for the one
    # configured base_url — no second host was ever named.
    assert contacted == ["http://localhost:8000/v1"]


def test_endpoint_class_and_remote_opt_in_exposed_on_settings():
    """Provenance surface (F-4(a)): both fields are readable on Settings for
    the cache key and telemetry (cell C keys on them)."""
    s = Settings(
        base_url="https://foo.runpod.net/v1", model="baidu/Unlimited-OCR",
        api_key="EMPTY", timeout=5, retries=1, ngram_size=35, window_size=128,
        max_workers=1, remote_opt_in=True,
    )
    assert s.endpoint_class == "remote"
    assert s.remote_opt_in is True


# ---------------------------------------------------------------------------
# price_for on a remote endpoint: still None unless a cited price exists
# ---------------------------------------------------------------------------


def test_price_for_does_not_invent_a_remote_price():
    from telemetry.prices import price_for

    # A remote endpoint changes nothing about which models are priced: an
    # unlisted model prices to None (unknown), never a guessed number, and
    # `endpoint_class` is not a `price_for` input at all — it cannot become
    # one without adding a price the audit did not cite.
    assert price_for("some-remote-vendor-model") is None
