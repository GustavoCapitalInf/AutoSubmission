# Phase 3 license register (ceiling experiment)

Rule (plan v1 §5, §8): nothing enters the stack without a row here; only Apache-2.0, MIT, BSD or equivalent
without an owner ruling; re-verified at every gate. Model revision hashes are recorded by the fetch receipts
(`discovery_reports/train13-logs/p3ceiling/fetch-<key>-<UTC>.json`, private tree) and copied here at G1.
Checked 2026-09-17 unless noted.

## Models (self-hosted on the rented Vast RTX 5090; weights downloaded from Hugging Face; no customer data leaves our infrastructure)

| Name | Repo | Revision | SPDX | Role | Source |
|---|---|---|---|---|---|
| PaddleOCR-VL-1.6 | `PaddlePaddle/PaddleOCR-VL-1.6` | recorded in fetch receipt `a` | Apache-2.0 | Stage A document parser (VL model) | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 |
| PP-DocLayoutV3 | PaddleX official model (host cache `~/.paddlex/official_models`) | paddlex 3.7.2 pin | Apache-2.0 | Stage A layout detection | https://github.com/PaddlePaddle/PaddleOCR |
| Qwen3.5-4B | `Qwen/Qwen3.5-4B` | recorded in fetch receipt `b` | Apache-2.0 | Stage B general VLM (primary) | https://huggingface.co/Qwen/Qwen3.5-4B |
| Qwen3.5-9B FP8 dynamic | `RedHatAI/Qwen3.5-9B-FP8-dynamic` | recorded in fetch receipt `b9` (only if run) | Apache-2.0 (third-party quantization of Apache-2.0 weights) | Stage B second variant | https://huggingface.co/RedHatAI/Qwen3.5-9B-FP8-dynamic |
| Qwen3.8-27B NVFP4 (NVIDIA ModelOpt build) | `nvidia/Qwen3.8-27B-NVFP4` | HF revision 482ca0f3832238542f8f5295dde86b5f22711d80; fetch receipt `b27` | Apache-2.0 (base `Qwen/Qwen3.8-27B` is Apache-2.0; the earlier "Qwen3.8 flagship (custom)" exclusion concerns the flagship only, checked 2026-09-18) | Stage B second opinion (plan arm 5), the model Gustavo asked to test on 2026-09-18 | https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4 |

Excluded on license: MinerU2.5 (Apache-2.0 with additional commercial terms), Qwen3.8 flagship (custom), Gemma 3 and earlier (Gemma terms), Llama family, any API-only model.

## Serving and training stack (host image and Paddle virtualenv)

| Package | Version on host | SPDX |
|---|---|---|
| vLLM | 0.29.0 | Apache-2.0 |
| PyTorch | 2.13.0+cu130 | BSD-3-Clause |
| transformers | 5.16.1 | Apache-2.0 |
| xgrammar | 0.2.3 | Apache-2.0 |
| llguidance | 1.7.6 | MIT |
| flashinfer | 0.6.18 | Apache-2.0 |
| paddleocr / paddlex / paddlepaddle-gpu | 3.7.0 / 3.7.2 / 3.3.0 | Apache-2.0 |
| huggingface_hub | 1.30.0 | Apache-2.0 |
| pypdfium2 (host) | 5.13.0 | Apache-2.0 OR BSD-3-Clause (pdfium: BSD-3-Clause) |
| numpy | host / local | BSD-3-Clause |

## Local harness (`vlm/`, `tools/vlm_*.py`)

| Package | Version (local) | SPDX |
|---|---|---|
| pypdfium2 | 5.8.0 | Apache-2.0 OR BSD-3-Clause |
| Pillow | 12.2.0 | MIT-CMU (HPND) |
| jsonschema | 4.26.0 | MIT |
| pydantic | 2.13.4 | MIT |
| Python standard library | 3.14.5 | PSF-2.0 |

## Flagged (outside `vlm/`, pre-existing)

| Package | Version | SPDX | Status |
|---|---|---|---|
| PyMuPDF (fitz) | 1.27.2.3 | AGPL-3.0-only | Used by the existing reader (`evidence/native.py`, `ocr/native_text.py`, `ocr/paddle_rung.py`, tests). Owner decision 2 in plan v1 §21: Artifex commercial license or migration to pdfium. Not used by the Phase 3 harness. |
| poppler (pdftoppm via pdf2image) | 24.08.0 | GPL-2.0-or-later / GPL-3.0 | Subprocess invocation only (`ocr/rasterize.py`); removed by the pdfium migration. Not used by the Phase 3 harness. |
