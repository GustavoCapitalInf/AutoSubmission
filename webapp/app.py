from __future__ import annotations
import io
import csv
import json
import threading
import zipfile
from collections import deque
from copy import deepcopy
from datetime import UTC, date, datetime
from flask import Flask, request, jsonify, render_template, Response, abort

from ocr.rasterize import pdf_page_count, rasterize_page
from ocr.render import rendered_skeleton, render_boxed
from analysis.revenue import apply_serialized_revenue_review, REVENUE_STATES
from .jobs import JobStore
from .worker import run_job

app = Flask(__name__)
store = JobStore()
_job_queue: deque[tuple[str, bytes, str, bool, str]] = deque()
_job_queue_lock = threading.Lock()
_job_worker_active = False


def _process_job_queue() -> None:
    global _job_worker_active
    while True:
        with _job_queue_lock:
            if not _job_queue:
                _job_worker_active = False
                return
            job_id, pdf_bytes, filename, force_ocr, parse_mode = _job_queue.popleft()
        run_job(job_id, pdf_bytes, filename, store, force_ocr, parse_mode)


def _enqueue_job(job_id: str, pdf_bytes: bytes, filename: str, force_ocr: bool, parse_mode: str) -> None:
    global _job_worker_active
    with _job_queue_lock:
        _job_queue.append((job_id, pdf_bytes, filename, force_ocr, parse_mode))
        should_start = not _job_worker_active
        if should_start:
            _job_worker_active = True
    if should_start:
        threading.Thread(target=_process_job_queue, daemon=True).start()


def _adb_rows(metrics: dict) -> list[tuple[str, str, object]]:
    """The Average Daily Balance working, one row per calendar day, so an
    underwriter can re-add the column in a spreadsheet and land on the same
    figure. Kept out of the flattened `metrics` section, where the whole daily
    ledger would collapse into a single unreadable JSON cell."""
    adb = metrics.get("adb")
    if not isinstance(adb, dict):
        return []
    rows: list[tuple[str, str, object]] = []
    for key in (
        "period_start", "period_end", "calendar_day_count",
        "opening_balance", "opening_balance_source", "closing_balance",
        "computed_closing_balance", "total_credits", "total_debits",
        "daily_balance_sum", "average_daily_balance", "ok", "reconciled",
    ):
        item = adb.get(key)
        rows.append(("adb", key, "" if item is None else item))
    for name, passed in (adb.get("validations") or {}).items():
        rows.append(("adb_validation", name, "pass" if passed else "FAIL"))
    for warning in adb.get("warnings") or []:
        rows.append(("adb_warning", "", warning))
    for day in adb.get("daily_balances") or []:
        rows.append(("adb_daily_balance", day.get("date", ""), day.get("ending_balance", "")))
    return rows


def _analysis_rows(analysis: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    for section in ("statement", "metrics", "quality", "integrity", "reconciliation"):
        value = analysis.get(section)
        if isinstance(value, dict):
            for key, item in value.items():
                if section == "metrics" and key == "adb":
                    continue  # emitted as its own section below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
                rows.append((section, key, "" if item is None else item))
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
    detection = analysis.get("detection")
    if isinstance(detection, dict):
        for key, item in detection.items():
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
    return rows


def _analysis_csv(analysis: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_analysis_rows(analysis))
    return buf.getvalue()


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        rows.append(("totals", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            rows.append((f"document_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("funders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"funder_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("potential_lenders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"potential_lender_{idx}", key, "" if value is None else value))
    for idx, provider in enumerate(package.get("insurance_providers") or [], start=1):
        for key, value in provider.items():
            rows.append((f"insurance_provider_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("lender_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"lender_evidence_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("potential_lender_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"potential_lender_evidence_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("insurance_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"insurance_evidence_{idx}", key, "" if value is None else value))
    for state in REVENUE_STATES:
        for idx, evidence in enumerate(package.get(f"{state}_evidence") or [], start=1):
            for key, value in evidence.items():
                rows.append((f"{state}_evidence_{idx}", key, "" if value is None else value))
    return rows


def _package_csv(package: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_package_rows(package))
    return buf.getvalue()


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _xlsx_sheet(rows: list[tuple[str, str, object]]) -> str:
    def cell(col: int, row: int, value: object) -> str:
        ref = f"{chr(64 + col)}{row}"
        return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(value)}</t></is></c>'

    sheet_rows = ['<row r="1">' + cell(1, 1, "section") + cell(2, 1, "field") + cell(3, 1, "value") + "</row>"]
    for idx, row in enumerate(rows, start=2):
        sheet_rows.append(
            f'<row r="{idx}">' + cell(1, idx, row[0]) + cell(2, idx, row[1]) + cell(3, idx, row[2]) + "</row>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows) + "</sheetData></worksheet>"
    )


def _rows_xlsx(rows: list[tuple[str, str, object]]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Extracted Data" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        z.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        z.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(rows))
        z.writestr("docProps/core.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dcterms="http://purl.org/dc/terms/">
<dcterms:created>{datetime.now(UTC).isoformat()}</dcterms:created></cp:coreProperties>""")
    return out.getvalue()


def _analysis_xlsx(analysis: dict) -> bytes:
    return _rows_xlsx(_analysis_rows(analysis))


def _package_xlsx(package: dict) -> bytes:
    return _rows_xlsx(_package_rows(package))


def _num(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _contributes_to_potential_totals(classification: dict) -> bool:
    explicit = classification.get("contributes_to_potential_lender_totals")
    if explicit is not None:
        return explicit is True
    return classification.get("contributes_to_potential_lender_count") is True


def _period_days(start: object, end: object) -> int | None:
    if not start or not end:
        return None
    try:
        start_date = date.fromisoformat(str(start)[:10])
        end_date = date.fromisoformat(str(end)[:10])
    except ValueError:
        return None
    days = (end_date - start_date).days + 1
    return days if days > 0 else None


def _package_analysis(jobs) -> dict:
    documents = []
    monthly = []
    average_balance_weighted_sum = 0.0
    average_balance_weight = 0
    average_balance_values: list[float] = []
    totals = {
        "documents": len(jobs),
        "completed": 0,
        "failed": 0,
        "approved": 0,
        "summary_only": 0,
        "manual_review": 0,
        "integrity_high": 0,
        "integrity_review": 0,
        "total_credits": 0.0,
        "total_posted_credits": 0.0,
        "total_posted_credit_count": 0,
        "true_revenue": 0.0,
        "confirmed_true_revenue": 0.0,
        "confirmed_true_revenue_total": 0.0,
        "confirmed_true_revenue_count": 0,
        "potential_revenue_total": 0.0,
        "potential_revenue_count": 0,
        "non_revenue_total": 0.0,
        "non_revenue_count": 0,
        "maximum_revenue": 0.0,
        "total_debits": 0.0,
        "cash_flow": 0.0,
        "lender_debits": 0.0,
        "lender_debit_count": 0,
        "lenders_detected": 0,
        "potential_lenders_detected": 0,
        "potential_lender_debit_count": 0,
        "potential_lender_debit_total": 0.0,
        "potential_lender_debits": 0.0,
        "monthly_lender_debits": 0.0,
        "insurance_count": 0,
        "insurance_total": 0.0,
        "withholding_numerator": 0.0,
        "withholding_denominator": 0.0,
        "potential_withholding_numerator": 0.0,
        "potential_withholding_denominator": 0.0,
        "nsf_count": 0,
    }

    funders: dict[str, dict] = {}
    potential_lenders: dict[str, dict] = {}
    insurance_providers: dict[str, dict] = {}
    package_transactions: list[dict] = []
    package_funder_matches: list[dict] = []
    package_potential_matches: list[dict] = []
    package_insurance_matches: list[dict] = []
    package_lender_evidence: list[dict] = []
    package_potential_lender_evidence: list[dict] = []
    package_insurance_evidence: list[dict] = []
    package_revenue_evidence: dict[str, list[dict]] = {
        state: [] for state in REVENUE_STATES
    }
    denominator_modes: set[str] = set()
    for job in jobs:
        analysis = job.analysis or {}
        statement = analysis.get("statement") or {}
        metrics = analysis.get("metrics") or {}
        quality = analysis.get("quality") or {}
        integrity = analysis.get("integrity") or {}
        detection = analysis.get("detection") or {}
        corporate_use = quality.get("corporate_use") or ""
        integrity_risk = integrity.get("risk_level") or ""
        ready = job.status == "done" and job.analysis is not None

        if ready:
            totals["completed"] += 1
        else:
            totals["failed"] += 1
        if corporate_use == "approved":
            totals["approved"] += 1
        elif corporate_use == "summary_only":
            totals["summary_only"] += 1
        elif corporate_use:
            totals["manual_review"] += 1
        if integrity_risk == "high":
            totals["integrity_high"] += 1
        elif integrity_risk == "review":
            totals["integrity_review"] += 1

        credits = _num(metrics.get("effective_total_deposits"))
        debits = _num(metrics.get("effective_total_withdrawals"))
        cash_flow = _num(metrics.get("cash_flow"))
        statement_transactions = [
            transaction
            for transaction in (statement.get("transactions") or [])
            if isinstance(transaction, dict)
        ]
        authoritative_rows = [
            transaction
            for transaction in statement_transactions
            if isinstance(transaction.get("classification"), dict)
        ]
        lender_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("contributes_to_withholding_rate") is True
        ]
        potential_lender_rows = [
            transaction
            for transaction in authoritative_rows
            if _contributes_to_potential_totals(transaction["classification"])
        ]
        insurance_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("contributes_to_insurance_totals") is True
        ]
        positive_statement_rows = [
            transaction
            for transaction in statement_transactions
            if _num(transaction.get("amount")) > 0
        ]
        classified_positive_rows = [
            transaction
            for transaction in positive_statement_rows
            if isinstance(transaction.get("classification"), dict)
        ]
        posted_credit_rows = [
            transaction
            for transaction in classified_positive_rows
            if transaction["classification"].get("is_posted") is not False
        ]
        revenue_rows = {
            state: [
                transaction
                for transaction in posted_credit_rows
                if transaction["classification"].get("revenue_classification") == state
            ]
            for state in REVENUE_STATES
        }
        revenue_rows_are_authoritative = (
            bool(authoritative_rows)
            and len(classified_positive_rows) == len(positive_statement_rows)
            and all(
                transaction["classification"].get("is_posted") is False
                or transaction["classification"].get("revenue_classification")
                in REVENUE_STATES
                for transaction in classified_positive_rows
            )
            and len(posted_credit_rows)
            == sum(len(rows) for rows in revenue_rows.values())
        )
        if authoritative_rows:
            lender_debits = round(sum(abs(_num(row.get("amount"))) for row in lender_rows), 2)
            lender_debit_count = len(lender_rows)
            potential_lender_debit_total = round(
                sum(abs(_num(row.get("amount"))) for row in potential_lender_rows),
                2,
            )
            potential_lender_debit_count = len(potential_lender_rows)
            insurance_count = len(insurance_rows)
            insurance_total = round(sum(abs(_num(row.get("amount"))) for row in insurance_rows), 2)
        else:
            # Compatibility for already-completed in-memory jobs created before
            # classification records were added. New reports always take the path above.
            lender_debits = _num(metrics.get("withholding_numerator"), _num(metrics.get("lender_debits")))
            lender_debit_count = int(_num(metrics.get("lender_debit_count"), 0.0))
            potential_lender_debit_total = _num(
                metrics.get("potential_lender_debit_total"),
                _num(metrics.get("potential_lender_debits")),
            )
            potential_lender_debit_count = int(
                _num(metrics.get("potential_lender_debit_count"), 0.0)
            )
            insurance_count = int(_num(metrics.get("insurance_count"), 0.0))
            insurance_total = _num(metrics.get("insurance_total"))
        if revenue_rows_are_authoritative:
            posted_credit_total = round(
                sum(_num(row.get("amount")) for row in posted_credit_rows),
                2,
            )
            posted_credit_count = len(posted_credit_rows)
            revenue_totals = {
                state: round(sum(_num(row.get("amount")) for row in rows), 2)
                for state, rows in revenue_rows.items()
            }
            revenue_counts = {
                state: len(rows) for state, rows in revenue_rows.items()
            }
        else:
            posted_credit_total = _num(metrics.get("total_posted_credits"), credits)
            posted_credit_count = int(
                _num(metrics.get("total_posted_credit_count"), metrics.get("effective_num_deposits") or 0)
            )
            confirmed_fallback = _num(
                metrics.get("confirmed_true_revenue_total"),
                _num(metrics.get("true_revenue"), posted_credit_total),
            )
            revenue_totals = {
                "true_revenue": confirmed_fallback,
                "potential_revenue": _num(metrics.get("potential_revenue_total")),
                "non_revenue": _num(metrics.get("non_revenue_total")),
            }
            revenue_counts = {
                "true_revenue": int(_num(metrics.get("confirmed_true_revenue_count"))),
                "potential_revenue": int(_num(metrics.get("potential_revenue_count"))),
                "non_revenue": int(_num(metrics.get("non_revenue_count"))),
            }
        eligible_deposits = _num(
            metrics.get("withholding_denominator"),
            _num(metrics.get("true_revenue"), credits),
        )
        denominator_mode = metrics.get("withholding_denominator_mode") or "legacy_eligible_deposits"
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
        average_balance = metrics.get("average_balance")
        average_balance_num = _num(average_balance, default=float("nan"))
        average_balance_source = metrics.get("average_balance_source")
        adb_calendar_days = metrics.get("calendar_day_count")
        adb_validated = metrics.get("adb_ok")

        totals["total_credits"] = round(totals["total_credits"] + credits, 2)
        totals["total_posted_credits"] = round(
            totals["total_posted_credits"] + posted_credit_total,
            2,
        )
        totals["total_posted_credit_count"] += posted_credit_count
        totals["confirmed_true_revenue_total"] = round(
            totals["confirmed_true_revenue_total"] + revenue_totals["true_revenue"],
            2,
        )
        totals["confirmed_true_revenue"] = totals["confirmed_true_revenue_total"]
        totals["true_revenue"] = totals["confirmed_true_revenue_total"]
        totals["confirmed_true_revenue_count"] += revenue_counts["true_revenue"]
        totals["potential_revenue_total"] = round(
            totals["potential_revenue_total"] + revenue_totals["potential_revenue"],
            2,
        )
        totals["potential_revenue_count"] += revenue_counts["potential_revenue"]
        totals["non_revenue_total"] = round(
            totals["non_revenue_total"] + revenue_totals["non_revenue"],
            2,
        )
        totals["non_revenue_count"] += revenue_counts["non_revenue"]
        totals["total_debits"] = round(totals["total_debits"] + debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + cash_flow, 2)
        totals["lender_debits"] = round(totals["lender_debits"] + lender_debits, 2)
        totals["lender_debit_count"] += lender_debit_count
        totals["potential_lender_debit_total"] = round(
            totals["potential_lender_debit_total"] + potential_lender_debit_total,
            2,
        )
        totals["potential_lender_debits"] = totals["potential_lender_debit_total"]
        totals["potential_lender_debit_count"] += potential_lender_debit_count
        totals["monthly_lender_debits"] = totals["lender_debits"]
        totals["insurance_count"] += insurance_count
        totals["insurance_total"] = round(totals["insurance_total"] + insurance_total, 2)
        totals["withholding_numerator"] = totals["lender_debits"]
        totals["potential_withholding_numerator"] = totals["potential_lender_debit_total"]
        totals["withholding_denominator"] = round(
            totals["withholding_denominator"] + eligible_deposits,
            2,
        )
        totals["potential_withholding_denominator"] = totals["withholding_denominator"]
        totals["nsf_count"] += nsf_count

        for match in detection.get("known_funders") or []:
            name = match.get("funder") or "Unknown"
            item = funders.setdefault(
                name,
                {"funder": name, "documents": 0, "total_debited": 0.0},
            )
            item["documents"] += 1
            match_debit_count = int(
                _num(match.get("debit_count"), len(match.get("transactions") or []))
            )
            if match_debit_count:
                item["debit_count"] = item.get("debit_count", 0) + match_debit_count
            item["total_debited"] = round(item["total_debited"] + _num(match.get("total_debited")), 2)
            package_funder_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )

        potential_matches_by_entity = {
            match.get("funder") or "Unknown candidate": match
            for match in detection.get("potential_lenders") or []
        }
        potential_rows_by_entity: dict[str, list[dict]] = {}
        for row in potential_lender_rows:
            classification = row["classification"]
            name = classification.get("canonical_entity") or "Unknown candidate"
            potential_rows_by_entity.setdefault(name, []).append(row)

        for name in sorted(set(potential_matches_by_entity) | set(potential_rows_by_entity)):
            match = potential_matches_by_entity.get(name) or {}
            entity_rows = potential_rows_by_entity.get(name) or []
            if entity_rows:
                match_count = len(entity_rows)
                match_total = round(
                    sum(abs(_num(row.get("amount"))) for row in entity_rows),
                    2,
                )
                match_transactions = entity_rows
                match_evidence = [row["classification"] for row in entity_rows]
            else:
                match_count = int(
                    _num(
                        match.get("potential_lender_debit_count"),
                        _num(match.get("debit_count"), len(match.get("transactions") or [])),
                    )
                )
                match_total = _num(
                    match.get("potential_lender_debit_total"),
                    _num(match.get("total_debited")),
                )
                match_transactions = match.get("transactions") or []
                match_evidence = match.get("evidence") or []
            match_exposure = (
                abs(match_total) / eligible_deposits * 100
                if eligible_deposits > 0
                else None
            )
            item = potential_lenders.setdefault(
                name,
                {
                    "funder": name,
                    "documents": 0,
                    "debit_count": 0,
                    "potential_lender_debit_count": 0,
                    "total_debited": 0.0,
                    "potential_lender_debit_total": 0.0,
                    "status": "review_required",
                    "review_required": True,
                },
            )
            item["documents"] += 1
            item["debit_count"] += match_count
            item["potential_lender_debit_count"] = item["debit_count"]
            item["total_debited"] = round(item["total_debited"] + match_total, 2)
            item["potential_lender_debit_total"] = item["total_debited"]
            package_potential_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "debit_count": match_count,
                    "potential_lender_debit_count": match_count,
                    "total_debited": round(match_total, 2),
                    "potential_lender_debit_total": round(match_total, 2),
                    "eligible_deposit_denominator": eligible_deposits,
                    "potential_withholding_exposure": match_exposure,
                    "transactions": match_transactions,
                    "evidence": match_evidence,
                    "status": "review_required",
                }
            )

        for match in detection.get("insurance_providers") or []:
            name = match.get("provider") or "Insurance provider not identified"
            item = insurance_providers.setdefault(
                name,
                {"provider": name, "documents": 0, "count": 0, "total_debited": 0.0},
            )
            item["documents"] += 1
            item["count"] += int(_num(match.get("count"), 0.0))
            item["total_debited"] = round(
                item["total_debited"] + _num(match.get("total_debited")),
                2,
            )
            package_insurance_matches.append(
                {
                    "provider": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )

        # Flattened ledger so the dashboard can show every statement's rows at once.
        for tx in statement_transactions:
            package_transaction = {
                **tx,
                "source_job": job.id,
                "source_document": job.filename,
                "source_bank": statement.get("bank"),
                "source_period_start": statement.get("period_start"),
                "source_period_end": statement.get("period_end"),
            }
            package_transactions.append(package_transaction)
            classification = tx.get("classification") or {}
            evidence = {
                **classification,
                "source_job": job.id,
                "source_document": job.filename,
            }
            if classification.get("contributes_to_withholding_rate") is True:
                package_lender_evidence.append(evidence)
            if _contributes_to_potential_totals(classification):
                package_potential_lender_evidence.append(evidence)
            if classification.get("contributes_to_insurance_totals") is True:
                package_insurance_evidence.append(evidence)
            revenue_state = classification.get("revenue_classification")
            if revenue_state in REVENUE_STATES and _num(tx.get("amount")) > 0:
                package_revenue_evidence[revenue_state].append(evidence)

        doc_row = {
            "id": job.id,
            "filename": job.filename,
            "status": job.status,
            "analysis_error": job.analysis_error,
            "error": job.error,
            "bank": statement.get("bank"),
            "account": statement.get("account_number"),
            "period_start": statement.get("period_start"),
            "period_end": statement.get("period_end"),
            "quality": quality.get("level"),
            "corporate_use": corporate_use,
            "integrity_risk": integrity_risk,
            "reconciles": (analysis.get("reconciliation") or {}).get("ok"),
            "credits": credits,
            "total_posted_credits": posted_credit_total,
            "total_posted_credit_count": posted_credit_count,
            "confirmed_true_revenue_total": revenue_totals["true_revenue"],
            "confirmed_true_revenue_count": revenue_counts["true_revenue"],
            "potential_revenue_total": revenue_totals["potential_revenue"],
            "potential_revenue_count": revenue_counts["potential_revenue"],
            "non_revenue_total": revenue_totals["non_revenue"],
            "non_revenue_count": revenue_counts["non_revenue"],
            "maximum_revenue": round(
                revenue_totals["true_revenue"] + revenue_totals["potential_revenue"],
                2,
            ),
            "revenue_reconciles": round(sum(revenue_totals.values()), 2) == posted_credit_total,
            "debits": debits,
            "cash_flow": cash_flow,
            "average_balance": average_balance,
            "average_balance_source": average_balance_source,
            "adb_calendar_days": adb_calendar_days,
            "adb_validated": adb_validated,
            "nsf_count": nsf_count,
            "lender_debits": lender_debits,
            "lender_debit_count": lender_debit_count,
            "lenders_detected": int(_num(metrics.get("lenders_detected"), len(detection.get("known_funders") or []))),
            "potential_lenders_detected": int(_num(metrics.get("potential_lenders_detected"), len(detection.get("potential_lenders") or []))),
            "potential_lender_debit_count": potential_lender_debit_count,
            "potential_lender_debit_total": potential_lender_debit_total,
            "potential_lender_debits": potential_lender_debit_total,
            "insurance_count": insurance_count,
            "insurance_total": insurance_total,
            "withholding_rate": metrics.get("withholding_rate"),
            "withholding_numerator": lender_debits,
            "withholding_denominator": eligible_deposits,
            "withholding_review_required": bool(metrics.get("withholding_review_required")) or eligible_deposits <= 0,
            "withholding_denominator_mode": denominator_mode,
            "withholding_denominator_label": metrics.get("withholding_denominator_label") or "Legacy eligible deposits",
            "potential_withholding_exposure": metrics.get("potential_withholding_exposure"),
            "potential_withholding_numerator": potential_lender_debit_total,
            "potential_withholding_denominator": eligible_deposits,
            "potential_withholding_review_required": (
                bool(metrics.get("potential_withholding_review_required"))
                or potential_lender_debit_count > 0
            ),
        }
        documents.append(doc_row)
        if ready:
            monthly.append(doc_row)
            if average_balance_num == average_balance_num:
                average_balance_values.append(average_balance_num)
                days = (
                    int(adb_calendar_days)
                    if isinstance(adb_calendar_days, (int, float)) and adb_calendar_days
                    else _period_days(statement.get("period_start"), statement.get("period_end")) or 1
                )
                average_balance_weighted_sum += average_balance_num * days
                average_balance_weight += days

    months = max(1, len(monthly))
    # Days-weighted mean of the per-statement daily-balance averages: summing
    # every statement's daily balances and dividing by every calendar day.
    package_average_balance = None
    if average_balance_weight > 0:
        package_average_balance = round(average_balance_weighted_sum / average_balance_weight, 2)
    elif average_balance_values:
        package_average_balance = round(sum(average_balance_values) / len(average_balance_values), 2)
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
    totals["maximum_revenue"] = round(
        totals["confirmed_true_revenue_total"] + totals["potential_revenue_total"],
        2,
    )
    totals["revenue_classified_total"] = round(
        totals["confirmed_true_revenue_total"]
        + totals["potential_revenue_total"]
        + totals["non_revenue_total"],
        2,
    )
    totals["revenue_classified_count"] = (
        totals["confirmed_true_revenue_count"]
        + totals["potential_revenue_count"]
        + totals["non_revenue_count"]
    )
    totals["revenue_reconciliation_delta"] = round(
        totals["revenue_classified_total"] - totals["total_posted_credits"],
        2,
    )
    totals["revenue_reconciles"] = (
        totals["revenue_reconciliation_delta"] == 0.0
        and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
    )
    totals["revenue_review_required"] = totals["potential_revenue_count"] > 0
    package_withholding_raw = (
        abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
        if totals["withholding_denominator"] > 0
        else None
    )
    package_withholding = round(package_withholding_raw, 2) if package_withholding_raw is not None else None
    withholding_review_required = totals["withholding_denominator"] <= 0
    potential_withholding_raw = (
        abs(totals["potential_withholding_numerator"])
        / totals["potential_withholding_denominator"]
        * 100
        if totals["potential_withholding_denominator"] > 0
        else None
    )
    potential_withholding = (
        round(potential_withholding_raw, 2)
        if potential_withholding_raw is not None
        else None
    )
    potential_withholding_review_required = totals["potential_lender_debit_count"] > 0
    for item in potential_lenders.values():
        item["eligible_deposit_denominator"] = totals["potential_withholding_denominator"]
        item["potential_withholding_exposure"] = (
            abs(item["total_debited"]) / totals["potential_withholding_denominator"] * 100
            if totals["potential_withholding_denominator"] > 0
            else None
        )
        item["potential_withholding_formula"] = (
            "abs(potential_lender_debit_total) / eligible_deposits * 100"
        )
    decision = "approved"
    if (
        totals["failed"]
        or totals["integrity_high"]
        or totals["manual_review"]
        or potential_withholding_review_required
        or totals["revenue_review_required"]
        or not totals["revenue_reconciles"]
    ):
        decision = "review_required"
    elif totals["summary_only"] or totals["integrity_review"]:
        decision = "limited_review"

    return {
        "totals": {
            **totals,
            "months": months,
            "avg_monthly_credits": round(totals["total_credits"] / months, 2),
            "avg_monthly_debits": round(totals["total_debits"] / months, 2),
            "avg_monthly_cash_flow": round(totals["cash_flow"] / months, 2),
            "average_daily_balance": package_average_balance,
            "package_withholding_rate": package_withholding,
            "package_withholding_rate_raw": package_withholding_raw,
            "eligible_deposits": totals["withholding_denominator"],
            "withholding_formula": "abs(total_qualifying_lender_debits) / eligible_deposits * 100",
            "withholding_review_required": withholding_review_required,
            "potential_withholding_exposure": potential_withholding,
            "potential_withholding_exposure_raw": potential_withholding_raw,
            "potential_withholding_formula": "abs(potential_lender_debit_total) / eligible_deposits * 100",
            "potential_withholding_review_required": potential_withholding_review_required,
            "decision": decision,
            "withholding_denominator_mode": (
                next(iter(denominator_modes)) if len(denominator_modes) == 1 else "mixed"
            ),
            "withholding_denominator_label": (
                "Confirmed true revenue"
                if denominator_modes == {"confirmed_true_revenue"}
                else "Legacy eligible deposits"
                if denominator_modes == {"legacy_eligible_deposits"}
                else "Mixed denominator configuration"
            ),
        },
        "documents": documents,
        "monthly": sorted(monthly, key=lambda r: (r.get("period_end") or "", r.get("filename") or "")),
        "funders": sorted(funders.values(), key=lambda r: r["total_debited"], reverse=True),
        "potential_lenders": sorted(potential_lenders.values(), key=lambda r: r["funder"]),
        "insurance_providers": sorted(
            insurance_providers.values(),
            key=lambda r: r["total_debited"],
            reverse=True,
        ),
        "transactions": package_transactions,
        "lender_evidence": package_lender_evidence,
        "potential_lender_evidence": package_potential_lender_evidence,
        "insurance_evidence": package_insurance_evidence,
        "true_revenue_evidence": package_revenue_evidence["true_revenue"],
        "potential_revenue_evidence": package_revenue_evidence["potential_revenue"],
        "non_revenue_evidence": package_revenue_evidence["non_revenue"],
        "detection": {
            "known_funders": package_funder_matches,
            "potential_lenders": package_potential_matches,
            "insurance_providers": package_insurance_matches,
            "lender_evidence": package_lender_evidence,
            "potential_lender_evidence": package_potential_lender_evidence,
            "insurance_evidence": package_insurance_evidence,
            "true_revenue_evidence": package_revenue_evidence["true_revenue"],
            "potential_revenue_evidence": package_revenue_evidence["potential_revenue"],
            "non_revenue_evidence": package_revenue_evidence["non_revenue"],
        },
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400
    force_ocr = request.form.get("force_ocr") == "1"
    parse_mode = request.form.get("parse_mode") or "auto"
    if parse_mode not in {"auto", "deterministic"}:
        return jsonify({"error": "invalid parse_mode"}), 400

    jobs = []
    for f in files:
        pdf_bytes = f.read()
        job = store.create(f.filename)
        job.pdf_bytes = pdf_bytes
        job.force_ocr = force_ocr
        job.parse_mode = parse_mode
        try:
            job.page_count = pdf_page_count(pdf_bytes)
        except Exception:
            job.page_count = 0
        _enqueue_job(job.id, pdf_bytes, f.filename, force_ocr, parse_mode)
        jobs.append({
            "id": job.id,
            "filename": job.filename,
            "page_count": job.page_count,
            "force_ocr": force_ocr,
            "parse_mode": parse_mode,
        })
    return jsonify({"jobs": jobs})


@app.route("/status/<job_id>")
def status(job_id):
    job = store.get(job_id)
    if job is None:
        abort(404)
    return jsonify({
        "status": job.status,
        "stage": job.stage,
        "error": job.error,
        "page_count": job.page_count,
        "analysis_ready": job.analysis is not None,
        "analysis_error": job.analysis_error,
        "parse_model": job.parse_model,
        "force_ocr": job.force_ocr,
        "parse_mode": job.parse_mode,
    })


@app.route("/live/<job_id>")
def live(job_id):
    job = store.get(job_id)
    if job is None:
        abort(404)
    return jsonify({"status": job.status, "live_text": job.live_text, "error": job.error})


@app.route("/rendered_skeleton")
def rendered_skeleton_route():
    # Static styled shell loaded once into the viewer iframe for live rendering.
    return Response(rendered_skeleton(), mimetype="text/html; charset=utf-8")


@app.route("/render/<job_id>")
def render(job_id):
    """Render the current (possibly partial) OCR output to an HTML body fragment
    where each detected region is wrapped in a colored, labeled box — mirroring
    the demo's rendered-with-boxes view — so the Rendered panel fills in live as
    pages stream. When the job is done, page images are rasterized so picture
    regions (e.g. check scans) embed their crop; during live they show a box."""
    job = store.get(job_id)
    if job is None:
        abort(404)
    pages = store.pages_live_ordered(job_id)
    page_images = None
    if job.status == "done" and job.pdf_bytes is not None:
        try:
            page_images = [rasterize_page(job.pdf_bytes, i, dpi=200)
                           for i in range(len(pages))]
        except Exception:
            page_images = None  # degrade to boxes-without-crops rather than 500
    return jsonify({"status": job.status, "fragment": render_boxed(pages, page_images)})


@app.route("/markdown/<job_id>")
def markdown(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return Response(job.markdown, mimetype="text/plain; charset=utf-8")


@app.route("/analysis/<job_id>")
def analysis(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return jsonify({
        "analysis": job.analysis,
        "analysis_error": job.analysis_error,
    })


@app.route("/analysis/<job_id>/revenue-review", methods=["POST"])
def revenue_review(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done" or job.analysis is None:
        abort(404)
    payload = request.get_json(silent=True) or {}
    source_location = str(payload.get("source_location") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    if not source_location:
        return jsonify({"error": "source_location is required"}), 400
    try:
        updated = apply_serialized_revenue_review(
            deepcopy(job.analysis),
            source_location=source_location,
            decision=decision,
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    stored = store.replace_analysis(job_id, updated)
    if stored is None:
        abort(404)
    return jsonify({"analysis": stored})


@app.route("/package_analysis")
def package_analysis():
    package = _package_from_request()
    if isinstance(package, tuple):
        return package
    return jsonify(package)


def _package_from_request():
    ids = [item for item in (request.args.get("ids") or "").split(",") if item]
    if not ids:
        return jsonify({"error": "no job ids supplied"}), 400
    jobs = []
    missing = []
    for job_id in ids:
        job = store.get(job_id)
        if job is None:
            missing.append(job_id)
        else:
            jobs.append(job)
    if missing:
        return jsonify({"error": "unknown job ids", "missing": missing}), 404
    return _package_analysis(jobs)


@app.route("/package_download/<fmt>")
def package_download(fmt):
    if fmt not in ("json", "csv", "xlsx"):
        abort(400)
    package = _package_from_request()
    if isinstance(package, tuple):
        return package
    if fmt == "json":
        content = json.dumps(package, indent=2)
        mimetype = "application/json"
        suffix = "json"
    elif fmt == "csv":
        content = _package_csv(package)
        mimetype = "text/csv"
        suffix = "csv"
    else:
        content = _package_xlsx(package)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        suffix = "xlsx"
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename=bank-statement-package.{suffix}"},
    )


@app.route("/page/<job_id>/<int:n>")
def page(job_id, n):
    job = store.get(job_id)
    if job is None or job.pdf_bytes is None or n < 0 or n >= job.page_count:
        abort(404)
    image = rasterize_page(job.pdf_bytes, n, dpi=100)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/result/<job_id>")
def result(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return job.html


@app.route("/download/<job_id>/<fmt>")
def download(job_id, fmt):
    if fmt not in ("md", "html", "json", "csv", "xlsx"):
        abort(400)
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    if fmt == "json":
        if job.analysis is None:
            abort(404)
        content = json.dumps(job.analysis, indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = _analysis_csv(job.analysis)
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = _analysis_xlsx(job.analysis)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = job.markdown if fmt == "md" else job.html
        mimetype = "text/markdown" if fmt == "md" else "text/html"
    base_name = job.filename.rsplit(".", 1)[0]
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.{fmt}"'},
    )


if __name__ == "__main__":
    app.run(debug=True)
