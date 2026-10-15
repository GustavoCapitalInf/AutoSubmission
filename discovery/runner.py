"""Per-document discovery processing. Consumes merged platform pieces only.

Resolution is the **production intake ladder** (`ocr.pipeline.parse_statement`)
and nothing else. That is a binding ruling with a scar behind it: H-3's first
corpus anchor used the generic `parse_native_pdf_text` directly and silently
produced different markdown for four banks (Navy Federal, TD Canada, Wells,
Desjardins all have layout-specific readers that come first), which showed up
as five phantom failures. Discovery measures coverage; measuring it through a
different reader than production uses would make every number a fiction.

Offline by construction, in every mode:

- `parse_mode="deterministic"` — the LLM extraction branch is unreachable, so
  no model call can occur even in principle.
- `force_ocr=False, allow_visual_ocr=False` — always: the visual OCR rung, the
  visual pair and the PaddleOCR rung were removed (model-code removal, slices
  S2, S4 and S5; owner ruling of 2026-10-13: the product uses no model).
  `ocr.pipeline` refuses either flag set to True.
- Local Tesseract only in `--scanned`, never in tranche 0/1.

Documents the mode cannot read are RECORDED, never skipped: a scanned document
in an offline tranche is `deferred:deferred_scanned` (work the tranche chose
not to do), and a document the offline ladder (Tesseract included) ran on and
read nothing usable from is `refused:insufficient_evidence` (slice S5,
declared: until then it was `deferred:deferred_visual_ocr`, "left for the
visual rung", and there is no such rung any more).

The retired escalation modes
----------------------------
`--scanned-visual` (W3-5, the local Unlimited-OCR rung), `--scanned-paddle`
(P21-ROUTING, the PaddleOCR rung) and `--research-paddle` (P22-TRUTHTABLE, a
named population read by Paddle into a research partition) each added a model
read on top of `--scanned`, reached two ways: RECOVERY (the offline rungs
produced nothing) and UPGRADE (an unclaimed Tesseract read was re-read). All
three are gone with their rungs, and with them every `EscalationRouter.decide`
call site in this module (2 -> 0, declared in
`tests/test_escalation_tripwires.py`). Their mode names stay as retired
vocabulary (in `LOCAL_OCR_MODES`, so the mode vocabulary is append-only and
historical rows and provenance records keep their meaning), and
`DiscoveryRunner` refuses to be constructed with any of them. Every row column
those modes filled stays in `ROW_FIELDS` at the fixed value an offline row has
always carried, and the report still summarizes a historical research run's
rows exactly as before.
"""
from __future__ import annotations

import re
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
from evidence.native import NATIVE_EXTRACTOR_ID
from layout import DocumentProfileFacts, classify_document as classify_document_kind
from layout.agreement import AGREE_COLUMNS, document_agreement, row_columns as agreement_row_columns
from layout.refusals import ACCOUNT_KINDS, KINDS, MODALITIES, TIERS
from ocr.escalation import (
    A_EXTRACTION,
    B_STRUCTURE,
    C_VALIDATION,
    NO_FAILURE,
    OPERATOR_FORCED_PADDLE,
    EvidenceQuality,
    ExtractionQualityGate,
)
from ocr.extraction_quality import EQ_ROW_COLUMNS, E_CLASSES, eq_row_values
from ocr.inspect import inspect_pdf
from ocr.local_tesseract import LocalOcrIncomplete
from telemetry import (
    DispatchCollector,
    EXTRACTION_TRIGGERS,
    FAILURE_CLASSES,
    OUTCOME_CLASSES,
    UNRESOLVED_TAXONOMY_VERSION,
    StageTimer,
    build_record,
    diagnose_unresolved,
    dispatch_section,
    document_section,
    model_calls_for,
    reconstructed_claim,
    score_vector,
    source_section,
)

from .inventory import DedupIndex

MODE_PROFILE_ONLY = "profile-only"
MODE_DIGITAL = "digital"
MODE_SCANNED = "scanned"
#: RETIRED (model-code removal, slice S2): the visual OCR rung's mode. The name
#: stays in the vocabulary (append-only, and in `LOCAL_OCR_MODES`) so historical
#: rows and provenance records keep their meaning; `DiscoveryRunner` refuses it.
MODE_SCANNED_VISUAL = "scanned-visual"
#: RETIRED (model-code removal, slice S5): the PaddleOCR discovery mode
#: (P21-ROUTING, Phase 2.1: `--scanned` plus the Paddle escalation rung). Kept
#: as vocabulary, like `MODE_SCANNED_VISUAL`; `DiscoveryRunner` refuses it.
MODE_SCANNED_PADDLE = "scanned-paddle"
#: RETIRED (model-code removal, slice S5): the RESEARCH mode (P22-TRUTHTABLE,
#: Phase 2.2, D7/D8: an operator-named population read by Paddle into a
#: research partition no run of record can select). Kept as vocabulary, so a
#: historical research run's provenance (`mode`) and rows keep their meaning;
#: `DiscoveryRunner` refuses it.
MODE_RESEARCH_PADDLE = "research-paddle"
MODE_DRY_RUN = "dry-run"

#: Modes that run the local Tesseract rung. Append-only: the three retired
#: modes stay members (each ran the offline ladder, Tesseract included, before
#: its model rung), because `telemetry/run_of_record.py` and
#: `tools/train/provenance.py` reconstruct a historical run's OCR key from
#: `mode in LOCAL_OCR_MODES`, and dropping a name would re-key that run.
LOCAL_OCR_MODES = frozenset({
    MODE_SCANNED, MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE, MODE_RESEARCH_PADDLE,
})

#: The retired mode names `DiscoveryRunner` refuses, each with the rung it
#: needed (model-code removal: S2 the visual rung, S5 the Paddle rung).
RETIRED_MODES: dict[str, str] = {
    MODE_SCANNED_VISUAL: "the visual OCR rung was removed",
    MODE_SCANNED_PADDLE: "the PaddleOCR rung was removed",
    MODE_RESEARCH_PADDLE: "the PaddleOCR research mode was removed",
}

#: What the visual rung did for one document. Row-level vocabulary (the
#: adjudication artifact); it reaches telemetry as `outcome.fallback_reason`
#: prefixed with `visual_ocr_`, which is an enum code like every other.
#: Historical since slices S2/S5 of the model-code removal (as is the Paddle
#: vocabulary below): no rung remains, so every row this runner writes carries
#: `not_attempted`; the names stay so a historical row still validates and a
#: historical run still summarizes.
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
#: P22-TRUTHTABLE (D8): the RESEARCH read. Not `recovered` and not `upgraded`
#: — neither word is true of it. A research read is not a rescue of a document
#: nothing could read and not a replacement of an unclaimed one: it is the
#: operator's named population being read by Paddle regardless of profile,
#: which is the research admission Gustavo authorized, and it earns its own
#: token so a rollup can never mistake it for either production shape.
PADDLE_RESEARCH = "research"

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
#: already lazily imports `webapp.artifact_cache` inside `_read`
#: specifically so a `cache=None` run never pulls the module
#: in at all, and a module-level import for one string constant would defeat
#: that. `tests/test_discovery.py` holds the two equal by test.
CACHE_FINDING_EVIDENCE_DRIFT = "cached_evidence_drift"

#: The closed vocabulary `DocumentRow.paddle_rung` is enforced against at the
#: row projection (mirrors `PARSER_ID_*`'s pattern above and `visual_rung`'s
#: own, unenforced-by-name, historical vocabulary).
_PADDLE_RUNG_VOCABULARY = frozenset({
    PADDLE_NOT_ATTEMPTED, PADDLE_RECOVERED, PADDLE_UPGRADED,
    PADDLE_NO_UPGRADE, PADDLE_FAILED, PADDLE_REFUSED_CUSTOMER_DATA,
    PADDLE_RESEARCH,
})

#: The closed vocabulary `DocumentRow.paddle_refusal_reason` is enforced
#: against: a LITERAL copy of the retired `ocr.paddle_config.REFUSAL_REASONS`
#: (removed with the Paddle rung, model-code removal slice S5; the module's
#: last commit holds the original). Historical vocabulary, append-only: no
#: rung produces one any more, so every row this runner writes carries `""`,
#: and the check stays exactly as closed as it was.
PADDLE_REFUSAL_REASONS: tuple[str, ...] = (
    "paddle_config_missing",
    "paddle_remote_opt_in_required",
    "remote_customer_data_refused",
    "paddle_data_scope_unknown",
    "paddle_runtime_mismatch",
    "paddle_worker_unreachable",
    "paddle_worker_url_not_loopback",
    "paddle_frame_mismatch",
    "paddle_evidence_malformed",
)

# ---------------------------------------------------------------------------
# P22-TRUTHTABLE (case 25): the funnel stages and the technical telemetry.
# ---------------------------------------------------------------------------

#: The default of every funnel stage. "This document did not reach this stage"
#: is a different fact from "it reached it and produced nothing", and a column
#: that defaulted to the empty string would fold the two together.
STAGE_NOT_ATTEMPTED = "not_attempted"

#: Review MINOR-5 (reproduced): the outcome reasons that mean NO READ WAS EVER
#: ATTEMPTED for this document. `DocumentRow.source_path` defaults to the
#: literal `"none"`, so without this the extraction stage folded "the ladder
#: ran and produced nothing" together with "the ladder never ran" — 16 of the
#: run of record's 29 `none` rows are invalid files refused before any read,
#: and every row of a `--profile-only` run would be mislabelled the same way.
#: `stage_evidence` already draws the distinction; this is the same fact,
#: taken from the same place: the reason the row ALREADY records, never
#: inferred from anything else. A closed tuple, guarded against drift by
#: `tests/test_two_denominators.py` reading it against `DEFERRED_REASONS` and
#: the runner's own literals. The two `research_*` members are historical
#: (the research mode was removed in slice S5); they stay so a historical
#: research row's stage reads as it always did.
NO_READ_ATTEMPTED_REASONS: frozenset[str] = frozenset({
    "profile_only",                        # the mode does not read at all
    "invalid_pdf", "encrypted",            # refused at the door, before the ladder
    "research_skipped_not_in_population",  # outside the operator's named set (historical)
    "research_refused_holdout",            # refused by the cage, before any read (historical)
    "not_processed",                       # the row's own default: nothing ran
})

#: The literal `peak_rss_mb` carries when `psutil` is not importable. A string,
#: not `None` and not `0`: an unmeasured figure that renders as a number is a
#: measurement nobody made.
PEAK_RSS_NOT_MEASURED = "not measured"

#: Closed per stage, enforced at the row projection exactly as `failure_class`
#: and `paddle_rung` already are. Each vocabulary is the set of states the
#: stage can be in — including the ones no producer reaches yet (2.3 fills
#: geometry, 2.4 fills layout), declared now so a report's columns do not
#: change shape underneath a reader when they do.
STAGE_VOCABULARY: dict[str, frozenset[str]] = {
    # which extractor produced the text of record for this document
    "stage_extract": frozenset({STAGE_NOT_ATTEMPTED, "native", "local_tesseract",
                                "paddle", "visual", "committed_artifact", "none"}),
    # whether canonical extraction evidence exists beside that text
    "stage_evidence": frozenset({STAGE_NOT_ATTEMPTED, "present", "absent"}),
    # whether a DocumentGeometry was built from it (2.3+)
    "stage_geometry": frozenset({STAGE_NOT_ATTEMPTED, "present", "absent"}),
    # whether a layout model resolved a structure over that geometry (2.4+)
    "stage_layout": frozenset({STAGE_NOT_ATTEMPTED, "resolved", "unresolved"}),
    # whether a financial candidate was produced, and by what route
    "stage_candidate": frozenset({STAGE_NOT_ATTEMPTED, "claimed", "unclaimed",
                                  "ambiguous", "parser_exception", "error"}),
    # the deterministic validator's verdict: the row's own outcome class
    "stage_verdict": frozenset({STAGE_NOT_ATTEMPTED, *OUTCOME_CLASSES}),
}

#: The closed shape of a research partition id — a LITERAL mirror of
#: `webapp.artifact_cache._RESEARCH_PARTITION_RE` and of
#: `tools/train/provenance.py::RESEARCH_PARTITION_PATTERN`, for the same
#: reason `CACHE_FINDING_EVIDENCE_DRIFT` above is a literal mirror: this
#: module imports `webapp.artifact_cache` lazily on purpose, and a
#: module-level import for one regex would defeat that. Held equal by test.
#: Since slice S5 nothing writes a non-empty `research_partition` on a row
#: (the research mode was removed); the check stays for historical rows.
RESEARCH_PARTITION_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"

#: P22-TRUTHTABLE (D8): the trigger the retired RESEARCH mode supplied, read
#: from `ocr/escalation.py` by NAME. Historical since slice S5 of the
#: model-code removal: no `decide(` call site remains anywhere in the tree, so
#: nothing supplies it to the router. It stays because
#: `discovery/report.py`'s research table (row-driven, so a historical research
#: run summarizes as it did) counts the rows whose `escalation_trigger` is in
#: it; `tests/test_escalation_tripwires.py` pins that it is read by that table
#: and supplied to nothing.
RESEARCH_TRIGGERS = frozenset({OPERATOR_FORCED_PADDLE})


# ---------------------------------------------------------------------------
# The population helpers (P22-TRUTHTABLE D7/D8), kept when the research mode
# that first called them was removed (model-code removal, slice S5, plan D16):
# deterministic and stdlib-only, and the text-first reader plan (AM-15) is
# their planned caller. Bodies unchanged.
# ---------------------------------------------------------------------------

def read_population(path: Path) -> frozenset[str]:
    """The operator's named population: one 64-hex content sha per line.

    No production caller since slice S5 (the `--research-paddle` mode that
    read it was removed); the text-first reader plan (AM-15) is the planned
    caller, and `tests/test_population_helpers.py` pins it.

    `#` comments and blank lines are ignored, an inline `# ...` tail is
    stripped, and case is normalised UP (the archive's shas are upper-cased
    everywhere in this tree). A line that is not a content sha REFUSES the
    whole file rather than being skipped: a population is the operator's
    statement of what will be studied, and silently dropping a malformed line
    would study a different set than the one they named. An EMPTY population
    refuses too — a research run with nothing to research is a mistake, not a
    no-op.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"population file {path}: cannot be read ({type(exc).__name__})") from exc
    shas: set[str] = set()
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if re.fullmatch(r"[0-9A-Fa-f]{64}", line) is None:
            raise ValueError(
                f"population file {path} line {number}: not a 64-hex content sha; refused "
                "rather than skipped"
            )
        shas.add(line.upper())
    if not shas:
        raise ValueError(f"population file {path} is empty; a research run needs a population")
    return frozenset(shas)


#: The ONE holdout artefact runtime code may read (the leakage firewall): the
#: committed digest `holdout_sha16s_from_digest` reads. Moved here from
#: `discovery/cli.py` with the research mode's removal (slice S5), beside the
#: function it is the default for; the path is unchanged.
DEFAULT_HOLDOUT_DIGEST = (
    Path(__file__).resolve().parents[1]
    / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"
)


def holdout_sha16s_from_digest(path: Path) -> frozenset[str]:
    """The holdout manifest's sha16 prefixes, read from the REPOSITORY digest.

    No production caller since slice S5 (the `--research-paddle` mode that
    checked its population against it was removed); the text-first reader
    plan (AM-15) is the planned caller (`DEFAULT_HOLDOUT_DIGEST` above is the
    committed digest), and `tests/test_population_helpers.py` pins it.

    `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` is the ONLY
    holdout artefact runtime code may read. The leakage firewall
    (`tests/test_truth_firewall.py`) forbids every production package from
    naming the sealed store's directory variable or importing its package at
    all — including in prose, which is why this paragraph describes the rule
    instead of quoting it. Reading the committed digest breaks nothing: its
    grammar is fixed — a status header followed by `- <SHA16> <status>` lines
    — this reads THAT BLOCK ONLY so the adjudicated list above it can never be
    mistaken for a holdout list, and the file carries no verdict at all.

    A missing or unreadable digest REFUSES: a research run that cannot check
    the cage must not run, because "we could not read the holdout list" and
    "the holdout list is empty" are the same silence and only one of them is
    safe.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"holdout digest {path}: cannot be read ({type(exc).__name__}); a research run "
            "may not proceed without the holdout list"
        ) from exc
    inside = False
    shas: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":"):
            inside = line == "holdout_sha16_status:"
            continue
        if not inside or not line.startswith("- "):
            continue
        member = line[2:].split()
        if member and re.fullmatch(r"[0-9A-F]{16}", member[0]):
            shas.add(member[0])
    return frozenset(shas)


def peak_rss_mb() -> str:
    """This PROCESS's resident set, in MiB, as a string — or the LITERAL
    `not measured` when `psutil` is not importable.

    Named for the card's column and narrower than that name (review MINOR-6):
    this is the process RSS read at the row's exit, not a per-document PEAK. A
    true peak needs sampling across the document's work, which is 2.3's to
    build; until then the honest reading of this column is "how large the
    process was when this row finished", and it is stated here, in
    `requirements-local.txt`, and in the closure record rather than implied by
    the name.

    `psutil` is in `requirements-local.txt` only: it is a measurement
    convenience on the development host, not something the engine needs to
    produce a verdict, and adding a native dependency to the runtime
    requirements for one column would be the wrong trade. The degraded value
    is a WORD rather than `0` or an empty number precisely because a column
    that reads as a figure is a measurement somebody made.
    """
    try:
        import psutil
    except ImportError:
        return PEAK_RSS_NOT_MEASURED
    try:
        return f"{psutil.Process().memory_info().rss / (1024 * 1024):.1f}"
    except Exception:  # a permission or platform failure is not a run failure
        return PEAK_RSS_NOT_MEASURED


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
    #:
    #: Since slice S5 of the model-code removal no router decision is made
    #: (no escalation mode remains), so `escalation_trigger` and
    #: `escalation_refused` are `""` on every row, exactly as every `--scanned`,
    #: `--digital` and dry-run row always carried them; `failure_class` and
    #: `evidence_quality` are the deterministic projection and are unchanged.
    #: Every column in the two Paddle blocks below is likewise the fixed value
    #: an offline row has always carried (`ROW_FIELDS` is append-only).
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
    # ordinary read. `paddle_refusal_reason` carried the closed
    # `PADDLE_REFUSAL_REASONS` token for the LAST `PaddleRefused` the retired
    # Paddle read raised (e.g. `paddle_runtime_mismatch`, the silent-PP-OCRv6
    # hazard D5 existed to catch) — `""` when no Paddle read ever refused,
    # which is every row since slice S5. `outcome_reason` keeps its own,
    # unrelated closed vocabulary (`ocr_failed`, and historically
    # `paddle_refused`); this column existed because that vocabulary is
    # deliberately coarser than `PADDLE_REFUSAL_REASONS`.
    cache_finding: str = ""
    paddle_refusal_reason: str = ""
    # P22-TRUTHTABLE (Phase 2.2, case 25). Appended at the END, mirroring every
    # block above. Six FUNNEL stages with closed vocabularies and a
    # `not_attempted` default, so a stage nothing has reached yet reads as
    # "not reached" rather than as a zero; four technical-telemetry columns
    # (empty for every non-Paddle row, because a figure a row never measured
    # must not read as a measured zero); the per-document peak RSS, which is
    # the literal `not measured` when `psutil` is not importable; the research
    # partition (D7, empty for every production row); the seven taxonomy
    # layers with the primary pair and the taxonomy version; and the
    # classifier's verdict as a RECORDED FACT (D2) — nine columns that are
    # written to the row and NEVER passed to `analyze_document`.
    #
    # There is deliberately NO cost, rate, price, billing or currency column
    # anywhere in this block: cost accounting is out of scope by Gustavo's
    # ruling of 2026-09-03, and `tests/test_two_denominators.py` greps both
    # `ROW_FIELDS` and every `summary.json` key for those tokens.
    stage_extract: str = STAGE_NOT_ATTEMPTED
    stage_evidence: str = STAGE_NOT_ATTEMPTED
    stage_geometry: str = STAGE_NOT_ATTEMPTED
    stage_layout: str = STAGE_NOT_ATTEMPTED
    stage_candidate: str = STAGE_NOT_ATTEMPTED
    stage_verdict: str = STAGE_NOT_ATTEMPTED
    bytes_up: str = ""
    bytes_down: str = ""
    inference_ms: str = ""
    vram_mb: str = ""
    peak_rss_mb: str = PEAK_RSS_NOT_MEASURED
    research_partition: str = ""
    reason_l0: str = ""
    reason_l1: str = ""
    reason_l2: str = ""
    reason_l3: str = ""
    reason_l4: str = ""
    reason_l5: str = ""
    reason_l6: str = ""
    primary_reason_layer: str = ""
    primary_reason: str = ""
    unresolved_taxonomy_version: int = UNRESOLVED_TAXONOMY_VERSION
    #: The classifier's verdict (`layout.document_class.classify_document`).
    #: `KIND_UNCERTAIN` at tier `uncertain` with `class_version = 0` is the
    #: honest default of a row NO classifier ran for — a bare row, a row from
    #: a mode that never reads a document — and it is distinguishable from a
    #: real `KIND_UNCERTAIN` verdict by exactly that version number.
    document_class: str = "KIND_UNCERTAIN"
    class_sub_kind: str = ""
    class_modality: str = "unknown"
    class_account_kind: str = "unknown"
    class_tier: str = "uncertain"
    class_signals: str = ""
    class_version: int = 0
    completeness_findings: str = ""
    #: The exception CLASS NAME if the classifier raised on this document.
    #: A recorded fact must never fail a run: the classifier is a reporting
    #: consumer, and a defect in it is a finding on the row, not a lost
    #: document.
    classifier_exception: str = ""
    # P23-EGATE (Phase 2.3, cell E). Appended at the END, mirroring every
    # block above. Thirteen extraction-quality columns projected at this
    # row's single exit from the document's EXTRACTOR evidence — never from
    # the native reader's, which is a different thing measured under a
    # different name (see `_project_extraction_quality`). Every one is a
    # RECORDED FACT in the strictest sense this programme uses: nothing reads
    # them but the report and the census, `ocr/escalation.py` does not import
    # the module that computes them, and no trigger, verdict or router input
    # exists that could. Ruling B's discipline is labelled evidence first,
    # review second, admission third; 2.3 is the first step only.
    #
    # Empty on every production row today by construction: no production
    # partition carries Paddle evidence, so the offline replay is
    # byte-identical with these columns present. The fold behind each column
    # is stated in `ocr.extraction_quality.EQ_ROW_COLUMNS` and in
    # `DocumentQuality`'s docstring — the minimum where a LOW value is the
    # defect, the maximum where a HIGH one is, the mean for the rec-score
    # distribution, and the worst page's class for `eq_class`.
    eq_version: str = ""
    eq_word_count: str = ""
    eq_density: str = ""
    eq_rec_mean: str = ""
    eq_rec_p10: str = ""
    eq_money_rate: str = ""
    eq_lexicon_rate: str = ""
    eq_garbage_rate: str = ""
    eq_line_height_cv: str = ""
    eq_right_edge_residual: str = ""
    eq_ink_outside_boxes: str = ""
    eq_orientation_votes: str = ""
    eq_class: str = ""
    # P23-AGREE (Phase 2.3 cell X, card item 2). Appended at the END, like
    # every block above. The native<->extractor agreement statistics and the
    # geometry census of ONE document, folded as `layout/agreement.py`'s
    # `DocumentAgreement` declares (every ratio a sum-over-sum across the
    # pages compared; `agree_pages` and `agree_frame_mismatch` counts of
    # pages; `geom_*` over every native page). EMPTY on every row whose
    # document does not carry BOTH a native reading and an extractor reading
    # — a half-measured agreement must never read as a measured one, and
    # today that is every production row, because no production partition
    # holds extractor evidence.
    #
    # These are REVIEW EVIDENCE (plan §H.4, E4) and nothing else: they are
    # written to the row and to nothing else, they reach no router input, no
    # analysis call and no verdict, and `tests/test_agreement.py` pins by AST
    # that neither `ocr/` nor `analysis/` may even name them.
    agree_version: str = ""
    agree_pages: str = ""
    agree_matched_native: str = ""
    agree_matched_paddle: str = ""
    agree_char: str = ""
    agree_amounts: str = ""
    agree_dates: str = ""
    agree_unmatched_table_density: str = ""
    agree_frame_mismatch: str = ""
    geom_rotation: str = ""
    geom_skew_deg: str = ""
    geom_page_size: str = ""

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
        # P22-TRUTHTABLE. The SAME enforcement pattern, extended to this
        # card's columns. `document_class` in particular: the primary
        # classification is DISJOINT — exactly ONE kind per row — and the way
        # a disjointness claim actually dies is a column quietly learning to
        # hold two names joined by a separator, so the row refuses anything
        # that is not one member of the closed vocabulary.
        for field_name, vocabulary in STAGE_VOCABULARY.items():
            value = getattr(self, field_name)
            if value not in vocabulary:
                raise ValueError(
                    f"{field_name} {value!r} is not in the closed vocabulary "
                    f"{tuple(sorted(vocabulary))}"
                )
        for field_name, vocabulary in (
            ("document_class", KINDS), ("class_modality", MODALITIES),
            ("class_account_kind", ACCOUNT_KINDS), ("class_tier", TIERS),
        ):
            value = getattr(self, field_name)
            if value not in vocabulary:
                raise ValueError(
                    f"{field_name} {value!r} is not ONE member of the closed "
                    f"vocabulary {vocabulary}"
                )
        if self.research_partition and re.fullmatch(
                RESEARCH_PARTITION_PATTERN, self.research_partition) is None:
            raise ValueError(
                f"research_partition {self.research_partition!r} must be '' (a production "
                f"row) or match {RESEARCH_PARTITION_PATTERN}"
            )
        # P23-EGATE. The SAME enforcement pattern for the one eq_ column that
        # carries a vocabulary rather than a number: `eq_class` is one member
        # of `ocr.extraction_quality.E_CLASSES` — `""` on every row the
        # projection did not run for, which is every production row.
        if self.eq_class not in E_CLASSES:
            raise ValueError(
                f"eq_class {self.eq_class!r} is not in the closed vocabulary {E_CLASSES}"
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
    #: P21-ROUTING closure (MAJOR-1). `None` on every ordinary read; the
    #: `CacheResult.finding` value (e.g. `CACHE_FINDING_EVIDENCE_DRIFT`) when
    #: the last `cached_ocr` call recomputed because its cached copy failed its
    #: own round-trip check. Read by `process()` right after the `_read` call
    #: and projected onto `row.cache_finding` — a per-instance attribute, not a
    #: per-call return value, for the same reason `_last_ocr_cached` is:
    #: `_read`'s own return tuple is a pinned shape callers and tests already
    #: destructure. (The retired rungs' `_last_visual_*` / `_last_paddle_*`
    #: attributes left with `_read_visual` and `_read_paddle`, slices S2 and S5.)
    _last_ocr_finding: str | None = None
    #: P22-TRUTHTABLE. The per-document facts `_finish` projects onto the row,
    #: and the read whose evidence the geometry seam would consume. NOT
    #: `_last_*` names: that prefix is pinned by AST to the cache dispositions
    #: and their reset, and these two are neither. `process()` resets both at
    #: its top, for the same reason those are reset there.
    _doc_facts: dict = {}
    _geometry_source = None

    def __init__(
        self,
        root: Path,
        *,
        mode: str,
        run_id: str,
        sink=None,
        cache=None,
        dedup: DedupIndex | None = None,
    ) -> None:
        if mode in RETIRED_MODES:
            # Model-code removal (slices S2 and S5): the model rung this mode
            # added was removed (the product uses no model). Refused at
            # construction, before anything is read, rather than run as a
            # silent `--scanned`.
            raise ValueError(
                f"discovery mode {mode!r} is retired: {RETIRED_MODES[mode]}; use {MODE_SCANNED!r}"
            )
        self.root = root
        self.mode = mode
        self.run_id = run_id
        self.sink = sink
        self.cache = cache
        self.dedup = dedup if dedup is not None else DedupIndex.with_pinned_corpus()
        self.allow_local_ocr = mode in LOCAL_OCR_MODES
        self.allow_artifacts = mode == MODE_DRY_RUN

    # -- per-document state -------------------------------------------------

    def _reset_per_document_state(self) -> None:
        """P21-ROUTING closure-2 (MAJOR-A). Every `_last_*` attribute on this
        class is a PER-DOCUMENT cache disposition (`_last_ocr_cached`,
        `_last_ocr_finding`), read back by `process()` right after the `_read`
        call that set it. `discovery/cli.py` drives ONE runner across a whole
        run, and a disposition a read did not reset would project a previous
        document's value onto this row (reproduced in review, MAJOR-A, with a
        cache drift landing on the wrong document). So `process()` calls this
        FIRST, before any read. The class attributes above are the defaults
        this restores; `tests/test_discovery.py` pins by AST that the set
        assigned here equals the set of `_last_*` class attributes, so a
        future attribute cannot be added without its reset."""
        self._last_ocr_cached = False
        self._last_ocr_finding = None

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

    def _project_cache_finding(self, row: "DocumentRow") -> None:
        """P21-ROUTING closure (MAJOR-1). Called right after the `_read`
        invocation: when its `cached_ocr` call observed a drift, the finding
        is projected onto `row.cache_finding`, so the fact that a drift
        happened survives the recompute that immediately follows it inside
        `cached_ocr` — a drifted entry is overwritten in the cache itself, but
        not on this row. `_read` resets `_last_ocr_finding` at its own call,
        AND `process()` resets it (with every other per-document `_last_*`
        attribute) via `_reset_per_document_state` before any read
        (closure-2, MAJOR-A), so it is never a previous document's. A read
        whose recompute FAILED after a drift (MINOR-D) has its finding set
        from the exception `cached_ocr` let through, so the finding lands here
        beside `error_type`. (The retired Paddle rung's finding was projected
        here too until slice S5.)"""
        finding = self._last_ocr_finding
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

    def _analyse(self, markdown: str, collector, sheets=None):
        """(payload, error_type, cached). Deterministic mode; never raises.

        `sheets` is the intake object's page list for the markdown being
        analysed, and it goes to BOTH the analysis and the cache: it is part of
        the analysis input hash, so handing the cache one partition and the
        pipeline another would store an answer under a key that does not
        describe it. None fail-closes, exactly as this call site did before the
        page-declaration check was activated.

        **The geometry seam (P22-TRUTHTABLE item 7, D6), INERT in 2.2.** When
        `Settings.reconstruction_mode` is anything but `off`, the read's own
        evidence becomes a `DocumentGeometry` and is passed to
        `analyze_document` beside the sha that identifies it — and that sha is
        key material, so a geometry-fed analysis and a text-only one of the
        same markdown never share a cache entry (cell K's `analysis_input_sha`).
        When the mode is `off` — which is EVERY run of record, the corpus
        gate, the whole default suite and every cohort replay — this function
        makes the SAME two calls it made before, with the same arguments, in
        the same order: `_geometry_for` returns `(None, None)` without reading
        the setting twice, without touching the evidence, and without
        importing the structurer. The union replay is what proves it rather
        than this paragraph.

        The seam does NOT enable the structurer: reconstruction is 2.4's
        subject and the mode's other two values have no producer in this
        tree. What lands here is the WIRING, so that 2.3 can turn it on for a
        research partition without touching the runner's call shape again.

        The read whose evidence would feed it arrives as `self._geometry_source`,
        set by `process()` immediately before each call, rather than as a
        fifth parameter — this method's four-argument signature is a contract
        tests substitute against with a replacement `_analyse` (the retired
        Paddle routing tests did; `tests/test_two_denominators.py` still does),
        and widening it would break a pin that has nothing to do with geometry.
        """
        geometry, evidence_sha = self._geometry_for(getattr(self, "_geometry_source", None))

        def analyse():
            return document_report_to_dict(analyze_document(
                markdown, parse_mode="deterministic", on_dispatch=collector,
                sheets=sheets,
            ) if geometry is None else analyze_document(
                markdown, parse_mode="deterministic", on_dispatch=collector,
                sheets=sheets, document_geometry=geometry,
            ))

        try:
            if self.cache is None:
                return analyse(), None, False
            from webapp.artifact_cache import cached_analysis

            result = cached_analysis(
                markdown, compute=analyse, cache=self.cache,
                parse_mode="deterministic", sheets=sheets,
            ) if evidence_sha is None else cached_analysis(
                markdown, compute=analyse, cache=self.cache,
                parse_mode="deterministic", sheets=sheets, evidence_sha256=evidence_sha,
            )
            return result.value, None, result.cached
        except Exception as exc:
            return None, type(exc).__name__, False

    @staticmethod
    def _geometry_for(document) -> tuple[object | None, str | None]:
        """`(DocumentGeometry, evidence sha)` when the reconstruction mode is
        ON and the read carries evidence; `(None, None)` otherwise.

        The mode is read from `analysis.config` (cell K's `Settings.
        reconstruction_mode`, default `off`) and is checked FIRST, so on the
        `off` path nothing about the read is inspected at all — not the
        evidence, not its sha, and the structurer's geometry module is not
        imported. That ordering is the inertness: an `off` run does not merely
        discard the geometry, it never builds one.
        """
        if document is None:
            return None, None
        from analysis.config import load_settings as _load_analysis_settings

        if getattr(_load_analysis_settings(), "reconstruction_mode", "off") == "off":
            return None, None
        evidence = getattr(document, "evidence", None) or getattr(document, "native_evidence", None)
        if evidence is None:
            return None, None
        from analysis.structurer.geometry import geometry_from_evidence

        return geometry_from_evidence(evidence), getattr(evidence, "evidence_sha256", None)

    # -- one document -------------------------------------------------------

    # -- the recorded facts (never an input to anything) --------------------

    def _finish(self, row: "DocumentRow", started: float) -> "DocumentRow":
        """The ONE exit of `process()`: project the RECORDED FACTS, stamp the
        elapsed time, hand the row back.

        P22-TRUTHTABLE (D2, case 6). Everything projected here DESCRIBES what
        the intake ladder decided and changes nothing about it — the document
        classification, the layered unresolved reason, the funnel stages, the
        per-document memory reading. Every one is written to the ROW and to
        nothing else: none is passed to `analyze_document`, none reaches a
        router input, none is consulted by any decision above. It runs at
        every exit, including the early ones, so a deferred or refused row
        carries the same columns as a validated one rather than a ragged
        subset.

        That separation is proven rather than asserted:
        `tests/test_two_denominators.py` runs the same document with the
        classifier present and with it stubbed out and asserts the analysis
        payload is byte-identical. A classification that could change a
        verdict would be a routing decision wearing a column's name (D2), and
        the classifier is a proposal for an adjudicator (R3), never truth and
        never an input.
        """
        facts = getattr(self, "_doc_facts", None) or {}
        row.peak_rss_mb = peak_rss_mb()
        self._project_funnel(row, facts)
        self._project_extraction_quality(row, facts)
        self._project_classification(row, facts)
        self._project_agreement(row, facts)
        self._project_taxonomy(row, facts)
        row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return row

    @staticmethod
    def _project_funnel(row: "DocumentRow", facts: dict) -> None:
        """Case 25. Six stages, each read off a fact the row already carries.

        `not_attempted` is never overwritten by a guess: a document whose
        analysis never ran keeps `stage_candidate = not_attempted` rather than
        being filed as `unclaimed`, because "no reader was asked" and "readers
        were asked and none claimed" are the two facts this funnel exists to
        keep apart. The SAME distinction is now drawn on the extraction stage
        (review MINOR-5): a document refused before the ladder ever ran reads
        `not_attempted`, and only a document the ladder ran for and got nothing
        from reads `none`. Both come from the outcome reason the row already
        records — `NO_READ_ATTEMPTED_REASONS`, a closed tuple — never from an
        inference about what probably happened. Geometry and layout stay
        `not_attempted` for every row in 2.2 by construction: nothing in this
        tree builds either.
        """
        never_read = row.outcome_reason in NO_READ_ATTEMPTED_REASONS
        row.stage_extract = (
            STAGE_NOT_ATTEMPTED if never_read
            else row.source_path if row.source_path in STAGE_VOCABULARY["stage_extract"]
            else "none"
        )
        row.stage_evidence = (
            STAGE_NOT_ATTEMPTED if row.source_path == "none"
            else "present" if row.evidence_sha256 else "absent"
        )
        row.stage_geometry = STAGE_NOT_ATTEMPTED   # 2.3 fills this
        row.stage_layout = STAGE_NOT_ATTEMPTED     # 2.4 fills this
        # P23-WAVE (Phase 2.3, case 14): the four technical-telemetry columns,
        # projected from the read of record's OWN `extraction_telemetry` — the
        # figures the retired Paddle rung measured for THIS document's requests
        # and `ocr/pipeline.py` carried onto the document (no rung sets the
        # field since slice S5, so all four stay empty). Nothing is computed here
        # and nothing is inferred: a column a request did not measure stays
        # EMPTY, because an unmeasured figure that renders as a number is a
        # measurement nobody made (the same rule `peak_rss_mb` follows).
        #
        # So these are populated on a LIVE Paddle read and on nothing else:
        # every non-Paddle rung leaves the field `None`, and a `cache_paddle =
        # hit` restores a document without it (the telemetry is transient by
        # ruling and never enters the artifact). Totals per document — the
        # summed inference time and the bytes in each direction — plus the
        # LARGEST per-page VRAM sample the worker reported, which is the only
        # one of the four that is a maximum rather than a sum.
        #
        # There is deliberately no cost, rate, price or billing column here or
        # anywhere near it: cost accounting is out of scope by Gustavo's ruling
        # of 2026-09-03, and `tests/test_two_denominators.py` greps `ROW_FIELDS`
        # and every `summary.json` key for those tokens.
        telemetry = getattr(facts.get("document"), "extraction_telemetry", None)
        if isinstance(telemetry, dict):
            totals = telemetry.get("totals")
            if isinstance(totals, dict):
                sent, received = totals.get("bytes_sent_total"), totals.get("bytes_received_total")
                inference = totals.get("inference_ms_total")
                if isinstance(sent, int) and not isinstance(sent, bool):
                    row.bytes_up = str(sent)
                if isinstance(received, int) and not isinstance(received, bool):
                    row.bytes_down = str(received)
                if isinstance(inference, (int, float)) and not isinstance(inference, bool):
                    row.inference_ms = f"{float(inference):.1f}"
            samples = [
                page.get("gpu_memory_used_mib")
                for page in (telemetry.get("pages") or [])
                if isinstance(page, dict)
            ]
            measured = [value for value in samples
                        if isinstance(value, int) and not isinstance(value, bool)]
            if measured:
                row.vram_mb = str(max(measured))
        dispatch = facts.get("dispatch")
        if dispatch is not None:
            row.stage_candidate = (
                dispatch.outcome if dispatch.outcome in STAGE_VOCABULARY["stage_candidate"]
                else "error"
            )
        elif facts.get("payload") is not None:
            # A payload with no observed dispatch is an analysis-cache hit: a
            # parser claimed it, on the run that filled the cache.
            row.stage_candidate = "claimed"
        elif facts.get("analysed"):
            row.stage_candidate = "error"
        if row.outcome_class in STAGE_VOCABULARY["stage_verdict"]:
            row.stage_verdict = row.outcome_class

    @staticmethod
    def _project_extraction_quality(row: "DocumentRow", facts: dict) -> None:
        """P23-EGATE: the thirteen `eq_*` columns, from the document's
        EXTRACTOR evidence and from nothing else.

        **Only an extractor's evidence is measured.** `StatementMarkdown`
        carries two evidence fields and they are not the same kind of thing:
        `evidence` is what an EXTRACTOR produced (today, the Paddle rung) and
        `native_evidence` is the native reader's record of text the document
        already carried. The extraction-quality question — did this
        extractor's own output come out usable — is not asked of a native
        read, exactly as `ExtractionQualityGate` is not called on one
        (`GATE_ASSESSED_SOURCES`); an unclaimed native document is a layout
        problem, never a Class-A extraction failure. So this reads
        `document.evidence`, never `native_evidence`, and refuses the native
        reader's id a second time in case some later rung ever attaches one
        there. Two independent conditions, because the mutant this kills
        (measure the native rows too) survives either one alone.

        **It is a projection, not a decision.** It runs at the row's single
        exit, after the analysis has already finished, and writes to the ROW
        and to nothing else. Nothing above reads an `eq_*` value; nothing can,
        because `ocr/escalation.py` does not import the module that computes
        them and `RouterInputs` has nowhere to put one.

        The ink columns are empty in production by construction: a page's
        pixels are not retained outside a research partition (`raster_sha256`
        only), and the census — which has the retained rasters — is where the
        ink metric is measured.

        A defect here is a FINDING, never a lost document: the same rule
        `_project_classification` follows for the same reason — a reporting
        consumer must not be able to fail a run. There is deliberately no
        `eq_exception` column (the card's column list is closed); a defect
        leaves the columns empty and shows up as a population that should
        have had them.
        """
        document = facts.get("document")
        evidence = getattr(document, "evidence", None) if document is not None else None
        if evidence is None or getattr(evidence, "extractor_id", "") == NATIVE_EXTRACTOR_ID:
            return
        try:
            values = eq_row_values(
                evidence, truncated_pages=tuple(getattr(document, "truncated_pages", ()) or ()),
            )
        except Exception:  # a recorded fact never fails a run
            return
        for column, _, _ in EQ_ROW_COLUMNS:
            setattr(row, column, values[column])

    @staticmethod
    def _project_classification(row: "DocumentRow", facts: dict) -> None:
        """D2: the classifier's verdict as a RECORDED FACT.

        Called after the read and before nothing — the analysis has already
        happened by the time this runs, which is a stronger guarantee than the
        card's "before analysis": the verdict cannot reach `analyze_document`
        because `analyze_document` is already finished.

        A classifier defect is a FINDING on the row, never a lost document:
        the exception's class name is recorded and the row keeps its honest
        `KIND_UNCERTAIN` default at `class_version = 0`. A reporting consumer
        must not be able to fail a run.
        """
        profile = facts.get("profile")
        if profile is None or not facts.get("classify"):
            return
        pages = tuple(facts.get("pages") or ())
        document = facts.get("document")
        evidence = (getattr(document, "evidence", None)
                    or getattr(document, "native_evidence", None)) if document is not None else None
        try:
            verdict = classify_document_kind(
                evidence=evidence,
                page_texts=None if evidence is not None else pages,
                profile=DocumentProfileFacts(
                    valid_pdf=profile.valid_pdf, encrypted=profile.encrypted,
                    page_count=profile.page_count, classification=profile.classification,
                    page_text_chars=tuple(len(page.strip()) for page in pages),
                    magic=facts.get("magic"),
                ),
            )
        except Exception as exc:  # a recorded fact never fails a run
            row.classifier_exception = type(exc).__name__
            return
        row.document_class = verdict.kind
        row.class_sub_kind = verdict.sub_kind or ""
        row.class_modality = verdict.modality
        row.class_account_kind = verdict.account_kind
        row.class_tier = verdict.tier
        row.class_version = verdict.version
        row.class_signals = "|".join(sorted({ref.signal for ref in verdict.evidence}))
        row.completeness_findings = ";".join(sorted({f.code for f in verdict.completeness}))
        facts["verdict"] = verdict

    @staticmethod
    def _project_agreement(row: "DocumentRow", facts: dict) -> None:
        """P23-AGREE item 2: the agreement statistics and the geometry census
        as RECORDED FACTS, at the row's single exit.

        Projected ONLY when the document carries BOTH readings — the native
        reader's `native_evidence` AND an extractor's `evidence` — and EMPTY
        otherwise, which is every row of every production run today. There is
        deliberately no fallback to one source: the columns describe a
        comparison, and a comparison with one side missing is not a weaker
        comparison, it is no comparison at all.

        Like the classification above, this runs AFTER the analysis has
        already finished, so the numbers cannot reach `analyze_document` even
        in principle; and like it, a defect here is a FINDING (empty columns)
        rather than a lost document — a reporting consumer must never fail a
        run. The E4 discipline (plan §H.4) in one sentence: these are review
        evidence on the row, they start nothing, and no extractor, router or
        validator may read them.
        """
        try:
            # The two attribute READS are inside the guard too (review
            # closure, MINOR-6): `getattr` swallows only `AttributeError`, so
            # a document object whose `evidence` property raises anything else
            # would otherwise propagate out of here and out of `_finish` —
            # the run-failing consumer this method exists not to be.
            document = facts.get("document")
            native = getattr(document, "native_evidence", None) if document is not None else None
            extractor = getattr(document, "evidence", None) if document is not None else None
            if native is None or extractor is None:
                return
            columns = agreement_row_columns(document_agreement(native, extractor))
        except Exception:  # as above: a recorded fact never fails a run
            return
        for name in AGREE_COLUMNS:
            setattr(row, name, columns[name])

    @staticmethod
    def _project_taxonomy(row: "DocumentRow", facts: dict) -> None:
        """The seven layers and the primary pair (item 1).

        The W3-2 diagnostics are recomputed here from the payload the row
        already produced rather than read back out of the emitted record: the
        record is written by `_emit`, which is allowed to be a no-op (a
        `NullSink` run, a sink that raised), and a row must not lose its
        financial layer because telemetry was off. `diagnose_document` is a
        pure projection over the payload — the same one `build_record` calls —
        so the two cannot disagree.
        """
        from telemetry.diagnostics import diagnose_document

        diagnostics = None
        try:
            diagnostics = diagnose_document(facts.get("payload"), row.outcome_class)
        except Exception:  # as above: a reporting consumer never fails a run
            diagnostics = None
        diagnosis = diagnose_unresolved(
            row, diagnostics, facts.get("verdict"),
            evidence_reasons=tuple(facts.get("evidence_reasons") or ()),
        )
        for name, value in diagnosis.as_row_fields().items():
            setattr(row, name, value)

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
        # P22-TRUTHTABLE: the per-document facts the recorded-fact projection
        # reads at `_finish`, and the read whose evidence the geometry seam
        # would use. Reset here for the same reason the `_last_*` attributes
        # are: one runner drives a whole run, and a previous document's facts
        # projected onto this row would be a defect of exactly the shape
        # MAJOR-A found. They are NOT `_last_*` attributes — the AST pin over
        # that prefix is about cache dispositions and stays exact.
        self._doc_facts = {}
        self._geometry_source = None
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
        self._doc_facts.update({"profile": profile, "magic": raw[:4].hex().upper()})

        if self.mode == MODE_PROFILE_ONLY:
            row.outcome_class, row.outcome_reason = "deferred", "profile_only"
            return self._finish(row, started)

        if not profile.valid_pdf or profile.encrypted:
            # The classifier decides `FILE_INVALID` from the profile FACTS
            # alone, before any text exists — so this path is classified too,
            # and the L0 layer of these rows carries the classifier's verdict
            # rather than a second opinion derived from a row column.
            self._doc_facts["classify"] = True
            row.outcome_class = "failed"
            row.outcome_reason = "encrypted" if profile.encrypted else "invalid_pdf"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_reason=row.outcome_reason)
            return self._finish(row, started)

        name = Path(relative_path).name
        try:
            with timer.time("ocr"):
                document, markdown, sheets, note = self._read(raw, name, profile)
        except LocalOcrIncomplete as exc:
            # Audit 2026-10-13 (REL-01): the local Tesseract rung refuses a read it could not finish (a time limit
            # passed, a short render, a host failure) instead of returning a partial one. The document fails
            # closed under the visual rung's `ocr_failed` and the run goes on; nothing was cached, so a later run
            # reads it afresh. Class name only, as for every other failure.
            self._last_ocr_finding = self._cache_finding_of(exc)
            self._project_cache_finding(row)
            row.outcome_class, row.outcome_reason = "failed", "ocr_failed"
            row.error_type = type(exc).__name__
            row.source_path = "none"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_type=row.error_type, error_reason="ocr_failed")
            return self._finish(row, started)
        self._project_cache_finding(row)

        if markdown is None:
            # Recorded, never skipped. Two different findings, kept apart
            # because DSC-2 acts on them differently:
            if note == "deferred_offline_rungs":
                # An offline tranche (digital, dry-run) met a document only
                # Tesseract could read: work this tranche deliberately did not
                # do. `deferred` is its own outcome class precisely so that
                # `failed` can keep meaning "attempted and errored".
                row.outcome_class, row.outcome_reason = "deferred", "deferred_scanned"
                row.source_path = "none"
                self._emit(row, profile, None, None, None, collector, timer,
                           deferred=row.outcome_reason)
                return self._finish(row, started)
            # `--scanned`: the offline ladder, Tesseract included, RAN and read
            # nothing usable. Until slice S5 of the model-code removal this was
            # `deferred:deferred_visual_ocr` ("left for the visual rung"), and
            # the Paddle modes went on to a RECOVERY read here. No model rung
            # remains (owner ruling of 2026-10-13: the product uses no model),
            # so nothing is left to defer to: the platform declines the
            # document, fail-closed, for a closed `REFUSED_REASONS` member, in
            # the row and in the telemetry record alike (declared: 13 documents
            # of the archive move). `insufficient_evidence` claims no judgement
            # about what the document is (that would be `unreadable`, an L1
            # kind); it maps to the same taxonomy layer the deferral did
            # (l2 `E0_no_evidence`), and like `deferred` it is unranked.
            row.outcome_class, row.outcome_reason = "refused", "insufficient_evidence"
            row.source_path = "none"
            self._emit(row, profile, None, None, None, collector, timer,
                       refused="insufficient_evidence")
            return self._finish(row, started)

        source = source_section(document)
        _project_source(row, source, committed_artifact=(note == "committed_artifact"))
        # The read of record for this document, recorded for the classifier and
        # the taxonomy.
        self._doc_facts.update({
            "classify": True, "document": document,
            "pages": list(document.pages) if document is not None else list(sheets or ()),
        })

        # P20-ROUTER item 2c. The extraction-quality verdict, computed from the
        # read alone, before `_analyse` runs below. It is a RECORDED FACT (the
        # row's `evidence_quality` and, below, `failure_class`); since slice S5
        # no escalation decision reads it, because none is made.
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

        self._geometry_source = document
        with timer.time("analysis"):
            payload, error_type, analysis_cached = self._analyse(markdown, collector, sheets)
        self._doc_facts["analysed"] = True

        # One detection sweep, read twice: for the near-miss vector (H-3) and,
        # on a cache-served row, for the parser identity the absent `Dispatch`
        # would otherwise have carried. Hoisted above the projection because
        # both consumers need it; `score_vector` is pure, so where it is called
        # changes nothing it returns.
        # `collector` is the dispatch of record for THIS markdown (until slice
        # S5 it was rebound when an escalated re-read was adopted), so the
        # near-miss sweep reuses the preparation the analysis already paid
        # for (#PREPHAND).
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
        # P20-ROUTER. `evidence` above is the read of record's (the one read
        # since slice S5 removed the upgrade adoption); `payload is not None` is
        # exactly "claimed" in deterministic mode (`analysis/pipeline.py`
        # raises on every other resolve outcome — see `classify_failure`'s
        # docstring and `tests/test_escalation_router.py`'s pin of that
        # claim).
        row.failure_class = classify_failure(
            evidence, claimed=payload is not None, validated=row.outcome_class == "validated",
        )
        # The facts the recorded-fact projection reads. `evidence.reasons` is
        # the ONE input the taxonomy's extraction layer needs that no row
        # column carries: the row records the gate's VERDICT
        # (`evidence_quality`), and the reasons behind an `unusable` verdict
        # are what tell E0 from E1. Handing them over here — rather than
        # letting the taxonomy re-derive them — is what keeps that layer
        # populated only from facts, never from inference.
        self._doc_facts.update({
            "payload": payload, "dispatch": dispatch,
            "evidence_reasons": tuple(evidence.reasons),
        })

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
        return self._finish(row, started)

    # -- telemetry ----------------------------------------------------------

    def _emit(
        self, row, profile, document, markdown, payload, collector, timer,
        *, error_type=None, error_reason=None, deferred=None, scores=None,
        escalated=False, fallback_reason=None, refused=None,
    ) -> None:
        """One H-3 record per enumerated document. Never raises.

        The record shape is H-3's, unchanged and unextended: discovery is a
        telemetry CONSUMER. Note what does NOT cross into it — the relative
        path, the folder label, the bank label and the masked account live in
        the discovery row only, because the H-3 sensitivity invariant forbids
        them and the discovery report is a different artifact with a different
        audience.

        `refused` (slice S5) is passed through to `build_record`'s existing
        `refused` field, exactly as `deferred` is, so a row the runner declines
        (`refused:insufficient_evidence`) and its telemetry record carry the
        same outcome. No record field is added.
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
                refused=refused,
            ))
        except Exception:
            return None


def _disposition(cache, cached: bool) -> str:
    return "bypass" if cache is None else ("hit" if cached else "miss")


def _project_source(row: "DocumentRow", source: dict, *, committed_artifact: bool = False) -> None:
    """The row's source-provenance columns, from `telemetry.record.source_section`.

    ONE function, so every call site projects the SAME fields the same way
    (the RECOVERY and UPGRADE adoption sites that also called it were removed
    with the escalation rungs, slice S5) — `evidence_sha256` /
    `paddle_provider` / `paddle_execution_class` (P21-ROUTING) are
    empty-string for every read that carries no extractor evidence (every
    rung that remains, and every pre-Phase-2.1 cached artifact)."""
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
    shape `visual_rung` always has. The two were mutually exclusive in
    practice (each escalation mode enabled one extractor), so at most one of
    the two checks below ever fired for a given row; since slice S5 both rungs
    are `not_attempted` on every row and this returns None."""
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
