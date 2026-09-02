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
type has nowhere to put it. `RouterInputs.__subclasses__() == []` is pinned
by test — a subclass that ADDS a field would still satisfy the field-name
check on the base class alone, which is why the pin also refuses subclassing.

`classify_failure` (A/B/C/"" from evidence + claimed + validated) lives in
`discovery/runner.py`, deliberately NOT here — it is the one function in this
story that is allowed to know what "claimed" and "validated" mean, and moving
it into this module would give the router a way to see the fact the whole
design keeps it blind to.

**Endpoint policy is enforced in exactly ONE place, and it is not here**
(P20-ROUTER review, MAJOR-1, ruled 2026-09-01). `ocr_client._build_client`
(cell B2) fails closed before any client object exists, so a refused or
unreachable endpoint surfaces as the visual rung's own transport failure
(`extractor_failed` at the vocabulary level; `ocr_failed`/`VISUAL_FAILED` on
the row) — never as a router refusal. `EscalationRouter.decide` picks an
extractor among the ones this module's OWN closed order already permits; it
does not itself judge whether a network endpoint is reachable, local, or
opted-in, because doing so would require it to know about `Settings`,
`base_url`s and `$0` policy — none of which belong in a module whose entire
job is staying blind to everything but a profile, a trigger set and an
evidence verdict. A prior revision of this module DID consult a guessed
`ocr.endpoint_policy` API here; it was fail-open on any contract mismatch
(an `ImportError` from importing the wrong name silently returned "allowed"),
and it was provably inert against cell B2's REAL, documented contract
(`docs/agent-handoffs/P20-SEAM.md`'s `check_endpoint`/`classify_endpoint`).
Removed rather than patched: the router has no way to know which contract B2
will ship, and a seam that can silently do nothing is worse than no seam.

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
#: refused it as unusable under one of its ADMITTED (parameter-free)
#: criteria: no text at all, below the character floor, or every page empty.
#: The upgrade path's ONLY trigger — deliberately never
#: `dispatch.outcome != "claimed"`, which is Class B wearing Class A's
#: clothes (the defect this card exists to close), and never the
#: alphanumeric-density SIGNAL (P20-ROUTER review, MAJOR-2 — see
#: `ALNUM_DENSITY_FLOOR` below; that signal is surfaced, never admitted).
EXTRACTOR_OUTPUT_UNUSABLE = "extractor_output_unusable"
#: An extractor raised or otherwise failed transport (endpoint down, raster
#: failure) while the page remains unread. Defined for the closed vocabulary;
#: no Phase-2.0 call site names it as a TRIGGER — a transport failure is
#: reported as the rung's own terminal failure (`VISUAL_FAILED`/`ocr_failed`),
#: not as a reason to try a different extractor, because there is only one
#: OCR extractor rung after Tesseract today.
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
#: card (the independent review's own reproduction, N1, confirms it: CASE 1
#: still kills the literal reading).
OPERATOR_FORCED_VISUAL = "operator_forced_visual"
#: T: a known-truncated page. DEFINED here and REFUSED by the router
#: (`ADMITTED_TRIGGERS` excludes it) — its population is measured
#: (`tools/phase2_trigger_split.py`), never routed, per OQ4. Potential
#: admission is Phase 2.4, not this card.
TRUNCATION_FLAGGED = "truncation_flagged"

#: The complete ExtractionTrigger vocabulary, mirrored (and held equal by
#: test) in `telemetry.record.EXTRACTION_TRIGGERS`. This is the vocabulary's
#: DECLARATION order — stable, documentation-facing — and is deliberately NOT
#: the order `EscalationRouter.decide` uses to pick which admitted trigger to
#: REPORT (see `TRIGGER_REPORT_PRIORITY`): a vocabulary's canonical order and
#: a reporting preference are different questions, and conflating them is
#: what made a recovery escalation report `image_only_document` instead of
#: `offline_rungs_produced_no_text` (P20-ROUTER review, MINOR-8).
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

#: When more than one admitted trigger is present, which one `decide` REPORTS
#: on the row (never which one is ADMITTED — that already happened). Ordered
#: most-specific-evidence first: a fact an EXTRACTOR observed about ITS OWN
#: output outranks a fact the PROFILE observed before any extractor ran,
#: which outranks the operator's blanket mode/flag permission. This is what
#: makes a recovery (evidence: nothing was produced at all) report
#: `offline_rungs_produced_no_text` rather than the co-occurring
#: `image_only_document` (P20-ROUTER review, MINOR-8).
TRIGGER_REPORT_PRIORITY: tuple[str, ...] = (
    OFFLINE_RUNGS_PRODUCED_NO_TEXT,
    EXTRACTOR_OUTPUT_UNUSABLE,
    EXTRACTOR_FAILED,
    IMAGE_ONLY_DOCUMENT,
    MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
    OPERATOR_FORCED_VISUAL,
    TRUNCATION_FLAGGED,
)

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

#: **Advisory only — never admits a trigger** (P20-ROUTER review, MAJOR-2,
#: ruled 2026-09-01: "the alphanumeric-density criterion becomes
#: SURFACE-ONLY, exactly like Trigger T"). Measured 2026-09-01 over the
#: batch-9 run of record's 56 CLAIMED Tesseract reads (36 validated + 15
#: withheld + 5 review): `tools/phase2_trigger_split.py --densities` reports
#: the minimum alphanumeric-character density among them as 0.7075
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
    but never move `usable` and never admit a router trigger (P20-ROUTER
    review, MAJOR-2).
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
        `profile` is accepted for interface symmetry with the router's other
        inputs; today's criteria read only the produced text, so it is
        otherwise unused here."""
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
    breaks. `RouterInputs.__subclasses__() == []` is pinned alongside the
    field set (P20-ROUTER review, MINOR-6): a subclass that ADDS a field and
    is accepted by `EscalationRouter.decide` (which only reads the five base
    attributes) would defeat the field pin without ever tripping it, since
    `__dataclass_fields__` on the SUBCLASS would include the base's five
    names plus its own — the base-class pin alone cannot see that shape.
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
    the ENTIRE repository (excluding this module and `tests/`) by AST and
    asserts each one's `RouterInputs` argument was built by a call to this
    function, that the set of call sites is exactly the three known ones, and
    that no `RouterInputs(` construction exists anywhere outside this module
    and the test tree — so a call site cannot hand-roll a `RouterInputs(...)`
    with a smuggled sixth positional value (the dataclass has none, but a
    hand-rolled call is also not the one reviewed, pinned constructor), and a
    new escalation call site anywhere in the codebase cannot go unnoticed
    (P20-ROUTER review, MINOR-6). Keyword-only, names pinned by this
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
    """The one authority that may name an extractor. Never a retry loop.

    Chooses AMONG extractors this module's own closed `EXTRACTOR_ORDER`
    already permits; it does not judge network endpoints, opt-in policy, or
    $0 status — that enforcement lives entirely in `ocr_client._build_client`
    (cell B2), which fails closed before any client object is constructed
    (see the module docstring's "Endpoint policy" section). A refused or
    unreachable endpoint therefore never reaches this class at all; it
    surfaces as the visual rung's own transport failure on the row.
    """

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

        # Deterministic trigger selection when more than one is admitted:
        # the most SPECIFIC one, per `TRIGGER_REPORT_PRIORITY` (evidence the
        # extractor itself produced, before a profile-level fact, before the
        # operator's blanket permission). A REPORTING choice (which named
        # cause goes on the row), not an admission decision — admission
        # already happened above.
        trigger = next((t for t in TRIGGER_REPORT_PRIORITY if t in admitted), None)
        return Escalation(extractor=extractor, trigger=trigger, refused=())
