"""Phase 2.0 (P20-ROUTER): the closed failure-class vocabulary, the
independent `EscalationRouter`, and the `ExtractionQualityGate`.

**The invariant this module exists to make structural.** Validator success may
STOP escalation. Validator failure may NEVER START escalation. Only
pre-financial evidence — a document profile computed before any parser runs,
or the measured quality of an extractor's own output — may start an
extractor. There is no B (structural) -> OCR edge and no C (financial
validation) -> OCR edge, because neither B nor C produces any member of
`ADMITTED_TRIGGERS`: a structural "unclaimed" verdict and a failed financial
oracle are never inputs this module can see, let alone act on.

**Import boundary (structural, pinned by
`tests/test_escalation_tripwires.py`).** This module imports nothing from
`analysis`, `discovery`, `webapp` or `telemetry`. It has no notion of a
parser, a `Dispatch`, a `Statement`, a reconciliation, an ADB or a
`validated`/`review`/`withheld`/`failed` outcome. `RouterInputs` is a frozen
dataclass whose five fields are exactly `profile`, `evidence`, `triggers`,
`attempted` and `stop` — there is no field for a payload, a report, a
dispatch outcome, a reason, a parser id or any financial fact, so a caller
cannot smuggle a validator's verdict into the router even by accident: the
type has nowhere to put it.

`classify_failure` (A/B/C/"" from evidence + claimed + validated) lives in
`discovery/runner.py`, deliberately NOT here — it is the one function in this
story that is allowed to know what "claimed" and "validated" mean, and moving
it into this module would give the router a way to see the fact the whole
design keeps it blind to.

Phase 2.0 exclusions (do not implement here): no PaddleOCR id in
`EXTRACTOR_ORDER` (see the SLOT comment), no page-level routing, no Trigger T
routing (`TRUNCATION_FLAGGED` is defined and refused — OQ4), no network call,
no statement-specific hardcode of any kind.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# FailureClass: the closed vocabulary a document's disposition is named from.
# ---------------------------------------------------------------------------

#: Extraction failure: the produced evidence itself is unusable (empty, below
#: the character floor, or every page empty). Assigned by
#: `ExtractionQualityGate`, BEFORE reconstruction or financial validation ever
#: runs.
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
#: classify.
NO_FAILURE = ""

#: The complete FailureClass vocabulary, mirrored (and held equal by test) in
#: `telemetry.record.FAILURE_CLASSES`.
FAILURE_CLASSES: tuple[str, ...] = (A_EXTRACTION, B_STRUCTURE, C_VALIDATION, NO_FAILURE)


# ---------------------------------------------------------------------------
# ExtractionTrigger: the closed LEGAL start vocabulary.
# ---------------------------------------------------------------------------

#: The profile alone already says there is no text to read natively: either
#: the document classifies `scanned`, or it has zero native text characters
#: on any page. This is the trigger that justifies attempting OCR AT ALL
#: (recorded on the recovery path); it is never used to justify a SECOND OCR
#: read after the first one already produced text — see
#: `EXTRACTOR_OUTPUT_UNUSABLE` for that.
IMAGE_ONLY_DOCUMENT = "image_only_document"
#: The profile classifies `mixed`: some pages carry native text, some do not.
#: Recorded for measurement; in Phase 2.0 it is consumed only through the
#: document-level triggers above and below it, never as an independent
#: admission for a second read of already-produced text (page-level routing
#: is Phase 2.4, not this card).
MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT = "mixed_document_pages_without_native_text"
#: R: the offline ladder (native, then local Tesseract) produced no text at
#: all for this document. The recovery path's trigger.
OFFLINE_RUNGS_PRODUCED_NO_TEXT = "offline_rungs_produced_no_text"
#: U-extract: an extractor DID produce a read, but `ExtractionQualityGate`
#: refused it as unusable (empty, below the character floor, or every page
#: empty, or below the measured alphanumeric-density floor). The upgrade
#: path's ONLY trigger — deliberately never `dispatch.outcome != "claimed"`,
#: which is Class B wearing Class A's clothes (the defect this card exists to
#: close).
EXTRACTOR_OUTPUT_UNUSABLE = "extractor_output_unusable"
#: An extractor raised or otherwise failed transport (endpoint down, raster
#: failure) while the page remains unread. Defined for the closed vocabulary;
#: no Phase-2.0 call site names it yet (there is only one OCR extractor rung
#: after Tesseract today, and a raised exception there already fails the
#: document closed without a second rung to fall back to).
EXTRACTOR_FAILED = "extractor_failed"
#: An explicit, deliberate, per-document operator instruction (the webapp's
#: `force_ocr` flag) that predates and is independent of any specific
#: analysis failure. It is the SOLE trigger at exactly one call site
#: (`webapp/worker.py`'s deterministic force_ocr fallback), where the `stop`
#: rule below still refuses it the moment a parser has already claimed —
#: `stop` is checked BEFORE any trigger, so a claimed-but-financially-failed
#: document (Class C) can never reach this trigger regardless of the
#: operator's flag. It is also recorded (redundantly, alongside
#: `OFFLINE_RUNGS_PRODUCED_NO_TEXT`) on the discovery runner's RECOVERY path,
#: where `--scanned-visual` is itself the operator's mode choice. It is
#: deliberately NOT added to the discovery runner's UPGRADE trigger set: a
#: Tesseract-sourced document whose text is already USABLE (Class B) must
#: never escalate, and every one of the run of record's 123 unclaimed
#: Tesseract reads profiles `scanned` or `mixed` (`tools/phase2_trigger_split.py`)
#: — admitting a profile- or mode-level trigger on the upgrade path would
#: re-open exactly the edge this card closes. See the module docstring's
#: import-boundary note and the P20-ROUTER report for this reading of the
#: card.
OPERATOR_FORCED_VISUAL = "operator_forced_visual"
#: T: a known-truncated page. DEFINED here and REFUSED by the router
#: (`ADMITTED_TRIGGERS` excludes it) — its population is measured
#: (`tools/phase2_trigger_split.py`), never routed, per OQ4. Potential
#: admission is Phase 2.4, not this card.
TRUNCATION_FLAGGED = "truncation_flagged"

#: The complete ExtractionTrigger vocabulary, mirrored (and held equal by
#: test) in `telemetry.record.EXTRACTION_TRIGGERS`.
ALL_TRIGGERS: tuple[str, ...] = (
    IMAGE_ONLY_DOCUMENT,
    MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
    OFFLINE_RUNGS_PRODUCED_NO_TEXT,
    EXTRACTOR_OUTPUT_UNUSABLE,
    EXTRACTOR_FAILED,
    OPERATOR_FORCED_VISUAL,
    TRUNCATION_FLAGGED,
)

#: The subset of `ALL_TRIGGERS` the router will act on. `TRUNCATION_FLAGGED`
#: is the one member defined-but-refused (OQ4): it is a legal vocabulary
#: member so its population can be measured and recorded, but it is never a
#: legal START signal in Phase 2.0.
ADMITTED_TRIGGERS: frozenset[str] = frozenset(ALL_TRIGGERS) - {TRUNCATION_FLAGGED}

#: The fixed preference order among ALLOWED extractors — never a retry loop
#: driven by validation, a preference among extractors the router has
#: already admitted. SLOT for Phase 2.1 (OQ5): PaddleOCR joins this tuple
#: between "local_tesseract" and a future "unlimited_ocr" member; Phase 2.0
#: does not add it (exclusion).
EXTRACTOR_ORDER: tuple[str, ...] = ("local_tesseract", "visual")


# ---------------------------------------------------------------------------
# Evidence quality: Class A, decided BEFORE reconstruction or validation.
# ---------------------------------------------------------------------------

#: Duplicated BY REFERENCE from `ocr/local_tesseract.py`'s own floor (line 42,
#: `< 200`) — the same number the extractor already enforces before it will
#: even return a document. Do not tune independently; if that floor changes,
#: this one changes with it.
CHAR_FLOOR = 200

#: Measured 2026-09-01 over the batch-9 run of record's 56 CLAIMED Tesseract
#: reads (36 validated + 15 withheld + 5 review — every Tesseract read a
#: parser ever recognised, regardless of financial outcome):
#: `tools/phase2_trigger_split.py --densities` reports the minimum
#: alphanumeric-character density among them as 0.7075. This floor is a
#: ROUND NUMBER measured to sit strictly beneath that minimum, never tuned to
#: a target split size: a Tesseract read whose alphanumeric density falls
#: below what any statement a parser has ever claimed has measured is
#: presumptively OCR noise, not merely an unrecognised layout. It classifies
#: all 36 validated Tesseract reads as usable (min validated density 0.7433)
#: — the pin `tests/test_escalation_router.py` checks directly against the
#: cold cache.
ALNUM_DENSITY_FLOOR = 0.70


@dataclass(frozen=True)
class EvidenceQuality:
    """Class-A evidence, decided from the produced text and the profile only.

    Never constructed from a `Dispatch`, a payload, or a validator verdict —
    only `ExtractionQualityGate.assess` builds one, and it never sees any of
    those.
    """

    usable: bool
    reasons: tuple[str, ...]
    chars_total: int
    pages_empty: int
    pages_total: int


class ExtractionQualityGate:
    """Class A, decided BEFORE any parser or validator runs.

    Deterministic and structural: every criterion is named in `reasons`, and
    the function of (document, profile) is pure — the same input always
    produces the same `EvidenceQuality`, and nothing here is randomised or
    time-dependent.
    """

    @staticmethod
    def assess(document, profile) -> EvidenceQuality:
        """`document` is the produced read (an object with a `.pages` list of
        page strings — a `StatementMarkdown` in production) or `None` when
        nothing was produced at all. `profile` is accepted for interface
        symmetry with the router's other inputs; today's criteria read only
        the produced text, so it is otherwise unused here."""
        del profile  # unused today; kept for interface symmetry / future criteria
        if document is None:
            return EvidenceQuality(
                usable=False, reasons=("no_text_produced",),
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
        if chars_total > 0:
            alnum_total = sum(1 for page in pages for ch in page if ch.isalnum())
            if (alnum_total / chars_total) < ALNUM_DENSITY_FLOOR:
                reasons.append("below_alnum_density_floor")

        return EvidenceQuality(
            usable=not reasons, reasons=tuple(reasons),
            chars_total=chars_total, pages_empty=pages_empty, pages_total=pages_total,
        )


# ---------------------------------------------------------------------------
# RouterInputs / Escalation / EscalationRouter
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RouterInputs:
    """Everything the router is allowed to see. Nothing else.

    The field set is pinned by name in `tests/test_escalation_tripwires.py`:
    a new field (a `payload`, a `dispatch_outcome`, a `validated` bool) fails
    that pin. This is the type that makes "the validator whispers to the
    router" a compile-shape impossible, not merely a discipline nobody
    breaks.
    """

    profile: object
    evidence: EvidenceQuality
    triggers: frozenset[str]
    attempted: tuple[str, ...]
    stop: bool


def router_inputs(
    *, profile, evidence: EvidenceQuality, triggers: frozenset[str],
    attempted: tuple[str, ...], stop: bool,
) -> RouterInputs:
    """The ONE constructor every `decide()` call site must use.

    `tests/test_escalation_tripwires.py` finds every `decide(` call site in
    `discovery/` and `webapp/` by AST and asserts each one's `RouterInputs`
    argument was built by a call to this function — so a call site cannot
    hand-roll a `RouterInputs(...)` with a smuggled sixth positional value
    (the dataclass has none, but a hand-rolled call is also not the one
    reviewed, pinned constructor). Keyword-only, names pinned by this
    signature.
    """
    return RouterInputs(
        profile=profile, evidence=evidence, triggers=frozenset(triggers),
        attempted=tuple(attempted), stop=bool(stop),
    )


@dataclass(frozen=True)
class Escalation:
    """The router's verdict: which extractor (if any) may run next."""

    extractor: str | None
    trigger: str | None
    refused: tuple[str, ...]


class EscalationRouter:
    """The one authority that may name an extractor. Never a retry loop."""

    @staticmethod
    def decide(inputs: RouterInputs) -> Escalation:
        if inputs.stop:
            return Escalation(extractor=None, trigger=None, refused=("stopped_by_validated",))

        admitted = inputs.triggers & ADMITTED_TRIGGERS
        if not admitted:
            return Escalation(extractor=None, trigger=None, refused=("no_admitted_trigger",))

        remaining = [e for e in EXTRACTOR_ORDER if e not in inputs.attempted]
        if not remaining:
            return Escalation(
                extractor=None, trigger=None, refused=("no_allowed_extractor_remains",),
            )

        extractor = remaining[0]
        allowed, endpoint_refusal = _endpoint_policy_allows(extractor)
        if not allowed:
            return Escalation(extractor=None, trigger=None, refused=(endpoint_refusal,))

        # Deterministic trigger selection when more than one is admitted: the
        # first member of ALL_TRIGGERS' declared order that is present. This
        # is a REPORTING choice (which named cause goes on the row), not an
        # admission decision — admission already happened above.
        trigger = next((t for t in ALL_TRIGGERS if t in admitted), None)
        return Escalation(extractor=extractor, trigger=trigger, refused=())


def _endpoint_policy_allows(extractor: str) -> tuple[bool, str]:
    """Consult cell B2's endpoint allowlist, if it has composed yet.

    Import-guarded: `ocr/endpoint_policy.py` is cell B2's file and has not
    composed onto this branch's base. Until it exists, every allowed
    extractor passes through unchanged (Phase 2.0's baseline — the visual
    rung is local/$0 already, per the existing `ocr/config.py` /
    `ocr/ocr_client.py` seam). Once B2 composes, this becomes a real
    consultation of its policy.
    """
    try:
        from ocr.endpoint_policy import extractor_allowed  # type: ignore[import-not-found]
    except ImportError:
        return True, ""
    allowed, reason = extractor_allowed(extractor)
    return bool(allowed), (reason or "endpoint_policy_refused")
