"""tests/layout_fixtures/builders.py — page-building primitives for the
synthetic document-kind fixtures (Phase 2.2 cell C, `P22-CLASSIFY.md` §6).

Every fixture in this package is built from LITERAL strings placed at KNOWN
positions, in the exact idiom of `tests/paddle_synthetic.py` (whose rendering
helpers and layout constants are reused by import — never copied, never
taken from a real document). From one list of `SyntheticPage`s three views
are derived and all three describe the same words:

* `evidence_from_pages`  — an `evidence.canonical.ExtractionEvidence` whose
  word boxes are the known positions (a `pdf_point` frame; or a `pixel` frame
  scaled to a dpi, the shape a Paddle read would produce);
* `texts_from_pages`     — the page strings a Tesseract-only read would hand
  the classifier (DEGRADED mode: text, no boxes);
* `render_native_pdf_pages` / `render_image_pdf` — a real PDF with a
  PyMuPDF-readable text layer, or the same page rasterised with no text
  layer (an image-only PDF), for the fixtures where the file itself matters.

Dates are >= 2031 everywhere (`SYNTHETIC_YEAR` is imported, never redefined);
names, labels and figures are invented; every money figure is generated
arithmetically from small integers.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF — the same renderer tests/paddle_synthetic.py uses

from evidence.canonical import ExtractionEvidence, PageEvidence, PageFrame, WordBox, word_id
from tests.paddle_synthetic import (
    CHAR_WIDTH,
    FONT_NAME,
    FONT_SIZE,
    LINE_HEIGHT,
    PAGE_HEIGHT_PT,
    PAGE_WIDTH_PT,
    SYNTHETIC_YEAR,
    SyntheticLine,
    SyntheticPage,
    SyntheticWord,
    render_image_pdf,
    render_native_pdf,
)

__all__ = [
    "CHAR_WIDTH",
    "FONT_SIZE",
    "LINE_HEIGHT",
    "PAGE_HEIGHT_PT",
    "PAGE_WIDTH_PT",
    "SYNTHETIC_YEAR",
    "TOP_MARGIN",
    "LEFT",
    "SyntheticLine",
    "SyntheticPage",
    "SyntheticWord",
    "Tok",
    "cents",
    "evidence_from_pages",
    "line_at",
    "make_page",
    "page_from_rows",
    "pdf_magic",
    "render_image_pdf",
    "render_native_pdf",
    "render_native_pdf_pages",
    "rtok",
    "texts_from_pages",
    "tok",
]

TOP_MARGIN = 72.0
LEFT = 54.0

#: A synthetic document sha for evidence objects (64 hex chars; not a real file's hash).
FIXTURE_DOCUMENT_SHA = "F" * 64


@dataclass(frozen=True)
class Tok:
    """One token to place on a line: `text` with its LEFT edge at `x`."""

    text: str
    x: float


def tok(text: str, x: float) -> Tok:
    return Tok(text=text, x=x)


def rtok(text: str, right_x: float) -> Tok:
    """A token whose RIGHT edge sits at `right_x` (how a money column is set)."""
    return Tok(text=text, x=right_x - len(text) * CHAR_WIDTH)


def _word(text: str, x: float, y_baseline: float) -> SyntheticWord:
    """The same box arithmetic as `tests.paddle_synthetic._word` (top-left
    origin, y down; the box spans one font size above the baseline; width is
    exact for the fixed-width font every fixture uses)."""
    width = max(len(text), 1) * CHAR_WIDTH
    return SyntheticWord(text=text, x0=x, y0=y_baseline - FONT_SIZE, x1=x + width, y1=y_baseline)


def line_at(y_baseline: float, tokens: list[Tok]) -> SyntheticLine:
    ordered = sorted(tokens, key=lambda t: t.x)
    return SyntheticLine(words=tuple(_word(t.text, t.x, y_baseline) for t in ordered))


def make_page(rows: list[list[Tok]], *, width_pt: float = PAGE_WIDTH_PT, height_pt: float = PAGE_HEIGHT_PT,
              top: float = TOP_MARGIN, line_height: float = LINE_HEIGHT) -> SyntheticPage:
    """Rows of tokens, one visual line each, from `top` downward. An empty row
    is a blank line (vertical space with no words)."""
    lines: list[SyntheticLine] = []
    y = top
    for row in rows:
        if row:
            lines.append(line_at(y, row))
        y += line_height
    if y > height_pt:
        raise ValueError(f"fixture rows overflow the page: {y} > {height_pt}")
    return SyntheticPage(width_pt=width_pt, height_pt=height_pt, lines=tuple(lines))


def page_from_rows(rows: list[list[Tok]], **kw) -> SyntheticPage:
    return make_page(rows, **kw)


def texts_from_pages(pages: list[SyntheticPage]) -> tuple[str, ...]:
    """DEGRADED-mode input: one string per page, words left to right, lines
    top to bottom, single spaces — the same shape `evidence.canonical.
    page_text` derives from boxes, so the two modes see the same words."""
    return tuple(page.text for page in pages)


def evidence_from_pages(pages: list[SyntheticPage], *, extractor_id: str = "fixture-native",
                        rotation_deg: int = 0, pixel_dpi: int | None = None) -> ExtractionEvidence:
    """Canonical evidence from known positions. `pixel_dpi` builds PIXEL
    frames (boxes scaled by dpi/72 and rounded, as a rasteriser + OCR read
    would produce); otherwise `pdf_point` frames. `rotation_deg` is RECORDED
    on every frame — the boxes are given in the display frame by hand (cell
    K's display-frame reader is not on this branch)."""
    page_evidence: list[PageEvidence] = []
    for index, page in enumerate(pages):
        if pixel_dpi is None:
            frame = PageFrame.pdf_points(page_index=index, width_pt=page.width_pt, height_pt=page.height_pt,
                                         rotation_deg=rotation_deg)
            scale = 1.0
        else:
            scale = pixel_dpi / 72.0
            frame = PageFrame.pixel(
                page_index=index,
                raster_width_px=round(page.width_pt * scale), raster_height_px=round(page.height_pt * scale),
                dpi=float(pixel_dpi), pdf_width_pt=page.width_pt, pdf_height_pt=page.height_pt,
                rotation_deg=rotation_deg,
            )
        words: list[WordBox] = []
        counter = 0
        for line_ref, line in enumerate(page.lines):
            for word in line.words:
                if pixel_dpi is None:
                    box = (word.x0, word.y0, word.x1, word.y1)
                else:
                    box = (round(word.x0 * scale), round(word.y0 * scale), round(word.x1 * scale), round(word.y1 * scale))
                words.append(WordBox(
                    word_id=word_id(index, line_ref, counter), page_index=index, text=word.text,
                    x0=box[0], y0=box[1], x1=box[2], y1=box[3], line_ref=line_ref,
                ))
                counter += 1
        page_evidence.append(PageEvidence(frame=frame, words=tuple(words)))
    return ExtractionEvidence(
        document_sha256=FIXTURE_DOCUMENT_SHA, extractor_id=extractor_id, model_token="fixture",
        pages=tuple(page_evidence),
    )


def render_native_pdf_pages(pages: list[SyntheticPage], *, rotate: int = 0) -> bytes:
    """A multi-page PDF with a REAL text layer, every word at its known
    position (the one-page form is `tests.paddle_synthetic.render_native_pdf`).
    `rotate` sets each page's /Rotate entry, so PyMuPDF's display rect turns
    while the content stream stays as authored."""
    doc = fitz.open()
    try:
        for page in pages:
            pdf_page = doc.new_page(width=page.width_pt, height=page.height_pt)
            for line in page.lines:
                for word in line.words:
                    pdf_page.insert_text((word.x0, word.y1), word.text, fontsize=FONT_SIZE, fontname=FONT_NAME)
            if rotate:
                pdf_page.set_rotation(rotate)
        return doc.tobytes()
    finally:
        doc.close()


def pdf_magic() -> str:
    """The first four bytes of a PDF as the profile records magic: UPPERCASE hex."""
    return b"%PDF".hex().upper()


def cents(value: int) -> str:
    """An integer number of cents as an EN money string (`1,234.56`)."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, frac = divmod(value, 100)
    return f"{sign}{whole:,}.{frac:02d}"
