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
from ocr.paddle_config import REFUSAL_REASONS as PADDLE_REFUSAL_REASONS
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
#: P21-ROUTING (Phase 2.1). The Paddle discovery mode: as `--scanned`, plus
#: the Paddle escalation rung in place of the visual one. Mutually exclusive
#: with every other mode (the CLI's mode group enforces it).
MODE_SCANNED_PADDLE = "scanned-paddle"
MODE_DRY_RUN = "dry-run"

#: Modes that run the local Tesseract rung.
LOCAL_OCR_MODES = frozenset({MODE_SCANNED, MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE})

#: What the visual rung did for one document. Row-level vocabulary (the
#: adjudication artifact); it reaches telemetry as `outcome.fallback_reason`
#: prefixed with `visual_ocr_`, which is an enum code like every other.
VISUAL_NOT_ATTEMPTED = "not_attempted"
VISUAL_RECOVERED = "recovered"      # offline rungs served nothing; visual did
VISUAL_UPGRADED = "upgraded"        # unclaimed Tesseract read replaced by a claim
VISUAL_NO_UPGRADE = "no_upgrade"    # escalation ran, did not claim; offline kept
VISUAL_FAILED = "failed"            # the rung raised (endpoint down/transport)

#: P21-ROUTING. The SAME vocabulary shape as the visual rung above, plus
#: `refused_customer_data` (D8): the rung's own authorization gate refused a
#: `customer`-scope document before any request left the machine — a named,
#: counted finding, never a silent hop to another extractor.
PADDLE_NOT_ATTEMPTED = "not_attempted"
PADDLE_RECOVERED = "recovered"
PADDLE_UPGRADED = "upgraded"
PADDLE_NO_UPGRADE = "no_upgrade"
PADDLE_FAILED = "failed"
PADDLE_REFUSED_CUSTOMER_DATA = "refused_customer_data"

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

#: P21-ROUTING closure (MAJOR-1). A LITERAL mirror of `webapp.artifact_cache.
#: CACHE_FINDING_EVIDENCE_DRIFT` — not imported, for the same reason
#: `telemetry.run_of_record._VISUAL_ROW_OUTCOMES` and `telemetry.record.
#: VISUAL_MODEL_TOKENS` are literal mirrors rather than imports: this module
#: already lazily imports `webapp.artifact_cache` inside `_read`/`_read_visual`
#: /`_read_paddle` specifically so a `cache=None` run never pulls the module
#: in at all, and a module-level import for one string constant would defeat
#: that. `tests/test_discovery.py` holds the two equal by test.
CACHE_FINDING_EVIDENCE_DRIFT = "cached_evidence_drift"

#: The closed vocabulary `DocumentRow.paddle_rung` is enforced against at the
#: row projection (mirrors `PARSER_ID_*`'s pattern above and `visual_rung`'s
#: own, unenforced-by-name, historical vocabulary).
_PADDLE_RUNG_VOCABULARY = frozenset({
    PADDLE_NOT_ATTEMPTED, PADDLE_RECOVERED, PADDLE_UPGRADED,
    PADDLE_NO_UPGRADE, PADDLE_FAILED, PADDLE_REFUSED_CUSTOMER_DATA,
})


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
    # P21-ROUTING (Phase 2.1). Appended at the END, mirroring the P20-ROUTER
    # block above. `paddle_rung` is the SAME vocabulary shape as `visual_rung`
    # plus `refused_customer_data` (D8). `cache_paddle` mirrors `cache_visual`.
    # `escalation_extractor` names which extractor the router actually sent a
    # candidate to for this row (`""` when none did) — the one field that
    # tells `visual_rung="upgraded"` and `paddle_rung="upgraded"` apart from a
    # row where neither ran, without inspecting both columns. `evidence_sha256`
    # / `paddle_provider` / `paddle_execution_class` are read off
    # `telemetry.record.source_section`'s new fields (from `document.evidence
    # .runtime` when present) — empty string when the rung of record carries
    # no evidence (every non-Paddle read). `offline_source_model` (design item
    # 8, CASE 9) is the PRE-escalation read's own model token, recorded only
    # when an escalation ADOPTS a replacement read — so a disagreement between
    # the offline and the escalated read is never silently lost.
    paddle_rung: str = "not_attempted"
    cache_paddle: str = "bypass"
    escalation_extractor: str = ""
    evidence_sha256: str = ""
    paddle_provider: str = ""
    paddle_execution_class: str = ""
    offline_source_model: str = ""
    # P21-ROUTING closure (MAJOR-1, MINOR-2). `cache_finding` is `""` on every
    # ordinary read and `webapp.artifact_cache.CACHE_FINDING_EVIDENCE_DRIFT`
    # when the LAST `cached_ocr` call this row's reads made (offline, or
    # whichever escalation rung ran) recomputed because its cached copy
    # failed its own round-trip check — never cleared once set, so an
    # earlier rung's finding on the same document survives a later rung's
    # ordinary read. `paddle_refusal_reason` carries the closed
    # `ocr.paddle_config.REFUSAL_REASONS` token for the LAST `PaddleRefused`
    # this row's Paddle read raised (e.g. `paddle_runtime_mismatch`, the
    # silent-PP-OCRv6 hazard D5 exists to catch) — `""` when no Paddle read
    # ever refused. `outcome_reason` keeps its own, unrelated closed
    # vocabulary (`ocr_failed`, `paddle_refused`, ...); this column exists
    # because that vocabulary is deliberately coarser than `REFUSAL_REASONS`.
    cache_finding: str = ""
    paddle_refusal_reason: str = ""

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
        if self.paddle_rung not in _PADDLE_RUNG_VOCABULARY:
            raise ValueError(
                f"paddle_rung {self.paddle_rung!r} is not in the closed "
                f"vocabulary {_PADDLE_RUNG_VOCABULARY}"
            )
        if self.escalation_extractor not in ("", "paddle", "visual"):
            raise ValueError(
                f"escalation_extractor {self.escalation_extractor!r} is not "
                f"one of '', 'paddle', 'visual'"
            )
        if self.cache_finding and self.cache_finding != CACHE_FINDING_EVIDENCE_DRIFT:
            raise ValueError(
                f"cache_finding {self.cache_finding!r} is not '' or "
                f"{CACHE_FINDING_EVIDENCE_DRIFT!r}"
            )
        if self.paddle_refusal_reason and self.paddle_refusal_reason not in PADDLE_REFUSAL_REASONS:
            raise ValueError(
                f"paddle_refusal_reason {self.paddle_refusal_reason!r} is not '' or "
                f"in the closed vocabulary {PADDLE_REFUSAL_REASONS}"
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
#:
#: P21-ROUTING (Phase 2.1): `"paddle"` joins the set — a Paddle read is an
#: EXTRACTOR read in exactly the same sense a Tesseract or visual one is (an
#: extractor either produced usable evidence or it did not); it is never
#: usable-by-construction the way a native or committed-artifact read is.
GATE_ASSESSED_SOURCES: frozenset[str] = frozenset({"local_tesseract", "visual", "paddle"})


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
    _last_paddle_cached = False
    #: P21-ROUTING closure (MAJOR-1). `None` on every ordinary read; the
    #: `CacheResult.finding` value (e.g. `CACHE_FINDING_EVIDENCE_DRIFT`) when
    #: the last `cached_ocr` call for that rung recomputed because its cached
    #: copy failed its own round-trip check. Read by `process()` right after
    #: each `_read*` call and projected onto `row.cache_finding` — a
    #: per-instance attribute, not a per-call return value, for the same
    #: reason `_last_ocr_cached` etc. already are: `_read`/`_read_visual`/
    #: `_read_paddle`'s own return tuples are pinned shapes callers and tests
    #: already destructure, and widening them is a bigger, riskier change
    #: than one more instance attribute read immediately after the call.
    _last_ocr_finding: str | None = None
    _last_visual_finding: str | None = None
    _last_paddle_finding: str | None = None
    #: P21-ROUTING closure (MINOR-2). The `.reason` of the last `PaddleRefused`
    #: `_read_paddle` caught, or `""` when its last call did not refuse.
    #: Projected onto `row.paddle_refusal_reason` right after each call.
    _last_paddle_refusal_reason: str = ""

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
        #: D4: the ONE mode constant `router_inputs(enabled=...)` is ever
        #: built from at this class's two `decide(` call sites — never a
        #: per-document expression (the AST tripwire in
        #: `tests/test_escalation_tripwires.py` requires `self.<attribute>`
        #: at those call sites, and this is the attribute). Exactly one
        #: member, or none: two-engine escalation is not possible in this
        #: phase (design item 8).
        self.enabled_extractors: frozenset[str] = (
            frozenset({"visual"}) if mode == MODE_SCANNED_VISUAL
            else frozenset({"paddle"}) if mode == MODE_SCANNED_PADDLE
            else frozenset()
        )
        # Escalation is a policy knob ON TOP of the rung: `--no-visual-escalation`
        # recovers the documents nothing could read without spending GPU time
        # re-reading Tesseract/visual output. Generalised (Phase 2.1) to gate
        # whichever single extractor this mode enables, if any.
        self.visual_escalation = bool(visual_escalation) and bool(self.enabled_extractors)
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

    # -- per-document state -------------------------------------------------

    def _reset_per_document_state(self) -> None:
        """P21-ROUTING closure-2 (MAJOR-A). Every `_last_*` attribute on this
        class is a PER-DOCUMENT cache disposition (`_last_*_cached`, the
        `_last_*_finding` trio, `_last_paddle_refusal_reason`), read back by
        `process()` right after the `_read*` call that set it. Each `_read*`
        method resets its OWN attributes at its own call — but a rung that
        does NOT run on a document leaves its attributes holding whatever the
        LAST document that ran that rung left there, and `discovery/cli.py`
        drives ONE runner across a whole run. Reproduced (re-review, MAJOR-A):
        a Paddle drift on document A projected `cache_finding =
        cached_evidence_drift` onto document B's row, where `_read_paddle`
        never ran. So `process()` calls this FIRST, before any read, and a
        projection can never see a previous document's value. The class
        attributes below are the defaults this restores; `tests/
        test_paddle_routing.py` pins by AST that the set assigned here equals
        the set of `_last_*` class attributes, so a future attribute cannot
        be added without its reset."""
        self._last_ocr_cached = False
        self._last_visual_cached = False
        self._last_paddle_cached = False
        self._last_ocr_finding = None
        self._last_visual_finding = None
        self._last_paddle_finding = None
        self._last_paddle_refusal_reason = ""

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

        self._last_ocr_finding = None
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
            self._last_ocr_finding = result.finding
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

        self._last_visual_finding = None
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
                self._last_visual_finding = result.finding
        except Exception as exc:
            self._last_visual_cached = False
            # MINOR-D: a drift observed just before a recompute that then
            # FAILED still travels — `cached_ocr` attaches the finding to the
            # exception it lets through, and the row records it beside
            # `error_type` rather than losing it with the failed read.
            self._last_visual_finding = self._cache_finding_of(exc)
            return None, None, type(exc).__name__
        self._last_visual_cached = cached
        if document is None:
            return None, None, None
        return document, document.to_markdown(), None

    def _read_paddle(self, raw: bytes, source_file: str, profile):
        """(document, markdown, error). The Paddle rung, cached, fail-closed.

        Mirrors `_read_visual` exactly, swapping the extractor:
        `force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
        allow_paddle_ocr=True, paddle_data_scope="customer"` — the LITERAL
        the runner reads the archive under (D8's privacy boundary; pinned by
        AST in `tests/test_paddle_routing.py`, never `"synthetic"` here).
        `PaddleRefused` and `PaddleTransportError` are caught HERE, exactly
        like `_read_visual` catches `Exception`, and returned as an error
        token rather than propagating: this document fails closed and the
        run continues.

        `error` is `None` on success, the literal `"refused_customer_data"`
        when the rung's OWN authorization gate refused a customer-scope
        document before any request left the machine (D8 — a named, counted
        finding, never a silent hop to another extractor), or the raised
        exception's CLASS NAME for every other failure (config error, runtime
        mismatch, transport failure) — the caller (`process()`) tells the two
        shapes apart on the row.
        """
        from ocr.paddle_config import PaddleRefused
        from ocr.pipeline import parse_statement

        def compute():
            return parse_statement(
                raw,
                source_file=source_file,
                profile=profile,
                force_ocr=True,
                allow_local_ocr=False,
                allow_visual_ocr=False,
                allow_paddle_ocr=True,
                paddle_data_scope="customer",
            )

        self._last_paddle_finding = None
        self._last_paddle_refusal_reason = ""
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
                    allow_visual_ocr=False,
                    allow_paddle_ocr=True,
                )
                document, cached = result.value, result.cached
                self._last_paddle_finding = result.finding
        except Exception as exc:
            self._last_paddle_cached = False
            self._last_paddle_finding = self._cache_finding_of(exc)  # MINOR-D, as _read_visual
            if isinstance(exc, PaddleRefused):
                # MINOR-2: the reason travels regardless of WHICH refusal it
                # is — `remote_customer_data_refused` keeps its own row
                # token too (the row's terminal outcome fields key on it),
                # but every other reason (`paddle_runtime_mismatch`, the
                # silent-PP-OCRv6 hazard, included) is no longer lost inside
                # the generic `PaddleRefused` class name.
                self._last_paddle_refusal_reason = exc.reason
                if exc.reason == "remote_customer_data_refused":
                    return None, None, "refused_customer_data"
            return None, None, type(exc).__name__
        self._last_paddle_cached = cached
        if document is None:
            return None, None, None
        return document, document.to_markdown(), None

    def _project_cache_finding(self, row: "DocumentRow") -> None:
        """P21-ROUTING closure (MAJOR-1). Called right after every `_read` /
        `_read_visual` / `_read_paddle` invocation: whichever rung's last
        `cached_ocr` call observed a drift is projected onto `row.
        cache_finding`, so the fact that a drift happened survives the
        recompute that immediately follows it inside `cached_ocr` — a
        drifted entry is overwritten in the cache itself, but not on this
        row. Each `_read*` method resets its OWN `_last_*_finding` to `None`
        at its own call, AND `process()` resets all three (with every other
        per-document `_last_*` attribute) via `_reset_per_document_state`
        before any read — closure-2, MAJOR-A: without that second reset a
        rung that did not run on THIS document still held the previous
        document's finding, and this projection copied it onto the wrong
        row. So at most one of the three is ever truthy for a single call,
        and none of them is ever a previous document's; `row.cache_finding`
        is set (never cleared) so an earlier rung's finding on the SAME
        document (offline, then an escalation) is not lost when a later
        rung's own call finds nothing to report. A rung whose recompute
        FAILED after a drift (MINOR-D) sets its `_last_*_finding` from the
        exception `cached_ocr` let through, so the finding lands here beside
        `error_type`."""
        finding = self._last_ocr_finding or self._last_visual_finding or self._last_paddle_finding
        if finding:
            row.cache_finding = finding

    @staticmethod
    def _cache_finding_of(exc: BaseException) -> str | None:
        """MINOR-D: the cache finding `webapp.artifact_cache.cached_ocr`
        attached to an exception it re-raised out of a failed recompute
        (`None` when there was none). Imported lazily, like `cached_ocr`
        itself — this module never imports `webapp.artifact_cache` at module
        level (see the mirrored `CACHE_FINDING_EVIDENCE_DRIFT` above)."""
        from webapp.artifact_cache import cache_finding_of

        return cache_finding_of(exc)

    def _project_paddle_refusal(self, row: "DocumentRow") -> None:
        """MINOR-2: called right after every `_read_paddle` invocation — the
        closed `REFUSAL_REASONS` token of the last `PaddleRefused` it caught,
        or nothing when it did not refuse. `outcome_reason` stays on its own,
        coarser vocabulary; this is the column a later diagnostic (D5's
        silent-PP-OCRv6 hazard) actually needs."""
        if self._last_paddle_refusal_reason:
            row.paddle_refusal_reason = self._last_paddle_refusal_reason

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
        self._reset_per_document_state()  # MAJOR-A: before ANY read, every document
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
        self._project_cache_finding(row)

        if markdown is None and not self.enabled_extractors:
            # Recorded, never skipped: real work this tranche deliberately did
            # not do. `deferred` is its own outcome class precisely so that
            # `failed` can keep meaning "attempted and errored" — the two are
            # different findings and DSC-2 acts on them differently.
            #
            # P21-ROUTING: generalised from `not self.allow_visual_ocr` — a
            # mode with NO escalation extractor enabled at all (digital,
            # scanned, profile-only, dry-run) defers exactly as before;
            # `--scanned-visual` and `--scanned-paddle` each enable exactly
            # one and fall through to RECOVERY below instead.
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
                stop=False, enabled=self.enabled_extractors,
            )))
            row.escalation_trigger = recovery_decision.trigger or ""
            row.escalation_refused = "; ".join(recovery_decision.refused)
            if recovery_decision.extractor not in ("visual", "paddle"):
                # Refused (today only reachable via an exhausted budget, or a
                # mode whose one enabled extractor is not this call's): an
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
            row.escalation_extractor = recovery_decision.extractor
            if recovery_decision.extractor == "visual":
                with timer.time("visual_ocr"):
                    document, markdown, visual_error = self._read_visual(raw, name, profile)
                self._project_cache_finding(row)
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
            else:  # "paddle" — P21-ROUTING
                with timer.time("paddle_ocr"):
                    document, markdown, paddle_error = self._read_paddle(raw, name, profile)
                self._project_cache_finding(row)
                self._project_paddle_refusal(row)
                sheets = list(document.pages) if document is not None else None
                timer.set_cache("paddle_ocr", _disposition(self.cache, self._last_paddle_cached))
                row.cache_paddle = timer.as_dict()["paddle_ocr"]["cache"]
                if markdown is None:
                    # D8: `refused_customer_data` is the rung's OWN
                    # authorization gate refusing before any request left the
                    # machine — a distinct, named finding, never folded into
                    # the generic transport-failure shape below.
                    if paddle_error == "refused_customer_data":
                        row.paddle_rung = PADDLE_REFUSED_CUSTOMER_DATA
                        row.outcome_class, row.outcome_reason = "failed", "paddle_refused"
                        row.error_type = "PaddleRefused"
                    else:
                        row.paddle_rung = PADDLE_FAILED
                        row.outcome_class, row.outcome_reason = "failed", "ocr_failed"
                        row.error_type = paddle_error
                    row.source_path = "none"
                    self._emit(row, profile, None, None, None, collector, timer,
                               error_type=row.error_type, error_reason=row.outcome_reason,
                               fallback_reason=_fallback_reason(row.visual_rung, row.paddle_rung))
                    row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                    return row
                row.paddle_rung = PADDLE_RECOVERED
                note = None

        source = source_section(document)
        _project_source(row, source, committed_artifact=(note == "committed_artifact"))

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
        if (
            row.visual_rung == VISUAL_NOT_ATTEMPTED
            and row.paddle_rung == PADDLE_NOT_ATTEMPTED
            and self.visual_escalation
            and source_path_for(document.model) == "local_tesseract"
        ):
            upgrade_triggers = (
                frozenset({EXTRACTOR_OUTPUT_UNUSABLE}) if not evidence.usable else frozenset()
            )
            upgrade_candidate = EscalationRouter.decide(router_inputs(
                profile=profile, evidence=evidence, triggers=upgrade_triggers,
                attempted=("local_tesseract",), stop=False, enabled=self.enabled_extractors,
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
            # could claim it. Read the pixels again with this mode's ONE enabled
            # extractor and keep that read ONLY if it analyses — in
            # deterministic mode a payload exists if and only if a parser
            # claimed, so "it analysed" IS the adoption test, and it stays
            # correct on a D-3 cache hit where no dispatch is observable.
            decision = self._apply_budget(upgrade_candidate)
            row.escalation_trigger = decision.trigger or ""
            row.escalation_refused = "; ".join(decision.refused)
            if decision.extractor is not None:
                row.escalation_extractor = decision.extractor
            if decision.extractor == "visual":
                with timer.time("visual_ocr"):
                    visual_doc, visual_md, visual_error = self._read_visual(raw, name, profile)
                self._project_cache_finding(row)
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
                        # CASE 9 (design item 8): the offline read's own model
                        # is preserved before it is replaced, so a
                        # disagreement between the two reads is never
                        # silently lost even though only the adopted read's
                        # payload is published.
                        row.offline_source_model = document.model
                        row.visual_rung = VISUAL_UPGRADED
                        document, markdown, collector = visual_doc, visual_md, visual_collector
                        sheets = visual_sheets
                        payload, error_type, analysis_cached = (
                            visual_payload, visual_error_type, visual_cached
                        )
                        source = source_section(document)
                        _project_source(row, source)
                        evidence = _evidence_for_row(document, profile, row.source_path)
                        row.evidence_quality = (
                            "usable" if evidence.usable else "unusable"
                        ) if row.source_path in GATE_ASSESSED_SOURCES else "none"
            elif decision.extractor == "paddle":  # P21-ROUTING
                with timer.time("paddle_ocr"):
                    paddle_doc, paddle_md, paddle_error = self._read_paddle(raw, name, profile)
                self._project_cache_finding(row)
                self._project_paddle_refusal(row)
                timer.set_cache("paddle_ocr", _disposition(self.cache, self._last_paddle_cached))
                row.cache_paddle = timer.as_dict()["paddle_ocr"]["cache"]
                if paddle_error == "refused_customer_data":
                    row.paddle_rung = PADDLE_REFUSED_CUSTOMER_DATA
                else:
                    row.paddle_rung = PADDLE_FAILED if paddle_error else PADDLE_NO_UPGRADE
                if paddle_md is not None:
                    paddle_collector = DispatchCollector()
                    paddle_sheets = list(paddle_doc.pages) if paddle_doc is not None else None
                    with timer.time("paddle_analysis"):
                        paddle_payload, paddle_error_type, paddle_cached = self._analyse(
                            paddle_md, paddle_collector, paddle_sheets
                        )
                    if paddle_payload is not None:
                        # CASE 9: the SAME validator produced a payload from
                        # the Paddle read — no fusion, no choice by which read
                        # reconciles: the offline read's model is recorded and
                        # the Paddle read is the one adopted, full stop.
                        row.offline_source_model = document.model
                        row.paddle_rung = PADDLE_UPGRADED
                        document, markdown, collector = paddle_doc, paddle_md, paddle_collector
                        sheets = paddle_sheets
                        payload, error_type, analysis_cached = (
                            paddle_payload, paddle_error_type, paddle_cached
                        )
                        source = source_section(document)
                        _project_source(row, source)
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
            fallback_reason=_fallback_reason(row.visual_rung, row.paddle_rung),
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


def _project_source(row: "DocumentRow", source: dict, *, committed_artifact: bool = False) -> None:
    """The row's source-provenance columns, from `telemetry.record.source_section`.

    ONE function so every call site (the initial read, the RECOVERY rungs and
    the UPGRADE adoption branches) projects the SAME fields the same way —
    `evidence_sha256` / `paddle_provider` / `paddle_execution_class` are new
    (P21-ROUTING) and empty-string for every read that carries no evidence
    (every non-Paddle rung, and every pre-Phase-2.1 cached artifact)."""
    row.source_path = "committed_artifact" if committed_artifact else source["path"]
    row.source_model = source["model"]
    row.truncated_pages = source["truncation"]["truncated_page_count"]
    row.evidence_sha256 = source.get("evidence_sha256") or ""
    row.paddle_provider = source.get("provider") or ""
    row.paddle_execution_class = source.get("execution_class") or ""


def _fallback_reason(visual_rung: str, paddle_rung: str = PADDLE_NOT_ATTEMPTED) -> str | None:
    """The row's escalation disposition as an H-3 enum code.

    It travels in `outcome.fallback_reason` — an existing, previously unused
    record field whose meaning is exactly this: the ladder did not stop where it
    normally stops. No telemetry field was added for W3-5; P21-ROUTING adds no
    new one either — `paddle_rung` gets the SAME `<extractor>_ocr_<state>`
    shape `visual_rung` always has. The two are mutually exclusive in
    practice (`enabled_extractors` holds one member per mode), so at most one
    of the two checks below ever fires for a given row."""
    if visual_rung != VISUAL_NOT_ATTEMPTED:
        return f"visual_ocr_{visual_rung}"
    if paddle_rung != PADDLE_NOT_ATTEMPTED:
        return f"paddle_ocr_{paddle_rung}"
    return None


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
        # Phase 2.0 (P20-SURFACES, composed by Ocean): the Q3 native-only gate
        # refuses an OCR-fed sibling-omission admission by raising
        # `Q3ProvenanceRefused`, which `_guarded` records as a parser failure
        # under that CLASS NAME. It is a POLICY refusal, not a crash, and a
        # triage queue must be able to tell the two apart — so the reason token
        # names it. Class name only, never a message (H3_SCHEMA I1).
        if any(
            getattr(failure, "exception", None) == "Q3ProvenanceRefused"
            for failure in (getattr(dispatch, "exceptions", None) or ())
        ):
            return "q3_provenance_refused"
        return "parser_exception"
    if dispatch is not None and dispatch.outcome == "unclaimed":
        return "parser_declined" if dispatch.attempted else "no_parser_matched"
    return "exception"
