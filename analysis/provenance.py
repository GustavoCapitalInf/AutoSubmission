"""Reads the extractor-model token off a document's own OCR header. Nothing else.

`ocr/document.py::StatementMarkdown.to_markdown()` stamps every document with a
header before any page content:

    <!-- source: <file> | pages: <n> | model: <model> | empty: <n> -->\\n\\n...

That header is the platform's only record of WHICH extractor produced the text
a parser is about to read. This module answers exactly one question about
it — "what does the trusted code's own trailing fields say the model was" —
and answers nothing else.

BLOCK-1 (`PHASE2_P20SURFACES_REVIEW.md`, reproduced and closed here): an
earlier version matched the header's fields with `.*?` (non-greedy) up to the
FIRST `-->` on line one, on the theory that `source_file` "is not guaranteed to
be free of the pipe character". That theory was correct and the fix was wrong
in the direction that matters: `source_file` is the UPLOADED FILENAME
(`webapp/app.py` -> `webapp/worker.py` -> `ocr/document.py`, unsanitised,
`webapp/app.py` states outright that "filename is attacker-supplied"), so a
filename containing `| pages: 1 | model: native-pdf-text | empty: 0 -->`
closed the header EARLY, at the attacker's fake `-->`, and handed back
`native-pdf-text` for a document whose real model field said something else
entirely.

THE FIX, in the ruling's own words: **parse from the RIGHT.** `empty:` is
always the LAST field `to_markdown()` writes and `model:` is always the ONE
BEFORE it — both are appended by TRUSTED code, unconditionally, after
whatever `source_file` contains. So instead of matching UP TO the first `-->`
(which an attacker controls), this match requires the ENTIRE remainder of the
document up to and including the closing `-->`, anchored on the LEFT at
character 0 (`\\A`) and, structurally, on the RIGHT at the guaranteed
blank-line separator `to_markdown()` always writes immediately after the
header (`blocks = [header, ""]`, joined by `"\\n\\n"` — so the two characters
right after `-->` are ALWAYS `\\n\\n`, whatever `header` itself contains).
`source` is matched GREEDILY and in `DOTALL` (so it may span embedded
newlines, closing the "inject a newline to relocate the real fields past
`extractor_model`'s old first-line boundary" hole in the same reproduction):
a greedy match backtracks from the END of the string, so of every substring
that LOOKS like a complete `| pages: N | model: TOKEN | empty: N -->` run,
the one this reader finds is always the LAST one in the document — and the
genuine, code-appended fields are PROVABLY the last such run, because nothing
legitimate follows them before the mandatory blank line. An attacker can make
`source_file` contain any number of FAKE, earlier-occurring header shapes;
none of them can be the last one, because the real fields are always
appended after `source_file`, verbatim, by code the reader does not have to
trust `source_file` to reach.

This is still "read the header, not the page" in the sense the module always
claimed: the match must start at the very first character of the document
(`\\A`), so a claim that starts anywhere else — including a real header two
physical lines down, or a header a PAGE printed as ordinary text — is not
found. It is no longer "read only physical line one", because a hostile
`source_file` can make "line one" (as `str.split("\\n", 1)` would see it) an
attacker-complete fake header with the genuine fields pushed past an injected
newline — exactly the second half of BLOCK-1's reproduction, and exactly what
requiring the guaranteed trailing blank line closes.

The `model` field is bounded to a closed charset — `[A-Za-z0-9._/+-]`, the
same one `ocr/config.py`'s token validation uses (P20-SEAM) — so no run of
`|`, `<`, `>` or whitespace inside a forged field can be mistaken for part of
the model token even if it somehow survived to sit in that position.

A first line that is not this shape, or a document that has no header at
all, answers `None`. Absence refuses — the direction
`tests/test_q3_native_only.py` depends on.

Used by `analysis/sibling_omission.py::publish_omissions` to gate the
`printed_pair_coincides_and_no_row_printed` omission class to native-pdf-text
provenance (Q3, `PHASE2_ARCHITECTURE_PLAN.md` §6 last paragraph; `OCR_LEGACY_
AUDIT.md` §5.8 step 6): that class was corroborated only on `native-pdf-text`
documents and the OCR row-loss failure mode it exists to bound has never been
measured on OCR'd input.
"""
from __future__ import annotations

import re

#: The closed charset a model token may be built from — no `|`, `<`, `>`, no
#: whitespace of any kind. Matches the token grammar `ocr/config.py`'s
#: validation uses for the same field (P20-SEAM), so a token this reader
#: accepts is a token that writer would also accept.
_MODEL_CHARSET = r"[A-Za-z0-9._/+-]"

#: The header's shape. `\A` anchors the LEFT edge at the very first character
#: of the document — a header that is not the first thing in the document is
#: not found. `(?P<source>.*)` is GREEDY and `re.DOTALL` lets it span embedded
#: newlines, so backtracking from the end of the string always prefers the
#: LAST occurrence of a complete `| pages: N | model: TOKEN | empty: N -->`
#: run — which is provably the trusted, code-appended one (BLOCK-1, this
#: module's docstring). The RIGHT edge is anchored structurally: `-->` must be
#: followed immediately by `\n\n`, the blank-line separator
#: `StatementMarkdown.to_markdown()` always writes right after the header
#: (`"\n\n".join([header, ""])`) regardless of what the header itself
#: contains. `pages:` and `empty:` are digit runs (the only shape
#: `to_markdown()` ever writes for them); `model:` is bounded to
#: `_MODEL_CHARSET`.
_HEADER_RE = re.compile(
    r"\A<!--\s*source:(?P<source>.*)"
    r"\|\s*pages:\s*(?P<pages>[0-9]+)\s*"
    r"\|\s*model:\s*(?P<model>" + _MODEL_CHARSET + r"*)\s*"
    r"\|\s*empty:\s*(?P<empty>[0-9]+)\s*-->\n\n",
    re.DOTALL,
)


def extractor_model(markdown: str | None) -> str | None:
    """The `model` token from `markdown`'s own header, or `None`.

    `None` on: an empty/absent document, a document that does not begin with
    the header `to_markdown()` writes (immediately followed by its guaranteed
    blank line), or a header whose `model` field is empty. Never returns a
    token from anywhere other than the trusted, code-appended trailing
    fields — see the module docstring for why a hostile `source_file` cannot
    change that.
    """
    if not markdown:
        return None
    match = _HEADER_RE.match(markdown)
    if match is None:
        return None
    model = match.group("model").strip()
    return model or None
