"""ocr/paddle_client.py — the bounded Paddle worker client (Phase 2.1 cell P,
`docs/agent-handoffs/P21-PADDLE.md` §2, D2, D5, CASE 16/18).

Stdlib `urllib.request` only — no `openai`, no `httpx`, no third-party HTTP
library. There is exactly one worker per process (the tunnel's local end);
this client has no fallback list and no second host to hop to, so a
transport failure or an identity mismatch ends the rung rather than trying
anywhere else (CASE 18's "exactly one URL ever contacted").

Execution class is asserted twice, never inferred from the URL (D2): once by
`ocr.paddle_config.load_paddle_settings` (the worker URL must already be
loopback), and again here in the constructor, because MINOR-2's lesson
(`PHASE2_P20SEAM_REVIEW.md`) is that a hand-built settings object — as tests
and callers both construct — must not be trusted to have gone through the
loader. `verify_identity` then requires the WORKER's own `/version` to echo
`ocr.paddle_config.paddle_runtime_identity()` and the settings' declared
provider/execution_class, field by field, before a single image byte is
sent.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from .endpoint_policy import classify_endpoint
from .paddle_config import (
    DATA_SCOPE_SYNTHETIC,
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
    PADDLE_WORKER_CONTRACT,
    PaddleConfigError,
    PaddleRefused,
    PaddleSettings,
    check_remote_authorization,
    load_paddle_settings,
    paddle_runtime_identity,
)

__all__ = [
    "IDENTITY_CHECK_FIELDS",
    "MAX_RESPONSE_BYTES",
    "DEFAULT_TIMEOUT",
    "MAX_TRANSPORT_RETRIES",
    "PaddleClient",
    "PaddleTransportError",
    "PaddleWorkerStatus",
    "probe",
    "verify_identity",
]

#: A bound on the /ocr, /version and /health response bodies. The worker
#: never legitimately returns more than a few pages' worth of word boxes;
#: anything past this is treated as a transport-level failure, never parsed.
MAX_RESPONSE_BYTES = 64 * 1024 * 1024

DEFAULT_TIMEOUT = 120.0
#: "retries (<= 2, same URL, transient errors only) are the ONLY loop" (§2).
MAX_TRANSPORT_RETRIES = 2

#: The fields `verify_identity` compares, one at a time (D5). Every one must
#: match; the caller's test asserts a mutation of any single field refuses.
IDENTITY_CHECK_FIELDS = (
    "contract",
    "provider",
    "execution_class",
    "paddleocr_version",
    "paddlepaddle_version",
    "ocr_version",
    "text_detection_model_name",
    "text_recognition_model_name",
    "pipeline_switches",
)


class PaddleTransportError(RuntimeError):
    """Any failure after a request was attempted: connection refused,
    timeout, an HTTP error status, a redirect (refused, never followed), a
    malformed or oversized response. `reason` is always
    `"paddle_worker_unreachable"`; `error_type` is the underlying
    exception's CLASS NAME — never its message (no document content, no
    connection detail, ever reaches this far)."""

    def __init__(self, reason: str, error_type: str):
        self.reason = reason
        self.error_type = error_type
        super().__init__(f"{reason} ({error_type})")


@dataclass(frozen=True)
class PaddleWorkerStatus:
    """The result of `probe`. Never raises; the caller decides. `identity`
    is the worker's `/version` payload on success, `None` otherwise."""

    available: bool
    reason: str
    identity: dict | None = None
    error_type: str | None = None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect: a 3xx from the worker is a transport failure,
    never a hop to `newurl` (CASE 18, M4's "no retry to a different URL")."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise urllib.error.HTTPError(req.full_url, code, f"redirect refused: {msg}", headers, fp)


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirectHandler)


class PaddleClient:
    """`PaddleClient(settings, *, timeout=120.0, opener=None, environ=None)`.

    `opener` is the test seam: any object with an `.open(request, timeout=)`
    context-managed return value stands in for `urllib`'s real network stack
    (`tests/paddle_fake_worker.FakeWorker` uses the real stdlib opener
    against a loopback socket, so the default suite never mocks urllib
    itself — only the worker at the other end is fake).

    MAJOR-2 (`PHASE2_P21PADDLE_REVIEW.md`): a `remote_paid` client cannot even
    be CONSTRUCTED unless the remote opt-in literal is present in `environ`
    (default `os.environ`) AND `settings.remote_opt_in` agrees — the same
    "never trust a hand-built settings object" discipline the loopback
    re-check already applies, extended to the opt-in flag. `environ` is the
    test seam; a `PaddleSettings` built by `load_paddle_settings()` already
    agrees with the real environment it read, so this is a no-op for every
    honest caller.

    R-2 (`PHASE2_P21PADDLE_REVIEW.md` re-review): the SAME re-derivation
    applies to `settings.customer_data_opt_in` — a hand-built settings
    object claiming it (regardless of which `data_scope` a later call might
    use) is refused at construction unless `environ` also carries the exact
    customer-data literal. `check_remote_authorization` still owns the
    scope-specific gate (a `data_scope="customer"` call needs this AND the
    caller to declare that scope); this is defense in depth at the object
    that will go on to make the request, not a replacement for it.
    """

    def __init__(self, settings: PaddleSettings, *, timeout: float = DEFAULT_TIMEOUT, opener=None,
                 environ: Mapping[str, str] | None = None):
        if classify_endpoint(settings.worker_url) != "loopback":
            raise PaddleConfigError(
                "PaddleClient requires a loopback worker_url (the SSH tunnel's local end); "
                "refusing a hand-built settings object that is not"
            )
        if settings.is_remote:
            source = os.environ if environ is None else environ
            remote_opt_in = settings.remote_opt_in and source.get(PADDLE_REMOTE_OPT_IN_ENV) == PADDLE_REMOTE_OPT_IN_LITERAL
            if not remote_opt_in:
                raise PaddleRefused(
                    "paddle_remote_opt_in_required",
                    f"PaddleClient refuses to construct a remote_paid client without "
                    f"{PADDLE_REMOTE_OPT_IN_ENV}={PADDLE_REMOTE_OPT_IN_LITERAL} agreeing in both "
                    "settings and the environment",
                )
            if settings.customer_data_opt_in:
                customer_opt_in = source.get(PADDLE_CUSTOMER_DATA_OPT_IN_ENV) == PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL
                if not customer_opt_in:
                    raise PaddleRefused(
                        "remote_customer_data_refused",
                        f"PaddleClient refuses to construct a client claiming customer_data_opt_in "
                        f"without {PADDLE_CUSTOMER_DATA_OPT_IN_ENV}={PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL} "
                        "agreeing in the environment",
                    )
        self.settings = settings
        self.timeout = timeout
        self._opener = opener or _default_opener()

    def _request(self, method: str, path: str, *, body: bytes | None = None) -> dict:
        url = self.settings.worker_url.rstrip("/") + path
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.settings.worker_token:
            headers["Authorization"] = f"Bearer {self.settings.worker_token}"

        attempt = 0
        while True:
            attempt += 1
            request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
            except urllib.error.HTTPError as exc:
                # A real response with an error/redirect status: not
                # transient (the worker answered), so no retry.
                raise PaddleTransportError("paddle_worker_unreachable", type(exc).__name__) from exc
            except Exception as exc:  # noqa: BLE001 - transport-layer catch-all, re-raised typed
                if attempt <= MAX_TRANSPORT_RETRIES and _is_transient(exc):
                    continue
                raise PaddleTransportError("paddle_worker_unreachable", type(exc).__name__) from exc

            if len(raw) > MAX_RESPONSE_BYTES:
                raise PaddleTransportError("paddle_worker_unreachable", "ResponseTooLarge")
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PaddleTransportError("paddle_worker_unreachable", type(exc).__name__) from exc

    def health(self) -> dict:
        return self._request("GET", "/health")

    def version(self) -> dict:
        return self._request("GET", "/version")

    def ocr_page(self, png_bytes: bytes, *, page_index: int, request_id: str) -> dict:
        payload = {
            "contract": PADDLE_WORKER_CONTRACT,
            "request_id": request_id,
            "page_index": page_index,
            "image_png_b64": base64.b64encode(png_bytes).decode("ascii"),
        }
        return self._request("POST", "/ocr", body=json.dumps(payload).encode("utf-8"))


def _is_transient(exc: Exception) -> bool:
    """Connection-level failures only (refused, reset, DNS, timeout) —
    NEVER a well-formed HTTP error response (those are `urllib.error.HTTPError`
    and are handled, and never retried, above)."""
    return isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError, OSError))


#: R-1 (`PHASE2_P21PADDLE_REVIEW.md` re-review): `gpu`, `python_version` and
#: `cuda_compiled` are copied into `evidence.runtime` by `ocr.paddle_rung`'s
#: whitelist but are NOT among `IDENTITY_CHECK_FIELDS` (they are not pinned
#: values — a GPU name or a Python patch version legitimately varies) — so
#: the top-level key whitelist alone did not stop a worker nesting arbitrary
#: text INSIDE one of these three fields (`gpu.note`, a `python_version`
#: string with a URL appended). These bound the SHAPE of exactly those three
#: fields before ANY of them can reach `verify_identity`'s caller — a
#: mismatch refuses `paddle_runtime_mismatch`, the SAME reason and the SAME
#: place (before any `/ocr` request) as every other identity check.
_GPU_KEYS = frozenset({"name", "memory_total_mib", "driver_version"})
#: Letters, digits, space, parentheses, `+`, `.`, `-` — a GPU model name
#: shape (e.g. "NVIDIA GeForce RTX 5090") with no `/`, no `:`, and (checked
#: separately) no whitespace run.
_GPU_NAME_RE = re.compile(r"\A[A-Za-z0-9()+.\- ]{1,80}\Z")
_DRIVER_VERSION_RE = re.compile(r"\A\d+(\.\d+){1,3}\Z")
_PYTHON_VERSION_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")


def _shape_invalid_runtime_fields(remote: Mapping[str, Any]) -> list[str]:
    """Which of `gpu` / `python_version` / `cuda_compiled` fail their shape
    bound in `remote` (a `/version` payload). Empty means all three are
    trustworthy shapes; this says nothing about their VALUES otherwise —
    `ocr.paddle_rung._runtime_block`'s whitelist still governs which keys
    survive into the evidence, and this only bounds what those three keys'
    own content may look like."""
    bad: list[str] = []
    gpu = remote.get("gpu")
    if not isinstance(gpu, Mapping) or set(gpu.keys()) != _GPU_KEYS:
        bad.append("gpu")
    else:
        name = gpu.get("name")
        if not isinstance(name, str) or not _GPU_NAME_RE.match(name) or "  " in name:
            bad.append("gpu.name")
        memory_total = gpu.get("memory_total_mib")
        if isinstance(memory_total, bool) or not isinstance(memory_total, int):
            bad.append("gpu.memory_total_mib")
        driver = gpu.get("driver_version")
        if not isinstance(driver, str) or not _DRIVER_VERSION_RE.match(driver):
            bad.append("gpu.driver_version")
    python_version = remote.get("python_version")
    if not isinstance(python_version, str) or not _PYTHON_VERSION_RE.match(python_version):
        bad.append("python_version")
    cuda_compiled = remote.get("cuda_compiled")
    if not isinstance(cuda_compiled, bool):
        bad.append("cuda_compiled")
    return bad


def verify_identity(settings: PaddleSettings, *, client: "PaddleClient | None" = None,
                     environ: Mapping[str, str] | None = None) -> dict:
    """Fetch `/version` and refuse unless every `IDENTITY_CHECK_FIELDS` entry
    equals the pin (`paddle_runtime_identity()`) or the settings' own
    declaration (provider, execution_class) — D5, CASE 16 — AND `gpu` /
    `python_version` / `cuda_compiled` each pass their shape bound (R-1).
    Raises `PaddleRefused("paddle_runtime_mismatch", …)` naming every
    mismatched or shape-invalid field; raises `PaddleTransportError`
    unchanged on a transport failure. Sends no document — `/version` carries
    no image. `environ` is forwarded to the `PaddleClient` this builds when
    `client` is not already supplied (MAJOR-2's re-derivation test seam);
    ignored when `client` is given."""
    client = client or PaddleClient(settings, environ=environ)
    remote = client.version()
    expected = paddle_runtime_identity()
    wanted = {
        "contract": expected["worker_contract"],
        "provider": settings.provider,
        "execution_class": settings.execution_class,
        "paddleocr_version": expected["paddleocr_version"],
        "paddlepaddle_version": expected["paddlepaddle_version"],
        "ocr_version": expected["ocr_version"],
        "text_detection_model_name": expected["text_detection_model_name"],
        "text_recognition_model_name": expected["text_recognition_model_name"],
        "pipeline_switches": dict(expected["pipeline_switches"]),
    }
    mismatched = [name for name in IDENTITY_CHECK_FIELDS if remote.get(name) != wanted[name]]
    mismatched.extend(_shape_invalid_runtime_fields(remote))
    if mismatched:
        raise PaddleRefused("paddle_runtime_mismatch", f"fields disagree with the pins: {', '.join(mismatched)}")
    return remote


def probe(settings: "PaddleSettings | None" = None, client: "PaddleClient | None" = None, *,
          environ: Mapping[str, str] | None = None) -> PaddleWorkerStatus:
    """Never raises. Config error -> `paddle_config_missing`; remote without
    the opt-in literal -> `paddle_remote_opt_in_required` (checked via
    `check_remote_authorization(settings, "synthetic", environ=environ)`
    BEFORE any request — the probe sends no document, so the scope gate it
    exercises is the opt-in one, never the customer-data one); unreachable ->
    `paddle_worker_unreachable` + the exception class name; mismatch ->
    `paddle_runtime_mismatch`. `environ` is the MAJOR-2 test seam threaded to
    both the authorization check and the `PaddleClient` this builds."""
    try:
        resolved = settings or load_paddle_settings()
    except PaddleConfigError:
        return PaddleWorkerStatus(False, "paddle_config_missing")
    try:
        check_remote_authorization(resolved, DATA_SCOPE_SYNTHETIC, environ=environ)
    except PaddleRefused as exc:
        return PaddleWorkerStatus(False, exc.reason)
    try:
        active_client = client or PaddleClient(resolved, environ=environ)
        identity = verify_identity(resolved, client=active_client)
    except PaddleConfigError:
        return PaddleWorkerStatus(False, "paddle_config_missing")
    except PaddleRefused as exc:
        return PaddleWorkerStatus(False, exc.reason)
    except PaddleTransportError as exc:
        return PaddleWorkerStatus(False, exc.reason, error_type=exc.error_type)
    return PaddleWorkerStatus(True, "ok", identity=identity)
