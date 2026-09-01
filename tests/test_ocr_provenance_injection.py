"""P20-SEAM: OCR_MODEL / `source_file` provenance-token injection, closed.

**The base-tree reproduction (F-4(b) / MAJOR-2), before this branch's fix.**
`OCR_MODEL` was a plain env read (`ocr/config.py`, pre-fix) stamped verbatim
into the first line of every visual-OCR document's analysis input
(`ocr.document.StatementMarkdown.to_markdown`). `analysis.parser_registry.
SOURCE_COMMENT_RE` (`^<!--\\s*SOURCE:.*?-->\\s*$`, `MULTILINE`, **not**
`DOTALL`) only strips that header when it stays on one line. Reproduced on
the base tree before any fix in this file existed::

    doc = StatementMarkdown(
        source_file="innocuous.pdf",
        model="evil-model\\n5,000.00 WIRE TRANSFER FROM SHELL CORP",
        pages=["page one text"],
    )
    admissible_text(doc.to_markdown())
    # -> the ENTIRE header survived, unstripped: the money token, the
    #    marker-shaped text, and the plotted newline all reached the text
    #    every parser's detection markers scan and every text metric runs
    #    over. `"5,000.00" in admissible_text(...)` was True.

The base-tree construction above **no longer completes**: `StatementMarkdown.
__post_init__` now validates `model` at the point it is SET and raises
`ocr.config.ProvenanceTokenError` before `to_markdown` is ever called — see
`test_the_base_tree_reproduction_is_now_refused_at_construction` below,
which is this exact reproduction, now asserted to raise rather than to leak.

**What closes it.** `ocr.config.MODEL_TOKEN_RE` (first character
alphanumeric, then only `[A-Za-z0-9._/+-]`, length 1-64) structurally
excludes whitespace of any kind (so `\\n`, `\\r`, a plain space), `<`, `>`,
`!`, `$`, `,`, quotes and backslash — which is also why a valid token cannot
contain `-->`, a `<|det|>`-style tag, or a `<!-- source:` fragment.
`ocr.config.validate_model_token` additionally refuses a money-shaped
substring (`\\d+\\.\\d{2}(?!\\d)`, e.g. "v1.00") and, for env-supplied tokens
only (`allow_reserved=False`), a token that impersonates a reserved
deterministic-rung prefix. `StatementMarkdown.__post_init__` validates with
`allow_reserved=True` (the native/local-tesseract rungs legitimately set
those exact prefixes) and separately refuses a `source_file` containing a
line break — the one property `source_file` needs, since a `-->` alone does
NOT escape the guard (backtracking consumes to the LAST `-->` on the line;
only a real newline breaks the single-line match).

Every hostile input below is tested against BOTH channels: `OCR_MODEL` (via
`load_settings`) and `source_file` (via `StatementMarkdown` construction).
"""
from __future__ import annotations

import os

import pytest

from analysis.parser_registry import admissible_text
from ocr.config import ProvenanceTokenError, load_settings, validate_model_token
from ocr.document import StatementMarkdown

# ---------------------------------------------------------------------------
# Hostile inputs (the card's list, verbatim)
# ---------------------------------------------------------------------------

#: `analysis.chase.DETECTION_MARKERS`'s "bank_name" marker text, mirrored here
#: (not imported) so this fixture stays a fixture even if the parser's own
#: marker text is later edited — a bank/parser-like marker string is exactly
#: the shape a hostile OCR_MODEL or filename could carry.
_CHASE_MARKER_TEXT = "JPMorgan Chase Bank"

HOSTILE_MODEL_INPUTS = {
    "newline": "evil-model\n5,000.00 WIRE TRANSFER FROM SHELL CORP",
    "crlf": "evil-model\r\n5,000.00 WIRE TRANSFER",
    "comment_close": "evil-->model",
    "angle_open": "evil<model",
    "angle_close": "evil>model",
    "money_literal": "v1.00",
    "bank_marker": _CHASE_MARKER_TEXT,
    "det_tag": "<|det|>label [0,0,100,100]<|/det|>",
    "source_comment_fragment": "<!-- source: injected.pdf -->",
    "whitespace": "evil model",
    "over_length": "a" * 65,
}

HOSTILE_SOURCE_FILE_INPUTS = {
    "newline": "evil.pdf\n5,000.00 WIRE TRANSFER FROM SHELL CORP",
    "crlf": "evil.pdf\r\n5,000.00 WIRE TRANSFER",
}

#: These are ACCEPTED as a filename (no charset on `source_file`, only the
#: line-break refusal) but must be proven harmless: the whole header line
#: still strips out of `admissible_text`, so none of this content reaches it.
ACCEPTED_HOSTILE_SOURCE_FILE_INPUTS = {
    "comment_close": "evil-->.pdf",
    "angle_open": "evil<name.pdf",
    "angle_close": "evil>name.pdf",
    "money_literal": "invoice v1.00.pdf",
    "bank_marker": f"{_CHASE_MARKER_TEXT} statement.pdf",
    "det_tag": "<|det|>label [0,0,100,100]<|/det|>.pdf",
    "source_comment_fragment": "<!-- source: injected.pdf -->.pdf",
    "whitespace": "a filename with spaces.pdf",
    "over_length": ("a" * 500) + ".pdf",
}


# ---------------------------------------------------------------------------
# The base-tree reproduction, now refused
# ---------------------------------------------------------------------------


def test_the_base_tree_reproduction_is_now_refused_at_construction():
    """The exact injection this module's docstring reproduces on the base
    tree: refused at `StatementMarkdown` construction, never reaching
    `to_markdown` or `admissible_text` at all."""
    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(
            source_file="innocuous.pdf",
            model="evil-model\n5,000.00 WIRE TRANSFER FROM SHELL CORP",
            pages=["page one text"],
        )


# ---------------------------------------------------------------------------
# OCR_MODEL: every hostile input refused at the point it is set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(HOSTILE_MODEL_INPUTS))
def test_hostile_model_token_refused_via_load_settings_override(label):
    """`load_settings(model_override=...)` — the CLI `--model` path."""
    with pytest.raises(ProvenanceTokenError):
        load_settings(model_override=HOSTILE_MODEL_INPUTS[label])


@pytest.mark.parametrize("label", sorted(HOSTILE_MODEL_INPUTS))
def test_hostile_model_token_refused_via_ocr_model_env(monkeypatch, label):
    """`load_settings()` reading `OCR_MODEL` — the env / server path."""
    monkeypatch.setenv("OCR_MODEL", HOSTILE_MODEL_INPUTS[label])
    with pytest.raises(ProvenanceTokenError):
        load_settings()


@pytest.mark.parametrize("label", sorted(HOSTILE_MODEL_INPUTS))
def test_hostile_model_token_refused_via_statement_markdown(label):
    """`StatementMarkdown.__post_init__` — the direct-construction path
    (`allow_reserved=True` still refuses every one of these)."""
    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(source_file="s.pdf", model=HOSTILE_MODEL_INPUTS[label], pages=["x"])


def test_env_value_impersonating_a_native_rung_is_refused():
    """An env value must not impersonate a native/tesseract read (F-4(b))."""
    for impostor in ("native-pdf-text", "native-pdf-text+fake-layout",
                      "local-tesseract-ocr", "deterministic-native-preflight"):
        with pytest.raises(ProvenanceTokenError):
            load_settings(model_override=impostor)


def test_reserved_prefixes_remain_legitimate_on_statement_markdown():
    """The carve-out: native/tesseract rungs set these directly and must not
    be refused by the same check that refuses an env impostor."""
    for legit in ("native-pdf-text", "native-pdf-text+navy-federal-layout",
                  "local-tesseract-ocr", "deterministic-native-preflight"):
        StatementMarkdown(source_file="s.pdf", model=legit, pages=["x"])  # must not raise


# ---------------------------------------------------------------------------
# source_file: line breaks refused; everything else accepted but harmless
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(HOSTILE_SOURCE_FILE_INPUTS))
def test_hostile_source_file_line_break_refused(label):
    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(source_file=HOSTILE_SOURCE_FILE_INPUTS[label], model="native-pdf-text", pages=["x"])


@pytest.mark.parametrize("label", sorted(ACCEPTED_HOSTILE_SOURCE_FILE_INPUTS))
def test_accepted_hostile_source_file_never_reaches_admissible_text(label):
    """No charset on `source_file` (a filename may legitimately contain
    almost anything) — but every one of these must still be fully absent
    from `admissible_text`, because the whole header line strips out
    regardless of what is inside it, as long as it stays on one line."""
    filename = ACCEPTED_HOSTILE_SOURCE_FILE_INPUTS[label]
    doc = StatementMarkdown(source_file=filename, model="native-pdf-text", pages=["ordinary page text"])
    admissible = admissible_text(doc.to_markdown())
    assert filename not in admissible, (label, filename, admissible[:200])


# ---------------------------------------------------------------------------
# End-to-end: every ACCEPTED (valid) token's header strips out whole
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "native-pdf-text",
        "native-pdf-text+navy-federal-layout",
        "local-tesseract-ocr",
        "baidu/Unlimited-OCR",
        "deterministic-native-preflight",
        "",
    ],
)
def test_every_accepted_model_token_header_strips_whole(model):
    """The header is stripped WHOLE — `admissible_text` carries none of the
    accepted token's characters (beyond what the page text itself contains),
    proving the guard closes the channel rather than merely not-yet-having a
    reason to."""
    doc = StatementMarkdown(source_file="statement.pdf", model=model, pages=["ordinary page text only"])
    markdown = doc.to_markdown()
    admissible = admissible_text(markdown)
    assert "<!--" not in admissible
    assert "source:" not in admissible.lower()
    if model:
        assert model not in admissible


# ---------------------------------------------------------------------------
# validate_model_token: direct unit coverage of the closed-charset function
# ---------------------------------------------------------------------------


def test_validate_model_token_returns_the_token_byte_identical():
    for token in ("native-pdf-text+wells", "baidu/Unlimited-OCR", "a"):
        assert validate_model_token(token, allow_reserved=True) == token


def test_validate_model_token_rejects_empty_string():
    with pytest.raises(ProvenanceTokenError):
        validate_model_token("", allow_reserved=True)


def test_validate_model_token_boundary_length():
    ok = "a" * 64
    assert validate_model_token(ok, allow_reserved=True) == ok
    with pytest.raises(ProvenanceTokenError):
        validate_model_token("a" * 65, allow_reserved=True)
