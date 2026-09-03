from __future__ import annotations
import os
import re
from dataclasses import dataclass

from .endpoint_policy import classify_endpoint, remote_opt_in_from_env
from .paddle_config import PADDLE_MODEL_TOKEN

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


class ProvenanceTokenError(ValueError):
    """A model/provenance token failed the closed-charset content policy.

    F-4(b) / MAJOR-2: `OCR_MODEL` is not only "which host gets the pixels" —
    it is arbitrary text stamped into the first line of every visual-OCR
    document's analysis input (`ocr.document.StatementMarkdown.to_markdown`).
    Raised at the point the token is SET — an env read (`load_settings`) or a
    `StatementMarkdown` construction (`ocr.document`) — never at the point it
    is printed, so a hostile token never becomes a `Settings.model` or a
    `StatementMarkdown.model` in the first place. There is nothing left to
    sanitize downstream, which is what makes this a closure rather than a
    second, escapable guard stacked on `admissible_text`'s.
    """


#: Closed charset (F-4(b)): first character alphanumeric, then only
#: `[A-Za-z0-9._/+-]`, length 1-64. Structurally excludes whitespace of any
#: kind (so a newline, CR, or a plain space cannot appear), `<`, `>`, `!`,
#: `$`, `,`, quotes and backslash — which is also why a valid token cannot
#: contain `-->`, a `<|det|>`-style region tag, or a `<!-- source:` fragment.
#:
#: BLOCK-1 (PHASE2_P20SEAM_REVIEW.md): anchored with `\A` / `\Z`, NOT `^` / `$`.
#: In Python, `$` matches at the end of the string OR immediately before a
#: trailing `\n` — `re.match(r"^...$", "evilmodel\n")` succeeds, so the
#: previous pattern accepted a token whose only hostile character was a
#: single trailing newline (and, via the same leak, a 65-character token
#: whose 65th character was `\n`, silently bypassing the length bound too).
#: `\A` and `\Z` anchor to the true start/end of the string with no such
#: carve-out. Every other anchored validator in this module uses the same
#: discipline: `_MONEY_SHAPE_RE` is unanchored by design (a `.search`, not
#: a full-string match, so `$` there was never the same hazard), and the
#: opt-in literal check (`ocr.endpoint_policy.remote_opt_in_from_env`) is a
#: plain `==` string comparison, not a regex, so it has no anchor to leak.
MODEL_TOKEN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}\Z")

#: A money-shaped substring the charset alone does not exclude: digits and a
#: single `.` are both allowed characters, so a version string like "v1.00"
#: is syntactically identical to a two-decimal amount. Matches one or more
#: digits, a literal `.`, then exactly two digits with no third digit
#: following (`(?!\d)`) — "1.00" matches; "1.005" does not, because its
#: two-digit window is immediately followed by another digit, not a
#: non-digit boundary.
_MONEY_SHAPE_RE = re.compile(r"\d+\.\d{2}(?!\d)")

#: The deterministic ladder's own model tokens. An env-supplied OCR_MODEL
#: must never equal or start with one of these — that would spoof
#: `telemetry.record.source_path_for`, `telemetry.prices.py`'s free-model
#: table, and cell D's Q3 native-only gate into believing an
#: operator-controlled visual read is a native/offline one. The native and
#: local-tesseract rungs legitimately set these tokens directly on
#: `StatementMarkdown` — never through this env-facing validator — which is
#: why `ocr.document.StatementMarkdown.__post_init__` validates with
#: `allow_reserved=True`.
#: P21-ROUTING (Phase 2.1): `PADDLE_MODEL_TOKEN` joins the reserved set so an
#: env-supplied `OCR_MODEL` cannot impersonate the Paddle rung either — the
#: same reasoning as the three deterministic-ladder tokens above. The Paddle
#: rung sets this token directly on `StatementMarkdown`
#: (`allow_reserved=True`), never through this env-facing validator.
RESERVED_MODEL_PREFIXES = (
    "native-pdf-text",
    "local-tesseract-ocr",
    "deterministic-native-preflight",
    PADDLE_MODEL_TOKEN,
)


def validate_model_token(token: str, *, allow_reserved: bool) -> str:
    """Validate a model/provenance token against the closed charset (F-4(b)).

    Returns the token byte-identical when it is accepted (this function never
    mutates or truncates); raises `ProvenanceTokenError` otherwise.

    `allow_reserved=False` (env / CLI override, via `load_settings`) also
    refuses a token that equals or starts with a `RESERVED_MODEL_PREFIXES`
    entry — an env value must not impersonate a native read.
    `allow_reserved=True` (`StatementMarkdown.__post_init__`) skips that one
    check, because the native and local-tesseract rungs legitimately set
    those exact tokens themselves.
    """
    if not isinstance(token, str) or not MODEL_TOKEN_RE.match(token):
        raise ProvenanceTokenError(
            f"model/provenance token rejected by the closed charset: {token!r}"
        )
    if _MONEY_SHAPE_RE.search(token):
        raise ProvenanceTokenError(
            f"model/provenance token rejected (money-shaped substring): {token!r}"
        )
    if not allow_reserved and any(
        token == prefix or token.startswith(prefix) for prefix in RESERVED_MODEL_PREFIXES
    ):
        raise ProvenanceTokenError(
            f"model/provenance token rejected (impersonates a reserved rung prefix): {token!r}"
        )
    return token


@dataclass
class Settings:
    base_url: str
    model: str
    api_key: str
    timeout: float
    retries: int
    ngram_size: int
    window_size: int
    max_workers: int
    #: OQ3 provenance (F-4(a)): the endpoint's structural class and whether an
    #: explicit remote opt-in was present when this Settings was built. These
    #: are DESCRIPTIVE fields for telemetry and the cache key (cell C keys on
    #: them) — NOT the enforcement authority. `ocr.ocr_client._build_client`
    #: re-derives the decision from `base_url` fresh via
    #: `ocr.endpoint_policy.check_endpoint`, so a hand-built `Settings` (as
    #: tests construct) cannot spoof these fields into bypassing the real
    #: check. `endpoint_class` auto-derives from `base_url` when left `None`.
    endpoint_class: str | None = None
    remote_opt_in: bool = False

    def __post_init__(self) -> None:
        if self.endpoint_class is None:
            self.endpoint_class = classify_endpoint(self.base_url)


def load_settings(model_override: str | None = None) -> Settings:
    base_url = os.environ.get("OCR_BASE_URL", "http://localhost:8000/v1")
    raw_model = model_override or os.environ.get("OCR_MODEL", "baidu/Unlimited-OCR")
    model = validate_model_token(raw_model, allow_reserved=False)
    return Settings(
        base_url=base_url,
        model=model,
        api_key=os.environ.get("OCR_API_KEY", "EMPTY"),
        timeout=float(os.environ.get("OCR_TIMEOUT", "120")),
        retries=int(os.environ.get("OCR_RETRIES", "3")),
        ngram_size=int(os.environ.get("OCR_NGRAM_SIZE", "35")),
        window_size=int(os.environ.get("OCR_WINDOW_SIZE", "128")),
        # How many pages to OCR concurrently. Defaults to 1 (sequential) because
        # on a single 24GB GPU (3090) the model already saturates the GPU per
        # page — concurrent requests thrash the KV cache and run SLOWER. On a
        # larger GPU (A100/H100) with spare KV-cache headroom, vLLM batches the
        # requests and this gives a real 2-3x speedup on multi-page statements
        # without changing output; raise OCR_MAX_WORKERS there (e.g. 4).
        max_workers=int(os.environ.get("OCR_MAX_WORKERS", "1")),
        endpoint_class=classify_endpoint(base_url),
        remote_opt_in=remote_opt_in_from_env(),
    )
