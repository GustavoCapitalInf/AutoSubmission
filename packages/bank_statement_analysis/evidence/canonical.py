"""Canonical extraction evidence — the ONE representation of words, boxes and
lines that every extractor produces and every geometry consumer reads
(Phase 2.1, `docs/agent-handoffs/PHASE2-1-PADDLE.md` §"Evidence contract", D1).

Why a neutral package
---------------------
`ocr/` produces evidence (native PDF words, PaddleOCR word boxes) and
`analysis/structurer/geometry.py` consumes it. The Phase 2.0 tripwires pin the
`analysis -> ocr` import allowlist EMPTY and forbid the OCR ladder from
importing `analysis`; an evidence type owned by either side would force one of
those boundaries to widen. This package is owned by neither: it imports
nothing from any repository package and, apart from the ONE lazy `fitz`
import inside `evidence/native.py::native_evidence_from_pdf` (Phase 2.2,
D3), only the standard library (pinned by `tests/test_evidence_boundary.py`),
knows nothing about a parser, a validator, a statement, an amount or a date,
and never decides what any word MEANS. It records where a word is and what it
says, immutably, with enough frame information that every coordinate
conversion is deterministic and replayable from the serialized artifact alone.

Coordinate conventions (explicit, tested — `tests/test_evidence_canonical.py`)
------------------------------------------------------------------------------
* Two coordinate spaces, a CLOSED vocabulary: ``"pdf_point"`` (PDF user-space
  points, 72 per inch, the convention `DocumentGeometry` already uses) and
  ``"pixel"`` (a raster's integer pixel grid). They are never interchangeable:
  a `PageFrame` names its space, and a word's box is in its page's space.
* Origin TOP-LEFT, y grows DOWNWARD, in BOTH spaces (PyMuPDF's `get_text("words")`
  and PaddleOCR's boxes both use this; PDF's native bottom-left origin never
  appears here).
* A box is ``(x0, y0, x1, y1)`` with ``x0 < x1`` and ``y0 < y1`` — enforced at
  construction, never silently swapped or clamped. A degenerate or inverted
  box is `MalformedGeometry` (the "no guessed structure" direction, CASE 8).
* Bounds (`inside_frame`, the ONE rule): a ``pixel`` frame is a CONTAINER —
  a box outside the raster is malformed by construction and refuses the page;
  a ``pdf_point`` frame is a VIEWPORT (Phase 2.2 closure ruling) — a PDF
  legitimately places text outside ``page.rect``, the box is kept verbatim,
  and the native reader (`evidence/native.py`, which places every word in the
  DISPLAY frame ``page.rect`` describes) notes each such word
  (``outside_frame:<word_id>``) and the per-page count. Nothing is ever
  clamped or dropped.
* A ``pixel`` frame carries the raster's dimensions and dpi, the PDF page's
  dimensions in points and the page's rotation as the rasteriser applied it;
  ``scale_x`` / ``scale_y`` are pixels-per-point per axis and MUST agree with
  ``dpi / 72`` within `SCALE_TOLERANCE` (relative), or the frame refuses. A
  ``pdf_point`` frame has scale exactly 1.0 and no raster fields.
* ``page_index`` is 0-BASED everywhere in this package (it matches
  `StatementMarkdown.pages` list indices, `PageIntegrity.page_index` and
  PaddleOCR's own `page_index`). `analysis/structurer/geometry.py`'s
  `PageGeometry.page` is 1-based and is derived as ``page_index + 1`` there —
  the one place the two conventions meet, and it is named.

Immutability
------------
Every object is a frozen dataclass. `PageEvidence.raw` — the extractor's
verbatim per-page result — is deep-frozen on construction (mappings become
`MappingProxyType`, lists become tuples) and hashed; `raw_sha256` is the hash
of its canonical JSON, so any later mutation would be detectable and, since
the structure is read-only, is not possible through the object at all.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields, replace
from statistics import median
from types import MappingProxyType
from typing import Any, Iterable, Mapping

__all__ = [
    "COORDINATE_SPACES",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceError",
    "ExtractionEvidence",
    "LineBox",
    "MalformedGeometry",
    "PDF_POINT",
    "PIXEL",
    "POINTS_PER_INCH",
    "PageEvidence",
    "PageFrame",
    "SCALE_TOLERANCE",
    "WordBox",
    "canonical_json",
    "from_json",
    "group_lines",
    "inside_frame",
    "page_text",
    "sha256_of_json",
    "to_json",
    "to_pdf_points",
    "to_pixels",
    "word_id",
]

#: The serialized shape's own version. Bump when a field is added, removed or
#: re-meant; `from_json` refuses any other value rather than guessing.
EVIDENCE_SCHEMA_VERSION = 1

PDF_POINT = "pdf_point"
PIXEL = "pixel"
COORDINATE_SPACES: tuple[str, ...] = (PDF_POINT, PIXEL)

POINTS_PER_INCH = 72.0
#: Relative tolerance between a pixel frame's declared per-axis scale
#: (raster px / PDF pt) and the scale its dpi implies (dpi / 72). Rasterisers
#: round page dimensions to whole pixels, so the two differ by at most a
#: fraction of a pixel over a page; 1 % is generous for that and far too
#: tight for a wrong dpi or a page/raster mismatch (a 200-vs-300 dpi mix-up
#: is a 50 % disagreement).
SCALE_TOLERANCE = 0.01

_ROTATIONS = (0, 90, 180, 270)


class EvidenceError(ValueError):
    """Any refusal by this package: malformed input, unknown vocabulary, a
    serialized shape from another schema version."""


class MalformedGeometry(EvidenceError):
    """A box, frame or page whose geometry cannot be trusted: inverted or
    degenerate boxes, a box outside its raster, a scale that disagrees with
    its dpi, mixed coordinate spaces on one page. Refused whole — never
    clamped, swapped, or guessed around (CASE 8)."""


# ---------------------------------------------------------------------------
# Deep-freezing and canonical JSON (the hashing substrate)
# ---------------------------------------------------------------------------

def _freeze(value: Any) -> Any:
    """Recursively turn mappings into read-only proxies and lists into tuples.

    Scalars pass through. Anything that is not a JSON-shaped value (a set, a
    custom object, bytes) is refused: `raw` must be exactly what `to_json`
    can reproduce, or the sha it carries would describe something else."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise EvidenceError(f"raw evidence holds a non-JSON value of type {type(value).__name__}")


def _thaw(value: Any) -> Any:
    """The inverse of `_freeze`, for serialization only."""
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def canonical_json(payload: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, floats via `repr`
    (round-trip exact), non-ASCII escaped so the bytes are platform-neutral."""
    return json.dumps(_thaw(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def sha256_of_json(payload: Any) -> str:
    """UPPERCASE hex SHA-256 of `canonical_json(payload)` (the platform's hash
    convention: `ocr.inspect.content_sha256` is uppercase too)."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest().upper()


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageFrame:
    """The coordinate frame one page's boxes live in. See the module docstring
    for the conventions. Validated on construction; a frame that cannot be
    trusted does not exist."""

    page_index: int
    space: str
    width: float
    height: float
    pdf_width_pt: float | None = None
    pdf_height_pt: float | None = None
    raster_width_px: int | None = None
    raster_height_px: int | None = None
    dpi: float | None = None
    raster_sha256: str | None = None
    rotation_deg: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.page_index, int) or isinstance(self.page_index, bool) or self.page_index < 0:
            raise EvidenceError(f"page_index must be a non-negative int, got {self.page_index!r}")
        if self.space not in COORDINATE_SPACES:
            raise EvidenceError(f"unknown coordinate space {self.space!r}; expected one of {COORDINATE_SPACES}")
        if not (_positive(self.width) and _positive(self.height)):
            raise MalformedGeometry(f"frame dimensions must be positive, got {self.width!r} x {self.height!r}")
        if self.rotation_deg not in _ROTATIONS:
            raise MalformedGeometry(f"rotation_deg must be one of {_ROTATIONS}, got {self.rotation_deg!r}")
        if self.space == PDF_POINT:
            if self.scale_x != 1.0 or self.scale_y != 1.0:
                raise MalformedGeometry("a pdf_point frame has scale exactly 1.0 on both axes")
            if any(v is not None for v in (self.raster_width_px, self.raster_height_px, self.dpi, self.raster_sha256)):
                raise MalformedGeometry("a pdf_point frame carries no raster fields")
            if self.pdf_width_pt is None or self.pdf_height_pt is None:
                object.__setattr__(self, "pdf_width_pt", float(self.width))
                object.__setattr__(self, "pdf_height_pt", float(self.height))
            if (float(self.pdf_width_pt), float(self.pdf_height_pt)) != (float(self.width), float(self.height)):
                raise MalformedGeometry("a pdf_point frame's width/height ARE its pdf dimensions")
            return
        # pixel space
        for name in ("raster_width_px", "raster_height_px"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise MalformedGeometry(f"a pixel frame requires a positive int {name}, got {value!r}")
        if (float(self.raster_width_px), float(self.raster_height_px)) != (float(self.width), float(self.height)):
            raise MalformedGeometry("a pixel frame's width/height ARE its raster dimensions")
        if not _positive(self.dpi):
            raise MalformedGeometry(f"a pixel frame requires a positive dpi, got {self.dpi!r}")
        if not (_positive(self.pdf_width_pt) and _positive(self.pdf_height_pt)):
            raise MalformedGeometry("a pixel frame requires the PDF page's dimensions in points")
        if not (_positive(self.scale_x) and _positive(self.scale_y)):
            raise MalformedGeometry("a pixel frame requires positive per-axis scales (px per pt)")
        expected = float(self.dpi) / POINTS_PER_INCH
        for name, scale, px, pt in (
            ("scale_x", self.scale_x, self.raster_width_px, self.pdf_width_pt),
            ("scale_y", self.scale_y, self.raster_height_px, self.pdf_height_pt),
        ):
            if abs(scale - expected) > SCALE_TOLERANCE * expected:
                raise MalformedGeometry(
                    f"{name}={scale!r} disagrees with dpi/72={expected!r} beyond {SCALE_TOLERANCE:.0%}"
                )
            derived = float(px) / float(pt)
            if abs(derived - scale) > SCALE_TOLERANCE * expected:
                raise MalformedGeometry(
                    f"{name}={scale!r} disagrees with raster/pdf ratio {derived!r} beyond {SCALE_TOLERANCE:.0%}"
                )
        if self.raster_sha256 is not None and not _is_sha256_hex(self.raster_sha256):
            raise EvidenceError("raster_sha256 must be a 64-character hex digest")

    @staticmethod
    def pixel(*, page_index: int, raster_width_px: int, raster_height_px: int, dpi: float,
              pdf_width_pt: float, pdf_height_pt: float, raster_sha256: str | None = None,
              rotation_deg: int = 0) -> "PageFrame":
        """The pixel frame for a raster of a PDF page; scales derived from the
        two dimension pairs (and then validated against dpi)."""
        return PageFrame(
            page_index=page_index, space=PIXEL,
            width=float(raster_width_px), height=float(raster_height_px),
            pdf_width_pt=float(pdf_width_pt), pdf_height_pt=float(pdf_height_pt),
            raster_width_px=int(raster_width_px), raster_height_px=int(raster_height_px),
            dpi=float(dpi), raster_sha256=raster_sha256, rotation_deg=rotation_deg,
            scale_x=float(raster_width_px) / float(pdf_width_pt),
            scale_y=float(raster_height_px) / float(pdf_height_pt),
        )

    @staticmethod
    def pdf_points(*, page_index: int, width_pt: float, height_pt: float, rotation_deg: int = 0) -> "PageFrame":
        return PageFrame(page_index=page_index, space=PDF_POINT, width=float(width_pt),
                         height=float(height_pt), pdf_width_pt=float(width_pt),
                         pdf_height_pt=float(height_pt), rotation_deg=rotation_deg)


def inside_frame(frame: PageFrame, x0: float, y0: float, x1: float, y1: float) -> bool:
    """THE bounds rule: is the box inside `[0, width] x [0, height]` of its
    frame (closed interval)? A `pixel` frame refuses a box for which this is
    false (a raster is a container); a `pdf_point` frame admits it and the
    native reader notes it (a page rect is a viewport). One function, two
    call sites, so the two can never disagree about "outside"."""
    return 0.0 <= x0 and x1 <= frame.width and 0.0 <= y0 and y1 <= frame.height


def to_pdf_points(frame: PageFrame, x: float, y: float) -> tuple[float, float]:
    """A point in `frame`'s space -> PDF points (same origin, same axes)."""
    if frame.space == PDF_POINT:
        return float(x), float(y)
    return float(x) / frame.scale_x, float(y) / frame.scale_y


def to_pixels(frame: PageFrame, x: float, y: float) -> tuple[float, float]:
    """A point in PDF points -> `frame`'s pixel space. Refuses on a pdf_point
    frame: there is no raster to map into, and inventing one is the error."""
    if frame.space != PIXEL:
        raise MalformedGeometry("to_pixels needs a pixel frame; a pdf_point frame has no raster")
    return float(x) * frame.scale_x, float(y) * frame.scale_y


# ---------------------------------------------------------------------------
# Words and lines
# ---------------------------------------------------------------------------

def word_id(page_index: int, line_ref: int | None, index: int) -> str:
    """`p{page}.l{line}.w{index}` — `l-` when the extractor gave no line."""
    line = "-" if line_ref is None else str(int(line_ref))
    return f"p{int(page_index)}.l{line}.w{int(index)}"


@dataclass(frozen=True)
class WordBox:
    """One word as the extractor read it, with its box in its page's space.

    `confidence` is an ANNOTATION copied from the extractor (a per-line score
    in PaddleOCR 3.7's case, so every word on a line shares it; `None` for
    native text, which has no such thing). Nothing in this package reads it;
    it exists so review surfaces and routing diagnostics can — and so the
    validator provably never does (CASE 7)."""

    word_id: str
    page_index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float | None = None
    line_ref: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise EvidenceError("a WordBox needs non-empty text; empty words are dropped by the adapter, never stored")
        for name in ("x0", "y0", "x1", "y1"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
                raise MalformedGeometry(f"{name} must be a finite number, got {value!r}")
            object.__setattr__(self, name, float(value))
        if not (self.x0 < self.x1 and self.y0 < self.y1):
            raise MalformedGeometry(
                f"inverted or degenerate box for {self.word_id}: "
                f"({self.x0}, {self.y0}, {self.x1}, {self.y1}) — refused, never swapped"
            )
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
                raise EvidenceError("confidence must be a number or None")
            if not (0.0 <= float(self.confidence) <= 1.0):
                raise EvidenceError(f"confidence out of [0, 1]: {self.confidence!r}")
            object.__setattr__(self, "confidence", float(self.confidence))
        if self.line_ref is not None and (isinstance(self.line_ref, bool) or not isinstance(self.line_ref, int) or self.line_ref < 0):
            raise EvidenceError("line_ref must be a non-negative int or None")

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class LineBox:
    """Words that share a visual baseline, left to right — DERIVED by
    `group_lines`, never taken from an extractor's own line breaks."""

    line_id: str
    page_index: int
    y_top: float
    y_bottom: float
    word_ids: tuple[str, ...]
    text: str


def _line_tolerance(words: Iterable[WordBox]) -> float:
    """Vertical-overlap tolerance from the page's OWN type size: 0.6 x the
    median word height, floored at one unit. Identical to the rule
    `analysis/structurer/geometry.py::_group_lines` has used since W3 (a
    statement set in 6pt and one set in 11pt are the same document class; a
    fixed threshold would work on one and merge two rows on the other).
    Unit-agnostic: heights are in the frame's own space."""
    heights = [word.height for word in words]
    return max(1.0, median(heights) * 0.6) if heights else 1.0


def group_lines(words: Iterable[WordBox], *, tolerance: float | None = None) -> tuple[LineBox, ...]:
    """Words -> visual lines by vertical overlap, THE one grouping rule.

    Deterministic: words are ordered by `(round(mid_y, 1), x0)`, a new line
    starts when a word's mid-y is more than `tolerance` from the previous
    word's, and each line's words are ordered by `x0`. `text` joins the words
    with single spaces. The algorithm is the one `geometry.py` already applied
    to native words; it is here so Paddle words and native words are grouped
    by the same code (D9, D1)."""
    ordered = sorted(words, key=lambda word: (round(word.mid_y, 1), word.x0))
    if not ordered:
        return ()
    pages = {word.page_index for word in ordered}
    if len(pages) != 1:
        raise MalformedGeometry(f"group_lines takes one page's words; got pages {sorted(pages)}")
    page_index = ordered[0].page_index
    limit = _line_tolerance(ordered) if tolerance is None else float(tolerance)

    rows: list[list[WordBox]] = [[ordered[0]]]
    for word in ordered[1:]:
        if abs(word.mid_y - rows[-1][-1].mid_y) <= limit:
            rows[-1].append(word)
        else:
            rows.append([word])

    lines: list[LineBox] = []
    for index, row in enumerate(rows):
        row.sort(key=lambda word: word.x0)
        lines.append(LineBox(
            line_id=f"p{page_index}.L{index}",
            page_index=page_index,
            y_top=min(word.y0 for word in row),
            y_bottom=max(word.y1 for word in row),
            word_ids=tuple(word.word_id for word in row),
            text=" ".join(word.text for word in row),
        ))
    return tuple(lines)


# ---------------------------------------------------------------------------
# Pages and documents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageEvidence:
    """One page: its frame, its words (extractor order), its derived lines,
    and the extractor's verbatim raw result (deep-frozen, hashed)."""

    frame: PageFrame
    words: tuple[WordBox, ...]
    lines: tuple[LineBox, ...] = ()
    raw: Mapping[str, Any] | None = None
    raw_sha256: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        words = tuple(self.words)
        object.__setattr__(self, "words", words)
        seen: set[str] = set()
        for word in words:
            if not isinstance(word, WordBox):
                raise EvidenceError("PageEvidence.words must hold WordBox instances")
            if word.page_index != self.frame.page_index:
                raise MalformedGeometry(
                    f"word {word.word_id} is on page {word.page_index} but the frame is page {self.frame.page_index}"
                )
            if word.word_id in seen:
                raise EvidenceError(f"duplicate word_id {word.word_id}")
            seen.add(word.word_id)
            # A `pixel` frame is a CONTAINER: a raster physically cannot hold
            # a box outside itself, so such a box is malformed by construction
            # and refuses the page. A `pdf_point` frame is a VIEWPORT (Phase
            # 2.2 closure ruling, option c): PDFs legitimately place text
            # outside `page.rect` — margin headers and footers, off-canvas
            # text — and the box is still a faithful record of where the word
            # is; the native reader keeps it verbatim and notes each such word
            # (`outside_frame:<word_id>`, plus a per-page count) so a consumer
            # can treat it as invisible-when-printed. Never clamped, never
            # dropped, never refused in `pdf_point` space. `inside_frame` is
            # the ONE bounds rule both this check and the reader's notes use.
            if self.frame.space == PIXEL and not inside_frame(self.frame, word.x0, word.y0, word.x1, word.y1):
                raise MalformedGeometry(
                    f"word {word.word_id} lies outside its raster "
                    f"({self.frame.width:.0f} x {self.frame.height:.0f}): "
                    f"({word.x0}, {word.y0}, {word.x1}, {word.y1})"
                )
        lines = tuple(self.lines) if self.lines else group_lines(words)
        object.__setattr__(self, "lines", lines)
        known = {word.word_id for word in words}
        for line in lines:
            if not isinstance(line, LineBox) or line.page_index != self.frame.page_index:
                raise EvidenceError("PageEvidence.lines must be this page's LineBox instances")
            missing = [wid for wid in line.word_ids if wid not in known]
            if missing:
                raise EvidenceError(f"line {line.line_id} references unknown words {missing}")
        if self.raw is not None:
            frozen = _freeze(self.raw)
            if not isinstance(frozen, Mapping):
                raise EvidenceError("raw evidence must be a mapping")
            object.__setattr__(self, "raw", frozen)
            digest = sha256_of_json(frozen)
            if self.raw_sha256 is None:
                object.__setattr__(self, "raw_sha256", digest)
            elif self.raw_sha256 != digest:
                raise EvidenceError("raw_sha256 does not match the raw evidence it claims to hash")
        elif self.raw_sha256 is not None:
            raise EvidenceError("raw_sha256 without raw evidence")
        object.__setattr__(self, "notes", tuple(str(note) for note in self.notes))

    @property
    def page_index(self) -> int:
        return self.frame.page_index

    def word(self, wid: str) -> WordBox:
        for word in self.words:
            if word.word_id == wid:
                return word
        raise KeyError(wid)


def page_text(page: PageEvidence) -> str:
    """The page as a reader sees it: one derived line per row, top to bottom,
    words left to right, single spaces — the string the intake ladder hands
    the validator for a Paddle page (D9). Never the extractor's own line
    breaks, never table markup, never a value the extractor did not read."""
    return "\n".join(line.text for line in page.lines)


@dataclass(frozen=True)
class ExtractionEvidence:
    """A whole document's evidence from ONE extractor, hashed.

    `runtime` is a mapping of provenance facts (versions, provider,
    execution class, GPU, settings-key material) — recorded verbatim, deep-
    frozen; this package attaches no meaning to its keys. `evidence_sha256`
    covers everything except itself and is what a cached copy must reproduce."""

    document_sha256: str
    extractor_id: str
    model_token: str
    pages: tuple[PageEvidence, ...]
    runtime: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = EVIDENCE_SCHEMA_VERSION
    evidence_sha256: str = ""

    def __post_init__(self) -> None:
        if not _is_sha256_hex(self.document_sha256):
            raise EvidenceError("document_sha256 must be a 64-character hex digest")
        if not isinstance(self.extractor_id, str) or not self.extractor_id.strip():
            raise EvidenceError("extractor_id is required")
        if not isinstance(self.model_token, str) or not self.model_token.strip():
            raise EvidenceError("model_token is required")
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise EvidenceError(
                f"evidence schema version {self.schema_version!r} is not {EVIDENCE_SCHEMA_VERSION}"
            )
        pages = tuple(self.pages)
        if not all(isinstance(page, PageEvidence) for page in pages):
            raise EvidenceError("ExtractionEvidence.pages must hold PageEvidence instances")
        indices = [page.page_index for page in pages]
        if indices != list(range(len(pages))):
            raise MalformedGeometry(f"pages must be contiguous from 0 in order; got indices {indices}")
        object.__setattr__(self, "pages", pages)
        object.__setattr__(self, "runtime", _freeze(dict(self.runtime)))
        digest = sha256_of_json(_document_payload(self, with_sha=False))
        if not self.evidence_sha256:
            object.__setattr__(self, "evidence_sha256", digest)
        elif self.evidence_sha256 != digest:
            raise EvidenceError("evidence_sha256 does not match the evidence it claims to hash")

    @property
    def word_count(self) -> int:
        return sum(len(page.words) for page in self.pages)

    def page_texts(self) -> list[str]:
        return [page_text(page) for page in self.pages]


# ---------------------------------------------------------------------------
# Serialization (deterministic; the sha reproduces across a round-trip)
# ---------------------------------------------------------------------------

def _frame_payload(frame: PageFrame) -> dict[str, Any]:
    return {f.name: getattr(frame, f.name) for f in fields(frame)}


def _word_payload(word: WordBox) -> dict[str, Any]:
    return {f.name: getattr(word, f.name) for f in fields(word)}


def _line_payload(line: LineBox) -> dict[str, Any]:
    payload = {f.name: getattr(line, f.name) for f in fields(line)}
    payload["word_ids"] = list(line.word_ids)
    return payload


def _page_payload(page: PageEvidence) -> dict[str, Any]:
    return {
        "frame": _frame_payload(page.frame),
        "words": [_word_payload(word) for word in page.words],
        "lines": [_line_payload(line) for line in page.lines],
        "raw": _thaw(page.raw),
        "raw_sha256": page.raw_sha256,
        "notes": list(page.notes),
    }


def _document_payload(evidence: ExtractionEvidence, *, with_sha: bool) -> dict[str, Any]:
    payload = {
        "schema_version": evidence.schema_version,
        "document_sha256": evidence.document_sha256,
        "extractor_id": evidence.extractor_id,
        "model_token": evidence.model_token,
        "runtime": _thaw(evidence.runtime),
        "pages": [_page_payload(page) for page in evidence.pages],
    }
    if with_sha:
        payload["evidence_sha256"] = evidence.evidence_sha256
    return payload


def to_json(evidence: ExtractionEvidence) -> dict[str, Any]:
    """A plain JSON-shaped dict (the artifact record's `document.evidence`)."""
    return _document_payload(evidence, with_sha=True)


def from_json(payload: Mapping[str, Any]) -> ExtractionEvidence:
    """The inverse of `to_json`. The rebuilt object re-derives every hash and
    refuses if the payload's `evidence_sha256` / `raw_sha256` do not
    reproduce — a cached copy that drifted is a finding, never served."""
    if not isinstance(payload, Mapping):
        raise EvidenceError("evidence payload must be a mapping")
    try:
        pages = tuple(
            PageEvidence(
                frame=PageFrame(**dict(page["frame"])),
                words=tuple(WordBox(**dict(word)) for word in page["words"]),
                lines=tuple(
                    LineBox(**{**dict(line), "word_ids": tuple(line["word_ids"])}) for line in page.get("lines", ())
                ),
                raw=page.get("raw"),
                raw_sha256=page.get("raw_sha256"),
                notes=tuple(page.get("notes", ())),
            )
            for page in payload["pages"]
        )
        return ExtractionEvidence(
            document_sha256=payload["document_sha256"],
            extractor_id=payload["extractor_id"],
            model_token=payload["model_token"],
            pages=pages,
            runtime=dict(payload.get("runtime") or {}),
            schema_version=int(payload.get("schema_version", -1)),
            evidence_sha256=str(payload.get("evidence_sha256") or ""),
        )
    except (KeyError, TypeError) as exc:
        raise EvidenceError(f"malformed evidence payload: {type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _positive(value: Any) -> bool:
    return (
        value is not None and not isinstance(value, bool)
        and isinstance(value, (int, float)) and value == value and value > 0
    )


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789ABCDEFabcdef" for c in value)


# `replace` is re-exported for callers that build a variant of a frozen object
# (a page with notes added) without reaching for dataclasses themselves.
replace = replace  # noqa: PLW0127 - deliberate re-export
