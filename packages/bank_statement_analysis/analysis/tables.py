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

W3 §LCPERIOD added two more, from the core-processor templates: reading a
summary row exactly once over a span of text (`unique_match`) and splitting a
document into the runs of its own named sections (`section_runs`). Both were
byte-identical in two parser modules.

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
from dataclasses import dataclass
from html import unescape
from itertools import takewhile
from collections.abc import Sequence
from typing import Callable, Iterable, TypeVar

__all__ = [
    "TAG_RE",
    "ROW_RE",
    "CELL_RE",
    "DatedCell",
    "compact_whitespace",
    "compact_lines",
    "unique_line",
    "clean_cell",
    "dated_cells",
    "attributed_descriptions",
    "table_rows",
    "tables_after",
    "section_between",
    "section_runs",
    "unique_match",
    "group_rows",
    "read_grid_rows",
    "glyph_damaged",
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


def compact_lines(markdown: str) -> list[str]:
    """The document as printed lines: blank lines dropped, each one compacted.

    The first thing a parser reading a flattened TEXT layer does, as opposed to
    one reading recovered `<table>` grids. Blank lines carry nothing — PDF
    flattening inserts and removes them by page — so a line-oriented reader
    that keeps them has to skip them at every decision instead.
    """
    return [compact_whitespace(line) for line in markdown.splitlines() if line.strip()]


def unique_line(lines: Iterable[str], pattern: re.Pattern[str]) -> re.Match | None:
    """The single distinct line matching `pattern`, or None when it is not one.

    A page header is reprinted on every page, so a document legitimately prints
    its account number, its period and its holder many times — always
    identically. TWO different values under one pattern is a different fact: it
    means the pattern is catching something else, or that the PDF holds more
    than one account (L-1). Returning None there makes the caller fail closed
    rather than take whichever came first.
    """
    matched = {line: match for line in lines if (match := pattern.match(line))}
    if len(matched) != 1:
        return None
    return next(iter(matched.values()))


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
    `read_grid_rows`, which is that caller).

    `starts_row` and `ends_row` are predicates, not patterns, and they are the
    caller's: the date grammar, the terminator vocabulary and the column the
    date is printed in are bank knowledge and stay in the parser. A compiled
    regex's `.match` is a valid predicate, which is how all four call sites
    pass theirs.

    What is NOT here is the rest of the row: which of a row's money cells is
    its amount and which is its running balance. That question has three
    different printed answers in the three layouts (Chase prints no balance
    column at all; RBC prints ``amount balance`` adjacent; TD Canada prints the
    Date column between them), so it is answered against the printed grid.
    `read_grid_rows` below answers it for the ONE of
    those three that a second issuer turned out to share, and takes the money
    pattern and the row labels as arguments so the bank knowledge still stays
    with the bank.
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


def single_match(region: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """The ONE printing of `pattern` inside `region`, or None when it is not one.

    Stricter than `unique_match` below, deliberately: that helper tolerates a
    reading printed twice IDENTICALLY (a page header repeats); this one refuses
    any second printing at all. A reader that treats a repeated summary term
    as a document that has been tampered with — a block pasted in from another
    statement, W3 §LILI — wants this rule, and it lives here rather than in
    that reader because `tests/test_no_parser_helper_clones.py` names a
    private enumerate-and-count of a pattern's matches a paraphrase of the
    shared helpers (SCAN-HYGIENE's guard, batch 8). Composed at train8.
    """
    found = list(pattern.finditer(region))
    if len(found) != 1:
        return None
    return found[0]


def unique_match(region: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """The single distinct reading of `pattern` inside `region`, or None.

    `unique_line` above is the same discipline over a list of LINES; this is it
    over a span of text, for the summary strips whose figures are not
    line-shaped — one issuer prints its whole strip on one line and another
    prints it as two interleaved columns.

    A row a strip prints twice, differently, is the document contradicting
    itself about its own summary, and there is no rule that says which printing
    to believe: taking the first would be picking one. Printing it twice
    IDENTICALLY is not that — a page header repeats — so the test is on the
    captured groups rather than on the number of matches.

    Shared because the second core processor's template and the third's each
    had a private copy, and `tests/test_no_parser_helper_clones.py` is what
    said so out loud (W3 §LCPERIOD L5.2).
    """
    found = list(pattern.finditer(region))
    if not found or len({match.groups() for match in found}) != 1:
        return None
    return found[0]


@dataclass(frozen=True)
class DatedCell:
    """One printed cell of a dated grid: the date that opens it, the value
    that closes it, and where in the run each of them stood.

    `described` is what the statement printed BETWEEN the two — the row's
    description on a ledger grid, and nothing at all on a daily-balance grid.
    `start` and `end` bound the whole cell, so a caller can recover what was
    printed to the LEFT of a row (the cheque serial in a `Number Date Amount`
    grid) as `run[previous.end:cell.start]`.

    `trailing` (audit B10: I05) is what the layer printed AFTER the value and
    before the next date opens — the merchant block a core-processor template
    prints below a row's amount, or the next row's lead. Only
    `attributed_descriptions` reads it, and only when its caller asks it to.
    """

    date: str
    value: str
    start: int
    end: int
    described: str
    trailing: str = ""


def dated_cells(
    run: str, *, date_pattern: re.Pattern[str], value_pattern: re.Pattern[str]
) -> list[DatedCell] | None:
    """Every cell a run prints, or None when one of its dates closes no cell.

    The operation two core-processor templates already needed four times over
    (W3 §LCPERIOD L5.2's discipline, one template further on): a printed grid
    whose flattened text layer has lost the columns is still readable, because
    **a cell opens at a date and closes at the first value printed before the
    next date opens**. That single rule reads three printings the physical
    lines cannot:

    * a description that wraps onto the lines BELOW its own amount — a greedy
      pattern would swallow the row after it;
    * several printed rows emitted on ONE physical line, which a line-anchored
      pattern silently halves;
    * a text layer that interleaves whole blocks of descriptions between a run
      of dates and the run of amounts that answers them.

    None — never a short list — when a date closes no cell: a row we could not
    read is not a row to drop, and dropping one silently is exactly how a
    ledger comes to disagree with a printed total while still looking
    complete. The callers' gates then have something to fail against.

    `date_pattern` and `value_pattern` are the CALLER's, compiled, and each
    must capture its token in group 1: the date grammar, the money grammar and
    the boundary classes that keep a token from starting inside another one
    are template knowledge and stay in the template's own module.
    """
    dates = list(date_pattern.finditer(run))
    cells: list[DatedCell] = []
    for index, found in enumerate(dates):
        stop = dates[index + 1].start() if index + 1 < len(dates) else len(run)
        after = run[found.end():stop]
        value = value_pattern.search(after)
        if value is None:
            return None
        cells.append(DatedCell(
            date=found.group(1),
            value=value.group(1),
            start=found.start(),
            end=found.end() + value.end(),
            described=after[: value.start()],
            trailing=after[value.end():],
        ))
    return cells


def _clip_at_a_token_boundary(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters, never through a token.

    A cut mid-token publishes a string the bank did not print: W3 §LCPERIOD
    L5.3 measured that class one field along, where truncation split a cheque
    serial and the remainder was still digits, so the reader published a WRONG
    number rather than a missing one. The same cut through a merchant name
    publishes a name nobody was paid.

    Where the first token is itself longer than the limit there is no boundary
    to cut at and nothing can be published: the caller's section default is a
    truthful label, and half a token is not.
    """
    if len(text) <= limit:
        return text
    boundary = text.rfind(" ", 0, limit + 1)
    return text[:boundary].rstrip() if boundary > 0 else ""


def attributed_descriptions(
    runs: Sequence[Sequence[DatedCell]], *, strip: str, limit: int,
    below: Callable[[list[str]], bool | None] | None = None,
    block_under_its_row: bool = False,
    unread: list[list[bool]] | None = None,
    unread_text: list[list[str]] | None = None,
) -> list[list[str]]:
    """What each row of a dated ledger printed for ITSELF, run by run.

    `DatedCell.described` is everything the layer printed between a row's date
    and its amount, and on the interleaving printing `dated_cells` documents
    that span is NOT all the row's own (W3 §GRAM4 G7.7, §DESCATTRIB). This
    template prints a row as a date, a label, and — indented under the label —
    a block of merchant detail; the flattened layer emits the grid and the
    detail as two streams and flushes the detail between the grid tokens, so a
    span can hold the blocks of SEVERAL rows welded together with a single
    space and no boundary between them.

    The rule this applies is a count, not a vocabulary — a merchant or lender
    list would be exactly the "read the bank's name to decide" inversion the
    platform forbids:

    * a row's own LABEL is what the layer printed on the row's own line, i.e.
      the span up to its first newline. Nothing above or below that line was
      printed to the right of this row's date, so nothing else is its label;
    * everything after that first newline is a FLUSH of merchant blocks. Each
      block belongs to a row whose date has already opened and whose detail
      the layer has not flushed yet, so the number of such rows is an UPPER
      BOUND on the number of blocks in the flush;
    * when that bound is 1 the flush is provably ONE block and it is this
      row's own, so it is published here. When it is more, the blocks are
      several rows' and the layer has erased the boundaries between them, so
      the block is published on NO row: a bare label understates a row, and a
      merchant published on the wrong posting is a wrong answer;
    * a span holding MORE THAN ONE continuation line is more than one flush
      and is indeterminate for the same reason.

    The bound over-counts and does not under-count, and both halves of that
    are measured rather than asserted. It over-counts because a row that
    printed no detail contributes no block, and because a block the layer
    flushed between two rows rather than inside a span is counted here and is
    not present — so the branch fails closed in the direction that drops text.

    **It does not under-count only because the count is carried across the
    runs of one section, which is why this takes the RUNS rather than one
    run's cells.** A section broken across a page is several runs
    (`section_runs` keeps them apart, because the furniture between them is
    not a description), and a block still outstanding when a run ends lands in
    the FIRST span of the next run. Counting per run restarts the bound at 0
    there and reads 1 on a span holding two rows’ blocks — the review
    reproduced exactly that construction. On the archive 24 of this complex’s
    29 described runs end with rows outstanding, so the boundary is the common
    case rather than the exotic one.

    Measured over the 1,090 described rows of the complex’s 21 validated
    documents (scored against the PDF word
    coordinates the flattened layer threw away): 75 rows attribute their block
    and every one of the 75 publishes exactly what the statement printed for
    that row; 34 rows are indeterminate and publish their bare label, 30 of
    which published another row’s merchant text before this rule; and no
    published description is anything but a prefix of the row’s own printing.

    `strip` and `limit` are the caller's, because the punctuation a template
    prints as column furniture is template knowledge; the whitespace collapse
    is not, since a description is what the bank printed and the layer's
    spacing is not part of it.

    **The block printed BELOW a row's amount (audit B10: I05).** Both
    templates print most rows' merchant block on the lines under the amount,
    where no span reaches, so the rule above publishes the bare label and the
    payer the statement printed is lost. A caller that passes `below` (the
    counted template's reader does, for its credit sections; so does the
    daily template's, which reads no text yet, see below) has that flush read
    by the same count: the complete lines after the amount's own line, up to
    the next row's line or the first blank line (a page break's furniture
    follows it), are a flush; when the count is 1 — this row alone has opened
    since the last flush — and `below(lines)` says the template proves the
    flush is one block, it is this row's own and is published after its
    label. Otherwise it is indeterminate and published on no row. `below` is
    template knowledge, as `strip` is: how many lines one block may wrap
    onto, and what proves a line holds one block rather than several welded
    together.

    `below` may also answer None: the template proves the flush names no
    payer at all (the daily template's teller and branch reference under a
    counter deposit), so it is published on no row and marks none, since no
    payer was lost. A rule that never answers True reads no text and marks
    every row the statement printed a block for: the daily template's reading
    while its restored text waits on the owner's G7 admission (that text
    pairs a returned credit with a debit; B10 review, round 1).

    So is `block_under_its_row` template knowledge: a template that prints
    every block directly under its own row (never flushed later) proves a
    line with NOTHING printed under it, before the next row's line, holds no
    block at all, so its rows are no longer outstanding.

    `unread`, when given, receives one flag per row, run by run: True where
    the row was outstanding at an indeterminate flush, so text the statement
    printed for it may have been dropped — the parser's 'payer text not read'
    mark (`Transaction.payer_text_unread`).

    `unread_text`, when given, receives one string per row, parallel to
    `unread` (audit round 2, R2-B07: R07): every row marked at an
    indeterminate flush, in a span or below an amount, gets that flush's
    lines joined with one space, whitespace collapsed and the template's
    furniture stripped as a description's is; every other row gets "". It is
    the text the statement printed for SOME row of that flush, never proven
    this row's, so it is no description: what the reader publishes is
    unchanged, and a caller keeps it apart (`Transaction.unread_payer_text`).
    A flush `below` proves names no payer marks no row and gives none.
    """
    published: list[list[str]] = []
    flags: list[list[bool]] = []
    flush_texts: list[list[str]] = []
    #: (run, row) of every row opened since the last flush.
    outstanding: list[tuple[int, int]] = []

    def mark(flush: list[str]) -> None:
        joined = re.sub(r"\s+", " ", " ".join(flush)).strip().strip(strip).strip()
        for run_at, row_at in outstanding:
            flags[run_at][row_at] = True
            flush_texts[run_at][row_at] = joined

    for run_index, cells in enumerate(runs):
        this_run: list[str] = []
        flags.append([False] * len(cells))
        flush_texts.append([""] * len(cells))
        for row_index, cell in enumerate(cells):
            label, _newline, flushed = cell.described.partition("\n")
            outstanding.append((run_index, row_index))
            lines = [line for line in flushed.split("\n") if line.strip()]
            if not lines:
                printed = label
            else:
                if len(outstanding) == 1 and len(lines) == 1:
                    printed = cell.described
                else:
                    printed = label
                    mark(lines)
                outstanding = []
            if below is not None:
                block = _block_below(cell.trailing, last=row_index == len(cells) - 1)
                if block and outstanding:
                    verdict = below(block)
                    if verdict is None:
                        pass  # the block names no payer: no row's payer text was lost
                    elif outstanding == [(run_index, row_index)] and verdict:
                        printed = f"{printed} {' '.join(block)}"
                    else:
                        mark(block)
                    outstanding = []
                elif block_under_its_row and "\n" in cell.trailing and not cell.trailing.strip():
                    # Nothing at all is printed between this row's line and the
                    # next row's: on a template that prints every block directly
                    # under its own row, no row of that line has a block.
                    outstanding = []
            printed = re.sub(r"\s+", " ", printed).strip(strip)
            this_run.append(_clip_at_a_token_boundary(printed, limit).strip())
        published.append(this_run)
    if unread is not None:
        unread.extend(flags)
    if unread_text is not None:
        unread_text.extend(flush_texts)
    return published


def _block_below(trailing: str, *, last: bool) -> list[str]:
    """Audit B10 (I05): the complete lines a layer printed after a row's amount,
    the amount's own line and the next row's line aside, up to the first blank
    line. `last` is the run's last row, whose trailing text runs to the end of
    the run rather than to another row's date."""
    segments = trailing.split("\n")[1:]
    if not last:
        segments = segments[:-1]
    block: list[str] = []
    for segment in segments:
        if not segment.strip():
            break
        block.append(segment.strip())
    return block


def section_runs(markdown: str, heading: re.Pattern[str]) -> dict[str, list[str]]:
    """The document split on its own section headings, `{name: [run, ...]}`.

    `heading` must capture the section's name in group 1; each run is the text
    from the end of one heading to the start of the next, whatever that next
    heading is. A section broken across a page reprints its heading, so a name
    can occur more than once and each occurrence is kept as its OWN run: the
    rows of all the runs are one section, but the runs are not concatenated,
    because everything between the last row of one and the heading of the next
    is page furniture, and a concatenation puts that furniture inside the
    description of the row the next run opens with.

    Names the caller does not read still bound the run before them, which is
    how a template's trailing blocks stop its last section.

    Shared for the same reason as `unique_match`, and lifted with it.
    """
    marks = [(m.start(), m.end(), m.group(1)) for m in heading.finditer(markdown)]
    blocks: dict[str, list[str]] = {}
    for index, (_start, end, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(markdown)
        blocks.setdefault(name, []).append(markdown[end:stop])
    return blocks


#: A word with digits welded inside it between letters — `A11ount` for
#: "Account", `4t5t060nt` for "Statement". A PDF whose embedded font carries a
#: broken character map extracts like this: the glyphs are right, the codepoints
#: they map to are not, and the substitution lands indiscriminately on letters
#: and digits alike.
_GLYPH_SUBSTITUTED_RE = re.compile(r"(?i)\b[a-z]+\d+[a-z]+\b")
#: Ordinary alphabetic vocabulary, the denominator.
_PLAIN_WORD_RE = re.compile(r"(?i)\b[a-z]{3,}\b")
#: Above this share of substituted words the text layer is not readable. The
#: surveyed populations do not come close to overlapping: 858 documents (the
#: 160 claimed RBC/CIBC, 80 unclaimed ones that must still be claimable, and a
#: 618-document stratified sample of every other issuer) top out at 0.036,
#: while the four documents with a broken CMap run 0.30 to 0.45. The threshold
#: sits an order of magnitude clear of both.
_GLYPH_DAMAGE_LIMIT = 0.15
#: Below this much vocabulary the ratio is noise rather than evidence.
_GLYPH_DAMAGE_MIN_WORDS = 20


def glyph_damaged(text: str) -> bool:
    """Is this text layer's character map broken beyond being readable?

    Detection normally fails safe on such a document, because the furniture a
    parser looks for is corrupted along with everything else. The danger is the
    document that corrupts its *body* while leaving the one string a parser
    keys on intact: these four print `ROYAL BANK OF CANADA` perfectly and then
    render seventeen thousand dollars as `17J000-00`. A gate widened for some
    other reason would claim them and publish the corrupted figures, which is
    worse than not reading them at all.

    The predicate is issuer-neutral — it reads the damage, not anyone's
    markers — but its WIRING is not platform-wide. It is an excluding marker on
    exactly three of the registry's 52 registrations (`rbc`, `rbc_french`,
    `cibc`), which are the ones W3 §RBCCIBC touched. Every other registration
    is unguarded, and a fifth over-threshold document exists:
    `Unidentified/125ead7e_Gulf Coast Bank - June 2026.pdf` at 0.261, another
    issuer's, unclaimed today and protected by nothing. Five documents in 3,493
    exceed the limit; four of them are behind this guard. Wiring it platform-
    wide is a follow-up card (W3 §RBCCIBC RC8.7), not something this cell could
    do inside its own ownership.
    """
    plain = len(_PLAIN_WORD_RE.findall(text))
    if plain < _GLYPH_DAMAGE_MIN_WORDS:
        return False
    return len(_GLYPH_SUBSTITUTED_RE.findall(text)) / plain > _GLYPH_DAMAGE_LIMIT


#: The cents group every printed amount ends with, in either locale
#: (`1,234.56` / `1 234,56`). Stripping it leaves the integer part, which is
#: what tells a price from a reference number.
_CENTS_TAIL_RE = re.compile(r"[.,]\d{2}\)?$")
_NON_DIGIT_RE = re.compile(r"\D")
#: What follows a money-shaped token that makes it the operand of a printed
#: exchange rate: the currency it is denominated in, and then the `@` mark.
#: Both are required — the code alone follows plenty of genuine cells.
_RATE_OPERAND_RE = re.compile(r"\s+[A-Z]{3}\s*@")


def _is_printed_price(token: str) -> bool:
    """False for a money-SHAPED token that the grid does not print as money.

    A printed price never carries a leading zero, so `00314.06` beside an
    amount is a reference number the description happens to end with, not a
    second money cell. `0.45` keeps its single leading zero and stays money.
    """
    body = token.strip().lstrip("(").lstrip("-").lstrip("$").strip()
    digits = _NON_DIGIT_RE.sub("", _CENTS_TAIL_RE.sub("", body))
    return not (len(digits) > 1 and digits[0] == "0")


def _grid_cells(line: str, pattern: re.Pattern[str]) -> list[re.Match]:
    """The money cells the activity grid prints on one physical line.

    Five kinds of money-shaped token are printed inside a description cell
    rather than in a money column, and each is recognised by the mark the
    statement prints beside it, never by its value:

    * the operand of `@` — the "at unit price" marker (`4 Drs @ 2.50 10.00`
      prints a rate and then the fee);
    * a percentage operand (`@ RBP+05.00%P.A`);
    * the numerator of a printed rate — `DEPOSIT NOTE FEE SELF-SERVICE 6170.0
      AT 2.25/1,000` charges $2.25 per $1,000, and the `/` is what says so;
    * the foreign-currency operand of an exchange rate — `INTERNET GLOBAL
      MONEY TRANSFER 450000.00 PKR @.005` moved 450,000 rupees, and the
      account was debited the converted figure printed in its own column. The
      mark is the same `@` as the first rule, read THROUGH the currency code
      the layout prints between the two: keying on the mark rather than on a
      list of currency codes is what keeps `403.50 SCD 09502` (a branch
      reference that happens to follow an amount) a printed cell;
    * a figure welded to whatever precedes it — `SERVICE CHARGE CAPPED MONTHLY
      FEE$16.95 RECORD-KEEPING N/A` quotes the monthly tariff and the row's own
      cell then prints it again, so reading the quote as a cell booked the fee
      twice. The mark is the missing gap: a printed cell starts a column, so
      anything non-whitespace immediately in front of a figure means the figure
      is inside the description's sentence. This is deliberately broader than
      the shape that motivated it — see the comment at the check for exactly
      what else it refuses and how it fails when it is wrong;
    * a reference number, which a printed price never resembles because a
      price carries no leading zero.
    """
    cells = []
    for match in pattern.finditer(line):
        if not _is_printed_price(match.group(0)):
            continue
        after = line[match.end():]
        if after[:1] == "%":
            continue
        if after[:1] == "/":
            continue
        if _RATE_OPERAND_RE.match(after):
            continue
        # A printed cell starts a column, so it is preceded by whitespace or by
        # nothing. This rejects EVERY non-whitespace predecessor, not only a
        # welded currency symbol: `(16.95`, `*16.95`, `:16.95` and `x16.95` are
        # all refused, and only a `$` welded to the figure is taken off first,
        # because that symbol belongs to the figure. (A leading `-` never
        # reaches here — the money patterns match it as part of the token, so
        # its predecessor is the space in front of the minus.)
        #
        # Being broader than the shape it was written for is a real cost, and
        # the failure mode is worth naming: suppressing a cell leaves its row
        # one cell short, so the NEXT cell — the running balance — is read as
        # the row's amount. `Item (100.00) 900.00` publishes amount 900.00 with
        # no balance instead of 100.00 with balance 900.00. That is wrong but
        # not silent: the balance chain then fails and the platform's coverage
        # and ledger checks withhold the document. Measured blast radius over
        # the surveyed populations is 9 tokens in 9 documents, all of them the
        # quoted tariff this rule exists for.
        attached = line[:match.start()]
        if attached.endswith("$"):
            attached = attached[:-1]
        if attached and not attached[-1].isspace():
            continue
        # The `@` may be separated from the figure by its symbol AND a space
        # (`4 Drs @ $ 5.00`), so that check reads the trimmed text.
        before = line[:match.start()].rstrip()
        if before.endswith("$"):
            before = before[:-1].rstrip()
        if before.endswith("@"):
            continue
        cells.append(match)
    return cells


def read_grid_rows(entries, *, pattern, to_amount, opening_label, closing_label):
    """Rows read off the printed grid rather than off the physical lines.

    `entries` is the activity section as `(text, date, opens_a_date_group)`,
    with the Date column already consumed by the caller. Returns the rows and
    the balance the table's own opening row prints.

    Two structural rules do all the work, and both come from the printed
    column order `... | Cheques & Debits | Deposits & Credits | Balance`:

    1. **A lone money cell is an amount; two money cells with nothing between
       them are one row's amount and its running balance.** Balance is the
       last column and is never printed without an amount beside it, so the
       pairing is decided by adjacency in the grid, not by which token comes
       last on a line. This is what makes a row carrying TWO money cells
       readable at all, and it is deliberately blind to the values: a balance
       smaller than its own amount is still the balance.

       The Balance column is also the ONLY column that prints a sign: the two
       activity columns print magnitudes and the column heading supplies the
       direction. So a bare minus standing between a row's amount and the cell
       that follows it is that balance going overdrawn (`194.82 - 192.33`),
       and it is read as one here rather than in the money pattern — which
       cannot tell it from the hyphen a merchant name ends with
       (`... LITTLE KABUL - 180.59`, where 180.59 is a withdrawal). Reading
       the sign where the column is known is what separates the two.
    2. **A row ends at its amount cell**, so text that follows one begins the
       next row. That reads a compressed line (several printed rows emitted on
       one physical line) and a wrapped row (one printed row spread over
       several physical lines) with the same rule, and it needs no whitelist
       of description wordings.

    The one line-level fact that survives: an amount printed alone on its line
    is vertically centred between two description lines, so a following
    description-only line continues THAT row instead of opening a new one.

    Rule 1 — where a row starts — is `group_rows` (W3 §GROUPER): a printed
    posting date opens a row here, and so does the table's own opening balance
    row, which prints no date. The entries a page footer or a header block
    would contribute never reach this function; the caller drops them.

    `opening_label` is one printed wording or several. A layout that continues
    its table across a page break re-prints the running balance under a second
    label (`Balance forward`), and that row is the same thing as the opening
    row: a balance, printed with no amount beside it, that is not a
    transaction. Both are matched here so neither becomes one.

    Promoted out of `analysis/rbc.py` (W3 §RBCCIBC) when a second issuer — CIBC
    — turned out to print the same grid. It is shared rather than copied: the
    money pattern, the amount conversion and the row labels are all arguments,
    so what moved is the reading of the grid and not either bank's knowledge of
    its own furniture.
    """
    entries = list(entries)
    rows: list[dict] = []
    opening: float | None = None
    description: list[str] = []
    #: the row the most recent cell closed, while it can still take a balance
    open_row: dict | None = None
    centred_amount = False
    # Case-insensitive matching, not `.upper()` plus an index: upper-casing can
    # change a string's length, and these two labels are used to CUT a line.
    labels = (opening_label,) if isinstance(opening_label, str) else tuple(opening_label)
    opens = re.compile("|".join(re.escape(label) for label in labels), re.IGNORECASE)
    closes = re.compile(re.escape(closing_label), re.IGNORECASE)

    def starts_row(entry) -> bool:
        text, _, opens_group = entry
        return bool(opens_group) or bool(opens.match(text))

    groups = group_rows(entries, starts_row=starts_row)
    #: Whatever the table prints above its first row start already stands
    #: inside that row: unlike a section heading in a Chase block, there is no
    #: furniture here for the caller to have left behind.
    head = list(takewhile(lambda entry: not starts_row(entry), entries))
    if head:
        groups.insert(0, head)

    stopped = False
    for group in groups:
        # A new posting date closes whatever was pending: a description
        # with no amount cell under it never became a row.
        description = []
        open_row = None
        centred_amount = False
        for text, tx_date, _ in group:
            if not text:
                continue
            stop = closes.search(text)
            if stop:
                text = text[:stop.start()].strip()
                if not text:
                    stopped = True
                    break
            cells = _grid_cells(text, pattern)
            label = opens.match(text)
            if label:
                # The table's own opening row prints ONE cell, in the Balance
                # column, and everything after it belongs to the rows that
                # follow. Consuming the whole physical line here discarded
                # them: this layout family compresses the column header, the
                # opening row and the first posting onto one line, so what was
                # thrown away was a real transaction. Take the label's own
                # cell, then let the remainder be read as grid content.
                description, open_row, centred_amount = [], None, False
                if not cells:
                    continue
                gap = text[label.end():cells[0].start()].strip()
                opening = to_amount(cells[0].group(0))
                if gap == "-":
                    opening = -opening
                text = text[cells[0].end():]
                cells = _grid_cells(text, pattern)
                if not text.strip():
                    continue
            if not cells:
                if open_row is not None and centred_amount:
                    open_row["description"] = f"{open_row['description']} {text}".strip()
                else:
                    description.append(text)
                centred_amount = False
                continue

            cells_only = (
                not text[:cells[0].start()].strip()
                and not text[cells[-1].end():].strip()
                and all(not text[a.end():b.start()].strip() for a, b in zip(cells, cells[1:]))
            )
            position = 0
            for match in cells:
                gap = text[position:match.start()].strip()
                # A bare minus between a row's amount and the next cell is the
                # sign of the balance that cell carries (rule 1). Anything else
                # standing between two cells is description, and it closes the
                # open row exactly as before.
                signed_balance = (
                    gap == "-"
                    and open_row is not None
                    and open_row["balance"] is None
                )
                if gap and not signed_balance:
                    description.append(gap)
                    open_row = None
                value = to_amount(match.group(0))
                if open_row is not None and open_row["balance"] is None:
                    open_row["balance"] = -value if signed_balance else value
                    open_row = None
                else:
                    row = {
                        "date": tx_date,
                        "description": " ".join(description).strip(),
                        "abs_amount": abs(value),
                        "amount": -abs(value),
                        "balance": None,
                    }
                    description = []
                    rows.append(row)
                    open_row = row
                position = match.end()
            tail = text[position:].strip()
            if tail:
                description.append(tail)
                open_row = None
            centred_amount = cells_only
        if stopped:
            break

    return rows, opening
