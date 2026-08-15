from __future__ import annotations
import io
import csv
import json
import os
import re
import threading
import zipfile
from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from flask import Flask, request, jsonify, render_template, Response, abort
from werkzeug.exceptions import RequestEntityTooLarge

from ocr.inspect import inspect_pdf
from ocr.rasterize import pdf_page_count, rasterize_page
from ocr.render import rendered_skeleton, render_boxed
from analysis.revenue import (
    apply_serialized_revenue_review,
    normalize_withholding_denominator_mode,
    REVENUE_STATES,
)
from .jobs import JobStore
from .worker import run_job

# Upload ceilings. Every value here is enforced server-side and mirrored in the
# dropzone caption, so what the operator is told is what the server does.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_FILES = 25
MAX_UPLOAD_PAGES = 500

# waitress worker threads. The dashboard polls /status, /live and /render for
# every in-flight job at once, so the stock four would head-of-line block.
SERVER_THREADS = 16

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
# Durable store (D-1): SQLite + on-disk PDFs under WEBAPP_DATA_DIR
# (default `webapp_data/` at repo root). See webapp/storage.py for the
# single-writer concurrency contract.
store = JobStore()

# Startup re-hydration: any job left queued/processing by a previous process
# is explicitly marked `interrupted` with an explanatory error — never
# silently lost. Completed jobs need nothing: their artifacts already serve
# from storage. (Auto-resume is deliberately not attempted: the one-worker
# queue holds no durable claim on partially processed OCR state, so a clean,
# explicit interruption the analyst can see beats a half-blind retry.)
_INTERRUPTED_ON_STARTUP: list[str] = store.mark_interrupted()

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


# Every payload key that carries the account number as printed. `account` is
# what the transaction classifier stamps onto each classification record;
# `account_number` is the statement field and the package document column.
_ACCOUNT_KEYS = frozenset({"account", "account_number"})


def _mask_account(value: object) -> str | None:
    """Last four digits only — `****1234`. Applied at the webapp boundary and
    nowhere else: `analysis/serialization.py` keeps emitting the number as
    printed, because the CLI and the forensic oracles reconcile against it."""
    if value is None:
        return None
    text = str(value)
    if not text.strip():
        return None
    digits = "".join(character for character in text if character.isdigit())
    return "****" + digits[-4:]


def _masked(payload: object) -> object:
    """A masked copy of a served payload. Copies rather than mutates — the job
    store holds the analyst's authoritative record and must not be rewritten by
    the act of serving it."""
    if isinstance(payload, dict):
        return {
            key: _mask_account(value)
            if key in _ACCOUNT_KEYS and not isinstance(value, (dict, list))
            else _masked(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_masked(item) for item in payload]
    return payload


_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


# Money-shaped only. `float()` would also accept "-nan" and "+inf", which a
# spreadsheet reads as the start of a formula rather than as a number.
_NUMERIC_CELL = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _escape_formula(value: object) -> object:
    """Neutralize a spreadsheet formula-injection cell by prefixing an
    apostrophe, which Excel and LibreOffice both read as "this is text".

    Negative money (`-1234.56`) parses as a number in both, so it is left
    alone — escaping it would turn every debit in the export into a string and
    break the underwriter's arithmetic to defend against nothing."""
    if not isinstance(value, str) or not value.startswith(_FORMULA_LEAD):
        return value
    if _NUMERIC_CELL.match(value):
        return value
    return "'" + value


def _escaped_rows(rows: list[tuple[str, str, object]]) -> list[tuple]:
    return [tuple(_escape_formula(cell) for cell in row) for row in rows]


_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_download_name(name: object) -> str:
    """Whitelist-sanitize a base name for `Content-Disposition`. The uploaded
    filename is attacker-supplied, so quotes, CR/LF and path separators must
    never reach the header."""
    base = _UNSAFE_NAME.sub("_", str(name or ""))[:100]
    return base if base.strip("._-") else "download"


def _adb_rows(metrics: dict) -> list[tuple[str, str, object]]:
    """The Average Daily Balance working, one row per calendar day, so an
    underwriter can re-add the column in a spreadsheet and land on the same
    figure. Kept out of the flattened `metrics` section, where the whole daily
    ledger would collapse into a single unreadable JSON cell."""
    adb = metrics.get("adb")
    if not isinstance(adb, dict):
        return []
    validated = (
        metrics.get("adb_ok") is True
        and metrics.get("average_daily_balance") is not None
        and adb.get("ok") is True
    )
    rows: list[tuple[str, str, object]] = []
    for key in (
        "period_start", "period_end", "calendar_day_count",
        "opening_balance", "opening_balance_source", "closing_balance",
        "computed_closing_balance", "total_credits", "total_debits",
        "ok", "reconciled",
    ):
        item = adb.get(key)
        rows.append(("adb", key, "" if item is None else item))
    if validated:
        rows.append(("adb", "daily_balance_sum", adb.get("daily_balance_sum", "")))
    for name, passed in (adb.get("validations") or {}).items():
        rows.append(("adb_validation", name, "pass" if passed else "FAIL"))
    for warning in adb.get("warnings") or []:
        rows.append(("adb_warning", "", warning))
    if validated:
        for day in adb.get("daily_balances") or []:
            rows.append(("adb_daily_balance", day.get("date", ""), day.get("ending_balance", "")))
    return rows


#: Payload keys that exist for API compatibility and must NOT be flattened into
#: the analyst-facing exports.
#:
#: `statement.stated_average_balance` is the deprecated alias of
#: `statement.bank_reported_average_balance` and carries the identical number.
#: It stays in the JSON payload, where a consumer of the old name would
#: otherwise break — that is the whole point of the alias. A CSV or XLSX sheet
#: is not that contract: it is a flat sheet a human reads, and printing the
#: bank's figure on three rows (statement canonical, statement alias, metrics
#: echo) reads as an extraction fault rather than as a compatibility shim. The
#: canonical row and the long-standing `metrics` echo both remain, so nothing
#: an analyst needs is lost and no reader has to work out which of three
#: identical numbers is authoritative.
_EXPORT_SUPPRESSED_KEYS = {("statement", "stated_average_balance")}


def _analysis_rows(analysis: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    for section in ("statement", "metrics", "quality", "integrity", "reconciliation"):
        value = analysis.get(section)
        if isinstance(value, dict):
            for key, item in value.items():
                if (section, key) in _EXPORT_SUPPRESSED_KEYS:
                    continue
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
    writer.writerows(_escaped_rows(_analysis_rows(analysis)))
    return buf.getvalue()


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        rows.append(("totals", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            rows.append((f"document_{idx}", key, "" if value is None else value))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
    for idx, duplicate in enumerate(package.get("duplicates") or [], start=1):
        for key, value in duplicate.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"duplicate_{idx}", key, "" if value is None else value))
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
    writer.writerows(_escaped_rows(_package_rows(package)))
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
    rows = _escaped_rows(rows)
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


def _package_duplicates(jobs) -> tuple[dict[str, str], list[dict]]:
    """Members of a package that repeat an EARLIER member's content hash.

    D-3 surfacing. A package that lists the same statement twice double-counts
    every figure derived from it, so the payload says so explicitly rather
    than leaving an underwriter to notice two identical rows. Detection is by
    the O-1 content hash only: a job created without PDF bytes has no hash and
    is never guessed to duplicate another such job. Returns
    ``({duplicate_job_id: first_job_id}, [group, ...])``.
    """
    first_by_hash: dict[str, object] = {}
    duplicate_of: dict[str, str] = {}
    groups: dict[str, dict] = {}
    for job in jobs:
        content_hash = getattr(job, "content_sha256", None)
        if not content_hash:
            continue
        first = first_by_hash.get(content_hash)
        if first is None:
            first_by_hash[content_hash] = job
            continue
        duplicate_of[job.id] = first.id
        group = groups.setdefault(
            content_hash,
            {
                "content_sha256": content_hash,
                "job_ids": [first.id],
                "filenames": [first.filename],
                "count": 1,
            },
        )
        group["job_ids"].append(job.id)
        group["filenames"].append(job.filename)
        group["count"] += 1
    return duplicate_of, [groups[key] for key in sorted(groups)]


def _package_analysis(jobs) -> dict:
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
    documents = []
    monthly = []
    adb_weighted_sum = Decimal("0")
    adb_weight = 0
    totals = {
        "documents": len(jobs),
        # D-3: duplicate content inside one package, surfaced explicitly.
        "duplicate_documents": len(duplicate_of),
        "distinct_documents": len(jobs) - len(duplicate_of),
        "has_duplicate_documents": bool(duplicate_of),
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
        "verified_revenue_total": 0.0,
        "verified_revenue_count": 0,
        "unverified_deposit_total": 0.0,
        "unverified_deposit_count": 0,
        "non_revenue_total": 0.0,
        "non_revenue_count": 0,
        # Deprecated aliases for version 3.0 API consumers.
        "true_revenue": 0.0,
        "confirmed_true_revenue": 0.0,
        "confirmed_true_revenue_total": 0.0,
        "confirmed_true_revenue_count": 0,
        "potential_revenue_total": 0.0,
        "potential_revenue_count": 0,
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
        elif authoritative_rows:
            # A partially classified new report fails reconciliation closed.
            # Valid state rows remain visible as evidence, while every positive
            # row still remains in the posted-credit side of the equation.
            incomplete_posted_rows = [
                transaction
                for transaction in positive_statement_rows
                if not isinstance(transaction.get("classification"), dict)
                or transaction["classification"].get("is_posted") is not False
            ]
            posted_credit_total = round(
                sum(_num(row.get("amount")) for row in incomplete_posted_rows),
                2,
            )
            posted_credit_count = len(incomplete_posted_rows)
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
            verified_fallback = _num(
                metrics.get("verified_revenue_total"),
                _num(
                    metrics.get("confirmed_true_revenue_total"),
                    _num(metrics.get("true_revenue"), posted_credit_total),
                ),
            )
            revenue_totals = {
                "verified_revenue": verified_fallback,
                "unverified_deposit": _num(
                    metrics.get("unverified_deposit_total"),
                    _num(metrics.get("potential_revenue_total")),
                ),
                "non_revenue": _num(metrics.get("non_revenue_total")),
            }
            revenue_counts = {
                "verified_revenue": int(
                    _num(
                        metrics.get("verified_revenue_count"),
                        _num(metrics.get("confirmed_true_revenue_count")),
                    )
                ),
                "unverified_deposit": int(
                    _num(
                        metrics.get("unverified_deposit_count"),
                        _num(metrics.get("potential_revenue_count")),
                    )
                ),
                "non_revenue": int(_num(metrics.get("non_revenue_count"))),
            }
        eligible_deposits = _num(
            metrics.get("withholding_denominator"),
            _num(metrics.get("true_revenue"), credits),
        )
        denominator_mode = normalize_withholding_denominator_mode(
            metrics.get("withholding_denominator_mode")
        )
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
        adb_calendar_days = metrics.get("calendar_day_count")
        average_daily_balance_num = _num(
            metrics.get("average_daily_balance"),
            default=float("nan"),
        )
        adb_validated = (
            metrics.get("adb_ok") is True
            and isfinite(average_daily_balance_num)
            and isinstance(adb_calendar_days, int)
            and not isinstance(adb_calendar_days, bool)
            and adb_calendar_days > 0
        )
        average_daily_balance = (
            metrics.get("average_daily_balance") if adb_validated else None
        )

        totals["total_credits"] = round(totals["total_credits"] + credits, 2)
        totals["total_posted_credits"] = round(
            totals["total_posted_credits"] + posted_credit_total,
            2,
        )
        totals["total_posted_credit_count"] += posted_credit_count
        totals["verified_revenue_total"] = round(
            totals["verified_revenue_total"] + revenue_totals["verified_revenue"],
            2,
        )
        totals["verified_revenue_count"] += revenue_counts["verified_revenue"]
        totals["unverified_deposit_total"] = round(
            totals["unverified_deposit_total"]
            + revenue_totals["unverified_deposit"],
            2,
        )
        totals["unverified_deposit_count"] += revenue_counts["unverified_deposit"]
        totals["confirmed_true_revenue_total"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue"] = totals["verified_revenue_total"]
        totals["true_revenue"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
        totals["potential_revenue_count"] = totals["unverified_deposit_count"]
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
            # D-3: the content identity of this member, and the earlier member
            # it repeats (None unless this exact content is already in the
            # package).
            "content_sha256": getattr(job, "content_sha256", None),
            "is_duplicate": job.id in duplicate_of,
            "duplicate_of": duplicate_of.get(job.id),
            "analysis_error": job.analysis_error,
            "error": job.error,
            "bank": statement.get("bank"),
            "account": statement.get("account_number"),
            "period_start": statement.get("period_start"),
            "period_end": statement.get("period_end"),
            "beginning_balance": statement.get("beginning_balance"),
            "ending_balance": statement.get("ending_balance"),
            "min_balance": metrics.get("min_balance"),
            "max_balance": metrics.get("max_balance"),
            "daily_balance_extrema_validated": adb_validated,
            "quality": quality.get("level"),
            "corporate_use": corporate_use,
            "integrity_risk": integrity_risk,
            "reconciles": (analysis.get("reconciliation") or {}).get("ok"),
            "credits": credits,
            "total_posted_credits": posted_credit_total,
            "total_posted_credit_count": posted_credit_count,
            "verified_revenue_total": revenue_totals["verified_revenue"],
            "verified_revenue_count": revenue_counts["verified_revenue"],
            "unverified_deposit_total": revenue_totals["unverified_deposit"],
            "unverified_deposit_count": revenue_counts["unverified_deposit"],
            "confirmed_true_revenue_total": revenue_totals["verified_revenue"],
            "confirmed_true_revenue_count": revenue_counts["verified_revenue"],
            "potential_revenue_total": revenue_totals["unverified_deposit"],
            "potential_revenue_count": revenue_counts["unverified_deposit"],
            "non_revenue_total": revenue_totals["non_revenue"],
            "non_revenue_count": revenue_counts["non_revenue"],
            "maximum_revenue": round(
                revenue_totals["verified_revenue"]
                + revenue_totals["unverified_deposit"],
                2,
            ),
            "revenue_reconciles": round(sum(revenue_totals.values()), 2) == posted_credit_total,
            "debits": debits,
            "cash_flow": cash_flow,
            "average_daily_balance": average_daily_balance,
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
            if adb_validated:
                adb_value = Decimal(str(average_daily_balance_num))
                adb_weighted_sum += adb_value * adb_calendar_days
                adb_weight += adb_calendar_days

    months = max(1, len(monthly))
    # Days-weighted mean of the per-statement daily-balance averages: summing
    # every statement's daily balances and dividing by every calendar day.
    package_average_daily_balance = None
    if adb_weight > 0:
        package_average_daily_balance = float(
            (adb_weighted_sum / adb_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
    totals["maximum_revenue"] = round(
        totals["verified_revenue_total"] + totals["unverified_deposit_total"],
        2,
    )
    totals["revenue_classified_total"] = round(
        totals["verified_revenue_total"]
        + totals["unverified_deposit_total"]
        + totals["non_revenue_total"],
        2,
    )
    totals["revenue_classified_count"] = (
        totals["verified_revenue_count"]
        + totals["unverified_deposit_count"]
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
    totals["revenue_review_required"] = totals["unverified_deposit_count"] > 0
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
            "average_daily_balance": package_average_daily_balance,
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
                "Verified revenue"
                if denominator_modes == {"verified_revenue"}
                else "Legacy eligible deposits"
                if denominator_modes == {"legacy_eligible_deposits"}
                else "Mixed denominator configuration"
            ),
        },
        "documents": documents,
        # D-3: one entry per content hash present more than once, listing every
        # member job that carries it (the first occurrence included).
        "duplicates": duplicate_groups,
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
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
        "true_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
        "non_revenue_evidence": package_revenue_evidence["non_revenue"],
        "detection": {
            "known_funders": package_funder_matches,
            "potential_lenders": package_potential_matches,
            "insurance_providers": package_insurance_matches,
            "lender_evidence": package_lender_evidence,
            "potential_lender_evidence": package_potential_lender_evidence,
            "insurance_evidence": package_insurance_evidence,
            "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
            "true_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
            "non_revenue_evidence": package_revenue_evidence["non_revenue"],
        },
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.errorhandler(RequestEntityTooLarge)
def _upload_too_large(_exc):
    """Flask aborts oversize requests before the view runs; the dashboard only
    ever parses JSON, so the stock HTML error page would surface as an opaque
    failure."""
    return jsonify({
        "error": f"upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB request limit",
    }), 413


def _checked_upload(filename: str, pdf_bytes: bytes) -> tuple[int | None, object, dict | None]:
    """Server-side gate for a single uploaded file. Returns
    (page_count, profile, error) with the error exclusive of the other two.

    Validation order and error shape are D-2a's; O-1 adds the preflight
    profile and rejects password-protected PDFs before any parsing —
    processing one could only ever fail later with a worse message."""
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        return None, None, {
            "error": f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            "filename": filename,
        }
    if not pdf_bytes.startswith(b"%PDF-"):
        return None, None, {"error": "file is not a PDF", "filename": filename}
    profile = inspect_pdf(pdf_bytes)
    if profile.encrypted:
        return None, None, {
            "error": "PDF is password-protected; upload a decrypted copy",
            "filename": filename,
        }
    try:
        page_count = pdf_page_count(pdf_bytes)
    except Exception:
        return None, None, {"error": "PDF could not be read", "filename": filename}
    if page_count > MAX_UPLOAD_PAGES:
        return None, None, {
            "error": f"PDF has {page_count} pages (limit {MAX_UPLOAD_PAGES})",
            "filename": filename,
        }
    return page_count, profile, None


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400
    if len(files) > MAX_UPLOAD_FILES:
        return jsonify({
            "error": f"{len(files)} files uploaded (limit {MAX_UPLOAD_FILES} per batch)",
        }), 400
    force_ocr = request.form.get("force_ocr") == "1"
    parse_mode = request.form.get("parse_mode") or "auto"
    if parse_mode not in {"auto", "deterministic"}:
        return jsonify({"error": "invalid parse_mode"}), 400

    # Validate the whole batch before creating any job. A half-accepted upload
    # would leave the dashboard aggregating an incomplete package with nothing
    # on screen to say a statement is missing.
    accepted: list[tuple[str, bytes, int, object]] = []
    for f in files:
        pdf_bytes = f.read()
        page_count, profile, error = _checked_upload(f.filename, pdf_bytes)
        if error is not None:
            return jsonify(error), 400
        accepted.append((f.filename, pdf_bytes, page_count, profile))

    jobs = []
    for filename, pdf_bytes, page_count, profile in accepted:
        # Records the document row (with content_sha256) and the job row, and
        # writes the PDF bytes to the disk store.
        job = store.create(
            filename,
            page_count=page_count,
            force_ocr=force_ocr,
            parse_mode=parse_mode,
            pdf_bytes=pdf_bytes,
        )
        # O-1: persist the preflight profile with the document row and flag a
        # re-upload of identical bytes (the earliest prior job with this hash).
        store.storage.set_document_profile(job.id, json.dumps(profile.to_dict()))
        duplicate_of = store.storage.duplicate_of(job.id)
        _enqueue_job(job.id, pdf_bytes, filename, force_ocr, parse_mode)
        jobs.append({
            "id": job.id,
            "filename": job.filename,
            "page_count": job.page_count,
            "force_ocr": force_ocr,
            "parse_mode": parse_mode,
            "content_sha256": job.content_sha256,
            "duplicate_of": duplicate_of,
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
        # O-1 additive surfacing: the document hash and, when these exact
        # bytes were uploaded before, the earliest prior job holding them.
        "content_sha256": job.content_sha256,
        "duplicate_of": (
            store.storage.duplicate_of(job_id) if job.content_sha256 else None
        ),
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
    if job.status == "done":
        # Disk-backed after completion: pdf_bytes is released from RAM when a
        # job finishes, so completed jobs rasterize from the PDF store.
        pdf_bytes = store.pdf_bytes(job_id)
        if pdf_bytes is not None:
            try:
                page_images = [rasterize_page(pdf_bytes, i, dpi=200)
                               for i in range(len(pages))]
            except Exception:
                page_images = None  # degrade to boxes-without-crops rather than 500
    return jsonify({"status": job.status, "fragment": render_boxed(pages, page_images)})


@app.route("/markdown/<job_id>")
def markdown(job_id):
    """RESIDUAL EXPOSURE (accepted, Wave 0): the raw OCR text still carries the
    account number exactly as printed, and so do /result and the md/html
    downloads. Masking is deliberately confined to the structured payloads;
    redacting the source view would destroy the evidence an underwriter checks
    a disputed figure against. Closing this needs authentication, which is
    D-2b — not redaction."""
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
        "analysis": _masked(job.analysis),
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
    # Free-text actor until authentication exists (D-2b); recorded with the
    # decision timestamp and the prior classification state in the same
    # storage transaction that persists the mutated analysis.
    actor = str(payload.get("actor") or "").strip() or "local-analyst"
    stored = store.apply_review(
        job_id,
        updated,
        source_location=source_location,
        decision=decision,
        actor=actor,
    )
    if stored is None:
        abort(404)
    return jsonify({"analysis": _masked(stored)})


@app.route("/package_analysis")
def package_analysis():
    package = _package_from_request()
    if isinstance(package, tuple):
        return package
    return jsonify(_masked(package))


def _requested_job_ids() -> tuple[list[str] | None, tuple | None]:
    """Resolve the request to an ordered job-id list.

    Accepts the durable form (`?package_id=<id>` minted by POST /package) and
    the original comma-separated form (`?ids=a,b,c`) unchanged. As a courtesy
    the ids slot also accepts a durable package id in place of a job id and
    expands it to the package's members."""
    package_id = (request.args.get("package_id") or "").strip()
    if package_id:
        member_ids = store.package_member_ids(package_id)
        if member_ids is None:
            return None, (jsonify({"error": "unknown package id", "missing": [package_id]}), 404)
        return member_ids, None
    tokens = [item for item in (request.args.get("ids") or "").split(",") if item]
    if not tokens:
        return None, (jsonify({"error": "no job ids supplied"}), 400)
    ids: list[str] = []
    missing: list[str] = []
    for token in tokens:
        if store.get(token) is not None:
            ids.append(token)
            continue
        member_ids = store.package_member_ids(token)
        if member_ids is None:
            missing.append(token)
        else:
            ids.extend(member_ids)
    if missing:
        return None, (jsonify({"error": "unknown job ids", "missing": missing}), 404)
    return ids, None


def _package_from_request():
    ids, error = _requested_job_ids()
    if error is not None:
        return error
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


@app.route("/package", methods=["POST"])
def create_package():
    """Mint a durable package id for an ordered set of completed-or-pending
    job ids. The comma-separated ids form keeps working unchanged; the id
    returned here can be used as `?package_id=` (or in the ids slot) and
    reproduces the same member set after a restart."""
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids")
    if isinstance(ids, str):
        ids = [item for item in ids.split(",") if item]
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "no job ids supplied"}), 400
    ids = [str(item) for item in ids]
    missing = [job_id for job_id in ids if store.get(job_id) is None]
    if missing:
        return jsonify({"error": "unknown job ids", "missing": missing}), 404
    reference = payload.get("reference")
    package_id = store.create_package(
        ids, reference=str(reference) if reference else None
    )
    return jsonify({"package_id": package_id, "ids": ids})


@app.route("/package_download/<fmt>")
def package_download(fmt):
    if fmt not in ("json", "csv", "xlsx"):
        abort(400)
    package = _package_from_request()
    if isinstance(package, tuple):
        return package
    package = _masked(package)
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
    store.record_export(
        package_id=(request.args.get("package_id") or "").strip() or None,
        detail={"format": fmt, "ids": request.args.get("ids") or None},
    )
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename=bank-statement-package.{suffix}"},
    )


@app.route("/page/<job_id>/<int:n>")
def page(job_id, n):
    job = store.get(job_id)
    if job is None or n < 0 or n >= job.page_count:
        abort(404)
    # In-memory bytes while the job is in flight; the disk store afterwards.
    pdf_bytes = store.pdf_bytes(job_id)
    if pdf_bytes is None:
        abort(404)
    image = rasterize_page(pdf_bytes, n, dpi=100)
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
        content = json.dumps(_masked(job.analysis), indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = _analysis_csv(_masked(job.analysis))
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = _analysis_xlsx(_masked(job.analysis))
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        # Raw OCR source, served verbatim: see the residual-exposure note on
        # /markdown. Masking the analyst's source view would corrupt it.
        content = job.markdown if fmt == "md" else job.html
        mimetype = "text/markdown" if fmt == "md" else "text/html"
    store.record_export(job_id=job_id, detail={"format": fmt})
    base_name = _safe_download_name(job.filename.rsplit(".", 1)[0])
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.{fmt}"'},
    )


def _server_config() -> tuple[str, int]:
    """Loopback by default. The app still has no authentication (that is D-2b),
    so exposing it beyond this machine has to be a deliberate act rather than
    the default anyone inherits."""
    host = os.environ.get("WEBAPP_HOST", "").strip() or "127.0.0.1"
    port = os.environ.get("WEBAPP_PORT", "").strip() or "5000"
    return host, int(port)


def main() -> None:
    """Serve through waitress. The Werkzeug development server is never used:
    its interactive debugger is arbitrary code execution for anyone who can
    reach the port, and it was previously enabled here with debug=True."""
    from waitress import serve

    host, port = _server_config()
    serve(app, host=host, port=port, threads=SERVER_THREADS)


if __name__ == "__main__":
    main()
