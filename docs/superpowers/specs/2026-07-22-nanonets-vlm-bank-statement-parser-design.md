> **STATUS: SUPERSEDED (2026-09-01, `docs/moneythumb-replacement/PHASE2_RULINGS.md` OQ11)**
>
> Gustavo's OQ11 ruling marks this design's ARCHITECTURE superseded, on the same
> grounds it superseded the PaddleOCR design this file's own "Supersedes:" line
> names (`2026-07-21-paddleocr-bank-statement-parser-design.md`, also banner-marked
> SUPERSEDED). The standalone parser / own-JSON / own-validator architecture is not
> the plan: `docs/moneythumb-replacement/
> PHASE2_ARCHITECTURE_PLAN.md` is the accepted architecture, and under it a vision
> extractor supplies EVIDENCE only, feeding the SAME deterministic validator every
> other reader in this platform already goes through — it must not become its own
> independent financial parser or validator.
>
> Any bbox / row / column / geometry reconstruction ideas relevant here are PRESERVED
> for reuse as the filling of `document_geometry` (`analysis/structurer/geometry.py`)
> in Phase 2.1, re-homed rather than discarded.
>
> `parse.py` as a standalone entry point is no longer a front door (closed under
> Phase 2.0 cell P20-SEAM's endpoint/entry-point work).
>
> The document body below is kept verbatim as a historical record of the design
> reasoning and is not edited by this notice. Do not read any of it as current
> architecture.
>
> ---

# Nanonets-OCR2 Bank Statement → Markdown — Design

**Date:** 2026-07-22
**Status:** Approved (pending written-spec review)
**Supersedes:** `2026-07-21-paddleocr-bank-statement-parser-design.md`

## Why this supersedes the PaddleOCR design

The original design used PaddleOCR (CPU) plus bbox reconstruction and per-bank
profiles. On the target hardware (Ryzen 7 7730U laptop, no NVIDIA GPU, integrated
Radeon iGPU unusable for ML) PaddleOCR ran ~100–150 s/page with `mkldnn` disabled —
untenable for multi-page statements. We pivot to a vision model,
**Nanonets-OCR2-3B**, served on a GPU we don't own locally.

The PaddleOCR code already built (Tasks 1–8: models, rasterize, engine, grouping,
helpers, detect, profiles, serialize, pipeline, CLI) is **retired** by this design.
`rasterize.py` and the git scaffold/venv are reused; the rest is replaced.

## Purpose

A standalone CLI that converts a bank-statement PDF into a single **Markdown**
file. Nanonets-OCR2-3B converts each page image to structured markdown (tables
rendered as HTML tables, plus semantic tags). The markdown is the deliverable —
it is handed to a downstream AI that does the math (e.g. daily average balance).
This tool does **no parsing into JSON and no math**.

## Scope & Constraints

- **Input:** PDF files (mostly digitally-generated; may be scanned). Treated
  uniformly: rasterize → per-page VLM.
- **Model:** **Nanonets-OCR2-1.5B-exp** (the smaller, experimental Nanonets
  document→markdown OCR VLM). Model name is **configurable**; default to this
  model, allow swapping (e.g. the 3B) via config.
- **Inference host:** an **OpenAI-compatible endpoint**, host-agnostic:
  - **Now:** a rented **RunPod NVIDIA GPU** running vLLM serving Nanonets-OCR2-3B.
  - **Later:** the user's **RX 7800 XT** box (vLLM/Ollama/llama.cpp) — same client,
    only the base URL/model/key change.
  - This machine (the laptop) is only ever the **client**; it never runs the model.
- **Processing:** **page by page** — one page image per API call; concatenate.
- **Output:** **one combined Markdown file per PDF** (pages separated), to a file
  via `--out` or to stdout. A single non-rendering provenance comment at the top.
- **Client library:** the `openai` Python package (free; points at our endpoint).
- **No OpenAI account, no OpenAI cost.** The only cost is the GPU rental.
- **No math, no JSON extraction, no per-bank logic.** One prompt handles every bank.

## Architecture & Flow

```
parse.py <statement.pdf> [--out out.md] [--dpi N] [--model NAME]
  1. Rasterize     pdf2image (poppler) → one PIL image per page @ configurable DPI
  2. Per page      encode image as base64 data URI; POST to the OpenAI-compatible
                   /v1/chat/completions endpoint with the Nanonets OCR prompt
  3. Collect       gather each page's returned markdown, in order
  4. Assemble      join pages with "--- Page N ---" separators; prepend a
                   provenance comment; write .md (or stdout)
```

One shared client + a thin per-page loop. No bbox math, no bank profiles.

## Configuration (`ocr/config.py`)

Read from environment with sensible defaults; overridable by CLI flags where noted.

| Setting             | Env var              | Default                                   |
| ------------------- | -------------------- | ----------------------------------------- |
| Endpoint base URL   | `NANONETS_BASE_URL`  | RunPod endpoint placeholder (user sets)   |
| Model name          | `NANONETS_MODEL`     | `nanonets/Nanonets-OCR2-1.5B-exp`               |
| API key             | `NANONETS_API_KEY`   | `"EMPTY"` (vLLM/local accept any value)   |
| Request timeout (s) | `NANONETS_TIMEOUT`   | `120`                                     |
| Max retries         | `NANONETS_RETRIES`   | `3`                                       |

`--model` overrides `NANONETS_MODEL`; base URL/key come from env only (secrets).

## Module Layout

```
hasToworkOCR/
├── parse.py                 # CLI entry point: args, orchestrate, write markdown
├── requirements.txt         # + openai; PaddleOCR deps removed
├── BankStatements/          # sample PDFs (already present)
├── output/                  # generated .md (gitignored)
└── ocr/
    ├── __init__.py
    ├── config.py            # env-driven settings (above)
    ├── rasterize.py         # (KEPT) PDF bytes → list[PIL.Image]
    ├── ocr_client.py        # OpenAI-compatible client: image → page markdown
    ├── document.py          # StatementMarkdown holder + to_markdown()
    └── pipeline.py          # rasterize → per-page OCR → assemble
```

**Removed from the PaddleOCR build** (delete files + their tests): `engine.py`,
`grouping.py`, `detect.py`, `parse_helpers.py`, `models.py`, `serialize.py`,
`profiles/` (all). Their tests (`test_models`, `test_engine`, `test_grouping`,
`test_parse_helpers`, `test_generic_profile`, `test_detect`, `test_serialize`,
old `test_pipeline`) are removed. `rasterize.py` + `test_rasterize.py` stay.

## Components

### `ocr/ocr_client.py`

- `build_prompt() -> str` — the Nanonets OCR instruction (convert the page to
  clean markdown; render tables as HTML tables; keep it faithful; no commentary).
- `image_to_data_uri(image: PIL.Image.Image) -> str` — PNG-encode → base64
  `data:image/png;base64,...`.
- `ocr_page(image, *, client=None) -> str` — build the chat-completions request
  (system/user with the image + prompt), call the endpoint, return the model's
  markdown text. Client is injectable for testing; default constructed from config
  (`OpenAI(base_url=..., api_key=..., timeout=...)`). Retries on transient errors
  with backoff up to `NANONETS_RETRIES`.

### `ocr/document.py`

```python
@dataclass
class StatementMarkdown:
    source_file: str
    model: str
    pages: list[str]          # one markdown string per page (in order)

    def to_markdown(self) -> str:
        # "<!-- source: X | pages: N | model: Y -->\n\n"
        # then pages joined by "\n\n--- Page {i} ---\n\n"
```

Empty pages are kept and rendered as `--- Page N (empty) ---`; the count of empty
pages is noted in the provenance comment.

### `ocr/pipeline.py`

- `parse_statement(pdf_bytes, source_file="", dpi=..., page_ocr_fn=None) ->
  StatementMarkdown` — rasterize, run `page_ocr_fn` (default `ocr_client.ocr_page`)
  per page, collect markdown, return `StatementMarkdown`. `page_ocr_fn` is
  injectable so tests never hit the network.

### `parse.py`

- CLI: `python parse.py <pdf> [--out FILE] [--dpi N] [--model NAME]`.
- Reads bytes, calls `parse_statement`, writes `to_markdown()` to `--out` or stdout.
- Unreadable/corrupt PDF → non-zero exit + stderr message, no partial file.

## Error Handling

- **Bad/unreadable PDF** → exit non-zero, clear stderr message; never write a
  partial `.md`.
- **Endpoint unreachable / HTTP / timeout** → retry with backoff up to
  `NANONETS_RETRIES`; if still failing, exit non-zero with a clear message (don't
  emit a half-statement).
- **A page returns empty markdown** → keep going; render `--- Page N (empty) ---`;
  count empties in the provenance comment.

## Testing

- **`ocr_client.ocr_page`** — unit test with a **mocked** OpenAI client (no network):
  assert the request carries a base64 image data URI + the prompt, and that the
  mocked completion's text is returned. Assert retry-then-succeed on a transient error.
- **`image_to_data_uri`** — assert `data:image/png;base64,` prefix and non-empty payload.
- **`ocr/pipeline.parse_statement`** — inject a fake `page_ocr_fn` (no network);
  assert N pages, correct separators, provenance comment, empty-page handling.
- **`ocr/document.to_markdown`** — assert provenance line + separators exact.
- **`rasterize.py`** — keep the existing real-PDF test.
- **One live smoke** (opt-in `live` marker, off by default) — hits the real
  configured endpoint on a single sample page; run on demand once the RunPod pod
  is up, not in normal test runs.

PaddleOCR/vision inference is never invoked in the default test run.

## Out of Scope

- Any math/calculation (downstream AI's job).
- JSON/structured extraction of transactions (markdown is the deliverable).
- Per-bank detection or profiles (one prompt handles all banks).
- Running the model on this laptop (client only).
- Non-PDF inputs.

## Deployment Notes (RunPod → 7800 XT)

- **RunPod (now):** launch a pod (e.g. RTX 4090/3090, 24GB) with a vLLM image
  serving `nanonets/Nanonets-OCR2-1.5B-exp`; it exposes `/v1`. Set `NANONETS_BASE_URL`
  to the pod's proxied URL and `NANONETS_API_KEY` to the token set on the server
  (or `EMPTY`). Spin up on demand, process, spin down to control cost.
- **RX 7800 XT (later):** serve the same model with vLLM (Linux+ROCm 7.x) or
  Ollama/llama.cpp (Windows+Vulkan); point `NANONETS_BASE_URL` at
  `http://localhost:...`/`v1`. No code change — just env vars.
```
