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
from itertools import takewhile
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
    Date column between them), so it is answered against the printed grid — see
    W3_TRACKA_LOG §GROUPER. `read_grid_rows` below answers it for the ONE of
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

    So admissibility is asserted rather than assumed, and it is asserted on the
    damage itself rather than on any particular parser's markers: a statement
    whose own words have digits substituted into them is not a statement this
    platform can read, whoever printed it.
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
    * a tariff quoted inside the description — `SERVICE CHARGE CAPPED MONTHLY
      FEE$16.95 RECORD-KEEPING N/A` names the monthly fee and then the row's
      own cell prints it again. The mark is the missing gap: a printed cell
      stands in a column, so a currency symbol welded to the word before it is
      part of the sentence, not the start of a column. Reading it as a cell
      booked the fee twice;
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
        # What the token is welded to on its left, taking off only a symbol
        # that is itself welded: the symbol belongs to the figure, whatever
        # else does not. A gap here means a column started; no gap means the
        # figure is a word inside the description's own sentence.
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
