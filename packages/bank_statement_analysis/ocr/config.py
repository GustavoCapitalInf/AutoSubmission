from __future__ import annotations
import re

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Import-time `.env` loading stays: several entry points reach their first
# `load_dotenv()` through this module (`ocr.document` imports it), and the
# order in which the `.env` values become visible must not move.
if load_dotenv is not None:
    load_dotenv()

# What lives here is the provenance-token content policy every `StatementMarkdown` is checked against.


class ProvenanceTokenError(ValueError):
    """A model/provenance token failed the closed-charset content policy.

    A model token is not only a label: it is text stamped into the
    first line of every document's analysis input
    (`ocr.document.StatementMarkdown.to_markdown`). Raised at the point the
    token is SET — a `StatementMarkdown` construction (`ocr.document`) — never
    at the point it is printed, so a hostile token never becomes a
    `StatementMarkdown.model` in the first place. There is nothing left to
    sanitize downstream.
    """


#: Closed charset: first character alphanumeric, then only `[A-Za-z0-9._/+-]`, length 1-64. It excludes whitespace of
#: any kind, `<`, `>`, `!`, `$`, `,`, quotes and backslash, so a valid token cannot contain `-->`, a `<|det|>`-style
#: region tag, or a `<!-- source:` fragment. Anchored with `\A` / `\Z`, not `^` / `$`: in Python `$` also matches
#: before a trailing `\n`, which would admit a token whose only hostile character is a final newline.
MODEL_TOKEN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}\Z")

#: A money-shaped substring the charset alone does not exclude: digits and a
#: single `.` are both allowed characters, so a version string like "v1.00"
#: is syntactically identical to a two-decimal amount. Matches one or more
#: digits, a literal `.`, then exactly two digits with no third digit
#: following (`(?!\d)`) — "1.00" matches; "1.005" does not, because its
#: two-digit window is immediately followed by another digit, not a
#: non-digit boundary.
_MONEY_SHAPE_RE = re.compile(r"\d+\.\d{2}(?!\d)")

#: The deterministic ladder's own model tokens, plus the retired Paddle and visual-pair tokens (as literals: stored
#: readings still carry them, and `tests/test_config.py` pins them). `validate_model_token(allow_reserved=False)`
#: refuses a token that equals or starts with one, so a supplied token cannot pass for a native read; it has no
#: production caller, only tests. The rungs set these tokens themselves, which is why
#: `StatementMarkdown.__post_init__` validates with `allow_reserved=True`.
RESERVED_MODEL_PREFIXES = (
    "native-pdf-text",
    "local-tesseract-ocr",
    "deterministic-native-preflight",
    "paddle-ocr+ppocrv5",
    "visual-pair-dots-qwen",
)


def validate_model_token(token: str, *, allow_reserved: bool) -> str:
    """Validate a model/provenance token against the closed charset.

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
