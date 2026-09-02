"""PaddleOCR runtime configuration: the pins, the vocabularies, the opt-ins,
and the environment contract (Phase 2.1, `docs/agent-handoffs/PHASE2-1-PADDLE.md`
§"Configuration contract", D2, D3, D5, D8).

This module is the ONE home of every constant the Paddle rung, its client,
its worker, the OCR settings key and the telemetry share. It makes no network
call, imports no model library, and never builds a client.

Three rules it exists to make structural:

* **Execution class by DECLARATION, never by URL (D2).** The client always
  talks to a loopback URL (an SSH tunnel is the transport), so a URL-based
  classification would call a Vast.ai GPU "local". `PADDLE_PROVIDER` and
  `PADDLE_EXECUTION_CLASS` are REQUIRED, come from a closed vocabulary, must
  agree with each other, and (in `ocr/paddle_client.py`) must be echoed by
  the worker's own `/version` before any image is sent.
* **Fail closed on configuration (CASE 17).** A missing required variable is
  `PaddleConfigError` naming EXACTLY that variable. There is no default host,
  port or user; nothing is guessed; nothing is contacted.
* **Two independent opt-ins (D3, D8).** `PADDLE_REMOTE_OPT_IN` (exact
  literal) is required for any `remote_paid` execution.
  `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` (a second exact literal) is required
  before a `customer`-scope document may be sent to a `remote_paid` worker —
  and Phase 2.1 never sets it; the runbook says it requires Gustavo's separate
  remote-data / privacy / retention ruling.

Secrets: the SSH host/port/user are runtime configuration and are never
written into the repository, a settings key, a telemetry record, a row or a
log line. `PaddleSettings.masked()` is the only display form.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .endpoint_policy import classify_endpoint

__all__ = [
    "DATA_SCOPES",
    "DATA_SCOPE_CUSTOMER",
    "DATA_SCOPE_SYNTHETIC",
    "EXECUTION_CLASSES",
    "EXECUTION_CLASS_LOCAL_FREE",
    "EXECUTION_CLASS_REMOTE_PAID",
    "PADDLEOCR_VERSION",
    "PADDLEPADDLE_VERSION",
    "PADDLE_CUSTOMER_DATA_OPT_IN_ENV",
    "PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL",
    "PADDLE_DEFAULT_RUNTIME_DIR",
    "PADDLE_DEFAULT_TUNNEL_LOCAL_PORT",
    "PADDLE_DEFAULT_WORKER_PORT",
    "PADDLE_EXTRACTOR_ID",
    "PADDLE_MODEL_TOKEN",
    "PADDLE_OCR_VERSION",
    "PADDLE_PIPELINE_SWITCHES",
    "PADDLE_RASTER_DPI",
    "PADDLE_REMOTE_OPT_IN_ENV",
    "PADDLE_REMOTE_OPT_IN_LITERAL",
    "PADDLE_SOURCE_PATH",
    "PADDLE_TEXT_DETECTION_MODEL",
    "PADDLE_TEXT_RECOGNITION_MODEL",
    "PADDLE_WORKER_CONTRACT",
    "PROVIDERS",
    "PROVIDER_CLASS",
    "PROVIDER_LOCAL",
    "PROVIDER_VAST",
    "REFUSAL_REASONS",
    "PaddleConfigError",
    "PaddleRefused",
    "PaddleSettings",
    "check_remote_authorization",
    "load_paddle_settings",
    "paddle_runtime_identity",
    "paddle_settings_key_material",
]

# ---------------------------------------------------------------------------
# The pins (D5). Changing any of these is a reviewed edit that opens a new
# OCR cache partition (they are settings-key material) and the rung REFUSES a
# worker whose `/version` disagrees on any of them — a remote upgrade stops
# the rung until the pin is reviewed, never the other way round (the silent
# PP-OCRv6 hazard).
# ---------------------------------------------------------------------------

#: PaddleOCR package version proven on the Vast.ai RTX 5090 (2026-09-02).
PADDLEOCR_VERSION = "3.7.0"
#: PaddlePaddle GPU runtime version on that host.
PADDLEPADDLE_VERSION = "3.3.0"
#: The OCR model family. PP-OCRv5 by ruling; v6 is a separate measurement.
PADDLE_OCR_VERSION = "PP-OCRv5"
#: The two official models the proven word-box run used (cached under
#: `~/.paddlex/official_models` on the host).
PADDLE_TEXT_DETECTION_MODEL = "PP-OCRv5_server_det"
PADDLE_TEXT_RECOGNITION_MODEL = "en_PP-OCRv5_mobile_rec"
#: Pipeline switches — exactly what the proven run declared. Word boxes ON;
#: document preprocessing OFF (orientation / unwarping would move pixels
#: before the frame is recorded); every recognised word kept
#: (`text_rec_score_thresh=0.0`) — confidence is an annotation, not a filter.
PADDLE_PIPELINE_SWITCHES: Mapping[str, Any] = MappingProxyType({
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "return_word_box": True,
    "text_rec_score_thresh": 0.0,
})
#: The JSON contract between `ocr/paddle_client.py` and `ocr/paddle_worker.py`.
PADDLE_WORKER_CONTRACT = 1
#: The raster dpi the rung feeds the worker (the ladder's visual default; a
#: letter page is 2550 x 3300 px, under PP-OCRv5's 4000 px detection limit).
PADDLE_RASTER_DPI = 300

# ---------------------------------------------------------------------------
# Identity tokens (closed charset — see `ocr/config.py::MODEL_TOKEN_RE`;
# no money shape; reserved so an env `OCR_MODEL` cannot impersonate the rung).
# ---------------------------------------------------------------------------

PADDLE_MODEL_TOKEN = "paddle-ocr+ppocrv5"
PADDLE_EXTRACTOR_ID = "paddle-ocr"
#: The `telemetry.record.SOURCE_PATHS` member this rung reports as.
PADDLE_SOURCE_PATH = "paddle"

# ---------------------------------------------------------------------------
# Vocabularies (closed)
# ---------------------------------------------------------------------------

PROVIDER_VAST = "vast.ai"
PROVIDER_LOCAL = "local"
PROVIDERS: tuple[str, ...] = (PROVIDER_VAST, PROVIDER_LOCAL)

EXECUTION_CLASS_REMOTE_PAID = "remote_paid"
EXECUTION_CLASS_LOCAL_FREE = "local_free"
EXECUTION_CLASSES: tuple[str, ...] = (EXECUTION_CLASS_REMOTE_PAID, EXECUTION_CLASS_LOCAL_FREE)

#: The ONLY legal pairings. A Vast.ai worker is remote and paid, full stop; a
#: local worker is local and free. Any other pairing is refused (D2).
PROVIDER_CLASS: Mapping[str, str] = MappingProxyType({
    PROVIDER_VAST: EXECUTION_CLASS_REMOTE_PAID,
    PROVIDER_LOCAL: EXECUTION_CLASS_LOCAL_FREE,
})

DATA_SCOPE_SYNTHETIC = "synthetic"
DATA_SCOPE_CUSTOMER = "customer"
DATA_SCOPES: tuple[str, ...] = (DATA_SCOPE_SYNTHETIC, DATA_SCOPE_CUSTOMER)

PADDLE_REMOTE_OPT_IN_ENV = "PADDLE_REMOTE_OPT_IN"
PADDLE_REMOTE_OPT_IN_LITERAL = "I_ACCEPT_REMOTE_PAID_PADDLE_OCR"
PADDLE_CUSTOMER_DATA_OPT_IN_ENV = "PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN"
PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL = "I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR"

PADDLE_DEFAULT_WORKER_PORT = 8765
PADDLE_DEFAULT_TUNNEL_LOCAL_PORT = 18765
PADDLE_DEFAULT_RUNTIME_DIR = ".paddle_runtime"

#: Closed refusal vocabulary (rows, telemetry and exceptions use these tokens
#: and nothing else).
REFUSAL_REASONS: tuple[str, ...] = (
    "paddle_config_missing",
    "paddle_remote_opt_in_required",
    "remote_customer_data_refused",
    "paddle_data_scope_unknown",
    "paddle_runtime_mismatch",
    "paddle_worker_unreachable",
    "paddle_worker_url_not_loopback",
)

_REQUIRED_ALWAYS = ("PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS")
_REQUIRED_FOR_VAST = ("PADDLE_VAST_HOST", "PADDLE_VAST_SSH_PORT", "PADDLE_VAST_SSH_USER")


class PaddleConfigError(ValueError):
    """Missing or invalid Paddle configuration. Names the offending variable;
    never carries a host, port, user or token VALUE."""


class PaddleRefused(RuntimeError):
    """A refusal BEFORE any request is sent. `reason` is a member of
    `REFUSAL_REASONS`."""

    def __init__(self, reason: str, detail: str = ""):
        if reason not in REFUSAL_REASONS:
            raise ValueError(f"unknown refusal reason {reason!r}")
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass(frozen=True)
class PaddleSettings:
    """Everything the rung, client and lifecycle tool need. Frozen; the SSH
    fields are present so the lifecycle tool can open the tunnel — they are
    NEVER settings-key or telemetry material (see `paddle_settings_key_material`)."""

    provider: str
    execution_class: str
    vast_host: str | None
    vast_ssh_port: int | None
    vast_ssh_user: str | None
    remote_opt_in: bool
    customer_data_opt_in: bool
    worker_url: str
    worker_port: int
    tunnel_local_port: int
    worker_token: str | None
    runtime_dir: str

    @property
    def is_remote(self) -> bool:
        return self.execution_class == EXECUTION_CLASS_REMOTE_PAID

    def masked(self) -> dict[str, Any]:
        """The ONLY display form: presence and class, never a value."""
        return {
            "provider": self.provider,
            "execution_class": self.execution_class,
            "vast_host": "<set>" if self.vast_host else None,
            "vast_ssh_port": "<set>" if self.vast_ssh_port else None,
            "vast_ssh_user": "<set>" if self.vast_ssh_user else None,
            "remote_opt_in": self.remote_opt_in,
            "customer_data_opt_in": self.customer_data_opt_in,
            "worker_url": self.worker_url,
            "worker_token": "<set>" if self.worker_token else None,
            "runtime_dir": self.runtime_dir,
        }


def _port(environ: Mapping[str, str], name: str, default: int | None) -> int:
    raw = environ.get(name)
    if raw is None or raw == "":
        if default is None:
            raise PaddleConfigError(f"required Paddle configuration variable {name} is not set")
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise PaddleConfigError(f"{name} must be an integer port") from exc
    if not (1 <= value <= 65535):
        raise PaddleConfigError(f"{name} must be a port in 1..65535")
    return value


def load_paddle_settings(environ: Mapping[str, str] | None = None) -> PaddleSettings:
    """Read the contract from `environ` (default `os.environ`). Fails closed.

    Order of checks is deliberate: vocabulary and pairing first, then the
    provider's required connection variables, then the loopback-only worker
    URL — so the FIRST error an operator sees is the most fundamental one.
    """
    source = os.environ if environ is None else environ
    for name in _REQUIRED_ALWAYS:
        if not source.get(name):
            raise PaddleConfigError(f"required Paddle configuration variable {name} is not set")
    provider = source["PADDLE_PROVIDER"].strip()
    execution_class = source["PADDLE_EXECUTION_CLASS"].strip()
    if provider not in PROVIDERS:
        raise PaddleConfigError(f"PADDLE_PROVIDER must be one of {PROVIDERS}")
    if execution_class not in EXECUTION_CLASSES:
        raise PaddleConfigError(f"PADDLE_EXECUTION_CLASS must be one of {EXECUTION_CLASSES}")
    if PROVIDER_CLASS[provider] != execution_class:
        raise PaddleConfigError(
            f"PADDLE_PROVIDER={provider!r} requires PADDLE_EXECUTION_CLASS="
            f"{PROVIDER_CLASS[provider]!r}; refusing the declared {execution_class!r}"
        )

    vast_host = vast_user = None
    vast_port: int | None = None
    if provider == PROVIDER_VAST:
        for name in _REQUIRED_FOR_VAST:
            if not source.get(name):
                raise PaddleConfigError(f"required Paddle configuration variable {name} is not set")
        vast_host = source["PADDLE_VAST_HOST"].strip()
        vast_user = source["PADDLE_VAST_SSH_USER"].strip()
        vast_port = _port(source, "PADDLE_VAST_SSH_PORT", None)
        if any(ch.isspace() for ch in vast_host) or any(ch.isspace() for ch in vast_user):
            raise PaddleConfigError("PADDLE_VAST_HOST / PADDLE_VAST_SSH_USER must not contain whitespace")

    worker_port = _port(source, "PADDLE_WORKER_PORT", PADDLE_DEFAULT_WORKER_PORT)
    tunnel_port = _port(source, "PADDLE_TUNNEL_LOCAL_PORT", PADDLE_DEFAULT_TUNNEL_LOCAL_PORT)
    worker_url = (source.get("PADDLE_WORKER_URL") or "").strip() or f"http://127.0.0.1:{tunnel_port}"
    if classify_endpoint(worker_url) != "loopback":
        # The tunnel is the transport. A worker reachable at any non-loopback
        # address would mean the loopback-only bind was defeated somewhere,
        # and this client is not the place to make that work.
        raise PaddleConfigError("PADDLE_WORKER_URL must be a loopback http(s) URL (the SSH tunnel's local end)")

    token = (source.get("PADDLE_WORKER_TOKEN") or "").strip() or None
    return PaddleSettings(
        provider=provider,
        execution_class=execution_class,
        vast_host=vast_host,
        vast_ssh_port=vast_port,
        vast_ssh_user=vast_user,
        remote_opt_in=source.get(PADDLE_REMOTE_OPT_IN_ENV) == PADDLE_REMOTE_OPT_IN_LITERAL,
        customer_data_opt_in=(
            source.get(PADDLE_CUSTOMER_DATA_OPT_IN_ENV) == PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL
        ),
        worker_url=worker_url,
        worker_port=worker_port,
        tunnel_local_port=tunnel_port,
        worker_token=token,
        runtime_dir=(source.get("PADDLE_RUNTIME_DIR") or "").strip() or PADDLE_DEFAULT_RUNTIME_DIR,
    )


def check_remote_authorization(settings: PaddleSettings, data_scope: str) -> None:
    """The two opt-in gates, evaluated BEFORE any request (D3, D8).

    * `remote_paid` without the exact remote opt-in literal -> refused.
    * a `customer`-scope document on a `remote_paid` worker without the
      exact customer-data literal -> refused (never set in Phase 2.1).
    * an unknown scope -> refused (a caller must declare what it is sending).
    A `local_free` worker needs neither literal.
    """
    if data_scope not in DATA_SCOPES:
        raise PaddleRefused("paddle_data_scope_unknown", f"data_scope={data_scope!r}")
    if not settings.is_remote:
        return
    if not settings.remote_opt_in:
        raise PaddleRefused(
            "paddle_remote_opt_in_required",
            f"set {PADDLE_REMOTE_OPT_IN_ENV}={PADDLE_REMOTE_OPT_IN_LITERAL} to allow remote paid PaddleOCR explicitly",
        )
    if data_scope == DATA_SCOPE_CUSTOMER and not settings.customer_data_opt_in:
        raise PaddleRefused(
            "remote_customer_data_refused",
            "customer documents are not sent to a remote worker without Gustavo's separate "
            f"remote-data ruling ({PADDLE_CUSTOMER_DATA_OPT_IN_ENV})",
        )


def paddle_runtime_identity() -> dict[str, Any]:
    """The pinned identity block: what the worker must echo, what provenance
    records, what the settings key hashes."""
    return {
        "paddleocr_version": PADDLEOCR_VERSION,
        "paddlepaddle_version": PADDLEPADDLE_VERSION,
        "ocr_version": PADDLE_OCR_VERSION,
        "text_detection_model_name": PADDLE_TEXT_DETECTION_MODEL,
        "text_recognition_model_name": PADDLE_TEXT_RECOGNITION_MODEL,
        "pipeline_switches": dict(PADDLE_PIPELINE_SWITCHES),
        "worker_contract": PADDLE_WORKER_CONTRACT,
    }


def paddle_settings_key_material(settings: PaddleSettings) -> dict[str, Any]:
    """The Paddle block of `webapp.artifact_cache.ocr_settings_key` when the
    extractor is `paddle`. Provider and execution class partition (a local
    read and a Vast read of the same bytes are different artifacts); the
    pins partition; the raster dpi is already key material upstream. NEVER
    the host, port, user, URL or token — instance-specific, never hashed."""
    identity = paddle_runtime_identity()
    identity.update({
        "provider": settings.provider,
        "execution_class": settings.execution_class,
        "model_token": PADDLE_MODEL_TOKEN,
        "extractor_id": PADDLE_EXTRACTOR_ID,
    })
    return identity
