# Per-document findings (generated 2026-09-21T21:52:51+00:00)

Reference agreement against the ChatGPT references (unverified, hybrid route). 'miss' = reference money tokens absent from the candidate page (strict; 'sep' of them are the same digits with different separators), 'extra' = candidate money tokens absent from the reference, 'dates miss' likewise for date tokens, 'T' = pages that hit the output cap, 'CER' = normalized character error rate over the document. Reference uncertainty per document: [UNREADABLE] spans and completion status from the reference metadata.

## D01 — Amex (6 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 87 (87) | 87 | 12 | 0 | 0 | 0.221 | p4 (40), p5 (32), p3 (32) |
| dotsmocr | ocr | 0 (0) | 0 | 1 | 0 | 0 | 0.191 | - |
| glm-ocr | ocr | 25 (18) | 18 | 8 | 0 | 0 | 0.204 | p5 (16), p3 (16), p6 (6) |
| ovisocr2 | ocr | 4 (4) | 4 | 0 | 0 | 0 | 0.212 | p1 (8) |
| teleocr-official | ocr | 8 (0) | 0 | 5 | 0 | 0 | 0.114 | p5 (8) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.021 | - |
| internvl3.5-8b | vision | 10 (10) | 10 | 0 | 0 | 0 | 0.061 | p5 (16), p1 (4) |
| qwen3.5-9b | vision | 14 (14) | 14 | 0 | 0 | 0 | 0.028 | p4 (16), p2 (12) |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.059 | - |

## D02 — BofA (16 pages, native; reference complete_with_uncertainty, 37 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 11 (5) | 5 | 51 | 0 | 0 | 0.256 | p13 (6), p10 (4), p1 (4) |
| dotsmocr | ocr | 6 (0) | 0 | 20 | 0 | 0 | 0.192 | p13 (6) |
| glm-ocr | ocr | 23 (0) | 0 | 67 | 0 | 0 | 0.221 | p10 (15), p13 (6), p5 (1) |
| ovisocr2 | ocr | 7 (1) | 1 | 19 | 0 | 0 | 0.172 | p13 (6), p1 (2) |
| teleocr-official | ocr | 9 (3) | 3 | 19 | 0 | 0 | 0.182 | p13 (6), p10 (4), p1 (2) |
| bonsai2-27b-pq2 | vision | 1 (1) | 5 | 6 | 0 | 0 | 0.076 | p13 (6) |
| internvl3.5-8b | vision | 2 (2) | 6 | 19 | 0 | 0 | 0.158 | p13 (6), p11 (2) |
| qwen3.5-9b | vision | 10 (5) | 5 | 2 | 0 | 0 | 0.116 | p13 (15) |
| qwen3.8-27b-nvfp4 | vision | 2 (1) | 5 | 7 | 0 | 0 | 0.082 | p13 (7) |

## D03 — CIBC French (6 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 9 (4) | 8 | 12 | 0 | 0 | 0.365 | p1 (8), p2 (4), p3 (3) |
| dotsmocr | ocr | 3 (0) | 3 | 0 | 0 | 0 | 0.285 | p2 (4), p4 (2) |
| glm-ocr | ocr | 12 (0) | 1 | 0 | 0 | 0 | 0.247 | p5 (7), p4 (3), p1 (2) |
| ovisocr2 | ocr | 9 (6) | 9 | 0 | 0 | 0 | 0.290 | p2 (6), p4 (4), p1 (4) |
| teleocr-official | ocr | 1 (0) | 1 | 0 | 0 | 0 | 0.205 | p4 (2) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.036 | - |
| internvl3.5-8b | vision | 92 (0) | 0 | 10 | 3 | 0 | 0.419 | p4 (46), p2 (45), p1 (1) |
| qwen3.5-9b | vision | 1 (1) | 1 | 2 | 0 | 0 | 0.161 | p1 (2) |
| qwen3.8-27b-nvfp4 | vision | 1 (1) | 1 | 0 | 0 | 0 | 0.064 | p1 (2) |

## D04 — Chase (8 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 39 (7) | 7 | 66 | 0 | 0 | 0.180 | p3 (25), p6 (11), p7 (7) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.073 | - |
| glm-ocr | ocr | 10 (0) | 0 | 22 | 0 | 0 | 0.045 | p6 (6), p2 (4) |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.037 | - |
| teleocr-official | ocr | 42 (1) | 1 | 34 | 0 | 0 | 0.051 | p5 (32), p6 (9), p1 (2) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.023 | - |
| internvl3.5-8b | vision | 2 (1) | 2 | 5 | 0 | 0 | 0.059 | p7 (2), p1 (2) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.025 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.021 | - |

## D05 — Citizen (5 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 5 (1) | 1 | 0 | 0 | 0 | 0.285 | p1 (5), p3 (1) |
| dotsmocr | ocr | 1 (1) | 1 | 0 | 0 | 0 | 0.231 | p2 (2) |
| glm-ocr | ocr | 2 (1) | 1 | 0 | 0 | 0 | 0.218 | p1 (2), p2 (1) |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.216 | - |
| teleocr-official | ocr | 1 (1) | 1 | 0 | 0 | 0 | 0.206 | p2 (2) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.202 | - |
| internvl3.5-8b | vision | 3 (2) | 2 | 0 | 0 | 0 | 0.241 | p2 (2), p1 (2), p4 (1) |
| qwen3.5-9b | vision | 2 (2) | 2 | 0 | 0 | 0 | 0.208 | p2 (2), p1 (2) |
| qwen3.8-27b-nvfp4 | vision | 1 (1) | 1 | 0 | 0 | 0 | 0.203 | p2 (2) |

## D06 — Mission Valley (12 pages, native; reference complete_with_uncertainty, 123 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 255 (220) | 223 | 51 | 0 | 0 | 0.658 | p5 (124), p4 (124), p3 (96) |
| dotsmocr | ocr | 33 (9) | 15 | 31 | 2 | 0 | 0.980 | p11 (12), p9 (12), p7 (12) |
| glm-ocr | ocr | 25 (2) | 5 | 35 | 0 | 0 | 0.647 | p11 (6), p10 (6), p9 (6) |
| ovisocr2 | ocr | 38 (14) | 16 | 27 | 5 | 0 | 3.413 | p10 (13), p9 (13), p8 (12) |
| teleocr-official | ocr | 47 (0) | 0 | 52 | 0 | 0 | 0.649 | p10 (12), p8 (12), p9 (11) |
| bonsai2-27b-pq2 | vision | 14 (5) | 7 | 21 | 1 | 0 | 0.845 | p8 (12), p7 (7), p11 (2) |
| internvl3.5-8b | vision | 26 (2) | 5 | 21 | 1 | 0 | 1.102 | p11 (6), p10 (6), p9 (6) |
| qwen3.5-9b | vision | 28 (6) | 16 | 26 | 3 | 0 | 1.385 | p10 (12), p9 (12), p8 (10) |
| qwen3.8-27b-nvfp4 | vision | 8 (0) | 2 | 12 | 0 | 0 | 1.012 | p7 (8), p11 (2) |

## D07 — PNC (4 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 1 (0) | 0 | 4 | 0 | 0 | 0.243 | p1 (1) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.194 | - |
| glm-ocr | ocr | 1 (0) | 0 | 0 | 0 | 0 | 0.247 | p1 (1) |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.219 | - |
| teleocr-official | ocr | 6 (0) | 0 | 2 | 0 | 0 | 0.218 | p1 (6) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.201 | - |
| internvl3.5-8b | vision | 2 (0) | 8 | 5 | 0 | 0 | 0.258 | p4 (7), p1 (2), p3 (1) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.159 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.270 | - |

## D08 — RBC French (7 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 0 (0) | 0 | 2 | 0 | 0 | 0.128 | - |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.082 | - |
| glm-ocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.077 | - |
| ovisocr2 | ocr | 0 (0) | 0 | 1 | 0 | 0 | 0.081 | - |
| teleocr-official | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.076 | - |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.080 | - |
| internvl3.5-8b | vision | 8 (0) | 3 | 0 | 0 | 0 | 0.172 | p3 (5), p4 (4), p6 (1) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.080 | - |
| qwen3.8-27b-nvfp4 | vision | 1 (0) | 1 | 0 | 0 | 0 | 0.093 | p3 (2) |

## D09 — RBC (4 pages, native; reference complete_with_uncertainty, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 4 (0) | 0 | 6 | 0 | 0 | 0.217 | p1 (4) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.044 | - |
| glm-ocr | ocr | 1 (0) | 0 | 0 | 0 | 0 | 0.073 | p1 (1) |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.050 | - |
| teleocr-official | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.061 | - |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.054 | - |
| internvl3.5-8b | vision | 11 (1) | 1 | 0 | 0 | 0 | 0.108 | p3 (6), p2 (4), p1 (2) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.059 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.073 | - |

## D10 — Regions (8 pages, mixed; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 94 (8) | 8 | 46 | 0 | 0 | 0.124 | p4 (54), p2 (23), p1 (16) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 1 | 0 | 0.179 | - |
| glm-ocr | ocr | 0 (0) | 0 | 1 | 0 | 0 | 0.033 | - |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.031 | - |
| teleocr-official | ocr | 85 (0) | 0 | 46 | 0 | 0 | 0.065 | p4 (54), p2 (20), p6 (9) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 1 | 0 | 0.568 | - |
| internvl3.5-8b | vision | 1 (0) | 0 | 2 | 0 | 0 | 0.052 | p3 (1) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.040 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.035 | - |

## D11 — ScotiaBank (39 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 239 (54) | 54 | 47 | 0 | 0 | 0.275 | p30 (17), p27 (16), p12 (16) |
| dotsmocr | ocr | 0 (0) | 0 | 41 | 0 | 0 | 0.282 | - |
| glm-ocr | ocr | 0 (0) | 2 | 39 | 0 | 0 | 0.275 | p11 (2) |
| ovisocr2 | ocr | 0 (0) | 0 | 39 | 0 | 0 | 0.301 | - |
| teleocr-official | ocr | 1 (0) | 1 | 41 | 0 | 0 | 0.153 | p13 (2) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 39 | 0 | 0 | 0.234 | - |
| internvl3.5-8b | vision | 1 (0) | 2 | 27 | 1 | 0 | 0.179 | p33 (2), p28 (1) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.000 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 39 | 0 | 0 | 0.271 | - |

## D12 — TD Can (4 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 19 (8) | 8 | 3 | 0 | 0 | 0.184 | p2 (9), p3 (7), p1 (6) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.110 | - |
| glm-ocr | ocr | 5 (0) | 2 | 0 | 0 | 0 | 0.142 | p3 (4), p1 (2), p2 (1) |
| ovisocr2 | ocr | 7 (3) | 3 | 5 | 1 | 0 | 0.200 | p4 (4), p3 (2), p2 (2) |
| teleocr-official | ocr | 33 (0) | 0 | 15 | 0 | 0 | 0.606 | p4 (31), p2 (1), p1 (1) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.184 | - |
| internvl3.5-8b | vision | 39 (0) | 7 | 21 | 0 | 0 | 0.281 | p1 (39), p4 (5), p3 (1) |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.185 | - |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.171 | - |

## D13 — TD (10 pages, native; reference complete_with_uncertainty, 11 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 6 (3) | 11 | 17 | 0 | 0 | 0.370 | p10 (10), p1 (4), p4 (2) |
| dotsmocr | ocr | 7 (1) | 1 | 6 | 1 | 0 | 0.318 | p10 (6), p4 (2) |
| glm-ocr | ocr | 56 (3) | 3 | 24 | 0 | 0 | 0.265 | p6 (13), p5 (11), p4 (11) |
| ovisocr2 | ocr | 4 (1) | 4 | 2 | 0 | 0 | 0.242 | p10 (6), p4 (2) |
| teleocr-official | ocr | 10 (1) | 1 | 7 | 0 | 0 | 0.261 | p10 (6), p4 (2), p9 (1) |
| bonsai2-27b-pq2 | vision | 1 (1) | 1 | 2 | 0 | 0 | 0.164 | p10 (2) |
| internvl3.5-8b | vision | 4 (3) | 4 | 3 | 0 | 0 | 0.247 | p10 (6), p4 (2) |
| qwen3.5-9b | vision | 0 (0) | 0 | 1 | 0 | 0 | 0.186 | - |
| qwen3.8-27b-nvfp4 | vision | 2 (2) | 2 | 1 | 0 | 0 | 0.221 | p10 (2), p4 (2) |

## D14 — Truist (6 pages, mixed; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 18 (4) | 4 | 11 | 0 | 0 | 0.334 | p1 (21), p3 (1) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.382 | - |
| glm-ocr | ocr | 4 (0) | 0 | 11 | 0 | 0 | 0.228 | p1 (4) |
| ovisocr2 | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.271 | - |
| teleocr-official | ocr | 9 (0) | 0 | 14 | 0 | 0 | 0.239 | p1 (9) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.243 | - |
| internvl3.5-8b | vision | 3 (2) | 2 | 11 | 0 | 0 | 0.262 | p1 (4), p3 (1) |
| qwen3.5-9b | vision | 31 (0) | 0 | 55 | 1 | 0 | 0.792 | p1 (31) |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.236 | - |

## D15 — US Bank (4 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 7 (3) | 7 | 6 | 1 | 0 | 0.718 | p3 (10), p1 (4) |
| dotsmocr | ocr | 0 (0) | 0 | 0 | 0 | 0 | 0.095 | - |
| glm-ocr | ocr | 9 (6) | 6 | 3 | 0 | 0 | 0.066 | p1 (9), p3 (6) |
| ovisocr2 | ocr | 4 (4) | 4 | 0 | 0 | 0 | 0.084 | p3 (4), p1 (4) |
| teleocr-official | ocr | 3 (0) | 0 | 0 | 0 | 0 | 0.055 | p1 (3) |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.064 | - |
| internvl3.5-8b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.149 | - |
| qwen3.5-9b | vision | 0 (0) | 0 | 0 | 0 | 0 | 0.054 | - |
| qwen3.8-27b-nvfp4 | vision | 9 (9) | 9 | 0 | 0 | 0 | 0.081 | p1 (12), p3 (6) |

## D16 — WellsFargo (12 pages, native; reference complete, 0 [UNREADABLE] spans)

| candidate | track | miss (sep) | extra | dates miss | T | failed | CER | worst pages (miss+extra) |
|---|---|---|---|---|---|---|---|---|
| deepseek-ocr-2 | ocr | 15 (11) | 11 | 18 | 1 | 0 | 0.206 | p2 (12), p10 (10), p9 (2) |
| dotsmocr | ocr | 0 (0) | 0 | 5 | 1 | 0 | 0.824 | - |
| glm-ocr | ocr | 4 (0) | 0 | 21 | 0 | 0 | 0.181 | p10 (4) |
| ovisocr2 | ocr | 2 (2) | 2 | 5 | 0 | 0 | 0.179 | p2 (4) |
| teleocr-official | ocr | 0 (0) | 0 | 41 | 0 | 0 | 0.277 | - |
| bonsai2-27b-pq2 | vision | 0 (0) | 0 | 2 | 1 | 0 | 0.321 | - |
| internvl3.5-8b | vision | 5 (2) | 2 | 19 | 0 | 0 | 0.202 | p2 (3), p10 (2), p9 (1) |
| qwen3.5-9b | vision | 1 (0) | 0 | 6 | 1 | 0 | 0.814 | p10 (1) |
| qwen3.8-27b-nvfp4 | vision | 0 (0) | 0 | 5 | 0 | 0 | 0.168 | - |
