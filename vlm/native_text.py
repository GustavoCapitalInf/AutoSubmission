"""What a page shows in print, from sources other than the reviewer.

Two sources, both local (nothing leaves the process):
* the PDF's own text layer, when the page has one (a native PDF; None for a scanned page);
* the proposer's reading of the page, the layout text dots.mocr returned.

They settle two things the reviewer cannot be trusted with on its own word:
* a reviewer that contradicts itself about a row's description (its correction and its own observation
  disagree) is settled by the text layer alone: whichever reading is printed there. The proposer's reading is
  never an arbiter for a description, because the disputed candidate came from it;
* a figure the reviewer reports (a balance, a stated total or count, a fee, a daily balance) is kept only if
  it is printed on the page, in the text layer or the proposer's reading. A figure printed nowhere is not
  evidence; it is dropped rather than allowed to contradict the arithmetic.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

# Money as printed: 1,000.00 / 1000.00, and the decimal-comma forms 1.000,00 / 1000,00. A sign, currency
# symbol or brackets around it do not matter: figures are compared as magnitudes.
_MONEY = (
    (re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+\.\d{2}(?!\d)"), ",", "."),
    (re.compile(r"(?<![\d.,])\d+\.\d{2}(?!\d)"), "", "."),
    (re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+,\d{2}(?!\d)"), ".", ","),
    (re.compile(r"(?<![\d.,])\d+,\d{2}(?![\d,])"), "", ","),
)
_INTEGER = re.compile(r"(?<![\d.,])\d{1,6}(?![\d]|[.,]\d)")
_TAG = re.compile(r"<[^>]+>")


def spaced(text: str) -> str:
    """Whitespace-insensitive form: runs of whitespace become one space."""
    return " ".join(str(text).split())


def _cents(value) -> Decimal | None:
    try:
        amount = abs(Decimal(str(value))).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


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
        found = set()
        for pattern, group, decimal in _MONEY:
            for token in pattern.findall(self._combined):
                normal = token.replace(group, "") if group else token
                amount = _cents(normal.replace(decimal, "."))
                if amount is not None:
                    found.add(amount)
        return frozenset(found)

    @cached_property
    def integers(self) -> frozenset:
        return frozenset(int(token) for token in _INTEGER.findall(self._combined))

    @cached_property
    def _native_spaced(self) -> str | None:
        return spaced(self.native) if self.native else None

    def amount_printed(self, value) -> bool:
        amount = _cents(value)
        return amount is not None and amount in self.amounts

    def integer_printed(self, value) -> bool:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return False
        return number == value and number in self.integers

    @cached_property
    def _native_words(self) -> Counter | None:
        return Counter(self.native.split()) if self.native else None

    def description_words_printed(self, description) -> bool | None:
        """Looser than description_printed, for measuring corroboration only (never for choosing a reading):
        every word of the description is printed on the page's text layer, at least as often. A text layer
        can read columns and wrapped lines in another order than the visual reading assembles them, so word
        order is not required. None without a text layer."""
        words = self._native_words
        if words is None:
            return None
        wanted = Counter(spaced(description or "").split())
        return bool(wanted) and not wanted - words

    def description_printed(self, description) -> bool | None:
        """Whether the text layer prints this description (whitespace-insensitive, punctuation-sensitive), or None
        when the page has no text layer: then there is nothing to settle a description with."""
        if self._native_spaced is None:
            return None
        text = spaced(description or "")
        return bool(text) and text in self._native_spaced
