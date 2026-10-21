"""The failure-class vocabulary and the extraction-quality gate.

It holds:

* `FAILURE_CLASSES`, the closed A/B/C vocabulary a discovery row names its
  failure with (mirrored in `telemetry.record.FAILURE_CLASSES`);
* `OPERATOR_FORCED_PADDLE`, the retired research trigger that
  `discovery/runner.py::RESEARCH_TRIGGERS` keeps for the report's historical
  research table;
* `ExtractionQualityGate` and `EvidenceQuality`, which decide Class A from the
  produced text alone, before any parser or validator runs.

**Import boundary (pinned by `tests/test_escalation_tripwires.py`).** This
module imports nothing from `analysis`, `discovery`, `webapp` or `telemetry`:
it has no notion of a parser, a `Dispatch`, a reconciliation or a validator
outcome. `classify_failure` (A/B/C/"" from evidence + claimed + validated)
lives in `discovery/runner.py` for that reason.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# FailureClass: the closed vocabulary a document's disposition is named from.
# ---------------------------------------------------------------------------

#: Extraction failure: the produced evidence itself is unusable (empty, below
#: the character floor, or every page empty). Assigned by
#: `ExtractionQualityGate`, BEFORE reconstruction or financial validation ever
#: runs. Never assigned to a `validated` document — see
#: `discovery.runner.classify_failure`, which checks `validated` FIRST.
A_EXTRACTION = "A"
#: Structural / layout failure: the evidence is usable, but no registered parser
#: claimed it (or the structurer could not resolve it). Its only sanctioned
#: fallback is geometry / generalized reconstruction on the SAME evidence —
#: never a second OCR engine.
B_STRUCTURE = "B"
#: Financial validation failure: a claimed reconstruction reached the
#: deterministic validator and failed its oracles. There is NO C -> OCR edge;
#: the only fallback is review or refuse.
C_VALIDATION = "C"
#: No failure: the document is `validated`, or no analysis stage has run for it
#: at all (deferred, invalid PDF, OCR failure) — there is nothing to classify. A
#: `validated` document is ALWAYS `NO_FAILURE`, regardless of what the evidence
#: gate would otherwise have said about the text that produced it: the
#: deterministic validator's verdict is authoritative over a structural
#: extraction-quality heuristic.
NO_FAILURE = ""

#: The complete FailureClass vocabulary, mirrored (and held equal by test) in
#: `telemetry.record.FAILURE_CLASSES`.
FAILURE_CLASSES: tuple[str, ...] = (A_EXTRACTION, B_STRUCTURE, C_VALIDATION, NO_FAILURE)


#: The retired research run mode's trigger. Nothing supplies it; `discovery/runner.py::RESEARCH_TRIGGERS` keeps it
#: by name so the report can count historical research rows, and telemetry's `EXTRACTION_TRIGGERS` keeps it so those
#: rows stay classifiable.
OPERATOR_FORCED_PADDLE = "operator_forced_paddle"


# ---------------------------------------------------------------------------
# Evidence quality: Class A, decided BEFORE reconstruction or validation.
# ---------------------------------------------------------------------------

#: The same number as `ocr/local_tesseract.py`'s `TEXT_FLOOR_CHARS` (`< 200`), the floor the extractor already
#: enforces before it returns a document. Change the two together.
CHAR_FLOOR = 200

#: Advisory only: `ExtractionQualityGate` records a read below it in `EvidenceQuality.signals`, never in `.reasons`
#: or `.usable`, so nothing routes on it. It is corpus-fitted (a round number just below the lowest density among
#: claimed Tesseract reads) and keys on whitespace share, so it detects wide, padded tabular layouts rather than
#: failed extraction. Making it a real criterion needs a human-labelled sample of readable and unreadable reads.
#: `tests/test_escalation_router.py` pins that it is surfaced and never admitted, not its value.
ALNUM_DENSITY_FLOOR = 0.70

#: The advisory signal name `EvidenceQuality.signals` carries when a read's
#: alphanumeric density falls below `ALNUM_DENSITY_FLOOR`. Never a member of
#: `.reasons`, never a cause of `usable=False`.
BELOW_ALNUM_DENSITY_FLOOR = "below_alnum_density_floor"


@dataclass(frozen=True)
class EvidenceQuality:
    """Class-A evidence, decided from the produced text and the profile only.

    Never constructed from a `Dispatch`, a payload, or a validator verdict —
    only `ExtractionQualityGate.assess` builds one, and it never sees any of
    those.

    `usable` is decided EXCLUSIVELY by the three ADMITTED, parameter-free
    criteria named in `reasons` (no text produced, below the character floor,
    every page empty). `signals` carries advisory-only observations — today,
    only `BELOW_ALNUM_DENSITY_FLOOR` — that are measured and recorded but never
    move `usable`.
    """

    usable: bool
    reasons: tuple[str, ...]
    signals: tuple[str, ...]
    chars_total: int
    pages_empty: int
    pages_total: int


class ExtractionQualityGate:
    """Class A, decided BEFORE any parser or validator runs.

    Deterministic and structural: every criterion is named in `reasons` or
    `signals`, and the function of (document, profile) is pure — the same
    input always produces the same `EvidenceQuality`, and nothing here is
    randomised or time-dependent.

    **Scope.** This gate assesses ONLY evidence an EXTRACTOR produced (a
    local-Tesseract read, or a historical visual-OCR one). A native PDF-text read, or a
    committed-artifact rung's cached markdown, is NOT extraction in this taxonomy's
    sense — it is either text the document already carried (usable by construction; an
    unclaimed native document is a layout problem, Class B, never a Class-A extraction
    failure) or a committed, already-claimed fixture. Callers (`discovery/runner.py`)
    must not call `assess` on those sources at all;
    `discovery.runner.GATE_ASSESSED_SOURCES` is the pinned list of source paths this
    gate may ever see, and `discovery.runner._evidence_for_row` is the one function
    allowed to decide which source gets a real assessment versus the "not assessed"
    default. `document is None` here means the RECOVERY shape specifically — the
    offline ladder, as a whole, produced no `StatementMarkdown` object at all — never
    "a read happened but wasn't kept" (a committed-artifact row has a markdown string
    with no `StatementMarkdown` object behind it, which is exactly why the caller must
    route it around this gate rather than calling `assess(None, ...)` on it).
    """

    @staticmethod
    def assess(document, profile) -> EvidenceQuality:
        """`document` is the produced read (an object with a `.pages` list of
        page strings — a `StatementMarkdown` in production) or `None` when
        the offline ladder produced nothing at all (the recovery shape).
        `profile` is accepted for future criteria; today's read only the
        produced text."""
        del profile  # unused today; kept for interface symmetry / future criteria
        if document is None:
            return EvidenceQuality(
                usable=False, reasons=("no_text_produced",), signals=(),
                chars_total=0, pages_empty=0, pages_total=0,
            )
        pages = [str(page) for page in (getattr(document, "pages", None) or [])]
        pages_total = len(pages)
        page_chars = [len(page.strip()) for page in pages]
        chars_total = sum(page_chars)
        pages_empty = sum(1 for chars in page_chars if chars == 0)

        reasons: list[str] = []
        if chars_total < CHAR_FLOOR:
            reasons.append("below_char_floor")
        if pages_total > 0 and pages_empty == pages_total:
            reasons.append("all_pages_empty")

        signals: list[str] = []
        if chars_total > 0:
            alnum_total = sum(1 for page in pages for ch in page if ch.isalnum())
            if (alnum_total / chars_total) < ALNUM_DENSITY_FLOOR:
                signals.append(BELOW_ALNUM_DENSITY_FLOOR)

        return EvidenceQuality(
            usable=not reasons, reasons=tuple(reasons), signals=tuple(signals),
            chars_total=chars_total, pages_empty=pages_empty, pages_total=pages_total,
        )
