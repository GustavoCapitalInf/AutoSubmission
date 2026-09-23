"""What a page shows in print, from sources other than the reviewer.

Two sources, both local (nothing leaves the process):
* the PDF's own text layer, when the page has one (a native PDF; None for a scanned page);
* the proposer's reading of the page, the layout text dots.mocr returned.

They settle two things the reviewer cannot be trusted with on its own word:
* a reviewer that contradicts itself about a row's description (its correction and its own observation
  disagree) is settled by the text layer alone, and only by the row's own printed block (the lines from its
  date to its amount, bounded by the neighbouring rows): whichever reading is printed there. The proposer's
  reading is never an arbiter for a description, because the disputed candidate came from it, and text
  printed elsewhere on the page (another row, a heading) never settles a row;
* a figure the reviewer reports (a balance, a stated total or count, a fee, a daily balance) is kept only if
  it is printed on the page, in the text layer or the proposer's reading. A figure printed nowhere is not
  evidence; it is dropped rather than allowed to contradict the arithmetic.

For measuring corroboration (vlm/confidence.py) only the text layer counts: the proposer's reading is where
the rows came from.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

# Money as printed: 1,000.00 / 1000.00, the decimal-comma forms 1.000,00 / 1000,00, and space-grouped
# decimal-comma 1 000,00 (French and Canadian statements; the space may be a no-break or thin space). A sign,
# currency symbol or brackets around it do not matter: figures are compared as magnitudes.
_SPACES = " \u00a0\u202f"
_MONEY = (
    (re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+\.\d{2}(?!\d)"), ",", "."),
    (re.compile(r"(?<![\d.,])\d+\.\d{2}(?!\d)"), "", "."),
    (re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+,\d{2}(?!\d)"), ".", ","),
    (re.compile(rf"(?<![\d.,])\d{{1,3}}(?:[{_SPACES}]\d{{3}})+,\d{{2}}(?!\d)"), _SPACES, ","),
    (re.compile(r"(?<![\d.,])\d+,\d{2}(?![\d,])"), "", ","),
)
_INTEGER = re.compile(r"(?<![\d.,])\d{1,6}(?![\d]|[.,]\d)")
_TAG = re.compile(r"<[^>]+>")
# Tokens a wrapped description may have printed between its parts: the row's own money and dates.
_SKIPPABLE = re.compile(r"^[-+(]?\$?[\d.,]+\)?-?$|^\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?$")
# How many lines a row's printed block may reach from the line of its amount (a wire transfer prints the
# beneficiary and address over several lines, with the amount on a line of its own).
_ROW_REACH = 6
# A line that begins a row: it starts with a date (03/02, 2026-03-02, Apr 29, 29 avr.).
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|janv(?:ier)?|f[ée]vr(?:ier)?|mars|avr(?:il)?|mai|juin|"
          r"juil(?:let)?|ao[uû]t|d[ée]c(?:embre)?)\.?")
_ROW_START = re.compile(rf"^(?:\d{{1,2}}[/.-]\d{{1,2}}(?:[/.-]\d{{2,4}})?(?!\S)|\d{{4}}-\d{{2}}-\d{{2}}(?!\S)|"
                        rf"{_MONTH}\s+\d{{1,2}}(?!\S)|\d{{1,2}}\s+{_MONTH}(?!\S))", re.I)


def spaced(text: str) -> str:
    """Whitespace-insensitive form: runs of whitespace become one space."""
    return " ".join(str(text).split())


def _cents(value) -> Decimal | None:
    try:
        amount = abs(Decimal(str(value))).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _amounts(text: str) -> set:
    found = set()
    for pattern, group, decimal in _MONEY:
        for token in pattern.findall(text or ""):
            normal = token
            for separator in group:
                normal = normal.replace(separator, "")
            amount = _cents(normal.replace(decimal, "."))
            if amount is not None:
                found.add(amount)
    return found


def native_page_texts(raw: bytes) -> list[str | None]:
    """Each page's own text layer, or None when a page has none (a scan, or text without letters or digits)."""
    import pypdfium2 as pdfium

    texts: list[str | None] = []
    with pdfium.PdfDocument(raw) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
            texts.append(text if re.search(r"[0-9A-Za-z]", text or "") else None)
    return texts


def layout_text(blocks) -> str:
    """The proposer's reading of a page as plain text: every block's content, table markup removed."""
    return "\n".join(html.unescape(_TAG.sub(" ", str(block.content))) for block in blocks)


@dataclass(frozen=True)
class PrintedEvidence:
    """A page's printed text from sources other than the reviewer: its text layer and the proposer's reading."""

    native: str | None
    proposer: str = ""

    @cached_property
    def _combined(self) -> str:
        return "\n".join(text for text in (self.native, self.proposer) if text)

    @cached_property
    def amounts(self) -> frozenset:
        return frozenset(_amounts(self._combined))

    @cached_property
    def native_amounts(self) -> frozenset:
        return frozenset(_amounts(self.native or ""))

    @cached_property
    def integers(self) -> frozenset:
        return frozenset(int(token) for token in _INTEGER.findall(self._combined))

    @cached_property
    def _native_spaced(self) -> str | None:
        return spaced(self.native) if self.native else None

    @cached_property
    def _native_lines(self) -> list[list[str]]:
        return [line.split() for line in (self.native or "").splitlines()]

    @cached_property
    def _line_amounts(self) -> list[set]:
        return [_amounts(" ".join(tokens)) for tokens in self._native_lines]

    def amount_printed(self, value) -> bool:
        amount = _cents(value)
        return amount is not None and amount in self.amounts

    def amount_in_text_layer(self, value) -> bool | None:
        """Whether the text layer itself prints this amount; None without a text layer."""
        if not self.native:
            return None
        amount = _cents(value)
        return amount is not None and amount in self.native_amounts

    def integer_printed(self, value) -> bool:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return False
        return number == value and number in self.integers

    def description_printed(self, description) -> bool | None:
        """Whether the text layer prints this description anywhere on the page (whitespace-insensitive,
        punctuation-sensitive), or None without a text layer. Page-wide: never used to choose a row's reading."""
        if self._native_spaced is None:
            return None
        text = spaced(description or "")
        return bool(text) and text in self._native_spaced

    def _anchors(self, amount) -> list[int]:
        target = _cents(amount)
        return [index for index, found in enumerate(self._line_amounts) if target is not None and target in found]

    @cached_property
    def _row_starts(self) -> list[bool]:
        return [bool(_ROW_START.match(" ".join(tokens))) for tokens in self._native_lines]

    def _block(self, anchor: int) -> range:
        """The printed block of the row whose amount is on line ``anchor``: back to the row's first line (the
        nearest line that begins with a date) and forward to just before the next row's first line, never
        reaching a line that prints other money, and at most _ROW_REACH lines each way."""
        amounts, starts = self._line_amounts, self._row_starts
        start = anchor
        while not starts[start] and start > max(0, anchor - _ROW_REACH) and not amounts[start - 1]:
            start -= 1
        end = anchor + 1
        while end < min(len(amounts), anchor + _ROW_REACH + 1) and not amounts[end] and not starts[end]:
            end += 1
        return range(start, end)

    def description_printed_near(self, description, amount) -> bool | None:
        """Whether the text layer prints this description as the row of its own amount: its words in order,
        contiguous except for money and date tokens (a description wrapped round the amount column), inside
        the row's printed block (_block), and either touching the amount's line or, when that line prints only
        figures and dates, directly against it. None without a text layer; False when the amount is printed on
        no line."""
        if not self.native:
            return None
        words = spaced(description or "").split()
        if not words:
            return False
        lines = self._native_lines
        for anchor in self._anchors(amount):
            stream = [(index, token) for index in self._block(anchor) for token in lines[index]]
            figures_only = all(_SKIPPABLE.match(token) for token in lines[anchor])
            for start in range(len(stream)):
                end = _match_from(stream, start, words)
                if end is None:
                    continue
                if any(stream[position][0] == anchor for position in range(start, end + 1)):
                    return True
                # Otherwise the reading lies wholly before or wholly after the amount's line. It counts only when
                # that line prints nothing but figures and dates, and nothing but those lies between the two.
                if stream[end][0] < anchor:
                    between = [token for index, token in stream[end + 1:] if index < anchor]
                else:
                    between = [token for index, token in stream[:start] if index > anchor]
                if figures_only and all(_SKIPPABLE.match(token) for token in between):
                    return True
        return False

    def description_words_near(self, description, amount) -> bool | None:
        """Looser, for measuring corroboration only (never for choosing a reading): every word of the description
        is printed in the row's printed block (_block), in any order, at least as often. None without a text
        layer; False when the amount is printed on no line."""
        if not self.native:
            return None
        wanted = Counter(spaced(description or "").split())
        if not wanted:
            return False
        lines = self._native_lines
        for anchor in self._anchors(amount):
            if not wanted - Counter(token for index in self._block(anchor) for token in lines[index]):
                return True
        return False


def _match_from(stream: list, start: int, words: list) -> int | None:
    """The position of the last token of ``words`` matched in order from ``stream[start]``, skipping only money
    and date tokens between them; None when they are not printed so."""
    if stream[start][1] != words[0]:
        return None
    position = start
    for word in words[1:]:
        position += 1
        while position < len(stream) and stream[position][1] != word and _SKIPPABLE.match(stream[position][1]):
            position += 1
        if position >= len(stream) or stream[position][1] != word:
            return None
    return position
