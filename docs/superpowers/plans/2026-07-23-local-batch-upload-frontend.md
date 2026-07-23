# Local Batch Upload Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask web app where the user drags/selects one or more bank-statement PDFs, watches per-file background processing status, and views/downloads the resulting Markdown and HTML.

**Architecture:** Flask app (`webapp/app.py`) with an in-memory thread-safe job store (`webapp/jobs.py`), a background worker (`webapp/worker.py`) that calls the existing `ocr.pipeline.parse_statement` per uploaded file in a daemon thread, and a single-page vanilla-JS frontend (`webapp/templates/index.html` + `webapp/static/app.js`) that polls per-job status and renders results/downloads inline.

**Tech Stack:** Python 3.12 (existing venv), Flask, vanilla HTML/JS (no build tooling), reusing `ocr.pipeline.parse_statement` and `ocr.render.markdown_to_html` unchanged.

## Global Constraints

- **Local only:** runs on `localhost`, single user, no auth, no deployment concerns.
- **No changes to the OCR engine, prompt, or `ocr.*` modules** — the webapp is purely a new consumer of `ocr.pipeline.parse_statement` and `ocr.render.markdown_to_html`.
- **Reuses existing `OCR_*` env vars** — no new configuration surface.
- **Processing is background/non-blocking:** each uploaded file gets its own daemon thread; the page polls per-file status (`queued`/`processing`/`done`/`error`) rather than blocking on the whole batch.
- **State is in-memory only** (process-lifetime dict) — no persistence across restarts.
- **One file's failure must not crash the app or block other files.**
- **Interpreter:** Python 3.12 via the existing `.venv`. Run everything as `.venv/Scripts/python.exe ...`.
- **Tests never hit the network or spawn real background threads** — `parse_statement` is mocked, and `/upload` route tests replace `threading.Thread` with a synchronous fake so job completion is deterministic.

---

### Task 1: In-memory job store

**Files:**
- Create: `webapp/__init__.py` (empty — package marker)
- Create: `webapp/jobs.py`
- Test: `tests/test_webapp_jobs.py`

**Interfaces:**
- Produces:
  - `@dataclass Job` with fields `id: str`, `filename: str`, `status: str = "queued"`, `markdown: str | None = None`, `html: str | None = None`, `error: str | None = None`.
  - `class JobStore`:
    - `create(filename: str) -> Job`
    - `get(job_id: str) -> Job | None`
    - `set_status(job_id: str, status: str) -> None`
    - `set_result(job_id: str, markdown: str, html: str) -> None` — also sets `status = "done"`
    - `set_error(job_id: str, error: str) -> None` — also sets `status = "error"`
  - All dict access guarded by an internal `threading.Lock`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webapp_jobs.py
from webapp.jobs import JobStore, Job


def test_create_and_get():
    store = JobStore()
    job = store.create("statement.pdf")
    assert isinstance(job, Job)
    assert job.filename == "statement.pdf"
    assert job.status == "queued"
    assert store.get(job.id) is job


def test_get_unknown_returns_none():
    store = JobStore()
    assert store.get("nope") is None


def test_set_status():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_status(job.id, "processing")
    assert store.get(job.id).status == "processing"


def test_set_result_marks_done():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_result(job.id, "# md", "<h1>md</h1>")
    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# md"
    assert fetched.html == "<h1>md</h1>"


def test_set_error_marks_error():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_error(job.id, "boom")
    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp'`

- [ ] **Step 3: Write minimal implementation**

```python
# webapp/__init__.py
```
(empty file)

```python
# webapp/jobs.py
from __future__ import annotations
import threading
import uuid
from dataclasses import dataclass


@dataclass
class Job:
    id: str
    filename: str
    status: str = "queued"  # "queued" | "processing" | "done" | "error"
    markdown: str | None = None
    html: str | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Job:
        job = Job(id=str(uuid.uuid4()), filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = status

    def set_result(self, job_id: str, markdown: str, html: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.markdown = markdown
                job.html = html
                job.status = "done"

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.error = error
                job.status = "error"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_jobs.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/__init__.py webapp/jobs.py tests/test_webapp_jobs.py
git commit -m "feat: add in-memory job store for the batch-upload frontend"
```

---

### Task 2: Background worker

**Files:**
- Create: `webapp/worker.py`
- Test: `tests/test_webapp_worker.py`

**Interfaces:**
- Consumes: `webapp.jobs.JobStore` (Task 1); `ocr.pipeline.parse_statement(pdf_bytes, source_file="") -> StatementMarkdown` (existing); `ocr.render.markdown_to_html(markdown_text, title="") -> str` (existing).
- Produces: `run_job(job_id: str, pdf_bytes: bytes, filename: str, store: JobStore) -> None` — sets status to `"processing"`, calls `parse_statement`, on success calls `store.set_result(job_id, markdown, html)`, on any exception calls `store.set_error(job_id, str(exception))`. Never raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webapp_worker.py
from webapp.jobs import JobStore
from webapp.worker import run_job


class _FakeDoc:
    def to_markdown(self):
        return "# Hello"


def test_run_job_success(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")
    monkeypatch.setattr("webapp.worker.parse_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file=""):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.worker'`

- [ ] **Step 3: Write minimal implementation**

```python
# webapp/worker.py
from __future__ import annotations
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .jobs import JobStore


def run_job(job_id: str, pdf_bytes: bytes, filename: str, store: JobStore) -> None:
    store.set_status(job_id, "processing")
    try:
        doc = parse_statement(pdf_bytes, source_file=filename)
        markdown = doc.to_markdown()
        html = markdown_to_html(markdown, title=filename)
        store.set_result(job_id, markdown, html)
    except Exception as e:
        store.set_error(job_id, str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_worker.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/worker.py tests/test_webapp_worker.py
git commit -m "feat: add background worker that runs parse_statement per upload"
```

---

### Task 3: Flask app and routes

**Files:**
- Create: `webapp/app.py`
- Test: `tests/test_webapp_app.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `webapp.jobs.JobStore` (Task 1), `webapp.worker.run_job` (Task 2).
- Produces: a Flask `app` object at module level, plus a module-level `store = JobStore()` singleton, both importable as `webapp.app.app` / `webapp.app.store`. Routes:
  - `GET /` — renders `templates/index.html`.
  - `POST /upload` — reads `request.files.getlist("files")`; 400 with `{"error": "no files uploaded"}` if empty; else creates a job + spawns a `threading.Thread(target=run_job, args=(job.id, pdf_bytes, filename, store), daemon=True)` per file; returns `{"jobs": [{"id": ..., "filename": ...}, ...]}`.
  - `GET /status/<job_id>` — 404 if unknown; else `{"status": ..., "error": ...}`.
  - `GET /result/<job_id>` — 404 if unknown or not `"done"`; else returns `job.html` as the response body.
  - `GET /download/<job_id>/<fmt>` — 400 if `fmt` not in `{"md", "html"}`; 404 if unknown or not `"done"`; else returns `job.markdown` or `job.html` with `Content-Disposition: attachment`.

- [ ] **Step 1: Install Flask**

Run:
```bash
.venv/Scripts/python.exe -m pip install flask
```
Expected: `Successfully installed flask-... ...`

- [ ] **Step 2: Add flask to requirements.txt**

```
openai
pdf2image==1.17.0
pillow
markdown
flask
pytest
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_webapp_app.py
import io
from webapp.app import app, store


class _FakeThread:
    """Runs the target synchronously so job completion is deterministic in tests."""
    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class _FakeDoc:
    def to_markdown(self):
        return "# Hello"


def _upload_one(client):
    data = {"files": (io.BytesIO(b"%PDF-fake"), "s.pdf")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    return resp.get_json()["jobs"][0]["id"]


def test_upload_creates_and_completes_job(monkeypatch):
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.worker.parse_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())
    client = app.test_client()

    job_id = _upload_one(client)

    status_resp = client.get(f"/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.get_json()["status"] == "done"

    result_resp = client.get(f"/result/{job_id}")
    assert "<h1>Hello</h1>" in result_resp.get_data(as_text=True)

    md_resp = client.get(f"/download/{job_id}/md")
    assert md_resp.get_data(as_text=True) == "# Hello"
    assert "attachment" in md_resp.headers["Content-Disposition"]

    html_resp = client.get(f"/download/{job_id}/html")
    assert "<h1>Hello</h1>" in html_resp.get_data(as_text=True)


def test_upload_with_no_files_returns_400():
    client = app.test_client()
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_status_unknown_job_returns_404():
    client = app.test_client()
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404


def test_download_invalid_format_returns_400(monkeypatch):
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.worker.parse_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())
    client = app.test_client()
    job_id = _upload_one(client)
    resp = client.get(f"/download/{job_id}/txt")
    assert resp.status_code == 400


def test_download_before_done_returns_404():
    client = app.test_client()
    job = store.create("pending.pdf")  # no thread started; status stays "queued"
    resp = client.get(f"/download/{job.id}/md")
    assert resp.status_code == 404
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.app'`

- [ ] **Step 5: Write minimal implementation**

```python
# webapp/app.py
from __future__ import annotations
import threading
from flask import Flask, request, jsonify, render_template, Response, abort

from .jobs import JobStore
from .worker import run_job

app = Flask(__name__)
store = JobStore()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400

    jobs = []
    for f in files:
        pdf_bytes = f.read()
        job = store.create(f.filename)
        thread = threading.Thread(
            target=run_job, args=(job.id, pdf_bytes, f.filename, store), daemon=True,
        )
        thread.start()
        jobs.append({"id": job.id, "filename": job.filename})
    return jsonify({"jobs": jobs})


@app.route("/status/<job_id>")
def status(job_id):
    job = store.get(job_id)
    if job is None:
        abort(404)
    return jsonify({"status": job.status, "error": job.error})


@app.route("/result/<job_id>")
def result(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return job.html


@app.route("/download/<job_id>/<fmt>")
def download(job_id, fmt):
    if fmt not in ("md", "html"):
        abort(400)
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    content = job.markdown if fmt == "md" else job.html
    mimetype = "text/markdown" if fmt == "md" else "text/html"
    base_name = job.filename.rsplit(".", 1)[0]
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.{fmt}"'},
    )


if __name__ == "__main__":
    app.run(debug=True)
```

`render_template("index.html")` will fail with a `TemplateNotFound` error until Task 4 adds
`webapp/templates/index.html` — the `GET /` route is not exercised by this task's tests, so
that's expected and does not block Task 3.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webapp_app.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: Commit**

```bash
git add webapp/app.py tests/test_webapp_app.py requirements.txt
git commit -m "feat: add Flask routes for upload, status, result, and download"
```

---

### Task 4: Frontend page and manual verification

**Files:**
- Create: `webapp/templates/index.html`
- Create: `webapp/static/app.js`
- Modify: `README.md`

**Interfaces:** none (templates/static assets served by Flask's default `templates/`/`static/` conventions relative to `webapp/app.py`'s package location; no new Python interfaces).

- [ ] **Step 1: Write `webapp/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bank Statement Parser</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; }
  #dropzone { border: 2px dashed #999; border-radius: 8px; padding: 2rem;
              text-align: center; color: #666; margin-bottom: 1.5rem; cursor: pointer; }
  #dropzone.drag { border-color: #333; color: #333; background: #f5f5f5; }
  .job { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .job-header { display: flex; justify-content: space-between; align-items: center; }
  .status { font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  .status-queued, .status-processing { background: #fff3cd; color: #856404; }
  .status-done { background: #d4edda; color: #155724; }
  .status-error { background: #f8d7da; color: #721c24; }
  .job-error { color: #721c24; margin-top: 0.5rem; }
  .job-result { border-top: 1px solid #eee; margin-top: 0.75rem; padding-top: 0.75rem; }
  .job-result iframe { width: 100%; height: 400px; border: 1px solid #ddd; }
  .downloads a { margin-right: 1rem; }
</style>
</head>
<body>
<h1>Bank Statement Parser</h1>
<div id="dropzone">Drop PDF files here, or click to choose files
  <input type="file" id="fileInput" multiple accept="application/pdf" style="display:none">
</div>
<div id="jobs"></div>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `webapp/static/app.js`**

```javascript
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const jobsEl = document.getElementById("jobs");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag");
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

function uploadFiles(fileList) {
  if (!fileList.length) return;
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  fetch("/upload", { method: "POST", body: form })
    .then((r) => r.json())
    .then((data) => {
      for (const job of data.jobs) {
        addJobRow(job.id, job.filename);
        pollJob(job.id);
      }
    });
}

function addJobRow(jobId, filename) {
  const div = document.createElement("div");
  div.className = "job";
  div.id = `job-${jobId}`;
  div.innerHTML =
    '<div class="job-header">' +
    `<strong>${filename}</strong>` +
    `<span class="status status-queued" id="status-${jobId}">queued</span>` +
    "</div>" +
    `<div id="body-${jobId}"></div>`;
  jobsEl.prepend(div);
}

function pollJob(jobId) {
  const interval = setInterval(() => {
    fetch(`/status/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        const statusEl = document.getElementById(`status-${jobId}`);
        statusEl.textContent = data.status;
        statusEl.className = `status status-${data.status}`;
        if (data.status === "done") {
          clearInterval(interval);
          showResult(jobId);
        } else if (data.status === "error") {
          clearInterval(interval);
          showError(jobId, data.error);
        }
      });
  }, 2000);
}

function showResult(jobId) {
  fetch(`/result/${jobId}`)
    .then((r) => r.text())
    .then((html) => {
      const bodyEl = document.getElementById(`body-${jobId}`);
      const escaped = html.replace(/"/g, "&quot;");
      bodyEl.innerHTML =
        '<div class="job-result">' +
        `<iframe srcdoc="${escaped}"></iframe>` +
        '<div class="downloads">' +
        `<a href="/download/${jobId}/md" download>Download .md</a>` +
        `<a href="/download/${jobId}/html" download>Download .html</a>` +
        "</div></div>";
    });
}

function showError(jobId, error) {
  const bodyEl = document.getElementById(`body-${jobId}`);
  bodyEl.innerHTML = `<div class="job-error">Error: ${error}</div>`;
}
```

- [ ] **Step 3: Run the full test suite (including the previously-skipped `GET /` path)**

```python
# add to tests/test_webapp_app.py
def test_index_page_renders():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Bank Statement Parser" in resp.data
```

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all tests PASS, including the new `test_index_page_renders` and every prior
suite (config/ocr_client/document/pipeline/cli/render/webapp_*) — nothing here touches
existing `ocr/` modules.

- [ ] **Step 4: Manual smoke test (requires the RunPod pod running)**

Run:
```bash
$env:OCR_BASE_URL = "https://<pod-id>-8000.proxy.runpod.net/v1"
$env:OCR_API_KEY = "sk-<pod-id>"
.venv/Scripts/python.exe -m webapp.app
```
Open `http://localhost:5000` in a browser, upload a real sample PDF from
`BankStatements/`, and confirm: the job appears with status `queued` → `processing` →
`done`, the rendered result appears inline, and both download links produce the
expected `.md`/`.html` files. If the pod isn't running, confirm the job instead reaches
`error` with a connection-error message shown inline, rather than crashing the page.

- [ ] **Step 5: Update README with run instructions**

Add this section to `README.md` (after the existing "Usage" section):

```markdown
## Local web frontend

For uploading and viewing statements without the command line:

```bash
.venv/Scripts/python.exe -m webapp.app
```

Open `http://localhost:5000`, drop in one or more PDFs, and watch each one's status
update live. Once a file finishes, its rendered result appears inline with download
links for both the raw Markdown and the styled HTML. Uses the same `OCR_*`
environment variables as the CLI.
```

- [ ] **Step 6: Commit**

```bash
git add webapp/templates/index.html webapp/static/app.js tests/test_webapp_app.py README.md
git commit -m "feat: add frontend page for batch statement upload"
```

---

## Self-Review Notes

- **Spec coverage:** job store with thread-safe status transitions (Task 1); background
  worker calling the unchanged `parse_statement`/`markdown_to_html` (Task 2); all five
  routes (`/`, `/upload`, `/status`, `/result`, `/download`) with the specified error
  codes (400 empty upload, 400 invalid download format, 404 unknown/not-done job)
  (Task 3); inline result + both download links + drag-and-drop + polling frontend
  (Task 4); manual smoke test instructions covering both the pod-up and pod-down cases
  (Task 4). ✅
- **No changes to `ocr/*`:** confirmed — only `webapp/*` files are created; `ocr.pipeline`
  and `ocr.render` are imported, not modified. ✅
- **Type/name consistency:** `JobStore.create/get/set_status/set_result/set_error` (Task 1)
  match exactly how `worker.run_job` (Task 2) and `webapp/app.py`'s routes (Task 3) call
  them. `run_job(job_id, pdf_bytes, filename, store)` signature is identical between its
  definition (Task 2) and every call site (Task 3's `/upload` route and its tests). ✅
- **Determinism:** the `_FakeThread` pattern in Task 3's tests (and reused in Task 4's
  manual-test note) avoids real threads in the automated suite, per the Global
  Constraints. ✅
