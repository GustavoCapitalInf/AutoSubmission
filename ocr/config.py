from __future__ import annotations
import re

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Import-time `.env` loading stays (D20): several entry points reach their first
# `load_dotenv()` through this module (`ocr.document` imports it), and the
# order in which the `.env` values become visible must not move.
if load_dotenv is not None:
    load_dotenv()

# Model-code removal, slice S2 (owner ruling of 2026-10-13: the product uses no
# model). The visual OCR settings (`Settings`, `load_settings` and their
# OCR_MODEL / OCR_BASE_URL / OCR_NGRAM_SIZE / OCR_WINDOW_SIZE / OCR_API_KEY /
# OCR_TIMEOUT / OCR_RETRIES / OCR_MAX_WORKERS / OCR_ALLOW_VISUAL_PAIR /
# OCR_VISUAL_PAIR_* reads) were the retired Unlimited-OCR client's and the
# visual pair's (removed in slice S4); nothing in this tree reads those names
# any more. The OCR cache key keeps their default
# values as frozen literals (`webapp.artifact_cache`). What stays here is the
# provenance-token content policy every `StatementMarkdown` is checked against.


class ProvenanceTokenError(ValueError):
    """A model/provenance token failed the closed-charset content policy.

    F-4(b) / MAJOR-2: a model token is not only a label — it is text stamped
    into the first line of every document's analysis input
    (`ocr.document.StatementMarkdown.to_markdown`). Raised at the point the
    token is SET — a `StatementMarkdown` construction (`ocr.document`) — never
    at the point it is printed, so a hostile token never becomes a
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
#: carve-out. `_MONEY_SHAPE_RE` is unanchored by design (a `.search`, not a
#: full-string match, so `$` there was never the same hazard).
MODEL_TOKEN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}\Z")

#: A money-shaped substring the charset alone does not exclude: digits and a
#: single `.` are both allowed characters, so a version string like "v1.00"
#: is syntactically identical to a two-decimal amount. Matches one or more
#: digits, a literal `.`, then exactly two digits with no third digit
#: following (`(?!\d)`) — "1.00" matches; "1.005" does not, because its
#: two-digit window is immediately followed by another digit, not a
#: non-digit boundary.
_MONEY_SHAPE_RE = re.compile(r"\d+\.\d{2}(?!\d)")

#: The deterministic ladder's own model tokens, plus the Paddle and visual-pair
#: tokens. An externally supplied token checked with `allow_reserved=False`
#: must never equal or start with one of these — that would spoof
#: `telemetry.record.source_path_for`, `telemetry.prices.py`'s free-model
#: table, and cell D's Q3 native-only gate into believing an
#: operator-controlled read is a native/offline one. The rungs legitimately set
#: these tokens directly on `StatementMarkdown`, which is why
#: `ocr.document.StatementMarkdown.__post_init__` validates with
#: `allow_reserved=True`.
#:
#: The Paddle and visual-pair tokens are LITERALS here since slice S2 (this
#: module no longer imports `ocr.paddle_config` or `ocr.visual_pair_config`):
#: "paddle-ocr+ppocrv5" was `ocr.paddle_config.PADDLE_MODEL_TOKEN` until the
#: PaddleOCR rung was removed in slice S5, and "visual-pair-dots-qwen" was
#: `ocr.visual_pair_config.MODEL_TOKEN` until the visual pair was removed in
#: slice S4 (stored readings still carry both, and `telemetry.record`'s
#: `PADDLE_MODEL_TOKENS` / `VISUAL_PAIR_MODEL_TOKENS` still name them).
#: `tests/test_config.py` pins both as literals.
#: `validate_model_token(allow_reserved=False)` lost its only production
#: caller with `load_settings` (follow-up).
RESERVED_MODEL_PREFIXES = (
    "native-pdf-text",
    "local-tesseract-ocr",
    "deterministic-native-preflight",
    "paddle-ocr+ppocrv5",
    "visual-pair-dots-qwen",
)


def validate_model_token(token: str, *, allow_reserved: bool) -> str:
    """Validate a model/provenance token against the closed charset (F-4(b)).

    Returns the token byte-identical when it is accepted (this function never
    mutates or truncates); raises `ProvenanceTokenError` otherwise.

    `allow_reserved=False` also refuses a token that equals or starts with a
    `RESERVED_MODEL_PREFIXES` entry — an externally supplied value must not
    impersonate a native read. `allow_reserved=True`
    (`StatementMarkdown.__post_init__`) skips that one check, because the
    native and local-tesseract rungs legitimately set those exact tokens
    themselves.
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
