"""Per-set comparison builder.

For each benchmark set this module lines up our production payload,
MoneyThumb's normalized output, and the audited expectations, and emits one
``ComparisonRow`` per compared field plus the set's capability findings.

Statement coverage (no silent omissions - see ``benchmark.coverage`` for the
proof): period bounds, beginning/ending balances, credit/debit totals and
counts, transaction count, ADB (withheld ADB compares as "withheld by
design"), min balance, negative days, NSF count/total, net cash flow, bank
and account identification, currency, reconciliation verdict, the revenue
taxonomies (three-state vs true/non-true, gross credits compared directly,
the pre-ruled 'Total Revenue' mislabel), per-lender MCA activity and funding
deposits, the daily-balance series, and package-level rows for the
multi-statement set.
"""
from __future__ import annotations

import re
import statistics
from typing import Any

from .classify import ComparisonRow, Outcome, UNSET, classify, values_match
from .expectations import Expectation
from analysis.flag_groups import FLAG_GROUP_BY_KEY

from .lenders import canonical_lender, flagged_lender_groups, ledger_tokens
from .manifest import BenchmarkSet
from .masking import mask_account, transaction_ref
from .normalize import MTLender, MTResultRow, MTSet, MTStatementRow, last4, parse_money
from .ourside import OurFileResult, OurSetResult

_CURRENCY_RE = re.compile(r"(?:Currency|Devise)\s*[:=]?\s*([A-Z]{3})\b")


def _audit_evidence(csv_name: str, statement: str, column: str, extra: str = "") -> dict:
    evidence = {
        "kind": "audit_csv",
        "file": f"docs/{csv_name}",
        "row": statement,
        "column": column,
    }
    if extra:
        evidence["detail"] = extra
    return evidence


def _printed_summary_evidence(detail: str) -> dict:
    return {
        "kind": "printed_summary",
        "detail": detail
        + " (statement's printed summary section, cross-checked by the "
        "reconciliation summary identity and the audited transaction count)",
    }


def _ledger_evidence(rows: list[dict[str, Any]], detail: str) -> dict:
    total = round(sum(abs(parse_money(r.get("amount")) or 0.0) for r in rows), 2)
    return {
        "kind": "ledger_rows",
        "detail": detail,
        "count": len(rows),
        "total": total,
        "transactions": [transaction_ref(r) for r in rows[:25]],
    }


def _statement_locator(name: str) -> str:
    return f"Bank Statements/{name}"


def _mt_summary_for(
    mt: MTSet, result: MTResultRow | None
) -> MTStatementRow | None:
    """The scorecard summary row matching a results row (account + month)."""
    if result is None:
        return None
    candidates = [
        row
        for row in mt.summary_rows
        if row.account_last4 is None
        or result.account_last4 is None
        or row.account_last4 == result.account_last4
    ]
    if result.end_date:
        month = result.end_date[:7]
        by_month = [row for row in candidates if (row.ending_date or "")[:7] == month]
        if by_month:
            return by_month[0]
    return candidates[0] if candidates else None


def _primary_result(mt: MTSet, filename: str) -> MTResultRow | None:
    """MT's row for the account with the most activity in one uploaded file."""
    rows = [row for row in mt.result_rows if row.filename == filename]
    if not rows:
        rows = mt.result_rows
    if not rows:
        return None
    return max(rows, key=lambda row: row.num_transactions or 0)


def _mt_activity_mean_note(mt: MTSet, summary: MTStatementRow | None) -> str:
    """Document MT's ADB basis when its own series reproduces its own average.

    CORRECTED (ADB-SPLIT card 4). This note used to say "activity-day basis",
    which was wrong and, worse, was undocumented MoneyThumb behaviour stated as
    if it were a specification. What is REPRODUCED, and all that is claimed
    here, was re-measured over `moneythumbResults/results` on 2026-08-15:

      * **11 of 11** MT daily-balance series are exactly the BANKING DAYS of
        their own span - Monday to Friday minus observed US federal Reserve
        Bank holidays. Not activity days: several of those days carry no
        posting at all, and every weekday holiday in range is absent.
      * **10 of 11** rows have `avg_balance` equal, to the cent, to the plain
        mean of that series (the eleventh differs by 0.01, a rounding
        presentation difference).
      * **6 of 6** documents where our own ledger validates AND MT prints an
        average reproduce MT's figure EXACTLY from our ledger under the
        banking-day denominator. Under a weekday-only denominator only 1 of
        those 6 reproduces, so the federal-holiday calendar is load-bearing.
      * **0 of 11** match a calendar-day mean over the same span.

    None of that makes the banking-day basis correct, and none of it is a
    specification: MT documents no basis, and this is inference from output.
    It is recorded so an analyst reading an `adb` row knows the two systems
    are answering different questions rather than one of them being wrong.
    Our published figure remains the canonical calendar-day underwriting ADB;
    `metrics.adb.underwriting_adb_alternates["banking_day"]` computes MT's
    construction over our ledger for exactly this comparison, and is never
    published as an ADB.
    """
    if summary is None or summary.avg_balance is None:
        return ""
    series = mt.daily_balances(summary.account_last4)
    if not series:
        return ""
    mean = round(statistics.mean(series.values()), 2)
    if values_match(mean, summary.avg_balance):
        return (
            f"MT's avg_balance equals the mean of its {len(series)} reported "
            "daily balances, which are the banking days of the span "
            "(weekdays minus federal bank holidays), not calendar days. "
            "Definition-relative difference, not an error by either system."
        )
    return ""


def build_statement_rows(
    set_name: str,
    prefix: str,
    our_file: OurFileResult,
    mt: MTSet,
    mt_result: MTResultRow | None,
    mt_summary: MTStatementRow | None,
    expectation: Expectation | None,
) -> list[ComparisonRow]:
    statement = our_file.statement
    metrics = our_file.metrics
    recon = our_file.reconciliation
    exp = expectation or Expectation(statement="")
    stmt_name = exp.statement or our_file.relative_path.rsplit("/", 1)[-1]
    contradiction_note = (
        "The source document contradicts itself on this field (audit: "
        f"{exp.balance_status or exp.adb_status}: "
        f"{exp.balance_root_cause or exp.adb_root_cause}). Our fail-closed "
        "withholding/retention is the defensible behaviour; MoneyThumb's "
        "reported value is recorded as commentary, not as correct."
        if exp.source_contradiction
        else None
    )
    summary_trusted = (
        recon.get("summary_ok") is True and not exp.source_contradiction
    )
    rows: list[ComparisonRow] = []

    def field(name: str) -> str:
        return f"{prefix}{name}"

    # --- identification -------------------------------------------------
    rows.append(
        classify(
            set_name, field("bank_name"),
            statement.get("bank"),
            mt_result.bank_name if mt_result else (mt_summary.bank_name if mt_summary else None),
            expected=exp.bank if exp.bank else UNSET,
            expected_evidence=_audit_evidence("adb-audit-results.csv", stmt_name, "bank"),
        )
    )

    ours_account = statement.get("account_number")
    mt_account = mt_result.account_number if mt_result else None
    expected_account = exp.account
    source_account = UNSET
    source_account_evidence = None
    if not expected_account and mt_account:
        digits = re.sub(r"\D", "", str(mt_account)).lstrip("0")
        if digits and (digits in our_file.markdown):
            source_account = last4(mt_account)
            source_account_evidence = {
                "kind": "source_text",
                "detail": "the account number MoneyThumb reports appears verbatim "
                f"in the statement text ({_statement_locator(stmt_name)})",
            }
    account_row = classify(
        set_name, field("account_number"),
        last4(ours_account), last4(mt_account),
        expected=last4(expected_account) if expected_account else UNSET,
        expected_evidence=_audit_evidence(
            "balance-metrics-audit-results.csv", stmt_name, "account"
        ),
        source_value=source_account,
        source_evidence=source_account_evidence,
        note="Values compared on last-4; all report renderings are masked.",
    )
    account_row.ours = mask_account(ours_account)
    account_row.mt = mask_account(mt_account)
    account_row.expected = mask_account(expected_account) if expected_account else None
    rows.append(account_row)

    printed_currency = _CURRENCY_RE.search(our_file.markdown)
    rows.append(
        classify(
            set_name, field("currency"),
            statement.get("currency"),
            mt_result.currency if mt_result else None,
            source_value=printed_currency.group(1) if printed_currency else UNSET,
            source_evidence={
                "kind": "source_text",
                "detail": f"printed marker '{printed_currency.group(0)}' in "
                f"{_statement_locator(stmt_name)}",
            } if printed_currency else None,
            material=False,
        )
    )

    # --- period ---------------------------------------------------------
    for name, ours_value, mt_value, column in (
        ("period_start", statement.get("period_start"),
         mt_summary.start_date if mt_summary else (mt_result.start_date if mt_result else None),
         "period_start"),
        ("period_end", statement.get("period_end"),
         mt_summary.ending_date if mt_summary else (mt_result.end_date if mt_result else None),
         "period_end"),
    ):
        rows.append(
            classify(
                set_name, field(name), ours_value, mt_value,
                expected=getattr(exp, column) or UNSET,
                expected_evidence=_audit_evidence("adb-audit-results.csv", stmt_name, column),
            )
        )

    # --- balances -------------------------------------------------------
    rows.append(
        classify(
            set_name, field("beginning_balance"),
            statement.get("beginning_balance"),
            mt_summary.starting_balance if mt_summary else (mt_result.start_balance if mt_result else None),
            expected=exp.opening if exp.opening is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", stmt_name, "expected_opening",
                extra=exp.balance_root_cause or "",
            ),
            contradiction=contradiction_note,
        )
    )
    ending_ours = statement.get("ending_balance")
    ending_note = ""
    if mt_result is not None and mt_result.end_balance_calc is not None:
        ending_note = (
            f"MT variants: endBalance={mt_result.end_balance}, "
            f"endBalanceCalc={mt_result.end_balance_calc}, "
            f"endBalancePDF={mt_result.end_balance_pdf}, "
            f"reconciled={mt_result.reconciled}."
        )
    rows.append(
        classify(
            set_name, field("ending_balance"),
            ending_ours,
            mt_summary.ending_balance if mt_summary else (mt_result.end_balance if mt_result else None),
            expected=exp.ending if exp.ending is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", stmt_name, "expected_ending",
            ),
            ours_withheld=ending_ours is None,
            contradiction=contradiction_note,
            note=ending_note,
        )
    )

    rows.append(
        classify(
            set_name, field("reconciliation_verdict"),
            recon.get("ok"),
            mt_result.reconciled if mt_result else (mt_summary.reconciled if mt_summary else None),
            expected=exp.detail_reconciles if exp.detail_reconciles is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", stmt_name, "detail_ledger_reconciles",
            ),
            note="Our ReconResult carries issue-level detail beyond the boolean.",
        )
    )

    # --- volume ---------------------------------------------------------
    volume_fields = (
        ("total_credits", metrics.get("effective_total_deposits"),
         mt_summary.total_credits if mt_summary else None,
         statement.get("stated_total_credits"), "stated_total_credits"),
        ("num_credits", metrics.get("effective_num_deposits"),
         mt_summary.num_credits if mt_summary else None,
         statement.get("stated_credit_count"), "stated_credit_count"),
        ("total_debits", metrics.get("effective_total_withdrawals"),
         abs(mt_summary.total_debits) if mt_summary and mt_summary.total_debits is not None else None,
         statement.get("stated_total_debits"), "stated_total_debits"),
        ("num_debits", metrics.get("effective_num_withdrawals"),
         mt_summary.num_debits if mt_summary else None,
         statement.get("stated_debit_count"), "stated_debit_count"),
    )
    for name, ours_value, mt_value, stated, stated_field in volume_fields:
        rows.append(
            classify(
                set_name, field(name), ours_value, mt_value,
                source_value=stated if (summary_trusted and stated is not None) else UNSET,
                source_evidence=_printed_summary_evidence(
                    f"printed {stated_field.replace('stated_', '').replace('_', ' ')} "
                    f"in {_statement_locator(stmt_name)}"
                ),
                contradiction=contradiction_note,
            )
        )

    rows.append(
        classify(
            set_name, field("transaction_count"),
            len(statement.get("transactions") or []),
            mt_result.num_transactions if mt_result else None,
            expected=exp.transactions if exp.transactions is not None else UNSET,
            expected_evidence=_audit_evidence("adb-audit-results.csv", stmt_name, "transactions"),
        )
    )

    expected_net = (
        round(exp.ending - exp.opening, 2)
        if exp.ending is not None and exp.opening is not None
        else None
    )
    rows.append(
        classify(
            set_name, field("net_cash_flow"),
            metrics.get("cash_flow"),
            mt_summary.net_cashflow if mt_summary else None,
            expected=expected_net if expected_net is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", stmt_name,
                "expected_ending - expected_opening",
            ),
            contradiction=contradiction_note,
        )
    )

    # Decidable direction check: when MT's own printed start/end balances
    # imply the opposite sign from MT's net cash flow, the credit/debit
    # orientation is arithmetically decidable without trusting either parser.
    mt_net = mt_summary.net_cashflow if mt_summary else None
    mt_start = mt_summary.starting_balance if mt_summary else None
    mt_end = mt_summary.ending_balance if mt_summary else None
    our_net = metrics.get("cash_flow")
    our_open = statement.get("beginning_balance")
    our_close = statement.get("ending_balance")
    if (
        mt_net is not None and mt_start is not None and mt_end is not None
        and abs(mt_net) > 1 and abs(mt_end - mt_start) > 1
        and (mt_end - mt_start) * mt_net < 0
    ):
        our_consistent = (
            our_net is not None and our_open is not None and our_close is not None
            and (our_close - our_open) * our_net > 0
        )
        direction_evidence = {
            "kind": "printed_balances",
            "detail": (
                "printed opening/closing balances as extracted by BOTH systems "
                f"(MT: {mt_start} -> {mt_end}; ours: {our_open} -> {our_close}) "
                "imply the sign of the period's net flow"
            ),
        }
        rows.append(
            ComparisonRow(
                set_name=set_name, field=field("net_flow_direction"),
                outcome=(
                    Outcome.OUR_SYSTEM_CORRECT if our_consistent else Outcome.UNRESOLVED
                ),
                ours=f"net {our_net:+.2f} (consistent with printed balances)"
                if our_consistent else f"net {our_net}",
                mt=f"net {mt_net:+.2f} contradicts MT's own printed "
                f"{mt_start} -> {mt_end} (delta {mt_end - mt_start:+.2f})",
                evidence=direction_evidence,
                rationale=(
                    "MoneyThumb's reported net cash flow has the opposite sign "
                    "of the movement implied by the printed balances MT itself "
                    "extracted - its credit/debit orientation is inverted for "
                    "this document. "
                    + ("Our orientation agrees with the printed balance "
                       "movement." if our_consistent else
                       "Our own orientation could not be confirmed against "
                       "printed balances - queued for Ocean.")
                ),
                for_ocean=not our_consistent,
            )
        )

    # --- balance analytics ----------------------------------------------
    adb_withheld = metrics.get("adb_ok") is not True
    adb_note_parts = [_mt_activity_mean_note(mt, mt_summary)]
    # DEFINITION-RELATIVE FRAMING (ADB-SPLIT card 4). An `adb` row that comes
    # back OUR_SYSTEM_CORRECT says our figure matches OUR audited expectation
    # and MoneyThumb's does not. That is true and it is worth knowing, but on
    # its own it reads as "MT computed the ADB wrongly", which the measurement
    # does not support: MT reproduces its own banking-day figure exactly (see
    # `_mt_activity_mean_note`), and on six benchmark documents our OWN ledger
    # reproduces MT's number under that denominator. The disagreement is about
    # which days the denominator counts, and our answer is authoritative
    # because it is the platform's ratified definition - not because MT's
    # arithmetic failed. Every adb verdict here carries that qualification.
    adb_alternates = (metrics.get("adb") or {}).get("underwriting_adb_alternates") or {}
    if not adb_withheld and mt_summary is not None and mt_summary.avg_balance is not None:
        banking = adb_alternates.get("banking_day")
        adb_note_parts.append(
            "DEFINITION-RELATIVE: ours is the canonical calendar-day "
            "underwriting ADB over the printed period; a verdict here is "
            "against that definition, not a finding that MoneyThumb "
            "miscalculated."
            + (
                f" Our own ledger on MT's banking-day denominator = {banking}."
                if banking is not None
                else ""
            )
        )
    if exp.printed_adb is not None:
        adb_note_parts.append(
            f"Bank prints '{exp.printed_adb_label}' = {exp.printed_adb} "
            "(audited: alternate/rounded balance basis - see adb CSV root_cause)."
        )
    rows.append(
        classify(
            set_name, field("adb"),
            metrics.get("average_daily_balance"),
            mt_summary.avg_balance if mt_summary else None,
            expected=exp.adb if exp.adb is not None else UNSET,
            expected_evidence=_audit_evidence(
                "adb-audit-results.csv", stmt_name, "independent_candidate_adb",
                extra="independent calendar-day reconstruction, ledger validated",
            ),
            ours_withheld=adb_withheld,
            contradiction=contradiction_note,
            note=" ".join(part for part in adb_note_parts if part),
        )
    )

    min_ours = metrics.get("min_balance")
    rows.append(
        classify(
            set_name, field("min_balance"),
            min_ours,
            mt_summary.min_balance if mt_summary else None,
            expected=exp.lowest if exp.lowest is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", stmt_name, "expected_lowest",
            ),
            ours_withheld=min_ours is None,
            contradiction=contradiction_note,
        )
    )

    ledger = our_file.daily_ledger()
    ledger_validated = bool(ledger) and exp.adb_ledger_valid
    negative_from_ledger = (
        sum(1 for balance in ledger.values() if balance < 0) if ledger_validated else None
    )
    rows.append(
        classify(
            set_name, field("negative_days"),
            metrics.get("negative_days"),
            mt_summary.days_neg if mt_summary else None,
            source_value=negative_from_ledger if negative_from_ledger is not None else UNSET,
            source_evidence={
                "kind": "validated_daily_ledger",
                "detail": f"per-calendar-day ledger for {stmt_name}, independently "
                "validated by the ADB audit (independent_ledger_valid=True)",
                "negative_days": negative_from_ledger,
            },
            material=False,
        )
    )

    ledger_complete = (
        recon.get("ok") is True
        and exp.transactions is not None
        and exp.transactions == len(statement.get("transactions") or [])
    )
    nsf_ours = metrics.get("nsf_count")
    rows.append(
        classify(
            set_name, field("nsf_count"),
            nsf_ours,
            mt_summary.num_nsfs if mt_summary else (mt_result.nsf_count if mt_result else None),
            source_value=nsf_ours if ledger_complete else UNSET,
            source_evidence={
                "kind": "ledger_rows",
                "detail": "NSF-classified rows in the complete reconciled ledger "
                f"(transaction count matches the audited {exp.transactions})",
                "count": nsf_ours,
            },
            material=False,
        )
    )
    rows.append(
        classify(
            set_name, field("nsf_total"),
            0.0 if nsf_ours == 0 else None,
            mt_summary.total_nsfs if mt_summary else None,
            source_value=0.0 if (ledger_complete and not nsf_ours) else UNSET,
            source_evidence={
                "kind": "ledger_rows",
                "detail": "no NSF-classified rows in the complete reconciled ledger",
                "count": 0,
            },
            material=False,
            note="We do not emit a standalone NSF dollar total today (counts + "
            "classified rows instead).",
        )
    )

    # --- revenue --------------------------------------------------------
    rows.append(
        classify(
            set_name, field("revenue_taxonomy"),
            {
                "verified_revenue": metrics.get("verified_revenue_total"),
                "verified_count": metrics.get("verified_revenue_count"),
                "unverified_deposits": metrics.get("unverified_deposit_total"),
                "unverified_count": metrics.get("unverified_deposit_count"),
                "non_revenue": metrics.get("non_revenue_total"),
                "non_revenue_count": metrics.get("non_revenue_count"),
            },
            {
                "true_credits": mt_summary.true_credits if mt_summary else None,
                "num_true_credits": mt_summary.num_true_credits if mt_summary else None,
                "nontrue_credits": mt_summary.nontrue_credits if mt_summary else None,
                "num_nontrue_credits": mt_summary.num_nontrue_credits if mt_summary else None,
            },
            different_definition={
                "ours": "three-state evidence-gated revenue classification "
                "(verified / unverified / non-revenue) with conservation "
                "identity and review loop",
                "moneythumb": "binary true / non-true credit split with no "
                "published evidence trail",
            },
            note="Gross credits are compared directly in the gross_posted_credits "
            "row; the taxonomies themselves are not forced into a winner.",
        )
    )
    rows.append(
        classify(
            set_name, field("gross_posted_credits"),
            metrics.get("total_posted_credits"),
            mt_summary.total_credits if mt_summary else None,
            source_value=(
                statement.get("stated_total_credits")
                if summary_trusted and statement.get("stated_total_credits") is not None
                else UNSET
            ),
            source_evidence=_printed_summary_evidence(
                f"printed total credits in {_statement_locator(stmt_name)}"
            ),
            contradiction=contradiction_note,
        )
    )

    return rows


def build_revenue_statistics_row(
    set_name: str, mt: MTSet, ours: OurSetResult
) -> ComparisonRow | None:
    """The pre-ruled 'Total Revenue' mislabel row (per set)."""
    stat = mt.revenue_statistic("Total Revenue")
    if stat is None:
        return None
    mt_value = parse_money(stat.get("monthly"))
    our_cash_flow = round(
        sum(f.metrics.get("cash_flow") or 0.0 for f in ours.files), 2
    )
    row = classify(
        set_name, "mt_total_revenue_row",
        {"verified_revenue_total": round(
            sum(f.metrics.get("verified_revenue_total") or 0.0 for f in ours.files), 2)},
        {"revenue_statistics['Total Revenue'].monthly": mt_value},
    )
    relation = (
        "equals our net cash flow for the compared statements"
        if values_match(mt_value, our_cash_flow)
        else "is a net-cash-flow-style quantity (our net cash flow for the "
        f"compared statements is {our_cash_flow})"
    )
    row.rationale += (
        f" MT's 'Total Revenue' value ({mt_value}) {relation}, not revenue."
    )
    return row


def build_mca_rows(
    set_name: str,
    ours: OurSetResult,
    mt: MTSet,
) -> list[ComparisonRow]:
    """Per-lender MCA comparison across the whole set (all files)."""
    rows: list[ComparisonRow] = []

    # Our side, canonicalized: confirmed + potential lenders.
    our_lenders: dict[str, dict[str, Any]] = {}
    for our_file in ours.files:
        detection = our_file.detection
        for kind, entries in (
            ("confirmed", detection.get("known_funders") or []),
            ("potential", detection.get("potential_lenders") or []),
        ):
            for funder in entries:
                canonical = canonical_lender(funder.get("funder"))
                entry = our_lenders.setdefault(
                    canonical,
                    {"kind": kind, "count": 0, "total": 0.0, "transactions": [],
                     "label": funder.get("funder")},
                )
                entry["count"] += funder.get("debit_count") or 0
                entry["total"] = round(entry["total"] + abs(funder.get("total_debited") or 0.0), 2)
                entry["transactions"].extend(funder.get("transactions") or [])

    # Counterparties our payload flags (owner ruling 2026-09-24) are not
    # lenders here, and a MoneyThumb lender matching one is no miss.
    our_flagged = flagged_lender_groups(our_file.detection for our_file in ours.files)

    mt_lenders: dict[str, MTLender] = {}
    for label, lender in mt.lenders().items():
        mt_lenders[canonical_lender(label)] = lender

    def ledger_debits(canonical: str) -> list[dict[str, Any]]:
        tokens = ledger_tokens(canonical)
        found: list[dict[str, Any]] = []
        for our_file in ours.files:
            for txn in our_file.ledger_rows_matching(tokens):
                amount = parse_money(txn.get("amount"))
                if amount is not None and amount < 0:
                    found.append(txn)
        return found

    def ledger_credits(canonical: str) -> list[dict[str, Any]]:
        tokens = ledger_tokens(canonical)
        found: list[dict[str, Any]] = []
        for our_file in ours.files:
            for txn in our_file.ledger_rows_matching(tokens):
                amount = parse_money(txn.get("amount"))
                if amount is not None and amount > 0:
                    found.append(txn)
        return found

    for canonical in sorted(set(our_lenders) | set(mt_lenders)):
        our_entry = our_lenders.get(canonical)
        mt_entry = mt_lenders.get(canonical)
        flagged_entry = our_flagged.get(canonical) if our_entry is None else None
        tracked = our_entry or flagged_entry
        our_count = tracked["count"] if tracked else None
        our_total = tracked["total"] if tracked else None
        mt_count = mt_entry.withdrawal_count if mt_entry else None
        mt_total = mt_entry.withdrawal_total if mt_entry else None

        evidence_rows = (
            [t for t in our_entry["transactions"]
             if (parse_money(t.get("amount")) or 0) < 0]
            if our_entry else ledger_debits(canonical)
        )
        ledger_count = len(evidence_rows) if evidence_rows else None
        ledger_total = (
            round(sum(abs(parse_money(t.get("amount")) or 0.0) for t in evidence_rows), 2)
            if evidence_rows else None
        )
        evidence = (
            _ledger_evidence(
                evidence_rows,
                f"ledger debits matching lender '{canonical}' "
                "(reconciled statement line items)",
            )
            if evidence_rows else None
        )

        scope_note = ""
        different_definition = None
        if flagged_entry is not None and mt_entry is not None:
            group = flagged_entry["group"]
            label = FLAG_GROUP_BY_KEY[group].label if group in FLAG_GROUP_BY_KEY else str(group)
            different_definition = {
                "ours": f"flagged here as {label}: a financing obligation outside "
                "lender math (owner ruling 2026-09-24)",
                "moneythumb": "MCA-specific lender list (mca_transactions)",
            }
            scope_note = f"'{canonical}' is flagged here ({label}), not a missed lender."
        potential_note = (
            " Detected by our POTENTIAL-lender tier (review-gated), not the "
            "confirmed tier." if our_entry and our_entry["kind"] == "potential" else ""
        )

        # Deposit-only lender entries (e.g. a funding credit with no
        # withholding debits yet) have nothing to compare on the withdrawal
        # side - the funding_deposits row below carries the comparison.
        any_withdrawals = bool(our_count) or bool(mt_count) or bool(ledger_count)
        for suffix, ours_value, mt_value, source_value in (
            ("withdrawal_count", our_count, mt_count, ledger_count),
            ("withdrawal_total", our_total, mt_total, ledger_total),
        ) if any_withdrawals else ():
            if different_definition is not None:
                row = classify(
                    set_name, f"mca.{canonical}.{suffix}", ours_value, mt_value,
                    different_definition=different_definition,
                    note=scope_note + potential_note,
                )
            else:
                row = classify(
                    set_name, f"mca.{canonical}.{suffix}", ours_value, mt_value,
                    source_value=source_value if source_value is not None else UNSET,
                    source_evidence=evidence,
                    note=potential_note.strip(),
                )
                if row.outcome is Outcome.MONEYTHUMB_CORRECT and our_entry is None:
                    row.for_ocean = True
                    row.rationale += (
                        " Our lender detection missed this financing counterparty "
                        "entirely; adding it to the classification registry is "
                        "LEDGER-owned data and requires an Ocean ruling (queued)."
                    )
            rows.append(row)

        mt_deposit = mt_entry.deposit_total if mt_entry else 0.0
        credit_rows = ledger_credits(canonical)
        our_deposit = (
            round(sum(parse_money(t.get("amount")) or 0.0 for t in credit_rows), 2)
            if credit_rows else 0.0
        )
        if (mt_deposit or 0.0) > 0 or our_deposit > 0:
            rows.append(
                classify(
                    set_name, f"mca.{canonical}.funding_deposits",
                    our_deposit if our_deposit else None,
                    mt_deposit if mt_deposit else None,
                    source_value=our_deposit if credit_rows else UNSET,
                    source_evidence=_ledger_evidence(
                        credit_rows,
                        f"ledger credits matching lender '{canonical}' "
                        "(funding proceeds)",
                    ) if credit_rows else None,
                    note=(
                        f"MT deposit dates: {mt_entry.deposit_dates}. "
                        if mt_entry and mt_entry.deposit_dates else ""
                    )
                    + "Our side recognizes lender funding credits as non-revenue "
                    "(lender_credits metric).",
                )
            )

    # Aggregate lender-set row.
    our_confirmed = sorted(
        canonical for canonical, entry in our_lenders.items() if entry["kind"] == "confirmed"
    )
    mt_detected = sorted(mt_lenders)
    ours_only = [c for c in our_confirmed if c not in mt_lenders]
    # A MoneyThumb lender our payload carries as a flagged position is not a
    # miss: the owner ruled it out of lender math (2026-09-24).
    mt_flagged = [c for c in mt_detected if c not in our_lenders and c in our_flagged]
    mt_only = [c for c in mt_detected if c not in our_lenders and c not in our_flagged]
    flagged_note = (
        f" MoneyThumb lenders flagged here, not missed: {mt_flagged}." if mt_flagged else ""
    )
    mt_only_corroborated = [c for c in mt_only if ledger_debits(c)]
    mt_only_deposit_only = [
        c for c in mt_only if (mt_lenders[c].withdrawal_count or 0) == 0
    ]
    if mt_flagged and not mt_only and not ours_only:
        rows.append(
            classify(
                set_name, "mca_lender_set", our_confirmed, mt_detected,
                different_definition={
                    "ours": "lenders are MCA and equipment-financing funders; other "
                    "financing obligations are flagged positions (owner ruling 2026-09-24)",
                    "moneythumb": "MCA-specific lender list (mca_transactions)",
                },
                note=flagged_note.strip(),
            )
        )
        return rows
    if mt_only and not ours_only and all(
        c in mt_only_deposit_only for c in mt_only
    ) and all(ledger_credits(c) for c in mt_only):
        # MT counts a position on the funding deposit alone; we recognized the
        # same deposit as a lender funding credit (non-revenue) but list a
        # lender only once withholding debits exist.
        aggregate = classify(
            set_name, "mca_lender_set", our_confirmed, mt_detected,
            different_definition={
                "ours": "lender listed when registry-confirmed withholding "
                "debits exist (funding credits tracked separately as "
                "lender_credits/non-revenue)",
                "moneythumb": "lender listed on a funding deposit alone "
                "(no withdrawals required)",
            },
            note=f"MT-only {mt_only} are deposit-only entries; our ledger "
            "recognizes the same funding credit(s) - see the "
            "funding_deposits row(s)." + flagged_note,
        )
        rows.append(aggregate)
        return rows
    if not ours_only and not mt_only:
        outcome_note = (
            "Identical canonical lender sets; per-lender rows carry the "
            "count/total evidence."
        )
        aggregate = classify(
            set_name, "mca_lender_set", our_confirmed, mt_detected,
            source_value=our_confirmed,
            source_evidence={"kind": "ledger_rows",
                             "detail": "per-lender ledger evidence (see mca.* rows)"},
            note=outcome_note,
        )
    elif mt_only_corroborated and not ours_only:
        aggregate = ComparisonRow(
            set_name=set_name, field="mca_lender_set",
            outcome=Outcome.MONEYTHUMB_CORRECT,
            ours=our_confirmed, mt=mt_detected,
            evidence={"kind": "ledger_rows",
                      "detail": f"ledger corroborates MT-only lenders {mt_only_corroborated}"},
            rationale=(
                "MoneyThumb detected financing counterparties "
                f"{mt_only_corroborated} that our registry missed (ledger rows "
                "corroborate). Registry additions require an Ocean ruling."
            ),
            for_ocean=True,
        )
    elif ours_only and not mt_only:
        aggregate = ComparisonRow(
            set_name=set_name, field="mca_lender_set",
            outcome=Outcome.OUR_SYSTEM_CORRECT,
            ours=our_confirmed, mt=mt_detected,
            evidence={"kind": "ledger_rows",
                      "detail": f"registry-confirmed ledger evidence for {ours_only}"},
            rationale=(
                f"We detected MCA-scope lenders {ours_only} that MoneyThumb "
                "missed; the reconciled ledger rows are the evidence."
            ),
        )
    else:
        aggregate = classify(
            set_name, "mca_lender_set", our_confirmed, mt_detected,
            note=f"ours-only={ours_only}, mt-only={mt_only}.",
        )
    aggregate.rationale += flagged_note
    rows.append(aggregate)

    return rows


def build_withholding_row(
    set_name: str, ours: OurSetResult, mt_summary: MTStatementRow | None
) -> ComparisonRow | None:
    if mt_summary is None or mt_summary.mca_withhold_percent is None:
        return None
    if ours.package:
        totals = ours.package.get("totals") or {}
        numerator = totals.get("withholding_numerator") or 0.0
        denominator = totals.get("withholding_denominator") or 0.0
        our_rate = round(numerator / denominator * 100, 2) if denominator else None
        rate_note = "Our rate is the package-level aggregate; MT value is its first month row."
    else:
        our_rate = ours.primary.metrics.get("withholding_rate")
        rate_note = ""
    return classify(
        set_name, "mca_withhold_percent",
        our_rate,
        mt_summary.mca_withhold_percent,
        different_definition={
            "ours": ours.primary.metrics.get("withholding_formula")
            or "documented withholding formula",
            "moneythumb": "opaque 'mca_withhold_percent' (definition unpublished)",
        },
        note="FIELD_MAPPING s7: underwriting-ratio definitions must be ours, "
        "documented, and evidence-based - MT's are opaque. " + rate_note,
    )


def build_position_count_row(
    set_name: str, ours: OurSetResult, mt_summaries: list[MTStatementRow]
) -> ComparisonRow | None:
    mt_positions = max(
        (row.num_mcas or 0 for row in mt_summaries), default=None
    )
    if mt_positions is None:
        return None
    our_confirmed = {
        canonical_lender(f.get("funder"))
        for our_file in ours.files
        for f in our_file.detection.get("known_funders") or []
    }
    return classify(
        set_name, "mca_position_count",
        len(our_confirmed),
        mt_positions,
        different_definition={
            "ours": "count of registry-confirmed lenders with qualifying "
            "withholding debits",
            "moneythumb": "num_mcas position count (counts a position on a "
            "funding deposit alone, no withdrawals required)",
        },
        note="Recorded per FIELD_MAPPING s6 (MCA group HAVE-partial: position "
        "counting is a DERIVE).",
    )


def build_daily_series_row(
    set_name: str,
    prefix: str,
    our_file: OurFileResult,
    mt: MTSet,
    mt_summary: MTStatementRow | None,
    expectation: Expectation | None,
) -> ComparisonRow | None:
    if mt_summary is None:
        return None
    series = mt.daily_balances(mt_summary.account_last4)
    # Restrict to this statement's period: for the package set MT's series
    # spans all months, while each of our ledgers covers one statement.
    period_start = our_file.statement.get("period_start")
    period_end = our_file.statement.get("period_end")
    if period_start and period_end:
        series = {
            day: balance for day, balance in series.items()
            if str(period_start) <= day <= str(period_end)
        }
    if not series:
        return None
    exp = expectation or Expectation(statement="")
    ledger = our_file.daily_ledger()
    if not ledger:
        contradiction = (
            "Our daily ledger is withheld (fail-closed) because the source's "
            "running-balance evidence conflicts (audit: "
            f"{exp.adb_status}: {exp.adb_root_cause}); MoneyThumb surfaced an "
            "banking-day series anyway - recorded as commentary, not as correct."
            if exp.source_contradiction else None
        )
        return classify(
            set_name, f"{prefix}daily_balance_series",
            "withheld (fail-closed daily ledger)",
            f"{len(series)} banking-day balances",
            ours_withheld=True,
            contradiction=contradiction,
        )
    matches = [
        day for day, balance in series.items()
        if day in ledger and values_match(ledger[day], balance)
    ]
    mismatches = {
        day: {"mt": balance, "ours": ledger.get(day)}
        for day, balance in series.items()
        if day not in matches
    }
    evidence = {
        "kind": "validated_daily_ledger",
        "detail": "per-calendar-day ledger independently validated by the ADB "
        "audit (independent_ledger_valid=True)",
        "activity_days_checked": len(series),
        "matching_days": len(matches),
        "mismatches": dict(list(mismatches.items())[:10]),
    }
    ours_desc = f"validated calendar-day ledger ({len(ledger)} days)"
    mt_desc = f"{len(series)} banking-day balances, {len(matches)} match"
    if not mismatches:
        return ComparisonRow(
            set_name=set_name, field=f"{prefix}daily_balance_series",
            outcome=Outcome.BOTH_MATCH_EXPECTED,
            ours=ours_desc, mt=mt_desc, evidence=evidence,
            rationale="Every MT banking-day balance matches our independently "
            "validated per-day ledger. Note MT's series covers banking days "
            "only (FIELD_MAPPING s5: gaps make its ADB unverifiable from its "
            "own output).",
        )
    if expectation is not None and expectation.adb_ledger_valid:
        return ComparisonRow(
            set_name=set_name, field=f"{prefix}daily_balance_series",
            outcome=Outcome.OUR_SYSTEM_CORRECT,
            ours=ours_desc, mt=mt_desc, evidence=evidence,
            rationale=f"{len(mismatches)} MT banking-day balances disagree with "
            "the independently validated ledger.",
        )
    return ComparisonRow(
        set_name=set_name, field=f"{prefix}daily_balance_series",
        outcome=Outcome.UNRESOLVED,
        ours=ours_desc, mt=mt_desc, evidence=evidence,
        rationale="Day-level disagreements with no independent validation of "
        "either series - queued for Ocean ruling.",
        for_ocean=True,
    )


def build_package_rows(
    set_name: str,
    benchmark_set: BenchmarkSet,
    ours: OurSetResult,
    mt: MTSet,
    expectations: dict[str, Expectation],
) -> list[ComparisonRow]:
    """Package-level rows for the multi-statement set."""
    if not ours.package:
        return []
    rows: list[ComparisonRow] = []
    package = ours.package
    documents = package.get("documents") or []
    totals = package.get("totals") or {}

    appinfo = (mt.response or {}).get("appinfo") or {}
    mt_statement_count = parse_money(appinfo.get("totalstatements"))
    if (
        mt_statement_count is not None
        and mt_statement_count != len(benchmark_set.files)
        and int(mt_statement_count) == len(mt.summary_rows)
    ):
        rows.append(
            classify(
                set_name, "package_file_count",
                totals.get("documents"),
                int(mt_statement_count),
                different_definition={
                    "ours": "package documents = uploaded statement PDFs "
                    "(manifest-verified count)",
                    "moneythumb": "totalstatements = account-statements "
                    "(each PDF split per detected account)",
                },
                note="MT's higher count reflects its secondary-account "
                "emission (see the multi_account_emission capability finding).",
            )
        )
    else:
        rows.append(
            classify(
                set_name, "package_file_count",
                totals.get("documents"),
                int(mt_statement_count) if mt_statement_count is not None else None,
                expected=len(benchmark_set.files),
                expected_evidence={"kind": "manifest",
                                   "detail": "benchmark manifest file count (hash-verified)"},
            )
        )

    # Primary-account month rows, ordered by period.
    def _exp_for(our_file: OurFileResult) -> Expectation | None:
        return expectations.get(our_file.relative_path.rsplit("/", 1)[-1])

    # Cross-month chaining (primary account).
    our_chain = all(
        values_match(documents[i].get("ending_balance"), documents[i + 1].get("beginning_balance"))
        for i in range(len(documents) - 1)
    ) if len(documents) > 1 else True
    primary_last4 = None
    for our_file in ours.files:
        primary_last4 = primary_last4 or last4(our_file.statement.get("account_number"))
    mt_primary_rows = [
        row for row in sorted(mt.summary_rows, key=lambda r: r.start_date or "")
        if row.account_last4 is None or primary_last4 is None
        or row.account_last4 == primary_last4
    ]
    if primary_last4 is None and mt.summary_rows:
        # Our Chase payloads carry no account number; take MT's busiest account.
        busiest = max(
            mt.summary_rows, key=lambda r: r.num_debits or 0
        ).account_last4
        mt_primary_rows = [
            row for row in sorted(mt.summary_rows, key=lambda r: r.start_date or "")
            if row.account_last4 == busiest
        ]
    mt_chain = all(
        values_match(mt_primary_rows[i].ending_balance, mt_primary_rows[i + 1].starting_balance)
        for i in range(len(mt_primary_rows) - 1)
    ) if len(mt_primary_rows) > 1 else True
    expected_chain = all(
        values_match(
            (_exp_for(ours.files[i]) or Expectation("")).ending,
            (_exp_for(ours.files[i + 1]) or Expectation("")).opening,
        )
        for i in range(len(ours.files) - 1)
    )
    rows.append(
        classify(
            set_name, "package_balance_chaining",
            our_chain, mt_chain,
            expected=expected_chain,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", "(all package members)",
                "expected_ending vs next expected_opening",
            ),
            note="Adjacent-month ending->starting balance continuity for the "
            "primary account.",
        )
    )

    # Package totals vs the sum of MT primary-account month rows.
    stated_credits = [
        f.statement.get("stated_total_credits") for f in ours.files
    ]
    stated_debits = [
        f.statement.get("stated_total_debits") for f in ours.files
    ]
    summary_all_trusted = all(
        f.reconciliation.get("summary_ok") is True for f in ours.files
    )
    mt_credit_sum = round(
        sum(row.total_credits or 0.0 for row in mt_primary_rows), 2
    ) if mt_primary_rows else None
    mt_debit_sum = round(
        sum(abs(row.total_debits or 0.0) for row in mt_primary_rows), 2
    ) if mt_primary_rows else None
    for name, ours_value, mt_value, stated in (
        ("package_total_credits", totals.get("total_credits"), mt_credit_sum,
         round(sum(v or 0.0 for v in stated_credits), 2) if all(v is not None for v in stated_credits) else None),
        ("package_total_debits", totals.get("total_debits"), mt_debit_sum,
         round(sum(v or 0.0 for v in stated_debits), 2) if all(v is not None for v in stated_debits) else None),
    ):
        rows.append(
            classify(
                set_name, name, ours_value, mt_value,
                source_value=stated if (summary_all_trusted and stated is not None) else UNSET,
                source_evidence=_printed_summary_evidence(
                    "sum of the printed per-statement summary totals "
                    "(primary account, package members)"
                ),
                note="MT has no explicit package totals; its primary-account "
                "month rows are summed for comparison. MT's own aggregate "
                "views also fold in the secondary account (capability finding).",
            )
        )
    expected_cash = None
    first_exp = _exp_for(ours.files[0])
    last_exp = _exp_for(ours.files[-1])
    if first_exp and last_exp and first_exp.opening is not None and last_exp.ending is not None:
        expected_cash = round(last_exp.ending - first_exp.opening, 2)
    mt_cash_sum = round(
        sum(row.net_cashflow or 0.0 for row in mt_primary_rows), 2
    ) if mt_primary_rows else None
    rows.append(
        classify(
            set_name, "package_cash_flow",
            totals.get("cash_flow"), mt_cash_sum,
            expected=expected_cash if expected_cash is not None else UNSET,
            expected_evidence=_audit_evidence(
                "balance-metrics-audit-results.csv", "(package members)",
                "last expected_ending - first expected_opening",
            ),
        )
    )
    return rows
