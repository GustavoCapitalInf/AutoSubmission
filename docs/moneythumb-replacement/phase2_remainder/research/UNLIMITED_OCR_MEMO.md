<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Memo — "Unlimited OCR": what it is, what it does today (2026-09-03), and whether it can be a second-opinion extractor

Prepared read-only against `bankStatementAnalysis` @ `train11` (HEAD `21e3163`). No file in the repository was modified. No secret value is reproduced here; only env-var NAMES are cited.

---

## 0. One-paragraph answer

"Unlimited OCR" in this repository is **not a SaaS vendor**. It is the open-weights model **`baidu/Unlimited-OCR`** (Baidu Inc., MIT license, released 2026-06-22), a DeepSeek-OCR derivative that the project self-hosts behind an OpenAI-compatible endpoint — either a local Flask shim on the operator's AMD RX 7800 XT (`local_ocr_server.py`) or a rented RunPod vLLM container. The name is the model's name, not a subscription tier. The model exists today, is actively maintained (25.1k GitHub stars, 3.18M HF downloads, last HF commit 2026-07-29), and has since acquired a **hosted Baidu AI Cloud API** ("文档解析（Unlimited-OCR）", public beta 2026-07-03, temporarily free) that the repository has never used. It is a **different engine family from PaddleOCR PP-OCRv5** (end-to-end vision-language autoregressive decoder vs. a detection+recognition pipeline), so it can act as a genuine architectural second opinion — with two caveats: (1) it is the same vendor and its paper says its single-page training labels were produced with PaddleOCR, so the two are not independent at the annotation-lineage level; (2) it emits **region-level** `<|det|>` boxes and **no word boxes and no confidence**, so it cannot fill the canonical `WordBox` evidence model without either a new region-level evidence type or a forced alignment onto Paddle's word geometry. Sending real customer statements anywhere but the loopback server would require the same separate remote-data / privacy / retention ruling that PHASE2_RULINGS.md already demands for Vast.ai.

---

## 1. Repository findings (file:line)

### 1.1 Identity and endpoint

| Fact | Evidence |
|---|---|
| Model token default `"baidu/Unlimited-OCR"` | `ocr/config.py:142`; mirrored in `telemetry/prices.py:37` (FREE_MODELS), `telemetry/record.py:166` (`VISUAL_MODEL_TOKENS`), `telemetry/run_of_record.py:240`, `local_ocr_server.py:35` |
| Base URL default `http://localhost:8000/v1` (OpenAI dialect) | `ocr/config.py:141`; the client is `openai.OpenAI(base_url, api_key, timeout)` at `ocr/ocr_client.py:567-568` |
| Two serving options, both self-hosted | **Local $0**: `local_ocr_server.py:1-18` (Flask, transformers `trust_remote_code`, bf16, eager attention, `model.infer(...)`), launched by `serve_local.sh:2-19` with ROCm env `HSA_OVERRIDE_GFX_VERSION`, `HF_HUB_DISABLE_XET`; deps `requirements-local.txt:8-18` (torch 2.9.1+rocm6.3, transformers 4.57.1). **Remote paid**: RunPod vLLM container `vllm/vllm-openai:unlimited-ocr`, `docs/runpod-setup.md:10-23`, `README.md:94-132`; endpoint host pattern `https://<pod-id>-8000.proxy.runpod.net/v1` (`run.ps1:25`, `docs/runpod-setup.md:22`) |
| Auth scheme | Bearer token via the OpenAI client. Env var **`OCR_API_KEY`** (`ocr/config.py:147`, default literal `"EMPTY"` for the local shim). For RunPod the key is derived from the pod id at launch (`run.ps1:24-27`; pattern documented at `docs/runpod-setup.md:19-23`). **No key value is committed**: no `.env` exists in the tree (only `.env.paddle.example`, whose names are Paddle/Vast only). |
| Other env knobs | `OCR_BASE_URL`, `OCR_MODEL`, `OCR_TIMEOUT` (120 s), `OCR_RETRIES` (3), `OCR_NGRAM_SIZE` (35), `OCR_WINDOW_SIZE` (128), `OCR_MAX_WORKERS` (1) — `ocr/config.py:141-158`; `OCR_LOCAL_MODEL`, `OCR_LOCAL_PORT` — `local_ocr_server.py:35-36`; remote opt-in literal env **`OCR_REMOTE_OPT_IN`** — `ocr/endpoint_policy.py:47-48` |
| Endpoint policy (OQ3) | `ocr/endpoint_policy.py:84-147` classifies loopback/private/remote/invalid structurally; `check_endpoint` (`:159-182`) allows remote only with the exact opt-in literal; `_build_client` re-derives the decision before the `openai` import (`ocr/ocr_client.py:544-568`); one endpoint per process, no fallback host (`ocr/endpoint_policy.py:19-21`) |
| Liveness probe | `GET /v1/models` only, no image sent (`ocr/availability.py:14-16, 140-195`) |
| History | `git 0ad20e6` 2026-07-23 "migrate from Nanonets to baidu/Unlimited-OCR" (Nanonets-OCR2 1.5B/3B produced repeating-token garbage); `56d28b3` local ROCm shim; `91cb767` RunPod docs. The project started 2026-07-21 as a PaddleOCR parser (`0979bbc`, `33a9734`), switched to Nanonets on 07-22, then to Unlimited-OCR on 07-23. |

### 1.2 Request shape the historical client sends (per page)

`ocr/ocr_client.py:600-676` (`ocr_page`):

* One **PNG page image** as a base64 `data:image/png;base64,…` URL (`image_to_data_uri`, `:321-325`), rasterized by `ocr/pipeline.py` at **300 DPI** (`parse_statement(dpi=300, fallback_dpi=250)`, `ocr/pipeline.py:22-25`); pages are OCR'd **independently**, optionally in parallel (`OCR_MAX_WORKERS`, `ocr/pipeline.py:159, 204`).
* Chat-completions message: text block **first** (`"<image>Free OCR."`, `_TASK` at `:10`, `build_prompt` at `:26-27`), then the `image_url` block (`:626-631`). Order and the literal `<image>` prefix are load-bearing (`docs/runpod-setup.md:112-117`).
* `temperature=0.0`, `max_tokens=4096` (`_MAX_TOKENS`, `:11`), `extra_body={"skip_special_tokens": False, "vllm_xargs": {"ngram_size": 35, "window_size": 128}}` (`:633-644`). Streaming optional (`on_delta`). Retries with exponential backoff (`:646-676`).
* Only PNG page images are ever sent — never the PDF, never multi-page in one request (the docs note `window_size=1024` would be needed for that, `docs/runpod-setup.md:125-127`).

### 1.3 Response shape the historical client consumes

* Plain `choices[0].message.content` string (markdown with HTML `<table><tr><td>` tables) plus `finish_reason` (`"stop"` / `"length"`) and, on vLLM, `usage.completion_tokens` — `ocr/ocr_client.py:574-587`, `ocr/truncation.py:11-22` (4096-token truncation flagged as page integrity).
* The raw text carries **region tags** `<|det|>label [x0,y0,x1,y1]<|/det|>content` prefixing "almost every transcribed line/table" (`docs/runpod-setup.md:134-135`). Labels observed/handled: `title, header, text, table, footer, figure, image, list, page_number, caption` (`ocr/render.py:155-160` `REGION_COLORS`) and picture labels `image|figure|picture|photo|chart|diagram|logo|signature` (`ocr/ocr_client.py:330-333`). Coordinates are treated as **0–1000 normalized per axis** (`ocr/ocr_client.py:328-329, 356-359`; `ocr/render.py:162-166, 171-172`). **No word boxes, no confidence, no per-cell coordinates for tables** anywhere in the client, server or tests (`tests/test_ocr_client.py:103-195` fixtures show only region tags).
* Known output quirks the client was written around: orphan/unclosed det tags, inline refusal prose on QR codes, `[Non-Text]` placeholders, repeated amounts, fused header rows, column bleed, mis-segmentation at 300 DPI, TD page-1 derailment (`ocr/ocr_client.py:12-23, 46-60, 63-82, 198-263`; `docs/runpod-setup.md:132-145`). All nine cleanup functions are **quarantined** (OQ1 = C): `POSTPROCESS_STATE="quarantined"`, `ADMITTED_POSTPROCESS=()` (`ocr/ocr_client.py:386-423`); `embed_image_regions` (pixels into markdown, audit F-2) is unwired on the analysis path (`:606-611`).

### 1.4 Documented pricing / latency / privacy notes in the repo

* **Cost**: `$0` vendor cost as a fact (`telemetry/prices.py:29-38`); infra cost unmetered ("self-hosted vLLM whose price depends on infrastructure we do not meter", `:13-17`). RunPod bills per GPU-hour while running; "Stop, don't Delete" (`docs/runpod-setup.md:157-162`).
* **Latency**: "~23 s/page" on the local RX 7800 XT with 1 worker (`README.md:50`; `docs/moneythumb-replacement/PARITY_MATRIX.md:13`). No RunPod/3090 latency was ever recorded. A single 24 GB GPU saturates per page; concurrency helps only on A100/H100 (`ocr/config.py:152-157`).
* **Privacy**: the audit's F-4 (egress + injection through unbounded env), now closed by the allowlist and the closed model-token charset (`ocr/config.py:18-111`); F-2 (pixels in canonical text) closed by unwiring; `trust_remote_code` named as supply-chain risk with "pin Unlimited revisions" (`PHASE2_ARCHITECTURE_PLAN.md:435`).
* **Never measured**: the visual rung produced **0 / 3,506** artifacts in every run of record (`OCR_LEGACY_AUDIT.md:55-75`; `PHASE2_ARCHITECTURE_PLAN.md:49`).

### 1.5 Rulings and plan notes about it

* **OQ5** (`PHASE2_RULINGS.md:39-43`): Tesseract stays first image rung; PaddleOCR is the primary new visual extractor; **Unlimited OCR is a bounded fallback after Paddle for remaining legitimate Class A extraction failures**; not in 2.0.
* **OQ3** (`:28-32`) allowlist enforced in code; **OQ6** (`:45-48`) RunPod may stay documented as an explicit optional/paid escape hatch, never an automatic fallback.
* **Ruling A** (`:137-151`): no automatic local → remote hop; no "parser failure → hosted model" hop; Class B → geometry, Class C → review, never another extractor.
* **Phase 2.1 authorization** (`:167-172`): Unlimited OCR explicitly **NOT authorized**; completion gate says "Unlimited OCR is not enabled" (`:216-220`); same in `PHASE2_STATE.md:124`, `BATCH9_TRANSITION.md:361,363`, `PHASE2_HANDOFF.md:85`.
* **Vast data-privacy boundary** (`:206-211`): no production customer statements to a third-party remote environment without a separate remote-data / privacy / retention ruling; SSH tunnelling does not change classification; "localhost does not mean local execution" (`:201-205`).
* **Architecture plan** (`PHASE2_ARCHITECTURE_PLAN.md`): geometry before Unlimited (`:36-38, 457`); ladder `Native → Tesseract → PaddleOCR → Unlimited` (`:122`); canonical `words[]` "empty for Unlimited until it grows boxes" and Unlimited sidecar = raw completion, `<|det|>` tags, `finish_reason`, token counts (`:208, 214`); **§7** "Generative, no word-level boxes/confidence, GPU, 4096-token truncation … Extra bar: printed count AND running balance AND printed total AND summary agreement, all on raw text; a single reconciling sum is not enough" (`:255-278`); Phase 2.3 = Unlimited as generative fallback on remaining Class A only (`:497-507`); `EXTRACTOR_ORDER = ("local_tesseract","paddle","visual")` with a future `unlimited_ocr` member "still a slot" (`ocr/escalation.py:198-203`).

### 1.6 The local model cache (ground truth for "what engine is this")

`~/.cache/huggingface/hub/models--baidu--Unlimited-OCR` (read-only inspection; no weights loaded):

* `refs/main` = `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead` (HF commit of 2026-07-03). Snapshot: `config.json`, `configuration_deepseek_v2.py`, `conversation.py`, `deepencoder.py`, `modeling_deepseekv2.py`, `modeling_unlimitedocr.py` (+ `.orig_backup`), `model-00001-of-000001.safetensors` (6,672,547,120 B), tokenizer files. `README.md` and `processor_config.json` are absent locally (`from_pretrained` fetches only what it needs, so absence proves nothing about the hub).
* `config.json`: `architectures: ["UnlimitedOCRForCausalLM"]`, `model_type: "unlimited-ocr"`; `language_config.architectures: ["DeepseekOCRForCausalLM"]` — DeepSeek-V2-style decoder, 12 layers, hidden 1280, **64 routed + 2 shared experts, 6 active per token**, vocab 129,280, `max_position_embeddings 32768`, **`sliding_window 128`**; `vision_config.model_name: "deeplip_b_l"` = `sam_vit_b` (12 layers, 768 wide) + `clip-l-14-224` (24 layers, 1024 wide); `candidate_resolutions [[1024,1024]]`; projector linear 2048→1280.
* Remote code: `modeling_unlimitedocr.py:44-59` parses both `<|ref|>…<|/ref|><|det|>…<|/det|>` and the simplified `<|det|>label [..]<|/det|>`; `draw_bounding_boxes` (`:79-92`) maps boxes with **`x / 999 * width`** (vendor convention 0–999; the paper says "0–1000"; the repo divides by 1000 — a ≤0.1 % scale discrepancy to settle); `infer()` (`:787`) defaults `base_size=1024, image_size=640, crop_mode=True, max_length=32768, no_repeat_ngram_size, ngram_window`; `infer_multi()` (`:1139-1150`) accepts a list of page images at one `<image>` token with prompt `"<image>Multi page parsing."`. The commented prompt variants (`"<image>\n<|grounding|>Given the layout of the image."`, `"<image>\nFree OCR."`, `"<image>\nParse the figure."`, `:797-802`) are DeepSeek-OCR's.
* **Local patch**: `modeling_unlimitedocr.py` differs from `.orig_backup` only by CRLF conversion and `.cuda()` → `.to(self.device)` / `torch.autocast(self.device.type, …)` at lines 582, 1003-1005, 1018, 1028-1030, 1042, 1049, 1059, 1070 — a portability edit for the ROCm box, no behavioral change. (The same edit is what upstream issue #81 reports for CPU inference.)
* **Drift check**: `sha256(model-00001-of-000001.safetensors)` locally = `2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6` = the LFS oid of the same file on HF `main` (`07dea832…`, 2026-07-29). `modeling_unlimitedocr.py` is 53,431 B on HF main = the local `.orig_backup`. The HF commit log shows the initial commit `d549bb9` (06-22) followed by eleven "Update README.md" commits. **Conclusion: the pinned local snapshot and today's `main` carry identical weights and code; the only drift since July is documentation.**

---

## 2. SOURCES

Fetched OK (2026-09-03):

1. https://huggingface.co/api/models/baidu/Unlimited-OCR — model JSON (sha `07dea832…`, lastModified 2026-07-29, MIT, `image-text-to-text`, custom_code, 3,181,811 downloads, 4,176 likes).
2. https://huggingface.co/baidu/Unlimited-OCR — model card summary.
3. https://huggingface.co/api/models/baidu/Unlimited-OCR/tree/main — file sizes + LFS sha256.
4. https://huggingface.co/baidu/Unlimited-OCR/commits/main — 12 commits, all post-initial are README edits.
5. https://huggingface.co/baidu/Unlimited-OCR/raw/main/README.md — sections, `infer`/`infer_multi` signatures, modes.
6. https://github.com/baidu/Unlimited-OCR and https://raw.githubusercontent.com/baidu/Unlimited-OCR/main/README.md — timeline, prompts, deployment, acknowledgements (DeepSeek-OCR, DeepSeek-OCR-2, PaddleOCR).
7. https://github.com/baidu/Unlimited-OCR/issues?q=is%3Aissue — issue list (51 issues, 27 PRs, 25.1k stars, 2.6k forks).
8. https://recipes.vllm.ai/baidu/Unlimited-OCR — serving recipe.
9. https://docs.vllm.ai/en/latest/api/vllm/model_executor/models/unlimited_ocr/ — module API.
10. https://hub.docker.com/v2/repositories/vllm/vllm-openai/tags/?name=unlimited-ocr — tag digests/dates.
11. https://arxiv.org/abs/2606.23050 and https://arxiv.org/html/2606.23050 — "Unlimited OCR Works" (Baidu Inc., v1 2026-06-22).
12. https://arxiv.org/html/2510.18234 — DeepSeek-OCR paper (inherited encoder, data, coordinate bins).
13. https://github.com/deepseek-ai/DeepSeek-OCR — inherited prompt list and modes.
14. https://www.marktechpost.com/2026/06/24/… — architecture/benchmark summary (2026-06-24).
15. https://cloud.baidu.com/doc/OCR/s/fmr1p39gb — Baidu AI Cloud "文档解析（Unlimited-OCR）" API doc.
16. https://qianfan.cloud.baidu.com/qianfandev/topic/688663 — Baidu Qianfan enterprise-service announcement (2026-07-03).
17. https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html — PP-OCRv5 architecture.
18. https://huggingface.co/datasets/llamaindex/ParseBench — benchmark description (top-10 rows only visible).
19. https://dev.to/arshtechpro/unlimited-ocr-parsing-a-40-page-pdf-in-one-pass-without-your-gpu-melting-4mc4 — practitioner notes.
20. https://codersera.com/blog/run-baidu-unlimited-ocr-locally-2026/ — practitioner notes (2026-07-05).
21. https://www.unlimitedocr.com/ — unrelated browser-first Tesseract.js tool (disambiguation).
22. https://unlimitedocr.net/ — promotional page for the Baidu model (self-described "Baidu Open Source Research"; official status **unverified**).

Fetched but empty/partial (FAILED for content): https://modelscope.cn/models/PaddlePaddle/Unlimited-OCR (empty body); https://huggingface.co/spaces/baidu/Unlimited-OCR (app shell only). Not fetched directly (seen only in search snippets): the Jerry Liu / LlamaIndex X post on ParseBench; the Medium/explainx/deepwiki/alphamatch write-ups.

Web searches run: `"baidu/Unlimited-OCR" huggingface`; `"Unlimited-OCR" vLLM "NGramPerReqLogitsProcessor"`; `"Unlimited OCR" API pricing OCR service`; `Baidu "Unlimited-OCR" model release … 2026`; `Unlimited-OCR Baidu Cloud Qianfan API pricing per page data retention`; `github baidu Unlimited-OCR issues handwriting low resolution …`; `"Unlimited-OCR" … "PaddleOCR-VL" comparison bounding box …`; `百度智能云 文档解析 Unlimited-OCR 数据 保留 隐私 服务协议`; `ParseBench llamaindex Unlimited-OCR PaddleOCR-VL-1.6 …`.

---

## 3. Documented current capabilities (as of 2026-09-03)

### 3.1 What it is

* **Publisher**: Baidu Inc. (HF org `baidu`; ModelScope mirror under the `PaddlePaddle` org per the GitHub README). Paper: "Unlimited OCR Works" (arXiv 2606.23050, v1 2026-06-22). License **MIT** (weights + code).
* **Architecture**: DeepSeek-OCR's **DeepEncoder unchanged and frozen** (SAM-ViT-B ~80M + CLIP-L ~300M, 16× token compression: 1024×1024 → 256 vision tokens), decoder = DeepSeek-3B-MoE (~3B total, ~500–570M active) in which **every attention layer is replaced by Reference Sliding Window Attention (R-SWA)**: each generated token attends to all prefill (image) tokens plus the preceding n=128 output tokens, so the KV cache is constant (`Lm + n`). Continue-trained from the DeepSeek-OCR checkpoint for 4,000 steps on ~2M document samples on 8×16 A800. (Paper; MarkTechPost; `config.json` `sliding_window 128`.)
* **Training data (paper)**: ~2M OCR samples, single:multi-page 9:1; **single-page PDF data annotated using PaddleOCR**; coordinates "normalized to 0–1000"; ~200k synthetic multi-page samples (2–50 pages) built by concatenating single pages; packed to 32K tokens. No breakdown by document type or language; nothing about bank statements, faxes, or handwriting.
* **Timeline**: 06-22 release; 06-23 arXiv + ModelScope; 06-24 HF Space; 06-28 vLLM support (Docker `vllm/vllm-openai:unlimited-ocr`, all tags pushed 2026-06-28); 07-03 Baidu Cloud API public beta; 07-21 ms-swift fine-tuning support. No v2. Repo HEAD commits are README-only since 07-03.

### 3.2 Inputs

* **Self-hosted (transformers / vLLM / SGLang)**: images (JPG/PNG); PDFs only after rasterization (vendor helper uses PyMuPDF at **300 DPI**). Two documented modes: **gundam** `base_size=1024, image_size=640, crop_mode=True` (dynamic tiling; vLLM allows up to **32 crops** vs DeepSeek-OCR's 6; a 2560×5120 image selects the 32-tile maximum) and **base** `1024×1024, crop_mode=False`. **Multi-page in one pass** (`infer_multi`, prompt `<image>Multi page parsing.`, `window_size=1024`) is **base mode only** — the paper concedes small text is missed there. Max generation `max_length=32768`. No documented max image count per prompt, no documented DPI guidance beyond 300, no documented file-size cap for self-hosting (bounded by VRAM/context).
* **Hosted (Baidu AI Cloud)**: PDF/JPG/JPEG/PNG/BMP/TIF/TIFF/OFD and DOC/DOCX/TXT/WPS/PPT/PPTX; images ≤10 MB, longest edge ≤8192 px; PDF ≤100 MB and ≤500 pages; asynchronous submit/poll; QPS 2 (submit) / 5 (query); OAuth 2.0 access_token from API Key + Secret Key.

### 3.3 Outputs

* **Text**: markdown with HTML tables, formulas; page separator `<page>` in multi-page mode.
* **Geometry**: `<|det|>label [x0,y0,x1,y1]<|/det|>` region tags (and DeepSeek-style `<|ref|>…<|/ref|><|det|>[[…]]<|/det|>`), **per layout region** (title/text/table/figure/header/footer/list/page_number/caption/image…), normalized coordinates (vendor code divides by 999; paper says 0–1000). **No word-level or line-level boxes, no cell-level table coordinates, no confidence scores** in any vendor document, code path, or community write-up ("you can survive without bounding-box outputs" is the community's phrasing; LlamaIndex's reviewer says it is "decent at bounding boxes" at the block level). Reading order = generation order; the paper reports a reading-order edit distance of 0.045 on OmniDocBench v1.5. Vendor post-processing (`remove_det`) strips tags for clean text.
* **Completion signals**: `finish_reason`, `usage` (vLLM), which the repo already reads.
* **Hosted API**: `markdown_url` + `parse_result_url` (JSON with layout, tables, reading order, title hierarchy, rotation angle per the product page), downloadable for **30 days**.

### 3.4 Engine identity and drift risk

* **Engine family**: proprietary-weights-but-open **end-to-end VLM** (autoregressive text decoder conditioned on compressed vision tokens). It is **not** a wrapper over Tesseract, Google Vision, Azure, Textract, or a general LLM API. It is a **DeepSeek-OCR fork** (same encoder, same tokenizer family, same `<|det|>`/`<|ref|>` grammar, same repetition-suppression recipe).
* **Drift**: weights unchanged since 2026-06-22 (sha verified). Docker tag `unlimited-ocr` is a mutable tag but has not been re-pushed since 06-28 (digest `542961a4…`; arch/CUDA-specific tags exist). vLLM module `vllm.model_executor.models.unlimited_ocr` requires **vLLM ≥ 0.25.0**; serving behavior can drift with vLLM releases (crop count, processor) even when weights do not. `trust_remote_code` remains a supply-chain exposure — pinning `revision=ee63731b…` (or the weight sha) is the mitigation the plan already names.
* **Behavioral sensitivity**: no chat template; empty output if the `<image>` prefix, text-first ordering, `skip_special_tokens=False`, or `vllm_xargs` are missing (vendor recipe; `docs/runpod-setup.md:106-130`). Repetition loops on dense repeated patterns are a documented failure class mitigated only by the n-gram processor (issues #82, #84).

### 3.5 Latency, throughput, rate limits, pricing

* Vendor: 5,580 tokens/s at 512-way concurrency on A800 (server throughput, not single-page latency); constant per-step latency across decoding. No per-page latency published. Community: 6.7 GB weights in bf16, "12 GB+ NVIDIA card comfortable"; CPU works with the `.cuda()` edit; MPS crashes (#81).
* Repo: ~23 s/page on RX 7800 XT via the eager-attention shim (`README.md:50`). Unknown on RTX 5090/vLLM.
* Rate limits: none self-hosted; hosted 2 QPS submit / 5 QPS query.
* Pricing: weights $0 (MIT). Self-hosting cost = GPU time (RunPod/Vast hourly; the Vast rate ruling is still open). Hosted: "接口限时免费" — limited-time free, 200 pages (individual) / 1,000 pages (enterprise) free quota; **post-trial per-page price not published**. There is no "unlimited" subscription; "Unlimited" refers to the constant-KV-cache design.

### 3.6 Data handling, region, terms

* Self-hosted: nothing leaves the host; MIT terms impose no usage restriction; no telemetry found in the remote code (it imports `requests` for URL image loading, `modeling_unlimitedocr.py:6`; not audited line by line for outbound calls).
* Hosted Baidu AI Cloud: results are stored as downloadable URLs for 30 days (explicit output retention); **input retention, training-use, processing region, and cross-border terms are not stated** on the API page or the announcement; Baidu AI Cloud is a PRC cloud, so mainland processing is the default assumption, **not verified**. Product page mentions private/on-prem deployment for data privacy. Whether the hosted service uses the same open weights or an enterprise variant is not stated.

### 3.7 Benchmarks (vendor + third-party)

* OmniDocBench v1.5 overall **93.23** (text edit 0.038, table TEDS 90.93, formula CDM 92.61, reading-order edit 0.045) vs DeepSeek-OCR 87.01; v1.6 **93.92**. PaddleOCR-VL-1.5/1.6 report 94.5 / 96.3 on the same suites (PaddleOCR docs).
* ParseBench (LlamaIndex, ~2,000 enterprise pages incl. financial filings): Unlimited-OCR mean **46.17** (text content 86.81, text formatting 0.97) vs PaddleOCR-VL-1.6 mean 67.43 (text content 82.71, formatting 54.64). Reviewer: strong on table parsing and reading order, weak on semantic formatting/charts, "decent at bounding boxes".
* No published numbers for faxed/low-resolution scans, skewed pages, handwriting, dark backgrounds, or bank statements. Community reports: low-res/severely rotated pages degrade; Hebrew hallucination (#90); Arabic weak (#89/#95).

---

## 4. Unknowns (not resolved by public documentation)

1. Behavior of the repo's prompt `"<image>Free OCR."` on Unlimited-OCR. The vendor documents only `document parsing.` and `Multi page parsing.`; `Free OCR.` is DeepSeek-OCR's "no layout" prompt, yet the repo observed det tags with it. Whether it changes box emission, table fidelity, or repetition is unmeasured.
2. Exact coordinate convention (999 vs 1000) — vendor code vs paper disagree; the repo uses 1000.
3. Per-page latency on the approved Vast RTX 5090 under vLLM ≥ 0.25 with 32-crop gundam mode; VRAM headroom for 4096–8192 output tokens.
4. Whether `processor_config.json` (present on HF main, absent locally) affects vLLM's multimodal processor at the pinned revision.
5. Hosted API: input retention, training use, region, post-trial price, SLA, whether weights equal the open model.
6. Robustness on the failure classes that motivate a second opinion (faxes, low-res, skew, handwriting, dark backgrounds) — no vendor numbers; only the DeepSeek-OCR lineage's general document training is known.
7. Whether the label vocabulary is closed and stable across pages (the repo's regexes accept any `\w+` label).
8. Whether `Locate <|ref|>…<|/ref|>` (DeepSeek-inherited) works on Unlimited-OCR and could yield a box for a specific string (would be one extra call per query; unverified).

---

## 5. Independence assessment vs PaddleOCR (PP-OCRv5 as used in Phase 2.1)

| Axis | PaddleOCR PP-OCRv5 (Phase 2.1) | Unlimited-OCR | Independent? |
|---|---|---|---|
| Engine family | Two-stage pipeline: text **detection** model + text-line **recognition** model (CTC), plus doc/text-line orientation classifiers; not a VLM | End-to-end **VLM**: DeepEncoder → MoE decoder with R-SWA; autoregressive generation | **Yes** — different architecture, different failure physics (Paddle fails by missing/mis-detecting boxes and mis-recognizing lines; Unlimited fails by hallucinating, looping, truncating, or mis-ordering) |
| Output | Words + boxes + per-line scores (`text_word`, `text_word_boxes`, `rec_scores`) | Markdown + region boxes; no scores | Complementary, not comparable one-to-one |
| Vendor | Baidu (PaddlePaddle) | Baidu (ModelScope mirror under PaddlePaddle; README credits PaddleOCR) | **No** — same organization |
| Training-label lineage | Its own labeled corpora | Paper: single-page training data **annotated using PaddleOCR**; encoder inherited from DeepSeek-OCR | **Partially correlated** — Unlimited learned from Paddle-produced labels, so systematic Paddle recognition errors on some glyph/layout classes can be inherited; agreement between the two is weaker evidence than agreement between unrelated lineages |
| Language prior | None beyond recognition dictionary | Strong LM prior (helps unusual fonts/dark backgrounds; also the hallucination source — "reconciles but disagrees with Paddle words" is the plan's own suspect class, `PHASE2_ARCHITECTURE_PLAN.md:503`) | Different error model |

Verdict: **materially independent at the engine/architecture level, correlated at the vendor and annotation-lineage level.** It is a legitimate second opinion for Class A pages where Paddle returns no usable words (faxes, low-res, skew, dark backgrounds), provided disagreement is treated as review evidence and Unlimited-only fields stay behind the §7 extra-oracle bar. It should not be represented as an independent oracle in the statistical sense.

---

## 6. Privacy / data-handling assessment

* **Loopback local server** (`local_ocr_server.py` on the operator's GPU): no third party; allowed by default under OQ3 (`ocr/endpoint_policy.py:171-172`). Residual risks: `trust_remote_code` execution (pinned snapshot, sha verified; local `.to(self.device)` patch is benign), and rasterized page PNGs in temp dirs (`local_ocr_server.py:97-104, 128-129` deletes them). **No separate customer-data ruling needed** for real statements on loopback, by the standing doctrine — but the rung remains unauthorized until Gustavo enables it (`PHASE2_RULINGS.md:169-172, 220`).
* **RunPod** (`remote`, requires `OCR_REMOTE_OPT_IN`): a third-party GPU host sees page pixels; RunPod's retention/terms were never recorded in the repo; the same classification the rulings apply to Vast.ai applies here ("SSH tunnelling does not change… third-party remote environment", `:206-211`). **A separate remote-data / privacy / retention ruling would be required** before any real customer statement is sent — exactly the ruling already pending for the 13 Paddle documents. Running Unlimited-OCR via vLLM on the already-approved Vast RTX 5090 would be the least-new-surface way to measure it, under the same `remote_paid` opt-in and the same customer-data boundary.
* **Baidu AI Cloud hosted API**: outputs retained ≥30 days as URLs; input retention, training use, and region unspecified; PRC cloud; OAuth keys. For US customer bank statements this is a materially different privacy posture from anything the rulings have contemplated. **Not recommended**; would need its own ruling and probably fails the bar.
* **Telemetry hygiene**: `baidu/Unlimited-OCR` is a `FREE_MODELS` member (`telemetry/prices.py:37`) — correct for loopback, **misleading for RunPod/Vast** where GPU-hours are paid; if a remote run is ever measured, provenance should carry provider/execution class as Paddle's does (`PHASE2_RULINGS.md:212-214`).

---

## 7. Feeding the canonical word+box evidence model — geometry adapter feasibility

**Canonical target** (`evidence/canonical.py`): `PageFrame` (pixel or PDF-point space, dpi, rotation), `WordBox {word_id, page_index, text, x0,y0,x1,y1, confidence?, line_ref}` (`:279-296`), `LineBox` derived by y-overlap (`group_lines`, `:353-395`), `PageEvidence{frame, words, lines, raw, notes}` (`:397-460`), `ExtractionEvidence{extractor_id, model_token, pages, runtime, schema_version=1}` (`:473-523`). The Paddle adapter (`ocr/paddle_adapter.py:70-160`) fills words from `text_word`/`text_word_boxes` and refuses whole pages on any malformed box — never inventing.

**What Unlimited-OCR can supply**: region label + region box (normalized) + the raw text span inside that region, per page, in generation order; plus `finish_reason` / token counts. **Cannot supply**: word boxes, line boxes, per-cell table coordinates, confidence.

**Feasible adapters (ranked)**

1. **Region-evidence sidecar (recommended first step).** Parse `<|det|>label [x0,y0,x1,y1]<|/det|>content` (the repo's `_REGION_SPLIT_RE`, `ocr/render.py:163-166`, already does this) into a new immutable `RegionBox {region_id, page_index, label, x0,y0,x1,y1 (pixels via PageFrame from the normalized box × raster size), raw_span (offsets into raw_text)}` stored in `PageEvidence.raw`/`notes` or a new schema field (bump `EVIDENCE_SCHEMA_VERSION` → 2 and `EXTRACTION_SCHEMA_VERSION` → 3). `words=()` stays empty, exactly as the plan already specifies (`PHASE2_ARCHITECTURE_PLAN.md:208`). This is lossless, invents nothing, and gives the structurer a coarse layout (which region is the transaction table, header, summary) that the validator's `evidence_refs[]` can cite as `raw_span` (`:224-233`). Coordinate convention must be fixed by measurement (999 vs 1000) and pinned by test.
2. **Alignment onto Paddle words (dual-engine pages only).** When both engines ran on the same raster (same `PageFrame`), align Unlimited's region text to Paddle's `WordBox` sequence by containment (Paddle word center inside the region box) and token-level diff. Product: per-Paddle-word agreement flags and, where Unlimited reads a token Paddle missed, a **boxless "unbacked token"** that can only reach the validator under the §7 four-identity bar. This is the "engine disagreement as review evidence, store both, do not merge" rule (`PHASE2_ARCHITECTURE_PLAN.md:176`).
3. **Not feasible / forbidden**: synthesizing `WordBox`es by splitting region text and distributing coordinates across the region width — that is invented geometry and contradicts the adapter discipline (`ocr/paddle_adapter.py:33-40`, MINOR-10) and "no word-box parent → not admissible" (`PHASE2_ARCHITECTURE_PLAN.md:233`).
4. **Speculative**: per-string `Locate <|ref|>…<|/ref|>` calls could box specific tokens (amount, date) on demand; unverified on Unlimited-OCR, one call per query, would need its own measurement before any design relies on it.

**Practical prerequisites before enabling as a second-opinion extractor**

* Keep the Phase 2.3 gating as ruled: Class A only, after Paddle produced no usable evidence; never Class B/C; never automatic remote; the rung stays disabled until Gustavo rules.
* Serving: pin `revision=ee63731b…` (weights sha `2bc48a7a…`), prefer vLLM ≥ 0.25 on an NVIDIA card (the ROCm shim at ~23 s/page is the slow path), pin the Docker digest rather than the mutable tag, keep `--no-enable-prefix-caching --mm-processor-cache-gb 0` and the n-gram logits processor.
* Measure, per page, both prompts (`Free OCR.` vs vendor `document parsing.`) on synthetic/non-sensitive fixtures for: det-tag emission rate, table fidelity, truncation at 4096 (consider 8192 as the recipe uses), repetition, and the 999/1000 box scale — before any real statement is sent.
* Do not use the Baidu Cloud API for customer data. Do not use RunPod/Vast for customer data without the separate ruling. Loopback is the only path that needs no new ruling.

---

## 8. Candidate interpretations considered and rejected

* **unlimitedocr.com** — an independent browser-first Tesseract.js tool; no API today; paid pilots $99–$249; states explicitly it is separate from Baidu's model. Not the repo's vendor (the repo's client speaks vLLM `extra_body`, uses `baidu/Unlimited-OCR`, and caches the Baidu weights).
* **Puter "free unlimited OCR API"** — unrelated marketing phrase.
* **unlimitedocr.net** — promotional page for the Baidu model; ownership unverified; no API.
* **Baidu Qianfan-OCR / Qianfan-OCR-Fast** — separate hosted OCR models on OpenRouter/Puter ($0.68/M input, $2.81/M output tokens quoted by resellers); not what the repo integrates.
* **In-repo false positives**: `analysis/atb.py:114` (`account_name="Unlimited Business Banking"`, an ATB product label), `tests/test_declines_e_variants.py:487` ("Huntington Unlimited Checking"), `W3_TRACKA_LOG.md` ("CHASE FREEDOM UNLIMITED"), and cached analysis artifacts under `.claude/recovery/webapp_data_train10_cold/` (bank product names inside customer data — not opened). None refer to the OCR model.
