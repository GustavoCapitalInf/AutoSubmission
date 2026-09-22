# Extraction shootout — pilot leaderboards (generated 2026-09-21T21:52:38+00:00)

Scope: 16 statements / 151 pages, one frozen run per candidate, image-only input at 300 DPI. All numbers are AGREEMENT WITH THE CHATGPT REFERENCES (reference_unverified, hybrid input route: embedded PDF text + rendered pages + manual additions), NOT source-verified correctness. Token recall = reference money/date tokens also present in the candidate page (exact string, occurrence-counted); 'extra' = candidate tokens absent from the reference. CER/WER are the labelled whitespace/markup-normalized pass; page-level edit distance also charges reading order and line segmentation. Truncated pages hit the output cap (repetition loops are the usual cause) and stay in every denominator. No universal winner is claimed from this pilot.

## Track A — specialized OCR / document-extraction models
| candidate | role | pages ok | truncated | money recall (strict) | of which separator-only | money extra | date recall | CER norm | WER norm | exact pages (norm) | repeated lines | pages/min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dotsmocr | primary | 151/151 | 5 | 98.5% | 11 of 50 missing | 20 | 97.4% | 0.396 | 0.626 | 5 | 1796 | 5.258 |
| ovisocr2 | primary | 151/151 | 6 | 97.8% | 35 of 75 missing | 43 | 97.6% | 0.692 | 0.923 | 5 | 6340 | 14.134 |
| glm-ocr | alternate | 151/151 | 0 | 94.7% | 30 of 177 missing | 38 | 94.3% | 0.256 | 0.277 | 1 | 369 | 24.620 |
| teleocr-official | primary | 151/151 | 0 | 92.4% | 6 of 255 missing | 8 | 93.2% | 0.253 | 0.281 | 5 | 78 | 7.432 |
| deepseek-ocr-2 | primary | 151/151 | 2 | 75.9% | 415 of 809 missing | 434 | 91.4% | 0.329 | 0.371 | 0 | 1363 | 25.593 |


## Track B — general-purpose vision-language models
| candidate | role | pages ok | truncated | money recall (strict) | of which separator-only | money extra | date recall | CER norm | WER norm | exact pages (norm) | repeated lines | pages/min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bonsai2-27b-pq2 | primary | 151/151 | 3 | 99.5% | 7 of 16 missing | 13 | 98.3% | 0.295 | 0.445 | 8 | 13909 | 4.876 |
| qwen3.8-27b-nvfp4 | primary | 151/151 | 0 | 99.3% | 14 of 24 missing | 21 | 98.4% | 0.284 | 0.340 | 8 | 2737 | 3.118 |
| qwen3.5-9b | primary | 151/151 | 5 | 97.4% | 28 of 87 missing | 38 | 97.7% | 0.407 | 0.633 | 45 | 8488 | 3.489 |
| internvl3.5-8b | alternate | 151/151 | 5 | 93.8% | 25 of 209 missing | 54 | 96.5% | 0.325 | 0.314 | 10 | 2271 | 3.704 |


## Cross-track summary (same corpus, same references, same renderer)
| candidate | role | pages ok | truncated | money recall (strict) | of which separator-only | money extra | date recall | CER norm | WER norm | exact pages (norm) | repeated lines | pages/min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bonsai2-27b-pq2 | primary | 151/151 | 3 | 99.5% | 7 of 16 missing | 13 | 98.3% | 0.295 | 0.445 | 8 | 13909 | 4.876 |
| qwen3.8-27b-nvfp4 | primary | 151/151 | 0 | 99.3% | 14 of 24 missing | 21 | 98.4% | 0.284 | 0.340 | 8 | 2737 | 3.118 |
| dotsmocr | primary | 151/151 | 5 | 98.5% | 11 of 50 missing | 20 | 97.4% | 0.396 | 0.626 | 5 | 1796 | 5.258 |
| ovisocr2 | primary | 151/151 | 6 | 97.8% | 35 of 75 missing | 43 | 97.6% | 0.692 | 0.923 | 5 | 6340 | 14.134 |
| qwen3.5-9b | primary | 151/151 | 5 | 97.4% | 28 of 87 missing | 38 | 97.7% | 0.407 | 0.633 | 45 | 8488 | 3.489 |
| glm-ocr | alternate | 151/151 | 0 | 94.7% | 30 of 177 missing | 38 | 94.3% | 0.256 | 0.277 | 1 | 369 | 24.620 |
| internvl3.5-8b | alternate | 151/151 | 5 | 93.8% | 25 of 209 missing | 54 | 96.5% | 0.325 | 0.314 | 10 | 2271 | 3.704 |
| teleocr-official | primary | 151/151 | 0 | 92.4% | 6 of 255 missing | 8 | 93.2% | 0.253 | 0.281 | 5 | 78 | 7.432 |
| deepseek-ocr-2 | primary | 151/151 | 2 | 75.9% | 415 of 809 missing | 434 | 91.4% | 0.329 | 0.371 | 0 | 1363 | 25.593 |


## Per-document money-token recall (reference money tokens present in the candidate)

| doc | folder | pages | deepseek-ocr-2 | dotsmocr | glm-ocr | ovisocr2 | teleocr-official | bonsai2-27b-pq2 | internvl3.5-8b | qwen3.5-9b | qwen3.8-27b-nvfp4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D01 | Amex | 6 | 5% | 100% | 73% | 96% | 91% | 100% | 89% | 85% | 100% |
| D02 | BofA | 16 | 96% | 98% | 92% | 97% | 97% | 100% | 99% | 96% | 99% |
| D03 | CIBC French | 6 | 96% | 99% | 94% | 96% | 100% | 100% | 55% (T3) | 100% | 100% |
| D04 | Chase | 8 | 84% | 100% | 96% | 100% | 83% | 100% | 99% | 100% | 100% |
| D05 | Citizen | 5 | 96% | 99% | 99% | 100% | 99% | 100% | 98% | 99% | 99% |
| D06 | Mission Valley | 12 | 8% | 88% (T2) | 91% | 86% (T5) | 83% | 95% (T1) | 91% (T1) | 90% (T3) | 97% |
| D07 | PNC | 4 | 99% | 100% | 99% | 100% | 93% | 100% | 98% | 100% | 100% |
| D08 | RBC French | 7 | 100% | 100% | 100% | 100% | 100% | 100% | 96% | 100% | 99% |
| D09 | RBC | 4 | 96% | 100% | 99% | 100% | 100% | 100% | 90% | 100% | 100% |
| D10 | Regions | 8 | 66% | 100% (T1) | 100% | 100% | 69% | 100% (T1) | 100% | 100% | 100% |
| D11 | ScotiaBank | 39 | 62% | 100% | 100% | 100% | 100% | 100% | 100% (T1) | 100% | 100% |
| D12 | TD Can | 4 | 88% | 100% | 97% | 96% (T1) | 79% | 100% | 75% | 100% | 100% |
| D13 | TD | 10 | 97% | 96% (T1) | 70% | 98% | 95% | 99% | 98% | 100% | 99% |
| D14 | Truist | 6 | 87% | 100% | 97% | 100% | 94% | 100% | 98% | 78% (T1) | 100% |
| D15 | US Bank | 4 | 86% (T1) | 100% | 82% | 92% | 94% | 100% | 100% | 100% | 82% |
| D16 | WellsFargo | 12 | 95% (T1) | 100% (T1) | 99% | 99% | 100% | 100% (T1) | 98% | 100% (T1) | 100% |

T<n> = n truncated pages in that document for that candidate.
