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

Phase 2.3 cell E (`docs/agent-handoffs/P23-EGATE.md` item 4) APPENDS the
DEFECT pages: one page per extraction-quality metric, each built from the
same literal ground truth by transforming `build_ledger_page`'s output, so
the defect is the ONLY difference between the page and a clean one. Every
one of them is still a page of obviously synthetic literals — the
substitution page's glyphs, the noise page's tokens and the garbage page's
long runs are generated from fixed alphabets in this file, never sampled
from anything. See `tests/test_extraction_quality.py` for the page -> metric
-> class table each of them proves.
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
        # No "input_path": the real worker's contract pops it before
        # returning (§1: "verbatim, minus input_path") — MINOR-9's fix
        # applies here too, since this generator stands in for a raw result.
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


# ---------------------------------------------------------------------------
# Phase 2.3 cell E — the DEFECT pages (P23-EGATE item 4)
#
# One page per extraction-quality metric. Every one is a TRANSFORM of
# `build_ledger_page`'s clean output (or a page built from the same literal
# alphabets), so the only difference between a defect page and the clean page
# is the defect itself — which is what makes "this metric moved and no other
# class fired" a statement about the metric rather than about two unrelated
# fixtures. Nothing here reads a document, a corpus or a cache.
# ---------------------------------------------------------------------------

#: The digit -> look-alike glyph pairs an OCR engine confuses on a low-quality
#: scan, applied by `substitute_digit_glyphs`. Deliberately the two the card
#: names (`O`/`0`, `l`/`1`) and no others.
GLYPH_SUBSTITUTIONS: tuple[tuple[str, str], ...] = (("0", "O"), ("1", "l"))

#: A vowel-free letter alphabet for `build_noise_page`'s tokens: no word of
#: any `layout.signals` lexicon can be spelled from it (every lexicon entry of
#: three letters or more carries a vowel), so the page's lexicon rate is zero
#: BY CONSTRUCTION rather than by luck.
NOISE_ALPHABET = "qxzvwkjfhb"

#: The word `build_garbage_token_page` / `build_repeated_letter_page` grow
#: their defect tokens from — the fixture's own header literal, never a word
#: read off anything.
DEFECT_STEM = "SYNTHETIC"


def build_blank_page(*, width_pt: float = PAGE_WIDTH_PT, height_pt: float = PAGE_HEIGHT_PT) -> SyntheticPage:
    """A page with NO words at all — the E0 fixture. Rendered, it is a blank
    sheet; as evidence, it is an extractor that returned nothing."""
    return SyntheticPage(width_pt=width_pt, height_pt=height_pt, lines=())


def keep_first_lines(page: SyntheticPage, count: int) -> SyntheticPage:
    """The same page with only its first `count` lines — the EVIDENCE half of
    the partly-covered fixture. The page is rendered whole and the evidence
    describes the top of it, which is what an extractor that missed regions
    produces. Deliberately a small fraction rather than a half: a mutant that
    measures the ink INSIDE the boxes instead of outside them must not land on
    the same number (P23-EGATE M4)."""
    if count < 0:
        raise ValueError("count must be >= 0")
    return SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines[:count])


def rotate_page_90(page: SyntheticPage) -> SyntheticPage:
    """The same words, rotated a quarter turn CLOCKWISE into a page whose
    width and height are swapped: `(x, y) -> (height - y, x)`.

    The text is untouched, so every recognition metric reads exactly what the
    clean page reads and the ONLY thing that moved is geometry — a page whose
    words run down the sheet while its frame says they run across it."""
    height = page.height_pt
    lines = tuple(
        SyntheticLine(words=tuple(
            SyntheticWord(text=word.text, x0=height - word.y1, y0=word.x0,
                          x1=height - word.y0, y1=word.x1)
            for word in line.words
        ))
        for line in page.lines
    )
    return SyntheticPage(width_pt=page.height_pt, height_pt=page.width_pt, lines=lines)


def substitute_digit_glyphs(page: SyntheticPage) -> SyntheticPage:
    """Every `0` becomes `O` and every `1` becomes `l`, in every word, with
    the boxes untouched (the substituted glyphs occupy the same cells in a
    fixed-width font). The page still LOOKS like a ledger and no money token
    on it parses any more."""
    def substituted(text: str) -> str:
        for digit, glyph in GLYPH_SUBSTITUTIONS:
            text = text.replace(digit, glyph)
        return text

    lines = tuple(
        SyntheticLine(words=tuple(
            SyntheticWord(text=substituted(word.text), x0=word.x0, y0=word.y0, x1=word.x1, y1=word.y1)
            for word in line.words
        ))
        for line in page.lines
    )
    return SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=lines)


def _noise_token(line_index: int, word_index: int, length: int = 5) -> str:
    alphabet = NOISE_ALPHABET
    return "".join(
        alphabet[(line_index * 7 + word_index * 3 + position) % len(alphabet)]
        for position in range(length)
    )


def build_noise_page(*, n_lines: int = 12, words_per_line: int = 6) -> SyntheticPage:
    """A page of well-formed, evenly-spaced, correctly-boxed tokens that are
    not words in any of the three languages and carry no money and no digits:
    the recognition-quality fixture whose LEXICON rate is what moves. Line
    heights are uniform and columns are aligned, so no box-regularity metric
    moves with it."""
    lines: list[SyntheticLine] = []
    y = TOP_MARGIN
    for line_index in range(n_lines):
        words = tuple(
            _word(_noise_token(line_index, word_index), LEFT_MARGIN + word_index * 80.0, y)
            for word_index in range(words_per_line)
        )
        lines.append(SyntheticLine(words=words))
        y += LINE_HEIGHT
    height = max(PAGE_HEIGHT_PT, y + TOP_MARGIN)
    return SyntheticPage(width_pt=PAGE_WIDTH_PT, height_pt=height, lines=tuple(lines))


def _defect_lines(page: SyntheticPage, tokens: list[str]) -> SyntheticPage:
    """`page` with one extra line per token, appended below its last line."""
    y = TOP_MARGIN + len(page.lines) * LINE_HEIGHT
    extra: list[SyntheticLine] = []
    for token in tokens:
        extra.append(SyntheticLine(words=(_word(token, LEFT_MARGIN, y),)))
        y += LINE_HEIGHT
    height = max(page.height_pt, y + TOP_MARGIN)
    return SyntheticPage(width_pt=page.width_pt, height_pt=height, lines=page.lines + tuple(extra))


def build_garbage_token_page(*, n_rows: int = 20, tokens: int = 12, token_chars: int = 30) -> SyntheticPage:
    """The clean ledger plus `tokens` over-long tokens (`token_chars` > the
    gate's 20-character bound), each on its own line. The letters CYCLE
    through the alphabet so no over-long token also carries a repeated-letter
    run: this fixture moves the LENGTH half of the garbage rule and nothing
    else."""
    if token_chars <= 20:
        raise ValueError("a garbage-token fixture needs tokens longer than the gate's bound")
    alphabet = NOISE_ALPHABET
    grown = [
        "".join(alphabet[(index + position) % len(alphabet)] for position in range(token_chars))
        for index in range(tokens)
    ]
    return _defect_lines(build_ledger_page(n_rows), grown)


def build_repeated_letter_page(*, n_rows: int = 20, tokens: int = 12, run: int = 6) -> SyntheticPage:
    """The clean ledger plus `tokens` SHORT tokens carrying a repeated-letter
    run (`DEFECT_STEM` with its last letter repeated). Every one of them is
    well under the 20-character bound, so a gate that implements only the
    length half of the garbage rule does not move at all here (P23-EGATE
    M3)."""
    grown = [DEFECT_STEM + DEFECT_STEM[-1] * run for _ in range(tokens)]
    if any(len(token) > 20 for token in grown):
        raise ValueError("a repeated-letter fixture must stay under the length bound")
    return _defect_lines(build_ledger_page(n_rows), grown)


#: The right edge of each money column on a multi-column page, rightmost
#: first. 120 points apart is ~18 character widths at this font size: far
#: wider than `right_edge_cluster_tolerance`, so two columns are two columns,
#: and nothing like the sub-character wobble the residual is about.
COLUMN_SPACING_PT = 120.0
RIGHTMOST_COLUMN_EDGE = 540.0


def build_column_page(*, columns: int = 2, n_rows: int = 12) -> SyntheticPage:
    """A FLAWLESS statement page whose figures sit in `columns` right-aligned
    money columns — withdrawals and deposits, or debit / credit / fees — with
    NO running balance, so consecutive lines end in DIFFERENT columns.

    Nothing on this page is a defect: every token is clean, every amount
    parses, the line heights are uniform, the lexicon rate is the clean
    ledger's. It exists because a residual measured over "the last money token
    of each line" reads the distance BETWEEN these columns as one column's own
    wobble, and fired E3 on exactly this layout at five times the ceiling
    (P23-EGATE review MAJOR-1). Every amount is a round figure, as everywhere
    else in this module, so no synthetic figure can coincide with a real one.
    """
    if columns < 1:
        raise ValueError("a column page needs at least one money column")
    edges = tuple(RIGHTMOST_COLUMN_EDGE - COLUMN_SPACING_PT * index
                  for index in reversed(range(columns)))
    lines: list[SyntheticLine] = []
    y = TOP_MARGIN

    def add_line(tokens: list[tuple[str, float]]) -> None:
        nonlocal y
        lines.append(SyntheticLine(words=tuple(_word(text, x, y) for text, x in tokens)))
        y += LINE_HEIGHT

    def right_aligned(text: str, edge: float) -> tuple[str, float]:
        """The x at which `text` ENDS on `edge` — the only way to build a
        right-aligned column with a fixed-width font."""
        return text, edge - max(len(text), 1) * CHAR_WIDTH

    headings = ["WITHDRAWAL", "DEPOSIT", "FEES", "INTEREST"]
    add_line([("SYNTHETIC", LEFT_MARGIN), ("STATEMENT", LEFT_MARGIN + 110.0)])
    add_line(
        [("DATE", COLUMN_X["date"]), ("DESCRIPTION", COLUMN_X["description"])]
        + [right_aligned(headings[index % len(headings)], edge)
           for index, edge in enumerate(edges)]
    )

    for row in range(1, n_rows + 1):
        amount = float(row * 10)
        add_line([
            (f"{SYNTHETIC_YEAR}-01-{row:02d}", COLUMN_X["date"]),
            ("SYNTHETIC", COLUMN_X["description"]),
            ("ROW", COLUMN_X["description"] + 100.0),
            right_aligned(f"{amount:.2f}", edges[(row - 1) % columns]),
        ])

    height = max(PAGE_HEIGHT_PT, y + TOP_MARGIN)
    return SyntheticPage(width_pt=PAGE_WIDTH_PT, height_pt=height, lines=tuple(lines))
