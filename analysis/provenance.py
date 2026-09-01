"""Reads the extractor-model token off a document's own OCR header. Nothing else.

`ocr/document.py::StatementMarkdown.to_markdown()` stamps every document with a
single-line header before any page content:

    <!-- source: <file> | pages: <n> | model: <model> | empty: <n> -->

That header is the platform's only record of WHICH extractor produced the text
a parser is about to read. This module answers exactly one question about
it — "what does the first line say the model was" — and answers nothing else:

* it reads ONLY the first line. A header that has moved to line two (a bug, or
  a hostile input) is not a header this reader has found, and it must never
  become one by scanning further — `analysis/parser_registry.py::SOURCE_COMMENT_RE`
  already strips this exact comment wherever it sits in the document for
  PARSING purposes (`admissible_text`); this module is a PROVENANCE reader and
  is deliberately narrower than that, because a Q3 gate keyed on "found the
  header somewhere" could be satisfied by a header a page printed as ordinary
  text, and a gate keyed on line one cannot;
* a first line that does not match the header shape answers `None`, never a
  token borrowed from elsewhere in the document. Absence refuses — the
  direction `tests/test_q3_native_only.py` depends on.

Used by `analysis/sibling_omission.py::publish_omissions` to gate the
`printed_pair_coincides_and_no_row_printed` omission class to native-pdf-text
provenance (Q3, `PHASE2_ARCHITECTURE_PLAN.md` §6 last paragraph; `OCR_LEGACY_
AUDIT.md` §5.8 step 6): that class was corroborated only on `native-pdf-text`
documents and the OCR row-loss failure mode it exists to bound has never been
measured on OCR'd input.
"""
from __future__ import annotations

import re

#: The header's shape, anchored at the very start of the string (`\A`, not
#: `^MULTILINE`): this pattern can only match line one. `.*?` (non-greedy)
#: rather than a `|`-delimited split, because `source_file` is operator/OCR
#: supplied text and is not guaranteed to be free of the pipe character; the
#: model field is bounded on the right by the literal `| empty:` that always
#: follows it in `to_markdown()`'s own template, so the field extracted is
#: exactly the text between `model:` and the next `| empty:`, whatever the
#: source/pages fields contain.
_HEADER_RE = re.compile(
    r"\A<!--\s*source:.*?\|\s*pages:.*?\|\s*model:\s*(?P<model>.*?)\s*\|\s*empty:.*?-->"
)


def extractor_model(markdown: str | None) -> str | None:
    """The `model` token from the FIRST LINE of `markdown`, or `None`.

    `None` on: an empty/absent document, a first line that is not the header
    `to_markdown()` writes, or a header whose `model` field is empty. Never
    reads a second line looking for one — a header that is not on line one
    is, for this reader, no header at all.
    """
    if not markdown:
        return None
    first_line = markdown.split("\n", 1)[0]
    match = _HEADER_RE.match(first_line)
    if match is None:
        return None
    model = match.group("model").strip()
    return model or None
