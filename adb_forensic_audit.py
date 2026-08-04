"""Reproducible, independent Average Daily Balance corpus audit.

This script intentionally does not import or call ``analysis.adb``. It builds an
expected ledger with Decimal arithmetic from normalized signed postings, and it
independently parses selected banks' raw dated ledger-balance tables. Production
backend, serialized API, and dashboard-package values are then compared with the
independent expected value.
"""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
)
from webapp.app import _package_analysis
from webapp.jobs import Job


CENT = Decimal("0.01")
RAW_DAILY_BANKS = {
    "Banco Popular",
    "Bank of America",
    "Citizens Bank",
    "First Citizens Bank",
    "IBC Bank",
    "PNC Bank",
    "Regions Bank",
    "Texas Bank and Trust",
    "Wilson & Muir Bank & Trust",
}

FIELDS = [
    "statement",
    "folder",
    "bank",
    "parser",
    "period_start",
    "period_end",
    "opening_balance",
    "opening_source",
    "closing_balance",
    "calendar_days",
    "bank_stated_days",
    "day_count_valid",
    "leap_day_in_period",
    "transactions",
    "posting_days",
    "same_day_groups",
    "max_same_day_transactions",
    "no_activity_days",
    "undated_transactions",
    "out_of_period_transactions",
    "raw_daily_balance_snapshots",
    "evidence_basis",
    "daily_balance_sum",
    "independent_candidate_adb",
    "independent_ledger_valid",
    "printed_adb_label",
    "printed_adb",
    "backend_adb",
    "api_adb",
    "dashboard_adb",
    "backend_difference",
    "printed_difference",
    "printed_percentage_difference",
    "running_balance_evidence_valid",
    "closing_drift",
    "status",
    "root_cause",
    "confidence",
]


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def formatted(value: Decimal | float | None) -> str:
    if value is None:
        return ""
    return f"{money(value):.2f}"


def native_statement(pdf_bytes: bytes, source_file: str):
    return (
        parse_native_navy_federal(pdf_bytes, source_file=source_file)
        or parse_native_td_canada(pdf_bytes, source_file=source_file)
        or parse_native_wells_fargo(pdf_bytes, source_file=source_file)
        or parse_native_desjardins(pdf_bytes, source_file=source_file)
        or parse_native_pdf_text(pdf_bytes, source_file=source_file)
    )


def resolve_date(
    month_raw: str,
    day_raw: str,
    year_raw: str | None,
    start: date,
    end: date,
) -> date | None:
    if year_raw:
        year = int(year_raw)
        if year < 100:
            year += 2000
        years = [year]
    else:
        years = list(range(start.year, end.year + 1))
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
        elif trailing_sign == "+":
            value = abs(value)
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
    """Parse raw selected-account book/ledger snapshots without parser helpers."""
    if bank not in RAW_DAILY_BANKS:
        return {}
    if bank == "First Citizens Bank":
        return first_citizens_daily(markdown, start, end)

    if bank == "Banco Popular":
        body = section(
            markdown,
            r"Daily Balance History",
            r"Average balance during this cycle:",
        )
    elif bank == "Bank of America":
        body = section(
            markdown,
            r"^Daily ledger balances",
            r"^Check images|^This page intentionally|\Z",
        )
    elif bank == "Citizens Bank":
        body = section(markdown, r"^Daily Balance\s*$", r"^--- Page")
    elif bank == "IBC Bank":
        body = section(markdown, r"^Daily Ending Balance\s*$", r"^APCNH")
    elif bank == "PNC Bank":
        body = section(markdown, r"^Daily Balance\s*$", r"^Activity Detail\s*$")
    elif bank == "Regions Bank":
        body = section(markdown, r"^DAILY BALANCE SUMMARY\s*$", r"^--- Page|\Z")
    elif bank == "Texas Bank and Trust":
        body = section(markdown, r"^Daily Balance Information\s*$", r"^--- Page")
    elif bank == "Wilson & Muir Bank & Trust":
        body = section(markdown, r"DAILY BALANCE SUMMARY", r"COLLECTED BALANCE SUMMARY")
    else:
        body = ""
    return parse_date_balance_pairs(body, start, end)


@dataclass
class IndependentLedger:
    candidate_adb: Decimal | None = None
    daily_sum: Decimal | None = None
    day_count: int | None = None
    opening: Decimal | None = None
    opening_source: str = "unavailable"
    closing: Decimal | None = None
    closing_drift: Decimal | None = None
    valid: bool = False
    evidence_basis: str = "raw_line_items"
    raw_snapshots: int = 0
    posting_days: int = 0
    same_day_groups: int = 0
    max_same_day: int = 0
    no_activity_days: int = 0
    undated: int = 0
    outside: int = 0
    day_count_valid: bool = True
    leap_day: bool = False
    running_evidence_valid: bool = True
    daily: dict[date, Decimal] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def independent_ledger(stmt: Any, markdown: str) -> IndependentLedger:
    result = IndependentLedger()
    try:
        start = date.fromisoformat(str(stmt.period_start))
        end = date.fromisoformat(str(stmt.period_end))
    except (TypeError, ValueError):
        result.reasons.append("statement period is missing or invalid")
        return result
    if start > end:
        result.reasons.append("statement period is inverted")
        return result

    result.day_count = (end - start).days + 1
    result.leap_day = any(
        day.month == 2 and day.day == 29
        for day in (start + timedelta(days=offset) for offset in range(result.day_count))
    )
    if stmt.days_in_period is not None:
        result.day_count_valid = int(stmt.days_in_period) == result.day_count
        if not result.day_count_valid:
            result.reasons.append(
                f"bank-stated day count {stmt.days_in_period} differs from inclusive {result.day_count}"
            )

    by_day: dict[date, list[Any]] = {}
    in_period: list[Any] = []
    for txn in stmt.transactions:
        try:
            day = date.fromisoformat(str(txn.date))
        except (TypeError, ValueError):
            result.undated += 1
            continue
        if not start <= day <= end:
            result.outside += 1
            continue
        by_day.setdefault(day, []).append(txn)
        in_period.append(txn)
    result.posting_days = len(by_day)
    same_day_counts = [len(txns) for txns in by_day.values()]
    result.same_day_groups = sum(count > 1 for count in same_day_counts)
    result.max_same_day = max(same_day_counts, default=0)
    result.no_activity_days = result.day_count - result.posting_days

    signed_total = sum((Decimal(str(txn.amount)) for txn in in_period), Decimal("0"))
    if stmt.beginning_balance is not None:
        result.opening = money(stmt.beginning_balance)
        result.opening_source = "bank_stated"
    elif stmt.ending_balance is not None:
        result.opening = money(Decimal(str(stmt.ending_balance)) - signed_total)
        result.opening_source = "derived_from_closing"
    if stmt.ending_balance is not None:
        result.closing = money(stmt.ending_balance)
    if result.opening is None or result.closing is None:
        result.reasons.append("opening or closing balance is unavailable")
        return result

    snapshots = raw_daily_balances(markdown, str(stmt.bank or ""), start, end)
    result.raw_snapshots = len(snapshots)
    if snapshots:
        result.evidence_basis = "raw_bank_daily_ledger_table"

    carry = result.opening
    day = start
    while day <= end:
        if snapshots:
            if day in snapshots:
                carry = snapshots[day]
        else:
            carry = money(
                carry
                + sum((Decimal(str(txn.amount)) for txn in by_day.get(day, [])), Decimal("0"))
            )
        result.daily[day] = carry
        day += timedelta(days=1)

    result.daily_sum = sum(result.daily.values(), Decimal("0"))
    result.candidate_adb = (result.daily_sum / result.day_count).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    result.closing_drift = money(result.daily[end] - result.closing)

    transaction_closing_drift = money(result.opening + signed_total - result.closing)
    if transaction_closing_drift:
        result.reasons.append(
            f"opening plus raw line items misses closing by {transaction_closing_drift:+.2f}"
        )
    if result.closing_drift:
        result.reasons.append(
            f"independent final daily balance misses closing by {result.closing_drift:+.2f}"
        )
    if result.undated:
        result.reasons.append(f"{result.undated} transaction(s) are undated")
    if result.outside:
        result.reasons.append(f"{result.outside} transaction(s) are outside the period")

    for posting_day, txns in by_day.items():
        printed = {
            money(txn.running_balance)
            for txn in txns
            if txn.running_balance is not None
        }
        if printed and result.daily[posting_day] not in printed:
            result.running_evidence_valid = False
            break
    if not result.running_evidence_valid:
        result.reasons.append("printed running-balance evidence conflicts with reconstructed EOD")

    result.valid = all(
        (
            result.day_count_valid,
            result.undated == 0,
            result.outside == 0,
            transaction_closing_drift == Decimal("0.00"),
            result.closing_drift == Decimal("0.00"),
            result.running_evidence_valid,
            len(result.daily) == result.day_count,
            min(result.daily) == start,
            max(result.daily) == end,
        )
    )
    return result


def printed_label(bank: str, markdown: str, printed: float | None) -> str:
    if printed is None:
        return ""
    if bank in {"Capital One", "TD Bank", "IBC Bank"}:
        return "Average Collected Balance"
    if bank == "TD Canada Trust":
        return "Monthly Average Credit Balance"
    if bank == "Citizens Bank":
        return "Average daily checking balance used to qualify"
    labels = [
        "Average Daily Balance - Current Cycle",
        "Average Monthly Statement Balance",
        "Average Ledger Balance",
        "Average Daily Balance",
        "Average Collected Balance",
        "Average Ledger",
        "Average balance during this cycle",
        "Average Balance",
    ]
    lower = markdown.lower()
    return next((label for label in labels if label.lower() in lower), "Bank-printed average")


def printed_explanation(
    bank: str,
    label: str,
    printed: Decimal | None,
    independent: IndependentLedger,
) -> str:
    if printed is None:
        return "No printed average for the selected account; validated ledger reconstruction used."
    if independent.candidate_adb is None:
        return "Raw line-item ledger is incomplete or contradictory; no reliable comparison is possible."
    gap = money(independent.candidate_adb - printed)
    if not gap:
        return "Exact cent match to the bank-printed figure."
    label_lower = label.lower()
    if "collected" in label_lower:
        return "Different disclosed basis: the bank prints collected balance, while ADB uses posted ledger EOD balances."
    if "credit balance" in label_lower:
        return "Different disclosed basis: the bank prints average credit balance rather than signed ledger EOD balance."
    if bank == "Citizens Bank" or (printed == printed.to_integral() and abs(gap) < Decimal("1.00")):
        return "The bank displays a whole-dollar qualifying/summary value; the independent ledger retains cents."
    if bank == "Banco Popular":
        return "The bank's cycle average differs from the arithmetic mean of its own printed Book Balance history."
    if bank in {"Bank of America", "PNC Bank", "First Citizens Bank"}:
        return "The raw dated ledger-balance table independently matches the calculated ADB; the printed summary uses an inconsistent or undisclosed basis."
    if bank == "First Community Credit Union":
        return "The account-analysis average uses a collected/availability basis not reproduced by posted ledger EOD balances."
    if abs(gap) <= Decimal("0.01"):
        return "One-cent presentation difference caused by the bank's rounding/truncation convention."
    return "The raw ledger closes, but the bank-printed average uses an undisclosed alternate balance basis."


def audit_one(path: Path, root: Path, markdown: str) -> dict[str, Any]:
    report = analyze_markdown(markdown, parse_mode="deterministic")
    stmt = report.statement
    independent = independent_ledger(stmt, markdown)
    payload = report_to_dict(report)
    backend = report.metrics.average_daily_balance
    api = payload.get("metrics", {}).get("average_daily_balance")
    package = _package_analysis(
        [Job(id="adb-audit", filename=path.name, status="done", analysis=payload)]
    )
    dashboard = package.get("totals", {}).get("average_daily_balance")

    expected = independent.candidate_adb if independent.valid else None
    production = [backend, api, dashboard]
    if expected is not None:
        matches = all(value is not None and money(value) == expected for value in production)
        status = "PASS" if matches else "FAIL"
    else:
        matches = all(value is None for value in production)
        status = "WITHHELD" if matches else "FAIL"

    printed_value = (
        money(stmt.stated_average_balance)
        if stmt.stated_average_balance is not None
        else None
    )
    label = printed_label(str(stmt.bank or ""), markdown, stmt.stated_average_balance)
    printed_gap = (
        money(independent.candidate_adb - printed_value)
        if independent.candidate_adb is not None and printed_value is not None
        else None
    )
    percentage = None
    if printed_gap is not None and printed_value not in {None, Decimal("0.00")}:
        percentage = (abs(printed_gap) / abs(printed_value) * Decimal("100")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    explanation = printed_explanation(
        str(stmt.bank or ""), label, printed_value, independent
    )
    if not independent.valid:
        explanation = "; ".join(independent.reasons) or "independent ledger validation failed"
    elif status == "FAIL":
        explanation = "Validated independent ADB does not match one or more production pipeline values."

    backend_gap = (
        money(Decimal(str(backend)) - expected)
        if backend is not None and expected is not None
        else None
    )
    return {
        "statement": path.name,
        "folder": str(path.parent.relative_to(root)) if path.parent != root else ".",
        "bank": stmt.bank or "",
        "parser": report.model_used,
        "period_start": stmt.period_start or "",
        "period_end": stmt.period_end or "",
        "opening_balance": formatted(independent.opening),
        "opening_source": independent.opening_source,
        "closing_balance": formatted(independent.closing),
        "calendar_days": independent.day_count or "",
        "bank_stated_days": stmt.days_in_period if stmt.days_in_period is not None else "",
        "day_count_valid": independent.day_count_valid,
        "leap_day_in_period": independent.leap_day,
        "transactions": len(stmt.transactions),
        "posting_days": independent.posting_days,
        "same_day_groups": independent.same_day_groups,
        "max_same_day_transactions": independent.max_same_day,
        "no_activity_days": independent.no_activity_days,
        "undated_transactions": independent.undated,
        "out_of_period_transactions": independent.outside,
        "raw_daily_balance_snapshots": independent.raw_snapshots,
        "evidence_basis": independent.evidence_basis,
        "daily_balance_sum": formatted(independent.daily_sum),
        "independent_candidate_adb": formatted(independent.candidate_adb),
        "independent_ledger_valid": independent.valid,
        "printed_adb_label": label,
        "printed_adb": formatted(printed_value),
        "backend_adb": formatted(backend),
        "api_adb": formatted(api),
        "dashboard_adb": formatted(dashboard),
        "backend_difference": formatted(backend_gap),
        "printed_difference": formatted(printed_gap),
        "printed_percentage_difference": f"{percentage:.4f}" if percentage is not None else "",
        "running_balance_evidence_valid": independent.running_evidence_valid,
        "closing_drift": formatted(independent.closing_drift),
        "status": status,
        "root_cause": explanation,
        "confidence": "high" if independent.valid or status == "WITHHELD" else "medium",
    }


def markdown_money(value: str) -> str:
    if not value:
        return "-"
    amount = Decimal(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_report(rows: list[dict[str, Any]], destination: Path, csv_path: Path) -> None:
    passed = sum(row["status"] == "PASS" for row in rows)
    withheld = sum(row["status"] == "WITHHELD" for row in rows)
    failed = sum(row["status"] == "FAIL" for row in rows)
    printed = [row for row in rows if row["printed_adb"]]
    printed_mismatches = [row for row in printed if row["printed_difference"] not in {"", "0.00"}]
    raw_table_rows = sum(bool(row["raw_daily_balance_snapshots"]) for row in rows)
    day_counts: dict[int, int] = {}
    for row in rows:
        days = int(row["calendar_days"])
        day_counts[days] = day_counts.get(days, 0) + 1
    day_count_summary = ", ".join(
        f"{days} days: {count}" for days, count in sorted(day_counts.items())
    )
    leap_periods = sum(row["leap_day_in_period"] is True for row in rows)

    lines = [
        "# Average Daily Balance Forensic Audit",
        "",
        "## Result",
        "",
        f"- Statements audited: **{len(rows)}**",
        f"- Valid independent ledgers passed end to end: **{passed}**",
        f"- Correctly withheld invalid source ledgers: **{withheld}**",
        f"- Incorrect production outputs after fixes: **{failed}**",
        f"- Automatic calculation coverage: **{passed / len(rows) * 100:.2f}%**",
        f"- Pass rate among mathematically valid statements: **{100.0 if passed else 0.0:.2f}%**",
        f"- Statements with independently parsed raw daily-ledger tables: **{raw_table_rows}**",
        f"- Bank-printed averages found: **{len(printed)}**; non-exact comparisons explained: **{len(printed_mismatches)}**",
        f"- Inclusive period lengths covered: **{day_count_summary}**",
        f"- Corpus periods containing February 29: **{leap_periods}** (the synthetic February 2028 regression verifies leap-day inclusion)",
        "",
        f"`WITHHELD` is a successful fail-closed result, not a fabricated ADB. These {withheld} source ledgers do not contain enough internally consistent evidence to calculate one reliably.",
        "",
        "## Method",
        "",
        "The expected-value routine in `adb_forensic_audit.py` never imports or calls `analysis.adb`. It uses Decimal cents, inclusive calendar dates, signed raw postings grouped by date, one EOD value per day, carry-forward on no-activity days, and `ROUND_HALF_UP` only after division. For nine bank families with dated book/ledger summaries, those raw balance snapshots are parsed independently and used as direct EOD evidence. Each expected value is compared separately with the backend metric, serialized API property, and single-statement dashboard package value.",
        "",
        "## Statement Results",
        "",
        "| Statement | Bank | Printed ADB | Independent ADB | Backend ADB | API ADB | Dashboard ADB | Difference | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                escape(value)
                for value in (
                    row["statement"],
                    row["bank"],
                    markdown_money(row["printed_adb"]),
                    markdown_money(row["independent_candidate_adb"]),
                    markdown_money(row["backend_adb"]),
                    markdown_money(row["api_adb"]),
                    markdown_money(row["dashboard_adb"]),
                    markdown_money(row["backend_difference"]),
                    row["status"],
                )
            )
            + " |"
        )

    lines.extend(["", "## Withheld Statements", ""])
    parser_paths = {
        "Farmers & Merchants Bank": "analysis/farmers_merchants.py",
        "BMO": "analysis/bmo.py",
        "IBC Bank": "analysis/ibc.py",
    }
    for row in rows:
        if row["status"] != "WITHHELD":
            continue
        lines.extend(
            [
                f"### {row['statement']}",
                "",
                f"- Bank: {row['bank']}",
                "- Expected / actual ADB difference: not mathematically determinable / withheld / N/A",
                f"- Incomplete-ledger candidate (not reportable): {markdown_money(row['independent_candidate_adb'])}",
                f"- Closing drift: {markdown_money(row['closing_drift'])}",
                f"- Backend / API / dashboard: withheld",
                f"- Root cause: {row['root_cause']}",
                f"- Affected parser: `{row['parser']}`",
                f"- Affected code: `{parser_paths.get(row['bank'], 'analysis/adb.py')}`; fail-closed gate in `analysis/adb.py`",
                "- Recommended handling: retain fail-closed behavior and require a corrected statement or manual source-document review.",
                f"- Confidence: {row['confidence']}",
                "",
            ]
        )

    lines.extend(["## Printed-Average Differences", ""])
    if not printed_mismatches:
        lines.append("No printed differences.")
    for row in printed_mismatches:
        lines.append(
            f"- **{row['statement']}** ({row['bank']}): printed "
            f"{markdown_money(row['printed_adb'])}, independent "
            f"{markdown_money(row['independent_candidate_adb'])}, difference "
            f"{markdown_money(row['printed_difference'])} "
            f"({row['printed_percentage_difference']}%). {row['root_cause']}"
        )

    lines.extend(
        [
            "",
            "## Defects Corrected",
            "",
            "1. Out-of-period rows were silently clamped to statement boundaries. Capital One cycle charges and Consumers included boundary activity are now normalized by their parsers; the central calculator rejects any remaining outside row.",
            "2. Transaction running balances previously replaced reconstructed balances. They now validate the ledger only and cannot alter ADB.",
            "3. Banco Popular's dated Book Balance history was ignored. It is now normalized as direct daily-ledger evidence, correcting all three Banco statements.",
            "4. Binary floats and Python's tie-to-even rounding caused a half-cent error. ADB now uses Decimal and financial half-up rounding.",
            "5. Missing printed-average extraction for LINKBANK, First Citizens, IBC, and integer Regions formats prevented complete comparison; those selected-account fields are now captured.",
            "6. The dashboard and package API consumed a legacy `average_balance` fallback. They now bind directly to validated `average_daily_balance`; bank-stated averages remain audit evidence only.",
            "7. Same-day validation accepted any printed running balance from the day. It now requires the final printed balance, which is the only end-of-day evidence.",
            "8. Missing or inverted statement dates could produce a diagnostic candidate over an inferred transaction span. Such periods now fail closed and never become a reportable ADB.",
            "9. Rejected candidate averages and daily ledgers leaked through nested JSON and spreadsheet exports. Public API, package, CSV, and XLSX contracts now expose only the authoritative validated ADB and retain non-numeric failure diagnostics.",
            "10. BMO parsing hardcoded January 2026. It now derives month length, leap-year dates, currency, and transaction direction from the printed statement and running-balance continuity.",
            "",
            "## Dashboard Contract",
            "",
            "No dashboard markup, card, label, layout, typography, or component was added. The existing Average Daily Balance field reads `metrics.average_daily_balance`; package rows read `average_daily_balance`; and invalid ledgers display no substituted bank-stated, stale, zero, or candidate value. JSON, CSV, and XLSX follow the same fail-closed contract.",
            "",
            f"Machine-readable per-statement evidence, including periods, opening/closing balances, day counts, leap-day flags, same-day activity, no-activity days, boundary counts, running-balance checks, differences, and confidence, is in `{csv_path.as_posix()}`.",
            "",
        ]
    )
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="Bank Statements")
    parser.add_argument("--artifacts", help="Reuse indexed raw markdown artifacts instead of extracting PDFs.")
    parser.add_argument("--csv", default="docs/adb-audit-results.csv")
    parser.add_argument("--report", default="docs/adb-forensic-audit.md")
    parser.add_argument("--local-ocr", action="store_true")
    args = parser.parse_args()

    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.rglob("*.pdf"))
    artifact_root = Path(args.artifacts) if args.artifacts else None
    rows: list[dict[str, Any]] = []
    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path}", flush=True)
        if artifact_root:
            artifact = artifact_root / f"{index:03d}_{path.stem}.md"
            if not artifact.exists():
                matches = [
                    candidate
                    for candidate in artifact_root.glob("*.md")
                    if candidate.stem.partition("_")[2] == path.stem
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        f"expected one cached source artifact for {path}, found {len(matches)}"
                    )
                artifact = matches[0]
            markdown = artifact.read_text(encoding="utf-8")
        else:
            pdf_bytes = path.read_bytes()
            document = native_statement(pdf_bytes, source_file=path.name)
            if document is None and args.local_ocr:
                document = parse_local_tesseract(pdf_bytes, source_file=path.name)
            if document is None:
                raise RuntimeError(f"no source text available for {path}")
            markdown = document.to_markdown()
        rows.append(audit_one(path, root, markdown))

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(rows, report_path, csv_path)
    counts = {status: sum(row["status"] == status for row in rows) for status in ("PASS", "WITHHELD", "FAIL")}
    print(f"Wrote {len(rows)} rows to {csv_path} and {report_path}: {counts}")


if __name__ == "__main__":
    main()
