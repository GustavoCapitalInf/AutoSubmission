"""telemetry/unresolved_taxonomy.py — the layered unresolved-reason taxonomy
(the idiom of `W3_2_TAXONOMY.md`).

"755 unresolved" is one number. This module makes it seven, one per LAYER, and
names exactly one of them the document's PRIMARY reason — so "why does this
file not validate" has one defensible answer, and the finer layers stay
visible beside it instead of being averaged into it.

A document carries **one code per layer**. The primary reason is the
highest-RANKED non-empty layer, ranked most-upstream first — the same
cause-over-symptom rule `telemetry/diagnostics.py::CLASS_PRECEDENCE` already
applies inside one layer (§4 of the taxonomy document). A statement that is
missing pages AND fails its detail coverage is reported by the missing pages;
reporting it by the arithmetic that noticed them would aim remediation at the
check instead of the cause.

The precedence table (asserted equal to `LAYER_PRECEDENCE` and `LAYER_NAMES`
by `tests/test_unresolved_taxonomy.py`, the W3-2 doc/code guard idiom — the
two cannot drift):

| # | layer | name | what it means |
|---|---|---|---|
| 1 | l0 | FILE | the bytes are not a readable document at all |
| 2 | l1 | KIND | a readable document, but not a complete statement |
| 3 | l2 | EXTRACTION | a statement whose text an extractor did not recover (Class A) |
| 4 | l3 | STRUCTURE | recovered text no reader could turn into records (Class B) |
| 5 | l4 | FINANCIAL | records that failed a financial check (Class C; the W3-2 classes) |
| 6 | l5 | DOCTRINE | the platform refusing on a ruled rule rather than on a defect |
| 7 | l6 | UNKNOWN | the taxonomy saw nothing — itself a finding, never nulled |

Four properties, each enforced by a mechanism rather than by this paragraph:

1. **Closed per layer, with an explicit `unmapped`.** Every layer's tuple is
   closed and every one carries `UNMAPPED`, so a reason `discovery/`,
   `telemetry/`, `ocr/` or `layout/` grows that this module has never seen
   lands in `unmapped` at RUNTIME and fails a drift guard at BUILD time. It is
   never nulled and never silently absorbed into a neighbouring code.
2. **Read-only, and derived only from facts the row already carries.** Nothing
   here recomputes anything. L2 is populated from the extraction gate's own
   reasons and the truncation count; L3 and L5 from the outcome reason the
   runner already emitted; L4 from the W3-2 diagnostics section that is
   already on the record; L0/L1 from the classifier's verdict. A kind never
   manufactures an E-code and an outcome never manufactures a B-code: an
   ILLEGIBLE classification is a statement about the DOCUMENT, not evidence
   that an extractor failed, and a withheld document is not evidence that its
   structure was unresolved.
3. **`valid_pdf` is deliberately NOT read here.** Whether a file is a document
   at all is the classifier's decision (`layout.document_class` refuses it as
   `FILE_INVALID` from the profile facts, before any text is read), and
   re-deriving it from a row column would give the taxonomy a second, quieter
   opinion about L0 that could disagree with the recorded one. The row facts
   this module does read are `outcome_class`, `outcome_reason`, `encrypted`,
   `evidence_quality` and `truncated_pages` — and a row OBJECT
   (`discovery.runner.DocumentRow`) and a row MAPPING (a `rows.csv` line)
   diagnose identically, which is pinned.
4. **A validated document carries no reason at all.** Not an empty diagnosis —
   no diagnosis: the seven columns and the primary pair are all empty. This is
   the same scoping decision `DIAGNOSABLE_CLASSES` makes for W3-2, restated
   for a wider ladder, and it is what keeps the unresolved tables about the
   unresolved.

`UNRESOLVED_TAXONOMY_VERSION` travels in every diagnosis for the reason
`DIAGNOSTICS_VERSION` travels in every record: a report spanning a vocabulary
change is not comparing like with like, and `discovery/report.py` prints a
`WARNING mixed unresolved-taxonomy versions` line when it sees more than one.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from .diagnostics import CLASS_PRECEDENCE, DIAGNOSABLE_CLASSES

__all__ = [
    "EVIDENCE_REASON_CODE",
    "L0_CODES",
    "L1_KINDS",
    "L2_CODES",
    "L3_CODES",
    "L4_CODES",
    "L5_CODES",
    "L6_CODES",
    "LAYERS",
    "LAYER_NAMES",
    "LAYER_PRECEDENCE",
    "REASON_LAYER",
    "RETIRED_RUNNER_REASONS",
    "UNMAPPED",
    "UNRESOLVED_TAXONOMY_VERSION",
    "VOCABULARY",
    "KindFacts",
    "UnresolvedDiagnosis",
    "diagnose_unresolved",
    "kind_facts_from_document_class",
    "parse_l1_code",
    "runner_reason_literals",
]

#: v1 — P22-TRUTHTABLE, as shipped. Bumped whenever a layer's vocabulary or
#: the precedence changes, for the reason `DIAGNOSTICS_VERSION` is bumped.
#:
#: WHEN THE BUMP RULE STARTS BINDING (Ocean's reading, recorded here because the
#: question is about this constant and nowhere else). The closure added a code
#: to a layer's set and left this number at 1, which reads against the rule one
#: line above. It is not: **version 1 has never been emitted by any run of
#: record.** No artifact anywhere carries the column — the reviewer checked —
#: and this cell is a single unmerged delivery, so there is no v1 rollup in
#: existence for a v2 rollup to be incomparable WITH. A vocabulary change made
#: BEFORE the first run of record at v1 is therefore part of what v1 turns out
#: to be, not a change to it, and does not bump.
#:
#: From the first run of record that RECORDS v1 onward, the rule binds without
#: exception, exactly as `DIAGNOSTICS_VERSION` is governed: ANY change to a
#: layer's code set — added, removed or renamed — or to the precedence is a
#: bump WITH a changelog entry. The reason is the same one that makes
#: `DIAGNOSTICS_VERSION` non-optional: once two runs exist either side of a
#: vocabulary change, the version is the ONLY thing that can tell a reader
#: their class counts are not comparing like with like, and that is most true
#: when the change fires on zero documents and nothing else looks different.
UNRESOLVED_TAXONOMY_VERSION = 1

#: The one name every layer's closed vocabulary carries, so nothing is ever
#: dropped. Spelled the same as the W3-2 class of the same purpose.
UNMAPPED = "unmapped"

LAYERS: tuple[str, ...] = ("l0", "l1", "l2", "l3", "l4", "l5", "l6")

#: Ranked most-upstream first; the primary reason is the highest-ranked
#: non-empty layer. Equal to `LAYERS` today and kept as its own name because
#: the ORDER is the ruling, not the numbering.
LAYER_PRECEDENCE: tuple[str, ...] = LAYERS

LAYER_NAMES: dict[str, str] = {
    "l0": "FILE",
    "l1": "KIND",
    "l2": "EXTRACTION",
    "l3": "STRUCTURE",
    "l4": "FINANCIAL",
    "l5": "DOCTRINE",
    "l6": "UNKNOWN",
}

# ---------------------------------------------------------------------------
# the per-layer vocabularies (plan §D.4, verbatim members)
# ---------------------------------------------------------------------------

#: L0 FILE. `FILE_INVALID` is also a `layout.refusals.KINDS` member — the
#: classifier decides it, this layer records it, and it lives at L0 rather
#: than L1 because "not a document" is upstream of "not a statement".
L0_CODES: tuple[str, ...] = ("FILE_INVALID", "FILE_ENCRYPTED")

#: L1 KIND. The classifier's kinds MINUS `STATEMENT_COMPLETE` (a complete
#: statement is no kind-layer reason) and MINUS `FILE_INVALID` (which is L0).
#: The rendered code carries the sub-kind or the completeness findings in
#: braces — `parse_l1_code` is the reader.
L1_KINDS: tuple[str, ...] = (
    "STATEMENT_PARTIAL",
    "STATEMENT_ILLEGIBLE",
    "ACTIVITY_EXPORT",
    "NOT_A_STATEMENT",
    "KIND_UNCERTAIN",
)

#: L2 EXTRACTION (Class A), plan §D.4. Ranked most-upstream first WITHIN the
#: layer, which is what "the most upstream E-code wins" means when an
#: extractor reports several reasons at once. E4 is cross-engine disagreement
#: — review evidence, produced by nothing before 2.3; E2/E3 are populated by
#: 2.3's per-extractor measurement. Only E0, E1 and E5 have a producer today,
#: and each of those is a fact the row already carries.
L2_CODES: tuple[str, ...] = (
    "E0_no_evidence",
    "E1_coverage_gap",
    "E2_recognition_quality",
    "E3_frame_orientation",
    "E4_cross_engine_disagreement",
    "E5_truncation_bleed",
)

#: L3 STRUCTURE (Class B), plan §D.4 B1-B8, plus the two B0 facts that exist
#: TODAY: the coarse "no reader claimed this document" and "more than one
#: reader claimed it". B1-B8 are the LayoutModel's refusal sub-classes and are
#: populated by 2.4 — declared now so the vocabulary a report prints does not
#: change under it.
L3_CODES: tuple[str, ...] = (
    "B0_no_reader_claimed",
    "B0_reader_ambiguous",
    "B1_no_table_region",
    "B2_column_model_unresolved",
    "B3_records_unassembled",
    "B4_summary_anchors_not_found",
    "B5_account_partition_ambiguous",
    "B6_cross_page_continuity_broken",
    "B7_grounding_failed",
    "B8_sign_undeterminable",
)

#: L4 FINANCIAL (Class C) = the W3-2 classes UNCHANGED, by identity rather
#: than by copy: this layer IS that taxonomy, and a copy would be a second
#: vocabulary to keep in sync. It already carries its own `unmapped` and its
#: own `undiagnosed`.
L4_CODES: tuple[str, ...] = CLASS_PRECEDENCE

#: L5 DOCTRINE, plan §D.4. `declined_by_claiming_reader` sits here rather than
#: at L3 because a reader that CLAIMED and then declined made a ruled refusal
#: about a document it recognised — R13 is the ruling that may later move that
#: population, and until it does, filing it as "structure unresolved" would
#: claim knowledge nobody has. `currency_package_refusal` and
#: `pinned_adjudicated_refusal` are declared and produced by nothing today.
L5_CODES: tuple[str, ...] = (
    "q3_sibling_omission_refusal",
    "currency_package_refusal",
    "not_a_formal_statement",
    "declined_by_claiming_reader",
    "pinned_adjudicated_refusal",
)

#: L6 UNKNOWN. `unmapped` (the taxonomy saw nothing it knows) is the layer's
#: own member via `VOCABULARY`; these three are the facts that ARE known and
#: are still not a reason the document could not validate.
L6_CODES: tuple[str, ...] = (
    "not_attempted_by_run",
    "platform_exception",
    "platform_defect",
    #: The layer's own meaning, §D.4 verbatim: "the taxonomy saw nothing — itself
    #: a finding, never nulled". Distinct from `unmapped`, and the distinction
    #: is the point: `unmapped` means the taxonomy met a code it has never seen,
    #: `unknown` means it met a document every layer had nothing to say about.
    #: Review MINOR-4 (reproduced on 20 class/reason pairs): without this the
    #: "never nulled" property rested on a coincidence in `telemetry/record.py`
    #: — that every reason mapped to `None` happens to be paired with a
    #: diagnosable class — rather than on this module closing the gap itself.
    "unknown",
)

VOCABULARY: dict[str, tuple[str, ...]] = {
    "l0": L0_CODES + (UNMAPPED,),
    "l1": L1_KINDS + (UNMAPPED,),
    "l2": L2_CODES + (UNMAPPED,),
    "l3": L3_CODES + (UNMAPPED,),
    # L4 already carries `unmapped` — it IS the W3-2 precedence list.
    "l4": L4_CODES,
    "l5": L5_CODES + (UNMAPPED,),
    "l6": L6_CODES + (UNMAPPED,),
}

# ---------------------------------------------------------------------------
# the reason map: every outcome reason the tree can emit -> a layer, or None
# ---------------------------------------------------------------------------

#: `None` means "this reason names no layer of its own": the layer comes from
#: another fact on the record (the W3-2 diagnostics for the financial classes)
#: or the document did not fail at all. It is an explicit entry, not an
#: omission, precisely so the drift guard can tell "mapped to nothing on
#: purpose" from "nobody has looked at this yet" — the second lands in
#: `unmapped` and fails the guard.
#:
#: `tests/test_unresolved_taxonomy.py::test_every_reason_the_runner_and_the_
#: record_can_emit_is_in_the_reason_map` reads the runner's and the record's
#: SOURCE (via `runner_reason_literals`) and asserts this mapping's key set is
#: exactly those literals plus `DEFERRED_REASONS` plus `REFUSED_REASONS` plus
#: `RETIRED_RUNNER_REASONS` — both directions, so a new reason fails the build
#: and a retired one does too unless it is DECLARED retired below.
REASON_LAYER: dict[str, tuple[str, str] | None] = {
    # -- L0: the file ------------------------------------------------------
    "invalid_pdf": ("l0", "FILE_INVALID"),
    "file_invalid": ("l0", "FILE_INVALID"),          # a reserved `refused` reason (nothing emits it)
    "encrypted": ("l0", "FILE_ENCRYPTED"),
    # -- L1: the kind (reserved `refused` reasons; nothing emits them, and
    #    each names the kind the platform declined the file AS) -------------
    "not_a_statement": ("l1", "NOT_A_STATEMENT"),
    "incomplete": ("l1", "STATEMENT_PARTIAL"),
    "unreadable": ("l1", "STATEMENT_ILLEGIBLE"),
    # -- L2: extraction ----------------------------------------------------
    #    `deferred_visual_ocr` is trigger R: the offline ladder produced NO
    #    text for a document it did attempt, which is an extraction fact.
    #    `deferred_scanned` is NOT (see L6): that mode never ran an extractor.
    #    Since slice S5 of the model-code removal the runner records trigger R
    #    as the refusal `insufficient_evidence` (the same layer and code), and
    #    `deferred_visual_ocr` / `escalation_refused` are historical (see
    #    `RETIRED_RUNNER_REASONS`).
    "deferred_visual_ocr": ("l2", "E0_no_evidence"),
    "ocr_failed": ("l2", "E0_no_evidence"),
    "escalation_refused": ("l2", "E0_no_evidence"),
    "insufficient_evidence": ("l2", "E0_no_evidence"),
    # -- L3: structure -----------------------------------------------------
    "no_parser_matched": ("l3", "B0_no_reader_claimed"),
    "parser_ambiguous": ("l3", "B0_reader_ambiguous"),
    # -- L4: financial -----------------------------------------------------
    #    None: the W3-2 diagnostics section on the same record already names
    #    the CLASS, and it is finer than the outcome reason is. Re-deriving a
    #    class from `withheld_adb` would throw that away.
    "withheld_adb": None,
    "integrity_flags": None,
    "integrity_check_exception": None,
    "quality_needs_review": None,
    # -- L5: doctrine ------------------------------------------------------
    "parser_declined": ("l5", "declined_by_claiming_reader"),
    "q3_provenance_refused": ("l5", "q3_sibling_omission_refusal"),
    "document_omission_unratified": ("l5", "q3_sibling_omission_refusal"),
    "contradictory": ("l4", "source_contradiction"),  # a reserved `refused` reason (nothing emits it)
    # -- L6: known, and still not a reason ---------------------------------
    "profile_only": ("l6", "not_attempted_by_run"),
    "deferred_scanned": ("l6", "not_attempted_by_run"),
    "not_processed": ("l6", "not_attempted_by_run"),
    "paddle_refused": ("l6", "not_attempted_by_run"),
    "research_skipped_not_in_population": ("l6", "not_attempted_by_run"),
    "research_refused_holdout": ("l6", "not_attempted_by_run"),
    "parser_exception": ("l6", "platform_exception"),
    "exception": ("l6", "platform_exception"),
    "document_publishes_no_account": ("l6", "platform_defect"),
    # -- not a failure at all ----------------------------------------------
    "approved": None,
    "no_analysis": ("l6", "platform_defect"),
}

#: The runner outcome reasons whose only emitter was removed with the model
#: rungs (model-code removal, slice S5): exactly the runner's reason literals
#: at the slice's parent (`57ca19a`) minus those at its head, as
#: `runner_reason_literals` reads them (measured; plan D13). Historical rows,
#: telemetry records and run summaries still carry them, so they stay in
#: `REASON_LAYER` (append-only) and the drift guard's expected set includes
#: this set. `tests/test_unresolved_taxonomy.py` also pins that NO member has
#: an emitter in the runner or the record today, so a retired name cannot
#: quietly come back into use under this exemption.
#:
#: * `deferred_visual_ocr`: trigger R's old spelling (the runner records
#:   `refused:insufficient_evidence` since S5); also a `DEFERRED_REASONS`
#:   member, kept for historical rows;
#: * `escalation_refused`: the retired escalation modes' terminal refusal;
#: * `paddle_refused`: the retired Paddle rung's customer-data refusal;
#: * `research_skipped_not_in_population`, `research_refused_holdout`: the
#:   retired research mode's two doors (also `DEFERRED_REASONS` members).
RETIRED_RUNNER_REASONS: frozenset[str] = frozenset({
    "deferred_visual_ocr",
    "escalation_refused",
    "paddle_refused",
    "research_refused_holdout",
    "research_skipped_not_in_population",
})

#: The extraction gate's OWN reasons (`ocr.escalation.ExtractionQualityGate`)
#: mapped to L2 codes. The guard reads the gate's source and asserts this
#: mapping's key set is exactly what it can produce, so a fourth reason there
#: fails the build here.
EVIDENCE_REASON_CODE: dict[str, str] = {
    "no_text_produced": "E0_no_evidence",
    "all_pages_empty": "E0_no_evidence",
    "below_char_floor": "E1_coverage_gap",
}

#: The W3-2 diagnostic CODE that is a doctrine fact rather than a financial
#: check: `not_a_formal_statement` is a document class the integrity pass
#: recorded, and W3-2 classes it advisory precisely because it is not a
#: failure of arithmetic. At L5 it is the reason it always was.
_DOCTRINE_CODE_L5: dict[str, str] = {
    "integrity:not_a_formal_statement": "not_a_formal_statement",
}

#: `classify_document`'s fold prefixes the WEAKEST account's reason with
#: `account_` (`telemetry/record.py`). The document-level reason is therefore
#: the account-level one wearing a prefix, and it is read through it rather
#: than mapped twice.
_ACCOUNT_PREFIX = "account_"


# ---------------------------------------------------------------------------
# the classifier's L1 vocabulary, read lazily
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _l1_members() -> frozenset[str]:
    """The closed set of names an L1 code may carry inside its braces: the
    classifier's sub-kinds and its completeness findings.

    Imported LAZILY and cached. `telemetry` is a write-only side-band that
    `webapp/`, `batch.py` and `discovery/` all import at module level; making
    `import telemetry` drag in `layout` (and, through it, `evidence`) for one
    vocabulary would spend that cost on every caller, including the ones that
    never diagnose anything.
    """
    from layout.refusals import FINDING_CODES, SUB_KINDS

    return frozenset(SUB_KINDS) | frozenset(FINDING_CODES)


def render_l1_code(kind: str, sub_kind: str | None, findings: tuple[str, ...]) -> str:
    """`NOT_A_STATEMENT{loan_statement}` / `STATEMENT_PARTIAL{a;b}` / `KIND_UNCERTAIN`.

    Members are de-duplicated and SORTED, so the code is a function of the
    verdict and not of the order the classifier happened to append its
    findings in — two runs over the same bytes must produce the same string.
    """
    members = sorted({m for m in ((sub_kind,) if sub_kind else ()) if m}
                     | {f for f in findings if f})
    return f"{kind}{{{';'.join(members)}}}" if members else kind


def parse_l1_code(code: str) -> tuple[str, tuple[str, ...]] | None:
    """`(kind, members)` for a well-formed L1 code, else `None`.

    Refuses `STATEMENT_COMPLETE` (not an L1 reason), `FILE_INVALID` (L0), a
    member outside the classifier's closed vocabulary, and empty braces. The
    round trip is what lets a report re-group rendered codes by kind without
    re-running the classifier.
    """
    if not isinstance(code, str) or not code:
        return None
    match = re.fullmatch(r"([A-Z_]+)(?:\{([A-Za-z0-9_;]+)\})?", code)
    if match is None:
        return None
    kind, body = match.group(1), match.group(2)
    if kind not in L1_KINDS:
        return None
    if body is None:
        return kind, ()
    members = tuple(body.split(";"))
    if not all(member in _l1_members() for member in members):
        return None
    return kind, members


# ---------------------------------------------------------------------------
# the inputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KindFacts:
    """The classifier's verdict, reduced to the three facts L0/L1 read.

    A separate type rather than the `DocumentClass` itself so this module
    never depends on that dataclass's shape, and so a row that carries only
    the three RECORDED columns (`document_class`, `class_sub_kind`,
    `completeness_findings`) can be diagnosed exactly like a live verdict.
    """

    kind: str
    sub_kind: str | None
    findings: tuple[str, ...]


def kind_facts_from_document_class(verdict: Any | None) -> KindFacts | None:
    """`layout.document_class.DocumentClass` -> `KindFacts`; `None` -> `None`."""
    if verdict is None:
        return None
    if isinstance(verdict, KindFacts):
        return verdict
    return KindFacts(
        kind=verdict.kind,
        sub_kind=verdict.sub_kind,
        findings=tuple(finding.code for finding in verdict.completeness),
    )


@dataclass(frozen=True)
class UnresolvedDiagnosis:
    """One code per layer, plus the primary pair and the vocabulary version."""

    reason_l0: str
    reason_l1: str
    reason_l2: str
    reason_l3: str
    reason_l4: str
    reason_l5: str
    reason_l6: str
    primary_layer: str
    primary_code: str
    version: int

    def as_row_fields(self) -> dict[str, object]:
        """The row columns, in `ROW_FIELDS` order."""
        return {
            "reason_l0": self.reason_l0,
            "reason_l1": self.reason_l1,
            "reason_l2": self.reason_l2,
            "reason_l3": self.reason_l3,
            "reason_l4": self.reason_l4,
            "reason_l5": self.reason_l5,
            "reason_l6": self.reason_l6,
            "primary_reason_layer": self.primary_layer,
            "primary_reason": self.primary_code,
            "unresolved_taxonomy_version": self.version,
        }


EMPTY_DIAGNOSIS = UnresolvedDiagnosis(
    reason_l0="", reason_l1="", reason_l2="", reason_l3="", reason_l4="",
    reason_l5="", reason_l6="", primary_layer="", primary_code="",
    version=UNRESOLVED_TAXONOMY_VERSION,
)


def _field(row: Any, name: str, default: Any = "") -> Any:
    """One reader for a row OBJECT and a row MAPPING alike."""
    if isinstance(row, Mapping):
        value = row.get(name, default)
    else:
        value = getattr(row, name, default)
    return default if value is None else value


def _truthy(value: Any) -> bool:
    """`rows.csv` round-trips booleans as the strings `True` / `False`."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _int(value: Any) -> int:
    try:
        return int(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0


def diagnose_unresolved(
    row: Any,
    diagnostics: Mapping[str, Any] | None,
    document_class: Any | None,
    *,
    evidence_reasons: tuple[str, ...] = (),
) -> UnresolvedDiagnosis:
    """One diagnosis for one document. Pure; reads, never computes.

    `row` is a `discovery.runner.DocumentRow` or a `rows.csv` mapping;
    `diagnostics` is the W3-2 section (`telemetry.diagnostics.diagnose`'s
    shape) or `None`; `document_class` is the classifier's verdict, a
    `KindFacts`, or `None` when no classification exists.

    `evidence_reasons` is `ocr.escalation.EvidenceQuality.reasons` for the
    read of record — the ONE fact L2 needs that the row does not carry as a
    column (the row carries the gate's VERDICT, `evidence_quality`, not its
    reasons). A caller that has the verdict but not the reasons gets
    `unmapped` at L2 rather than a guess: "unusable, and we did not record
    why" is a finding, and inventing `E1` for it would be the taxonomy doing
    the extractor's job.
    """
    outcome_class = str(_field(row, "outcome_class", ""))
    if outcome_class == "validated":
        # A validated document has no unresolved reason. Not an empty
        # diagnosis — no diagnosis.
        return EMPTY_DIAGNOSIS

    facts = kind_facts_from_document_class(document_class)
    codes: dict[str, str] = {layer: "" for layer in LAYERS}

    # -- L0: the row's own encryption fact, and the classifier's file verdict.
    #    `valid_pdf` is deliberately not read (module docstring, property 3).
    if _truthy(_field(row, "encrypted", False)):
        codes["l0"] = "FILE_ENCRYPTED"

    # -- L1: the classifier's verdict, rendered. `FILE_INVALID` is L0's.
    if facts is not None:
        if facts.kind == "FILE_INVALID":
            codes["l0"] = codes["l0"] or "FILE_INVALID"
        elif facts.kind in L1_KINDS:
            codes["l1"] = render_l1_code(facts.kind, facts.sub_kind, tuple(facts.findings))
        elif facts.kind != "STATEMENT_COMPLETE":
            # A kind the classifier grew that this vocabulary lacks: loud, and
            # never nulled.
            codes["l1"] = UNMAPPED

    # -- L2: the extraction gate's own verdict and the truncation count. Never
    #    inferred from a kind (an ILLEGIBLE document may have been read
    #    perfectly) or from an outcome.
    if str(_field(row, "evidence_quality", "none")) == "unusable":
        mapped = [EVIDENCE_REASON_CODE[reason] for reason in evidence_reasons
                  if reason in EVIDENCE_REASON_CODE]
        codes["l2"] = min(mapped, key=L2_CODES.index) if mapped else UNMAPPED
    elif _int(_field(row, "truncated_pages", 0)) > 0:
        codes["l2"] = "E5_truncation_bleed"

    # -- L4 and the doctrine half of L5: the W3-2 section already on the
    #    record. Only for the classes W3-2 itself diagnoses — `failed` has no
    #    payload to project and `deferred` is a statement about the run.
    if outcome_class in DIAGNOSABLE_CLASSES:
        evaluated = bool(diagnostics) and bool(diagnostics.get("evaluated"))
        primary = (diagnostics or {}).get("primary_class") if evaluated else None
        if not evaluated or not primary:
            codes["l4"] = "undiagnosed"
        else:
            codes["l4"] = primary if primary in L4_CODES else UNMAPPED
    for code in (diagnostics or {}).get("codes") or ():
        doctrine = _DOCTRINE_CODE_L5.get(code)
        if doctrine and not codes["l5"]:
            codes["l5"] = doctrine

    # -- the outcome reason, read through the document fold's prefix. It fills
    #    whichever layer it names, and only if that layer is still empty: a
    #    recorded fact outranks a reason token that merely implies one.
    reason = str(_field(row, "outcome_reason", ""))
    if reason.startswith(_ACCOUNT_PREFIX):
        reason = reason[len(_ACCOUNT_PREFIX):]
    if reason not in REASON_LAYER:
        codes["l6"] = codes["l6"] or UNMAPPED
    else:
        target = REASON_LAYER[reason]
        if target is not None:
            layer, code = target
            if not codes[layer]:
                codes[layer] = code

    primary_layer = next((layer for layer in LAYER_PRECEDENCE if codes[layer]), "")
    if not primary_layer:
        # An UNRESOLVED document always has a primary reason, by construction
        # rather than by luck: if no layer spoke, L6 says so in its own closed
        # word. A row reaching here carries an outcome reason this module
        # deliberately mapped to no layer (the financial classes, whose layer
        # comes from the withheld diagnosis) on a class that carries no
        # diagnosis — so there is genuinely nothing to report, and "nothing to
        # report" is a finding with a name, never an empty column. The validated
        # early-return above is the one path that yields no diagnosis at all,
        # and it yields no diagnosis on purpose.
        codes["l6"] = "unknown"
        primary_layer = "l6"
    return UnresolvedDiagnosis(
        reason_l0=codes["l0"], reason_l1=codes["l1"], reason_l2=codes["l2"],
        reason_l3=codes["l3"], reason_l4=codes["l4"], reason_l5=codes["l5"],
        reason_l6=codes["l6"],
        primary_layer=primary_layer,
        primary_code=codes[primary_layer] if primary_layer else "",
        version=UNRESOLVED_TAXONOMY_VERSION,
    )


# ---------------------------------------------------------------------------
# the drift guard's reader (pure over source text, so a mutant can be applied
# to a SCRATCH copy and the tree never touched)
# ---------------------------------------------------------------------------

def _reason_constants(node: ast.AST | None) -> set[str]:
    """String constants an expression can EVALUATE to as a reason.

    Descends through the two shapes the tree actually uses — `a if c else b`
    and `x or (...)` — and through nothing else. An f-string contributes
    NOTHING on purpose: `classify_document`'s fold returns
    `f"account_{reason}"`, whose literal part is a prefix rather than a
    reason, and collecting it would put `account_` in the guard's vocabulary.
    """
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else set()
    if isinstance(node, ast.IfExp):
        return _reason_constants(node.body) | _reason_constants(node.orelse)
    if isinstance(node, ast.BoolOp):
        return set().union(*(_reason_constants(value) for value in node.values))
    return set()


def _is_row_attribute(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == name
            and isinstance(node.value, ast.Name) and node.value.id == "row")


def runner_reason_literals(runner_source: str, record_source: str) -> frozenset[str]:
    """Every outcome-reason literal the runner and the record can emit.

    PURE over source TEXT, which is what lets the mutation table apply M2 to a
    scratch copy and assert the guard sees the planted reason with the working
    tree untouched (`git status --porcelain` clean throughout).

    Four shapes, each precise rather than a text sweep — a `re.findall` over
    quoted strings would collect exception class names, cache tokens and
    docstring prose and make the guard's "no stale entries" half unusable:

    * `row.outcome_class, row.outcome_reason = <class>, <reason>` in the runner;
    * `row.outcome_reason = <reason>` (including the `a if c else b` shape);
    * the `DocumentRow` dataclass's own `outcome_reason` default;
    * every `return` in `_failure_reason` (the runner) and in
      `classify_outcome` / `classify_document` (the record), where a two-tuple
      contributes its SECOND element and a bare return contributes itself.
    """
    found: set[str] = set()

    runner = ast.parse(runner_source)
    for node in ast.walk(runner):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_row_attribute(target, "outcome_reason"):
                    found |= _reason_constants(node.value)
                elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                    for element, value in zip(target.elts, node.value.elts):
                        if _is_row_attribute(element, "outcome_reason"):
                            found |= _reason_constants(value)
        elif isinstance(node, ast.ClassDef) and node.name == "DocumentRow":
            for statement in node.body:
                if (isinstance(statement, ast.AnnAssign)
                        and isinstance(statement.target, ast.Name)
                        and statement.target.id == "outcome_reason"):
                    found |= _reason_constants(statement.value)

    for source, names in ((runner, ("_failure_reason",)),
                          (ast.parse(record_source), ("classify_outcome", "classify_document"))):
        for node in ast.walk(source):
            if not (isinstance(node, ast.FunctionDef) and node.name in names):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Return):
                    continue
                value = inner.value
                if isinstance(value, ast.Tuple) and len(value.elts) == 2:
                    found |= _reason_constants(value.elts[1])
                else:
                    found |= _reason_constants(value)

    return frozenset(found)
