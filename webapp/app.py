from __future__ import annotations
import io
import csv
import json
import os
import re
import threading
import zipfile
from collections import Counter, deque
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
    revenue_review_gate,
)
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.cadence import describe_cadence
from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from analysis.revenue_view import apply_revenue_view
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
    analysis: object, *, carry_over: bool | None = None, settings: dict | None = None, export: bool = False
) -> object:
    """A stored analysis as the dashboard presents it: the owner's Settings applied to a COPY.

    Two settings apply. The NSF basis (analysis/nsf_days.py): printed days by default, or every calendar day with
    the balance carried over inactive days when Settings turns carry-over on. And the flag groups
    (analysis/flagged_view.py): an unticked group is hidden from the summaries and its rows lose their flag.
    Every surface that shows or exports an analysis goes through here, so the dashboard, the downloads and the
    package agree; the stored record is never rewritten, and a change of setting applies to every job at once.

    `settings` is a snapshot of every setting, read here once when it is not passed; `carry_over`, when given,
    still decides the NSF basis. `export` leaves out what only the dashboard reads (the NSF days its NSFs chip
    lists, `metrics.nsf_days`), so a download carries what it carried before the chip."""
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    if carry_over is None:
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over, list_days=not export)
    # 5.6 (true revenue spec §10.4, §12): each account's revenue flags, and an older payload's True revenue nulled.
    served = apply_revenue_view(apply_flagged_groups_to_payload(rebased, enabled=settings))
    # Audit B11 (I51): a download never prints a figure the dashboard reads as N/A.
    return _export_revenue_view(served) if export else served


#: Audit B11 (I51, §10.4 for the exports): the figures a download leaves empty when an account's revenue is not
#: established (its captured credits are not the money its Total counts, or it was analysed before 5.6): True,
#: Counted, Held and every name that carries them or a part of them. The dashboard already reads them as N/A; a
#: download printed them as numbers beside `revenue_established = False`. Non-revenue stays: its rows are known
#: non-revenue, captured rows only.
_UNESTABLISHED_REVENUE_KEYS = (
    "true_revenue", "true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
    "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
    "excluded_pending_review_by_reason", "revenue_review_items", "unverified_deposit_total",
    "potential_revenue_total", "maximum_revenue",
)
#: ... and when its Verified figure is not established: Verified and its aliases (T9).
_UNESTABLISHED_VERIFIED_KEYS = ("verified_revenue_total", "confirmed_true_revenue", "confirmed_true_revenue_total")


def _export_account_revenue(account: object) -> object:
    """One account's served copy as a download prints it (audit B11, I51): the figures its revenue flags do not
    establish are None, written as empty cells. A copy; the served payload is untouched."""
    if not isinstance(account, dict) or not isinstance(account.get("metrics"), dict):
        return account
    metrics = account["metrics"]
    nulled = {}
    if metrics.get("revenue_established") is not True:
        nulled.update({key: None for key in _UNESTABLISHED_REVENUE_KEYS if key in metrics})
    if metrics.get("verified_revenue_established") is not True:
        nulled.update({key: None for key in _UNESTABLISHED_VERIFIED_KEYS if key in metrics})
    return {**account, "metrics": {**metrics, **nulled}} if nulled else account


def _export_revenue_view(payload: object) -> object:
    """A served payload as the statement downloads print it, either shape (`_export_account_revenue`)."""
    if isinstance(payload, dict) and is_document_payload(payload):
        return {**payload, "accounts": [_export_account_revenue(account) for account in payload["accounts"]]}
    return _export_account_revenue(payload)


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
    # Audit B11 (I51): the package's counted-plus-held figures, and the held count, are partial when a member's
    # revenue is not established (its True, Counted and Held totals are already None, §10.4), so a download leaves
    # them empty too.
    totals = package.get("totals")
    if isinstance(totals, dict) and totals.get("revenue_unestablished_documents"):
        exported["totals"] = {
            **totals, **{key: None for key in _PACKAGE_PARTIAL_REVENUE_KEYS if key in totals},
        }
    return exported


#: Audit B11 (I51): the package totals built from every member's counted and held credits, and the held count.
_PACKAGE_PARTIAL_REVENUE_KEYS = ("maximum_revenue", "potential_revenue_total", "unverified_deposit_total",
                                 "revenue_review_items")


def _export_document_revenue(row: dict) -> dict:
    """A member's row as the package downloads print it (audit B11, I51): its Verified figure (and the alias of it)
    empty unless established, and its counted-plus-held figures empty unless its revenue is. A left-out repeat's row
    carries no figure and is unchanged."""
    if row.get("is_duplicate") is True:
        return row
    nulled = {}
    if row.get("verified_revenue_established") is False:
        nulled.update({key: None for key in ("verified_revenue_total", "confirmed_true_revenue_total") if key in row})
    if row.get("revenue_established") is False:
        nulled.update({key: None for key in ("unverified_deposit_total", "potential_revenue_total", "maximum_revenue")
                       if key in row})
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
                if section == "metrics" and key in ("adb", *_TIER_REASON_KEYS):
                    continue  # emitted as their own sections below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
                rows.append((section, key, "" if item is None else item))
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
        rows.extend(_tier_reason_rows(metrics))
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


#: 5.6 (true revenue spec §10.8): the by-reason figures of the counted and held tiers, exported as readable rows.
_TIER_REASON_KEYS = ("counted_flagged_by_reason", "excluded_pending_review_by_reason")


def _tier_reason_rows(figures: dict, section: str = "revenue_tier") -> list[tuple[str, str, object]]:
    """One row per tier, reason and figure: `(revenue_tier, <tier>.<reason>.count | .total, value)`. A reason code
    is a constant of analysis/revenue.py; the rows still reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for key in _TIER_REASON_KEYS:
        reasons = figures.get(key)
        tier = key[: -len("_by_reason")]
        for reason, slot in (reasons.items() if isinstance(reasons, dict) else ()):
            for field in ("count", "total"):
                value = slot.get(field) if isinstance(slot, dict) else None
                rows.append((section, f"{tier}.{reason}.{field}", "" if value is None else value))
    return rows


def _flagged_position_rows(positions: object) -> list[tuple[str, str, object]]:
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited, the credits it paid in and their
    total (plan contract C5: a factor's payouts, owner ruling 2026-09-26), the cadence, and (5.3) whether the
    payee is unconfirmed (`review_required`).

    Served payloads hold only the ticked groups (analysis/flagged_view.py via `_displayed`), so the sheet follows
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


#: Audit B11 (I32): the columns of the statement downloads' posted-credit table.
_POSTED_CREDIT_COLUMNS = ("date", "description", "amount", "currency", "tier", "reason", "state", "review_status")


def _posted_credit_table(analysis: dict) -> list[tuple]:
    """Audit B11 (I32): one row per posted credit, so an underwriter can check, deposit by deposit, which credits make
    up True (the ledger otherwise sits in one JSON cell, over a spreadsheet's cell limit on most statements): a
    `columns` row, then `(section, n, date, description, amount, currency, tier, reason, state, review status)`.
    The tier and reason are the payload's codes (analysis/revenue.py). Every account of a document payload has its
    own block, under its section prefix. A block written after the flat rows (`_analysis_rows` stays three columns
    for its readers); its statement text reaches a file only through `_escaped_rows`."""
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
    currency = _statement_currency(analysis) or ""
    rows: list[tuple] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = _num(transaction.get("amount"))
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        if amount <= 0 or record.get("is_posted") is False:
            continue
        rows.append(("posted_credit", len(rows) + 1, transaction.get("date") or "",
                     transaction.get("description") or "", amount, currency, record.get("revenue_tier") or "",
                     record.get("revenue_tier_reason") or "", record.get("revenue_classification") or "",
                     record.get("revenue_review_status") or ""))
    return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS), *rows] if rows else []


def _analysis_csv(analysis: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_escaped_rows(_analysis_rows(analysis) + _posted_credit_table(analysis)))
    return buf.getvalue()


#: A package member's id: a job's id, or `<job id>#account_<n>` for an account of a document (app.js packageMember).
_PACKAGE_MEMBER_ID = re.compile(r"(.*)#account_\d+")


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        if key in _TIER_REASON_KEYS:
            continue  # emitted as readable rows below
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("totals", key, "" if value is None else value))
    rows.extend(_tier_reason_rows(totals))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
    # money cells and read them as missing data rather than as refused units.
    for key, value in (package.get("currency") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("currency", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            if key in _TIER_REASON_KEYS:
                continue  # emitted as readable rows below
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"document_{idx}", key, "" if value is None else value))
        if document.get("duplicate_reason") == "superseded_interim":
            # Audit round 2, R2-B14 (R14): the words the dashboard's notice gives a left-out shorter printout.
            rows.append((f"document_{idx}", "duplicate_reason_words", SUPERSEDED_INTERIM_WORDS))
        rows.extend(_tier_reason_rows(document, f"document_{idx}.revenue_tier"))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
    for idx, duplicate in enumerate(package.get("duplicates") or [], start=1):
        for key, value in duplicate.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"duplicate_{idx}", key, "" if value is None else value))
    # Audit round 2, R2-B14 (R14): each pair of overlapping statements that share credits, and the notice's words for it.
    filenames: dict[str, str] = {}
    for document in package.get("documents") or []:
        member = _PACKAGE_MEMBER_ID.fullmatch(str(document.get("id") or ""))
        filenames.setdefault(member[1] if member else str(document.get("id") or ""), document.get("filename"))
    for idx, pair in enumerate(totals.get("overlapping_statements") or [], start=1):
        for key, value in pair.items():
            rows.append((f"overlapping_statement_{idx}", key, "" if value is None else value))
        total = pair.get("shared_credit_total")
        money = f"{float(total):,.2f}" if _is_money_value(total) else "N/A"
        rows.append((f"overlapping_statement_{idx}", "words", _overlap_words(pair, filenames, money)))
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
    # Audit B11 (I32): one evidence section per tier, so counted credits (in True) and held ones (out of it) no longer
    # share `unverified_deposit_evidence_N`. A credit of a member analysed before 5.6 carries no tier and stays there.
    unverified = package.get("unverified_deposit_evidence") or []
    for section, records in (
        ("verified_revenue_evidence", package.get("verified_revenue_evidence") or []),
        ("counted_flagged_evidence",
         [record for record in unverified if record.get("revenue_tier") == "counted_flagged"]),
        ("excluded_pending_review_evidence",
         [record for record in unverified if record.get("revenue_tier") == "excluded_pending_review"]),
        ("unverified_deposit_evidence",
         [record for record in unverified
          if record.get("revenue_tier") not in ("counted_flagged", "excluded_pending_review")]),
        ("non_revenue_evidence", package.get("non_revenue_evidence") or []),
    ):
        for idx, evidence in enumerate(records, start=1):
            for key, value in evidence.items():
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    return rows


#: Audit B11 (I32): the columns of the package downloads' ledger table.
_PACKAGE_TRANSACTION_COLUMNS = ("source_document", "source_account", "source_currency", "date", "description",
                                "amount", "classification", "tier", "reason", "state", "review_status")


def _package_transaction_table(package: dict) -> list[tuple]:
    """Audit B11 (I32): the package's combined ledger (`transactions`), one row per posting, each naming its statement,
    account and currency: a `columns` row, then `(package_transaction, n, ...)`. Written after the flat rows; its
    statement text reaches a file only through `_escaped_rows`."""
    rows: list[tuple] = []
    for transaction in package.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        rows.append(("package_transaction", len(rows) + 1, transaction.get("source_document") or "",
                     "" if transaction.get("source_account") is None else transaction["source_account"],
                     transaction.get("source_currency") or "", transaction.get("date") or "",
                     transaction.get("description") or "", _num(transaction.get("amount")),
                     record.get("classification") or "", record.get("revenue_tier") or "",
                     record.get("revenue_tier_reason") or "", record.get("revenue_classification") or "",
                     record.get("revenue_review_status") or ""))
    return [("package_transaction", "columns", *_PACKAGE_TRANSACTION_COLUMNS), *rows] if rows else []


def _package_csv(package: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(_escaped_rows(_package_rows(package) + _package_transaction_table(package)))
    return buf.getvalue()


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _xlsx_cell(ref: str, value: object) -> str:
    """One cell, typed (audit B11, I52): a bool is a boolean cell (checked first: a bool is an int), a finite int or
    float a number, so SUM and a pivot add the money; anything else, NaN, inf and every numeric-looking string
    included (a masked account number, a leading-zero reference), is an inline string. An inline string is never a
    formula; its text keeps `_escape_formula`'s apostrophe, which a Save As CSV carries on, so the cell stays inert
    when the sheet is written back out as text."""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and isfinite(value):
        return f'<c r="{ref}"><v>{value!r}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(value)}</t></is></c>'


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
        # Audit B11 (I32): a table block (the posted credits, the package ledger) writes one row per item, each value
        # in its own column.
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
    return _rows_xlsx(_analysis_rows(analysis) + _posted_credit_table(analysis))


def _package_xlsx(package: dict) -> bytes:
    return _rows_xlsx(_package_rows(package) + _package_transaction_table(package))


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
             "total_credited": 0.0, "dates": [], "review_required": False},
        )
        item["review_required"] = item["review_required"] or classification.get("review_required") is True
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
    first_date, last_date, review_required}`. The cadence is read over the payee's dates in every member together
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
                "review_required": item["review_required"],
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
    # Audit B11 (I07): the per-month True, Verified and Non-revenue.
    "avg_monthly_true_revenue",
    "avg_monthly_verified_revenue",
    "avg_monthly_non_revenue",
})

_CROSS_CURRENCY_TOTAL_KEYS = frozenset({
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    # Audit B11 (I07): the per-month True, Verified and Non-revenue.
    "avg_monthly_true_revenue",
    "avg_monthly_verified_revenue",
    "avg_monthly_non_revenue",
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
    # 5.6 (§9.2): True revenue and its counted and held parts.
    "true_revenue_total",
    "counted_flagged_total",
    "excluded_pending_review_total",
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


def _is_money_value(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _stored_accounts(analysis: object) -> list[dict]:
    """The account payloads a stored analysis publishes, in printed order: one for today's payload, each account of a
    document payload, none for a job with no analysis."""
    if not isinstance(analysis, dict) or not analysis:
        return []
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_stored_accounts")
        return [account for account in accounts if isinstance(account, dict)]
    return [analysis] if isinstance(analysis.get("statement"), dict) else []


def _account_identities(account: object) -> frozenset[str]:
    """Audit B11 (I06, MCA standard §4.6(3)): what makes two accounts of two jobs ONE statement.

    * its published content (`account_content_digest`), when its ledger prints at least one transaction: a payload
      with no ledger publishes too little to tell two statements apart, and is never matched on it;
    * its statement key, when every part of it is printed: the bank, the account number's last four digits, the
      period's first and last day, and the opening and closing balance. A re-download of the same statement (other
      bytes, so another content hash) prints the same key.

    An empty set when neither is established: such an account is never taken for a copy of another."""
    if not isinstance(account, dict) or not isinstance(account.get("statement"), dict):
        return frozenset()
    statement = account["statement"]
    identities: set[str] = set()
    if any(isinstance(row, dict) for row in statement.get("transactions") or []):
        identities.add("digest:" + account_content_digest(account))
    bank = " ".join(str(statement.get("bank") or "").split()).casefold()
    digits = "".join(character for character in str(statement.get("account_number") or "") if character.isdigit())
    start, end = statement.get("period_start"), statement.get("period_end")
    opening, closing = statement.get("beginning_balance"), statement.get("ending_balance")
    if (bank and len(digits) >= 4 and isinstance(start, str) and start and isinstance(end, str) and end
            and _is_money_value(opening) and _is_money_value(closing)):
        identities.add(f"statement:{bank}|{digits[-4:]}|{start}|{end}|{float(opening):.2f}|{float(closing):.2f}")
    return frozenset(identities)


#: Audit round 2, R2-B14 (R46): what `_printed_account_digits` removes from a printed account number before it reads
#: the digits at its end: blanks and the separators banks print inside a number.
_ACCOUNT_NUMBER_SEPARATORS = re.compile(r"[\s\-./]")
_TRAILING_DIGITS = re.compile(r"[0-9]+$")


def _printed_account_digits(account: object) -> str:
    """Audit round 2, R2-B14 (R46): the digits an account's statement prints at the END of its account number, its
    blanks, '-', '.' and '/' removed ('XXXX-1010' gives '1010', '12XXXX3456' '3456', '100000001010' all twelve); ''
    when the number ends in no digit or is not printed."""
    statement = account.get("statement") if isinstance(account, dict) else None
    if not isinstance(statement, dict):
        return ""
    match = _TRAILING_DIGITS.search(_ACCOUNT_NUMBER_SEPARATORS.sub("", str(statement.get("account_number") or "")))
    return match.group(0) if match else ""


def _numbers_conflict(digits: str, other: str) -> bool:
    """Audit round 2, R2-B14 (R46): two printed account numbers are two accounts when both print more than four
    digits and the shorter's digits are not the end of the longer's. A masked or four-digit print never conflicts."""
    if len(digits) <= 4 or len(other) <= 4:
        return False
    common = min(len(digits), len(other))
    return digits[-common:] != other[-common:]


#: Audit round 2, R2-B14 (R16): a copy's rank keys, in order, by the name a left-out copy's row gives for the kept one
#: winning on it (`duplicate_kept_because`); copies alike on all three keep the one listed first (`listed_first`).
_KEPT_BECAUSE = ("has_analysis", "current_rules", "has_review_decisions")
_REVIEW_DECISIONS = frozenset({"confirmed", "rejected"})


def _copy_rank(job) -> tuple[int, int, int]:
    """Audit round 2, R2-B14 (R16): how good a copy of a repeated statement is, lower first: 0 when the job is done
    and publishes an account (else 1); 0 when its analysis is current, 1 when an account of its served copy
    (`apply_revenue_view`) has `revenue_established` False or a record lacks or predates `CLASSIFICATION_VERSION`
    (the `analysis_rules_outdated` rule of analysis/flagged_view.py; a job with no account is never current); 0 when a
    posted credit of it carries the analyst's decision (`revenue_review_status` confirmed or rejected)."""
    analysis = getattr(job, "analysis", None)
    accounts = _stored_accounts(analysis)
    has_analysis = getattr(job, "status", None) == "done" and bool(accounts)
    current = False
    if accounts:
        served = apply_revenue_view(apply_flagged_groups_to_payload(analysis, enabled={}))
        current = (
            isinstance(served, dict) and served.get("analysis_rules_outdated") is not True
            and all((account.get("metrics") or {}).get("revenue_established") is not False
                    for account in _stored_accounts(served))
        )
    decided = any(
        isinstance(row, dict) and _num(row.get("amount")) > 0 and isinstance(row.get("classification"), dict)
        and row["classification"].get("is_posted") is not False
        and row["classification"].get("revenue_review_status") in _REVIEW_DECISIONS
        for account in accounts
        for row in (account.get("statement") or {}).get("transactions") or []
    )
    return (0 if has_analysis else 1, 0 if current else 1, 0 if decided else 1)


def _kept_because(kept_rank: tuple, dropped_rank: tuple) -> str:
    """Audit round 2, R2-B14 (R16): the first rank key on which the kept copy beats the left-out one, else
    `listed_first`."""
    return next((name for name, kept, dropped in zip(_KEPT_BECAUSE, kept_rank, dropped_rank) if kept < dropped),
                "listed_first")


def _package_duplicates(jobs) -> tuple[list, list[dict], dict[str, dict[int, str]], list[dict]]:
    """Audit B11 (I06): the package's jobs with every repeated statement left out, before any member is expanded.

    D-3 surfaced a repeated content hash and nothing acted on it, so one statement listed twice doubled True,
    Verified, Counted, Held, Non-revenue and the month count, and the package stayed Approved. MCA practice removes a
    duplicate statement (standard §4.6(3)). A job is left out when it repeats a kept job's id (`same_job`: the same
    job listed twice; it adds nothing and is listed once), its content hash (`same_content`: the same PDF uploaded
    twice), or, account by account, every account's statement identity (`same_statement`: a re-download whose bytes
    differ; `_account_identities`). A job some of whose accounts repeat a kept job's keeps its other accounts; the
    repeated ones are named in `repeated_accounts` (job id -> {account index: the kept job's id}) for
    `_package_members` to leave out. The accounts of ONE document are never compared with each other here: each
    carries the job's hash, and two of them publishing one content is the publisher's refusal
    (`document_publishes_duplicate_account`).

    Audit round 2, R2-B14 (R16): which copy is kept. The jobs claim their ids, hashes and identities in the order of
    their rank (`_copy_rank`: a completed analysis, then the current rules, then the analyst's review decisions, then
    the listed place), so a failed, queued, processing or interrupted copy, a copy analysed under older rules or a
    copy without the decisions recorded on another never takes a better copy's place; copies alike keep the one
    listed first. Each left-out entry says why its kept copy was kept (`kept_because`).

    Audit round 2, R2-B14 (R46): a statement key (`statement:`, which reads only the account number's last four
    digits) never joins two accounts whose printed full numbers conflict (`_printed_account_digits`,
    `_numbers_conflict`): each key holds every kept job that claimed it, in claim order, and an account matches the
    first of them whose number does not conflict with its own, in the same-statement test, in the choice of the job
    it repeats and in `repeated_accounts` alike. A content digest (`digest:`, which covers the whole payload, the
    number included) matches as before, and so does a masked or a four-digit print.

    Returns ``(kept jobs, dropped, repeated_accounts, groups)`` in LISTED order: `dropped` lists ``{"job",
    "duplicate_of", "reason", "kept_because", "position"}`` (`position`: the job's place in the list); each group lists
    the kept job and then every job that repeats it (D-3's shape: `content_sha256` is the kept job's hash)."""
    listed = list(jobs)
    #: Each listed job's accounts' identities and printed digits, read once (a content digest hashes a whole payload).
    identities_of: list[list[frozenset[str]]] = []
    digits_of: list[list[str]] = []
    claims: list[set[tuple[str, str]]] = []
    for job in listed:
        accounts = _stored_accounts(getattr(job, "analysis", None))
        identities_of.append([_account_identities(account) for account in accounts])
        digits_of.append([_printed_account_digits(account) for account in accounts])
        keys = {("id", str(job.id))}
        if getattr(job, "content_sha256", None):
            keys.add(("hash", str(job.content_sha256)))
        keys.update(("identity", key) for identities in identities_of[-1] for key in identities)
        claims.append(keys)
    shared = Counter(key for keys in claims for key in keys)
    # Only a job that shares an id, a hash or an identity with another listed job can meet a copy of itself, so only
    # such a job is ranked (the rank reads a served copy of the analysis); the others claim what no other job claims.
    ranks = [_copy_rank(job) if any(shared[key] > 1 for key in keys) else (0, 0, 0)
             for job, keys in zip(listed, claims)]
    kept_positions: list[int] = []
    dropped: list[dict] = []
    repeated_accounts: dict[str, dict[int, str]] = {}
    first_by_id: dict[str, int] = {}
    first_by_hash: dict[str, int] = {}
    #: identity key -> [(the kept job's position, its account's printed digits)], in claim order.
    first_by_identity: dict[str, list[tuple[int, str]]] = {}

    def claimed(key: str, digits: str) -> int | None:
        """The position of the kept job an account with this identity key and these printed digits repeats."""
        entries = first_by_identity.get(key)
        if not entries:
            return None
        if key.startswith("digest:"):
            return entries[0][0]
        return next((position for position, other in entries if not _numbers_conflict(digits, other)), None)

    for position in sorted(range(len(listed)), key=lambda place: (ranks[place], place)):
        job = listed[position]
        content_hash = getattr(job, "content_sha256", None)
        identities, digits = identities_of[position], digits_of[position]
        first, reason = None, None
        if job.id in first_by_id:
            first, reason = first_by_id[job.id], "same_job"
        elif content_hash and content_hash in first_by_hash:
            first, reason = first_by_hash[content_hash], "same_content"
        elif identities and all(any(claimed(key, own) is not None for key in account)
                                for account, own in zip(identities, digits)):
            first = next(earlier for key in sorted(identities[0])
                         if (earlier := claimed(key, digits[0])) is not None)
            reason = "same_statement"
        if first is not None:
            dropped.append({"job": job, "duplicate_of": listed[first].id, "reason": reason,
                            "kept_because": _kept_because(ranks[first], ranks[position]), "position": position,
                            "kept_position": first})
            continue
        if is_document_payload(getattr(job, "analysis", None)):
            for index, (account, own) in enumerate(zip(identities, digits), start=1):
                earlier = next((place for key in sorted(account) if (place := claimed(key, own)) is not None), None)
                if earlier is not None:
                    repeated_accounts.setdefault(job.id, {})[index] = listed[earlier].id
        kept_positions.append(position)
        first_by_id[job.id] = position
        if content_hash:
            first_by_hash.setdefault(content_hash, position)
        for account, own in zip(identities, digits):
            for key in account:
                first_by_identity.setdefault(key, []).append((position, own))
    dropped.sort(key=lambda entry: entry["position"])
    groups: dict[int, dict] = {}
    for entry in dropped:
        first = listed[entry["kept_position"]]
        group = groups.setdefault(entry.pop("kept_position"), {
            "content_sha256": getattr(first, "content_sha256", None),
            "job_ids": [first.id],
            "filenames": [first.filename],
            "count": 1,
        })
        group["job_ids"].append(entry["job"].id)
        group["filenames"].append(entry["job"].filename)
        group["count"] += 1
    kept = [listed[position] for position in sorted(kept_positions)]
    return kept, dropped, repeated_accounts, [groups[position] for position in sorted(groups)]


def _duplicate_row(entry: dict) -> dict:
    """A left-out job's row in `documents` (audit B11, I06): what identifies it and the job it repeats, and no figure,
    because none of its money enters the package. Audit round 2, R2-B14: why the job kept in its place was kept
    (`duplicate_kept_because`, R16; None for a shorter printout another statement covers, R14)."""
    job = entry["job"]
    accounts = _stored_accounts(job.analysis)
    statement = (accounts[0].get("statement") or {}) if accounts else {}
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "content_sha256": getattr(job, "content_sha256", None),
        "is_duplicate": True,
        "duplicate_of": entry["duplicate_of"],
        "duplicate_reason": entry["reason"],
        "duplicate_kept_because": entry.get("kept_because"),
        "bank": statement.get("bank"),
        "account": statement.get("account_number"),
        "currency": _statement_currency(accounts[0]) if accounts else None,
        "period_start": statement.get("period_start"),
        "period_end": statement.get("period_end"),
    }


_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _iso_day(value: object):
    """A `YYYY-MM-DD` day, or None for anything else (an impossible date included), as app.js isoDay reads it."""
    from datetime import date

    match = _ISO_DAY.fullmatch(str(value or ""))
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _statement_month(period_start: object, period_end: object) -> int | None:
    """The calendar month a statement stands for, as `year * 12 + month - 1`: the month holding most of its period's
    days, the earlier on a tie (app.js statementMonth, the Monthly Statements table's rule). A statement running
    2031-03-02 to 2031-04-01 is March 2031. None when neither day reads."""
    from datetime import timedelta

    start, end = _iso_day(period_start), _iso_day(period_end)
    if start is None and end is None:
        return None
    if start is None or end is None or end < start:
        day = start or end
        return day.year * 12 + day.month - 1
    days: dict[int, int] = {}
    day, counted = start, 0
    while day <= end and counted < 400:
        key = day.year * 12 + day.month - 1
        days[key] = days.get(key, 0) + 1
        day += timedelta(days=1)
        counted += 1
    return max(days.items(), key=lambda item: (item[1], -item[0]))[0]


#: Audit round 2, R2-B14 (R14): the words a left-out shorter printout reads in the package downloads, as the dashboard's
#: duplicate notice reads them (app.js DUPLICATE_REASON_WORDS).
SUPERSEDED_INTERIM_WORDS = "a shorter printout of days another statement covers"


def _posted_rows(account: dict) -> list[dict]:
    """An account's posted rows, credits and debits (a row whose record says `is_posted` False is not)."""
    return [
        row for row in (account.get("statement") or {}).get("transactions") or []
        if isinstance(row, dict)
        and not (isinstance(row.get("classification"), dict) and row["classification"].get("is_posted") is False)
    ]


def _row_day(row: dict) -> str:
    """A row's date as one text: its ISO day, or the printed text when it is no ISO day."""
    day = _iso_day(row.get("date"))
    return day.isoformat() if day is not None else str(row.get("date") or "").strip()


def _row_cents(row: dict) -> int:
    return int(round(_num(row.get("amount")) * 100))


def _statement_span(account: dict, rows: list[dict]):
    """A statement's period: its printed first and last day, or else its first and last posted row's day. None when
    neither reads."""
    statement = account.get("statement") or {}
    start, end = _iso_day(statement.get("period_start")), _iso_day(statement.get("period_end"))
    if start is not None and end is not None and start <= end:
        return start, end
    days = sorted(day for row in rows if (day := _iso_day(row.get("date"))) is not None)
    return (days[0], days[-1]) if days else None


def _days_shared(span, other) -> int:
    first, last = max(span[0], other[0]), min(span[1], other[1])
    return (last - first).days + 1 if first <= last else 0


def _span_covered(span, others) -> bool:
    """Whether every day of `span` lies inside the union of the `others` periods."""
    from datetime import timedelta

    cursor = span[0]
    for start, end in sorted(others):
        if start > cursor:
            break
        if end >= cursor:
            cursor = end + timedelta(days=1)
        if cursor > span[1]:
            return True
    return cursor > span[1]


def _package_superseded(kept, repeated_accounts: dict[str, dict[int, str]] | None = None,
                        members: set[tuple[str, int | None]] | None = None):
    """Audit round 2, R2-B14 (R14, MCA standard §4.6(3): overlapping interim statements of one account are removed):
    the statements of one account that a shorter printout repeats, after the exact repeats are left out
    (`_package_duplicates`).

    The kept jobs' accounts (a done job's, never one `repeated_accounts` already leaves out and, when `members` is
    given, only the ``(job id, account index or None)`` members `_package_members` admits, so a statement whose money
    the package does not count never covers another or is covered) are grouped by their bank, casefolded, and the
    last four digits of their printed number (`_printed_account_digits`); a statement's period is its printed one, or
    else its first and last posted row's day. Two accounts of one document are never compared, and two statements
    whose printed full numbers conflict (`_numbers_conflict`) are never one account's. Taking the shortest period
    first (of two alike, the one listed later first), a statement is left out (`superseded_interim`) when its period
    lies inside the union of the other kept statements' periods of its account, it prints a posted row, and every
    posted row of it, credit or debit, is a posted row of those statements, as a multiset on the day and the signed
    cents: an interim or month-to-date printout beside the full statement, a second month-to-date printout of one open
    month, or a custom range of days the full statements print. It repeats the statement left in the package that
    shares the most of its days (of two alike, the one listed first).

    Any other overlap of two statements of one account is never netted: the credits the two share in the days both
    cover (a multiset on the day, the cents and the description, casefolded, its blanks collapsed) are counted, and a
    pair sharing one or more is named in `overlapping`, ``{"job", "other", "shared_credit_count",
    "shared_credit_total"}`` (`job` the statement listed later, with `account` and `other_account` for an account of a
    document), which sends the package to review.

    Returns ``(kept jobs, dropped, superseded_accounts, overlapping)``: a job whose every account is left out is
    dropped as a duplicate is (``{"job", "duplicate_of", "reason": "superseded_interim"}``, in listed order); an
    account of a document whose other accounts stay is named in `superseded_accounts` (job id -> {account index: the
    covering job's id}) for `_package_members` to leave out with `repeated_accounts`."""
    repeated_accounts = repeated_accounts or {}
    statements: list[dict] = []
    for order, job in enumerate(kept):
        if getattr(job, "status", None) != "done":
            continue
        analysis = getattr(job, "analysis", None)
        document = is_document_payload(analysis)
        accounts = _stored_accounts(analysis)
        for index, account in enumerate(accounts, start=1):
            if document and index in repeated_accounts.get(job.id, {}):
                continue
            if members is not None and (job.id, index if document else None) not in members:
                continue
            digits = _printed_account_digits(account)
            bank = " ".join(str((account.get("statement") or {}).get("bank") or "").split()).casefold()
            rows = _posted_rows(account)
            span = _statement_span(account, rows)
            if not bank or len(digits) < 4 or span is None:
                continue
            statements.append({
                "job": job, "order": order, "index": index if document else None, "accounts": len(accounts),
                "group": (bank, digits[-4:]), "digits": digits, "span": span,
                "rows": Counter((_row_day(row), _row_cents(row)) for row in rows),
                "credits": [row for row in rows if _num(row.get("amount")) > 0],
            })
    groups: dict[tuple, list[dict]] = {}
    for statement in statements:
        groups.setdefault(statement["group"], []).append(statement)

    def peers(statement: dict, alive: list[dict]) -> list[dict]:
        return [other for other in alive if other["job"] is not statement["job"]
                and not _numbers_conflict(statement["digits"], other["digits"])]

    def most_days(statement: dict, others: list[dict]) -> dict:
        return max(others, key=lambda other: (_days_shared(statement["span"], other["span"]), -other["order"]))

    superseded: list[tuple[dict, dict]] = []
    overlapping: list[dict] = []
    for group in groups.values():
        alive = list(group)
        left_out: list[tuple[dict, dict]] = []
        for statement in sorted(group, key=lambda item: ((item["span"][1] - item["span"][0]).days, -item["order"])):
            others = peers(statement, alive)
            if not others or not statement["rows"] or not _span_covered(statement["span"],
                                                                        [other["span"] for other in others]):
                continue
            pool: Counter = Counter()
            for other in others:
                pool.update(other["rows"])
            if statement["rows"] - pool:
                continue
            left_out.append((statement, most_days(statement, others)))
            alive.remove(statement)
        for statement, covering in left_out:
            # The statement it repeats is one the package keeps: a covering statement left out after it hands it on.
            remaining = [other for other in peers(statement, alive)
                         if _days_shared(statement["span"], other["span"]) > 0]
            superseded.append((statement, most_days(statement, remaining) if remaining else covering))
        alive.sort(key=lambda item: (item["order"], item["index"] or 0))
        for position, earlier in enumerate(alive):
            for later in alive[position + 1:]:
                if later["job"] is earlier["job"] or _numbers_conflict(later["digits"], earlier["digits"]):
                    continue
                first, last = max(earlier["span"][0], later["span"][0]), min(earlier["span"][1], later["span"][1])
                if first > last:
                    continue
                shared = _credits_between(earlier, first, last) & _credits_between(later, first, last)
                if not shared:
                    continue
                pair = {
                    "job": later["job"].id,
                    "other": earlier["job"].id,
                    "shared_credit_count": sum(shared.values()),
                    "shared_credit_total": round(sum(cents * count for (_day, cents, _text), count in shared.items())
                                                 / 100, 2),
                }
                if later["index"] is not None:
                    pair["account"] = later["index"]
                if earlier["index"] is not None:
                    pair["other_account"] = earlier["index"]
                overlapping.append(pair)

    by_job: dict[str, list[tuple[dict, dict]]] = {}
    for statement, covering in superseded:
        by_job.setdefault(statement["job"].id, []).append((statement, covering))
    dropped: list[dict] = []
    superseded_accounts: dict[str, dict[int, str]] = {}
    for job in kept:
        entries = by_job.get(job.id)
        if not entries:
            continue
        if len(entries) == entries[0][0]["accounts"]:
            # Every account the job publishes is a shorter printout: the job is left out as a repeat is.
            first = min(entries, key=lambda entry: entry[0]["index"] or 0)
            dropped.append({"job": job, "duplicate_of": first[1]["job"].id, "reason": "superseded_interim"})
            continue
        for statement, covering in entries:
            superseded_accounts.setdefault(job.id, {})[statement["index"]] = covering["job"].id
    dropped_ids = {entry["job"].id for entry in dropped}
    return [job for job in kept if job.id not in dropped_ids], dropped, superseded_accounts, overlapping


def _credits_between(statement: dict, first, last) -> Counter:
    """A statement's posted credits dated from `first` to `last`, as a multiset on the day, the cents and the
    description, casefolded, its blanks collapsed (`_package_superseded`)."""
    return Counter(
        (_row_day(row), _row_cents(row), " ".join(str(row.get("description") or "").split()).casefold())
        for row in statement["credits"]
        if (day := _iso_day(row.get("date"))) is not None and first <= day <= last
    )


def _overlap_words(pair: dict, filenames: dict[str, str], money: str) -> str:
    """Audit round 2, R2-B14 (R14): a pair of overlapping statements as the package names it (app.js
    overlappingStatementWords reads the same words)."""
    count = pair.get("shared_credit_count") or 0
    return (f"{filenames.get(pair.get('job'), pair.get('job'))} and {filenames.get(pair.get('other'), pair.get('other'))} "
            f"share {count} {'credit' if count == 1 else 'credits'} ({money}) in the days both cover, counted in both")


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


def _package_members(
    jobs, *, settings: dict | None = None, outdated: dict[str, bool] | None = None,
    repeated_accounts: dict[str, dict[int, str]] | None = None,
) -> tuple[list[tuple], list[dict]]:
    """`(members, excluded)` — what enters the package math, and what does not.

    `outdated`, when given, receives each job's `analysis_rules_outdated` (job id -> bool), read off the displayed
    copy below: the flag sits at the top of a statement, so an account of a statement of several accounts, which is
    the member, does not carry it.

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

    Audit B11 (I06): an account `repeated_accounts` names (one an earlier job of
    the package already published, `_package_duplicates`) is excluded as a
    duplicate, never summed twice; its document's other accounts stay members.
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
        if outdated is not None:
            outdated[job.id] = isinstance(analysis, dict) and analysis.get("analysis_rules_outdated") is True
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
        repeated = (repeated_accounts or {}).get(job.id) or {}
        for index, account in enumerate(accounts, start=1):
            if index in repeated:
                excluded.append({
                    "job_id": job.id,
                    "account_index": index,
                    "account_count": count,
                    "outcome": "duplicate",
                    "reason": "duplicate_statement",
                    "is_duplicate": True,
                    "duplicate_of": repeated[index],
                })
                continue
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
    # Audit B11 (I06): a repeated statement is left out before any member is expanded, listed and never summed.
    listed_jobs = list(jobs)
    jobs, dropped_duplicates, repeated_accounts, duplicate_groups = _package_duplicates(listed_jobs)
    #: 5.6 (§12): job id -> whether it was analysed with older classification rules, from its displayed copy.
    outdated_jobs: dict[str, bool] = {}
    members, excluded_accounts = _package_members(jobs, settings=settings, outdated=outdated_jobs,
                                                  repeated_accounts=repeated_accounts)
    # Audit round 2, R2-B14 (R14): after the exact repeats, a shorter printout of days another statement of its account
    # covers is left out the way a repeat is, and any other overlap that shares credits is named, never netted. Only
    # the statements the package counts (its members) are compared; when one is left out, the members are read again
    # without it, so every figure below is computed without it.
    kept_jobs, superseded_jobs, superseded_accounts, overlapping_statements = _package_superseded(
        jobs, repeated_accounts, members={(member[0].id, member[2]) for member in members})
    if superseded_jobs or superseded_accounts:
        first_place: dict[str, int] = {}
        for place, job in enumerate(listed_jobs):
            first_place.setdefault(job.id, place)
        dropped_duplicates = sorted(
            [*dropped_duplicates, *({**entry, "position": first_place[entry["job"].id]} for entry in superseded_jobs)],
            key=lambda entry: entry["position"],
        )
        for job_id, accounts in superseded_accounts.items():
            repeated_accounts.setdefault(job_id, {}).update(accounts)
        jobs = kept_jobs
        outdated_jobs = {}
        members, excluded_accounts = _package_members(jobs, settings=settings, outdated=outdated_jobs,
                                                      repeated_accounts=repeated_accounts)
        for entry in excluded_accounts:
            if entry.get("is_duplicate") is True and entry.get("account_index") in superseded_accounts.get(
                    entry.get("job_id"), {}):
                entry["reason"] = "superseded_interim"
    duplicate_accounts = sum(len(accounts) for accounts in repeated_accounts.values())
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
    #: Audit B11 (I07, I33): the calendar month each counted statement stands for (`_statement_month`), and how many
    #: counted statements print no period, each its own month.
    month_keys: set[int] = set()
    months_unplaced = 0
    #: Audit B11 (I31, I05, I13): the members whose own rows do not reconcile to the bank's figures, and the members
    #: whose True rests on rows the holds could not screen or whose payer no parser read.
    unreconciled_members: list[str] = []
    holder_unscreened_members: list[str] = []
    payer_text_unread_members: list[str] = []
    adb_weighted_sum = Decimal("0")
    adb_weight = 0
    totals = {
        # Every job the package lists, its repeats included.
        "documents": len(listed_jobs),
        # D-3, audit B11 (I06): the repeated statements, left out of every figure below.
        "duplicate_documents": len(dropped_duplicates),
        "distinct_documents": len(listed_jobs) - len(dropped_duplicates),
        "has_duplicate_documents": bool(dropped_duplicates) or bool(duplicate_accounts),
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
        # 5.6 (§9.2): True revenue, verified plus counted, and the held credits. None when a completed member's
        # revenue is not established (below).
        "true_revenue_total": 0.0,
        "true_revenue_count": 0,
        "counted_flagged_total": 0.0,
        "counted_flagged_count": 0,
        "excluded_pending_review_total": 0.0,
        "excluded_pending_review_count": 0,
        "revenue_review_items": 0,
        # Deprecated aliases for version 3.0 API consumers. 5.6 (T9): true_revenue is True revenue.
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
    # 5.6 (§9.2): the counted and held credits' evidence, and the members whose revenue is not established.
    package_tier_evidence: dict[str, list[dict]] = {"counted_flagged": [], "excluded_pending_review": []}
    package_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {}}
    unestablished_verified: list[str] = []
    unestablished_revenue: list[str] = []
    # True revenue final review M10 (§11): a member whose True or Verified figure is not established adds a partial
    # figure to that mode's denominator, so the package publishes no rate on it.
    partial_revenue_denominator = False
    any_member_gated = False
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
        verified_revenue_established = ready and (
            (
                revenue_rows_are_authoritative
                and (
                    str(metrics.get("deposits_source") or "line_items") == "line_items"
                    or abs(line_item_total - deposit_total) < 0.005
                )
            )
            or (bool(statement) and not positive_statement_rows and credits == 0)
        )
        # 5.6 (§9.2, §10.4): True revenue is established when the verified figure is and every posted credit carries
        # a tier; a payload analysed before 5.6 carries none (§12).
        tiered = revenue_rows_are_authoritative and all(
            isinstance(row["classification"].get("revenue_tier"), str) for row in posted_credit_rows
        )
        revenue_established = verified_revenue_established and (tiered or not posted_credit_rows)
        tier_rows = {
            tier: [row for row in posted_credit_rows if row["classification"].get("revenue_tier") == tier]
            for tier in ("verified", "counted_flagged", "excluded_pending_review")
        } if tiered else {}
        tier_totals = {tier: round(sum(_num(row.get("amount")) for row in rows), 2) for tier, rows in tier_rows.items()}
        member_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {}}
        for tier in member_by_reason:
            for row in tier_rows.get(tier, []):
                reason = row["classification"].get("revenue_tier_reason") or ""
                slot = member_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                slot["count"] += 1
                slot["total"] = round(slot["total"] + _num(row.get("amount")), 2)
        # T7, §10.7 (S4.4/S4.5 review): only an undecided direction conflict gates, as the rebuild counts it
        # (analysis/revenue.py); a confirmed or rejected one no longer does.
        direction_conflict = any(
            row["classification"].get("revenue_match_method") == "direction_conflict"
            and row["classification"].get("revenue_review_status") == "pending"
            for row in posted_credit_rows
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
            # 5.6 (§9.2): `true_revenue` is True revenue now, never a verified figure. Without either verified key the
            # member's verified figure is not established: None, shown as N/A, never 0.0. A member that captured no
            # credit and whose Total is zero took in nothing, and is established at zero.
            verified_fallback = _num(
                metrics.get("verified_revenue_total"),
                _num(metrics.get("confirmed_true_revenue_total"), float("nan")),
            )
            if not isfinite(verified_fallback):
                verified_fallback = 0.0 if verified_revenue_established else None
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
        # 5.6 (§9.2): without a stored denominator, the legacy eligible deposits (never `true_revenue`).
        eligible_deposits = _num(
            metrics.get("withholding_denominator"),
            _num(metrics.get("legacy_eligible_deposits"), credits),
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
        elif excluded_positions and denominator_mode == "true_revenue":
            # 5.6 (§11): an R-d pair can hold a credit this member counted (a named transfer between two members), so
            # the True-revenue denominator loses the pair's credits that it holds: verified or counted, and only those.
            counted_transfer_credits = round(sum(
                _num(raw_transactions[position].get("amount"))
                for position in excluded_positions
                if position < len(raw_transactions) and isinstance(raw_transactions[position], dict)
                and _num(raw_transactions[position].get("amount")) > 0
                and ((raw_transactions[position].get("classification") or {}).get("revenue_tier")
                     in ("verified", "counted_flagged"))
            ), 2)
            eligible_deposits = round(max(eligible_deposits - counted_transfer_credits, 0.0), 2)
        denominator_modes.add(str(denominator_mode))
        nsf_count = int(_num(metrics.get("effective_nsf_count"), 0.0))
        nsf_source = metrics.get("nsf_source")
        if isinstance(nsf_source, str):
            nsf_sources.add(nsf_source)  # a member with no analysis contributes no count and no basis
        # The days that count names (analysis/nsf_days.py), for the dashboard's NSFs chip over the combined ledger:
        # each is shown by this member's row that ended it. Display only; no figure reads it.
        nsf_days = metrics.get("nsf_days") if isinstance(metrics.get("nsf_days"), list) else []
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
        # A member without a verified figure (None) adds nothing; the total is N/A with it below (§10.4).
        totals["verified_revenue_total"] = round(
            totals["verified_revenue_total"] + _num(revenue_totals["verified_revenue"]),
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
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
        totals["potential_revenue_count"] = totals["unverified_deposit_count"]
        totals["non_revenue_total"] = round(
            totals["non_revenue_total"] + revenue_totals["non_revenue"],
            2,
        )
        totals["non_revenue_count"] += revenue_counts["non_revenue"]
        if ready and not verified_revenue_established:
            unestablished_verified.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        if ready and not revenue_established:
            unestablished_revenue.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        if ready and (
            (denominator_mode == "true_revenue" and not revenue_established)
            or (denominator_mode == "verified_revenue" and not verified_revenue_established)
        ):
            partial_revenue_denominator = True
        member_reconciles = round(sum(_num(total) for total in revenue_totals.values()), 2) == posted_credit_total
        if tiered:
            # T7 over the package's member rows, which leave out R-d's internal-transfer pairs (`excluded_positions`
            # above), so a held pair credit is neither held nor posted here. The pairing proves the money is the
            # holder's own, moving between two of its accounts: it is no revenue awaiting review, and its share must
            # not gate the package. The statement's own gate (analysis/revenue.py) cannot see the sibling account's
            # debit and counts it.
            member_gated = revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tier_totals["excluded_pending_review"],
                posted_total=posted_credit_total,
                tiers_sum_to_posted=member_reconciles,
                true_total=round(tier_totals["verified"] + tier_totals["counted_flagged"], 2),
            )
            totals["true_revenue_total"] = round(
                totals["true_revenue_total"] + tier_totals["verified"] + tier_totals["counted_flagged"], 2
            )
            totals["true_revenue_count"] += len(tier_rows["verified"]) + len(tier_rows["counted_flagged"])
            totals["counted_flagged_total"] = round(totals["counted_flagged_total"] + tier_totals["counted_flagged"], 2)
            totals["counted_flagged_count"] += len(tier_rows["counted_flagged"])
            totals["excluded_pending_review_total"] = round(
                totals["excluded_pending_review_total"] + tier_totals["excluded_pending_review"], 2
            )
            totals["excluded_pending_review_count"] += len(tier_rows["excluded_pending_review"])
            totals["revenue_review_items"] += len(tier_rows["excluded_pending_review"])
            for tier, reasons in member_by_reason.items():
                for reason, slot in reasons.items():
                    item = package_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                    item["count"] += slot["count"]
                    item["total"] = round(item["total"] + slot["total"], 2)
        else:
            # §12: a member analysed before 5.6 is gated by the rule it was analysed under.
            member_gated = (
                any(row["classification"].get("revenue_classification") == "unverified_deposit"
                    and row["classification"].get("revenue_review_status") == "pending"
                    for row in posted_credit_rows)
                or direction_conflict
                or not member_reconciles
            )
        any_member_gated = any_member_gated or (ready and member_gated)
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
            name = (classification.get("potential_payee_label") or classification.get("canonical_entity")
                    or "Unknown candidate")
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
                # Audit B11 (I32): a revenue evidence record names its unit and its account, so a mixed-currency or
                # multi-account package's evidence can be read without a join (None: one account, no currency).
                revenue_evidence = {**evidence, "source_currency": statement_currency, "source_account": account_index}
                package_revenue_evidence[revenue_state].append(revenue_evidence)
                if classification.get("revenue_tier") in package_tier_evidence:
                    package_tier_evidence[classification["revenue_tier"]].append(revenue_evidence)

        # 5.6 (§9.2, §10.4): the row's True, Counted and Held figures follow `revenue_established`, as the package's do.
        # A member with no captured credit and a zero Total is established at zero and holds no tier row.
        row_tier_totals = {tier: tier_totals.get(tier, 0.0) for tier in ("verified", "counted_flagged",
                                                                         "excluded_pending_review")}
        row_tier_counts = {tier: len(tier_rows.get(tier, [])) for tier in row_tier_totals}

        doc_row = {
            # One row per MEMBER. An account of a multi-account document is
            # named by the document it came from plus its printed position —
            # never by the document alone, which would give two members one id
            # and let the second overwrite the first everywhere a package row
            # is looked up by id.
            "id": job.id if account_index is None else f"{job.id}#account_{account_index}",
            "filename": job.filename,
            "status": job.status,
            # D-3: the content identity of this member. Audit B11 (I06): a member
            # never repeats another; a repeated statement is left out and listed
            # with its own row (`_duplicate_row`).
            "content_sha256": getattr(job, "content_sha256", None),
            "is_duplicate": False,
            "duplicate_of": None,
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
            "verified_revenue_established": verified_revenue_established,
            # 5.6 (§12): its statement was analysed with older classification rules, so re-analysis computes its true
            # revenue (a member not established for another reason, a summary-only one, is not outdated).
            "analysis_rules_outdated": outdated_jobs.get(job.id, False),
            # 5.6 (§9.2): True revenue and its parts; None for a member whose revenue is not established.
            "revenue_established": revenue_established,
            "true_revenue_total": (
                round(row_tier_totals["verified"] + row_tier_totals["counted_flagged"], 2)
                if revenue_established else None
            ),
            "true_revenue_count": (
                row_tier_counts["verified"] + row_tier_counts["counted_flagged"] if revenue_established else None
            ),
            "counted_flagged_total": row_tier_totals["counted_flagged"] if revenue_established else None,
            "counted_flagged_count": row_tier_counts["counted_flagged"] if revenue_established else None,
            "excluded_pending_review_total": (
                row_tier_totals["excluded_pending_review"] if revenue_established else None
            ),
            "excluded_pending_review_count": (
                row_tier_counts["excluded_pending_review"] if revenue_established else None
            ),
            "counted_flagged_by_reason": member_by_reason["counted_flagged"] if revenue_established else None,
            "excluded_pending_review_by_reason": (
                member_by_reason["excluded_pending_review"] if revenue_established else None
            ),
            "revenue_review_required": member_gated,
            "unverified_deposit_total": revenue_totals["unverified_deposit"],
            "unverified_deposit_count": revenue_counts["unverified_deposit"],
            "confirmed_true_revenue_total": revenue_totals["verified_revenue"],
            "confirmed_true_revenue_count": revenue_counts["verified_revenue"],
            "potential_revenue_total": revenue_totals["unverified_deposit"],
            "potential_revenue_count": revenue_counts["unverified_deposit"],
            "non_revenue_total": revenue_totals["non_revenue"],
            "non_revenue_count": revenue_counts["non_revenue"],
            "maximum_revenue": round(
                _num(revenue_totals["verified_revenue"])
                + revenue_totals["unverified_deposit"],
                2,
            ),
            # Audit B11 (I31): the four-tier identity under its own name; `revenue_reconciles` is its deprecated alias.
            "revenue_tiers_sum_to_posted": member_reconciles,
            "revenue_reconciles": member_reconciles,
            # Audit B11 (B9's I13, B10's I05): the statement integrity facts the True card shows.
            "holder_unscreened": metrics.get("holder_unscreened") is True,
            "payer_text_unread": metrics.get("payer_text_unread") is True,
            "debits": debits,
            "cash_flow": cash_flow,
            "average_daily_balance": average_daily_balance,
            "adb_calendar_days": adb_calendar_days,
            "adb_validated": adb_validated,
            "nsf_count": nsf_count,
            "nsf_source": nsf_source,
            "nsf_days": nsf_days,
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
            # Audit B11 (I07, I33): the calendar month it stands for. Two accounts of one business for one month,
            # uploaded as two files, are one month.
            month_key = _statement_month(statement.get("period_start"), statement.get("period_end"))
            if month_key is None:
                months_unplaced += 1
            else:
                month_keys.add(month_key)
            if (analysis.get("reconciliation") or {}).get("ok") is not True:
                unreconciled_members.append(doc_row["id"])
            if doc_row["holder_unscreened"]:
                holder_unscreened_members.append(doc_row["id"])
            if doc_row["payer_text_unread"]:
                payer_text_unread_members.append(doc_row["id"])
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
    # to read a null as missing data. Audit B11 (I07, I33) chose the
    # denominator (distinct calendar months, below) and kept this refusal, as
    # the audit plan says, for the new per-month True and Verified too.
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

    # Audit B11 (I07, I33): `months` is the number of distinct CALENDAR months the counted statements stand for (the
    # Monthly Statements table's rule, `_statement_month`), each statement that prints no period its own month. It
    # used to count members, so K accounts uploaded as K files read K times the months and every monthly average 1/K
    # of the business's combined figure (MINOR-10, which L1-S3 left to a policy; the audit plan chose the calendar
    # month, as MCA underwriters combine a business's accounts by month, standard §4.4 and §4.6). Each per-month
    # average below is the per-calendar-month sum across accounts divided by it.
    months = max(1, len(month_keys) + months_unplaced)
    # MINOR-10: the statement periods (one per document and printed cycle) beside the months, published when the two
    # differ; the dashboard prints "N statements · M months".
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
    # Audit B11 (I31): the four-tier identity summed over the members, under its own name; `revenue_reconciles` is its
    # deprecated alias. Neither is a reconciliation against the bank's figures: `unreconciled_documents` lists the
    # members whose own rows do not reconcile (`reconciliation.ok`), which the dashboard's Revenue chip reads.
    totals["revenue_tiers_sum_to_posted"] = (
        totals["revenue_reconciliation_delta"] == 0.0
        and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
    )
    totals["revenue_reconciles"] = totals["revenue_tiers_sum_to_posted"]
    totals["unreconciled_documents"] = sorted(unreconciled_members)
    # Audit B11 (B9's I13, B10's I05): the members whose holder's name is unknown, or whose credits' payer no parser
    # read; the True card names them.
    totals["holder_unscreened_documents"] = sorted(holder_unscreened_members)
    totals["payer_text_unread_documents"] = sorted(payer_text_unread_members)
    # 5.6 (T7, §9.2): the gate applied to each member; a package needs revenue review when one of them does.
    totals["revenue_review_required"] = any_member_gated
    totals["counted_flagged_by_reason"] = package_by_reason["counted_flagged"]
    totals["excluded_pending_review_by_reason"] = package_by_reason["excluded_pending_review"]
    totals["revenue_unestablished_documents"] = sorted(set(unestablished_revenue) | set(unestablished_verified))
    totals["true_revenue"] = totals["true_revenue_total"]
    if unestablished_revenue:
        # §10.4: a package's True, Counted and Held figures stand only when every completed member's revenue does.
        for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                    "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                    "counted_flagged_by_reason", "excluded_pending_review_by_reason"):
            totals[key] = None
    if unestablished_verified:
        # T9: confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so they are N/A with it.
        for key in ("verified_revenue_total", "confirmed_true_revenue_total", "confirmed_true_revenue"):
            totals[key] = None
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
    if partial_revenue_denominator:
        # Final review M10 (§11): the denominator is partial in the True- or Verified-revenue mode, so neither rate
        # on it is published, and the package asks for review.
        package_withholding = package_withholding_raw = None
        potential_withholding = potential_withholding_raw = None
        withholding_review_required = True
    potential_withholding_review_required = totals["potential_lender_debit_count"] > 0
    for item in potential_lenders.values():
        item["eligible_deposit_denominator"] = totals["potential_withholding_denominator"]
        item["potential_withholding_exposure"] = (
            abs(item["total_debited"]) / totals["potential_withholding_denominator"] * 100
            if totals["potential_withholding_denominator"] > 0 and not partial_revenue_denominator
            else None
        )
        item["potential_withholding_formula"] = (
            "abs(potential_lender_debit_total) / eligible_deposits * 100"
        )
    decision = "approved"
    # Audit B11: the four-tier identity is no longer read here (I31): it held by construction on every tiered member,
    # and a member whose tiers do not sum already gates through `revenue_review_required` (its T7 term, or §12's for an
    # older member). A repeated statement left out of the figures needs an analyst (I06).
    if (
        totals["failed"]
        or totals["integrity_high"]
        or totals["manual_review"]
        or potential_withholding_review_required
        or totals["revenue_review_required"]
        or totals["has_duplicate_documents"]
        # Audit round 2, R2-B14 (R14): two statements of one account that share credits in the days both cover.
        or overlapping_statements
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
        # Audit B11 (I06): the accounts of kept documents left out because an earlier job published them; only when
        # there is one, so a package without one carries no new key.
        **({"duplicate_accounts": duplicate_accounts} if duplicate_accounts else {}),
        # Audit round 2, R2-B14 (R14): the overlapping statements of one account that share credits, each pair named
        # with what it shares, counted in both (never netted); only when there is one.
        **({"overlapping_statements": overlapping_statements} if overlapping_statements else {}),
        "months": months,
        # Gross: every posted credit, not True revenue (audit B11, I07: the dashboard labels it so).
        "avg_monthly_credits": round(totals["total_credits"] / months, 2),
        "avg_monthly_debits": round(totals["total_debits"] / months, 2),
        "avg_monthly_cash_flow": round(totals["cash_flow"] / months, 2),
        # Audit B11 (I07): what an MCA advance is sized on (standard §4.1, §4.4): the per-calendar-month True and
        # Verified revenue across the package's accounts, divided by its distinct months. Both None wherever True is
        # N/A (a member not established, §10.4), and refused as the other per-month averages are (one document's
        # accounts, a mixed or undeclared currency). Non-revenue's beside them, for the copied summary.
        "avg_monthly_true_revenue": (
            None if totals["true_revenue_total"] is None else round(totals["true_revenue_total"] / months, 2)
        ),
        "avg_monthly_verified_revenue": (
            None if totals["true_revenue_total"] is None or totals["verified_revenue_total"] is None
            else round(totals["verified_revenue_total"] / months, 2)
        ),
        "avg_monthly_non_revenue": round(totals["non_revenue_total"] / months, 2),
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
            else "True revenue"
            if denominator_modes == {"true_revenue"}
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
        # 5.6 (§9.2): the by-reason money is refused with the totals; the counts stay.
        for key in ("counted_flagged_by_reason", "excluded_pending_review_by_reason"):
            if isinstance(published_totals.get(key), dict):
                published_totals[key] = {
                    reason: {**slot, "total": None} for reason, slot in published_totals[key].items()
                }
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
        published_totals["revenue_tiers_sum_to_posted"] = False
        published_totals["withholding_review_required"] = True
        published_totals["decision"] = "review_required"

    true_revenue_evidence = None if unestablished_revenue else [
        evidence for evidence in (*package_revenue_evidence["verified_revenue"], *package_tier_evidence["counted_flagged"])
    ]
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
        # Audit B11 (I06): each repeated statement left out is listed after the members, `is_duplicate` set, with the
        # job it repeats and why, and no figure (`_duplicate_row`). A job listed twice is the same job: it is listed
        # once, and only its group below names the repeat.
        "documents": documents + [
            _duplicate_row(entry) for entry in dropped_duplicates if entry["reason"] != "same_job"
        ],
        # 5.6 (§12): a member was analysed with older classification rules (its row says which), as a statement's
        # served copy says of itself.
        "analysis_rules_outdated": any(row["analysis_rules_outdated"] for row in documents),
        # D-3: one entry per statement present more than once (audit B11: by job id, content hash or statement
        # identity), listing the first job and every job that repeats it.
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
        # 5.6 (§9.2, T9): True revenue's evidence is the members' verified plus counted rows; None when a member's
        # revenue is not established.
        "true_revenue_evidence": true_revenue_evidence,
        "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
        "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
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
            "true_revenue_evidence": true_revenue_evidence,
            "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
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
    # 5.6 (true revenue spec §10.7, §12): a confirm on a rule-verified credit; a record whose state and tier disagree;
    # a payload whose posted credits carry a tier only in part.
    "a credit a rule verified can only be marked non-revenue",
    "every posted credit's revenue state must agree with its tier",
    "every posted credit carries a revenue tier, or none does",
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
        # A package stored before audit B11 can list one job twice.
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
    # Audit B11 (I06): a job listed twice (`?ids=a,a`, or a package id beside one of its own members) is one job,
    # never two members.
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
    # Audit B11 (I06): each job once, so a durable package never lists one twice.
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
        content = json.dumps(_masked(_displayed(job.analysis, export=True)), indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = _analysis_csv(_masked(_displayed(job.analysis, export=True)))
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = _analysis_xlsx(_masked(_displayed(job.analysis, export=True)))
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
