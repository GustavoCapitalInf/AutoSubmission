# Bank Statement → Markdown (Unlimited-OCR)

Converts a bank-statement PDF into one Markdown file by running each page through
`baidu/Unlimited-OCR` on an **OpenAI-compatible endpoint**. The OCR stage itself
does no math — it only transcribes. The downstream
[analysis layer](#analysis-layer--statement--metrics--mcalender-findings-gemini)
turns that markdown into structured metrics (daily average balance, deposits, NSF
counts) and MCA/lender findings.

## How it runs

The model runs on a GPU **elsewhere** — this machine is only the client:

- **Remote:** a rented **RunPod** NVIDIA GPU serving `baidu/Unlimited-OCR` via
  vLLM's dedicated `vllm/vllm-openai:unlimited-ocr` image (exposes `/v1`).
- **Local (AMD):** your **RX 7800 XT** box, via transformers + PyTorch-ROCm behind
  a small OpenAI-compatible shim (`local_ocr_server.py`). vLLM/SGLang are CUDA-only
  and Ollama/llama.cpp don't support this architecture, so transformers is the
  route on RDNA3. Same client — only the base URL / key change. See
  [Serving locally on an AMD GPU](#serving-locally-on-an-amd-gpu-rx-7800-xt--rocm).

No OpenAI account or cost is involved; the `openai` package just speaks the same
wire format your server exposes.

## Setup (Python 3.12)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Poppler must be installed (Windows: `C:\poppler-24.08.0\Library\bin`).

## Serving the model (RunPod)

Requires the dedicated image (the architecture isn't in a stable vLLM pip release):

```
Container image:        vllm/vllm-openai:unlimited-ocr
Container start command: baidu/Unlimited-OCR --host 0.0.0.0 --port 8000 --trust-remote-code \
                          --logits_processors vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor \
                          --no-enable-prefix-caching --mm-processor-cache-gb 0
Environment variables:  HF_HUB_DISABLE_XET=1
Container disk:         60GB
Expose HTTP ports:      8000
GPU:                    any card with >=8GB VRAM (BF16)
```

## Serving locally on an AMD GPU (RX 7800 XT / ROCm)

Runs `baidu/Unlimited-OCR` on your own GPU instead of RunPod — no per-hour cost.
`local_ocr_server.py` loads the model via its `trust_remote_code` `model.infer(...)`
and exposes the same `/v1/chat/completions` the client already speaks, so the CLI
and webapp work unchanged. Verified on an RX 7800 XT (gfx1101), ROCm 6.3/7.x,
Python 3.12–3.14, at ~23 s/page.

```bash
# one-time: add the GPU-serving deps on top of the client venv
.venv/bin/python -m pip install -r requirements-local.txt

# start the server (loads the model, then serves on http://localhost:8000/v1)
./serve_local.sh
```

Then, in another shell, point the client at it and run as usual:

```bash
export OCR_BASE_URL=http://localhost:8000/v1
export OCR_API_KEY=EMPTY
.venv/bin/python -m webapp.app          # or: .venv/bin/python parse.py <pdf> --out out.md
```

Notes:
- **transformers must be 4.x** (pinned in `requirements-local.txt`) — the model's
  remote code imports `is_torch_fx_available`, removed in transformers 5.x.
- `serve_local.sh` sets `HSA_OVERRIDE_GFX_VERSION=11.0.0` (the standard RDNA3
  desktop workaround) and `HF_HUB_DISABLE_XET=1`.
- **Live streaming + region boxes work.** The server calls `infer()` in
  `eval_mode` (non-streaming client) or taps its internal `TextStreamer`
  (streaming client) so the raw `<|det|>label [x0,y0,x1,y1]<|/det|>` region tags
  reach the client token-by-token — driving the webapp's live fill, colored box
  overlays, and inline check-image cropping. (`save_results` mode would instead
  strip those tags into a clean `result.md`, killing the boxes — so the server
  avoids it.)
- The vLLM-only request fields (`skip_special_tokens`, `vllm_xargs`) are accepted
  and mapped where meaningful (`ngram_size`→`no_repeat_ngram_size`,
  `window_size`→`ngram_window`) or ignored.
- **RDNA3 stability fix:** the server forces the math SDPA backend during
  inference. The vision encoder's `scaled_dot_product_attention` otherwise hits an
  experimental ROCm flash/mem-efficient kernel that faults with an HSA hardware
  exception on gfx1101 for larger image tensors. Math is always correct (slightly
  slower). Keep `image_size` at 640 (Gundam crop) — `image_size=1024` crashes even
  with the math backend.
- **DPI 300 is the tuned default** (`parse.py`/pipeline). On dense check-detail
  tables, 200→300 measurably recovers amounts the model dropped at 200; 400 is
  *worse* (oversampling degrades the crop tiling). The prompt stays `Free OCR.` —
  the `<image>\n<|grounding|>…` markdown prompts return empty output on this model.

## Configure the endpoint

```bash
export OCR_BASE_URL="https://<pod-id>-8000.proxy.runpod.net/v1"   # or http://localhost:8000/v1
export OCR_MODEL="baidu/Unlimited-OCR"                            # default
export OCR_API_KEY="EMPTY"                                        # or the token your server expects
# optional: OCR_TIMEOUT (default 120), OCR_RETRIES (default 3),
#           OCR_NGRAM_SIZE (default 35), OCR_WINDOW_SIZE (default 128)
```

`OCR_WINDOW_SIZE` should be raised (e.g. 1024) if you send multi-page/whole-document
requests instead of single pages.

## Usage

```bash
.venv/Scripts/python.exe parse.py "BankStatements/CHASE_BANK/Chase Salomon January.pdf" --out output/chase.md
# flags: --out FILE (else stdout), --dpi N (default 300), --model NAME (override)
```

Output: one `.md` with a provenance comment header and pages separated by
`--- Page N ---`. The model's own `<|det|>...<|/det|>` region-annotation tags are
stripped automatically, leaving clean text and HTML tables.

## Local web frontend

A dark, 4-panel document viewer (original page images | markdown source |
rendered markdown | analysis metrics) with a toolbar to upload PDFs, switch between documents, and
download results. Easiest way to launch (PowerShell) — pass the current RunPod
pod id and it derives the endpoint + key for you:

```powershell
.\run.ps1 -PodId jy39vysntpffa0
```

Or set the env vars yourself and run it directly with the venv Python (note:
plain `python` is the wrong interpreter — use the venv one so the deps resolve):

```powershell
$env:OCR_BASE_URL = "https://<pod-id>-8000.proxy.runpod.net/v1"
$env:OCR_API_KEY  = "sk-<pod-id>"
.venv\Scripts\python.exe -m webapp.app
```

Then open `http://localhost:5000`. Uses the same `OCR_*` environment variables as
the CLI.

## Analysis layer — statement → metrics + MCA/lender findings (Gemini)

The `analysis/` package turns the OCR markdown into structured underwriting data.
It's built on **separation of concerns**: an LLM (Google **Gemini**, cheap
`gemini-3.5-flash-lite`) only transcribes the statement into a normalized ledger;
all math and detection is deterministic Python. Stages:

1. **Extract** (`extract.py`) — markdown → `Statement` via Gemini structured
   outputs (Pydantic `response_schema`). Captures line items *and* the bank's own
   printed summary block (totals, counts, printed average balance).
2. **Reconcile** (`reconcile.py`) — `beginning + Σamounts == ending`, running-
   balance continuity, and **line-item coverage vs the bank's stated totals**.
   Catches OCR/extraction errors before any number is trusted. A statement that
   fails reconciliation is automatically re-extracted with the stronger
   `gemini-3.5-flash` (you pay flash-lite prices for the clean majority).
3. **Metrics** (`metrics.py`) — daily average balance (from dated running
   balances, carrying forward across no-activity days), or the bank's printed
   average when line items are incomplete; deposits/withdrawals, NSF count,
   negative days.
4. **Detect** (`detect.py`) — MCA/lender detection: a known-funder dictionary
   plus recurring fixed-debit pattern detection (the daily/weekly remittance
   signature), each returning the evidence transactions.

```bash
# one-time: deps + API key (key lives in a gitignored .env, never in code)
.venv/bin/python -m pip install -r requirements-analysis.txt
echo 'GEMINI_API_KEY=your-key-here' > .env

# analyze one OCR'd statement
.venv/bin/python analyze.py output/ace.md              # human-readable report
.venv/bin/python analyze.py output/ace.md --json out.json

# batch-triage a whole folder into a CSV (one row per statement)
.venv/bin/python batch.py output/ --out triage.csv     # folder of .md
OCR_BASE_URL=http://localhost:8000/v1 OCR_API_KEY=EMPTY \
    .venv/bin/python batch.py BankStatements/ --out triage.csv   # PDFs (OCR + analyze)
```

The batch CSV carries the key underwriting figures per statement plus a
`needs_review` flag driven by whether the bank's own summary reconciles — clean
statements flow through, only the questionable ones get human eyes. Small-bank /
image statements (where per-transaction detail is incomplete) still yield
trustworthy figures from the bank's printed summary, which reconciliation validates.

Tune via env: `GEMINI_MODEL`, `GEMINI_ESCALATION_MODEL`. Extend maintained lender,
candidate, insurance, and exclusion aliases in
`analysis/classification_registry.py`.

Transaction categories, lender/insurance precedence, contribution flags, and the
eligible-deposit denominator are defined in
[`docs/transaction-classification.md`](docs/transaction-classification.md).

## Tests

```bash
.venv/Scripts/python.exe -m pytest            # fast unit tests (network mocked)
OCR_BASE_URL=... .venv/Scripts/python.exe -m pytest -m live   # real-endpoint smoke
```
