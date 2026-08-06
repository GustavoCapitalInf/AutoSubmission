"""Shared HTML-table and section-chunking utilities (R-2 shared utilities).

The OCR ladder hands parsers a markdown document that mixes flattened plain
text with `<table>` fragments where the extractor recovered a grid. Almost
every parser therefore needs the same four operations, and before R-2 each kept
its own copy of them:

* collapse runs of whitespace (7 identical `_compact` clones)
* strip tags and unescape entities from a table cell (4 identical `_clean`
  clones, plus 12 copies of the three regexes they share)
* turn a `<table>` fragment into a list of cell rows (4 identical `_rows`)
* find the table(s) that follow a section heading (3 near-identical
  `_tables_after`, differing only in how the bank spells "continued")
* cut the text between two heading patterns (4 identical `_section`)

These are text-shape utilities, not bank knowledge: the headings, the
"continued" spelling and the section boundaries stay in each parser, as
arguments. Parsers whose version of one of these carries extra
document-specific scrubbing (first_community, community_section, banco_popular,
first_citizens) keep their own — folding their special cases in here would move
bank knowledge into shared code, which is exactly what R-2 is meant to stop.
"""
from __future__ import annotations

import re
from html import unescape

__all__ = [
    "TAG_RE",
    "ROW_RE",
    "CELL_RE",
    "compact_whitespace",
    "clean_cell",
    "table_rows",
    "tables_after",
    "section_between",
]

#: Any HTML tag. Used to reduce a cell to its text.
TAG_RE = re.compile(r"<[^>]+>")
#: A table row, capturing its inner HTML.
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
#: A table cell, capturing its inner HTML. Tolerates attributes (colspan).
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)


def compact_whitespace(text: str) -> str:
    """Collapse every run of whitespace to a single space and trim.

    PDF flattening scatters newlines and runs of spaces through what was one
    printed line; nearly every row regex in the parsers assumes this has been
    applied first.
    """
    return re.sub(r"\s+", " ", text).strip()


def clean_cell(value: str) -> str:
    """Table cell HTML -> plain text: tags removed, entities decoded,
    whitespace compacted."""
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub("", value))).strip()


def table_rows(table: str) -> list[list[str]]:
    """A `<table>` fragment -> rows of cleaned cell text.

    Rows with no `<td>` (header rows using `<th>`, spacer rows) come back as
    empty lists rather than being dropped, so a caller indexing rows
    positionally sees the same shape the source had.
    """
    return [[clean_cell(cell) for cell in CELL_RE.findall(row)] for row in ROW_RE.findall(table)]


def tables_after(markdown: str, heading: str, *, continued: str = "") -> list[str]:
    """Every `<table>` fragment that follows an occurrence of `heading`.

    `heading` is matched literally as a whole line. `continued` is an optional
    regex fragment for the suffix a bank appends when a section spans pages
    (`" - continued"`, `" \\(continued\\)"`); banks that never do this pass
    nothing. Sections that break across several tables yield several
    fragments, in document order.
    """
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(heading)}{continued}\s*$.*?(<table>.*?</table>)",
        re.IGNORECASE | re.DOTALL,
    )
    return [m.group(1) for m in pattern.finditer(markdown)]


def section_between(markdown: str, start: str, end: str) -> str:
    """The text between the first match of `start` and the next `end`.

    `start` and `end` are regex fragments, not literals — callers pass real
    patterns (alternations, anchors) — and the search is case-insensitive and
    spans newlines. Returns `""` when the section is absent, which callers
    treat as "this statement has no such section" rather than as an error.
    """
    m = re.search(start + r"(?P<body>.*?)" + end, markdown, re.IGNORECASE | re.DOTALL)
    return m.group("body") if m else ""
