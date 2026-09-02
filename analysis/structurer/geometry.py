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

Phase 2.1 (`docs/agent-handoffs/P21-GEOMETRY.md`) adds a second extraction
source — PaddleOCR word boxes, in raster pixels — through the extractor-
neutral `evidence/` package (`docs/agent-handoffs/PHASE2-1-PADDLE.md`
§"Evidence contract", D1). This module is now the ONE consumer of that
package for the structurer:

* `native_evidence_from_pdf` reads a native PDF into canonical evidence
  (`ExtractionEvidence`) — the same representation Paddle's adapter produces,
  in `pdf_point` space. It lives HERE, not in `evidence/`, because `evidence/`
  is pinned standard-library-only (`tests/test_evidence_boundary.py`) and
  PyMuPDF is not the standard library; the native PDF reader is a consumer of
  the contract, like the structurer itself.
* `geometry_from_evidence` is the one path from ANY `ExtractionEvidence`
  (native or Paddle) to `DocumentGeometry`, converting every word to PDF
  points through its own page's frame and rebuilding the already-grouped
  lines (`evidence.group_lines` is the ONE grouping rule; nothing here
  regroups).
* `geometry_from_pdf` is now exactly `geometry_from_evidence(native_evidence_
  from_pdf(pdf_bytes))` — pinned byte-identical to its Phase 2.0 behaviour on
  the structurer fixtures and the corpus (`tests/test_geometry_frames.py`).

`PageGeometry.page` stays 1-based; `PageFrame.page_index` (from `evidence/`)
is 0-based. `geometry_from_evidence` is the one place the two conventions
meet: `page == frame.page_index + 1`, always.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from evidence import (
    ExtractionEvidence,
    LineBox,
    PageEvidence,
    PageFrame,
    WordBox,
    group_lines as _canonical_group_lines,
    to_pdf_points,
    word_id,
)

__all__ = [
    "DocumentGeometry",
    "PageGeometry",
    "Word",
    "GeoLine",
    "geometry_from_pdf",
    "geometry_from_evidence",
    "native_evidence_from_pdf",
]

#: `ExtractionEvidence.extractor_id` / `model_token` for the native PDF
#: reader. Not a bank, not a customer, not a value — the name of a reading
#: method, same class as `local-tesseract-ocr` / `paddle-ocr+ppocrv5`.
NATIVE_EXTRACTOR_ID = "native-pdf-words"

#: A `PageEvidence.notes` entry meaning: this page's own `get_text`/`rect`
#: read threw (a PyMuPDF failure this project has never observed on its
#: corpus), OR the read succeeded but produced a rect this contract cannot
#: represent as a `PageFrame` (P21-GEOMETRY-CLOSURE-2 R-3: a zero-area rect
#: is the reachable shape — `evidence/`'s own frame validation refuses a
#: non-positive width/height, and there is no salvageable dimension to
#: report either way). Both are the SAME operative fact: there is never a
#: real page size to publish, so the page is kept — for page-number
#: fidelity — with no words and a minimal, valid placeholder frame.
#: Distinct from `WORD_REFUSED_NOTE` (P21-GEOMETRY-CLOSURE F-5): a word
#: refusal happens only once a real frame already exists.
#: `geometry_from_evidence` does NOT special-case this note
#: (P21-GEOMETRY-CLOSURE F-8: the neutral consumer must not branch on a
#: source-specific note string) — it reports the placeholder frame's own
#: declared dimensions like any other page, which is a documented,
#: untriggered (0/109 corpus PDFs) divergence from the Phase 2.0 reader's
#: hardcoded `0.0 x 0.0` for this exact case (both sub-cases).
UNREADABLE_PAGE_NOTE = "native_page_unreadable"

#: A `PageEvidence.notes` entry meaning: the page's `get_text`/`rect` read
#: succeeded (the real frame dimensions are known and reported), but
#: building at least one `WordBox` from what PyMuPDF returned failed — an
#: out-of-contract box (P21-GEOMETRY-CLOSURE F-5: `evidence/canonical.py`'s
#: own strict `x0 < x1 and y0 < y1` validation, which `Word`/legacy
#: `_group_lines` never enforced). The fail-closed direction is kept
#: deliberately (one bad word refuses the WHOLE page — no guessed
#: structure, no silently dropping just the offending word), which is a
#: documented, latent (0/261,526 words on the pinned corpus) divergence
#: from Phase 2.0's keep-every-word behaviour. Named separately from
#: `UNREADABLE_PAGE_NOTE` because the two causes are different: this page
#: COULD be read; one word in it could not be trusted.
WORD_REFUSED_NOTE = "native_page_word_refused"

#: A `PageEvidence.notes` entry meaning: PyMuPDF's `get_text("words")` boxes
#: are in the page's UNROTATED coordinate space while `page.rect` (this
#: frame's width/height) is the ROTATED display rectangle. Phase 2.0's
#: `geometry_from_pdf` already mixed the two on a rotated page; this cell
#: PRESERVES that behaviour byte-for-byte rather than silently correcting it
#: (see `docs/agent-handoffs/P21-GEOMETRY.md` item 5 — a documented Phase 2.2
#: prerequisite, not fixed here). Measured 0/830 pages on the pinned corpus.
UNROTATED_WORDS_NOTE = "native_words_unrotated_space"

_VALID_ROTATIONS = (0, 90, 180, 270)


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
    #: The canonical evidence frame this page was converted from (Phase 2.1).
    #: `None` for geometry built the old way (nothing in this codebase does
    #: that any more, but the default keeps every positional constructor call
    #: already in the test suite valid).
    frame: PageFrame | None = None
    #: `ExtractionEvidence.extractor_id` this page's words came from
    #: (`"native-pdf-words"`, `"paddle-ocr+ppocrv5"`, ...). Defaults to
    #: `"native"` for the same backward-compatibility reason as `frame`.
    source: str = "native"


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


def _line_text_and_spans(words: tuple) -> tuple[str, tuple[tuple[int, int], ...]]:
    """The `GeoLine.text` / `GeoLine.spans` arithmetic, in one place so both
    `_group_lines` and `geometry_from_evidence` use it identically."""
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for index, word in enumerate(words):
        if index:
            parts.append(" ")
            offset += 1
        spans.append((offset, offset + len(word.text)))
        parts.append(word.text)
        offset += len(word.text)
    return "".join(parts), tuple(spans)


def _group_lines(page_number: int, words: list[Word]) -> tuple[GeoLine, ...]:
    """Words -> visual lines. A thin wrapper: the grouping rule itself is
    `evidence.group_lines` (Phase 2.1, D1/D9/D4-of-the-card-item-4) — this
    function only adapts `Word` to `WordBox` and back, so Paddle words and
    native words are grouped by the exact same code. Do not reintroduce a
    second tolerance/median computation here (`tests/test_geometry_frames.py`
    has an AST guard against it — M4)."""
    if not words:
        return ()
    boxes = tuple(
        WordBox(word_id=word_id(0, None, index), page_index=0, text=word.text,
                x0=word.x0, y0=word.y0, x1=word.x1, y1=word.y1)
        for index, word in enumerate(words)
    )
    by_id = dict(zip((box.word_id for box in boxes), words))
    built: list[GeoLine] = []
    for line in _canonical_group_lines(boxes):
        row = tuple(by_id[wid] for wid in line.word_ids)
        text, spans = _line_text_and_spans(row)
        built.append(GeoLine(page_number, row, text, spans))
    return tuple(built)


def native_evidence_from_pdf(pdf_bytes: bytes) -> ExtractionEvidence | None:
    """Native PDF word geometry, read through the canonical evidence contract.

    One `WordBox` per PyMuPDF word (`page.get_text("words")` items with
    non-blank text), one `PageFrame.pdf_points` per page (`page.rect` for
    width/height, `page.rotation` recorded — see `UNROTATED_WORDS_NOTE`),
    words grouped into lines by the ONE rule. `document_sha256` is computed
    locally (`hashlib.sha256(pdf_bytes)`), not imported from `ocr.inspect` —
    this module has no `ocr` import, by design (the analysis -> ocr allowlist
    stays pinned empty).

    Returns `None` exactly when there are no words to read at all: unparseable
    bytes, or a document that opens but prints nothing this reader can find
    (the honest answer for a scanned page — there are no words, only pixels).
    Never raises. Two DISTINCT page-level failures are both kept as an empty
    page (never abort the whole document) but named honestly and separately
    (P21-GEOMETRY-CLOSURE F-5, R-3): a page whose own `get_text`/`rect` read
    throws (a PyMuPDF failure this project's 109-PDF corpus has never
    produced), OR whose read succeeds but produces a rect `PageFrame` cannot
    represent (a zero-area rect being the reachable shape — no real
    dimensions exist to report either way), gets `UNREADABLE_PAGE_NOTE` and a
    minimal placeholder frame; a page that reads fine, produces a
    representable frame, but whose PyMuPDF word list contains a box
    `evidence/`'s strict `x0 < x1 and y0 < y1` refuses gets `WORD_REFUSED_NOTE`
    and its REAL frame — the whole page is refused (no guessed structure, no
    silently dropping just the bad word), a deliberate, documented, latent
    (0/261,526 words on the pinned corpus) divergence from Phase 2.0's
    keep-every-word behaviour. Anything else this contract cannot
    faithfully represent aborts the whole document to `None` rather than
    guess.
    """
    try:
        import fitz
    except Exception:
        return None

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    document_sha256 = hashlib.sha256(pdf_bytes).hexdigest().upper()
    runtime = {
        "pymupdf_version": str(getattr(fitz, "pymupdf_version", getattr(fitz, "__version__", "unknown"))),
    }

    pages: list[PageEvidence] = []
    try:
        for page_index, page in enumerate(document):
            # Two SEPARATE failure classes (P21-GEOMETRY-CLOSURE F-5, R-3):
            # no real dimensions exist for this page at all (the read threw,
            # OR it succeeded but the rect cannot become a valid `PageFrame`
            # -- a zero-area rect is the reachable shape, still caught here
            # since a frame is required before any word can be placed in it),
            # or the page reads fine and gets a real frame but a word PyMuPDF
            # returned cannot be trusted as a box (`evidence/`'s strict
            # `x0 < x1 and y0 < y1`). Conflating them under one note
            # mislabelled a readable page with one bad word as "unreadable";
            # they now get distinct notes and, for the second, the page's
            # REAL dimensions.
            try:
                raw_words = page.get_text("words")
                rect = page.rect
                rotation = int(page.rotation) % 360
                if rotation not in _VALID_ROTATIONS:
                    rotation = 0
                frame = PageFrame.pdf_points(
                    page_index=page_index, width_pt=float(rect.width), height_pt=float(rect.height),
                    rotation_deg=rotation,
                )
            except Exception:
                placeholder = PageFrame.pdf_points(page_index=page_index, width_pt=1.0, height_pt=1.0)
                pages.append(PageEvidence(frame=placeholder, words=(), notes=(UNREADABLE_PAGE_NOTE,)))
                continue
            try:
                words = tuple(
                    WordBox(word_id=word_id(page_index, None, k), page_index=page_index,
                            text=str(item[4]), x0=float(item[0]), y0=float(item[1]),
                            x1=float(item[2]), y1=float(item[3]))
                    for k, item in enumerate(raw_words) if str(item[4]).strip()
                )
                notes = (UNROTATED_WORDS_NOTE,) if rotation else ()
                page_evidence = PageEvidence(frame=frame, words=words, notes=notes)
            except Exception:
                notes = (WORD_REFUSED_NOTE,) + ((UNROTATED_WORDS_NOTE,) if rotation else ())
                page_evidence = PageEvidence(frame=frame, words=(), notes=notes)
            pages.append(page_evidence)
    except Exception:
        return None
    finally:
        try:
            document.close()
        except Exception:
            pass

    if not pages:
        return None
    try:
        evidence = ExtractionEvidence(
            document_sha256=document_sha256, extractor_id=NATIVE_EXTRACTOR_ID,
            model_token=NATIVE_EXTRACTOR_ID, pages=tuple(pages), runtime=runtime,
        )
    except Exception:
        return None
    return evidence if evidence.word_count else None


def geometry_from_evidence(evidence: ExtractionEvidence | None) -> DocumentGeometry | None:
    """The ONE consumer path: any `ExtractionEvidence` (native or Paddle) ->
    `DocumentGeometry`.

    Every word is converted to PDF points through its own page's frame
    (`evidence.to_pdf_points`: the identity for a `pdf_point` frame, a
    per-axis division by scale for a `pixel` frame). Lines are NOT
    regrouped — `page.lines` was already built by `evidence.group_lines`,
    the one rule — only rebuilt as `GeoLine`s with the text/span arithmetic
    `_group_lines` has always used, so an offset computed on the resulting
    text still lands on the right word regardless of the source. A page's
    reported width/height is always its own frame's declared dimensions —
    this function never branches on a `notes` string (P21-GEOMETRY-CLOSURE
    F-8): the ONE source-neutral path does not interpret a source-specific
    fact, and an empty page is an empty page whatever its notes say.

    `None` when there is nothing to read (`evidence` is `None`, or it holds
    no words). Never raises on its own defect: a hostile evidence-shaped
    object (one whose `pages`/`words`/`lines` do not hold the types this
    function expects, or whose `lines` reference a word id its page lacks —
    something the real `PageEvidence`/`ExtractionEvidence` constructors
    already refuse to build) is answered with `None`, the same honest
    refusal a document with nothing to read has always gotten.
    """
    if evidence is None:
        return None
    try:
        pages: list[PageGeometry] = []
        for page in evidence.pages:
            frame = page.frame
            if not isinstance(frame, PageFrame):
                return None
            converted: dict[str, Word] = {}
            for source_word in page.words:
                if not isinstance(source_word, WordBox):
                    return None
                x0, y0 = to_pdf_points(frame, source_word.x0, source_word.y0)
                x1, y1 = to_pdf_points(frame, source_word.x1, source_word.y1)
                converted[source_word.word_id] = Word(source_word.text, x0, y0, x1, y1)
            lines: list[GeoLine] = []
            for line in page.lines:
                if not isinstance(line, LineBox):
                    return None
                row = tuple(converted[word_ref] for word_ref in line.word_ids)
                text, spans = _line_text_and_spans(row)
                lines.append(GeoLine(page.page_index + 1, row, text, spans))
            # F-8: no branch on a note string here. The neutral consumer
            # reports the frame's own declared dimensions for every page —
            # a page with zero words is an empty page whatever its notes
            # say, and a source-specific note interpreted in the ONE
            # source-neutral path is exactly the leak this cell exists to
            # prevent. (A future extractor emitting the same note string
            # for an unrelated reason would otherwise have its page
            # dimensions silently zeroed here.)
            pages.append(PageGeometry(
                page.page_index + 1, float(frame.pdf_width_pt), float(frame.pdf_height_pt), tuple(lines),
                frame=frame, source=evidence.extractor_id,
            ))
    except Exception:
        return None

    geometry = DocumentGeometry(tuple(pages))
    return geometry if geometry.word_count else None


def geometry_from_pdf(pdf_bytes: bytes) -> DocumentGeometry | None:
    """Word boxes for a native-text PDF, or None when there are none to read.

    None is the honest answer for a scanned page: there are no words, only
    pixels, and inventing line boxes from an image is the visual rung's job
    (W3-5), not this one. Never raises — a structurer input that throws would
    put the crash class W3-1 just closed back into the platform.

    Phase 2.1: exactly `geometry_from_evidence(native_evidence_from_pdf(...))`
    — pinned byte-identical to the Phase 2.0 implementation on the structurer
    fixtures and the pinned corpus (`tests/test_geometry_frames.py`).
    """
    return geometry_from_evidence(native_evidence_from_pdf(pdf_bytes))
