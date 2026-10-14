"""WORKER-PRIVACY (W3 #WORKERPRIV) — `str(e)` never reaches the durable store.

`analysis/pipeline.py` carries the law already: every crash on the
deterministic seam is reduced to the exception's CLASS NAME, never its
message, because a message routinely quotes the cell of the document that
provoked it (H3_SCHEMA I1, W3 §MG-C2 D1). That comment names `webapp/worker.py`
as the reason the law exists — and the worker held the two holes it names:

* `_analyze_doc` returned `str(e)` as the job's ``analysis_error``, and
* `run_job` stored `str(e)` as the job's ``error``.

Both columns are DURABLE (`webapp/storage.py`'s ``jobs`` table, through
`JobStore`) and both are served verbatim to the browser by ``/status``,
``/result`` and ``/analysis``. A refusal that quoted an account number was
published, survived a restart, and sat in front of a user.

These tests pin the BOUNDARY, not any one exception: what happens when the
analysis raises, and when anything under `run_job` raises, whatever it is and
whatever it says.
"""
from __future__ import annotations

import ast
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import run_job

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: The fragment of the statement an exception message quotes. Account-shaped,
#: because that is the shape MG-C2 measured escaping.
PROVOKING_TOKEN = "4021-9987-3315-0042"

#: The same fact in a form that CANNOT be confused with the document's own
#: copy. The durable store legitimately holds the statement text — that is the
#: accepted, separately-governed `/markdown` residual exposure (Wave 0, closed
#: by authentication and not by redaction) — so a WHOLE-DATABASE sweep needs a
#: token that exists only inside the exception message. It is deliberately not
#: printed anywhere in `DOCUMENT_MARKDOWN`.
EXCEPTION_ONLY_SENTINEL = "SENTINEL-EXCEPTION-TEXT-a7f31c9e"

#: A realistic poisoned message: the quoted cell, plus the sweep sentinel.
POISONED_MESSAGE = (
    f"invalid literal for int() with base 10: '{PROVOKING_TOKEN}' "
    f"[{EXCEPTION_ONLY_SENTINEL}]"
)

DOCUMENT_MARKDOWN = f"""<!-- source: seam.pdf | pages: 1 | model: native -->

--- Page 1 ---
ACCOUNT {PROVOKING_TOKEN}
Beginning Balance 1,000.00
02/03 CARD PURCHASE 100.00 900.00
Ending Balance 900.00
"""

#: The literal `analysis/pipeline.py` raises when the deterministic path finds
#: no claiming parser, and the string `webapp/static/app.js` matches to give
#: the user the one actionable answer that mode produces.
DECLARED_REFUSAL = "no deterministic parser matched this statement"


class _FakeDoc:
    model = "test-model"
    pages = [DOCUMENT_MARKDOWN]

    def to_markdown(self) -> str:
        return DOCUMENT_MARKDOWN


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))


def _read_ok(monkeypatch) -> None:
    """The intake ladder succeeds, so only the analysis can fail."""
    monkeypatch.setattr(
        "webapp.worker.parse_statement",
        lambda pdf_bytes, source_file="", **kwargs: _FakeDoc(),
    )


def _analysis_raises(monkeypatch, exc: BaseException) -> None:
    def boom(markdown, parse_mode="auto", **kwargs):
        raise exc

    monkeypatch.setattr("webapp.worker.analyze_document", boom)


def _run(store, filename: str = "s.pdf", *, parse_mode: str = "auto"):
    # Distinct bytes per job: the D-3 artifact cache keys on the content hash,
    # so two jobs over identical bytes in one store would serve the second from
    # the first's cached read and never reach the code under test.
    pdf_bytes = f"%PDF-fake-{filename}".encode()
    job = store.create(filename)
    run_job(job.id, pdf_bytes, filename, store, parse_mode=parse_mode)
    return store.get(job.id)


def _run_deterministic(store, filename: str = "s.pdf"):
    return _run(store, filename, parse_mode="deterministic")


# ---------------------------------------------------------------------------
# Site 1 — the analysis boundary (`_analyze_doc`), durable `analysis_error`
# ---------------------------------------------------------------------------


def test_the_analysis_boundary_does_not_publish_the_exception_message(monkeypatch, store):
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, ValueError(POISONED_MESSAGE))

    fetched = _run(store)

    assert fetched.status == "done"          # the document still publishes
    assert fetched.analysis is None
    published = fetched.analysis_error or ""
    assert PROVOKING_TOKEN not in published
    assert EXCEPTION_ONLY_SENTINEL not in published
    assert "invalid literal" not in published


def test_the_analysis_boundary_names_the_class_and_the_stage(monkeypatch, store):
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, ValueError(POISONED_MESSAGE))

    fetched = _run(store)

    assert fetched.analysis_error == (
        "analysis stage failed: ValueError "
        "(message withheld; an exception message can quote statement text)"
    )


@pytest.mark.parametrize("exc", [
    KeyError(PROVOKING_TOKEN),
    TypeError(POISONED_MESSAGE),
    AttributeError(POISONED_MESSAGE),
    IndexError(POISONED_MESSAGE),
    UnicodeDecodeError("utf-8", PROVOKING_TOKEN.encode(), 0, 1, POISONED_MESSAGE),
], ids=lambda e: type(e).__name__)
def test_the_analysis_boundary_reduces_every_exception_class(monkeypatch, store, exc):
    """The property is about the SEAM, so the class is not part of it."""
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, exc)

    fetched = _run(store)

    published = fetched.analysis_error or ""
    assert published.startswith(f"analysis stage failed: {type(exc).__name__}")
    assert PROVOKING_TOKEN not in published
    assert EXCEPTION_ONLY_SENTINEL not in published


def test_a_successful_job_publishes_no_error_at_all(monkeypatch, store):
    """The control half: this cell cannot invent an error on a healthy job."""
    _read_ok(monkeypatch)
    monkeypatch.setattr("webapp.worker.analyze_document",
                        lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json",
                        lambda document: {"quality": {"level": "transaction_level"}})

    fetched = _run(store)

    assert fetched.status == "done"
    assert fetched.analysis_error is None
    assert fetched.error is None


# ---------------------------------------------------------------------------
# Site 2 — the job boundary (`run_job`), durable `error`
# ---------------------------------------------------------------------------


def test_the_job_boundary_does_not_publish_the_exception_message(monkeypatch, store):
    def boom(pdf_bytes, source_file="", **kwargs):
        raise RuntimeError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    fetched = _run(store)

    assert fetched.status == "error"
    published = fetched.error or ""
    assert PROVOKING_TOKEN not in published
    assert EXCEPTION_ONLY_SENTINEL not in published
    assert "invalid literal" not in published
    assert published == (
        "reading stage failed: RuntimeError "
        "(message withheld; an exception message can quote statement text)"
    )


def test_the_job_boundary_names_the_preflight_stage(monkeypatch, store):
    """The phase tracker starts before the ladder, so a preflight crash is not
    mislabelled as a read."""
    def boom(pdf_bytes):
        raise ValueError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.inspect_pdf", boom)

    fetched = _run(store)

    assert fetched.status == "error"
    assert fetched.error == (
        "preflight stage failed: ValueError "
        "(message withheld; an exception message can quote statement text)"
    )
    assert EXCEPTION_ONLY_SENTINEL not in (fetched.error or "")


def test_the_job_boundary_names_the_analysis_stage(monkeypatch, store):
    """A raise from the un-guarded half of `_analyze_doc` (the markdown render
    and the report stage sit OUTSIDE its `try`) reaches the job boundary, and
    the phase must have advanced past `reading` by then."""
    _read_ok(monkeypatch)

    def boom(markdown, title=""):
        raise RuntimeError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.markdown_to_html", boom)

    fetched = _run(store)

    assert fetched.status == "error"
    assert fetched.error == (
        "analysis stage failed: RuntimeError "
        "(message withheld; an exception message can quote statement text)"
    )


def test_the_telemetry_record_still_carries_only_the_class_name(monkeypatch, store):
    """Pre-existing and compliant (H3_SCHEMA I1), pinned here so the sweep
    below is not vacuous: a record IS written for a failed job, and it names
    the class and nothing else."""
    def boom(pdf_bytes, source_file="", **kwargs):
        raise RuntimeError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    _run(store)

    records = store.storage.telemetry_records()
    assert len(records) == 1
    assert records[0]["outcome"]["error_type"] == "RuntimeError"
    assert PROVOKING_TOKEN not in str(records[0])
    assert EXCEPTION_ONLY_SENTINEL not in str(records[0])


# ---------------------------------------------------------------------------
# The sweep — the sentinel appears NOWHERE in the durable store
# ---------------------------------------------------------------------------


def _every_durable_string(storage) -> str:
    """Every cell of every table, plus the raw bytes of every file the store
    owns (the database itself, its journal, the PDF store, cache artifacts).

    Deliberately schema-blind: it enumerates `sqlite_master` rather than the
    columns this cell happens to know about, so a table added later is swept
    without anyone remembering to add it here.
    """
    parts: list[str] = []
    with closing(sqlite3.connect(str(storage.db_path))) as conn:
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        assert "jobs" in tables and "telemetry" in tables, tables
        for table in tables:
            for row in conn.execute(f"SELECT * FROM {table}"):  # noqa: S608 - names from sqlite_master
                parts.extend("" if value is None else str(value) for value in row)
    for path in sorted(storage.data_dir.rglob("*")):
        if path.is_file():
            parts.append(str(path))
            parts.append(path.read_bytes().decode("utf-8", errors="replace"))
    return "\n".join(parts)


def test_the_sentinel_appears_nowhere_in_the_durable_store(monkeypatch, store):
    """The invariant the card exists for, over BOTH boundaries at once.

    Two poisoned jobs against one store — one that dies in the analysis and
    one that dies in the read — then the whole data directory is searched for
    a token that only ever existed inside an exception message.
    """
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, ValueError(POISONED_MESSAGE))
    analysis_job = _run(store, "analysis-failure.pdf")

    def boom(pdf_bytes, source_file="", **kwargs):
        raise RuntimeError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.parse_statement", boom)
    read_job = _run(store, "read-failure.pdf")

    assert analysis_job.status == "done" and analysis_job.analysis_error
    assert read_job.status == "error" and read_job.error

    blob = _every_durable_string(store.storage)
    # The sweep is live: the document's own text IS in the store (accepted
    # `/markdown` exposure), so a sweep that found nothing at all would prove
    # nothing about the exception channel.
    assert PROVOKING_TOKEN in blob
    assert EXCEPTION_ONLY_SENTINEL not in blob
    assert "invalid literal" not in blob


def test_no_package_export_carries_the_exception_text(monkeypatch):
    """THE SINK THE CARD DID NOT NAME.

    `_package_analysis` copies BOTH columns into every member's `doc_row`
    (`webapp/app.py:880-881`) and `_package_rows` then walks EVERY key of that
    dict into the CSV and the XLSX. `_masked` does not touch them —
    `_ACCOUNT_KEYS` is `{account, account_number}` — so the leak was not merely
    rendered in a browser: it was written into the spreadsheet an underwriter
    downloads and keeps. `_escaped_rows` would have neutralised it as a formula
    and passed it through as text.

    Driven through the real Flask app and the real export routes, because the
    columns being clean at the store is not the same claim as the export being
    clean.
    """
    import io
    import zipfile

    from webapp.app import app as flask_app
    from webapp.app import store as app_store

    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, ValueError(POISONED_MESSAGE))
    analysis_job = app_store.create("export-analysis-failure.pdf")
    run_job(analysis_job.id, b"%PDF-export-analysis-failure",
            "export-analysis-failure.pdf", app_store)

    def boom(pdf_bytes, source_file="", **kwargs):
        raise RuntimeError(POISONED_MESSAGE)

    monkeypatch.setattr("webapp.worker.parse_statement", boom)
    read_job = app_store.create("export-read-failure.pdf")
    run_job(read_job.id, b"%PDF-export-read-failure",
            "export-read-failure.pdf", app_store)

    assert app_store.get(analysis_job.id).analysis_error
    assert app_store.get(read_job.id).error

    client = flask_app.test_client()
    ids = f"{analysis_job.id},{read_job.id}"

    for fmt in ("json", "csv"):
        response = client.get(f"/package_download/{fmt}?ids={ids}")
        assert response.status_code == 200, (fmt, response.status_code)
        body = response.get_data(as_text=True)
        # The sink is LIVE: both fields really are exported, so the two
        # absences below are about the content and not about the field.
        assert "analysis_error" in body and "error" in body
        assert PROVOKING_TOKEN not in body
        assert EXCEPTION_ONLY_SENTINEL not in body
        assert "invalid literal" not in body

    response = client.get(f"/package_download/xlsx?ids={ids}")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.get_data())) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "analysis_error" in sheet
    assert PROVOKING_TOKEN not in sheet
    assert EXCEPTION_ONLY_SENTINEL not in sheet


# ---------------------------------------------------------------------------
# The declared refusal — a named reason survives, and only by exact match
# ---------------------------------------------------------------------------


def test_the_declared_refusal_still_reaches_the_user(monkeypatch, store):
    """#WORKERPRIV D2. `no deterministic parser matched this statement` is a
    fixed literal of ours carrying no document content, and it is the ONE
    analysis error a user can act on. Reducing it to `RuntimeError` would have
    silently deleted `friendlyAnalysisError`'s primary branch and the guidance
    it gives ("use Auto mode, or add a deterministic parser")."""
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, RuntimeError(DECLARED_REFUSAL))

    fetched = _run_deterministic(store)

    assert fetched.status == "done"
    assert fetched.analysis_error == DECLARED_REFUSAL


def test_the_allow_list_is_exact_match_and_not_containment(monkeypatch, store):
    """The whole safety of the allow-list. A poisoned message that CONTAINS a
    declared literal must not ride it out of the boundary."""
    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, RuntimeError(f"{DECLARED_REFUSAL}: {POISONED_MESSAGE}"))

    fetched = _run_deterministic(store)

    published = fetched.analysis_error or ""
    assert published == (
        "analysis stage failed: RuntimeError "
        "(message withheld; an exception message can quote statement text)"
    )
    assert PROVOKING_TOKEN not in published
    assert EXCEPTION_ONLY_SENTINEL not in published


def test_a_refusal_whose_text_varies_is_not_admitted(monkeypatch, store):
    """`AmbiguousParserError`/`ParserCrashError` carry SAFE text (registry ids,
    class names) but variable text, so they cannot be pinned to a constant and
    are reduced like anything else. Their class name already names the finding,
    which is why that costs nothing."""
    from analysis.parser_registry import AmbiguousParserError

    _read_ok(monkeypatch)
    _analysis_raises(monkeypatch, AmbiguousParserError([("chase", 0.9), ("bmo", 0.9)]))

    fetched = _run_deterministic(store)

    assert fetched.analysis_error == (
        "analysis stage failed: AmbiguousParserError "
        "(message withheld; an exception message can quote statement text)"
    )


def test_the_declared_literal_is_still_what_the_pipeline_raises():
    """The coupling, made explicit instead of silent. If the pipeline rewords
    its refusal, the allow-list stops matching and the user quietly loses the
    guidance — so the reword fails here first."""
    from analysis.pipeline import analyze_markdown
    from webapp.worker import _DECLARED_ANALYSIS_REFUSALS

    with pytest.raises(RuntimeError) as raised:
        analyze_markdown("UNSUPPORTED BANK STATEMENT", parse_mode="deterministic")
    assert str(raised.value) in _DECLARED_ANALYSIS_REFUSALS


def test_the_browser_still_recognises_the_declared_refusal():
    """The other half of the same coupling: the literal is only worth carrying
    because `friendlyAnalysisError` turns it into an instruction."""
    app_js = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    assert "no deterministic parser matched" in app_js


# ---------------------------------------------------------------------------
# The source guard — the boundary census, enforced
# ---------------------------------------------------------------------------

#: Functions in `webapp/worker.py` that ARE the boundary: handing them the
#: caught exception is the compliant thing to do, and their own behaviour is
#: pinned by the tests above.
_WORKER_BOUNDARY_HELPERS = frozenset({"_stage_failure", "_analysis_failure"})

#: The same, for `webapp/app.py` (#PRIVACY3, APP-PRIVACY). `_review_refusal`
#: is the route's declared boundary: exact-match allow-list of five constants
#: in that file, everything else reduced to the class name. Its behaviour is
#: pinned by `tests/test_privacy3_boundaries.py`, including the `==` -> `in`
#: mutant and the coupling to `analysis/revenue.py`'s actual raises.
#: `_volume_failure` (audit 2026-10-13, BE-1) decides whether a start-up failure is the data volume's own (full,
#: I/O error, read-only, cannot open) from two integers only: the C layer's `sqlite_errorcode` and an OSError's
#: `errno`. It returns a bool and never reads a message, `args` or a traceback; `tests/test_webapp_disk_guard.py`
#: pins that with an exception whose text is a tripwire.
_BOUNDARY_HELPERS = {
    "worker.py": _WORKER_BOUNDARY_HELPERS,
    "app.py": frozenset({"_review_refusal", "_volume_failure"}),
}

#: THE LEDGER, and it is now EMPTY. Every place in `webapp/` where a caught
#: exception object was used for anything other than its class name is closed.
#:
#: It held two entries through batch 6, both `webapp/app.py:revenue_review`
#: returning `str(exc)` as an HTTP 404/400 body out of
#: `apply_serialized_revenue_review`. Non-durable (a response body, not a
#: stored column) but not harmless: `webapp/static/app.js` throws
#: `payload.error` into a `window.alert`, and the `except ValueError` was
#: BROADER than the fixed literals `analysis/revenue.py` raises, so any
#: `ValueError` from deeper inside `rebuild_serialized_revenue_views` was
#: published verbatim. #PRIVACY3 closed both with the same allow-list shape
#: `_analysis_failure` uses here, and the entries came out - which is what this
#: comment records, because a ledger that shrinks silently is a ledger nobody
#: can audit.
#:
#: The list is still the point, in the other direction: an EMPTY expectation
#: means the first new leak anywhere in `webapp/` fails this test.
#:
#: Phase 2.1 (P21-ROUTING closure-2, MINOR-D; composed-tree finding, Ocean
#: 2026-09-02): ONE entry, and it is not a leak. `webapp/artifact_cache.py::
#: cached_ocr` re-raises a `compute()` failure unchanged after a cached
#: evidence blob was found drifted, and before re-raising it STORES a closed
#: token on the exception object (`exc.cache_finding =
#: CACHE_FINDING_EVIDENCE_DRIFT`) so the caller can record the drift beside the
#: class name. Nothing is READ from the exception — not its message, not its
#: args, not its traceback — and the token is a module constant, so no
#: document content can travel through this use. The census is strict by
#: design (any use of the name that is not `type(e)` / bare `raise` / a
#: boundary helper is a finding), which is exactly why the entry is ledgered
#: here with its reason rather than special-cased in the scanner: the reader
#: `cache_finding_of` is the only consumer and reads only that attribute.
_LEDGERED_EXCEPTION_USES: list[str] = ["webapp/artifact_cache.py:cached_ocr"]


def _exception_object_uses(path: Path, helpers: frozenset[str]) -> list[str]:
    """Every use of a caught exception's NAME that is not `type(e)`, a bare
    re-`raise`, or an argument to one of `helpers`.

    Strict by design: passing the exception anywhere else — `str()`, `repr()`,
    an f-string, `%`-formatting, `.args`, another function — is a finding.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    try:
        relative = path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:                       # a synthetic file under tmp_path
        relative = path.name
    findings: list[str] = []

    #: #WORKERPRIV m-3, closed by #PRIVACY3. The walk below sees only
    #: `except X as name` handlers, so three shapes were invisible to it: a
    #: handler that recovers the exception through `sys.exc_info()`, one that
    #: renders it with `traceback.format_exc()`, and a bare `except:` doing
    #: either. None exists in `webapp/` today - which is exactly when to add
    #: the clause, because the guard that finds nothing is the one nobody
    #: notices is blind.
    _RECOVERY_CALLS = {
        ("sys", "exc_info"), ("traceback", "format_exc"),
        ("traceback", "print_exc"), ("traceback", "format_exception"),
    }

    def recovery_findings(handler: ast.ExceptHandler, owner: str) -> None:
        for node in ast.walk(handler):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if (func.value.id, func.attr) in _RECOVERY_CALLS:
                    findings.append(f"{relative}:{owner}")
            elif isinstance(func, ast.Name) and func.id in {
                "exc_info", "format_exc", "print_exc", "format_exception"
            }:
                findings.append(f"{relative}:{owner}")

    def handler_findings(handler: ast.ExceptHandler, owner: str) -> None:
        allowed: set[int] = set()
        for node in ast.walk(handler):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "type" and len(node.args) == 1:
                    allowed.add(id(node.args[0]))
                elif node.func.id in helpers:
                    allowed.update(id(arg) for arg in node.args)
            elif isinstance(node, ast.Raise) and node.exc is not None:
                allowed.add(id(node.exc))
        for node in ast.walk(handler):
            if (
                isinstance(node, ast.Name)
                and node.id == handler.name
                and isinstance(node.ctx, ast.Load)
                and id(node) not in allowed
            ):
                findings.append(f"{relative}:{owner}")

    def visit(node: ast.AST, owner: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = node.name
        if isinstance(node, ast.ExceptHandler):
            # `node.name` is None for a bare `except:` and for `except X:`.
            # Those cannot bind the exception, but they CAN still recover it
            # through the recovery calls above (m-3).
            if node.name:
                handler_findings(node, owner)
            recovery_findings(node, owner)
        for child in ast.iter_child_nodes(node):
            visit(child, owner)

    visit(tree, "<module>")
    return findings


def test_no_caught_exception_object_escapes_the_boundary_in_the_worker():
    """`webapp/worker.py` on its own: the two sites this cell owns must hand
    the exception to a boundary helper or read only its class."""
    findings = _exception_object_uses(
        PROJECT_ROOT / "webapp" / "worker.py", _WORKER_BOUNDARY_HELPERS
    )
    assert findings == []


def test_the_webapp_exception_ledger_is_complete():
    """The boundary census over ALL of `webapp/`, as an assertion."""
    findings: list[str] = []
    for path in sorted((PROJECT_ROOT / "webapp").rglob("*.py")):
        helpers = _BOUNDARY_HELPERS.get(path.name, frozenset())
        findings.extend(_exception_object_uses(path, helpers))
    assert sorted(findings) == sorted(_LEDGERED_EXCEPTION_USES)


@pytest.mark.parametrize("body,expected", [
    ("        return str(e)\n", ["leaky.py:handler"]),
    ("        return repr(e)\n", ["leaky.py:handler"]),
    ('        return f"{e}"\n', ["leaky.py:handler"]),
    ('        return "%s" % (e,)\n', ["leaky.py:handler"]),
    ("        return e.args[0]\n", ["leaky.py:handler"]),
    ("        return log(e)\n", ["leaky.py:handler"]),
    ("        return type(e).__name__\n", []),
    ("        raise e\n", []),
    ("        return _stage_failure('reading', e)\n", []),
    # m-3, closed by #PRIVACY3: recovering the exception WITHOUT binding it.
    ("        return str(sys.exc_info()[1])\n", ["leaky.py:handler"]),
    ("        return traceback.format_exc()\n", ["leaky.py:handler"]),
    ("        traceback.print_exc()\n", ["leaky.py:handler"]),
    ("        return format_exc()\n", ["leaky.py:handler"]),
])
def test_the_source_guard_can_actually_see_a_leak(tmp_path, body, expected):
    """A guard nobody has watched fail is not a guard. Every shape the census
    had to recognise, plus the three the boundary permits."""
    leaky = tmp_path / "leaky.py"
    leaky.write_text(
        "def handler():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as e:\n" + body,
        encoding="utf-8",
    )
    assert _exception_object_uses(leaky, _WORKER_BOUNDARY_HELPERS) == expected


@pytest.mark.parametrize("header,body,expected", [
    ("    except Exception as e:\n", "        return str(e)\n", ["leaky.py:handler"]),
    ("    except Exception:\n", "        return traceback.format_exc()\n",
     ["leaky.py:handler"]),
    ("    except:\n", "        return traceback.format_exc()\n", ["leaky.py:handler"]),
    ("    except:\n", "        return str(sys.exc_info()[1])\n", ["leaky.py:handler"]),
    ("    except Exception:\n", "        return 'a fixed literal'\n", []),
    ("    except:\n", "        pass\n", []),
])
def test_the_source_guard_sees_a_handler_that_never_binds_the_exception(
    tmp_path, header, body, expected
):
    """#WORKERPRIV m-3, closed by #PRIVACY3.

    The census walks `except X as name` handlers and reads every use of
    `name` - which is blind to the three shapes that recover the exception
    some OTHER way: `sys.exc_info()`, `traceback.format_exc()`, and a bare
    `except:` doing either.

    None of them exists in `webapp/` today, and that is the argument FOR
    closing it now rather than the argument against: a boundary guard that has
    only ever been true is a guard nobody has watched fail, and `except:` plus
    `format_exc()` is the shape a debugging session leaves behind.
    """
    leaky = tmp_path / "leaky.py"
    leaky.write_text(
        "import sys, traceback\n"
        "from traceback import format_exc\n"
        "def handler():\n"
        "    try:\n"
        "        pass\n" + header + body,
        encoding="utf-8",
    )
    assert _exception_object_uses(leaky, _WORKER_BOUNDARY_HELPERS) == expected
