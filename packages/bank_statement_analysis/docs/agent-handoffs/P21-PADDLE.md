# Agent Handoff — P21-PADDLE (Phase 2.1 cell P: the PaddleOCR 3.7 / PP-OCRv5 extractor — the loopback worker on the Vast.ai RTX 5090, the bounded client, the result adapter into canonical evidence, the rung, the lifecycle tool, the measurements)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (all of it — the Phase 2.1 section at the end is
binding: Ruling A, Ruling B, the Vast authorization, the DATA PRIVACY BOUNDARY), then the umbrella
`docs/agent-handoffs/PHASE2-1-PADDLE.md` (every section; D2, D3, D5, D7, D8, D9; cases 5, 7, 11, 13,
16, 17, 18, 20), then `evidence/canonical.py` and `ocr/paddle_config.py` (both committed by Ocean —
you CONSUME them; read every docstring), then `ocr/endpoint_policy.py`, `ocr/config.py`,
`ocr/rasterize.py`, `ocr/availability.py`, `ocr/ocr_client.py::_build_client` (the shape of a
fail-closed client), `local_ocr_server.py` (prior art for a single-file worker; do NOT copy its
model code), and `tests/fixtures/paddle/paddle_demo_wordboxes_res.json` (the REAL PaddleOCR 3.7
result shape, fetched from the proven run — build the adapter against it, not against memory).
Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0`; no
document from `Bank Statements/`, `tests/corpus_cache/` or any real statement is ever read by your
code, sent anywhere, or used as a fixture; the ONLY network egress you may perform is SSH/SCP to
the host named by the `PADDLE_VAST_*` environment and HTTP to `127.0.0.1:<tunnel port>`, and only
with synthetic fixtures.**

# Why
The proven fact is narrow: PaddleOCR 3.7.0 with `return_word_box=True` runs on the Vast RTX 5090
and returns word boxes. Everything that turns that into platform evidence is missing: a service that
cannot be reached from anywhere but an SSH tunnel and cannot be fed anything but a bounded PNG; a
client that refuses to send a byte until the declaration, the opt-in, the data scope and the worker's
own identity all agree; an adapter that turns the 3.7 result shape into immutable canonical evidence
without interpreting a single value; a rung that yields page text derived from geometry; and a
measurement of what a page costs. Paddle produces evidence. It never produces financial truth.

# Design (ruled — do not re-decide; the umbrella card is the authority where this is silent)
## 1. `ocr/paddle_worker.py` — the remote service (D7)
Single file; runs under the host's `/venv/main` Python 3.12 with ONLY stdlib + `paddleocr` +
`Pillow` + `numpy` (all present there). Importable locally WITHOUT paddleocr: the `paddleocr` import
lives inside the inference function, so request validation is unit-tested offline.
* `http.server.ThreadingHTTPServer`; bind address is `127.0.0.1` ONLY — the script refuses to start
  on any other address (an env `PADDLE_WORKER_BIND` other than `127.0.0.1` is a startup error, not an
  option). Port from `PADDLE_WORKER_PORT` (default `8765`; never Jupyter's 8080).
* Identity from the worker's OWN environment: `PADDLE_PROVIDER`, `PADDLE_EXECUTION_CLASS`
  (validated against `ocr/paddle_config.py`'s pairing — copy the two tiny vocabularies into the
  worker as literals with a comment naming their source; the worker does not import the repo).
* Routes: `GET /health` → `{"ok": true, "contract": 1}`; `GET /version` → `{"contract": 1, "provider",
  "execution_class", "gpu": {"name", "memory_total_mib", "driver_version"}, "paddleocr_version",
  "paddlepaddle_version", "cuda_compiled", "ocr_version": "PP-OCRv5", "text_detection_model_name",
  "text_recognition_model_name", "pipeline_switches": {…the five…}, "python_version",
  "worker_started_at", "model_loaded": bool}`; `POST /ocr` with JSON `{"contract": 1, "request_id":
  str, "page_index": int, "image_png_b64": str}` → `{"raw": <the PaddleOCR result dict verbatim,
  minus "input_path">, "image": {"width", "height", "sha256"}, "timing": {"decode_ms",
  "inference_ms", "total_ms", "cold_load": bool}, "gpu": {"memory_used_mib"}, "model": <the identity
  block>}`. Any other route/method → 404/405 JSON. Errors → `{"error": <token>}` from a closed set
  (`bad_json`, `contract_mismatch`, `body_too_large`, `not_png`, `image_too_large`, `bad_base64`,
  `unauthorized`, `inference_failed`) with 4xx/5xx; never a traceback, never content.
* Bounds enforced BEFORE decoding: `Content-Length` ≤ 32 MiB (refuse otherwise; no chunked bodies);
  JSON parsed with a depth/size guard; base64 decoded with `validate=True`; PNG magic checked
  (`\x89PNG\r\n\x1a\n`); `Image.MAX_IMAGE_PIXELS = 30_000_000` and `PIL.Image.DecompressionBombError`
  → `image_too_large`; max side 6,000 px; exactly one image per request; `page_index` a non-negative
  int. Optional bearer token: when `PADDLE_WORKER_TOKEN` is set in the worker's env, every request
  must carry `Authorization: Bearer <token>` (constant-time compare) or → `unauthorized`.
* Inference: the `PaddleOCR(...)` instance is built ONCE with EXACTLY the pinned identity
  (`text_detection_model_name`, `text_recognition_model_name`, `ocr_version="PP-OCRv5"`, and the
  five switches — read `PaddleOCR.__init__`'s real signature: it is in the umbrella card's baseline
  table), lazily on first `/ocr` (so `/health` and `/version` answer before the model loads; the
  first request reports `cold_load: true`); one inference at a time (a lock); the result taken from
  `result[0].json["res"]` (or the equivalent 3.7 accessor — verify on the host, and record which in
  the docstring) and returned VERBATIM. No retention: the image bytes live only in memory; nothing is
  written to disk; the log line per request is `request_id, page_index, width x height, ms, status`
  — never text.
* `python ocr/paddle_worker.py --self-check` prints the identity block and exits (used by `deploy`).

## 2. `ocr/paddle_client.py` — the bounded client (D2, D5, CASE 16/18)
Stdlib `urllib.request` only (no `openai`, no `httpx`): `PaddleClient(settings, *, timeout=120.0,
opener=None)` (an injectable opener is the test seam). Constructor: `settings.worker_url` must
classify `loopback` via `ocr.endpoint_policy.classify_endpoint` (already guaranteed by
`load_paddle_settings`; re-check here — MINOR-2's lesson: never trust a hand-built settings object).
`version()` / `health()` / `ocr_page(png_bytes, *, page_index, request_id) -> dict`. Response size
bounded (64 MiB), JSON only, no redirects followed (a redirect is `paddle_worker_unreachable`), no
retry to any other URL — retries (≤ 2, same URL, transient errors only) are the ONLY loop.
`verify_identity(settings) -> dict`: fetch `/version`; refuse (`PaddleRefused("paddle_runtime_mismatch",
…)`) unless `contract`, `provider`, `execution_class`, `paddleocr_version`, `paddlepaddle_version`,
`ocr_version`, both model names and all five switches EQUAL `ocr.paddle_config.paddle_runtime_identity()`
+ the settings' declaration — every field, one at a time, in the tests. `probe(settings=None,
client=None) -> PaddleWorkerStatus(available, reason, identity, error_type)` never raises: config
error → `paddle_config_missing`; remote without opt-in → `paddle_remote_opt_in_required` (checked
BEFORE any request, via `check_remote_authorization(settings, "synthetic")` — the probe sends no
document so the scope gate it exercises is the opt-in one); unreachable → `paddle_worker_unreachable`
+ the exception CLASS name; mismatch → `paddle_runtime_mismatch`. `PaddleTransportError(RuntimeError)`
carries `reason="paddle_worker_unreachable"` and `error_type` (class name) — never the message.

## 3. `ocr/paddle_adapter.py` — PaddleOCR 3.7 result → canonical evidence (D9, CASE 5, CASE 8)
`page_evidence_from_result(raw: dict, *, frame: PageFrame) -> PageEvidence`: words from
`text_word[i][j]` with box `text_word_boxes[i][j] = [x0, y0, x1, y1]` (ints, pixels of the raster the
frame describes), `line_ref = i`, `confidence = rec_scores[i]` (a LINE score copied to each word —
Paddle 3.7 scores lines; say so in the docstring), `word_id = evidence.word_id(page_index, i, j)`,
text `str(text_word[i][j])`. Word text that is blank/whitespace is DROPPED and counted
(`notes=("dropped_empty_words:N",)`) — never invented, never merged. Length mismatches between
`text_word`, `text_word_boxes`, `rec_texts`, `rec_scores` → `MalformedGeometry` for the PAGE (the
rung then FAILS the document with `paddle_evidence_malformed`; no partial page). Boxes that are
inverted/degenerate/outside the raster are refused by `evidence/` itself — do not pre-clamp. `raw` =
the whole result dict (minus nothing; the worker already dropped `input_path`), frozen and hashed by
`PageEvidence`. `lines` derived by `evidence.group_lines` (through `PageEvidence`'s default).
Nothing here reads an amount, a date, a sign, a header; the adapter has no idea what a statement is.
`evidence_from_pages(pages, *, document_sha256, runtime) -> ExtractionEvidence` with
`extractor_id=PADDLE_EXTRACTOR_ID`, `model_token=PADDLE_MODEL_TOKEN`, `runtime` = the identity block
the worker echoed + `{"provider", "execution_class", "gpu", "worker_contract", "dpi"}` — NEVER the
URL, host, port, token or request ids.

## 4. `ocr/paddle_rung.py` — the rung (the ONLY thing cell R wires into the ladder)
```python
@dataclass(frozen=True)
class PaddleRead:
    pages: list[str]                 # evidence.page_texts(): D9's geometric page strings, in order
    evidence: ExtractionEvidence     # immutable; the artifact's `document.evidence` (cell R stores it)
    page_extractor: list[str]        # [PADDLE_MODEL_TOKEN] * len(pages)
    telemetry: dict                  # per page {inference_ms, total_ms, bytes_sent, bytes_received,
                                     #   width, height, cold_load, gpu_memory_used_mib} + totals; NEVER content

def read_document(pdf_bytes: bytes, *, document_sha256: str, data_scope: str,
                  settings: PaddleSettings | None = None, client: PaddleClient | None = None,
                  dpi: int = PADDLE_RASTER_DPI) -> PaddleRead
```
Order, fail closed, no bytes leave before step 4: (1) `settings = settings or load_paddle_settings()`
(→ `PaddleConfigError` surfaces as `PaddleRefused("paddle_config_missing", <variable name>)`);
(2) `check_remote_authorization(settings, data_scope)` (CASE 13 / CASE 20); (3)
`client.verify_identity(settings)` (D5 / CASE 16); (4) rasterise every page with
`ocr.rasterize.rasterize_pdf(pdf_bytes, dpi=dpi)`; read each page's `rect` (width/height in points,
display orientation) and `rotation` with PyMuPDF (`fitz`, already an `ocr/` dependency); build
`PageFrame.pixel(page_index=i, raster_width_px=image.width, raster_height_px=image.height, dpi=dpi,
pdf_width_pt=rect.width, pdf_height_pt=rect.height, raster_sha256=<sha256 of the PNG bytes>,
rotation_deg=page.rotation)` — a frame that refuses (scale disagreement: the raster is not this
page's) FAILS the document (`paddle_frame_mismatch`), never proceeds; (5) PNG-encode each page,
`client.ocr_page(...)`, adapt; (6) assemble `PaddleRead`. Transport failures propagate as
`PaddleTransportError` (the caller records `paddle_rung=failed` + the class name; CASE 18 — no other
host, no other extractor is ever tried from here). `pdf_bytes` is never written to disk; page PNGs
exist only in memory. A page count of 0 → `PaddleRead([], …)` with an evidence of zero pages — no
invention.

## 5. `tools/paddle_vast.py` — the lifecycle tool
Subcommands: `check` (env names present — values NEVER printed; `ssh -p … nvidia-smi
--query-gpu=name,memory.total --format=csv`; `/venv/main` versions == pins; prints `<HOST>`),
`deploy` (`scp ocr/paddle_worker.py` → `/workspace/ci_paddle/paddle_worker.py`; `--self-check` there),
`start` (remote `nohup /venv/main/bin/python /workspace/ci_paddle/paddle_worker.py` with
`PADDLE_PROVIDER`, `PADDLE_EXECUTION_CLASS`, `PADDLE_WORKER_PORT`, `PADDLE_WORKER_TOKEN` exported on
the remote command line from the LOCAL settings' provider/class and a token generated per session
(`secrets.token_urlsafe(32)`, written to `<runtime_dir>/worker.token` with mode 0600 semantics where
the platform allows; never printed); pidfile on the remote at `/workspace/ci_paddle/worker.pid`; waits
for `/health` THROUGH THE TUNNEL, not by exposing anything), `tunnel-up` (`ssh -N -o
ExitOnForwardFailure=yes -o BatchMode=yes -L 127.0.0.1:<local>:127.0.0.1:<remote> -p <port>
<user>@<host>` as a detached `subprocess.Popen`, pid in `<runtime_dir>/tunnel.pid`; refuses if the
local port is already listening), `tunnel-down`, `status` (masked settings + `probe()` result +
remote `nvidia-smi` summary), `stop`, `measure` (§6). Every subprocess argument that contains the
host/port/user is built from `settings`, never echoed; the tool's own output is scanned by a test for
the placeholder host of `tests/test_paddle_config.py` to prove masking. The tool refuses any
`measure --fixture` path under `Bank Statements/`, `tests/corpus_cache/` or `discovery_reports/`.

## 6. Measurements (D8; the closure's §25 figures) — `tools/paddle_vast.py measure`
Synthetic fixture set: build it in `tests/paddle_synthetic.py` (importable by the tool and the tests):
a rendered "statement-like" page family — a header line, a column header row (DATE / DESCRIPTION /
AMOUNT / BALANCE), N ledger rows of OBVIOUSLY synthetic literals (dates in a fixed year, descriptions
like `SYNTHETIC ROW 07`, amounts and balances generated arithmetically so the running balance chains),
rendered (a) as a native PDF with PyMuPDF (`fitz.open()`, `insert_text`, known positions) and (b) as
an image-only PDF (the same page rasterised at 300 dpi and re-embedded with `insert_image`) — this is
the pair CASE 5/6 and the end-to-end synthetic proof use. `measure` sends the image-only pages: cold
model-load latency (first request after `start`), warm latency (median/p95 over ≥ 20 requests),
per-page inference (`timing.inference_ms`), end-to-end (rasterise + encode + transfer + infer + adapt,
wall clock), bytes sent/received per page, peak local RSS (`resource`/`psutil` if present, else
`tracemalloc` + a note), remote RAM + GPU VRAM used + GPU utilisation sampled via `ssh nvidia-smi`
during the warm run, total GPU-attributable seconds (worker wall time between `start` and `stop`),
and paid cost = seconds × hourly rate IF the rate is discoverable (`vast-capabilities` JSON on the
host, or `--hourly-rate` supplied by Ocean/Gustavo) else `"rate not measured"` — never a guess. Write
`docs/moneythumb-replacement/PADDLE_MEASUREMENTS.md` (numbers, the fixture description, the commands,
the worker identity block — NO host/port/token, NO customer document) and the raw JSON to
`<runtime_dir>/measure-<utc>.json` (gitignored).

## 7. The fake worker (the default suite's ONLY worker)
`tests/paddle_fake_worker.py::FakeWorker` — a context manager running an in-process
`ThreadingHTTPServer` on `127.0.0.1` port 0 implementing the SAME contract from a canned result
source (the demo fixture, or `tests/paddle_synthetic.py`'s deterministic generator that turns a
rendered page into a 3.7-shaped result from the KNOWN word positions — no OCR); configurable
identity (defaults = the pins), token, per-request failure injection (500, malformed JSON, oversized
body, hang until timeout, refuse connections by not starting), and a `requests` log (count, bytes,
page indices — never image content). Cell R's tests will import it; keep its constructor stable and
documented.

# Files you own (exact; nothing else)
`ocr/paddle_worker.py` · `ocr/paddle_client.py` · `ocr/paddle_adapter.py` · `ocr/paddle_rung.py` ·
`tools/paddle_vast.py` · `tests/paddle_fake_worker.py` · `tests/paddle_synthetic.py` ·
`tests/test_paddle_worker.py` · `tests/test_paddle_client.py` · `tests/test_paddle_adapter.py` ·
`tests/test_paddle_rung.py` · `tests/test_paddle_vast_tool.py` · `tests/test_paddle_live.py`
(`pytestmark = pytest.mark.live` + `skipif` unless `load_paddle_settings()` succeeds AND the remote
opt-in literal is set AND `probe()` is available) · `tests/fixtures/paddle/` (add synthetic
fixtures; never a real statement) · `.env.paddle.example` (placeholders only) ·
`docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md` · `docs/moneythumb-replacement/PADDLE_MEASUREMENTS.md`
· your W3 section. `ocr/paddle_config.py` is Ocean's: you may APPEND (a new constant, a new refusal
reason) with a line in your report; never change an existing value. Not yours: `ocr/pipeline.py`,
`ocr/document.py`, `ocr/escalation.py`, `ocr/config.py`, `webapp/`, `discovery/`, `telemetry/`,
`evidence/`, `analysis/`.

# Tests / cases you must prove (in the default suite unless marked live)
CASE 5 (adapter half): the demo fixture → 33 lines / 62 words → every word's box reproduces from
`raw` → `to_json`/`from_json` sha round-trip; the synthetic ledger page → its known words in reading
order · CASE 7: `confidence` lives ONLY on `WordBox`/`raw`; `PaddleRead.pages` strings contain no
score; a mutant setting every `rec_scores` to 1.0 (and to 0.0) leaves `pages` byte-identical · CASE 8:
each malformed shape (length mismatch, inverted box, out-of-raster box, missing key, non-list
`text_word`) refuses the page and the rung fails the document — no partial evidence · CASE 11: the
token/extractor id/provenance block through `validate_model_token`; `runtime` contains no URL/host/
port/token (assert on the JSON) · CASE 13: opt-in absent / wrong / the visual literal → refused before
the fake worker sees a connection (assert `requests == []`); present → the request is made · CASE 16:
declaration `vast.ai`/`remote_paid` + a fake worker echoing `local`/`local_free` (or any single
mismatching field) → `paddle_runtime_mismatch`, zero `/ocr` requests; the evidence `runtime` records
`vast.ai`/`remote_paid` on success, and the URL was loopback throughout · CASE 17: every missing
variable → `paddle_config_missing` naming it; no opener call · CASE 18: connection refused, timeout,
500, malformed JSON, oversized response, redirect → `PaddleTransportError` with the class name;
exactly one URL ever contacted (the opener records) · CASE 20: `data_scope="customer"` on remote
without the second literal → `remote_customer_data_refused`, zero requests; `"synthetic"` proceeds;
local_free proceeds for both · worker unit tests (offline, no paddleocr): every bound and error
token; loopback-only bind refusal; token required when set; `/version` shape · lifecycle tool tests
(subprocess calls mocked): argument construction never prints the host; refuses customer paths ·
LIVE (`tests/test_paddle_live.py`, deselected): the real worker over the real tunnel on the synthetic
image-only PDF → word boxes returned → evidence sha stable across two runs → the identity block
equals the pins → `PaddleRead.pages` non-empty and the ledger rows regroup.

# Mutation table (run every mutant, name every killer)
M1 skip `check_remote_authorization` → CASE 13/20 · M2 `verify_identity` compares only the contract
→ CASE 16 per-field · M3 client accepts a non-loopback URL → the URL refusal test · M4 retry to
`http://localhost:8000/v1` (the visual endpoint) on failure → CASE 18's single-URL assertion · M5
adapter clamps an out-of-raster box → CASE 8 · M6 adapter joins `rec_texts` instead of grouped words →
the reading-order test on the two-column synthetic page · M7 confidence filter (`< 0.5` dropped) →
CASE 7's 0.0 mutant · M8 worker binds `0.0.0.0` → the bind refusal · M9 worker accepts 40 MiB → the
bound test · M10 `runtime` carries `worker_url` → CASE 11's JSON assertion · M11 rung writes the PDF
to a temp file → an AST/`tempfile`/`open(` scan of `ocr/paddle_rung.py` · M12 `measure` accepts a
`Bank Statements/` path → the refusal test.

# Proof floor
Full default suite; the 5 canonical guards (the OQ2 scan covers `ocr/*.py` — your modules included:
no literal amounts, dates, account digits, issuer strings); the 7 canonical conformance files;
`python corpus_gate.py` GREEN; `pytest -m corpus`; privacy scan 0 over your added lines against the
Phase 2.0 run of record; message scan 0; **a secrets scan**: `git diff <base>..HEAD` contains no
occurrence of the VALUES of `PADDLE_VAST_HOST` / `PADDLE_VAST_SSH_PORT` / `PADDLE_VAST_SSH_USER`
(compare against `os.environ` at scan time; report the count, 0); the live test run ONCE by you with
its numbers in your report; `tools/paddle_vast.py stop` + `tunnel-down` executed at the end (the
worker does not stay running unattended; say so).

# Report contract (final message to Ocean AND your W3 section `# §P21PADDLE — …`)
population (synthetic fixtures only — say so) · root cause · solution · newly validated (0) ·
previously validated preserved (all — nothing on the offline path changed) · regressions (0) ·
correctness evidence (the case table, the mutation table) · remote evidence (opt-in state,
declaration + corroboration, bytes sent, the identity block, the measurements) · generalization
evidence (the worker is provider-agnostic; what a `local_free` deployment would need) · commits ·
proof-floor exits · privacy + secrets counts · risks last.

# Exclusions
No wiring into `parse_statement` / `discovery` / the webapp (cell R). No Unlimited OCR. No PP-Structure,
no PP-OCRv6, no doc-preprocessing switches. No character fusion, no confidence filtering, no value
interpretation. No public exposure of the worker (no Vast "open port", no Caddy route, no `0.0.0.0`).
No customer document, ever. No second host, no fallback URL. No Kubernetes/queues/multiple workers.
