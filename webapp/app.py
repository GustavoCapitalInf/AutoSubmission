from __future__ import annotations
import io
import csv
import hashlib
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
    non_revenue_reason,
    normalize_withholding_denominator_mode,
    REVENUE_STATES,
    revenue_contribution_flags,
    revenue_review_gate,
    withholding_basis_below_floor,
    withholding_basis_publishable,
)
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.cadence import describe_cadence
from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA, WITHHOLDING_FORMULA
from analysis.revenue_view import (
    DEBIT_FLAG_KINDS,
    UNESTABLISHED_REVENUE_KEYS,
    UNESTABLISHED_VERIFIED_KEYS,
    UNESTABLISHED_WITHHOLDING_BASIS_KEYS,
    WITHHOLDING_BASIS_UNESTABLISHED,
    apply_revenue_view,
    debit_side_flags,
    withholding_basis_unestablished,
)
from analysis import zelle_view
from analysis import lender_payment_changes as payment_changes_module
from analysis.true_revenue import zelle_deposit
from analysis.zelle_view import ZELLE_DEPOSITS_KEY, ZELLE_ROW_TAG, apply_zelle_view
from analysis.payee_matcher import match_known_payee
from analysis.transaction_classifier import (
    _CONSUMER_P2P_RAIL,
    _PUSH_RAIL,
    _RETURN_CREDIT_TIERS,
    _TRANSFER_WORDING,
    RETURNED_FUNDER_PAYMENT_WINDOW_DAYS,
    _deposit_channel_credit,
    _deposit_return_debit,
    _received_on_day,
    _returned_payment_credit,
    _undo_debit_names_a_credit,
    is_round_sum,
    paper_or_cash_deposit,
)
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


def _zelle_setting(settings: dict | None) -> bool:
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): whether the settings snapshot asks for
    Zelle deposits counted as True revenue (Yes, the default; a missing or malformed value reads as Yes)."""
    value = (settings or {}).get("zelle_true_revenue", SETTINGS_DEFAULTS["zelle_true_revenue"])
    return value if isinstance(value, bool) else SETTINGS_DEFAULTS["zelle_true_revenue"]


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
    lists, `metrics.nsf_days`), so a download carries what it carried before the chip.

    The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §9.2, §10; R2-OW17): FIRST, the
    Zelle reading the setting "Mark Zelle Payments as True Revenue" asks for (analysis/zelle_view.py), whose stored
    edits are paths in the stored shape, so it runs before any served key is added."""
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    if carry_over is None:
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    analysis = apply_zelle_view(analysis, counted=_zelle_setting(settings))
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over, list_days=not export)
    # 5.6 (true revenue spec §10.4, §12): each account's revenue flags, and an older payload's True revenue nulled.
    served = apply_revenue_view(apply_flagged_groups_to_payload(rebased, enabled=settings))
    # Audit B11 (I51): a download never prints a figure the dashboard reads as N/A.
    return _export_revenue_view(served) if export else served


#: Audit B11 (I51, §10.4 for the exports): the figures a download leaves empty when an account's revenue is not
#: established, and when its Verified figure is not. Audit round 2, R2-B16 (R52): the lists live in
#: analysis/revenue_view.py, which the CLI reads too.
_UNESTABLISHED_REVENUE_KEYS = UNESTABLISHED_REVENUE_KEYS
_UNESTABLISHED_VERIFIED_KEYS = UNESTABLISHED_VERIFIED_KEYS


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
    # The final review of round 2, F1 (§10.4, §11): the withholding basis the served copy marks as not established
    # (its rate is None already) is an empty cell too, as the dashboard reads it N/A.
    if metrics.get(WITHHOLDING_BASIS_UNESTABLISHED) is True:
        nulled.update({key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in metrics})
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
        totals = exported["totals"] = {
            **totals, **{key: None for key in _PACKAGE_PARTIAL_REVENUE_KEYS if key in totals},
        }
    # The final review of round 2, F1 (§10.4, §11): the withholding basis summed over a member whose basis is not
    # established (final review M10: no rate on it) is an empty cell, as the dashboard reads it N/A. Audit round 3,
    # R3-B03 (R3-27): so is the sum of members analysed under different bases, which is no basis at all.
    if isinstance(totals, dict) and (totals.get(WITHHOLDING_BASIS_UNESTABLISHED) is True
                                     or totals.get("withholding_basis_mixed") is True):
        exported["totals"] = {
            **totals, **{key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in totals},
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
    # The final review of round 2, F1 (§10.4, §11): a member whose withholding basis is not established prints no basis.
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
                if section == "metrics" and key in ("adb", *_TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
                    continue  # emitted as their own sections below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
                rows.append((section, key, "" if item is None else item))
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
        rows.extend(_tier_reason_rows(metrics))
        rows.extend(_zelle_deposit_rows(metrics.get(ZELLE_DEPOSITS_KEY)))
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


#: The owner's request of 2026-10-06 (lender payment changes; true revenue spec §10.8; R2-OW18, H1): the fields of a
#: `lender_payment_change_<n>` section, in order; a field the item does not carry is an empty cell. `schedule_confirmed`
#: and `via` are the orchestrator's choices of 2026-10-06 (§ Still open 18 and 23); `first_after_kind`,
#: `resumed_date` (a pause) and `last_step_percent` (a change through unreported levels) are R2-OW18 review round 1's.
#: Audit round 3, R3-B05: a pause's catch-up (`first_after_amount`, `first_after_multiple`) and its debits of 2x or
#: more inside the gap (`larger_debits_inside`, "2054-03-16 1300.0; ..."), R3-25; a Caught up item's fields (the
#: owner's answer of 2026-10-07: `missed_payments` to `catch_up_amount`). Its review round 1: a pause's catch-ups after
#: the presence that ended it, before payments resumed (`catch_ups_inside`, "2054-03-17 1700.0 2x; ...").
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
#: R2-OW18 (H1): the nested notes, flattened with dots. Audit round 3, R3-B05: a stop's `other_debits_after.catch_ups`
#: and `payoff.earlier` (R3-25), and a pause's or a stop's `same_amount_debits` (R3-84).
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
#: R2-OW18 (H2): the package's added fields.
LENDER_PAYMENT_CHANGE_PACKAGE_FIELDS = (
    "source_document", "from_document", "to_document", "cross_statement", "source_currency", "source_period_end",
)


def _lender_payment_change_rows(items: object, *, package: bool = False) -> list[tuple[str, str, object]]:
    """R2-OW18 (H1, H2): one readable section per lender payment change, `lender_payment_change_<n>`, with
    LENDER_PAYMENT_CHANGE_EXPORT_FIELDS and the dotted notes (a package adds its source fields and the other-account
    note). A label is statement text: these rows reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for number, item in enumerate((entry for entry in items if isinstance(entry, dict))
                                  if isinstance(items, list) else (), start=1):
        section = f"lender_payment_change_{number}"
        for name in LENDER_PAYMENT_CHANGE_EXPORT_FIELDS:
            value = item.get(name)
            if name in ("alongside", "via") and isinstance(value, list):
                # A via level carries the step into it (R2-OW18 review round 1): "weekly 950.0 (-5%)".
                value = "; ".join(f"{entry.get('cadence')} {entry.get('amount')}"
                                  + (f" ({entry['change_percent']:+d}%)" if name == "via"
                                     and isinstance(entry.get("change_percent"), int) else "")
                                  for entry in value if isinstance(entry, dict))
            elif name == "larger_debits_inside" and isinstance(value, list):
                # Audit round 3, R3-25: "2054-03-16 1300.0; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')}" for entry in value
                                  if isinstance(entry, dict))
            elif name == "catch_ups_inside" and isinstance(value, list):
                # R3-B05 review round 1: "2054-03-17 1700.0 2x; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')} {entry.get('multiple')}x"
                                  for entry in value if isinstance(entry, dict))
            rows.append((section, name, "" if value is None else value))
        # Audit round 3, R3-B06 (R3-83): the package's reappearance note beside the continuation.
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


#: 5.6 (true revenue spec §10.8): the by-reason figures of the counted and held tiers, exported as readable rows.
#: R2-OW03 (owner ruling 2026-10-02): and the non-revenue breakdown (`non_revenue.<code>.count` / `.total`).
_TIER_REASON_KEYS = ("counted_flagged_by_reason", "excluded_pending_review_by_reason", "non_revenue_by_reason")


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


def _zelle_deposit_rows(
    figures: object, section: str = "revenue_tier", *, setting: bool | None = None,
) -> list[tuple[str, str, object]]:
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (spec §10.8; R2-OW17): the served Zelle figures
    (`zelle_deposits`, analysis/zelle_view.py) as readable rows of the revenue_tier section, only where the key is
    present: `zelle_deposits.setting` (Yes or No), `.count`, `.total`, `.<tier>.count`, `.<tier>.total` and
    `.setting_applied`. A money figure the package refuses is an empty cell. `setting` is the choice the figures were
    served under; an account's figures say it themselves (Yes exactly when the reading served is the one the setting
    asked for and counts, or is not and does not: `counted_as_true_revenue` equals `setting_applied`)."""
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
    tagged: list[bool] = []
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
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): a trailing `zelle` column, only in a block
    # where a row carries the served Zelle tag (Yes), 'Zelle' on those rows; every other block is today's.
    if any(tagged):
        return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS, "zelle"),
                *((*row, "Zelle" if zelle else "") for row, zelle in zip(rows, tagged))]
    return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS), *rows]


#: Audit round 2, R2-B16 (R53): the columns of the statement downloads' posted-debit table; the last, a confirmed
#: funder's payment the bank returned unpaid (the location of the credit that returned it, the record's
#: `returned_funder_payment_by`; owner ruling 2026-10-02, the underwriter's Q5, R2-OW13's note to this batch).
_POSTED_DEBIT_COLUMNS = (
    "date", "description", "amount", "currency", "classification", "flagged_group", "canonical_entity",
    "review_required", "returned_funder_payment",
)


def _posted_debit_table(analysis: dict) -> list[tuple]:
    """Audit round 2, R2-B16 (R53): one row per posted debit, the posted-credit table's twin, so the lender payments,
    the withholding and the NSFs read row by row (the ledger otherwise sits only in one JSON cell, over a spreadsheet's
    cell limit on most statements): a `columns` row, then `(posted_debit, n, date, description, amount (signed),
    currency, classification, flagged group, entity, review required, returned funder payment)`. The flag group is
    written only where Settings shows it (`flag_shown`, analysis/flagged_view.py), so an unticked group never leaks;
    the other fields are the record's as served (the last, R2-OW13's `returned_funder_payment_by`: where a confirmed
    funder's payment came back unpaid, the location of the credit that returned it). Every account of a document
    payload has its own block, under its section prefix. Written after the credit table; its statement text reaches a
    file only through `_escaped_rows`."""
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
    currency = _statement_currency(analysis) or ""
    rows: list[tuple] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = _num(transaction.get("amount"))
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
#: Audit round 2, R2-B15 (R15): the fields of an `excluded_account_<n>` section of the package downloads, in order.
_EXCLUDED_ACCOUNT_FIELDS = ("job_id", "filename", "account_index", "account_count", "outcome", "reason")


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        if key in (*_TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
            continue  # emitted as readable rows below
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("totals", key, "" if value is None else value))
    rows.extend(_tier_reason_rows(totals))
    # R2-OW17: the package's Zelle figures; its `counted_as_true_revenue` is the setting it was built under.
    package_zelle = totals.get(ZELLE_DEPOSITS_KEY)
    rows.extend(_zelle_deposit_rows(
        package_zelle,
        setting=package_zelle.get("counted_as_true_revenue") is True if isinstance(package_zelle, dict) else None,
    ))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
    # money cells and read them as missing data rather than as refused units.
    for key, value in (package.get("currency") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("currency", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            if key in (*_TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
                continue  # emitted as readable rows below
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"document_{idx}", key, "" if value is None else value))
        if document.get("duplicate_reason") in SUPERSEDED_REASON_WORDS:
            # Audit round 2, R2-B14 (R14 and its review round 1): the words the dashboard's notice gives a left-out
            # shorter printout or printout of more than a month.
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
    # Audit round 2, R2-B15 (R15): each account left out of every figure for another reason than a repeat (a repeat is
    # named by its document row and its duplicate group above), so the sheet an underwriter reads names it.
    left_out = [entry for entry in package.get("excluded_accounts") or []
                if isinstance(entry, dict) and entry.get("is_duplicate") is not True]
    for idx, entry in enumerate(left_out, start=1):
        for key in _EXCLUDED_ACCOUNT_FIELDS:
            value = entry.get(key)
            rows.append((f"excluded_account_{idx}", key, "" if value is None else value))
    # Audit round 2, R2-B14 (R14): each pair of overlapping statements that share credits, and the notice's words for it.
    filenames: dict[str, str] = {}
    for document in package.get("documents") or []:
        member = _PACKAGE_MEMBER_ID.fullmatch(str(document.get("id") or ""))
        filenames.setdefault(member[1] if member else str(document.get("id") or ""), document.get("filename"))
    for idx, pair in enumerate(totals.get("overlapping_statements") or [], start=1):
        for key, value in pair.items():
            rows.append((f"overlapping_statement_{idx}", key, "" if value is None else value))
        total = pair.get("shared_credit_total")
        # R2-B14 review round 1 (CURRENCY DOCTRINE): the shared money is the pair's account's, and its words say so;
        # a pair whose currency is unknown prints no unit, as the dashboard does.
        money = (f"{float(total):,.2f}" + (f" {pair['currency']}" if pair.get("currency") else "")
                 if _is_money_value(total) else "N/A")
        rows.append((f"overlapping_statement_{idx}", "words", _overlap_words(pair, filenames, money)))
    # Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): each match the package passes made across its statements
    # (`package_match_<n>`, its credit and debit as JSON) and each debit they flag (`debit_flag_<n>`), the statement's
    # words written through the escaped-row path like every other cell.
    for section, entries in (("package_match", package.get("package_matches")), ("debit_flag", package.get("debit_flags"))):
        for idx, entry in enumerate(entries or [], start=1):
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): each lump-sum payoff (in paid to lenders, out of
    # the withholding rate), `lump_sum_payoff_<n>`, its words the bank's, through the escaped-row path.
    for idx, item in enumerate(package.get("lump_sum_payoffs") or [], start=1):
        if isinstance(item, dict):
            for key, value in item.items():
                rows.append((f"lump_sum_payoff_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("funders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"funder_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("potential_lenders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"potential_lender_{idx}", key, "" if value is None else value))
    # The owner's request of 2026-10-06 (R2-OW18, H2): each lender payment change across the package's statements, and
    # each member not checked across statements with its reason.
    rows.extend(_lender_payment_change_rows(package.get("lender_payment_changes"), package=True))
    for idx, entry in enumerate(package.get("lender_payment_changes_unchecked") or [], start=1):
        for key in ("source_document", "reason"):
            value = entry.get(key) if isinstance(entry, dict) else None
            rows.append((f"lender_payment_unchecked_{idx}", key, "" if value is None else value))
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
    tagged: list[bool] = []
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
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # R2-OW17: the trailing `zelle` column, only where a row carries the served Zelle tag.
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


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


#: Audit round 2, R2-B16 (R53): the most characters a spreadsheet cell holds (Excel's limit, counted in UTF-16 units).
XLSX_CELL_LIMIT = 32767


def _xlsx_text(value: object) -> str:
    """An inline string's text (R53): the value, or, when it holds more than XLSX_CELL_LIMIT UTF-16 units (a character
    outside the Basic Multilingual Plane counts two, as Excel counts it), a pointer naming its length. Never cut: a
    cell over the limit makes Excel refuse the file at load, and its repair truncates the cell. The CSV and the JSON
    download keep such a value whole."""
    text = str(value)
    units = len(text.encode("utf-16-le", "surrogatepass")) // 2
    if units > XLSX_CELL_LIMIT:
        return f"Not shown: {units:,} characters, over the spreadsheet cell limit; see the JSON download."
    return text


def _xlsx_cell(ref: str, value: object) -> str:
    """One cell, typed (audit B11, I52): a bool is a boolean cell (checked first: a bool is an int), a finite int or
    float a number, so SUM and a pivot add the money; anything else, NaN, inf and every numeric-looking string
    included (a masked account number, a leading-zero reference), is an inline string. An inline string is never a
    formula; its text keeps `_escape_formula`'s apostrophe, which a Save As CSV carries on, so the cell stays inert
    when the sheet is written back out as text. Audit round 2, R2-B16 (R53): a text over the spreadsheet cell limit is
    replaced whole by a pointer (`_xlsx_text`)."""
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
    return _rows_xlsx(_analysis_rows(analysis) + _posted_credit_table(analysis) + _posted_debit_table(analysis))


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
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the funder payments returned unpaid; their count is
    # unit-free and stays.
    "returned_funder_payment_total",
    # Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the package passes' money, published only where a pass
    # found a row (_PACKAGE_MATCH_TOTAL_KEYS); their counts are unit-free and stay.
    "returned_deposit_cross_statement_total",
    "unmatched_deposit_return_total",
    "processor_chargeback_total",
    # Owner ruling 2026-10-02 (the underwriter's Q4; R2-OW16): the deposits pass 2 held and the held ones it annotated.
    "own_account_transfer_held_total",
    "own_account_transfer_already_held_total",
    # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): the lump-sum payoffs, published only where a
    # member has one (_PACKAGE_MATCH_TOTAL_KEYS); their count is unit-free and stays.
    "lump_sum_payoff_total",
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

#: Audit round 3, R3-B03 (R3-27; true revenue spec §9.2, §11): each withholding basis's label, as a package names a
#: member's basis where its members were analysed under different ones (`withholding_basis_by_member`).
_WITHHOLDING_BASIS_LABELS = {
    "legacy_eligible_deposits": "Legacy eligible deposits",
    "verified_revenue": "Verified revenue",
    "true_revenue": "True revenue",
}

#: Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the totals the package passes publish only where a pass
#: found a row, so a currency refusal nulls each of them only where it is published (a package without one keeps no
#: such key).
_PACKAGE_MATCH_TOTAL_KEYS = frozenset({
    "returned_deposit_cross_statement_total", "unmatched_deposit_return_total", "processor_chargeback_total",
    # R2-OW16 (the underwriter's Q4).
    "own_account_transfer_held_total", "own_account_transfer_already_held_total",
    # Audit round 3, R3-B03 (R3-79): published the same way, only where a member has a lump-sum payoff.
    "lump_sum_payoff_total",
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
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): a funder's payments returned unpaid, summed across the
    # package like its total debited.
    "returned_payment_total",
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
      bytes, so another content hash) prints the same key;
    * audit round 3, R3-B18 (R3-02): its ledger key (`ledger:`), when it prints both period days, both balances and at
      least one ledger row: the period's days, the two balances and a hash over every ledger row's day and signed
      cents (`_row_day`, `_row_cents`), whatever its classification. It is a parse identity no review decision, rules
      version or setting changes, and it reads no bank and no account number, so another reading of a statement
      whose bank or number was not read (or was read on one reading only) still matches it; `_package_duplicates`
      never joins it between two printed full numbers that conflict.

    An empty set when none is established: such an account is never taken for a copy of another."""
    if not isinstance(account, dict) or not isinstance(account.get("statement"), dict):
        return frozenset()
    statement = account["statement"]
    identities: set[str] = set()
    ledger = [row for row in statement.get("transactions") or [] if isinstance(row, dict)]
    if ledger:
        identities.add("digest:" + account_content_digest(account))
    bank = " ".join(str(statement.get("bank") or "").split()).casefold()
    digits = "".join(character for character in str(statement.get("account_number") or "") if character.isdigit())
    start, end = statement.get("period_start"), statement.get("period_end")
    opening, closing = statement.get("beginning_balance"), statement.get("ending_balance")
    printed = (isinstance(start, str) and start and isinstance(end, str) and end
               and _is_money_value(opening) and _is_money_value(closing))
    if printed and bank and len(digits) >= 4:
        identities.add(f"statement:{bank}|{digits[-4:]}|{start}|{end}|{float(opening):.2f}|{float(closing):.2f}")
    if printed and ledger:
        rows = json.dumps(sorted((_row_day(row), _row_cents(row)) for row in ledger))
        identities.add(f"ledger:{start}|{end}|{float(opening):.2f}|{float(closing):.2f}|"
                       + hashlib.sha256(rows.encode("utf-8")).hexdigest())
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
    posted credit of it carries the analyst's decision (`revenue_review_status` confirmed or rejected). The owner's
    amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): a decision in EITHER Zelle reading counts (the stored
    records and the counted reading's, analysis/zelle_view.py): a Yes-mode reject on a Zelle row lives only in the
    counted reading's edits, the stored reading having gone back to its analysis state."""
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
    counted = zelle_view.reading(analysis, counted=True) if accounts else analysis
    decided = any(
        isinstance(row, dict) and _num(row.get("amount")) > 0 and isinstance(row.get("classification"), dict)
        and row["classification"].get("is_posted") is not False
        and row["classification"].get("revenue_review_status") in _REVIEW_DECISIONS
        for reading in ((accounts,) if counted is analysis else (accounts, _stored_accounts(counted)))
        for account in reading
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
    number included) matches as before, and so does a masked or a four-digit print. Audit round 3, R3-B18 (R3-02): a
    ledger key (`ledger:`, the period, the balances and every ledger row's day and signed cents, no bank and no
    number) is read as a statement key is, so another reading of a statement whose bank or number was not read is the
    same statement (`same_statement`, the copy kept by `_copy_rank`), never between conflicting printed numbers.

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
    (`duplicate_kept_because`, R16; None for a printout the account's other statements print, R14)."""
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


#: Audit round 2, R2-B15 (R13): the days of an average calendar month (365.25 / 12), the unit the days an account's
#: statements cover are read in.
_AVERAGE_MONTH_DAYS = Decimal("30.4375")


def _covered_days(period_start: object, period_end: object) -> set:
    """Audit round 2, R2-B15 (R13): the days a statement's printed period covers, its first and last included; empty
    unless both days read and the end is not before the start; at most 400 days, as `_statement_month` reads."""
    from datetime import timedelta

    start, end = _iso_day(period_start), _iso_day(period_end)
    if start is None or end is None or end < start:
        return set()
    days, day = set(), start
    while day <= end and len(days) < 400:
        days.add(day)
        day += timedelta(days=1)
    return days


def _months_covered(days: int) -> int:
    """Audit round 2, R2-B15 (R13): a count of days as whole calendar months, half up (90 days are 3, 59 are 2, 45 are
    1)."""
    return int((Decimal(days) / _AVERAGE_MONTH_DAYS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


#: Audit round 2, R2-B14 (R14): the words a left-out shorter printout reads in the package downloads, as the dashboard's
#: duplicate notice reads them (app.js DUPLICATE_REASON_WORDS).
SUPERSEDED_INTERIM_WORDS = "a shorter printout of days another statement covers"
#: Audit round 2, R2-B14 review round 1: the words a left-out printout of more than a month reads (app.js
#: DUPLICATE_REASON_WORDS), whose rows the account's other statements print.
SUPERSEDED_LONG_PRINTOUT_WORDS = "a printout of more than a month whose every row other statements of the account print"
#: Each reason `_package_superseded` leaves a statement out for, and its words.
SUPERSEDED_REASON_WORDS = {
    "superseded_interim": SUPERSEDED_INTERIM_WORDS,
    "superseded_long_printout": SUPERSEDED_LONG_PRINTOUT_WORDS,
}
#: A statement period of more days than this is more than a month (`_package_superseded` tests it first).
_MONTH_DAYS = 31
#: Audit round 3, R3-B18 (R3-04): the most days two statements of one account may share and still be named only when
#: they share a credit (a boundary day or a cycle that closes on the day the next opens; every one of the corpus's
#: overlapping distinct-period pairs shares exactly one day).
_OVERLAP_BOUNDARY_DAYS = 3
#: Audit round 3, R3-B18 (R3-04): the most days apart two statements of one account may print one credit (equal cents)
#: and still share it (`_shared_credits`): a transaction or value date, a pending item posted a day later.
_OVERLAP_SHIFT_DAYS = 3
#: Audit round 3, R3-B18 (R3-05): the fewest days of a month-length statement, the only kind a printout of more than a
#: month is left out in favour of in `_package_superseded`'s first phase (7,096 of the corpus's 7,241 printed periods
#: run 28 to 35 days; a shorter one is a partial month or a printout).
_FULL_STATEMENT_DAYS = 28
#: Audit round 3, R3-B18 review round 1: the most days of a monthly cycle (every printed period of the corpus's 7,241
#: that runs more than a month runs 32 to 35 days; none runs 36 or more), so a statement of more days is a printout (a
#: 60- or 90-day activity printout, a multi-month export), never a month its partial printouts are cut from: the first
#: phase of `_package_superseded` tests it against all its account's statements, not only the month-length ones.
_LONGEST_CYCLE_DAYS = 35


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
    the package does not count never covers another or is covered) are compared when they are one account's
    (`_pair_kind`; audit round 3, R3-B18, R3-02: every account with a period, whatever its bank and digits): a
    "printed" pair prints one bank (`_package_bank`: casefolded, an informal printout's label read as its bank) and
    one last four (`_printed_account_digits`) with no conflict between full numbers (`_numbers_conflict`); a statement
    that prints no bank or fewer than four digits makes a "possible" pair with one whose bank, account name and
    declared currency do not differ from its own where both print one. A statement's period is its printed one, or
    else its first and last posted row's day. Two accounts of one document are never compared. A statement is left
    out when its period lies inside the union of the periods of the other kept statements it is one account with, it
    prints a posted row, and every posted row of it, credit or debit, is a posted row of those statements, as a
    multiset on the day and the signed cents (never a fuzzy match). The statements of more than a month
    (`_MONTH_DAYS`) are tested first, the longest first, so a quarterly printout or a multi-month export whose rows the
    account's other statements print is left out (`superseded_long_printout`) and those statements stay; audit round
    3, R3-B18 (R3-05): in that first phase a statement is left out only in favour of month-length statements
    (`_FULL_STATEMENT_DAYS` days or more) that alone cover its period and print its rows, no two of which sharing its
    days overlap each other by more than `_OVERLAP_BOUNDARY_DAYS` days or share a credit in the days both cover (no
    double count between them); otherwise it waits. Review round 1: the month-length rule reads a statement of a
    monthly cycle's length (`_LONGEST_CYCLE_DAYS` days or fewer) only; a printout of more days is proved by all its
    account's statements (a month-to-date, a short first or closing month included), and the double-count test reads
    only the statements the second phase would keep side by side (`settled`: a month-to-date beside its month, or a
    printout two neighbouring months print, is left out there first, and before them another printout of more than
    `_LONGEST_CYCLE_DAYS` days that the others print, as this phase leaves it out, so a second activity printout never
    keeps the first in the package). A printout of 32 to 35 days that only a shorter statement proves with the
    month-length ones waits too: the second phase may leave that shorter statement, or a month-length one inside the
    printout, out in its favour, and the days the printout shares with a statement it does not print whole count
    twice, the pair named (the recorded residual).
    Then every statement left, long ones included, the shortest first, so an interim or month-to-date printout beside
    the full statement, a second month-to-date printout of one open month, or a short custom range of days the full
    statements print is left out (`superseded_interim`) and a full month, a 32-35-day monthly cycle included, is never
    left out for partial printouts of it that print nothing it does not (of two periods alike, the one listed later is
    tested first; R2-B14 review round 1). It repeats the statement left in the package that shares the most of its
    days (of two alike, the one listed first).

    Any other overlap of two statements of one account is never netted. Audit round 3, R3-B18 (R3-04): the credits
    the two share in the days both cover are matched one to one on the cents within `_OVERLAP_SHIFT_DAYS` days,
    whatever their wording (`_shared_credits`). A printed pair is named when it shares a credit, shares more than
    `_OVERLAP_BOUNDARY_DAYS` days, or one period lies inside the other; a possible pair when it shares more than
    `_OVERLAP_BOUNDARY_DAYS` days and either shares at least half the credits the fewer-credited side prints in those
    days, or the two print one period and the same opening and closing balances. A named pair is listed in
    `overlapping`, ``{"job", "other", "shared_credit_count", "shared_credit_total", "currency", "days_shared"}`` (`job`
    the statement listed later; `currency` the account's, None when the two declare different ones; `days_shared` the
    days both cover; with `account` and `other_account` for an account of a document), and sends the package to
    review; the figures keep the double count.

    Returns ``(kept jobs, dropped, superseded_accounts, overlapping)``: a job whose every account is left out is
    dropped as a duplicate is (``{"job", "duplicate_of", "reason"}``, in listed order); an account of a document whose
    other accounts stay is named in `superseded_accounts` (job id -> {account index: (the covering job's id, the
    reason)}) for `_package_members` to leave out with `repeated_accounts`."""
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
            statement = account.get("statement") or {}
            rows = _posted_rows(account)
            span = _statement_span(account, rows)
            if span is None:
                continue
            days = (span[1] - span[0]).days + 1
            statements.append({
                "job": job, "order": order, "index": index if document else None, "accounts": len(accounts),
                # Audit round 3, R3-B18 (R3-02, R3-04): what `_pair_kind` reads the account by, whatever is printed.
                "bank": _package_bank(statement), "digits": _printed_account_digits(account),
                "name": " ".join(str(statement.get("account_name") or "").split()).casefold(),
                "currency": _statement_currency(account),
                "opening": statement.get("beginning_balance"), "closing": statement.get("ending_balance"),
                "start_printed": _iso_day(statement.get("period_start")),
                "end_printed": _iso_day(statement.get("period_end")),
                "span": span, "days": days,
                "rows": Counter((_row_day(row), _row_cents(row)) for row in rows),
                "credits": [row for row in rows if _num(row.get("amount")) > 0],
            })

    def peers(statement: dict, alive: list[dict]) -> list[dict]:
        """The statements left in the package that `statement` is one account with (`_pair_kind`)."""
        return [other for other in alive if _pair_kind(statement, other) is not None]

    def most_days(statement: dict, others: list[dict]) -> dict:
        return max(others, key=lambda other: (_days_shared(statement["span"], other["span"]), -other["order"]))

    def printed_by(statement: dict, others: list[dict]) -> bool:
        """The drop's proof: `others` cover the statement's period and print every posted row of it (a multiset on the
        day and the signed cents), and it prints one."""
        if not others or not statement["rows"] or not _span_covered(statement["span"],
                                                                    [other["span"] for other in others]):
            return False
        pool: Counter = Counter()
        for other in others:
            pool.update(other["rows"])
        return not statement["rows"] - pool

    superseded: list[tuple[dict, dict]] = []
    overlapping: list[dict] = []
    alive = list(statements)
    left_out: list[tuple[dict, dict]] = []
    def only_rows_of(statement: dict, printout: dict) -> bool:
        """Audit round 3, R3-B18 review round 2: whether `statement` prints a posted row in `printout`'s days and every
        posted row it prints there is one of `printout`'s (a multiset on the day and the signed cents)."""
        start, end = printout["span"]
        within = Counter({key: count for key, count in statement["rows"].items()
                          if (day := _iso_day(key[0])) is not None and start <= day <= end})
        return bool(within) and not within - printout["rows"]

    def double_counted(one: dict, two: dict, printout: dict) -> bool:
        """Two statements that overlap each other by more than a boundary's days, or share a credit in the days both
        cover (`_shared_credits`): kept side by side, they count money twice. Audit round 3, R3-B18 review round 2:
        only two statements that are one account's, each printing a posted row (a statement printing none counts no
        money): a printed pair (`_pair_kind`), or a possible pair that the overlap pass names (`_possible_pair_named`)
        or whose two statements each print only rows of the `printout` being tested in its days (`only_rows_of`), so a
        second account of the holder at the bank whose number is not read, a possible peer of every statement of the
        first that prints rows of its own, never reads as a double count beside the first."""
        if not one["rows"] or not two["rows"]:
            return False
        kind = _pair_kind(one, two)
        first, last = max(one["span"][0], two["span"][0]), min(one["span"][1], two["span"][1])
        if kind is None or first > last:
            return False
        count = _shared_credits(one, two, first, last)[0]
        if kind == "possible" and not _possible_pair_named(one, two, first, last, count) and not (
                only_rows_of(one, printout) and only_rows_of(two, printout)):
            return False
        return (last - first).days + 1 > _OVERLAP_BOUNDARY_DAYS or count >= 1

    def interim(group: list[dict]) -> list[dict]:
        """The second phase's pass over `group` alone: the shortest first (of two alike, the later listed first), one
        left out when the others of `group` it is one account with print it (`printed_by`)."""
        left = list(group)
        for statement in sorted(left, key=lambda item: (item["days"], -item["order"])):
            if printed_by(statement, peers(statement, left)):
                left.remove(statement)
        return left

    def counts_twice(statement: dict, group: list[dict]) -> bool:
        """Whether two statements of `group` that share days with `statement` count money twice (`double_counted`)."""
        sharing = [other for other in group if _days_shared(statement["span"], other["span"]) > 0]
        return any(double_counted(one, two, statement) for place, one in enumerate(sharing)
                   for two in sharing[place + 1:])

    def settled(group: list[dict]) -> list[dict]:
        """Audit round 3, R3-B18 review round 1: the statements of `group` the second phase would keep side by side
        (`interim`: a month-to-date beside its month, a printout two neighbouring months print, left out), so the
        double count that phase resolves never keeps a long printout in the package. Before that pass, the longest
        first, a printout of more than `_LONGEST_CYCLE_DAYS` days that the others print is left out, as the first phase
        leaves it out. Review round 2: so is a printout of 32 to `_LONGEST_CYCLE_DAYS` days that the month-length
        statements of `group` alone print (`_FULL_STATEMENT_DAYS`) and that count nothing twice between them, read on
        the second phase's own pass over them (`interim`), as the first phase leaves it out, so a 34-day export the
        monthly statements print is no double count beside the month it straddles."""
        left = list(group)
        for statement in sorted((item for item in group if item["days"] > _MONTH_DAYS),
                                key=lambda item: (-item["days"], -item["order"])):
            if statement["days"] > _LONGEST_CYCLE_DAYS:
                if printed_by(statement, peers(statement, left)):
                    left.remove(statement)
                continue
            proof = [other for other in peers(statement, left) if other["days"] >= _FULL_STATEMENT_DAYS]
            if printed_by(statement, proof) and not counts_twice(statement, interim(proof)):
                left.remove(statement)
        return interim(left)

    # Phase 1 (R2-B14 review round 1): a printout of more than a month, the longest first (of two alike, the later
    # listed first). Audit round 3, R3-B18 (R3-05): it is left out only in favour of month-length statements
    # (`_FULL_STATEMENT_DAYS` or more) that alone prove it and no two of which sharing its days overlap each other by
    # more than `_OVERLAP_BOUNDARY_DAYS` or share a credit (no double count between them), so a 32-35-day monthly
    # cycle is never left out for partial printouts of it. Review round 1: the month-length rule reads a statement of a
    # monthly cycle's length only (`_LONGEST_CYCLE_DAYS`); one of more days is a printout, proved by all its account's
    # statements (a month-to-date, a short first or closing month), and the double-count test reads only the
    # statements the second phase would keep side by side (`settled`), another printout of more than
    # `_LONGEST_CYCLE_DAYS` days the others print left out before them.
    for statement in sorted((item for item in statements if item["days"] > _MONTH_DAYS),
                            key=lambda item: (-item["days"], -item["order"])):
        full = [other for other in peers(statement, alive)
                if other["days"] >= _FULL_STATEMENT_DAYS or statement["days"] > _LONGEST_CYCLE_DAYS]
        if not printed_by(statement, full) or counts_twice(statement, settled(full)):
            continue
        statement["reason"] = "superseded_long_printout"
        left_out.append((statement, most_days(statement, full)))
        alive.remove(statement)
    # Phase 2: every statement left, long ones included, the shortest first (of two alike, the later listed first),
    # against all the statements it is one account with: the partial printouts that print nothing a statement does not
    # are left out before it, and it stays.
    for statement in sorted(alive, key=lambda item: (item["days"], -item["order"])):
        others = peers(statement, alive)
        if not printed_by(statement, others):
            continue
        statement["reason"] = "superseded_interim"
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
            kind = _pair_kind(earlier, later)
            if kind is None:
                continue
            first, last = max(earlier["span"][0], later["span"][0]), min(earlier["span"][1], later["span"][1])
            if first > last:
                continue
            days_shared = (last - first).days + 1
            count, cents = _shared_credits(earlier, later, first, last)
            if kind == "printed":
                # R3-04: a printed pair sharing a credit, more than a boundary's days, or a period inside the other.
                inside = any(one["span"][0] >= two["span"][0] and one["span"][1] <= two["span"][1]
                             for one, two in ((earlier, later), (later, earlier)))
                named = count >= 1 or days_shared > _OVERLAP_BOUNDARY_DAYS or inside
            else:
                # R3-02: a possible pair only where more than a boundary's days are shared and the shared credits, or
                # one period printed with both balances, show the two are one account's.
                named = _possible_pair_named(earlier, later, first, last, count)
            if not named:
                continue
            pair = {
                "job": later["job"].id,
                "other": earlier["job"].id,
                "shared_credit_count": count,
                "shared_credit_total": round(cents / 100, 2),
                # R2-B14 review round 1 (CURRENCY DOCTRINE): the unit of the shared money, the account's; unknown
                # when the two statements declare different ones.
                "currency": later["currency"] if later["currency"] == earlier["currency"] else None,
                # Audit round 3, R3-B18 (R3-04): the days both cover.
                "days_shared": days_shared,
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
            # Every account the job publishes is a printout other statements print: the job is left out as a repeat is.
            first = min(entries, key=lambda entry: entry[0]["index"] or 0)
            dropped.append({"job": job, "duplicate_of": first[1]["job"].id, "reason": first[0]["reason"]})
            continue
        for statement, covering in entries:
            superseded_accounts.setdefault(job.id, {})[statement["index"]] = (covering["job"].id, statement["reason"])
    dropped_ids = {entry["job"].id for entry in dropped}
    return [job for job in kept if job.id not in dropped_ids], dropped, superseded_accounts, overlapping


def _pair_kind(statement: dict, other: dict) -> str | None:
    """Audit round 3, R3-B18 (R3-02, R3-04): whether two of `_package_superseded`'s statements are one account's, and
    on what. None for two accounts of one document (never compared). "printed" when both print a bank and four digits
    or more, the banks (`_package_bank`) and the last fours are equal and the full numbers do not conflict
    (`_numbers_conflict`): R2-B14's account, with no name or currency test, so a holder's name read two ways never
    splits it. None when both print four digits or more and the last fours differ or the numbers conflict. Otherwise
    (a statement printing no bank or fewer than four digits) "possible" when the banks agree where both print one, the
    account names do not differ where both print one and the declared currencies (`_statement_currency`) are equal
    where both declare one; else None."""
    if statement["job"] is other["job"]:
        return None
    digits, other_digits = statement["digits"], other["digits"]
    if len(digits) >= 4 and len(other_digits) >= 4:
        if digits[-4:] != other_digits[-4:] or _numbers_conflict(digits, other_digits):
            return None
        if statement["bank"] and other["bank"] and statement["bank"] == other["bank"]:
            return "printed"
    if statement["bank"] and other["bank"] and statement["bank"] != other["bank"]:
        return None
    if statement["name"] and other["name"] and statement["name"] != other["name"]:
        return None
    if statement["currency"] and other["currency"] and statement["currency"] != other["currency"]:
        return None
    return "possible"


def _possible_pair_named(earlier: dict, later: dict, first, last, count: int) -> bool:
    """Audit round 3, R3-B18 (R3-02, R3-04): whether `_package_superseded`'s overlap pass names a "possible" pair
    (`_pair_kind`) whose common days run from `first` to `last` and which shares `count` credits there
    (`_shared_credits`): more than `_OVERLAP_BOUNDARY_DAYS` days shared and either at least half the credits the
    fewer-credited side prints in those days shared, or one period printed by both with the same opening and closing
    balances. Review round 2: the long-printout phase reads a possible pair as a double count on this evidence, or
    where both statements print only rows of the printout it tests, so a second account of the holder at the bank whose
    number is not read, printing rows of its own, never reads as one beside the first."""
    fewer = min(len(_dated_credits(earlier, first, last)), len(_dated_credits(later, first, last)))
    one_period = (
        earlier["start_printed"] is not None and earlier["end_printed"] is not None
        and (earlier["start_printed"], earlier["end_printed"]) == (later["start_printed"], later["end_printed"])
        and all(_is_money_value(entry[side]) for entry in (earlier, later) for side in ("opening", "closing"))
        and all(round(float(earlier[side]) * 100) == round(float(later[side]) * 100) for side in ("opening", "closing"))
    )
    return (last - first).days + 1 > _OVERLAP_BOUNDARY_DAYS and ((count >= 1 and 2 * count >= fewer) or one_period)


def _dated_credits(statement: dict, first, last) -> list[tuple]:
    """A statement's posted credits dated from `first` to `last`: ``(day, cents, position)`` each, `position` its place
    among the statement's posted credits (`_package_superseded`)."""
    return [
        (day, _row_cents(row), position) for position, row in enumerate(statement["credits"])
        if (day := _iso_day(row.get("date"))) is not None and first <= day <= last
    ]


def _shared_credits(earlier: dict, later: dict, first, last) -> tuple[int, int]:
    """Audit round 3, R3-B18 (R3-04; MCA standard §4.6(3): match on account, date, amount and text): the credits two
    statements of one account share in the days both cover (`first` to `last`), as ``(count, cents)``. A one-to-one
    match: only the posted, dated credits of each side inside those days are read (so a recurring amount printed just
    outside them is never shared); the later statement's credits, in (day, cents, place) order, each take the untaken
    credit of the earlier with equal cents whose day is at most `_OVERLAP_SHIFT_DAYS` away (the smallest gap, then the
    earlier day, then the place). The description is not read: a transaction or value date, a pending item or another
    reference is still one credit."""
    pool = _dated_credits(earlier, first, last)
    taken: set[int] = set()
    count = cents = 0
    for day, amount, _position in sorted(_dated_credits(later, first, last)):
        best = min(
            ((abs((other_day - day).days), other_day, position) for other_day, other_amount, position in pool
             if position not in taken and other_amount == amount
             and abs((other_day - day).days) <= _OVERLAP_SHIFT_DAYS),
            default=None,
        )
        if best is not None:
            taken.add(best[2])
            count += 1
            cents += amount
    return count, cents


def _overlap_words(pair: dict, filenames: dict[str, str], money: str) -> str:
    """Audit round 2, R2-B14 (R14): a pair of overlapping statements as the package names it (app.js
    overlappingStatementWords reads the same words). Audit round 3, R3-B18 (R3-04): a pair named although it shares
    no credit (a period inside the other, or more than three common days) reads the days the two cover."""
    count = pair.get("shared_credit_count") or 0
    names = (f"{filenames.get(pair.get('job'), pair.get('job'))} and "
             f"{filenames.get(pair.get('other'), pair.get('other'))}")
    if not count:
        return f"{names} cover {pair.get('days_shared')} of the same days of one account"
    return (f"{names} share {count} {'credit' if count == 1 else 'credits'} ({money}) in the days both cover, "
            "counted in both")


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
                "filename": getattr(job, "filename", None),
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
                    "filename": getattr(job, "filename", None),
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
                    "filename": getattr(job, "filename", None),
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
                    "filename": getattr(job, "filename", None),
                    "account_index": index,
                    "account_count": count,
                    "outcome": "failed",
                    "reason": "document_omission_unratified",
                })
                continue
            if outcome != "validated":
                excluded.append({
                    "job_id": job.id,
                    "filename": getattr(job, "filename", None),
                    "account_index": index,
                    "account_count": count,
                    "outcome": outcome,
                    "reason": reason,
                })
                continue
            members.append((job, account, index, count))
    return members, excluded


#: Owner ruling 2026-10-02 (the underwriter's Q6, "2": "match a bounced deposit to its original deposit across
#: consecutive months of the same account"; audit I42; true revenue spec §6.2's package passes; R2-OW15): two statements
#: of one account are consecutive when the later one starts 0 to this many days after the earlier one ends. The
#: corpus's gaps are 0 to 3 days, or over 20 (a month missing), so any bound from 3 to 20 reads the same; 7 also spans a
#: holiday and a 28th-to-1st cycle.
PACKAGE_CONSECUTIVE_DAYS = 7

#: Owner ruling 2026-10-02 (the underwriter's Q4, "Let's go with option 2 and I'll review it anyways": "Within one deal
#: (a package), match a deposit to an exact-cents transfer OUT of another of the business's accounts 0-2 days
#: earlier"; audit I30; true revenue spec §6.2's package passes; R2-OW16): the most days a matched deposit posts after
#: the transfer out.
PACKAGE_TRANSFER_DAYS = 2
#: R2-OW16: the classes a transfer out never has (a lender's, a financing's, a card payment's, an insurer's, a tax's, a
#: payroll's or a fee's debit is no transfer between the business's accounts, whatever wording it prints).
_TRANSFER_OUT_REFUSED_CLASSES = frozenset({
    "confirmed_lender", "potential_lender", "alternative_position", "line_of_credit", "vehicle_financing", "bank_loan",
    "mortgage", "lease_or_rental", "personal_loan", "floor_plan_financing", "factoring", "debt_relief",
    "lease_or_equipment_financing", "credit_card_payment", "insurance", "tax", "payroll", "fee",
})
#: R2-OW16: the contributions a transfer out never makes (a lender, potential-lender, withholding or flagged row).
_TRANSFER_OUT_REFUSED_CONTRIBUTIONS = (
    "contributes_to_withholding_rate", "contributes_to_lender_count", "contributes_to_potential_lender_count",
    "contributes_to_flagged_totals",
)
#: R2-OW16, the destination veto: a transfer out that prints the account it goes to ('TO CHK 2020', 'TO 9999': the
#: normaliser has already dropped '*', '.' and '#' masks; an X mask may stand before the digits) never pairs with a
#: deposit into an account whose last four differ.
_TRANSFER_DESTINATION = re.compile(r"\bTO (?:CHK|CHECKING|SAV|SAVINGS|ACCT|ACCOUNT|SHARE|DDA)?\s*(?:X+\s*)?(\d{4,})\b")
#: R2-OW16: the held reasons of a deposit that names no third party (a transfer, the holder's own name, a wire with no
#: sender): such a deposit that pairs with a transfer out is annotated, display only; nothing about it moves.
_OWN_MONEY_HELD_REASONS = frozenset({
    "transfer_no_counterparty", "transfer_account_designation", "holder_name", "wire_no_sender",
})


def _bank_key(statement: object) -> str:
    """The bank a statement prints, casefolded and its blanks collapsed ('' when none): the bank an account is read
    under by R2-OW15's and R2-OW16's package passes (audit round 2, R2-B15's months read `_package_bank` since audit
    round 3, R3-B18)."""
    bank = statement.get("bank") if isinstance(statement, dict) else None
    return " ".join(str(bank or "").split()).casefold()


#: Audit round 3, R3-B18 (R3-04): an informal printout's label, read as the bank whose account it prints
#: (`_package_bank`). Chase's online transaction export publishes the label "Chase Transaction Export"
#: (analysis/chase.py:240, `bank="Chase Transaction Export"`) where its statements publish "Chase"
#: (analysis/chase.py:867, `bank="Chase"`); the export is no formal statement (analysis/parser_registry_entries.py:363,
#: `chase_export`'s `formal_statement: False`). Found's month-to-date view already prints its statement's label
#: "Lead Bank (Found)" (analysis/found_lead.py:360) and needs none.
_PACKAGE_BANK_ALIASES = {"chase transaction export": "chase"}


def _package_bank(statement: object) -> str:
    """Audit round 3, R3-B18 (R3-02, R3-04): the bank one account's statements are compared under by the package's
    shorter-printout and overlap pass (R14, `_package_superseded`) and its months (R13): `_bank_key`, an informal
    printout's label read as its bank (`_PACKAGE_BANK_ALIASES`)."""
    bank = _bank_key(statement)
    return _PACKAGE_BANK_ALIASES.get(bank, bank)


def _revenue_rows_authoritative(rows: list[dict]) -> bool:
    """Whether a member's rows (its statement's rows less R-d's internal-transfer positions) state every posted
    credit's revenue: a row carries a classification record, every positive row carries one, and every posted one a
    revenue state (§9.2, the member loop's rule)."""
    positive = [row for row in rows if _num(row.get("amount")) > 0]
    classified = [row for row in positive if isinstance(row.get("classification"), dict)]
    return (
        any(isinstance(row.get("classification"), dict) for row in rows)
        and len(classified) == len(positive)
        and all(row["classification"].get("is_posted") is False
                or row["classification"].get("revenue_classification") in REVENUE_STATES for row in classified)
    )


def _member_tiered(rows: list[dict]) -> bool:
    """R2-OW15: whether a member's rows are tiered (§9.2, §10.4): its revenue rows are authoritative and every posted
    credit carries a 5.6 tier. The package passes (`_package_matches`) and the member loop read this one helper, so a
    member the passes overlay is never one the loop publishes without its tier figures."""
    if not _revenue_rows_authoritative(rows):
        return False
    return all(
        isinstance(row["classification"].get("revenue_tier"), str)
        for row in rows
        if _num(row.get("amount")) > 0 and isinstance(row.get("classification"), dict)
        and row["classification"].get("is_posted") is not False
    )


def _consecutive(earlier: dict, later: dict) -> bool:
    """R2-OW15: `later` is the statement that follows `earlier`: both period days read, and `later` starts 0 to
    PACKAGE_CONSECUTIVE_DAYS days after `earlier` ends. Two overlapping statements (R2-B14's R14) never are."""
    if earlier["end"] is None or later["start"] is None:
        return False
    return 0 <= (later["start"] - earlier["end"]).days <= PACKAGE_CONSECUTIVE_DAYS


def _chained(earlier: dict, later: dict) -> bool:
    """R2-OW15: `later` follows `earlier` (_consecutive) and opens on its closing balance, to the cent."""
    return (
        _consecutive(earlier, later) and _is_money_value(earlier["closing"]) and _is_money_value(later["opening"])
        and round(float(earlier["closing"]) * 100) == round(float(later["opening"]) * 100)
    )


def _same_account(first: dict, second: dict) -> bool:
    """R2-OW15 (Q6's identity): two package members are statements of ONE account: two jobs, one declared currency
    and one printed bank (`_bank_key`), and either both print four digits or more, with an equal last four and no
    conflict (R2-B14's `_numbers_conflict`), or one prints fewer: then the account names do not differ where both
    print one, and the balance chains (one follows the other and opens on its closing balance, `_chained`). A member
    with no declared currency is never one."""
    if first["job_id"] == second["job_id"] or not first["currency"] or first["currency"] != second["currency"]:
        return False
    if not first["bank"] or first["bank"] != second["bank"]:
        return False
    if len(first["digits"]) >= 4 and len(second["digits"]) >= 4:
        return first["digits"][-4:] == second["digits"][-4:] and not _numbers_conflict(first["digits"],
                                                                                        second["digits"])
    if first["name"] and second["name"] and first["name"] != second["name"]:
        return False
    return _chained(first, second) or _chained(second, first)


def _months_linked(first: dict, second: dict) -> bool:
    """Audit round 3, R3-B18 (R3-02; the owner's Q6 identity of 2026-10-02, "consecutive months of the same account"):
    two counted members are statements of one account for the months' floor (R13). Never two accounts of one document
    (one job). Two keyed members (each a bank, `_package_bank`, and four digits or more) are one account when the bank
    and the last four are equal, chained or not (audit round 2, R2-B15's key, kept exactly). Otherwise the banks agree
    where both print one, the account names do not differ where both print one, and the balance chains (R2-OW15's
    `_chained`, unchanged: one starts 0 to PACKAGE_CONSECUTIVE_DAYS days after the other ends and opens on its closing
    balance, to the cent). A member linked to none is its own account."""
    if first["job_id"] == second["job_id"]:
        return False
    if first["bank"] and second["bank"] and len(first["digits"]) >= 4 and len(second["digits"]) >= 4:
        return first["bank"] == second["bank"] and first["digits"][-4:] == second["digits"][-4:]
    if first["bank"] and second["bank"] and first["bank"] != second["bank"]:
        return False
    if first["name"] and second["name"] and first["name"] != second["name"]:
        return False
    return _chained(first, second) or _chained(second, first)


def _different_accounts(first: dict, second: dict) -> bool:
    """R2-OW16 (Q4's identity): two package members are two of the business's accounts: two members (two jobs, or one
    document's two accounts), one declared currency, both print four digits or more, and the last fours differ or the
    full numbers conflict (R2-B14's `_numbers_conflict`). There is no bank-name arm: one account read under two bank
    spellings is never two accounts, and a member that prints fewer than four digits is never paired (it is marked
    `no_account_number`)."""
    if first["key"] == second["key"] or not first["currency"] or first["currency"] != second["currency"]:
        return False
    if len(first["digits"]) < 4 or len(second["digits"]) < 4:
        return False
    return first["digits"][-4:] != second["digits"][-4:] or _numbers_conflict(first["digits"], second["digits"])


def _match_side(entry: dict, position: int, row: dict) -> dict:
    """R2-OW15: one leg of a package match as its row note and the package's `package_matches` name it. The account is
    `account_index` (1-based, None for a statement of one account), never `account`: the served payload masks every
    key named `account` as a printed account number (`_masked`)."""
    record = row["classification"]
    digits = entry["digits"]
    return {
        "job": entry["job_id"], "filename": entry["filename"], "account_index": entry["account"],
        "source_location": record.get("source_location") or f"transaction:{position + 1}",
        "date": row.get("date"), "amount": row.get("amount"), "bank": entry["bank_printed"],
        "last4": digits[-4:] if len(digits) >= 4 else None,
    }


def _package_matches(members: list[tuple], rd_positions: dict[tuple, set[int]]) -> dict:
    """Owner ruling 2026-10-02 (the underwriter's Q6, "2": "Match a bounced deposit to its original deposit across
    consecutive months of the same account (within a package, and within one statement as today), and count a
    redeposited check once. Flag, but do not deduct, returns that cannot be matched and processor chargebacks"; audit
    I42; true revenue spec §6.2's package passes, §9.2, §11; R2-OW15): the package passes over the members
    `_package_members` admitted, recomputed on every call from their displayed copies and never written back (no job,
    stored analysis, review row or package record changes; a statement viewed alone keeps its own figures).

    `rd_positions` holds each member's R-d internal-transfer positions (`_internal_transfer_positions`), which no pass
    reads. A member enters the passes when its job is done, its rows are tiered (`_member_tiered`, the member loop's
    test) and it declares a currency; in a package of two members or more, a member that does not is marked
    (`unchecked`: 'no_currency', else 'older_rules'), unless it prints no row (nothing to match), and a member that
    enters but prints fewer than four account digits is marked 'no_account_number' (R2-OW16: pass 2 never pairs it;
    pass 1 still reaches it through the balance chain). A row enters when it is posted and no proven duplicate.

    Pass 1, returned deposits across statements: a debit that undoes a deposit (`_deposit_return_debit`, R2-B08's
    wordings included) that no credit of its statement pairs (pass 4's `matched_reversal_pair` naming its location)
    and that is no correction naming an equal credit of its own statement (pass 4's `_undo_debit_names_a_credit`, run
    unchanged over the member's rows; such a debit stays flagged, never netted across) is matched to its original
    deposit in the SAME account's IMMEDIATELY PRECEDING statement (`_same_account` and `_consecutive`): an equal-cents
    deposit-channel credit (`_deposit_channel_credit`) dated on or before it, with no day cap inside that statement,
    whose tier is not `non_revenue`, which pass 4 did not pair, which carries no analyst decision (an analyst's Confirm
    or Mark beats the pass) and which no other debit took. The debits are read in (date, member, position) order, the
    members in their canonical order (period start, job, account), and each takes the NEAREST candidate (the latest
    credit day, then the canonical member, then the position). The original leaves True as non-revenue (`overlays`:
    method `matched_reversal_pair`, rule `returned_deposit_cross_statement`, `package_match` naming the return); its
    initial state, review status and pass-4 link are kept, so Confirm Revenue still overrides the match. A redeposit
    after the return stays counted. Inside one statement nothing changes (pass 4 keeps its 14 days).

    Pass 2, own-account transfers (owner ruling 2026-10-02, the underwriter's Q4, "Let's go with option 2 and I'll
    review it anyways"; audit I30; R2-OW16): a counted deposit that prints no payer (tier `counted_flagged`, reason
    exactly `no_payer_printed`; never a rail, a round sum (`is_round_sum`), a check or cash-device deposit
    (`paper_or_cash_deposit`), a decided credit or one pass 1 took) is matched to an exact-cents transfer out of
    ANOTHER of the business's accounts (`_different_accounts`: another uploaded statement, or another account of the
    same document after R-d) dated 0 to PACKAGE_TRANSFER_DAYS days before it. A transfer out is a posted, dated debit
    printing transfer wording (`_TRANSFER_WORDING`), no rail, no lender, potential-lender, withholding or flagged
    contribution, none of the financing, card-payment, insurance, tax, payroll or fee classes, and no pass-1 note; one
    that prints the account it goes to (`_TRANSFER_DESTINATION`) never pairs with a deposit into an account whose last
    four differ. One to one: the credits in (date, member, position) order, each taking the nearest untaken debit
    (the smallest gap, then the member and the position). The deposit is held (`overlays`: tier
    `excluded_pending_review`, reason `own_account_transfer_matched`, `package_match` naming the transfer, its state
    `unverified_deposit` and its pending status kept, so Confirm Revenue releases it into True and marks it Verified);
    the debit gains a display note. Then each held deposit that names no third party (`_OWN_MONEY_HELD_REASONS`) and
    passes the same deposit tests is tried against the debits still untaken by the same rule, one to one: it gains a
    display note only (`moved` false), its tier, reason, flags, totals and gate unchanged. Pass 2 never sets an
    internal-transfer mark and never removes a row from gross deposits.

    Pass 3, the debit flags (`debit_side_flags`, never deducted, never a gate term): every ready member's returns that
    neither its statement nor pass 1 matched (`unmatched_deposit_return`, with `candidate_decided` when the nearest
    candidate but for the decision carries one) and its processor chargebacks and adjustments (`processor_chargeback`).

    Returns `{"overlays": {member: {position: fields}}, "matches": [...], "debit_flags": [...], "unchecked": {member:
    marker}, "moved": {member: [{"tier", "state", "amount"}]}}`, deterministic and independent of the listing order."""
    from types import SimpleNamespace

    entries: list[dict] = []
    for job, analysis, account_index, _count in members:
        statement = analysis.get("statement") if isinstance(analysis, dict) else None
        if not (job.status == "done" and job.analysis is not None and isinstance(statement, dict)):
            continue
        raw = statement.get("transactions") if isinstance(statement.get("transactions"), list) else []
        excluded = rd_positions.get((job.id, account_index)) or set()
        kept = [row if isinstance(row, dict) and position not in excluded else None for position, row in enumerate(raw)]
        entries.append({
            "key": (job.id, account_index), "job_id": job.id, "filename": getattr(job, "filename", None),
            "account": account_index,
            "order": (str(statement.get("period_start") or ""), str(job.id), account_index or 0),
            "currency": _statement_currency(analysis), "bank": _bank_key(statement), "bank_printed": statement.get("bank"),
            "digits": _printed_account_digits(analysis),
            "name": " ".join(str(statement.get("account_name") or "").split()).casefold(),
            "start": _iso_day(statement.get("period_start")), "end": _iso_day(statement.get("period_end")),
            "opening": statement.get("beginning_balance"), "closing": statement.get("ending_balance"),
            "raw": raw, "kept": kept,
            "rows": [(position, row) for position, row in enumerate(kept)
                     if row is not None and isinstance(row.get("classification"), dict)
                     and row["classification"].get("is_posted") is not False
                     and not row["classification"].get("duplicate_of")],
            "tiered": _member_tiered([row for row in kept if row is not None]),
        })
    entries.sort(key=lambda entry: entry["order"])
    unchecked: dict[tuple, str] = {}
    if len(members) >= 2:
        for entry in entries:
            if not any(row is not None for row in entry["kept"]):
                continue  # a statement that prints no row has nothing to match, and is never marked
            if entry["currency"] is None:
                unchecked[entry["key"]] = "no_currency"
            elif not entry["tiered"]:
                unchecked[entry["key"]] = "older_rules"
            elif len(entry["digits"]) < 4:
                unchecked[entry["key"]] = "no_account_number"  # R2-OW16: pass 2 never pairs it
    matchable = [entry for entry in entries if entry["currency"] is not None and entry["tiered"]]

    def text_of(row: dict) -> str:
        return str(row["classification"].get("normalized_description") or "")

    def location_of(row: dict, position: int) -> str:
        return row["classification"].get("source_location") or f"transaction:{position + 1}"

    # Pass 1's return debits, each with whether pass 4's correction guard keeps it back.
    returns: list[tuple] = []
    for entry in matchable:
        paired = {
            row["classification"].get("revenue_related_transaction") for _position, row in entry["rows"]
            if _num(row.get("amount")) > 0 and row["classification"].get("revenue_match_method") == "matched_reversal_pair"
        }
        records = duplicates = None
        for position, row in entry["rows"]:
            if _num(row.get("amount")) >= 0 or not _deposit_return_debit(text_of(row)):
                continue
            location = location_of(row, position)
            if location in paired:
                continue
            if records is None:
                # Pass 4's guard over the member's every row, wrapped as the records it reads, with its duplicates.
                records = [
                    SimpleNamespace(
                        amount=_num(row_.get("amount")),
                        is_posted=row_["classification"].get("is_posted") is not False,
                        date=row_["classification"].get("date") or row_.get("date") or "",
                        normalized_description=str(row_["classification"].get("normalized_description") or ""),
                    ) if isinstance(row_, dict) and isinstance(row_.get("classification"), dict)
                    else SimpleNamespace(amount=0.0, is_posted=False, date="", normalized_description="")
                    for row_ in entry["raw"]
                ]
                duplicates = {
                    position_ for position_, row_ in enumerate(entry["raw"])
                    if isinstance(row_, dict) and isinstance(row_.get("classification"), dict)
                    and row_["classification"].get("duplicate_of")
                }
            day = _iso_day(row.get("date"))
            guarded = _undo_debit_names_a_credit(records, duplicates, position)
            returns.append(((day is None, day.toordinal() if day else 0, entry["order"], position),
                            entry, position, row, location, day, guarded))

    overlays: dict[tuple, dict[int, dict]] = {}
    matches: list[dict] = []
    moved: dict[tuple, list[dict]] = {}
    matched_locations: dict[tuple, set[str]] = {}
    decided_candidates: dict[tuple, dict] = {}
    taken: set[tuple] = set()
    for _sort, debit_entry, position, row, location, debit_day, guarded in sorted(returns, key=lambda item: item[0]):
        if guarded or debit_day is None:
            continue
        cents = -_row_cents(row)
        best = best_any = None
        for credit_entry in matchable:
            if not (_same_account(credit_entry, debit_entry) and _consecutive(credit_entry, debit_entry)):
                continue
            for credit_position, credit_row in credit_entry["rows"]:
                record = credit_row["classification"]
                if _row_cents(credit_row) != cents or (credit_entry["key"], credit_position) in taken:
                    continue
                credit_day = _iso_day(credit_row.get("date"))
                if (credit_day is None or credit_day > debit_day or record.get("revenue_tier") == "non_revenue"
                        or record.get("revenue_match_method") == "matched_reversal_pair"
                        or not _deposit_channel_credit(text_of(credit_row))):
                    continue
                candidate = ((-credit_day.toordinal(), credit_entry["order"], credit_position),
                             credit_entry, credit_position, credit_row, credit_day)
                if best_any is None or candidate[0] < best_any[0]:
                    best_any = candidate
                if record.get("revenue_review_status") not in _REVIEW_DECISIONS and (
                        best is None or candidate[0] < best[0]):
                    best = candidate
        if best is None:
            if best_any is not None:
                decided = best_any[3]["classification"]
                decided_candidates[(debit_entry["key"], location)] = {
                    "job": best_any[1]["job_id"], "filename": best_any[1]["filename"],
                    "account_index": best_any[1]["account"],
                    "source_location": location_of(best_any[3], best_any[2]), "date": best_any[3].get("date"),
                    "decision": decided.get("revenue_review_status"),
                }
            continue
        _rank, credit_entry, credit_position, credit_row, credit_day = best
        record = credit_row["classification"]
        taken.add((credit_entry["key"], credit_position))
        gap = (debit_day - credit_day).days
        credit_side = _match_side(credit_entry, credit_position, credit_row)
        debit_side = _match_side(debit_entry, position, row)
        tier_before, reason_before = record.get("revenue_tier"), record.get("revenue_tier_reason")
        overlays.setdefault(credit_entry["key"], {})[credit_position] = {
            "revenue_classification": "non_revenue",
            "revenue_tier": "non_revenue",
            "revenue_tier_reason": None,
            "revenue_match_method": "matched_reversal_pair",
            "revenue_matched_rule": "returned_deposit_cross_statement",
            "revenue_review_required": False,
            **revenue_contribution_flags("non_revenue", "non_revenue"),
            "package_match": {"kind": "returned_deposit", "moved": True, "debit": debit_side, "gap_days": gap,
                              "tier_before": tier_before, "reason_before": reason_before},
        }
        overlays.setdefault(debit_entry["key"], {})[position] = {
            "package_match": {"kind": "returned_deposit", "credit": credit_side},
        }
        moved.setdefault(credit_entry["key"], []).append({
            "tier": tier_before, "state": record.get("revenue_classification"),
            "amount": round(_num(credit_row.get("amount")), 2),
        })
        matched_locations.setdefault(debit_entry["key"], set()).add(location)
        matches.append({
            "kind": "returned_deposit", "moved": True,
            "credit": {**credit_side, "currency": credit_entry["currency"], "tier_before": tier_before,
                       "reason_before": reason_before},
            "debit": {**debit_side, "currency": debit_entry["currency"]},
            "gap_days": gap,
        })

    # Pass 2 (R2-OW16, the underwriter's Q4): own-account transfers, then the held deposits' display notes.
    noted = {(key, position) for key, rows in overlays.items() for position in rows}  # pass 1's rows

    def rails(text: str) -> bool:
        return bool(_CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text))

    transfers_out: list[tuple] = []
    for entry in matchable:
        if len(entry["digits"]) < 4:
            continue  # `_different_accounts` never pairs it (marked 'no_account_number')
        for position, row in entry["rows"]:
            record = row["classification"]
            day = _iso_day(row.get("date"))
            text = text_of(row)
            if (_num(row.get("amount")) >= 0 or day is None or (entry["key"], position) in noted
                    or not _TRANSFER_WORDING.search(text) or rails(text)
                    or any(record.get(flag) is True for flag in _TRANSFER_OUT_REFUSED_CONTRIBUTIONS)
                    or record.get("classification") in _TRANSFER_OUT_REFUSED_CLASSES):
                continue
            destination = _TRANSFER_DESTINATION.search(text)
            transfers_out.append((entry, position, row, day, destination.group(1)[-4:] if destination else None))

    def deposits_in(held: bool) -> list[tuple]:
        found = []
        for entry in matchable:
            if len(entry["digits"]) < 4:
                continue
            for position, row in entry["rows"]:
                record = row["classification"]
                day = _iso_day(row.get("date"))
                text = text_of(row)
                if held:
                    eligible = (record.get("revenue_tier") == "excluded_pending_review"
                                and record.get("revenue_tier_reason") in _OWN_MONEY_HELD_REASONS)
                else:
                    eligible = (record.get("revenue_tier") == "counted_flagged"
                                and record.get("revenue_tier_reason") == "no_payer_printed")
                # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): nor a Zelle deposit, which the
                # counted reading may hold as the holder's own name: PNC's 'ZEL FROM' escapes the consumer rail, and Q4
                # (2026-10-02) never matches P2P (true_revenue.zelle_deposit).
                if (not eligible or _num(row.get("amount")) <= 0 or day is None
                        or (entry["key"], position) in taken or (entry["key"], position) in noted
                        or record.get("revenue_review_status") in _REVIEW_DECISIONS
                        or rails(text) or zelle_deposit(text)
                        or is_round_sum(_num(row.get("amount"))) or paper_or_cash_deposit(text)):
                    continue
                found.append(((day.toordinal(), entry["order"], position), entry, position, row, day))
        return sorted(found, key=lambda item: item[0])

    transfers_taken: set[tuple] = set()
    for held in (False, True):
        for _sort, credit_entry, credit_position, credit_row, credit_day in deposits_in(held):
            cents = _row_cents(credit_row)
            best = None
            for debit_entry, position, row, debit_day, destination in transfers_out:
                if ((debit_entry["key"], position) in transfers_taken or -_row_cents(row) != cents
                        or not _different_accounts(credit_entry, debit_entry)):
                    continue
                gap = (credit_day - debit_day).days
                if not 0 <= gap <= PACKAGE_TRANSFER_DAYS:
                    continue
                if destination is not None and destination != credit_entry["digits"][-4:]:
                    continue  # the destination veto: it went to another account
                candidate = ((gap, debit_entry["order"], position), debit_entry, position, row, gap)
                if best is None or candidate[0] < best[0]:
                    best = candidate
            if best is None:
                continue
            _rank, debit_entry, position, row, gap = best
            transfers_taken.add((debit_entry["key"], position))
            taken.add((credit_entry["key"], credit_position))
            record = credit_row["classification"]
            credit_side = _match_side(credit_entry, credit_position, credit_row)
            debit_side = _match_side(debit_entry, position, row)
            tier_before, reason_before = record.get("revenue_tier"), record.get("revenue_tier_reason")
            note = {"kind": "own_account_transfer", "moved": not held, "debit": debit_side, "gap_days": gap,
                    "tier_before": tier_before, "reason_before": reason_before}
            if held:
                overlays.setdefault(credit_entry["key"], {})[credit_position] = {"package_match": note}
            else:
                overlays.setdefault(credit_entry["key"], {})[credit_position] = {
                    "revenue_classification": "unverified_deposit",
                    "revenue_tier": "excluded_pending_review",
                    "revenue_tier_reason": "own_account_transfer_matched",
                    "revenue_review_required": True,
                    **revenue_contribution_flags("unverified_deposit", "excluded_pending_review"),
                    "package_match": note,
                }
                moved.setdefault(credit_entry["key"], []).append({
                    "tier": tier_before, "state": record.get("revenue_classification"),
                    "amount": round(_num(credit_row.get("amount")), 2),
                })
            overlays.setdefault(debit_entry["key"], {})[position] = {
                "package_match": {"kind": "own_account_transfer", "credit": credit_side, "moved": not held},
            }
            matches.append({
                "kind": "own_account_transfer", "moved": not held,
                "credit": {**credit_side, "currency": credit_entry["currency"], "tier_before": tier_before,
                           "reason_before": reason_before},
                "debit": {**debit_side, "currency": debit_entry["currency"]},
                "gap_days": gap,
            })

    # Pass 3: every ready member's debit flags, its R-d positions left out (their places kept, so a location reads).
    debit_flags: list[dict] = []
    for entry in entries:
        for flag in debit_side_flags(entry["kept"], matched_locations=matched_locations.get(entry["key"], set())):
            decided = (decided_candidates.get((entry["key"], flag["source_location"]))
                       if flag["kind"] == "unmatched_deposit_return" else None)
            debit_flags.append({
                "kind": flag["kind"],
                **({"wording": flag["wording"]} if "wording" in flag else {}),
                **({"candidate_decided": decided} if decided else {}),
                "source_job": entry["job_id"], "source_document": entry["filename"], "source_account": entry["account"],
                "source_currency": entry["currency"], "source_location": flag["source_location"],
                "date": flag["date"], "amount": flag["amount"], "description": flag["description"],
            })

    # Pass 4 (the final review of round 2, F2(b); the owner's ruling of 2026-10-02 on the underwriter's Q5 across
    # statements): a bounce-worded return whose funder payment sits in the same account's preceding statement.
    _returned_funder_payments_across(matchable, overlays, matches, location_of, text_of)
    # Pass 4's re-debits (the owner's answer of 2026-10-07 to audit round 3's R3-73, "Count it once"; R3-B02): a
    # returned payment the same funder re-debits in the account's next statement leaves the package's numerator.
    represented = _represented_funder_payments_across(matchable, overlays, location_of)
    return {"overlays": overlays, "matches": matches, "debit_flags": debit_flags, "unchecked": unchecked,
            "moved": moved, "represented": represented}


def _represented_funder_payments_across(matchable: list[dict], overlays: dict, location_of) -> dict:
    """The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once (Recommended)"; true revenue spec §6.2's
    package passes, §9.2, §11; R3-B02): R2-OW13's rule across a member boundary. A returned funder payment still in the
    withholding numerator (a member's own, rule D's or the named pair's, or one pass 4 matched to a return in the next
    statement) whose same funder re-debits it in ANOTHER member, the statement of its return or the one immediately
    after it in the same account (`_same_account`, `_consecutive`), leaves the package's numerator, by the classifier's
    rule (analysis.represented_payments.re_debits: the same cents off its cycle, or an exact 2x catch-up, dated on or
    after the return and within one cadence gap after it; the series read over those members, the re-debits a statement
    already took left out, and its recurring-phase guard reading every dated return of those members, a re-debited one
    included: review round 2 of R3-B02). The payment's package copy gains `contributes_to_withholding_rate` false and
    `represented_by` (the re-debit's location in its statement); paid to lenders, the lender count, the funder rollups
    and revenue never move, and each statement viewed alone keeps its own figures. Returns {(member key, the payment's
    location): the warning item's represented fields (`represented_date`, `_location`, `_kind`, `_job`, `_document`, and
    `_account` for a statement of several accounts)}."""
    from analysis.lender_payment_changes import calendar_for
    from analysis.represented_payments import Attempt, Returned, re_debits

    def record_of(entry: dict, position: int, row: dict) -> dict:
        overlay = (overlays.get(entry["key"]) or {}).get(position)
        return {**row["classification"], **overlay} if overlay else row["classification"]

    following: dict[tuple, dict] = {}
    for entry in matchable:
        for later in matchable:
            if later is not entry and _same_account(entry, later) and _consecutive(entry, later):
                following.setdefault(entry["key"], later)
                break
    by_member: dict[tuple, list] = {}
    known: dict[tuple, list] = {}
    used: set[tuple] = set()
    returns: list[tuple] = []
    for entry in matchable:
        rows_at = {location_of(row, position): (position, row) for position, row in entry["rows"]}
        for position, row in entry["rows"]:
            record = record_of(entry, position, row)
            day = _iso_day(row.get("date"))
            if (_num(row.get("amount")) >= 0 or day is None or record.get("classification") != "confirmed_lender"
                    or not record.get("canonical_entity")):
                continue
            if not (record.get("contributes_to_lender_totals") is True or record.get("returned_funder_payment_by")):
                continue
            attempt = Attempt((entry["key"], position), record["canonical_entity"], day, abs(_row_cents(row)),
                              (day.toordinal(), entry["order"], position))
            by_member.setdefault(entry["key"], []).append(attempt)
            taken = rows_at.get(record.get("represented_by") or "")
            if taken is not None:
                used.add((entry["key"], taken[0]))  # a re-debit its own statement already took
            if not record.get("returned_funder_payment_by"):
                continue
            match = record.get("package_match") or {}
            if match.get("kind") == "returned_funder_payment" and isinstance(match.get("credit"), dict):
                credit = match["credit"]
                credit_entry = next((other for other in matchable if other["job_id"] == credit.get("job")
                                     and other["account"] == credit.get("account_index")), None)
                credit_day = _iso_day(credit.get("date"))
            else:
                found = rows_at.get(record["returned_funder_payment_by"])
                credit_entry = entry if found is not None else None
                credit_day = _iso_day(found[1].get("date")) if found is not None else None
            if credit_day is None:
                continue
            # Every dated return, a re-debited one included, for the rule's recurring-phase guard (review round 2).
            known.setdefault(entry["key"], []).append(Returned(attempt, credit_day))
            if (credit_entry is not None and not record.get("represented_by")
                    and record.get("contributes_to_withholding_rate") is True):
                returns.append(((credit_day.toordinal(), entry["order"], position), entry, position, row, attempt,
                                credit_entry, credit_day))
    represented: dict = {}
    for _sort, entry, position, row, attempt, credit_entry, credit_day in sorted(returns, key=lambda item: item[0]):
        members = [credit_entry] + ([following[credit_entry["key"]]] if credit_entry["key"] in following else [])
        allowed = {member["key"] for member in members if member is not entry}
        if not allowed:
            continue
        series = [candidate for key in {entry["key"], *allowed} for candidate in by_member.get(key, [])]
        found = re_debits([Returned(attempt, credit_day)], series, calendar_for(entry["currency"]),
                          may_re_debit=lambda _returned, candidate: candidate.key[0] in allowed, taken=list(used),
                          returns=[known_return for key in {entry["key"], *allowed}
                                   for known_return in known.get(key, [])])
        if attempt.key not in found:
            continue
        (re_debit_key, kind) = found[attempt.key]
        used.add(re_debit_key)
        re_debit_entry = next(member for member in members if member["key"] == re_debit_key[0])
        re_debit_row = dict(re_debit_entry["rows"])[re_debit_key[1]]
        re_debit_location = location_of(re_debit_row, re_debit_key[1])
        overlays.setdefault(entry["key"], {}).setdefault(position, {}).update({
            "contributes_to_withholding_rate": False, "represented_by": re_debit_location,
        })
        represented[(entry["key"], location_of(row, position))] = {
            "represented_date": re_debit_row.get("date"), "represented_location": re_debit_location,
            "represented_kind": kind, "represented_job": re_debit_entry["job_id"],
            "represented_document": re_debit_entry["filename"],
            **({"represented_account": re_debit_entry["account"]} if re_debit_entry["account"] is not None else {}),
        }
    return represented


def _paid_funder_payment(record: dict) -> bool:
    """F2(b) (final review of round 2): a served row's record is a confirmed funder's posted payment counted as paid to
    lenders that no pair reversed and no return took (rule D's funder debits, `_is_paid_funder_debit`, on a dict)."""
    return (
        record.get("classification") == "confirmed_lender"
        and record.get("contributes_to_lender_totals") is True
        and record.get("is_posted") is not False
        and not record.get("reversed_by")
        and not record.get("returned_funder_payment_by")
    )


def _returned_funder_payments_across(matchable: list[dict], overlays: dict, matches: list, location_of, text_of) -> None:
    """The final review of round 2, F2(b) (true revenue spec §6.2's package passes, §9.2, §11; the owner's ruling of
    2026-10-02 on the underwriter's Q5, "Match the return to the funder payment it reverses"; R2-OW13's rule D across
    statements): the package's pass 4, over the members pass 1 reads (`matchable`), after passes 1 to 3, adding to their
    `overlays` and `matches` in place.

    A return is a member's posted, non-duplicate credit that rule D could read (a bounce form, `_returned_payment_credit`;
    out of True, `_RETURN_CREDIT_TIERS`; no lender credit, except one that names the confirmed funder whose payment it
    returns: D1 reads the funder's name on its own return, the named pair's case, which a statement pairs on its own
    but no statement can across two) that its statement left unpaired (no `returns_funder_payment`,
    no pair's `reversed_by` naming it, no earlier pass's note) and that is dated; a credit the revenue side paired with a
    debit of its own statement dated on or before it is left alone (rule D's partner guard: the statement's own pair
    stands), while a partner dated after it cannot be the payment it returns (F2(a)) and holds nothing back. Two of
    these are departures from rule D, which the fix run's review round 1 named for ratification (spec §20): rule D
    never reads a lender credit, and it leaves alone any credit the revenue side paired that is not its own payment's
    partner, whatever the partner's date. Its payment
    is sought in the SAME account's IMMEDIATELY PRECEDING statement (`_same_account` and `_consecutive`): a confirmed
    funder's paid payment (`_paid_funder_payment`) of equal cents dated 0 to RETURNED_FUNDER_PAYMENT_WINDOW_DAYS days
    before it, that funder's only where the return names a confirmed funder (`match_known_payee`). Rule D's choice: the
    payment on the RECEIVED ON day the return prints first, then the latest, then the canonical member and the later
    row; and its
    guard: the return is left alone when an equal posted debit that is no confirmed lender's lies in the window, in
    either statement, as near as the chosen payment. The returns are read in (date, member, position) order; each
    payment is taken once.

    The payment's copy leaves the package's paid to lenders (`contributes_to_lender_totals` and, as rule D does,
    `contributes_to_flagged_totals` false; `returned_funder_payment_by` the return's location), keeping its withholding
    and its lender count; both legs carry `package_match` `{kind: "returned_funder_payment", ...}` (the payment's names
    the return, the return's the payment and its funder), and `matches` gains the pair. R2-OW18's package payment
    changes read the payment's copy as a returned attempt (`_package_lender_payment_changes`). Revenue never moves;
    each statement viewed alone keeps its own figures."""
    noted = {(key, position) for key, rows in overlays.items() for position in rows}
    taken: set[tuple] = set()
    returns: list[tuple] = []
    for entry in matchable:
        rows_by_location = {location_of(row, position): row for position, row in entry["rows"]}
        named_pairs = {row["classification"].get("reversed_by") for _position, row in entry["rows"]
                       if row["classification"].get("reversed_by")}
        for position, row in entry["rows"]:
            record = row["classification"]
            day = _iso_day(row.get("date"))
            if (_num(row.get("amount")) <= 0 or day is None or (entry["key"], position) in noted
                    or record.get("returns_funder_payment") or location_of(row, position) in named_pairs
                    or record.get("revenue_tier") not in _RETURN_CREDIT_TIERS
                    or not _returned_payment_credit(text_of(row))):
                continue
            named = match_known_payee(text_of(row), credit=True)
            funder = named.entity if named is not None and named.state == "confirmed_lender" else None
            if record.get("contributes_to_lender_credit_exclusion") is True and funder is None:
                continue  # a lender credit is read only where it names the confirmed funder (the named pair's case)
            if record.get("revenue_match_method") == "matched_reversal_pair":
                partner = rows_by_location.get(record.get("revenue_related_transaction"))
                partner_day = _iso_day(partner.get("date")) if isinstance(partner, dict) else None
                if partner_day is None or partner_day <= day:
                    continue
            returns.append(((day.toordinal(), entry["order"], position), entry, position, row, day, funder))
    for _sort, credit_entry, credit_position, credit_row, credit_day, funder in sorted(returns, key=lambda item: item[0]):
        text = text_of(credit_row)
        cents = _row_cents(credit_row)
        received = _received_on_day(text)
        best = None
        guards: list[int] = []
        for debit_entry in matchable:
            preceding = _same_account(debit_entry, credit_entry) and _consecutive(debit_entry, credit_entry)
            if not (preceding or debit_entry is credit_entry):
                continue
            for position, row in debit_entry["rows"]:
                record = row["classification"]
                day = _iso_day(row.get("date"))
                if -_row_cents(row) != cents or day is None:
                    continue
                gap = (credit_day - day).days
                if not 0 <= gap <= RETURNED_FUNDER_PAYMENT_WINDOW_DAYS:
                    continue
                if record.get("classification") != "confirmed_lender":
                    guards.append(gap)  # rule D's guard debits, in either statement
                    continue
                if (not preceding or (debit_entry["key"], position) in taken or (debit_entry["key"], position) in noted
                        or not _paid_funder_payment(record)
                        or (funder is not None and record.get("canonical_entity") != funder)):
                    continue
                on_received = received is not None and (day.month, day.day) == received
                rank = (0 if on_received else 1, -day.toordinal(), debit_entry["order"], -position)
                candidate = (rank, debit_entry, position, row, gap)
                if best is None or candidate[0] < best[0]:
                    best = candidate
        if best is None:
            continue
        _rank, debit_entry, position, row, gap = best
        if any(guard <= gap for guard in guards):
            continue
        taken.add((debit_entry["key"], position))
        record = row["classification"]
        credit_side = _match_side(credit_entry, credit_position, credit_row)
        debit_side = {**_match_side(debit_entry, position, row), "funder": record.get("canonical_entity")}
        overlays.setdefault(debit_entry["key"], {})[position] = {
            "contributes_to_lender_totals": False,
            "contributes_to_flagged_totals": False,
            "returned_funder_payment_by": credit_side["source_location"],
            "package_match": {"kind": "returned_funder_payment", "credit": credit_side},
            # Audit round 3, R3-B03 (R3-79): a returned payoff attempt rejoins the rate and is no lump sum, as Q5 rules
            # inside a statement (`_returned_payoff_in_rate`).
            **({"contributes_to_withholding_rate": True, "lump_sum_payoff": None}
               if record.get("lump_sum_payoff") else {}),
        }
        overlays.setdefault(credit_entry["key"], {})[credit_position] = {
            "package_match": {"kind": "returned_funder_payment", "debit": debit_side},
        }
        matches.append({
            "kind": "returned_funder_payment", "moved": True,
            "credit": {**credit_side, "currency": credit_entry["currency"], "description": credit_row.get("description")},
            "debit": {**debit_side, "currency": debit_entry["currency"]},
            "gap_days": gap,
        })


def _package_match_totals(matched: dict) -> dict:
    """R2-OW15 (§9.2): the package passes' totals, each count and total only where a pass found a row:
    `returned_deposit_cross_statement_count` / `_total` (the deposits pass 1 took out of True), R2-OW16's
    `own_account_transfer_held_count` / `_total` (the deposits pass 2 held) and
    `own_account_transfer_already_held_count` / `_total` (the held deposits it annotated), the debit flags'
    `<kind>_count` / `<kind>_total` (their magnitude) and `package_match_unchecked_count`."""
    totals: dict = {}
    returned = [match for match in matched["matches"] if match["kind"] == "returned_deposit" and match["moved"]]
    if returned:
        totals["returned_deposit_cross_statement_count"] = len(returned)
        totals["returned_deposit_cross_statement_total"] = round(
            sum(abs(_num(match["credit"]["amount"])) for match in returned), 2)
    # R2-OW16 (the underwriter's Q4): the deposits pass 2 held, and the already-held deposits it only annotated.
    for key, moved in (("own_account_transfer_held", True), ("own_account_transfer_already_held", False)):
        transfers = [match for match in matched["matches"]
                     if match["kind"] == "own_account_transfer" and match["moved"] is moved]
        if transfers:
            totals[f"{key}_count"] = len(transfers)
            totals[f"{key}_total"] = round(sum(abs(_num(match["credit"]["amount"])) for match in transfers), 2)
    for kind in DEBIT_FLAG_KINDS:
        flags = [flag for flag in matched["debit_flags"] if flag["kind"] == kind]
        if flags:
            totals[f"{kind}_count"] = len(flags)
            totals[f"{kind}_total"] = round(sum(abs(_num(flag["amount"])) for flag in flags), 2)
    if matched["unchecked"]:
        totals["package_match_unchecked_count"] = len(matched["unchecked"])
    return totals


#: Audit round 2, R2-B15 (R54): the job statuses a package counts as pending, not failed (an error, an interrupted run or
#: a job done without an analysis stays failed).
_PENDING_JOB_STATUSES = frozenset({"queued", "processing"})

#: The owner's request of 2026-10-06 (lender payment changes; true revenue spec §9.2; R2-OW18, F3): a member chains to
#: the statement before it when it starts at most this many days before that statement ends (an overlap), or up to
#: PACKAGE_CONSECUTIVE_DAYS after.
LENDER_CHAIN_OVERLAP_DAYS = 5
#: R2-OW18 (F2): why a member's lender payments were not checked across statements, and the words the package's
#: neutral line and its downloads give each reason.
LENDER_PAYMENT_UNCHECKED_WORDS = {
    "not_ready": "not analysed yet",
    "analysed_before_check": "analysed before the check: re-analyze",
    "no_currency": "no currency declared: checked alone",
    "no_period": "no statement period: checked alone",
    "no_account_number": "fewer than 4 account digits and no balance chain: checked alone",
}


def _package_lender_payment_changes(members: list[tuple], overlays: dict | None = None) -> tuple[list[dict] | None,
                                                                                                    list[dict]]:
    """The owner's request of 2026-10-06 (lender payment changes; "can we also detect when a payment to lender has
    decreased? That would be a really important metric to track."; true revenue spec §9.2; R2-OW18, part F): each
    lender payment series read across the package's consecutive statements of ONE account, recomputed on every call
    from the kept members' displayed copies (with the package passes' overlay: passes 1 to 3 change no debit's lender
    fields; the final review of round 2's pass 4 (F2(b)) marks a payment it matched as returned
    (`returned_funder_payment_by`, `contributes_to_lender_totals` false), so a series reads it as a returned attempt,
    not a payment, as R2-OW13's restore does inside one statement) and never written back. Information only: no total,
    rollup, gate or revenue figure reads it.

    A member enters when it is analysed and its served detection carries `lender_payment_changes` (it was analysed
    with the check); otherwise it is listed and left out (`not_ready`, `analysed_before_check`). Members are visited in
    canonical order (period start, job, account) and each joins the first chain whose last member is the same account
    (R2-OW15's `_same_account`) and ends between LENDER_CHAIN_OVERLAP_DAYS days after and PACKAGE_CONSECUTIVE_DAYS
    days before it starts; otherwise it starts a chain. A member with no declared currency, no period, or fewer than
    four account digits and no balance chain is checked alone and listed (in a package of two members or more).
    `analysis.lender_payment_changes.payment_changes` runs per chain (its own overlap de-duplication included); each
    item gains its statement's source fields, a change item the statements of its last old payment (`from_*`) and of
    its new regime's second payment (`to_*`) and `cross_statement`; a stop whose series pays or is attempted after it
    in a chain of another account of the package gains `continues_in_other_account` and is never confirmed. Audit round
    3, R3-83: only when that first payment or attempt comes within the stop's grace window, counted in the business
    days the two chains' statements cover (`covered_business_days`); a later one gains `reappears_in_other_account`
    (with `covered_business_days`) and leaves the stop as its own chain reads it.

    Returns (items, unchecked): items is None when no member was assessed."""
    entries: list[dict] = []
    unchecked: list[dict] = []
    for job, analysis, account_index, _count in members:
        source = {"source_job": job.id, "source_document": getattr(job, "filename", None),
                  **({"source_account": account_index} if account_index is not None else {})}
        statement = analysis.get("statement") if isinstance(analysis, dict) else None
        if not (job.status == "done" and job.analysis is not None and isinstance(statement, dict)):
            unchecked.append({**source, "reason": "not_ready"})
            continue
        detection = analysis.get("detection")
        if not isinstance(detection, dict) or not isinstance(detection.get("lender_payment_changes"), list):
            unchecked.append({**source, "reason": "analysed_before_check"})
            continue
        member_overlay = (overlays or {}).get((job.id, account_index)) or {}
        excluded = _internal_transfer_positions(job.analysis, account_index)
        rows = []
        for position, transaction in enumerate(statement.get("transactions") or []):
            record = transaction.get("classification") if isinstance(transaction, dict) else None
            if position in excluded or not isinstance(record, dict):
                continue
            if position in member_overlay:
                record = {**record, **member_overlay[position]}
            if record.get("is_posted") is False or record.get("duplicate_of"):
                continue
            rows.append(record)
        entries.append({
            **source, "job_id": job.id, "currency": _statement_currency(analysis), "bank": _bank_key(statement),
            "digits": _printed_account_digits(analysis),
            "name": " ".join(str(statement.get("account_name") or "").split()).casefold(),
            "start": _iso_day(statement.get("period_start")), "end": _iso_day(statement.get("period_end")),
            "opening": statement.get("beginning_balance"), "closing": statement.get("ending_balance"),
            "order": (str(statement.get("period_start") or ""), str(job.id), account_index or 0),
            "rows": payment_changes_module.StatementRows(rows, statement.get("period_start"),
                                                          statement.get("period_end"), _statement_currency(analysis)),
        })
    if not entries:
        return None, unchecked
    entries.sort(key=lambda entry: entry["order"])
    chains: list[list[dict]] = []
    for entry in entries:
        for chain in chains:
            last = chain[-1]
            if (last["end"] is not None and entry["start"] is not None and _same_account(last, entry)
                    and -LENDER_CHAIN_OVERLAP_DAYS <= (entry["start"] - last["end"]).days <= PACKAGE_CONSECUTIVE_DAYS):
                chain.append(entry)
                break
        else:
            chains.append([entry])
    if len(members) >= 2:
        for chain in chains:
            if len(chain) != 1:
                continue
            entry = chain[0]
            reason = ("no_currency" if entry["currency"] is None
                      else "no_period" if entry["start"] is None or entry["end"] is None
                      else "no_account_number" if len(entry["digits"]) < 4 else None)
            if reason is not None:
                unchecked.append({key: entry[key] for key in ("source_job", "source_document", "source_account")
                                  if key in entry} | {"reason": reason})

    def statement_source(chain: list[dict], index: int, prefix: str = "source") -> dict:
        entry = chain[index]
        fields = {f"{prefix}_job": entry["source_job"], f"{prefix}_document": entry["source_document"]}
        if "source_account" in entry:
            fields[f"{prefix}_account"] = entry["source_account"]
        return fields

    items: list[dict] = []
    for chain_index, chain in enumerate(chains):
        for item in payment_changes_module.payment_changes([entry["rows"] for entry in chain]):
            published = payment_changes_module.public_item(item)
            source = chain[item["_source_statement"]]
            published.update(statement_source(chain, item["_source_statement"]))
            published["source_currency"] = source["currency"]
            published["source_period_end"] = source["rows"].period_end
            if item["kind"] in ("decrease", "increase", "cadence_change"):
                published.update(statement_source(chain, item["_from_statement"], "from"))
                published.update(statement_source(chain, item["_to_statement"], "to"))
                origin, target = chain[item["_from_statement"]], chain[item["_to_statement"]]
                published["cross_statement"] = (origin["job_id"], origin.get("source_account")) != (
                    target["job_id"], target.get("source_account"))
            if item["kind"] == "stop":
                # F5: the series continues from another account of the deal (a chain of no member of this account).
                # Audit round 3, R3-83: only when its first payment or attempt there comes within the stop's grace
                # window, counted in the business days the two chains' statements cover (a third account's never
                # count); a later one leaves the stop as its own chain reads it and is named apart.
                found = None
                reappears = None
                calendar = payment_changes_module.calendar_for(chain[0]["currency"])
                for other_index, other in enumerate(chains):
                    if other_index == chain_index or any(_same_account(one, two) for one in chain for two in other):
                        continue
                    activity = payment_changes_module.series_activity_after(
                        [entry["rows"] for entry in other], item["_series_key"], item["_last_presence"])
                    if activity is None:
                        continue
                    covered = payment_changes_module.covered_business_days(
                        item["_last_presence"], activity["date"],
                        [(entry["start"], entry["end"]) for entry in chain + other], calendar)
                    key = (activity["date"], other_index)
                    if covered <= item["grace_business_days"]:
                        if found is None or key < found[0]:
                            found = (key, other, activity)
                    elif reappears is None or key < reappears[0]:
                        reappears = (key, other, activity, covered)
                if found is not None:
                    _key, other, activity = found
                    published["continues_in_other_account"] = {
                        **statement_source(other, activity["statement"]),
                        "first_date": activity["date"], "amount": activity["amount"]}
                    published["stop_confirmed"] = False
                elif reappears is not None:
                    _key, other, activity, covered = reappears
                    published["reappears_in_other_account"] = {
                        **statement_source(other, activity["statement"]),
                        "first_date": activity["date"], "amount": activity["amount"],
                        "covered_business_days": covered}
            items.append(published)
    return items, unchecked


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
    # covers (or, its review round 1, a printout of more than a month whose rows the account's other statements print)
    # is left out the way a repeat is, and any other overlap that shares credits is named, never netted. Only the
    # statements the package counts (its members) are compared; when one is left out, the members are read again
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
            repeated_accounts.setdefault(job_id, {}).update(
                {index: covering for index, (covering, _reason) in accounts.items()})
        jobs = kept_jobs
        outdated_jobs = {}
        members, excluded_accounts = _package_members(jobs, settings=settings, outdated=outdated_jobs,
                                                      repeated_accounts=repeated_accounts)
        for entry in excluded_accounts:
            superseded = superseded_accounts.get(entry.get("job_id"), {}).get(entry.get("account_index"))
            if entry.get("is_duplicate") is True and superseded is not None:
                entry["reason"] = superseded[1]
    duplicate_accounts = sum(len(accounts) for accounts in repeated_accounts.values())
    # Owner ruling 2026-10-02 (the underwriter's Q6; §6.2's package passes; R2-OW15): the package passes over the final
    # members, after the repeats and the shorter printouts are left out and before the member loop, which reads their
    # overlay on its copies of the members' rows. R-d's positions are never matched.
    package_matched = _package_matches(members, {
        (member_job.id, member_index): _internal_transfer_positions(member_job.analysis, member_index)
        for member_job, _member_analysis, member_index, _member_count in members
    })
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
    #: Audit round 2, R2-B15 (R13): each counted member's account reading and the days its statement covers, joined
    #: into accounts after the loop (audit round 3, R3-B18, R3-02: `_months_linked`, the bank and the last four where
    #: both print them, else the balance chain within the bank; a member linked to none is its own account).
    months_members: list[dict] = []
    #: Audit B11 (I31, I05, I13): the members whose own rows do not reconcile to the bank's figures, and the members
    #: whose True rests on rows the holds could not screen or whose payer no parser read.
    unreconciled_members: list[str] = []
    holder_unscreened_members: list[str] = []
    payer_text_unread_members: list[str] = []
    #: Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the members that are premium trust accounts.
    premium_trust_members: list[str] = []
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
        # Paid to lenders: the members' confirmed lender debits counted as paid.
        "lender_debits": 0.0,
        "lender_debit_count": 0,
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the members' funder payments returned unpaid, out of
        # lender_debits and in withholding_numerator.
        "returned_funder_payment_total": 0.0,
        "returned_funder_payment_count": 0,
        "lenders_detected": 0,
        "potential_lenders_detected": 0,
        "potential_lender_debit_count": 0,
        "potential_lender_debit_total": 0.0,
        "potential_lender_debits": 0.0,
        # Audit round 2, R2-B15 (R55): per calendar month: lender_debits / months (set with the other per-month figures
        # below; it was the package's total under a monthly name). Its place here keeps the downloads' row order.
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
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the kept members' returned funder payments, each naming
    # its statement and its unit.
    package_returned_funder_payments: list[dict] = []
    # The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs"; R3-B03): the kept members'
    # lump-sum payoffs (each naming its statement and its unit) and their sum, published only where there is one.
    package_lump_sum_payoffs: list[dict] = []
    package_lump_sum = {"count": 0, "total": 0.0}
    package_potential_lender_evidence: list[dict] = []
    package_insurance_evidence: list[dict] = []
    package_revenue_evidence: dict[str, list[dict]] = {
        state: [] for state in REVENUE_STATES
    }
    # 5.6 (§9.2): the counted and held credits' evidence, and the members whose revenue is not established.
    package_tier_evidence: dict[str, list[dict]] = {"counted_flagged": [], "excluded_pending_review": []}
    # R2-OW03 (owner ruling 2026-10-02, §9.2): and the non-revenue breakdown, summed over the kept members whatever
    # their revenue's standing (Non-revenue stays where True is N/A, §10.4).
    package_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {},
                                                     "non_revenue": {}}
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (§9.2; R2-OW17): the kept members' Zelle figures, part
    # by part ((served tier, amount) slots, read from each member's metrics.zelle_deposits), whether a member carried
    # them, and whether every member's reading is the one the setting asks for.
    zelle_counted = _zelle_setting(settings)
    package_zelle: dict = {"carried": False, "setting_applied": True, "count": 0, "total": 0.0, "by_tier": {}}
    unestablished_verified: list[str] = []
    unestablished_revenue: list[str] = []
    # True revenue final review M10 (§11): a member whose True or Verified figure is not established adds a partial
    # figure to that mode's denominator, so the package publishes no rate on it.
    partial_revenue_denominator = False
    # The final review of round 2, F1 (review round 1 of its fix run; §9.2): a member row marked as publishing no rate.
    any_member_basis_unestablished = False
    any_member_gated = False
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
    package_flagged_evidence: list[dict] = []
    denominator_modes: set[str] = set()
    # Audit round 3, R3-B03 (R3-27): each ready member's withholding basis, published where the package mixes them.
    withholding_basis_by_member: list[dict] = []
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
        elif job.status in _PENDING_JOB_STATUSES:
            # Audit round 2, R2-B15 (R54): a job still queued or processing has not failed; it is pending, a key the
            # package publishes only when one is, so a package without one is unchanged.
            totals["pending"] = totals.get("pending", 0) + 1
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
        # Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the package passes' overlay, on NEW copies of the
        # rows they matched or annotated (the displayed copy and the stored job are never touched), before R-d's
        # positions are left out, so every reader below sees it: the tiers and their reasons, the revenue rows and
        # evidence, the member's gate, the ledger and the document row.
        member_key = (job.id, account_index)
        member_overlay = package_matched["overlays"].get(member_key) or {}
        if member_overlay:
            raw_transactions = [
                {**transaction, "classification": {**transaction["classification"], **member_overlay[position]}}
                if position in member_overlay else transaction
                for position, transaction in enumerate(raw_transactions)
            ]
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
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): paid to lenders reads the lender-total flag; the
        # withholding numerator reads the withholding flag, which also holds the funder payments returned unpaid.
        lender_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("contributes_to_lender_totals") is True
        ]
        withholding_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("contributes_to_withholding_rate") is True
        ]
        returned_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("returned_funder_payment_by")
        ]
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs"; R3-B03): the paid
        # payoff-worded debits, in paid to lenders and out of the withholding rows above.
        lump_sum_rows = [
            transaction
            for transaction in authoritative_rows
            if transaction["classification"].get("lump_sum_payoff")
            and transaction["classification"].get("contributes_to_lender_totals") is True
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
        # R2-OW15: the one helper the package passes read too (`_member_tiered`).
        tiered = _member_tiered(statement_transactions)
        revenue_established = verified_revenue_established and (tiered or not posted_credit_rows)
        tier_rows = {
            tier: [row for row in posted_credit_rows if row["classification"].get("revenue_tier") == tier]
            for tier in ("verified", "counted_flagged", "excluded_pending_review")
        } if tiered else {}
        tier_totals = {tier: round(sum(_num(row.get("amount")) for row in rows), 2) for tier, rows in tier_rows.items()}
        member_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {},
                                                        "non_revenue": {}}
        for tier in ("counted_flagged", "excluded_pending_review"):
            for row in tier_rows.get(tier, []):
                reason = row["classification"].get("revenue_tier_reason") or ""
                slot = member_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                slot["count"] += 1
                slot["total"] = round(slot["total"] + _num(row.get("amount")), 2)
        # R2-OW03 (owner ruling 2026-10-02, §9.2): the non-revenue breakdown, the rebuild's rule (a non_revenue row that
        # carries a code REVENUE_TIER_REASONS files under non_revenue), from the member's rows when it has them (the
        # rows `non_revenue_total` reads, its internal-transfer pairs left out), else from its stored metrics.
        if authoritative_rows:
            for row in posted_credit_rows:
                record = row["classification"]
                if record.get("revenue_tier") == "non_revenue" and non_revenue_reason(record.get("revenue_tier_reason")):
                    slot = member_by_reason["non_revenue"].setdefault(
                        record["revenue_tier_reason"], {"count": 0, "total": 0.0})
                    slot["count"] += 1
                    slot["total"] = round(slot["total"] + _num(row.get("amount")), 2)
        elif isinstance(metrics.get("non_revenue_by_reason"), dict):
            for reason, figures in metrics["non_revenue_by_reason"].items():
                if non_revenue_reason(reason) and isinstance(figures, dict):
                    member_by_reason["non_revenue"][reason] = {
                        "count": int(_num(figures.get("count"))), "total": round(_num(figures.get("total")), 2)}
        member_by_reason["non_revenue"] = dict(sorted(member_by_reason["non_revenue"].items()))
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
            withholding_numerator = round(sum(abs(_num(row.get("amount"))) for row in withholding_rows), 2)
            returned_funder_payment_total = round(sum(abs(_num(row.get("amount"))) for row in returned_rows), 2)
            returned_funder_payment_count = len(returned_rows)
            lump_sum_payoff_total = round(sum(abs(_num(row.get("amount"))) for row in lump_sum_rows), 2)
            lump_sum_payoff_count = len(lump_sum_rows)
            potential_lender_debit_total = round(
                sum(abs(_num(row.get("amount"))) for row in potential_lender_rows),
                2,
            )
            potential_lender_debit_count = len(potential_lender_rows)
            insurance_count = len(insurance_rows)
            insurance_total = round(sum(abs(_num(row.get("amount"))) for row in insurance_rows), 2)
        else:
            # Compatibility for already-completed in-memory jobs created before
            # classification records were added. New reports always take the path above. R2-OW13: paid to lenders is
            # the stored lender_debits, and the numerator the stored withholding_numerator, falling back to it.
            lender_debits = _num(metrics.get("lender_debits"), _num(metrics.get("withholding_numerator")))
            lender_debit_count = int(_num(metrics.get("lender_debit_count"), 0.0))
            withholding_numerator = _num(metrics.get("withholding_numerator"), lender_debits)
            returned_funder_payment_total = _num(metrics.get("returned_funder_payment_total"))
            returned_funder_payment_count = int(_num(metrics.get("returned_funder_payment_count"), 0.0))
            lump_sum_payoff_total = _num(metrics.get("lump_sum_payoff_total"))
            lump_sum_payoff_count = int(_num(metrics.get("lump_sum_payoff_count"), 0.0))
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
        # Audit round 3, R3-B03 (R3-72): the member's stored basis, before R-d's, the counted-pair and the moved-credit
        # deductions below; its row's rate and exposure are recomputed only where the basis it prints moved from it.
        stored_eligible_deposits = eligible_deposits
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
        # Owner ruling 2026-10-02 (the underwriter's Q6; §11; R2-OW15): a deposit the package passes took out of True
        # leaves a revenue basis it was in: the True-revenue mode loses the moved credits stored verified or counted,
        # the Verified mode those stored as verified revenue; the legacy basis and the numerator are untouched. R2-OW16
        # (the underwriter's Q4): pass 2's held deposits (stored counted) are moved credits too; its annotated held
        # deposits never are.
        moved_credits = package_matched["moved"].get(member_key) or []
        if moved_credits and denominator_mode in ("true_revenue", "verified_revenue"):
            moved_total = round(sum(
                item["amount"] for item in moved_credits
                if (item["tier"] in ("verified", "counted_flagged") if denominator_mode == "true_revenue"
                    else item["state"] == "verified_revenue")
            ), 2)
            eligible_deposits = round(max(eligible_deposits - moved_total, 0.0), 2)
        # Audit round 3, R3-B03 (R3-27): only a member with an analysis contributes a basis, so a failed member no longer
        # turns a True-revenue package "mixed".
        if ready:
            denominator_modes.add(str(denominator_mode))
            withholding_basis_by_member.append({
                "source_job": job.id, **({"account_index": account_index} if account_index is not None else {}),
                "mode": str(denominator_mode), "label": _WITHHOLDING_BASIS_LABELS.get(str(denominator_mode), ""),
            })
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
        # R2-OW03: the non-revenue breakdown beside it, never gated on the member's revenue being established.
        for reason, slot in member_by_reason["non_revenue"].items():
            item = package_by_reason["non_revenue"].setdefault(reason, {"count": 0, "total": 0.0})
            item["count"] += slot["count"]
            item["total"] = round(item["total"] + slot["total"], 2)
        # R2-OW17: the member's Zelle figures (its served metrics.zelle_deposits). Under No, a member that carries none
        # contributes its excluded Zelle deposits as its non-revenue part, so the package figure covers every member.
        member_zelle = metrics.get(ZELLE_DEPOSITS_KEY) if isinstance(metrics.get(ZELLE_DEPOSITS_KEY), dict) else None
        if member_zelle is not None:
            package_zelle["carried"] = True
            package_zelle["setting_applied"] = package_zelle["setting_applied"] and (
                member_zelle.get("setting_applied") is not False)
            parts = member_zelle.get("by_tier") if isinstance(member_zelle.get("by_tier"), dict) else {}
        elif not zelle_counted and member_by_reason["non_revenue"].get("zelle_excluded"):
            parts = {"non_revenue": member_by_reason["non_revenue"]["zelle_excluded"]}
        else:
            parts = {}
        for tier, slot in parts.items():
            if not isinstance(slot, dict):
                continue
            item = package_zelle["by_tier"].setdefault(tier, {"count": 0, "total": 0.0})
            item["count"] += int(_num(slot.get("count")))
            item["total"] = round(item["total"] + _num(slot.get("total")), 2)
            package_zelle["count"] += int(_num(slot.get("count")))
            package_zelle["total"] = round(package_zelle["total"] + _num(slot.get("total")), 2)
        if ready and not verified_revenue_established:
            unestablished_verified.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        if ready and not revenue_established:
            unestablished_revenue.append(job.id if account_index is None else f"{job.id}#account_{account_index}")
        # The final review of round 2, F1 (§9.2, §11): the member's own basis is not established (its served copy already
        # says so, or the package's reading of its rows does); its row publishes no rate and its potential lenders no
        # exposure, as the statement viewed alone (analysis/revenue_view.py).
        member_basis_unestablished = metrics.get(WITHHOLDING_BASIS_UNESTABLISHED) is True or (
            ready and withholding_basis_unestablished(denominator_mode, verified_established=verified_revenue_established,
                                                      established=revenue_established))
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
            for tier in ("counted_flagged", "excluded_pending_review"):
                for reason, slot in member_by_reason[tier].items():
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
        totals["returned_funder_payment_total"] = round(
            totals["returned_funder_payment_total"] + returned_funder_payment_total, 2
        )
        totals["returned_funder_payment_count"] += returned_funder_payment_count
        package_lump_sum["count"] += lump_sum_payoff_count
        package_lump_sum["total"] = round(package_lump_sum["total"] + lump_sum_payoff_total, 2)
        totals["potential_lender_debit_total"] = round(
            totals["potential_lender_debit_total"] + potential_lender_debit_total,
            2,
        )
        totals["potential_lender_debits"] = totals["potential_lender_debit_total"]
        totals["potential_lender_debit_count"] += potential_lender_debit_count
        totals["insurance_count"] += insurance_count
        totals["insurance_total"] = round(totals["insurance_total"] + insurance_total, 2)
        # R2-OW13 (the underwriter's Q5): the members' numerators, paid plus returned, never the paid figure alone.
        totals["withholding_numerator"] = round(totals["withholding_numerator"] + withholding_numerator, 2)
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
                {"funder": name, "documents": 0, "total_debited": 0.0, "returned_payment_count": 0,
                 "returned_payment_total": 0.0},
            )
            item["documents"] += 1
            match_debit_count = int(
                _num(match.get("debit_count"), len(match.get("transactions") or []))
            )
            # R2-OW13: a funder whose every payment bounced publishes debit_count 0, and is listed with it.
            if match_debit_count or "debit_count" in match:
                item["debit_count"] = item.get("debit_count", 0) + match_debit_count
            item["total_debited"] = round(item["total_debited"] + _num(match.get("total_debited")), 2)
            item["returned_payment_count"] += int(_num(match.get("returned_payment_count"), 0.0))
            item["returned_payment_total"] = round(
                item["returned_payment_total"] + _num(match.get("returned_payment_total")), 2
            )
            package_funder_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the warning's items, each naming its statement, its
        # account (a statement of several) and its unit, as an evidence record does.
        for returned_item in detection.get("returned_funder_payments") or []:
            if isinstance(returned_item, dict):
                package_returned_funder_payments.append({
                    **returned_item, "source_job": job.id, "source_document": job.filename,
                    "source_currency": statement_currency,
                    **({"source_account": account_index} if account_index is not None else {}),
                    # Audit round 3, R3-B02 (R3-73): a payment the funder re-debited in the next statement.
                    **package_matched["represented"].get((member_key, returned_item.get("debit_location")), {}),
                })
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): the member's lump-sum payoffs, each naming
        # its statement, its account (a statement of several) and its unit; a payment the package's pass 4 matched to a
        # return in the next statement is out of paid there and no lump sum (its overlay row says so).
        paid_lump_sums = {row["classification"].get("source_location") for row in lump_sum_rows}
        for lump_sum_item in detection.get("lump_sum_payoffs") or []:
            if isinstance(lump_sum_item, dict) and (not authoritative_rows
                                                    or lump_sum_item.get("location") in paid_lump_sums):
                package_lump_sum_payoffs.append({
                    **lump_sum_item, "source_job": job.id, "source_document": job.filename,
                    "source_currency": statement_currency,
                    **({"source_account": account_index} if account_index is not None else {}),
                })

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
            # Audit round 3, R3-B03 (R3-72, R3-20): published only over a basis the member row publishes a rate on (the
            # floor's helper in place of `eligible_deposits > 0`), never where F1 refuses the member's basis.
            match_exposure = (
                abs(match_total) / eligible_deposits * 100
                if withholding_basis_publishable(eligible_deposits, denominator_mode) and not member_basis_unestablished
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
                    # F1 (final review of round 2): no basis where the member's is not established. Audit round 3,
                    # R3-B03 (R3-20): nor under the withholding basis floor, as the statement's own row reads.
                    "eligible_deposit_denominator": (
                        None if member_basis_unestablished
                        or withholding_basis_below_floor(eligible_deposits, denominator_mode)
                        else eligible_deposits),
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
            # The withholding rows, and (audit round 3, R3-B02: R3-73) a returned funder payment its funder re-debited,
            # which left the rate but is still a lender row, and (R3-B03: R3-79) a paid lump-sum payoff, in paid to
            # lenders and out of the rate.
            if (classification.get("contributes_to_withholding_rate") is True
                    or classification.get("returned_funder_payment_by")
                    or (classification.get("lump_sum_payoff")
                        and classification.get("contributes_to_lender_totals") is True)):
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

        # Audit round 3, R3-B03 (R3-72; true revenue spec §9.2): a member row divides by the basis it prints. Where the
        # package moved the member's basis (R-d's internal-transfer deduction, the 5.6 counted-pair deduction, R2-OW15/16's
        # moved credits), its rate and potential exposure are its own numerators over that basis; elsewhere they are the
        # stored figures, as before. Neither is published under R3-20's floor (`withholding_basis_publishable`) or where
        # F1 refuses the member's basis.
        member_rate_published = (
            withholding_basis_publishable(eligible_deposits, denominator_mode) and not member_basis_unestablished)
        if round(eligible_deposits, 2) != round(stored_eligible_deposits, 2):
            member_withholding_rate = (
                abs(withholding_numerator) / eligible_deposits * 100 if member_rate_published else None)
            member_potential_exposure = (
                abs(potential_lender_debit_total) / eligible_deposits * 100 if member_rate_published else None)
        else:
            member_withholding_rate = metrics.get("withholding_rate") if member_rate_published else None
            member_potential_exposure = metrics.get("potential_withholding_exposure") if member_rate_published else None
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
            # R2-OW03 (owner ruling 2026-10-02, §9.2): its non-revenue breakdown, kept where its revenue is not
            # established (its rows are known non-revenue, captured rows only).
            "non_revenue_by_reason": member_by_reason["non_revenue"],
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
            # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: a premium trust account, whose deposits that
            # would count are held (a statement fact; no figure reads it).
            "premium_trust_account": metrics.get("premium_trust_account") is True,
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
            # R2-OW13 (the underwriter's Q5): its funder payments returned unpaid, out of lender_debits.
            "returned_funder_payment_total": returned_funder_payment_total,
            "returned_funder_payment_count": returned_funder_payment_count,
            "lenders_detected": int(_num(metrics.get("lenders_detected"), len(detection.get("known_funders") or []))),
            "potential_lenders_detected": int(_num(metrics.get("potential_lenders_detected"), len(detection.get("potential_lenders") or []))),
            "potential_lender_debit_count": potential_lender_debit_count,
            "potential_lender_debit_total": potential_lender_debit_total,
            "potential_lender_debits": potential_lender_debit_total,
            "insurance_count": insurance_count,
            "insurance_total": insurance_total,
            "withholding_rate": member_withholding_rate,
            # R2-OW13: paid lender debits plus returned funder payments.
            "withholding_numerator": withholding_numerator,
            "withholding_denominator": eligible_deposits,
            "withholding_review_required": (
                bool(metrics.get("withholding_review_required")) or eligible_deposits <= 0 or member_basis_unestablished
                # Audit round 3, R3-B03 (R3-20): a revenue basis under the floor asks for review, as $0 does.
                or not withholding_basis_publishable(eligible_deposits, denominator_mode)
            ),
            "withholding_denominator_mode": denominator_mode,
            "withholding_denominator_label": metrics.get("withholding_denominator_label") or "Legacy eligible deposits",
            "potential_withholding_exposure": member_potential_exposure,
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
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): the member's lump-sum payoffs (in its
        # `lender_debits`, out of its `withholding_numerator`), only where it has one.
        if lump_sum_payoff_count:
            doc_row["lump_sum_payoff_total"] = lump_sum_payoff_total
            doc_row["lump_sum_payoff_count"] = lump_sum_payoff_count
        # The final review of round 2, F1 (§9.2): the member's withholding basis is not established, only where it is;
        # the package goes to review (review round 1 of the fix run).
        if member_basis_unestablished:
            doc_row[WITHHOLDING_BASIS_UNESTABLISHED] = True
            any_member_basis_unestablished = True
        # R2-OW17: the member's Zelle figures, where its served copy carries them (the Monthly cell reads them).
        if member_zelle is not None:
            doc_row[ZELLE_DEPOSITS_KEY] = deepcopy(member_zelle)
        # Owner ruling 2026-10-02 (the underwriter's Q6; §9.2; R2-OW15): the member's rows the package passes matched
        # or annotated, and why the passes could not read it ('no_currency', 'older_rules'), each only where there is one.
        if member_overlay:
            doc_row["package_match_count"] = len(member_overlay)
        if member_key in package_matched["unchecked"]:
            doc_row["package_match_unchecked"] = package_matched["unchecked"][member_key]
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
            # Audit round 2, R2-B15 (R13): the days it covers, for its account's month floor below; audit round 3,
            # R3-B18 (R3-02): with what its account is read by (`_months_linked`).
            months_members.append({
                "job_id": job.id, "account_index": account_index,
                "bank": _package_bank(statement), "digits": _printed_account_digits(analysis),
                "name": " ".join(str(statement.get("account_name") or "").split()).casefold(),
                "start": _iso_day(statement.get("period_start")), "end": _iso_day(statement.get("period_end")),
                "opening": statement.get("beginning_balance"), "closing": statement.get("ending_balance"),
                "days": _covered_days(statement.get("period_start"), statement.get("period_end")),
            })
            if (analysis.get("reconciliation") or {}).get("ok") is not True:
                unreconciled_members.append(doc_row["id"])
            if doc_row["holder_unscreened"]:
                holder_unscreened_members.append(doc_row["id"])
            if doc_row["payer_text_unread"]:
                payer_text_unread_members.append(doc_row["id"])
            if doc_row["premium_trust_account"]:
                premium_trust_members.append(doc_row["id"])
            if adb_validated:
                adb_value = Decimal(str(average_daily_balance_num))
                adb_weighted_sum += adb_value * adb_calendar_days
                adb_weight += adb_calendar_days

    # The owner's request of 2026-10-06 (lender payment changes; §9.2; R2-OW18): each lender payment series read across
    # the consecutive statements of one account, from the kept members' displayed copies (information only).
    lender_payment_changes, lender_payment_unchecked = _package_lender_payment_changes(
        members, package_matched["overlays"])

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
    #
    # Audit round 2, R2-B15 (R13): floored by the days each account's statements cover, as whole months of 30.4375
    # days, half up (the largest account's), so consecutive statements of one account never read fewer months than
    # the days they cover: a 16th-to-15th cycle across February (02-16..03-15 and 03-16..04-15 both stand for March)
    # or a cycle whose periods share their closing day read 3 months over 3 statements, never 2, and a statement of
    # 59 days reads 2, never 1. The labels (`_statement_month`) are unchanged; a floor below the calendar count is inert.
    #
    # Audit round 3, R3-B18 (R3-02): an account is the members `_months_linked` joins (a small union-find in member
    # order): two keyed members by the bank and the last four, as before; a member that prints no bank or fewer than
    # four digits by the balance chain of the owner's Q6 identity (R2-OW15's `_chained`) within its bank and holder, so
    # a 16th-to-15th cycle whose number is not read reads its months too. A member linked to none is its own account.
    links = list(range(len(months_members)))

    def account_of(place: int) -> int:
        while links[place] != place:
            links[place] = links[links[place]]
            place = links[place]
        return place

    for place, member in enumerate(months_members):
        for other_place in range(place):
            if _months_linked(months_members[other_place], member):
                links[account_of(place)] = account_of(other_place)
    account_days: dict[int, set] = {}
    for place, member in enumerate(months_members):
        account_days.setdefault(account_of(place), set()).update(member["days"])
    month_floor = max((_months_covered(len(days)) for days in account_days.values()), default=0)
    months = max(1, len(month_keys) + months_unplaced, month_floor)
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
    # The final review of round 2, F2(b) (the underwriter's Q5 across statements): each payment pass 4 matched to a
    # return in the next statement is out of its funder's paid rollup and in its returned payments (the member rows
    # already read the overlay), and R2-OW13's warning lists it, naming both documents.
    for match in package_matched["matches"]:
        if match["kind"] != "returned_funder_payment":
            continue
        debit, credit = match["debit"], match["credit"]
        amount = round(abs(_num(debit.get("amount"))), 2)
        rollup = funders.get(debit.get("funder") or "Unknown")
        if rollup is not None:
            rollup["debit_count"] = max(int(rollup.get("debit_count", 0)) - 1, 0)
            rollup["total_debited"] = round(rollup["total_debited"] - amount, 2)
            rollup["returned_payment_count"] += 1
            rollup["returned_payment_total"] = round(rollup["returned_payment_total"] + amount, 2)
        package_returned_funder_payments.append({
            "funder": debit.get("funder"), "amount": amount, "debit_date": debit.get("date"),
            "debit_location": debit.get("source_location"), "credit_date": credit.get("date"),
            "credit_location": credit.get("source_location"), "credit_description": credit.get("description"),
            "source_job": debit.get("job"), "source_document": debit.get("filename"),
            "source_currency": debit.get("currency"),
            **({"source_account": debit["account_index"]} if debit.get("account_index") is not None else {}),
            "credit_job": credit.get("job"), "credit_document": credit.get("filename"),
            **({"credit_account": credit["account_index"]} if credit.get("account_index") is not None else {}),
            "cross_statement": True,
            # Audit round 3, R3-B02 (R3-73): the funder re-debited it (the re-debit's statement named).
            **package_matched["represented"].get(((debit.get("job"), debit.get("account_index")),
                                                  debit.get("source_location")), {}),
        })
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
    # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the members whose deposits that would count are held for
    # a premium trust account's title; the True card names how many.
    totals["premium_trust_documents"] = sorted(premium_trust_members)
    # 5.6 (T7, §9.2): the gate applied to each member; a package needs revenue review when one of them does.
    totals["revenue_review_required"] = any_member_gated
    totals["counted_flagged_by_reason"] = package_by_reason["counted_flagged"]
    totals["excluded_pending_review_by_reason"] = package_by_reason["excluded_pending_review"]
    # R2-OW03 (owner ruling 2026-10-02, §9.2): the kept members' non-revenue breakdown. It is left out of the two nulling
    # blocks below (§10.4's and R2-B15 R54's: Non-revenue stays), and its money is refused with the totals under a
    # currency refusal, its counts kept.
    totals["non_revenue_by_reason"] = dict(sorted(package_by_reason["non_revenue"].items()))
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (§9.2; R2-OW17): the kept members' Zelle figures, part
    # by part, present when a kept member carries them; `counted_as_true_revenue` is the setting, `setting_applied`
    # False when a member's is. Its money is refused with the totals under a currency refusal, its counts kept.
    if package_zelle["carried"]:
        order = {tier: position for position, tier in enumerate(("verified", "counted_flagged",
                                                                 "excluded_pending_review", "non_revenue"))}
        totals[ZELLE_DEPOSITS_KEY] = {
            "counted_as_true_revenue": zelle_counted,
            "setting_applied": package_zelle["setting_applied"],
            "count": package_zelle["count"],
            "total": package_zelle["total"],
            "by_tier": dict(sorted(package_zelle["by_tier"].items(), key=lambda item: order.get(item[0], len(order)))),
        }
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
    # Audit round 2, R2-B15 (R54): a package with no statement analysed (every job failed, was interrupted or is still
    # queued or processing, or every account was left out) has no revenue figure at all: True, Verified, Counted and
    # Held are N/A, never a $0.00 an underwriter would read as a measured decline, and nothing reads as reconciled.
    # With one analysed statement or more, §10.4 holds as before: a failed member's credits are in no total.
    no_statement_analysed = totals["completed"] == 0
    if no_statement_analysed:
        for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                    "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                    "counted_flagged_by_reason", "excluded_pending_review_by_reason", "verified_revenue_total",
                    "confirmed_true_revenue_total", "confirmed_true_revenue"):
            totals[key] = None
        totals["revenue_tiers_sum_to_posted"] = totals["revenue_reconciles"] = False
    # Audit round 3, R3-B03 (R3-27; true revenue spec §9.2, §11): the package's one basis. A package with no ready member
    # keeps today's legacy mode (no rate: it has no basis); one whose members were analysed under different bases is
    # mixed, and publishes no rate over the blend.
    package_denominator_mode = (
        next(iter(denominator_modes)) if len(denominator_modes) == 1
        else "legacy_eligible_deposits" if not denominator_modes else "mixed"
    )
    mixed_basis = len(denominator_modes) > 1
    # Audit round 3, R3-B03 (R3-20): a revenue basis under the withholding basis floor publishes no rate, as $0 does; the
    # legacy basis and a mixed one (refused below) never read the floor. Never a gate.
    package_basis_below_floor = not mixed_basis and withholding_basis_below_floor(
        totals["withholding_denominator"], package_denominator_mode)
    package_withholding_raw = (
        abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
        if withholding_basis_publishable(totals["withholding_denominator"], package_denominator_mode)
        else None
    )
    package_withholding = round(package_withholding_raw, 2) if package_withholding_raw is not None else None
    withholding_review_required = not withholding_basis_publishable(
        totals["withholding_denominator"], package_denominator_mode)
    potential_withholding_raw = (
        abs(totals["potential_withholding_numerator"])
        / totals["potential_withholding_denominator"]
        * 100
        if withholding_basis_publishable(totals["potential_withholding_denominator"], package_denominator_mode)
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
    if mixed_basis:
        # Audit round 3, R3-B03 (R3-27): members analysed under different withholding bases (a job stored before
        # R2-OW14, legacy or with no mode, beside a new one) sum legacy deposits and True revenue into one figure that is
        # neither: no package rate and no potential exposure is published over it, and the package asks for review
        # (F1/M10's precedent, review round 1 of the final fix run). Each member row keeps its own basis and rate.
        package_withholding = package_withholding_raw = None
        potential_withholding = potential_withholding_raw = None
        withholding_review_required = True
    # A lender row carries no basis where the package publishes no exposure over a basis: a partial one (M10), a mixed
    # one (R3-27) or one under the floor (R3-20); a basis of $0 or less keeps its 0.0, as before.
    rollup_basis_refused = partial_revenue_denominator or mixed_basis or package_basis_below_floor
    potential_withholding_review_required = totals["potential_lender_debit_count"] > 0
    for item in potential_lenders.values():
        # The final review of round 2, F1: no basis on a lender row where the package's is partial (M10), or the
        # dashboard would compute the exposure the package refuses from it.
        item["eligible_deposit_denominator"] = (
            None if rollup_basis_refused else totals["potential_withholding_denominator"])
        item["potential_withholding_exposure"] = (
            abs(item["total_debited"]) / totals["potential_withholding_denominator"] * 100
            if withholding_basis_publishable(totals["potential_withholding_denominator"], package_denominator_mode)
            and not rollup_basis_refused
            else None
        )
        item["potential_withholding_formula"] = POTENTIAL_WITHHOLDING_FORMULA
    # Audit round 2, R2-B15 (R15): the accounts left out of every figure for a reason other than a repeat: a statement
    # whose main account is held or idle (the 2026-09-23 ruling), an account that did not validate on its own (Q1), and
    # every account of a document whose transfers could not be paired (Q2) or that left a section out without proof
    # (L1-C17). Membership and every figure stay as they are; the package says so (completeness partial, the count,
    # the download section and the dashboard's notice) and needs an analyst, as the same account uploaded alone does.
    left_out_accounts = [entry for entry in excluded_accounts if entry.get("is_duplicate") is not True]
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
        # The final review of round 2, F1 (review round 1 of its fix run; §9.2, §11): a member whose withholding basis
        # is not established, or the package's own partial basis (M10), publishes no rate, so the package needs an
        # analyst, as each such statement viewed alone does. The legacy basis sets neither.
        or any_member_basis_unestablished
        or partial_revenue_denominator
        # Audit round 3, R3-B03 (R3-27; F1/M10's precedent, review round 1 of the final fix run): members analysed under
        # different withholding bases publish no package rate, so the package needs an analyst (re-analyze them on one
        # basis). R3-20's floor, like a $0 basis, never gates.
        or mixed_basis
        or totals["has_duplicate_documents"]
        # Audit round 2, R2-B14 (R14): two statements of one account that share credits in the days both cover.
        or overlapping_statements
        # Audit round 2, R2-B15: an account left out for another reason than a repeat (R15), and a job still queued or
        # processing (R54).
        or left_out_accounts
        or totals.get("pending")
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
        # Audit round 2, R2-B15 (R15; Q1: the package surfaces partial completeness): the accounts left out for another
        # reason than a repeat, published only when there is one. `sibling_account_omission_detected` stays Q10's.
        **({
            "completeness": "partial",
            "excluded_account_count": len(left_out_accounts),
        } if left_out_accounts else {}),
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
        # Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the package passes' counts and totals, each only where
        # a pass found a row (_package_match_totals), so a package without one carries no new key.
        **_package_match_totals(package_matched),
        "months": months,
        # Gross: every posted credit, not True revenue (audit B11, I07: the dashboard labels it so).
        "avg_monthly_credits": round(totals["total_credits"] / months, 2),
        "avg_monthly_debits": round(totals["total_debits"] / months, 2),
        # Audit round 2, R2-B15 (R55): the confirmed lender debits per calendar month, beside the package's total
        # (`lender_debits`); refused with the other per-period figures (_PER_PERIOD_AVERAGE_KEYS, a mixed currency).
        "monthly_lender_debits": round(totals["lender_debits"] / months, 2),
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
        # R2-OW13 (the underwriter's Q5): the members' numerators (paid plus returned) over the withholding basis.
        "withholding_formula": WITHHOLDING_FORMULA,
        "withholding_review_required": withholding_review_required,
        # The final review of round 2, F1 (§9.2, §11): the basis M10 refuses the rate on, only where it does.
        **({WITHHOLDING_BASIS_UNESTABLISHED: True} if partial_revenue_denominator else {}),
        # Audit round 3, R3-B03 (R3-27): the members' bases, only where they differ (the dashboard names them).
        **({"withholding_basis_mixed": True, "withholding_basis_by_member": withholding_basis_by_member}
           if mixed_basis else {}),
        # Audit round 3, R3-B03 (R3-20): a revenue basis under the withholding basis floor, only where it is.
        **({"withholding_basis_below_floor": True} if package_basis_below_floor else {}),
        # Audit round 3, R3-B03 (R3-79, the owner's answer of 2026-10-07): the lump-sum payoffs in `lender_debits` and
        # out of `withholding_numerator`, only where a member has one (the total refused across currencies).
        **({"lump_sum_payoff_total": package_lump_sum["total"], "lump_sum_payoff_count": package_lump_sum["count"]}
           if package_lump_sum["count"] else {}),
        "potential_withholding_exposure": potential_withholding,
        "potential_withholding_exposure_raw": potential_withholding_raw,
        "potential_withholding_formula": POTENTIAL_WITHHOLDING_FORMULA,
        "potential_withholding_review_required": potential_withholding_review_required,
        "decision": decision,
        # Audit round 3, R3-B03 (R3-27): read off the ready members only; a package with none keeps the legacy mode.
        "withholding_denominator_mode": package_denominator_mode,
        # The basis the summed NSF count was cut on (analysis/nsf_days.py). "mixed" when members differ, e.g. a
        # member whose count is unavailable, or a legacy payload that could not be re-based.
        "nsf_source": next(iter(nsf_sources)) if len(nsf_sources) == 1 else ("mixed" if nsf_sources else None),
        "withholding_denominator_label": _WITHHOLDING_BASIS_LABELS.get(
            package_denominator_mode, "Mixed denominator configuration"),
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
            if key in _PACKAGE_MATCH_TOTAL_KEYS and key not in published_totals:
                continue  # R2-OW15: published only where a package pass found a row
            published_totals[key] = None
        # 5.6 (§9.2): the by-reason money is refused with the totals; the counts stay. R2-OW03: the non-revenue
        # breakdown's too.
        for key in _TIER_REASON_KEYS:
            if isinstance(published_totals.get(key), dict):
                published_totals[key] = {
                    reason: {**slot, "total": None} for reason, slot in published_totals[key].items()
                }
        # R2-OW17: the Zelle figures' money too, every count kept (a nested count-and-money dict, refused part by part).
        zelle_totals = published_totals.get(ZELLE_DEPOSITS_KEY)
        if isinstance(zelle_totals, dict):
            published_totals[ZELLE_DEPOSITS_KEY] = {
                **zelle_totals, "total": None,
                "by_tier": {tier: {**slot, "total": None} for tier, slot in (zelle_totals.get("by_tier") or {}).items()},
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

    # Audit round 2, R2-B15 (R54): no evidence for a True revenue the package has no figure for.
    true_revenue_evidence = None if unestablished_revenue or no_statement_analysed else [
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
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the kept members' returned funder payments.
        "returned_funder_payments": package_returned_funder_payments,
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): the lump-sum payoffs' lines, each in its
        # statement's own unit, only where there is one (never summed here, so the currency refusal leaves them).
        **({"lump_sum_payoffs": package_lump_sum_payoffs} if package_lump_sum_payoffs else {}),
        # The owner's request of 2026-10-06 (R2-OW18): the lender payment changes across each account's consecutive
        # statements, absent only when no member was assessed, and the members not checked across statements (each with
        # its reason), only where there is one. Never summed, so the currency refusal leaves them as they are.
        **({"lender_payment_changes": lender_payment_changes} if lender_payment_changes is not None else {}),
        **({"lender_payment_changes_unchecked": lender_payment_unchecked} if lender_payment_unchecked else {}),
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
        # Owner ruling 2026-10-02 (the underwriter's Q6; §9.2; R2-OW15): each match the package passes made across its
        # statements, each leg naming its statement, account and unit, and each debit they flag (never deducted); only
        # where there is one.
        **({"package_matches": package_matched["matches"]} if package_matched["matches"] else {}),
        **({"debit_flags": package_matched["debit_flags"]} if package_matched["debit_flags"] else {}),
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
    # Audit round 3, R3-B02 (R3-21; spec §10.7): a confirm on a credit that returns a confirmed funder's payment.
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
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (spec §10.7; R2-OW17): the decision is validated on
    # the Zelle reading the reviewer sees, and the latest decision on a posting sets both readings
    # (analysis/zelle_view.py with_both_readings). The setting is read once for the request.
    settings = load_settings(store.storage.data_dir)
    shown = _zelle_setting(settings)
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
    return jsonify({"analysis": _masked(_displayed(stored, settings=settings))})


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
    # R2-OW17 (spec §10.7): validated on the Zelle reading shown, all or nothing; the other reading follows the latest
    # decision on each posting (analysis/zelle_view.py with_both_readings). The setting is read once for the request.
    settings = load_settings(store.storage.data_dir)
    shown = _zelle_setting(settings)
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
    return jsonify({"analysis": _masked(_displayed(stored, settings=settings)), "applied": len(parsed)})


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
