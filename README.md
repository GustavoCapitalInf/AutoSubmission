# Bank Statement → Markdown (Unlimited-OCR)

Converts a bank-statement PDF into one Markdown file by running each page through
`baidu/Unlimited-OCR` on an **OpenAI-compatible endpoint**. The markdown is meant
to be handed to a downstream AI that does the math (e.g. daily average balance).
This tool does no math and no JSON extraction.

## How it runs

The model runs on a GPU **elsewhere** — this machine is only the client:

- **Now:** a rented **RunPod** NVIDIA GPU serving `baidu/Unlimited-OCR` via vLLM's
  dedicated `vllm/vllm-openai:unlimited-ocr` image (exposes `/v1`).
- **Later:** your **RX 7800 XT** box (vLLM / Ollama / llama.cpp). Same client —
  only the base URL / model / key change.

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
# flags: --out FILE (else stdout), --dpi N (default 200), --model NAME (override)
```

Output: one `.md` with a provenance comment header and pages separated by
`--- Page N ---`. The model's own `<|det|>...<|/det|>` region-annotation tags are
stripped automatically, leaving clean text and HTML tables.

## Local web frontend

A dark, 3-panel document viewer (original page images | markdown source |
rendered markdown) with a toolbar to upload PDFs, switch between documents, and
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

## Tests

```bash
.venv/Scripts/python.exe -m pytest            # fast unit tests (network mocked)
OCR_BASE_URL=... .venv/Scripts/python.exe -m pytest -m live   # real-endpoint smoke
```
