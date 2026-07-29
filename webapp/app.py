from __future__ import annotations
import io
import csv
import json
import threading
import zipfile
from collections import deque
from datetime import UTC, date, datetime
from flask import Flask, request, jsonify, render_template, Response, abort

from ocr.rasterize import pdf_page_count, rasterize_page
from ocr.render import rendered_skeleton, render_boxed
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
        "total_debits": 0.0,
        "cash_flow": 0.0,
        "lender_debits": 0.0,
        "monthly_lender_debits": 0.0,
        "nsf_count": 0,
    }

    funders: dict[str, dict] = {}
    package_transactions: list[dict] = []
    package_funder_matches: list[dict] = []
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
        lender_debits = _num(metrics.get("lender_debits"))
        monthly_lender_debits = _num(metrics.get("monthly_lender_debits"))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
        average_balance = metrics.get("average_balance")
        average_balance_num = _num(average_balance, default=float("nan"))
        average_balance_source = metrics.get("average_balance_source")
        adb_calendar_days = metrics.get("calendar_day_count")
        adb_validated = metrics.get("adb_ok")

        totals["total_credits"] = round(totals["total_credits"] + credits, 2)
        totals["total_debits"] = round(totals["total_debits"] + debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + cash_flow, 2)
        totals["lender_debits"] = round(totals["lender_debits"] + lender_debits, 2)
        totals["monthly_lender_debits"] = round(totals["monthly_lender_debits"] + monthly_lender_debits, 2)
        totals["nsf_count"] += nsf_count

        for match in detection.get("known_funders") or []:
            name = match.get("funder") or "Unknown"
            item = funders.setdefault(name, {"funder": name, "documents": 0, "total_debited": 0.0})
            item["documents"] += 1
            item["total_debited"] = round(item["total_debited"] + _num(match.get("total_debited")), 2)
            package_funder_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                }
            )

        # Flattened ledger so the dashboard can show every statement's rows at once.
        for tx in statement.get("transactions") or []:
            if not isinstance(tx, dict):
                continue
            package_transactions.append(
                {
                    **tx,
                    "source_job": job.id,
                    "source_document": job.filename,
                    "source_bank": statement.get("bank"),
                    "source_period_start": statement.get("period_start"),
                    "source_period_end": statement.get("period_end"),
                }
            )

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
            "debits": debits,
            "cash_flow": cash_flow,
            "average_balance": average_balance,
            "average_balance_source": average_balance_source,
            "adb_calendar_days": adb_calendar_days,
            "adb_validated": adb_validated,
            "nsf_count": nsf_count,
            "lender_debits": lender_debits,
            "withholding_rate": metrics.get("withholding_rate"),
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
    total_revenue = totals["total_credits"]
    package_withholding = (
        round((totals["monthly_lender_debits"] / total_revenue) * 100, 2)
        if total_revenue > 0 and totals["monthly_lender_debits"] > 0
        else None
    )
    decision = "approved"
    if totals["failed"] or totals["integrity_high"] or totals["manual_review"]:
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
            "decision": decision,
        },
        "documents": documents,
        "monthly": sorted(monthly, key=lambda r: (r.get("period_end") or "", r.get("filename") or "")),
        "funders": sorted(funders.values(), key=lambda r: r["total_debited"], reverse=True),
        "transactions": package_transactions,
        "detection": {"known_funders": package_funder_matches},
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
