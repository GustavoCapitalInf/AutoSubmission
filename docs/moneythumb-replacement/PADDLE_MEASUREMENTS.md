# PADDLE_MEASUREMENTS — Phase 2.1 cell P runtime/cost telemetry

```
STATUS: MEASURED — one live run over the real SSH tunnel to the Vast.ai RTX 5090
DATE: 2026-09-02
FIXTURE: tests/paddle_synthetic.py (build_ledger_page / render_image_pdf) — SYNTHETIC ONLY,
         never a real statement, never Bank Statements/ or tests/corpus_cache/ content
```

## Identity (worker's own `/version`, verified against the D5 pins before any image was sent)

| field | value |
|---|---|
| provider / execution_class | `vast.ai` / `remote_paid` |
| GPU | NVIDIA GeForce RTX 5090, 32,607 MiB total, driver 580.173.02 |
| PaddleOCR / PaddlePaddle | 3.7.0 / 3.3.0 |
| OCR version | PP-OCRv5 |
| detection / recognition model | `PP-OCRv5_server_det` / `en_PP-OCRv5_mobile_rec` |
| pipeline switches | orientation classify off, unwarping off, textline orientation off, `return_word_box=True`, `text_rec_score_thresh=0.0` |
| worker contract | 1 |
| remote Python | 3.12.14 |

No PP-OCRv6 anywhere in the identity; no host, port, user or token in this file or in the
measurement JSON (`.paddle_runtime/measure-*.json`, gitignored).

## Fixture

An 8-row synthetic ledger page (`tests.paddle_synthetic.build_ledger_page(n_rows=8)`),
rasterised to an image-only PDF at 300 dpi (the D5-pinned raster dpi) and re-encoded as PNG:
2550 x 3300 px, ~248 KiB PNG before base64.

## Cold vs. warm latency

Measured immediately after a fresh `tools.paddle_vast start` (the worker's `/version` reported
`model_loaded: false` before this request — a genuine cold load, not a warm re-measurement):

| metric | value |
|---|---|
| cold end-to-end (local rasterise + transfer + infer + adapt via `client.ocr_page`) | **5,087.5 ms** |
| cold inference only (`timing.inference_ms`, the worker's own model-load + first-forward-pass timer) | **3,981.0 ms** |
| warm median end-to-end, n=20 | **1,521.8 ms** |
| warm p95 end-to-end, n=20 | **1,590.1 ms** |

(An earlier measurement taken against an already-warm worker — reused from the live proof
immediately before it — showed cold end-to-end 1,495.7 ms / inference 444.6 ms and warm median
1,503.4 ms / p95 1,538.0 ms: consistent with the 1.5 s warm figure above, and the number that
would be mistakenly reported as "cold" had the worker not been explicitly restarted for a true
measurement.)

## Transfer size (per page, this fixture)

| metric | value |
|---|---|
| bytes sent (PNG, base64-encoded, JSON-wrapped) | 253,799 bytes (~248 KiB) |
| bytes received (JSON response incl. word boxes) | 12,263 bytes (~12 KiB) |

## GPU

| metric | value |
|---|---|
| GPU memory used, model loaded, idle between requests | 7,692 MiB / 32,607 MiB total |
| GPU utilization sampled at that instant | 0% (idle between requests; the pipeline serialises inference, so utilization is bursty around each request, not sustained) |

## Runtime / cost

| metric | value |
|---|---|
| total worker wall-clock across this proof (two `start`/`stop` cycles: the live proof + a warm re-measurement, then a fresh restart + the cold measurement above) | ~262 s (~4.4 minutes) |
| measurement-only wall time (the `measure` command itself, 21 requests) | 35.7 s (cold run) + 31.8 s (warm-worker run) |
| hourly rate | not discoverable from the instance's own `vast-capabilities` manifest (no cost/price/rate field published) and not supplied by Gustavo for this run |
| **cost** | **"rate not measured"** — runtime is reported above; cost is never estimated from an assumed rate |

## What this measures (and does not)

This is the Paddle rung's cost per SYNTHETIC page at 300 dpi on an idle, already-deployed RTX
5090 worker over a warm SSH tunnel. It does not include: model download/first-install time (the
official PP-OCRv5 models were already cached on the host before this measurement — a fresh
instance would pay that cost once), Vast.ai instance provisioning/boot time, or any measurement
against the 13-document legal escalation population (D8: that population is not sent to Vast in
Phase 2.1).

## Commands run (host/port/user/token never shown; the runbook has the full sequence)

```
python -m tools.paddle_vast check
python -m tools.paddle_vast deploy
python -m tools.paddle_vast start
python -m tools.paddle_vast tunnel-up
PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR python -m pytest tests/test_paddle_live.py -m live -q
python -m tools.paddle_vast stop && python -m tools.paddle_vast start   # fresh restart for a genuine cold measurement
PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR python -m tools.paddle_vast measure --n-rows 8 --warm-requests 20
python -m tools.paddle_vast stop
python -m tools.paddle_vast tunnel-down
```
