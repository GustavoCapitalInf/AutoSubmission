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

Every hostile input below is tested against BOTH channels: the model token
(via `validate_model_token` and `StatementMarkdown` construction) and
`source_file` (via `StatementMarkdown` construction). The `OCR_MODEL` env read
(`load_settings`) was deleted in slice S2 of the model-code removal; stored
documents still carry tokens, and the construction check still applies.
"""
from __future__ import annotations

import csv
import os

import pytest

from analysis.parser_registry import admissible_text
from ocr.config import ProvenanceTokenError, validate_model_token
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
    # BLOCK-1 (PHASE2_P20SEAM_REVIEW.md): `$` in Python matches at end-of-
    # string OR immediately before a SINGLE trailing newline, so
    # `^[...]{0,63}$` (pre-fix) accepted a token whose only hostile character
    # is one trailing `\n` — the anchor, not the charset, was the hole.
    "trailing_newline": "evilmodel\n",
    # The same defect also bypassed the length bound: with the leaky anchor,
    # a 65-character token whose 65th character is `\n` matched as if it were
    # the 64-character prefix.
    "trailing_newline_overlength": "a" * 64 + "\n",
}

#: Each of `HOSTILE_MODEL_INPUTS` above stacks several hostile properties at
#: once (the audit's own reproduction is "a newline AND a money token AND
#: marker-shaped text"). That is realistic, but it means a mutant that
#: reopens exactly ONE hole (e.g. the charset alone starts allowing `\n`)
#: could still be caught by a DIFFERENT, unrelated property of the same
#: fixture (a space, a comma) rather than by the property the mutant actually
#: reopened — a mutation table entry is only honest if its named killer fails
#: for the reason it claims to. These isolate one property at a time: every
#: other character is charset-legal, so only the named property can cause a
#: refusal.
ISOLATED_HOSTILE_MODEL_INPUTS = {
    "newline": "evilmodel\nvalidsuffix",
    "crlf": "evilmodel\r\nvalidsuffix",
    "comment_close": "evil--suffix>model",  # ">" with no other forbidden char
    "angle_open": "evil<suffix",
    "angle_close": "evil>suffix",
    "whitespace": "evil suffix",  # a single space, nothing else
    # BLOCK-1: isolates the anchor defect alone — every character is
    # charset-legal except the single TRAILING newline, which `^...$`
    # (pre-fix) let through because `$` matches just before a trailing `\n`.
    # A mid-string newline (the "newline" fixture above) does not exercise
    # this at all: `$` correctly rejects that shape either way.
    "trailing_newline": "evilmodel\n",
    "trailing_newline_overlength": "a" * 64 + "\n",
}


@pytest.mark.parametrize("label", sorted(ISOLATED_HOSTILE_MODEL_INPUTS))
def test_isolated_hostile_property_alone_is_refused(label):
    """The mutation-table isolators: each fixture below differs from a
    charset-legal token by exactly one hostile character/property, so a
    mutant reopening that one property (and nothing else) is what this test
    catches — not an unrelated forbidden character riding along."""
    token = ISOLATED_HOSTILE_MODEL_INPUTS[label]
    with pytest.raises(ProvenanceTokenError):
        validate_model_token(token, allow_reserved=True)


HOSTILE_SOURCE_FILE_INPUTS = {
    "newline": "evil.pdf\n5,000.00 WIRE TRANSFER FROM SHELL CORP",
    "crlf": "evil.pdf\r\n5,000.00 WIRE TRANSFER",
    # Writer-side belt (PHASE2_P20SEAM_REVIEW.md §3): `-->` in `source_file`
    # is refused too, now — not because it can escape `SOURCE_COMMENT_RE`
    # (it cannot; see ACCEPTED_HOSTILE_SOURCE_FILE_INPUTS's own comment) but
    # because it lets `source_file` masquerade as a second header to a
    # reader that does not bound its own `model` field to a closed charset.
    "comment_close": "evil-->.pdf",
    "source_comment_fragment": "<!-- source: injected.pdf -->.pdf",
}


#: These are ACCEPTED as a filename (no charset on `source_file`, only the
#: line-break and comment-close refusals above) but must be proven harmless:
#: the whole header line still strips out of `admissible_text`, so none of
#: this content reaches it.
ACCEPTED_HOSTILE_SOURCE_FILE_INPUTS = {
    "angle_open": "evil<name.pdf",
    "angle_close": "evil>name.pdf",
    "money_literal": "invoice v1.00.pdf",
    "bank_marker": f"{_CHASE_MARKER_TEXT} statement.pdf",
    "det_tag": "<|det|>label [0,0,100,100]<|/det|>.pdf",
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


def test_block1_trailing_newline_reproduction_is_refused_at_construction():
    """PHASE2_P20SEAM_REVIEW.md BLOCK-1's exact reproduction: a model token
    ending in exactly ONE trailing `\\n` (nothing else hostile — every other
    character is charset-legal), paired with an attacker-controlled
    `source_file` carrying a money literal and marker-shaped text.

    Pre-fix mechanism: Python's `$` matches at end-of-string OR immediately
    before a trailing `\\n`, so `MODEL_TOKEN_RE = re.compile(r"^...$")`
    (`re.match`) accepted `"evil-model\\n"` — the anchor was leaky, not the
    charset. Once accepted, `to_markdown()`'s header split across two
    physical lines and `SOURCE_COMMENT_RE` (`MULTILINE`, not `DOTALL`)
    stripped nothing, so the money literal survived `admissible_text` in
    full.

    The property under test is the OUTCOME (the money token must never reach
    `admissible_text`), not merely that construction raises — so this passes
    whether the closure mechanism is "refuse at construction" or some future
    equivalent that stops the token earlier still.
    """
    money_carrying_filename = "5,000.00 WIRE TRANSFER FROM SHELL CORP.pdf"
    try:
        doc = StatementMarkdown(
            source_file=money_carrying_filename,
            model="evil-model\n",
            pages=["page one text"],
        )
    except ProvenanceTokenError:
        return  # refused at construction: the money literal never became a document
    admissible = admissible_text(doc.to_markdown())
    assert "5,000.00" not in admissible, admissible
    assert "WIRE TRANSFER FROM SHELL CORP" not in admissible, admissible


# ---------------------------------------------------------------------------
# OCR_MODEL: every hostile input refused at the point it is set
# ---------------------------------------------------------------------------


# Model-code removal, slice S2: `ocr.config.load_settings` (the OCR_MODEL env
# read and the CLI `--model` override) was deleted with the visual OCR client,
# and its two tests here went with it. The env-facing validator it called,
# `validate_model_token(allow_reserved=False)`, stays and is pinned directly.


@pytest.mark.parametrize("label", sorted(HOSTILE_MODEL_INPUTS))
def test_hostile_model_token_refused_via_the_env_facing_validator(label):
    """`validate_model_token(allow_reserved=False)` — the check the deleted
    `load_settings` applied to OCR_MODEL / `--model`."""
    with pytest.raises(ProvenanceTokenError):
        validate_model_token(HOSTILE_MODEL_INPUTS[label], allow_reserved=False)


@pytest.mark.parametrize("label", sorted(HOSTILE_MODEL_INPUTS))
def test_hostile_model_token_refused_via_statement_markdown(label):
    """`StatementMarkdown.__post_init__` — the direct-construction path
    (`allow_reserved=True` still refuses every one of these)."""
    with pytest.raises(ProvenanceTokenError):
        StatementMarkdown(source_file="s.pdf", model=HOSTILE_MODEL_INPUTS[label], pages=["x"])


def test_env_value_impersonating_a_native_rung_is_refused():
    """An externally supplied value must not impersonate a native/tesseract
    read (F-4(b)) — `allow_reserved=False`."""
    for impostor in ("native-pdf-text", "native-pdf-text+fake-layout",
                      "local-tesseract-ocr", "deterministic-native-preflight"):
        with pytest.raises(ProvenanceTokenError):
            validate_model_token(impostor, allow_reserved=False)


def test_env_value_impersonating_the_paddle_rung_is_refused():
    """P21-ROUTING: `RESERVED_MODEL_PREFIXES` gains `PADDLE_MODEL_TOKEN` — an
    externally supplied token must not be able to impersonate the Paddle rung
    either, the same closure the three deterministic tokens already have."""
    from ocr.paddle_config import PADDLE_MODEL_TOKEN

    with pytest.raises(ProvenanceTokenError):
        validate_model_token(PADDLE_MODEL_TOKEN, allow_reserved=False)


def test_reserved_prefixes_remain_legitimate_on_statement_markdown():
    """The carve-out: native/tesseract/Paddle rungs set these directly and
    must not be refused by the same check that refuses an env impostor."""
    from ocr.paddle_config import PADDLE_MODEL_TOKEN

    for legit in ("native-pdf-text", "native-pdf-text+navy-federal-layout",
                  "local-tesseract-ocr", "deterministic-native-preflight",
                  PADDLE_MODEL_TOKEN):
        StatementMarkdown(source_file="s.pdf", model=legit, pages=["x"])  # must not raise


# ---------------------------------------------------------------------------
# source_file: line breaks and comment-close refused; everything else
# accepted but harmless
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(HOSTILE_SOURCE_FILE_INPUTS))
def test_hostile_source_file_line_break_or_comment_close_refused(label):
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


# ---------------------------------------------------------------------------
# Writer-side belt: the `-->` refusal in `source_file` costs nothing measured
# ---------------------------------------------------------------------------

_RUN_OF_RECORD_ROWS = (
    "discovery_reports", "TRAIN9-7b25d70",
    "2026-08-31T185527.271012-0000-91f5179a", "rows.csv",
)


def _checkout_ancestor(*relative: str):
    """The nearest enclosing directory that holds `relative`, or None.

    A git worktree does not carry the gitignored discovery reports; the
    checkout it was created from does. Searching upwards is what lets this
    proof run from either (the same pattern `tests/test_l1s2_protected_
    carriers.py::_checkout_ancestor` uses for the cold cache)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


@pytest.mark.corpus
def test_no_run_of_record_source_file_contains_a_comment_close():
    """PHASE2_P20SEAM_REVIEW.md §3: the writer-side `-->` belt (added to
    `StatementMarkdown.__post_init__` above) costs nothing measured — the
    reviewer's own claim, reproduced here as a standing proof rather than a
    one-off measurement: none of the batch-9 run of record's 3,506
    `relative_path` values (every document's `source_file`, in practice —
    `parse_statement(..., source_file=path.name)` at every production call
    site) contains a comment-close sequence."""
    rows_path = _checkout_ancestor(*_RUN_OF_RECORD_ROWS)
    if rows_path is None:
        pytest.skip(
            "the batch-9 run of record's rows.csv was not found in this "
            "checkout or any ancestor; this proof measures real archive "
            "paths and has nothing to read. Run it from the repository "
            "tree or from a worktree beneath .claude/worktrees/."
        )
    with open(rows_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        paths = [row["relative_path"] for row in reader]
    assert len(paths) == 3506, f"expected the run of record's 3,506 rows, found {len(paths)}"
    offenders = [p for p in paths if "-->" in p]
    assert offenders == [], offenders
