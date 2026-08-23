"""QUEUE-SUPERVISOR (#HYGIENE8): the worker slot is released when the worker
dies, and the queue is re-armed.

The defect these tests replace was measured by §PRIVACY3 P8.1 and pinned there
by two `KNOWN_LIMITATION` tests: `_job_worker_active` is a claim on the single
worker slot, and the ONLY place that released it was the loop's own `return`.
`run_job`'s `BaseException` arm re-raises by design — swallowing a `SystemExit`
would defeat a shutdown — so the worker thread died holding the slot,
`_enqueue_job` never started another worker, and every later upload sat at
`queued` with `error=None` for the life of the process.

Three properties, and they are three because they fail separately:

1. **release** — the flag is False after the worker dies, whatever killed it.
   This alone un-strands every FUTURE upload.
2. **re-arm** — a replacement worker is started when work is already queued.
   This is what rescues the documents that were in the queue when the worker
   died, in a process where no further upload ever arrives.
3. **do not re-arm on the way out** — a `SystemExit` or `KeyboardInterrupt`
   means the process is going away, and starting a fresh worker would begin new
   OCR work on a process that has been told to stop. The slot is still released.

Every test drives the REAL `webapp.app._process_job_queue` against a real
`JobStore` on a temp path; the only substitution is `run_job` itself, because
the property under test is the supervisor's and not the worker's.
"""
from __future__ import annotations

import ast
import threading
import time
from collections import deque
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from webapp import app as webapp_app                                       # noqa: E402
from webapp.jobs import JobStore                                           # noqa: E402
from webapp.storage import Storage                                         # noqa: E402


@pytest.fixture
def supervisor(monkeypatch, tmp_path):
    """The module with a private store, a private queue and the slot claimed.

    `_job_worker_active = True` is the state a live worker thread is in: the
    fixture starts where `_enqueue_job` leaves the module before it spawns the
    thread, so what the tests exercise is exactly the thread's own path.
    """
    store = JobStore(Storage(tmp_path / "queue"))
    monkeypatch.setattr(webapp_app, "store", store)
    monkeypatch.setattr(webapp_app, "_job_worker_active", True)
    monkeypatch.setattr(webapp_app, "_job_queue", deque())
    return store


def _enqueue(store, name: str) -> str:
    job = store.create(name)
    webapp_app._job_queue.append((job.id, b"%PDF-x", name, False, "auto"))
    return job.id


def _live_workers() -> list[threading.Thread]:
    return [
        thread for thread in threading.enumerate()
        if thread is not threading.current_thread()
        and thread.is_alive()
        and getattr(thread, "_target", None) is webapp_app._process_job_queue
    ]


def _join_workers(deadline: float = 30.0) -> None:
    """Wait for every replacement worker thread to finish, including the ones
    not started yet when this is called.

    A single `enumerate()` pass is not enough and the first revision of this
    helper proved it: a repeated failure produces a CHAIN of replacements, and
    joining the snapshot let the test assert four of five documents. The chain
    is safe to wait on because each dying worker starts its successor BEFORE it
    re-raises, so "no live worker" is a terminal state rather than a gap.
    """
    end = time.monotonic() + deadline
    while True:
        alive = _live_workers()
        if not alive:
            return
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise AssertionError("replacement workers did not finish in time")
        for thread in alive:
            thread.join(max(0.0, end - time.monotonic()))


# ---------------------------------------------------------------------------
# 1. Release — the slot comes back, whatever killed the worker
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("failure", [
    RuntimeError("the worker thread died"),
    MemoryError(),
    SystemExit(1),
    KeyboardInterrupt(),
])
def test_the_worker_slot_is_released_when_run_job_unwinds(supervisor, monkeypatch, failure):
    """The half §PRIVACY3 P8.1 measured stranded. One job, nothing behind it, so
    the re-arm decision is not in play and only the release is."""
    first = _enqueue(supervisor, "one.pdf")

    def raising_run_job(job_id, pdf_bytes, filename, target, force_ocr=False,
                        parse_mode="auto"):
        target.set_status(job_id, "processing")
        target.set_error(job_id, "the worker stopped without publishing a result")
        raise failure

    monkeypatch.setattr(webapp_app, "run_job", raising_run_job)

    with pytest.raises(type(failure)):
        webapp_app._process_job_queue()

    assert webapp_app._job_worker_active is False
    assert supervisor.get(first).status == "error"


def test_the_escaping_exception_is_the_same_object(supervisor, monkeypatch):
    """A bare `raise`, so the thread's death and its stderr traceback are
    unchanged — the supervisor releases the slot, it does not decide anything
    about the exception. A `raise exc` would rebind the traceback; a
    `raise ... from` would attach a `__cause__`."""
    _enqueue(supervisor, "one.pdf")
    sentinel = RuntimeError("sentinel")

    def raising_run_job(*args, **kwargs):
        raise sentinel

    monkeypatch.setattr(webapp_app, "run_job", raising_run_job)

    with pytest.raises(RuntimeError) as caught:
        webapp_app._process_job_queue()

    assert caught.value is sentinel
    assert caught.value.__cause__ is None


# ---------------------------------------------------------------------------
# 2. Re-arm — the documents already in the queue still get processed
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_a_dead_worker_is_replaced_and_the_queue_drains(supervisor, monkeypatch):
    """Two jobs, the first one kills the worker. Before QUEUE-SUPERVISOR the
    second sat at `queued` with `error=None` forever; now a replacement thread
    picks it up and the queue empties."""
    first = _enqueue(supervisor, "one.pdf")
    second = _enqueue(supervisor, "two.pdf")
    seen: list[str] = []

    def run_job(job_id, pdf_bytes, filename, target, force_ocr=False, parse_mode="auto"):
        seen.append(job_id)
        target.set_status(job_id, "processing")
        if job_id == first:
            target.set_error(job_id, "the worker stopped without publishing a result")
            raise RuntimeError("the worker thread died")
        target.set_status(job_id, "done")

    monkeypatch.setattr(webapp_app, "run_job", run_job)

    with pytest.raises(RuntimeError):
        webapp_app._process_job_queue()
    _join_workers()

    assert seen == [first, second]
    assert len(webapp_app._job_queue) == 0
    assert webapp_app._job_worker_active is False
    assert supervisor.get(first).status == "error"
    assert supervisor.get(second).status == "done"


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_a_failure_that_repeats_for_every_document_drains_and_stops(supervisor, monkeypatch):
    """The re-arm cannot spin, and this is the measurement rather than the
    argument: each replacement pops one job under the same lock and `run_job`
    marks it before re-raising, so a failure that repeats for every document
    drains the queue one document per thread and stops. Nothing recurses — the
    dying thread starts the next one and then finishes unwinding."""
    ids = [_enqueue(supervisor, f"{n}.pdf") for n in range(5)]
    seen: list[str] = []

    def always_raising(job_id, pdf_bytes, filename, target, force_ocr=False,
                       parse_mode="auto"):
        seen.append(job_id)
        target.set_status(job_id, "processing")
        target.set_error(job_id, "the worker stopped without publishing a result")
        raise RuntimeError("the worker thread died")

    monkeypatch.setattr(webapp_app, "run_job", always_raising)

    with pytest.raises(RuntimeError):
        webapp_app._process_job_queue()
    _join_workers()

    assert seen == ids                      # each document popped exactly once
    assert len(webapp_app._job_queue) == 0
    assert webapp_app._job_worker_active is False
    assert all(supervisor.get(job_id).status == "error" for job_id in ids)


def test_no_replacement_is_started_when_the_queue_is_empty(supervisor, monkeypatch):
    """`_release_worker_slot` returns its decision so it can be asserted rather
    than inferred from a race. An empty queue needs no worker: the next
    `_enqueue_job` starts one, which is the base tree's own contract."""
    _enqueue(supervisor, "one.pdf")

    def raising_run_job(*args, **kwargs):
        raise RuntimeError("the worker thread died")

    monkeypatch.setattr(webapp_app, "run_job", raising_run_job)
    before = threading.active_count()

    with pytest.raises(RuntimeError):
        webapp_app._process_job_queue()

    assert threading.active_count() == before
    assert webapp_app._job_worker_active is False


# ---------------------------------------------------------------------------
# 3. Shutdown — release, but do not start new work
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("signal", [SystemExit(0), KeyboardInterrupt()])
def test_a_shutdown_signal_releases_the_slot_and_starts_nothing(
    supervisor, monkeypatch, signal
):
    """`run_job`'s arm re-raises so a shutdown still ends the process
    (§PRIVACY3 P8.1). Re-arming here would undo that by beginning new OCR work
    on a process that has been told to stop — so the slot comes back and the
    queue is deliberately LEFT with its work in it."""
    _enqueue(supervisor, "one.pdf")
    second = _enqueue(supervisor, "two.pdf")

    def signalling_run_job(job_id, pdf_bytes, filename, target, force_ocr=False,
                           parse_mode="auto"):
        target.set_status(job_id, "processing")
        target.set_error(job_id, "the worker stopped without publishing a result")
        raise signal

    monkeypatch.setattr(webapp_app, "run_job", signalling_run_job)
    before = threading.active_count()

    with pytest.raises(type(signal)):
        webapp_app._process_job_queue()

    assert threading.active_count() == before
    assert webapp_app._job_worker_active is False      # a process that survives
    assert len(webapp_app._job_queue) == 1             # can still take the next
    assert supervisor.get(second).status == "queued"


def test_the_shutdown_vocabulary_is_the_two_signals_and_nothing_wider():
    """A wider tuple would silently stop rescuing queued work after an ordinary
    crash; a narrower one would start OCR during a shutdown. Both directions are
    the defect, so the set itself is pinned."""
    assert webapp_app._SHUTDOWN_SIGNALS == (SystemExit, KeyboardInterrupt)
    # and neither of the ordinary killers is inside it
    assert not issubclass(MemoryError, webapp_app._SHUTDOWN_SIGNALS)
    assert not issubclass(RuntimeError, webapp_app._SHUTDOWN_SIGNALS)
    assert not issubclass(RecursionError, webapp_app._SHUTDOWN_SIGNALS)


# ---------------------------------------------------------------------------
# 4. The success path is byte-identical in behaviour
# ---------------------------------------------------------------------------

def test_the_normal_drain_is_unchanged(supervisor, monkeypatch):
    """The handler is on the failure path only: a queue that empties normally
    still returns through the loop's own `return`, resets the flag there, and
    starts no thread. §PRIVACY3 P8.1's three-way table called the queue half
    byte-identical before and after m-7; this keeps it so for the success row."""
    ids = [_enqueue(supervisor, f"{n}.pdf") for n in range(3)]
    seen: list[str] = []

    def run_job(job_id, pdf_bytes, filename, target, force_ocr=False, parse_mode="auto"):
        seen.append(job_id)
        target.set_status(job_id, "done")

    monkeypatch.setattr(webapp_app, "run_job", run_job)
    before = threading.active_count()

    webapp_app._process_job_queue()

    assert seen == ids
    assert threading.active_count() == before
    assert webapp_app._job_worker_active is False
    assert len(webapp_app._job_queue) == 0


# ---------------------------------------------------------------------------
# 5. The structural half — the handler exists and is on the supervisor
# ---------------------------------------------------------------------------

def test_the_supervisor_guards_the_run_job_call(supervisor):
    """The inverse of the AST assertion §PRIVACY3 pinned (`_process_job_queue`
    has NO `try`). It is kept as an AST test for the same reason it was written
    as one: a refactor that moves the call out of the handler passes every
    behavioural test above only until the next failure mode arrives."""
    tree = ast.parse((PROJECT_ROOT / "webapp" / "app.py").read_text(encoding="utf-8"))
    supervisor_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_process_job_queue"
    )
    handlers = [node for node in ast.walk(supervisor_fn) if isinstance(node, ast.Try)]
    assert len(handlers) == 1, "the supervisor's handler moved or multiplied"
    guarded = {
        call.func.id
        for node in handlers[0].body
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }
    assert "run_job" in guarded, "run_job is no longer inside the handler"
    caught = [ast.unparse(h.type) for h in handlers[0].handlers]
    assert caught == ["BaseException"], (
        "the supervisor must catch BaseException: the exceptions that strand "
        f"the slot are precisely the ones `except Exception` misses ({caught})"
    )
    # ...and it re-raises bare, so nothing about the thread's death changes.
    reraises = [
        node for node in ast.walk(handlers[0].handlers[0])
        if isinstance(node, ast.Raise)
    ]
    assert len(reraises) == 1 and reraises[0].exc is None, (
        "the supervisor must re-raise bare"
    )
