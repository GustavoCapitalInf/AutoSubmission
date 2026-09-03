<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Layout-reconstruction research memo: bank-agnostic transaction tables from word boxes

Date: 2026-09-03. Prepared for the Phase 2.2 design discussion (deterministic-first reconstruction of transaction tables from a `DocumentGeometry` of words + page coordinates, feeding the ledger-identity / running-balance validator). Research was done fresh today via web search and primary-source fetches; every claim below is tagged with its source, and anything that is my own design proposal rather than a published result is marked **[proposal]**.

Context assumed: PaddleOCR 3.7.0 with PP-OCRv5 det+rec on a remote RTX 5090 (opt-in, loopback tunnel), native-PDF words with coordinates for born-digital statements, one `DocumentGeometry` type feeding the router, a downstream deterministic validator, and a Phase-3 boundary that excludes multimodal models.

---

## SOURCES

Fetch status is as of 2026-09-03. "OK" = the page body was fetched and read. "search-only" = the item was located and summarised via search-result snippets but the primary page was not fetched. "FAILED" = fetch attempted and refused/404/unparseable.

### PaddleOCR 3.x (primary docs, model cards, papers)
- S1 OK https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html
- S2 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/layout_detection.html
- S3 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/table_structure_recognition.html
- S4 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/table_cells_detection.html
- S5 OK https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/table_recognition_v2.html
- S6 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/table_classification.html
- S7 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/doc_img_orientation_classification.html
- S8 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_image_unwarping.html
- S9 OK https://www.paddleocr.ai/latest/en/version3.x/module_usage/textline_orientation_classification.html
- S10 OK http://www.paddleocr.ai/main/en/version3.x/module_usage/layout_analysis.html (reached via 301 from paddlepaddle.github.io)
- S11 OK https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html
- S12 OK https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-ChatOCRv4.html
- S13 OK https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html
- S14 OK https://github.com/PaddlePaddle/PaddleOCR/blob/main/README.md (release timeline, licence)
- S15 OK https://paddlepaddle.github.io/PaddleX/latest/en/module_usage/tutorials/ocr_modules/table_structure_recognition.html
- S16 OK https://paddlepaddle.github.io/PaddleX/latest/en/module_usage/tutorials/ocr_modules/table_cells_detection.html
- S17 OK https://arxiv.org/html/2510.14528v1 (PaddleOCR-VL technical report, 0.9B)
- S18 OK https://arxiv.org/html/2601.21957 (PaddleOCR-VL-1.5 report)
- S19 OK https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 (model card)
- S20 OK https://huggingface.co/PaddlePaddle/PP-DocLayoutV2 (model card)
- S21 OK https://huggingface.co/PaddlePaddle/HPD-Parsing (model card)

### Table structure recognition / word-box heuristics
- S22 OK https://arxiv.org/html/2412.12827v1 and https://arxiv.org/abs/2412.12827 (TabSniper, bank statements)
- S23 OK https://arxiv.org/html/2405.05260 (Financial Table Extraction in Image Documents) — the PDF variant FAILED to parse
- S24 OK https://ar5iv.labs.arxiv.org/html/2005.00589 and https://arxiv.org/abs/2005.00589 (GTE / FinTabNet)
- S25 OK https://ar5iv.labs.arxiv.org/html/2110.00061 and https://arxiv.org/abs/2110.00061 (PubTables-1M / TATR)
- S26 OK https://ar5iv.labs.arxiv.org/html/2203.01017 (TableFormer) — the PDF variant FAILED to parse
- S27 OK https://ar5iv.labs.arxiv.org/html/2408.09869 (Docling technical report) — the abs page gave only the abstract, the PDF FAILED to parse
- S28 OK https://docling-project.github.io/docling/usage/advanced_options/
- S29 OK https://arxiv.org/abs/2303.00716 (Aligning benchmark datasets for TSR; FinTabNet.c)
- S30 OK https://github.com/microsoft/table-transformer, https://raw.githubusercontent.com/microsoft/table-transformer/main/README.md, https://raw.githubusercontent.com/microsoft/table-transformer/main/src/postprocess.py
- S31 OK https://arxiv.org/abs/1908.04729 (GraphTSR / SciTSR)
- S32 OK https://arxiv.org/abs/2105.06224 (LGPMA)
- S33 OK https://arxiv.org/abs/2504.10258 (XY-Cut++)
- S34 OK https://raw.githubusercontent.com/jsvine/pdfplumber/stable/README.md and https://raw.githubusercontent.com/jsvine/pdfplumber/stable/pdfplumber/table.py
- S35 OK https://raw.githubusercontent.com/camelot-dev/camelot/master/camelot/parsers/stream.py — the readthedocs pages (how-it-works, api) FAILED (404 on master and latest); the `main`-branch raw path FAILED (404)
- S36 OK https://raw.githubusercontent.com/tabulapdf/tabula-java/master/src/main/java/technology/tabula/extractors/BasicExtractionAlgorithm.java
- S37 OK https://www.infoq.com/articles/redesign-pdf-table-extraction/ (practitioner article, banking PDFs)
- S38 OK https://github.com/sebastienrousseau/bankstatementparser (README)
- S39 OK https://arxiv.org/html/2510.16066 (AI-BAAM, Malaysian bank statements)
- S40 OK https://arxiv.org/pdf/2512.09666 (Neurosymbolic IE from transactional documents) — fetched but the PDF summary was thin; treat as weakly read
- S41 search-only TabbyPDF (Shigarov et al., ICIST 2018; Springer chapter 10.1007/978-3-319-99972-2_20)
- S42 search-only SPLERGE (Tensmeyer et al., ICDAR 2019)
- S43 search-only Ha, Haralick, Phillips 1995, "Recursive X-Y cut using bounding boxes of connected components" (ICDAR 1995)
- S44 FAILED https://developer.ibm.com/exchanges/data/all/fintabnet/ (IBM DAX deprecated; page has no dataset facts)

### Column roles / lexicons / continuation lines
- S45 OK https://raw.githubusercontent.com/bank2ynab/bank2ynab/master/bank2ynab.conf (multilingual CSV header mappings; the `develop` path FAILED 404)
- S46 OK https://localextract.app/blog/bank-statement-pdf-format-explained (vendor blog; practice, not literature)
- S47 OK https://www.docuclipper.com/blog/bank-statement-verification/ (vendor blog; practice, not literature)

### Document classification
- S48 OK https://arxiv.org/html/2606.02162 (Multimodal approaches for VRD type classification, comparative)
- S49 search-only DiT / LayoutLMv3 RVL-CDIP numbers (92.69 / 95.64) as quoted in search snippets of arXiv 2210.07448 and related
- S50 search-only check/MICR signals (PyImageSearch, Doubango MICR page, IDRBT cheque dataset, Kaggle cheque-detection)

### OCR quality without ground truth / multi-engine
- S51 OK https://arxiv.org/html/2607.16203 (DocOCR-Eval)
- S52 OK https://journal.dhbenelux.org/journal/issues/004/article-3-Cuper.html (QuPipe, OCR quality without GT)
- S53 search-only Cuper, van Dongen, Koster, "Unraveling Confidence" (ICDAR 2023)
- S54 FAILED https://hal.science/hal-01191701v1 (Ben Salah, Moreux, Ragot, Paquet, ICDAR 2015, "OCR performance prediction using cross-OCR alignment") — bot wall; method known from search snippets and the Neudecker survey citation
- S55 search-only ROVER (Fiscus 1997), Lund & Ringger 2009, LV-ROVER (Stuner 2020), LV-ROVER-MLT (arXiv 2607.00250)
- S56 FAILED https://link.springer.com/chapter/10.1007/978-3-031-70442-0_13 (Confidence-Aware Document OCR Error Detection) — auth redirect

---

## A. PaddleOCR 3.x beyond det+rec

### A.0 Release state (matters for what "3.7.0" contains)
Per the repository README (S14): 3.2.0 on 2025-08-21 (PP-OCRv5 English +11%), 3.3.0 on 2025-10-16 (PaddleOCR-VL, 109 languages), 3.4.0 on 2026-01-29 (PaddleOCR-VL-1.5, 94.5% OmniDocBench), 3.5.0 on 2026-04-21 (Office-to-Markdown, PaddleOCR.js), 3.6.0 on 2026-05-28 (PaddleOCR-VL-1.6, 96.3% OmniDocBench v1.6), **3.7.0 on 2026-06-11 (PP-OCRv6)**, and HPD-Parsing on 2026-07-22. Repository licence: Apache 2.0.

Implication: the installed 3.7.0 very likely ships **PP-OCRv6** (S13): a three-tier family (tiny 1.5M, small, medium 34.5M params); `PP-OCRv6_medium` reports 86.2% detection Hmean vs 81.6% for `PP-OCRv5_server` and 83.2% vs 78.1% recognition accuracy, 0.29 s/image vs 0.32 s on A100, and "50 languages with a single unified model". The README claims "significant improvements in table, ancient document, and rare character recognition". This is a det+rec upgrade inside the existing architecture, not a new component, so it is the cheapest accuracy lever available; it needs a controlled A/B on the corpus slice (numbers above are Baidu's own benchmark, not statements).

### A.1 PP-StructureV3 (S1)
Seven components: layout detection, general OCR subline, optional document preprocessing, optional table recognition subline, seal, formula, chart. Output: JSON, Markdown, docx; tables as HTML with cell boxes; benchmark environment is Tesla T4 + Xeon Gold 6271C on paddlepaddle-gpu 3.0.0. **GPU memory is not published** on any of the module pages I fetched (S1–S6, S15, S16); only latency and model file size are.

### A.2 Layout detection (S2, S10, S20)
| Model | Categories | mAP@0.5 | T4 GPU ms (normal / high-perf) | Size |
|---|---|---|---|---|
| PP-DocLayout_plus-L | 20 (incl. table, header, footer, page number, seal, chart, image) | 83.2 | 53.03 / 17.23 | 126 MB |
| PP-DocLayout-L | 23 | 90.4 | 33.59 | 123.8 MB |
| PP-DocLayout-M | 23 | 75.2 | 13.03 / 4.72 | 22.6 MB |
| PP-DocLayout-S | 23 | 70.9 | 11.54 / 3.86 | 4.8 MB |
| PP-DocBlockLayout | 1 ("Block") | 95.9 | 34.60 / 28.54 | 123.9 MB |
| PicoDet_layout_1x_table | table only | 97.5 | 9.57 | 7.4 MB |
| RT-DETR-H_layout_3cls | table / image / stamp | 95.8 | 114.80 | 470 MB |
| PP-DocLayoutV2 (layout_analysis module) | 25, plus reading order | 81.4 | ~31 ms inference (paddle_static) | 203.8 MB |

Output per box: `cls_id`, `label`, `score`, `coordinate [xmin, ymin, xmax, ymax]` (S2). The evaluation set for PP-DocLayout_plus-L is "self-built Chinese/English papers, PPT, magazines, contracts, books, exams, ancient books (1,300 images)" (S2) — **no statements, no financial tables** in the stated mix. PP-DocLayoutV2 (S17, S20) is "an RT-DETR-based detection model" followed by "a pointer network, which is responsible for ordering these layout elements"; it emits boxes + labels + reading order; the layout_analysis page (S10) says "Currently, this module only supports the PP-DocLayoutV2 model" while its examples reference PP-DocLayoutV3 (which the VL-1.5 paper, S18, describes as instance segmentation + reading order). Licence Apache-2.0 (S20).

Failure modes (from the training-domain statement, not from a statement-specific evaluation): a bank statement's borderless transaction body may be labelled "text" rather than "table"; the wired-vs-wireless prior of the training corpora is unknown. Treat any layout label as advisory.

### A.3 Table classification, cell detection, structure recognition (S3–S6, S15, S16)
- `PP-LCNet_x1_0_table_cls`: two classes `wired_table` / `wireless_table`; Top-1 94.2%; 2.62 / 0.60 ms GPU; 6.6 MB (S6).
- `RT-DETR-L_wired_table_cell_det`: mAP 82.7, 33.47 / 27.02 ms GPU, 124 MB; `RT-DETR-L_wireless_table_cell_det`: **metrics not published** on either the PaddleOCR or PaddleX page (S4, S16). Output: `cell` boxes with score. No training recipe in PaddleOCR (S4).
- Structure recognition (S3, S15): SLANet 59.52%, SLANet_plus 63.69%, SLANeXt_wired 69.65%, SLANeXt_wireless **not published**; accuracy is on a "High-difficulty Chinese table recognition dataset"; SLANet/SLANet_plus 6.9 MB, ~23 ms GPU; SLANeXt 351 MB, 85.9 ms GPU, 501 ms CPU. Output fields: `structure` (HTML tokens), `bbox` (cell coordinates), `structure_score`. **Docs state: "table cell predictions for the SLANeXt series models are invalid"** — so the newer structure models give HTML only; cell geometry then comes from the RT-DETR cell detector.
- Table Recognition v2 pipeline (S5): layout → table classification → wired/wireless branch → cell detection → structure recognition → OCR; outputs `cell_box_list`, `pred_html`, `rec_texts`, `rec_scores`. Options: `use_e2e_wired_table_rec_model`, `use_e2e_wireless_table_rec_model`, `use_ocr_results_with_table_cells` ("split and re-recognize OCR detection results based on the cell prediction results"), `use_table_orientation_classify`. Row/column indices are derivable only by parsing `pred_html`; there is no per-cell confidence beyond `structure_score`.

No published number for borderless financial tables from Paddle; the only borderless-relevant statement is the SLANet_plus note that it "greatly improved the recognition ability for wireless and complex tables" (S3). Latency figures are T4; on the 5090 they will be lower, but VRAM is unpublished.

### A.4 Preprocessing (S7, S8, S9)
- `PP-LCNet_x1_0_doc_ori`: 0/90/180/270; Top-1 99.06 on a 1,000-image self-built set; 2.62 / 0.59 ms GPU; 7 MB.
- `UVDoc` unwarping: CER 0.179 on its test set; 19.05 ms GPU, 869.8 ms CPU; 30.3 MB; "does not support fine-tuning".
- `PP-LCNet_x0_25_textline_ori`: 0/180 per text line; 98.85 Top-1; 2.16 / 0.41 ms GPU; 0.96 MB (x1_0 variant 99.42, 6.5 MB).

### A.5 PaddleOCR-VL, HPD-Parsing, PP-ChatOCRv4 (S11, S17, S18, S19, S21, S12)
- PaddleOCR-VL-0.9B (S17): "a NaViT-style dynamic resolution visual encoder and the ERNIE-4.5-0.3B language model"; two stages: PP-DocLayoutV2 finds and orders elements, then "each sub-image is independently fed into the VLM". **The 0.9B VLM does not output boxes itself**; boxes come from PP-DocLayoutV2; the VLM emits text / OTSL tables / LaTeX / Markdown. OmniDocBench v1.5 table TEDS 89.76, TEDS-S 93.52; A100 with vLLM at batch 512: 1.2241 pages/s, 43.7 GB average VRAM (that is the batch-512 server footprint, not the minimum). Apache 2.0. Training mix mentions "Financial reports" as a table category but gives no financial breakdown.
- PaddleOCR-VL-1.5 (S18): adds seal recognition and **text spotting** — the VLM now emits location tokens (`Text⊕<LOC_xTL><LOC_yTL>…`) in a 4-point quadrilateral form; OmniDocBench v1.5 overall 94.50, table TEDS 92.76 / TEDS-S 95.79; layout model PP-DocLayoutV3; A100 FastDeploy 1.4335 pages/s. Limitation stated: extreme physical distortion.
- PaddleOCR-VL-1.6 (S19): 2026-05-28, ~1.0B params BF16, Apache 2.0, 96.33% OmniDocBench v1.6, "fully compatible with PaddleOCR-VL-1.5"; PaddlePaddle 3.2.1+, vLLM Docker.
- HPD-Parsing (S21): 1B, InternVL3.5-1B backbone, Hierarchical Parallel Decoding; 94.91% OmniDocBench v1.6; 4,752 tokens/s on A800 80 GB at batch 512; Apache 2.0; 2026-07.
- PP-ChatOCRv4 (S12): chains preprocessing + layout + table + OCR with vector retrieval and an LLM; "you first need to prepare the API key for the large language model" (Baidu Qianfan ERNIE; optional PP-DocBee2 MLLM); outputs key-value JSON; no determinism statement.

**Boundary ruling (my reading of the architecture, not a Paddle statement):** PaddleOCR-VL (all versions) and HPD-Parsing are vision-language models with an autoregressive LLM decoder generating the table as tokens. They are "multimodal models" under any reasonable Phase-3 boundary. Their table output is generated text (OTSL/HTML) rather than measured geometry, is not deterministic under sampling/batching, and cannot be traced word-by-word to boxes (1.5+ adds coordinate tokens for text spotting, which are still generated, not measured). PP-ChatOCRv4 additionally requires a remote LLM API. All three are out of scope for a deterministic reconstruction; they could only ever be a shadow/diagnostic lane.

---

## B. Table structure from word boxes (borderless, financial)

### B.1 Classical deterministic algorithms (what the mature tools actually do)
- **Recursive X-Y cut** (S43): top-down segmentation using projection profiles over bounding boxes of connected components; "once bounding boxes of connected components are obtained, the recursive X-Y cut is completed within an order of a second". It is fully deterministic; it is the ancestor of every projection-profile row/column splitter. XY-Cut++ (S33) adds "pre-mask processing, multi-granularity segmentation, and cross-modal matching" for reading order (98.8 BLEU on DocBench-100) — reading order, not table cells.
- **pdfplumber `text` strategy** (S34): `words_to_edges_v` clusters words on `x0`, `x1`, and centre with a 1-point tolerance, keeps clusters with ≥ `min_words_vertical` (default 3) words, and turns each surviving alignment into a vertical edge (plus one at the rightmost boundary); `words_to_edges_h` clusters by `top` with ≥ `min_words_horizontal` (default 1). Then: find lines, merge near-overlapping (`snap_tolerance` 3, `join_tolerance` 3), intersections (`intersection_tolerance` 3), most granular rectangles = cells, group contiguous cells into tables. Words: `x_tolerance` 3, `y_tolerance` 3. Everything is deterministic and explainable; it is also brittle on ragged columns because a single mis-aligned word can add a spurious edge.
- **Camelot Stream** (S35): `row_tol` 2 ("combine text vertically, to generate rows"), `column_tol` 0 ("combine text horizontally, to generate columns"), `edge_tol` 50 ("extending textedges vertically"); Nurminen's text-edge table detection "looks for spaces between text": generate left/middle/right textedges, select relevant ones, guess table bbox from textline positions; `_group_rows`, `_merge_columns`, `_join_rows`, `_add_columns` (columns added where text appears between existing boundaries); `split_text` optionally splits a textline spanning two columns.
- **Tabula basic/stream** (S36): first line's chunks seed vertical "regions"; each later chunk merges into a region it `horizontallyOverlaps`, else opens a new region; column positions = sorted right edges of regions; each chunk goes to the first column with `tc.getLeft() <= column`. No tolerances; the right-edge rule is what makes right-aligned numerics behave.
- **TabbyPDF** (S41): heuristic detection + structure recovery from PDF text-printing instructions, distances, fonts and rulings; ICDAR-2013 F 93.64% (structure) / 83.18% (detection + extraction).

Common failure modes stated by their authors or evident from the algorithms: spurious columns from wrapped description text that happens to align; merged adjacent tables; sparse wide tables (S23: "incomplete column detection in wide, sparse tables with large inter-column spacing"); a value drifting across an inferred boundary (S37: "a small shift can move values across inferred boundaries"); one physical line ≠ one transaction (S37).

### B.2 Learned TSR from images and from boxes
- **FinTabNet / GTE** (S24): "annual reports of the S&P 500 companies"; >70K pages (61,801 / 7,191 / 7,085) with table bbox + structure; >110K tables with cell boxes (91,596 / 10,635 / 10,656). Key domain fact: "Financial tables often have very different styles ... with fewer graphical lines and larger gaps within each table and more colour variations." GTE structure TEDS on FinTabNet: 87.14 zero-shot, 91.02 after fine-tuning.
- **PubTables-1M / TATR** (S25, S30): 947,642 TSR tables (52.7% complex); canonicalisation (blank spanning cells split, column-header cells merged, "projected row header" = a row with exactly one non-blank cell in the first column — the exact shape of a section-title row in a statement); DETR gets GriTS_Top 0.9949 / GriTS_Con 0.9938 / GriTS_Loc 0.9922 on simple tables. TATR's `postprocess.py` (S30) is the best public reference for **turning row/column boxes + word boxes into cells**: `refine_rows/refine_columns` with `nms_by_containment(overlap_threshold=0.5)`, `remove_objects_without_content`, `align_rows/align_columns` to the table bbox, headers via `overlap_height / row_height >= 0.5`, `table_structure_to_cells` = row × column intersection, `slot_into_containers` assigns a token to the cell with `intersect_area / token_area` above a threshold (0.5 generally, 0.001 for final text). MIT licence. FinTabNet.c (S29): canonicalised FinTabNet; on ICDAR-2013, TATR trained on FinTabNet went 42% → 65% after alignment, combined data 69% → 81%, showing that annotation convention dominates the reported numbers.
- **TableFormer / Docling** (S26, S27, S28): predicts HTML tokens + a cell-box decoder; TEDS FinTabNet 96.8 (simple 97.5 / complex 96.0), PubTabNet 96.75, TableBank 89.6; cell mAP 82.1 → 86.8 with post-processing. Stated failure: "large tables (e.g. tables that occupy half of the page or more) yield poor predictions" due to image downscaling — a transaction table is exactly that. Docling matches "TableFormer structure predictions ... back to the PDF cells in post-processing" by IoU pairing with a threshold and grid-geometry fallback for orphan cells (`do_cell_matching=True` default; `TableFormerMode.ACCURATE` default); throughput 0.6–1.3 pages/s on CPU; MIT.
- **GraphTSR / SciTSR** (S31), **LGPMA** (S32), **SPLERGE** (S42): graph relation prediction over cell boxes (SciTSR, 15,000 scientific tables), aligned-mask cell boxes solving "empty cells locating and division", and learned row/column projection split + merge respectively. TSRFormer was not fetched; SEM (Split-Embed-Merge, S42 search hit) is the same family. All are trained on scientific/financial-report tables, none on statements; all are stochastic at training time but deterministic at inference given fixed weights and no batching effects.

### B.3 Bank-statement-specific work
- **TabSniper** (S22; Dec 2024; American Express authors): the only paper found that targets statements directly. Dataset BankTabNet: 310 statements, ~11,607 page images, 5,165 TSR tables (53,178 row, 18,448 column, 4,569 column-header, 912 spanning-row boxes); **public release not stated**. Pipeline: DETR table detection + categorisation into Credit / Debit / Check / Txn_bal / Txn_amt_bal / Txn_chk_bal / Other (with three Naive-Bayes text classifiers over 840 caption + 860 header words); DETR TSR predicting table / row / column / column header / spanning row with CIoU loss; long tables (>20 rows) split then merged; "top aligned OCR words in left most Date column" define row separators; header synonyms ("Date", "Description", "Amount", "Check Number", "Credit", "Debit", "Balance") mapped to columns; amount-column sign resolved by "minus signs/brackets"; final check "OpenBal − Σ Debit + Σ Credit − EndBal" = 0. Numbers: TSR AP 83.1 / AP50 94.8 on BankTabNet vs Table-Transformer 70.4 AP; 1.91 min per 20-page statement on an M1 Max CPU. Failure: tilted scans clip words.
- **AI-BAAM** (S39): DB-ResNet50 + CRNN-VGG16 OCR with per-bank template matching over six Malaysian banks (~110 PDFs); 98.08% table NED; failure modes "multi-line address formats", "bank-specific layout variations", "merged description cells". It is per-bank, so it is evidence of what per-bank costs, not a model to follow.
- **Financial Table Extraction in Image Documents** (S23): Tesseract word boxes; columns via union-find where trees merge on width-IoU; rows from Tesseract line ids; a small LSTM predicts column breaks from token-distance features; 3,038 tables / 510K segments; the learned model reached only 10.50% perfect alignments (MCC 0.951) — i.e. cell-level errors remain common even with learning.
- **Practitioner sources** (S37, S38, S46): InfoQ's banking pipeline is `clusterByY → headerDetector → columnInferer → rowAssembler`, with validation on "date parsing success rate, numeric parsing success rate for amount and balance columns, row consistency, and sanity checks", and a stream-vs-lattice chooser. `bankstatementparser` (S38) is deterministic for CAMT/OFX/MT940/CSV but for PDFs uses `pypdf extract_text` and a vision-LLM fallback, with a "Golden Rule" `opening + credits − debits == closing` and statuses VERIFIED / DISCREPANCY / UNVERIFIABLE / FAILED; no accuracy numbers. LocalExtract (S46) states the continuation rule most parsers use: "If the next line has a date in the date column position, it is a new transaction. If it has text only in the description column position, it is a continuation."

### B.4 Heuristic vs learned on unseen layouts — what the evidence supports
- Learned image TSR models are strong on their own benchmarks (TableFormer 96.8 TEDS on FinTabNet) but (a) degrade on page-sized tables (S26), (b) depend heavily on annotation convention (S29), (c) are trained on report tables, not statement bodies, and (d) are opaque with respect to why a column boundary was placed. TabSniper shows that even a statement-trained DETR needs OCR-word row separators and rule-based post-processing to reach usable output (S22).
- Word-box heuristics are deterministic, reproducible, and fully traceable to word ids; their known failures are all geometric and therefore detectable (a token straddling a boundary, a column with too few members, a row with two dates). That is what a validator wants: crisp failure rather than plausible-looking guesses.
- Nothing in the literature supports an optimizer that selects "whichever reconstruction reconciles"; TabSniper and bankstatementparser use the ledger identity strictly as a post-hoc check, which matches the constraint given.

---

## C. Column-role inference and continuation lines

### C.1 Header lexicon (published / real-world strings)
From bank2ynab's bank CSV mappings (S45) plus TabSniper's synonym set (S22):
- Date: Date, Datum, Buchungsdatum, Transaktionsdatum, Abschlussdatum, Fecha.
- Description: Description, Payee, Memo, Libellé, Concepto, Beschreibung, Omschrijving, Naam, Mededelingen.
- Debit/outflow: Debit, Outflow, Withdrawals, Débit, Retrait, Cargo, Belastung, Soll, Af.
- Credit/inflow: Credit, Inflow, Deposits, Crédit, Dépôt, Abono, Gutschrift, Haben, Bij.
- Balance: Balance, Running Balance, Solde, Saldo.
- Amount: Amount, Montant, Importe, Betrag.
- Check number: Check Number / Check No. / Chèque / No. de chèque **[the French/Spanish check forms are my additions, not from S45]**.
Canadian French statement variants such as "Retraits", "Dépôts", "Solde", "Débit", "Crédit" appear in S45 and match Desjardins/BMO usage found in search snippets; treat the exact Quebec forms as needing corpus confirmation.

### C.2 Numeric-behaviour tests (published heuristics)
- TabSniper (S22): for Txn_bal tables "checked for non-empty columns"; Txn_amt_bal "checked for minus signs/brackets"; Txn_check_bal "checked for check numbers"; global check `OpenBal − ΣDebit + ΣCredit − EndBal = 0`.
- bankstatementparser (S38): Golden Rule per currency group.
- InfoQ (S37): numeric parse rate per column, date parse rate, row consistency.
- No paper was found that formalises "monotone balance consistency" as a column-role signal; the balance-difference test below is a **[proposal]** grounded in the ledger identity the validator already uses.

### C.3 Continuation lines (published heuristics)
- Presence/absence rule (S46): date in the date-column x-range ⇒ new transaction; text only in the description x-range ⇒ continuation; the stated failure is "text that could be a date but is actually part of a description" — resolved by x-position, not by regex alone.
- TabSniper (S22): row separators from the top-aligned words in the leftmost Date column; multi-line rows handled by "rule-based row-separation bounding boxes".
- InfoQ (S37): "treat every physical line as a transaction row, you split one transaction into multiple rows"; also page-break splits (S46: "A transaction whose description wraps to multiple lines may be split across a page break").
- Datasets: none public with continuation-line labels for statements (BankTabNet's release status unknown, S22).

---

## D. Document classification and missing-page detection

### D.1 Datasets
- RVL-CDIP: 400K greyscale pages, 16 classes (letter, form, email, handwritten, advertisement, scientific report/publication, specification, file folder, news, budget, invoice, presentation, questionnaire, resume, memo) — no bank statement, cheque, or credit-card statement class (S48). DocLayNet's six document-level classes include "financial reports" (annual reports, not statements). TabSniper's BankTabNet has page-region classes (Credit, Debit, Check, transaction tables, summaries, service fees, check images, captions, headers) but is not stated as public (S22). Commercial classifiers (Veryfi, UiPath) list "bank statement", "bank check", "credit card" as classes but publish no benchmark. Synthetic vendor datasets exist (Shaip). Conclusion: **there is no public benchmark for statement-vs-check-vs-invoice; any classifier will be trained on our own corpus.**

### D.2 Approaches and numbers
- S48 (2026 comparative): on RVL-CDIP, Donut 0.95 at 307 ms, LayoutLMv3 (public checkpoint) 0.90 at 554 ms (official 0.9544), Qwen3-VL-32B 0.75, Qwen3-32B text-only 0.55; conclusion "No single architecture can be recommended universally". DiT-Large 92.69, LayoutLMv3-Large 95.64 (S49). None of these is needed for a 6–8-class financial-document split with strong lexical cues; text-only TF-IDF/logistic baselines are standard but no statement-specific number exists.
- Deterministic signals with published grounding: page count and "Page X of Y" (S46, S47); repeated column headers per page (S46); opening/closing balance keywords (S22, S38); MICR E-13B line at the bottom of cheques with routing/account/cheque-number groups, typical cheque aspect ratio ~2.3:1 (S50); PP-DocLayout labels "table", "header", "footer", "page number", "seal", "image", "chart" (S2) as cheap region-type features if a layout model is run.

### D.3 Missing-page detection (practice, no paper found)
- "Page X of Y" sequence completeness and monotonicity (S46).
- Balance continuity: "Match the ending balance from one statement to beginning balance on the next statement" and running-balance walk-through; both are what vendors use to flag "potentially manipulated or missing pages" (S47).
- Transaction-date gaps and running-balance discontinuity between the last row of page p and the first row of page p+1 (my formulation of S47's check at page granularity) **[proposal]**.

---

## E. Multi-engine OCR disagreement and quality without ground truth

- **Cross-OCR alignment** (S54, search-only): Ben Salah, Moreux, Ragot, Paquet (ICDAR 2015) estimate per-page word recognition rate without ground truth by aligning the primary OCR with a "reference OCR" ("an uncertain GT") and regressing (SVR) on alignment features. This is the direct precedent for using native-PDF words vs Paddle words (or Paddle vs a second engine) as a quality estimate.
- **Voting/ensembles** (S55): ROVER word-level voting (Fiscus 1997); Lund & Ringger 2009 aligned multiple full OCR systems (55.0% lattice error reduction, 35.8% realised WER reduction on poor typewritten documents); Lund et al. maximum-entropy selection with voting + dictionary features (24.6% relative WER improvement over the best of five engines); LV-ROVER lexicon-verified voting. These improve text; they do not by themselves detect layout failure.
- **Confidence as proxy** (S53): Cuper et al. (ICDAR 2023) on 2,000 Dutch newspapers with ABBYY: confidence-based proxy separates very good from very bad pages with 83% accuracy but "must be recalculated for individual OCR engine setups and producers".
- **QuPipe** (S52): quality without GT from dictionary lookup (token/type), garbage-word rules (>20 characters, repeated letters), language detection, character trigram perplexity, average word/sentence length; binarised per measure; "smart quantity" 0.831 precision / 0.418 recall. Explicitly did not use engine confidence.
- **DocOCR-Eval** (S51): ranks OCR tools without GT by measuring how much an MLLM has to correct the output (ANLS; NDCG 0.968–0.975 vs annotated rankings) — sound, but it is an MLLM in the loop and therefore outside the boundary.
- Nothing found that formalises "box density" or "alignment regularity" as OCR quality metrics; the table-specific ones below are **[proposal]**.

---

## RECOMMENDATION

### R.1 Architecture: deterministic geometry pipeline, with an evidence ledger, not a search

Inputs: `DocumentGeometry` = pages × words {text, x0, y0, x1, y1, source ∈ {native, ocr}, rec_score?, word_id}. Outputs: `TransactionTable`s with rows {date, description lines, debit, credit, amount, balance, check_no, provenance = word ids + column id + line ids}, plus `PageFurniture`, `BalanceBlocks`, `PageContinuity`, and a per-decision evidence record. Every stage is a pure function of its inputs with fixed, versioned thresholds; the ledger identity is computed once at the end by the validator, never used to choose among candidates.

Stage 0 — Normalise. Scale to page points; for OCR pages record skew estimated from the median angle of word-baseline segments (deterministic Hough/least squares) and rotate boxes back; native pages are already upright. Units: `h` = median word height per page, `cw` = median character width (box width / text length over alphanumeric words).

Stage 1 — Lines. Two words share a line if their vertical overlap ≥ 0.5·min(height) (the TATR containment convention, S30) — equivalent to pdfplumber's `y_tolerance=3` / Camelot `row_tol=2` for 10-pt text (S34, S35). Union-find, then sort words by x. Failure: superscripts/footnote markers split lines — bounded by the overlap rule.

Stage 2 — Page furniture and continuity. A line is furniture if its digit-masked text and its y (±0.5 h, page-normalised) recur on ≥2 pages (repeated headers/footers, account masks, "Statement period"). Regex for `Page X of Y` in ≥3 languages → `PageContinuity{observed pages, declared Y, gaps}`. This replaces layout-model "header/footer/page number" labels with a rule whose failures are enumerable (a two-page statement where page 2 is only a footer; handled by a keyword fallback).

Stage 3 — Table region proposal (Nurminen text-edge method, S35, with pdfplumber's alignment clustering, S34). Compute vertical alignment edges from x0, x1 and centre clusters with tolerance 0.5·cw and ≥3 members (`min_words_vertical`, S34); extend an edge through consecutive lines while gaps ≤ `edge_tol` (Camelot default 50 pt, S35; make it 4·h). A table region = maximal vertical run of lines that touch ≥2 distinct edges and contain ≥1 amount token. Split regions at (a) a line matching the header lexicon (new header ⇒ new table), (b) a "projected row header" line — one non-blank text cell spanning ≥2 column extents with no amount (PubTables-1M canonical definition, S25) — which becomes a section title (multi-account / "Deposits" / "Withdrawals" subsections), (c) a vertical gap > 2.5·h.

Stage 4 — Column model. Within a region, cluster numeric tokens by **right edge x1** (Tabula's right-edge rule, S36) and text tokens by left edge x0, tolerance 0.5·cw, union-find merging on x-overlap (S23). Amount tokens are those parsed by a locale-aware grammar: `1,234.56`, `1 234,56`, `1.234,56`, `(123.45)`, `123.45-`, `-123.45`, `123.45 CR/DR`, `$`/`€`/`£` prefixes; the grammar is fixed per statement by majority vote of separators (deterministic). Column boundaries = midpoints between adjacent cluster extents; a token straddling a boundary is a **hard flag** (`straddle`), not a coin toss. A header row = the nearest line above the first amount-bearing line whose tokens hit the lexicon; multi-line headers = lines within 1.5·h above it; header tokens map to columns by x-overlap ≥ 0.5.

Stage 5 — Rows. Anchor line = has a date token inside the date column's x-range (or, headerless, in the leftmost text cluster) AND ≥1 amount in an amount/balance column. Continuation line = no date in the date range, no amount in amount ranges, all words inside the description range, within 2.0·h below the previous anchor or continuation, left edge ≥ description column x0 − 0.5·cw. Amount-but-no-date lines: attach to the previous anchor as a second amount line **only if** the previous anchor has no value in that column (some banks print debit and balance on separate lines); otherwise emit `orphan_amount` flag. Date-like tokens inside the description range are text (S46's failure case), by construction. Page-break continuation: continuation lines at the top of page p+1's first table body, before any anchor, attach to the last anchor of page p iff the column model of the two regions matches (same header text or same cluster x-positions within 1·cw). Section titles and balance blocks (lexicon: opening/beginning/closing/ending balance, solde d'ouverture/de clôture, saldo inicial/final) are emitted separately with their single amount.

Stage 6 — Column roles (evidence ledger, fixed precedence). Order of authority: (1) header lexicon hit on the column; (2) if no header, structural tests in fixed order: balance = rightmost amount column present on ≥ 80% of anchors whose row-to-row difference equals ± another column's value on the same row for ≥ 60% of consecutive anchor pairs; debit/credit = two amount columns that are mutually exclusive per row on ≥ 95% of anchors; amount = single amount column with sign/parenthesis/CR-DR markers (TabSniper's test, S22); check_no = integer tokens without separators, 3–8 digits, on ≤ 100% of rows. The tests never override a header; they **confirm** it or raise `role_conflict` (e.g., header says Credit but the balance-difference test says the column behaves as a debit). Headerless inference is recorded as `role_inferred_without_header`. The reconstruction emits exactly one table per region; the validator computes the ledger identity and running balance; disagreements come back as flags, not as a re-search.

Stage 7 — Output and determinism. Byte-stable JSON; thresholds live in one versioned constants module (`RECON_PARAMS_VERSION`); no randomness anywhere; native-PDF and OCR paths use the same stages (only Stage 0 differs). Provenance per cell = word ids, so the validator can point at the geometry that produced a failing row.

Why this and not a learned TSR: TableFormer/TATR reach 96–99 TEDS/GriTS on report tables (S25, S26) but are trained on other domains, degrade on page-sized tables (S26), and depend on annotation canon (S29); TabSniper, the only statement-trained model, still relies on OCR-word row separators and rule post-processing (S22) and its dataset is not public. The geometry rules above are the same primitives every mature deterministic tool uses (S34–S36), with the two additions that matter for statements: right-edge clustering for numerics and the anchor/continuation rule by x-position.

### R.2 Which Paddle 3.x components to add, and their cost

Worth adding now (all deterministic given fixed weights, all tiny):
1. `PP-LCNet_x1_0_doc_ori` (7 MB, ~2.6 ms on T4): fixes 90/180/270 pages before detection; no reason not to. (S7)
2. `PP-LCNet_x0_25_textline_ori` (0.96 MB, ~2 ms): catches upside-down lines on scans. (S9)
3. Evaluate **PP-OCRv6_medium** against PP-OCRv5_server on the corpus slice — same architecture, a claimed +4.6 det / +5.1 rec and specific table-text gains; this is the highest-leverage change if the claims hold on statements. (S13, S14)

Worth adding only for photographed pages, gated by a heuristic: `UVDoc` (30 MB, 19 ms GPU; cannot be fine-tuned); it would sit before detection when the page has non-rectangular text-line curvature. (S8)

Optional, advisory only (not on the reconstruction path): `PP-DocLayout_plus-L` or `PP-DocBlockLayout` (~125 MB, 17–53 ms per page on T4) to emit region labels (table / header / footer / seal / image / chart / page number) as extra features for document classification (Section D) and as a cross-check on Stage 3 regions. Its training mix has no statements (S2), so its labels must never gate a row. `PP-DocLayoutV2` adds reading order (S10) which the geometry pipeline does not need.

Not worth adding for this problem, because word boxes already exist and these would introduce a second, opaque structure decision:
- SLANet / SLANet_plus / SLANeXt: image-based structure with 59.5–69.7% accuracy on Baidu's hard Chinese set, wireless numbers unpublished, and "table cell predictions ... invalid" for SLANeXt (S3, S15). Their HTML output would compete with, not inform, the deterministic grid.
- RT-DETR table cell detection: wireless metrics unpublished (S4, S16); cell boxes on a borderless statement body are exactly what we can compute from word alignment. Could be run as a diagnostic on a sample to measure disagreement with Stage 4, nothing more.
- Table classification (wired/wireless): not needed; ruling lines, when present in native PDFs, can be read directly from the page's vector lines (pdfplumber `lines` strategy, S34) and used as an additional edge source.
- PaddleOCR-VL 0.9B / 1.5 / 1.6, HPD-Parsing: VLMs with an autoregressive LLM decoder; the 0.9B model outputs no boxes (S17), 1.5+ generates coordinate tokens (S18); 43.7 GB VRAM at batch 512 on A100 (S17) — feasible on a 5090 at small batch, but out of scope under the Phase-3 boundary and by the determinism requirement. Any use would be a shadow lane for disagreement metrics only.
- PP-ChatOCRv4: remote LLM API required (S12). Out of scope.

### R.3 Document classification and missing pages (Section D)

Tier 1 deterministic gates before any model: page count; `Page X of Y` completeness; presence of a period ("statement period", "du … au", "del … al"); balance lexicon hits (opening/closing); ≥1 Stage-3 table region with a date column and an amount column; MICR-line regex on the bottom 15% of the page and a page aspect ratio in [2.0, 2.6] ⇒ `check_image`; "VOID"/"NUL" lexicon ⇒ `voided_check`; screenshot signal = OCR page with pixel dimensions far from any paper size and no furniture repetition; credit-card statements = "minimum payment / payment due / credit limit" lexicon with a single amount column and no running balance; loan statements = "principal / interest / escrow" lexicon. Tier 2 = a TF-IDF + logistic classifier over OCR text plus the Tier-1 features, trained on our own labelled corpus, because no public benchmark covers these classes (S48). Tier 3 (optional) = PP-DocLayout region-type histogram as extra features. LayoutLM-family / Donut are not justified for an 8-class lexically-separable problem and would add a model with no public statement benchmark (S48).

Missing pages: `Page X of Y` gaps; running-balance discontinuity at page boundaries (last balance on page p vs first computed balance on page p+1); date order violations at page boundaries; opening-to-closing identity failure with a count of pages below the declared Y. Each is a flag with a page reference (S46, S47).

### R.4 Two-engine disagreement and quality without ground truth (Section E)

When both native-PDF words and Paddle words exist for a page (or two OCR runs): align boxes greedily by IoU ≥ 0.5 after Stage-0 normalisation (the same overlap convention as TATR, S30); report (a) matched-box ratio each way, (b) normalised character agreement on matched pairs, (c) **exact agreement of parsed amounts and dates** (the tokens the validator cares about), (d) unmatched-box density in the table region. This is the cross-OCR alignment idea (S54) restricted to the fields that matter, with no regression model. Single-engine quality without GT: rec-score distribution (mean, p10) **calibrated per engine and settings** (S53's warning), dictionary rate on description tokens (QuPipe, S52), garbage-token rule (>20 chars, repeated letters, S52), amount-grammar parse rate per numeric column (S37), and two table-geometry regularity measures **[proposal]**: coefficient of variation of line heights inside a table region and mean absolute residual of numeric tokens to their column's right edge in units of `cw`. Thresholds are set on the corpus slice and versioned; a page failing them is routed to the paid OCR lane or to review, never silently accepted.

### R.5 What is not supported by evidence (do not present as fact)
- No public number exists for any Paddle table model on borderless financial tables; the wireless variants' metrics are simply absent from the docs (S3, S4, S15, S16).
- No published bank-statement TSR dataset is confirmed public (BankTabNet release not stated, S22).
- No paper formalises balance-difference column-role inference or geometry-regularity OCR quality; those are proposals grounded in the ledger identity and in the tools' alignment primitives.
- PP-OCRv6's gains are Baidu benchmarks; only a corpus A/B can confirm them for statements.
