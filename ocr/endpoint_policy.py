"""The $0 / no-paid-vendor invariant, enforced in code (OQ3 = ALLOWLIST).

`ocr/availability.py` has asserted since Wave 3 that "no paid vendor is
involved and none may be" — a convention nothing enforced. `OCR_BASE_URL` was
a plain env read: one env var repointed the image-bearing request at any host
(OCR_LEGACY_AUDIT.md F-4(a)). Gustavo's ruling (PHASE2_RULINGS.md OQ3):
approved local/private endpoints may be used by default; remote or paid
processing requires explicit, deliberate, recorded opt-in; **a local
extractor failure must never silently trigger a remote or paid service.**

This module is the enforcement authority. It classifies a base URL
structurally (scheme + host only — never a network call, never a DNS lookup
beyond what `ipaddress`/`urlsplit` do on the literal string) and decides
whether the endpoint policy allows it. It does not build a client and does
not send anything; callers (`ocr.ocr_client._build_client`,
`ocr.availability.probe_visual_ocr`) call `check_endpoint` and refuse BEFORE
either of those happens.

There is exactly one visual endpoint per process: this module has no
fallback list, no second URL, no retry-a-different-host logic of any kind —
a refused or failing endpoint ends the rung (fail closed), it never hops.
"""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

#: Closed vocabulary for `classify_endpoint`'s return value.
ENDPOINT_CLASSES = ("loopback", "private", "remote", "invalid")

#: The ONE env var that can turn on a remote/paid endpoint, and the ONE exact
#: literal it must equal. Deliberately not a truthy check ("1", "true", "yes")
#: — a remote/paid OCR endpoint is a deliberate, recorded decision, not
#: something a stray env var should flip on by accident.
OCR_REMOTE_OPT_IN_ENV = "OCR_REMOTE_OPT_IN"
OCR_REMOTE_OPT_IN_LITERAL = "I_ACCEPT_REMOTE_PAID_OCR"


def remote_opt_in_from_env(environ: "os._Environ[str] | dict[str, str] | None" = None) -> bool:
    """True only when `OCR_REMOTE_OPT_IN` is exactly the opt-in literal.

    `environ` is an injection seam for tests; production callers pass nothing
    and get `os.environ`.
    """
    source = os.environ if environ is None else environ
    return source.get(OCR_REMOTE_OPT_IN_ENV) == OCR_REMOTE_OPT_IN_LITERAL


def classify_endpoint(base_url: str) -> str:
    """Which class `base_url` falls into: loopback / private / remote / invalid.

    Structural only — the URL's scheme and host, nothing else:

    * `loopback` — `localhost`, `127.0.0.0/8`, `::1`.
    * `private` — RFC 1918 / link-local / IPv6 ULA, or a `.local` name.
    * `remote` — anything else with a valid http(s) host, including every
      public name (`*.runpod.net` included) and every public IP.
    * `invalid` — unparseable, no host, or a non-http(s) scheme. Never
      allowed by `check_endpoint`, opt-in or not.
    """
    if not isinstance(base_url, str) or not base_url:
        return "invalid"
    try:
        parsed = urlsplit(base_url)
    except ValueError:
        return "invalid"
    if parsed.scheme not in ("http", "https"):
        return "invalid"
    try:
        host = parsed.hostname
    except ValueError:
        return "invalid"
    if not host:
        return "invalid"
    host = host.lower()
    if host == "localhost":
        return "loopback"
    if host.endswith(".local"):
        return "private"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # An ordinary DNS name that is neither localhost nor .local: a name
        # alone is not evidence of locality, so it is remote.
        return "remote"
    if ip.is_loopback:
        return "loopback"
    if ip.is_private or ip.is_link_local:
        return "private"
    return "remote"


@dataclass(frozen=True)
class EndpointDecision:
    """The enforcement verdict for one base URL. Never carries document content."""

    allowed: bool
    klass: str
    reason: str


def check_endpoint(base_url: str, *, opt_in: bool) -> EndpointDecision:
    """The OQ3 enforcement decision.

    `loopback` and `private` are allowed by default. `remote` is allowed
    ONLY when `opt_in` is True (see `remote_opt_in_from_env`). `invalid` is
    never allowed, opt-in or not.
    """
    klass = classify_endpoint(base_url)
    if klass == "invalid":
        return EndpointDecision(
            False, klass, f"unparseable or non-http(s) OCR endpoint: {base_url!r}"
        )
    if klass in ("loopback", "private"):
        return EndpointDecision(True, klass, f"{klass} endpoint allowed by default")
    if opt_in:
        return EndpointDecision(
            True, klass, "remote endpoint allowed by explicit OCR_REMOTE_OPT_IN"
        )
    return EndpointDecision(
        False,
        klass,
        "remote OCR endpoint refused: set "
        f"{OCR_REMOTE_OPT_IN_ENV}={OCR_REMOTE_OPT_IN_LITERAL} to allow it explicitly",
    )


class EndpointRefused(RuntimeError):
    """Raised before any client is built or any request is sent.

    Carries the `EndpointDecision` and the refused `base_url` for the
    console-facing caller (`ocr.availability.probe_visual_ocr` reports it as
    `usable=False` with `error_type="EndpointRefused"`); never carries
    document content, because none exists yet at this point in the ladder.
    """

    def __init__(self, decision: EndpointDecision, base_url: str):
        self.decision = decision
        self.base_url = base_url
        super().__init__(decision.reason)
