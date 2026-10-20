# Phase 3 program plan v1 — the Capital Infusion statement model (VLM proposer under a deterministic gate)

Status: DRAFT v1 for owner review, 2026-09-17. Planning only. Nothing in this document has been
executed: no training, no data export, no paid compute, no production change, no native rewrite.
Author: root (CTO role, as instructed). Input: `CI-STATEMENT-VLM-PLAN.md` (v0, preserved unchanged;
changelog in §22). Frozen Phase 2/v6 checkpoint: tag `phase2-v6-freeze-20260917` (commit 1bae39a4…),
checkpoint directory `discovery_reports/train13-logs/checkpoints/phase2-v6-freeze-20260917/`.

Versions, licenses and hardware facts below were checked on 2026-09-17 against public sources; the
sources are listed in §23 and must be re-verified at each gate because this field moves monthly.

---

## 1. Executive recommendation

Build a two-stage, self-hosted extraction proposer and keep every admission decision deterministic.

1. **Stage A, document parser:** PaddleOCR-VL-1.6 (1.0B, Apache-2.0), the current leader on
   OmniDocBench v1.6 (96.3) and on table recognition, served with vLLM. It turns a page image into
   layout boxes and HTML/Markdown tables. A deterministic assembler maps table rows to candidate
   transactions. It is small enough to run on the RTX 5090 with headroom, fast (well under a second
   per page), and fine-tunable on our synthetic tables.
2. **Stage B, general VLM:** Qwen3.5-9B (Apache-2.0, natively multimodal, 262K context) as the
   candidate for fine-tuning: it resolves page roles, section semantics, column meaning on layouts
   Stage A cannot structure, account/period/currency metadata, and continuation across pages, emitting
   schema-constrained JSON (vLLM structured outputs, xgrammar). Qwen3.8-27B (Apache-2.0, August 2026)
   is the "strong second opinion" for experiments only, quantized to fit the 5090; it is not the
   production candidate on a single consumer GPU.
3. **The gate:** running-balance reconciliation, date monotonicity, period totals, duplicate and gap
   detection, currency and account consistency, under the existing ADB, currency, reconciliation and
   false-accept doctrines. The gate is the only admission authority. The deterministic reader stays
   primary wherever it validates exactly; the proposer handles the residue, hard layouts and
   controlled second opinions. Fail closed on missing, contradictory or unreconciled evidence.
4. **Performance:** measured today, 78 percent of end-to-end time is outside the GPU. The first wins
   are pipelining, in-process pdfium rasterization and right-sized image encoding, all in Python with
   native-backed libraries. No Rust or C/C++ rewrite is justified by evidence yet; one Rust candidate
   (a preprocessing service) is defined with a benchmark and an adoption threshold (§6, §7).
5. **Licensing:** every model and library in the recommended stack is Apache-2.0, MIT or BSD, with one
   exception already inside our pipeline: PyMuPDF (AGPL-3.0) must be replaced by pdfium (Apache/BSD)
   or licensed commercially from Artifex before production. This is an owner decision (§21).
6. **Data boundary:** customer pages and derived training records stay on infrastructure we control
   or rent under the existing remote_paid rules; never a third-party model API. Training on customer
   pages is a separate owner approval; the plan reaches a strong first model with synthetic data and
   silver labels derived from our own validated outputs.
7. **First execution phase:** a two-week ceiling measurement with off-the-shelf models, no training,
   explicit go/revise/stop thresholds (§11). Approval to spend on the rented GPU for those two weeks
   is the only budget decision needed to start.

Why this and not a single big VLM: the small document parser is more accurate on tables than
general models hundreds of times its size, it is cheap to fine-tune, and its output is easy to check
deterministically. The general VLM is used where judgement is needed and is bounded by the gate.

---

## 2. Current state and gap assessment

What exists (from the frozen Phase 2/v6 state and the plan census):

* A deterministic reader that validates 2,625 of 3,380 documents with balance-reconciled rows, an
  ADB/currency doctrine, a truth table and adjudication store, a sealed holdout, and a privacy boundary
  with retention attestation. This is the evaluation infrastructure and the primary path.
* A residue of 755 documents: 583 native-text PDFs with usable text but unparsed structure, 131 scans
  Tesseract read but no parser understood, 12 mixed, 16 non-PDF artefacts, 13 without text.
* A pinned PaddleOCR research wave (Phase 2.3) with immutable per-page evidence, custody rows and
  per-page timings on the approved GPU, closed for the v6 family (steps 1–6).
* Canonical geometry (word boxes) from PyMuPDF on native pages.

Gaps this program closes:

* No structure model between geometry and the structurer: the residue is mostly layout.
* No proposer/verifier split: every reader is today either exact or nothing.
* No synthetic data engine, no silver-label export, no fine-tuning stack, no serving stack for VLMs.
* A pipeline that spends most of its wall time outside the GPU (§6).
* An AGPL dependency (PyMuPDF) in a commercial pipeline.

Non-gaps (do not rebuild): the holdout cage, adjudication store, doctrines, privacy boundary,
evidence hashing and receipts, the deterministic reader.

---

## 3. Architecture and data flow

```
PDF/image  ─► Ingest (hash, page count, text-layer probe, classification of page roles)
           ─► Native path: PyMuPDF/pdfium words ─► deterministic reader ─► GATE ─► ledger   (primary)
           ─► Residue path (no text layer, reader refused, or second opinion requested):
                 render pages (pdfium, model-fit resolution, JPEG/WebP)
                 ─► Stage A: PaddleOCR-VL-1.6 (vLLM) ─► layout boxes + tables ─► row assembler
                 ─► Stage B: Qwen3.5-9B (vLLM, JSON schema) for page roles, sections, column
                     semantics, metadata, continuation; consumes Stage A output + the page image
                 ─► Proposal set (rows with per-field provenance: page, box, source stage, confidence)
                 ─► GATE (deterministic): reconcile balances/dates/totals/duplicates/currency/account
                 ─► admitted rows to the ledger, or quarantine with reasons and preserved evidence
Evidence store: every model input (image hash), prompt hash, model+weights hash, raw output, parsed
proposal, gate verdict and reasons, timings. Nothing admitted without a reconciled check.
```

Component boundaries: ingest/render/preprocess (Python + native-backed libs), model serving (vLLM,
GPU), proposal assembly and the gate (pure Python, deterministic, versioned), evidence and lineage
(SQLite/DuckDB + content-addressed files, as today), evaluation harness (Python), synthetic data
engine (Python renderer), fine-tuning (Python, PEFT/LLaMA-Factory), API service (FastAPI).

Metrics (ADB etc.) are computed downstream by the existing deterministic code only.

---

## 4. Rules and non-negotiable invariants

1. The model proposes; deterministic arithmetic decides. The VLM is never the admission authority.
2. The deterministic reader remains primary wherever it validates exactly.
3. The VLM handles residue, difficult layouts and controlled second opinions only.
4. Dates, amounts, balances, continuity, statement totals and other provable facts pass deterministic
   reconciliation before admission. A statement whose rows do not reconcile is quarantined with
   reasons; never partially admitted without an explicit, recorded rule.
5. The model emits source-level fields with per-field provenance (page, box, source stage); never
   derived underwriting metrics such as ADB.
6. Metric computation stays deterministic under the existing ADB, currency, reconciliation and
   false-accept doctrines.
7. Fail closed when evidence is missing, contradictory or unreconciled.
8. The sealed holdout is never used for training, prompt design, model selection or threshold
   tuning; it is read only by the evaluation harness under the existing custody rules.
9. Customer documents and derived training records stay inside infrastructure we control or rent
   under the approved rules; no third-party model API; no new external provider without a ruling.
10. Every model input and output is content-addressed and receipted; weights, prompts, schemas and
    gate versions are pinned by hash in every receipt.
11. Determinism: identical inputs, weights, prompts, sampling settings (temperature 0, fixed seeds)
    and software versions must produce identical proposals; any nondeterminism is measured and
    recorded, never assumed away.
12. No silent second reading: cache keys depend only on pinned configuration and tree constants
    (the Phase 2.3 partition-key lesson is fixed at the root in this program).

---

## 5. Model and tool evaluation matrix

Candidates evaluated (open weights, self-hostable), with license and fit on one RTX 5090 (32 GB):

| Model | Params | License | Role fit | 5090 fit | Notes |
|---|---|---|---|---|---|
| PaddleOCR-VL-1.6 | 1.0B | Apache-2.0 | Stage A document parser (layout + tables → JSON/Markdown) | Easy (bf16 ≈ 2 GB) | OmniDocBench v1.6 96.3, SOTA table recognition; vLLM serving; default 1,280×28×28 image tokens |
| GLM-OCR | 0.9B | MIT (+PP-DocLayoutV3 Apache) | Stage A alternative; structured JSON extraction | Easy | Competitive on OmniDocBench (score to be re-read from the card at G0); compare head-to-head in the ceiling |
| DeepSeek-OCR-2 | ~3B (verify at G0) | Apache-2.0 | Stage A alternative (grounded Markdown) | Easy | Throughput-oriented; table scores to be compared in the ceiling |
| dots.ocr-3B, olmOCR-2-7B | 3B / 7B | MIT / Apache-2.0 | Alternatives for messy scans | Easy | Keep as fallbacks; not primary |
| MinerU2.5 | ~1.2B | Apache-2.0 with additional terms | — | — | Excluded: extra commercial terms and attribution obligations |
| Qwen3.5-9B | 9B | Apache-2.0 | Stage B general VLM, fine-tune candidate | bf16 ≈ 18 GB + KV; LoRA training fits with QLoRA/gradient checkpointing | Native VL, 262K context; vLLM ≥ 0.28 |
| Qwen3.5-4B / 2B | 4B / 2B | Apache-2.0 | Stage B low-cost variant | Easy | Evaluate if 9B latency is the bottleneck |
| Qwen3-VL-8B/32B-Instruct | 8B / 32B | Apache-2.0 | Prior generation | 8B easy; 32B FP8 only | Superseded by Qwen3.5 for new work; keep for comparison |
| Qwen3.6-35B-A3B | 35B MoE (3B active) | Apache-2.0 | Fast strong second opinion | 4-bit only (~20 GB) | Multimodal; decode fast; weights large |
| Qwen3.8-27B | 27B dense | Apache-2.0 | Strongest open second opinion | AWQ/GPTQ 4-bit only (~15 GB); bf16 does not fit | August 2026; experiments only on the 5090 |
| Qwen3.8-Max-class | 2.4T MoE | custom licence | — | — | Excluded: licence and size |
| Gemma 4 (12B, 26B MoE, 31B) | 12–31B | Apache-2.0 (new for Gemma 4) | Alternative Stage B | 12B bf16 ≈ 24 GB (tight) | Multimodal; evaluate 12B if Qwen3.5-9B disappoints |
| Nanonets-OCR2 (owner's July note) | 1.5B/3B | check card | Markdown OCR | Easy | Superseded by the parsers above on tables; kept as a comparison point |

Serving and training stack (pinned at the ceiling gate; re-pin at each gate):

| Component | Choice | Version to pin | License | Why |
|---|---|---|---|---|
| Serving | vLLM | 0.28.0 (2026-08-26) or the first release supporting every chosen model | Apache-2.0 | Structured outputs (xgrammar/guidance), prefix caching, OpenAI-compatible API we already use |
| Structured decoding | xgrammar via vLLM `--structured-outputs-config` | vLLM-bundled | Apache-2.0 | JSON-schema constrained decoding; low per-token overhead |
| Framework | PyTorch cu128 | 2.9.x | BSD-3 | Blackwell (sm_120) needs CUDA 12.8+ wheels; FlashAttention 2 backend on Blackwell |
| Fine-tuning | PEFT + TRL, orchestrated by LLaMA-Factory (or ms-swift) | latest stable at the gate | Apache-2.0 | LoRA/QLoRA for VLMs incl. Qwen3.5 and PaddleOCR-VL; Unsloth optional for speed (verify licence terms of the exact release) |
| Rendering | pypdfium2 (pdfium) | latest stable | Apache-2.0 / BSD-3 | In-process, fast, liberal licence; replaces PyMuPDF (AGPL) and poppler subprocesses |
| Imaging | Pillow (+ libjpeg-turbo), OpenCV | stable | MIT-CMU / BSD / Apache-2.0 | Encoding, deskew, denoise |
| Data | Polars, PyArrow, DuckDB | stable | MIT / Apache-2.0 / MIT | Large-scale validation and lineage queries |
| API | FastAPI + uvicorn | stable | MIT / BSD | Thin, typed, async |
| Native option | Rust (PyO3, maturin, rayon, image, pdfium-render) | stable | MIT / Apache-2.0 | Only for the preprocessing service if the benchmark in §6 says so |

Final model recommendations: Stage A = PaddleOCR-VL-1.6; Stage B = Qwen3.5-9B; experiment-only
second opinion = Qwen3.8-27B (4-bit). Exact checkpoints, revisions and weight hashes are pinned at the
start of the ceiling experiment and recorded in its receipts; the plan does not pin a revision hash
in prose because the hubs move.

License-verification process (applies to models, libraries and native dependencies): read the
model card and LICENSE file of the exact revision; record licence name, SPDX id, revision hash,
date and URL in `docs/moneythumb-replacement/phase3/LICENSES.md`; reject anything that is not
Apache-2.0, MIT, BSD or equivalent without an owner ruling; re-check at every gate; the CI build
fails on an unrecorded dependency (pip-licenses / cargo-deny).

---

## 6. Programming-language and performance-engineering study

### 6.1 Measured baseline (today's stage 6, 78 documents, 611 pages, PaddleOCR v6 on the rented RTX 5090)

| Measure | Value |
|---|---|
| GPU inference per page (worker-reported) | mean 678 ms, p50 676 ms, p95 962 ms, max 1,034 ms |
| Wall time per page (chunk wall / pages) | 3.06 s |
| Share of wall time inside GPU inference | 22 percent |
| Non-inference time per page (raster, encode, transfer, orchestration, evidence writes) | 2.38 s |
| Upload per page (300-dpi PNG) | mean 536 KB |
| Worker VRAM | ≤ 7.7 GB |
| Concurrency | 1 page in flight (OCR_MAX_WORKERS=1), one document at a time, poppler subprocess rasterization |

Conclusion: the pipeline is not GPU-bound. Three quarters of the time is CPU rasterization,
PNG encoding, serial round trips over the SSH tunnel, per-chunk subprocess and SQLite/evidence
writes. The GPU is idle most of the time.

### 6.2 Expected bottlenecks in the Phase 3 pipeline (before optimization)

* Rasterization: poppler `pdftoppm` per page/document through pdf2image (process spawn, PNG to disk,
  re-read). Expect 0.5 to 1.0 s per page at 300 dpi.
* Encoding: PNG at 300 dpi is 5× larger than needed by the models (Stage A uses ≈1,280 image tokens;
  a 1,500-px long edge JPEG q90 is ≈150 KB).
* Serial orchestration: render → upload → infer → parse per page with no overlap.
* Evidence: hashing rasters and writing JSON is small (< 30 ms per page) but on the critical path.
* Two model stages per page double the round trips unless batched.
* The gate, row assembly, parsing and validation: microseconds to milliseconds per statement in
  Python; not a bottleneck at any foreseeable volume.

### 6.3 Component-by-component recommendation

| Component | Recommendation | Rationale | Expected end-to-end effect |
|---|---|---|---|
| Orchestration, pipeline, batching | Python (asyncio), unchanged language | GIL is irrelevant: the work is I/O and GPU; prefetch 2–3 pages while the GPU is busy; batch pages per statement to vLLM | Wall 3.06 → ≈ 1.0 s/page (≈3×) with zero native code |
| PDF rasterization | Python + pypdfium2 (native pdfium in-process) | Removes process spawn and disk round trip; liberal licence; pdfium is single-threaded per document, so parallelize across documents with processes | Raster 0.5–1.0 → ≈ 0.1–0.2 s/page |
| Image encoding and resize | Pillow with libjpeg-turbo / OpenCV, model-fit resolution | Right-size images to the model's token budget; JPEG/WebP | Upload 536 KB → ≈ 150 KB/page; encode time down ≈ 3× |
| Deskew / denoise / rotation / crop | OpenCV (C++ under a Python API) | Mature, Apache-2.0, SIMD-optimized | Milliseconds per page; no new native code |
| OCR post-processing, row assembly, normalization | Python (pure) | Deterministic, readable, auditable; volume is tiny | No change needed |
| Date/amount/currency parsing | Python (pure, versioned regex/grammar) | Auditability beats speed; cost is negligible | None |
| Deterministic reconciliation (the gate) | Python (pure, `decimal`) | Must be obviously correct and reviewable; microseconds per statement | None |
| Large-scale schema validation and lineage queries | Python + Polars/DuckDB (Rust/C++ under the hood) | Vectorized, out-of-core, no GIL for the heavy part | Corpus-scale validation in seconds |
| Multi-page stitching, duplicate and gap detection | Python (pure) | Small data, complex rules | None |
| Hashing, evidence generation, artefact verification | Python `hashlib` (C, SIMD-enabled) with streaming; parallel per document | Already native-backed | Marginal |
| Serialization | Python `orjson` (Rust-backed) for JSON; Arrow for tables | Fast, safe, no custom code | Marginal |
| Synthetic rendering | Python (HTML/CSS templates rendered by headless Chromium or a PDF library), parallel processes | Fidelity and variety matter more than speed; offline batch | N/A |
| Batch scheduling / parallel documents | Python multiprocessing + asyncio; vLLM continuous batching | Adequate to tens of pages per second on one GPU | N/A |
| CPU→GPU transfer, zero-copy | vLLM's own paths; images sent as compressed bytes over HTTP | No custom kernels or transfers needed | N/A |
| Model inference, attention, quantization kernels | vLLM (CUDA/Triton kernels), FP8/AWQ where supported on Blackwell | Already optimized; Rust/C cannot accelerate this | Model-bound after the CPU fixes: ≈ 0.3–0.7 s/page for Stage A + B combined at batch |
| Model serving integration | vLLM OpenAI-compatible server; Python client | Standard | N/A |
| API service | Python FastAPI | Throughput needs are modest (documents/hour), not requests/second | N/A |
| High-throughput preprocessing service (candidate) | Rust (pdfium-render, image, rayon) exposed via PyO3/maturin | Only if, after the Python fixes, CPU preprocessing is still ≥ 30 percent of wall time at target throughput | Estimated additional 1.5–2× on the CPU path; adopt only on benchmark evidence (§6.6) |

Should remain in Python: everything that decides admission or must be read by an auditor; everything
whose cost is below 5 percent of wall time; everything that changes weekly.

### 6.4 Integration boundaries

* Python ↔ GPU: HTTP to vLLM (images as bytes, JSON out). No custom CUDA. Structured outputs
  enforced server-side by grammar.
* Python ↔ native libraries: pypdfium2, Pillow, OpenCV, Polars, orjson, hashlib (all in-process,
  vendor-maintained ABI).
* Python ↔ Rust (if adopted): one crate, one `maturin` wheel, one function surface
  (`render_and_encode(pdf_bytes, page_indices, target_long_edge) -> list[(jpeg_bytes, sha256, w, h)]`),
  GIL released inside, no shared mutable state, no unsafe beyond the pdfium FFI wrapper.
* No new C/C++ code. Existing C/C++ enters only through mature libraries (pdfium, libjpeg-turbo,
  OpenCV, CUDA via vLLM).

### 6.5 Memory safety, security, build and operations

* Rust: memory-safe by default; the FFI edge to pdfium is the only unsafe surface, and pdfium itself
  is the same C++ rendering core Chromium ships, fuzzed continuously. Builds need a Rust toolchain in
  CI and wheels per platform (maturin); debugging crosses a language boundary; observability needs
  explicit spans from Rust into the Python tracer.
* C/C++ (new code): rejected. Memory-safety risk on untrusted PDFs is the exact threat model
  (malformed customer uploads); we would take that risk only through libraries that are fuzzed by
  large upstream projects.
* Optimized Python: no new attack surface; all parsing of untrusted bytes happens inside pdfium /
  Pillow / OpenCV, which must be pinned and patched promptly.
* Cross-platform: development on Windows (today), production on Linux containers; pdfium, Pillow,
  OpenCV, Polars ship wheels for both; a Rust component would need both wheels built and tested.

### 6.6 Benchmark design and adoption threshold

Harness: one script, identical inputs (a fixed 200-document set drawn from validated documents and the
residue, ≈ 1,500 pages, fixed seeds), identical correctness requirement (byte-identical proposals and
gate verdicts across implementations; raster hashes compared per page), three warm runs after one
cold run, on the same GPU instance.

Measured per implementation: pages/s, documents/s, transactions/s, p50/p95/p99 statement latency,
CPU utilization, GPU utilization (nvidia-smi sampling), peak and sustained RAM and VRAM, bytes
transferred, cold-start and warm-start times, concurrency scaling (1, 2, 4, 8 documents in flight),
cost per page and per statement (instance price × wall time), correctness (deterministic
equivalence) and a diff report of any divergence.

Adoption threshold for any native component (Rust or otherwise): at least 25 percent improvement in
end-to-end statement latency or cost per page at identical correctness, no regression in p95
latency, RAM or VRAM, no change to any gate verdict on the full validated corpus, and an estimated
maintenance cost below one engineer-week per quarter. A microbenchmark alone never justifies a
rewrite. Rollback conditions: any reconciliation diff, any crash on the fuzz corpus of malformed
PDFs, a platform build failure that cannot be fixed within a day, or maintenance exceeding the
budget for two consecutive quarters.

### 6.7 Migration complexity and cost

* Python pipelining and pypdfium2: 3–5 engineer-days, low risk, reversible.
* Image policy (resolution, JPEG/WebP): 1–2 days; validated by raster-hash and proposal equivalence.
* Rust preprocessing service: 2–3 engineer-weeks including wheels, fuzzing and observability; only if
  the benchmark demands it.
* Removing PyMuPDF (licence): 3–5 days to swap to pypdfium2 for rendering and word boxes, plus a
  geometry-equivalence check on the validated corpus (word boxes may differ in rounding; the reader's
  validation must remain exact).

### 6.8 Ranked optimizations by expected end-to-end impact

1. Pipelining and per-statement batching (Python): ≈ 3× throughput.
2. In-process pdfium rasterization: removes most of the remaining CPU time.
3. Model-fit image size and JPEG/WebP encoding: ≈ 3–4× less transfer and encode time.
4. Two-stage batching (Stage A and B requests batched per statement): halves round trips.
5. FP8 or AWQ weights for Stage B on Blackwell: ≈ 1.5–2× decode speed if supported by the pinned vLLM.
6. Rust preprocessing service: last, conditional on §6.6.

---

## 7. Component-by-component language decision matrix (decision record)

| Component | Selected | Alternatives evaluated | Benchmark evidence required | Expected benefit | Migration and maintenance | Security impact | Reject / roll back when |
|---|---|---|---|---|---|---|---|
| Orchestration and API | Python 3.12 (asyncio, FastAPI) | Rust (Tokio/axum), Go | End-to-end latency and throughput with prefetch depth 1/2/4 | 3× throughput | Days; low | None | Never for language reasons; only if throughput target > 20 pages/s per GPU proves unreachable |
| Rasterization | Python + pypdfium2 | PyMuPDF (AGPL), poppler CLI, Rust pdfium-render | Raster ms/page, raster hash equivalence, RAM | 5–10× on this step | Days | Liberal licence; fuzzed core | If pdfium fidelity differs on the validated corpus (measured, not assumed) |
| Encoding and preprocessing | Pillow/libjpeg-turbo/OpenCV | Rust image crate | Encode ms/page, bytes/page, proposal equivalence at each resolution | 3–4× on transfer | Days | None new | If model accuracy drops at reduced resolution (ceiling experiment measures this) |
| Gate, parsing, assembly, stitching | Python (pure) | Rust via PyO3 | None needed (cost < 1 percent) | None | None | Readability protects correctness | N/A |
| Corpus-scale validation and lineage | Python + Polars/DuckDB | pandas, SQL only | Validation wall time at 3,380 documents | 10× vs pandas | Days | None | N/A |
| Serving and kernels | vLLM (CUDA/Triton) | SGLang, TensorRT-LLM | Tokens/s, p95, VRAM | Already optimized | None | Pinned versions | If Blackwell kernel bugs block; then SGLang |
| Preprocessing service | Candidate: Rust (PyO3/maturin/rayon/pdfium-render) | Python multiprocessing | §6.6 harness with the 25 percent threshold | 1.5–2× on CPU path if CPU-bound after Python fixes | 2–3 weeks; wheels, CI, fuzzing | Small unsafe FFI surface | Threshold not met, or maintenance > 1 engineer-week/quarter |
| Synthetic renderer | Python (HTML/CSS → Chromium PDF, plus reportlab) | Rust typst, LaTeX | Pages/min offline (irrelevant to production) | N/A | Days | Offline only | N/A |
| Evidence hashing and serialization | Python hashlib, orjson, Arrow | Rust | Hash ms/page | Marginal | None | None | N/A |

---

## 8. Licensing and commercial-use review

Models (recommended): PaddleOCR-VL-1.6 Apache-2.0; Qwen3.5-9B Apache-2.0; Qwen3.8-27B Apache-2.0
(experiments); GLM-OCR MIT (its layout companion PP-DocLayoutV3 Apache-2.0); DeepSeek-OCR-2
Apache-2.0; Gemma 4 Apache-2.0 (alternative). Excluded: MinerU2.5 (Apache-2.0 with additional
commercial terms and attribution), Qwen3.8-Max-class (custom licence), Gemma 3 and earlier (Gemma
Terms of Use), Llama-family models (Llama licence obligations), any API-only model.

Derivative weights: Apache-2.0 and MIT permit fine-tuning and private deployment of derivative weights
without publishing them; attribution notices must be kept in the repository's LICENSES file.

Libraries: vLLM Apache-2.0; PyTorch BSD-3; xgrammar Apache-2.0; PEFT/TRL/transformers Apache-2.0;
LLaMA-Factory Apache-2.0; ms-swift Apache-2.0; Unsloth core Apache-2.0 (verify the exact release's
terms before use); pypdfium2 and pdfium Apache-2.0 or BSD-3; Pillow MIT-CMU (HPND); OpenCV Apache-2.0;
Polars MIT; PyArrow Apache-2.0; DuckDB MIT; FastAPI MIT; orjson Apache-2.0/MIT; Tesseract Apache-2.0.
Rust crates: pyo3 and maturin Apache-2.0/MIT; rayon MIT/Apache-2.0; image MIT/Apache-2.0;
pdfium-render Apache-2.0/MIT (dual).

Flagged: **PyMuPDF (fitz) is AGPL-3.0**; our backend use in a commercial product needs either an
Artifex commercial licence or replacement. **Poppler is GPL-2/3**; invoking `pdftoppm` as a separate
process is the accepted boundary, but pdfium removes the question. Both are resolved by the pdfium
migration recommended in §6; the owner decides between buying a licence and migrating (§21).

Process: LICENSES.md with SPDX ids, revision hashes and dates; `pip-licenses` and `cargo-deny` in CI;
re-verification at every gate; no dependency added without an entry.

---

## 9. Training-data boundary, retention, lineage and attestation

Boundary: customer documents, page images, model inputs/outputs, silver labels and any derived
training record exist only (a) on the local machine, (b) on the rented GPU instance under the
existing remote_paid rules (encrypted transport, private connection file, retention attestation per
job), or (c) on the designated separate machine. No third-party model API; no new external provider
without a ruling. Training on customer pages is a distinct approval (§21).

Data classes and handling:

| Class | Examples | Where | Retention | Attestation |
|---|---|---|---|---|
| Customer source | PDFs, page images | Local + rented GPU during a job | Local per existing policy; rented instance wiped at job end | Retention attestation (as Phase 2.3) |
| Derived research evidence | Model outputs, proposals, gate verdicts | Local research partitions | Kept with receipts | Hash receipts |
| Silver labels | Reconciled rows aligned to pages | Local, content-addressed | Kept while the source is kept; deleted with the source | Manifest per export |
| Synthetic data | Rendered statements + labels | Anywhere we control | Indefinite | Manifest per generation |
| Weights and adapters | Base checkpoints, LoRA adapters | Local + rented instance during jobs | Base per licence; adapters kept with lineage | Hash in every receipt |
| Sealed holdout | Holdout documents and adjudications | Existing cage only | Existing rules | Existing custody |

Lineage: every training run records dataset manifest hashes, generator version and seeds, base
checkpoint revision hash, adapter hash, hyperparameters, software versions, GPU identity, and the
evaluation receipts; every inference receipt records weights hash, prompt hash, schema hash, gate
version, image hashes. Deletion: a customer deletion request removes source, derived evidence and
silver labels by content hash and records the removal; adapters trained on removed data are
retired at the next retraining (recorded). Access control: private directories, no customer bytes in
Git, logs contain hashes and counts only. Encryption: SSH/TLS in transit; disk encryption at rest on
the local machine and the rented instance where the provider supports it (verify per instance).

---

## 10. Synthetic-data and silver-label strategy

Silver labels: eligible only when the deterministic reader validated the document exactly (balance
reconciled, no overrides), the page-to-row alignment is unambiguous (rows map to one page with word
boxes or Stage A boxes), and the document is not in the holdout. Export as page-aligned JSON matching
the proposal schema, with the reader's version and the reconciliation receipt hash. Ineligible: any
document with adjudication overrides, any holdout member, any document under a deletion request.

Synthetic engine: a ledger simulator (accounts, opening balances, transaction mixes per business
type, fees, transfers, holds, returned items, multi-currency) produces ground-truth ledgers; renderers
produce PDFs and images across the 91 layout families and new variants (column orders, running
balance present/absent, multi-account, continuation lines, summaries, cheques images, foreign
formats, date formats), then degrade a fraction into scans (rotation, skew, noise, JPEG, blur,
shadows, low DPI). Labels are exact by construction. Volume: tens of thousands of pages; refreshed
per retraining. The generator is versioned and its manifest hashed; no customer content is used as
a template beyond layout statistics.

Partition rules (fixed before the ceiling experiment): TRAIN (synthetic + eligible silver + adjudicated
hard cases), VALIDATION (a held-out slice of real validated documents by layout family, never trained
on), TEST (the existing truth table and adjudication slice), SEALED HOLDOUT (untouched, evaluation
only). Contamination controls: content hashes of every holdout page are blacklisted from every
training manifest; the training pipeline refuses a manifest containing one; family-level leakage
is measured by reporting per-family metrics separately for families present and absent in TRAIN.

---

## 11. Two-week ceiling experiment (execution requires the budget approval in §21; nothing else)

Purpose: measure how far off-the-shelf models reach under the gate before any training. Hardware:
the approved rented RTX 5090 (experimentation class). Models: Stage A PaddleOCR-VL-1.6 and GLM-OCR;
Stage B Qwen3.5-9B (bf16) and Qwen3.8-27B (4-bit) as the second opinion. No fine-tuning.

Partitions: the 755 residue (VLM target), the CTRL control sample (≈150 validated documents, the
reader's known-good behaviour), a 200-document validated calibration set for the hybrid comparison.
The sealed holdout is NOT touched in this experiment. Prompt and schema design uses synthetic pages
and a 20-document development slice from the validated set only.

Arms:
1. Deterministic reader baseline (as today): validated / refused per document.
2. Stage A only + deterministic row assembler + gate.
3. Stage B only (schema JSON from the page image) + gate.
4. Hybrid: Stage A boxes/tables as input to Stage B + gate.
5. Hybrid with the second-opinion model on disagreements.

Procedure per document: ingest, page roles, render at the model-fit resolution (and at 300 dpi for
the equivalence check), run the arm, assemble proposals with provenance, run the gate, write
receipts; every timing measured separately: CPU preprocessing (raster, encode), transfer, queue
wait, inference (prefill and decode), postprocessing (parse, assemble), gate. Sampling temperature
0, fixed seeds, pinned versions; a repeat run on 50 documents measures nondeterminism.

Measurements: row-level exact match against reader rows on the calibration set (date, description
normalized, amount, direction, balance, section, currency, account, period); page-level and
statement-level pass rates; per-layout-family results; gate outcomes (admitted, quarantined with
reason codes); false accepts (admitted rows that contradict validated rows) and false rejects;
refusals; coverage on the residue (statements fully reconciled); repair rate (residue statements the
hybrid reconciles that the reader refused); unresolved residue by failure class; multi-page
continuity (carry-over balance checks), duplicate and missing-row behaviour; latency p50/p95/p99,
GPU utilization, RAM/VRAM, throughput, cost per page and per statement; a failure taxonomy with
preserved evidence (page hash, output hash, gate reasons) for every non-admitted statement.

Thresholds (per arm, on the residue, at zero false accepts on the calibration set):
* GO to the data engine and fine-tuning: hybrid reconciles ≥ 40 percent of the residue statements,
  Stage A table-row exact match ≥ 90 percent on validated pages, no false accepts, cost ≤ USD 0.05
  per statement at the measured throughput.
* REVISE (change models, prompts, resolution or the gate; re-run for one more week): 20–40 percent
  reconciled, or false accepts traced to a fixable gate gap.
* STOP (do not proceed to training; report and return to the layout-model path): < 20 percent
  reconciled, or false accepts that the gate cannot close, or nondeterminism above 1 percent of rows.

Deliverables: the receipts, the per-arm report, the failure taxonomy, the profiling table for §6,
the pinned versions and weight hashes, the LICENSES entries, and a go/revise/stop recommendation
for independent review before any training approval.

Guardrails: no holdout access; no third-party API; instance wiped and attested after the run; no
native rewrite; profiling only.

---

## 12. Fine-tuning plan (activates only after the ceiling review and a separate approval)

Targets: Stage A (PaddleOCR-VL-1.6, full or LoRA fine-tune on synthetic tables and silver-labelled
real tables) for our table dialects; Stage B (Qwen3.5-9B, LoRA r=16–64 on attention and MLP,
bf16 base with gradient checkpointing or QLoRA if VRAM binds) for page roles, sections, column
semantics, metadata and continuation, with strict JSON targets.

Data: TRAIN partition per §10, curriculum synthetic → silver → hard cases; validation on the
family-stratified VALIDATION slice; early stopping on gate-pass rate, not on token loss.

Compute: the rented 5090 for LoRA (hours per run); a larger rented GPU only if the 27B model is ever
promoted, which this plan does not recommend. Every run records the lineage of §9. Training on
customer-derived records requires the owner approval in §21; until then, synthetic-only training is
the default first run.

Acceptance to move to shadow: improvement over the ceiling arm on the VALIDATION slice with zero
false accepts, no regression on the CTRL sample, deterministic equivalence of the gate, and an
independent review of the training manifest.

---

## 13. Evaluation matrix

| Dimension | Sets | Metrics | Gate |
|---|---|---|---|
| Reader agreement | CTRL, calibration set | row exact match per field; statement reconciliation | zero false accepts |
| Residue coverage | 755 residue by class (native-unparsed, scans, mixed, non-PDF, no-text) | reconciled statements, quarantined with reasons, unresolved | class-specific targets |
| Layout families | 91 families, present vs absent in TRAIN | per-family pass rates | no family below floor without a note |
| Field exactness | dates, descriptions, amounts, directions, balances, account metadata, periods, sections, currencies | exact / normalized match | amounts and balances exact |
| Continuity | multi-page statements | carry-over reconciliation, duplicate and gap detection | zero admitted gaps |
| Adversarial | synthetic tampered statements (edited amounts, removed rows, altered balances) | detection rate | ≥ 99 percent detected by the gate |
| Sealed holdout | holdout cage | false accepts, coverage | zero false accepts (existing doctrine) |
| Performance | benchmark set | §6.6 measures | thresholds in §6.6 |
| Determinism | repeat runs | row-level variance | ≤ 1 percent, recorded |

---

## 14. Threat model

* Data leakage: customer bytes never leave controlled infrastructure; logs carry hashes and counts;
  prompts never include other customers' data; model outputs stored only in private partitions.
* Prompt injection via document content (text in a statement instructing the model): the model's
  output is constrained by schema and ignored unless it reconciles; no tool use; no free-text
  commands executed.
* Fraud: altered statements (edited amounts, removed rows, fabricated balances). The gate detects
  internal inconsistency; external verification (bank data feeds) is outside this program; document
  forensics remain a separate track.
* Hallucination: constrained decoding plus reconciliation; no partial admission.
* Malformed inputs: parsing only inside fuzzed libraries (pdfium, Pillow, OpenCV), pinned and
  patched; size and page limits; timeouts.
* Memory safety: no new C/C++; Rust only behind a small FFI surface if adopted.
* Model supply chain: weights downloaded once, hashed, stored locally; revision pinned; no automatic
  updates; licence recorded.
* Insider/agent risk: independent review of any instrument that admits data; receipts immutable.

---

## 15. Deployment stages

1. Offline: experiments and training on the rented GPU; no customer-facing effect.
2. Shadow: the proposer runs alongside the reader on live intake; outputs recorded, never admitted;
   disagreement and gate statistics reviewed weekly.
3. Controlled canary: admission of gate-passed proposals for the residue only, capped share per week,
   with human review of a sample and instant rollback to reader-only.
4. Production eligibility: after a full cycle at zero false accepts on the holdout and canary
   review, the proposer becomes a standard path for the residue; the reader remains primary.

Production serving: a rented Linux GPU instance (L40S/RTX 6000-class or the 5090 if throughput
suffices) running vLLM with the pinned weights; the Windows workstation is not a production host.

---

## 16. Monitoring, drift, rollback and retraining

Monitored per day: gate pass and quarantine rates by reason, refusals, per-family pass rates,
latency and cost, model output length and schema-violation counts, nondeterminism on a daily repeat
sample. Drift alarms: a family's pass rate drops by more than 10 points for two days, or new layout
signatures exceed a threshold. Rollback: a single switch to reader-only; adapters versioned so any
prior adapter can be restored within minutes. Retraining: monthly, or on drift, with synthetic
refresh from new families; every retrain passes the full evaluation matrix and independent review.
Incidents: any admitted row later found wrong triggers quarantine of the statement, a root-cause
receipt, and a gate amendment before any further admission.

---

## 17. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ceiling too low (< 20 percent reconciled) | Medium | Program stops | Two-stage design; revise arm; layout-model path remains |
| False accepts through gate gaps | Low | High | Adversarial synthetic set; zero-false-accept bar; canary caps |
| Blackwell software instability (kernels, FA3) | Medium | Delays | Pinned PyTorch 2.9 cu128, FA2 backend, SGLang fallback |
| Licence drift or wrong assumption | Low | Legal | LICENSES.md, CI checks, re-verification per gate |
| PyMuPDF AGPL exposure | Certain today | Legal | Owner decision: licence or migrate (§21) |
| Data boundary breach | Low | Severe | No API, attestation per job, hashes-only logs |
| Overfitting to our families | Medium | Coverage stalls on new banks | Synthetic diversity, family-stratified validation |
| Nondeterminism in serving | Medium | Audit weakness | Temperature 0, seeds, measured variance, receipts |
| Cost overrun | Low | Budget | Small models, rented hours, per-phase caps |
| Single-engineer bottleneck | High | Schedule | Independent review agents; strict scope; time boxes |

---

## 18. Milestones, dependencies, staffing, time and budget

| Milestone | Duration | Depends on | Staffing | Budget (GPU rental, USD) |
|---|---|---|---|---|
| M0 Gates and boundary rulings, LICENSES.md, pins | 1 week | owner decisions §21 | 1 engineer | 0 |
| M1 Ceiling experiment (§11) | 2 weeks | M0, budget approval | 1 engineer + 1 reviewer | 100–250 |
| M2 Data engine (§10) | 3 weeks (parallel from M1 week 2) | M0 | 1 engineer | 0 |
| M3 Python performance fixes and pdfium migration (§6) | 1 week (parallel) | M1 profiling | 1 engineer | 0 |
| M4 Fine-tuning (§12) | 2 weeks | M1 GO, M2, separate approval | 1 engineer + 1 reviewer | 200–600 |
| M5 Evaluation and admission rules (§13) | 1–2 weeks | M4 | 1 engineer + 1 reviewer | 50 |
| M6 Shadow and canary (§15) | 3–4 weeks | M5 | 1 engineer, owner review | 150–400/month serving |
| Optional Rust preprocessing service (§6.6) | 2–3 weeks | benchmark threshold | 1 engineer | 0 |

Total to a gated production candidate: roughly 10–12 weeks and USD 500–1,500 of GPU rental,
excluding production serving and any Artifex licence. Staffing assumption: one senior engineer (root,
with independent review agents) and the owner for rulings and weekly review.

---

## 19. Gate deliverables and evidence

| Gate | Evidence required |
|---|---|
| G0 start | Signed owner decisions (§21); LICENSES.md; pinned versions; partition manifests with holdout blacklist |
| G1 ceiling done | Receipts per arm; per-arm report; failure taxonomy; profiling table; nondeterminism measurement; independent review; go/revise/stop |
| G2 data engine | Generator manifest and samples; silver export manifest with eligibility receipts; contamination check |
| G3 training | Lineage record; validation results; zero false accepts; independent review of manifests |
| G4 shadow | Weekly disagreement and gate statistics; rollback drill receipt |
| G5 canary | Capped admissions; reviewed samples; holdout evaluation at zero false accepts |
| G6 production eligibility | Full evaluation matrix; monitoring live; retraining and rollback procedures rehearsed |
| Any native adoption | §6.6 benchmark report meeting the threshold; equivalence diff empty; fuzz corpus clean |

---

## 20. Decision log

| Decision | Selected | Rejected | Why |
|---|---|---|---|
| Architecture | Two-stage proposer (document parser + general VLM) under a deterministic gate | Single large VLM; end-to-end learned parser with its own validator | Small parsers beat large VLMs on tables; the gate keeps audit and admission deterministic; the July 2026 standalone-parser designs were superseded for the same reason (OQ11) |
| Stage A model | PaddleOCR-VL-1.6 | GLM-OCR (kept as comparison), DeepSeek-OCR-2, MinerU2.5 | Best table accuracy, Apache-2.0, vLLM support; MinerU has extra terms |
| Stage B model | Qwen3.5-9B | Qwen3-VL-8B (older), Qwen3.8-27B (does not fit bf16), Gemma 4 12B (tight), Llama (licence) | Apache-2.0, native VL, fits the 5090 for LoRA and serving |
| Serving | vLLM | SGLang, TensorRT-LLM, Ollama | Structured outputs, batching, existing OpenAI-compatible client; SGLang is the fallback |
| Fine-tuning | PEFT/TRL via LLaMA-Factory | Full fine-tune; Unsloth-only | Fits one GPU; reproducible; Unsloth optional after licence check |
| Rendering | pypdfium2 | PyMuPDF (AGPL), poppler subprocess | Licence and speed |
| Languages | Python for everything except mature native libraries; Rust as a conditional candidate | C/C++ rewrites; Rust-first rewrite | Measured bottleneck is orchestration and I/O; native code without evidence adds risk |
| Data boundary | Self-hosted only | Cloud document-AI APIs | Rulings; customer data |
| First phase | Ceiling experiment with no training | Train first | Cheapest way to learn the ceiling and the failure modes |
| Holdout | Untouched | Use for prompt tuning | Doctrine |

---

## 21. Remaining owner decisions (business, legal, budget, risk acceptance only)

1. **Budget for the ceiling experiment:** approve up to USD 250 of rented GPU time for two weeks on
   the existing provider under the existing remote_paid rules. (Blocks M1.)
2. **PyMuPDF (AGPL) in the commercial pipeline:** buy an Artifex commercial licence, or approve the
   migration to pdfium (3–5 engineering days plus a geometry-equivalence check). Recommendation:
   migrate. (Blocks production eligibility, not the experiment.)
3. **Training-data boundary:** approve fine-tuning on customer-derived silver labels and adjudicated
   hard cases on the rented GPU under the existing rules with attestation per job, or restrict
   training to synthetic data until further notice. Recommendation: approve, with the deletion and
   lineage rules of §9. (Blocks M4's real-data runs; synthetic-only runs need no new approval.)
4. **Retention period for derived training records and adapters:** recommendation: keep while the
   source document is retained; delete with the source; adapters retired at next retrain. (Legal.)
5. **Production hosting:** rented Linux GPU instance (opex) versus owned hardware (capex).
   Recommendation: rented until volume justifies otherwise; decide before M6.

Everything else in this plan is a technical decision made here and open to challenge in review.

---

## 22. Changelog versus the v0 proposal (`CI-STATEMENT-VLM-PLAN.md`, preserved unchanged)

* Architecture changed from a single fine-tuned general VLM to a two-stage proposer (document parser
  + general VLM) after evaluating current document-parsing models: small specialized models lead on
  tables at a fraction of the compute.
* Model choice updated from Qwen2.5-VL to Qwen3.5-9B (native multimodal, Apache-2.0, 2026) with
  Qwen3.8-27B as an experiment-only second opinion; Qwen2.5-VL is superseded.
* Added the measured performance baseline and the language/performance study, decision matrix,
  benchmark harness and adoption threshold; concluded that Python with native-backed libraries wins
  first and that Rust is a conditional candidate, not a plan.
* Added the licensing review, including the PyMuPDF AGPL finding and the pdfium migration.
* Added the data boundary/retention/lineage/attestation design, the threat model, deployment stages,
  monitoring and rollback rules, the risk register, the gate deliverables and the decision log.
* Detailed the two-week ceiling experiment with arms, measurements and go/revise/stop thresholds.
* Reduced the owner decision list to five business/legal/budget/risk items.

## 23. Sources checked on 2026-09-17 (re-verify at each gate)

Model cards and repositories: PaddlePaddle/PaddleOCR-VL-1.6 (Apache-2.0; OmniDocBench v1.6 96.33);
zai-org/GLM-OCR (MIT; PP-DocLayoutV3 Apache-2.0); deepseek-ai/DeepSeek-OCR-2 (Apache-2.0);
Qwen/Qwen3.5-9B (Apache-2.0; native VL; 262K context; vLLM main at release); QwenLM/Qwen3.6 and
Qwen3.8 (Qwen3.8-27B Apache-2.0, native VL, August 2026; Qwen3.8-Max-class custom licence);
Qwen/Qwen3-VL-8B/32B-Instruct (Apache-2.0); Gemma 4 announcements (Apache-2.0). Serving: vLLM
releases (v0.28.0, 2026-08-26), vLLM structured-outputs documentation (xgrammar/guidance, auto
backend); vLLM issues and forum threads on RTX 5090 (sm_120, CUDA 12.8, PyTorch 2.7+ cu128 wheels,
FlashAttention 2 on Blackwell). Fine-tuning: LLaMA-Factory, ms-swift, Unsloth documentation for
Qwen3-VL/Qwen3.5. Rendering and licences: PyMuPDF licensing pages and discussions (AGPL-3.0 with
commercial licences from Artifex); pypdfium2 (Apache-2.0 or BSD-3); pdfium-render (Apache-2.0 or
MIT). Performance baseline: this repository's stage-6 custody rows and wave log (2026-09-17).
