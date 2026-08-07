"""W3-2 — why a claimed document was withheld, as a closed check taxonomy.

Discovery withheld 614 claimed documents (17.5% of the archive). "Withheld"
says the platform refused to publish an ADB; it does not say *which* check
refused. This module turns that into a per-check answer, bank-agnostically, so
remediation can be ranked by check-class x parser x volume instead of done
statement by statement.

**Read-only projection.** Everything here reads the already-serialized analysis
payload — the same dict `build_record` is handed. Nothing is recomputed, no
analysis code is called, no object is mutated. `analysis/` is protected and is
not imported by this module at all (the vocabulary drift-guard test reads its
*source text*, which is also read-only). A test asserts the payload is
byte-identical before and after diagnosis.

**Sensitivity invariant (H3_SCHEMA I1) applies absolutely.** Reconciliation
issues and ADB warnings are free text that quotes amounts, dates and
transaction descriptions — for example
``row 7 ('ACH DEBIT ...'): balance jumped to 12,345.67``. Those strings are
**never** stored. They are matched against literal format-string anchors that
`analysis/` itself writes, and only the resulting enum code survives. What a
record carries is: check names (our constants), taxonomy codes (our
constants), summary *field* names (our schema's constants), and counts.

**Nothing is silently dropped.** Every vocabulary is closed and paired with an
explicit `unmapped` bucket: a new ADB check, a new integrity flag, a new
reconciliation issue or a new ADB warning that this module has never seen
lands in `unmapped` (names for the enum-shaped sources, counts only for the
free-text ones) and shows up in the rollup. `tests/test_diagnostics.py` also
fails loudly the moment `analysis/` grows a check name or integrity flag that
is not in the tables below.

Mapping rationale, per code: `docs/moneythumb-replacement/W3_2_TAXONOMY.md`.
"""
from __future__ import annotations

#: Bumped when a code is added, removed or re-classed. Travels in every record
#: so a rollup over mixed runs can tell which vocabulary produced a row.
#:
#: 1 - W3-2, as shipped.
#: 2 - W3-2b: `integrity:integrity_check_exception` re-classed from advisory to
#:     the new `check_unavailable` class. A record emitted at version 1 that
#:     carries that code would rank one class lower than the same document
#:     ranks now, so a rollup spanning both versions is comparing two
#:     vocabularies - which is what this field exists to make visible.
DIAGNOSTICS_VERSION = 2

#: The explicit label for a document whose claiming parser could not be
#: established. Defined here, in the lower layer, because both the telemetry
#: rollup and the W3-4 adjudication tooling group by parser and must agree on
#: what "we do not know" looks like. Only ever reachable behind an explicit
#: `--allow-unattributed`, so it always means "you were told".
UNATTRIBUTED = "(parser unknown)"

#: The outcome classes this module diagnoses. `withheld` is the fail-closed
#: refusal W3-2 exists to explain; `validated` and `review` published a number,
#: so their diagnostics are empty by construction (the 106-corpus anchor).
DIAGNOSABLE_CLASSES = ("withheld",)


# --------------------------------------------------------------------------
# Source 1 — ADB validation checks (analysis/adb.py::_validate)
#
# `metrics.adb.validations` is already a {check_name: bool} dict of OUR
# constants, so it needs no parsing: the failing names ARE the taxonomy. The
# set below is asserted equal to the literals in `analysis/adb.py`.
# --------------------------------------------------------------------------

ADB_CHECKS: frozenset[str] = frozenset({
    "statement_period_dates_valid",
    "all_transactions_dated",
    "transactions_within_period",
    "bank_daily_balance_dates_valid",
    "daily_balance_count_equals_calendar_days",
    "daily_balances_contiguous",
    "covers_opening_day",
    "covers_closing_day",
    "final_balance_matches_statement_closing",
    "ledger_reconciles_to_closing",
    "opening_balance_matches_statement",
    "running_balances_support_daily_ledger",
    "posting_dates_cover_source",
    "agrees_with_bank_stated_average",
})

# --------------------------------------------------------------------------
# Source 2 — document integrity flags (analysis/pipeline.py::assess_document_integrity)
#
# Also already enum codes. Same treatment, same drift guard.
# --------------------------------------------------------------------------

INTEGRITY_FLAGS: frozenset[str] = frozenset({
    "summary_math_inconsistent",
    "ledger_sum_mismatch",
    "running_balance_breaks",
    "credit_detail_coverage_mismatch",
    "debit_detail_coverage_mismatch",
    "transaction_detail_not_corporate_reliable",
    "not_a_formal_statement",
    "parser_ambiguous",
    # W3-1. Both say something about OUR code rather than about the statement's
    # arithmetic — a parser raised, or a registered integrity check did. They
    # are NOT treated alike: W3-2b classes `integrity_check_exception` as
    # `check_unavailable` (a diagnosis made incomplete) while
    # `parser_exception` stays advisory (a crash before any claim, so there is
    # no diagnosis to be incomplete). See CLASS_OF and ADVISORY_CODES.
    "parser_exception",
    "integrity_check_exception",
    "conflicting_statement_summaries",
    "missing_declared_statement_page",
})

# --------------------------------------------------------------------------
# Source 3 — reconciliation issues (analysis/reconcile.py, plus the one
# escalation issue appended in analysis/pipeline.py).
#
# Free text. Matched on the invariant literal PREFIX of each format string,
# plus a tail fragment where the prefix alone is not decisive; first match
# wins, and the string itself is discarded.
#
# Anchored on the prefix on purpose. The continuity issue interpolates a
# transaction description (`row 7 ('...'): balance jumped to ...`), so a
# document could otherwise put another rule's anchor inside its own
# description text and choose its own bucket. Prefix-anchoring puts the
# decision in text `analysis/` wrote, not text the statement supplied.
# --------------------------------------------------------------------------

#: (prefix, required tail fragment or None, code)
RECON_ISSUE_ANCHORS: tuple[tuple[str, str | None, str], ...] = (
    ("cannot run sum check", None, "recon:sum_check_inputs_missing"),
    ("sum check off by", None, "recon:sum_check_failed"),
    ("bank-stated summary does not reconcile", None, "recon:summary_identity_failed"),
    ("captured $", " in credits (", "recon:credit_coverage_short"),
    ("captured $", " in debits (", "recon:debit_coverage_short"),
    ("escalation extraction failed", None, "recon:escalation_extraction_failed"),
    ("row ", "balance jumped to", "recon:running_balance_break"),
)
RECON_UNMAPPED = "recon:unmapped_issue"

# --------------------------------------------------------------------------
# Source 4 — ADB warnings (analysis/adb.py).
#
# Deliberately overlapping with source 1: most warnings are the prose form of a
# validation check, and mapping them anyway costs one redundant code but means
# no warning can be dropped. The overlap earns its keep on the two paths where
# `compute_average_daily_balance` returns BEFORE `_validate` runs — no period,
# or no derivable opening balance — where `validations` is empty and the
# warning is the only evidence that exists.
#
# Substring anchors are sufficient here (unlike the reconciliation issues):
# every ADB warning interpolates only dates, counts and amounts - never a
# transaction description - so no statement text can reach these strings.
# --------------------------------------------------------------------------

ADB_WARNING_ANCHORS: tuple[tuple[str, str], ...] = (
    ("have no parseable date", "adb_state:undated_transactions"),
    ("statement period start missing", "adb_state:period_start_missing"),
    ("statement period end missing", "adb_state:period_end_missing"),
    ("statement period is inverted", "adb_state:period_inverted"),
    ("cannot determine a statement period", "adb_state:period_unresolvable"),
    ("fall outside the statement period", "adb_state:out_of_period_transactions"),
    ("no opening balance and none derivable", "adb_state:opening_balance_underivable"),
    ("does not provide a valid, ordered start and end date", "adb_state:period_dates_invalid"),
    ("bank daily balance has invalid or out-of-period date", "adb_state:daily_balance_date_invalid"),
    ("bank daily balance history contains duplicate date", "adb_state:daily_balance_date_duplicate"),
    ("daily balance series has a gap", "adb_state:daily_balance_series_gap"),
    ("daily balances for a", "adb_state:daily_balance_count_mismatch"),
    ("final reconstructed balance", "adb_state:final_balance_drift"),
    ("statement prints no closing balance", "adb_state:closing_balance_absent"),
    ("statement prints no beginning balance", "adb_state:beginning_balance_absent"),
    ("ledger does not reconcile", "adb_state:ledger_reconcile_failed"),
    ("running balances do not support", "adb_state:running_balances_unsupported"),
    ("posting date(s) but the statement", "adb_state:posting_dates_incomplete"),
    ("differs from the bank-printed", "adb_state:stated_average_disagrees"),
)
ADB_WARNING_UNMAPPED = "adb_state:unmapped_warning"

ADB_CHECK_UNMAPPED = "adb:unmapped"
INTEGRITY_UNMAPPED = "integrity:unmapped"

#: Summary-block fields whose absence is reportable. Names only, from
#: `analysis.schema.Statement`. NOTE what "absent" means here: this reads the
#: SERIALIZED payload, and `report_to_dict` nulls `ending_balance` when neither
#: the ledger nor the bank's own summary supports it. So an entry is "absent
#: from what the platform published", which is the honest thing for a
#: diagnostic to say - it is exactly the field the next stage did not get.
SUMMARY_FIELDS: tuple[str, ...] = (
    "period_start",
    "period_end",
    "beginning_balance",
    "ending_balance",
    "days_in_period",
    "stated_total_credits",
    "stated_total_debits",
    "stated_credit_count",
    "stated_debit_count",
    "stated_service_charge",
    "stated_interest_paid",
    "stated_average_balance",
    "stated_daily_balances",
)


# --------------------------------------------------------------------------
# The coarse failure classes: one per document, for the rollup.
# --------------------------------------------------------------------------

#: Ranked most-upstream first. The primary class is the highest-ranked class
#: present, so a document whose ledger fails to reconcile BECAUSE only 26% of
#: the stated debit detail was captured is reported as `detail_coverage` (the
#: cause) rather than `ledger_identity` (the symptom). Rationale per class:
#: W3_2_TAXONOMY.md section 4.
CLASS_PRECEDENCE: tuple[str, ...] = (
    "no_analysis_payload",
    "adb_not_computable",
    "extraction_failure",
    "check_unavailable",
    "source_contradiction",
    "period_integrity",
    "summary_field_missing",
    "summary_identity",
    "detail_coverage",
    "posting_date_coverage",
    "balance_continuity",
    "ledger_identity",
    "daily_ledger_structure",
    "page_coverage",
    "unmapped",
    "advisory_only",
    "undiagnosed",
)

CLASS_OF: dict[str, str] = {
    # the ADB engine never reached its validation suite
    "adb_state:period_unresolvable": "adb_not_computable",
    "adb_state:opening_balance_underivable": "adb_not_computable",
    "recon:escalation_extraction_failed": "extraction_failure",
    # W3-2b. A registered integrity check RAISED, so its finding is UNKNOWN -
    # not clean. It ranks above every financial class deliberately: the check
    # that crashed is typically the one that would have produced
    # `source_contradiction`, so its absence proves nothing, and an incomplete
    # diagnosis must never present as a confident lower class. Compare
    # `integrity:parser_exception`, which stays advisory - a parser that
    # crashed produced no claim, so there is no diagnosis to be incomplete.
    "integrity:integrity_check_exception": "check_unavailable",
    # the document contradicts itself, proven by a registration integrity check
    "integrity:conflicting_statement_summaries": "source_contradiction",
    # the period the whole calculation is divided by
    "adb:statement_period_dates_valid": "period_integrity",
    "adb:all_transactions_dated": "period_integrity",
    "adb:transactions_within_period": "period_integrity",
    "adb_state:period_start_missing": "period_integrity",
    "adb_state:period_end_missing": "period_integrity",
    "adb_state:period_inverted": "period_integrity",
    "adb_state:period_dates_invalid": "period_integrity",
    "adb_state:undated_transactions": "period_integrity",
    "adb_state:out_of_period_transactions": "period_integrity",
    # an input the checks need was not published at all
    "recon:sum_check_inputs_missing": "summary_field_missing",
    "adb:opening_balance_matches_statement": "summary_field_missing",
    "adb_state:beginning_balance_absent": "summary_field_missing",
    "adb_state:closing_balance_absent": "summary_field_missing",
    # the bank's own summary block does not satisfy its own identity
    "recon:summary_identity_failed": "summary_identity",
    "integrity:summary_math_inconsistent": "summary_identity",
    # line-item detail does not add up to the bank's stated totals
    "recon:credit_coverage_short": "detail_coverage",
    "recon:debit_coverage_short": "detail_coverage",
    "integrity:credit_detail_coverage_mismatch": "detail_coverage",
    "integrity:debit_detail_coverage_mismatch": "detail_coverage",
    # posting dates were folded together, so days carry the wrong balances
    "adb:posting_dates_cover_source": "posting_date_coverage",
    "adb_state:posting_dates_incomplete": "posting_date_coverage",
    # printed running balances contradict the reconstructed ledger
    "recon:running_balance_break": "balance_continuity",
    "integrity:running_balance_breaks": "balance_continuity",
    "adb:running_balances_support_daily_ledger": "balance_continuity",
    "adb_state:running_balances_unsupported": "balance_continuity",
    # beginning + activity != ending
    "recon:sum_check_failed": "ledger_identity",
    "integrity:ledger_sum_mismatch": "ledger_identity",
    "adb:ledger_reconciles_to_closing": "ledger_identity",
    "adb:final_balance_matches_statement_closing": "ledger_identity",
    "adb_state:ledger_reconcile_failed": "ledger_identity",
    "adb_state:final_balance_drift": "ledger_identity",
    # the reconstructed day series itself is malformed
    "adb:daily_balance_count_equals_calendar_days": "daily_ledger_structure",
    "adb:daily_balances_contiguous": "daily_ledger_structure",
    "adb:covers_opening_day": "daily_ledger_structure",
    "adb:covers_closing_day": "daily_ledger_structure",
    "adb:bank_daily_balance_dates_valid": "daily_ledger_structure",
    "adb_state:daily_balance_count_mismatch": "daily_ledger_structure",
    "adb_state:daily_balance_series_gap": "daily_ledger_structure",
    "adb_state:daily_balance_date_invalid": "daily_ledger_structure",
    "adb_state:daily_balance_date_duplicate": "daily_ledger_structure",
    # pages the statement itself declares are not in the supplied PDF
    "integrity:missing_declared_statement_page": "page_coverage",
    # the explicit never-silently-dropped bucket
    ADB_CHECK_UNMAPPED: "unmapped",
    INTEGRITY_UNMAPPED: "unmapped",
    RECON_UNMAPPED: "unmapped",
    ADB_WARNING_UNMAPPED: "unmapped",
}

#: Codes that are real evidence but must NOT decide the primary class: they are
#: consequences of another failure, or advisory comparisons that never withhold
#: on their own. They stay in `codes` (they are useful in a rollup) and are
#: enumerated here so that a NEW code cannot fall out of the class map by
#: accident - the vocabulary test asserts every code is classed or listed here.
ADVISORY_CODES: frozenset[str] = frozenset({
    "adb:agrees_with_bank_stated_average",
    "adb_state:stated_average_disagrees",
    "integrity:transaction_detail_not_corporate_reliable",
    "integrity:not_a_formal_statement",
    "integrity:parser_ambiguous",
    # W3-1: a parser raised. Routing and defect fact, not a reason the numbers
    # failed - and, unlike a crashed integrity check, it leaves NO diagnosis
    # incomplete: a parser that crashed produced no claim, so the document
    # never reached the checks at all. A withheld document carrying this was
    # withheld by a check in the classed vocabulary above, and letting a crash
    # decide the primary class would put "a parser broke" at the top of a list
    # that exists to rank WHICH FINANCIAL CHECK failed. W3-1's exception
    # ranking is where it is acted on.
    #
    # `integrity:integrity_check_exception` was advisory here until W3-2b and
    # is now classed `check_unavailable` - see CLASS_OF for why the two crash
    # flags are treated differently.
    "integrity:parser_exception",
})

#: Every code this module can ever emit.
VOCABULARY: frozenset[str] = frozenset(
    [f"adb:{name}" for name in ADB_CHECKS]
    + [f"integrity:{flag}" for flag in INTEGRITY_FLAGS]
    + [code for _, _, code in RECON_ISSUE_ANCHORS]
    + [code for _, code in ADB_WARNING_ANCHORS]
    + [ADB_CHECK_UNMAPPED, INTEGRITY_UNMAPPED, RECON_UNMAPPED, ADB_WARNING_UNMAPPED]
)

_RANK = {name: index for index, name in enumerate(CLASS_PRECEDENCE)}


def _match_issue(text: str) -> str | None:
    """First reconciliation anchor that fits. The text itself is not retained."""
    for prefix, tail, code in RECON_ISSUE_ANCHORS:
        if text.startswith(prefix) and (tail is None or tail in text):
            return code
    return None


def _match_warning(text: str) -> str | None:
    """First ADB-warning anchor that fits. The text itself is not retained."""
    for needle, code in ADB_WARNING_ANCHORS:
        if needle in text:
            return code
    return None


def empty_diagnostics() -> dict:
    """The not-diagnosed shape.

    `counts` is empty rather than zeroed: H3_SCHEMA I5 - a validated document
    has no failing-check count of zero, it has no measurement at all.
    """
    return {
        "evaluated": False,
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "primary_class": None,
        "classes": [],
        "codes": [],
        "adb_checks_failed": [],
        "integrity_flags": [],
        "summary_fields_absent": [],
        "counts": {},
        "unmapped": [],
    }


def diagnose(payload: dict | None, outcome_class: str) -> dict:
    """The per-check failure taxonomy for one document. Never mutates `payload`.

    Returns `empty_diagnostics()` for every outcome class that is not
    diagnosable, which is what makes the 106 pinned non-withheld documents
    produce nothing.
    """
    if outcome_class not in DIAGNOSABLE_CLASSES or not isinstance(payload, dict):
        return empty_diagnostics()

    reconciliation = payload.get("reconciliation") or {}
    metrics = payload.get("metrics") or {}
    adb = metrics.get("adb") or {}
    integrity = payload.get("integrity") or {}
    statement = payload.get("statement") or {}

    codes: set[str] = set()
    unmapped: set[str] = set()
    unmapped_issues = 0
    unmapped_warnings = 0

    # 1. ADB validation checks, by name.
    validations = adb.get("validations") or {}
    adb_failed: list[str] = []
    for name, passed in validations.items():
        if not isinstance(name, str):
            continue
        if name not in ADB_CHECKS:
            codes.add(ADB_CHECK_UNMAPPED)
            unmapped.add(f"adb:{name}")
            if not passed:
                adb_failed.append(name)
            continue
        if not passed:
            adb_failed.append(name)
            codes.add(f"adb:{name}")

    # 2. Integrity flags, by name.
    flags: list[str] = []
    for flag in integrity.get("flags") or []:
        if not isinstance(flag, str):
            continue
        flags.append(flag)
        if flag in INTEGRITY_FLAGS:
            codes.add(f"integrity:{flag}")
        else:
            codes.add(INTEGRITY_UNMAPPED)
            unmapped.add(f"integrity:{flag}")

    # 3. Reconciliation issues - matched, then discarded.
    issues = reconciliation.get("issues") or []
    for issue in issues:
        if not isinstance(issue, str):
            continue
        code = _match_issue(issue)
        if code is None:
            codes.add(RECON_UNMAPPED)
            unmapped_issues += 1
        else:
            codes.add(code)

    # 4. ADB warnings - matched, then discarded.
    warnings = adb.get("warnings") or []
    for warning in warnings:
        if not isinstance(warning, str):
            continue
        code = _match_warning(warning)
        if code is None:
            codes.add(ADB_WARNING_UNMAPPED)
            unmapped_warnings += 1
        else:
            codes.add(code)

    # 5. Which summary fields the payload does not carry. Names only.
    absent = [
        field for field in SUMMARY_FIELDS
        if statement.get(field) in (None, [], "")
    ]

    classes = sorted(
        {CLASS_OF[code] for code in codes if code in CLASS_OF},
        key=lambda name: _RANK[name],
    )
    if not classes:
        # Withheld, but nothing that decides a class. Both outcomes are
        # findings in their own right, so each gets its own name rather than
        # a null: `advisory_only` = evidence exists but is all consequence or
        # comparison; `undiagnosed` = the platform withheld and this taxonomy
        # saw nothing at all, which means a check went unobserved.
        classes = ["advisory_only" if codes else "undiagnosed"]
    primary = classes[0]

    return {
        "evaluated": True,
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "primary_class": primary,
        "classes": classes,
        "codes": sorted(codes),
        "adb_checks_failed": sorted(adb_failed),
        "integrity_flags": sorted(flags),
        "summary_fields_absent": absent,
        "counts": {
            "reconciliation_issues": len(issues),
            "unmapped_reconciliation_issues": unmapped_issues,
            "adb_warnings": len(warnings),
            "unmapped_adb_warnings": unmapped_warnings,
            "adb_checks_run": len(validations),
            "adb_checks_failed": len(adb_failed),
            "continuity_breaks": _count(reconciliation.get("continuity_breaks")),
            "transactions": len(statement.get("transactions") or []),
            "transactions_with_running_balance": sum(
                1 for row in statement.get("transactions") or []
                if isinstance(row, dict) and row.get("running_balance") is not None
            ),
            "stated_daily_balances": _count(adb.get("stated_daily_balance_count")),
            "out_of_period_transactions": _count(adb.get("out_of_period_transaction_count")),
            "missing_posting_dates": len(adb.get("missing_posting_dates") or []),
            "calendar_days": _count(adb.get("calendar_day_count")),
            "parsed_posting_days": _count(adb.get("parsed_posting_days")),
            "source_posting_days": _count(adb.get("source_posting_days")),
        },
        "unmapped": sorted(unmapped),
    }


def _count(value: object) -> int | None:
    """A count, or None when the platform did not measure it (H3_SCHEMA I5).

    `None` is not zero: `source_posting_days` is null when the ADB engine had
    no source text to compare against, which is a different fact from "the
    statement prints no posting dates".
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
