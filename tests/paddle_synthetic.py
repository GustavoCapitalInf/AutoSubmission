"""tests/paddle_synthetic.py — the synthetic "statement-like" fixture set
(Phase 2.1 cell P, `docs/agent-handoffs/P21-PADDLE.md` §6, D8).

NOT a real statement, and never derived from one: a header line, a DATE /
DESCRIPTION / AMOUNT / BALANCE column-header row, and N ledger rows of
obviously synthetic literals whose amounts and running balance are generated
arithmetically. Every word's position is KNOWN up front (`build_ledger_page`)
— the same ground truth drives:

* `render_native_pdf` — a native PDF with a real, PyMuPDF-readable text layer
  (for a future native/PyMuPDF evidence path);
* `render_image_pdf` — the SAME page rasterised to a PNG and re-embedded
  with no text layer (what the Paddle rung and the live proof actually OCR);
* `synthetic_paddle_result` — a PaddleOCR-3.7-`return_word_box=True`-shaped
  raw result built DIRECTLY from the known word positions, scaled into the
  raster's pixel space — no OCR engine runs to produce it, which is what
  makes the default suite's Paddle tests exact and fast.

This module is imported by `tools/paddle_vast.py measure` (D8: the tool
refuses to measure anything but a fixture built here) and by every
`tests/test_paddle_*.py` module that needs a page. It never reads
`Bank Statements/`, `tests/corpus_cache/` or any real document.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF

#: A fixed synthetic year, deliberately far from any real filing period —
#: "obviously synthetic" per the card, not a date that could be mistaken for
#: a real statement's period.
SYNTHETIC_YEAR = 2031

FONT_SIZE = 11.0
FONT_NAME = "Courier"  # a fixed-width font: char width is a simple constant
CHAR_WIDTH = FONT_SIZE * 0.6
LEFT_MARGIN = 54.0
TOP_MARGIN = 72.0
LINE_HEIGHT = 18.0
PAGE_WIDTH_PT = 612.0   # US Letter, points
PAGE_HEIGHT_PT = 792.0

COLUMN_X = {
    "date": LEFT_MARGIN,
    "description": LEFT_MARGIN + 90.0,
    "amount": LEFT_MARGIN + 330.0,
    "balance": LEFT_MARGIN + 430.0,
}

STARTING_BALANCE = 500  # a plain integer opening balance; every later figure derives arithmetically


@dataclass(frozen=True)
class SyntheticWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class SyntheticLine:
    words: tuple[SyntheticWord, ...]

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass(frozen=True)
class SyntheticPage:
    width_pt: float
    height_pt: float
    lines: tuple[SyntheticLine, ...]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


def _word(text: str, x: float, y_baseline: float) -> SyntheticWord:
    """A word box around one token, top-left origin / y-down (the same
    convention `evidence.canonical` uses): `y_baseline` is where PyMuPDF's
    `insert_text` places the glyph baseline; the box spans one font size
    upward from it. Width is `len(text) * CHAR_WIDTH` — exact for a
    fixed-width font, and this module always uses one."""
    width = max(len(text), 1) * CHAR_WIDTH
    return SyntheticWord(text=text, x0=x, y0=y_baseline - FONT_SIZE, x1=x + width, y1=y_baseline)


def build_ledger_page(n_rows: int = 8) -> SyntheticPage:
    """A synthetic bank-statement-LIKE page. Deterministic for a given
    `n_rows`: the same call always returns the same words at the same
    positions, which is what lets `synthetic_paddle_result` reproduce a
    PaddleOCR-shaped result without ever running PaddleOCR."""
    lines: list[SyntheticLine] = []
    y = TOP_MARGIN

    def add_line(tokens: list[tuple[str, float]]) -> None:
        nonlocal y
        lines.append(SyntheticLine(words=tuple(_word(text, x, y) for text, x in tokens)))
        y += LINE_HEIGHT

    add_line([("SYNTHETIC", LEFT_MARGIN), ("STATEMENT", LEFT_MARGIN + 110.0)])
    add_line([
        ("DATE", COLUMN_X["date"]), ("DESCRIPTION", COLUMN_X["description"]),
        ("AMOUNT", COLUMN_X["amount"]), ("BALANCE", COLUMN_X["balance"]),
    ])

    balance = STARTING_BALANCE
    for row in range(1, n_rows + 1):
        # A round dollar figure: `tools/privacy_scan_branch.py`'s `round_money`
        # exclusion treats every `.00`-ending MONEY token as template/tolerance
        # shape, never archive content — the deliberate way to keep an
        # arithmetically-generated synthetic figure from ever coincidentally
        # matching a real printed balance somewhere in a 3,000+ document corpus.
        amount = float(row * 10)
        balance = balance + amount
        add_line([
            (f"{SYNTHETIC_YEAR}-01-{row:02d}", COLUMN_X["date"]),
            ("SYNTHETIC", COLUMN_X["description"]),
            ("ROW", COLUMN_X["description"] + 100.0),
            (f"{row:02d}", COLUMN_X["description"] + 145.0),
            (f"{amount:.2f}", COLUMN_X["amount"]),
            (f"{balance:.2f}", COLUMN_X["balance"]),
        ])

    height = max(PAGE_HEIGHT_PT, y + TOP_MARGIN)
    return SyntheticPage(width_pt=PAGE_WIDTH_PT, height_pt=height, lines=tuple(lines))


def render_native_pdf(page: SyntheticPage) -> bytes:
    """A one-page PDF with a REAL PyMuPDF-readable text layer, every word
    drawn at its known position."""
    doc = fitz.open()
    try:
        pdf_page = doc.new_page(width=page.width_pt, height=page.height_pt)
        for line in page.lines:
            for word in line.words:
                pdf_page.insert_text((word.x0, word.y1), word.text, fontsize=FONT_SIZE, fontname=FONT_NAME)
        return doc.tobytes()
    finally:
        doc.close()


def render_image_pdf(page: SyntheticPage, *, dpi: int = 300) -> bytes:
    """The SAME page, rasterised at `dpi` and re-embedded with NO text
    layer — an image-only PDF, exactly the shape the Paddle rung and the
    live proof are handed. Never written to disk."""
    from ocr.rasterize import rasterize_pdf

    native = render_native_pdf(page)
    image = rasterize_pdf(native, dpi=dpi)[0]
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    doc = fitz.open()
    try:
        pdf_page = doc.new_page(width=page.width_pt, height=page.height_pt)
        pdf_page.insert_image(fitz.Rect(0, 0, page.width_pt, page.height_pt), stream=png_bytes)
        return doc.tobytes()
    finally:
        doc.close()


def raster_dimensions(page: SyntheticPage, *, dpi: int = 300) -> tuple[int, int]:
    """The pixel dimensions `render_image_pdf`'s raster has at `dpi` — the
    same rounding `ocr.rasterize.rasterize_pdf` (via Poppler) applies, used
    to keep `synthetic_paddle_result`'s pixel boxes consistent with what the
    rung will actually rasterize."""
    scale = dpi / 72.0
    return round(page.width_pt * scale), round(page.height_pt * scale)


def synthetic_paddle_result(page: SyntheticPage, *, dpi: int = 300) -> dict:
    """A PaddleOCR-3.7 `return_word_box=True`-shaped raw result built
    DIRECTLY from `page`'s known word positions, scaled into `dpi`'s pixel
    space. No OCR engine runs; the shape matches
    `tests/fixtures/paddle/paddle_demo_wordboxes_res.json` exactly (the same
    keys, the same per-line `text_word` / `text_word_boxes` nesting). One
    Paddle "line" per `SyntheticLine` — each row here was already drawn as
    one visual line, so there is no segmentation to simulate."""
    scale = dpi / 72.0
    text_word: list[list[str]] = []
    text_word_boxes: list[list[list[int]]] = []
    rec_texts: list[str] = []
    rec_scores: list[float] = []
    rec_boxes: list[list[int]] = []
    rec_polys: list[list[list[int]]] = []
    dt_polys: list[list[list[int]]] = []
    textline_orientation_angles: list[int] = []

    for line in page.lines:
        words = [word.text for word in line.words]
        boxes = [
            [round(word.x0 * scale), round(word.y0 * scale), round(word.x1 * scale), round(word.y1 * scale)]
            for word in line.words
        ]
        text_word.append(words)
        text_word_boxes.append(boxes)
        rec_texts.append(" ".join(words))
        rec_scores.append(1.0)
        x0 = min(box[0] for box in boxes)
        y0 = min(box[1] for box in boxes)
        x1 = max(box[2] for box in boxes)
        y1 = max(box[3] for box in boxes)
        rec_boxes.append([x0, y0, x1, y1])
        poly = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        rec_polys.append(poly)
        dt_polys.append(poly)
        textline_orientation_angles.append(-1)

    return {
        "input_path": "synthetic.png",
        "page_index": 0,
        "model_settings": {"use_doc_preprocessor": False, "use_textline_orientation": False},
        "text_type": "general",
        "return_word_box": True,
        "text_rec_score_thresh": 0.0,
        "dt_polys": dt_polys,
        "rec_polys": rec_polys,
        "rec_boxes": rec_boxes,
        "rec_texts": rec_texts,
        "rec_scores": rec_scores,
        "text_word": text_word,
        "text_word_boxes": text_word_boxes,
        "textline_orientation_angles": textline_orientation_angles,
        "text_det_params": {
            "box_thresh": 0.6, "limit_side_len": 64, "limit_type": "min",
            "max_side_limit": 4_000, "thresh": 0.3, "unclip_ratio": 1.5,
        },
    }
