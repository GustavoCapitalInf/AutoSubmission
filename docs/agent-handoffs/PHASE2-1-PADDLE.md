# Phase 2.1 — PADDLEOCR + CANONICAL WORD BOXES + DOCUMENTGEOMETRY (umbrella implementation card; Ocean, 2026-09-02)

**Authority:** Gustavo's Phase 2.1 authorization, Ruling A (automatic hosted extraction REFUSED),
Ruling B (density SURFACE-ONLY) and the explicit Vast.ai authorization — all recorded in
`docs/moneythumb-replacement/PHASE2_RULINGS.md` §"Phase 2.1 rulings and authorization"; OQ1–OQ11
(same file); the accepted architecture (`PHASE2_ARCHITECTURE_PLAN.md` §1–§5, §9, §10, §17 "Phase
2.1"); the standing rules (`BATCH9-RULES.md` + `PHASE2-RULES.md`, both carried forward in full —
the Phase-2.1 delta is §"Rules delta" below). Every Phase 2.0 safety invariant is binding and is
listed in the rulings file. **Validator success may STOP escalation; validator failure may NEVER
START escalation.**

## Objective (exact)
The first visual extractor that emits **geometry**, not only text: PaddleOCR 3.7.0 / PP-OCRv5 with
word boxes, executed on the explicitly authorized Vast.ai RTX 5090 development worker, producing
**immutable raw evidence → canonical words/lines → `DocumentGeometry`**, feeding the SAME
deterministic validator through the SAME `StatementMarkdown` seam, allowed to run ONLY on an admitted
Class-A trigger (R + U-extract; today 13 + 0 = 13 documents). At the same time, native PDF word
boxes (PyMuPDF) fill the SAME `DocumentGeometry` through the SAME canonical-evidence representation,
so Phase 2.2's reconstruction can consume one geometry regardless of source. Expected coverage
movement: **see §Corpus measurement — the 13-document legal population is NOT sent to Vast in this
phase (privacy boundary); OCR-fed `validated` at closure is 0 unless Gustavo separately authorizes the
remote-data run.** The 2,625 floor is untouched.

## Baseline (verified 2026-09-02 before anything moved)
| fact | value |
|---|---|
| `origin/main` = `HEAD` | `9a54952` (docs tip on Phase 2.0; code tree `941918f`) |
| `phase2.0-final` | `fc09631` (annotated; on origin); CI 33605871579 SUCCESS |
| train branch | **`train11`** (opened from `origin/main` `9a54952`) |
| floor | 2,625 / 3,380; Phase 2.0 cold run `TRAIN10-941918f/2026-09-02T063646.710847-0000-ef34ee30` 2,625 → 2,625, 3,380 unchanged; its cold cache `.claude/recovery/webapp_data_train10_cold` (READ-ONLY; offline OCR key `32F00F24…` at OCR_STAGE_VERSION 5; analysis key `7799FEE4…` at ANALYSIS_STAGE_VERSION 17) |
| versions | OCR_STAGE_VERSION 5 · EXTRACTION_SCHEMA_VERSION 1 · RASTER_VERSION 1 · ANALYSIS_STAGE_VERSION 17 · registry 84 |
| suite at `941918f` | 8,342 passed / 45 skipped / 38 deselected; guards 267; conformance 1,282; gate 105/3/1 |
| triggers (Phase 2.0 run of record) | R 13 · U 123 · U-extract 0 · U-structure 123 · density-surfaced 23 · legal escalation population **13** · validated∩class-A 0 |
| local toolchain | Python 3.14.5 (CI pins 3.12 — write for both); PyMuPDF 1.27.2.3; Pillow 12.2.0; tesseract 5.5.0; poppler 24.08.0; **no `paddleocr` locally** (the adapter/client never import it) |
| Vast host (from `PADDLE_VAST_*` env; never written down) | reachable over SSH with the existing key; RTX 5090 32,607 MiB idle; `/venv/main` Python 3.12.14, **paddleocr 3.7.0, paddlepaddle-gpu 3.3.0, paddlex 3.7.2**, CUDA 13.0 driver 580.173.02; cached official models `PP-OCRv5_server_det` + `en_PP-OCRv5_mobile_rec`; the proven word-box result at `/workspace/paddle_output_wordboxes/paddle_demo_res.json` (public PaddleOCR demo image, non-sensitive) — keys `input_path, page_index, model_settings, dt_polys, text_det_params, text_type, textline_orientation_angles, text_rec_score_thresh, return_word_box, rec_texts, rec_scores, rec_polys, rec_boxes, text_word_boxes, text_word`; `rec_boxes` = `[x0,y0,x1,y1]` int pixels, `rec_polys` = 4-point pixel polygons, `text_word` = list-of-words per line, `text_word_boxes` = list-of-`[x0,y0,x1,y1]` per word per line, `rec_scores` = per-line float; loopback ports 8765/8766 free; Jupyter on 0.0.0.0:8080 (never reused); no `fastapi`/`uvicorn` in the venv (stdlib worker) |

## Scope — four bounded cells, disjoint file ownership; Ocean owns the evidence contract
| cell | card | delivers | cases |
|---|---|---|---|
| **0 (Ocean, first)** | this file §Evidence contract | the extractor-neutral package **`evidence/`** — canonical words/lines/pages, coordinate frames, JSON round-trip, the ONE geometric line-grouping function, evidence hashing. Committed on `train11` before the cells open; every cell builds against it. | contract for 5, 6, 8 |
| **G** | `P21-GEOMETRY.md` | `analysis/structurer/geometry.py` gains `PageFrame` + `geometry_from_evidence`; `geometry_from_pdf` is re-homed onto native evidence (byte-identical behaviour, pinned); explicit, tested coordinate conventions and conversions; malformed/ambiguous geometry refuses | 5 (geometry half), 6, 8 |
| **P** | `P21-PADDLE.md` | `ocr/paddle_config.py` (env contract, opt-ins, pins), `ocr/paddle_worker.py` (the remote loopback service), `ocr/paddle_client.py` (bounded HTTP client), `ocr/paddle_adapter.py` (Paddle 3.7 result → canonical evidence), `ocr/paddle_rung.py` (rasterize → worker → pages + evidence), `tools/paddle_vast.py` (check / deploy / start / tunnel / status / stop / measure), the fake-worker test double, the live (opt-in, deselected) proofs, the runtime/cost measurement on synthetic fixtures | 5 (adapter half), 7, 11, 13, 16, 17, 18, 20 |
| **R** | `P21-ROUTING.md` | the router's `enabled` extractor set and `EXTRACTOR_ORDER` slot filled; `parse_statement(allow_paddle_ocr=…)`; `StatementMarkdown.page_extractor` / `.evidence`; the artifact record + `EXTRACTION_SCHEMA_VERSION` 2; the OCR settings key's Paddle identity block; `discovery` mode `--scanned-paddle`, `_read_paddle`, row columns; vocabularies (`SOURCE_PATHS`, model token, `GATE_ASSESSED_SOURCES`); telemetry + run-of-record + `tools/train/provenance.py` partitions; the customer-data refusal at the runner; the cases that prove the forbidden edges are absent | 1, 2, 3, 4, 9, 10, 12, 14, 15, 19 |

Composition order at the train: **0 → G → P → R** (contract, then the two consumers of it, then the
wiring that consumes both). Ownership is disjoint by construction (see each card); any overlap
discovered is reported to Ocean, never resolved by a cell.

## Material design decisions (Ocean; each is inside Phase 2.1, preserves every binding invariant, and is a reviewed decision)
Format per the authorization: original expected approach → what changed → why better → new risks →
tests/tripwires → recorded here → in review → proved on the composed tree.

**D1 — an extractor-neutral `evidence/` package, not Paddle types inside `ocr/`.** *Expected:* Paddle
evidence dataclasses in `ocr/`, consumed by `analysis/structurer/geometry.py`. *Changed:* a new
top-level package `evidence/` (imports nothing from `ocr`, `analysis`, `discovery`, `webapp`,
`telemetry`) holds the canonical representation; `ocr/paddle_adapter.py` produces it and
`analysis/structurer/geometry.py` consumes it. *Why:* the Phase 2.0 tripwires pin the analysis→ocr
import allowlist EMPTY and forbid ocr→analysis in the ladder; an evidence type owned by either side
forces one boundary to widen. A neutral data package keeps both boundaries exactly as pinned and gives
"one geometry representation regardless of extraction source" a real home. *Risks:* a third place for
coordinate conventions to drift. *Tripwires:* `tests/test_evidence_boundary.py` — `evidence/` imports
only stdlib; the analysis allowlist stays `frozenset()`; `ocr/` never imports `analysis`; one
line-grouping function exists (geometry.py's `_group_lines` is pinned to delegate to it, native output
byte-identical to Phase 2.0 on the structurer fixtures).

**D2 — execution class by DECLARATION, corroborated by the worker; never by URL.** *Expected:* record
`provider`/`execution_class` from env. *Changed:* additionally, the worker's `/version` MUST echo the
same `provider` and `execution_class` (set on the remote from ITS environment by the lifecycle tool),
and the client refuses a mismatch before sending any image. `ocr.endpoint_policy.classify_endpoint`
is never consulted for Paddle's class (it would say `loopback`); the Paddle client accepts ONLY a
loopback worker URL (the tunnel is the transport) and refuses anything else. *Why:* CASE 16 becomes
structural — two independent sources must agree, and the URL cannot vote. *Risks:* an operator could
mislabel both ends identically. *Tripwires:* the label pair is validated against the closed vocabulary
(`vast.ai`⇒`remote_paid` only; `local`⇒`local_free` only); mutation tests on every mismatch.

**D3 — a Paddle-specific opt-in literal.** *Expected:* reuse `OCR_REMOTE_OPT_IN`. *Changed:*
`PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR` (exact `==`, never truthy), independent of the
visual rung's literal. *Why:* one opt-in must not authorize two paid extractors; each remote/paid
decision is recorded on its own. *Risks:* none new. *Tests:* CASE 13 both directions; the visual literal
alone does NOT enable Paddle and vice versa.

**D4 — `RouterInputs` gains a sixth field, `enabled: frozenset[str]` (a MODE constant).** *Expected:*
the runner post-filters the router's pick by mode. *Changed:* the router chooses the first extractor in
`EXTRACTOR_ORDER = ("local_tesseract", "paddle", "visual")` that is `enabled` and not `attempted`.
*Why:* the honest alternative (marking a not-enabled extractor "attempted") lies on the row, and a
post-filter silently turns "the router named paddle" into "visual never runs" in `--scanned-visual`
mode; `enabled` is known before any document is read (a run/mode fact, pre-financial by construction)
and keeps existing visual-rung behaviour byte-identical (`enabled={"visual"}`). *Risks:* the pinned
five-field set widens — the property that matters (no payload / outcome / dispatch / financial field)
is preserved. *Tripwires:* the field pin becomes six names; `router_inputs(...)` keyword-only with
`enabled`; a repo-wide AST tripwire that every `enabled=` argument at a `decide(` call site is a
runner/mode attribute reference (`self.enabled_extractors` or a module constant), never a per-document
expression; `RouterInputs.__subclasses__() == []` unchanged.

**D5 — runtime identity PINNED in code and VERIFIED against the worker; the cache key uses the pin.**
*Expected:* read versions from the worker into the key. *Changed:* `ocr/paddle_config.py` pins
`PADDLEOCR_VERSION = "3.7.0"`, `PADDLEPADDLE_VERSION = "3.3.0"`, `OCR_VERSION = "PP-OCRv5"`,
`TEXT_DETECTION_MODEL = "PP-OCRv5_server_det"`, `TEXT_RECOGNITION_MODEL = "en_PP-OCRv5_mobile_rec"`,
the pipeline switches (`use_doc_orientation_classify=False`, `use_doc_unwarping=False`,
`use_textline_orientation=False`, `return_word_box=True`, `text_rec_score_thresh=0.0`) and
`PADDLE_WORKER_CONTRACT = 1`; the rung refuses a worker whose `/version` differs on ANY of them. *Why:*
the OCR settings key must be computable offline (cache lookups make no network call) and a model/version
change must be an explicit, reviewed edit that opens a new partition — never a silent drift (the
silent-PP-OCRv6 hazard). *Risks:* a remote upgrade stops the rung until the pin is reviewed — the
intended direction. *Tests:* every pin field mutated one at a time on the fake worker → refused
(`paddle_runtime_mismatch`), no image sent.

**D6 — raw evidence lives INSIDE the OCR artifact record (`document.evidence`), not a separate stage.**
*Expected:* a sidecar file. *Changed:* `EXTRACTION_SCHEMA_VERSION` 1 → 2: the record gains
`page_extractor: list[str]` (per-page provenance, all rungs) and `evidence: dict | None` (the full
canonical evidence with the verbatim raw Paddle result per page, its sha256, rasters' hashes and dpi).
*Why:* one key, one atomic write, one run-of-record selection; "raw next to derived" literally; every
existing reader (`cohort_replay`, `_ArtifactJoin`, the fixpriv instruments) reads `document.pages` and
ignores extra keys. *Risks:* the offline partition's key changes too (the schema version is key material
for every extractor) → the whole OCR cache is cold at the train's cold run (~73 min at Phase 2.0's
pace) — REQUIRED anyway by the completion gate. *Tests:* the `EXTRACTION_SCHEMA_VERSION == 2` pin in the
same commit; round-trip `put_ocr`/`cached_ocr` with evidence; a cache hit reproduces `evidence` sha
byte-for-byte; `to_markdown()` byte-identical (the committed corpus artifacts pin it).

**D7 — a stdlib-only, loopback-bound, bounded worker with no retention (no FastAPI/uvicorn).**
*Expected:* a small web framework service. *Changed:* `ocr/paddle_worker.py` uses
`http.server.ThreadingHTTPServer` + `json` + Pillow + numpy + paddleocr — nothing else — binds
`127.0.0.1` only, refuses non-loopback bind, enforces max body 32 MiB, PNG only, one image per
request, max side 6,000 px, max 30 MP, `Image.MAX_IMAGE_PIXELS` set, decompression-bomb-safe decode,
serialised inference (one at a time), per-request timeout, an optional bearer token (generated per
session by the lifecycle tool, never committed), `/health` and `/version` separate from `/ocr`, no
filesystem paths accepted, nothing written to disk, no logging of content. *Why:* smaller supply-chain
and attack surface on a third-party host; the same JSON contract serves a future `local_free` worker
unchanged. *Risks:* fewer conveniences. *Tests:* the worker module is importable locally WITHOUT
paddleocr (the paddle import is inside the inference function) so its request validation is unit-tested
offline; every bound has a refusal test; the live proof runs the real worker over the tunnel.

**D8 — the corpus measurement over the legal population is NOT executed through Vast in Phase 2.1.**
Not an improvement — a scope consequence of the privacy boundary, stated up front so no cell "helpfully"
runs the archive. The 13 R documents are production customer statements. The runner therefore
declares `data_scope="customer"` on every document it reads, and the Paddle rung on a `remote_paid`
worker REFUSES that scope unless a SECOND literal is set
(`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN=I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR`) — which this
phase never sets and which the runbook says requires Gustavo's separate remote-data / privacy /
retention ruling (CASE 20). The end-to-end pipeline (Paddle → evidence → geometry → `StatementMarkdown`
→ the SAME validator) is proved on SYNTHETIC statements rendered by the test suite (native PDF with
known words via PyMuPDF; the same page rasterised into an image-only PDF), and the runtime / cost
measurements are taken on those. Phase 2.1's coverage report names Paddle-eligible = 13, attempted =
0 (privacy boundary), newly validated = 0, with the reason. Gustavo's ruling on the 13-document remote
run is requested in the closure report.

**D9 — page text for the validator is derived GEOMETRICALLY from word boxes, by the one grouping
function.** *Expected:* join Paddle's `rec_texts` in order. *Changed:* words (from `text_word` /
`text_word_boxes`) are grouped into visual lines by y-overlap with a tolerance derived from the page's
own median word height (the existing `geometry.py` rule), ordered top-to-bottom / left-to-right, and
each line's words joined by single spaces; the page string is those lines joined by `\n`. *Why:* Paddle's
detection segments split a ledger row into date / description / amount polygons; the validator's
parsers expect a Tesseract-shaped row per line; and the SAME lines feed `DocumentGeometry`, so what the
parser reads and what the structurer sees are one object. Never OCR newline formatting as financial
structure. *Risks:* two words on one row whose boxes overlap vertically less than the tolerance split
into two lines — a read error the validator surfaces, never a rewrite. *Tests:* CASE 5 round-trip and a
synthetic two-column ledger whose rows regroup exactly.

## Evidence contract (`evidence/` — Ocean, cell 0; frozen before the cells open)
```
evidence/__init__.py
evidence/canonical.py
    CoordinateSpace: "pdf_point" | "pixel"            (closed vocabulary; refused otherwise)
    PageFrame(frozen): page_index (0-based), space, width, height        (of the space's own units)
                       pdf_width_pt, pdf_height_pt (page size in points, from the PDF; None if unknown)
                       raster_width_px, raster_height_px, dpi, raster_sha256 (None for native)
                       rotation_deg (the PDF page's /Rotate as applied by the rasteriser; 0 for native)
                       scale_x, scale_y (units-of-`space` per PDF point; 1.0 for pdf_point)
    WordBox(frozen):  word_id, text, x0, y0, x1, y1, confidence (float | None), line_ref (raw
                       line index in the extractor's own output; None for native), page_index
    LineBox(frozen):  line_id, page_index, y_top, y_bottom, word_ids (ordered), text (space-joined)
    PageEvidence(frozen): frame, words (tuple, in extractor order), lines (tuple, derived), raw (dict |
                       None — the extractor's verbatim per-page result), raw_sha256
    ExtractionEvidence(frozen): document_sha256, extractor_id, model_token, runtime (dict: versions,
                       provider, execution_class, gpu, settings key material), pages (tuple),
                       evidence_sha256 (sha256 over canonical JSON of everything but this field)
    group_lines(words, *, tolerance=None) -> tuple[LineBox, ...]   THE ONE grouping rule
    page_text(page: PageEvidence) -> str                             D9's page string
    to_json / from_json (deterministic; sort_keys, no floats re-rounded on round-trip)
    coordinate helpers: to_pdf_points(frame, x, y) / to_pixels(frame, x, y); origin TOP-LEFT, y DOWN
                       in BOTH spaces; bbox order (x0, y0, x1, y1) with x0<=x1, y0<=y1 enforced
```
Invariants pinned by `tests/test_evidence_canonical.py`: immutability (frozen; `raw` is deep-frozen on
construction — a `MappingProxyType` tree — and `to_json` of `raw` equals the sha it was hashed with);
`page_text` never reorders words within a line except by x; ids are `p{page}.l{line}.w{index}`;
mixed-space words on one page refuse; `pixel` frames require dpi and raster dims; `pdf_point` frames
require pdf dims; scale consistency `|scale − dpi/72| ≤ 1 %` or refuse; every `WordBox` x0≤x1 / y0≤y1
or refuse (no silent swap).

## Configuration contract (cell P; `ocr/paddle_config.py`)
| variable | required | meaning |
|---|---|---|
| `PADDLE_PROVIDER` | yes | closed vocabulary `vast.ai` \| `local` |
| `PADDLE_EXECUTION_CLASS` | yes | closed vocabulary `remote_paid` \| `local_free`; `vast.ai` ⇒ `remote_paid` only, `local` ⇒ `local_free` only; any other pairing refused |
| `PADDLE_VAST_HOST` / `PADDLE_VAST_SSH_PORT` / `PADDLE_VAST_SSH_USER` | when provider = `vast.ai` | the SSH endpoint; absence → `PaddleConfigError` naming EXACTLY the missing variable; never defaulted, never logged in full (reports print `<HOST>`) |
| `PADDLE_REMOTE_OPT_IN` | when class = `remote_paid` | must equal `I_ACCEPT_REMOTE_PAID_PADDLE_OCR` exactly |
| `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` | never in Phase 2.1 | `I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_PADDLE_OCR` — D8; the runbook forbids setting it without Gustavo's ruling |
| `PADDLE_WORKER_PORT` | no (default `8765`) | the worker's LOOPBACK port on the host that runs it |
| `PADDLE_TUNNEL_LOCAL_PORT` | no (default `18765`) | the local loopback end of the SSH tunnel (distinct from the remote port by default so "localhost" reads as a tunnel, not a service) |
| `PADDLE_WORKER_URL` | no (derived `http://127.0.0.1:<local port>`) | override allowed ONLY to a loopback URL; anything else refused |
| `PADDLE_WORKER_TOKEN` | no | optional bearer token; the lifecycle tool generates one per session into the gitignored runtime dir and passes it to both ends |
| `PADDLE_RUNTIME_DIR` | no (default `.paddle_runtime/`, gitignored) | pidfiles, session token, tunnel log |
Committed: `.env.paddle.example` with placeholders only (`PADDLE_VAST_HOST=<set in your shell>`),
`docs/moneythumb-replacement/PADDLE_VAST_RUNBOOK.md`. Pins (code constants, not env): see D5.
`ocr/config.py`'s dotenv load already reads a gitignored `.env`; the tracked example must contain no
real value (the privacy scanner + a test assert no IP / port literal in tracked Paddle files).

## Vast runtime design (cell P)
```
local app ── http://127.0.0.1:18765 ──▶ ssh -N -L 127.0.0.1:18765:127.0.0.1:8765 ──▶ Vast container
                                                                                        │ 127.0.0.1:8765
                                                                                        ▼
                                                                          ocr/paddle_worker.py (/venv/main)
                                                                                        │
                                                                                        ▼
                                                                          PaddleOCR 3.7.0 · PP-OCRv5 · RTX 5090
```
* `tools/paddle_vast.py check` — env present (names only), `ssh … nvidia-smi`, `/venv/main` versions
  equal the pins; prints `<HOST>` never the value. `deploy` — `scp` `ocr/paddle_worker.py` +
  `evidence/canonical.py` to `/workspace/ci_paddle/` (the worker imports only stdlib + paddleocr;
  the canonical module is copied so the worker can validate its own output shape against the same
  contract; nothing else from the repo goes remote). `start` — `nohup` the worker under `/venv/main`
  bound to `127.0.0.1:$PADDLE_WORKER_PORT` with `PADDLE_PROVIDER` / `PADDLE_EXECUTION_CLASS` /
  token exported on the remote side; waits for `/health`. `tunnel-up` / `tunnel-down` — the SSH
  forward as a detached process with a pidfile; `ExitOnForwardFailure=yes`; `status`; `stop`.
  `measure` — the runtime/cost measurement (§Telemetry) on synthetic fixtures ONLY (it refuses a
  path under `Bank Statements/` or `tests/corpus_cache/`).
* Worker contract v1 — `GET /health` → `{"ok": true, "contract": 1}`; `GET /version` → contract,
  provider, execution_class, gpu {name, memory_total_mib, driver}, paddleocr_version,
  paddlepaddle_version, cuda_compiled, ocr_version, text_detection_model_name,
  text_recognition_model_name, model_settings, python_version, worker_started_at; `POST /ocr`
  `{"contract": 1, "request_id", "page_index", "image_png_b64"}` → `{"raw": <the PaddleOCR 3.7
  result dict verbatim, minus input_path>, "image": {width, height, sha256}, "timing":
  {decode_ms, inference_ms, total_ms, cold_load: bool}, "gpu": {memory_used_mib}, "model": <the
  identity block>}`. Errors are JSON `{"error": <closed token>}` with 4xx/5xx; never a traceback with
  content.
* Security boundary: loopback bind enforced (refuses `0.0.0.0`); bounded sizes (D7); PNG magic
  checked before decode; JSON depth/size bounded; no path parameters; no retention; the optional
  token; the SSH tunnel is the only transport; the worker is never registered as a Vast "open port"
  and never fronted by Caddy.

## Extraction routing (cell R)
* `ocr.escalation.EXTRACTOR_ORDER = ("local_tesseract", "paddle", "visual")`; `RouterInputs.enabled`
  (D4); `decide` = `stop` → refuse; no admitted trigger → refuse; first extractor in order that is
  enabled and not attempted, else `no_allowed_extractor_remains`. `ADMITTED_TRIGGERS` unchanged (T
  still refused; the density SIGNAL still never a trigger — Ruling B).
* `ocr.pipeline.parse_statement(..., allow_paddle_ocr: bool = False, paddle_data_scope: str | None =
  None)`: the Paddle rung runs ONLY when `force_ocr=True and allow_paddle_ocr=True and not
  allow_visual_ocr` (both OCR extractors allowed in one call → `ValueError`: the router chooses, the
  ladder does not); the non-forced ladder is UNCHANGED (native → Tesseract → return / `None`) — the
  Paddle rung is NOT a fallthrough of the auto path (CASE 12; Ruling A). `paddle_data_scope` ∈
  `{"synthetic", "customer"}` is REQUIRED with `allow_paddle_ocr` (D8).
* `discovery`: `MODE_SCANNED_PADDLE` (`--scanned-paddle`), `enabled_extractors = {"paddle"}`
  (`--scanned-visual` keeps `{"visual"}`); `_read_paddle` mirrors `_read_visual` into its own partition
  (`allow_paddle_ocr=True` is key material); the preflight probe (`paddle_client.probe`) refuses to
  start on config / opt-in / version / health failure; the escalation budget applies; the runner
  passes `paddle_data_scope="customer"` ALWAYS (it reads the archive) — so in Phase 2.1 a real
  `--scanned-paddle` archive run is REFUSED at the rung with `remote_customer_data_refused` and the
  row records it (`paddle_rung = refused_customer_data`), which is the measurement this phase reports.
* Rows: `paddle_rung` (same vocabulary as `visual_rung`: `not_attempted | recovered | upgraded |
  no_upgrade | failed | refused_customer_data`), `cache_paddle`, `escalation_extractor`
  (`"" | paddle | visual`), `evidence_sha256`, `paddle_provider`, `paddle_execution_class`; appended at
  the END of `ROW_FIELDS`.
* `GATE_ASSESSED_SOURCES` gains `"paddle"`; `classify_failure` unchanged; the row-level pin
  `validated ∩ class-A = 0` re-measured.
* Repo-wide AST tripwire: every `allow_paddle_ocr=True` call site is one of the reviewed ones
  (`discovery/runner.py::_read_paddle` only; the webapp is NOT wired to Paddle in 2.1 — Ruling A).

## Canonical evidence, adapter, word boxes, coordinates (cells P and G)
* `ocr/paddle_adapter.py::evidence_from_paddle(raw_pages, frames, *, document_sha256, runtime)`:
  for each page, words from `text_word[i][j]` / `text_word_boxes[i][j]` (line-level
  `rec_scores[i]` copied to each word as `confidence` — Paddle 3.7 scores lines, not words; recorded as
  such), `line_ref = i`; `dt_polys` / `rec_polys` / `rec_boxes` / `textline_orientation_angles` kept
  verbatim in `raw`; boxes validated (`x0≤x1`, `y0≤y1`, inside the raster) or the page refuses
  (`malformed_geometry`, CASE 8) — never clamped, never swapped; a word with empty text is dropped and
  counted (`dropped_empty_words`) — never invented. Lines by `evidence.group_lines`. Nothing about
  amounts, signs or dates is interpreted here.
* Coordinates: Paddle boxes are `pixel` space of the raster the rung produced (origin top-left, y
  down, integers); the frame carries dpi, raster dims, PDF page dims (points, from PyMuPDF's
  `page.rect` — display orientation) and `rotation_deg`; `scale = raster_px / pdf_pt` per axis,
  cross-checked against `dpi/72` (±1 %) or refused. `DocumentGeometry` stays in PDF points (the
  existing consumer convention); `geometry_from_evidence` converts pixel words to points through the
  frame; a `pdf_point` frame converts with scale 1. The conversion is deterministic and replayable from
  the artifact alone (the frame is stored in the evidence).
* `analysis/structurer/geometry.py`: `PageGeometry` gains `frame: PageFrame | None = None` and
  `source: str = "native"` (defaults keep every existing constructor call valid); `geometry_from_pdf`
  becomes `geometry_from_evidence(native_evidence_from_pdf(pdf_bytes))` with the SAME return on the
  structurer fixtures (pinned) and the same `None` answers; `_group_lines` delegates to
  `evidence.group_lines`.
* Native geometry (cell G): `evidence/native.py::native_evidence_from_pdf(pdf_bytes) ->
  ExtractionEvidence | None` — PyMuPDF `page.get_text("words")` → `WordBox` in `pdf_point`, frame from
  `page.rect` / `page.rotation`, `extractor_id="native-pdf-words"`, no raw, no confidence.

## Provenance / lineage
* Model token (closed charset, no money shape): **`paddle-ocr+ppocrv5`** — validated by
  `validate_model_token` at construction; NOT reserved-prefixed; `RESERVED_MODEL_PREFIXES` gains it so
  an env `OCR_MODEL` cannot impersonate the Paddle rung either. `SOURCE_PATHS` gains `"paddle"`;
  `source_path_for` maps exactly that token → `"paddle"` (any other `paddle*` string stays `"none"` /
  unrecognised — the P20-SEAM fallthrough test is updated to say so). `FREE_MODELS` does NOT gain it
  (remote_paid is not free; `price_for` → `None`, `estimate.complete = False`, the model named — cost is
  measured, never invented).
* `StatementMarkdown.page_extractor: list[str]` (one token per page: `native-pdf-text*` /
  `local-tesseract-ocr` / `paddle-ocr+ppocrv5` — set by the ladder for whichever rung produced the
  pages) and `StatementMarkdown.evidence: ExtractionEvidence | None`; `to_markdown()` unchanged
  byte-for-byte (the committed corpus artifacts pin it).
* OCR settings key (`extractor == "paddle"` branch): the D5 pin block + `provider` +
  `execution_class` + `paddle_worker_contract` + `evidence_schema_version` — NEVER host, port, token or
  URL. `allow_paddle_ocr` joins the boolean partition fields. `EXTRACTION_SCHEMA_VERSION` 1 → 2 with
  its pin in the same commit; `OCR_STAGE_VERSION` stays 5 (no existing extractor's output changes).
* Telemetry: `source_section` gains `evidence_sha256`, `provider`, `execution_class`; `model_calls_for`
  reports one call per Paddle page with `purpose: "paddle_ocr"`, inference ms and the unpriced model
  named. `telemetry/run_of_record.py` + `tools/train/provenance.py` gain the `paddle_ocr_key`
  partition and `paddle_rung ∈ {recovered, upgraded}` → that key.
* Lineage: every canonical word has `word_id` / `line_ref` / page / raster sha / dpi / settings key
  through the evidence; a parser-derived value's `evidence_refs[]` (field-level attribution) is NOT built
  in 2.1 (exclusion — the seam into the validator is unchanged); the path back from a page string to
  its words is `LineBox.word_ids` + `page_text`'s deterministic construction.

## Artifact / cache / replay implications
`cached_ocr` persists and restores `page_extractor` and `evidence` (a cache hit rebuilds the frozen
evidence from JSON; its sha must reproduce). `run_of_record` selects the Paddle partition only from a
row that names it. `tools/cohort_replay.py` needs no change beyond the partition vocabulary (it
replays through `run_of_record`). The Phase 2.0 cold cache (`webapp_data_train10_cold`) is READ-ONLY;
the train's cold run writes `webapp_data_train11_cold`.

## Runtime / cost telemetry (cell P, `tools/paddle_vast.py measure`; reported in the closure)
Per §25 of the authorization: Paddle-eligible documents/pages (13 / their page count from the run of
record) · attempted · executed · usable evidence · word boxes returned · extraction-quality failures ·
reconstruction/parser claims · validator accepted · newly validated · review · refuse · false accepts
· validated regressions · remote connection failures · **cold model-load latency · warm inference
latency · per-page inference latency · end-to-end remote latency (local rasterise + transfer + infer +
adapt) · peak local RAM · remote RAM · GPU VRAM used · GPU utilisation · bytes transferred per page ·
total Vast GPU runtime attributable to the measurements · paid cost** = runtime × the instance's
hourly rate if the rate is discoverable from the instance (`vast-capabilities`) or from Gustavo; if
not discoverable, runtime is reported and cost is marked "rate not measured" — never estimated from
thin air. Measured on the synthetic fixture set (D8).

## Required tests (the twenty cases, mapped)
| case | property | cell |
|---|---|---|
| 1 | legitimate Class A (R: offline rungs produced no text; U-extract: gate-unusable Tesseract read) in `--scanned-paddle` → the router names `paddle`; the rung runs (fake worker) | R |
| 2 | Class B usable-but-unclaimed Tesseract read → Paddle MUST NOT run (router refuses `no_admitted_trigger`; the fake worker records zero requests) | R |
| 3 | Class C: claimed reconstruction fails a financial oracle → Paddle MUST NOT run (no `decide` call can see it; runner integration) | R |
| 4 | density-surfaced-only document (`below_alnum_density_floor` signal, usable) → Paddle MUST NOT run | R |
| 5 | Paddle 3.7 word boxes (the committed demo-shape fixture + a synthetic ledger) → canonical words → `DocumentGeometry` → pixels → points → pixels round-trip within 1e-6 pt; lines regroup exactly | P + G |
| 6 | native PyMuPDF words → `native_evidence_from_pdf` → the SAME `geometry_from_evidence` → identical to Phase 2.0's `geometry_from_pdf` on the structurer fixtures | G |
| 7 | Paddle confidence is an annotation: it is absent from `to_markdown()`, absent from `admissible_text`, unread by `analyze_document` (AST: no `confidence` read anywhere under `analysis/` except the structurer's own `chain_agreement` field which predates this); a mutant that raises every score to 1.0 changes no outcome | P + R |
| 8 | malformed / ambiguous geometry (inverted box, box outside raster, scale mismatch, mixed spaces, missing dpi) → refuse; no guessed structure | G + P |
| 9 | extractor disagreement: Tesseract read and Paddle read of one page differ on an amount → both evidences retained on the row/record; no fusion; no balance-based winner (the adoption test stays "the SAME validator produced a payload"; a mutant that picks the reconciling one is killed) | R |
| 10 | postprocess remains quarantined: `ADMITTED_POSTPROCESS == ()`; the Paddle page string never passes through `ocr_client.postprocess` / `apply_admitted` (AST + runtime spy) | R |
| 11 | model token `paddle-ocr+ppocrv5` obeys `MODEL_TOKEN_RE`, no money shape, cannot be set from `OCR_MODEL` (reserved), the header reader returns it and Q3 refuses it | P + R |
| 12 | no automatic remote fallback: the non-forced ladder never reaches the Paddle rung; `allow_paddle_ocr` outside `force_ocr` is inert; the webapp has no Paddle call site (AST) | R |
| 13 | `PADDLE_REMOTE_OPT_IN` literal present → remote permitted; absent / truthy-but-wrong / the VISUAL literal only → refused before any request (fake worker sees nothing) | P |
| 14 | Q3 remains native-only on a Paddle-fed document (`q3_provenance_refused`) | R |
| 15 | no statement-specific hardcodes in `evidence/`, the new `ocr/paddle_*` modules, `tools/paddle_vast.py` (the OQ2 scans extended to `evidence/`) | P + G + R |
| 16 | a loopback tunnel URL → provenance `vast.ai` / `remote_paid` (declaration + worker corroboration); a worker echoing `local` against a `vast.ai` declaration → refused | P |
| 17 | any missing `PADDLE_VAST_*` / provider / class variable → `PaddleConfigError` naming it; no default host; nothing contacted | P |
| 18 | connection refused / timeout / 5xx / malformed JSON / oversized response → `paddle_rung = failed` with the error class; the row is terminal `ocr_failed`; NO other extractor or endpoint is tried (spy on `_build_client` and `urllib`) | P + R |
| 19 | all 2,625 previously validated documents protected: the offline partition's page strings byte-identical under EXTRACTION_SCHEMA_VERSION 2 (cohort replay `--expect-identical` at base and at closure; the cold run) | R + train |
| 20 | customer-data scope on a `remote_paid` worker → refused before any bytes leave, unless the second literal is set; the runner always declares `customer` | P + R |
Plus: mutation tables for every gate / charset / allowlist / order rule each cell adds (every mutant
applied as documented, every killer named); the boundary tripwires (D1, D4); the call-site tripwires;
the live proofs behind `@pytest.mark.live` + `skipif` on the config (deselected by default; run once
by Ocean at the train and recorded).

## Corpus measurements at closure
baseline validated · tip validated · validated regressions · R / U / U-extract / U-structure /
density-surfaced / legal population (re-derived on the new run of record) · Paddle-eligible
documents and pages · Paddle attempted (0 — privacy boundary, D8; the refusal counted per row) ·
the synthetic end-to-end proof (documents, pages, words, lines, validator outcome) · the §Telemetry
figures · OCR-fed validated (0) · `paddle_rung` / `escalation_extractor` distributions · tests added ·
targeted / full suite / guards / conformance / gate / corpus slice / cohort replay / cold run / compare
/ CI results · stage-version and cache-selection changes · worktree status · final SHAs.

## Regression gates
Per cell: `newly validated = 0`; `previously validated preserved = all, payload identical` (cohort
replay at base `--expect-identical`, and at closure); mutation tables complete; privacy scan 0 (added
lines against the run-of-record population); message scan 0; **no `PADDLE_VAST_*` value, IP, port or
token in any added line** (a dedicated scan over the branch diff). At the train: the union cohort
replay; `floor.sh` green; the cold run at the composed tree (`coldrun.sh` → `webapp_data_train11_cold`)
vs the Phase 2.0 run of record with `--fail-on-regression` (2,625 → 2,625; 0 movers); remote CI green
(run id recorded); the live Paddle proof recorded once by Ocean over the tunnel.

## Adversarial review plan
Every cell branch gets an independent adversarial review (performed in the current orchestration
environment per `ORCHESTRATION-MODEL-POLICY.md` — Gustavo's 2026-09-02 override supersedes the
"Opus" wording this card originally carried; a fresh agent that reads only the
rulings, this card, the cell card, the diff and the tests). Attack list (from the authorization §28):
Class B → Paddle leakage · Class C → Paddle leakage · validator-driven escalation · density-trigger
leakage · Trigger T accidentally live · implicit Vast fallback · other hosted/cloud fallback ·
localhost tunnel misclassified as local · missing remote opt-in checks · hardcoded Vast connection
information · committed credentials / secrets · production customer data transmitted remotely (D8's
refusal) · Paddle becoming a financial parser · confidence influencing validation · coordinate
conversion errors · bbox grouping errors · page-index errors (0- vs 1-based across `evidence`,
`PageGeometry.page` (1-based, existing) and Paddle's `page_index`) · rotation errors · native / Paddle
provenance confusion · raw evidence mutation · postprocess quarantine bypass · Q3 OCR leakage ·
artifact / cache ambiguity · model / provenance injection · OCR hardcodes · balance-based candidate
selection · unpinned runtime / model behaviour · unbounded remote payload handling · the `enabled`
field smuggling a per-document fact. Findings are reproduced before acceptance; BLOCK/MAJOR close
pre-compose; re-review must be green. Ocean composes; cells never merge or push.

## Rules delta for Phase 2.1 cells (over BATCH9-RULES + PHASE2-RULES)
* Train **`train11`**; worktree `.claude/worktrees/mt21-<card>`, branch `wave21-<card>`; base =
  `train11` at your handoff's commit. Cold caches `webapp_data_train8/9/10_cold` READ-ONLY.
* **Network:** the ONLY network egress any cell may perform is (a) SSH/SCP to the host named by the
  `PADDLE_VAST_*` environment and (b) HTTP to `127.0.0.1:<tunnel port>` — cell P only, and only for
  synthetic / public fixtures. No other host, ever. The default suite makes no network call
  (fake worker on an ephemeral loopback port is in-process).
* **Never** print, log, commit or paste the values of `PADDLE_VAST_*`, the session token, or any
  Vast credential; reports say `<HOST>`. `tools/paddle_vast.py` masks them. `~/.vast_api_key` on the
  remote is never read.
* **No production customer document leaves the machine.** The archive, `tests/corpus_cache/`,
  `Bank Statements/` and any fixture derived from a real statement are `customer` scope. Synthetic
  fixtures are rendered by tests from literal strings.
* Python 3.14 locally / 3.12 in CI and on the worker — write for all three; the worker file must
  run under the remote's 3.12 with only stdlib + paddleocr + Pillow + numpy.
* Report contract as PHASE2-RULES (failure-class evidence, escalation evidence) plus **remote
  evidence**: opt-in state, provider/class declaration, worker corroboration, bytes sent (synthetic
  only), and the zero-secrets scan.

## Explicit exclusions (Phase 2.1)
Unlimited OCR · Phase 2.2 (no structurer enablement; `GENERIC_STRUCTURER_ENABLED` stays off — pinned)
· Phase 2.3 · the 123 U-structure population as a coverage wave · Trigger T live · density live ·
automatic hosted extraction · automatic Vast fallback · other paid/cloud extractors · PP-Structure ·
PP-OCRv6 · character-level fusion · confidence arbitration · validator-selected candidates · candidate
auto-adoption · new bank parsers · parser expansion · distributed OCR workers · Kubernetes · the
webapp wired to Paddle · page-level routing (2.4) · `evidence_refs[]` on parser-derived values ·
Tesseract word boxes (documented as a future option) · a local PaddleOCR install (the `local_free`
class is in the vocabulary and the worker is provider-agnostic; not installed or proved here) ·
production customer uploads to Vast without a separate ruling. Opportunities exposed are DOCUMENTED
in the cell's W3 section, not built.

## Completion criteria (Phase 2.1 is complete only when ALL hold — then STOP)
PaddleOCR 3.7 integration bounded · PP-OCRv5 selection explicit (pinned + verified) · word boxes
enabled and proven (fixture + live) · Paddle runs only on admitted Class-A triggers (cases 1–4) · Vast
execution requires the explicit opt-in (13) · connection configuration from environment only, no
hardcoded host/port (17 + the scan) · no silent local → Vast fallback (12, 18) · remote execution
classified `remote_paid` through a loopback tunnel (16) · raw evidence immutable · canonical
words/bboxes proven (5) · Paddle → `DocumentGeometry` (5) · native → `DocumentGeometry` (6) · one
common geometry abstraction (D1) · coordinate transforms explicit and tested (8) · the SAME validator
the only authority (7, 9) · postprocess quarantine intact (10) · density surface-only (4) · Q3
native-only (14) · **no unauthorized production customer document reached Vast (20; the runbook and
the closure report attest it)** · 2,625 preserved · 0 blocking regressions · every newly validated
Paddle-fed SHA named (expected: none — attempted 0) · false accepts 0 on evaluated truth (the synthetic
fixtures' known truth) · runtime/cost recorded · proof floor green · adversarial reviews complete,
findings reproduced and closed, re-reviews green · cold run / replay green · CI green · docs durable
(`BATCH9_TRANSITION.md` §7, `PHASE2_STATE.md`, `PROJECT_STATUS.md`, `PHASE2_HANDOFF.md`,
`PADDLE_VAST_RUNBOOK.md`, the reviews) · worktree clean → **STOP. Return the Phase 2.1 closure report to
Gustavo. Phase 2.2 does not begin. Unlimited OCR is not enabled. The 13-document remote-data ruling is
requested, not assumed.**
