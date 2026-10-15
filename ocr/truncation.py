"""OCR truncation detection (Wave 2 / O-3): flag-only page integrity.

Model-code removal, slice S2: the visual OCR client (``ocr/ocr_client.py``)
and the local server it spoke to are gone, so nothing in the tree produces a
model-side signal any more; the offline rungs are assessed structurally, and
the model-side reading below stays for stored legacy reads (deleting it is a
separate follow-up). The text below describes the rung as it was.

A silently truncated page is the worst OCR failure mode we have: the markdown
looks well-formed, the parser claims it, the reconciliation gate reports a
"missing transactions" delta, and the document is filed as a parser defect
instead of an intake defect. This module turns that silence into an explicit
signal on the OCR result.

Two independent evidence classes
--------------------------------
1. **Model-side** — what the OCR endpoint itself reports about why generation
   stopped. The client speaks the OpenAI chat-completions dialect
   (``ocr/ocr_client.py``), so the authoritative field is
   ``choices[0].finish_reason``: ``"stop"`` means the model finished, ``"length"``
   means it hit ``max_tokens`` (``ocr_client._MAX_TOKENS``, 4096) mid-page. When
   the endpoint reports token usage, ``completion_tokens >= max_tokens`` is the
   same fact observed from the other side and is accepted as a fallback (the
   local server in ``local_ocr_server.py`` reports ``finish_reason`` but no
   ``usage`` block, and a streamed response carries ``finish_reason`` only on the
   final chunk). Both are read defensively: an endpoint that reports neither
   simply yields no model-side signal, never a false one.

2. **Structural page-tail** — a page whose *tail* leaves markup open. The OCR
   model emits transaction tables as HTML (``<table><tr><td>``); a completed page
   always closes what it opened, and each page is OCR'd independently, so a
   statement table continuing onto the next page still closes on this one. A page
   that ends inside a table, row, or cell — or inside a half-written tag — was cut
   off mid-generation. Nothing else produces that shape: ``ocr_client.postprocess``
   rebuilds tables balanced, and the det-tag/placeholder strippers only remove
   matched constructs.

Precision over recall — deliberately
------------------------------------
A flagged page routes to re-OCR or human review, so a false positive costs real
money and analyst attention. Every signal here is therefore a *hard* structural
impossibility in a complete read, not a statistical hunch. Signals that would
raise recall at the cost of precision were considered and rejected:

- "page ends without terminal punctuation" — statements end on bare amounts,
  footers, and page numbers all the time;
- "output length is close to the token ceiling" — a dense page legitimately runs
  long, and the ceiling case is already covered exactly by ``finish_reason``;
- "trailing partial money token" (e.g. ``1,234.5``) — single-decimal values occur
  in printed rates ("0.5% APY"), so it would fire on clean pages.

Flag-only (this wave)
---------------------
Nothing here changes extraction. ``assess_pages`` is called by ``ocr/pipeline.py``
*after* a rung's text is final (including the existing mis-segmentation and TD
re-OCR recoveries), and the result is recorded on ``StatementMarkdown``. No page
is re-OCR'd, dropped, or rewritten because of a flag.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------------------
# Model-side signals
# ---------------------------------------------------------------------------

# finish_reason values that mean "generation was cut off by a token ceiling".
# "stop" (finished), "tool_calls"/"function_call" (not applicable to OCR) and
# None (endpoint did not report) are all NOT truncation.
MODEL_TRUNCATION_FINISH_REASONS = frozenset({"length", "max_tokens"})

SIGNAL_FINISH_REASON = "model_finish_reason_length"
SIGNAL_TOKEN_CEILING = "model_token_ceiling_reached"

# ---------------------------------------------------------------------------
# Structural page-tail signals
# ---------------------------------------------------------------------------

SIGNAL_OPEN_TABLE = "open_table_at_tail"
SIGNAL_OPEN_ROW = "open_row_at_tail"
SIGNAL_OPEN_CELL = "open_cell_at_tail"
SIGNAL_PARTIAL_TAG = "partial_tag_at_tail"

# (signal, opening-tag pattern, closing-tag pattern). Attribute-tolerant:
# ocr_client emits <td colspan=...> in repaired tables.
_TAG_PAIRS = (
    (SIGNAL_OPEN_TABLE, re.compile(r"<table\b[^>]*>", re.I), re.compile(r"</\s*table\s*>", re.I)),
    (SIGNAL_OPEN_ROW, re.compile(r"<tr\b[^>]*>", re.I), re.compile(r"</\s*tr\s*>", re.I)),
    (SIGNAL_OPEN_CELL, re.compile(r"<t[dh]\b[^>]*>", re.I), re.compile(r"</\s*t[dh]\s*>", re.I)),
)

# A tag start that never closes, running to the end of the page: "<td", "<|det",
# "</tab". The character class requires a letter or the model's "|" special-token
# marker after the (optional) slash, so prose comparisons ("balance < 0") and bare
# angle noise are not tags.
_PARTIAL_TAG_TAIL_RE = re.compile(r"<\s*/?\s*[A-Za-z|][^>]*\Z")
# At least one complete tag somewhere on the page — the gate that makes the
# partial-tag signal meaningful (native-text and Tesseract pages carry no markup,
# so a stray "<" in a description can never flag them).
_ANY_TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z|][^>]*>")


@dataclass
class PageIntegrity:
    """Truncation evidence for one OCR page. ADVISORY: consumed by downstream
    routing (re-OCR / review), never by extraction."""

    page_index: int
    truncated: bool = False
    signals: list[str] = field(default_factory=list)
    finish_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class PageText(str):
    """OCR page markdown that also carries the model's completion signals.

    A ``str`` subclass rather than a ``(text, meta)`` tuple on purpose: the page
    text flows through several re-OCR/recovery branches in ``ocr/pipeline.py``
    (mis-segmentation fallback, TD page-1 recovery) which pick *which* read to
    keep. Carrying the metadata on the value itself means the signals always
    describe the read that was actually kept, with no attribution bookkeeping —
    and every existing consumer, including test doubles that return a plain
    ``str``, keeps working unchanged (readers use ``getattr(..., None)``).
    """

    __slots__ = ("finish_reason", "completion_tokens", "max_tokens")

    def __new__(cls, text: str = "", *, finish_reason: str | None = None,
                completion_tokens: int | None = None, max_tokens: int | None = None):
        obj = super().__new__(cls, text)
        obj.finish_reason = finish_reason
        obj.completion_tokens = completion_tokens
        obj.max_tokens = max_tokens
        return obj


def model_truncation_signals(finish_reason: str | None,
                             completion_tokens: int | None = None,
                             max_tokens: int | None = None) -> list[str]:
    """Truncation signals reported by the OCR endpoint itself."""
    signals: list[str] = []
    if isinstance(finish_reason, str) and finish_reason.strip().lower() in MODEL_TRUNCATION_FINISH_REASONS:
        signals.append(SIGNAL_FINISH_REASON)
    if (isinstance(completion_tokens, int) and isinstance(max_tokens, int)
            and max_tokens > 0 and completion_tokens >= max_tokens):
        signals.append(SIGNAL_TOKEN_CEILING)
    return signals


def _last_start(pattern: re.Pattern, text: str) -> int:
    last = -1
    for match in pattern.finditer(text):
        last = match.start()
    return last


def structural_tail_signals(text: str) -> list[str]:
    """Truncation signals visible in the page tail alone.

    Fires only on markup a complete read could not have left open: an unclosed
    ``<table>``/``<tr>``/``<td>`` after the last matching close tag, or a tag that
    was still being written when generation stopped.
    """
    if not text:
        return []
    signals: list[str] = []
    for signal, open_re, close_re in _TAG_PAIRS:
        last_open = _last_start(open_re, text)
        if last_open >= 0 and last_open > _last_start(close_re, text):
            signals.append(signal)
    stripped = text.rstrip()
    if _ANY_TAG_RE.search(stripped) and _PARTIAL_TAG_TAIL_RE.search(stripped):
        signals.append(SIGNAL_PARTIAL_TAG)
    return signals


def assess_page(text: str, *, page_index: int = 0,
                finish_reason: str | None = None,
                completion_tokens: int | None = None,
                max_tokens: int | None = None) -> PageIntegrity:
    """Assess one page. Model-side metadata is taken from the arguments when
    given, otherwise from the ``PageText`` the OCR client returned."""
    if finish_reason is None:
        finish_reason = getattr(text, "finish_reason", None)
    if completion_tokens is None:
        completion_tokens = getattr(text, "completion_tokens", None)
    if max_tokens is None:
        max_tokens = getattr(text, "max_tokens", None)

    signals = model_truncation_signals(finish_reason, completion_tokens, max_tokens)
    signals += structural_tail_signals(text)
    return PageIntegrity(page_index=page_index, truncated=bool(signals),
                         signals=signals, finish_reason=finish_reason)


def assess_pages(pages) -> list[PageIntegrity]:
    """Assess every page of a rung's output, in page order."""
    return [assess_page(page or "", page_index=index) for index, page in enumerate(pages)]
