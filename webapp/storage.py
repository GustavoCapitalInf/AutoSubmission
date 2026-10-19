"""Durable persistence for the webapp (Wave 1 / D-1).

SQLite (stdlib ``sqlite3``) schema and all data access for jobs, documents,
packages, review decisions and the audit log, plus the on-disk PDF store.

Engine and concurrency
----------------------
* stdlib ``sqlite3`` only — no new dependencies. WAL journal mode.
* SINGLE-WRITER DISCIPLINE: the webapp runs exactly one background worker
  thread (the one-job-at-a-time queue in ``webapp/app.py``), and every other
  write (review decisions, package minting, audit rows) happens on a request
  thread of the same process. Writes are short transactions; WAL plus a
  30-second busy timeout serializes them safely. There is deliberately no
  connection pool and no cross-process coordination — this store is scoped to
  the one local server process, matching the existing one-worker queue.
* Cross-thread safety: a NEW connection is opened per call (per-connection-
  per-call), so no connection object ever crosses a thread boundary. Each
  public method is a single transaction.

Migration / back-compat statement (required by the D-1 brief)
-------------------------------------------------------------
v1 shipped fresh. NO importer exists because no durable data predated D-1 —
the previous store was purely in-memory, so "migrating" it is meaningless;
that IS the migration/back-compat answer for v1. The ``schema_version``
table records the schema in force and ``_MIGRATIONS`` is the forward-only
hook: to move from version N to N+1, register a callable under
``_MIGRATIONS[N]``. Downgrades are refused. The analysis result payload is
stored as OPAQUE JSON text (the ``report_to_dict`` output, verbatim and
UNMASKED — masking stays a serve-time concern in ``webapp/app.py``), so
``analysis/`` contract changes never require a schema migration here.
v2 (O-1) is the first exercise of the hook: an additive ``profile_json``
column on ``documents`` storing the preflight DocumentProfile.
v3 (D-3) adds the ``artifact_cache`` INDEX table for the content-addressed
artifact cache. Only the index lives in SQLite; the artifacts themselves are
files under ``<data_dir>/artifacts/`` (see ``webapp/artifact_cache.py``), so
the database never grows by the size of an OCR read. The index is a pure
derived cache: unlike ``review_decisions``/``audit_log`` it is deliberately
NOT append-only (hit counters update, stale rows are evicted), and dropping
the whole table plus the artifact directory only costs recomputation.

Content hash convention (the O-1 handshake)
-------------------------------------------
``content_sha256(pdf_bytes)`` = UPPERCASE hex SHA-256 of the raw PDF bytes,
exactly the convention of ``corpus_gate.sha256_upper``. The ONE definition
lives in ``ocr/inspect.py`` (relocated there in O-1) and is re-exported
here. PDF bytes live on disk as ``<content_sha256>.pdf`` inside the data
directory — never inside SQLite, and released from RAM once a job reaches a
terminal state.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

# O-1: the hash definition RELOCATED to ocr/inspect.py (the preflight needs it
# and ocr must not depend on webapp). Re-exported here so every D-1 consumer
# (webapp.jobs, tests) keeps importing webapp.storage.content_sha256 — still
# exactly ONE definition.
from ocr.inspect import content_sha256

# The data directory's one rename-into-place helper (a brief retry on the Windows refusal while a reader has the
# target open), shared rather than copied: audit 2026-10-13, BE-4.
from .settings import _replace as _replace_retrying

__all__ = ["Storage", "content_sha256", "default_data_dir", "utc_now_iso", "SCHEMA_VERSION"]

SCHEMA_VERSION = 4


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """v2 (O-1): store the preflight DocumentProfile with the document row.

    Additive only — v1 rows keep working with profile_json NULL."""
    conn.execute("ALTER TABLE documents ADD COLUMN profile_json TEXT")


_ARTIFACT_CACHE_V3 = """
CREATE TABLE IF NOT EXISTS artifact_cache (
    stage          TEXT    NOT NULL,
    cache_key      TEXT    NOT NULL,
    input_sha256   TEXT    NOT NULL,
    settings_key   TEXT    NOT NULL,
    format_version INTEGER NOT NULL,
    artifact_path  TEXT    NOT NULL,
    byte_size      INTEGER NOT NULL,
    created_at     TEXT    NOT NULL,
    last_hit_at    TEXT,
    hit_count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stage, cache_key)
);
CREATE INDEX IF NOT EXISTS idx_artifact_cache_input
    ON artifact_cache(stage, input_sha256);
"""


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """v3 (D-3): the artifact-cache INDEX table.

    Additive only — a new table, no existing row or column is touched.
    ``artifact_path`` is stored RELATIVE to the data directory so a data
    directory stays relocatable (the tests' tmp dirs are a different path
    every run)."""
    conn.executescript(_ARTIFACT_CACHE_V3)


_TELEMETRY_V4 = """
CREATE TABLE IF NOT EXISTS telemetry (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id         TEXT    NOT NULL UNIQUE,
    run_id            TEXT    NOT NULL,
    job_id            TEXT,
    content_sha256    TEXT    NOT NULL,
    emitted_at        TEXT    NOT NULL,
    telemetry_version INTEGER NOT NULL,
    emitter           TEXT    NOT NULL,
    outcome_class     TEXT    NOT NULL,
    dispatch_outcome  TEXT,
    parser_id         TEXT,
    source_path       TEXT    NOT NULL,
    record            TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_run     ON telemetry(run_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_sha     ON telemetry(content_sha256);
CREATE INDEX IF NOT EXISTS idx_telemetry_outcome ON telemetry(outcome_class);
CREATE TRIGGER IF NOT EXISTS telemetry_no_update
BEFORE UPDATE ON telemetry
BEGIN
    SELECT RAISE(ABORT, 'telemetry is append-only');
END;
CREATE TRIGGER IF NOT EXISTS telemetry_no_delete
BEFORE DELETE ON telemetry
BEGIN
    SELECT RAISE(ABORT, 'telemetry is append-only');
END;
"""


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """v4 (H-3): the per-statement telemetry table.

    Additive only — a new table, no existing row or column is touched. Every
    typed column is a PROJECTION of the canonical record JSON in ``record``,
    indexed so the coverage query never parses JSON to group; the blob stays
    the single definition of the shape (H3_SCHEMA I2). Append-only triggers
    match ``audit_log``: telemetry is evidence, and evidence is not edited.
    Retention/expiry is deliberately absent this wave — a run-scoped delete
    would have to contend with the trigger above, so an expiry policy is a
    D-7/Wave-3 decision that comes with a documented exception."""
    conn.executescript(_TELEMETRY_V4)


#: Forward-only migration hook: ``_MIGRATIONS[N]`` upgrades version N -> N+1.
#: Fresh databases run the v1 script and then every migration, so there is a
#: single creation path and the hook is exercised on every new store.
_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
}

_SHA256_HEX = re.compile(r"^[0-9A-F]{64}$")

# Job statuses that mean "work was in flight when the process died".
_IN_FLIGHT_STATUSES = ("queued", "processing")

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL,
    applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    content_sha256 TEXT    NOT NULL,
    filename       TEXT    NOT NULL,
    byte_size      INTEGER NOT NULL,
    page_count     INTEGER NOT NULL DEFAULT 0,
    uploaded_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_sha ON documents(content_sha256);

CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    document_id    INTEGER REFERENCES documents(id),
    filename       TEXT    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'queued',
    stage          TEXT    NOT NULL DEFAULT 'queued',
    force_ocr      INTEGER NOT NULL DEFAULT 0,
    parse_mode     TEXT    NOT NULL DEFAULT 'auto',
    parse_model    TEXT,
    page_count     INTEGER NOT NULL DEFAULT 0,
    error          TEXT,
    analysis_error TEXT,
    analysis_json  TEXT,
    markdown       TEXT,
    html           TEXT,
    created_at     TEXT    NOT NULL,
    started_at     TEXT,
    finished_at    TEXT
);

CREATE TABLE IF NOT EXISTS packages (
    id               TEXT PRIMARY KEY,
    caller_reference TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS package_members (
    package_id TEXT    NOT NULL REFERENCES packages(id),
    position   INTEGER NOT NULL,
    job_id     TEXT    NOT NULL REFERENCES jobs(id),
    PRIMARY KEY (package_id, position)
);

CREATE TABLE IF NOT EXISTS review_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL REFERENCES jobs(id),
    source_location TEXT NOT NULL,
    decision        TEXT NOT NULL,
    actor           TEXT NOT NULL DEFAULT 'local-analyst',
    decided_at      TEXT NOT NULL,
    prior_state     TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    job_id     TEXT,
    package_id TEXT,
    detail     TEXT,
    at         TEXT NOT NULL
);

-- review_decisions and audit_log are APPEND-ONLY. No code path issues
-- UPDATE or DELETE against them, and these triggers make the contract
-- self-enforcing even for a stray ad-hoc query.
CREATE TRIGGER IF NOT EXISTS review_decisions_no_update
BEFORE UPDATE ON review_decisions
BEGIN SELECT RAISE(ABORT, 'review_decisions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS review_decisions_no_delete
BEFORE DELETE ON review_decisions
BEGIN SELECT RAISE(ABORT, 'review_decisions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _review_detail(source_location: str, decision: str, actor: str, account: int | None) -> dict:
    """A review's audit detail. A location numbers a posting within its account, so a review that named the account
    records it; one that did not records exactly what it always did."""
    detail: dict = {"source_location": source_location, "decision": decision, "actor": actor}
    if account is not None:
        detail["account"] = account
    return detail


def default_data_dir() -> Path:
    """Absolute external override, else the private root's webapp data directory."""
    from ocr.private_artifacts import private_artifact_path, validate_private_artifact_path

    env = os.environ.get("WEBAPP_DATA_DIR", "").strip()
    if env:
        return validate_private_artifact_path(env)
    return private_artifact_path('webapp_data')


class Storage:
    """Schema owner and sole data-access layer for the webapp's durable state.

    One instance per data directory; every method opens its own short-lived
    connection (see the module docstring's concurrency notes).
    """

    def __init__(self, data_dir: str | Path | None = None, *, read_only: bool = False) -> None:
        """``read_only`` (audit 2026-10-13, BE-1): the store the web app falls back to when the normal one cannot be
        opened or written at start-up (a full data volume). It creates, migrates and writes nothing — not at
        construction, and every connection is opened ``mode=ro``, so a write raises instead of landing — and it
        checks nothing either: the caller asks ``schema_version()`` before serving from it."""
        from ocr.private_artifacts import validate_private_artifact_path

        self.read_only = read_only
        self.data_dir = validate_private_artifact_path(data_dir) if data_dir is not None else default_data_dir()
        self.db_path = self.data_dir / "webapp.db"
        if read_only:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # connection / schema
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            # No journal-mode PRAGMA: it needs the write path that failed. The database is already in WAL mode.
            conn = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            has_version_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            if not has_version_table:
                # Fresh stores take the same path as old ones: create v1, then
                # walk the forward migrations — one creation path, and the
                # migration hook is exercised on every new database.
                conn.executescript(_SCHEMA_V1)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (1, utc_now_iso()),
                )
                version = 1
            else:
                row = conn.execute("SELECT version FROM schema_version").fetchone()
                version = int(row["version"]) if row else 0
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"data directory {self.data_dir} holds schema v{version}, but this "
                    f"code only understands v{SCHEMA_VERSION}; downgrades are refused"
                )
            while version < SCHEMA_VERSION:
                migrate = _MIGRATIONS.get(version)
                if migrate is None:
                    raise RuntimeError(
                        f"no forward migration registered from schema v{version}"
                    )
                migrate(conn)
                version += 1
                conn.execute("DELETE FROM schema_version")
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (version, utc_now_iso()),
                )

    def schema_version(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            return int(row["version"]) if row else 0

    # ------------------------------------------------------------------
    # PDF disk store
    # ------------------------------------------------------------------

    def pdf_path(self, sha256_upper: str) -> Path:
        if not _SHA256_HEX.match(sha256_upper or ""):
            raise ValueError("content_sha256 must be 64 uppercase hex characters")
        return self.data_dir / f"{sha256_upper}.pdf"

    def save_pdf(self, sha256_upper: str, pdf_bytes: bytes) -> Path:
        """Write ``<content_sha256>.pdf`` into the data directory (idempotent:
        identical content hashes to an identical name, so an existing file is
        already the right bytes).

        Audit 2026-10-13 (BE-4): written through a temporary file of its own (``tempfile.mkstemp`` beside the target)
        and renamed into place. One fixed ``<sha>.pdf.tmp`` used to be shared by two requests storing the same new
        bytes at once, and one of them failed (about one aligned pair in four on Windows, measured). The rename is
        retried briefly as ``webapp/settings.py`` does (Windows refuses it while a reader has the target open); a
        rename still refused while the target exists means another request stored these same bytes first, which is
        the file this call wanted. The temporary file is always removed."""
        path = self.pdf_path(sha256_upper)
        if path.exists():
            return path
        handle, temporary = tempfile.mkstemp(dir=self.data_dir, prefix=f".{sha256_upper[:16]}-", suffix=".pdf.tmp")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(pdf_bytes)
            try:
                _replace_retrying(temporary, path)
            except PermissionError:
                if not path.exists():
                    raise
        finally:
            Path(temporary).unlink(missing_ok=True)
        return path

    def load_pdf(self, sha256_upper: str) -> bytes | None:
        path = self.pdf_path(sha256_upper)
        try:
            return path.read_bytes()
        except OSError:
            return None

    # ------------------------------------------------------------------
    # artifact cache index (D-3) — payloads live on disk, never here
    # ------------------------------------------------------------------

    def artifact_root(self) -> Path:
        """Directory holding the cached artifact payload files."""
        return self.data_dir / "artifacts"

    def cache_lookup(self, stage: str, cache_key: str) -> dict | None:
        """The index row for a cache key, or None. Read-only: recording the
        hit is a separate call so a lookup whose payload file turns out to be
        missing never inflates the hit counter."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT stage, cache_key, input_sha256, settings_key, format_version,"
                " artifact_path, byte_size, created_at, last_hit_at, hit_count"
                " FROM artifact_cache WHERE stage = ? AND cache_key = ?",
                (stage, cache_key),
            ).fetchone()
            return dict(row) if row else None

    def cache_record(
        self,
        stage: str,
        cache_key: str,
        *,
        input_sha256: str,
        settings_key: str,
        artifact_path: str,
        byte_size: int,
        format_version: int,
    ) -> None:
        """Insert or replace the index row for a written artifact. Replace is
        correct here: the key already pins content + settings + format, so a
        second write of the same key is the same artifact recomputed."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO artifact_cache"
                " (stage, cache_key, input_sha256, settings_key, format_version,"
                "  artifact_path, byte_size, created_at, last_hit_at, hit_count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)",
                (
                    stage,
                    cache_key,
                    input_sha256,
                    settings_key,
                    format_version,
                    artifact_path,
                    byte_size,
                    utc_now_iso(),
                ),
            )

    def cache_record_hit(self, stage: str, cache_key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE artifact_cache SET hit_count = hit_count + 1, last_hit_at = ?"
                " WHERE stage = ? AND cache_key = ?",
                (utc_now_iso(), stage, cache_key),
            )

    def cache_forget(self, stage: str, cache_key: str) -> None:
        """Drop an index row (used when its payload file has gone missing)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "DELETE FROM artifact_cache WHERE stage = ? AND cache_key = ?",
                (stage, cache_key),
            )

    def cache_entries(
        self, stage: str | None = None, *, input_sha256: str | None = None
    ) -> list[dict]:
        clauses = []
        params: list[object] = []
        for column, value in (("stage", stage), ("input_sha256", input_sha256)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT stage, cache_key, input_sha256, settings_key, format_version,"
                " artifact_path, byte_size, created_at, last_hit_at, hit_count"
                f" FROM artifact_cache{where} ORDER BY stage, created_at, cache_key",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def cache_stats(self) -> dict[str, dict[str, int]]:
        """Per-stage entry count, total artifact bytes and accumulated hits —
        the one query the discovery runner needs for its cache report."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT stage, COUNT(*) AS entries, COALESCE(SUM(byte_size), 0) AS bytes,"
                " COALESCE(SUM(hit_count), 0) AS hits FROM artifact_cache GROUP BY stage"
            ).fetchall()
            return {
                row["stage"]: {
                    "entries": int(row["entries"]),
                    "bytes": int(row["bytes"]),
                    "hits": int(row["hits"]),
                }
                for row in rows
            }

    # ------------------------------------------------------------------
    # documents / jobs
    # ------------------------------------------------------------------

    def record_upload(
        self,
        job_id: str,
        *,
        filename: str,
        content_sha256: str | None,
        byte_size: int = 0,
        force_ocr: bool = False,
        parse_mode: str = "auto",
        page_count: int = 0,
    ) -> str | None:
        """Record one upload in ONE transaction: its document row (when it has bytes), its job row and its `upload`
        audit row. Returns the earliest PRIOR job whose document holds the same bytes, or None.

        Audit 2026-10-13 (BE-2): one transaction is what makes that answer final. `duplicate_of` finds a prior
        document only through its job row, and the document and job rows used to be written in two transactions, so
        two concurrent uploads of the same new bytes could commit A's document, then all of B, then A's job: B's
        answer was None at its upload and named A a moment later. Now no document row is ever visible without its
        job row; SQLite has one writer at a time and AUTOINCREMENT ids only grow, so document ids follow commit
        order; and no document or job row is ever deleted or renumbered. Every document with a lower id therefore
        has its job row when this transaction commits, and the answer read here, inside it, is the one
        `duplicate_of` gives at any later time, None included. Retention work that deletes or renumbers documents or
        jobs must revisit this and the `Job.duplicate_of` memo built on it (`webapp/jobs.py`)."""
        with closing(self._connect()) as conn, conn:
            document_id = None
            if content_sha256 is not None:
                cursor = conn.execute(
                    "INSERT INTO documents (content_sha256, filename, byte_size, page_count, uploaded_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (content_sha256, filename, byte_size, page_count, utc_now_iso()),
                )
                document_id = int(cursor.lastrowid)
            conn.execute(
                "INSERT INTO jobs (id, document_id, filename, status, stage, force_ocr,"
                " parse_mode, page_count, created_at) VALUES (?, ?, ?, 'queued', 'queued', ?, ?, ?, ?)",
                (job_id, document_id, filename, int(force_ocr), parse_mode, page_count, utc_now_iso()),
            )
            self._insert_audit(
                conn, "upload", job_id=job_id, detail={"filename": filename, "content_sha256": content_sha256},
            )
            if document_id is None:
                return None
            prior = conn.execute(
                "SELECT jobs.id FROM jobs"
                " JOIN documents ON documents.id = jobs.document_id"
                " WHERE documents.content_sha256 = ? AND documents.id < ?"
                " ORDER BY documents.id LIMIT 1",
                (content_sha256, document_id),
            ).fetchone()
            return prior["id"] if prior else None

    def set_document_profile(self, job_id: str, profile_json: str) -> None:
        """Attach the preflight DocumentProfile (as opaque JSON) to the
        document row belonging to this job (schema v2, O-1)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE documents SET profile_json = ?"
                " WHERE id = (SELECT document_id FROM jobs WHERE id = ?)",
                (profile_json, job_id),
            )

    def document_profile(self, job_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT documents.profile_json FROM jobs"
                " JOIN documents ON documents.id = jobs.document_id"
                " WHERE jobs.id = ?",
                (job_id,),
            ).fetchone()
            if row is None or row["profile_json"] is None:
                return None
            return json.loads(row["profile_json"])

    def duplicate_of(self, job_id: str) -> str | None:
        """The earliest PRIOR job whose document has the same content_sha256,
        or None. 'Prior' is by document insertion order, so the first upload of
        given bytes is never flagged and every re-upload points at it."""
        with closing(self._connect()) as conn:
            own = conn.execute(
                "SELECT documents.id AS document_id, documents.content_sha256 AS sha"
                " FROM jobs JOIN documents ON documents.id = jobs.document_id"
                " WHERE jobs.id = ?",
                (job_id,),
            ).fetchone()
            if own is None:
                return None
            prior = conn.execute(
                "SELECT jobs.id FROM jobs"
                " JOIN documents ON documents.id = jobs.document_id"
                " WHERE documents.content_sha256 = ? AND documents.id < ?"
                " ORDER BY documents.id LIMIT 1",
                (own["sha"], own["document_id"]),
            ).fetchone()
            return prior["id"] if prior else None

    def create_job(
        self,
        job_id: str,
        *,
        filename: str,
        document_id: int | None = None,
        force_ocr: bool = False,
        parse_mode: str = "auto",
        page_count: int = 0,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO jobs (id, document_id, filename, status, stage, force_ocr,"
                " parse_mode, page_count, created_at) VALUES (?, ?, ?, 'queued', 'queued', ?, ?, ?, ?)",
                (job_id, document_id, filename, int(force_ocr), parse_mode, page_count, utc_now_iso()),
            )

    def load_job(self, job_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT jobs.*, documents.content_sha256 AS content_sha256"
                " FROM jobs LEFT JOIN documents ON documents.id = jobs.document_id"
                " WHERE jobs.id = ?",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_job_status(self, job_id: str, status: str, stage: str | None = None) -> None:
        """Persist a status transition (stage follows status unless given).

        Stamps ``started_at`` on the first move to ``processing`` and
        ``finished_at`` on any terminal status, and appends a
        ``status_change`` audit row.
        """
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, stage = ?,"
                " started_at = CASE WHEN ? = 'processing' AND started_at IS NULL THEN ? ELSE started_at END,"
                " finished_at = CASE WHEN ? IN ('done', 'error', 'interrupted') THEN ? ELSE finished_at END"
                " WHERE id = ?",
                (status, stage if stage is not None else status, status, now, status, now, job_id),
            )
            if cursor.rowcount:
                self._insert_audit(conn, "status_change", job_id=job_id, detail={"status": status})

    def set_job_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        with closing(self._connect()) as conn, conn:
            if parse_model is None:
                conn.execute("UPDATE jobs SET stage = ? WHERE id = ?", (stage, job_id))
            else:
                conn.execute(
                    "UPDATE jobs SET stage = ?, parse_model = ? WHERE id = ?",
                    (stage, parse_model, job_id),
                )

    def set_job_result(
        self,
        job_id: str,
        *,
        markdown: str,
        html: str,
        analysis_json: str | None,
        analysis_error: str | None,
        parse_model: str | None,
    ) -> None:
        """Persist the final artifacts. ``analysis_json`` is the verbatim,
        UNMASKED ``report_to_dict`` payload as opaque text — masking is
        applied at serve time in ``webapp/app.py``, never here."""
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = 'done', markdown = ?, html = ?, analysis_json = ?,"
                " analysis_error = ?, parse_model = ?, finished_at = ? WHERE id = ?",
                (markdown, html, analysis_json, analysis_error, parse_model, now, job_id),
            )
            if cursor.rowcount:
                self._insert_audit(conn, "status_change", job_id=job_id, detail={"status": "done"})

    def set_job_error(self, job_id: str, error: str) -> None:
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = 'error', error = ?, finished_at = ? WHERE id = ?",
                (error, now, job_id),
            )
            if cursor.rowcount:
                self._insert_audit(conn, "status_change", job_id=job_id, detail={"status": "error"})

    def set_job_analysis(self, job_id: str, analysis_json: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE jobs SET analysis_json = ? WHERE id = ?", (analysis_json, job_id))

    def record_reanalysis(self, job_id: str, *, analysis_json: str, detail: dict) -> bool:
        """Replace a job's analysis with a re-analysis of its statement (spec §8.6), in ONE transaction: the audit
        row carrying the analysis being replaced, verbatim, is written first, then the job row takes the new analysis
        and loses any old analysis error (a re-analysis that produced an analysis has none). `detail` goes into the
        audit row beside the replaced analysis. Returns False, writing nothing, for a job that does not exist."""
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT analysis_json, analysis_error FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return False
            self._insert_audit(
                conn,
                "reanalysis",
                job_id=job_id,
                detail={
                    **detail,
                    "previous_analysis_json": row["analysis_json"],
                    "previous_analysis_error": row["analysis_error"],
                },
            )
            conn.execute(
                "UPDATE jobs SET analysis_json = ?, analysis_error = NULL WHERE id = ?",
                (analysis_json, job_id),
            )
        return True

    def in_flight_job_ids(self) -> list[str]:
        """The jobs left queued/processing, read only (a read-only start-up shows them interrupted without writing)."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT id FROM jobs WHERE status IN ({','.join('?' * len(_IN_FLIGHT_STATUSES))})",
                _IN_FLIGHT_STATUSES,
            ).fetchall()
            return [row["id"] for row in rows]

    def mark_interrupted_jobs(self, note: str) -> list[str]:
        """Startup re-hydration: any job that was queued/processing when the
        process died is explicitly marked ``interrupted`` with an explanatory
        error — never silently lost. Returns the affected job ids."""
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                f"SELECT id, status FROM jobs WHERE status IN ({','.join('?' * len(_IN_FLIGHT_STATUSES))})",
                _IN_FLIGHT_STATUSES,
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE jobs SET status = 'interrupted', stage = 'interrupted',"
                    " error = ?, finished_at = ? WHERE id = ?",
                    (note, now, row["id"]),
                )
                self._insert_audit(
                    conn,
                    "status_change",
                    job_id=row["id"],
                    detail={"status": "interrupted", "prior_status": row["status"], "note": note},
                )
            return [row["id"] for row in rows]

    # ------------------------------------------------------------------
    # review decisions (append-only)
    # ------------------------------------------------------------------

    def record_review(
        self,
        job_id: str,
        *,
        analysis_json: str,
        source_location: str,
        decision: str,
        actor: str = "local-analyst",
        prior_state_json: str | None = None,
        account: int | None = None,
    ) -> None:
        """Apply an analyst review: the stored analysis mutation, the
        append-only decision row (actor, timestamp, prior state) and the
        audit row land in ONE transaction so no restart can separate them.
        The account the reviewer named (1-based) goes into the audit row; the
        prior state already carries the posting's own account number."""
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE jobs SET analysis_json = ? WHERE id = ?", (analysis_json, job_id))
            conn.execute(
                "INSERT INTO review_decisions (job_id, source_location, decision, actor, decided_at, prior_state)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, source_location, decision, actor, now, prior_state_json),
            )
            self._insert_audit(
                conn,
                "review",
                job_id=job_id,
                detail=_review_detail(source_location, decision, actor, account),
            )

    def record_reviews(
        self,
        job_id: str,
        *,
        analysis_json: str,
        decisions: Sequence[tuple[str, str, str | None, int | None]],
        actor: str = "local-analyst",
    ) -> None:
        """Apply several analyst decisions at once — `(source_location, decision,
        prior_state_json, account)` each: the stored analysis after every one of
        them, and for EACH decision its append-only decision row (actor,
        timestamp, prior state) and its audit row, all in ONE transaction, so a
        batch lands whole or not at all. Each prior state is the posting's record
        before the batch (a stored analysis that still carries legacy revenue
        state names keeps them in every prior state of the batch, where decisions
        made one at a time would see them renamed from the second on)."""
        now = utc_now_iso()
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE jobs SET analysis_json = ? WHERE id = ?", (analysis_json, job_id))
            for source_location, decision, prior_state_json, account in decisions:
                conn.execute(
                    "INSERT INTO review_decisions (job_id, source_location, decision, actor, decided_at, prior_state)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (job_id, source_location, decision, actor, now, prior_state_json),
                )
                self._insert_audit(
                    conn,
                    "review",
                    job_id=job_id,
                    detail=_review_detail(source_location, decision, actor, account),
                )

    def review_history(self, job_id: str) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, job_id, source_location, decision, actor, decided_at, prior_state"
                " FROM review_decisions WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # packages
    # ------------------------------------------------------------------

    def create_package(self, job_ids: list[str], reference: str | None = None) -> str:
        package_id = str(uuid.uuid4())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO packages (id, caller_reference, created_at) VALUES (?, ?, ?)",
                (package_id, reference, utc_now_iso()),
            )
            conn.executemany(
                "INSERT INTO package_members (package_id, position, job_id) VALUES (?, ?, ?)",
                [(package_id, position, job_id) for position, job_id in enumerate(job_ids)],
            )
            self._insert_audit(
                conn,
                "package_created",
                package_id=package_id,
                detail={"job_ids": job_ids, "reference": reference},
            )
        return package_id

    def package_member_ids(self, package_id: str) -> list[str] | None:
        """Ordered member job ids, or None if the package does not exist."""
        with closing(self._connect()) as conn:
            package = conn.execute(
                "SELECT id FROM packages WHERE id = ?", (package_id,)
            ).fetchone()
            if package is None:
                return None
            rows = conn.execute(
                "SELECT job_id FROM package_members WHERE package_id = ? ORDER BY position",
                (package_id,),
            ).fetchall()
            return [row["job_id"] for row in rows]

    # ------------------------------------------------------------------
    # audit log (append-only)
    # ------------------------------------------------------------------

    def _insert_audit(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        *,
        job_id: str | None = None,
        package_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO audit_log (event_type, job_id, package_id, detail, at) VALUES (?, ?, ?, ?, ?)",
            (
                event_type,
                job_id,
                package_id,
                json.dumps(detail) if detail is not None else None,
                utc_now_iso(),
            ),
        )

    def append_audit(
        self,
        event_type: str,
        *,
        job_id: str | None = None,
        package_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            self._insert_audit(conn, event_type, job_id=job_id, package_id=package_id, detail=detail)

    def append_telemetry(self, record: dict) -> None:
        """Store one H-3 telemetry record (schema v4).

        The typed columns are projections of ``record``; the JSON blob is the
        definition. ``INSERT OR IGNORE`` on the unique ``record_id`` makes a
        re-emitted record idempotent rather than a constraint error — telemetry
        must never be able to fail the work it describes.
        """
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO telemetry (
                    record_id, run_id, job_id, content_sha256, emitted_at,
                    telemetry_version, emitter, outcome_class, dispatch_outcome,
                    parser_id, source_path, record
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["record_id"],
                    record["run_id"],
                    record.get("job_id"),
                    record["document"]["content_sha256"],
                    record["emitted_at"],
                    record["telemetry_version"],
                    record["emitter"],
                    record["outcome"]["class"],
                    record["dispatch"]["outcome"],
                    record["dispatch"]["parser_id"],
                    record["source"]["path"],
                    json.dumps(record, sort_keys=True, ensure_ascii=False),
                ),
            )

    def telemetry_records(self, run_id: str | None = None) -> list[dict]:
        """Every stored record, parsed, oldest first."""
        where, params = ("", [])
        if run_id is not None:
            where, params = (" WHERE run_id = ?", [run_id])
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT record FROM telemetry{where} ORDER BY id", params
            ).fetchall()
        return [json.loads(row["record"]) for row in rows]

    def telemetry_coverage(self, run_id: str | None = None) -> list[dict]:
        """Grouped counts straight from the indexed columns — no JSON parsing."""
        where, params = ("", [])
        if run_id is not None:
            where, params = (" WHERE run_id = ?", [run_id])
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT dispatch_outcome, outcome_class, COUNT(*) AS n
                FROM telemetry{where}
                GROUP BY dispatch_outcome, outcome_class
                ORDER BY n DESC, outcome_class
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def audit_events(
        self,
        event_type: str | None = None,
        *,
        job_id: str | None = None,
        package_id: str | None = None,
    ) -> list[dict]:
        clauses = []
        params: list[object] = []
        for column, value in (
            ("event_type", event_type),
            ("job_id", job_id),
            ("package_id", package_id),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT id, event_type, job_id, package_id, detail, at FROM audit_log{where} ORDER BY id",
                params,
            ).fetchall()
            return [dict(row) for row in rows]
