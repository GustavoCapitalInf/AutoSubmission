<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Repository memo — the corpus, the denominator, and the 755 unresolved

Read-only investigation, 2026-09-03, at `train11` (code tree `4f7d798`, docs tip `21e3163`).
Run of record used for every "current" number: `discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136/` (the Phase 2.1 cold run; validated 2,625 / failed 672 / withheld 49 / review 21 / deferred 13 over 3,380 distinct shas). Batch-9 census numbers come from `docs/moneythumb-replacement/census_batch9/per_sha.csv` (784 rows = the unresolved set at the batch-8 run of record `cda8882d`), crossed by sha against the current run.

No document was opened. Documents are named by sha only.

---

## 1. The 3,380 denominator

**Definition (Ocean's decision, `docs/moneythumb-replacement/BATCH8_TRANSITION.md:166-171`, 2026-08-27):** the measurement population is the FROZEN archive of record, `3,615 PDFs = 109 pinned + 3,506 discovery`, denominator = **3,380 distinct content SHA-256s**.

**How it is computed** (`discovery/inventory.py`):
- Frozen constants `discovery/inventory.py:15-21`: `FROZEN_FILES 3768`, `FROZEN_PDFS 3615`, `FROZEN_BYTES 996_080_803`, `FROZEN_PINNED 109`, `FROZEN_DISCOVERY 3506`. Every run re-verifies the inventory before doing work (`provenance.md` records `baseline_deviations: []`).
- `enumerate_root` (`discovery/inventory.py:83-140`) walks `Bank Statements/` with `rglob("*")` and **keeps only files whose suffix is `.pdf` (case-insensitive)**; everything else is counted in `files` and otherwise ignored.
- The 109 pinned-corpus paths (the manifest of `docs/balance-metrics-audit-results.csv`) are partitioned out; the remaining 3,506 PDFs are the discovery set and become the rows of `rows.csv`.
- Identity is `content_sha256` of the file bytes (`ocr/inspect.py` profile; `discovery/runner.py:1061`). `DedupIndex.classify` (`discovery/runner.py:1069`) labels each row `unique` / `duplicate` / `pinned_corpus_duplicate`.
- Measured on the current run: 3,506 rows → `unique 3,300`, `duplicate 124`, `pinned_corpus_duplicate 82`; **3,380 distinct shas**; 71 shas carry more than one row. **80 of the 109 pinned corpus documents also occur as discovery files** (82 rows) and are therefore inside the 3,380; **29 pinned documents are not in the denominator at all.**

**What a unit is.** One unit = one PDF file's content sha. Not an account, not a statement period. A three-month package in one PDF is one unit. A multi-account file is one unit whose outcome is the FOLD over its accounts — the weakest account's class (`telemetry/record.py:596-706 classify_document`, `DOCUMENT_LADDER = ("failed","withheld","review","validated")`; no account → `failed`; an omission not in `RATIFIED_OMISSION_REASONS` → `failed/document_omission_unratified`). `rows.csv.account_count` records how many accounts the analysis published (0 on 685 of the 755; 1 on the other 70). `likely_account_count` is the intake inspector's advisory token count, consumed by nothing.

**What is NOT in the denominator — the non-PDF files.** The archive holds 3,768 files; 3,615 are `.pdf`. The other **153** (`find "Bank Statements" -type f`, by extension): `png 68 · jpg 36 · jpeg 20 · csv 10 · xlsx 7 · zip 2 · xls 1 · docx 1 · .pdf1/.pdf2/.pdf3/.pdf4/.pdf5 1 each · 3 extensionless files under Unidentified/ (three extensionless files)`. **Every check image, screenshot or photo saved as PNG/JPG is outside the 3,380 by construction.** The non-statements inside the 755 are all PDFs.

**The corpus gate is a different population.** `corpus_gate.py` audits only the pinned 109-path manifest (105 PASS / 3 WITHHELD / 1 REFUSED; `corpus_gate.py:96-106`), field-by-field against the two committed audit CSVs (110 lines each incl. header). It is the truth set, not the coverage denominator.

---

## 2. What "validated" means, and every non-validated outcome

**The per-account rung** — `telemetry/record.py:540-593 classify_outcome`, precedence top-down:
1. `deferred=` declared by the run → `("deferred", <DEFERRED_REASONS: deferred_scanned | deferred_visual_ocr | profile_only>)` (`record.py:65`).
2. payload `None` → `("failed", error_reason or "exception"/"no_analysis")`.
3. `metrics.average_daily_balance is None` → `("withheld", "withheld_adb")`.
4. integrity flag `parser_ambiguous` → `review/parser_ambiguous`; `parser_exception` → `review/parser_exception`; `integrity_check_exception` → `review/integrity_check_exception`; any other flag → `review/integrity_flags`.
5. `quality.corporate_use != "approved"` → `review/quality_needs_review`.
6. else `("validated", "approved")`.

So `validated` ⇔ an ADB was published ∧ zero integrity flags ∧ `corporate_use == "approved"`. Unpacking:
- ADB is published only when `m.adb_ok = trust_running_balances and adb.ok` with daily balances present (`analysis/metrics.py:440-458`), and `trust_running_balances = recon.ok and no "UNCAPTURED" rows` (`analysis/pipeline.py:1095`). `adb.ok` is the 14-check ADB validation suite (`analysis/adb.py::_validate`; names in `W3_2_TAXONOMY.md §3.1`: period dates valid, all transactions dated, within period, daily-balance dates valid, count equals calendar days, contiguous, covers opening/closing day, final balance matches statement closing, ledger reconciles to closing, opening matches statement, running balances support ledger, posting dates cover source).
- `corporate_use == "approved"` requires `recon.ok and aggregate_rows == 0` on a registration with `formal_statement=True` (`analysis/pipeline.py:350-410 assess_quality`); informal registrations (chase_export, found_lead) always land `manual_review_required` with the `not_a_formal_statement` flag.
- Integrity flags (10-enum, `W3_2_TAXONOMY.md §3.2`): `summary_math_inconsistent`, `ledger_sum_mismatch`, `running_balance_breaks`, `credit/debit_detail_coverage_mismatch`, `credit/debit_count_mismatch`, `conflicting_statement_summaries`, `missing_declared_statement_page`, `transaction_detail_not_corporate_reliable`, `not_a_formal_statement`, `parser_ambiguous`, `parser_exception`, `integrity_check_exception`, `repair_exception`.

**The failure-reason vocabulary** (`discovery/runner.py:1514-1551 _failure_reason`): `parser_ambiguous` (AmbiguousParserError), `q3_provenance_refused` (Q3 gate refused an OCR-fed omission), `parser_exception` (a parser raised — class name only), `parser_declined` (a registration claimed at detection and `parse` returned None), `no_parser_matched` (nothing claimed), `exception`. Preflight adds `invalid_pdf` / `encrypted`; the OCR ladder adds `ocr_failed`, `paddle_refused`; deferral adds the three `DEFERRED_REASONS`.

**The failure-stage vocabulary** (census column `failure_stage`): `preflight` · `ocr:no-text` · `dispatch:unclaimed` · `dispatch:declined` · `analysis:adb-withheld` · `analysis:integrity-review`.

**The failure CLASS** (`discovery/runner.py:335-372 classify_failure`, vocabulary in `ocr/escalation.py:66-91`): `validated` → `""` (checked FIRST); evidence unusable → `A` (extraction); usable but unclaimed → `B` (structure); claimed and not validated → `C` (financial). Only extractor reads are ever assessed (`GATE_ASSESSED_SOURCES = {local_tesseract, visual, paddle}`, `runner.py:390`); a native-text document is usable BY CONSTRUCTION and can never be `A`. The gate's admitted triad (`ocr/escalation.py:216 CHAR_FLOOR = 200`; no text / below floor / every page empty) is parameter-free; the alphanumeric-density signal (`ALNUM_DENSITY_FLOOR 0.70`, `escalation.py:266`) is surface-only (Ruling B).

**The ladder** (`discovery/compare.py:33-45`): `failed < withheld < review < validated`; `deferred` and `unknown` are unranked (moving in or out of them is neither improvement nor regression).

---

## 3. What is already known about the 755

### 3.1 The current run of record (distinct shas, non-validated = 755)

| outcome / reason | digital·native | scanned·tesseract | mixed·tesseract | unknown·none | scanned/mixed·none | total |
|---|---:|---:|---:|---:|---:|---:|
| failed / no_parser_matched | 448 | 78 | 11 | | | 537 |
| failed / parser_declined | 85 | 33 | 1 | | | 119 |
| withheld / withheld_adb | 34 | 15 | | | | 49 |
| review / integrity_flags | 16 | 5 | | | | 21 |
| failed / invalid_pdf | | | | 16 | | 16 |
| deferred / deferred_visual_ocr | | | | | 13 (11 scanned + 2 mixed) | 13 |
| **total** | **583** | **131** | **12** | **16** | **13** | **755** |

- `failure_class`: **B 656 · C 70 · "" 29** (the 16 invalid PDFs + 13 no-text scans). By source: B digital/native 533, B scanned/tesseract 111, B mixed/tesseract 12, C digital 50, C scanned 20.
- `evidence_quality`: `usable` on all 143 Tesseract reads, `none` on 612 (native or no read). **Row-level Class A = 0.**
- `escalation_trigger` / `escalation_refused` empty and `paddle_rung` / `visual_rung` = `not_attempted` on all 755. **No Paddle or visual escalation has ever executed on a real document in any run of record** (every `summary.json` under `discovery_reports/` has `escalations_used: 0`; no `scanned-visual` run exists).
- Pages: **5,110** over the 755 (digital 4,513 · scanned 545 · mixed 52); median 5, max 55. 118 are single-page, 80 two-page.
- 7 of the 755 are pinned-corpus documents with adjudicated fail-closed outcomes (3 withheld, 3 review, 1 refused — the Columbia repair-doctrine ceremony, `corpus_gate.py:PINNED_REFUSALS`).
- Batch-9 Phase-2.0/2.1 headline measures (`tools/phase2_trigger_split.py`, `BATCH9_TRANSITION.md:359`): **R 13** (offline rungs produced no text = the 13 deferred) · **U 123** (usable Tesseract reads unclaimed: 89 `no_parser_matched` + 34 `parser_declined`; scanned 111 / mixed 12) · U-extract (gate-unusable) **0** · U-structure 123 · density-surfaced 23 · **legal escalation population 13 = Paddle-eligible 13 documents / 17 pages** · validated∩(R∪U) 0 · OCR-fed validated 0 (36 validated Tesseract reads exist among the 2,625: `validated x source_path: native 2,589 / local_tesseract 36`).

### 3.2 The batch-9 census crossed onto the current 755

`per_sha.csv` (784 rows, 77 columns; produced read-only by `tools/batch9_census.py` over the batch-8 run + cold cache; families/lists inherited from the batch-8 digital census `CENSUS_BATCH8_DIGITAL.md` at `10cc722`). Crossing by sha: **all 755 current unresolved shas are in the census; the 29 census shas no longer unresolved are exactly batch 9's +29 validated** (guardian_cu 8; pnc families 12; core_processor_enclosures 3; category_partition 3; scotiabank WH 2; pnc WH 1).

Current 755 by census cluster prefix (`cluster_group`):

| prefix | docs | meaning (census rules, `CENSUS_BATCH9.md` §Classification rules) | failure_class now |
|---|---:|---|---|
| `FAM:*` | 322 | `no_parser_matched` sha listed under a batch-8 census layout family (91 families; 37 credit-union suffix/summary families = 176 docs) | B |
| `DECL:*` | 119 | a registration claimed at detection and `parse` returned None (core_processor_sectioned 22, huntington 12, lili 9, community_section 9, bmo_ca_business 6, navy_federal 6, capital_one 6, core_processor_enclosures 6, …) | B 116 / C 3 |
| `NOT-STATEMENT` | 117 | 104 `not_statements` + 13 `portal-export` per the batch-8 census's committed sha lists | B |
| `SCAN-UNCLAIMED` | 89 | scanned/mixed docs with Tesseract text no reader claims; thin 51 / medium 13 / dense 25; **59 single-page** | B |
| `WH:*` | 52 | withheld ADB (frost 9 = period not printed; rbc 6; southside 5; bmo 4; wells 4; pnc 3; …) codes A ledger/closing, B running balances, C posting-date coverage, D out-of-period, E no validations run, F opening | C 49 / B 3 |
| `RV:*` | 18 | review: `not_a_formal_statement` exports (chase_export 4, found_lead 3) and `missing_declared_statement_page` (linkbank 4, community_section 2, southside 2, citizens 1, texas_first 1, core_enclosures 1) | C |
| `PF-INVALID-PDF` | 16 | first bytes are the Java object-serialisation magic (AC ED 00 05), 12-26 KB, 0 pages; Desjardins 11 / Unidentified 4 / TD 1 — portal download artifacts, not documents | "" |
| `OCR-NEGATIVE` | 13 | Tesseract produced no text (= R = deferred 13): scanned 11 / mixed 2; 11 single-page; 17 pages; BofA 3, Unidentified 3, Chase 2, BMO/Citizens/TD/Truist/Wells 1 | "" |
| `TEXT-LAYER-DEFECT` | 8 | digital PDFs whose embedded subset fonts decode to a substitution alphabet (digits included): RBC 4, Chase 1, BofA/unidentified 2, First Citizens 1 (front page image-only) | B |
| `NO-TEXT` | 1 | a digital document with 0 characters (BMO) | B |

Census `b8_kind` on the 755: `family 346 · none 283 · not_statement 104 · portal_export 13 · text_layer_defect 8 · no_text 1`.

**The NOT-STATEMENT bucket, precisely.** All 117 are digital/native-text PDFs; page counts 2 (32), 1 (29), 7 (12), 4 (10), 6 (7), 3 (6); folders Unidentified 51, Bank of America 16, Chase 7, Scotiabank 6, PNC 4, TD 4, Brex 3, CIBC 3, RBC 3, BMO 2. The 13 portal/range exports are DESCRIBED (`CENSUS_BATCH8_DIGITAL.md:1711-1738`: activity views / browser prints with a dated ledger but no statement period, no beginning/ending pair, no printed totals; customer-chosen windows, pending rows, reverse chronology). **The 104 `not_statements` are a bare sha list (`CENSUS_BATCH8_DIGITAL.md:1819-1931`) with no per-document reason recorded.** Both lists were produced by the `unid-census-7` workflow (12 read-only shard readers over cached text, one merge; adversarial verification covered only the top-14 families) — agent judgement over text, not a deterministic classifier, and not verified for this bucket. Whether any of the 104 is a voided check, a cheque image, a letter, or a fragment is not recorded anywhere.

**The scanned residue, precisely.** `SCAN-UNCLAIMED` thin members (51; 42 single-page, <600 chars or <3 money tokens per page) are described by the census as "screenshots, photos, partial pages — a classification problem"; dense members (25; 15 with 2+ pages; hints TD 12, Wells 6, Chase 5, BofA 4) are "a reader problem". Together with OCR-NEGATIVE the census names a 78-document population for "a later, measured visual experiment". Native-text unresolved documents have median 2,024 chars/page (min 306); density dense 401 / medium 131 / thin 51; 48 have <3 money tokens per page; 8 have vowel-word share <0.8 (the text-layer defects — the census notes its proxy does NOT separate them and "a detector is still missing"; `grep` finds no mojibake/text-layer detector in `ocr/`).

**Earlier residue classification.** `PROD-RESIDUE-CLASSIFY` (handoff) is a PRIVACY residue classification of literals in production code — not a document classification. `discovery/adjudication.py` (W3-4) adjudicates CLUSTERS of failures into dispositions (parser proposals / human queue), never document type. There has never been a document-type (statement vs non-statement vs fragment) classification pass with per-document reasons.

---

## 4. Where the corpus and the artifacts live

- Archive: `Bank Statements/` (gitignored `Bank Statements/**`), 58 top-level analyst folders (bank labels; `Unidentified` holds 404 of the 784 census docs). `Misc/` holds pinned documents. Folder label = `inventory.folder_label` (top-level dir) — an analyst label, used only for the `folder_agreement` rollup; **never identity evidence** (UNKNOWN-ISSUER ruling, Gustavo 2026-08-14: never infer issuer from filename, folder label, template similarity or nearby corpus organisation).
- A resolved-population root `.claude/recovery/corpus_frozen_3615/` (symlinks, BATCH8_TRANSITION.md:170) exists for the frozen population.
- Cold caches (READ-ONLY; sqlite index `webapp.db` + artifact files; opened by direct path — "never open the webapp_data sqlite index in write mode, it writes on read"): `.claude/recovery/webapp_data_train8_cold` (batch 8/9), `webapp_data_train10_cold` (Phase 2.0), **`webapp_data_train11_cold` (Phase 2.1: OCR partition 3,364 entries under offline key `B3F8D008…`, EXTRACTION_SCHEMA_VERSION 2; analysis 2,656 entries under key `7799FEE4…`)**. Partition selection is `telemetry/run_of_record.py` (OQ10), used by `tools/cohort_replay.py` (`--run` REQUIRED; `--expect-unresolved 29` is the fidelity form because 29 shas have `source_path=none` forever).
- Run-of-record directory contents: `rows.csv` (46 columns: `relative_path, folder_label, content_sha256, byte_size, valid_pdf, encrypted, classification, page_count, likely_account_count, dedup_status, duplicate_of, source_path, source_model, truncated_pages, parser_id, parser_score, dispatch_outcome, parser_id_source, candidates, attempted, near_miss, parser_exceptions, outcome_class, outcome_reason, error_type, statement_bank, account_last4, account_count, cache_ocr, cache_analysis, cache_visual, visual_rung, elapsed_ms, failure_class, escalation_trigger, evidence_quality, escalation_refused, paddle_rung, cache_paddle, escalation_extractor, evidence_sha256, paddle_provider, paddle_execution_class, offline_source_model, cache_finding, paddle_refusal_reason`), `summary.json`, `telemetry.jsonl`, `provenance.json/.md`, `hash_map.csv`, `report.txt`, `train8_compare.md`.
- Per-document intake profile (`ocr/inspect.py`, `DocumentProfile`): `valid_pdf`, `encrypted`, `classification` = `digital` (total native chars ≥ 500 AND at least half the pages ≥ 200 chars, `inspect.py:34-35,142-158`) / `scanned` (no page ≥ 200) / `mixed` / `unknown` (invalid or encrypted), `page_count`, per-page `page_text_chars`, `content_sha256`, `likely_ocr_required`, advisory `likely_account_count`. Whole-archive classification (summary.json): digital 3,297 · scanned 176 · mixed 16 · unknown 17 (rows, not shas).
- Paddle eligibility ("Class A" / the 13): the router (`ocr/escalation.py`) may START only on `ADMITTED_TRIGGERS` — profile-level `image_only_document` / `mixed_document_pages_without_native_text` (recovery path only, `runner.py:412-431`), `offline_rungs_produced_no_text` (R), `extractor_output_unusable` (U-extract, admitted triad), `extractor_failed`, `operator_forced_visual`; `truncation_flagged` is defined and refused (OQ4). `EXTRACTOR_ORDER = ("local_tesseract","paddle","visual")` (`escalation.py:205`); `RouterInputs.enabled` (P21-ROUTING) lets the run MODE choose. There is no Class-A CLASS of documents beyond "R ∪ U-extract"; the other populations are B (656) and C (70). Paddle on customer scope is refused at the runner without `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` (D8).

---

## 5. Existing classification / detection machinery

- **No document-type classifier exists.** `analysis/detect.py` is lender / potential-lender / insurance / recurring-debit detection over transactions (`detect.py:1-60`); `analysis/classification_registry.py` is transaction classification. The only document-level classification is `ocr/inspect.py`'s digital/scanned/mixed/unknown plus preflight validity/encryption.
- **Dispatch** = `analysis/parser_registry.py` (R-3): each of 84 registrations returns a `Detection` score (0.0 excluded · <0.5 weak, never claims · 0.5 every required marker · <1.0 corroborated · 1.0 exclusive sentinel), ordered by `(band, id)` with explicit `supersedes` edges; two claims → `ambiguous` → review; `detect`/`parse` run behind `_guarded` (a crash becomes `ParserFailure` with class name only). Claiming means "this reader recognised its own template", not "this is a bank statement".
- **Unknown issuer**: publish `bank=None` when structure validates but issuer is unproven (community_section's issuer-less docs; the French-caisse template registered template-keyed).
- **A voided check image today.** As a PNG/JPG: not enumerated (outside the 3,380). As an image-only PDF: profile `scanned` → local Tesseract → if text ≥ floor: `evidence usable`, no parser claims → `failed/no_parser_matched`, **failure_class B** — indistinguishable in every recorded column from an unseen-bank statement; if Tesseract yields nothing → `deferred/deferred_visual_ocr` → member of R → **Paddle-eligible**. Nothing refuses reconciliation attempts on non-statements; nothing labels them. The batch-8 census's `NOT-STATEMENT` sha list is the only non-statement marker and it lives in docs, not in code.
- Text-layer defects (8) are served to readers as `digital` with garbage text; no detector.

---

## 6. The regression floor, the cold run, false accepts, and label leakage

- **Cold run** (`tools/train/coldrun.sh`, `tools/train/winrun.py`): `python -m discovery --scanned --root "Bank Statements" --out discovery_reports/TRAIN<n>-<tree>` against a fresh cache dir under a Windows Job-Object cap (floor 2.0 GB / cap 4 GB / `OCR_MAX_WORKERS=1`); provenance pre/post; then `tools/train8_compare.py <base> <candidate> --quarantine <empty> --fail-on-regression`. The Phase 2.1 cold run took 02:28:26 → 03:42:49 UTC (≈74 min) at peak 1,239.3 MB (job) / 1,222.7 MB (process).
- **Comparison** (`discovery/compare.py`, `tools/train8_compare.py`): keyed on `content_sha256`, never ordering; per shared sha `direction ∈ improved | regressed | unchanged | unranked` over `LADDER`; improvements and regressions reported on separate lines, never netted; **exit 2 if ANY shared sha moved down the ladder** (comparable or quarantined). "Validated regression" = a base-`validated` sha now `review`/`withheld`/`failed`. `tools/cohort_replay.py` additionally proves `validated → validated` shas payload-IDENTICAL (or lists changed leaf paths) through the runner's exact document call (`document_report_to_dict(analyze_document(...))`); exit 2 on a validated regression, exit 3 on `--expect-identical` drift.
- **Doctrine** (`docs/agent-handoffs/BATCH9-RULES.md`): every previously validated sha is protected; `+10 / -2` is not acceptable; a validated→validated payload change must be proven semantically correct; never gain coverage by relaxing any check.
- **"False accept"** — defined in `PHASE2_ARCHITECTURE_PLAN.md §12` (line 388): "system `validated` but human oracle contradicts a money identity or row — release-blocking if > 0 on holdout". **The holdout cage (§12: encrypted separate manifest, strata, human truth fields, burned vs graduated) has NOT been built** — no module under `tools/`, `discovery/`, `telemetry/` mentions a holdout. Phase 2.1's "false accepts 0 on evaluated truth" was over the SYNTHETIC fixture only (`PHASE2-1-PADDLE.md:444`).
- **Human truth that exists**: only the pinned 109 (`docs/adb-audit-results.csv`, `docs/balance-metrics-audit-results.csv` — period, transaction count, calendar-day ADB, opening/ending/high/low, sha; `docs/new-statement-audit-results.csv` 4 rows) enforced by `corpus_gate.py`, plus `moneythumbResults/` (8 MoneyThumb tests, 6 JSON, "never ground truth"; compared by `benchmark/`). **For ≈3,270 of the 3,380 there is no human label of any kind; "validated" is the validator's own verdict, and a false accept among the 2,625 is detectable only through the 80 pinned shas inside the denominator or by the fail-closed doctrine itself.**
- **Label-leakage surfaces** a generalized reconstruction or classifier could accidentally consume: (a) folder labels (`rows.csv.folder_label`) — barred as identity evidence by ruling; (b) the committed census artefacts — `per_sha.csv` (parser ids, reconciliation facts, families, clusters, bank hints), `clusters.json` (sha16 lists per group), the batch-8 family / NOT-STATEMENT / portal-export sha lists in `CENSUS_BATCH8_DIGITAL.md` — all agent-derived, all keyed by sha, none human-verified per document; (c) the pinned-109 audit CSVs (numeric truth); (d) `tests/corpus_cache/` (6 committed OCR artifacts of pinned image-only documents); (e) the cold-cache analysis partition (validated payloads for 2,656 documents — a "what the parser decided" oracle). There are **no transaction-level human labels** anywhere. Guards: `tests/test_no_statement_hardcodes.py` and siblings (275 guard tests) refuse statement-specific literals; the privacy scanners refuse archive tokens in added lines and commit messages.

---

## 7. Metrics recorded today versus the brief's §21 list

**Recorded per document** — `telemetry.jsonl` (63 leaf keys/record): `stages.preflight|ocr|analysis.ms` and `.cache`; `models.calls` + `models.cost.{amount, complete, currency, price_table_version, unpriced_models}` (`telemetry/prices.py` never invents a price; Tesseract prices to 0; an unpriced model yields `amount: None`); `source.model`; `document.byte_size`; diagnostics. `rows.csv`: `elapsed_ms`, `page_count`, `classification`, `cache_*`, `failure_class`, `evidence_quality`, `escalation_*`, `paddle_rung`, `evidence_sha256`, `paddle_provider`, `paddle_execution_class`, `paddle_refusal_reason`, `cache_finding`.

**Recorded per run** — `winrun.jsonl`: `peak_job_mb`, `peak_process_mb`, avail before/after, start/end, exit, timeout; `provenance.md`: host, Python, Tesseract/poppler/pymupdf versions, tree, stage versions, registry fingerprint, cache keys and partitions, inventory, `pip freeze` count; `summary.json`: classification, dispatch, failure_class totals, cache bytes/entries/hits, escalations_used, escalation_trigger/extractor histograms.

**Recorded for Paddle (synthetic only, `PADDLE_MEASUREMENTS.md`)**: cold e2e 5,208.3 ms · cold inference 3,844.0 ms · warm median 1,872.3 ms · p95 2,152.4 ms · bytes/page 253,799 raw PNG / 338,489 wire / 12,264 back · VRAM 7,692 / 32,607 MiB · GPU util sampled 0 % (sampling artefact) · local RSS "not measured (psutil not installed)" · worker wall ≈123 s · cost "rate not measured".

**Missing versus §21** (nothing records these today):
- Paddle attempted / extraction success / geometry success / reconstruction success / validator success as separate per-document counters — `rows.csv` has only `paddle_rung` (`not_attempted|recovered|upgraded|no_upgrade|failed|refused_customer_data`) and `evidence_quality`.
- Non-statement / incomplete-statement / unreadable classifications — no classifier, no column.
- False accepts on real documents — no oracle beyond the 109.
- Per-document RAM (only run-level peak), per-document VRAM (only polled samples), GPU seconds per document (the worker's `timing.inference_ms` exists per request but is not written to `rows.csv`), transferred bytes per document (measured by `paddle_vast measure`, not per row), paid cost (rate unknown → "rate not measured").
- Latency percentiles are derivable from `elapsed_ms` / `stages.*.ms` but not reported.

---

## 8. Surprises worth carrying into the plan

1. The 755 are all PDFs; the archive's 153 PNG/JPG/CSV/XLSX/other files are outside the denominator entirely. "Voided checks / check images / screenshots" inside the 755 are PDFs — most plausibly the 51 thin single-page scans and part of the 104 unexplained `not_statements`.
2. 583 of the 755 (77 %) are native-text digital PDFs with usable text (median 2,024 chars/page) and are Class B by construction: the residue is overwhelmingly a layout-understanding problem, not an OCR problem. Paddle's legal population under current doctrine is 13 documents / 17 pages (11 single-page scans).
3. No Paddle or visual escalation has ever run on a real document in any run of record.
4. There is no document-type classifier, no text-layer-defect detector, and no per-document reason for the 104 `not_statements`.
5. The holdout cage the architecture plan calls "operational" does not exist; false accepts are unmeasurable outside the pinned 109 (80 of which sit inside the 3,380; 7 of those are among the 755 by adjudicated fail-closed outcome).
6. 29 of the 109 pinned truth-set documents are not in the 3,380 at all.

## 9. Not determinable without opening documents (or without a ruling)

- What the 104 `not_statements` and the 51 thin scans actually are, per document.
- Whether the three extensionless the three extensionless files are PDFs (never enumerated regardless).
- The true account count of multi-account documents (only the advisory token count exists).
- The Vast hourly rate (Gustavo's ruling pending), hence any paid-cost figure.
