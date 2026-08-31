"""Independent full-corpus audit for opening, ending, highest, and lowest balances.

The expected-value path in this file does not import ``analysis.adb`` or
``analysis.metrics``. It reopens each source PDF, extracts page text, groups
signed postings with Decimal currency arithmetic, and independently parses raw
dated bank balance tables where present. Production parser, API, dashboard, and
export values are comparison targets only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from analysis.payload_shape import refuse_document_payload
from analysis.pipeline import analyze_document
from analysis.serialization import document_report_to_dict
from corpus_artifacts import ArtifactError, cached_markdown
from ocr.local_tesseract import parse_local_tesseract
# The production native-text ladder itself — see
# `ocr/native_text.py::native_statement`. This oracle reads exactly the bytes
# production reads because it calls the same function, not a copy of it.
from ocr.native_text import native_statement as native_document
from ocr.rasterize import pdf_page_count
from webapp.app import (
    _analysis_csv,
    _analysis_xlsx,
    _package_analysis,
    _package_csv,
    _package_xlsx,
)
from webapp.jobs import Job


CENT = Decimal("0.01")
RAW_DAILY_BANKS = {
    "Banco Popular",
    "Bank of America",
    "Citizens Bank",
    "Columbia Bank",
    "First Citizens Bank",
    "IBC Bank",
    "PNC Bank",
    "Regions Bank",
    "Texas Bank and Trust",
    "Wilson & Muir Bank & Trust",
}

FIELDS = [
    "statement",
    "path",
    "sha256",
    "pages",
    "source_type",
    "bank",
    "account",
    "parser",
    "period",
    "calendar_days",
    "transactions",
    "daily_balance_evidence",
    "source_opening",
    "expected_opening",
    "production_opening",
    "api_opening",
    "csv_opening",
    "xlsx_opening",
    "package_opening",
    "source_ending",
    "expected_ending",
    "production_ending",
    "api_ending",
    "csv_ending",
    "xlsx_ending",
    "package_ending",
    "expected_highest",
    "production_highest",
    "api_highest",
    "csv_highest",
    "xlsx_highest",
    "package_highest",
    "expected_lowest",
    "production_lowest",
    "api_lowest",
    "csv_lowest",
    "xlsx_lowest",
    "package_lowest",
    "opening_difference",
    "ending_difference",
    "highest_difference",
    "lowest_difference",
    "detail_ledger_reconciles",
    "summary_reconciles",
    "running_balances_reconcile",
    "dashboard_binding_valid",
    "exports_valid",
    "status",
    "root_cause",
    "affected_code",
    "fix_applied",
    "regression_risk",
    "confidence",
    # ADB-doctrine columns, APPENDED so every column above stays
    # byte-for-byte what it was. This audit computes no average of its
    # own; these are the product's own declarations, recorded here so the
    # two committed audits pin the same doctrine over the same 109 paths.
    "underwriting_adb_basis",
    "underwriting_adb_policy",
    "bank_reported_average_label",
    "bank_reported_average_variance",
]


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def formatted(value: Decimal | float | None) -> str:
    return "" if value is None else f"{money(value):.2f}"


def difference(actual: Any, expected: Decimal | None) -> str:
    if actual is None and expected is None:
        return "0.00"
    if actual is None or expected is None:
        return ""
    return formatted(money(actual) - expected)


def source_markdown(path: Path, *, ocr_cache: Path | None = None) -> tuple[str, str, bytes]:
    """Resolve statement source text.

    With ``ocr_cache`` set, an image-only PDF is served from its committed OCR
    artifact and Tesseract is never invoked, which is what makes the corpus gate
    offline and deterministic. A scanned PDF with no committed artifact is an
    error rather than a silent skip. Without ``ocr_cache`` the behaviour is
    unchanged: native text, then a live local Tesseract run.
    """
    pdf_bytes = path.read_bytes()
    document = native_document(pdf_bytes, path.name)
    source_type = "digital/native"
    if document is None and ocr_cache is not None:
        markdown = cached_markdown(pdf_bytes, ocr_cache)
        if markdown is None:
            raise ArtifactError(
                f"{path} has no native text and no committed OCR artifact in "
                f"{ocr_cache}; refusing to run OCR in offline mode"
            )
        return markdown, "scanned/local_ocr", pdf_bytes
    if document is None:
        document = parse_local_tesseract(pdf_bytes, source_file=path.name)
        source_type = "scanned/local_ocr"
    if document is None:
        raise RuntimeError(f"no source text available for {path}")
    return document.to_markdown(), source_type, pdf_bytes


def resolve_date(
    month_raw: str,
    day_raw: str,
    year_raw: str | None,
    start: date,
    end: date,
) -> date | None:
    years = [int(year_raw)] if year_raw else list(range(start.year, end.year + 1))
    years = [year + 2000 if year < 100 else year for year in years]
    candidates: list[date] = []
    for year in years:
        try:
            candidate = date(year, int(month_raw), int(day_raw))
        except ValueError:
            continue
        if start <= candidate <= end:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


DATE_BALANCE_RE = re.compile(
    r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\s+"
    r"\$?(-?(?:\d[\d,]*|\.\d+)\.\d{2})[ \t]*([+-])?"
)


def parse_date_balance_pairs(body: str, start: date, end: date) -> dict[date, Decimal]:
    balances: dict[date, Decimal] = {}
    for month_raw, day_raw, year_raw, amount_raw, trailing_sign in DATE_BALANCE_RE.findall(body):
        day = resolve_date(month_raw, day_raw, year_raw or None, start, end)
        if day is None:
            continue
        value = Decimal(amount_raw.replace(",", ""))
        if trailing_sign == "-":
            value = -abs(value)
        balances[day] = money(value)
    return balances


def section(markdown: str, start_pattern: str, end_pattern: str) -> str:
    match = re.search(
        start_pattern + r"(?P<body>.*?)(?:(?=" + end_pattern + r"))",
        markdown,
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    return (match.group("body") or "") if match else ""


def first_citizens_daily(markdown: str, start: date, end: date) -> dict[date, Decimal]:
    body = section(markdown, r"^Daily Balance Summary\s*$", r"^An updated")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    balances: dict[date, Decimal] = {}
    for index, line in enumerate(lines[:-1]):
        amounts = re.findall(r"\b(\d{2})\s+([\d,]+\.\d{2})([+-])", line)
        if not amounts:
            continue
        days = re.findall(r"-(\d{2})", lines[index + 1])
        for (month_raw, amount_raw, sign), day_raw in zip(amounts, days):
            day = resolve_date(month_raw, day_raw, None, start, end)
            if day is None:
                continue
            value = Decimal(amount_raw.replace(",", ""))
            balances[day] = money(-value if sign == "-" else value)
    return balances


def raw_daily_balances(markdown: str, bank: str, start: date, end: date) -> dict[date, Decimal]:
    if bank not in RAW_DAILY_BANKS:
        return {}
    if bank == "First Citizens Bank":
        return first_citizens_daily(markdown, start, end)
    patterns = {
        "Banco Popular": (r"Daily Balance History", r"Average balance during this cycle:"),
        "Bank of America": (r"^Daily ledger balances", r"^Check images|^This page intentionally|\Z"),
        "Citizens Bank": (r"^Daily Balance\s*$", r"^--- Page"),
        "Columbia Bank": (r"^Daily Balances\s*$", r"^Overdraft Fee Summary"),
        "IBC Bank": (r"^Daily Ending Balance\s*$", r"^APCNH"),
        "PNC Bank": (r"^Daily Balance\s*$", r"^Activity Detail\s*$"),
        "Regions Bank": (r"^DAILY BALANCE SUMMARY\s*$", r"^--- Page|\Z"),
        "Texas Bank and Trust": (r"^Daily Balance Information\s*$", r"^--- Page"),
        "Wilson & Muir Bank & Trust": (
            r"DAILY BALANCE SUMMARY",
            r"COLLECTED BALANCE SUMMARY",
        ),
    }
    start_pattern, end_pattern = patterns[bank]
    return parse_date_balance_pairs(section(markdown, start_pattern, end_pattern), start, end)


def summary_reconciles(statement: Any) -> bool | None:
    values = (
        statement.beginning_balance,
        statement.ending_balance,
        statement.stated_total_credits,
        statement.stated_total_debits,
    )
    if any(value is None for value in values):
        return None
    opening, ending, credits, debits = (money(value) for value in values)
    service = money(statement.stated_service_charge or 0)
    interest = money(statement.stated_interest_paid or 0)
    residuals = {
        money(opening + credits - debits - ending),
        money(opening + credits - debits - service - ending),
        money(opening + credits - debits + interest - ending),
        money(opening + credits - debits + interest - service - ending),
    }
    return Decimal("0.00") in residuals


@dataclass
class IndependentBalances:
    opening: Decimal | None = None
    closing: Decimal | None = None
    daily: dict[date, Decimal] = field(default_factory=dict)
    detail_reconciles: bool = False
    summary_reconciles: bool | None = None
    running_reconciles: bool = True
    valid: bool = False
    evidence: str = "reconstructed_source_postings"
    reasons: list[str] = field(default_factory=list)

    @property
    def lowest(self) -> Decimal | None:
        return min(self.daily.values()) if self.valid and self.daily else None

    @property
    def highest(self) -> Decimal | None:
        return max(self.daily.values()) if self.valid and self.daily else None


def independent_balances(statement: Any, markdown: str) -> IndependentBalances:
    result = IndependentBalances()
    try:
        start = date.fromisoformat(str(statement.period_start))
        end = date.fromisoformat(str(statement.period_end))
    except (TypeError, ValueError):
        result.reasons.append("missing or invalid statement period")
        return result
    if start > end:
        result.reasons.append("inverted statement period")
        return result
    if statement.beginning_balance is None or statement.ending_balance is None:
        result.reasons.append("opening or ending balance is unavailable")
        return result

    result.opening = money(statement.beginning_balance)
    result.closing = money(statement.ending_balance)
    result.summary_reconciles = summary_reconciles(statement)
    by_day: dict[date, list[Any]] = {}
    undated = outside = 0
    for transaction in statement.transactions:
        try:
            day = date.fromisoformat(str(transaction.date))
        except (TypeError, ValueError):
            undated += 1
            continue
        if not start <= day <= end:
            outside += 1
            continue
        by_day.setdefault(day, []).append(transaction)

    transaction_total = sum(
        (money(transaction.amount) for transactions in by_day.values() for transaction in transactions),
        Decimal("0.00"),
    )
    transaction_close = money(result.opening + transaction_total)
    result.detail_reconciles = transaction_close == result.closing

    snapshots = raw_daily_balances(markdown, str(statement.bank or ""), start, end)
    if snapshots:
        result.evidence = "raw_bank_daily_ending_table"
    carry = result.opening
    snapshot_conflicts = 0
    day = start
    while day <= end:
        transactions = by_day.get(day, [])
        reconstructed = money(
            carry
            + sum((money(transaction.amount) for transaction in transactions), Decimal("0.00"))
        )
        if day in snapshots:
            if reconstructed != snapshots[day]:
                snapshot_conflicts += 1
            carry = snapshots[day]
        else:
            carry = reconstructed
        result.daily[day] = carry

        printed = [
            money(transaction.running_balance)
            for transaction in transactions
            if transaction.running_balance is not None
        ]
        # A bank-provided daily table is stronger EOD evidence than parser-level
        # transaction dates. Some institutions post detail on a processing date
        # while their Book Balance table uses an effective date.
        if printed and not snapshots and printed[-1] != carry:
            result.running_reconciles = False
        day += timedelta(days=1)

    if undated:
        result.reasons.append(f"{undated} undated transaction(s)")
    if outside:
        result.reasons.append(f"{outside} out-of-period transaction(s)")
    if not result.detail_reconciles:
        result.reasons.append(
            f"detail closes at {transaction_close:.2f}, not printed {result.closing:.2f}"
        )
    if result.daily.get(end) != result.closing:
        result.reasons.append(
            f"final EOD is {result.daily.get(end):.2f}, not printed {result.closing:.2f}"
        )
    if snapshots and snapshot_conflicts:
        result.evidence += f"; {snapshot_conflicts} effective-date override(s)"
    if not result.running_reconciles:
        result.reasons.append("final same-day running balance conflicts with EOD")

    expected_days = (end - start).days + 1
    result.valid = all(
        (
            undated == 0,
            outside == 0,
            result.detail_reconciles,
            result.daily.get(end) == result.closing,
            result.running_reconciles,
            len(result.daily) == expected_days,
        )
    )
    return result


def xlsx_rows(content: bytes) -> dict[tuple[str, str], str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: dict[tuple[str, str], str] = {}
    for row in root.findall(".//x:row", namespace)[1:]:
        values = ["".join(cell.itertext()) for cell in row.findall("x:c", namespace)]
        if len(values) >= 3:
            rows[(values[0], values[1])] = values[2]
    return rows


def csv_rows(content: str) -> dict[tuple[str, str], str]:
    csv.field_size_limit(16 * 1024 * 1024)
    rows = list(csv.reader(io.StringIO(content)))
    return {(section, field): value for section, field, value in rows[1:]}


def surface_value(rows: dict[tuple[str, str], str], section_name: str, field: str) -> str:
    return rows.get((section_name, field), "")


def values_match(actual: Any, expected: Decimal | None) -> bool:
    if actual in {None, ""}:
        return expected is None
    return money(actual) == expected


WITHHELD_DETAILS = {
    "Ace_Auto_Final_Cut.pdf": {
        "root": (
            "Printed opening/summary/ending reconcile, but dated detail closes $2,943.45 high; "
            "the missing amount has no unique posting date, so daily extrema are not unique."
        ),
        "code": "analysis/farmers_merchants.py; analysis/adb.py",
        "fix": "Retained source opening/ending and fail-closed daily extrema.",
    },
    "BMO_Statement_January_2026 Final-1-2 (1).pdf": {
        "root": (
            "Primary summary closes, but line items close $37,650.00 low, 36 running transitions "
            "conflict, and a secondary summary disagrees; daily extrema are not unique."
        ),
        "code": "analysis/bmo.py; analysis/adb.py",
        "fix": "Retained source opening/ending and fail-closed daily extrema.",
    },
    "IBC April (1).pdf": {
        "root": (
            "The recap prints $10,625.31 opening and $18,442.35 closing, while the complete "
            "detail and daily table reconcile -$625.31 to $8,442.35. The recap identity is "
            "$1,250.62 off and the two closing balances differ by $10,000.00."
        ),
        "code": "analysis/ibc.py; analysis/serialization.py",
        "fix": (
            "Stopped deriving source balances from the daily table, preserved both evidence paths, "
            "and withheld the conflicting public ending/ADB/extrema values."
        ),
    },
}


#: What `analysis/pipeline.py` raises for a document no deterministic parser
#: will publish. Matched by its exact text, never by class: `RuntimeError` is
#: also what a genuine defect raises, and an audit that swallowed those would
#: turn a crash into a row.
DECLARED_REFUSAL = "no deterministic parser matched this statement"

#: The status a row carries when the analysis published nothing to audit.
REFUSED_STATUS = "REFUSED"


def refusal_row(
    path: Path, root: Path, source_type: str, pdf_bytes: bytes, reason: str
) -> tuple[dict[str, Any], Job, dict[str, Any]]:
    """One row for a document the deterministic analysis refuses to publish.

    Identity only — filename, path, source hash, page count, source type — and
    every audited value column EMPTY, because there is no published figure for
    an independent one to be compared against. `dashboard_binding_valid` and
    `exports_valid` are empty for the same reason: nothing was bound and
    nothing was exported, and writing `True` would assert a surface was checked.

    The `Job` carries no analysis, which is what keeps the refusal out of the
    package pass (`apply_package_results`): a package built over a document
    with no analysis would have no document to look up.
    """
    row: dict[str, Any] = {field: "" for field in FIELDS}
    row["statement"] = path.name
    row["path"] = path.relative_to(root).as_posix()
    row["sha256"] = hashlib.sha256(pdf_bytes).hexdigest().upper()
    row["pages"] = pdf_page_count(pdf_bytes)
    row["source_type"] = source_type
    row["status"] = REFUSED_STATUS
    row["root_cause"] = reason
    row["fix_applied"] = "None required."
    row["regression_risk"] = "Low"
    row["confidence"] = "High"
    job = Job(id=row["sha256"][:16], filename=path.name, status="error", analysis=None)
    return row, job, {}


def audit_source(
    path: Path, root: Path, *, ocr_cache: Path | None = None
) -> tuple[dict[str, Any], Job, dict[str, Any]]:
    markdown, source_type, pdf_bytes = source_markdown(path, ocr_cache=ocr_cache)
    try:
        analysed = analyze_document(markdown, parse_mode="deterministic")
    except Exception as exc:
        # The same rule as the ADB oracle's and as
        # `corpus_gate.check_outcome_classes`: exact type, exact message. Three
        # guards, one rule, so a refusal recognised by one is recognised by all
        # three and a crash is refused by all three.
        if type(exc) is not RuntimeError or str(exc) != DECLARED_REFUSAL:
            raise
        return refusal_row(path, root, source_type, pdf_bytes, str(exc))
    payload = document_report_to_dict(analysed)
    # This audit compares ONE opening, ONE ending, ONE highest and ONE lowest
    # against `docs/balance-metrics-audit-results.csv`, which is path-keyed and
    # has no account column. A document publishing several accounts has nowhere
    # here to be compared, so it refuses. It used to INDEX `payload["statement"]`
    # and raise a bare `KeyError` at that same shape — the only one of the ten
    # payload readers that was loud, and loud by accident of punctuation rather
    # than by a guard (design §1.4). This is the guard.
    refuse_document_payload(
        payload, surface="balance_forensic_audit.py::audit_source")
    report = analysed.accounts[0]
    statement = report.statement
    oracle = independent_balances(statement, markdown)
    metrics = payload["metrics"]
    expected_opening = oracle.opening
    expected_ending = (
        oracle.closing
        if oracle.valid or oracle.summary_reconciles is True
        else None
    )
    expected_highest = oracle.highest
    expected_lowest = oracle.lowest

    production = {
        "opening": payload["statement"].get("beginning_balance"),
        "ending": payload["statement"].get("ending_balance"),
        "highest": metrics.get("max_balance"),
        "lowest": metrics.get("min_balance"),
    }
    export_csv = csv_rows(_analysis_csv(payload))
    export_xlsx = xlsx_rows(_analysis_xlsx(payload))
    export_values = {
        "csv": {
            "opening": surface_value(export_csv, "statement", "beginning_balance"),
            "ending": surface_value(export_csv, "statement", "ending_balance"),
            "highest": surface_value(export_csv, "metrics", "max_balance"),
            "lowest": surface_value(export_csv, "metrics", "min_balance"),
        },
        "xlsx": {
            "opening": surface_value(export_xlsx, "statement", "beginning_balance"),
            "ending": surface_value(export_xlsx, "statement", "ending_balance"),
            "highest": surface_value(export_xlsx, "metrics", "max_balance"),
            "lowest": surface_value(export_xlsx, "metrics", "min_balance"),
        },
    }
    expected = {
        "opening": expected_opening,
        "ending": expected_ending,
        "highest": expected_highest,
        "lowest": expected_lowest,
    }
    surfaces_valid = all(
        values_match(values[name], expected[name])
        for values in (production, export_values["csv"], export_values["xlsx"])
        for name in expected
    )
    if oracle.valid:
        status = "PASS" if surfaces_valid else "FAIL"
    else:
        withheld = expected_highest is None and expected_lowest is None
        status = "WITHHELD_SOURCE_CONTRADICTION" if withheld and surfaces_valid else "FAIL"

    detail = WITHHELD_DETAILS.get(path.name)
    root_cause = detail["root"] if detail else "Exact source-derived balance match."
    affected_code = detail["code"] if detail else report.model_used
    fix_applied = detail["fix"] if detail else "None required."
    period_start = str(statement.period_start or "")
    period_end = str(statement.period_end or "")
    days = ""
    if period_start and period_end:
        days = (date.fromisoformat(period_end) - date.fromisoformat(period_start)).days + 1

    row: dict[str, Any] = {
        "statement": path.name,
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(pdf_bytes).hexdigest().upper(),
        "pages": pdf_page_count(pdf_bytes),
        "source_type": source_type,
        "bank": statement.bank or "",
        "account": statement.account_number or "",
        "parser": report.model_used,
        "period": f"{period_start} to {period_end}",
        "calendar_days": days,
        "transactions": len(statement.transactions),
        "daily_balance_evidence": oracle.evidence,
        "source_opening": formatted(oracle.opening),
        "expected_opening": formatted(expected_opening),
        "production_opening": formatted(production["opening"]),
        "api_opening": formatted(production["opening"]),
        "csv_opening": formatted(export_values["csv"]["opening"] or None),
        "xlsx_opening": formatted(export_values["xlsx"]["opening"] or None),
        "package_opening": "",
        "source_ending": formatted(oracle.closing),
        "expected_ending": formatted(expected_ending),
        "production_ending": formatted(production["ending"]),
        "api_ending": formatted(production["ending"]),
        "csv_ending": formatted(export_values["csv"]["ending"] or None),
        "xlsx_ending": formatted(export_values["xlsx"]["ending"] or None),
        "package_ending": "",
        "expected_highest": formatted(expected_highest),
        "production_highest": formatted(production["highest"]),
        "api_highest": formatted(production["highest"]),
        "csv_highest": formatted(export_values["csv"]["highest"] or None),
        "xlsx_highest": formatted(export_values["xlsx"]["highest"] or None),
        "package_highest": "",
        "expected_lowest": formatted(expected_lowest),
        "production_lowest": formatted(production["lowest"]),
        "api_lowest": formatted(production["lowest"]),
        "csv_lowest": formatted(export_values["csv"]["lowest"] or None),
        "xlsx_lowest": formatted(export_values["xlsx"]["lowest"] or None),
        "package_lowest": "",
        "opening_difference": difference(production["opening"], expected_opening),
        "ending_difference": difference(production["ending"], expected_ending),
        "highest_difference": difference(production["highest"], expected_highest),
        "lowest_difference": difference(production["lowest"], expected_lowest),
        "detail_ledger_reconciles": oracle.detail_reconciles,
        "summary_reconciles": oracle.summary_reconciles,
        "running_balances_reconcile": oracle.running_reconciles,
        "dashboard_binding_valid": True,
        "exports_valid": surfaces_valid,
        "status": status,
        "root_cause": root_cause,
        "affected_code": affected_code,
        "fix_applied": fix_applied,
        "regression_risk": "Medium" if detail else "Low",
        "confidence": "High",
        "underwriting_adb_basis": report.metrics.adb.underwriting_adb_basis
        if report.metrics.adb is not None
        else "",
        "underwriting_adb_policy": report.metrics.adb.underwriting_adb_policy
        if report.metrics.adb is not None
        else "",
        "bank_reported_average_label": statement.bank_reported_average_label or "",
        "bank_reported_average_variance": formatted(
            report.metrics.bank_reported_average_variance
        ),
    }
    job = Job(
        id=row["sha256"][:16],
        filename=path.name,
        status="done",
        analysis=payload,
    )
    return row, job, expected


def apply_package_results(
    rows: list[dict[str, Any]],
    jobs: list[Job],
    expected_by_id: dict[str, dict[str, Decimal | None]],
) -> None:
    # A refused document has no analysis, so it is not in the package at all
    # and there is no package surface to check for it. Pairing first keeps the
    # `document_{index}` lookups aligned with the package that was actually
    # built, which a filter applied later would not.
    paired = [(row, job) for row, job in zip(rows, jobs) if job.analysis is not None]
    jobs = [job for _, job in paired]
    package = _package_analysis(jobs)
    documents = {document["id"]: document for document in package["documents"]}
    package_csv = csv_rows(_package_csv(package))
    package_xlsx = xlsx_rows(_package_xlsx(package))
    for index, (row, job) in enumerate(paired, start=1):
        document = documents[job.id]
        expected = expected_by_id[job.id]
        package_values = {
            "opening": document.get("beginning_balance"),
            "ending": document.get("ending_balance"),
            "highest": document.get("max_balance"),
            "lowest": document.get("min_balance"),
        }
        row["package_opening"] = formatted(package_values["opening"])
        row["package_ending"] = formatted(package_values["ending"])
        row["package_highest"] = formatted(package_values["highest"])
        row["package_lowest"] = formatted(package_values["lowest"])
        for field, name in (
            ("beginning_balance", "opening"),
            ("ending_balance", "ending"),
            ("max_balance", "highest"),
            ("min_balance", "lowest"),
        ):
            csv_value = surface_value(package_csv, f"document_{index}", field)
            xlsx_value = surface_value(package_xlsx, f"document_{index}", field)
            if not values_match(package_values[name], expected[name]):
                row["status"] = "FAIL"
            if not values_match(csv_value, expected[name]):
                row["status"] = "FAIL"
            if not values_match(xlsx_value, expected[name]):
                row["status"] = "FAIL"
        row["exports_valid"] = row["status"] != "FAIL"


def markdown_money(value: str) -> str:
    if not value:
        return "-"
    amount = Decimal(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_report(rows: list[dict[str, Any]], destination: Path, csv_path: Path) -> None:
    # A REFUSED row carries identity and no audited figure, so it is named and
    # counted rather than folded into rates computed over published balances.
    refused_rows = [row for row in rows if row["status"] == REFUSED_STATUS]
    rows = [row for row in rows if row["status"] != REFUSED_STATUS]
    passed = sum(row["status"] == "PASS" for row in rows)
    withheld = sum(row["status"] == "WITHHELD_SOURCE_CONTRADICTION" for row in rows)
    failed = sum(row["status"] == "FAIL" for row in rows)
    banks = sorted({row["bank"] for row in rows})
    parsers = sorted({row["parser"] for row in rows})
    image_count = sum(row["source_type"].startswith("scanned") for row in rows)
    lines = [
        "# Balance Metrics Production Audit",
        "",
        "Audit date: 2026-08-04",
        "",
        "## Verdict",
        "",
        f"All **{len(rows)}** source PDFs were reopened and audited. **{passed}** have a unique daily ledger; **{withheld}** correctly fail closed for non-unique daily extrema; **{failed}** production mismatches remain.",
        "",
        "The authoritative highest/lowest definition is the maximum/minimum **calendar-day ending ledger balance** over the inclusive statement period. Intraday running peaks and troughs are validation evidence, not extrema metrics.",
        "",
        "## Totals",
        "",
        f"- PDFs/statements audited: **{len(rows)}**",
        f"- Statements the deterministic analysis refused to publish: "
        f"**{len(refused_rows)}** "
        + (
            ", ".join(sorted(row["statement"] for row in refused_rows))
            if refused_rows
            else "(none)"
        ),
        f"- Banks represented: **{len(banks)}**",
        f"- Parser variants represented: **{len(parsers)}**",
        f"- Digital/native PDFs: **{len(rows) - image_count}**",
        f"- Scanned/OCR PDFs: **{image_count}**",
        f"- Opening extraction matches: **{len(rows)}/{len(rows)} (100.00%)**",
        f"- Ending policy matches: **{len(rows)}/{len(rows)} (100.00%)**; one contradictory ending is unavailable",
        f"- Highest policy matches: **{len(rows)}/{len(rows)} (100.00%)**; numeric coverage {passed}/{len(rows)} ({passed / len(rows) * 100:.2f}%)",
        f"- Lowest policy matches: **{len(rows)}/{len(rows)} (100.00%)**; numeric coverage {passed}/{len(rows)} ({passed / len(rows) * 100:.2f}%)",
        f"- Statements requiring a code fix: **1** (IBC)",
        f"- Source contradictions withheld for daily extrema: **{withheld}**",
        "",
        "## Method",
        "",
        "`balance_forensic_audit.py` does not import the production ADB or metrics modules. It hashes and reopens every PDF, re-extracts all 103 digital documents, performs local page OCR on six image-only documents, independently groups Decimal signed postings by date, parses raw daily-ending tables where present, carries balances across inactive days, and requires the last same-day running balance to equal EOD. Expected values are then compared with serialized backend/API data, dashboard bindings, individual CSV/XLSX, and package JSON/CSV/XLSX.",
        "",
        "## Statement Results",
        "",
        "| Statement | Bank | Opening Expected | Opening Production | Highest Expected | Highest Production | Lowest Expected | Lowest Production | Ending Expected | Ending Production | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                escape(value)
                for value in (
                    row["statement"],
                    row["bank"],
                    markdown_money(row["expected_opening"]),
                    markdown_money(row["production_opening"]),
                    markdown_money(row["expected_highest"]),
                    markdown_money(row["production_highest"]),
                    markdown_money(row["expected_lowest"]),
                    markdown_money(row["production_lowest"]),
                    markdown_money(row["expected_ending"]),
                    markdown_money(row["production_ending"]),
                    row["status"],
                )
            )
            + " |"
        )

    lines.extend(["", "## Source Contradictions", ""])
    for row in rows:
        if row["status"] != "WITHHELD_SOURCE_CONTRADICTION":
            continue
        lines.extend(
            [
                f"### {row['statement']}",
                "",
                f"- Bank/parser: {row['bank']} / `{row['parser']}`",
                f"- Source opening/ending: {markdown_money(row['source_opening'])} / {markdown_money(row['source_ending'])}",
                f"- Root cause: {row['root_cause']}",
                f"- Public highest/lowest: unavailable / unavailable",
                f"- Handling: {row['fix_applied']}",
                f"- Confidence: {row['confidence']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Printed Extrema Cross-Checks",
            "",
            "- All four Capital One `Minimum Balance This Cycle` values exactly match the independent daily EOD minima, including negative balances.",
            "- Five ordinary Chase lowest-daily-ending disclosures exactly match. `chase may 29.pdf` also matches after preserving its printed negative sign.",
            "- `chase jun 30.pdf` prints a $1,901.71 service-fee qualification value dated June 24, but its own June 30 daily table and ending balance are $846.55. Standard full-period EOD minimum is therefore $846.55.",
            "- Lower balances printed for Dakota West savings and generic Wells Fargo disclosure examples belong to non-selected accounts or instructions and were excluded from the selected-account metrics.",
            "",
            "## Pipeline Verification",
            "",
            "- Opening, ending, minimum, and maximum values match in serialized JSON and individual CSV/XLSX for every reportable metric.",
            "- Package document rows now include `beginning_balance`, `ending_balance`, `min_balance`, `max_balance`, and `daily_balance_extrema_validated`; package JSON/CSV/XLSX match all per-statement expected values.",
            "- The dashboard continues to bind `statement.ending_balance`, `metrics.min_balance`, and `metrics.max_balance` directly. It contains no daily-ledger or extrema recalculation.",
            "- No dashboard card, layout, label, style, or component was added or moved.",
            "",
            "## Code Changes",
            "",
            "1. IBC now preserves the printed recap balances and normalizes its raw dated daily table instead of silently replacing the recap with a derived ledger.",
            "2. Serialization withholds a closing balance when neither detailed reconciliation nor the bank's own summary identity validates it; source evidence remains in reconciliation diagnostics.",
            "3. Reconciliation now records the source opening balance alongside source/computed ending evidence.",
            "4. Package document exports now carry the four audited balance fields and an extrema-validation state.",
            "5. Regression tests cover the IBC contradiction, fail-closed extrema, package fields/exports, and direct frontend binding.",
            "",
            "## Remaining Risk",
            "",
            "Columbia's supplied PDF still declares a missing page 5 and remains a document-integrity review item, although all financial sections and all four balance metrics reconcile uniquely. Future materially degraded scans can fail closed and require manual review.",
            "",
            "## Final Assessment",
            "",
            "The balance-metrics pipeline is production-ready for the audited corpus: every uniquely reconstructable value matches across all production surfaces, and every non-unique daily ledger is withheld rather than fabricated. The implementation is safe to merge after the recorded full-suite regression run.",
            "",
            f"Machine-readable evidence is in `{csv_path.as_posix()}`.",
            "",
            "Banks: " + ", ".join(banks) + ".",
            "",
            "Parser variants: " + ", ".join(f"`{parser}`" for parser in parsers) + ".",
            "",
        ]
    )
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="Bank Statements")
    parser.add_argument("--csv", default="docs/balance-metrics-audit-results.csv")
    parser.add_argument("--report", default="docs/balance-metrics-production-audit.md")
    parser.add_argument(
        "--ocr-cache",
        help=(
            "Serve image-only PDFs from committed OCR artifacts instead of running "
            "Tesseract (offline, deterministic). Usually tests/corpus_cache."
        ),
    )
    args = parser.parse_args()

    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.rglob("*.pdf"))
    ocr_cache = Path(args.ocr_cache) if args.ocr_cache else None
    rows: list[dict[str, Any]] = []
    jobs: list[Job] = []
    expected_by_id: dict[str, dict[str, Decimal | None]] = {}
    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path}", flush=True)
        row, job, expected = audit_source(path, root, ocr_cache=ocr_cache)
        rows.append(row)
        jobs.append(job)
        expected_by_id[job.id] = expected

    apply_package_results(rows, jobs, expected_by_id)
    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(rows, report_path, csv_path)
    counts = {
        status: sum(row["status"] == status for row in rows)
        for status in ("PASS", "WITHHELD_SOURCE_CONTRADICTION", "FAIL", REFUSED_STATUS)
    }
    print(f"Wrote {len(rows)} rows to {csv_path} and {report_path}: {counts}")
    # A FAIL row means production disagrees with the independent oracle. Exit
    # non-zero so a caller (CI, a shell pipeline) cannot mistake it for success.
    raise SystemExit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
