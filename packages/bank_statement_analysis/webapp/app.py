from __future__ import annotations
import io
import errno
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
from collections import deque
from copy import deepcopy
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
from analysis import zelle_view
from analysis.served_view import displayed, zelle_setting
from .jobs import JobStore, UnknownJobs
from .settings import load_settings, save_settings
from .storage import SCHEMA_VERSION, Storage
from .worker import run_job
from .reanalysis import replay_reviews, rerun_analysis
from .export_view import masked, package_for_export
from .statement_export import analysis_csv, analysis_xlsx
from .package_export import package_csv, package_xlsx

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


_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_download_name(name: object) -> str:
    """Whitelist-sanitize a base name for `Content-Disposition`. The uploaded
    filename is attacker-supplied, so quotes, CR/LF and path separators must
    never reach the header."""
    base = _UNSAFE_NAME.sub("_", str(name or ""))[:100]
    return base if base.strip("._-") else "download"


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
        "analysis": masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir))),
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
    return jsonify({"analysis": masked(displayed(stored, settings=settings))})


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
    return jsonify({"analysis": masked(displayed(stored, settings=settings)), "applied": len(parsed)})


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
        "analysis": masked(displayed(stored, settings=load_settings(store.storage.data_dir))),
        "reviews_replayed": len(replay.replayed),
        "reviews_not_replayed": len(replay.not_replayed),
        "reviews_decided_by_rules": len(replay.decided_by_rules),
    })


@app.route("/package_analysis")
def package_analysis():
    package = _package_from_request()
    if isinstance(package, tuple):
        return package
    return jsonify(masked(package))


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
    """The requested package, built on one snapshot of its jobs (`JobStore.snapshot`), so a job that finishes or is
    reviewed while it is built is read as it stood before. A job the store does not hold raises UnknownJobs."""
    ids, error = _requested_job_ids()
    if error is not None:
        return error
    return package_view.package_analysis(store.snapshot(ids), settings=load_settings(store.storage.data_dir))


@app.errorhandler(UnknownJobs)
def _unknown_jobs(unknown):
    return jsonify({"error": "unknown job ids", "missing": unknown.ids}), 404


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
    package = masked(package_for_export(package))
    if fmt == "json":
        content = json.dumps(package, indent=2)
        mimetype = "application/json"
        suffix = "json"
    elif fmt == "csv":
        content = package_csv(package)
        mimetype = "text/csv"
        suffix = "csv"
    else:
        content = package_xlsx(package)
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
            masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)), indent=2)
        mimetype = "application/json"
    elif fmt == "csv":
        if job.analysis is None:
            abort(404)
        content = analysis_csv(
            masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)))
        mimetype = "text/csv"
    elif fmt == "xlsx":
        if job.analysis is None:
            abort(404)
        content = analysis_xlsx(
            masked(displayed(job.analysis, settings=load_settings(store.storage.data_dir), export=True)))
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
