"""Per-document discovery processing. Consumes merged platform pieces only.

Resolution is the **production intake ladder** (`ocr.pipeline.parse_statement`)
and nothing else. That is a binding ruling with a scar behind it: H-3's first
corpus anchor used the generic `parse_native_pdf_text` directly and silently
produced different markdown for four banks (Navy Federal, TD Canada, Wells,
Desjardins all have layout-specific readers that come first), which showed up
as five phantom failures. Discovery measures coverage; measuring it through a
different reader than production uses would make every number a fiction.

Offline by construction in every mode except `--scanned-visual`:

- `parse_mode="deterministic"` — the LLM extraction branch is unreachable, so
  no Gemini call can occur even in principle. TRUE IN EVERY MODE, including
  `--scanned-visual`: the visual rung reads pixels into markdown, it does not
  extract, and no paid vendor is reachable from any discovery mode.
- `allow_visual_ocr=False` — `ocr.pipeline` imports `ocr.ocr_client` lazily
  *inside* the visual rung, so in the offline modes the model client module is
  never even imported. A test asserts exactly that.
- Local Tesseract only in `--scanned` / `--scanned-visual`, never in tranche 0/1.

Documents the mode cannot read are RECORDED, never skipped: a scanned document
in an offline tranche is `deferred_scanned`, and a document that would need the
visual rung is `deferred_visual_ocr`.

The visual rung (W3-5, `--scanned-visual`)
------------------------------------------
`--scanned-visual` is the SAME production ladder with its last rung enabled: it
is `--scanned` plus the local Unlimited-OCR server (our own GPU, `$0` vendor).
Discovery's policy around it stays offline-first, and there are exactly two ways
a document reaches it:

1. **Recovery** — the offline rungs produced nothing at all. In `--scanned`
   that document is `deferred_visual_ocr`; here it gets the visual read.
2. **Upgrade** — the offline read came from local Tesseract and no parser
   claimed the text it produced (discovery class 5: a text-QUALITY failure, not
   a layout-knowledge one). The visual rung reads the same pages again and the
   result is adopted only if it actually claims. A NATIVE-text document that
   goes unclaimed is a layout problem and is never escalated — spending GPU time
   re-reading text we already have perfectly is the one thing this rung must
   not do.

Both paths call `parse_statement(force_ocr=True, allow_visual_ocr=True)`, which
is the same rung the webapp uses, through the same D-3 cache, with the same O-3
truncation assessment. The offline rungs are not re-run (they already ran, and
`force_ocr` is part of the cache key), so the two reads occupy two disjoint
cache partitions of the same bytes.

The deferral taxonomy does not soften: a document the visual rung ALSO cannot
serve stops being `deferred` and becomes an explicit terminal `failed` —
`ocr_failed` when the rung raised (server down mid-run: that document fails
closed, the run continues), and when it produced text nobody parsed, whichever
of `no_parser_matched` / `parser_declined` the dispatch earned. Nothing is lost
silently.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from analysis.payload_shape import (
    is_document_payload,
    payload_account_count,
    payload_accounts,
)
from analysis.pipeline import analyze_document
from analysis.serialization import document_report_to_dict
from corpus_artifacts import cached_markdown, cached_pages
from ocr.escalation import (
    ADMITTED_TRIGGERS,
    A_EXTRACTION,
    B_STRUCTURE,
    C_VALIDATION,
    EXTRACTOR_OUTPUT_UNUSABLE,
    IMAGE_ONLY_DOCUMENT,
    MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT,
    NO_FAILURE,
    OFFLINE_RUNGS_PRODUCED_NO_TEXT,
    OPERATOR_FORCED_VISUAL,
    Escalation,
    EscalationRouter,
    EvidenceQuality,
    ExtractionQualityGate,
    router_inputs,
)
from ocr.inspect import inspect_pdf
from telemetry import (
    DispatchCollector,
    EXTRACTION_TRIGGERS,
    FAILURE_CLASSES,
    StageTimer,
    build_record,
    dispatch_section,
    document_section,
    model_calls_for,
    reconstructed_claim,
    score_vector,
    source_path_for,
    source_section,
)

from .inventory import DedupIndex

MODE_PROFILE_ONLY = "profile-only"
MODE_DIGITAL = "digital"
MODE_SCANNED = "scanned"
MODE_SCANNED_VISUAL = "scanned-visual"
MODE_DRY_RUN = "dry-run"

#: Modes that run the local Tesseract rung.
LOCAL_OCR_MODES = frozenset({MODE_SCANNED, MODE_SCANNED_VISUAL})

#: What the visual rung did for one document. Row-level vocabulary (the
#: adjudication artifact); it reaches telemetry as `outcome.fallback_reason`
#: prefixed with `visual_ocr_`, which is an enum code like every other.
VISUAL_NOT_ATTEMPTED = "not_attempted"
VISUAL_RECOVERED = "recovered"      # offline rungs served nothing; visual did
VISUAL_UPGRADED = "upgraded"        # unclaimed Tesseract read replaced by a claim
VISUAL_NO_UPGRADE = "no_upgrade"    # escalation ran, did not claim; offline kept
VISUAL_FAILED = "failed"            # the rung raised (endpoint down/transport)

#: Committed OCR artifacts exist for the six image-only PINNED statements only.
#: They are what lets the dry run cover all 109 with zero OCR; no archive
#: document has one, so an archive scan defers instead.
ARTIFACT_CACHE = Path("tests/corpus_cache")

#: How this row's routing block (`parser_id`, `parser_score`,
#: `dispatch_outcome`, `candidates`) was established. The row projection is the
#: only writer, and the vocabulary exists so that a reader of `rows.csv` can
#: tell an OBSERVED verdict from a RECONSTRUCTED one without re-running
#: anything — the distinction the coverage metric was blind to on warm runs
#: (§DISCOBS; W3 #COUNTSP3).
#:
#: `""` is a fifth state and means the analysis stage never ran for this
#: document at all (deferred, invalid PDF, OCR failure): there is no routing
#: verdict to have a provenance.
PARSER_ID_LIVE_DISPATCH = "live_dispatch"
PARSER_ID_LIVE_DETECT = "live_detect"
PARSER_ID_UNAVAILABLE = "unavailable"


@dataclass
class DocumentRow:
    """One discovery row. Adjudication-grade, not telemetry-grade.

    This carries the relative path and folder label a human needs to act on a
    finding; it is written to a gitignored directory. Account identifiers are
    masked to last-4 and no transaction-level detail appears here at all.
    """

    relative_path: str
    folder_label: str
    content_sha256: str
    byte_size: int
    valid_pdf: bool = False
    encrypted: bool = False
    classification: str = "unknown"
    page_count: int = 0
    likely_account_count: int = 0
    dedup_status: str = "unique"
    duplicate_of: str | None = None
    source_path: str = "none"
    source_model: str | None = None
    truncated_pages: int = 0
    parser_id: str | None = None
    parser_score: float | None = None
    dispatch_outcome: str | None = None
    #: Provenance of the four fields above. See PARSER_ID_* above; empty when
    #: no analysis stage ran for this document.
    parser_id_source: str = ""
    candidates: list[str] = field(default_factory=list)
    #: Registrations that claimed this document and then declined to parse it
    #: (`Dispatch.attempted`). Bare ids, not `id:score` pairs: the declining
    #: parser's detection score is already in `candidates`, and what this
    #: column adds is the fact that it got as far as `parse` and returned None.
    #: A parser that raised is NOT here — that is `parser_exceptions`.
    attempted: list[str] = field(default_factory=list)
    near_miss: list[str] = field(default_factory=list)
    #: "<parser_id>:<stage>:<ExceptionClass>" per registration that raised.
    #: Registry ids and exception class names only — never a message (W3-1).
    parser_exceptions: list[str] = field(default_factory=list)
    outcome_class: str = "failed"
    outcome_reason: str = "not_processed"
    error_type: str | None = None
    statement_bank: str | None = None
    account_last4: str | None = None
    #: How many accounts the ANALYSIS published for this document — not
    #: `likely_account_count`, which is the OCR inspector's advisory count of
    #: number-shaped tokens and is consumed by nothing. L1-C18: on a document
    #: publishing several accounts `account_last4` is EMPTY and this column
    #: carries the fact, because a per-document field that can hold one
    #: account's value is left empty rather than filled from a chosen account.
    #: 0 when no payload was published at all, so "no analysis" and "one
    #: account" stay different facts.
    account_count: int = 0
    cache_ocr: str = "bypass"
    cache_analysis: str = "bypass"
    cache_visual: str = "bypass"
    visual_rung: str = "not_attempted"
    elapsed_ms: float = 0.0
    #: P20-ROUTER (Phase 2.0). Appended at the END so existing readers-by-name
    #: are unaffected. `failure_class` is `ocr.escalation.FailureClass`
    #: ("A"/"B"/"C"/""), computed by `classify_failure` below — never guessed,
    #: never touched by `ocr/escalation.py`, which sees no verdict at all.
    #: `escalation_trigger` is the `ExtractionTrigger` the router named when it
    #: admitted an extractor, or `""` when no router decision named one (no
    #: candidate was ever built, or the decision refused). `evidence_quality`
    #: is `usable`/`unusable`/`none` from `ExtractionQualityGate` — `none`
    #: means no read was ever produced to assess (invalid PDF, encrypted,
    #: deferred, profile-only). `escalation_refused` is the router's own
    #: refusal reasons, `"; "`-joined, recorded whenever a router decision was
    #: made and did not name an extractor.
    failure_class: str = ""
    escalation_trigger: str = ""
    evidence_quality: str = "none"
    escalation_refused: str = ""

    def as_dict(self) -> dict:
        # P20-ROUTER review, MAJOR-3. The closed vocabularies are enforced
        # HERE, at the row projection — the same pattern `classify_outcome`
        # uses for `DEFERRED_REASONS` (`telemetry/record.py`) — rather than
        # merely documented: a token from outside either tuple raises before
        # it ever reaches `rows.csv`. `escalation_trigger` additionally
        # allows `""`, its own default meaning "no router decision named a
        # trigger for this row".
        if self.failure_class not in FAILURE_CLASSES:
            raise ValueError(
                f"failure_class {self.failure_class!r} is not in the closed "
                f"vocabulary {FAILURE_CLASSES}"
            )
        if self.escalation_trigger and self.escalation_trigger not in EXTRACTION_TRIGGERS:
            raise ValueError(
                f"escalation_trigger {self.escalation_trigger!r} is not in the "
                f"closed vocabulary {EXTRACTION_TRIGGERS} (or '')"
            )
        row = asdict(self)
        row["candidates"] = "; ".join(self.candidates)
        row["attempted"] = "; ".join(self.attempted)
        row["near_miss"] = "; ".join(self.near_miss)
        row["parser_exceptions"] = "; ".join(self.parser_exceptions)
        return row


def classify_failure(
    evidence: EvidenceQuality, claimed: bool | None, validated: bool | None,
) -> str:
    """(FailureClass) for one document. Lives HERE, not in `ocr/escalation.py`.

    `ocr/escalation.py` never sees `claimed` or `validated` — that is the
    entire point of the import boundary its own tests pin. This function is
    the one place allowed to know what those words mean, and it is a pure
    fold over three already-computed facts: it does not call the router, does
    not look at a `Dispatch`, and cannot itself start an extractor.

    **Order (P20-ROUTER review, BLOCK-1 — `validated` is checked FIRST).** A
    document the deterministic validator proved `validated` is `NO_FAILURE`
    REGARDLESS of what an extraction-quality heuristic would otherwise have
    said about the text that produced it: the validator's verdict is
    authoritative over a structural evidence-quality signal, never the other
    way round. Only once a document is NOT validated does the evidence
    question even arise: unusable evidence is `A`; usable-but-unclaimed is
    `B`; usable, claimed, and still not validated is `C`.

    One deliberately UNCHANGED nuance, worth a note rather than a fix
    (P20-ROUTER review, MINOR-9): `claimed` here is `payload is not None`,
    and a parser that claims and then crashes downstream (`dispatch.outcome
    == "claimed"` but no payload survives) is therefore graded `B`
    (structure) rather than `C` (a claimed-but-invalid reconstruction). That
    is a parser DEFECT (W3-1), not a financial-validation failure, and the
    run of record's population for this shape is 0 — not worth widening the
    function's inputs for a case that has never occurred.
    """
    if validated:
        return NO_FAILURE
    if not evidence.usable:
        return A_EXTRACTION
    if not claimed:
        return B_STRUCTURE
    return C_VALIDATION


#: P20-ROUTER review, BLOCK-1. `ExtractionQualityGate` may assess ONLY
#: evidence an EXTRACTOR produced — a local-Tesseract or visual-OCR read.
#: A native PDF-text read is not an "extraction" in this taxonomy (an
#: unclaimed native document is Class B, a layout problem, never Class A —
#: the architecture's own words: "re-reading perfect text with a GPU cannot
#: invent a parser"), and a committed-artifact rung's cached markdown has no
#: `StatementMarkdown` object behind it at all (`document is None` there,
#: which the gate would otherwise — wrongly — read as "no text produced").
#: `_evidence_for_row` is the one function allowed to decide which source
#: gets a real assessment; every other source's row records
#: `evidence_quality="none"` and treats the evidence as usable BY
#: CONSTRUCTION for `classify_failure`'s purposes (a native/committed-
#: artifact document is never graded `A` — only `B`, `C`, or `""`).
GATE_ASSESSED_SOURCES: frozenset[str] = frozenset({"local_tesseract", "visual"})


def _evidence_for_row(document, profile, source_path: str) -> EvidenceQuality:
    """The row's `EvidenceQuality`, scoped to `GATE_ASSESSED_SOURCES`.

    `document` is whichever `StatementMarkdown` is currently of record (or
    `None` for the committed-artifact rung, which never has one). Only a
    genuinely OCR-sourced read is handed to the real gate; every other
    source is reported "usable by construction" — never assessed, never
    graded Class A — which is what keeps a validated native document, and
    every committed-artifact row, out of the extraction-failure vocabulary
    entirely.
    """
    if source_path in GATE_ASSESSED_SOURCES:
        return ExtractionQualityGate.assess(document, profile)
    return EvidenceQuality(
        usable=True, reasons=(), signals=(), chars_total=0, pages_empty=0, pages_total=0,
    )


def _profile_triggers(profile) -> frozenset[str]:
    """The profile-level triggers RECOVERY may record, from the O-1 preflight
    profile alone. Recorded ONLY on the recovery path, where the document
    genuinely produced no text at all (Class A is not in question) — never on
    the upgrade path, where a Tesseract read already exists: every one of the
    run of record's 123 unclaimed Tesseract reads profiles `scanned` or
    `mixed` (`tools/phase2_trigger_split.py`), so admitting a profile-level
    trigger there would let a Class-B (usable, unclaimed) document escalate
    on the strength of a fact that is equally true of every Tesseract read,
    claimed or not — exactly the edge this card closes. See
    `ocr.escalation.OPERATOR_FORCED_VISUAL`'s docstring for the same reasoning
    applied to the mode/operator trigger.
    """
    triggers: set[str] = set()
    if profile.classification == "scanned" or profile.native_text_total_chars == 0:
        triggers.add(IMAGE_ONLY_DOCUMENT)
    if profile.classification == "mixed":
        triggers.add(MIXED_DOCUMENT_PAGES_WITHOUT_NATIVE_TEXT)
    return frozenset(triggers)


def estimate_class_a_population(root: Path, relative_paths, disk_spelling=None) -> int:
    """A cheap, PRE-RUN upper bound on how many documents this run could ever
    legally escalate — read-only preflight profiling, no OCR, no analysis.

    The predicate is LITERALLY the router's own admission test —
    `_profile_triggers(profile) & ADMITTED_TRIGGERS` — not a hand-written
    approximation of it (P20-ROUTER review, MINOR-7: a duplicated predicate
    is how the two silently drifted apart; a zero-page, valid, unencrypted
    PDF profiles `classification="unknown"` with `native_text_total_chars ==
    0`, which `_profile_triggers` already admits via `IMAGE_ONLY_DOCUMENT`
    but the old hand-written `classification in ("scanned", "mixed")` check
    missed entirely). A `digital` profile's native rung always succeeds, so
    it never reaches the router and is correctly never counted.

    An unreadable file counts TOWARD the ceiling rather than being skipped —
    a transient read error (this host's OneDrive `PermissionError`s are a
    documented recurring case) must never SILENTLY LOWER a safety ceiling;
    the safe failure direction for an estimate that exists to bound GPU
    spend is to over-count, never to under-count.
    """
    count = 0
    for relative_path in relative_paths:
        path = root / (disk_spelling(relative_path) if disk_spelling else relative_path)
        try:
            raw = path.read_bytes()
        except OSError:
            count += 1
            continue
        profile = inspect_pdf(raw)
        if _profile_triggers(profile) & ADMITTED_TRIGGERS:
            count += 1
    return count


def _mask_last4(value: str | None) -> str | None:
    """Account identifiers appear as last-4 or not at all."""
    if not value:
        return None
    digits = [character for character in str(value) if character.isalnum()]
    return "".join(digits[-4:]) if len(digits) >= 4 else "".join(digits)


def _fmt(pairs) -> list[str]:
    return [f"{identifier}:{score:g}" for identifier, score in pairs]


def _project_accounts(row: "DocumentRow", payload: dict) -> None:
    """The row's two Statement-derived columns, plus how many accounts published.

    L1-C18. `account_last4` is the column by which a person identifies a
    document, and on a document publishing several accounts there is no value
    that column can honestly hold: filling it from the FIRST account is the
    forbidden selection wearing printed order as a disguise, and it would put
    the L-1 defect back into the discovery row after the payload had it
    removed. So it is left EMPTY and `account_count` carries the fact.

    `statement_bank` is the DOCUMENT's issuer, which every published section of
    one member statement shares. A document whose accounts disagree about it is
    not one statement, and the row refuses rather than picking one. The refusal
    propagates out of `process`, which is the right loudness for a payload no
    publisher in this tree can build: a run that met one would stop rather than
    file a row naming an issuer it chose.
    """
    if not is_document_payload(payload):
        statement = payload.get("statement") or {}
        row.statement_bank = statement.get("bank")
        row.account_last4 = _mask_last4(statement.get("account_number"))
        row.account_count = 1
        return
    surface = "discovery/runner.py::_project_accounts"
    accounts = payload_accounts(payload, surface=surface)
    row.account_count = payload_account_count(payload, surface=surface)
    row.account_last4 = None
    banks = {(account.get("statement") or {}).get("bank") for account in accounts}
    if len(banks) != 1:
        raise ValueError(
            "the accounts of one document name different issuers; a member "
            "statement's sections share an issuer, so this is not one "
            "document (document_accounts_disagree_on_issuer)"
        )
    row.statement_bank = banks.pop()


def _project_identity(row: "DocumentRow", scores, payload: dict) -> str:
    """Fill a cache-served row's routing block. Returns the provenance mark.

    THE HOLE THIS CLOSES. On a D-3 analysis cache hit `analyze_markdown` never
    runs, so no `Dispatch` is observed and the row carried no `parser_id` and
    no `dispatch_outcome` at all. The report then excluded the document from
    the coverage denominator entirely (`dispatch_cached`), which is honest but
    blind: on the warm re-runs that are now normal, hundreds of correctly
    parsed statements were invisible to every parser-keyed rollup, and
    COUNTS-P3's counterfactual denominators were short by exactly that set
    (W3 #COUNTSP3). "Family populations from `rows.csv` alone" became a
    standing prohibition because of it.

    SURVEY: what the cached payload actually holds. The answer is that parser
    identity is **genuinely absent** from it, so it cannot be read out:

    * ``payload["detection"]`` is `analysis.detect.DetectionResult` — funders,
      potential lenders, insurance providers, recurring debits. It is the
      *financial* detection layer and says nothing about which parser routed
      the document. The name collision with parser detection is the trap here.
    * ``payload["model_used"]`` is ``f"{bank_label}-deterministic"`` built from
      the extracted `Statement.bank` (`analysis/pipeline.py`), so it is a BANK
      label, lower-cased and hyphenated — not a parser id, and not unique to
      one: several registrations share a bank label, and the honest-unknown-
      issuer registrations publish `bank=None`, which renders as the literal
      `"bank-deterministic"`.
    * ``payload["statement"]["bank"]`` is that same extracted label; the row
      already carries it as `statement_bank`.
    * ``payload["quality"]`` / ``payload["integrity"]`` carry flags and notes.
      A parser's identity reaches them only as English prose inside a note,
      which is not an identity.

    So the identity is RE-RESOLVED live, from the detection sweep the row
    already pays for (`score_vector`, 1.8-11.7 ms/document, and cheaper still
    since DETECT-BUDGET), and the result is MARKED `live_detect` rather than
    passed off as an observation.

    WHY ONE DETECTION SWEEP IS ENOUGH TO NAME THE PARSER. Discovery analyses in
    `parse_mode="deterministic"`, and in that mode `analyze_markdown` produces
    a payload on exactly one path: a claiming parser returned a statement.
    Every other `resolve` outcome raises before a payload exists — `ambiguous`
    (AmbiguousParserError), `parser_exception` (ParserCrashError), `unclaimed`
    (RuntimeError). And `resolve` declares `ambiguous` whenever more than one
    registration survives `supersedes` pruning, BEFORE any parse runs. So a
    cached payload is itself the evidence that the sweep had exactly one
    survivor and that its `parse` succeeded: the survivor is the parser of
    record, `attempted` was empty, and the outcome was `claimed`. Nothing is
    guessed.

    FAIL-CLOSED, twice. The generic structurer (W3-3c, opt-in, off) is the one
    branch that can publish a payload with no parser behind it, so a
    structurer payload projects nothing. And if the sweep does NOT name exactly
    one survivor while a payload exists, this refuses to name a parser rather
    than pick one. Both cases mark `unavailable`, which is a finding, not a
    blank.

    WHAT THE FAIL-CLOSED BRANCH DID NOT CATCH, kept as history because the
    honest version of this argument is narrower than the tidy one. The
    reasoning above holds *within one registry composition*. Through batch 5
    it did not hold across a registry change that a warm cache outlived:
    `webapp/artifact_cache.py` stated the rule ("bump ANALYSIS_STAGE_VERSION
    in the same commit"), but the wave process COMPOSES the bump at merge, so
    mid-wave commits that added `supersedes` edges shipped without one.
    Inside such a window a cached payload could have been authored by a
    parser that TODAY loses a supersedes contest - and today's sweep then
    named exactly one survivor, the new winner, confidently and wrongly. One
    survivor is not a symptom here, so `unavailable` never fired; only the
    zero-survivor and multi-survivor shapes reach it.

    CLOSED in batch 6 by REGFP (W3 §REGFP): `analysis_settings_key` now
    carries `registry_fingerprint()` - a digest of the registry's key
    material (ids, banks, bands, supersedes edges, markers, callables) - so a
    registry change rotates the analysis cache by construction and no cached
    payload can outlive the composition that authored it. The inherited
    stale-cache shape above is therefore unreachable; the paragraph stays so
    the next reader knows why the settings key carries the fingerprint.

    NOT reconstructed, deliberately: `parser_exceptions`. A detect-stage crash
    in some *other* registration is part of the observed `Dispatch` and is not
    recoverable from a score vector (a crashed detect scores 0.0 and 0.0 is
    dropped), so the column stays empty and says nothing rather than saying
    "no parser crashed". `attempted` is empty because the reasoning above
    proves it was.

    ONE DERIVATION, TWO ARTIFACTS (#TELCOV). The claimant reasoning and its
    fail-closed guards moved to `telemetry.collect.reconstructed_claim` when
    the H-3 record became the second consumer of them. This function is now the
    row's half — the `PARSER_ID_*` vocabulary and the fields it fills — over a
    shared answer, so `rows.csv` and `telemetry.jsonl` cannot name different
    parsers for the same document. `reconstructed_claim` also adds a guard this
    one did not need: the payload must carry a deterministic `model_used`.
    Discovery analyses in `parse_mode="deterministic"`, where every payload is
    a parser's or the structurer's, so that guard changes no discovery row —
    it is what makes the same function safe for `batch.py` and the webapp,
    which run `parse_mode="auto"`.
    """
    claim = reconstructed_claim(scores, payload)
    if claim is None:
        return PARSER_ID_UNAVAILABLE
    parser_id, score = claim
    row.parser_id = parser_id
    row.parser_score = score
    row.dispatch_outcome = "claimed"
    row.candidates = _fmt([claim])
    return PARSER_ID_LIVE_DETECT


class DiscoveryRunner:
    """Processes documents one at a time; owns no routing decisions of its own."""

    _last_ocr_cached = False
    _last_visual_cached = False

    def __init__(
        self,
        root: Path,
        *,
        mode: str,
        run_id: str,
        sink=None,
        cache=None,
        dedup: DedupIndex | None = None,
        visual_escalation: bool = True,
        escalation_budget: int | None = None,
    ) -> None:
        self.root = root
        self.mode = mode
        self.run_id = run_id
        self.sink = sink
        self.cache = cache
        self.dedup = dedup if dedup is not None else DedupIndex.with_pinned_corpus()
        self.allow_local_ocr = mode in LOCAL_OCR_MODES
        self.allow_visual_ocr = mode == MODE_SCANNED_VISUAL
        # Escalation is a policy knob ON TOP of the rung: `--no-visual-escalation`
        # recovers the documents nothing could read without spending GPU time
        # re-reading Tesseract output.
        self.visual_escalation = bool(visual_escalation) and self.allow_visual_ocr
        self.allow_artifacts = mode == MODE_DRY_RUN
        #: P20-ROUTER item 2f. `None` (the default) is UNBOUNDED — every
        #: existing caller that constructs a `DiscoveryRunner` directly
        #: (every test in this tree, `discovery/cli.py` before it opts in)
        #: keeps its exact historical behaviour. `discovery/cli.py::run()`
        #: sets this from `estimate_class_a_population` before processing a
        #: `--scanned-visual` run, and `process()` REFUSES to escalate past
        #: it — a safety valve on top of the router, never a substitute for
        #: it (the router's own admission rules still apply first).
        self.escalation_budget = escalation_budget
        self.escalations_used = 0

    # -- resolution ---------------------------------------------------------

    def _read(self, raw: bytes, source_file: str, profile):
        """(document, markdown, sheets, note). Production ladder, offline rungs only.

        `sheets` is the intake object's own page list, carried out beside the
        markdown because `analyze_markdown` needs it and it cannot be recovered
        from the string (W3 §PIPEFIX P4b.1). On the committed-artifact rung
        there is no intake object, so it comes from the artifact's committed
        page list — the other half of the same artifact — and is None when that
        artifact has none, which fail-closes the page-declaration check exactly
        as an unwired caller would.

        Served through D-3's content-addressed cache, so identical bytes under
        identical settings are never re-read across tranches or re-runs. The
        cache is keyed on content + settings, and `allow_visual_ocr=False` is
        part of that key, so a tranche-1 miss cannot be served a tranche-2
        artifact or vice versa.
        """
        from ocr.pipeline import parse_statement

        def compute():
            return parse_statement(
                raw,
                source_file=source_file,
                profile=profile,
                force_ocr=False,
                allow_local_ocr=self.allow_local_ocr,
                allow_visual_ocr=False,   # never: no model client is constructed
            )

        if self.cache is None:
            document, cached = compute(), False
        else:
            from webapp.artifact_cache import cached_ocr

            result = cached_ocr(
                raw,
                compute=compute,
                cache=self.cache,
                source_file=source_file,
                content_hash=profile.content_sha256,
                force_ocr=False,
                allow_local_ocr=self.allow_local_ocr,
                allow_visual_ocr=False,
            )
            document, cached = result.value, result.cached
        self._last_ocr_cached = cached
        if document is not None:
            return document, document.to_markdown(), list(document.pages), None
        if self.allow_artifacts:
            markdown = cached_markdown(raw, ARTIFACT_CACHE)
            if markdown is not None:
                return None, markdown, cached_pages(raw, ARTIFACT_CACHE), "committed_artifact"
        return None, None, None, (
            "deferred_scanned" if self.allow_local_ocr else "deferred_offline_rungs"
        )

    def _read_visual(self, raw: bytes, source_file: str, profile):
        """(document, markdown, error_type). The visual rung, cached, fail-closed.

        `force_ocr=True` goes straight to the visual rung: the offline rungs
        either already ran on this document or provably cannot serve it, and
        re-running them would only burn time. It is also what keeps this read in
        its own D-3 partition — `force_ocr`, `allow_local_ocr` and
        `allow_visual_ocr` are all cache-key material, as are the visual service
        knobs (`ocr_model`, `ocr_base_url`, `ngram_size`, `window_size`,
        `dpi`, `fallback_dpi`), so a visual artifact can never be served for an
        offline read or across a model/endpoint change.

        The endpoint can die mid-run. `ocr_page` retries and then re-raises, so
        that exception is caught HERE and returned as an error type: this
        document fails closed and the run continues. A failure is never cached —
        `cached_ocr` only stores what `compute` returned.
        """
        from ocr.pipeline import parse_statement

        def compute():
            return parse_statement(
                raw,
                source_file=source_file,
                profile=profile,
                force_ocr=True,
                allow_local_ocr=False,
                allow_visual_ocr=True,
            )

        try:
            if self.cache is None:
                document, cached = compute(), False
            else:
                from webapp.artifact_cache import cached_ocr

                result = cached_ocr(
                    raw,
                    compute=compute,
                    cache=self.cache,
                    source_file=source_file,
                    content_hash=profile.content_sha256,
                    force_ocr=True,
                    allow_local_ocr=False,
                    allow_visual_ocr=True,
                )
                document, cached = result.value, result.cached
        except Exception as exc:
            self._last_visual_cached = False
            return None, None, type(exc).__name__
        self._last_visual_cached = cached
        if document is None:
            return None, None, None
        return document, document.to_markdown(), None

    def _analyse(self, markdown: str, collector, sheets=None):
        """(payload, error_type, cached). Deterministic mode; never raises.

        `sheets` is the intake object's page list for the markdown being
        analysed, and it goes to BOTH the analysis and the cache: it is part of
        the analysis input hash, so handing the cache one partition and the
        pipeline another would store an answer under a key that does not
        describe it. None fail-closes, exactly as this call site did before the
        page-declaration check was activated.
        """
        def analyse():
            return document_report_to_dict(analyze_document(
                markdown, parse_mode="deterministic", on_dispatch=collector,
                sheets=sheets,
            ))

        try:
            if self.cache is None:
                return analyse(), None, False
            from webapp.artifact_cache import cached_analysis

            result = cached_analysis(
                markdown, compute=analyse, cache=self.cache,
                parse_mode="deterministic", sheets=sheets,
            )
            return result.value, None, result.cached
        except Exception as exc:
            return None, type(exc).__name__, False

    def _upgrade_eligible(self, collector, payload) -> bool:
        """Is this document even a CANDIDATE for the upgrade path?

        This is the historical `_needs_visual_upgrade` gate, narrowed to
        exactly the exclusions it always encoded (the caller has already
        confirmed `visual_escalation`, a live document, and a Tesseract
        source — see `process()`):

        * **A live dispatch only.** On a D-3 analysis cache hit no dispatch
          exists this run; guessing "unclaimed" there would escalate the
          entire archive on every re-run. A cached payload means it analysed
          fine.
        * **Not for parser crashes.** A claimed document whose parser then
          threw is a parser defect (W3-1), not an OCR one, so it is left
          alone regardless of what the extraction-quality gate said about its
          text.

        Being a CANDIDATE is necessary but not sufficient: whether an
        extractor actually runs is the router's `Escalation`, computed from
        the offline read alone (`process()`'s `upgrade_candidate`) — a
        Class-B (usable, unclaimed) candidate reaches this gate and is still
        refused, because the router never admitted a trigger for it.
        """
        if collector.seen:
            return collector.dispatch.outcome != "claimed"
        return payload is None

    def _apply_budget(self, decision: Escalation) -> Escalation:
        """The run's own pre-computed Class-A trigger population is a ceiling
        ON TOP of the router's admission rules, never a substitute for them:
        this only ever NARROWS a decision that already named an extractor,
        and it narrows it to `None` rather than silently keeping the original
        (a refused escalation is a named, recorded finding — see
        `estimate_class_a_population` and `escalation_budget` above).
        """
        if decision.extractor is None:
            return decision
        if self.escalation_budget is not None and self.escalations_used >= self.escalation_budget:
            return Escalation(
                extractor=None, trigger=decision.trigger,
                refused=("escalation_budget_exhausted",),
            )
        self.escalations_used += 1
        return decision

    # -- one document -------------------------------------------------------

    def process(
        self, relative_path: str, folder_label: str,
        *, disk_relative_path: str | None = None,
    ) -> DocumentRow:
        # relative_path is the document's IDENTITY (manifest spelling, from
        # enumerate_root); disk_relative_path is where the bytes actually live
        # when a case-insensitive filesystem kept a different casing
        # (Inventory.disk_spelling). Only the read uses the disk spelling.
        started = time.perf_counter()
        path = self.root / (disk_relative_path or relative_path)
        raw = path.read_bytes()
        timer, collector = StageTimer(), DispatchCollector()

        with timer.time("preflight"):
            profile = inspect_pdf(raw)

        row = DocumentRow(
            relative_path=relative_path,
            folder_label=folder_label,
            content_sha256=profile.content_sha256,
            byte_size=len(raw),
            valid_pdf=profile.valid_pdf,
            encrypted=profile.encrypted,
            classification=profile.classification,
            page_count=profile.page_count,
            likely_account_count=profile.likely_account_count,
        )
        status, first_seen = self.dedup.classify(profile.content_sha256, relative_path)
        row.dedup_status, row.duplicate_of = status, first_seen

        if self.mode == MODE_PROFILE_ONLY:
            row.outcome_class, row.outcome_reason = "deferred", "profile_only"
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        if not profile.valid_pdf or profile.encrypted:
            row.outcome_class = "failed"
            row.outcome_reason = "encrypted" if profile.encrypted else "invalid_pdf"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_reason=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        name = Path(relative_path).name
        with timer.time("ocr"):
            document, markdown, sheets, note = self._read(raw, name, profile)

        if markdown is None and not self.allow_visual_ocr:
            # Recorded, never skipped: real work this tranche deliberately did
            # not do. `deferred` is its own outcome class precisely so that
            # `failed` can keep meaning "attempted and errored" — the two are
            # different findings and DSC-2 acts on them differently.
            row.outcome_class = "deferred"
            row.outcome_reason = (
                "deferred_scanned" if note == "deferred_offline_rungs" else "deferred_visual_ocr"
            )
            row.source_path = "none"
            self._emit(row, profile, None, None, None, collector, timer,
                       deferred=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        if markdown is None:
            # RECOVERY: exactly the `deferred_visual_ocr` class of tranche 2.
            # The mode exists to attempt these, so from here on the document can
            # no longer be deferred — it either reads or it fails, explicitly.
            #
            # P20-ROUTER. The offline ladder produced NOTHING (`document` is
            # `None`), which is unambiguously Class A — `EvidenceQuality` for
            # "no text produced" is unusable by construction, so this is the
            # one call site that never needs the gate's other criteria. The
            # router still decides, rather than the runner assuming, because
            # it is also where the escalation-budget ceiling and the (today
            # unreachable, structurally guarded) "visual already attempted"
            # refusal live.
            recovery_evidence = ExtractionQualityGate.assess(None, profile)
            recovery_triggers = (
                frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT, OPERATOR_FORCED_VISUAL})
                | _profile_triggers(profile)
            )
            # `attempted=()` when `allow_local_ocr` is False would let `decide`
            # name `local_tesseract` here — unreachable today, because every
            # mode `visual_escalation` can be true in also has
            # `allow_local_ocr=True` (`MODE_SCANNED_VISUAL in LOCAL_OCR_MODES`)
            # — but worth naming: that shape would still fail CLOSED (the
            # `!= "visual"` check below writes a terminal `escalation_refused`
            # row rather than reading Tesseract pixels it was never asked to
            # read), never open (P20-ROUTER review, MINOR-9).
            recovery_decision = self._apply_budget(EscalationRouter.decide(router_inputs(
                profile=profile, evidence=recovery_evidence, triggers=recovery_triggers,
                attempted=("local_tesseract",) if self.allow_local_ocr else (),
                stop=False,
            )))
            row.escalation_trigger = recovery_decision.trigger or ""
            row.escalation_refused = "; ".join(recovery_decision.refused)
            if recovery_decision.extractor != "visual":
                # Refused (today only reachable via an exhausted budget): an
                # explicit terminal failure, never a silent loss, exactly like
                # a genuine OCR transport failure below.
                #
                # P20-ROUTER re-review, closure 49fe3fe, MINOR-11.
                # `row.source_path` becomes `"none"` two lines below, which is
                # NOT in `GATE_ASSESSED_SOURCES` — so `evidence_quality` is
                # `"none"` here too, matching every other `source_path="none"`
                # row and keeping `GATE_ASSESSED_SOURCES` the honest single
                # answer to "which rows ever carry usable/unusable" (the
                # gate's own verdict, `recovery_evidence`, is still the one
                # `EscalationRouter.decide` acted on above — this only
                # changes what the ROW reports, not the decision already
                # made).
                row.evidence_quality = "none"
                row.visual_rung = VISUAL_NOT_ATTEMPTED
                row.outcome_class, row.outcome_reason = "failed", "escalation_refused"
                row.source_path = "none"
                self._emit(row, profile, None, None, None, collector, timer,
                           error_reason="escalation_refused")
                row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                return row
            with timer.time("visual_ocr"):
                document, markdown, visual_error = self._read_visual(raw, name, profile)
            sheets = list(document.pages) if document is not None else None
            timer.set_cache("visual_ocr", _disposition(self.cache, self._last_visual_cached))
            row.cache_visual = timer.as_dict()["visual_ocr"]["cache"]
            if markdown is None:
                # The rung was asked and produced nothing: an exception (server
                # down) or, only in principle, a cached negative. Either way the
                # document is terminal, and `error_type` tells the two apart.
                row.visual_rung = VISUAL_FAILED
                row.outcome_class, row.outcome_reason = "failed", "ocr_failed"
                row.error_type = visual_error
                row.source_path = "none"
                self._emit(row, profile, None, None, None, collector, timer,
                           error_type=visual_error, error_reason="ocr_failed",
                           fallback_reason=_fallback_reason(row.visual_rung))
                row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                return row
            row.visual_rung = VISUAL_RECOVERED
            note = None

        source = source_section(document)
        row.source_path = "committed_artifact" if note == "committed_artifact" else source["path"]
        row.source_model = source["model"]
        row.truncated_pages = source["truncation"]["truncated_page_count"]

        # P20-ROUTER item 2c. The extraction-quality verdict — and, for a
        # Tesseract-sourced candidate, the router's UPGRADE decision — are
        # computed from the offline read ALONE, right here, BEFORE `_analyse`
        # runs below. `tests/test_escalation_router.py` proves the decision
        # this produces is identical whether or not an intervening `_analyse`
        # call happens at all: nothing about it depends on a dispatch or a
        # payload. Whether it is ever ACTED on is a separate question,
        # answered after `_analyse` by `_upgrade_eligible` (the historical
        # cache-hit / parser-crash exclusions) — never by asking the router to
        # reconsider once analysis has run.
        #
        # `_evidence_for_row` scopes the gate to `GATE_ASSESSED_SOURCES`
        # (P20-ROUTER review, BLOCK-1): a native or committed-artifact read
        # is reported `evidence_quality="none"` and is usable BY
        # CONSTRUCTION for `classify_failure` — never assessed, never graded
        # Class A.
        evidence = _evidence_for_row(document, profile, row.source_path)
        row.evidence_quality = (
            ("usable" if evidence.usable else "unusable")
            if row.source_path in GATE_ASSESSED_SOURCES else "none"
        )
        upgrade_candidate = None
        if row.visual_rung == VISUAL_NOT_ATTEMPTED and self.visual_escalation and (
            source_path_for(document.model) == "local_tesseract"
        ):
            upgrade_triggers = (
                frozenset({EXTRACTOR_OUTPUT_UNUSABLE}) if not evidence.usable else frozenset()
            )
            upgrade_candidate = EscalationRouter.decide(router_inputs(
                profile=profile, evidence=evidence, triggers=upgrade_triggers,
                attempted=("local_tesseract",), stop=False,
            ))

        with timer.time("analysis"):
            payload, error_type, analysis_cached = self._analyse(markdown, collector, sheets)

        if upgrade_candidate is not None:
            # P20-ROUTER review, MINOR-9. The candidate's own verdict is
            # recorded UNCONDITIONALLY — before the eligibility gate runs —
            # so a Class-B document that happened to be claimed (excluded by
            # `_upgrade_eligible` below) reports the same `no_admitted_
            # trigger` refusal as one that was not: the column is comparable
            # across every row a candidate was ever built for, not only the
            # ones the historical exclusions let through.
            row.escalation_trigger = upgrade_candidate.trigger or ""
            row.escalation_refused = "; ".join(upgrade_candidate.refused)
        if upgrade_candidate is not None and self._upgrade_eligible(collector, payload):
            # UPGRADE (discovery class 5): Tesseract produced text and no parser
            # could claim it. Read the pixels again with the visual rung and keep
            # that read ONLY if it analyses — in deterministic mode a payload
            # exists if and only if a parser claimed, so "it analysed" IS the
            # adoption test, and it stays correct on a D-3 cache hit where no
            # dispatch is observable.
            decision = self._apply_budget(upgrade_candidate)
            row.escalation_trigger = decision.trigger or ""
            row.escalation_refused = "; ".join(decision.refused)
            if decision.extractor == "visual":
                with timer.time("visual_ocr"):
                    visual_doc, visual_md, visual_error = self._read_visual(raw, name, profile)
                timer.set_cache("visual_ocr", _disposition(self.cache, self._last_visual_cached))
                row.cache_visual = timer.as_dict()["visual_ocr"]["cache"]
                row.visual_rung = VISUAL_FAILED if visual_error else VISUAL_NO_UPGRADE
                if visual_md is not None:
                    visual_collector = DispatchCollector()
                    visual_sheets = list(visual_doc.pages) if visual_doc is not None else None
                    with timer.time("visual_analysis"):
                        visual_payload, visual_error_type, visual_cached = self._analyse(
                            visual_md, visual_collector, visual_sheets
                        )
                    if visual_payload is not None:
                        row.visual_rung = VISUAL_UPGRADED
                        document, markdown, collector = visual_doc, visual_md, visual_collector
                        sheets = visual_sheets
                        payload, error_type, analysis_cached = (
                            visual_payload, visual_error_type, visual_cached
                        )
                        source = source_section(document)
                        row.source_path = source["path"]
                        row.source_model = source["model"]
                        row.truncated_pages = source["truncation"]["truncated_page_count"]
                        evidence = _evidence_for_row(document, profile, row.source_path)
                        row.evidence_quality = (
                            "usable" if evidence.usable else "unusable"
                        ) if row.source_path in GATE_ASSESSED_SOURCES else "none"

        # One detection sweep, read twice: for the near-miss vector (H-3) and,
        # on a cache-served row, for the parser identity the absent `Dispatch`
        # would otherwise have carried. Hoisted above the projection because
        # both consumers need it; `score_vector` is pure, so where it is called
        # changes nothing it returns.
        # `collector` is the dispatch of record for THIS markdown — rebound
        # above when a visual re-read was adopted — so the near-miss sweep
        # reuses the preparation the analysis already paid for (#PREPHAND).
        # It is a hint, not an instruction: `score_vector` re-derives the
        # admissible text and ignores anything that does not match it.
        scores, registration_count = score_vector(markdown, collector)

        dispatch = collector.dispatch
        if dispatch is not None:
            row.parser_id_source = PARSER_ID_LIVE_DISPATCH
            row.dispatch_outcome = dispatch.outcome
            row.parser_id = dispatch.parser_id
            row.parser_score = (
                dispatch.detection.score if dispatch.detection is not None else None
            )
            row.candidates = _fmt(dispatch.candidates)
            row.attempted = list(dispatch.attempted)
            row.parser_exceptions = [
                f"{failure.parser_id}:{failure.stage}:{failure.exception}"
                for failure in dispatch.exceptions
            ]
        elif payload is not None:
            # A payload with no dispatch means exactly one thing: the analysis
            # stage was served from the D-3 cache. Re-resolve the identity and
            # mark how. See `_project_identity`.
            row.parser_id_source = _project_identity(row, scores, payload)

        row.near_miss = _fmt([(i, s) for i, s in scores if s < 0.5][:5])

        if payload is not None:
            _project_accounts(row, payload)

        from telemetry.record import classify_document

        # The DOCUMENT's outcome. One row per document, one outcome per row:
        # `discovery/compare.py` ranks on `content_sha256` alone, and that
        # ladder is what the non-regression regime is measured on.
        row.outcome_class, row.outcome_reason = classify_document(
            payload,
            error_type=error_type,
            error_reason=_failure_reason(error_type, dispatch),
        )
        row.error_type = error_type
        # P20-ROUTER. `evidence` above is the FINAL read of record (the
        # upgrade adoption branch recomputes it); `payload is not None` is
        # exactly "claimed" in deterministic mode (`analysis/pipeline.py`
        # raises on every other resolve outcome — see `classify_failure`'s
        # docstring and `tests/test_escalation_router.py`'s pin of that
        # claim).
        row.failure_class = classify_failure(
            evidence, claimed=payload is not None, validated=row.outcome_class == "validated",
        )

        # Cache disposition comes from CacheResult.cached, the same source
        # H-3 uses, so the CLI reports it identically to the webapp.
        timer.set_cache("ocr", _disposition(self.cache, self._last_ocr_cached))
        timer.set_cache("analysis", _disposition(self.cache, analysis_cached))
        stages = timer.as_dict()
        row.cache_ocr = stages["ocr"]["cache"]
        row.cache_analysis = stages["analysis"]["cache"]

        self._emit(
            row, profile, document, markdown, payload, collector, timer,
            error_type=error_type,
            scores=(scores, registration_count),
            escalated=bool(payload.get("escalated")) if payload else False,
            fallback_reason=_fallback_reason(row.visual_rung),
        )
        row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return row

    # -- telemetry ----------------------------------------------------------

    def _emit(
        self, row, profile, document, markdown, payload, collector, timer,
        *, error_type=None, error_reason=None, deferred=None, scores=None,
        escalated=False, fallback_reason=None,
    ) -> None:
        """One H-3 record per enumerated document. Never raises.

        The record shape is H-3's, unchanged and unextended: discovery is a
        telemetry CONSUMER. Note what does NOT cross into it — the relative
        path, the folder label, the bank label and the masked account live in
        the discovery row only, because the H-3 sensitivity invariant forbids
        them and the discovery report is a different artifact with a different
        audience.
        """
        if self.sink is None:
            return
        try:
            if scores is None:
                scores = score_vector(markdown, collector) if markdown else ([], 0)
            vector, registration_count = scores
            self.sink.write(build_record(
                run_id=self.run_id,
                emitter="discovery",
                document=document_section(
                    profile.content_sha256, row.byte_size, profile,
                    duplicate_of_prior_record=row.dedup_status != "unique",
                ),
                source=source_section(document),
                dispatch=dispatch_section(
                    collector.dispatch, vector, registration_count, payload=payload,
                ),
                stages=timer.as_dict(),
                model_calls=model_calls_for(document, payload),
                payload=payload,
                escalated=escalated,
                error_type=error_type,
                error_reason=error_reason,
                deferred=deferred,
                fallback_reason=fallback_reason,
            ))
        except Exception:
            return None


def _disposition(cache, cached: bool) -> str:
    return "bypass" if cache is None else ("hit" if cached else "miss")


def _fallback_reason(visual_rung: str) -> str | None:
    """The row's visual disposition as an H-3 enum code.

    It travels in `outcome.fallback_reason` — an existing, previously unused
    record field whose meaning is exactly this: the ladder did not stop where it
    normally stops. No telemetry field was added for W3-5.
    """
    if visual_rung == VISUAL_NOT_ATTEMPTED:
        return None
    return f"visual_ocr_{visual_rung}"


def _failure_reason(error_type: str | None, dispatch) -> str | None:
    """Why this document failed, in the vocabulary the report ranks by.

    The `parser_exception` branch is what the W3-1 boundary bought: before it,
    a crashing parser produced no `Dispatch` at all, so the run recorded the
    bare exception class of whatever escaped and every crash landed in the
    undifferentiated `exception` bucket. Now the dispatch says a parser broke,
    the deterministic mode's own `RuntimeError` no longer disguises it as
    "no parser matched", and the row names the failure class it belongs to.

    `parser_declined` is the same argument applied one level down. An unclaimed
    document with a non-empty `Dispatch.attempted` is NOT a bank whose layout we
    have never seen: a parser recognised it, ran, and returned None. Those two
    findings need different work — one needs a new parser, the other needs an
    existing one widened — and reporting both as `no_parser_matched` put the
    cheaper queue at the bottom of the more expensive one. `no_parser_matched`
    now means what it says: nothing even claimed it.
    """
    if error_type is None:
        return None
    if error_type == "AmbiguousParserError":
        return "parser_ambiguous"
    if dispatch is not None and dispatch.outcome == "parser_exception":
        return "parser_exception"
    if dispatch is not None and dispatch.outcome == "unclaimed":
        return "parser_declined" if dispatch.attempted else "no_parser_matched"
    return "exception"
