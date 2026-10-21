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
#: Structural / layout failure: the evidence is usable, but no registered
#: parser claimed it (or the structurer could not resolve it). Its only
#: sanctioned fallback is geometry / generalized reconstruction on the SAME
#: evidence (Phase 2.2) — never a second OCR engine.
B_STRUCTURE = "B"
#: Financial validation failure: a claimed reconstruction reached the
#: deterministic validator and failed its oracles. There is NO C -> OCR edge;
#: the only fallback is review or refuse.
C_VALIDATION = "C"
#: No failure: the document is `validated`, or no analysis stage has run for
#: it at all (deferred, invalid PDF, OCR failure) — there is nothing to
#: classify. A `validated` document is ALWAYS `NO_FAILURE`, regardless of
#: what the evidence gate would otherwise have said about the text that
#: produced it (P20-ROUTER review, BLOCK-1): the deterministic validator's
#: verdict is authoritative over a structural extraction-quality heuristic.
NO_FAILURE = ""

#: The complete FailureClass vocabulary, mirrored (and held equal by test) in
#: `telemetry.record.FAILURE_CLASSES`.
FAILURE_CLASSES: tuple[str, ...] = (A_EXTRACTION, B_STRUCTURE, C_VALIDATION, NO_FAILURE)


#: The retired research run mode's trigger (P22-TRUTHTABLE, Phase 2.2, D8).
#: Nothing supplies it since slice S5 of the model-code removal;
#: `discovery/runner.py::RESEARCH_TRIGGERS` keeps it by name so the report can
#: still count historical research rows, and telemetry's
#: `EXTRACTION_TRIGGERS` keeps it so those rows stay classifiable.
OPERATOR_FORCED_PADDLE = "operator_forced_paddle"


# ---------------------------------------------------------------------------
# Evidence quality: Class A, decided BEFORE reconstruction or validation.
# ---------------------------------------------------------------------------

#: Duplicated BY REFERENCE from `ocr/local_tesseract.py`'s own floor
#: (`TEXT_FLOOR_CHARS`, `< 200`) — the same number the extractor already enforces before it will
#: even return a document. Do not tune independently; if that floor changes,
#: this one changes with it.
CHAR_FLOOR = 200

#: **Advisory only — never admits a trigger** (P20-ROUTER review, MAJOR-2,
#: ruled 2026-09-01: "the alphanumeric-density criterion becomes
#: SURFACE-ONLY, exactly like Trigger T"). Measured 2026-09-01 over the
#: batch-9 run of record's 56 CLAIMED Tesseract reads (36 validated + 15
#: withheld + 5 review): the minimum alphanumeric-character density among
#: them is 0.7075
#: (min among the 36 validated alone: 0.7433).
#:
#: **Honest characterisation, not "never tuned."** This is a CORPUS-FITTED
#: threshold — a round number chosen 0.0075 below the observed minimum among
#: documents a parser happened to claim, not a property of unreadable text
#: independent of the sample. Composition analysis (the review's own
#: measurement) shows it keys on WHITESPACE SHARE, not noise: the 79
#: `validated`, `claimed` native documents whose density falls below this
#: floor have a median whitespace share of 0.321 against 0.157 for the
#: `validated` population above it, while punctuation/other share barely
#: moves (0.079 vs 0.061) — this is a wide-column / padded-tabular-layout
#: detector, not an extraction-failure detector. Reproduced fragility: moving
#: the floor anywhere in [0.20, 0.74] leaves the ENTIRE test suite, including
#: the corpus-marked slice, green (the escalation population moves from 13 to
#: 48 with every test passing); only above 0.7433 does the corpus pin fire,
#: and that pin runs only under `@pytest.mark.corpus`, deselected by default.
#:
#: For exactly these reasons it is now SURFACE-ONLY: `ExtractionQualityGate`
#: records whether a read falls below it in `EvidenceQuality.signals`
#: (never `.reasons`, never `.usable`), so the value and the population it
#: identifies (23 of the 123 U documents on the run of record) are visible
#: and measured, but nothing routes on it. Admitting it as a real trigger is
#: Phase 2.1's decision to make, and only with labelled evidence: a sample of
#: Tesseract reads a HUMAN has confirmed unreadable vs confirmed
#: readable-but-unparsed, with the criterion's error rate measured in BOTH
#: directions on that sample — not a threshold derived from the very
#: population it will be used to split.
#:
#: **The resulting split (0 admitted / 23 surfaced) is pinned in the
#: CORPUS-MARKED slice only** (`tests/test_escalation_router.py::
#: test_validated_tesseract_reads_are_never_classified_class_a`,
#: `@pytest.mark.corpus`), not in the default suite — stated plainly rather
#: than left implicit (P20-ROUTER re-review, closure 49fe3fe, MAJOR-4's
#: secondary point). Moving this floor to 0.20, 0.74 or even 0.75 leaves the
#: DEFAULT suite green either way: since the signal never sets `usable` or
#: admits a trigger (enforced independently, at both the gate and the
#: `discovery.runner` call site — see that module's `upgrade_triggers`), a
#: floor move can never change what escalates or what validates. It can only
#: change the SIZE of a measured, reported, non-routing population, which is
#: why a corpus-only pin — checked whenever the corpus-marked slice runs,
#: not on every commit — is the level of protection this constant needs: a
#: floor drift here is a measurement-honesty question, never a safety one.
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
    criteria named in `reasons` (no text produced, below the character
    floor, every page empty). `signals` carries advisory-only observations —
    today, only `BELOW_ALNUM_DENSITY_FLOOR` — that are measured and recorded
    but never move `usable` (P20-ROUTER review, MAJOR-2).
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

    **Scope (P20-ROUTER review, BLOCK-1).** This gate assesses ONLY evidence
    an EXTRACTOR produced (today: a local-Tesseract or visual-OCR read). A
    native PDF-text read, or a committed-artifact rung's cached markdown, is
    NOT extraction in this taxonomy's sense — it is either text the document
    already carried (usable by construction; an unclaimed native document is
    a layout problem, Class B, never a Class-A extraction failure) or a
    committed, already-claimed fixture. Callers (`discovery/runner.py`) must
    not call `assess` on those sources at all; `discovery.runner.GATE_ASSESSED_SOURCES`
    is the pinned list of source paths this gate may ever see, and
    `discovery.runner._evidence_for_row` is the one function allowed to
    decide which source gets a real assessment versus the "not assessed"
    default. `document is None` here means the RECOVERY shape specifically —
    the offline ladder, as a whole, produced no `StatementMarkdown` object at
    all — never "a read happened but wasn't kept" (a committed-artifact row
    has a markdown string with no `StatementMarkdown` object behind it, which
    is exactly why the caller must route it around this gate rather than
    calling `assess(None, ...)` on it).
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
