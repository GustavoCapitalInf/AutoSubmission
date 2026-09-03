"""Orchestrates the analysis stages: extract -> reconcile -> metrics -> detect.

No statement is ever re-extracted because it failed reconciliation. The
reconciliation-based selection between two hosted extractions that used to sit
between `reconcile` and `metrics` was REMOVED under ruling R9
(`docs/moneythumb-replacement/PHASE2_RULINGS.md`, 2026-09-03; card P22-FENCE):
the validator is a verifier, never an optimizer, and
`tests/test_pipeline_escalation_fence.py` characterised the removed behaviour
at the base tree and pins its absence."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Callable
from .config import Settings, load_settings
from .count_semantics import claiming_parser_id, counts_comparable
from .schema import Statement
from .dates import assign_transaction_years
from .extract import extract_statement
from .reconcile import reconcile, ReconResult
from .metrics import compute_metrics, Metrics
from .detect import detect, DetectionResult
from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
    prints_internal_transfer_designation,
)
from .bofa import repair_bofa_summary
from .regions import repair_regions_summary
# Re-exported, not re-declared. `SiblingOmission` is CONSTRUCTED at the skip
# sites inside three readers, and a reader cannot import this module (it is
# downstream of the registry that imports the readers). Its home is therefore
# the leaf module `analysis/sibling_omission.py`, which imports nothing of
# ours; the name stays published here because `DocumentReport` is what carries
# the record and this is where a reader of the document model looks for it.
from .sibling_omission import (
    Q3ProvenanceRefused,
    SiblingOmission,
    collecting as _collecting_omissions,
)
# The other half of the same seam, and here for the same reason: a reader that
# establishes a document's SEVERAL accounts cannot import this module, so the
# object it hands them over in lives in a leaf that imports only the schema.
from .multi_account import (
    DocumentPartition as MultiAccountPartition,
    PublishedAccount,
    collecting as _collecting_accounts,
)
from .first_community import repair_first_community_posted_activity
from .parser_registry import (
    AmbiguousParserError,
    Dispatch,
    ParserCrashError,
    Registration,
    by_bank_label,
    prepare,
    resolve,
    run_integrity_checks,
)
from . import parser_registry_entries as _parser_registry_entries  # noqa: F401  - populates the registry
from .structurer import STRUCTURER_MODEL, structure_unclaimed
from .bank_repairs import (
    repair_b1_beginning_balance,
    repair_capital_one_running_amount,
    repair_chase_remote_deposit_count_column,
    repair_regions_transactions,
    repair_santander_signs_from_balances,
    repair_scotiabank_misc_payment_sign,
    repair_single_row_signs_from_balances,
    repair_truist_converted_checks,
)


def normalize_statement(stmt: Statement) -> Statement:
    """Remove rows the extractor occasionally misclassifies as transactions."""
    transactions = []
    for t in stmt.transactions:
        desc = t.description.strip().upper()
        amount = round(t.amount, 2)
        balance = round(t.running_balance, 2) if t.running_balance is not None else None
        is_daily_balance = desc.startswith(("DAILY BALANCE", "DAILY BALANCE SUMMARY")) and (
            amount == 0.0 or balance is not None
        )
        is_balance_marker = desc.startswith((
            "BEGINNING BALANCE",
            "BALANCE FORWARD",
            "BALANCE BROUGHT FORWARD",
            "OPENING BALANCE",
            "CLOSING BALANCE",
        )) and (
            (balance is not None and amount == balance)
            or (stmt.beginning_balance is not None and amount == round(stmt.beginning_balance, 2))
            or (stmt.ending_balance is not None and amount == round(stmt.ending_balance, 2))
        )
        if is_daily_balance or is_balance_marker:
            continue
        transactions.append(t)
    if len(transactions) == len(stmt.transactions):
        return stmt
    return stmt.model_copy(update={"transactions": transactions})


#: The bank-summary repairs, keyed by the registration whose paper each one
#: reads. Both rewrite PUBLISHED figures — balances and stated totals — from
#: labels they expect to find, so each may run only for the parser that owns
#: the layout those labels belong to. `tests/test_analysis.py::
#: test_every_summary_repair_is_keyed_on_a_live_registration` holds the ids to
#: the registry, so renaming a parser cannot silently switch its repair off.
_SUMMARY_REPAIRS: dict[str, Callable[[str, Statement], Statement]] = {
    "bank_of_america": repair_bofa_summary,
    "regions": repair_regions_summary,
}


def apply_statement_repairs(
    markdown: str, stmt: Statement, *, dispatch: Dispatch | None = None
) -> Statement:
    # These two used to be gated on substrings of the document — `"REGIONS" in
    # markdown.upper()`, `"BANK OF AMERICA" ... "ACCOUNT SUMMARY"`. A bank's
    # name in a document is as often a fact about a COUNTERPARTY as about the
    # issuer, which is R4-3 (a marker that reads another bank's ledger row)
    # applied to a REPAIR instead of to a detection marker — and a repair is
    # the more dangerous place for it, because detection competes and a repair
    # simply overwrites. HUNT-CELL H6.1 measured it: five statements of another
    # issuer that merely pay a bill to the bank one of these repairs belongs
    # to — and print a `Service Charge Summary` — had `beginning_balance`,
    # `ending_balance` and every stated total rewritten from their OWN issuer's
    # labels; three further documents in the archive are having `ending_balance`
    # rewritten the same way today. §PIPEFIX P2.4 names all eight.
    #
    # The gate is now the CLAIMING registration, and for an LLM extraction that
    # claimed nothing, the registration whose bank label it named — exactly the
    # `_registration_for` resolution (the R-3 ruling) that `assess_quality` and
    # `assess_document_integrity` already use, so a repair reaches precisely the
    # documents whose parser knowledge the rest of the pipeline is applying.
    #
    # RESTRICTION-ONLY, and that is what makes the hunk safe to review: each
    # repair keeps its own internal guard untouched, so the new key can only
    # STOP a repair firing, never start one on a document that did not already
    # satisfy it. At most one can fire now, since a document has one owner.
    owner = _registration_for(stmt, dispatch)
    repair = _SUMMARY_REPAIRS.get(owner.id) if owner is not None else None
    if repair is not None:
        stmt = repair(markdown, stmt)
    stmt = repair_first_community_posted_activity(stmt)
    stmt = repair_b1_beginning_balance(stmt)
    stmt = repair_capital_one_running_amount(stmt)
    stmt = repair_chase_remote_deposit_count_column(stmt)
    stmt = repair_regions_transactions(markdown, stmt)
    stmt = repair_truist_converted_checks(stmt)
    stmt = repair_santander_signs_from_balances(stmt)
    stmt = repair_scotiabank_misc_payment_sign(stmt)
    stmt = repair_single_row_signs_from_balances(stmt)
    # Statement periods that cross a year boundary: parsers stamp one year on
    # every MM/DD row, so re-derive the year from the period before anything
    # chronological (ADB, daily ledger) is built on these dates.
    stmt = assign_transaction_years(stmt)
    return normalize_statement(stmt)


@dataclass
class Quality:
    level: str
    transaction_detail_reliable: bool
    summary_totals_reliable: bool
    aggregate_rows: int = 0
    corporate_use: str = "review"
    notes: list[str] | None = None


@dataclass
class DocumentIntegrity:
    risk_level: str
    flags: list[str]
    notes: list[str]
    possible_document_issue: bool = False


@dataclass
class Report:
    statement: Statement
    reconciliation: ReconResult
    metrics: Metrics
    detection: DetectionResult
    quality: Quality
    integrity: DocumentIntegrity
    model_used: str
    escalated: bool
    classifications: list[TransactionClassification] = field(default_factory=list)


#: Integrity flags whose SCOPE is the DOCUMENT rather than one account.
#:
#: Every other flag `assess_document_integrity` raises is a statement about one
#: account's ledger — the reconciliation, coverage and count flags, and every
#: consequence `assess_quality` produces. These five are statements about the
#: PDF: more than one parser claimed it, a parser raised on it, the repair
#: stage raised and was discarded whole, a registered integrity check raised,
#: or it declares bank pages the supplied file does not carry. A document
#: carrying N accounts carries each of them ONCE, not N times.
#:
#: THE SPLIT IS ADDITIVE, and reading it any other way is the mistake this
#: partition invites. Moving these flags OUT of an account's published block
#: changes what the platform publishes: `telemetry.record.classify_outcome`
#: reads `parser_ambiguous`, `parser_exception` and `integrity_check_exception`
#: from that block to route a document to review, and `corpus_gate` pins the
#: block as it is served. So the account keeps every flag it publishes today,
#: in published order, and the document object carries the document-scope
#: subset IN ADDITION — never instead.
DOCUMENT_SCOPE_FLAGS: frozenset[str] = frozenset({
    "parser_ambiguous",
    "parser_exception",
    "repair_exception",
    "integrity_check_exception",
    "missing_declared_statement_page",
})


def split_integrity_flags(flags: Sequence[str]) -> tuple[list[str], list[str]]:
    """`(document-scope, account-scope)` flags, each in PUBLISHED order.

    A partition, not a re-ordering: each half is a SUBSEQUENCE of the input, so
    re-assembling them by filtering the original list yields the original list.
    That is load-bearing rather than cosmetic — `corpus_gate.py` pins the
    published flag tuple exactly as it is served ("Published ORDER, not
    sorted"), so an assembly that concatenates the two scopes moves a pinned
    tuple on the first document that carries flags of both scopes in the other
    order.
    """
    document = [flag for flag in flags if flag in DOCUMENT_SCOPE_FLAGS]
    account = [flag for flag in flags if flag not in DOCUMENT_SCOPE_FLAGS]
    return document, account


@dataclass
class RollupOracle:
    """The document's printed enumerating table, kept as EVIDENCE.

    A roll-up that lists a member's accounts is the one cross-account oracle
    this paper prints, and it is recorded so it can be AUDITED — never so a
    figure can be taken from it. No value is read out of a table whose column
    ROLES were not printed (`column_roles_printed`); position is never
    evidence of what a column means.
    """

    caption_class: str
    column_roles_printed: bool
    rows: int
    cross_account_total_printed: bool


@dataclass(frozen=True)
class InternalTransfer:
    """One movement of money between two accounts of the SAME document (R-d).

    `a` and `b` are `(account_index, posting_index)` into `DocumentReport.accounts`
    and each account's own published ledger — indices, never amounts, never
    descriptions, never dates. `basis` names WHICH leg carried the printed
    designation that admitted the pair, so a reader can tell the 42 pairs that
    rest on one printed row from the one that has two.

    **A document-level fact, and stored as one.** Not a field on `Transaction`
    and not one on `TransactionClassification`: either would add a key to every
    transaction dict of every payload in the archive to record something that
    cannot exist on a single-account document.

    **Both legs stay in their ledgers.** Removing either would break that
    account's own reconciliation and its ADB — the money really was in that
    account on that day — and it is also the only way `reconcile` stays
    untouched. The flag reaches package ANALYTICS and nothing else.
    """

    a: tuple[int, int]
    b: tuple[int, int]
    basis: str


#: `assess_document_integrity` produces ONE ACCOUNT's block, so a note about the
#: DOCUMENT has nowhere to go inside it (W3 §L1S2 carried this forward). These
#: are the document-scope notes, and the vocabulary is closed for the same
#: reason L1-C17's is: a note that decides whether a package aggregates is a
#: token, not prose.
#:
#: `ambiguous_internal_transfer` — a posting has TWO OR MORE admissible
#: counterparts, so which sibling row it moved to is not established. No pairing
#: is recorded, both printed legs stay in their ledgers untouched, and the
#: PACKAGE refuses to aggregate this document rather than aggregating it wrongly
#: (design §3.3; Gustavo's Q2 ruling, BATCH9_TRANSITION §8.14). The account's own
#: validation, its ledger and its ADB history are not affected.
AMBIGUOUS_INTERNAL_TRANSFER = "ambiguous_internal_transfer"

DOCUMENT_INTEGRITY_NOTES: frozenset[str] = frozenset({AMBIGUOUS_INTERNAL_TRANSFER})


@dataclass
class DocumentReport:
    """One DOCUMENT: N account `Report`s plus the document's own printed facts.

    `Statement` and `Report` are one ACCOUNT's and stay so. This is the object
    that knows a PDF can carry several accounts, and it is the only place a
    fact about the DOCUMENT rather than about an account may live.

    `accounts` is in PRINTED ORDER and is never sorted. Printed order is
    printed evidence about a SEQUENCE; it is not evidence that the first
    element stands for the whole document, and nothing here selects one account
    to do so. A per-document field that can hold only one account's value is
    left EMPTY, with `account_count` carrying the fact instead.

    Every document this stage builds carries exactly one account and no
    document-level fact, which is precisely the shape RULE S
    (`analysis/serialization.py::document_report_to_dict`) publishes as today's
    payload, byte for byte.
    """

    accounts: list[Report]
    document_period: tuple[str, str] | None = None
    rollup: RollupOracle | None = None
    omissions: list[SiblingOmission] = field(default_factory=list)
    boundary_mechanism: str | None = None
    #: Movements this document prints in TWO of its own accounts' ledgers (R-d).
    #: Empty on every single-account document by construction: a document with
    #: one ledger has no sibling for a movement to have a counterpart in.
    internal_transfers: list[InternalTransfer] = field(default_factory=list)
    #: Document-scope integrity notes, from `DOCUMENT_INTEGRITY_NOTES`. The
    #: account blocks keep their own notes exactly as they publish them today;
    #: this is the scope those blocks have no room for.
    integrity_notes: list[str] = field(default_factory=list)

    def document_scope_flags(self) -> list[str]:
        """The document-scope integrity flags its accounts carry.

        In printed account order, de-duplicated, and IN ADDITION to what each
        account publishes: this is a VIEW over the accounts' own blocks, and
        reading it never removes a flag from one.
        """
        seen: dict[str, None] = {}
        for account in self.accounts:
            for flag in split_integrity_flags(account.integrity.flags)[0]:
                seen.setdefault(flag, None)
        return list(seen)


def _registration_for(stmt: Statement, dispatch: Dispatch | None) -> Registration | None:
    """The parser whose knowledge applies to this statement.

    The claiming registration when one exists. Otherwise the registration whose
    bank label matches - an LLM extraction that named a bank we do have a
    parser for still gets that parser's document knowledge, which is what the
    pre-R-3 `stmt.bank == ...` literals gave it.
    """
    if dispatch is not None and dispatch.registration is not None:
        return dispatch.registration
    return by_bank_label(stmt.bank)


def assess_quality(
    stmt: Statement, recon: ReconResult, *, dispatch: Dispatch | None = None
) -> Quality:
    aggregate_rows = sum(1 for t in stmt.transactions if "UNCAPTURED" in t.description.upper())
    notes: list[str] = []
    registration = _registration_for(stmt, dispatch)
    if registration is not None and not registration.formal_statement:
        notes.append(registration.informal_quality_note)
        return Quality(
            level="needs_review",
            transaction_detail_reliable=recon.ok,
            summary_totals_reliable=False,
            aggregate_rows=aggregate_rows,
            corporate_use="manual_review_required",
            notes=notes,
        )
    if aggregate_rows:
        notes.append(
            "transaction list includes bank-summary aggregate rows for activity not available as individual postings"
        )
    if not recon.ok and recon.summary_ok is True:
        notes.append(
            "bank summary reconciles, but transaction-level detail is incomplete or internally inconsistent"
        )
        if recon.credit_coverage is not None and (recon.credit_coverage < 0.98 or recon.credit_coverage > 1.02):
            notes.append("captured credit line items do not match the bank-stated credit total")
        if recon.debit_coverage is not None and (recon.debit_coverage < 0.98 or recon.debit_coverage > 1.02):
            notes.append("captured debit line items do not match the bank-stated debit total")
    if recon.ok and aggregate_rows == 0:
        return Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=recon.summary_ok is not False,
            corporate_use="approved",
            notes=notes,
        )
    if recon.ok and aggregate_rows:
        return Quality(
            level="summary_aggregate",
            transaction_detail_reliable=False,
            summary_totals_reliable=recon.summary_ok is True,
            aggregate_rows=aggregate_rows,
            corporate_use="summary_only",
            notes=notes,
        )
    if recon.summary_ok is True:
        return Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=True,
            aggregate_rows=aggregate_rows,
            corporate_use="manual_review_required",
            notes=notes,
        )
    return Quality(
        level="needs_review",
        transaction_detail_reliable=False,
        summary_totals_reliable=False,
        aggregate_rows=aggregate_rows,
        corporate_use="manual_review_required",
        notes=notes,
    )


#: A printed page declaration, as the integrity check counts them.
#:
#: `CONTINUED ON NEXT PAGE` is a continuation footer, not a page declaration.
#: Banks print it immediately above the page number, and PDF flattening joins
#: the two lines, so "…NEXT PAGE" + "2 of 20" reads as "Page 2 of 20" to a
#: pattern that only looks for the word.
#:
#: RESTRICTION-ONLY PROPERTY, and the reason that hunk was safe: a negative
#: lookbehind can only REMOVE matches from the set the pattern found before,
#: never add one. `declared_pages` can therefore only shrink, so
#: `missing_declared_statement_page` can only be withdrawn from a document that
#: carried it — this cannot raise the flag on any document that did not already
#: have it, and cannot move a validated document to review.
_PAGE_DECLARATION_RE = re.compile(
    r"(?<!NEXT )\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b", re.IGNORECASE
)

def assess_document_integrity(
    stmt: Statement,
    recon: ReconResult,
    quality: Quality,
    *,
    markdown: str = "",
    dispatch: Dispatch | None = None,
    sheets: Sequence[str] | None = None,
    repair_failure: str | None = None,
) -> DocumentIntegrity:
    # `str` is itself a `Sequence[str]`, so `sheets=markdown` type-checks, then
    # iterates to one CHARACTER per "sheet": thousands of unlabelled sheets, and
    # `missing_declared_statement_page` silently cleared on every document. That
    # is the worst failure this parameter can have, so it is refused loudly
    # rather than coerced. Raising, not treating it as None: passing the
    # document text here is a caller defect, and a caller that believes it is
    # supplying page structure while supplying none would otherwise run in the
    # check's weakest mode forever with nothing to show for it. No document's
    # content can reach this — only a call site can.
    if isinstance(sheets, str):
        raise TypeError(
            "sheets must be the intake object's page list, not the document "
            "text; a str iterates per character and would clear the "
            "page-declaration check"
        )
    flags: list[str] = []
    notes: list[str] = []

    if recon.summary_ok is False:
        flags.append("summary_math_inconsistent")
        notes.append("bank-stated summary totals do not reconcile to beginning and ending balances")
    if recon.sum_delta is not None and abs(recon.sum_delta) > 1.0:
        flags.append("ledger_sum_mismatch")
        notes.append("transaction sum does not reconcile to the printed ending balance")
    if recon.continuity_breaks:
        flags.append("running_balance_breaks")
        notes.append(f"{recon.continuity_breaks} printed running-balance continuity break(s) detected")
    if recon.credit_coverage is not None and (recon.credit_coverage < 0.98 or recon.credit_coverage > 1.02):
        flags.append("credit_detail_coverage_mismatch")
        notes.append("line-item credits do not match the bank-stated credit total")
    if recon.debit_coverage is not None and (recon.debit_coverage < 0.98 or recon.debit_coverage > 1.02):
        flags.append("debit_detail_coverage_mismatch")
        notes.append("line-item debits do not match the bank-stated debit total")
    if quality.level in {"summary_aggregate", "summary_trusted"} or (
        quality.summary_totals_reliable and not quality.transaction_detail_reliable
    ):
        flags.append("transaction_detail_not_corporate_reliable")
        notes.append("summary figures may be usable, but transaction-level detail is not reliable enough for corporate approval")
    registration = _registration_for(stmt, dispatch)
    if registration is not None and not registration.formal_statement:
        flags.append("not_a_formal_statement")
        notes.append(registration.informal_integrity_note)
    # The bank printed a per-direction COUNT and we captured rows; did they
    # agree? Computed in reconcile (no issue appended, so `recon.ok` and the
    # ADB are untouched) and made a consequence here, where it is a flag and
    # never a refusal. Three gates, all required:
    #
    #   `formal`        — a count on a document class that is not a bank
    #                     statement is not a finding.
    #   `counts_comparable` — the printed figure must denote the same set of
    #                     rows `direction` does. A parser absent from
    #                     `analysis/count_semantics.py` is UNSURVEYED, which is
    #                     not comparable, so a NEW registration emits nothing
    #                     until its printed summary has been read. That default
    #                     is structural: this check can only get quieter when
    #                     the registry grows.
    #   `is False`      — load-bearing, not style: `None` is not-applicable
    #                     (no printed count, or aggregate-backed rows), and
    #                     `not None` would flag every document that never ran
    #                     the check.
    #
    # Keyed on the CLAIMING parser only: `_registration_for` also resolves by
    # bank label for LLM extractions, and a semantics entry is evidence about
    # what one parser's reader produced, not about the bank's paper. The key is
    # derived by `count_semantics.claiming_parser_id` rather than spelled out
    # here because `reconcile` needs the SAME key to apply the same table row's
    # mapping (W3 §COUNTSMAP), and two copies of one expression can drift.
    formal = registration is None or registration.formal_statement
    claiming = claiming_parser_id(dispatch)
    if formal and counts_comparable(claiming, "credit") and recon.stated_credit_count_matches is False:
        flags.append("credit_count_mismatch")
        notes.append("captured credit rows do not match the bank-stated credit count")
    if formal and counts_comparable(claiming, "debit") and recon.stated_debit_count_matches is False:
        flags.append("debit_count_mismatch")
        notes.append("captured debit rows do not match the bank-stated debit count")
    if dispatch is not None and dispatch.outcome == "ambiguous":
        flags.append("parser_ambiguous")
        notes.append(
            "more than one deterministic parser claimed this document ("
            + ", ".join(name for name, _score in dispatch.candidates)
            + "); routed to review rather than resolved by guesswork"
        )
    if dispatch is not None and dispatch.outcome == "parser_exception":
        flags.append("parser_exception")
        notes.append(
            "a deterministic parser raised on this document ("
            + ", ".join(dispatch.crashed)
            + "); routed to review rather than reported as unrecognised"
        )
    # A swallowed repair may not be silent. `analyze_markdown` discards a
    # repair stage that raised and publishes the UNREPAIRED statement — a
    # review cause with a named class, in the same family as `parser_exception`
    # above. `repair_failure` is a CLASS NAME (the seam that produced it keeps
    # nothing else), so interpolating it here cannot carry a fragment of the
    # document into the payload. (W3 §REPAIR-GUARD / §PIPE5.)
    #
    # THE NOTE NAMES THE STAGE, NOT ONE REPAIR, and the precision is the point.
    # `apply_statement_repairs` is TWELVE steps and only ONE is a bank-summary
    # repair; the other eleven are nine further bank-specific repairs,
    # `assign_transaction_years` and `normalize_statement`. Saying "a
    # bank-summary repair raised" would be wrong twice over: it misnames the
    # eleven, and on a raise late in the stage the bank-summary repair had
    # already SUCCEEDED and is being discarded with everything else.
    #
    # WHAT THE DISCARD COSTS, disclosed rather than implied: because
    # `assign_transaction_years` is inside the stage, a statement whose period
    # crosses a year boundary publishes WRONG TRANSACTION DATES, not merely
    # uncorrected summary figures — parsers stamp one year on every MM/DD row
    # and that step is what re-derives it, so the dated ledger, the daily
    # balance series and the ADB are all downstream of the discard. That is a
    # strictly larger blast radius than the summary, and it is why the note
    # below does not promise the statement is merely "unrepaired" in the
    # summary sense. It is still the right trade: the alternative is either a
    # half-repaired statement nobody can characterise, or an escaped exception
    # carrying the document's text into the durable job store. The discard is
    # the only fail-closed option, and the flag makes it loud — the document
    # routes to `review`, so a human reads it before the numbers are used.
    # Pinned by `test_the_discard_publishes_uncorrected_dates_on_a_year_boundary`.
    if repair_failure is not None:
        flags.append("repair_exception")
        notes.append(
            f"a statement-repair stage raised ({repair_failure}) and was "
            "discarded whole; the unrepaired statement stands, including any "
            "date, sign or summary correction the stage would have made, so "
            "the document is routed to review rather than reported as clear"
        )
    contradictions: list[str] = []
    if markdown and registration is not None:
        contradictions, check_failures = run_integrity_checks(registration, markdown, stmt)
        for failure in check_failures:
            flags.append("integrity_check_exception")
            notes.append(
                f"a registered document-integrity check raised ({failure.parser_id}: "
                f"{failure.exception}); its finding is unavailable, so the document is "
                "routed to review rather than reported as clear"
            )
    if contradictions:
        flags.append("conflicting_statement_summaries")
        notes.extend(contradictions)
    declared_pages = [
        (int(current), int(total)) for current, total in _PAGE_DECLARATION_RE.findall(markdown)
    ]
    if declared_pages:
        declared_total = max(total for _, total in declared_pages)
        present = {current for current, total in declared_pages if total == declared_total}
        missing = sorted(set(range(1, declared_total + 1)) - present)
        # A missing LABEL is only evidence of a missing PAGE when every sheet
        # the PDF carries prints one, and plenty do not. HUNT-CELL H6.2 measured
        # three Burke & Herbert statements whose Nth declared page is an
        # unlabelled deposit-image sheet — and whose rows reproduce the
        # published ledger exactly, so the "missing" page corroborates the parse
        # it was impeaching. UNID-PACK-B §UB4.3 measured the same defect in a
        # second shape: a core-processor platform whose footers run `1 of 8`
        # … `6 of 8` and which appends the GLBA privacy notice as two sheets
        # with no footer at all. (No issuer or platform is named here — this
        # file is scanned for registered bank labels; §UB4.3 holds the four
        # document hashes.)
        #
        # So an unlabelled sheet is counted as what it is: a candidate for any
        # one of the pages whose label was not found. The flag is withheld only
        # when BOTH hold — enough candidates for the unfound labels, and a PDF
        # that is not simply short of its own declared total.
        #
        # What that pair does NOT do is defeat padding, and the limit is stated
        # here rather than discovered later: a blank or whitespace-only sheet is
        # excluded from `printed_sheets` and raises neither count, but a sheet
        # carrying ANY text — one character is enough — is a candidate, because
        # nothing here reads the page. A short PDF padded with text-bearing
        # junk sheets will have this flag withdrawn. Closing that needs a reader
        # that can tell a statement page from a filler page, which is a
        # different capability from counting them.
        #
        # `sheets` is the INTAKE OBJECT's page list (`StatementMarkdown.pages`),
        # one entry per physical sheet, passed down by the caller that ran the
        # intake ladder. It is deliberately NOT recovered by re-splitting
        # `markdown` on the `--- Page N ---` separators `to_markdown` writes
        # between those same pages. That was this hunk's first form and it was
        # wrong in the way FILENAME-BOUNDARY is about, one layer further down:
        # the separator is an unescaped text convention and page content is OCR
        # output, so a statement printing the literal line `--- Page 9 ---`
        # manufactures a sheet that does not exist. Appended inside the last
        # page it even leaves the 1..K sequence intact, so validating the
        # separator STREAM cannot close it — the count has to come from the
        # object that knows how many sheets were rasterised. This flag is
        # fraud-relevant; a document must not clear it by printing a line.
        #
        # FAIL-CLOSED when the caller supplies nothing: no sheet list means no
        # evidence that anything is present but unlabelled, so `missing` stands
        # exactly as it did before this cell. A caller can only ever weaken this
        # check by proving structure, never by staying silent.
        #
        # ASYMMETRY, deliberate and conservative: `declared_pages` reads
        # declarations from the whole document and takes `declared_total` from
        # the largest denominator, while a sheet counts as labelled if it
        # carries ANY declaration, whatever its denominator. A sheet printing
        # `Page 1 of 2` inside a document that declares 8 is therefore treated
        # as labelled rather than as a candidate. That direction only ever keeps
        # the flag, so the asymmetry cannot clear a document.
        #
        # This does NOT blunt the check: the pinned Columbia statement declares
        # 5 pages, supplies 4 sheets and labels all four, so nothing can stand
        # in for page 5 and its flag stands byte-identical — as does the
        # synthetic Wells fixture behind the FILENAME-BOUNDARY suppression test.
        printed_sheets = [sheet for sheet in (sheets or ()) if sheet.strip()]
        unlabelled_sheets = sum(
            1 for sheet in printed_sheets if not _PAGE_DECLARATION_RE.search(sheet)
        )
        accounted_for = (
            len(printed_sheets) >= declared_total and len(missing) <= unlabelled_sheets
        )
        if missing and not accounted_for:
            flags.append("missing_declared_statement_page")
            notes.append(
                "statement declares "
                f"{declared_total} bank page(s), but page label(s) "
                f"{', '.join(str(page) for page in missing)} are absent from the supplied PDF"
            )

    unique_flags = list(dict.fromkeys(flags))
    unique_notes = list(dict.fromkeys(notes))
    possible_document_issue = (
        recon.summary_ok is False
        or recon.continuity_breaks >= 3
        or bool(contradictions)
        or (
            quality.level == "summary_trusted"
            and recon.continuity_breaks > 0
            and any("coverage_mismatch" in flag for flag in unique_flags)
        )
    )
    if possible_document_issue:
        risk_level = "high"
    elif unique_flags:
        risk_level = "review"
    else:
        risk_level = "clear"

    return DocumentIntegrity(
        risk_level=risk_level,
        flags=unique_flags,
        notes=unique_notes,
        possible_document_issue=possible_document_issue,
    )


@dataclass
class _Analysed:
    """What ONE analysis of one document produced, before it is published.

    `accounts` is in PRINTED ORDER and its FIRST member is the account the
    claiming registration returned — the one `analyze_markdown` has always
    answered about. `partition` is what that reader established about the
    document, or `None` where it established nothing, which is every document
    no multi-account reader claims.
    """

    accounts: list[Report]
    partition: MultiAccountPartition | None = None


def analyze_markdown(markdown: str, *, settings: Settings | None = None,
                     parse_mode: str = "auto",
                     document_geometry: object | None = None,
                     sheets: Sequence[str] | None = None,
                     on_dispatch: Callable[[Dispatch], None] | None = None) -> Report:
    """ONE ACCOUNT's analysis — unchanged, and still the answer for one account.

    A thin call onto `_analyse`, which is the body this function had until the
    first multi-account publisher landed. Splitting it is what lets the DOCUMENT
    entry point reach every account a reader established without this one
    changing what it answers: on a document whose reader publishes one account
    `_analyse` returns one report and this returns it, exactly as before.

    On a document whose reader publishes SEVERAL, this still answers about the
    first — the account the registration returned — and the others are reached
    only through `analyze_document`. That is not a fallback: `Statement` is one
    account, this function's contract is one account, and a caller asking for
    one account gets the one the paper printed first rather than a fold.
    """
    return _analyse(
        markdown,
        settings=settings,
        parse_mode=parse_mode,
        document_geometry=document_geometry,
        sheets=sheets,
        on_dispatch=on_dispatch,
    ).accounts[0]


def _analyse(markdown: str, *, settings: Settings | None = None,
             parse_mode: str = "auto",
             document_geometry: object | None = None,
             sheets: Sequence[str] | None = None,
             on_dispatch: Callable[[Dispatch], None] | None = None) -> _Analysed:
    # `sheets` is `StatementMarkdown.pages` from the caller that ran the intake
    # ladder — the authentic per-sheet structure of the PDF, which this string
    # cannot be trusted to reproduce (see `assess_document_integrity`). Optional
    # and fail-closed: a caller that does not have it changes nothing.
    settings = settings or load_settings()
    if parse_mode not in {"auto", "deterministic"}:
        raise ValueError(f"unknown parse_mode: {parse_mode}")

    # THE ADMISSIBILITY BOUNDARY (W3 FILENAME-BOUNDARY). Everything below this
    # line — detection, every parser's `parse`, the repairs, the ADB engine's
    # source-text check, the integrity checks and the LLM extraction prompt —
    # sees the document with its source-filename comment removed.
    #
    # Deliberately a REBIND of the parameter rather than a second local passed
    # to each consumer: one line makes the property total and checkable by
    # reading this function, where a new local would leave the guarantee to
    # every present and future call site remembering which variable is the
    # admissible one. Filenames are operator-supplied metadata (R-4b); F-
    # PROVENANCE measured 7 of 10 sampled parsers reading financial evidence
    # out of them — periods, ADB and year inference moving on a rename alone.
    # The fix belongs here, at the one seam every parser is behind, not as an
    # exclusion re-implemented in each parser.
    #
    # `admissible_text` is idempotent, and detection already applied it, so the
    # detection path is unchanged and parse now sees the exact bytes detection
    # scored. It removes the comment line and the blank lines that followed it,
    # so absolute line numbers shift by a constant prefix; nothing downstream
    # keys off an absolute markdown line index (the structurer derives its own
    # indices from the text it is handed, and `DocumentGeometry` is built from
    # OCR word boxes, not from this string).
    #
    # The rebind is taken FROM the detect sweep's own preparation rather than
    # computed beside it (W3 #PREPHAND). `PreparedDocument` begins by computing
    # exactly `admissible_text(markdown)` — the same function on the same
    # string, so the boundary is where it was and says what it said — and then
    # holds each parser's normalization of that text for the sweep. Passing the
    # object to `resolve` instead of the string is what makes one document cost
    # one preparation: `resolve` sweeps on it and publishes it as
    # `Dispatch.prepared`, and telemetry's near-miss vector — a SECOND full
    # sweep over the same document, per H3_SCHEMA §4 — reuses it instead of
    # preparing everything a second time.
    prepared = prepare(markdown)
    markdown = prepared.admissible

    model_used = settings.model
    # THE ACCOUNT-PUBLICATION SEAM (L1-S4). A reader that establishes a
    # document's several accounts from its printed partition publishes them
    # here while it parses; `resolve` runs every candidate's `parse`, so several
    # attempts may publish and only the one whose statement the dispatch
    # returned is the document's — settled below by IDENTITY rather than by
    # arrival order. There is exactly one collection per document because
    # `collecting()` is RE-ENTRANT BY ITS OWN CONSTRUCTION — a block opened
    # inside another yields the OUTER collector rather than shadowing it — and
    # NOT because a caller wraps this one: `analyze_document` opened its own
    # collection around this call until 6f031d4 removed it, and this comment
    # outlived that seam by one commit.
    with _collecting_accounts() as _published_accounts:
        dispatch = resolve(prepared)
    if on_dispatch is not None:
        # H-3 telemetry seam: write-only side-band, nothing here is read back.
        # The callback's contract is "must not raise, must not mutate", and it
        # is discharged on the telemetry side (telemetry/collect.py) rather
        # than by a try/except here — swallowing exceptions inside this module
        # would be new control flow in the orchestrator to cover a defect in an
        # observer.
        #
        # Deliberately a callback and NOT a `Dispatch` field on `Report`:
        # `Dispatch.statement` is the parsed Statement — every amount and
        # description — so hanging it off `Report` would put the full financial
        # record one generic `asdict()` away from anything that walks a report.
        # Telemetry projects ids and scores out of `dispatch` and stores
        # nothing else. Do not "simplify" this into a Report field.
        on_dispatch(dispatch)
    deterministic_stmt = dispatch.statement
    # Which published partition the dispatch CLAIMED, by identity of the
    # statement it returned. A losing candidate's partition is discarded here
    # rather than downstream, which is the same rule
    # `sibling_omission.publish_omissions` applies to a losing candidate's
    # omissions and for the same reason: an attempt that publishes nothing has
    # established nothing about this document.
    partition = _published_accounts.resolve_claim(deterministic_stmt)
    # W3-3c: the generic structurer is a fallback on the UNCLAIMED branch. It
    # never competes with a claiming parser, and it is deliberately not reached
    # for `ambiguous` or `parser_exception`, which have their own fail-closed
    # outcomes: structuring either would bury a finding a human must see under
    # a plausible-looking answer. Off unless GENERIC_STRUCTURER_ENABLED is set,
    # and it returns None rather than raising, so this line cannot change any
    # existing behaviour until the opt-in is flipped.
    structured_stmt = (
        structure_unclaimed(markdown, geometry=document_geometry)
        if deterministic_stmt is None and dispatch.outcome == "unclaimed"
        else None
    )
    repair_failure: str | None = None
    if deterministic_stmt is not None:
        normalized = normalize_statement(deterministic_stmt)
        # THE REPAIR SEAM (W3 §MG-C2 D1 / §REPAIR-GUARD / §PIPE5).
        #
        # `parser_registry` states the law for the deterministic branch: "no
        # code path from `resolve` through `parse` raises". Every `detect` and
        # every `parse` runs behind `_guarded`, which reduces a crash to a
        # `ParserFailure` — registration id, stage, and the exception's CLASS
        # NAME, never its message, because a message routinely quotes the cell
        # of the document that provoked it (H3_SCHEMA I1). The repairs run
        # AFTER dispatch, so they were the one line in this branch standing
        # outside that promise: a repair that raised propagated out of
        # `analyze_markdown` as a bare exception, and through batch 5
        # `webapp/worker.py` did `store.set_error(job_id, str(exc))` — putting
        # the quoted cell in the durable job store and in front of a user.
        # (WORKER-PRIVACY, batch 6, closed that boundary too: the job store now
        # receives the stage and the exception's class name, never its message.
        # The two closures are independent; neither is the other's excuse.)
        #
        # MG-C closed the leak at its loudest SOURCE (`money.read_money` names
        # the reader and the refusal class, never the token). This closes the
        # SEAM, which is the part that generalises: an `int()` on a mangled
        # cell or a `KeyError` on a mis-shaped grid quotes the document too.
        #
        # The repair stage is discarded ATOMICALLY — the unrepaired statement
        # stands, which is exactly what this branch published before repairs
        # existed. Deliberately not per-repair: recovering WHICH step of the
        # stage raised would mean running the ten repairs, the year assignment
        # and the normalization independently, and that changes what the stage
        # DOES — today the first raise stops the rest — which this card is
        # explicit is out of scope. For the same reason the class name is NOT
        # attributed to `dispatch.registration`: only the keyed summary repair
        # belongs to the claiming parser, so naming it as the author of one of
        # the nine unconditional repairs' crashes would be exactly the
        # misattribution this seam exists to prevent.
        #
        # NOT applied to the LLM-branch repair call below, and that is a
        # boundary rather than an omission: `extract_statement` on that
        # branch is itself an unguarded call that raises out of this
        # function, so guarding one line inside a branch that makes no
        # totality promise would buy nothing. (A second such call — the
        # escalation extraction, with its own `except` — stood after
        # `reconcile` until R9 removed it; see the pinned `escalated` below.)
        try:
            stmt = apply_statement_repairs(markdown, normalized, dispatch=dispatch)
        except Exception as exc:
            stmt = normalized
            repair_failure = type(exc).__name__
        # MODEL-LABEL (W3 §PIPE5). `(stmt.bank or "bank")` published the single
        # label `bank-deterministic` for every document whose parser publishes
        # no issuer — the honest-unknown-issuer registrations (UNKNOWN-ISSUER)
        # and the issuer-agnostic core-processor templates, which claim on a
        # PLATFORM's paper and so cannot name the bank without inventing one.
        # Collapsing them into one bucket makes the aggregation dishonest in
        # the one direction that matters: it reads as a single parser having
        # produced 41 documents that four different parsers produced, and it
        # is the label the coverage audits and the forensic audits carry.
        #
        # The claiming registration's id is the honest name. It is what
        # actually dispatched, it is already the key every other consequence in
        # this module is drawn on (`_registration_for`), and it is a registry
        # id rather than anything read out of the document.
        #
        # NARROW BY CONSTRUCTION: `stmt.bank is None` is required, so a
        # document that carries a bank label takes the byte-identical old
        # expression and cannot move. `is None` and not falsiness — a parser
        # that published an empty label would be stating something different
        # from "this paper names no issuer", and this hunk does not adjudicate
        # that. The suffix is unchanged, which is load-bearing:
        # `telemetry.record.model_calls_for` reads `endswith("-deterministic")`
        # to mean "no model call was made", so cost and call accounting are
        # untouched.
        owner = _registration_for(stmt, dispatch)
        if stmt.bank is None and owner is not None:
            model_used = f"{owner.id}-deterministic"
        else:
            bank_label = (stmt.bank or "bank").lower().replace(" ", "-")
            model_used = f"{bank_label}-deterministic"
    elif structured_stmt is not None:
        # No `apply_statement_repairs`: its repairs are bank-specific and this
        # branch is where no bank was identified. The one correction the
        # structurer needs (assign_transaction_years) already ran inside the
        # subsystem, BEFORE grounding, so the date grounding accepted is the
        # date that ships.
        stmt = normalize_statement(structured_stmt)
        model_used = STRUCTURER_MODEL
    else:
        if dispatch.outcome == "ambiguous" and parse_mode == "deterministic":
            raise AmbiguousParserError(dispatch.candidates)
        # BLOCK-2 (`PHASE2_P20SURFACES_REVIEW.md`), unconditional in every
        # `parse_mode`. Below, the `parser_exception` -> `ParserCrashError`
        # refusal fired only `and parse_mode == "deterministic"` — every other
        # mode fell through to `extract_statement`, so Q3's native-only gate
        # (`sibling_omission.publish_omissions`, raises `Q3ProvenanceRefused`)
        # was fail-CLOSED in deterministic mode and fail-OPEN in the webapp's
        # default `parse_mode="auto"`: a document refused for OCR provenance
        # was routed to a HOSTED MODEL CALL, and on success published one
        # account with the omitted sibling silently dropped (`omissions ==
        # []`, no `sibling_account_omission_detected`) — the exact L-1 defect
        # `analysis/sibling_omission.py`'s own module docstring exists to
        # prevent, reached through the gate whose whole purpose is to prevent
        # it. A policy refusal must never start an extractor escalation
        # (`PHASE2-0-SAFETY.md` §Objective), so this checks the recorded
        # exception's CLASS NAME ONLY — never a message, exactly as
        # `analysis.parser_registry.ParserFailure` already stores it — and
        # refuses in EVERY mode. This does not widen the pre-existing
        # `unclaimed` asymmetry (BLOCK-2's own finding: an `unclaimed`
        # dispatch still falls through to `extract_statement` outside
        # deterministic mode exactly as it always did; that is a separate,
        # pre-existing edge this fix does not touch).
        if dispatch.outcome == "parser_exception" and any(
            failure.exception == Q3ProvenanceRefused.__name__
            for failure in dispatch.exceptions
        ):
            raise ParserCrashError(dispatch.exceptions)
        if dispatch.outcome == "parser_exception" and parse_mode == "deterministic":
            # Not "no parser matched": that would file our own defect as a gap
            # in our layout knowledge, in the one report a human reads.
            raise ParserCrashError(dispatch.exceptions)
        if parse_mode == "deterministic":
            raise RuntimeError("no deterministic parser matched this statement")
        stmt = normalize_statement(extract_statement(markdown, settings=settings, model=model_used))
        stmt = apply_statement_repairs(markdown, stmt, dispatch=dispatch)
    # One key for both halves of the count check: the mapping `reconcile`
    # applies and the semantics `assess_document_integrity` judges the result
    # under come from the same table row or the check is judging one comparison
    # by another's rules (W3 §COUNTSMAP).
    claiming = claiming_parser_id(dispatch)
    recon = reconcile(stmt, parser_id=claiming)

    # R9 (`PHASE2_RULINGS.md`, 2026-09-03; card P22-FENCE): PINNED FALSE.
    #
    # Until this cell the block that stood here ran a SECOND hosted extraction
    # with `settings.escalation_model` whenever `recon` failed, reconciled the
    # alternate, and kept whichever extraction reconciled — "falling back to
    # fewer overall issues" — which is, verbatim, the "multiple extractions ->
    # compare financial reconciliation -> prefer whichever reconciles" pattern
    # the anti-optimizer rule forbids. It is REMOVED, not fenced: this module
    # makes at most one `extract_statement` call, binds at most one `reconcile`
    # result per scope, and derives this flag from nothing. The field stays on
    # `Report`, and so in every payload, for shape stability only.
    # `tests/test_pipeline_escalation_fence.py` characterised the removed
    # behaviour at the base tree and pins its absence with AST tripwires. (The
    # #PRIVACY3 guarantee the removed guard's first clause carried — no hosted
    # call in deterministic mode — is now structural: the one call left is in
    # the branch above, after the deterministic-mode raises.)
    escalated = False

    published = list(partition.accounts) if partition is not None else []
    source_scope = published[0].section_text if published else markdown
    primary = _account_report(
        stmt, recon,
        dispatch=dispatch, settings=settings,
        markdown=markdown,
        # THE SOURCE SCOPE, and the one argument of this call that is not the
        # whole document (design §2.5). `posting_dates_cover_source` proves a
        # parser did not fold several printed posting days into one, and it
        # proves it by comparing the parsed dates with the dates printed in the
        # SOURCE it is handed. For an account of a member statement that source
        # is that account's own section: handed the whole PDF it counts a
        # sibling's posting days against this ledger and refuses a document
        # that is in fact complete. `source_scope` is the section the claiming
        # reader established from PRINTED boundaries, and it is the whole
        # document for every reader that establishes none — which is every
        # document in the archive but the ones a multi-account reader claims.
        source_markdown=source_scope,
        sheets=sheets, repair_failure=repair_failure,
        model_used=model_used, escalated=escalated,
    )

    # THE OTHER ACCOUNTS. Each is reconstructed by the reader from the
    # document's own printed partition and is validated INDEPENDENTLY here, by
    # the same unchanged validator, against its OWN section's text (R-b, and
    # design §2.5's source scope). Nothing about a sibling reaches this
    # account's report and nothing about this account reaches a sibling's: they
    # share the document's markdown for the page and integrity-check facts that
    # are the PDF's, and nothing else.
    #
    # `normalize_statement` and `apply_statement_repairs` are applied exactly as
    # they were to the claimed statement, so the accounts of one document are
    # treated alike. The repairs are keyed on the CLAIMING registration or on
    # each repair's own printed guard, so none of them can reach a document this
    # reader did not claim.
    accounts = [primary]
    for account in published[1:]:
        sibling = apply_statement_repairs(
            markdown, normalize_statement(account.statement), dispatch=dispatch,
        )
        accounts.append(_account_report(
            sibling, reconcile(sibling, parser_id=claiming),
            dispatch=dispatch, settings=settings,
            markdown=markdown, source_markdown=account.section_text,
            sheets=sheets, repair_failure=repair_failure,
            model_used=model_used, escalated=False,
        ))
    return _Analysed(accounts=accounts, partition=partition)


def _account_report(
    stmt: Statement,
    recon: ReconResult,
    *,
    dispatch: Dispatch | None,
    settings: Settings,
    markdown: str,
    source_markdown: str,
    sheets: Sequence[str] | None,
    repair_failure: str | None,
    model_used: str,
    escalated: bool,
) -> Report:
    """ONE ACCOUNT's report, from its statement and its own reconciliation.

    Everything `analyze_markdown` did after reconciliation and escalation,
    unchanged and in the same order, extracted so that the SECOND account of a
    member statement is analysed by the same code as the first. That is R-b
    made mechanical: `reconcile`, `compute_metrics`, `assess_quality`,
    `assess_document_integrity` and `detect` are not touched, and what changed
    is only that they can now be called on each account of a document instead
    of once per PDF.

    Two of the arguments are document facts and stay document facts for every
    account, and the distinction is the whole point of this signature:

    * `markdown` is the DOCUMENT's text. `assess_document_integrity` reads it
      for the page-declaration check and for the claiming registration's own
      integrity checks, and both are statements about the PDF — a document
      declaring four pages declares them once, not once per account;
    * `source_markdown` is the scope the ADB's source-coverage check is applied
      against, which is the ACCOUNT's own section wherever a reader established
      one.

    On a single-account document the two are the same string and this function
    computes exactly what the body it was lifted from computed.
    """
    classifications = classify_statement_transactions(stmt)
    metrics = compute_metrics(
        stmt,
        trust_stated_summary=recon.summary_ok,
        trust_running_balances=recon.ok and not any("UNCAPTURED" in t.description.upper() for t in stmt.transactions),
        # the source text lets the ADB engine prove the parser did not fold
        # several posting dates into one
        source_markdown=source_markdown,
        classifications=classifications,
        withholding_denominator_mode=settings.withholding_denominator_mode,
    )
    quality = assess_quality(stmt, recon, dispatch=dispatch)
    if quality.level == "summary_aggregate":
        metrics.notes = [
            note for note in metrics.notes
            if note != "not computing average balance from line items because reconciliation failed"
        ]
        if "not computing average balance from aggregate-backed transaction detail" not in metrics.notes:
            metrics.notes.append("not computing average balance from aggregate-backed transaction detail")
    if quality.notes:
        for note in quality.notes:
            if note not in metrics.notes:
                metrics.notes.append(note)
    integrity = assess_document_integrity(
        stmt, recon, quality, markdown=markdown, dispatch=dispatch, sheets=sheets,
        repair_failure=repair_failure,
    )
    if integrity.possible_document_issue and quality.corporate_use != "approved":
        quality = Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            aggregate_rows=quality.aggregate_rows,
            corporate_use="manual_review_required",
            notes=(quality.notes or []) + ["document integrity issue prevents automated corporate approval"],
        )
    if integrity.possible_document_issue:
        note = "document integrity review recommended; inconsistent source data can be a fraud-risk signal but is not proof of fraud"
        if note not in metrics.notes:
            metrics.notes.append(note)

    return Report(
        statement=stmt,
        reconciliation=recon,
        metrics=metrics,
        detection=detect(
            stmt,
            classifications=classifications,
            eligible_deposits=metrics.eligible_deposits,
        ),
        quality=quality,
        integrity=integrity,
        model_used=model_used,
        escalated=escalated,
        classifications=classifications,
    )


def analyze_document(markdown: str, *, settings: Settings | None = None,
                     parse_mode: str = "auto",
                     document_geometry: object | None = None,
                     sheets: Sequence[str] | None = None,
                     on_dispatch: Callable[[Dispatch], None] | None = None) -> DocumentReport:
    """The DOCUMENT entry point: one PDF's text in, one `DocumentReport` out.

    `analyze_markdown` answers "what does this ACCOUNT's statement say" and
    keeps answering exactly that. This answers "what does this DOCUMENT say",
    which on most of the archive is the same answer wearing the object that can
    hold more than one of them, and on a member statement is several accounts,
    each reconstructed from the paper's own printed partition and each validated
    INDEPENDENTLY by the unchanged validator (R-b).

    What it fills, and what it deliberately does not:

    * `accounts` in PRINTED ORDER, never sorted, and never one chosen to stand
      for the document (L1-C18);
    * `document_period`, `rollup` and `boundary_mechanism` only where a reader
      ESTABLISHED them — the period the document printed once for every section,
      the enumerating table it read as an ORACLE, the mechanism the accounts
      were partitioned by. A single-account document establishes none of them,
      so all three stay empty: a per-document fact taken from an account is a
      fact nobody read (L1-C18 again, and it is the rule that bites hardest
      exactly where it is most tempting to break);
    * `omissions`, which is not derived from any published account: it is what
      the READER established about a section it declined to publish, and the L-1
      rule is that such a gap is surfaced or the document is refused. It arrives
      from the skip sites through `analysis/sibling_omission.py::collecting`,
      opened here because this is the seam that owns the object it belongs on;
    * `internal_transfers` and `integrity_notes`, computed HERE and nowhere
      else, because a movement between two accounts is a fact about a DOCUMENT
      and there is no other place in this platform that can see two of one
      document's ledgers at once.

    RULE S is unchanged and is decided by ACCOUNT COUNT alone
    (`analysis/serialization.py::_publishes_todays_payload`): a document
    carrying one account publishes today's payload byte for byte whatever
    document-level fact it also carries.
    """
    # The omission collector is opened HERE because the omissions are read
    # here, off the scope; the ACCOUNT collector is not, because `_analyse`
    # opens its own and hands the partition back in its return value. The
    # asymmetry is deliberate: a scope opened and never read is a question a
    # reader has to answer for themselves.
    with _collecting_omissions(markdown) as omitted:
        analysed = _analyse(
            markdown,
            settings=settings,
            parse_mode=parse_mode,
            document_geometry=document_geometry,
            sheets=sheets,
            on_dispatch=on_dispatch,
        )
    partition = analysed.partition
    transfers, notes = identify_internal_transfers(analysed.accounts)
    return DocumentReport(
        accounts=analysed.accounts,
        omissions=list(omitted),
        document_period=partition.document_period if partition is not None else None,
        boundary_mechanism=partition.boundary_mechanism if partition is not None else None,
        rollup=(
            RollupOracle(
                caption_class=partition.rollup.caption_class,
                column_roles_printed=partition.rollup.column_roles_printed,
                rows=partition.rollup.rows,
                cross_account_total_printed=partition.rollup.cross_account_total_printed,
            )
            if partition is not None and partition.rollup is not None
            else None
        ),
        internal_transfers=transfers,
        integrity_notes=notes,
    )


def identify_internal_transfers(
    accounts: Sequence[Report],
) -> tuple[list[InternalTransfer], list[str]]:
    """R-d: which of this document's postings moved money between its OWN accounts.

    `(transfers, document_scope_notes)`. Four clauses, ALL of them required, and
    the order they are applied in is itself the fail-closed decision:

    1. **the arithmetic** — a posting in a SIBLING account of the SAME document
       with the same posting date, the same magnitude to the cent and the
       opposite sign. Same document only: a counterpart in another statement of
       the same package is not printed evidence of an internal movement, it is a
       coincidence of date and amount, and pairing across documents would let two
       unrelated statements cancel each other's deposits (Q2, §8.14);
    2. **uniqueness, DOCUMENT-WIDE** — a posting with TWO OR MORE arithmetic
       counterparts pairs with NONE. Uniqueness is decided on the arithmetic
       rather than after clause 4 has thinned the field, which is the stricter
       reading: if a printed credit could have come from either of two sibling
       debits, which one it came from is not established, and a designation
       saying "this came from one of my own accounts" does not say WHICH ROW.
       Every posting on both sides of such a collision is refused, the note
       `ambiguous_internal_transfer` is attached to the DOCUMENT, and the package
       refuses to aggregate it (§3.3). Never guess: a wrong pairing silently
       removes a real deposit from a funder's total, which is worse than
       refusing;
    3. **one-to-one** — and it FOLLOWS from clause 2 rather than being checked
       here a second time. If a posting's only counterpart did not name it back,
       that counterpart saw two, and clause 2 has already refused the whole
       document. A branch that cannot fire is a branch no mutation table can
       show is doing anything, so the property is asserted where it can be:
       `corpus_gate.py::_assert_document_facts` refuses a published payload in
       which one posting is a leg of two transfers;
    4. **the printed designation** — at least one of the two legs prints an
       INTERNAL-MOVEMENT designation, read by
       `analysis/transaction_classifier.py::prints_internal_transfer_designation`
       and therefore by `_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone. A pair that
       fails this clause is simply NOT FLAGGED — it is not ambiguous, it is an
       arithmetic coincidence, and both postings keep every effect they have
       today. That is the clause the whole rule turns on: without it a member
       who deposits a sum into checking on the day they withdraw the same sum
       from savings for an unrelated purpose has that printed deposit deleted
       from a funder's view of the business by an inference.

    Both legs stay in their ledgers whatever this returns. Nothing here touches
    a `Statement`, a `Report`, a reconciliation or an ADB; the result is a
    document-level index pair that only package ANALYTICS read.

    Trivially empty for one account: with a single ledger there is no sibling
    for a counterpart to be in, so this returns `([], [])` without looking at a
    posting — which is why it costs the archive nothing.
    """
    if len(accounts) < 2:
        return [], []

    postings: list[tuple[int, int, str, float, str]] = [
        (account_index, posting_index, txn.date, round(txn.amount, 2), txn.description)
        for account_index, report in enumerate(accounts)
        for posting_index, txn in enumerate(report.statement.transactions)
    ]

    def admissible(left, right) -> bool:
        """Clause 1, and only clause 1."""
        return (
            left[0] != right[0]
            and left[2] == right[2]
            and abs(abs(left[3]) - abs(right[3])) < 0.005
            and left[3] * right[3] < 0
        )

    counterparts: dict[int, list[int]] = {
        index: [other for other, right in enumerate(postings)
                if other != index and admissible(left, right)]
        for index, left in enumerate(postings)
    }
    ambiguous = any(len(found) > 1 for found in counterparts.values())
    notes = [AMBIGUOUS_INTERNAL_TRANSFER] if ambiguous else []
    if ambiguous:
        # Clause 2, fail-closed for the WHOLE document rather than for the
        # colliding posting alone. A document that cannot say which sibling row
        # a movement landed in cannot have its accounts aggregated, and pairing
        # the unambiguous pairs beside an unresolved one would publish a partial
        # exclusion that reads as a complete one.
        return [], notes

    transfers: list[InternalTransfer] = []
    paired: set[int] = set()
    for index, found in counterparts.items():
        if len(found) != 1 or index in paired:
            continue
        other = found[0]
        left, right = postings[index], postings[other]
        designations = (
            prints_internal_transfer_designation(left[4]),
            prints_internal_transfer_designation(right[4]),
        )
        if not any(designations):
            continue  # clause 4: an arithmetic coincidence is not a transfer
        credit, debit = (left, right) if left[3] > 0 else (right, left)
        credit_designated = prints_internal_transfer_designation(credit[4])
        debit_designated = prints_internal_transfer_designation(debit[4])
        basis = (
            "printed_internal_transfer_designation_on_both_legs"
            if credit_designated and debit_designated
            else "printed_internal_transfer_designation_on_the_credit_leg"
            if credit_designated
            else "printed_internal_transfer_designation_on_the_debit_leg"
        )
        paired.update({index, other})
        transfers.append(InternalTransfer(
            a=(left[0], left[1]), b=(right[0], right[1]), basis=basis,
        ))
    return transfers, notes
