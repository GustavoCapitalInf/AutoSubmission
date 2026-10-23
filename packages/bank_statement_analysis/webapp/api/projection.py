"""A package as v1 publishes it: one snapshot of its documents, read under the API's fixed reading and projected onto
the contract. Pure: no Flask, no store, no saved setting."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, get_args

from analysis import nsf_days
from analysis import package as package_view
from analysis.display_settings import DEFAULTS as DISPLAY_DEFAULTS
from analysis.package.calendar import iso_day
from analysis.package.model import MemberKey
from analysis.payload_shape import PayloadShapeError, payload_accounts
from analysis.served_view import displayed
from analysis.zelle_view import ZELLE_DEPOSITS_KEY

from ..export_view import masked
from ..jobs import JobSnapshot
from ..worker import NO_PARSER_MATCHED, NO_USABLE_TEXT
from .contract import (
    API_VERSION,
    FAILURE_MESSAGES,
    AnalysedDocument,
    CorporateUse,
    CurrencyRefusal,
    Decision,
    DocumentProgress,
    DuplicateDocument,
    ExcludedAccount,
    Failure,
    FailedDocument,
    FailureCode,
    Funder,
    IncludedAccount,
    IntegrityRisk,
    MonthPositions,
    PackageFigures,
    PotentialLender,
    ProcessingPackage,
    Quality,
    ReadyPackage,
    Review,
)

#: The one reading v1 serves: the owner's display defaults, never the settings saved in the browser
#: (tests/test_api_contract.py pins it).
API_READING: Mapping[str, bool] = MappingProxyType(dict(DISPLAY_DEFAULTS))

_PENDING = frozenset({"queued", "processing"})
_ANALYSIS_REFUSALS: Mapping[str, FailureCode] = MappingProxyType({
    NO_USABLE_TEXT: "unreadable", NO_PARSER_MATCHED: "unsupported_statement",
})
_SURFACE = "webapp/api/projection.py::_reading_applied"
#: The member a value outside each closed vocabulary reads as: its most conservative.
_CONSERVATIVE: Mapping[Any, str] = MappingProxyType({
    Quality: "needs_review", CorporateUse: "manual_review_required", IntegrityRisk: "high",
    Decision: "review_required", CurrencyRefusal: "undetermined_statement_currency",
})


def package_resource(
    package_id: str, created_at: datetime, documents: Sequence[JobSnapshot]
) -> ProcessingPackage | ReadyPackage:
    """The package read from one snapshot of its documents (`JobStore.snapshot`, in submitted order). A document still
    queued or processing makes it a ProcessingPackage and no figure is computed. A document with no analysis under
    API_READING is a FailedDocument, and one whose Zelle reading cannot be applied is left out of the figures. Raises
    pydantic.ValidationError when the package holds a value the contract cannot carry."""
    head = {"api_version": API_VERSION, "package_id": package_id, "created_at": created_at}
    if any(document.status in _PENDING for document in documents):
        return ProcessingPackage(status="processing", documents=[_progress(document) for document in documents],
                                 **head)
    failures = {document.id: code for document in documents if (code := _failure(document)) is not None}
    counted = [document for document in documents if failures.get(document.id) != "reading_unavailable"]
    package = masked(package_view.package_analysis(counted, settings=dict(API_READING)))
    totals = package["totals"]
    complete = not failures and totals.get("completeness") != "partial"
    outdated = package["analysis_rules_outdated"] is True
    decision = _closed(totals.get("decision"), Decision)
    fields = {
        **head,
        "status": "ready",
        "review": Review(required=decision != "approved" or not complete or outdated, decision=decision,
                         analysis_rules_outdated=outdated),
        "complete": complete,
        "figures": None if totals["completed"] == 0 else _figures(package),
        "documents": _terminal_documents(documents, failures, package),
    }
    unsigned = ReadyPackage(revision="0" * 64, **fields)
    canonical = json.dumps(unsigned.model_dump(mode="json", exclude={"revision"}), sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return ReadyPackage(revision=hashlib.sha256(canonical.encode()).hexdigest(), **fields)


def _failure(document: JobSnapshot) -> FailureCode | None:
    """Why a finished document has no analysis under API_READING; None when it has one."""
    if document.status == "interrupted":
        return "interrupted"
    if document.status != "done":
        return "processing_failed"
    if document.analysis is None:
        return _ANALYSIS_REFUSALS.get(document.analysis_error or "", "analysis_failed")
    if not _reading_applied(displayed(document.analysis, settings=dict(API_READING))):
        return "reading_unavailable"
    return None


def _reading_applied(shown: object) -> bool:
    """False when an account of the displayed analysis is served in another Zelle reading than API_READING's
    (`metrics.zelle_deposits.setting_applied`, analysis/zelle_view.py)."""
    try:
        accounts = payload_accounts(shown, surface=_SURFACE)
    except PayloadShapeError:
        return True
    return all(
        ((account.get("metrics") or {}).get(ZELLE_DEPOSITS_KEY) or {}).get("setting_applied") is not False
        for account in accounts
    )


def _progress(document: JobSnapshot) -> DocumentProgress:
    status = document.status if document.status in _PENDING else "finished"
    return DocumentProgress(status=status, **_identity(document))


def _identity(document: JobSnapshot) -> dict:
    return {"document_id": document.id, "filename": document.filename,
            "sha256": (document.content_sha256 or "").lower()}


def _terminal_documents(documents: Sequence[JobSnapshot], failures: Mapping[str, FailureCode],
                        package: Mapping) -> list[FailedDocument | DuplicateDocument | AnalysedDocument]:
    """Each document in submitted order: failed, else a repeat the package left out, else analysed with its accounts
    (its member rows and its exclusions, a statement-wide exclusion first)."""
    rows = [row for row in package["documents"] if isinstance(row, dict)]
    repeats = {row["id"]: row for row in rows if row.get("is_duplicate") is True}
    published = []
    for document in documents:
        identity = _identity(document)
        code = failures.get(document.id)
        if code is not None:
            failure = Failure(code=code, message=FAILURE_MESSAGES[code])
            published.append(FailedDocument(status="failed", failure=failure, **identity))
            continue
        repeat = repeats.get(document.id)
        if repeat is not None:
            published.append(DuplicateDocument(status="duplicate", duplicate_of=repeat["duplicate_of"],
                                               reason=str(repeat.get("duplicate_reason")), **identity))
            continue
        accounts = [
            _included(row) for row in rows
            if row.get("is_duplicate") is not True
            and row["id"] == MemberKey(document.id, row.get("account_index")).id
        ] + [
            ExcludedAccount(status="excluded", account_index=entry.get("account_index"), reason=str(entry["reason"]))
            for entry in package.get("excluded_accounts") or [] if entry.get("job_id") == document.id
        ]
        accounts.sort(key=lambda account: account.account_index or 0)
        published.append(AnalysedDocument(status="analysed", accounts=accounts, **identity))
    return published


def _included(row: Mapping) -> IncludedAccount:
    adb = cents(row.get("average_daily_balance")) if row.get("adb_validated") is True else None
    return IncludedAccount(
        status="included",
        account_index=row.get("account_index"),
        bank=_text(row.get("bank")),
        account_masked=_text(row.get("account")),
        currency=_text(row.get("currency")),
        period_start=iso_day(row.get("period_start")),
        period_end=iso_day(row.get("period_end")),
        opening_balance_cents=cents(row.get("beginning_balance")),
        closing_balance_cents=cents(row.get("ending_balance")),
        deposits_cents=cents(row.get("credits")),
        deposit_count=_count(row.get("deposit_count")),
        withdrawals_cents=cents(row.get("debits")),
        true_revenue_cents=cents(row.get("true_revenue_total")),
        true_revenue_count=_count(row.get("true_revenue_count")),
        held_for_review_cents=cents(row.get("excluded_pending_review_total")),
        non_revenue_cents=cents(row.get("non_revenue_total")),
        average_daily_balance_cents=adb,
        average_daily_balance_days=_count(row.get("adb_calendar_days")) if adb is not None else None,
        negative_days=_negative_days(row.get("nsf_count"), row.get("nsf_source")),
        lender_payments_cents=cents(row.get("lender_debits")),
        lender_payment_count=row["lender_debit_count"],
        returned_funder_payments_cents=cents(row.get("returned_funder_payment_total")),
        active_positions=_count(row.get("active_positions")),
        possible_positions=_count(row.get("possible_positions")),
        withholding_rate_bps=basis_points(row.get("withholding_rate")),
        quality=_closed(row.get("quality"), Quality),
        corporate_use=_closed(row.get("corporate_use"), CorporateUse),
        integrity_risk=_closed(row.get("integrity_risk"), IntegrityRisk),
        reconciles=row.get("reconciles") if isinstance(row.get("reconciles"), bool) else None,
        revenue_review_required=row.get("revenue_review_required") is True,
    )


def _figures(package: Mapping) -> PackageFigures:
    totals = package["totals"]
    refusal = totals.get("currency_refusal_reason")
    return PackageFigures(
        currency=_text(totals.get("currency")),
        currency_refusal=None if refusal is None else _closed(refusal, CurrencyRefusal),
        months=totals["months"],
        statement_periods=totals.get("statement_periods", totals["months"]),
        deposits_cents=cents(totals.get("total_credits")),
        monthly_deposits_cents=cents(totals.get("avg_monthly_credits")),
        withdrawals_cents=cents(totals.get("total_debits")),
        monthly_withdrawals_cents=cents(totals.get("avg_monthly_debits")),
        true_revenue_cents=cents(totals.get("true_revenue_total")),
        true_revenue_count=_count(totals.get("true_revenue_count")),
        monthly_true_revenue_cents=cents(totals.get("avg_monthly_true_revenue")),
        held_for_review_cents=cents(totals.get("excluded_pending_review_total")),
        non_revenue_cents=cents(totals.get("non_revenue_total")),
        average_daily_balance_cents=cents(totals.get("average_daily_balance")),
        negative_days=_negative_days(totals.get("nsf_count"), totals.get("nsf_source")),
        lender_payments_cents=cents(totals.get("lender_debits")),
        lender_payment_count=totals["lender_debit_count"],
        monthly_lender_payments_cents=cents(totals.get("monthly_lender_debits")),
        returned_funder_payments_cents=cents(totals.get("returned_funder_payment_total")),
        withholding_rate_bps=basis_points(totals.get("package_withholding_rate")),
        funders=[
            Funder(name=str(item["funder"]), account_periods=item["documents"],
                   payment_count=_count(item.get("debit_count")), paid_cents=cents(item.get("total_debited")),
                   returned_payment_count=item["returned_payment_count"],
                   returned_cents=cents(item.get("returned_payment_total")))
            for item in package["funders"]
        ],
        potential_lenders=[
            PotentialLender(name=str(item["funder"]), account_periods=item["documents"],
                            payment_count=item["debit_count"], paid_cents=cents(item.get("total_debited")))
            for item in package["potential_lenders"]
        ],
        active_positions_by_month=[
            MonthPositions(month=item["month"], active_positions=_count(item.get("active_positions")),
                           possible_positions=_count(item.get("possible_positions")))
            for item in package["active_positions_by_month"]
        ],
    )


def cents(value: object) -> int | None:
    """Integer cents of a money figure, rounded half up; None for None, a bool, a non-number or a non-finite number."""
    hundredths = _scaled(value)
    return None if hundredths is None else int(hundredths)


def basis_points(percent: object) -> int | None:
    """Integer basis points of a percentage, rounded half up; None as `cents` gives None, and for a negative rate."""
    points = _scaled(percent)
    return None if points is None or points < 0 else int(points)


def _scaled(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        exact = Decimal(str(value))
    except InvalidOperation:
        return None
    if not exact.is_finite():
        return None
    return (exact * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _count(value: object) -> int | None:
    """A count: a non-negative int, else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _negative_days(nsf_count: object, source: object) -> int | None:
    """The negative-day count on v1's basis only (printed days); a carried, legacy or unavailable basis gives None."""
    return _count(nsf_count) if source == nsf_days.PRINTED else None


def _closed(value: object, vocabulary: Any) -> str:
    """`value` when it is a member of the closed `vocabulary` (a Literal of the contract), else its most conservative
    member."""
    return value if value in get_args(vocabulary) else _CONSERVATIVE[vocabulary]


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None
