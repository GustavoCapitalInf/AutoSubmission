"""Word geometry: the input the 3a spike proved was missing.

The 3a measurement said it plainly. Reach into the gate was easy and reach
THROUGH it did not move, and the dominant refusal cause was that a flattened
line does not begin with a date — a multi-column page whose reading order was
destroyed before the structurer ever saw it. Flat text cannot tell a check
number to the left of a date from a description, cannot tell a debit column
from a credit column, and cannot tell a continuation line from a new row.
Positions can tell all three.

This module turns a PDF into words with coordinates and groups them into
visual lines. It does NOT decide what any column means — that is `rows.py`,
where the decision can be tested against the document's own arithmetic.

Deliberately separate from `ocr/`: the intake ladder produces the markdown
every other path consumes, and this is an additional read of the same bytes
for one consumer. Nothing here changes what any parser sees.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

__all__ = ["DocumentGeometry", "PageGeometry", "Word", "GeoLine", "geometry_from_pdf"]


@dataclass(frozen=True)
class Word:
    """One word as printed, with its box in PDF points (origin top-left)."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


@dataclass(frozen=True)
class GeoLine:
    """Words that share a baseline, left to right.

    `text` is the line as a reader sees it, and `spans` maps each word to its
    offset in that string, so a column decision made on x-coordinates can be
    applied to the text without re-tokenising it.
    """

    page: int
    words: tuple[Word, ...]
    text: str
    spans: tuple[tuple[int, int], ...]

    @property
    def top(self) -> float:
        return min(word.y0 for word in self.words)

    def x_at(self, offset: int) -> float | None:
        """The x0 of the word containing this text offset."""
        for word, (start, end) in zip(self.words, self.spans):
            if start <= offset < end:
                return word.x0
        return None


@dataclass(frozen=True)
class PageGeometry:
    page: int
    width: float
    height: float
    lines: tuple[GeoLine, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocumentGeometry:
    """Every page's lines. Empty pages are kept so page numbers stay true."""

    pages: tuple[PageGeometry, ...]

    @property
    def lines(self) -> tuple[GeoLine, ...]:
        return tuple(line for page in self.pages for line in page.lines)

    @property
    def word_count(self) -> int:
        return sum(len(line.words) for page in self.pages for line in page.lines)


def _group_lines(page_number: int, words: list[Word]) -> tuple[GeoLine, ...]:
    """Words -> visual lines, by vertical overlap rather than exact baseline.

    The tolerance is derived from the page's own type size (median word
    height), not from a constant: a statement set in 6pt and one set in 11pt
    are the same document class, and a fixed pixel threshold would silently
    work on one and merge two rows on the other.
    """
    if not words:
        return ()
    tolerance = max(1.0, median(word.height for word in words) * 0.6)
    ordered = sorted(words, key=lambda word: (round(word.mid_y, 1), word.x0))

    lines: list[list[Word]] = []
    current: list[Word] = [ordered[0]]
    for word in ordered[1:]:
        if abs(word.mid_y - current[-1].mid_y) <= tolerance:
            current.append(word)
        else:
            lines.append(current)
            current = [word]
    lines.append(current)

    built: list[GeoLine] = []
    for row in lines:
        row.sort(key=lambda word: word.x0)
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        offset = 0
        for index, word in enumerate(row):
            if index:
                parts.append(" ")
                offset += 1
            spans.append((offset, offset + len(word.text)))
            parts.append(word.text)
            offset += len(word.text)
        built.append(GeoLine(page_number, tuple(row), "".join(parts), tuple(spans)))
    return tuple(built)


def geometry_from_pdf(pdf_bytes: bytes) -> DocumentGeometry | None:
    """Word boxes for a native-text PDF, or None when there are none to read.

    None is the honest answer for a scanned page: there are no words, only
    pixels, and inventing line boxes from an image is the visual rung's job
    (W3-5), not this one. Never raises — a structurer input that throws would
    put the crash class W3-1 just closed back into the platform.
    """
    try:
        import fitz
    except Exception:
        return None

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    pages: list[PageGeometry] = []
    try:
        for index, page in enumerate(document, start=1):
            try:
                raw = page.get_text("words")
                rect = page.rect
            except Exception:
                pages.append(PageGeometry(index, 0.0, 0.0, ()))
                continue
            words = [
                Word(str(item[4]), float(item[0]), float(item[1]), float(item[2]), float(item[3]))
                for item in raw
                if str(item[4]).strip()
            ]
            pages.append(PageGeometry(
                index, float(rect.width), float(rect.height), _group_lines(index, words)
            ))
    except Exception:
        return None
    finally:
        try:
            document.close()
        except Exception:
            pass

    geometry = DocumentGeometry(tuple(pages))
    return geometry if geometry.word_count else None
