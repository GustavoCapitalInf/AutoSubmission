"""P20-SEAM: OQ3 = ALLOWLIST — the $0 / no-paid-vendor endpoint policy, in code.

`OCR_BASE_URL` was a plain env read with no allowlist (F-4(a)): one env var
repointed the image-bearing request at any host, and
`ocr/availability.py:5-6`'s "no paid vendor is involved and none may be" was a
convention nothing enforced. `ocr.endpoint_policy` is the enforcement:
loopback and private endpoints are allowed by default; a remote endpoint is
allowed ONLY with the exact opt-in literal `OCR_REMOTE_OPT_IN=
I_ACCEPT_REMOTE_PAID_OCR`; refusal happens before any client is built or
anything is sent. No test here ever performs a real network call.

Model-code removal, slice S2: the visual OCR client (`ocr.ocr_client._build_client`)
and its probe (`ocr.availability.probe_visual_ocr`) were deleted, and their
enforcement tests here went with them (refusal before any client is built, the
spoof checks on the deleted `ocr.config.Settings` fields, the one-host probe).
The policy module itself stays until slice S5 because the Paddle client and the
visual pair still import it, so its unit tests below stay too. The remote-price
check that sat at the end of this file moved to `tests/test_telemetry.py`.
"""
from __future__ import annotations

import pytest

from ocr.endpoint_policy import (
    OCR_REMOTE_OPT_IN_ENV,
    OCR_REMOTE_OPT_IN_LITERAL,
    check_endpoint,
    classify_endpoint,
    remote_opt_in_from_env,
)


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
        # NEW-1 (re-review, closure 1cc759e): the IMDS exclusion is
        # `str(ip) in _IMDS_ADDRESSES`, which only matches AFTER the
        # ipv4_mapped normalisation has turned `::ffff:169.254.169.254`
        # into `169.254.169.254` — that interaction is interpreter-
        # independent (it does not rely on any `is_*` delegation), so unlike
        # N7a (CGNAT, deliberately unkillable on 3.12.3+/3.13+, where
        # `is_private` already excludes CGNAT) this one IS killable here.
        ("http://[::ffff:169.254.169.254]/v1", "remote"),
        # MINOR-6: a raw tab/CR/LF anywhere in the URL is refused before
        # parsing — `urlsplit` silently drops these, so classifying the
        # stripped string would answer for a different string than the one
        # a client is actually handed.
        ("http://loc\talhost/v1", "invalid"),
        ("http://localhost\r\n/v1", "invalid"),
        ("http://localhost/v1\t", "invalid"),
        # NEW-3 (re-review, closure 1cc759e): MINOR-6 closed the tab/CR/LF-
        # anywhere case but `urlsplit` ALSO strips the whole WHATWG
        # C0-control-or-space set (0x00-0x20) from the ENDS of the string —
        # a leading/trailing space, a leading NUL, a leading/trailing other
        # C0 control character all silently became a different (stripped)
        # string before classification.
        (" http://localhost:8000/v1", "invalid"),
        ("\x01http://localhost:8000/v1", "invalid"),
        ("\x00http://localhost:8000/v1", "invalid"),
        ("http://localhost:8000/v1\x1f", "invalid"),
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


