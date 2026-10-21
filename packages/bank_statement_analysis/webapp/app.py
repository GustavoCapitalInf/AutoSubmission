from __future__ import annotations
import io
import csv
import errno
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import zipfile
from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from flask import Flask, request, jsonify, render_template, Response, abort
from werkzeug.exceptions import RequestEntityTooLarge

# The .env file is loaded here, first, before any product module below reads the environment (POPPLER_PATH at
# ocr.rasterize's import, WEBAPP_MIN_FREE_MB below, ...). ocr/config.py and analysis/config.py also load it for the
# command-line tools. The first load wins (override=False), and
# every load reads the package folder's .env, so the order only decides WHEN the values are there, not which they are.
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .auth import refuse_unauthenticated_bind, request_is_authorized, unauthorized

from ocr.inspect import inspect_pdf
from ocr.rasterize import pdf_page_count, rasterize_page
from ocr.render import REPORT_CSP_HEADER, REPORT_CSP_META
from analysis import package as package_view
from analysis.package.model import is_count, is_money_value, num, statement_currency
from analysis.package.publish import TIER_REASON_KEYS
from analysis.payload_shape import is_document_payload, payload_accounts, payload_document_block
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.adb import ADVISORY_VALIDATIONS as ADB_ADVISORY_VALIDATIONS
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.revenue_view import (
    LARGE_UNSOURCED_DEPOSIT_FIELDS,
    UNESTABLISHED_WITHHOLDING_BASIS_KEYS,
    WITHHOLDING_BASIS_UNESTABLISHED,
)
from analysis import zelle_view
from analysis.holder_name import PREMIUM_TRUST_WORDS
from analysis.served_view import displayed, zelle_setting
from analysis.zelle_view import ZELLE_DEPOSITS_KEY, ZELLE_ROW_TAG
from spreadsheet_safety import FORMULA_LEAD, NUMERIC_CELL, escape_formula
from .jobs import JobStore
from .settings import load_settings, save_settings
from .storage import SCHEMA_VERSION, Storage
from .worker import run_job
from .reanalysis import replay_reviews, rerun_analysis

# Upload ceilings. Every value here is enforced server-side and mirrored in the
# dropzone caption, so what the operator is told is what the server does.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_FILES = 25
MAX_UPLOAD_PAGES = 500

# waitress worker threads. The dashboard polls /status for every in-flight job
# at once, so the stock four would head-of-line block.
SERVER_THREADS = 16

#: The free space the data volume keeps. Nothing ever deletes a job, document, PDF or artifact (retention is an
#: owner decision), and a full volume stops the server from starting. An upload, or a
#: Re-analyze, that would leave less than this is refused with 507 before anything is written. Default 256 MB;
#: `WEBAPP_MIN_FREE_MB` overrides it (0 turns the floor off).
DEFAULT_MIN_FREE_MB = 256


def _min_free_bytes(raw: str | None) -> int:
    """`WEBAPP_MIN_FREE_MB` as bytes. A value that is not a whole number of megabytes (0 or more) falls back to the
    default with a warning on stderr: a typo in this variable must never stop the server from starting."""
    if raw is None or not raw.strip():
        return DEFAULT_MIN_FREE_MB * 1024 * 1024
    try:
        megabytes = int(raw.strip())
    except ValueError:
        megabytes = -1
    if megabytes < 0:
        sys.stderr.write(
            f"WEBAPP_MIN_FREE_MB={raw!r} is not a whole number of megabytes; using {DEFAULT_MIN_FREE_MB}\n"
        )
        return DEFAULT_MIN_FREE_MB * 1024 * 1024
    return megabytes * 1024 * 1024


MIN_FREE_BYTES = _min_free_bytes(os.environ.get("WEBAPP_MIN_FREE_MB"))

#: The refusals the floor answers with (507): fixed text, never a measured figure or a path.
STORAGE_NEARLY_FULL = "the server's storage is nearly full; no statement was accepted"
STORAGE_NEARLY_FULL_REASON = "the server's storage is nearly full"


def _data_volume_nearly_full(incoming_bytes: int = 0) -> bool:
    """True when writing `incoming_bytes` would leave the data volume below MIN_FREE_BYTES. A free-space figure that
    cannot be read answers False: the guard fails open on itself only, it never refuses work by its own error."""
    try:
        free = shutil.disk_usage(store.storage.data_dir).free
    except OSError:
        return False
    return free - incoming_bytes < MIN_FREE_BYTES


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

#: How the store opened at start-up: None normally; STORE_READ_ONLY when it could not be opened or written but can
#: be read (saved statements are served, every write is refused); STORE_UNAVAILABLE when it cannot be read either
#: (only the page itself is served). Stopping the import instead would make the host restart the server until it
#: gave up, and nothing could be served.
STORE_READ_ONLY = "read_only"
STORE_UNAVAILABLE = "unavailable"

#: The 503 answers of a degraded start-up: fixed text.
STORAGE_READ_ONLY_ERROR = (
    "the server's storage could not be written when it started (the data volume may be full); saved statements can "
    "be viewed, but nothing can be uploaded, reviewed, re-analyzed, packaged, saved or downloaded until space is "
    "freed and the server is restarted"
)
STORAGE_UNAVAILABLE_ERROR = (
    "the server's storage could not be opened when it started (the data volume may be full); free space and restart "
    "the server"
)


#: The failures that mean the data volume cannot be written: SQLite's primary result codes SQLITE_READONLY (8),
#: SQLITE_IOERR (10; the outage's "disk I/O error" at the journal-mode PRAGMA), SQLITE_FULL (13) and
#: SQLITE_CANTOPEN (14), and the matching OS errors. A busy or locked database, a permission problem or a schema the
#: code does not understand is none of these: it still stops the start, as before, so a restart can clear it.
_SQLITE_VOLUME_FAILURES = frozenset({8, 10, 13, 14})
_OS_VOLUME_FAILURES = frozenset(
    code for code in (errno.ENOSPC, errno.EIO, errno.EROFS, getattr(errno, "EDQUOT", None)) if code is not None
)


def _volume_failure(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.Error):
        code = getattr(exc, "sqlite_errorcode", None)
        return isinstance(code, int) and (code & 0xFF) in _SQLITE_VOLUME_FAILURES
    if isinstance(exc, OSError):
        return exc.errno in _OS_VOLUME_FAILURES
    return False


def _open_store() -> tuple[JobStore, list[str], str | None]:
    """The durable store (D-1) and the startup re-hydration, without letting a full volume stop the server.

    Startup re-hydration: any job left queued/processing by a previous process
    is explicitly marked `interrupted` with an explanatory error — never
    silently lost. Completed jobs need nothing: their artifacts already serve
    from storage. (Auto-resume is deliberately not attempted: the one-worker
    queue holds no durable claim on partially processed OCR state, so a clean,
    explicit interruption the analyst can see beats a half-blind retry.)

    Only a failure of the data volume itself (`_volume_failure`: `disk I/O error` at the journal-mode PRAGMA,
    `database or disk is full` while marking interrupted jobs, a read-only or full filesystem) falls back to a
    read-only store. Anything else (a locked database, a schema the code does not understand, a refused data
    directory) still stops the start: those are not a full disk, and serving them would be wrong."""
    try:
        opened = JobStore()
        return opened, opened.mark_interrupted(), None
    except (sqlite3.Error, OSError) as exc:
        if not _volume_failure(exc):
            raise
    fallback = JobStore(Storage(read_only=True))
    try:
        if fallback.storage.schema_version() != SCHEMA_VERSION:
            return fallback, [], STORE_UNAVAILABLE
        return fallback, fallback.mark_interrupted(persist=False), STORE_READ_ONLY
    except (sqlite3.Error, OSError):
        return fallback, [], STORE_UNAVAILABLE


# Durable store (D-1): SQLite + on-disk PDFs under WEBAPP_DATA_DIR
# (default `webapp_data/` at repo root). See webapp/storage.py for the
# single-writer concurrency contract.
store, _INTERRUPTED_ON_STARTUP, STORE_STATE = _open_store()

_job_queue: deque[tuple[str, bytes, str, bool, str]] = deque()
_job_queue_lock = threading.Lock()
_job_worker_active = False


#: No exception class is exempt from the re-arm. In a worker thread, `SystemExit` and `KeyboardInterrupt` do not
#: end the process: `threading` hands them to the thread's excepthook and the interpreter continues. A real Ctrl-C
#: or `sys.exit` happens on the main thread and never passes through here. So a signal raised inside `run_job` is a
#: dead worker, not a dying process, and queued work would otherwise wait until the next upload.


def _release_worker_slot() -> bool:
    """Hand the one worker slot back after a worker thread dies mid-job.

    `_job_worker_active` claims the single worker slot. When `run_job` unwinds, the thread would otherwise die
    holding it, `_enqueue_job` would never start another worker, and later uploads would wait at `queued`.

    The slot is always released. A replacement starts when work is queued, and it claims the slot inside the same
    critical section that releases it (the claim-before-spawn order `_enqueue_job` keeps), so two workers never
    drain one queue.

    The re-arm cannot spin: the replacement pops from the same queue under the same lock, and `run_job` marks the
    popped job `error` before it re-raises, so a failure that repeats drains the queue one document per thread.

    Returns whether a replacement was started.
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
            job_id, pdf_bytes, filename, force_ocr = _job_queue.popleft()
        try:
            run_job(job_id, pdf_bytes, filename, store, force_ocr)
        except BaseException:
            # The handler is on the SUPERVISOR and not on `run_job`'s arm, which
            # is the point: the arm must keep
            # re-raising (swallowing a death is worse than a stranded queue),
            # so the slot has to be released by whoever owns it. Nothing is
            # swallowed here either — the `raise` below is bare, so the stderr
            # traceback and the thread's death are unchanged — and nothing is
            # inspected: the class of what escaped decides nothing (the note
            # above `_release_worker_slot`).
            _release_worker_slot()
            raise


def _enqueue_job(job_id: str, pdf_bytes: bytes, filename: str, force_ocr: bool) -> None:
    global _job_worker_active
    with _job_queue_lock:
        _job_queue.append((job_id, pdf_bytes, filename, force_ocr))
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


#: What a package and its member rows carry for the dashboard alone, left out of the package downloads (the
#: re-analyze note's flag, S6 review, reads off the served copies and names no figure).
_PACKAGE_DISPLAY_ONLY_KEYS = ("nsf_days", "analysis_rules_outdated")


def _package_for_export(package: dict) -> dict:
    """A copy of a package payload without the fields only the dashboard reads: from the package itself and from
    its member rows, which it lists twice (`documents`, and `monthly` for the members with a period)."""
    exported = {key: value for key, value in package.items() if key not in _PACKAGE_DISPLAY_ONLY_KEYS}
    for section in ("documents", "monthly"):
        rows = package.get(section)
        if isinstance(rows, list):
            exported[section] = [
                _export_document_revenue(
                    {key: value for key, value in row.items() if key not in _PACKAGE_DISPLAY_ONLY_KEYS}
                ) if isinstance(row, dict) else row
                for row in rows
            ]
    # The package's counted-plus-held figures, and the held count, are partial when a member's revenue is not
    # established (its True, Counted and Held totals are already None, §10.4), so a download leaves them empty too.
    # So does a package that analyses no statement (R54: its True, Verified, Counted and Held are already None),
    # whose revenue counts are left empty too, never the 0.0 or 0 an underwriter would read as a measured decline.
    # The served totals keep them: the dashboard's review badge reads its null True count as N/A, and would read a
    # null held count as a payload analysed before 5.6.
    totals = package.get("totals")
    no_analysis = isinstance(totals, dict) and totals.get("completed") == 0
    if isinstance(totals, dict) and (totals.get("revenue_unestablished_documents") or no_analysis):
        emptied = (*_PACKAGE_PARTIAL_REVENUE_KEYS, *(_PACKAGE_NO_ANALYSIS_COUNT_KEYS if no_analysis else ()))
        totals = exported["totals"] = {**totals, **{key: None for key in emptied if key in totals}}
    # §10.4, §11: the withholding basis summed over a member whose basis is not established is an empty cell, as
    # the dashboard reads it N/A. So is the sum of members analysed under different bases, which is no basis at
    # all.
    if isinstance(totals, dict) and (totals.get(WITHHOLDING_BASIS_UNESTABLISHED) is True
                                     or totals.get("withholding_basis_mixed") is True):
        exported["totals"] = {
            **totals, **{key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in totals},
        }
    return exported


#: The package totals built from every member's counted and held credits, and the held count.
_PACKAGE_PARTIAL_REVENUE_KEYS = ("maximum_revenue", "potential_revenue_total", "unverified_deposit_total",
                                 "revenue_review_items")
#: The package's revenue counts, which a download also leaves empty when the package analyses no statement
#: (`completed` 0: every job failed, was interrupted, is still on its way or holds no analysis, or every account was
#: left out), beside R54's empty True, Verified, Counted and Held.
_PACKAGE_NO_ANALYSIS_COUNT_KEYS = ("unverified_deposit_count", "potential_revenue_count", "verified_revenue_count",
                                   "confirmed_true_revenue_count")


def _export_document_revenue(row: dict) -> dict:
    """A member's row as the package downloads print it: its Verified figure (and the alias of it) empty unless
    established, and its counted-plus-held figures empty unless its revenue is. A left-out repeat's row carries no
    figure and is unchanged."""
    if row.get("is_duplicate") is True:
        return row
    nulled = {}
    if row.get("verified_revenue_established") is False:
        nulled.update({key: None for key in ("verified_revenue_total", "confirmed_true_revenue_total") if key in row})
    if row.get("revenue_established") is False:
        nulled.update({key: None for key in ("unverified_deposit_total", "potential_revenue_total", "maximum_revenue")
                       if key in row})
    # §10.4, §11: a member whose withholding basis is not established prints no basis.
    if row.get(WITHHOLDING_BASIS_UNESTABLISHED) is True:
        nulled.update({key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in row})
    return {**row, **nulled} if nulled else row


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


# The formula-injection rule (R-24) lives in `spreadsheet_safety`, which `batch.py` shares; these names stay
# importable from here.
_FORMULA_LEAD = FORMULA_LEAD
_NUMERIC_CELL = NUMERIC_CELL
_escape_formula = escape_formula


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
    ledger would collapse into a single unreadable JSON cell.

    A validation reads "pass" or "FAIL"; one of `ADB_ADVISORY_VALIDATIONS`,
    which decides nothing, reads "advisory pass" or "advisory FAIL", so its
    False on a published ADB is not read as a failed required check."""
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
        verdict = "pass" if passed else "FAIL"
        if name in ADB_ADVISORY_VALIDATIONS:
            verdict = f"advisory {verdict}"
        rows.append(("adb_validation", name, verdict))
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

#: §10.8, §17.1: the words that make a printed account title read as a bank's account designation in the statement
#: CSV/XLSX: analysis/holder_name.py's `_DESIGNATION_WORDS` (copied, not imported, so the reader stays private; a test
#: pins that every one of them is here), then the account words and the product words the banks print as a title ('US
#: BUSINESS ACCOUNT', 'CAD CHEQUING ACCOUNT', '(RECEIVABLES)'), then the Lloyd's market's name, which a bank prints as
#: the designation of an insurance agency's account holding Lloyd's premiums ('LLOYDS OF LONDON' after the agency's
#: legal form; Lloyd's of London, the public insurance market, requires its coverholders to keep the premiums they
#: collect in a separate trust account).
_EXPORT_DESIGNATION_WORDS = frozenset({
    "PREMIUM", "TRUST", "OPERATING", "WIRE", "PRODUCER", "PAYABLE", "ESCROW", "PAYROLL", "CLIENT", "CLIENTS",
    "CUSTOMER", "RESERVE", "TAX", "GENERAL", "SWEEP", "MAIN", "IOLTA", "DEPOSIT", "DISBURSEMENT", "COLLECTION",
    "ACCOUNT", "ACCT", "CHECKING", "CHEQUING", "SAVINGS", "RECEIVABLE", "RECEIVABLES",
    "LLOYDS", "LLOYD'S",
})
#: The premium-trust words (holder_name.PREMIUM_TRUST_WORDS, public: 'PREM TRST', 'PREMIUM FUNDS TRUST').
_EXPORT_PREMIUM_TRUST_TITLE = re.compile(PREMIUM_TRUST_WORDS)
#: The punctuation a title's word is trimmed of at either end, brackets included ('(RECEIVABLES)' is RECEIVABLES).
_TITLE_WORD_TRIM = "()[]{}<>.,;:!?'\"-/#*&"


def _designation_title(title: object) -> bool:
    """Whether a printed account title reads as a bank's account designation: a word of it, read upper case with its
    dots dropped and its brackets and punctuation trimmed, is in `_EXPORT_DESIGNATION_WORDS`, or it prints the
    premium-trust words. An owner's name or a legal-form fragment ('LIABILITY', 'BILLS') does not."""
    if not isinstance(title, str) or not title.strip():
        return False
    text = title.upper()
    if _EXPORT_PREMIUM_TRUST_TITLE.search(text):
        return True
    return any(token.replace(".", "").strip(_TITLE_WORD_TRIM) in _EXPORT_DESIGNATION_WORDS for token in text.split())


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

    True revenue spec §2.2, §10.8: the payload is read as the downloads read it
    (`_downloads_view`), with no Verified revenue and no "Counted, not
    verified".
    """
    analysis = _downloads_view(analysis)
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
                # A printed title is written only where it reads as a bank's account designation; an owner's name or a
                # legal-form fragment read as the title is left out of the flat sheet (the JSON download and the served
                # payload keep it as read).
                if section == "statement" and key == "account_title" and not _designation_title(item):
                    continue
                if section == "metrics" and key in ("adb", *TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY,
                                                    LARGE_UNSOURCED_DEPOSITS_KEY):
                    continue  # emitted as their own sections below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
                rows.append((section, key, "" if item is None else item))
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
        rows.extend(_tier_reason_rows(metrics))
        rows.extend(_zelle_deposit_rows(metrics.get(ZELLE_DEPOSITS_KEY)))
        # §10.8: one section per large unsourced deposit the served copy flags (its count and total are metric rows
        # above); nothing where none is flagged.
        rows.extend(_large_unsourced_deposit_rows(metrics.get(LARGE_UNSOURCED_DEPOSITS_KEY)))
    detection = analysis.get("detection")
    if isinstance(detection, dict):
        for key, item in detection.items():
            if key in ("flagged_positions", "lender_payment_changes"):
                continue  # emitted as readable rows below
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
        rows.extend(_lender_payment_change_rows(detection.get("lender_payment_changes")))
    return rows


#: True revenue spec §10.8: the fields of a `lender_payment_change_<n>` section, in order; a field the item does not
#: carry is an empty cell. `first_after_kind`, `resumed_date` (a pause) and `last_step_percent` (a change through
#: unreported levels) describe the change; a pause's catch-up (`first_after_amount`, `first_after_multiple`) and its
#: debits of 2x or more inside the gap (`larger_debits_inside`, "2054-03-16 1300.0;..."); a Caught up item's fields
#: (`missed_payments` to `catch_up_amount`); a pause's catch-ups after the presence that ended it, before payments
#: resumed (`catch_ups_inside`, "2054-03-17 1700.0 2x; ...").
LENDER_PAYMENT_CHANGE_EXPORT_FIELDS = (
    "kind", "lender", "lender_label", "lender_label_after", "lender_state", "position", "positions",
    "cadence", "cadence_before", "cadence_after", "amount_before", "amount_after", "change_percent", "cadence_changed",
    "schedule_confirmed", "weekly_equivalent_before", "weekly_equivalent_after", "payments_before", "payments_after",
    "last_before_date", "first_after_date", "last_after_date", "first_after_kind", "resumed_date",
    "first_after_amount", "first_after_multiple", "larger_debits_inside", "catch_ups_inside", "restart",
    "pause_business_days", "back_to_earlier", "reverted", "reverted_date", "via", "last_step_percent",
    "weekly_total_before", "weekly_total_after", "alongside",
    "last_payment_date", "last_payment_amount", "payments", "last_presence_date", "quiet_business_days",
    "grace_business_days", "coverage_end", "coverage_end_source", "stop_confirmed",
    "missed_payments", "missed_first_date", "missed_last_date", "multiple", "catch_up_date", "catch_up_amount",
)
#: The nested notes, flattened with dots. A stop's `other_debits_after.catch_ups` and `payoff.earlier`, and a pause's
#: or a stop's `same_amount_debits`.
LENDER_PAYMENT_CHANGE_NOTE_FIELDS = (
    ("after_funding", ("date", "amount")),
    ("other_debits_after", ("count", "last_date", "catch_ups")),
    ("payoff", ("date", "amount", "earlier")),
    ("same_amount_debits", ("count", "first_date", "last_date")),
    ("continues_as", ("lender_label", "amount", "first_date")),
    ("new_lender_after", ("lender_label", "cadence", "amount", "first_date")),
    ("debt_relief_after", ("date",)),
    ("other_stream_continues", ("amount", "cadence")),
    ("last_attempt_returned", ("date",)),
)
#: The package's added fields.
LENDER_PAYMENT_CHANGE_PACKAGE_FIELDS = (
    "source_document", "from_document", "to_document", "cross_statement", "source_currency", "source_period_end",
)


def _lender_payment_change_rows(items: object, *, package: bool = False) -> list[tuple[str, str, object]]:
    """One readable section per lender payment change, `lender_payment_change_<n>`, with
    LENDER_PAYMENT_CHANGE_EXPORT_FIELDS and the dotted notes (a package adds its source fields and the other-account
    note). A label is statement text: these rows reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for number, item in enumerate((entry for entry in items if isinstance(entry, dict))
                                  if isinstance(items, list) else (), start=1):
        section = f"lender_payment_change_{number}"
        for name in LENDER_PAYMENT_CHANGE_EXPORT_FIELDS:
            value = item.get(name)
            if name in ("alongside", "via") and isinstance(value, list):
                # A via level carries the step into it: "weekly 950.0 (-5%)".
                value = "; ".join(f"{entry.get('cadence')} {entry.get('amount')}"
                                  + (f" ({entry['change_percent']:+d}%)" if name == "via"
                                     and isinstance(entry.get("change_percent"), int) else "")
                                  for entry in value if isinstance(entry, dict))
            elif name == "larger_debits_inside" and isinstance(value, list):
                # "2054-03-16 1300.0; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')}" for entry in value
                                  if isinstance(entry, dict))
            elif name == "catch_ups_inside" and isinstance(value, list):
                # "2054-03-17 1700.0 2x; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')} {entry.get('multiple')}x"
                                  for entry in value if isinstance(entry, dict))
            rows.append((section, name, "" if value is None else value))
        # The package's reappearance note beside the continuation.
        notes = LENDER_PAYMENT_CHANGE_NOTE_FIELDS + ((
            ("continues_in_other_account", ("source_document", "first_date", "amount")),
            ("reappears_in_other_account", ("source_document", "first_date", "amount", "covered_business_days")),
        ) if package else ())
        for note, fields in notes:
            value = item.get(note)
            for name in fields:
                cell = value.get(name) if isinstance(value, dict) else None
                rows.append((section, f"{note}.{name}", "" if cell is None else cell))
        if package:
            for name in LENDER_PAYMENT_CHANGE_PACKAGE_FIELDS:
                value = item.get(name)
                rows.append((section, name, "" if value is None else value))
    return rows


def _tier_reason_rows(figures: dict, section: str = "revenue_tier") -> list[tuple[str, str, object]]:
    """One row per tier, reason and figure: `(revenue_tier, <tier>.<reason>.count | .total, value)`. A reason code
    is a constant of analysis/revenue.py; the rows still reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for key in TIER_REASON_KEYS:
        reasons = figures.get(key)
        tier = key[: -len("_by_reason")]
        for reason, slot in (reasons.items() if isinstance(reasons, dict) else ()):
            for field in ("count", "total"):
                value = slot.get(field) if isinstance(slot, dict) else None
                rows.append((section, f"{tier}.{reason}.{field}", "" if value is None else value))
    return rows


def _zelle_deposit_rows(
    figures: object, section: str = "revenue_tier", *, setting: bool | None = None,
) -> list[tuple[str, str, object]]:
    """Spec §10.8: the served Zelle figures (`zelle_deposits`, analysis/zelle_view.py) as readable rows of the
    revenue_tier section, only where the key is present: `zelle_deposits.setting` (Yes or No), `.count`, `.total`,
    `.<tier>.count`, `.<tier>.total` and `.setting_applied`. A money figure the package refuses is an empty cell.
    `setting` is the choice the figures were served under; an account's figures say it themselves (Yes exactly when
    the reading served is the one the setting asked for and counts, or is not and does not: `counted_as_true_revenue`
    equals `setting_applied`)."""
    if not isinstance(figures, dict):
        return []
    if setting is None:
        setting = figures.get("counted_as_true_revenue") is (figures.get("setting_applied") is not False)
    rows: list[tuple[str, str, object]] = [(section, "zelle_deposits.setting", "Yes" if setting else "No")]
    for field in ("count", "total"):
        value = figures.get(field)
        rows.append((section, f"zelle_deposits.{field}", "" if value is None else value))
    by_tier = figures.get("by_tier")
    for tier, slot in (by_tier.items() if isinstance(by_tier, dict) else ()):
        for field in ("count", "total"):
            value = slot.get(field) if isinstance(slot, dict) else None
            rows.append((section, f"zelle_deposits.{tier}.{field}", "" if value is None else value))
    rows.append((section, "zelle_deposits.setting_applied", figures.get("setting_applied") is not False))
    return rows


#: True revenue spec §9.1, §9.2, §10.8: the served list of large unsourced deposits (a statement's metrics key, a
#: package's top-level key) and the fields of a statement's and a package's `large_unsourced_deposit_<n>` section:
#: LARGE_UNSOURCED_DEPOSIT_FIELDS, then the member's. §2.2, §10.8: without `revenue_tier_reason`, the counted tier's
#: reason (such a credit is counted in True revenue without proof of the sale); the JSON download keeps it.
LARGE_UNSOURCED_DEPOSITS_KEY = "large_unsourced_deposits"
_LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS = tuple(
    field for field in LARGE_UNSOURCED_DEPOSIT_FIELDS if field != "revenue_tier_reason")
_PACKAGE_LARGE_UNSOURCED_DEPOSIT_FIELDS = (
    *_LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS, "source_job", "source_document", "source_account", "source_currency",
)


def _large_unsourced_deposit_rows(
    items: object, fields: tuple[str, ...] = _LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS,
) -> list[tuple[str, str, object]]:
    """§10.8: one readable section per flagged credit, `large_unsourced_deposit_<n>`, in served order, its `fields` (an
    empty cell where the item has none). A description is statement text: these rows reach a file only through
    `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    entries = [entry for entry in items if isinstance(entry, dict)] if isinstance(items, list) else []
    for number, item in enumerate(entries, start=1):
        for field in fields:
            value = item.get(field)
            rows.append((f"large_unsourced_deposit_{number}", field, "" if value is None else value))
    return rows


def _flagged_position_rows(positions: object) -> list[tuple[str, str, object]]:
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited, the credits it paid in and their
    total, the cadence, and (5.3) whether the payee is unconfirmed (`review_required`).

    Served payloads hold only the ticked groups (analysis/flagged_view.py via `displayed`), so the sheet follows
    Settings. A payee name is statement text: these rows reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    numbers: dict[str, int] = {}
    for entry in positions if isinstance(positions, list) else []:
        group = entry.get("group") if isinstance(entry, dict) else None
        if not isinstance(group, str) or group not in FLAG_GROUP_BY_KEY:
            continue
        numbers[group] = numbers.get(group, 0) + 1
        for field in ("payee", "count", "total_debited", "count_credited", "total_credited", "cadence",
                      "review_required"):
            value = entry.get(field)
            rows.append((f"flagged_{group}_{numbers[group]}", field, "" if value is None else value))
    return rows


#: The columns of the statement downloads' posted-credit table. True revenue spec §2.2, §10.8: no `state` column
#: (the 5.4 state, `verified_revenue` or `unverified_deposit`).
_POSTED_CREDIT_COLUMNS = ("date", "description", "amount", "currency", "tier", "reason", "review_status")


def _tier_cell(record: dict) -> str:
    """A ledger row's `tier` cell, from a record as the downloads read it (`_downloads_view`): its tier, or for a
    credit analysed before 5.6, which has none, its state in the page's words (`revenue`, `review_required` or
    `non_revenue`, as its tag reads); empty for a row with neither."""
    return record.get("revenue_tier") or record.get("revenue_classification") or ""


def _posted_credit_table(analysis: dict) -> list[tuple]:
    """One row per posted credit, so an underwriter can check, deposit by deposit, which credits make up True (the
    ledger otherwise sits in one JSON cell, over a spreadsheet's cell limit on most statements): a `columns` row, then
    `(section, n, date, description, amount, currency, tier, reason, review status)`. The tier and reason are the
    payload's codes (analysis/revenue.py), as the downloads read them (`_downloads_view`: a credit in True revenue is
    `true_revenue`, with no reason; `_tier_cell` before 5.6). Every account of a document payload has its own block,
    under its section prefix. A block written after the flat rows (`_analysis_rows` stays three columns for its
    readers); its statement text reaches a file only through `_escaped_rows`."""
    analysis = _downloads_view(analysis)
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_posted_credit_table")
        return [
            (f"account_{index}.{row[0]}", *row[1:])
            for index, account in enumerate(accounts, start=1)
            for row in _posted_credit_table(account)
        ]
    statement = analysis.get("statement") if isinstance(analysis, dict) else None
    if not isinstance(statement, dict):
        return []
    currency = statement_currency(analysis) or ""
    rows: list[tuple] = []
    tagged: list[bool] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = num(transaction.get("amount"))
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        if amount <= 0 or record.get("is_posted") is False:
            continue
        rows.append(("posted_credit", len(rows) + 1, transaction.get("date") or "",
                     transaction.get("description") or "", amount, currency, _tier_cell(record),
                     record.get("revenue_tier_reason") or "", record.get("revenue_review_status") or ""))
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # A trailing `zelle` column, only in a block where a row carries the served Zelle tag (Yes), 'Zelle' on those rows;
    # every other block is today's.
    if any(tagged):
        return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS, "zelle"),
                *((*row, "Zelle" if zelle else "") for row, zelle in zip(rows, tagged))]
    return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS), *rows]


#: The columns of the statement downloads' posted-debit table; the last, a confirmed funder's payment the bank
#: returned unpaid (the location of the credit that returned it, the record's `returned_funder_payment_by`).
_POSTED_DEBIT_COLUMNS = (
    "date", "description", "amount", "currency", "classification", "flagged_group", "canonical_entity",
    "review_required", "returned_funder_payment",
)


def _posted_debit_table(analysis: dict) -> list[tuple]:
    """One row per posted debit, the posted-credit table's twin, so the lender payments, the withholding and the NSFs
    read row by row (the ledger otherwise sits only in one JSON cell, over a spreadsheet's cell limit on most
    statements): a `columns` row, then `(posted_debit, n, date, description, amount (signed), currency, classification,
    flagged group, entity, review required, returned funder payment)`. The flag group is written only where Settings
    shows it (`flag_shown`, analysis/flagged_view.py), so an unticked group never leaks; the other fields are the
    record's as served (the last, `returned_funder_payment_by`: where a confirmed funder's payment came back
    unpaid, the location of the credit that returned it). Every account of a document payload has its own block, under
    its section prefix. Written after the credit table; its statement text reaches a file only through `_escaped_rows`."""
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_posted_debit_table")
        return [
            (f"account_{index}.{row[0]}", *row[1:])
            for index, account in enumerate(accounts, start=1)
            for row in _posted_debit_table(account)
        ]
    statement = analysis.get("statement") if isinstance(analysis, dict) else None
    if not isinstance(statement, dict):
        return []
    currency = statement_currency(analysis) or ""
    rows: list[tuple] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = num(transaction.get("amount"))
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        if amount >= 0 or record.get("is_posted") is False:
            continue
        review = record.get("review_required")
        rows.append(("posted_debit", len(rows) + 1, transaction.get("date") or "",
                     transaction.get("description") or "", amount, currency, record.get("classification") or "",
                     (record.get("flagged_group") or "") if record.get("flag_shown") is True else "",
                     record.get("canonical_entity") or "", review if isinstance(review, bool) else "",
                     record.get("returned_funder_payment_by") or ""))
    if not rows:
        return []
    return [("posted_debit", "columns", *_POSTED_DEBIT_COLUMNS), *rows]


#: True revenue spec §2.2, §10.8: "Can you get rid of verified revenue from the fronted end please and "counted, not
#: verified" still keep them in the backend but don't show it", the CSV and Excel downloads included ("Hide them there
#: too"). These downloads name no Verified revenue and no "Counted, not verified" (the tiers `verified` and
#: `counted_flagged`) as things of their own: True revenue, their sum, Held for review and Non-revenue stay, and no
#: figure moves. The served payload, the JSON download, the CLI and every stored analysis keep both tiers: only the CSV
#: and XLSX row builders (`_analysis_rows`, `_posted_credit_table`, `_package_rows` and `_package_transaction_table`)
#: read a payload through `_downloads_view`, so every CSV and XLSX download does.
_HIDDEN_TIERS = frozenset({"verified", "counted_flagged"})
#: The tier a credit of a hidden tier is written as: True revenue, of which each is a part.
_TRUE_REVENUE_TIER = "true_revenue"
#: Every key that names a hidden tier, its figures or an alias of them, left out wherever it sits: `verified_revenue_*`
#: (with `avg_monthly_verified_revenue` and the records' `contributes_to_verified_revenue`), `counted_flagged_*`,
#: `unverified_deposit_*` (5.4's name for counted plus held), `potential_revenue*` and `confirmed_true_revenue*` (the
#: aliases of those two) and the Zelle figures' `verified` and `counted_flagged` slots (merged first, below). A payload
#: analysed before 5.6 has no tier: its 5.4 lists and its deposits to review are renamed first (`_OLDER_KEY_WORDS`).
_HIDDEN_TIER_KEY = re.compile(r"verified|counted_flagged|potential_revenue|confirmed_true_revenue")
#: A classification record's 5.4 state (`verified_revenue`, `unverified_deposit` or `non_revenue`), current and initial.
#: On a credit with a tier (5.6 on), the tier says what the state says without the verified and counted split, so the
#: state is left out unless it is `non_revenue`; on a credit analysed before 5.6 (no tier) the state is its only revenue
#: reading and is written in the page's words (`_OLDER_STATE_WORDS`).
_STATE_KEYS = frozenset({"revenue_classification", "revenue_initial_classification"})
#: The page's words for a pre-5.6 credit's state, as its tag reads (app.js transactionCategory: "Revenue", "Review
#: required", "Non-revenue"): never 5.4's `verified_revenue` or `unverified_deposit`.
_OLDER_STATE_WORDS = {
    "verified_revenue": "revenue", "unverified_deposit": "review_required", "non_revenue": "non_revenue",
}
#: A pre-5.6 account's revenue view (`_older_revenue_view`) writes its 5.4 lists under the page's words, and its
#: deposits to review (what its review view lists and its badge counts) with their count and total. A 5.6 view's
#: `unverified_deposit_*` is counted plus held, an alias of a hidden tier, and is left out.
_OLDER_KEY_WORDS = {
    "verified_revenue_evidence": "revenue_evidence",
    "unverified_deposit_evidence": "review_required_evidence",
    "unverified_deposit_count": "review_required_count",
    "unverified_deposit_total": "review_required_total",
}
#: A record's rule and its sentence (`revenue_matched_rule`, `revenue_reason`): why the rules read it as they did. A
#: credit in True revenue carries neither (a counted one's says the source is not confirmed); a held or non-revenue
#: one keeps both, the words naming a hidden tier rewritten (`_SENTENCE_REWRITES`, `_ZELLE_READING`), and a rule or
#: sentence that still names one after that is left out.
_RULE_KEYS = frozenset({"revenue_matched_rule", "revenue_reason"})
_HIDDEN_TIER_WORDS = re.compile(r"verified|counted and flagged|counted_flagged|counted, not verified", re.IGNORECASE)
#: The rewrites of a held or non-revenue sentence, in order: the hold of a counted re-statement ("never verified,
#: and held for review (<label>)"), the $1 floor's hold of a verified credit ("is never verified and never counted") and
#: the holder's own push a rule verified ("never revenue and never verified;").
_SENTENCE_REWRITES = (
    ("never verified, and held for review (", "held for review ("),
    ("is never verified and never counted", "is never counted in True revenue"),
    (" and never verified;", ";"),
)
#: Q3's sentence on a Zelle deposit the policy excluded ends on the rules' reading (analysis/true_revenue.py
#: `_zelle_excluded`): "...; the rules read it as: <label>." A reading in a hidden tier ("Verified revenue", a counted
#: reason's label) is written "True revenue.", as the page says it (app.js zellePriorSentence); a held one keeps its
#: label.
_ZELLE_READING = "the rules read it as: "
#: The counted tier's reason codes (analysis/revenue.py REVENUE_TIER_REASONS), left out wherever a record carries one:
#: on a credit counted in True revenue, on one a reviewer confirmed and on one a reviewer rejected (which keeps it).
_COUNTED_REASONS = frozenset(code for code, (tier, _label) in REVENUE_TIER_REASONS.items() if tier == "counted_flagged")
#: The lender classifier's sentence on a row no lender, insurance or category rule read (most credits,
#: analysis/transaction_classifier.py), whose "verified" is a lender's, never a revenue tier, written without the word.
_UNMATCHED_ROW_REASONS = {
    "No verified lender, insurance, or operational-category rule matched.":
        "No lender, insurance, or operational-category rule matched.",
}
#: The verified withholding basis (WITHHOLDING_DENOMINATOR_MODE=verified_revenue; never chosen on screen), as the page
#: names it (app.js WITHHOLDING_BASIS_LABELS): its mode (`narrower_revenue_basis`, a downloads-only code naming no tier;
#: the backend's mode stays `verified_revenue`), its label and its definition, and in a note's sentence, in lower case
#: as the page's rate note names it; the True basis's definition in the page's words. Its figures are unchanged.
_NARROWER_BASIS_MODE = "narrower_revenue_basis"
_NARROWER_BASIS_LABEL = "Narrower revenue basis"
_NARROWER_BASIS_IN_A_NOTE = "the narrower revenue basis"
_BASIS_DEFINITIONS = {
    "verified_revenue": "a part of true revenue only",
    "true_revenue": "true revenue: posted credits minus known non-revenue and the deposits held for review",
}
#: The context signal that keeps a Zelle deposit's reading with Zelle counted (analysis/true_revenue.py `_ZELLE_PRIOR`).
_ZELLE_PRIOR = "zelle_prior:"


def _true_revenue_slot(slots: list) -> dict | None:
    """The Zelle figures' slot of True revenue: the `verified` and `counted_flagged` slots (`{count, total}`) added up, a
    count or a total empty (None) where a slot's is, as an unestablished or refused part is. None where neither is."""
    present = [slot for slot in slots if isinstance(slot, dict)]
    if not present:
        return None
    counts = [slot.get("count") for slot in present]
    totals = [slot.get("total") for slot in present]
    return {
        "count": sum(counts) if all(is_count(count) for count in counts) else None,
        "total": round(sum(totals), 2) if all(is_money_value(total) for total in totals) else None,
    }


def _zelle_by_tier_without_hidden_tiers(by_tier: dict) -> dict:
    """`zelle_deposits.by_tier` as the downloads read it: the `verified` and `counted_flagged` slots as one
    `true_revenue` slot, first, then the held and non-revenue slots as served."""
    slot = _true_revenue_slot([by_tier.get(tier) for tier in ("verified", "counted_flagged")])
    rest = {tier: value for tier, value in by_tier.items() if tier not in _HIDDEN_TIERS}
    return {_TRUE_REVENUE_TIER: slot, **rest} if slot is not None else rest


def _context_signals_without_hidden_tiers(signals: object) -> object:
    """A record's `revenue_context_signals` as the downloads read them: a Zelle deposit's prior reading in a hidden tier
    (`zelle_prior:verified`, `zelle_prior:counted_flagged:<reason>`) is `zelle_prior:true_revenue`, and any other signal
    naming a hidden tier is left out."""
    if not isinstance(signals, (list, tuple)):
        return signals
    kept = []
    for signal in signals:
        if isinstance(signal, str) and signal.startswith(_ZELLE_PRIOR):
            tier = signal[len(_ZELLE_PRIOR):].split(":", 1)[0]
            if tier in _HIDDEN_TIERS:
                signal = f"{_ZELLE_PRIOR}{_TRUE_REVENUE_TIER}"
        elif isinstance(signal, str) and _HIDDEN_TIER_KEY.search(signal):
            continue
        kept.append(signal)
    return tuple(kept) if isinstance(signals, tuple) else kept


def _older_revenue_view(node: dict) -> bool:
    """Whether `node` is an account's revenue view (its metrics or detection) analysed before 5.6: it lists 5.4's
    unverified deposits and no held tier (5.6's `excluded_pending_review_evidence` is a list; before it, None or
    absent). A package's lists always carry the held tier, so a package is never read as one."""
    return "unverified_deposit_evidence" in node and not isinstance(node.get("excluded_pending_review_evidence"), list)


def _zelle_prior_tier(signals: object) -> str | None:
    """The tier the rules gave a Zelle deposit the policy excluded (its `zelle_prior:<tier>:<reason>` signal), or
    None."""
    for signal in signals if isinstance(signals, (list, tuple)) else ():
        if isinstance(signal, str) and signal.startswith(_ZELLE_PRIOR):
            return signal[len(_ZELLE_PRIOR):].split(":", 1)[0]
    return None


def _reason_without_hidden_tiers(key: str, value: object, record: dict) -> object:
    """A held or non-revenue record's rule or sentence as the downloads write it: the sentence with the words that name
    a hidden tier rewritten (`_SENTENCE_REWRITES`; a Zelle deposit's reading in a hidden tier as "True revenue."), and
    None (left out) where the rule or the rewritten sentence still names one."""
    if not isinstance(value, str):
        return value
    if key == "revenue_reason":
        for old, new in _SENTENCE_REWRITES:
            value = value.replace(old, new)
        reading = value.rfind(_ZELLE_READING)
        if reading >= 0 and _zelle_prior_tier(record.get("revenue_context_signals")) in _HIDDEN_TIERS:
            value = f"{value[:reading + len(_ZELLE_READING)]}True revenue."
    return None if _HIDDEN_TIER_WORDS.search(value) else value


def _posted_row_key(job: object, account: object, location: object) -> tuple:
    """A posted row's key, `(statement job, account, location)`, as app.js `debitFlagKey` keys a large
    unsourced deposit, a record and a package ledger row. A statement's items and records name neither job nor account
    (they sit under the account that lists them); a package's name both, its account absent (None) for a one-account
    member."""
    return (job or None, account, location)


def _large_deposit_keys(node: dict) -> frozenset | None:
    """The keys (`_posted_row_key`) of the large unsourced deposits that `node` serves: a statement account's, in its
    `metrics`, or a package's, at its top level beside its combined ledger; None where `node` is neither."""
    metrics = node.get("metrics")
    if isinstance(metrics, dict):
        items = metrics.get(LARGE_UNSOURCED_DEPOSITS_KEY)
    elif isinstance(node.get("transactions"), list) and "totals" in node:
        items = node.get(LARGE_UNSOURCED_DEPOSITS_KEY)
    else:
        return None
    return frozenset(
        _posted_row_key(item.get("source_job"), item.get("source_account"), item.get("source_location"))
        for item in (items if isinstance(items, (list, tuple)) else ()) if isinstance(item, dict))


def _downloads_view(node: object, *, flagged: frozenset = frozenset(), scope: tuple = (None, None)) -> object:
    """A served payload (statement, document or package), or any part of it, as the CSV and XLSX downloads write it: a
    copy in which no key names a hidden tier (`_HIDDEN_TIER_KEY`), a classification record's hidden tier reads
    `true_revenue` (current and initial, and a package pass's `tier_before`), its counted reason is left out, its 5.4
    state is left out (a tier says it) or, before 5.6, written in the page's words (`_STATE_KEYS`), its rule and sentence
    are kept only out of True revenue, and without a hidden tier's words (`_RULE_KEYS`), a counted credit awaits no
    review unless it is a large deposit to source, a pre-5.6 view's lists are renamed (`_OLDER_KEY_WORDS`), the Zelle
    figures carry one True revenue slot, and the verified withholding basis reads as the page names it. Every figure is
    unchanged; the input is never mutated.

    A counted credit the payload flags as a large deposit to source keeps `pending`, as its row on the page keeps
    Confirm Revenue. `flagged` holds the flagged credits' keys (`_large_deposit_keys`, read from a statement account or
    a package as the walk reaches it, or passed in for a part of one) and `scope` the statement job and account the
    walk is under (a package row or record names its own)."""
    if isinstance(node, (list, tuple)):
        items = [_downloads_view(item, flagged=flagged, scope=scope) for item in node]
        return tuple(items) if isinstance(node, tuple) else items
    if not isinstance(node, dict):
        return node
    served_flags = _large_deposit_keys(node)
    if served_flags is not None:
        flagged, scope = served_flags, (None, None)
    if node.get("source_job"):
        scope = (node["source_job"], node.get("source_account"))
    record = "revenue_classification" in node
    tiered = isinstance(node.get("revenue_tier"), str)
    older = _older_revenue_view(node)
    out: dict = {}
    for key, value in node.items():
        if older and key in _OLDER_KEY_WORDS:
            out[_OLDER_KEY_WORDS[key]] = _downloads_view(value, flagged=flagged, scope=scope)
            continue
        if key == "by_tier" and isinstance(value, dict):
            value = _zelle_by_tier_without_hidden_tiers(value)
        if record and key in _STATE_KEYS:
            if not tiered:
                out[key] = _OLDER_STATE_WORDS.get(value, value)
            elif value == "non_revenue":
                out[key] = value
            continue
        if record and key in _RULE_KEYS:
            if node.get("revenue_tier") in _HIDDEN_TIERS:
                continue
            if value is not None:
                value = _reason_without_hidden_tiers(key, value, node)
                if value is None:
                    continue
            out[key] = value
            continue
        if _HIDDEN_TIER_KEY.search(str(key)):
            continue
        if key in ("revenue_tier", "revenue_initial_tier", "tier_before") and value in _HIDDEN_TIERS:
            value = _TRUE_REVENUE_TIER
        elif key in ("revenue_tier_reason", "reason_before") and value in _COUNTED_REASONS:
            value = None
        elif (key == "revenue_review_status" and value == "pending" and node.get("revenue_tier") == "counted_flagged"
              and _posted_row_key(*scope, node.get("source_location")) not in flagged):
            # A counted credit is in True revenue; the page offers it no review a verified one lacks, unless it is a
            # large deposit to source, whose row keeps Confirm Revenue.
            value = "not_required"
        elif key == "reason" and value in _UNMATCHED_ROW_REASONS:
            value = _UNMATCHED_ROW_REASONS[value]
        elif key == "revenue_context_signals":
            value = _context_signals_without_hidden_tiers(value)
        elif key in ("withholding_denominator_mode", "mode") and value == "verified_revenue":
            value = _NARROWER_BASIS_MODE
        elif key in ("withholding_denominator_label", "label") and value == "Verified revenue":
            value = _NARROWER_BASIS_LABEL
        elif key == "eligible_deposit_definition" and node.get("withholding_denominator_mode") in _BASIS_DEFINITIONS:
            value = _BASIS_DEFINITIONS[node["withholding_denominator_mode"]]
        elif key == "withholding_denominator_options" and isinstance(value, (list, tuple)):
            # Nothing on screen offers the verified basis, so it is no option, except on a statement analysed on it,
            # whose options list its own mode as the downloads name it.
            own = node.get("withholding_denominator_mode") == "verified_revenue"
            modes = [_NARROWER_BASIS_MODE if mode == "verified_revenue" else mode for mode in value
                     if mode != "verified_revenue" or own]
            value = tuple(modes) if isinstance(value, tuple) else modes
        elif key == "notes" and isinstance(value, (list, tuple)):
            # A withholding note names its basis by its label mid-sentence ("... because Verified revenue is zero or
            # missing"), so the narrower basis is named there in lower case.
            notes = [note.replace("Verified revenue", _NARROWER_BASIS_IN_A_NOTE) if isinstance(note, str) else note
                     for note in value]
            value = tuple(notes) if isinstance(value, tuple) else notes
        else:
            value = _downloads_view(value, flagged=flagged, scope=scope)
        out[key] = value
    return out


def _analysis_csv(analysis: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_escaped_rows(
        _analysis_rows(analysis) + _posted_credit_table(analysis) + _posted_debit_table(analysis)
    ))
    return buf.getvalue()


#: A package member's id: a job's id, or `<job id>#account_<n>` for an account of a document (app.js packageMember).
_PACKAGE_MEMBER_ID = re.compile(r"(.*)#account_\d+")
#: The fields of an `excluded_account_<n>` section of the package downloads, in order.
_EXCLUDED_ACCOUNT_FIELDS = ("job_id", "filename", "account_index", "account_count", "outcome", "reason")
#: The fields of a `repeated_account_<n>` section of the package downloads, in order, before its words: an account
#: of a kept document the package leaves out as a repeat (B11's `duplicate_statement`) or as a superseded printout
#: (R14's `superseded_interim` or `superseded_long_printout`).
_REPEATED_ACCOUNT_FIELDS = ("job_id", "filename", "account_index", "account_count", "outcome", "reason",
                            "duplicate_of")


def _repeated_account_words(entry: dict, filenames: dict[str, str]) -> str:
    """A repeated account of a document as the dashboard's duplicate notice names it (app.js renderDuplicateNotice):
    "account <n> of <file> repeats <file>", then the reason's words in parentheses for a superseded printout (none for a
    B11 repeat). A job is named by its listed row's filename, "an earlier statement" where none is listed (app.js
    nameOf)."""
    def name(job_id: object) -> str:
        return (filenames.get(str(job_id)) if job_id is not None else None) or "an earlier statement"

    index = entry.get("account_index")
    shown = f"{index:,}" if isinstance(index, int) and not isinstance(index, bool) else "N/A"
    words = f"account {shown} of {name(entry.get('job_id'))} repeats {name(entry.get('duplicate_of'))}"
    reason = entry.get("reason")
    return f"{words} ({SUPERSEDED_REASON_WORDS[reason]})" if reason in SUPERSEDED_REASON_WORDS else words


#: The fields of a `returned_funder_payment_<n>` section of the package downloads, in order, before its words: the
#: served warning item's, then the re-debit's of a payment the funder re-debited.
_RETURNED_FUNDER_PAYMENT_FIELDS = (
    "funder", "amount", "debit_date", "debit_location", "credit_date", "credit_location", "credit_description",
    "source_job", "source_document", "source_account", "source_currency", "cross_statement", "credit_job",
    "credit_document", "credit_account", "represented_date", "represented_location", "represented_kind",
    "represented_job", "represented_document", "represented_account",
)


#: The readable day and the uploaded file's name as app.js writes them in the lender notes of the owner's request
#: (readableDate, statementFileName), so the download's words are the dashboard's.
_READABLE_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_STATEMENT_ID_PREFIX = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})(?:[_\s-]+|$)", re.IGNORECASE)


def _readable_date(value) -> str:
    """app.js readableDate: "Jun 22, 2026" for an ISO day; any other value as given; N/A when missing."""
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if match:
        try:
            day = datetime(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            day = None
        if day is not None:
            return f"{_READABLE_MONTHS[day.month - 1]} {day.day}, {day.year}"
    return str(value) if value else "N/A"


def _statement_file_name(name) -> str:
    """app.js statementFileName: the uploaded file's name, any leading job id or UUID (and its separator) removed."""
    text = str(name if name is not None else "").strip()
    while text and _STATEMENT_ID_PREFIX.match(text):
        text = _STATEMENT_ID_PREFIX.sub("", text, count=1).strip()
    return text


def _returned_funder_payment_source(item: dict) -> str:
    """app.js paymentChangeSourceLine for a returned funder payment's note, read without a package page's rows (the
    downloads name each statement by its file, as the dashboard does where it has no rows): none on a statement's own
    item (it names no source; a returned payment's item carries no `scope`, which only a payment change's does), "From:
    <file> → <file>" for a match across statements, else "From: <file>"."""
    if "source_job" not in item and "source_document" not in item:
        return ""

    def label(prefix: str) -> str:
        return _statement_file_name(item.get(f"{prefix}_document")) or "a statement"

    if item.get("cross_statement") is True:
        return f"From: {label('source')} → {label('credit')}"
    return f"From: {label('source')}"


def _returned_funder_payment_words(item: dict) -> str:
    """A returned funder payment as the dashboard's warning reads it (app.js returnedFunderPaymentWarning, §10.1), its
    money as the downloads write money: the amount, then the item's own unit where it names one (the overlapping
    statements' words; no unit when it is unknown). A payment matched to its return across statements names both
    documents; a payment the funder re-debited names the re-debit and is counted once in the withholding rate. In the
    plain voice of the owner's request that the dashboard now writes (a headline, its sentences, the statements it
    comes from), so the download's words are the dashboard's."""
    amount = item.get("amount")
    money = (f"{abs(float(amount)):,.2f}" + (f" {item['source_currency']}" if item.get("source_currency") else "")
             if is_money_value(amount) else "N/A")
    quoted = f' (the bank printed: "{item["credit_description"]}")' if item.get("credit_description") else ""
    sentences = [f"{item.get('funder') or 'Confirmed lender'}: a payment was returned.",
                 f"The {money} payment on {_readable_date(item.get('debit_date'))} was returned unpaid on "
                 f"{_readable_date(item.get('credit_date'))}{quoted}."]
    if item.get("represented_date"):
        where = (f" ({_statement_file_name(item.get('represented_document')) or 'a statement'})"
                 if item.get("represented_job") or item.get("represented_document") else "")
        caught_up = item.get("represented_kind") == "caught_up"
        day = _readable_date(item["represented_date"])
        sentences.append(f"It was caught up on {day}{where}, by one debit of twice the payment." if caught_up
                         else f"It was taken again on {day}{where}.")
        sentences.append("It isn't counted as paid; it is counted once in the withholding rate, by the "
                         f"{'catch-up' if caught_up else 'second debit'}.")
    else:
        sentences.append("It isn't counted as paid, but it still counts in the withholding rate.")
    source = _returned_funder_payment_source(item)
    if source:
        sentences.append(f"{source}.")
    return " ".join(sentences)


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    """The package's flat export sheet, read as the downloads read it."""
    evidence_sections = _package_evidence_sections(package)
    # The sections are read apart from the package, so they take its large deposits to source.
    flagged = _large_deposit_keys(package) or frozenset()
    package = _downloads_view(package)
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        if key in (*TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
            continue  # emitted as readable rows below
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("totals", key, "" if value is None else value))
    rows.extend(_tier_reason_rows(totals))
    # The package's Zelle figures. The setting row reads the setting the package was built under (`setting`; its
    # `counted_as_true_revenue` is the members' reading), or, on a package built before the key, its
    # `counted_as_true_revenue`, which was the setting.
    package_zelle = totals.get(ZELLE_DEPOSITS_KEY)
    package_setting = None
    if isinstance(package_zelle, dict):
        package_setting = package_zelle["setting"] if isinstance(package_zelle.get("setting"), bool) else (
            package_zelle.get("counted_as_true_revenue") is True)
    rows.extend(_zelle_deposit_rows(package_zelle, setting=package_setting))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
    # money cells and read them as missing data rather than as refused units.
    for key, value in (package.get("currency") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("currency", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            if key in (*TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
                continue  # emitted as readable rows below
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"document_{idx}", key, "" if value is None else value))
        if document.get("duplicate_reason") in SUPERSEDED_REASON_WORDS:
            # The words the dashboard's notice gives a left-out shorter printout or printout of more than a month.
            rows.append((f"document_{idx}", "duplicate_reason_words",
                         SUPERSEDED_REASON_WORDS[document["duplicate_reason"]]))
        rows.extend(_tier_reason_rows(document, f"document_{idx}.revenue_tier"))
        rows.extend(_zelle_deposit_rows(document.get(ZELLE_DEPOSITS_KEY), f"document_{idx}.revenue_tier"))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
    for idx, duplicate in enumerate(package.get("duplicates") or [], start=1):
        for key, value in duplicate.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"duplicate_{idx}", key, "" if value is None else value))
    # Each listed job's filename by its id: a member id's job part to its row's filename, kept members and left-out
    # repeat rows alike, the first row of a job winning (app.js renderDuplicateNotice's nameOf), for the words below.
    filenames: dict[str, str] = {}
    for document in package.get("documents") or []:
        member = _PACKAGE_MEMBER_ID.fullmatch(str(document.get("id") or ""))
        filenames.setdefault(member[1] if member else str(document.get("id") or ""), document.get("filename"))
    # Each account left out of every figure for a reason other than a repeat (`excluded_account_<n>`), so the sheet
    # an underwriter reads names it. A repeated account of a document, a B11 repeat or an R14 superseded printout,
    # has its own `repeated_account_<n>` section below, and a whole repeated job its document row and duplicate group
    # above.
    excluded = [entry for entry in package.get("excluded_accounts") or [] if isinstance(entry, dict)]
    left_out = [entry for entry in excluded if entry.get("is_duplicate") is not True]
    for idx, entry in enumerate(left_out, start=1):
        for key in _EXCLUDED_ACCOUNT_FIELDS:
            value = entry.get(key)
            rows.append((f"excluded_account_{idx}", key, "" if value is None else value))
    # Each account of a kept document left out as a repeat, in listed order, its fields and then the dashboard
    # notice's words for it.
    repeated = [entry for entry in excluded if entry.get("is_duplicate") is True]
    for idx, entry in enumerate(repeated, start=1):
        for key in _REPEATED_ACCOUNT_FIELDS:
            value = entry.get(key)
            rows.append((f"repeated_account_{idx}", key, "" if value is None else value))
        rows.append((f"repeated_account_{idx}", "words", _repeated_account_words(entry, filenames)))
    # Each pair of overlapping statements that share credits, and the notice's words for it.
    for idx, pair in enumerate(totals.get("overlapping_statements") or [], start=1):
        for key, value in pair.items():
            rows.append((f"overlapping_statement_{idx}", key, "" if value is None else value))
        total = pair.get("shared_credit_total")
        # The shared money is the pair's account's, and its words say so; a pair whose currency is unknown prints no
        # unit, as the dashboard does.
        money = (f"{float(total):,.2f}" + (f" {pair['currency']}" if pair.get("currency") else "")
                 if is_money_value(total) else "N/A")
        rows.append((f"overlapping_statement_{idx}", "words", _overlap_words(pair, filenames, money)))
    # Each match the package passes made across its statements (`package_match_<n>`, its credit and debit as JSON) and
    # each debit they flag (`debit_flag_<n>`), the statement's words written through the escaped-row path like every
    # other cell.
    for section, entries in (("package_match", package.get("package_matches")), ("debit_flag", package.get("debit_flags"))):
        for idx, entry in enumerate(entries or [], start=1):
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    # §10.8: after the debit flags, each member's large unsourced deposit (`large_unsourced_deposit_<n>`),
    # its statement, account and unit named, its share its own statement's.
    rows.extend(_large_unsourced_deposit_rows(package.get(LARGE_UNSOURCED_DEPOSITS_KEY),
                                              _PACKAGE_LARGE_UNSOURCED_DEPOSIT_FIELDS))
    # Each lump-sum payoff (in paid to lenders, out of the withholding rate), `lump_sum_payoff_<n>`, its words the bank's,
    # through the escaped-row path.
    for idx, item in enumerate(package.get("lump_sum_payoffs") or [], start=1):
        if isinstance(item, dict):
            for key, value in item.items():
                rows.append((f"lump_sum_payoff_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("funders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"funder_{idx}", key, "" if value is None else value))
    # Each funder payment the bank returned unpaid, as the package serves it, its fields and then the dashboard's
    # warning line, each in its own statement's unit (a refused package sums none of them).
    returned = [item for item in package.get("returned_funder_payments") or [] if isinstance(item, dict)]
    for idx, item in enumerate(returned, start=1):
        for key in _RETURNED_FUNDER_PAYMENT_FIELDS:
            value = item.get(key)
            rows.append((f"returned_funder_payment_{idx}", key, "" if value is None else value))
        rows.append((f"returned_funder_payment_{idx}", "words", _returned_funder_payment_words(item)))
    for idx, funder in enumerate(package.get("potential_lenders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"potential_lender_{idx}", key, "" if value is None else value))
    # Each lender payment change across the package's statements, and each member not checked across statements with
    # its reason.
    rows.extend(_lender_payment_change_rows(package.get("lender_payment_changes"), package=True))
    for idx, entry in enumerate(package.get("lender_payment_changes_unchecked") or [], start=1):
        for key in ("source_document", "reason"):
            value = entry.get(key) if isinstance(entry, dict) else None
            rows.append((f"lender_payment_unchecked_{idx}", key, "" if value is None else value))
    # §10.8: each month's active and possible positions, the accounts added up, as the copied memo names them
    # (`active_positions_month_<n>`); N/A an empty cell.
    for idx, entry in enumerate(package.get("active_positions_by_month") or [], start=1):
        for key in ("month", "active_positions", "possible_positions"):
            value = entry.get(key) if isinstance(entry, dict) else None
            rows.append((f"active_positions_month_{idx}", key, "" if value is None else value))
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
    # One evidence section per tier, so credits in True and held ones (out of it) never share a section
    # (`_package_evidence_sections`), each record read as the downloads read it.
    for section, records in evidence_sections:
        for idx, evidence in enumerate(_downloads_view(records, flagged=flagged), start=1):
            for key, value in evidence.items():
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    return rows


def _package_evidence_sections(package: dict) -> tuple[tuple[str, list], ...]:
    """The package's revenue evidence, one section per tier, from the served lists, every posted credit of every member
    in exactly one. Per true revenue spec §2.2 and §10.8, the credits in True revenue are one
    section, `true_revenue_evidence` (the members' verified credits and their counted ones), where they were a Verified
    and a Counted section, written even where the package's True is N/A (a member analysed before 5.6), so a 5.6
    member's credits are never in no section; then the held credits; a member analysed before 5.6 (no tier) has its
    credits under its states in the page's words, `revenue_evidence` and `review_required_evidence` (5.4's unverified
    deposits, its review set); then every member's non-revenue credits. The True section is in the package ledger's
    order (`transactions`: each member's rows as printed, the members in the package's order), as a statement's True
    evidence is in its ledger's, where the served lists put every verified credit before every counted one, so that the
    point where its dates went back marked the counted tier."""
    verified = [record for record in package.get("verified_revenue_evidence") or [] if isinstance(record, dict)]
    unverified = [record for record in package.get("unverified_deposit_evidence") or [] if isinstance(record, dict)]

    def tiered(record: dict) -> bool:
        return isinstance(record.get("revenue_tier"), str)

    transactions = package.get("transactions") or []
    ledger: dict[tuple, int] = {}
    for position, transaction in enumerate(transactions):
        if isinstance(transaction, dict) and isinstance(transaction.get("classification"), dict):
            key = _posted_row_key(transaction.get("source_job"), transaction.get("source_account"),
                                  transaction["classification"].get("source_location"))
            ledger.setdefault(key, position)

    def ledger_position(record: dict) -> int:
        # A record the ledger does not list (none is expected) follows those it does, in served order (a stable sort).
        return ledger.get(_posted_row_key(record.get("source_job"), record.get("source_account"),
                                          record.get("source_location")), len(transactions))

    in_true = sorted([record for record in verified if tiered(record)]
                     + [record for record in unverified if record.get("revenue_tier") == "counted_flagged"],
                     key=ledger_position)
    return (
        ("true_revenue_evidence", in_true),
        ("excluded_pending_review_evidence",
         [record for record in unverified if record.get("revenue_tier") == "excluded_pending_review"]),
        ("revenue_evidence", [record for record in verified if not tiered(record)]),
        ("review_required_evidence", [record for record in unverified if not tiered(record)]),
        ("non_revenue_evidence", package.get("non_revenue_evidence") or []),
    )


#: The columns of the package downloads' ledger table. True revenue spec §2.2, §10.8: no `state` column (the 5.4 state,
#: `verified_revenue` or `unverified_deposit`); the tier and reason are read through `_downloads_view`.
_PACKAGE_TRANSACTION_COLUMNS = ("source_document", "source_account", "source_currency", "date", "description",
                                "amount", "classification", "tier", "reason", "review_status")


def _package_transaction_table(package: dict) -> list[tuple]:
    """The package's combined ledger (`transactions`), one row per posting, each naming its statement, account and
    currency: a `columns` row, then `(package_transaction, n, ...)`, its tier and reason as the downloads read them
    (`_downloads_view`). Written after the flat rows; its statement text reaches a file only through `_escaped_rows`."""
    package = _downloads_view(package)
    rows: list[tuple] = []
    tagged: list[bool] = []
    for transaction in package.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        rows.append(("package_transaction", len(rows) + 1, transaction.get("source_document") or "",
                     "" if transaction.get("source_account") is None else transaction["source_account"],
                     transaction.get("source_currency") or "", transaction.get("date") or "",
                     transaction.get("description") or "", num(transaction.get("amount")),
                     record.get("classification") or "", _tier_cell(record),
                     record.get("revenue_tier_reason") or "", record.get("revenue_review_status") or ""))
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # The trailing `zelle` column, only where a row carries the served Zelle tag.
    if any(tagged):
        return [("package_transaction", "columns", *_PACKAGE_TRANSACTION_COLUMNS, "zelle"),
                *((*row, "Zelle" if zelle else "") for row, zelle in zip(rows, tagged))]
    return [("package_transaction", "columns", *_PACKAGE_TRANSACTION_COLUMNS), *rows]


def _package_csv(package: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_escaped_rows(_package_rows(package) + _package_transaction_table(package)))
    return buf.getvalue()


#: Characters XML 1.0 forbids in a document (C0 controls other than tab, LF and CR; U+FFFE and U+FFFF) and lone
#: surrogates, which UTF-8 cannot encode. One of them in a cell made sheet1.xml ill-formed (the whole workbook
#: refused to open), and a lone surrogate made the download raise.
_XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


def _xml_escape(value: object) -> str:
    """Text for an XLSX inline string (its only caller is `_xlsx_cell`). Each character XML forbids becomes U+FFFD, the
    replacement character: SUBSTITUTED, never deleted, so a leading control can never let a formula lead start the
    cell after `_escape_formula` has looked at it, and the cell keeps its length in UTF-16 units. The CSV and the JSON
    downloads keep the text as read."""
    return (
        _XML_FORBIDDEN.sub("�", str(value))
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


#: The most characters a spreadsheet cell holds (Excel's limit, counted in UTF-16 units).
XLSX_CELL_LIMIT = 32767


def _xlsx_text(value: object) -> str:
    """An inline string's text: the value, or, when it holds more than XLSX_CELL_LIMIT UTF-16 units (a character
    outside the Basic Multilingual Plane counts two, as Excel counts it), a pointer naming its length. Never cut: a
    cell over the limit makes Excel refuse the file at load, and its repair truncates the cell. The CSV and the JSON
    download keep such a value whole."""
    text = str(value)
    units = len(text.encode("utf-16-le", "surrogatepass")) // 2
    if units > XLSX_CELL_LIMIT:
        return f"Not shown: {units:,} characters, over the spreadsheet cell limit; see the JSON download."
    return text


def _xlsx_cell(ref: str, value: object) -> str:
    """One cell, typed: a bool is a boolean cell (checked first: a bool is an int), a finite int or float a number, so
    SUM and a pivot add the money; anything else, NaN, inf and every numeric-looking string included (a masked account
    number, a leading-zero reference), is an inline string. An inline string is never a formula; its text keeps
    `_escape_formula`'s apostrophe, which a Save As CSV carries on, so the cell stays inert when the sheet is written
    back out as text. A text over the spreadsheet cell limit is replaced whole by a pointer (`_xlsx_text`)."""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and isfinite(value):
        return f'<c r="{ref}"><v>{value!r}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(_xlsx_text(value))}</t></is></c>'


def _xlsx_column(index: int) -> str:
    """A 1-based column number as its spreadsheet letters (1 -> A, 27 -> AA)."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _xlsx_sheet(rows: list[tuple]) -> str:
    def cell(col: int, row: int, value: object) -> str:
        return _xlsx_cell(f"{_xlsx_column(col)}{row}", value)

    sheet_rows = ['<row r="1">' + cell(1, 1, "section") + cell(2, 1, "field") + cell(3, 1, "value") + "</row>"]
    for idx, row in enumerate(rows, start=2):
        # A table block (the posted credits, the package ledger) writes one row per item, each value in its own
        # column.
        sheet_rows.append(
            f'<row r="{idx}">' + "".join(cell(col, idx, value) for col, value in enumerate(row, start=1)) + "</row>"
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
    return _rows_xlsx(_analysis_rows(analysis) + _posted_credit_table(analysis) + _posted_debit_table(analysis))


def _package_xlsx(package: dict) -> bytes:
    return _rows_xlsx(_package_rows(package) + _package_transaction_table(package))


#: The words a left-out shorter printout reads in the package downloads, as the dashboard's duplicate notice reads them
#: (app.js DUPLICATE_REASON_WORDS).
SUPERSEDED_INTERIM_WORDS = "a shorter printout of days another statement covers"
#: The words a left-out printout of more than a month reads (app.js DUPLICATE_REASON_WORDS), whose rows
#: the account's other statements print.
SUPERSEDED_LONG_PRINTOUT_WORDS = "a printout of more than a month whose every row other statements of the account print"
#: Each reason `package_superseded` leaves a statement out for, and its words.
SUPERSEDED_REASON_WORDS = {
    "superseded_interim": SUPERSEDED_INTERIM_WORDS,
    "superseded_long_printout": SUPERSEDED_LONG_PRINTOUT_WORDS,
}


def _overlap_words(pair: dict, filenames: dict[str, str], money: str) -> str:
    """A pair of overlapping statements as the package names it (app.js overlappingStatementWords reads the same
    words). A pair named although it shares no credit (a period inside the other, or more than three common days)
    reads the days the two cover."""
    count = pair.get("shared_credit_count") or 0
    names = (f"{filenames.get(pair.get('job'), pair.get('job'))} and "
             f"{filenames.get(pair.get('other'), pair.get('other'))}")
    if not count:
        return f"{names} cover {pair.get('days_shared')} of the same days of one account"
    return (f"{names} share {count} {'credit' if count == 1 else 'credits'} ({money}) in the days both cover, "
            "counted in both")


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
    processing one could only ever fail later with a worse message.

    A multipart filename carrying a raw
    CR/LF is refused HERE, first, with a class-name-only message — never the
    raw filename echoed back (unlike every other branch below, which is safe
    to echo because ordinary filenames carry no attack shape). Before this,
    such a filename reached `ocr.document.StatementMarkdown.__post_init__`
    deep inside the reading stage, which refuses it too (`ProvenanceTokenError`
    on a line-break in `source_file`) — but as an opaque per-job failure
    instead of a clean 400 at upload, and `_stage_failure` (`webapp/
    worker.py`) already withholds that message from the job record, so the
    only change here is WHERE the refusal happens, not what it reveals.

    NEW-4: the same reasoning extends to `-->`, which
    `StatementMarkdown.__post_init__` also refuses (the writer-side belt) but
    this function did not — a filename like `a-->b.pdf` reached the view (a raw
    `-->` does not corrupt multipart framing the way CR/LF does) and then died
    as the same opaque per-job failure as CR/LF. Refused here
    too, for consistency, with the identical class-name-only shape."""
    if "\r" in filename or "\n" in filename or "-->" in filename:
        return None, None, {"error": "ProvenanceTokenError"}
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


#: /upload's answer when the batch could not be stored: every job the request created is marked failed with this
#: text and none is queued. Fixed text, never an exception's.
UPLOAD_NOT_STORED = "the statements could not be stored; none was accepted. Upload them again"

#: /upload's answer (HTTP 400) to a request that still sends `force_ocr=1` (an API caller, or a page cached from before
#: the change): the product uses no model, so there is no visual OCR to force. Refused before any file is read, stored
#: or queued. The jobs table's force_ocr column and the field in /status stay, so a job stored with the flag still
#: loads; its re-analysis answers webapp/worker.py's FORCED_OCR_RETIRED.
FORCE_OCR_REMOVED = "Force visual OCR was removed: statements are read deterministically and with local OCR only."


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400
    if len(files) > MAX_UPLOAD_FILES:
        return jsonify({
            "error": f"{len(files)} files uploaded (limit {MAX_UPLOAD_FILES} per batch)",
        }), 400
    if request.form.get("force_ocr") == "1":
        return jsonify({"error": FORCE_OCR_REMOVED}), 400
    # Every job is read the same way (native PDF text, then local OCR); the field stays in the job row and the answer.
    force_ocr = False

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

    # The free-space floor: validation answers first, then nothing is written when the batch would leave the
    # data volume below MIN_FREE_BYTES.
    if _data_volume_nearly_full(sum(len(pdf_bytes) for _name, pdf_bytes, _pages, _profile in accepted)):
        return jsonify({"error": STORAGE_NEARLY_FULL}), 507

    # Store the whole batch before queueing any of it, so a storage failure on
    # file k never leaves files 1..k-1 processed under ids the dashboard never
    # received. A failure marks every job this request created failed, queues
    # none of them, and answers with fixed text, never the exception's own.
    created = []
    try:
        for filename, pdf_bytes, page_count, profile in accepted:
            # Records the document row (with content_sha256) and the job row, and
            # writes the PDF bytes to the disk store.
            job = store.create(
                filename,
                page_count=page_count,
                force_ocr=force_ocr,
                pdf_bytes=pdf_bytes,
            )
            created.append(job)
            # O-1: persist the preflight profile with the document row.
            store.storage.set_document_profile(job.id, json.dumps(profile.to_dict()))
    except Exception:
        for job in created:
            try:
                store.set_error(job.id, UPLOAD_NOT_STORED)
            except Exception:
                pass  # best effort: a job still `queued` in storage is marked interrupted at the next start
        return jsonify({"error": UPLOAD_NOT_STORED}), 503

    jobs = []
    for job, (filename, pdf_bytes, page_count, profile) in zip(created, accepted):
        _enqueue_job(job.id, pdf_bytes, filename, force_ocr)
        jobs.append({
            "id": job.id,
            "filename": job.filename,
            "page_count": job.page_count,
            "force_ocr": force_ocr,
            "parse_mode": job.parse_mode,
            "content_sha256": job.content_sha256,
            # A re-upload of identical bytes names the earliest prior job holding
            # them, read in the transaction that created the job.
            "duplicate_of": job.duplicate_of,
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
        # bytes were uploaded before, the earliest prior job holding them
        # (asked of storage at most once per job: audit BE-2).
        "content_sha256": job.content_sha256,
        "duplicate_of": store.duplicate_of(job_id) if job.content_sha256 else None,
    })


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
    return Response(job.markdown, mimetype="text/plain", headers=_REPORT_HEADERS)


#: The routes that serve statement text as it was read (/result, /markdown, the html and md downloads) carry a
#: sandboxing Content-Security-Policy (no script, form or external resource; the report needs only its inline styles
#: and data: crops) and nosniff, so markup a PDF's text layer prints never runs in the app's origin.
_REPORT_HEADERS = {"Content-Security-Policy": REPORT_CSP_HEADER, "X-Content-Type-Options": "nosniff"}


def _inert_report(html: str) -> str:
    """The html download with the report's Content-Security-Policy meta tag in its head, so the saved file is inert
    when opened from disk (a meta tag cannot carry `sandbox`; the policy still forbids every script). Reports
    rendered since EXP-1 already carry it and are served as stored; one stored earlier gets it inserted after its
    charset line (or right after <head>, or at the very start when it has no head), every other byte unchanged. Only
    the head counts: a copy of the tag printed in the statement's body does not stand in for it."""
    head_end = html.find("</head>")
    head = html[:head_end] if head_end >= 0 else ""
    if REPORT_CSP_META in head:
        return html
    charset = '<meta charset="utf-8">\n'
    at = head.find(charset)
    if at >= 0:
        cut = at + len(charset)
    else:
        start = head.find("<head>")
        cut = start + len("<head>") if start >= 0 else 0
    return html[:cut] + REPORT_CSP_META + "\n" + html[cut:]


@app.route("/analysis/<job_id>")
def analysis(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return jsonify({
        "analysis": _masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir))),
        "analysis_error": job.analysis_error,
    })


#: `analysis/revenue.py`'s declared review refusals (the pattern is `webapp/worker.py`'s
#: `_DECLARED_ANALYSIS_REFUSALS`). `webapp/static/app.js` shows the response body in a `window.alert`, and any
#: `ValueError` from deeper inside `rebuild_serialized_revenue_views` (the money grammar raises some) could carry
#: statement text. So matching is exact, the value published is the member of this tuple, never the exception's own
#: string, and anything else is reduced. `test_every_declared_review_refusal_is_actually_raised` drives each member
#: out of `analysis/revenue.py`, so the tuple cannot drift from the raises.
_DECLARED_REVIEW_REFUSALS: tuple[str, ...] = (
    "transaction source location was not found",
    "decision must be confirm, reject, or reset",
    "only automatically unverified deposits can be reviewed",
    "every posted credit must have an authoritative classification record",
    "every posted credit must have a valid revenue classification",
    "account was not found",
    "transaction source location is in more than one account; name the account",
    # True revenue spec §10.7, §12: a confirm on a rule-verified credit; a record whose state and tier disagree; a
    # payload whose posted credits carry a tier only in part.
    "a credit a rule verified can only be marked non-revenue",
    "every posted credit's revenue state must agree with its tier",
    "every posted credit carries a revenue tier, or none does",
    # Spec §10.7: a confirm on a credit that returns a confirmed funder's payment.
    "a credit that returns a confirmed funder's payment can only be marked non-revenue",
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
    # Spec §10.7: the decision is validated on the Zelle reading the reviewer sees, and the latest decision on a
    # posting sets both readings (analysis/zelle_view.py with_both_readings). The setting is read once for the
    # request.
    settings = load_settings(store.storage.data_dir)
    shown = zelle_setting(settings)
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None or job.status != "done" or job.analysis is None:
            abort(404)
        try:
            updated = zelle_view.with_both_readings(
                deepcopy(job.analysis), shown=shown, decisions=[(source_location, decision, account)],
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
            zelle_true_revenue=shown,
        )
    if stored is None:
        abort(404)
    return jsonify({"analysis": _masked(displayed(stored, settings=settings))})


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
    # Spec §10.7: validated on the Zelle reading shown, all or nothing; the other reading follows the latest decision
    # on each posting (analysis/zelle_view.py with_both_readings). The setting is read once for the request.
    settings = load_settings(store.storage.data_dir)
    shown = zelle_setting(settings)
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None or job.status != "done" or job.analysis is None:
            abort(404)
        try:
            updated = zelle_view.with_both_readings(deepcopy(job.analysis), shown=shown, decisions=parsed)
        except LookupError as exc:
            return jsonify({"error": _review_refusal(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": _review_refusal(exc)}), 400
        stored = store.apply_reviews(job_id, updated, decisions=parsed, actor=actor, zelle_true_revenue=shown)
    if stored is None:
        abort(404)
    return jsonify({"analysis": _masked(displayed(stored, settings=settings)), "applied": len(parsed)})


#: A re-analysis with no analysis to save: none was produced, or the one produced was refused. The saved analysis
#: stays; the `reason` beside this is text the worker already publishes for the same outcome (`webapp/worker.py`
#: `_stage_failure` / `_analysis_failure`, its no-usable-text NO_USABLE_TEXT, or FORCED_OCR_RETIRED for a job stored
#: with the retired Force visual OCR flag) or `webapp/reanalysis.py`'s READING_NOT_CACHED or READS_DIFFERENTLY, never
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
        # The free-space floor: a re-analysis appends the whole replaced analysis to the append-only audit log,
        # so it is refused, writing nothing, when the volume is below the floor.
        if _data_volume_nearly_full():
            return jsonify({"error": REANALYSIS_NOT_SAVED, "reason": STORAGE_NEARLY_FULL_REASON}), 507
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
        "analysis": _masked(displayed(stored, settings=load_settings(store.storage.data_dir))),
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
        # An older stored package can list one job twice.
        return _unique_ids(member_ids), None
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
    # A job listed twice (`?ids=a,a`, or a package id beside one of its own members) is one job, never two
    # members.
    return _unique_ids(ids), None


def _unique_ids(ids: list[str]) -> list[str]:
    """`ids` in order, each once (its first place kept)."""
    return list(dict.fromkeys(ids))


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
    return package_view.package_analysis(jobs, settings=load_settings(store.storage.data_dir))


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
    # Each job once, so a durable package never lists one twice.
    ids = _unique_ids([str(item) for item in ids])
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
    package = _masked(_package_for_export(package))
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
    return Response(job.html, mimetype="text/html", headers=_REPORT_HEADERS)


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
        content = json.dumps(
            _masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)), indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = _analysis_csv(
            _masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)))
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = _analysis_xlsx(
            _masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)))
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        # Raw OCR source, served verbatim: see the residual-exposure note on
        # /markdown. Masking the analyst's source view would corrupt it.
        content = job.markdown if fmt == "md" else job.html
        mimetype = "text/markdown" if fmt == "md" else "text/html"
        if fmt == "html" and isinstance(content, str):
            content = _inert_report(content)
    store.record_export(job_id=job_id, detail={"format": fmt})
    base_name = _safe_download_name(job.filename.rsplit(".", 1)[0])
    headers = {"Content-Disposition": f'attachment; filename="{base_name}.{fmt}"'}
    if fmt in ("md", "html"):
        headers.update(_REPORT_HEADERS)
    return Response(content, mimetype=mimetype, headers=headers)


#: What a read-only start-up still serves: GET routes that read the store and write nothing to the data volume.
#: Everything else is refused with 503: the POST routes, and the two downloads, which write an export audit row
#: (served without it, the audit trail would lose them). A route added later is refused until it is named here.
#: `healthz` is the hosting line's probe.
_READ_ONLY_ENDPOINTS = frozenset({
    "index", "static", "healthz", "get_settings", "status", "markdown", "analysis", "package_analysis", "page",
    "result",
})
#: What a start-up whose store cannot be read at all still serves: the page and the probe.
_UNAVAILABLE_ENDPOINTS = frozenset({"index", "static", "healthz"})


def _storage_degraded_error():
    text = STORAGE_READ_ONLY_ERROR if STORE_STATE == STORE_READ_ONLY else STORAGE_UNAVAILABLE_ERROR
    return jsonify({"error": text}), 503


# The password gate is registered before every other request hook, so an unauthenticated request is answered 401
# before any other hook (the degraded-store refusal included) can say anything about the server.
@app.before_request
def _gate_intern_auth():
    if request_is_authorized():
        return None
    return unauthorized()


@app.before_request
def _refuse_what_a_degraded_store_cannot_do():
    """A degraded start-up (`_open_store`) answers what it can and refuses the rest with fixed text; a normal one is
    untouched. On the hosting line the password gate must stay ahead of this hook."""
    if STORE_STATE is None:
        return None
    allowed = _READ_ONLY_ENDPOINTS if STORE_STATE == STORE_READ_ONLY else _UNAVAILABLE_ENDPOINTS
    if request.method in ("GET", "HEAD") and request.endpoint in allowed:
        return None
    return _storage_degraded_error()


if STORE_STATE is not None:
    # A read the read-only store cannot serve after all (its connection needs the volume too) answers with the same
    # fixed text instead of a 500 page. Registered only on a degraded start-up, so a normal one is unchanged.
    app.register_error_handler(sqlite3.Error, lambda _exc: _storage_degraded_error())


def _server_config() -> tuple[str, int]:
    """Loopback by default. Exposing beyond this machine is a deliberate act
    (WEBAPP_HOST) and, off-loopback, requires WEBAPP_AUTH_PASSWORD — a D-2b
    intern-testing slice, not the full production auth trio."""
    host = os.environ.get("WEBAPP_HOST", "").strip() or "127.0.0.1"
    port = os.environ.get("WEBAPP_PORT", "").strip() or "5000"
    return host, int(port)


@app.route("/healthz")
def healthz():
    """Load-balancer / Docker probe. No job, document, or store data."""
    return jsonify({"ok": True})


def main() -> None:
    """Serve through waitress. The Werkzeug development server is never used:
    its interactive debugger is arbitrary code execution for anyone who can
    reach the port."""
    from waitress import serve

    host, port = _server_config()
    refuse_unauthenticated_bind(host)
    serve(app, host=host, port=port, threads=SERVER_THREADS)


if __name__ == "__main__":
    main()
