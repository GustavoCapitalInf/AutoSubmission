# Bank Statement → Markdown (Nanonets-OCR2)

Converts a bank-statement PDF into one Markdown file by running each page through
a Nanonets-OCR2 model on an **OpenAI-compatible endpoint**. The markdown is meant
to be handed to a downstream AI that does the math (e.g. daily average balance).
This tool does no math and no JSON extraction.

## How it runs

The model runs on a GPU **elsewhere** — this machine is only the client:

- **Now:** a rented **RunPod** NVIDIA GPU serving `nanonets/Nanonets-OCR2-1.5B-exp`
  via vLLM (exposes `/v1`).
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

## Configure the endpoint

```bash
export NANONETS_BASE_URL="https://<pod-id>-8000.proxy.runpod.net/v1"   # or http://localhost:8000/v1
export NANONETS_MODEL="nanonets/Nanonets-OCR2-1.5B-exp"                # default
export NANONETS_API_KEY="EMPTY"                                        # or the token your server expects
# optional: NANONETS_TIMEOUT (default 120), NANONETS_RETRIES (default 3)
```

## Usage

```bash
.venv/Scripts/python.exe parse.py "BankStatements/CHASE_BANK/Chase Salomon January.pdf" --out output/chase.md
# flags: --out FILE (else stdout), --dpi N (default 200), --model NAME (override)
```

Output: one `.md` with a provenance comment header and pages separated by
`--- Page N ---`.

## Tests

```bash
.venv/Scripts/python.exe -m pytest            # fast unit tests (network mocked)
NANONETS_BASE_URL=... .venv/Scripts/python.exe -m pytest -m live   # real-endpoint smoke
```
