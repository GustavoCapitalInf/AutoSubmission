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

W3 Track A added a fifth, from the other half of the ladder: when the extractor
recovers no grid at all and the parser is reading a flattened text layer, the
printed rows have to be recovered from the physical lines. `group_rows` is that
operation (see its docstring for the promotion history).

These are text-shape utilities, not bank knowledge: the headings, the
"continued" spelling, the section boundaries and the date/terminator grammars
stay in each parser, as arguments. Parsers whose version of one of these carries
extra document-specific scrubbing (first_community, community_section,
banco_popular, first_citizens) keep their own — folding their special cases in
here would move bank knowledge into shared code, which is exactly what R-2 is
meant to stop.
"""
from __future__ import annotations

import re
from html import unescape
from typing import Callable, Iterable, TypeVar

__all__ = [
    "TAG_RE",
    "ROW_RE",
    "CELL_RE",
    "compact_whitespace",
    "clean_cell",
    "table_rows",
    "tables_after",
    "section_between",
    "group_rows",
]

_Item = TypeVar("_Item")

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


def group_rows(
    items: Iterable[_Item],
    *,
    starts_row: Callable[[_Item], object],
    ends_row: Callable[[_Item], object] | None = None,
) -> list[list[_Item]]:
    """Group a printed line stream into the rows the statement prints.

    A flattened text layer has no grid: one printed row can arrive as several
    physical lines (the description wrapped, or the amount cell wrapped under
    it), and a page break can cut a row in half. Recovering the rows is the
    same operation in every layout that prints a dated ledger, and W3 Track A
    proved it three times over — `chase.py`, `td_can.py` and `rbc.py` each
    arrived at it independently:

    1. **a row starts where the grid starts one** — `starts_row(item)`, which
       is a date-shaped token in the statement's own Date column (Chase's
       leading ``MM/DD``, RBC's leading ``DD Mon``, TD Canada's ``MonDD``
       between the amount and balance columns), or the check number in a
       CHECK NO. column;
    2. **every other line continues the row it is inside** — this is what
       makes a wrapped description, a wrapped amount cell and a page-split
       row read correctly, and it is what replaced the closed whitelist of
       description wordings that caused the 217-document
       `chase x detail_coverage` withheld cell;
    3. **`ends_row(item)` closes the open row and starts nothing** — the
       printed section total and the headings of whatever follows the section
       inside the same block are grid furniture, not rows.

    Items before the first row start, and items after an `ends_row` line,
    belong to no row and are not returned: a parser must not publish a row the
    grid never opened. That is a Chase-shaped section, where anything above the
    first row is a heading or a column header. A caller whose first printed
    line already stands inside the table's first row — RBC's activity table,
    which opens with an undated `Opening balance` row — restores that leading
    run itself rather than have this function guess which case it is in (see
    `rbc._read_grid_rows`).

    `starts_row` and `ends_row` are predicates, not patterns, and they are the
    caller's: the date grammar, the terminator vocabulary and the column the
    date is printed in are bank knowledge and stay in the parser. A compiled
    regex's `.match` is a valid predicate, which is how all four call sites
    pass theirs.

    What is deliberately NOT here is the rest of the row: which of a row's
    money cells is its amount and which is its running balance. That question
    has three different printed answers in the three layouts (Chase prints no
    balance column at all; RBC prints ``amount balance`` adjacent; TD Canada
    prints the Date column between them), so it is answered by each parser
    against its own printed grid — see W3_TRACKA_LOG §GROUPER.
    """
    rows: list[list[_Item]] = []
    current: list[_Item] | None = None
    for item in items:
        if starts_row(item):
            if current:
                rows.append(current)
            current = [item]
        elif ends_row is not None and ends_row(item):
            if current:
                rows.append(current)
            current = None
        elif current is not None:
            current.append(item)
    if current:
        rows.append(current)
    return rows


def section_between(markdown: str, start: str, end: str) -> str:
    """The text between the first match of `start` and the next `end`.

    `start` and `end` are regex fragments, not literals — callers pass real
    patterns (alternations, anchors) — and the search is case-insensitive and
    spans newlines. Returns `""` when the section is absent, which callers
    treat as "this statement has no such section" rather than as an error.
    """
    m = re.search(start + r"(?P<body>.*?)" + end, markdown, re.IGNORECASE | re.DOTALL)
    return m.group("body") if m else ""
