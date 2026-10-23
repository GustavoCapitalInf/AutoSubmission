from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from types import MappingProxyType
from typing import Annotated, Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

#: Sent in every body; a bump needs a SCHEMA_FINGERPRINTS pin (test_the_schema_is_pinned_to_its_api_version).
API_VERSION = "1.0"

IntakeRefusalCode = Literal[
    "no_statements", "too_many_statements", "invalid_filename", "statement_too_large", "not_a_pdf", "pdf_encrypted",
    "pdf_unreadable", "too_many_pages", "storage_full", "not_stored",
]
ErrorCode = Literal[
    IntakeRefusalCode, "invalid_package_id", "invalid_request", "request_too_large", "package_conflict",
    "package_not_found", "route_not_found", "method_not_allowed", "unauthorized", "api_disabled", "storage_degraded",
    "internal_error",
]
FailureCode = Literal[
    "unreadable", "unsupported_statement", "analysis_failed", "processing_failed", "interrupted", "reading_unavailable",
]
Quality = Literal["transaction_level", "summary_aggregate", "needs_review"]
CorporateUse = Literal["approved", "summary_only", "manual_review_required"]
IntegrityRisk = Literal["clear", "review", "high"]
Decision = Literal["approved", "limited_review", "review_required"]
CurrencyRefusal = Literal["multiple_currencies", "undetermined_statement_currency"]


class ErrorEntry(NamedTuple):
    status: int
    message: str


ERRORS: Mapping[str, ErrorEntry] = MappingProxyType({
    "no_statements": ErrorEntry(400, "the request carries no statement; send 1 to 25 PDFs as multipart `files`"),
    "too_many_statements": ErrorEntry(400, "the request carries more than 25 statements"),
    "invalid_filename": ErrorEntry(400, "a filename carries a line break or `-->`"),
    "statement_too_large": ErrorEntry(400, "a statement is larger than 100 MB"),
    "not_a_pdf": ErrorEntry(400, "a file is not a PDF"),
    "pdf_encrypted": ErrorEntry(400, "a PDF is password-protected; send a decrypted copy"),
    "pdf_unreadable": ErrorEntry(400, "a PDF could not be read"),
    "too_many_pages": ErrorEntry(400, "a PDF has more than 500 pages"),
    "invalid_package_id": ErrorEntry(400, "the package id must be a UUID in lowercase canonical form"),
    "invalid_request": ErrorEntry(400, "the request could not be read"),
    "unauthorized": ErrorEntry(401, "a valid bearer token is required"),
    "package_not_found": ErrorEntry(404, "no package has this id"),
    "route_not_found": ErrorEntry(404, "no API route has this path"),
    "method_not_allowed": ErrorEntry(405, "this route does not accept this method"),
    "package_conflict": ErrorEntry(409, "this package id already names other statements; use a new package id"),
    "request_too_large": ErrorEntry(413, "the request is larger than 100 MB"),
    "internal_error": ErrorEntry(500, "the server could not answer this request"),
    "not_stored": ErrorEntry(503, "the statements could not be stored; none was accepted. Send them again"),
    "api_disabled": ErrorEntry(503, "the API is not configured on this server"),
    "storage_degraded": ErrorEntry(
        503, "the server's storage failed when it started; this request cannot be served until it restarts"),
    "storage_full": ErrorEntry(507, "the server's storage is nearly full; no statement was accepted"),
})

FAILURE_MESSAGES: Mapping[str, str] = MappingProxyType({
    "unreadable": "no usable text could be read from this PDF, natively or by OCR",
    "unsupported_statement": "no parser reads this statement's layout",
    "analysis_failed": "the statement was read but its analysis failed",
    "processing_failed": "processing this statement failed",
    "interrupted": "the server restarted while this statement was processed; submit it under a new package id",
    "reading_unavailable": "the stored analysis cannot be read with Zelle deposits counted as True revenue",
})


def _field(description: str, source: str | None = None, **constraints: Any) -> Any:
    return Field(description=description, json_schema_extra={"x-source": source} if source else None, **constraints)


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


Cents = int
Count = Annotated[int, Field(ge=0)]
Index = Annotated[int, Field(ge=1)]
BasisPoints = Annotated[int, Field(ge=0)]
Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PackageId = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class ApiError(_Wire):
    code: ErrorCode = _field("What was refused; the error catalog gives each code's HTTP status.")
    message: str = _field("The code's one fixed message; never statement content or exception text.")
    filename: str | None = _field("The refused file's name, when one file was refused.")


class ErrorResponse(_Wire):
    error: ApiError = _field("The refusal.")


class _Document(_Wire):
    document_id: str = _field("The statement's id within the package.", "job.id")
    filename: str = _field("The file's name as submitted.", "job.filename")
    sha256: Sha256 = _field("Lowercase hex SHA-256 of the PDF bytes.", "job.content_sha256")


class DocumentProgress(_Document):
    status: Literal["queued", "processing", "finished"] = _field(
        "`finished`: analysed, failed or interrupted; the ready package says which.", "job.status")


class IncludedAccount(_Wire):
    """One account whose figures are in the package's. Every source is a key of the package's member row,
    `documents[]`."""

    status: Literal["included"] = _field("An account whose figures are in the package's figures.")
    account_index: Index | None = _field(
        "1-based place of the account in a statement that prints several; null for a statement of one account.",
        "account_index")
    bank: str | None = _field("The bank, as printed.", "bank")
    account_masked: str | None = _field("`****` and the last four digits of the account number.", "account, masked")
    currency: str | None = _field(
        "ISO 4217 code of this account's money figures; null when the statement names none.", "currency")
    period_start: date | None = _field("First day of the printed statement period.", "period_start")
    period_end: date | None = _field("Last day of the printed statement period.", "period_end")
    opening_balance_cents: Cents | None = _field("Opening balance.", "beginning_balance")
    closing_balance_cents: Cents | None = _field("Closing balance; null unless the statement reconciles.",
                                                 "ending_balance")
    deposits_cents: Cents | None = _field("Credits, less transfers between the statement's own accounts.", "credits")
    deposit_count: Count | None = _field(
        "Number of the credits in `deposits_cents`; null when no count pairs with that total.", "deposit_count")
    withdrawals_cents: Cents | None = _field("Debits, less transfers between the statement's own accounts.", "debits")
    true_revenue_cents: Cents | None = _field(
        "True revenue: verified plus counted credits; null when not established.", "true_revenue_total")
    true_revenue_count: Count | None = _field("Number of the credits in True revenue.", "true_revenue_count")
    held_for_review_cents: Cents | None = _field(
        "Credits held for an analyst's review; null when revenue is not established.", "excluded_pending_review_total")
    non_revenue_cents: Cents | None = _field("Credits that are not revenue.", "non_revenue_total")
    average_daily_balance_cents: Cents | None = _field(
        "Average daily balance over every calendar day of the period; null unless the daily ledger is validated.",
        "average_daily_balance")
    average_daily_balance_days: Count | None = _field(
        "Calendar days the average daily balance covers; null with it.", "adb_calendar_days, when adb_validated")
    negative_days: Count | None = _field(
        "Printed days that end below zero; null when the count is on another basis or not computable.",
        "nsf_count, when nsf_source is negative_printed_days")
    lender_payments_cents: Cents | None = _field("Payments to confirmed lenders.", "lender_debits")
    lender_payment_count: Count = _field("Number of the payments in `lender_payments_cents`.", "lender_debit_count")
    returned_funder_payments_cents: Cents | None = _field(
        "Funder payments returned unpaid.", "returned_funder_payment_total")
    active_positions: Count | None = _field(
        "Confirmed lenders' positions active in the period; null when not read.", "active_positions")
    possible_positions: Count | None = _field(
        "Potential lenders' positions active in the period; null when not read.", "possible_positions")
    withholding_rate_bps: BasisPoints | None = _field(
        "Lender payments (paid and returned) over the withholding basis; null when the basis publishes no rate.",
        "withholding_rate")
    quality: Quality = _field("How the statement's figures were established.", "quality")
    corporate_use: CorporateUse = _field("Whether the statement's figures can be used as they are.", "corporate_use")
    integrity_risk: IntegrityRisk = _field("Document integrity finding.", "integrity_risk")
    reconciles: bool | None = _field("Whether the account's own figures reconcile to the bank's.", "reconciles")
    revenue_review_required: bool = _field(
        "Whether the account's revenue needs an analyst's review.", "revenue_review_required")


class ExcludedAccount(_Wire):
    status: Literal["excluded"] = _field("An account left out of the package's figures.")
    account_index: Index | None = _field(
        "1-based place of the account in its statement; null when the whole statement is left out because its main "
        "account was not verified or printed no activity.", "excluded_accounts[].account_index")
    reason: str = _field(
        "Why, in an open vocabulary: main_account_unverified, main_account_idle, document_transfer_pairing_ambiguous, "
        "document_omission_unratified, duplicate_statement, superseded_long_printout, superseded_interim, or the "
        "account's own outcome reason.", "excluded_accounts[].reason")


Account = Annotated[IncludedAccount | ExcludedAccount, Field(discriminator="status")]


class Failure(_Wire):
    code: FailureCode = _field("Why the statement has no analysis under the v1 reading.")
    message: str = _field("The code's one fixed message.")


class AnalysedDocument(_Document):
    status: Literal["analysed"] = _field("The statement was analysed; its accounts say which entered the figures.")
    accounts: list[Account] = _field("Each account, in printed order (a statement-wide exclusion first).",
                                     "documents[], excluded_accounts[]", min_length=1)


class FailedDocument(_Document):
    status: Literal["failed"] = _field("The statement has no analysis under the v1 reading; nothing of it is counted.")
    failure: Failure = _field("Why.", "job.status, job.analysis_error")


class DuplicateDocument(_Document):
    status: Literal["duplicate"] = _field("The statement repeats another of the package; nothing of it is counted.")
    duplicate_of: str = _field("`document_id` of the statement kept in its place.", "documents[].duplicate_of")
    reason: str = _field("Why, in an open vocabulary: same_content, same_statement, superseded_long_printout, "
                         "superseded_interim.", "documents[].duplicate_reason")


TerminalDocument = Annotated[AnalysedDocument | FailedDocument | DuplicateDocument, Field(discriminator="status")]


class Review(_Wire):
    required: bool = _field("True unless `decision` is approved, the package is complete and no statement was "
                            "analysed under older classification rules.")
    decision: Decision = _field("The analysis' publication status; not a funder's credit decision.", "totals.decision")
    analysis_rules_outdated: bool = _field("A statement was analysed under older classification rules.",
                                           "analysis_rules_outdated")


class Funder(_Wire):
    name: str = _field("The confirmed funder.", "funders[].funder")
    account_periods: Count = _field("Account periods in which the funder was paid.", "funders[].documents")
    payment_count: Count | None = _field("Payments to the funder; null when no match counted them.",
                                         "funders[].debit_count")
    paid_cents: Cents | None = _field("Paid to the funder; null under a currency refusal.", "funders[].total_debited")
    returned_payment_count: Count = _field("Payments to the funder returned unpaid.",
                                           "funders[].returned_payment_count")
    returned_cents: Cents | None = _field("Returned unpaid; null under a currency refusal.",
                                          "funders[].returned_payment_total")


class PotentialLender(_Wire):
    name: str = _field("The potential lender, which an analyst confirms or dismisses.", "potential_lenders[].funder")
    account_periods: Count = _field("Account periods in which it was paid.", "potential_lenders[].documents")
    payment_count: Count = _field("Payments to it.", "potential_lenders[].debit_count")
    paid_cents: Cents | None = _field("Paid to it; null under a currency refusal.", "potential_lenders[].total_debited")


class MonthPositions(_Wire):
    month: Month = _field("A calendar month the statements stand for.", "active_positions_by_month[].month")
    active_positions: Count | None = _field("Confirmed lenders' positions active that month; null when not read.",
                                            "active_positions_by_month[].active_positions")
    possible_positions: Count | None = _field("Potential lenders' positions active that month; null when not read.",
                                              "active_positions_by_month[].possible_positions")


class PackageFigures(_Wire):
    currency: str | None = _field("ISO 4217 code of every money figure here; null when refused.", "totals.currency")
    currency_refusal: CurrencyRefusal | None = _field(
        "Why the package's money figures are null: its statements are in several currencies, or one names none.",
        "totals.currency_refusal_reason")
    months: Count = _field("Calendar months the counted statements stand for; every monthly figure divides by it.",
                           "totals.months")
    statement_periods: Count = _field("Statement periods counted (one per statement and printed cycle).",
                                      "totals.statement_periods, else totals.months")
    deposits_cents: Cents | None = _field("Gross credits of the included accounts.", "totals.total_credits")
    monthly_deposits_cents: Cents | None = _field("Gross credits per month.", "totals.avg_monthly_credits")
    withdrawals_cents: Cents | None = _field("Debits of the included accounts.", "totals.total_debits")
    monthly_withdrawals_cents: Cents | None = _field("Debits per month.", "totals.avg_monthly_debits")
    true_revenue_cents: Cents | None = _field("True revenue; null unless every included account's is established.",
                                              "totals.true_revenue_total")
    true_revenue_count: Count | None = _field("Number of the credits in True revenue.", "totals.true_revenue_count")
    monthly_true_revenue_cents: Cents | None = _field("True revenue per month.", "totals.avg_monthly_true_revenue")
    held_for_review_cents: Cents | None = _field("Credits held for an analyst's review.",
                                                 "totals.excluded_pending_review_total")
    non_revenue_cents: Cents | None = _field("Credits that are not revenue.", "totals.non_revenue_total")
    average_daily_balance_cents: Cents | None = _field(
        "Days-weighted average daily balance of the validated accounts; null when none is validated or two "
        "accounts of one statement would be averaged.", "totals.average_daily_balance")
    negative_days: Count | None = _field(
        "Printed days ending below zero, summed over the included accounts; null when any count is on another basis.",
        "totals.nsf_count, when totals.nsf_source is negative_printed_days")
    lender_payments_cents: Cents | None = _field("Payments to confirmed lenders.", "totals.lender_debits")
    lender_payment_count: Count = _field("Number of the payments in `lender_payments_cents`.",
                                         "totals.lender_debit_count")
    monthly_lender_payments_cents: Cents | None = _field("Payments to confirmed lenders per month.",
                                                         "totals.monthly_lender_debits")
    returned_funder_payments_cents: Cents | None = _field("Funder payments returned unpaid.",
                                                          "totals.returned_funder_payment_total")
    withholding_rate_bps: BasisPoints | None = _field(
        "Lender payments (paid and returned) over the withholding basis; null when the basis publishes no rate.",
        "totals.package_withholding_rate")
    funders: list[Funder] = _field("Confirmed funders, largest paid first (by count under a currency refusal).",
                                   "funders")
    potential_lenders: list[PotentialLender] = _field("Potential lenders, by name.", "potential_lenders")
    active_positions_by_month: list[MonthPositions] = _field("Positions per calendar month.",
                                                             "active_positions_by_month")


class _PackageHead(_Wire):
    api_version: str = _field("This contract's version: `1.0`.")
    package_id: PackageId = _field("The id the caller chose for the package.")
    created_at: datetime = _field("When the package was created (UTC).", "packages.created_at")


class ProcessingPackage(_PackageHead):
    status: Literal["processing"] = _field("A statement is still queued or processing; no figure is computed yet.")
    documents: list[DocumentProgress] = _field("Each statement, in submitted order.")


class ReadyPackage(_PackageHead):
    status: Literal["ready"] = _field("Every statement is analysed, failed or a duplicate.")
    revision: Sha256 = _field("Lowercase hex SHA-256 of this body without `revision`; it changes whenever another "
                              "field does, such as after an analyst's review in the dashboard.")
    review: Review = _field("Whether a person must look before the figures are used.")
    complete: bool = _field("Every statement analysed, no account left out (repeats aside) and no section omitted.",
                            "totals.completeness")
    figures: PackageFigures | None = _field("The package's figures; null when no account entered them.",
                                            "totals, when totals.completed is not 0")
    documents: list[TerminalDocument] = _field("Each statement, in submitted order.")


Package = Annotated[ProcessingPackage | ReadyPackage, Field(discriminator="status")]
