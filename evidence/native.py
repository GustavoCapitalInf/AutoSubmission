"""The ONE native PDF reader: PyMuPDF words -> canonical evidence, in the
DISPLAY frame (Phase 2.2 cell K, `docs/agent-handoffs/P22-IDENTITY.md`
items 1-2; umbrella D3/D4).

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
a TRANSFORM, never a swap of the original coordinates — and the result must
lie inside the declared frame or the page is refused (`WORD_OUTSIDE_FRAME_NOTE`,
zero words, real frame). On an unrotated page the rotation matrix is the
identity and the raw boxes ARE the display boxes; they are taken verbatim
(the identity is applied as the identity), so the Phase 2.1 byte-identity
pin on unrotated pages holds by construction rather than by floating-point
luck. A rotated page carries `ROTATION_APPLIED_NOTE` in its notes and
`rotation_deg` on its frame; the Phase 2.1 note is retired and never emitted.

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
    MalformedGeometry,
    PageEvidence,
    PageFrame,
    WordBox,
    word_id,
)

__all__ = [
    "FRAME_DISPLAY",
    "NATIVE_EXTRACTOR_ID",
    "ROTATION_APPLIED_NOTE",
    "UNREADABLE_PAGE_NOTE",
    "WORD_OUTSIDE_FRAME_NOTE",
    "WORD_REFUSED_NOTE",
    "native_evidence_from_pdf",
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

#: A `PageEvidence.notes` entry meaning: the page read fine and every word
#: became a valid box, but at least one box, once transformed into the
#: display frame, lies outside `[0, width] x [0, height]` — refused whole by
#: the same bounds rule `PageEvidence` enforces for every frame (Phase 2.2
#: item 3: a `pdf_point` frame gained the check `pixel` frames already had).
#: Never clamped, never swapped: a word outside the page the reader declared
#: is a defect of the transform or of the PDF, and the page reports zero
#: words with its REAL frame so the refusal is visible.
WORD_OUTSIDE_FRAME_NOTE = "native_word_outside_frame"

#: A `PageEvidence.notes` entry on every page whose `page.rotation` is not 0:
#: the boxes were transformed by `page.rotation_matrix` into the display
#: frame (D4). Replaces Phase 2.1's `native_words_unrotated_space`, which
#: meant the opposite and is retired.
ROTATION_APPLIED_NOTE = "rotation_applied"

_VALID_ROTATIONS = (0, 90, 180, 270)
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _matrix_tuple(matrix) -> tuple[float, float, float, float, float, float]:
    return (float(matrix.a), float(matrix.b), float(matrix.c), float(matrix.d),
            float(matrix.e), float(matrix.f))


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
    `WORD_REFUSED_NOTE` (a real frame; one PyMuPDF box is inverted or
    degenerate), `WORD_OUTSIDE_FRAME_NOTE` (a real frame; every box is valid
    but one lies outside the display frame after the transform). Anything
    else this contract cannot faithfully represent aborts the whole document
    to `None` rather than guess.

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
            except Exception:
                placeholder = PageFrame.pdf_points(page_index=page_index, width_pt=1.0, height_pt=1.0)
                pages.append(PageEvidence(frame=placeholder, words=(), notes=(UNREADABLE_PAGE_NOTE,)))
                continue
            rotation_notes = (ROTATION_APPLIED_NOTE,) if rotation else ()
            # The identity is applied AS the identity: an unrotated page's raw
            # boxes are its display boxes, verbatim (the Phase 2.1 byte-
            # identity pin). Any other matrix maps every corner.
            transform = None if matrix == _IDENTITY else matrix
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
            # Failure class 3: every box is valid, but one lies outside the
            # display frame — `PageEvidence`'s own bounds rule refuses it. By
            # elimination this is the only `MalformedGeometry` a page of valid
            # same-index, unique-id `WordBox`es can raise here, so no second
            # copy of the bounds arithmetic is kept in this module.
            try:
                page_evidence = PageEvidence(frame=frame, words=tuple(words), notes=rotation_notes)
            except MalformedGeometry:
                page_evidence = PageEvidence(frame=frame, words=(), notes=(WORD_OUTSIDE_FRAME_NOTE,) + rotation_notes)
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
