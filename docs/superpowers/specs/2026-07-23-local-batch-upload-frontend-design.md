# Local Batch Upload Frontend — Design

**Date:** 2026-07-23
**Status:** Approved (pending written-spec review)

## Purpose

A local-only web frontend for uploading one or more bank-statement PDFs, running
them through the existing `ocr.pipeline.parse_statement` (Unlimited-OCR), and
viewing/downloading the resulting Markdown/HTML — without touching the command
line. Single user, runs on the user's own laptop (`localhost`), no auth, no
deployment concerns.

## Scope & Constraints

- **Audience:** the user only, running locally (`python webapp/app.py` →
  `http://localhost:5000`). No multi-user auth, no remote hosting.
- **Batch upload:** multiple PDFs in one submission, each processed and reported
  independently.
- **Processing model:** background threads, not request-blocking. The page polls
  per-file status so slow/large batches don't hang the browser.
- **Result presentation:** both — inline rendered HTML per finished file, and
  download links for the raw `.md` and rendered `.html`.
- **Backend:** Flask (synchronous, no async framework needed for a single user).
- **Frontend:** plain HTML + vanilla JS. No build tooling, no JS framework.
- **Reuses existing code as-is:** `ocr.pipeline.parse_statement`,
  `ocr.render.markdown_to_html`, and the existing `OCR_*` env vars. No changes to
  the OCR engine, prompt, or config surface.
- **Failure isolation:** one file's endpoint/OCR failure must not crash the app
  or block other files' processing — surfaced as a per-file error status.
- **State:** in-memory only (a process-lifetime dict). Restarting the app clears
  job history — acceptable for a local single-user tool; no persistence needed.

## Architecture & Flow

```
Browser                          Flask app (webapp/app.py)
--------                         --------------------------
GET /              ------------> serve index.html
                                  (drop zone + file list area)

POST /upload (N files)  -------> for each file:
                                    - save PDF bytes to a temp path
                                    - create JobStore entry (status="queued")
                                    - spawn a daemon Thread running _run_job(job_id)
                                  <- {"jobs": [{"id": ..., "filename": ...}, ...]}

JS renders one row per         (background thread, per job)
job id; starts polling            _run_job:
                                     - set status="processing"
                                     - call parse_statement(...)
                                     - on success: store markdown + html,
                                       status="done"
                                     - on exception: store error message,
                                       status="error"

GET /status/<job_id>  ---------> {"status": "queued|processing|done|error",
  (polled every ~2s per row)       "error": "..." }   # error only if status=="error"

GET /result/<job_id>  ---------> rendered HTML fragment (once status=="done")
  (fetched once when status                            for inline display
   flips to "done")

GET /download/<job_id>/md    --> raw markdown, Content-Disposition: attachment
GET /download/<job_id>/html  --> rendered HTML, Content-Disposition: attachment
```

## Components

### `webapp/jobs.py` — in-memory job store

```python
@dataclass
class Job:
    id: str
    filename: str
    status: str  # "queued" | "processing" | "done" | "error"
    markdown: str | None = None
    html: str | None = None
    error: str | None = None

class JobStore:
    def create(self, filename: str) -> Job: ...
    def get(self, job_id: str) -> Job | None: ...
    def set_status(self, job_id: str, status: str) -> None: ...
    def set_result(self, job_id: str, markdown: str, html: str) -> None: ...
    def set_error(self, job_id: str, error: str) -> None: ...
```

A single module-level `JobStore()` instance, guarded by a `threading.Lock` for
dict access (simple correctness under concurrent background threads).

### `webapp/worker.py` — background processing

```python
def run_job(job_id: str, pdf_bytes: bytes, filename: str, store: JobStore) -> None:
    """Runs in a daemon thread. Calls parse_statement, updates the job store."""
```

Catches all exceptions from `parse_statement` (network errors, OCR failures)
and records them via `store.set_error`, never lets them propagate/crash the
thread silently — errors must be visible in the UI.

### `webapp/app.py` — Flask routes

- `GET /` — render `templates/index.html`.
- `POST /upload` — accept `request.files.getlist("files")`, for each: read
  bytes, `store.create(filename)`, spawn
  `threading.Thread(target=run_job, args=(job.id, pdf_bytes, filename, store), daemon=True).start()`.
  Returns `{"jobs": [{"id": job.id, "filename": job.filename}, ...]}`.
- `GET /status/<job_id>` — 404 if unknown job id, else
  `{"status": job.status, "error": job.error}`.
- `GET /result/<job_id>` — 404 if unknown or not yet `"done"`, else returns
  `job.html` (the rendered fragment/page).
- `GET /download/<job_id>/<fmt>` — `fmt` in `{"md", "html"}`; 400 on other
  values; 404 if job unknown or not done; else returns the raw content with
  `Content-Disposition: attachment; filename="<name>.<fmt>"`.

### `webapp/templates/index.html` + `webapp/static/app.js`

- Multi-file `<input type="file" multiple accept="application/pdf">` plus a
  drop-zone `<div>` (drag-and-drop calls the same upload handler).
- On upload response, append one `<li>` per job: filename, status badge,
  (once done) an inline `<iframe>` or `<div>` with the fetched result HTML, and
  two `<a>` download links.
- `setInterval` polling per pending job id; stops polling that job once status
  is `done` or `error`.
- No external JS libraries — `fetch()` + DOM manipulation only.

## Error Handling

- **Per-file OCR/network failure** → job status `"error"`, error message shown
  in that file's row; other files keep processing normally.
- **Unsupported/corrupt upload** (`parse_statement` raises on unreadable PDF
  bytes) → same error-status path, no special-casing needed — reuses the
  existing exception handling inside `parse_statement`/`rasterize_pdf`.
- **Unknown job id in `/status`, `/result`, `/download`** → HTTP 404.
- **Empty upload (`POST /upload` with no files)** → 400 with a plain error
  message.

## Testing

- **`webapp/jobs.py`** — unit tests: create/get/set_status/set_result/set_error,
  unknown-id lookups return `None`.
- **`webapp/worker.py`** — unit test with `parse_statement` monkeypatched
  (success path sets `done` + markdown/html; exception path sets `error` +
  message) — no network involved.
- **`webapp/app.py` routes** — Flask test client, `parse_statement` mocked at
  the import site used by the worker:
  - `POST /upload` with one/multiple fake PDFs → returns job ids, jobs reach
    `done` (poll `store` directly in the test rather than sleeping on real
    threads — call `run_job` synchronously in the test instead of via a real
    thread where determinism matters).
  - `GET /status/<unknown>` → 404.
  - `GET /download/<job_id>/txt` → 400 (invalid format).
  - `GET /download/<job_id>/md` before job is done → 404.
- **Manual smoke test** (once the RunPod pod is running again): start the app,
  upload a real sample PDF via the browser, confirm status transitions and the
  inline result/downloads work end to end. Not part of the automated suite.

## Out of Scope

- Authentication/multi-user support.
- Persisting job history across restarts.
- Remote deployment/hosting.
- Any change to the OCR engine, prompt, or `ocr.pipeline`/`ocr.ocr_client`
  modules — the frontend is purely a new consumer of the existing pipeline.
- Progress *within* a single file (e.g., "page 3 of 10") — status is coarse
  (queued/processing/done/error) per file, not per page.
