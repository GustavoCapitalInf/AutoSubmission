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
v1 ships fresh. NO importer exists because no durable data predates this
task — the previous store was purely in-memory, so "migrating" it is
meaningless; that IS the migration/back-compat answer for v1. The
``schema_version`` table records the schema in force and ``_MIGRATIONS``
is the forward-only hook: to move from version N to N+1, register a
callable under ``_MIGRATIONS[N]``. Downgrades are refused. The analysis
result payload is stored as OPAQUE JSON text (the ``report_to_dict``
output, verbatim and UNMASKED — masking stays a serve-time concern in
``webapp/app.py``), so ``analysis/`` contract changes never require a
schema migration here.

Content hash convention (shared with O-1 — do not change unilaterally)
----------------------------------------------------------------------
``content_sha256(pdf_bytes)`` = UPPERCASE hex SHA-256 of the raw PDF bytes,
exactly the convention of ``corpus_gate.sha256_upper``. PDF bytes live on
disk as ``<content_sha256>.pdf`` inside the data directory — never inside
SQLite, and released from RAM once a job reaches a terminal state.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = 1

#: Forward-only migration hook: ``_MIGRATIONS[N]`` upgrades version N -> N+1.
#: Empty for v1 — see the module docstring for why no importer exists.
_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}

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


def content_sha256(data: bytes) -> str:
    """UPPERCASE hex SHA-256 of the raw PDF bytes.

    This is the O-1 handshake definition and matches
    ``corpus_gate.sha256_upper`` exactly: ``hashlib.sha256(data).hexdigest().upper()``.
    """
    return hashlib.sha256(data).hexdigest().upper()


def default_data_dir() -> Path:
    """``WEBAPP_DATA_DIR`` env override, else ``webapp_data/`` at repo root."""
    env = os.environ.get("WEBAPP_DATA_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "webapp_data"


class Storage:
    """Schema owner and sole data-access layer for the webapp's durable state.

    One instance per data directory; every method opens its own short-lived
    connection (see the module docstring's concurrency notes).
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "webapp.db"
        self._ensure_schema()

    # ------------------------------------------------------------------
    # connection / schema
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
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
                conn.executescript(_SCHEMA_V1)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, utc_now_iso()),
                )
                return
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
        already the right bytes)."""
        path = self.pdf_path(sha256_upper)
        if not path.exists():
            tmp = path.with_suffix(".pdf.tmp")
            tmp.write_bytes(pdf_bytes)
            os.replace(tmp, path)
        return path

    def load_pdf(self, sha256_upper: str) -> bytes | None:
        path = self.pdf_path(sha256_upper)
        try:
            return path.read_bytes()
        except OSError:
            return None

    # ------------------------------------------------------------------
    # documents / jobs
    # ------------------------------------------------------------------

    def record_document(
        self, sha256_upper: str, filename: str, byte_size: int, page_count: int
    ) -> int:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO documents (content_sha256, filename, byte_size, page_count, uploaded_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (sha256_upper, filename, byte_size, page_count, utc_now_iso()),
            )
            return int(cursor.lastrowid)

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
    ) -> None:
        """Apply an analyst review: the stored analysis mutation, the
        append-only decision row (actor, timestamp, prior state) and the
        audit row land in ONE transaction so no restart can separate them."""
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
                detail={"source_location": source_location, "decision": decision, "actor": actor},
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
