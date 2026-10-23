"""A full data volume refuses new work and never stops the server from starting (audit 2026-10-13, BE-1).

* The floor: an upload (counting the batch's own bytes) or a Re-analyze that would leave the data volume below
  `MIN_FREE_BYTES` is refused with 507 and fixed text before anything is written. Validation still answers first; a
  free-space figure that cannot be read never refuses work; a malformed `WEBAPP_MIN_FREE_MB` falls back to the default.
* The start: on 2026-10-06 the demo's full volume made the import of `webapp.app` raise (`disk I/O error` at the
  journal-mode PRAGMA), so the host restarted the server until it gave up. Now an operational database or filesystem
  failure at start-up opens the store read-only: saved statements are served, every write is refused with 503 and
  fixed text, in-flight jobs show interrupted. A store that cannot be read either serves only the page.

All data is fabricated (SAMPLE / CONTOSO); nothing reads a statement.
"""
from __future__ import annotations

import errno
import io
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from collections import namedtuple
from contextlib import closing
from pathlib import Path

import pytest

from webapp import app as app_module
from webapp import intake as intake_module
from webapp.jobs import JobStore
from webapp.storage import SCHEMA_VERSION, Storage

ROOT = Path(__file__).resolve().parents[1]
_Usage = namedtuple("_Usage", "total used free")


def _sample_pdf(size: int = 0) -> bytes:
    return b"%PDF-SAMPLE-" + uuid.uuid4().hex.encode() + b"x" * size


def _counts(storage: Storage) -> tuple[int, int, int, int]:
    with closing(sqlite3.connect(storage.db_path)) as conn:
        rows = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("jobs", "documents", "audit_log"))
    return rows + (len(list(storage.data_dir.glob("*.pdf"))),)


@pytest.fixture
def floor(monkeypatch):
    """A 1,000-byte floor and a settable free-space figure."""
    free = {"bytes": 10**12}
    monkeypatch.setattr(app_module, "MIN_FREE_BYTES", 1000)
    monkeypatch.setattr(app_module.shutil, "disk_usage", lambda path: _Usage(10**13, 0, free["bytes"]))
    monkeypatch.setattr("webapp.intake.pdf_page_count", lambda pdf_bytes: 1)
    queued: list[str] = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda job_id, *args: queued.append(job_id))
    free["queued"] = queued
    return free


def _upload(*contents: bytes):
    client = app_module.app.test_client()
    data = {"files": [(io.BytesIO(content), f"sample-{n}.pdf") for n, content in enumerate(contents)]}
    return client.post("/upload", data=data, content_type="multipart/form-data")


# ---------------------------------------------------------------------------------------------------------------------
# The floor
# ---------------------------------------------------------------------------------------------------------------------


def test_an_upload_below_the_floor_is_refused_before_anything_is_written(floor):
    floor["bytes"] = 999
    before = _counts(app_module.store.storage)
    response = _upload(_sample_pdf(), _sample_pdf())
    assert response.status_code == 507
    assert response.get_json() == {"error": intake_module.STORAGE_NEARLY_FULL}
    assert _counts(app_module.store.storage) == before
    assert floor["queued"] == []


def test_the_batch_counts_against_the_floor(floor):
    content = _sample_pdf(500)
    floor["bytes"] = 1000 + len(content) - 1
    assert _upload(content).status_code == 507
    floor["bytes"] = 1000 + len(content)  # exactly the floor left after the write: accepted
    response = _upload(content)
    assert response.status_code == 200
    assert floor["queued"] == [response.get_json()["jobs"][0]["id"]]


def test_an_unreadable_free_space_figure_never_refuses(floor, monkeypatch):
    def unreadable(path):
        raise OSError("statvfs failed")

    monkeypatch.setattr(app_module.shutil, "disk_usage", unreadable)
    assert _upload(_sample_pdf()).status_code == 200


def test_validation_still_answers_first(floor):
    floor["bytes"] = 0
    response = _upload(b"not a pdf at all")
    assert response.status_code == 400
    assert response.get_json()["error"] == "file is not a PDF"


def test_the_floor_reads_the_data_volume(floor, monkeypatch):
    seen = []
    monkeypatch.setattr(app_module.shutil, "disk_usage", lambda path: seen.append(Path(path)) or _Usage(1, 0, 10**12))
    assert _upload(_sample_pdf()).status_code == 200
    assert seen == [Path(app_module.store.storage.data_dir)]


def _done_job() -> str:
    job = app_module.store.create("sample.pdf", page_count=1, pdf_bytes=_sample_pdf())
    app_module.store.set_result(job.id, "# SAMPLE", "<h1>SAMPLE</h1>", {"statement": {"bank": "CONTOSO"}}, None,
                                "test-model")
    return job.id


def test_a_reanalysis_below_the_floor_writes_nothing(floor, monkeypatch):
    job_id = _done_job()
    floor["bytes"] = 999
    monkeypatch.setattr("webapp.app.rerun_analysis", lambda *a, **k: pytest.fail("re-analysis ran"))
    before = _counts(app_module.store.storage)
    response = app_module.app.test_client().post(f"/analysis/{job_id}/reanalyze", json={})
    assert response.status_code == 507
    assert response.get_json() == {"error": app_module.REANALYSIS_NOT_SAVED,
                                   "reason": app_module.STORAGE_NEARLY_FULL_REASON}
    assert _counts(app_module.store.storage) == before


def test_a_reanalysis_still_answers_its_own_refusals_first(floor):
    floor["bytes"] = 0
    response = app_module.app.test_client().post("/analysis/no-such-job/reanalyze", json={})
    assert response.status_code == 404


@pytest.mark.parametrize(("raw", "megabytes"), [
    (None, 256), ("", 256), ("  ", 256), ("0", 0), ("512", 512), (" 64 ", 64),
    ("256MB", 256), ("-1", 256), ("1.5", 256), ("lots", 256),
])
def test_the_floor_setting_is_read_defensively(raw, megabytes):
    assert app_module._min_free_bytes(raw) == megabytes * 1024 * 1024


def test_a_malformed_floor_setting_never_stops_the_server_from_starting(tmp_path):
    env = {**os.environ, "WEBAPP_DATA_DIR": str(tmp_path / "data"), "WEBAPP_MIN_FREE_MB": "256MB",
           "PYTHONDONTWRITEBYTECODE": "1"}
    script = "import webapp.app as a; print(a.MIN_FREE_BYTES, a.STORE_STATE)"
    done = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.split() == [str(256 * 1024 * 1024), "None"]
    assert "WEBAPP_MIN_FREE_MB" in done.stderr


# ---------------------------------------------------------------------------------------------------------------------
# The start
# ---------------------------------------------------------------------------------------------------------------------


@pytest.fixture
def saved(tmp_path, monkeypatch):
    """A data directory holding one finished job and one left queued by a previous process."""
    data = tmp_path / "data"
    store = JobStore(Storage(data))
    done = store.create("contoso.pdf", page_count=1, pdf_bytes=_sample_pdf())
    store.set_result(done.id, "# SAMPLE", "<h1>SAMPLE</h1>", {"statement": {"bank": "CONTOSO"}}, None, "test-model")
    queued = store.create("fabrikam.pdf", page_count=1, pdf_bytes=_sample_pdf())
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(data))
    return {"data": data, "done": done.id, "queued": queued.id}


#: SQLite result codes as the C layer sets them on its exceptions (`sqlite_errorcode`): SQLITE_IOERR_SHMSIZE (the
#: extended code a WAL database's shared-memory file raises when it cannot grow), SQLITE_FULL, SQLITE_BUSY.
SQLITE_IOERR_SHMSIZE, SQLITE_FULL, SQLITE_BUSY = 4874, 13, 5


def _sqlite_error(message: str, code: int) -> sqlite3.OperationalError:
    error = sqlite3.OperationalError(message)
    error.sqlite_errorcode = code
    return error


def _fail_writable_connections(monkeypatch, message="disk I/O error", code=SQLITE_IOERR_SHMSIZE):
    real = Storage._connect

    def connect(self):
        if not self.read_only:
            raise _sqlite_error(message, code)
        return real(self)

    monkeypatch.setattr(Storage, "_connect", connect)


def _row_status(data: Path, job_id: str) -> str:
    with closing(sqlite3.connect(data / "webapp.db")) as conn:
        return conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]


def test_a_store_that_cannot_be_written_opens_read_only(saved, monkeypatch):
    _fail_writable_connections(monkeypatch)
    store, interrupted, state = app_module._open_store()
    assert state == app_module.STORE_READ_ONLY
    assert store.storage.read_only is True
    assert interrupted == [saved["queued"]]
    assert store.get(saved["done"]).analysis == {"statement": {"bank": "CONTOSO"}}
    shown = store.get(saved["queued"])
    assert (shown.status, shown.stage) == ("interrupted", "interrupted")
    assert shown.error.startswith("interrupted:")
    assert _row_status(saved["data"], saved["queued"]) == "queued"  # nothing was written
    with pytest.raises(sqlite3.OperationalError):
        store.storage.append_audit("export", job_id=saved["done"])  # a write cannot land


def test_a_full_disk_while_marking_interrupted_jobs_opens_read_only(saved, monkeypatch):
    def full(self, note):
        raise _sqlite_error("database or disk is full", SQLITE_FULL)

    monkeypatch.setattr(Storage, "mark_interrupted_jobs", full)
    store, interrupted, state = app_module._open_store()
    assert state == app_module.STORE_READ_ONLY
    assert interrupted == [saved["queued"]]
    assert _row_status(saved["data"], saved["queued"]) == "queued"


def test_a_full_filesystem_opens_read_only(saved, monkeypatch):
    def no_space(self):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Storage, "_ensure_schema", no_space)
    assert app_module._open_store()[2] == app_module.STORE_READ_ONLY


def test_a_locked_database_still_stops_the_start(saved, monkeypatch):
    """Not a volume failure: the start fails as it always did, so the host's restart can clear it, rather than the
    server staying read-only until someone restarts it."""
    _fail_writable_connections(monkeypatch, "database is locked", SQLITE_BUSY)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        app_module._open_store()


def test_a_permission_problem_still_stops_the_start(saved, monkeypatch):
    def denied(self):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Storage, "_ensure_schema", denied)
    with pytest.raises(PermissionError):
        app_module._open_store()


def test_the_volume_failures_are_read_from_sqlites_own_result_codes(tmp_path):
    """Real errors from the C layer: a database that cannot grow (SQLITE_FULL) and a file that cannot be opened
    (SQLITE_CANTOPEN) are volume failures; a database another connection holds (SQLITE_BUSY) is not."""
    database = tmp_path / "sample.db"
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("CREATE TABLE sample (value TEXT)")
    with closing(sqlite3.connect(database)) as conn:
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        conn.execute(f"PRAGMA max_page_count = {pages}")
        with pytest.raises(sqlite3.OperationalError) as full:
            with conn:
                conn.executemany("INSERT INTO sample VALUES (?)", [("SAMPLE" * 500,)] * 50)
    assert app_module._volume_failure(full.value)
    with pytest.raises(sqlite3.OperationalError) as cannot_open:
        sqlite3.connect(f"{(tmp_path / 'missing' / 'sample.db').as_uri()}?mode=ro", uri=True)
    assert app_module._volume_failure(cannot_open.value)
    holder = sqlite3.connect(database, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with closing(sqlite3.connect(database, timeout=0, isolation_level=None)) as other:
            with pytest.raises(sqlite3.OperationalError) as busy:
                other.execute("BEGIN IMMEDIATE")
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert not app_module._volume_failure(busy.value)
    assert not app_module._volume_failure(ValueError("not storage"))


class _Tripwire(sqlite3.OperationalError):
    """An exception whose text cannot be read: `_volume_failure` is a declared privacy boundary helper
    (tests/test_worker_privacy.py) on the promise that it reads only the integer codes."""

    def __str__(self):
        raise AssertionError("the message was read")

    __repr__ = __str__

    @property
    def args(self):
        raise AssertionError("the args were read")


class _OsTripwire(OSError):
    def __str__(self):
        raise AssertionError("the message was read")

    __repr__ = __str__


def test_the_volume_check_reads_only_the_integer_codes():
    full = _Tripwire.__new__(_Tripwire)
    full.sqlite_errorcode = SQLITE_FULL
    busy = _Tripwire.__new__(_Tripwire)
    busy.sqlite_errorcode = SQLITE_BUSY
    no_space = _OsTripwire(errno.ENOSPC, "SAMPLE-SECRET")
    assert app_module._volume_failure(full) is True
    assert app_module._volume_failure(busy) is False
    assert app_module._volume_failure(no_space) is True
    assert app_module._volume_failure(_Tripwire.__new__(_Tripwire)) is False  # no code at all: not a volume failure


def test_a_store_that_cannot_be_read_either_is_unavailable(saved, monkeypatch):
    def connect(self):
        raise _sqlite_error("disk I/O error", SQLITE_IOERR_SHMSIZE)

    monkeypatch.setattr(Storage, "_connect", connect)
    _store, interrupted, state = app_module._open_store()
    assert (state, interrupted) == (app_module.STORE_UNAVAILABLE, [])


def test_a_normal_start_is_unchanged(saved):
    store, interrupted, state = app_module._open_store()
    assert state is None
    assert store.storage.read_only is False
    assert interrupted == [saved["queued"]]
    assert _row_status(saved["data"], saved["queued"]) == "interrupted"


def test_a_schema_the_code_does_not_understand_still_stops_the_start(saved):
    with closing(sqlite3.connect(saved["data"] / "webapp.db")) as conn, conn:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
    with pytest.raises(RuntimeError, match="downgrades are refused"):
        app_module._open_store()


def _degraded(monkeypatch, saved, state):
    _fail_writable_connections(monkeypatch)
    store, _ids, opened_state = app_module._open_store()
    assert opened_state == app_module.STORE_READ_ONLY
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "STORE_STATE", state)
    return app_module.app.test_client()


def test_a_read_only_start_serves_saved_statements_and_refuses_every_write(saved, monkeypatch):
    client = _degraded(monkeypatch, saved, app_module.STORE_READ_ONLY)
    refusal = {"error": app_module.STORAGE_READ_ONLY_ERROR}
    assert client.get("/").status_code == 200
    assert client.get(f"/status/{saved['done']}").get_json()["status"] == "done"
    assert client.get(f"/status/{saved['queued']}").get_json()["status"] == "interrupted"
    assert client.get(f"/analysis/{saved['done']}").status_code == 200
    assert client.get("/api/settings").status_code == 200
    for response in (
        client.post("/upload", data={"files": (io.BytesIO(_sample_pdf()), "s.pdf")}, content_type="multipart/form-data"),
        client.post(f"/analysis/{saved['done']}/reanalyze", json={}),
        client.post("/api/settings", json={"nsf_carry_over": True}),
        client.post("/package", json={"job_ids": [saved["done"]]}),
        client.get(f"/download/{saved['done']}/md"),
    ):
        assert (response.status_code, response.get_json()) == (503, refusal)
    assert _row_status(saved["data"], saved["queued"]) == "queued"


def test_an_unavailable_start_serves_only_the_page(saved, monkeypatch):
    client = _degraded(monkeypatch, saved, app_module.STORE_UNAVAILABLE)
    assert client.get("/").status_code == 200
    response = client.get(f"/status/{saved['done']}")
    assert (response.status_code, response.get_json()) == (503, {"error": app_module.STORAGE_UNAVAILABLE_ERROR})


def test_the_server_starts_and_serves_when_its_volume_cannot_be_written(saved):
    """The 2026-10-06 outage, end to end in a fresh process: `PRAGMA journal_mode=WAL` raises `disk I/O error` on
    every connection, the error the demo's log recorded. Importing the app used to raise there; now it starts
    read-only (a read-only connection runs no such PRAGMA) and answers."""
    env = {**os.environ, "WEBAPP_DATA_DIR": str(saved["data"]), "PYTHONDONTWRITEBYTECODE": "1"}
    script = "\n".join([
        "import sqlite3, json",
        "real_connect = sqlite3.connect",
        "class Failing:",
        "    def __init__(self, conn):",
        "        object.__setattr__(self, 'conn', conn)",
        "    def __getattr__(self, name):",
        "        return getattr(self.conn, name)",
        "    def __setattr__(self, name, value):",
        "        setattr(self.conn, name, value)",
        "    def execute(self, sql, *args):",
        "        if sql.strip().upper().startswith('PRAGMA JOURNAL_MODE'):",
        "            error = sqlite3.OperationalError('disk I/O error')",
        f"            error.sqlite_errorcode = {SQLITE_IOERR_SHMSIZE}",
        "            raise error",
        "        return self.conn.execute(sql, *args)",
        "    def __enter__(self):",
        "        self.conn.__enter__()",
        "        return self",
        "    def __exit__(self, *exc):",
        "        return self.conn.__exit__(*exc)",
        "sqlite3.connect = lambda *a, **k: Failing(real_connect(*a, **k))",
        "import webapp.app as app",
        "client = app.app.test_client()",
        f"done = client.get('/status/{saved['done']}')",
        "upload = client.post('/upload', data={})",
        "print(json.dumps([app.STORE_STATE, done.status_code, done.get_json()['status'], upload.status_code]))",
    ])
    finished = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=300)
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert json.loads(finished.stdout.strip().splitlines()[-1]) == ["read_only", 200, "done", 503]
