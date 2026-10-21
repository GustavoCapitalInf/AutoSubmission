"""The ONE native PDF reader: PyMuPDF words -> canonical evidence, in the
DISPLAY frame (Phase 2.2 cell K; umbrella D3/D4).

Why it lives here
-----------------
The intake ladder (`ocr/pipeline.py`) must attach native evidence to the
artifact it returns and cannot import `analysis`; the structurer
(`analysis/structurer/geometry.py`) must consume the same reader and cannot
import `ocr`. The only home both may import is this neutral package, whose
boundary tripwire (`tests/test_evidence_boundary.py`) is amended precisely
for it: `evidence/` still imports nothing from any repository package, and
the ONLY third-party import anywhere under `evidence/` is `fitz` (PyMuPDF),
imported LAZILY inside `native_evidence_from_pdf` and nowhere else — so
`import evidence` succeeds with PyMuPDF absent, and a module-level `import
fitz` anywhere in the package fails the tripwire.

The display frame (D4)
----------------------
PyMuPDF's `page.get_text("words")` returns boxes in the page's UNROTATED
coordinate space, while `page.rect` — the frame this reader declares — is the
ROTATED display rectangle (width and height swapped on a 90/270 page). Phase
2.1 recorded the mismatch as a note (`native_words_unrotated_space`) and left
the boxes where they were; the Paddle raster is display-oriented, so a
rotated page's two geometries could not be compared. Every word box is now
transformed by `page.rotation_matrix` into the display frame: the four
corners are mapped and the axis-aligned box of the mapped corners is taken —
a TRANSFORM, never a swap of the original coordinates. A `pdf_point` frame
is a VIEWPORT, not a container (the Phase 2.2 closure ruling): a word whose
transformed box lies outside `page.rect` — a margin header or footer, off-
canvas text — is kept verbatim and noted (`outside_frame:<word_id>`, plus a
per-page count), never clamped, never dropped, never a refusal (measured over
the archive, refusing such pages had cost every page of 102 documents, 89 of
them validated). On an unrotated page the rotation matrix is the
identity and the raw boxes ARE the display boxes; they are taken verbatim
(the identity is applied as the identity), so the Phase 2.1 byte-identity
pin on unrotated pages holds by construction rather than by floating-point
luck. A rotated page carries `ROTATION_APPLIED_NOTE` in its notes and
`rotation_deg` on its frame; the Phase 2.1 note is retired and never emitted.

Phase 2.3 closes the two latent defects the cell's re-review named,
both with a
population of 0 in the archive and both reachable by a real PDF:

* **N-1** — the display transform is now taken from the rectangle
  `page.rect` reports (`_display_matrix`) whenever PyMuPDF's own
  `rotation_matrix` disagrees with it, because a CropBox that OVERHANGS its
  MediaBox makes that matrix translate by the unclamped box while the rect,
  the word coordinates and Poppler's raster are all the clamped one. Where
  the two agree — every page whose CropBox sits inside its MediaBox —
  PyMuPDF's matrix is used verbatim, so no existing page's evidence bytes
  move; where they do not, the page carries `CLAMPED_TRANSFORM_NOTE`.
* **N-2** — a `/Rotate` written as an INDIRECT reference is RESOLVED
  (`_indirect_rotate`) before the mod-90 test, so an indirect 45 is refused
  by name like a direct one instead of being silently mis-framed. ONE call —
  `xref_object` already resolves a reference chain to its terminal value —
  and the resolved value is acted on only where the page's own geometry
  corroborates it, because PyMuPDF's writer flattens a reference-bodied
  object into the bare object NUMBER, so a resolved integer can be an xref
  number rather than an angle. Closure of the cell's own review, MAJOR-1.

What is and is not here
-----------------------
No `ocr` import (the document sha is computed locally with `hashlib`, never
via `ocr.inspect`); no parser, validator, statement, amount or date
knowledge; no grouping rule of its own (`PageEvidence` derives lines through
`evidence.group_lines`, the ONE rule). Nothing here decides what a word
MEANS.
"""
from __future__ import annotations

import hashlib

from .canonical import (
    ExtractionEvidence,
    PageEvidence,
    PageFrame,
    WordBox,
    inside_frame,
    word_id,
)

__all__ = [
    "CLAMPED_TRANSFORM_NOTE",
    "FRAME_DISPLAY",
    "INVALID_ROTATION_NOTE",
    "NATIVE_EXTRACTOR_ID",
    "OUTSIDE_FRAME_NOTE_PREFIX",
    "ROTATION_APPLIED_NOTE",
    "UNREADABLE_PAGE_NOTE",
    "WORDS_OUTSIDE_FRAME_NOTE_PREFIX",
    "WORD_OUTSIDE_FRAME_NOTE",
    "WORD_REFUSED_NOTE",
    "native_evidence_from_pdf",
    "outside_frame_word_ids",
    "words_outside_frame",
]

#: `ExtractionEvidence.extractor_id` / `model_token` for the native PDF
#: reader. Not a bank, not a customer, not a value — the name of a reading
#: method, same class as `local-tesseract-ocr` / `paddle-ocr+ppocrv5`.
NATIVE_EXTRACTOR_ID = "native-pdf-words"

#: `runtime["frame"]`: the coordinate frame every word box of this evidence
#: is expressed in. Always the display frame (`page.rect`) since Phase 2.2.
FRAME_DISPLAY = "display"

#: A `PageEvidence.notes` entry meaning: this page's own `get_text`/`rect`/
#: `rotation_matrix` read threw, OR the read succeeded but produced a rect
#: this contract cannot represent as a `PageFrame` (a zero-area rect is the
#: reachable shape). Both are the SAME operative fact: there is never a real
#: page size to publish, so the page is kept — for page-number fidelity —
#: with no words and a minimal, valid placeholder frame (P21-GEOMETRY-CLOSURE-2 R-3).
UNREADABLE_PAGE_NOTE = "native_page_unreadable"

#: A `PageEvidence.notes` entry meaning: the page read fine (its REAL frame
#: is reported) but at least one PyMuPDF word could not become a `WordBox` —
#: an inverted or degenerate box `evidence/canonical.py` refuses. One bad
#: word refuses the WHOLE page (no guessed structure, no silently dropping
#: just the offending word), a documented, latent (0 words on the pinned
#: corpus, Phase 2.1's measurement) divergence from Phase 2.0's keep-every-
#: word behaviour (P21-GEOMETRY-CLOSURE F-5).
WORD_REFUSED_NOTE = "native_page_word_refused"

#: RETIRED (Phase 2.2 closure ruling, option c — never emitted). Between the
#: cell's first commit and its closure, a word outside the display frame
#: refused its whole page under this note; measured over the archive that
#: refused every page of 102 documents (89 validated) for margin headers and
#: footers, defeating the lineage the evidence exists for. A `pdf_point`
#: frame is now a VIEWPORT: the reader keeps every box verbatim and notes the
#: out-of-frame words instead (below). The name is kept so imports resolve.
WORD_OUTSIDE_FRAME_NOTE = "native_word_outside_frame"

#: A `PageEvidence.notes` entry PER out-of-frame word: `outside_frame:<word_id>`.
#: The word's box, once transformed into the display frame, lies outside
#: `[0, width] x [0, height]` (`evidence.canonical.inside_frame`, the ONE
#: bounds rule) — a margin header/footer or off-canvas text the printed page
#: does not show. The box is kept VERBATIM (never clamped, never dropped) so
#: the evidence stays a faithful record; a consumer that wants what a reader
#: sees (a native-vs-raster comparison, the LayoutModel) treats these ids as
#: invisible-when-printed. Read them back with `outside_frame_word_ids`.
OUTSIDE_FRAME_NOTE_PREFIX = "outside_frame:"

#: A `PageEvidence.notes` entry, present only when the count is non-zero:
#: `words_outside_frame=<n>` — how many of the page's words carry an
#: `outside_frame:` note. Read it back with `words_outside_frame`.
WORDS_OUTSIDE_FRAME_NOTE_PREFIX = "words_outside_frame="

#: A `PageEvidence.notes` entry meaning: the page object's RAW `/Rotate`
#: (its own, or inherited from a parent `Pages` node) is not a multiple of
#: 90 — a value the PDF standard does not define. PyMuPDF then reports
#: `page.rotation == 0` with an identity `rotation_matrix` but a swapped
#: `page.rect` and rotated word coordinates, so any box this reader emitted
#: would miss the ink of the page a viewer shows (review F-2). The page is
#: refused whole — zero words, its declared rect as the frame — and named;
#: the archive carries 0 such pages (the closure-2 census).
INVALID_ROTATION_NOTE = "invalid_rotation"

#: A `PageEvidence.notes` entry on every page whose `page.rotation` is not 0:
#: the boxes were transformed by `page.rotation_matrix` into the display
#: frame (D4). Replaces Phase 2.1's `native_words_unrotated_space`, which
#: meant the opposite and is retired.
ROTATION_APPLIED_NOTE = "rotation_applied"

#: A `PageEvidence.notes` entry meaning: PyMuPDF's own `page.rotation_matrix`
#: disagreed with the rectangle `page.rect` reports, and the display
#: transform was derived from that RECTANGLE instead (P22-IDENTITY re-review
#: N-1). The reachable shape is a page whose CropBox OVERHANGS its MediaBox
#: and that carries a `/Rotate`: PyMuPDF clamps `page.rect` and the word
#: coordinates to the MediaBox — which is also what Poppler renders — but
#: builds `rotation_matrix`'s translation from the UNCLAMPED CropBox, so
#: every box the reader emitted was offset by the overhang (measured 76 pt
#: at 90/180/270 on the synthetic pin; boxes-on-ink 0.000). The rect is the
#: rectangle the frame declares and the raster shows, so the rect wins. The
#: note exists because a page whose two sources of truth disagreed is worth
#: knowing about even when the reader recovered.
CLAMPED_TRANSFORM_NOTE = "clamped_display_transform"

_VALID_ROTATIONS = (0, 90, 180, 270)
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
#: How far a component of PyMuPDF's rotation matrix may differ from the one
#: derived from `page.rect` before the derived matrix is used instead. The
#: two are EXACTLY equal on every page whose CropBox sits inside its
#: MediaBox (the rotation components are 0 / +-1 and the translations are the
#: rect's own dimensions), and differ by the overhang — tens of points — on
#: an N-1 page. Nothing lies between, so this bound only has to exclude a
#: floating-point last bit; preferring PyMuPDF's matrix wherever the two
#: agree is what keeps every existing page's evidence bytes unchanged.
_MATRIX_TOLERANCE = 1e-6
#: How far `page.rect` may differ from the transpose of the rectangle the page
#: crops to before the two are no longer "the same rectangle, swapped". Page
#: sides are whole or near-whole points; half a point is far below any real
#: difference and far above float noise.
_TRANSPOSE_TOLERANCE = 0.5


def _clamped_box(page) -> tuple[float, float] | None:
    """The width and height of the rectangle the page actually crops to — its
    CropBox INTERSECTED with its MediaBox, which is what PyMuPDF reports as
    `page.rect` (up to the display rotation) and what the rasteriser renders
    (N-1). `None` when either box cannot be read."""
    try:
        crop, media = page.cropbox, page.mediabox
        x0, y0 = max(float(crop.x0), float(media.x0)), max(float(crop.y0), float(media.y0))
        x1, y1 = min(float(crop.x1), float(media.x1)), min(float(crop.y1), float(media.y1))
    except Exception:
        return None
    return abs(x1 - x0), abs(y1 - y0)


def _rect_is_transposed(page) -> bool:
    """THE observable signature of the F-2 harm: PyMuPDF reports NO rotation,
    yet the rectangle it declares (`page.rect`) is the TRANSPOSE of the
    rectangle the page crops to.

    That combination means PyMuPDF has normalised a rotation away while still
    swapping the frame, so the boxes it hands back are in a space no renderer
    displays — measured: on such a page Poppler's raster has the UNSWAPPED
    dimensions and NO display transform, at any of the four angles, puts ink
    under a single word box (ink fraction 0.000 at 0/90/180/270). A square
    page is excluded because on it the transpose is the rectangle itself and
    the signature would carry no information."""
    try:
        if int(page.rotation) % 360 != 0:
            return False
        width, height = float(page.rect.width), float(page.rect.height)
    except Exception:
        return False
    box = _clamped_box(page)
    if box is None:
        return False
    box_width, box_height = box
    return (
        abs(width - box_height) <= _TRANSPOSE_TOLERANCE
        and abs(height - box_width) <= _TRANSPOSE_TOLERANCE
        and abs(box_width - box_height) > _TRANSPOSE_TOLERANCE
    )


def _indirect_rotate(document, page, value):
    """The integer an INDIRECT `/Rotate` resolves to — used ONLY where the
    page's own geometry corroborates it — or `None`.

    P22-IDENTITY re-review N-2: `xref_get_key` reports a `/Rotate` written as
    `12 0 R` with kind `xref`, and the Phase 2.2 reader treated that as "no
    value", so an indirect 45 escaped the invalid-rotation refusal and was
    mis-framed exactly as a direct 45 had been. The reference is resolved
    here, through `xref_object`, before the mod-90 test.

    ONE call, and it is all there ever is, because `xref_object` ALREADY
    RESOLVES the chain. Measured on files whose bytes were checked object by
    object: where object A's body really is the reference `B 0 R` and B holds
    270, `xref_object(A)` returns `'270'` — the terminal's value, not `B` and
    not the text `B 0 R`. A bounded walk over `xref_object` would therefore be
    a walk over values the library has already followed, and its
    reference-shaped exit (`endswith(" R")`) is unreachable by construction.

    The number that comes back is NOT trustworthy on its own, and that is the
    defect this closure fixes. PyMuPDF's own writer FLATTENS an object whose
    body is a reference: `Document.tobytes()` writes `A 0 obj\\n B \\nendobj`
    for a body of `B 0 R`, so a document round-tripped through it carries, in
    its bytes, an indirect `/Rotate` resolving to the arbitrary INTEGER B —
    an object number, not an angle. Every renderer then reads that integer as
    the rotation (both PyMuPDF and Poppler swap the page at B = 90), and the
    reader that returned it unchecked refused the page whenever B was not a
    multiple of 90 — losing the whole native reading of a document every
    renderer displays perfectly. Corroboration is what makes an arbitrary
    resolved integer safe to act on, both ways:

    * a resolved multiple of 90 is taken only when `page.rotation` is that
      same angle — i.e. the library read the same value and applied it. Where
      they differ, the number describes no page this reader can see and it is
      refused as no value;
    * a resolved NON-multiple of 90 is taken — and refuses the page by name —
      only when the mis-framing signature is actually present
      (`_rect_is_transposed`). That is exactly the F-2 harm and nothing else:
      a page that renders correctly is never refused for a number in an
      object no renderer reads.

    Anything else — a name, a dictionary, a real, a missing object, an
    uncorroborated integer — is `None`, the same "no value this reader can
    trust" answer the walk gives for an absent key, and the page then follows
    PyMuPDF's own rotation exactly as it did before this fix.
    """
    head = str(value).strip().split(" ", 1)[0]
    if not head.isdigit():
        return None
    try:
        source = str(document.xref_object(int(head))).strip()
    except Exception:
        return None
    if not source.lstrip("+-").isdigit():
        return None
    resolved = int(source)
    try:
        rotation = int(page.rotation) % 360
    except Exception:
        return None
    if resolved % 90 == 0:
        return resolved if rotation == resolved % 360 else None
    return resolved if _rect_is_transposed(page) else None


def _raw_rotate(document, page):
    """The page's RAW `/Rotate` integer — its own key, else the nearest
    ancestor `Pages` node's (the standard's inheritance) — or `None` when
    no node carries one or the walk cannot be completed. Read from the
    objects themselves because PyMuPDF normalises the value before
    `page.rotation` and silently mis-frames an invalid one (review F-2). An
    INDIRECT value is resolved through the object it names, and used only
    where the page's own geometry corroborates it (re-review N-2)."""
    xref = page.xref
    for _ in range(64):
        kind, value = document.xref_get_key(xref, "Rotate")
        if kind == "int":
            return int(value)
        if kind == "xref":
            return _indirect_rotate(document, page, value)
        if kind not in ("null", ""):
            return None
        kind, value = document.xref_get_key(xref, "Parent")
        if kind != "xref":
            return None
        head = str(value).strip().split(" ", 1)[0]
        if not head.isdigit():
            return None
        xref = int(head)
    return None


def outside_frame_word_ids(notes) -> tuple[str, ...]:
    """The word ids a page's notes mark as outside the display frame, in note
    order (empty when none)."""
    return tuple(
        note[len(OUTSIDE_FRAME_NOTE_PREFIX):] for note in notes if str(note).startswith(OUTSIDE_FRAME_NOTE_PREFIX)
    )


def words_outside_frame(notes) -> int:
    """The page's recorded out-of-frame word count (0 when the count note is
    absent — the count note exists only when it is non-zero)."""
    for note in notes:
        if str(note).startswith(WORDS_OUTSIDE_FRAME_NOTE_PREFIX):
            return int(note[len(WORDS_OUTSIDE_FRAME_NOTE_PREFIX):])
    return 0


def _matrix_tuple(matrix) -> tuple[float, float, float, float, float, float]:
    return (float(matrix.a), float(matrix.b), float(matrix.c), float(matrix.d),
            float(matrix.e), float(matrix.f))


def _display_matrix(rotation: int, width: float, height: float) -> tuple[float, float, float, float, float, float]:
    """The display transform a page of DISPLAY size `width` x `height` with
    this rotation must have, derived from that rectangle alone.

    The same formula the four-angle pin carries independently
    (`tests/test_native_evidence.py::_expected_display`), written as an
    affine matrix in PyMuPDF's point-times-matrix convention: a `/Rotate` of
    R displays the page R degrees CLOCKWISE, and in top-left-origin, y-down
    coordinates the unrotated page's `(x, y)` lands at `(H - y, x)` for 90,
    `(W - x, H - y)` for 180 and `(y, W - x)` for 270, where `W` / `H` are
    the UNROTATED dimensions — which are the display dimensions swapped at
    90 and 270, so every constant below is one of this page's own display
    sides. That is the whole point (re-review N-1): the rectangle the frame
    declares, the rectangle the rasteriser renders and the rectangle the word
    coordinates live in are one rectangle, and the transform is built from
    it rather than from a CropBox the page does not display.
    """
    if rotation == 90:
        return (0.0, 1.0, -1.0, 0.0, float(width), 0.0)
    if rotation == 180:
        return (-1.0, 0.0, 0.0, -1.0, float(width), float(height))
    if rotation == 270:
        return (0.0, -1.0, 1.0, 0.0, 0.0, float(height))
    return _IDENTITY


def _matrices_agree(left, right) -> bool:
    return all(abs(a - b) <= _MATRIX_TOLERANCE for a, b in zip(left, right))


def _display_box(
    m: tuple[float, float, float, float, float, float], x0: float, y0: float, x1: float, y1: float,
) -> tuple[float, float, float, float]:
    """The axis-aligned box of the four corners mapped by the affine matrix
    `(a, b, c, d, e, f)`: `x' = a*x + c*y + e`, `y' = b*x + d*y + f` — PyMuPDF's
    own point-times-matrix convention. A transform of the corners, then the
    enclosing box: the ORIGINAL coordinates are never swapped or reordered."""
    a, b, c, d, e, f = m
    xs: list[float] = []
    ys: list[float] = []
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        xs.append(a * x + c * y + e)
        ys.append(b * x + d * y + f)
    return min(xs), min(ys), max(xs), max(ys)


def native_evidence_from_pdf(pdf_bytes: bytes) -> ExtractionEvidence | None:
    """Native PDF word geometry, read through the canonical evidence
    contract, in the DISPLAY frame.

    One `WordBox` per PyMuPDF word (`page.get_text("words")` items with
    non-blank text) with its box transformed by `page.rotation_matrix` into
    the frame `page.rect` describes; one `PageFrame.pdf_points` per page
    (`page.rect` for width/height, `page.rotation` recorded); words grouped
    into lines by the ONE rule. `document_sha256` is computed locally
    (`hashlib.sha256(pdf_bytes)`, upper-case hex). `runtime` records the
    PyMuPDF version and `frame = "display"`. `raw`, `confidence` and
    `line_ref` are `None`: native text has no extractor-side score, no line
    index and no verbatim per-page result worth freezing.

    Returns `None` exactly when the Phase 2.1 reader returned `None`:
    PyMuPDF unimportable, unparseable bytes, a document with no pages, or a
    document that opens but yields no word this reader can place (the honest
    answer for a scanned page — there are no words, only pixels). Never
    raises. Three DISTINCT page-level failures are each kept as an empty page
    (never abort the whole document), named honestly and separately:
    `UNREADABLE_PAGE_NOTE` (no real frame exists — placeholder 1x1 frame),
    `INVALID_ROTATION_NOTE` (the page's raw `/Rotate`, own or inherited, is
    not a multiple of 90 — the declared rect, zero words), `WORD_REFUSED_NOTE`
    (a real frame; one PyMuPDF box is inverted or degenerate). A word whose
    transformed box lies outside the display frame
    is NOT a failure: it is kept verbatim and noted per word
    (`OUTSIDE_FRAME_NOTE_PREFIX`) with the page's count
    (`WORDS_OUTSIDE_FRAME_NOTE_PREFIX`). Anything else this contract cannot
    faithfully represent aborts the whole document to `None` rather than
    guess.

    `import fitz` is the first statement of this function body and the ONLY
    third-party import anywhere in `evidence/` (D3; pinned by AST in
    `tests/test_evidence_boundary.py` — the node's enclosing function and
    module are asserted).
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
        "frame": FRAME_DISPLAY,
    }

    pages: list[PageEvidence] = []
    try:
        for page_index, page in enumerate(document):
            # Failure class 1: no real dimensions exist for this page at all
            # (the read threw, OR it succeeded but the rect cannot become a
            # valid `PageFrame` — a zero-area rect is the reachable shape).
            try:
                raw_words = page.get_text("words")
                rect = page.rect
                rotation = int(page.rotation) % 360
                if rotation not in _VALID_ROTATIONS:
                    rotation = 0
                matrix = _matrix_tuple(page.rotation_matrix)
                frame = PageFrame.pdf_points(
                    page_index=page_index, width_pt=float(rect.width), height_pt=float(rect.height),
                    rotation_deg=rotation,
                )
                raw_rotate = _raw_rotate(document, page)
            except Exception:
                placeholder = PageFrame.pdf_points(page_index=page_index, width_pt=1.0, height_pt=1.0)
                pages.append(PageEvidence(frame=placeholder, words=(), notes=(UNREADABLE_PAGE_NOTE,)))
                continue
            if raw_rotate is not None and raw_rotate % 90 != 0:
                # Review F-2: an invalid `/Rotate` (not a multiple of 90).
                # PyMuPDF has already normalised it away; the boxes it would
                # give us do not describe the page a viewer shows. Refused
                # whole, named, with the declared rect so the refusal is
                # visible — never a guessed frame.
                pages.append(PageEvidence(frame=frame, words=(), notes=(INVALID_ROTATION_NOTE,)))
                continue
            rotation_notes = (ROTATION_APPLIED_NOTE,) if rotation else ()
            # Re-review N-1: PyMuPDF's `rotation_matrix` and the rectangle
            # `page.rect` reports can disagree — an overhanging CropBox makes
            # the matrix translate by the UNCLAMPED box while the rect and the
            # word coordinates are the clamped one. `page.rect` is the
            # rectangle this reader publishes as the frame AND the rectangle
            # the rasteriser renders, so where the two disagree the rect wins
            # and the page says so. Where they AGREE — every page whose
            # CropBox sits inside its MediaBox, which is the entire archive —
            # PyMuPDF's own matrix is used, so no existing page's evidence
            # bytes move by a floating-point hair.
            derived = _display_matrix(rotation, float(rect.width), float(rect.height))
            if _matrices_agree(matrix, derived):
                chosen = matrix
            else:
                chosen = derived
                rotation_notes += (CLAMPED_TRANSFORM_NOTE,)
            # The identity is applied AS the identity: an unrotated page's raw
            # boxes are its display boxes, verbatim (the Phase 2.1 byte-
            # identity pin). Any other matrix maps every corner.
            transform = None if chosen == _IDENTITY else chosen
            # Failure class 2: a real frame, but one PyMuPDF box cannot be
            # trusted as a box (`WordBox`'s own strict `x0 < x1 and y0 < y1`).
            try:
                words: list[WordBox] = []
                for k, item in enumerate(raw_words):
                    text = str(item[4])
                    if not text.strip():
                        continue
                    x0, y0, x1, y1 = float(item[0]), float(item[1]), float(item[2]), float(item[3])
                    if transform is not None:
                        x0, y0, x1, y1 = _display_box(transform, x0, y0, x1, y1)
                    words.append(WordBox(word_id=word_id(page_index, None, k), page_index=page_index,
                                         text=text, x0=x0, y0=y0, x1=x1, y1=y1))
            except Exception:
                pages.append(PageEvidence(frame=frame, words=(), notes=(WORD_REFUSED_NOTE,) + rotation_notes))
                continue
            # The viewport rule (closure ruling, option c): a box outside the
            # display frame is KEPT verbatim and NOTED — one note per word,
            # plus the count — through the ONE bounds rule `inside_frame`.
            outside = tuple(
                word.word_id for word in words if not inside_frame(frame, word.x0, word.y0, word.x1, word.y1)
            )
            outside_notes = tuple(OUTSIDE_FRAME_NOTE_PREFIX + wid for wid in outside)
            if outside:
                outside_notes += (WORDS_OUTSIDE_FRAME_NOTE_PREFIX + str(len(outside)),)
            pages.append(PageEvidence(frame=frame, words=tuple(words), notes=rotation_notes + outside_notes))
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
