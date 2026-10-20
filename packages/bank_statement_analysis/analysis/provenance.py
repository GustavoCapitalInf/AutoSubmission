"""Reads the extractor-model token off a document's own OCR header. Nothing else.

`ocr/document.py::StatementMarkdown.to_markdown()` stamps every document with a
header before any page content:

    <!-- source: <file> | pages: <n> | model: <model> | empty: <n> -->\\n\\n...

That header is the platform's only record of WHICH extractor produced the text
a parser is about to read.

MINOR-9 (`PHASE2_P20SURFACES_REVIEW.md` re-review, closure `2cb4c0e`): an
earlier version of this docstring claimed "a claim that starts anywhere else —
including ... a header a PAGE printed as ordinary text — is not found." That
was false, and BLOCK-1R measured it: a right-anchored, DOTALL match has no
bound on how far right it may look, so a `| pages: N | model: T | empty: N
-->` run printed in the PAGE BODY — after the genuine header fields, where
`to_markdown()` itself supplies the blank line the run needs
(`"\\n\\n"` between page blocks) — matched, and WON, because it sat closer to
the true end of the string than the genuine run. This paragraph states only
what the CURRENT reader guarantees, measured, not asserted:

**THE PROPERTY, EXACTLY.** `extractor_model` returns a token if and only if
the document (a) begins with `<!-- source:`, (b) has a blank line immediately
after its first physical line (`\\n\\n`, or `\\r\\n\\r\\n` for a CRLF
document — MINOR-8; `to_markdown()` always writes one), and (c) contains
EXACTLY ONE well-formed `| pages: N | model: TOKEN | empty: N -->` run
ANYWHERE in the document, and that one run's `-->` is the thing that
terminates physical line one. Any other shape — no header, no blank line,
ZERO such runs, or MORE THAN ONE (wherever the extra one sits — before the
genuine fields in a hostile filename, as `source_file`-injection findings
before this one already forced this reader to survive, or after them in the
page body, as BLOCK-1R forced) — returns `None`.

**WHY AMBIGUITY REFUSES RATHER THAN PICKS A WINNER.** BLOCK-1R's own
adversarial review prototyped and measured the alternative — bound the header
region on the LEFT instead of the right (`markdown.partition("\\n\\n")[0]`,
right-anchored) — and found it trades one hole for another: it closes the
body-run vector, but a `source_file` containing an embedded `\\n\\n` then
makes physical line one itself a complete, well-formed, ATTACKER-CHOSEN
header that no reader can distinguish from the genuine one. There is no
"pick the correct run" rule that is safe against a run before the genuine
fields AND a run after them at the same time, because "correct" depends on
knowing which one the trusted code appended — which is exactly the fact an
attacker who can print either one is trying to hide. So this reader does not
choose: zero runs and more than one run are both `None`, the same answer
`analysis/sibling_omission.py` already gives "absence" (`SiblingOmission`'s
own docstring) and the same direction S4 already reads ambiguity in
(Q2: "ambiguity refuses the aggregation, never the account"). A hostile
filename that also happens to sit on a genuinely native document is REFUSED
here, not rescued — `tests/test_q3_native_only.py::
test_a_hostile_source_file_still_reports_the_true_model_when_it_is_native`
is the pinned proof of that direction, by name.

**WHY THIS IS STILL "READ THE HEADER, NOT THE PAGE" IN SUBSTANCE.** A genuine
document — one whose `source_file` and page text were never crafted to plant
a second field run — has EXACTLY ONE such run by construction (the one
`to_markdown()` appends), and it always terminates physical line one, so this
reader answers every genuine document exactly as a naive "read line one"
reader would. The difference is what happens on a document that is NOT
genuine: rather than trusting whichever run happens to be found first, last,
or nearest an anchor, a second run anywhere is proof the document is not
trustworthy on this question, and the reader says so by refusing rather than
guessing.

The `model` field is bounded to a closed charset — `[A-Za-z0-9._/+-]`, the
same one `ocr/config.py`'s token validation uses (P20-SEAM) — so no run of
`|`, `<`, `>` or whitespace inside a forged field can be mistaken for part of
the model token even if it somehow survived to sit in that position.

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

#: One well-formed field run, found ANYWHERE in the document — deliberately
#: not anchored at all, because ambiguity detection needs to find every
#: candidate, not just the first or the last. `pages:` and `empty:` are digit
#: runs (the only shape `to_markdown()` ever writes for them); `model:` is
#: bounded to `_MODEL_CHARSET`.
_FIELD_RUN_RE = re.compile(
    r"\|\s*pages:\s*[0-9]+\s*"
    r"\|\s*model:\s*(?P<model>" + _MODEL_CHARSET + r"*)\s*"
    r"\|\s*empty:\s*[0-9]+\s*-->"
)


def extractor_model(markdown: str | None) -> str | None:
    """The `model` token from `markdown`'s own header, or `None`.

    See the module docstring ("THE PROPERTY, EXACTLY") for the precise
    condition. In short: exactly one well-formed field run in the whole
    document, terminating physical line one, preceded by `<!-- source:` and
    followed by the mandatory blank line — anything else, including zero runs
    or more than one, is `None`. Absence and ambiguity both refuse.
    """
    if not markdown or not markdown.startswith("<!-- source:"):
        return None
    first_line, newline, rest = markdown.partition("\n")
    if not newline or not rest.startswith(("\n", "\r\n")):
        return None
    # `first_line` (from a plain `\n` partition) still carries a trailing `\r`
    # on a CRLF document — MINOR-8 — so the position physical line one's
    # CONTENT ends at is one character short of `len(first_line)` there.
    line_end = len(first_line) - 1 if first_line.endswith("\r") else len(first_line)
    runs = list(_FIELD_RUN_RE.finditer(markdown))
    if len(runs) != 1 or runs[0].end() != line_end:
        return None
    model = runs[0].group("model").strip()
    return model or None
