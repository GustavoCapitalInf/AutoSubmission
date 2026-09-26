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

from ocr.config import load_settings as load_ocr_settings
from ocr.inspect import inspect_pdf
from ocr.rasterize import pdf_page_count, rasterize_page
from ocr.render import rendered_skeleton, render_boxed
from analysis.payload_shape import (
    DOCUMENT_KEY as _DOCUMENT_KEY,
    account_content_digest,
    is_document_payload,
    payload_account_count,
    payload_accounts,
    payload_document_block,
)
from analysis.revenue import (
    apply_serialized_revenue_review,
    normalize_withholding_denominator_mode,
    REVENUE_STATES,
)
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.cadence import describe_cadence
from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from .jobs import JobStore
from .settings import DEFAULTS as SETTINGS_DEFAULTS, load_settings, save_settings
from .worker import run_job
from .reanalysis import replay_reviews, rerun_analysis

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


#: There is NO shutdown exemption on the re-arm, and the reason is measured
#: rather than assumed (#HYGIENE8 review MINOR-3). The first version of this
#: supervisor kept a `(SystemExit, KeyboardInterrupt)` vocabulary on the premise
#: that either escaping `run_job` meant "the process is going away". In a
#: worker thread neither does: `threading` hands both to the thread's
#: excepthook and the interpreter continues. A real Ctrl-C is delivered to the
#: MAIN thread, and a real `sys.exit` there ends the process — daemon workers
#: and all — without ever passing through this handler; a signal can reach the
#: worker thread only by being raised INSIDE it, by `run_job` or something it
#: called. On that path the process lives on, and a queue left with its work in
#: it would sit at `queued` with `error=None` until the next upload arrived and
#: its worker drained it: §PRIVACY3 P8.1's exact symptom on a narrower path. So
#: a thread-raised signal is a dead worker, not a dying process, and a dead
#: worker is replaced whatever killed it. `run_job`'s own `BaseException` arm
#: still re-raises rather than swallowing, so the thread still dies with its
#: traceback on stderr; nothing here inspects what escaped.


def _release_worker_slot() -> bool:
    """Hand the one worker slot back after a worker thread dies mid-job.

    #HYGIENE8 QUEUE-SUPERVISOR, closing the defect §PRIVACY3 P8.1 measured and
    carried. `_job_worker_active` is a claim on the single worker slot, and
    until this function existed the ONLY place that released it was the loop's
    own `return`. So when `run_job` unwound — which is exactly what its
    `BaseException` arm makes it do — the thread died holding the slot,
    `_enqueue_job` never started another worker, and every later upload sat at
    `queued` with `error=None` for the life of the process.

    Two things happen here and they are separate decisions:

    * **the slot is always released**, because a claim held by a thread that no
      longer exists is not a claim; and
    * **a replacement worker is started when there is queued work**, whatever
      killed the one that died (the note above says why no exception class is
      exempt). Releasing the flag alone would already un-strand every FUTURE
      upload; the re-arm is what rescues the documents that were already in the
      queue when the worker died, in a process where no further upload ever
      arrives.

    **The replacement claims the slot inside the same critical section that
    releases it** (#HYGIENE8 review MAJOR-1). The first version of this function
    set the flag `False` and then spawned the replacement with the flag LEFT
    `False`, so for the whole life of the replacement the module said no worker
    existed, the next upload started a second one, and two threads drained one
    queue — the single worker slot double-booked until both happened to exit.
    Both jobs still completed exactly once (every pop is under the lock), so
    the defect was of the SLOT and not of a job; but the slot is what keeps two
    OCR jobs from running at once on this host. The flag is therefore written
    ONCE here, to the re-arm decision itself: `True` exactly when a replacement
    is about to be started and `False` otherwise, under the lock `_enqueue_job`
    reads it under — the same claim-before-spawn order `_enqueue_job` keeps.

    The re-arm cannot spin: the replacement pops from the same queue under the
    same lock, and `run_job` marks the popped job `error` before it re-raises,
    so a failure that repeats for every document drains the queue one document
    per thread and stops. Nothing recurses — the dying thread starts the next
    one and then finishes unwinding.

    Returns whether a replacement was started, so a test can assert the
    decision rather than infer it from a race.
    """
    global _job_worker_active
    with _job_queue_lock:
        rearm = bool(_job_queue)
        _job_worker_active = rearm
    if rearm:
        threading.Thread(target=_process_job_queue, daemon=True).start()
    return rearm


def _process_job_queue() -> None:
    global _job_worker_active
    while True:
        with _job_queue_lock:
            if not _job_queue:
                _job_worker_active = False
                return
            job_id, pdf_bytes, filename, force_ocr, parse_mode = _job_queue.popleft()
        try:
            run_job(job_id, pdf_bytes, filename, store, force_ocr, parse_mode)
        except BaseException:
            # The handler is on the SUPERVISOR and not on `run_job`'s arm, which
            # is the whole shape §PRIVACY3 P8.1 argued for: the arm must keep
            # re-raising (swallowing a death is worse than a stranded queue),
            # so the slot has to be released by whoever owns it. Nothing is
            # swallowed here either — the `raise` below is bare, so the stderr
            # traceback and the thread's death are unchanged — and nothing is
            # inspected: the class of what escaped decides nothing (the note
            # above `_release_worker_slot`).
            _release_worker_slot()
            raise


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


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _displayed(
    analysis: object, *, carry_over: bool | None = None, settings: dict | None = None
) -> object:
    """A stored analysis as the dashboard presents it: the owner's Settings applied to a COPY.

    Two settings apply. The NSF basis (analysis/nsf_days.py): printed days by default, or every calendar day with
    the balance carried over inactive days when Settings turns carry-over on. And the flag groups
    (analysis/flagged_view.py): an unticked group is hidden from the summaries and its rows lose their flag.
    Every surface that shows or exports an analysis goes through here, so the dashboard, the downloads and the
    package agree; the stored record is never rewritten, and a change of setting applies to every job at once.

    `settings` is a snapshot of every setting, read here once when it is not passed; `carry_over`, when given,
    still decides the NSF basis."""
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    if carry_over is None:
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over)
    return apply_flagged_groups_to_payload(rebased, enabled=settings)


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
    """The flat export sheet for one published payload.

    A document carrying several accounts renders EVERY account, each under its
    own section prefix in printed order, with the document's own facts in a
    `document` section of their own. Measured before this teaching, the same
    call returned ZERO rows for a document payload: an underwriter would have
    downloaded an empty sheet for a statement that reconciled.

    The section prefix is what keeps two accounts apart. The flat sheet is
    keyed on `(section, field)`, so two accounts writing `("statement",
    "ending_balance")` would collide and one would silently win.
    """
    if is_document_payload(analysis):
        surface = "webapp/app.py::_analysis_rows"
        rows: list[tuple[str, str, object]] = []
        for key, item in payload_document_block(analysis, surface=surface).items():
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("document", key, "" if item is None else item))
        for index, account in enumerate(
            payload_accounts(analysis, surface=surface), start=1
        ):
            rows.extend(
                (f"account_{index}.{section}", field, value)
                for section, field, value in _account_analysis_rows(account)
            )
        return rows
    return _account_analysis_rows(analysis)


def _account_analysis_rows(analysis: dict) -> list[tuple[str, str, object]]:
    """One ACCOUNT's rows — today's sheet, unchanged."""
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
            if key == "flagged_positions":
                continue  # emitted as readable rows below
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
    return rows


def _flagged_position_rows(positions: object) -> list[tuple[str, str, object]]:
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited, the credits it paid in and their
    total (plan contract C5: a factor's payouts, owner ruling 2026-09-26), and the cadence.

    Served payloads hold only the ticked groups (analysis/flagged_view.py via `_displayed`), so the sheet follows
    Settings. A payee name is statement text: these rows reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    numbers: dict[str, int] = {}
    for entry in positions if isinstance(positions, list) else []:
        group = entry.get("group") if isinstance(entry, dict) else None
        if not isinstance(group, str) or group not in FLAG_GROUP_BY_KEY:
            continue
        numbers[group] = numbers.get(group, 0) + 1
        for field in ("payee", "count", "total_debited", "count_credited", "total_credited", "cadence"):
            value = entry.get(field)
            rows.append((f"flagged_{group}_{numbers[group]}", field, "" if value is None else value))
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
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
    # money cells and read them as missing data rather than as refused units.
    for key, value in (package.get("currency") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("currency", key, "" if value is None else value))
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
    # Lender detection §8.4: one section per flagged payee, `flagged_<group>_<n>`. The package holds only the
    # groups Settings ticks, so the sheet follows Settings.
    for group, items in (package.get("flagged_positions") or {}).items():
        for idx, item in enumerate(items, start=1):
            for key, value in item.items():
                rows.append((f"flagged_{group}_{idx}", key, "" if value is None else value))
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


def _counts_as_flagged(classification: dict, shown: frozenset[str]) -> bool:
    """A row the package's flag roll-up counts: the analysis marked it a contributing row of a flag group
    (`contributes_to_flagged_totals`: a posted debit, or a posted factoring credit, that is not a proven duplicate
    and not reversed; plan contract C4), and Settings ticks its group."""
    group = classification.get("flagged_group")
    return (
        classification.get("contributes_to_flagged_totals") is True
        and isinstance(group, str)
        and group in shown
    )


def _add_flagged_rows(rollup: dict[tuple[str, str], dict], rows: list[dict]) -> None:
    """Fold one member's counted flag rows into the package roll-up, keyed by (group, payee).

    The payee is the row's canonical entity, or its group's label when the analysis named none (plan contract
    C5). `documents` counts the members a payee appears in, as the funder roll-up does. A debit adds to `count`
    and `total_debited`; a credit (a factor's payout, owner ruling 2026-09-26) adds to `count_credited` and
    `total_credited`. The dates of both are kept so the first and last dates, and the cadence, are read across
    every member rather than per statement."""
    seen: set[tuple[str, str]] = set()
    for row in rows:
        classification = row["classification"]
        group = classification["flagged_group"]
        entity = classification.get("canonical_entity")
        payee = entity if isinstance(entity, str) and entity else FLAG_GROUP_BY_KEY[group].label
        item = rollup.setdefault(
            (group, payee),
            {"payee": payee, "documents": 0, "count": 0, "total_debited": 0.0, "count_credited": 0,
             "total_credited": 0.0, "dates": []},
        )
        if (group, payee) not in seen:
            seen.add((group, payee))
            item["documents"] += 1
        amount = _num(row.get("amount"))
        if amount < 0:
            item["count"] += 1
            item["total_debited"] = round(item["total_debited"] + abs(amount), 2)
        else:
            item["count_credited"] += 1
            item["total_credited"] = round(item["total_credited"] + amount, 2)
        posted = parse_date(row.get("date") or classification.get("date"))
        if posted is not None:
            item["dates"].append(posted)


def _published_flagged_positions(
    rollup: dict[tuple[str, str], dict], *, refuse_cross_currency: bool
) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, count_credited, total_credited, cadence,
    first_date, last_date}`. The cadence is read over the payee's dates in every member together
    (analysis/cadence.py), its debits and its credits alike, so a monthly payment split across monthly statements
    reads as monthly.

    Largest total first, debited plus credited; a package that refuses to combine currencies ranks by the
    unit-free count, debits plus credits, then the payee, because an order read off summed money would publish the
    cross-currency comparison the refusal withholds (CURRENCY DOCTRINE §F)."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "count_credited": item["count_credited"],
                "total_credited": item["total_credited"],
                "cadence": describe_cadence(dates)[0] if dates else None,
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
            })
        if not items:
            continue
        if refuse_cross_currency:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["count"] + item["count_credited"]), item["payee"])
            )
        else:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["total_debited"] + item["total_credited"]), item["payee"])
            )
    return published


#: Package totals that carry money, or that divide one money figure by another.
#: Adding or dividing these across statements denominated in different
#: currencies is a unit error — `30,000 CAD + 20,000 USD != 50,000 package ADB`
#: (CURRENCY DOCTRINE §F) — so a package that is not PROVEN single-currency
#: publishes every one of them as None.
#:
#: None is this payload's established "not computable" value: an unvalidated ADB
#: already travels that way (`analysis/serialization.py::_metrics_dict`), the
#: CSV/XLSX writers already render it as an empty cell, and the dashboard's
#: `formatMoney` already renders it "N/A". A silent zero would read as "the
#: package moved no money" and a converted figure would be fabricated evidence;
#: the doctrine forbids both, so refusal is the only honest shape.
#: The published figures whose denominator is a count of MEMBERS. Two accounts
#: of one document are one period of banking and two members, so every one of
#: these is wrong by exactly that factor unless the package refuses it
#: (design §6.5's fourth bullet; the L1-S3 review measured the halving).
_PER_PERIOD_AVERAGE_KEYS = frozenset({
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    "monthly_lender_debits",
})

_CROSS_CURRENCY_TOTAL_KEYS = frozenset({
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    "cash_flow",
    "confirmed_true_revenue",
    "confirmed_true_revenue_total",
    "eligible_deposits",
    "flagged_position_total",
    "flagged_position_total_credited",
    "insurance_total",
    "lender_debits",
    "maximum_revenue",
    "monthly_lender_debits",
    "non_revenue_total",
    "package_withholding_rate",
    "package_withholding_rate_raw",
    "potential_lender_debit_total",
    "potential_lender_debits",
    "potential_revenue_total",
    "potential_withholding_denominator",
    "potential_withholding_exposure",
    "potential_withholding_exposure_raw",
    "potential_withholding_numerator",
    "revenue_classified_total",
    "revenue_reconciliation_delta",
    "total_credits",
    "total_debits",
    "total_posted_credits",
    "true_revenue",
    "unverified_deposit_total",
    "verified_revenue_total",
    "withholding_denominator",
    "withholding_numerator",
})

#: The same rule for the cross-document funder / potential-lender / insurance
#: rollups, whose money is summed across the package exactly like a total.
#:
#: `potential_lender_debit_total` is the DEPRECATED ALIAS of `total_debited` on
#: a potential-lender rollup — `_package_analysis` assigns one from the other —
#: so it has to be refused with it. Leaving it out let a mixed-unit number
#: survive into the JSON, the CSV, the XLSX and the dashboard, where
#: `lenderRowHtml`'s `potential_lender_debit_total ?? total_debited` accessor
#: reads the alias FIRST and would have defeated the refusal at exactly the
#: place it was designed to bite. Every money key on these rollups belongs
#: here; everything left on them is a genuine count.
_CROSS_CURRENCY_ROLLUP_KEYS = (
    "total_debited",
    "total_credited",
    "potential_lender_debit_total",
    "eligible_deposit_denominator",
    "potential_withholding_exposure",
)


def _statement_currency(analysis: dict) -> str | None:
    """The ISO code this member's statement is denominated in, or None when the
    document does not declare one.

    `analysis/schema.py` gives `Statement.currency` a non-null default, so every
    payload the current pipeline produces carries a code. None here therefore
    means a payload that predates the field or never came from `Statement` at
    all — a genuine unknown, which CURRENCY DOCTRINE §B resolves by failing
    closed rather than by forcing a currency onto it.

    Case and surrounding blanks are folded away: ISO 4217 codes are uppercase,
    so `usd` is a spelling of USD rather than a second unit, and refusing a
    package over a spelling would be a false refusal, not a safe one.
    """
    statement = analysis.get("statement")
    if not isinstance(statement, dict):
        return None
    code = statement.get("currency")
    if not isinstance(code, str):
        return None
    return code.strip().upper() or None


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


def _ratified_omissions(analysis: object) -> list[dict]:
    """The RATIFIED sibling omissions this document published, if it is one.

    Q10 (Gustavo, 2026-08-30 — BATCH9_TRANSITION §8.7): *surface the omission,
    do not demote.* A section admitted as omitted on PRINTED evidence beside an
    account that validated independently leaves the document `validated`; what
    it must never do is disappear. So the package — which is where a person
    reads a member's figures as though they were the member's whole banking —
    says that a section of one of its documents was established and not
    published.

    An omission whose reason is NOT a ratified class is not surfaced here: it
    is a publisher defect, `classify_document` already fails the document for
    it, and reporting a defect as "partial" would dress it as a policy.
    """
    from telemetry.record import RATIFIED_OMISSION_REASONS

    # BOTH shapes. Since L1-S4 a SINGLE-account document that surfaced an
    # omission publishes a `document` block beside today's payload, and the
    # fifteen protected carriers of W3 §L1S2 are exactly that shape — so
    # gating this on `accounts` would have kept Q10's surface dark on every
    # document the ruling was made about.
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY)
    omissions = (block or {}).get("omitted_sections") or []
    return [
        omission for omission in omissions
        if isinstance(omission, dict)
        and omission.get("reason") in RATIFIED_OMISSION_REASONS
    ]


def _unratified_omissions(analysis: object) -> list[dict]:
    """The omissions whose reason is not a ratified class — a publisher defect.

    A document carrying one is `failed` at `classify_document`, so none of its
    accounts may enter a package: a member contributing money out of a document
    the platform failed would be a total nobody could defend.
    """
    from telemetry.record import RATIFIED_OMISSION_REASONS

    # BOTH shapes. Since L1-S4 a SINGLE-account document that surfaced an
    # omission publishes a `document` block beside today's payload, and the
    # fifteen protected carriers of W3 §L1S2 are exactly that shape — so
    # gating this on `accounts` would have kept Q10's surface dark on every
    # document the ruling was made about.
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY)
    omissions = (block or {}).get("omitted_sections") or []
    return [
        omission for omission in omissions
        if not isinstance(omission, dict)
        or omission.get("reason") not in RATIFIED_OMISSION_REASONS
    ]


#: The document-scope note that refuses a document's PACKAGE AGGREGATION.
#: Declared in `analysis/pipeline.py`; named here as the string the package
#: reads, and held to that module's constant by `tests/test_l1s4_transfers.py`
#: so the two cannot drift into two spellings of one refusal.
_AMBIGUOUS_TRANSFER_NOTE = "ambiguous_internal_transfer"


def _document_notes(analysis: object) -> list[str]:
    """The DOCUMENT-scope integrity notes this payload carries, either shape."""
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY) or {}
    notes = block.get("integrity_notes") or []
    return [note for note in notes if isinstance(note, str)]


def _internal_transfer_positions(analysis: object, account_index: int | None) -> set[int]:
    """Which of THIS member's postings the document paired as internal (R-d).

    `account_index` is the member's 1-based position in the document's printed
    account order, and `None` for a job publishing today's payload — which has
    one ledger and therefore no sibling for a counterpart to be in, so the
    answer for it is always empty and this costs a single-account package
    nothing.

    The indices come from the document's own `internal_transfers`, which the
    publisher wrote and nothing here recomputes: a package that decided for
    itself which postings were transfers would be applying a transfer grammar
    at the aggregation layer, and there would then be two answers to one
    question.
    """
    if account_index is None or not isinstance(analysis, dict):
        return set()
    block = analysis.get(_DOCUMENT_KEY) or {}
    positions: set[int] = set()
    for transfer in block.get("internal_transfers") or []:
        if not isinstance(transfer, dict):
            continue
        for leg in (transfer.get("a"), transfer.get("b")):
            if (isinstance(leg, (list, tuple)) and len(leg) == 2
                    and leg[0] == account_index - 1
                    and isinstance(leg[1], int) and not isinstance(leg[1], bool)):
                positions.add(leg[1])
    return positions


_MAIN_ACCOUNT_TITLE = re.compile(r"\b(?:business|commercial|corporate)\b", re.IGNORECASE)


def _account_roster(analysis: object) -> list[dict]:
    """Every account a statement judged account by account prints (document.account_roster); [] for any other."""
    document = analysis.get("document") if isinstance(analysis, dict) else None
    roster = document.get("account_roster") if isinstance(document, dict) else None
    return [entry for entry in roster if isinstance(entry, dict)] if isinstance(roster, list) else []


_NOT_A_MAIN_ACCOUNT = frozenset({"credit_card", "loan"})


def main_account_rank(kind, title) -> int:
    """How likely an account is the one a lender funds, as the dashboard ranks it (app.js mainAccountRank): a
    checking account first, then one whose title names no kind (a product name such as "... Plus Banking" can be the
    operating account), then any other deposit account; a business title one higher within its tier; a card or a
    loan never."""
    if kind in _NOT_A_MAIN_ACCOUNT:
        return -1
    tier = 4 if kind == "checking" else 2 if kind in (None, "") else 0
    return tier + (1 if _MAIN_ACCOUNT_TITLE.search(str(title or "")) else 0)


def _unverified_main_account(roster: list[dict]) -> dict | None:
    """The statement's main account when it was not verified, as the dashboard decides it (app.js
    unverifiedMainAccount): a HELD account of the best rank (main_account_rank). Which account a lender funds is then
    undetermined, and no other account stands in for it. None when no account of the best rank is held, when the
    best rank is a card's or a loan's (no account a lender funds), or there is no roster."""
    if not roster:
        return None
    ranks = [main_account_rank(entry.get("kind"), entry.get("title")) for entry in roster]
    best = max(ranks)
    held = [entry for entry, rank in zip(roster, ranks) if rank == best and entry.get("status") == "held"]
    return held[0] if held and best >= 0 else None


def _idle_main_account(roster: list[dict]) -> dict | None:
    """The statement's main account when it printed no activity this period (owner ruling, 2026-09-23: it needs
    review; the dashboard keeps showing the active account, app.js idleMainAccount): the idle account of the best rank
    (main_account_rank), when no account of that rank was verified or held. None otherwise."""
    if not roster:
        return None
    ranks = [main_account_rank(entry.get("kind"), entry.get("title")) for entry in roster]
    best = max(ranks)
    top = [entry for entry, rank in zip(roster, ranks) if rank == best]
    if best < 0 or any(entry.get("status") in ("published", "held") for entry in top):
        return None
    return next((entry for entry in top if entry.get("status") == "idle"), None)


def _package_members(jobs, *, settings: dict | None = None) -> tuple[list[tuple], list[dict]]:
    """`(members, excluded)` — what enters the package math, and what does not.

    A member is ONE ACCOUNT. A job publishing today's payload is one member and
    is admitted exactly as it always was — this function cannot change what a
    single-account package computes, because for such a job it yields one
    `(job, analysis)` pair whose analysis is the stored one as the dashboard
    shows it (`_displayed`: the owner's NSF basis and flag groups applied to a
    copy; the stored record is never rewritten and every other field is the
    stored one). Settings are read once per package — here, or by the caller
    that passes `settings` — so a setting saved mid-request cannot split the
    members across two NSF bases or two sets of ticked flag groups.

    Two rules apply to a job that publishes several accounts, and both are the
    package's own arithmetic protecting itself:

    * **membership requires the account's OWN `validated`.** A package sums,
      counts and days-weights its members. An account the platform did not
      validate has no authoritative figure to contribute, and admitting it
      because a SIBLING validated would let one account's proof carry
      another's numbers. Excluded accounts are RETURNED, never dropped: the
      package publishes what it left out.
    * **no average over one content digest twice.** Two accounts of one
      document publishing identical content are one account published twice,
      and every cross-account total here — a sum, a count, the days-weighted
      ADB — would count that money twice. `document_report_to_dict` refuses to
      publish such a document; this is the same refusal standing where the
      arithmetic happens, because a payload can reach a package from a store
      that was written before the publisher learned to refuse it.
    """
    from telemetry.record import classify_outcome

    members: list[tuple] = []
    excluded: list[dict] = []
    # One read per package, so a setting saved mid-request cannot split the members across two NSF bases or two
    # sets of ticked flag groups.
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    for job in jobs:
        analysis = _displayed(job.analysis or {}, settings=settings)
        roster = _account_roster(analysis)
        unverified, idle = _unverified_main_account(roster), _idle_main_account(roster)
        if unverified is not None or idle is not None:
            # The statement's main account (its business checking account, as the dashboard shows it) was not
            # verified, or printed no activity and needs review: no other account of the statement stands in for it
            # in the package's figures.
            excluded.append({
                "job_id": job.id,
                "account_index": None,
                "account_count": len(roster),
                "outcome": "withheld",
                "reason": "main_account_unverified" if unverified is not None else "main_account_idle",
            })
            continue
        if not is_document_payload(analysis):
            members.append((job, analysis, None, 1))
            continue
        surface = "webapp/app.py::_package_members"
        accounts = payload_accounts(analysis, surface=surface)
        count = payload_account_count(analysis, surface=surface)
        unratified = _unratified_omissions(analysis)
        digests = [account_content_digest(account) for account in accounts]
        if len(set(digests)) != len(digests):
            raise ValueError(
                "two accounts of one document publish identical content; a "
                "duplicate section would be double-counted by every "
                "cross-account total in this package "
                "(document_publishes_duplicate_account)"
            )
        ambiguous = _AMBIGUOUS_TRANSFER_NOTE in _document_notes(analysis)
        for index, account in enumerate(accounts, start=1):
            outcome, reason = classify_outcome(account)
            if ambiguous:
                # §3.3 / Q2. A posting with two or more admissible counterparts
                # leaves it unestablished WHICH sibling row the money moved to,
                # so this document's accounts cannot be aggregated without
                # either double-counting a movement or deleting a printed
                # deposit. The package refuses to aggregate it and says so.
                #
                # It refuses the AGGREGATION and nothing else: each account
                # keeps its own outcome, its own ledger and its own ADB, both
                # printed legs stay where the paper printed them, and the
                # excluded set below is published rather than dropped.
                excluded.append({
                    "job_id": job.id,
                    "account_index": index,
                    "account_count": count,
                    "outcome": outcome,
                    "reason": "document_transfer_pairing_ambiguous",
                })
                continue
            if unratified:
                # The DOCUMENT failed (L1-C17). Its accounts may not carry
                # money into a package on their own validation.
                excluded.append({
                    "job_id": job.id,
                    "account_index": index,
                    "account_count": count,
                    "outcome": "failed",
                    "reason": "document_omission_unratified",
                })
                continue
            if outcome != "validated":
                excluded.append({
                    "job_id": job.id,
                    "account_index": index,
                    "account_count": count,
                    "outcome": outcome,
                    "reason": reason,
                })
                continue
            members.append((job, account, index, count))
    return members, excluded


def _package_analysis(jobs, *, settings: dict | None = None) -> dict:
    # The one settings snapshot this package is built on: its members are displayed with it, and its flag roll-up
    # keeps the groups it ticks.
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    shown_groups = enabled_group_keys(settings)
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
    members, excluded_accounts = _package_members(jobs, settings=settings)
    #: Q10. Every ratified sibling omission any member document published. The
    #: package says so rather than demoting anything: an omission admitted on
    #: printed evidence beside an independently validated account is a
    #: COMPLETENESS fact about the paper, not a fault in the account's figures.
    omitted_sections = [
        omission
        for job in jobs
        for omission in _ratified_omissions(job.analysis or {})
    ]
    documents = []
    monthly = []
    #: `(job, period start, period end)` for every member that contributed —
    #: the honest count of statement PERIODS, beside `months`'s count of
    #: members. See the note at `statement_periods` below (MINOR-10).
    period_keys: set[tuple] = set()
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
        # Lender detection §8.3: the ticked flag groups' counted debits and their total, and apart from them the
        # counted credits (a factor's payouts, owner ruling 2026-09-26) and theirs. Never lender math (D7).
        "flagged_position_count": 0,
        "flagged_position_total": 0.0,
        "flagged_position_count_credited": 0,
        "flagged_position_total_credited": 0.0,
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
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
    package_flagged_evidence: list[dict] = []
    denominator_modes: set[str] = set()
    nsf_sources: set[str] = set()
    #: CURRENCY DOCTRINE §F bookkeeping: how many money-contributing members
    #: each declared currency has, and how many declared none at all.
    currency_documents: dict[str, int] = {}
    undeclared_currency_documents = 0
    for job, analysis, account_index, account_count in members:
        statement = analysis.get("statement") or {}
        metrics = analysis.get("metrics") or {}
        quality = analysis.get("quality") or {}
        integrity = analysis.get("integrity") or {}
        detection = analysis.get("detection") or {}
        corporate_use = quality.get("corporate_use") or ""
        integrity_risk = integrity.get("risk_level") or ""
        # `totals["documents"]` counts JOBS and the counters below count
        # MEMBERS, which are the same number until a document publishes two
        # accounts and different on purpose after that: a package sums, counts
        # and days-weights ACCOUNTS, and one document contributing two of them
        # is two contributions.
        ready = job.status == "done" and job.analysis is not None

        # CURRENCY DOCTRINE §F. A member with no analysis at all contributes
        # exactly zero to every money total below — each `_num` call falls back
        # to its default over the empty dicts — so it carries no unit and cannot
        # make a package multi-currency. A member that DOES contribute money has
        # to declare the unit it contributed in; one that does not is an unknown
        # and fails the package closed rather than joining a pool as if proven.
        statement_currency = _statement_currency(analysis)
        if analysis:
            if statement_currency is None:
                undeclared_currency_documents += 1
            else:
                currency_documents[statement_currency] = (
                    currency_documents.get(statement_currency, 0) + 1
                )

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
        # R-d, at the one layer that can see two of a document's ledgers at
        # once. A movement between two accounts of ONE document is one
        # movement; a package that sums both accounts counts the same money as
        # a deposit AND as a withdrawal, and every derivation built on those —
        # gross deposits, deposit counts, revenue, the withholding denominator,
        # the flattened ledger — carries the double.
        #
        # Excluded by INDEX, from the document's own `internal_transfers`, and
        # only where the paper printed an internal designation on a leg: the
        # rule that produced these indices refused four of the archive's
        # forty-seven candidate pairs for want of one.
        #
        # BOTH LEGS STAY IN THEIR LEDGERS. Nothing here touches `statement`,
        # the account's reconciliation or its ADB — the money really was in
        # that account on that day, and removing it would break the account's
        # own arithmetic. What is excluded is this member's CONTRIBUTION to a
        # cross-account total.
        raw_transactions = statement.get("transactions") or []
        # `analysis` here is this MEMBER's account payload — `_package_members`
        # hands one account at a time — and the transfer record is a DOCUMENT
        # fact, so it is read off the job's own payload. Getting this wrong is
        # silent: the account payload carries no `document` block, the position
        # set comes back empty, and the exclusion never fires.
        excluded_positions = _internal_transfer_positions(job.analysis, account_index)
        statement_transactions = [
            transaction
            for position, transaction in enumerate(raw_transactions)
            if isinstance(transaction, dict) and position not in excluded_positions
        ]
        excluded_credits = excluded_debits = 0.0
        excluded_credit_count = 0
        if excluded_positions:
            excluded_rows = [
                raw_transactions[position] for position in sorted(excluded_positions)
                if position < len(raw_transactions)
                and isinstance(raw_transactions[position], dict)
            ]
            excluded_credits = round(
                sum(_num(row.get("amount")) for row in excluded_rows
                    if _num(row.get("amount")) > 0), 2)
            excluded_credit_count = sum(1 for row in excluded_rows if _num(row.get("amount")) > 0)
            excluded_debits = round(
                sum(abs(_num(row.get("amount"))) for row in excluded_rows
                    if _num(row.get("amount")) < 0), 2)
            # The account's own `effective_total_*` are the figures the BANK
            # stated for that account, and the bank counted the transfer. The
            # deduction is arithmetic over rows this package already holds, and
            # `cash_flow` is recomputed from the two adjusted sides rather than
            # adjusted twice: a pair removes a credit from one member and the
            # matching debit from another, so a package's cash flow is
            # unchanged by construction, which is the point.
            credits = round(credits - excluded_credits, 2)
            debits = round(debits - excluded_debits, 2)
            cash_flow = round(credits - debits, 2)
        # The Monthly Statements table's "Deposits Per Month": the count that pairs with `credits`, less the
        # transfers removed above. It pairs when the total IS the rows' total, when the bank printed its own
        # count beside its total, or when the captured rows add up to the bank's total exactly. Otherwise (a
        # parser that read the bank's total but not its count, and captured rows that fall short) the count
        # would describe other money: None, shown as N/A.
        deposit_total = _num(metrics.get("effective_total_deposits"), float("nan"))
        line_item_total = _num(metrics.get("total_deposits"), float("nan"))
        count_pairs = (
            str(metrics.get("deposits_source") or "line_items") == "line_items"
            or _is_count(statement.get("stated_credit_count"))
            or abs(line_item_total - deposit_total) < 0.005
        )
        stated_deposit_count = metrics.get("effective_num_deposits")
        deposit_count = (
            max(stated_deposit_count - excluded_credit_count, 0)
            if count_pairs and _is_count(stated_deposit_count)
            else None
        )
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
        flagged_rows = [
            transaction
            for transaction in authoritative_rows
            if _counts_as_flagged(transaction["classification"], shown_groups)
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
        # Monthly Statements' True deposits (the verified revenue) stand for this member only when every captured
        # credit carries its revenue state AND the captured credits are the money its Total counts: the line items are
        # the Total's source, or they add up to the bank's own total. Otherwise the verified figure is a part of an
        # unknown whole (a summary-only statement, a partly classified one, a payload from before classification
        # records, a failed member), and the table says N/A rather than show it as the month's revenue. A member
        # that captured no credit and whose Total is zero took in nothing, and its True deposits are zero.
        revenue_established = ready and (
            (
                revenue_rows_are_authoritative
                and (
                    str(metrics.get("deposits_source") or "line_items") == "line_items"
                    or abs(line_item_total - deposit_total) < 0.005
                )
            )
            or (bool(statement) and not positive_statement_rows and credits == 0)
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
        if excluded_credits and denominator_mode == "legacy_eligible_deposits":
            # The legacy denominator is `effective_total_deposits` less the
            # LENDER credits, so an internal transfer is still inside it and has
            # to come out — a withholding rate whose denominator counts the
            # member's own money twice under-states the exposure.
            #
            # The verified-revenue mode needs no deduction and must not get
            # one: an internal-transfer credit is already `non_revenue` by
            # `analysis/transaction_classifier.py`'s own vocabulary, so
            # `verified_revenue_total` never carried it and subtracting again
            # would remove money the denominator never held.
            eligible_deposits = round(max(eligible_deposits - excluded_credits, 0.0), 2)
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
        nsf_source = metrics.get("nsf_source")
        if isinstance(nsf_source, str):
            nsf_sources.add(nsf_source)  # a member with no analysis contributes no count and no basis
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

        # Flag groups (lender detection §8.3): the ticked groups' counted rows of this member's ledger, less its
        # internal-transfer legs. They never reach the lender totals, the withholding or the decision (D7).
        _add_flagged_rows(flagged_rollup, flagged_rows)

        # Flattened ledger so the dashboard can show every statement's rows at once.
        for tx in statement_transactions:
            package_transaction = {
                **tx,
                "source_job": job.id,
                "source_document": job.filename,
                "source_bank": statement.get("bank"),
                # The combined ledger shows rows from every member at once, so
                # each row has to carry its own denomination — a package-wide
                # currency would mislabel every row of a mixed package.
                "source_currency": statement_currency,
                "source_period_start": statement.get("period_start"),
                "source_period_end": statement.get("period_end"),
            }
            if account_index is not None:
                # A row of one account of a multi-account document: its location is numbered within that account,
                # so a review of it names the account (1-based, printed order). Other rows carry no such key.
                package_transaction["source_account"] = account_index
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
            if _counts_as_flagged(classification, shown_groups):
                # A location is numbered within its own account, so a multi-account member's evidence names it.
                package_flagged_evidence.append(
                    evidence if account_index is None else {**evidence, "source_account": account_index}
                )
            revenue_state = classification.get("revenue_classification")
            if revenue_state in REVENUE_STATES and _num(tx.get("amount")) > 0:
                package_revenue_evidence[revenue_state].append(evidence)

        doc_row = {
            # One row per MEMBER. An account of a multi-account document is
            # named by the document it came from plus its printed position —
            # never by the document alone, which would give two members one id
            # and let the second overwrite the first everywhere a package row
            # is looked up by id.
            "id": job.id if account_index is None else f"{job.id}#account_{account_index}",
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
            # CURRENCY DOCTRINE §D/§F: this row's figures are all in one
            # currency and stay denominated even when the package refuses to
            # combine them with another member's.
            "currency": statement_currency,
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
            "deposit_count": deposit_count,
            "total_posted_credits": posted_credit_total,
            "total_posted_credit_count": posted_credit_count,
            "verified_revenue_total": revenue_totals["verified_revenue"],
            "verified_revenue_count": revenue_counts["verified_revenue"],
            "verified_revenue_established": revenue_established,
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
            "nsf_source": nsf_source,
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
        if account_index is not None:
            # Only a multi-account document has these to say, so a package of
            # today's payloads carries neither key and is byte-identical.
            doc_row["account_index"] = account_index
            doc_row["account_count"] = account_count
        documents.append(doc_row)
        if ready:
            monthly.append(doc_row)
            # MINOR-10: the same rows counted as PERIODS rather than as
            # members. Two accounts of one document share a job id and the
            # document's one printed cycle, so they collapse to one; two
            # documents never do, whatever period they print.
            period_keys.add((job.id, statement.get("period_start"),
                             statement.get("period_end")))
            if adb_validated:
                adb_value = Decimal(str(average_daily_balance_num))
                adb_weighted_sum += adb_value * adb_calendar_days
                adb_weight += adb_calendar_days

    # Design §6.5's fourth bullet, and Q5's direction: **no published average is
    # computed over two accounts of one document.** The L1-S3 review measured
    # what its absence does — a package holding one job that publishes two
    # different validated accounts over ONE statement period published every
    # per-month average HALVED, because `months` counts MEMBERS and each
    # account is a member. Two accounts of one document are one period of
    # banking, not two.
    #
    # The duplicate-content-digest refusal in `_package_members` does not catch
    # this and cannot: it fires only when two accounts publish IDENTICAL
    # content, and two different accounts of one document pass it. This is the
    # member-set check §6.5 actually asked for, and it is keyed on the document
    # identity two members share.
    #
    # It REFUSES rather than re-divides. Choosing a denominator — periods,
    # documents, distinct months — is a policy about what a package average
    # means, and a stage whose whole claim is zero movement may not choose one.
    # A refused average is published as `None` beside the reason, the way
    # CURRENCY DOCTRINE §F refuses a cross-currency total, so no consumer has
    # to read a null as missing data.
    members_by_document: dict[str, int] = {}
    for member_job, _member_analysis, member_index, _member_count in members:
        if member_index is None:
            continue  # a single-account job is one member and one document
        identity = getattr(member_job, "content_sha256", None) or member_job.id
        members_by_document[identity] = members_by_document.get(identity, 0) + 1
    documents_with_several_members = sorted(
        identity for identity, count in members_by_document.items() if count > 1
    )
    refuse_cross_account_averages = bool(documents_with_several_members)

    months = max(1, len(monthly))
    # MINOR-10 (the L1-S3 review). `months` counts MEMBERS — it always has, and
    # it is the divisor every per-period average below is taken over — and
    # `webapp/static/app.js` labels it "statement periods". Identical numbers
    # until a document publishes two accounts, and two accounts of one document
    # are ONE statement period, so from that document on the dashboard was
    # printing a count of accounts under the name of a count of periods.
    #
    # The COUNT is not changed, deliberately: it is the denominator of a
    # published average, choosing a denominator is the policy L1-S3 refused to
    # choose on its own, and Q5 rules the arithmetic forbidden rather than
    # re-divided. What is published is the honest period count BESIDE it, and
    # only when the two differ — so a package of today's payloads carries
    # neither key and is byte-identical. The dashboard prefers it when it is
    # there and falls back to `months` when it is not.
    statement_periods = len(period_keys) or months
    # Days-weighted mean of the per-statement daily-balance averages: summing
    # every statement's daily balances and dividing by every calendar day.
    package_average_daily_balance = None
    if adb_weight > 0:
        package_average_daily_balance = float(
            (adb_weighted_sum / adb_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
    if refuse_cross_account_averages:
        # The ADB doctrine forbids a document-level combined ADB outright, so a
        # days-weighted mean over two accounts of one document is the forbidden
        # figure arrived at by a different route.
        package_average_daily_balance = None
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
    totals["flagged_position_count"] = sum(item["count"] for item in flagged_rollup.values())
    totals["flagged_position_total"] = round(sum(item["total_debited"] for item in flagged_rollup.values()), 2)
    totals["flagged_position_count_credited"] = sum(item["count_credited"] for item in flagged_rollup.values())
    totals["flagged_position_total_credited"] = round(
        sum(item["total_credited"] for item in flagged_rollup.values()), 2
    )
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

    # ------------------------------------------------------------------
    # CURRENCY DOCTRINE §F — the package layer stops mixing currencies.
    #
    # Everything above ran exactly as it always has; this is the one place the
    # currency rule applies, so the same-currency path reaches the return with
    # byte-identical figures and the refusal cannot leak a half-converted
    # number into an earlier accumulation.
    # ------------------------------------------------------------------
    if undeclared_currency_documents:
        # Fail closed (§B): a member contributed money in a unit it never
        # named. It must not silently join a same-currency pool as if proven.
        currency_resolution = "undetermined"
        package_currency = None
        currency_refusal_reason = "undetermined_statement_currency"
    elif len(currency_documents) > 1:
        currency_resolution = "mixed"
        package_currency = None
        currency_refusal_reason = "multiple_currencies"
    elif len(currency_documents) == 1:
        currency_resolution = "single"
        package_currency = next(iter(currency_documents))
        currency_refusal_reason = None
    else:
        # No member produced an analysis, so no member contributed a figure in
        # any currency. Every total is a structural zero over an empty set;
        # there is no unit to protect and nothing to refuse.
        currency_resolution = "no_analyzed_documents"
        package_currency = None
        currency_refusal_reason = None
    refuse_cross_currency = currency_refusal_reason is not None

    # CURRENCY DOCTRINE §F reaches the ORDER, not only the values. Ranking these
    # rollups by their summed money publishes a cross-currency comparison —
    # "this lender took more than that one" — and nulling the figures afterwards
    # leaves that assertion standing in the row order, where it is read as fact
    # and cannot be audited because the numbers behind it are gone. A refused
    # package therefore ranks by a unit-free key: the count, then the name.
    #
    # `potential_lenders` already sorts by name. Its order never encoded a
    # magnitude comparison, so it is correct in both cases and is deliberately
    # left alone rather than churned.
    if refuse_cross_currency:
        package_funders = sorted(
            funders.values(),
            key=lambda r: (-int(r.get("debit_count") or 0), r["funder"]),
        )
        package_insurance_providers = sorted(
            insurance_providers.values(),
            key=lambda r: (-int(r.get("count") or 0), r["provider"]),
        )
    else:
        package_funders = sorted(
            funders.values(), key=lambda r: r["total_debited"], reverse=True
        )
        package_insurance_providers = sorted(
            insurance_providers.values(), key=lambda r: r["total_debited"], reverse=True
        )
    package_potential_lenders = sorted(
        potential_lenders.values(), key=lambda r: r["funder"]
    )
    package_flagged_positions = _published_flagged_positions(
        flagged_rollup, refuse_cross_currency=refuse_cross_currency
    )

    published_totals = {
        **totals,
        # §6.5 / Q5. Published only when the refusal fires, so a package of
        # today's payloads carries neither key and is byte-identical.
        **({
            "cross_account_averages_refused": True,
            "cross_account_average_refusal_reason": (
                "two or more members are accounts of ONE document, so a "
                "per-period average over them would divide one period of "
                "banking by a count of accounts (no_average_over_one_document)"
            ),
            "documents_with_several_members": len(documents_with_several_members),
        } if refuse_cross_account_averages else {}),
        # Q10 (BATCH9_TRANSITION §8.7): surfaced, never demoted, and published
        # ONLY when there is something to surface. A `False` / `"complete"`
        # default would put two new fields on every package this platform has
        # ever produced, which is movement — and this stage moves nothing. Their
        # ABSENCE is today's package, unchanged; their presence is the fact.
        **({
            "sibling_account_omission_detected": True,
            "completeness": "partial",
            "omitted_section_count": len(omitted_sections),
        } if omitted_sections else {}),
        # MINOR-10, published only when it differs from `months` — so a package
        # of today's payloads carries no new key and is byte-identical.
        **({"statement_periods": statement_periods}
           if statement_periods != months else {}),
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
        # The basis the summed NSF count was cut on (analysis/nsf_days.py). "mixed" when members differ, e.g. a
        # member whose count is unavailable, or a legacy payload that could not be re-based.
        "nsf_source": next(iter(nsf_sources)) if len(nsf_sources) == 1 else ("mixed" if nsf_sources else None),
        "withholding_denominator_label": (
            "Verified revenue"
            if denominator_modes == {"verified_revenue"}
            else "Legacy eligible deposits"
            if denominator_modes == {"legacy_eligible_deposits"}
            else "Mixed denominator configuration"
        ),
        # CURRENCY DOCTRINE §D: the one denomination every figure above is in,
        # surfaced once. None whenever the package could not prove a single one.
        "currency": package_currency,
        "currency_resolution": currency_resolution,
        "cross_currency_totals_refused": refuse_cross_currency,
        "currency_refusal_reason": currency_refusal_reason,
    }

    if refuse_cross_account_averages:
        # Only the PER-PERIOD figures. The sums and counts are unaffected: two
        # accounts of one document really did move that money, and adding them
        # counts each posting once. What cannot be divided by a member count is
        # a per-period average, and the ADB is refused for the doctrine's own
        # reason rather than for this one.
        for key in _PER_PERIOD_AVERAGE_KEYS:
            published_totals[key] = None

    if refuse_cross_currency:
        for key in _CROSS_CURRENCY_TOTAL_KEYS:
            published_totals[key] = None
        for item in (
            *package_funders,
            *package_potential_lenders,
            *package_insurance_providers,
            *(item for items in package_flagged_positions.values() for item in items),
        ):
            for key in _CROSS_CURRENCY_ROLLUP_KEYS:
                if key in item:
                    item[key] = None
        # A judgement read off a refused figure must not read as a pass. The
        # reconciliation cannot be asserted, the withholding denominator is not
        # available, and the package as a whole needs an analyst.
        published_totals["revenue_reconciles"] = False
        published_totals["withholding_review_required"] = True
        published_totals["decision"] = "review_required"

    return {
        "totals": published_totals,
        # CURRENCY DOCTRINE §F: the package's currency composition, and — when
        # the package is not single-currency — exactly which totals were refused
        # and why, so no consumer has to infer a refusal from a null.
        "currency": {
            "resolution": currency_resolution,
            "currency": package_currency,
            "currencies": sorted(currency_documents),
            "documents_by_currency": {
                code: currency_documents[code] for code in sorted(currency_documents)
            },
            "undeclared_currency_documents": undeclared_currency_documents,
            "cross_currency_totals_refused": refuse_cross_currency,
            "refusal_reason": currency_refusal_reason,
            "refused_total_fields": (
                sorted(_CROSS_CURRENCY_TOTAL_KEYS) if refuse_cross_currency else []
            ),
        },
        "documents": documents,
        # D-3: one entry per content hash present more than once, listing every
        # member job that carries it (the first occurrence included).
        "duplicates": duplicate_groups,
        "monthly": sorted(monthly, key=lambda r: (r.get("period_end") or "", r.get("filename") or "")),
        "funders": package_funders,
        "potential_lenders": package_potential_lenders,
        "insurance_providers": package_insurance_providers,
        # Lender detection §8.3: the ticked flag groups, never lender math.
        "flagged_positions": package_flagged_positions,
        "transactions": package_transactions,
        "lender_evidence": package_lender_evidence,
        "potential_lender_evidence": package_potential_lender_evidence,
        "insurance_evidence": package_insurance_evidence,
        "flagged_evidence": package_flagged_evidence,
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
        # An account of a multi-account document that the platform did not
        # validate is not a package member — a package sums, counts and
        # days-weights its members, and an unvalidated account has no
        # authoritative figure to contribute. It is PUBLISHED as excluded
        # rather than dropped: a member that vanished quietly is the L-1
        # defect wearing a package's clothes.
        #
        # The key exists only when there is something to say, so a package of
        # today's single-account payloads is byte-identical to what it was.
        **({"excluded_accounts": excluded_accounts} if excluded_accounts else {}),
        # Q10: the omissions themselves, so a reader of the package can see
        # WHICH sections were established and not published rather than only
        # that some were. Conditional for the same reason as the totals above.
        **({"omitted_sections": omitted_sections} if omitted_sections else {}),
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


def _checked_upload(filename: str, pdf_bytes: bytes, *, read_native_text: bool = True) -> tuple[int | None, object, dict | None]:
    """Server-side gate for a single uploaded file. Returns
    (page_count, profile, error) with the error exclusive of the other two.

    Validation order and error shape are D-2a's; O-1 adds the preflight
    profile and rejects password-protected PDFs before any parsing —
    processing one could only ever fail later with a worse message.

    MINOR-8 (PHASE2_P20SEAM_REVIEW.md): a multipart filename carrying a raw
    CR/LF is refused HERE, first, with a class-name-only message — never the
    raw filename echoed back (unlike every other branch below, which is safe
    to echo because ordinary filenames carry no attack shape). Before this,
    such a filename reached `ocr.document.StatementMarkdown.__post_init__`
    deep inside the reading stage, which refuses it too (`ProvenanceTokenError`
    on a line-break in `source_file`) — but as an opaque per-job failure
    instead of a clean 400 at upload, and `_stage_failure` (`webapp/
    worker.py`) already withholds that message from the job record, so the
    only change here is WHERE the refusal happens, not what it reveals.

    NEW-4 (re-review, closure 1cc759e): the same reasoning extends to `-->`,
    which `StatementMarkdown.__post_init__` also refuses (the writer-side
    belt) but this function did not — a filename like `a-->b.pdf` reached
    the view (a raw `-->` does not corrupt multipart framing the way CR/LF
    does) and then died as the same opaque per-job failure MINOR-8 fixed for
    CR/LF. Refused here too, for consistency, with the identical
    class-name-only shape."""
    if "\r" in filename or "\n" in filename or "-->" in filename:
        return None, None, {"error": "ProvenanceTokenError"}
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        return None, None, {
            "error": f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            "filename": filename,
        }
    if not pdf_bytes.startswith(b"%PDF-"):
        return None, None, {"error": "file is not a PDF", "filename": filename}
    profile = (inspect_pdf(pdf_bytes) if read_native_text
               else inspect_pdf(pdf_bytes, read_native_text=False))
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


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({"settings": load_settings(store.storage.data_dir)})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Save owner display settings. JSON only: a cross-site HTML form cannot send it without a preflight."""
    updates = request.get_json(silent=True)
    if not request.is_json or updates is None:
        return jsonify({"error": "settings must be sent as a JSON object"}), 400
    try:
        settings = save_settings(store.storage.data_dir, updates)
    except ValueError:
        # A fixed refusal: no exception text crosses this boundary (tests/test_worker_privacy.py).
        return jsonify({"error": "invalid settings update"}), 400
    except OSError:
        # A read-only data folder, or a replace that kept colliding with readers; the setting is unchanged.
        return jsonify({"error": "settings could not be saved"}), 503
    return jsonify({"settings": settings})


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
    # The forced pair skips native text at intake as well as in the worker.
    # Encryption, page limits and the document hash still receive structural
    # validation; the explicit legacy comparison keeps its previous preflight.
    read_native_text = not (force_ocr and not load_ocr_settings().visual_pair_legacy_visual)

    # Validate the whole batch before creating any job. A half-accepted upload
    # would leave the dashboard aggregating an incomplete package with nothing
    # on screen to say a statement is missing.
    accepted: list[tuple[str, bytes, int, object]] = []
    for f in files:
        pdf_bytes = f.read()
        page_count, profile, error = _checked_upload(f.filename, pdf_bytes, read_native_text=read_native_text)
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
        "analysis": _masked(_displayed(job.analysis)),
        "analysis_error": job.analysis_error,
    })


#: `analysis/revenue.py`'s DECLARED review refusals (#PRIVACY3, the APP-PRIVACY
#: half; the pattern is `webapp/worker.py`'s `_DECLARED_ANALYSIS_REFUSALS`).
#:
#: `revenue_review` returned `str(exc)` as the HTTP body on both arms, and
#: `webapp/static/app.js` puts that body straight into a `window.alert`. The
#: three literals the batch-6 ledger named are real and worth keeping — but the
#: `except` is BROADER than the raises: any `ValueError` raised deeper inside
#: `rebuild_serialized_revenue_views` (which `apply_serialized_revenue_review`
#: calls on its way out) was published verbatim, and the money grammar is
#: exactly such a raiser. Reduction is now the default.
#:
#: FIVE, not three. The batch-6 census (W3 §WORKERPRIV WP6.1) counted only the
#: raises inside `apply_serialized_revenue_review` itself and missed the two in
#: `rebuild_serialized_revenue_views`, which its last line calls; both are
#: reachable through this route and both are fixed literals. Measured, and
#: `test_every_declared_review_refusal_is_actually_raised` drives each of the
#: five out of `analysis/revenue.py` so the tuple cannot drift from the raises.
#:
#: Matching is EXACT and the value published is the member of this tuple, never
#: the exception's own string, so what crosses the boundary is provably a
#: constant in this file. `f"{DECLARED}: {a quoted cell}"` does not match and is
#: reduced like anything else. Fail-closed: admission is a deliberate edit.
#:
#: SEVEN since the review learned to name its account: a location numbers a
#: posting within its account, so a document of several accounts can hold one
#: location per account, and `apply_serialized_revenue_review` refuses such a
#: location unless the review names the account, and a named account it lacks.
_DECLARED_REVIEW_REFUSALS: tuple[str, ...] = (
    "transaction source location was not found",
    "decision must be confirm, reject, or reset",
    "only automatically unverified deposits can be reviewed",
    "every posted credit must have an authoritative classification record",
    "every posted credit must have a valid revenue classification",
    "account was not found",
    "transaction source location is in more than one account; name the account",
)


def _review_refusal(exc: BaseException) -> str:
    """The only exception text this route may put in an HTTP body.

    A declared refusal keeps its named reason; anything else is reduced to the
    class name. The vocabulary matches `webapp/worker.py:_stage_failure` word
    for word, deliberately: an operator reading a withheld message in a browser
    alert and a withheld message in the job store should not have to learn that
    they mean the same thing.
    """
    message = str(exc)
    for declared in _DECLARED_REVIEW_REFUSALS:
        if message == declared:
            return declared  # this module's constant, not the exception's text
    return (
        f"revenue review failed: {type(exc).__name__} "
        "(message withheld; an exception message can quote statement text)"
    )


#: One lock per statement around a review's read-modify-write. A review reads the stored analysis, applies its
#: decision to a copy and saves the copy; two reviews of one statement at once (the multi-select's batch and a row's
#: own button, or two tabs) would each start from the same stored analysis and the second save would drop the first
#: one's decision while both decision rows stayed recorded. Reviews of different statements do not wait on each other.
_review_locks: dict[str, threading.Lock] = {}
_review_locks_guard = threading.Lock()


def _review_lock(job_id: str) -> threading.Lock:
    """The statement's review lock. Taken only for a job the store knows (the routes check first), so a
    request naming no statement leaves nothing behind."""
    with _review_locks_guard:
        return _review_locks.setdefault(job_id, threading.Lock())


#: The longest actor name a review records. Free text until authentication exists (D-2b), and recorded twice per
#: decision (decision row and audit row), so it is held to the length of a name.
MAX_REVIEW_ACTOR = 120


def _review_actor(payload: dict) -> tuple[str | None, str | None]:
    """`(actor, None)`, or `(None, refusal)` for an actor that is not a name."""
    actor = payload.get("actor")
    if actor is None:
        return "local-analyst", None
    if not isinstance(actor, str) or len(actor.strip()) > MAX_REVIEW_ACTOR:
        return None, f"actor must be text of at most {MAX_REVIEW_ACTOR} characters"
    return actor.strip() or "local-analyst", None


def _review_account(value: object) -> tuple[int | None, str | None]:
    """`(account, None)` — the 1-based account in printed order, or None when the review names none — or
    `(None, refusal)`. A location numbers a posting within its account, so a statement of several accounts needs it."""
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None, "account must be a whole number from 1"
    return value, None


@app.route("/analysis/<job_id>/revenue-review", methods=["POST"])
def revenue_review(job_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "the review must be a JSON object"}), 400
    source_location = str(payload.get("source_location") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    if not source_location:
        return jsonify({"error": "source_location is required"}), 400
    account, refusal = _review_account(payload.get("account"))
    if refusal:
        return jsonify({"error": refusal}), 400
    # Free-text actor until authentication exists (D-2b); recorded with the
    # decision timestamp and the prior classification state in the same
    # storage transaction that persists the mutated analysis.
    actor, refusal = _review_actor(payload)
    if refusal:
        return jsonify({"error": refusal}), 400
    if store.get(job_id) is None:
        abort(404)
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None or job.status != "done" or job.analysis is None:
            abort(404)
        try:
            updated = apply_serialized_revenue_review(
                deepcopy(job.analysis),
                source_location=source_location,
                decision=decision,
                account=account,
            )
        except LookupError as exc:
            return jsonify({"error": _review_refusal(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": _review_refusal(exc)}), 400
        stored = store.apply_review(
            job_id,
            updated,
            source_location=source_location,
            decision=decision,
            actor=actor,
            account=account,
        )
    if stored is None:
        abort(404)
    return jsonify({"analysis": _masked(_displayed(stored))})


#: The most decisions one batch may carry: more than any statement prints credits, far fewer than a request could
#: be made to hold.
MAX_REVIEW_BATCH = 500


@app.route("/analysis/<job_id>/revenue-reviews", methods=["POST"])
def revenue_reviews(job_id):
    """Several analyst decisions on one statement (the dashboard's multi-select), all or nothing.

    Every decision is applied to a working copy first, in order; only when all of them hold are the result and,
    for each decision, its own decision row and audit row saved, in one storage transaction
    (`JobStore.apply_reviews`). A refused decision refuses the batch and nothing is saved. A posting — its location
    within its account — may appear once per batch, so each recorded prior state is the one before the batch.
    Refusals use the same vocabulary as the single-decision route (`_review_refusal`): no exception text reaches the
    response."""
    payload = request.get_json(silent=True)
    decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if not isinstance(decisions, list) or not decisions:
        return jsonify({"error": "decisions must be a non-empty list"}), 400
    if len(decisions) > MAX_REVIEW_BATCH:
        return jsonify({"error": f"a batch holds at most {MAX_REVIEW_BATCH} decisions"}), 400
    parsed: list[tuple[str, str, int | None]] = []
    seen: set[tuple[int | None, str]] = set()
    for item in decisions:
        if not isinstance(item, dict):
            return jsonify({"error": "each decision must be an object"}), 400
        source_location = str(item.get("source_location") or "").strip()
        decision = str(item.get("decision") or "").strip().lower()
        if not source_location:
            return jsonify({"error": "source_location is required"}), 400
        account, refusal = _review_account(item.get("account"))
        if refusal:
            return jsonify({"error": refusal}), 400
        if (account, source_location) in seen:
            return jsonify({"error": "a transaction appears more than once in the batch"}), 400
        seen.add((account, source_location))
        parsed.append((source_location, decision, account))
    if len({account is None for _, _, account in parsed}) > 1:
        # "transaction:2" and account 1's "transaction:2" can be one posting: a batch names every account or none.
        return jsonify({"error": "every decision must name its account, or none may"}), 400
    actor, refusal = _review_actor(payload)
    if refusal:
        return jsonify({"error": refusal}), 400
    if store.get(job_id) is None:
        abort(404)
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None or job.status != "done" or job.analysis is None:
            abort(404)
        updated = deepcopy(job.analysis)
        try:
            for source_location, decision, account in parsed:
                updated = apply_serialized_revenue_review(
                    updated, source_location=source_location, decision=decision, account=account)
        except LookupError as exc:
            return jsonify({"error": _review_refusal(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": _review_refusal(exc)}), 400
        stored = store.apply_reviews(job_id, updated, decisions=parsed, actor=actor)
    if stored is None:
        abort(404)
    return jsonify({"analysis": _masked(_displayed(stored)), "applied": len(parsed)})


#: A re-analysis with no analysis to save: none was produced, or the one produced was refused. The saved analysis
#: stays; the `reason` beside this is text the worker already publishes for the same outcome (`webapp/worker.py`
#: `_stage_failure` / `_analysis_failure`) or `webapp/reanalysis.py`'s READING_NOT_CACHED or READS_DIFFERENTLY, never
#: an exception's own text.
REANALYSIS_NOT_SAVED = "no new analysis was saved; the saved analysis is unchanged"


@app.route("/analysis/<job_id>/reanalyze", methods=["POST"])
def reanalyze(job_id):
    """Analyze a saved statement again under the current rules (spec §8.6, D12) and replace its analysis in place:
    the job keeps its id and its place in Recent.

    The stored PDF (kept on disk by content hash) goes through the worker's own read and analysis path, its reading
    served from the artifact cache only (`webapp/reanalysis.py::rerun_analysis`): a statement whose reading is not
    cached is refused and no reading rung runs, so this request thread never competes with the upload queue's worker
    for OCR. The analysis replaced is written to the audit log first, in the same transaction as the replacement
    (`JobStore.apply_reanalysis`), and the analyst's revenue decisions are replayed where their posting is unchanged
    (`replay_reviews`); the answer counts those replayed, those that need redoing and those a rule now decides. JSON
    only, like the review and settings routes: a cross-site HTML form cannot send it without a preflight.

    Held under the statement's review lock from reading the job to saving the new analysis: a decision saved in
    between would land on the old analysis and then be overwritten, while its decision row stayed recorded. Reviews
    of other statements do not wait."""
    if not isinstance(request.get_json(silent=True), dict):
        return jsonify({"error": "the request must be a JSON object"}), 400
    if store.get(job_id) is None:
        return jsonify({"error": "job not found"}), 404
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        if job.status != "done":
            return jsonify({"error": "job is not finished"}), 409
        pdf_bytes = store.pdf_bytes(job_id)
        if pdf_bytes is None:
            return jsonify({"error": "the original PDF is not stored"}), 409
        rerun = rerun_analysis(store, job, pdf_bytes)
        if rerun.analysis is None:
            return jsonify({"error": REANALYSIS_NOT_SAVED, "reason": rerun.reason}), 422
        replay = replay_reviews(rerun.analysis, store.review_history(job_id))
        stored = store.apply_reanalysis(
            job_id, replay.analysis, replayed=replay.replayed, not_replayed=replay.not_replayed,
            decided_by_rules=replay.decided_by_rules)
    if stored is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify({
        "analysis": _masked(_displayed(stored)),
        "reviews_replayed": len(replay.replayed),
        "reviews_not_replayed": len(replay.not_replayed),
        "reviews_decided_by_rules": len(replay.decided_by_rules),
    })


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
        content = json.dumps(_masked(_displayed(job.analysis)), indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = _analysis_csv(_masked(_displayed(job.analysis)))
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = _analysis_xlsx(_masked(_displayed(job.analysis)))
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
