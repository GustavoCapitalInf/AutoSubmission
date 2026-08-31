# OCR_LEGACY_AUDIT — Phase 2, task 1 (READ-ONLY)

**Card:** `docs/agent-handoffs/OCR-LEGACY-AUDIT.md`.
**Base:** `main` at the frozen deterministic-v1 / multi-account-v1 baseline (tag `batch9-final`,
`819d97d`; audit tree `c90154a`). Registry 84 · `ANALYSIS_STAGE_VERSION` 17 · `OCR_STAGE_VERSION` 4.
**Nothing was implemented.** No code under `analysis/`, `ocr/` or `webapp/` was touched, no OCR call
was made, no paid call was made, no cache was written.

---

## 0. Method, and what was deliberately NOT read

The audit is of CODE, TESTS and artifact FORMATS. No archive document was opened. The one place a
document store was touched at all is the `artifact_cache` **index table** of the batch-8 cold cache
(`.claude/recovery/webapp_data_train8_cold/webapp.db`), opened `mode=ro`: that table carries stage
names, cache keys, hashes, byte sizes and timestamps and no document text. The run of record's own
`rows.csv` was read for provenance columns (`source_path`, `source_model`, `visual_rung`,
`cache_visual`, `dispatch_outcome`, `outcome_class`) — the run's own record of itself, not the
documents.

**Which run each number came from — corrected after adversarial review.** The frozen
deterministic-v1 / multi-account-v1 baseline was measured as
`discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a` (the **batch-9 run of
record**). An earlier draft of this document cited
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` (the batch-8 run)
throughout while naming the batch-9 baseline in its header. **Every row-derived number below has
been re-measured on the batch-9 run of record and each table names the run it came from.** The
entire intake-provenance surface is byte-for-byte identical between the two runs — `visual_rung`,
`cache_visual`, `source_path`, `source_model`, 3,506 rows, 3,380 distinct shas — because nothing in
batch 9 touched the intake ladder, so the governing finding is unaffected. Three numbers did change
and are corrected in place: the U trigger (122 → **123**), the residue bound (135 → **136**), and
the local-Tesseract outcome split. The cold cache is shared by both runs and its numbers are
unchanged.

Two instruments produced the numbers below and both are committed:

* `tools/ocr_legacy_census.py --tree` — the component inventory: LOC, `git log --follow` recency and
  commit count, first-party importers split production / tests / tools, and transitive reachability
  from a declared set of production entry points.
* `tools/ocr_legacy_census.py --cache-index <data-dir>` — per-stage row counts and the multiplicity
  of `input_sha256` inside each stage, from the SQLite index alone.

The tool writes nothing (its docstring's `READ-ONLY BY CONSTRUCTION` section states how) and calls no analysis entry point, so
it is deliberately **not** registered in `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` — that register
answers a question this tool does not raise, and it is a shared append surface that has already cost
one composition conflict.

History was searched as the card instructed, not only the tree: `git log --all -- '*unlimited*'`
returns nothing (no file was ever named for the vendor), so the legacy was found by content instead.
It is not a remnant in the archaeological sense — it is a **complete, wired, currently unexercised
subsystem**, which is a different and more dangerous thing.

---

## 1. The finding that governs everything else

**The visual (Unlimited-OCR) rung has never produced a single artifact in the frozen baseline.**

| measurement | value | evidence |
|---|---|---|
| `visual_rung` column | `not_attempted` on **3,506 / 3,506** rows | `rows.csv`, batch-9 run of record `TRAIN9-7b25d70/…-91f5179a` (identical on the batch-8 run) |
| `cache_visual` column | `bypass` on **3,506 / 3,506** rows | same; a fifth independent witness, contributed by the adversarial review and confirmed here |
| distinct OCR settings keys in the cold cache | **1** | `tools/ocr_legacy_census.py --cache-index` |
| which key | `ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False)` | recomputed at this tree against the index's single distinct `settings_key` |
| `source_path` distribution | native **3,297** · local_tesseract **179** · none **30** · **visual 0** | `rows.csv`, batch-9 run of record (identical on the batch-8 run) |
| `source_model` distribution | `native-pdf-text` 2,871 · `+wells` 234 · `+printed-rows` 83 · `+navy-federal-layout` 48 · `+first-citizens-layout` 36 · `+woodforest-columns` 19 · `+desjardins-layout` 6 · `local-tesseract-ocr` 179 · empty 30 | `rows.csv`, batch-9 run of record (all nine values identical on the batch-8 run) |
| OCR artifacts per input sha (cold cache) | `1x: 3,364`; inputs with **more than one: 0** | `--cache-index` |
| analysis artifacts per input sha | `1x: 2,630`; more than one: **0** | `--cache-index` |

So: 2,625 validated documents, `ANALYSIS_STAGE_VERSION` 17 and every non-regression claim the
program has made rest on **3,297 native-text reads and 179 local-Tesseract reads**. The 485-line
Unlimited-OCR client, the 259-line local server, the truncation-recovery machinery, the DPI
fallback, the TD page-1 recovery and the `--scanned-visual` discovery mode contributed **nothing**
to the frozen baseline and have never been measured against it.

That has two consequences the proposal in §5 is built around:

1. **The Phase-2 architecture already exists in the tree.** `discovery/runner.py` implements the
   card's whole flow diagram — recovery, upgrade, the same deterministic validator, cache
   partitioning, fail-closed on an endpoint death — and has simply never been run. Phase 2 is
   mostly an *audit-and-enable* problem, not a build problem.
2. **Everything on the visual side is unproven at archive scale.** Code that has processed zero
   documents cannot be labelled `active`, and the postprocess chain in particular contains a
   value-destroying rewrite PAIR (F-1, F-11) that nothing has ever been in a position to catch.

---

## 2. Classification table

Labels are exactly the card's vocabulary: `active · reusable · obsolete · duplicate · unsafe ·
unknown`. Exactly one per component. `active` = it runs on a production path today and produced
output in the run of record. `reusable` = correct, tested, wired, but not exercised — keep it.
`unsafe` = it could bypass or weaken a check, or leak a document.

### 2.1 The intake package `ocr/`

| # | component | path (anchors) | label | evidence |
|---|---|---|---|---|
| 1 | package marker | `ocr/__init__.py` (0 bytes) | active | imported transitively by 26 production modules, 29 tests, 38 tools; 1 commit, 2026-07-21. Nothing to audit. |
| 2 | visual-OCR settings | `ocr/config.py:14-42` | **unsafe** | `base_url` (`:28`), `model` (`:29`), `api_key` (`:30`) are pure `os.environ` reads with **no allowlist and no code-level bound**. `ocr/availability.py:5-6` asserts "No paid vendor is involved and none may be" — that is a convention, not an enforcement: one env var repoints the image-bearing request at any host. Read by `webapp/artifact_cache.py:589` for the cache key even when the rung never runs. 4 commits, last 2026-07-28. See F-4. |
| 3 | document preflight | `ocr/inspect.py:185-220` (`inspect_pdf`), `:65-72` (`content_sha256`), `:141-158` (`_classify`) | active | The ONE hash definition (`webapp/storage.py:66` imports it). Drives the ladder (`ocr/pipeline.py:57-67`). 19/19 dedicated tests (`tests/test_inspect.py`). Ran on every document of the run of record. |
| 4 | canonical intake object | `ocr/document.py:7-49` (`StatementMarkdown`), `:33-49` (`to_markdown`) | active | THE seam into the validator (§2.3 #23). 6 production importers, 11 test files, 35 tools. `to_markdown` is pinned by the committed corpus artifacts and by `ocr/document.py:34-36`'s own "must not add a byte" note. |
| 5 | the intake ladder | `ocr/pipeline.py:22-151` (`parse_statement`) | active | The single routing authority (O-1). Called by `webapp/worker.py:6`, `discovery/runner.py:399,455`, `corpus_gate.py:1715`, `parse.py:5`, `batch.py:70`, `coverage_audit.py:19`. 15/15 dedicated tests. |
| 6 | native-text rungs | `ocr/native_text.py:1521-1561` (`native_statement`) + 8 rungs at `:288, :500, :576, :801, :852, :884, :905, :1453` | active | Produced 3,297 / 3,506 reads. 18 commits, last 2026-08-26. Ladder identity pinned by `tests/test_native_rung_parity.py:134,184,250,271`. |
| 7 | printed column grid | `ocr/column_grid.py:1-404`; entry `page_words`, `find_columns`, `read_rows` | active | Sole consumer `ocr/native_text.py:10` (Woodforest — 19 documents in the run of record). 18 tests in `tests/test_column_grid.py`. Named at `tests/test_no_parser_helper_clones.py:215,248` as an architecture exclusion. |
| 8 | local Tesseract rung | `ocr/local_tesseract.py:12-44` | active | Produced 179 reads — on the batch-9 run of record: **36 validated, 15 withheld, 5 review, 123 failed** (the batch-8 run split them 36 / 16 / 5 / 122). **But: zero default-suite coverage** — its only real call site (`tests/test_new_statement_corpus.py:218`) is reachable only from the `live`+`skipif(tesseract missing)` test at `:263`; everywhere else it is monkeypatched (`tests/test_pipeline.py:222` replaces it with `pytest.fail`). 1 commit, 2026-07-28. See F-5. |
| 9 | rasterization | `ocr/rasterize.py:12-27` | active | `pdf_page_count` used by `webapp/app.py:1876`, `balance_forensic_audit.py:34`; `rasterize_page` by `webapp/app.py:1996,2234`. `rasterize_pdf` itself is reachable only from the visual rung and `ocr/local_tesseract.py:22`. **One offline assertion in the whole suite** (`tests/test_new_statement_corpus.py:242`, `pdf_page_count` only); `rasterize_pdf` / `rasterize_page` have no real-invocation offline test. Hard-codes a Windows Poppler path at `:7-10`. |
| 10 | Unlimited-OCR client | `ocr/ocr_client.py:1-485`; request `:419-485`, cleanup chain `:409-416` | **unsafe** | Zero documents in the baseline. `collapse_repeated_amounts` (`:63-82`) and `fix_amount_column_bleed` (`:129-171`) both **rewrite ledger values**, in complementary scopes — demonstrated, F-1 and F-11. `embed_image_regions` (`:344-374`) injects document PIXELS into the canonical text — F-2. `_mask_qr` (`:235-242`) and `_TD_MARKERS_RE` (`:219`) are issuer-specific behaviour inside the intake layer — F-3. Builds the client from the unbounded env settings (`:385-387`) — F-4. 38/38 tests in `tests/test_ocr_client.py`, all against `_FakeClient` (`:331-371`). |
| 11 | endpoint liveness probe | `ocr/availability.py:140-178` (`probe_visual_ocr`), `:87-127` (`_unreachable`) | reusable | Correct, well-argued, injection-seamed (`list_models`), and never fired: its only caller is `discovery/cli.py:31`, reached only in `--scanned-visual`, which was never run. `detail=str(exc)[:200]` (`:125`) is console-only and that is asserted as an AST fact by `tests/test_privacy3_boundaries.py:1770,1783`. Keep it — Phase 2's refuse-to-start needs exactly this. |
| 12 | page-integrity assessment | `ocr/truncation.py:135-196`; `PageText` `:112-132` | active | `assess_pages` runs on EVERY rung, offline ones included (`ocr/pipeline.py:82,148`), so it ran on all 3,476 reads. Flag-only by construction (`:46-51`). 28/33 tests in `tests/test_truncation.py`; `:194-207` proves the cleanup chain cannot manufacture a signal. |
| 13 | markdown → HTML | `ocr/render.py:60-146` (`promote_headers`, `markdown_to_html`, `render_fragment`) | active | `webapp/worker.py:7`, `parse.py:6`. 14/14 tests. |
| 14 | boxed region viewer | `ocr/render.py:148-215` (`render_boxed`, `_render_boxed_page`, `REGION_COLORS`) | reusable | Live at `webapp/app.py:19,2000` but only meaningful for `<|det|>`-tagged visual output; on native/Tesseract pages `_render_boxed_page` (`:186-196`) falls through to plain text. Re-enters `ocr_client.postprocess` at `:179,:192`, so BOTH rewrites (F-1, F-11) reach what an operator reads on screen, not only what the validator reads. |

### 2.2 The vendor side

| # | component | path | label | evidence |
|---|---|---|---|---|
| 15 | local OpenAI-compatible server | `local_ocr_server.py:1-259` | reusable | The `$0` vendor: `baidu/Unlimited-OCR` on the operator's own GPU, speaking `GET /v1/models` + `POST /v1/chat/completions`. **Not imported by anything** (census reach = NO), 2 commits, last 2026-07-23. It is the thing that makes "zero recurring paid inference" true, so it is kept, not deleted — but it is untested and unmeasured. |
| 16 | operator surface | `README.md:1,4,14-15,39-41,51,103,240`; `requirements-local.txt:1`; `serve_local.sh:2-3`; `run.ps1:2,50` | reusable | Documents both a **rented RunPod GPU** and the local server. The RunPod half is the actual pre-deterministic remnant: it describes a paid, per-hour, remote deployment. Phase 2 must decide whether that half stays documented. |
| 17 | price policy | `telemetry/prices.py:28-45`; `FREE_MODELS` `:29-38`, `price_for` `:41-45` | active | `baidu/Unlimited-OCR`, `local-tesseract-ocr`, `native-pdf-text*` and `deterministic-native-preflight` price to `(0.0, 0.0)`; anything else returns `None` = unknown, and `estimate` reports `complete: False`. Fail-closed in the right direction; a Phase-2 extractor with no entry reports *unknown cost*, never zero. |

### 2.3 Caching, artifact formats, and the seam

| # | component | path | label | evidence |
|---|---|---|---|---|
| 18 | artifact cache | `webapp/artifact_cache.py:553-564` (key), `:573-605` (`ocr_settings_key`), `:695-706` (path + atomic write), `:781-797` (`put_ocr`), `:835-854` (rebuild) | active | Layout `<data_dir>/artifacts/<stage>/<key[:2]>/<KEY>.json`; envelope `{cache_format, stage, input_sha256, settings_key, artifact}`; OCR record `artifact.document = null | {model, pages, page_integrity[]}`, each integrity entry `{page_index, truncated, signals, finish_reason}`. Index: SQLite `artifact_cache` (`webapp/storage.py:80-96`), PK `(stage, cache_key)`. |
| 19 | `OCR_STAGE_VERSION` | `webapp/artifact_cache.py:297` (= **4**); read at `:594`; recorded at `tools/train/provenance.py:51,236` | active | Pinned by `tests/test_artifact_cache.py:854` (`assert OCR_STAGE_VERSION == 4`); `:861,866` prove a bump invalidates rather than corrupts. Bump history at `:275-296` (page_integrity → Woodforest columns → printed-row extraction). |
| 20 | OCR cache key inputs | `webapp/artifact_cache.py:592-604` | active | `stage_version, force_ocr, allow_local_ocr, allow_visual_ocr, dpi, fallback_dpi, ocr_model, ocr_base_url, ngram_size, window_size`. Excluded by design (`:121-141`): filename, `max_workers`, `timeout`, `retries`, `api_key`, callbacks, the preflight profile. Every knob's partitioning is pinned by `tests/test_artifact_cache.py:143` and `tests/test_visual_rung.py:492-501`. **Not keyed:** the Tesseract binary version, the Poppler version, the PyMuPDF version — see F-6. |
| 21 | committed corpus artifacts | `corpus_artifacts.py:42,72-132`; generator `build_corpus_cache.py:26-111`; store `tests/corpus_cache/{manifest.json, ocr/<SHA>.md, pages/<SHA>.json}` (6 documents, 14 files) | active | Read by `discovery/runner.py:431-433` and `corpus_gate.py:1730-1731`, both hash-verified (`artifact_sha256`, `pages_sha256`). Manifest carries `ocr_model` per entry (`build_corpus_cache.py:87`). Exists precisely to keep Tesseract version drift out of the pinned corpus (`tests/corpus_cache/README.md`). The generator itself is `reusable` (reach = NO, 5 commits). |
| 22 | cold cache (shared by both runs) | `.claude/recovery/webapp_data_train8_cold/` | active | 5,997 files: `artifacts/ocr` 3,364 JSON + `artifacts/analysis` 2,630 JSON + `webapp.db`. **PDF count: 0** — the source documents are not in it, which is why F-8 (Q3 re-measurement) needs the archive and not just the cache. |
| 23 | the seam OCR → `Statement` / `DocumentReport` | `webapp/worker.py:318-343` → `:408` → `analysis/pipeline.py:1119-1123`; `discovery/runner.py:399-437` → `:511-517`; `tools/cohort_replay.py:129-141` | active | The seam is **three values, not two** (corrected after adversarial review): `markdown = StatementMarkdown.to_markdown()`, `sheets = list(StatementMarkdown.pages)`, and — inside the markdown's own first line — the extractor's `model` string, which `to_markdown()` (`ocr/document.py:38-41`) writes and the extractor controls. The third channel is closed not by the seam's shape but by a GUARD: `admissible_text` (`analysis/parser_registry.py:197-215`) strips that comment via `SOURCE_COMMENT_RE` (`:194`) at `analyze_markdown`'s single parse seam, pinned by `tests/test_filename_boundary.py`. The guard is escapable by a newline in the model string — see F-4(b). There is no per-field provenance — see §5.5. `corpus_gate.py:725-772` (`ANALYSIS_CALL_SITES` / `PRODUCTION_SUPPLIES_SHEETS`) is a standing guard that every production analysis caller passes `sheets=`. |
| 24 | webapp job worker | `webapp/worker.py:293-342` (`_read_document`), `:346-470` (`run_job`), `_STAGE_NAMES` `:45-49` | active | Owns MODE policy only, never routing (`:39-44`). `deterministic` mode: offline rungs, then an operator-forced visual escalation at `:444`. `auto` mode: full ladder at `:454`, `allow_visual_ocr=True`. |
| 25 | discovery visual rung | `discovery/runner.py:438-500` (`_read_visual`), `:521-541` (`_needs_visual_upgrade`), `:606-670` (recovery + upgrade), `:100-101` (`VISUAL_*` vocabulary), `:181` (row field) | **reusable — the Phase-2 architecture, already written** | Recovery (offline rungs produced nothing) and Upgrade (Tesseract read that no parser claimed) both call `parse_statement(force_ocr=True, allow_visual_ocr=True)` into a disjoint cache partition, then the SAME `_analyse`. Fail-closed on an endpoint death (`:620-621`, `ocr_failed`). `_needs_visual_upgrade` is narrow by construction (`:524-533`). **Exercised on 0 documents.** |
| 26 | discovery CLI + preflight refusal | `discovery/cli.py:31,107-138`; modes `discovery/runner.py:87-91` | reusable | `--scanned-visual` is the only mode that enables the rung; it probes the endpoint up front and refuses to start (`ocr/availability.py:8-12`). Never run. |
| 27 | telemetry provenance | `telemetry/record.py:66` (`SOURCE_PATHS`), `:119-134` (`source_path_for`), `:196-197`, `:318-337` (`model_calls_for`) | active | `SOURCE_PATHS = ("native", "local_tesseract", "visual", "none")` is a CLOSED vocabulary and `source_path_for`'s final branch is `return "visual"` (`:133`) — i.e. **any unrecognised model string is reported as the visual rung**. A Phase-2 PaddleOCR rung that does not add its own branch would be mis-attributed. See F-7. |
| 28 | deferral taxonomy | `telemetry/record.py:65` (`DEFERRED_REASONS`), `discovery/runner.py:435,596-604` | active | `deferred_scanned` / `deferred_visual_ocr` / `profile_only`. `deferred_visual_ocr` is the existing, recorded, deterministic name for "the offline rungs produced nothing" — **13 documents carry it in the run of record**. This is the insufficiency trigger the card asks for, already implemented. |
| 29 | non-regression replay | `tools/cohort_replay.py:109-150` (`ColdCache`), `:119-129` (`_payload`), `:295-299` (miss handling) | **unsafe** | `_payload` runs `SELECT artifact_path ... WHERE stage=? AND input_sha256=?` and takes **`rows[0]` with no `ORDER BY` and no settings-key filter**. Correct today because every input holds exactly one OCR artifact (measured: 0 inputs with more than one). The moment an OCR-fed document has both an offline and an OCR partition, the replay's source becomes arbitrary. See F-9. |

### 2.4 Legacy scripts from before the deterministic shift

| # | component | path | label | evidence |
|---|---|---|---|---|
| 30 | OCR CLI | `parse.py:1-46`; call `:30` | **unsafe** | "Bank statement PDF → Markdown via Unlimited-OCR" (`:10`) — the repository's original front door. Calls `parse_statement` with the **defaults**, i.e. `allow_visual_ocr=True`: any document without native text goes straight to the env-configured endpoint with its pixels, with no probe and no confirmation. `:32` prints `str(e)` to stderr (console-only, same class as `ocr/availability.py:125`). Publishes no verdict, so it cannot weaken a validator check; the risk is egress. Severity LOW-MEDIUM. |
| 31 | per-bank OCR sweep | `sweep_ocr.py:1-67` | obsolete | Dev-only. Reach = NO, 0 importers, 1 commit (2026-07-24). Writes full OCR'd statement text to `output/<label>.md` + `.html` — a plaintext document sink outside the artifact store (gitignored at `.gitignore:4`, so not a commit leak, but also not scanned by anything). |
| 32 | OCR defect triage | `triage_scan.py:1-49` | obsolete | Reads `output/*.md` produced by #31. Its `CHECKS` dict (`:8-21`) is a useful inventory of the visual rung's known defect signatures and should be salvaged into a test before deletion. 1 commit, 2026-07-24. |
| 33 | coverage audit | `coverage_audit.py:1-205` | obsolete | Reach = NO; superseded by `discovery/` + `tools/cohort_replay.py`. Excused in `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` as "measurement script over markdown". Calls `parse_statement` with the full ladder (`:178`), so it too can reach the endpoint. |
| 34 | deterministic coverage audit | `deterministic_coverage_audit.py:1-288` | duplicate | Measures what `discovery/runner.py` measures, over the same ladder. Kept honest by `tests/test_native_rung_parity.py` (it is one of the six pinned ladder consumers) and excused in the same register. Its continued existence is now purely a second implementation of the same question. |
| 35 | batch CLI | `batch.py:60-76`, `:255-262` | active | Passes `sheets=doc.pages` correctly (`:262`). But `:73` calls `parse_statement(raw, source_file=path.name)` with the **defaults** — same `allow_visual_ocr=True` egress as #30. |
| 36 | markdown analysis CLI | `analyze.py:188` | active | `analyze_document(markdown)` **without `sheets`** — correct and deliberate (it has no intake object), and it fail-closes the page-declaration check exactly as intended (`analysis/pipeline.py:623-628`). Excused in the register at `corpus_gate.py`. |
| 37 | forensic oracles | `adb_forensic_audit.py:28`, `balance_forensic_audit.py:33`, `adb_debug.py:26` | active | The three independent oracles; all three bind `native_statement` by identity, pinned by `tests/test_native_rung_parity.py:134`. Deliberately excused from the analysis-caller register. |
| 38 | structurer geometry | `analysis/structurer/geometry.py:135-179` (`geometry_from_pdf`) | reusable | **Unwired in production**: `document_geometry` is a parameter of `analyze_markdown`/`analyze_document` (`analysis/pipeline.py:699,728,1121`) that no production caller ever supplies; the only callers of `geometry_from_pdf` are `tools/measure_structurer.py:117` and tests. Its docstring (`:137-141`) explicitly reserves the scanned case: "inventing line boxes from an image is the visual rung's job". This is the pre-built socket for OCR-supplied geometry. |
| 39 | structurer spike | `experiments/w3_3a/evaluate.py:59-60` | obsolete | A measurement spike that calls `inspect_pdf` + `parse_statement`. Provably outside every production path by `tests/test_experiments_are_not_wired.py:33-40`. Its question was answered by the structurer wave. |

### 2.5 Tests and fixtures

| # | component | path | label | evidence |
|---|---|---|---|---|
| 40 | ladder identity guard | `tests/test_native_rung_parity.py` (6 tests, no fixtures, no markers, offline) | active | Pure AST/identity guard: `:134` every consumer's binding **is** `ocr.native_text.native_statement`; `:184` the repo-wide import scan equals the hand-written `LADDER_BINDINGS`; `:250` nothing outside the ladder's home calls a rung; `:271-276` every defined rung is wired, none twice, generic rung last. **Known admitted hole pinned at `:230`: a `getattr(...)` dynamic rung access is invisible to the scan.** A Phase-2 extractor added by dynamic dispatch would evade this guard. |
| 41 | visual-rung tests | `tests/test_visual_rung.py` (32 tests), `tests/test_ocr_client.py` (38), `tests/test_pipeline.py` (15), `tests/test_truncation.py` (33) | active | All offline: `_build_client` stubbed (`tests/test_pipeline.py:64` etc.), `probe_visual_ocr(list_models=…)` injected, `ocr.ocr_client` asserted absent from `sys.modules` after importing the CLI (`tests/test_discovery.py:310-322`, `tests/test_visual_rung.py:252-265`). |
| 42 | live tests | `tests/test_live_smoke.py:9,17`; `tests/test_new_statement_corpus.py:263` | reusable | The only three tests that can leave the process, each double-guarded (`pytestmark = pytest.mark.live` + `skipif` on `OCR_BASE_URL` / `shutil.which("tesseract")`), and `pytest.ini:2` deselects `live` and `corpus` by default. This is the correct shape for Phase 2's live proofs. |
| 43 | OCR fixtures | `tests/corpus_cache/ocr/<SHA>.md` (6), `tests/corpus_cache/pages/<SHA>.json` (6), `manifest.json` | active | The committed Tesseract reads of the 6 image-only corpus statements. Format: markdown page dump + `{"pages": [...]}`, filename = uppercase SHA-256 of the source PDF. |
| 44 | Q3 corroboration probe | `tools/q3_corroboration_probe.py:1-908` | reusable | The oracle for F-8. Its own docstring (`:70-77`) states the gap: all six `guardian_cu` sections carry `native-pdf-text`, "so on this population that hazard cannot arise", and "anyone re-running this probe against OCR'd input … is asking the question for the first time". |
| 45 | PaddleOCR | — | **absent** | `grep -riE "paddle\|easyocr\|textract\|donut\|trocr\|surya"` over the tree returns **zero** hits. PaddleOCR is entirely net-new; there is no legacy to reuse and no adapter interface to fit it into except a new rung in `ocr/pipeline.py`. |

### 2.6 Totals

| label | count | components |
|---|---|---|
| **active** | 26 | 1, 3, 4, 5, 6, 7, 8, 9, 12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 27, 28, 35, 36, 37, 40, 41, 43 |
| **reusable** | 9 | 11, 14, 15, 16, 25, 26, 38, 42, 44 |
| **obsolete** | 4 | 31, 32, 33, 39 |
| **duplicate** | 1 | 34 |
| **unsafe** | 4 | 2 (`ocr/config.py`), 10 (`ocr/ocr_client.py`), 29 (`tools/cohort_replay.py::ColdCache._payload`), 30 (`parse.py`) |
| **unknown** | 0 | — |
| absent (net-new) | 1 | 45 (PaddleOCR) |

`unknown` is empty because every component's reachability was **computed** (transitive first-party
import walk from eight declared production entry points, `tools/ocr_legacy_census.py`) rather than
guessed, and every "does it run" question was answered from the run of record's own columns. If a
component could not be resolved either way it would be labelled `unknown` here; none was.

### 2.7 Evidence / confidence plumbing — the card item whose answer is "none"

Audited explicitly because its absence is load-bearing rather than an oversight.

* **There is no confidence plumbing anywhere in the OCR path.** A case-insensitive search for
  `confidence` / `conf_score` / `ocr_score` across `ocr/`, `webapp/`, `telemetry/`,
  `analysis/schema.py`, `analysis/pipeline.py` and `analysis/serialization.py` returns **0 hits**.
  No extractor emits a score, no record carries one, and the validator has no parameter that could
  read one. This is the strongest single property in §5.7: an extractor literally has no channel
  through which to argue for its own output.
* **What exists instead is EVIDENCE, and it is boolean and structural.** `PageIntegrity`
  (`ocr/truncation.py:98-109`) carries `truncated`, a list of named `signals` from a closed set
  (`:65-77`) and the endpoint's own `finish_reason` — advisory, flag-only, and explicitly never
  consumed by extraction (`ocr/truncation.py:46-51`, `ocr/pipeline.py:143-147`). The two evidence
  classes are the model's own completion metadata and a hard structural impossibility in the page
  tail; the module documents three higher-recall signals it considered and rejected (`:32-44`)
  precisely so that no probabilistic judgement enters.
* **On the validator's side, evidence is likewise named and closed**: `currency_source`
  (`analysis/schema.py:94-100`) is a provenance enum, the omission classes are a closed vocabulary
  (`telemetry/record.py`), and reconciliation/ADB/coverage are arithmetic over printed figures.
* **Implication for Phase 2.** A second extractor must NOT introduce a confidence score as the way
  to choose between two reads. The existing adoption test — "the deterministic validator claimed
  it" (`discovery/runner.py:655-660`) — is a decision made by the validator, not by the extractor,
  and it is the only kind of arbitration the architecture can accept without giving an extractor a
  voice in its own adoption.

### The five most consequential rows

1. **#25 `discovery/runner.py:438-670` — `reusable`.** The card's flow diagram is already implemented,
   cache-partitioned and fail-closed, and has processed zero documents. Phase 2 starts by enabling
   and measuring this, not by designing it.
2. **#10 `ocr/ocr_client.py` — `unsafe`.** The only OCR extractor that has never run is also the one
   that rewrites money in two complementary scopes (F-1, F-11) and embeds document pixels into the
   text the validator reads (F-2).
3. **#29 `tools/cohort_replay.py::ColdCache._payload` — `unsafe`.** The whole non-regression regime
   silently loses determinism the first time a document has two OCR partitions (F-9).
4. **#2 `ocr/config.py` — `unsafe`.** The `$0`/no-paid-vendor guarantee is documented as an invariant
   and enforced by nothing (F-4).
5. **#38 `analysis/structurer/geometry.py` — `reusable`, unwired.** `document_geometry` is a live
   parameter that no production caller fills; it is the pre-built socket for OCR word boxes and the
   cheapest structural win available in Phase 2.

---

## 3. Findings

**F-1 — `collapse_repeated_amounts` destroys ledger values. `ocr/ocr_client.py:63-82`, in
`postprocess` at `:413`.**
`_MONEY_RUN_RE` matches three or more money tokens separated by `\s+`, and `\s` matches **newlines**.
So a page region rendered as one bare amount per line — the shape a scanned amount column takes when
the model does not emit table markup — collapses to a single token whenever one value repeats three
or more times. Demonstrated at this tree on a synthetic input: three identical money tokens on three
consecutive lines return as **one** token; the same three values inside `<td>` cells are correctly
left untouched; three *distinct* amounts on consecutive lines are left untouched.

**The blast radius is larger than "three identical fees become one fee"** — found by the adversarial
review, reproduced independently here at this tree. A bare amount column of `[a, a, a, b, c]` on five
consecutive lines — three identical fees followed by two unrelated amounts — returns **`[a]`**.
`_MONEY_RUN_RE` consumes the entire whitespace-separated run and `repl` replaces the *whole match*
with the dominant value, so every distinct amount that merely sits adjacent in the same run is
**deleted**, not deduplicated. The function can destroy amounts it never saw repeat, and the effect
survives the full chain: `postprocess()` on the same input returns the single token.

The docstring's safety argument ("legitimate amounts live in table cells … or on lines with
dates/descriptions") is a claim about the model's output shape, not a property of the code, and it
has never been tested against a real page because the rung has never run. Under the batch-9
non-regression rules, an extractor that rewrites a source value to a different value is not a repair,
it is the thing the repair doctrine forbids ("parsers never write an amount") arriving one layer
upstream of the parser. **It is not, however, the only such site — see F-11, and see §5.7: the PAIR
is what Phase 2 must resolve before any OCR-fed document is validated.**

**F-11 — `fix_amount_column_bleed` is a SECOND value rewrite, and it lives inside `<td>` cells.
`ocr/ocr_client.py:129-171`, `_AMOUNT_BLEED_RE` at `:126`, in `postprocess` at `:416`.**
Raised by the adversarial review as its BLOCK; reproduced independently here at this tree. The
pattern is `^(.+?)\s+(-?\$?[\d,]+\.\d{2})$` and the "description tail" group is `(.+?)` —
**anything, a money token included**. In any table carrying an `Amount` header, an Amount cell that
the model rendered as two fused money values has its **leading amount moved into the description
column and its trailing amount promoted to the row's amount**:

```
in : <tr><td>01/02</td><td>ACH DEBIT</td><td>1,000.00 234.56</td></tr>
out: <tr><td>01/02</td><td>ACH DEBIT 1,000.00</td><td>234.56</td></tr>
```

The parser then reads the smaller figure where the page printed the larger one. Two fused money
values in one cell is precisely the fusion class the three sibling repair functions exist to handle,
so this is not an exotic input — it is the function's own domain. By this audit's own standard it is
the same defect class as F-1, and it reaches reconciliation, ledger identity, transaction coverage
and ADB by exactly the same route.

Three consequences, each of which changed earlier text in this document:

1. **§5.7's original summary was false** ("the whole safety delta … is one function") and has been
   rewritten. The same sentence was in W3 §OCRAUDIT and has been corrected there too.
2. **The original Open Question 1 recommended confining F-1's collapse to `<td>` cells.** That is
   unsafe: `fix_amount_column_bleed` operates *only* inside `<td>` cells. Table cells are not a safe
   harbour — they are where the second rewrite already lives. OQ1 has been re-posed with that
   premise removed.
3. **The chain needs a per-function rewrite census, not a spot fix.** `postprocess`
   (`ocr/ocr_client.py:409-416`) is six functions deep; two of them provably write values.
   `split_fused_header_row` (`:174`) and `repair_fused_amount_table` (`:273`) restructure rows and
   re-emit cells. Neither the review nor this audit could construct a value-losing input for the
   latter — its `_FUSED_HEADER_CELL_RE` guard at `:269` is tight — and **neither claims one
   exists**; but its per-row loop folds every `len(cells) >= 3` row whose last cell is money into
   three columns by joining `cells[1:-1]` into the description, a shape that on a
   debit/credit/balance table would fold two money columns into the description. That is
   **explicitly UNPROVEN** and is exactly what the census in §5.7 must settle.

**F-2 — the OCR path puts document PIXELS into the canonical text. `ocr/ocr_client.py:344-374`
(`embed_image_regions`), bounded at `:367-371` and `:377-382`.**
Picture regions are cropped from the page and inlined as `<img src="data:image/png;base64,…">` in
the markdown, subject only to area heuristics and a 25,000-character cap. That markdown is the
`StatementMarkdown.pages` payload, so it is persisted into the artifact cache
(`webapp/artifact_cache.py:789`), hashed into `analysis_input_sha`, and scanned by every parser's
detection markers. Consequences: (a) up to ~18 KB of raw document imagery per region inside the
analysis input; (b) the branch privacy scanners match printed TOKENS and cannot see base64, so this
content is invisible to them; (c) parser detection and every text metric run over a page containing
a multi-kilobyte opaque blob. Not a leak today (0 visual reads), but it is a leak SHAPE that the
existing scanners are structurally unable to catch.

**F-3 — issuer-specific behaviour inside the intake layer. `ocr/ocr_client.py:215-263`
(`_TD_MARKERS_RE`, `is_td_statement`, `looks_truncated_td`, `_mask_qr`, `_TD_RECOVERY_VARIANTS`),
reached from `ocr/pipeline.py:121-125`.**
The visual rung detects one named issuer by printed markers, whites out a fixed rectangle of its
page 1 (`:241`, 60–100% × 0–12%), and re-OCRs across five hard-coded `(dpi, mask)` variants. This is
exactly the statement-specific-hardcode class that `tests/test_no_statement_hardcodes.py` forbids in
`analysis/` — the guards' scope stops at the intake layer, so nothing catches it here. It is
defensible as intake (it changes which pixels are read, not what a value means) but it should be
declared, not discovered, and Phase 2 must decide whether the guard scope extends to `ocr/`.

**F-4 — the unvalidated OCR environment is BOTH an egress path and a content-INJECTION path.
`ocr/config.py:26-42`, `ocr/ocr_client.py:385-387`, `ocr/pipeline.py:149`, `ocr/document.py:33-49`.**
*Widened after adversarial review; the earlier version of this finding was egress-only.*

**(a) Egress.** `OCR_BASE_URL`, `OCR_MODEL` and `OCR_API_KEY` are plain env reads with no allowlist.
**Four** entry points default `allow_visual_ocr=True` and will therefore post page images to whatever
host that variable names: `parse.py:30`, `batch.py:73`, `coverage_audit.py:178` and — the one an
earlier draft missed — **`sweep_ocr.py:52`**, which is also the script that writes full OCR'd
statement text to `output/`. Every other `parse_statement` call site in the tree passes
`allow_visual_ocr=False` explicitly, except `discovery/runner.py:458`, which is the deliberate visual
rung. `telemetry/prices.py` fails closed on the *reporting* side (an unknown model prices to `None`,
not `0.0`); nothing fails closed on the *calling* side, and `ocr/availability.py:5-6` states an
invariant that no code enforces.

**(b) Injection — the more serious half.** `OCR_MODEL` is not only "which host gets the pixels"; it
is **arbitrary text in the analysis input of every document the visual rung reads**.
`ocr/pipeline.py:149` stamps `model=settings.model` onto the visual rung's `StatementMarkdown`, and
`to_markdown()` (`ocr/document.py:33-49`) writes that string into the first line of the analysis
input: `<!-- source: … | model: {self.model} | empty: N -->`. Reproduced end-to-end at this tree:
with `OCR_MODEL` set to a value containing a **newline**, the second line — including an injected
money-shaped token — survives `admissible_text()` and reaches the text every parser's detection
markers scan and every text metric runs over. A model string containing `-->` does **not** escape
(backtracking consumes to the last `-->` on the line); a newline does, because `SOURCE_COMMENT_RE`
(`analysis/parser_registry.py:194`) is `MULTILINE` and **not** `DOTALL`.

Unreachable today — zero visual reads — and reachable the day Phase 2 enables the rung. It is made
sharper, not safer, by §5.5 item 2, which proposes *new* extractor-authored model-string conventions
(`unlimited-ocr+…`, `paddle+…`) that go straight into that header. **Required in the same commit that
adds any extractor: a closed character class on its model token** (no newline, no `<`, no `-->`),
validated where the token is set rather than where it is printed.

**F-5 — the second-largest extractor in the baseline has no default-suite test.
`ocr/local_tesseract.py:12-44`.**
179 reads of the run of record — 36 of them validated documents — came from a 44-line module whose
only real invocation in the suite is behind `pytest.mark.live` + `skipif(shutil.which("tesseract")
is None)`. Its own 200-character floor (`:42`) and its per-page `except: pages.append("")` (`:40-41`)
are unexercised offline. `ocr/rasterize.py` is in the same position (one `pdf_page_count` assertion).

**F-6 — binary versions are outside the cache key. `webapp/artifact_cache.py:592-604`.**
The OCR settings key covers the vLLM-side knobs (`ocr_model`, `ocr_base_url`, `ngram_size`,
`window_size`, `dpi`, `fallback_dpi`) but not the **Tesseract**, **Poppler** or **PyMuPDF** versions.
An upgraded local binary silently reuses artifacts produced by the previous one. Today this is
absorbed by the `OCR_STAGE_VERSION` discipline and by the committed corpus artifacts (which exist to
pin exactly this — `tests/corpus_cache/README.md`), but Phase 2 adds a second binary extractor and
makes the omission load-bearing.

**F-7 — the provenance vocabulary is closed and its fallthrough is `visual`.
`telemetry/record.py:66,119-133`.**
`source_path_for` returns `"visual"` for **any** model string that is not `native-pdf-text*`,
`local-tesseract-ocr` or `deterministic-native-preflight`. A PaddleOCR rung that forgets to add its
branch is silently reported as the GPU/visual path in every telemetry record, discovery row and cost
estimate. `SOURCE_PATHS` must gain a member and `telemetry/prices.py:29-38` a free-model entry, in
the same commit as the rung.

**F-8 — the Q3 corroboration class has never met the failure mode it exists for.**
`docs/moneythumb-replacement/BATCH9_BACKLOG.md:47-53`; `tools/q3_corroboration_probe.py:70-77`. All
six `guardian_cu` sections that passed 6/6 carry extractor model `native-pdf-text`. The roll-up
witness was ruled in to bound OCR row-loss and has been measured only where OCR row-loss cannot
occur. The re-measurement plan is §5.8.

**F-9 — the non-regression replay picks an arbitrary OCR artifact once there is more than one.
`tools/cohort_replay.py:119-129`.**
Measured at the cold cache: `ocr` stage — 3,364 rows, 3,364 distinct inputs, **1** distinct settings
key, **0** inputs holding more than one artifact. `_payload` is therefore correct today by accident
of the population, not by construction. Phase 2's OCR-fed document necessarily holds two OCR
partitions of the same `input_sha256` (the offline read that came back empty or unclaimed, and the
OCR read), and SQLite's row order without `ORDER BY` is unspecified. `--fail-on-regression` would
then compare a tree against a baseline read it did not choose.

**F-10 — one shipped guard has a declared hole a Phase-2 extractor could walk through.
`tests/test_native_rung_parity.py:217-233`, pin at `:230`.**
`_rungs_reached` catches direct calls, aliased imports and attribute calls, and explicitly does not
catch `getattr(module, name)`. The guard is honest about it. A Phase-2 rung registered dynamically
would not be seen by the ladder-identity guard, which is the guard that exists because the ladder
once drifted in two places at once.

---

## 4. Reuse plan (three sentences)

Keep and enable, do not rebuild: `discovery/runner.py`'s recovery/upgrade block (#25), the
`--scanned-visual` mode and its refuse-to-start probe (#11, #26), `local_ocr_server.py` (#15) and the
whole cache/stage-version/provenance apparatus (#18–#21, #27–#28), because they already implement the
card's flow diagram, already partition the cache correctly and already fail closed. Quarantine before
reuse: `ocr/ocr_client.py`'s cleanup chain — the whole chain should be quarantined for Phase 2 and
re-admitted function by function on the evidence of §5.7's rewrite census, because F-1 and F-11 write
values in complementary scopes and a table-only confinement moves one into the other; and F-2 must
become a reference rather than an inlined blob — and `tools/cohort_replay.py::ColdCache._payload` must select its artifact deterministically
(F-9) before a single OCR-fed document is admitted to a cold run. Delete or salvage: `sweep_ocr.py`,
`triage_scan.py` (salvaging its `CHECKS` dict into a real test), `coverage_audit.py` and
`deterministic_coverage_audit.py`, and decide whether the README's rented-RunPod half still describes
a deployment the program will ever use.

---

## 5. The Phase-2 extraction architecture (design, not code)

```
                       PDF bytes
                          |
                 inspect_pdf  (ocr/inspect.py:185)
                          |
              native deterministic ladder
              (ocr/native_text.py:1521)
                          |
        +-----------------+------------------+
        |                                    |
   text produced                      no text produced
        |                                    |
   deterministic validator            INSUFFICIENT EXTRACTION
   (analysis/pipeline.py:1119)        reason: no_native_text
        |                                    |
   +----+------------------+                 |
   |                       |                 |
validated                claimed = false     |
   |                       |                 |
  done             INSUFFICIENT EXTRACTION   |
                   reason: unclaimed_after_  |
                           image_only_read   |
                          |                  |
                          +--------+---------+
                                   |
                        Unlimited OCR / PaddleOCR
                        (extractors only; own cache
                         partition; own model token)
                                   |
                     canonical statement / accounts
                     (StatementMarkdown -> markdown + sheets)
                                   |
                     THE SAME deterministic validator
                     (analysis/pipeline.py:1119, unchanged)
                                   |
                          validated / refuse
```

### 5.1 What is genuinely new, and what is not

Everything above the "Unlimited OCR / PaddleOCR" box exists and runs. The right-hand branch exists
and runs (`discovery/runner.py:606-670`) but has processed zero documents. The only net-new
components are: a PaddleOCR rung, the provenance vocabulary entries it needs, and the four safety
changes F-1/F-11 (the rewrite pair), F-2, F-6 and F-9.

### 5.2 What decides "insufficient extraction" — a deterministic, recorded reason

Never "try OCR and see". Exactly two triggers, both already implemented and both already recorded on
the discovery row:

| trigger | decided by | recorded as | population on the **batch-9 run of record** (batch-8 in brackets) |
|---|---|---|---|
| **R — recovery.** The offline rungs produced *no text at all*. | `discovery/runner.py:606` (`markdown is None`); upstream `ocr/pipeline.py:57-89`, and the profile-driven skip at `:63-67` (`valid_pdf and page_count > 0 and native_text_total_chars == 0`) | `outcome_reason = deferred_visual_ocr` (`discovery/runner.py:599`; vocabulary `telemetry/record.py:65`), then `visual_rung = recovered \| failed` | **13 documents** |
| **U — upgrade.** A **local-Tesseract** read that no parser claimed, with a live dispatch. | `discovery/runner.py:521-541` (`_needs_visual_upgrade`): requires `source_path_for(model) == "local_tesseract"`, requires `collector.seen` and `dispatch.outcome != "claimed"`, refuses on a cached payload and on parser crashes | `visual_rung = upgraded \| no_upgrade \| failed` (`:100-101,181`) | **123** (was ≤122 on the batch-8 run). Derived two ways that agree exactly: `source_path = local_tesseract AND dispatch_outcome != claimed` = 123, and `source_path = local_tesseract AND outcome_class = failed` = 123 |

Both are properties of a completed offline attempt, computed before any OCR call, and written to the
row whether or not the rung then runs. A native-text document that goes unclaimed is **never**
escalated (`:526-528`) — that is a missing parser, and re-reading perfect text with a GPU cannot
create one. Proposed additions, both still deterministic and both still recorded:

* **T — truncation.** `PageIntegrity.truncated` is already computed for every rung
  (`ocr/pipeline.py:82,148`) and already on the row (`discovery/runner.py:633`,
  `truncated_pages`). A Tesseract read with flagged pages is a text-quality failure by the same
  argument as U, and it is currently only surfaced, never acted on. Admit it as a third trigger only
  with its own recorded reason.
* **Explicitly NOT a trigger:** a reconciliation failure, an ADB withholding, a page-completeness
  flag or any other *validator verdict*. Escalating on a validator verdict is how "try OCR until it
  reconciles" gets built by accident, and it is the one shape that could launder a bad read into a
  validated document.

### 5.3 Cache key and stage version

The existing key is already correct for two extractors and needs three additions:

1. `OCR_STAGE_VERSION` **4 → 5** at `webapp/artifact_cache.py:297`, with the pin at
   `tests/test_artifact_cache.py:854` updated in the SAME commit (the bump-history comment at
   `:275-296` is the required record). Every change to any extractor's output — including the F-1/F-11
   removal — is a bump; that is what makes an OCR-fed cold run reproducible.
2. Add an `extractor` field to the OCR settings key (`webapp/artifact_cache.py:592-604`) naming
   which extractor stack was asked for (`offline` / `unlimited_ocr` / `paddle`). Today the three
   capability booleans encode this implicitly; a third extractor makes the encoding ambiguous.
3. Add the **binary versions** the read depends on (F-6): Tesseract's `--version`, Poppler's, and
   the PaddleOCR model revision. If a version is unobtainable, key on the sentinel `unknown` — which
   partitions conservatively (a new key, a re-read) rather than silently reusing.

Everything else stands: input hash = `content_sha256(pdf_bytes)`; layout
`<data_dir>/artifacts/ocr/<key[:2]>/<KEY>.json`; the record `{model, pages, page_integrity[]}`;
`analysis_input_sha = f(admissible_text(markdown), sheets_sha256(sheets))`, so an OCR-fed document
automatically lands in its own analysis partition too.

### 5.4 How cost is bounded

* **Zero recurring paid inference stays the default and stays structural.** The offline ladder runs
  first, always; `ocr/pipeline.py` imports `ocr.ocr_client` *lazily inside the visual rung*, and two
  tests assert the module is absent from `sys.modules` after importing the discovery CLI
  (`tests/test_discovery.py:310-322`, `tests/test_visual_rung.py:252-265`). Keep that property for
  PaddleOCR: a lazy import inside the rung, plus its own absence assertion.
* **The residue is bounded by the triggers, and the bound is measurable in advance.** On the
  **batch-9 run of record**: 13 (R) + 123 (U) = **136 of 3,506 documents, just under 4%**, with the
  two trigger sets DISJOINT (measured overlap 0). The batch-8 run gave 135; a runner built to the
  stale figure would refuse the 123rd document, which is why the provenance correction matters more
  than the arithmetic. A run whose escalation count
  exceeds its own pre-computed trigger population is a defect, not a cost overrun — so the runner
  should refuse to escalate more documents than the triggers named, and report the count.
* **The default extractor for the residue is free.** PaddleOCR is local and CPU-capable;
  Unlimited-OCR runs on the operator's own GPU via `local_ocr_server.py`. Neither is metered.
* **Close F-4 before enabling anything.** An allowlist on `OCR_BASE_URL` (loopback and an explicitly
  configured private host), enforced in `ocr/config.py`, with `telemetry/prices.py`'s
  `FREE_MODELS` as the *reporting* half of the same policy. A paid endpoint should require an
  explicit, recorded opt-in, not an env var nobody audits.
* **Paid OCR / VLM remains out of scope** for the first Phase-2 wave, per the cost-first doctrine —
  and the audit's own numbers argue it: the residue is just under 4%, and none of it has been tried
  with the free extractors yet.

### 5.5 The provenance the payload carries

Today provenance is **one token for the whole document**: `StatementMarkdown.model`
(`ocr/document.py:10`), persisted at `webapp/artifact_cache.py:789`, mapped to a closed vocabulary by
`telemetry/record.py:119-133`, surfaced as `source_path` / `source_model` on the discovery row. There
is no per-field provenance anywhere: the seam into the validator is a markdown string plus a page
list (§2.3 #23), and a `Statement` field cannot say which extractor produced it.

Proposal, in ascending cost — the first is required, the rest are Phase-2-later:

1. **Required now: per-PAGE provenance.** `StatementMarkdown` already has a per-page vector
   (`page_integrity`, `ocr/document.py:22`) and the cache already round-trips it
   (`webapp/artifact_cache.py:791-794, 846-852`). Add `page_extractor: list[str]` beside it, written
   by `ocr/pipeline.py` for whichever rung produced each page. This is what makes a mixed document
   (native pages + OCR'd pages) describable at all, and it is a strict addition to a record format
   that already carries a parallel per-page list — the cheapest honest step.
2. **Required now: the vocabulary entries** (F-7): a `SOURCE_PATHS` member per extractor, a
   `source_path_for` branch per model prefix, a `FREE_MODELS` entry, and a model-string prefix
   convention (`unlimited-ocr+…`, `paddle+…`) mirroring `native-pdf-text+<layout>`.
3. **Later: field-level attribution.** Only reachable through the structurer seam — `document_geometry`
   (#38) is the existing parameter, and OCR word boxes are the natural filling for it. A field that
   can name the page and the word boxes it came from is field-level provenance; anything short of
   that is a guess, and the audit will not propose a guess.

### 5.6 How the non-regression regime extends to an OCR-fed document

* **`tools/cohort_replay.py` must first be made deterministic (F-9).** `ColdCache._payload` needs a
  settings-key argument and a total order; the caller must ask for the partition the run of record
  actually used. Without this, `--expect-identical` and `--fail-on-regression` become
  non-deterministic the day a second OCR partition exists. This is the single blocking prerequisite.
* **Baselines are per-extractor, and a document may hold several.** An OCR-fed document has an
  offline partition (its historical, empty or unclaimed read) and an OCR partition. The
  non-regression question is asked **per partition**: the offline baseline must stay byte-identical
  (nothing about the offline ladder changed), and the OCR partition is new coverage with no
  baseline — so it can only ever be `newly validated`, never a regression, in its first run.
* **The protection rule is unchanged and is already structurally satisfied.** Every previously
  validated document was validated from a native or Tesseract read; the R trigger only fires where
  no text was produced (outcome `deferred`), and the U trigger only fires where the dispatch did not
  claim — and a validated document is by definition claimed. **No previously validated document can
  reach either trigger.** That is not a policy, it is a property of `discovery/runner.py:521-541,606`
  — and it is now also a MEASUREMENT: on the batch-9 run of record the intersection of the 2,625
  validated shas with the 136-document trigger set R ∪ U is **0** (independently derived by the
  adversarial review and confirmed here). True by construction AND true by measurement; it should
  still be asserted as a test before the rung is enabled.
* **The adoption test stays "the deterministic validator claimed it".** `discovery/runner.py:655-660`
  adopts the visual read only if `visual_payload is not None`. Keep it; do NOT relax it to "the OCR
  read looks better".
* **The cold run** gains an OCR tranche run with `--scanned-visual` over the trigger population only,
  compared against the batch-9 run of record with `--fail-on-regression`, with the OCR partition's
  documents named by sha in advance — the same discipline every coverage wave already follows.
* **`OCR_STAGE_VERSION` 5 invalidates the OCR partition**, so the first OCR-fed cold run is a cold
  run in the literal sense; budget for it.

### 5.7 Check by check: why the extractors cannot bypass or weaken any protection

The structural argument, stated accurately: **the extractors produce `StatementMarkdown` and nothing
else, and the validator's entry point takes a markdown string and a page list**
(`analysis/pipeline.py:1119-1123`). There is no confidence score, no extractor-supplied hint and no
bypass flag anywhere on the seam — and `corpus_gate.py:725-772` already polices that production
callers supply the `sheets` half.

**One correction to the earlier draft, which claimed a two-value seam with "no third channel".**
There IS a third channel: the extractor writes its `model` string into the first line of the
markdown (`ocr/document.py:38-41`). What closes it is not the seam's shape but a named guard —
`admissible_text` / `SOURCE_COMMENT_RE` (`analysis/parser_registry.py:194,197-215`), applied
centrally at `analyze_markdown`'s single parse seam since W3 FILENAME-BOUNDARY and pinned by
`tests/test_filename_boundary.py`. The safety conclusion survives; the reason had to be named,
because a guard can be escaped (a newline in the model string does escape it — F-4(b)) where a
missing channel cannot. Any Phase-2 extractor's model token must therefore be constrained to a
closed character class in the commit that introduces it. Check by check:

| protection | where it lives | why an extractor cannot weaken it |
|---|---|---|
| **reconciliation** | `analysis/reconcile.py` via `analysis/pipeline.py` | Computed from the parsed `Statement`, which is produced by a registered parser from the markdown. An extractor can only change what is printed on the page it reports; it has no channel to the reconciliation result. **The real exposure is the value-rewriting PAIR, F-1 and F-11** — an extractor that rewrites an amount changes the input to reconciliation, and F-11 does it inside the very transaction cell reconciliation sums. Resolving the pair (OQ1) closes it; two further chain members are unproven either way and are covered by §5.7's census. |
| **ledger identity** | `analysis/reconcile.py`, `analysis/balance_by_date.py` | Same seam. Identity is recomputed from the rows the parser read; a lost row makes identity FAIL, not pass. The failure direction is safe. What is NOT safe is a rewrite: F-1 removes a row *and* nothing else, so the remainder can still look consistent; F-11 leaves the row count intact while changing which figure the row carries, which is the harder of the two to detect downstream. |
| **transaction coverage** | `analysis/metrics.py`, coverage ratios | Coverage is a ratio of parsed rows to the statement's own printed counts/totals. An OCR read that loses rows lowers coverage and fails; it cannot raise it, because the denominator is read from the same page. |
| **account boundaries** | `analysis/multi_account.py`, the L-1 rule | Boundaries come from the document's own printed partition. An extractor that merges or splits sections produces ambiguous boundaries, and Q10's ruling fail-closes on ambiguity. Adopting an OCR read that changes the account count on a document that previously published accounts must be a STOP, not a substitution — the U trigger cannot reach such a document (it was claimed), so this is a guard against a future third trigger. |
| **page completeness** | `analysis/pipeline.py:427` (`assess_document_integrity`), sheet reconciliation `:640-651`, flag `:205` | **Strictly stronger on an OCR read.** The OCR rung rasterizes every page (`ocr/rasterize.py:12`, `ocr/pipeline.py:131`), so `len(pages)` is the PDF's true page count, whereas a native read's page list is whatever MuPDF produced. The check fail-closes when `sheets` is absent (`:623-628`), and `corpus_gate.py:725-772` asserts every production caller supplies it. `discovery/runner.py:613,653` already pass the visual read's own `sheets`. |
| **statement period** | the parsers' period readers; ADB doctrine | Read from printed captions. A degraded read either finds the caption or does not; not finding it refuses. There is no path by which an extractor supplies a period. |
| **explicit currency evidence** | `analysis/schema.py:94-100,159-166` (`CurrencySource`), `CURRENCY_DOCTRINE.md` | `currency_source` is a closed provenance vocabulary and none of its members is an extractor. An OCR read can only make printed currency evidence *harder* to find, which lands on `schema_default` / a refusal, never on a stronger claim. |
| **ADB** | `analysis/adb.py`; one calendar-day ADB over the printed period | Requires daily evidence covering the printed period; missing days withhold. A lossy read withholds. Again only a rewrite could forge coverage: F-1 by collapsing a run of repeated daily balances — precisely the shape it collapses — and F-11 by substituting a cell's second money value for its first in a daily table that prints two. |
| **integrity checks** | `assess_document_integrity`, `analysis/pipeline.py` flags/notes | Flags are raised from the text and the sheet list. An extractor cannot suppress a flag; it can only produce text that does not trigger one, which is indistinguishable from a document that does not have the defect — except for `missing_declared_statement_page`, which the OCR read strengthens (above). |
| **multi-account independent validation** | `analyze_document` → per-account validation (`analysis/pipeline.py:1119+`), Q1/Q5/Q10 | Unchanged: each account is validated on its own by the same validator over the same markdown. The extractor is upstream of the partition, so it cannot make one account borrow another's evidence — it can only fail to produce a section, which surfaces as `sibling_account_omission_detected` / `completeness: partial` under Q10, never as a silent promotion. |

**Summary of the exposure — CORRECTED after adversarial review.** Of the ten protections, nine are
structurally out of the extractors' reach, and page completeness is strictly stronger on a rasterised
read. All ten share the same exposure, and it is **the value-rewriting sites inside
`ocr_client.postprocess`** — the places where the OCR path writes a value rather than reading one.
There are **at least two**. An earlier draft of this section claimed there was exactly one, and that
claim was false:

| site | what it rewrites | scope |
|---|---|---|
| **F-1** `collapse_repeated_amounts` (`:63-82`, called at `:413`) | deletes every amount in a whitespace-separated run of 3+ money tokens in which one value repeats 3+ times — including distinct amounts that merely sit adjacent | bare text, **outside** table cells |
| **F-11** `fix_amount_column_bleed` (`:129-171`, called at `:416`) | moves the leading money value of a two-money Amount cell into the description and promotes the trailing one | **inside** `<td>` cells |

The two are complementary in scope, which is exactly why "confine the collapse to table cells" is not
a fix: it moves one rewrite into the other's territory. Two further members of the same chain
(`split_fused_header_row` `:174`, `repair_fused_amount_table` `:273`) restructure rows and re-emit
cells; neither the review nor this audit could construct a value-losing input for them, and neither
claims one exists.

**Phase-2 deliverable, owed before any OCR-fed document is validated:** a per-function rewrite census
of all six members of `postprocess` (`ocr/ocr_client.py:409-416`), each characterised as
*reads-only*, *restructures-without-writing*, or *writes a value*, with a synthetic fixture
demonstrating the answer for each. Until that census exists the whole chain must be treated as
value-writing. This audit's position — that no OCR-fed document may be validated until the rewrites
are ruled — was reached correctly, but on an incomplete inventory of the reason; the inventory is now
two proven sites plus a declared unknown, rather than one function.

### 5.8 Re-measuring the Q3 class on OCR'd input (F-8)

The class `printed_pair_coincides_and_no_row_printed` was ruled in to bound **OCR row loss** and has
been measured only on six `native-pdf-text` documents. The re-measurement, as a later card:

1. **Seed = the same six `guardian_cu` sections.** The population is emitted by the design's own
   instrument (`tools/l1_split_prototype.py::_population` via
   `tools/q3_corroboration_probe.py`), never named by hand; `--expect-sections 6` already makes a
   different count a STOP (exit 2).
2. **The obstacle is stated in the backlog and is real:** the cold cache holds one `ocr`-stage
   artifact per document and **no PDFs** (measured: 0 PDF files in 5,997). So the six cannot be
   re-read from the cache — the re-measurement needs the archive documents themselves, and it is
   therefore an archive-present card, not a cache-replay card.
3. **Produce a second, OCR'd read of each of the six** through `parse_statement(force_ocr=True,
   allow_visual_ocr=True)` at `OCR_STAGE_VERSION` 5, into its own cache partition. Nothing about the
   native artifacts changes; the six keep their existing baselines.
4. **Run `tools/q3_corroboration_probe.py` unchanged against the OCR'd text.** It is the oracle and
   it must not be widened to make a witness appear (its own `:29-32`). Its self-attack suite
   (`:57-64` — the mis-read cent, the removed column caption, the unlocatable row, the absent
   roll-up, the one printed dated row) runs on the OCR'd sections too; a mutant that stops killing
   on OCR'd input is itself the finding.
5. **The result is a 6 × 7 table on OCR'd input, reported beside the native one.** Cells that PASS on
   native and FAIL on OCR are the class's real cost and the number the ruling was actually asking
   for. Any `UNDECIDABLE` cell (exit 3) blocks OCR-fed reliance on the class.
6. **Until that table exists, no OCR-fed document may rely on the class.** Concretely: the omission
   class is admitted only when the document's extractor model is `native-pdf-text*`; an OCR-fed
   section falls outside it and fail-closes unless another ratified class applies. That is a
   one-predicate gate, it is the conservative direction, and it should be wired in the same card that
   enables the rung — not the one that measures it.

---

## 6. Open questions for Gustavo

1. **THE VALUE-REWRITING PAIR (F-1 and F-11) — how should the OCR cleanup chain be resolved?**
   *Re-posed after adversarial review; the earlier version of this question asked only about F-1 and
   recommended confining it to `<td>` cells, which is unsafe because F-11 already lives there.*

   Two functions in `ocr_client.postprocess` provably write values rather than reading them:
   `collapse_repeated_amounts` (`:63-82`), which deletes every amount in an adjacent run of bare
   money tokens where one value repeats three or more times — including distinct amounts it never
   saw repeat; and `fix_amount_column_bleed` (`:129-171`), which moves the leading money value of a
   two-money Amount **cell** into the description and promotes the trailing one. Their scopes are
   complementary — one outside table cells, one inside — so neither can be made safe by relocating
   it into the other's territory. Both were written for real Unlimited-OCR degeneracies; neither has
   ever run on a real page. The options:

   * **(a) Remove both.** Degenerate pages then fail or land as truncation-flagged failures, which
     is the fail-closed direction. Costs whatever recall the two repairs would genuinely have won —
     an amount nobody has measured, because the rung has never run.
   * **(b) Scope both behind a per-extractor flag**, off by default, with a committed fixture per
     transformation proving on SYNTHETIC input exactly what each function does and does not change,
     and a page that either function touched carrying an explicit flag so it can never be silently
     adopted. This is the option that keeps the repairs available without letting them act
     unmeasured.
   * **(c) Quarantine the whole `postprocess` chain for Phase 2** — the visual rung emits raw model
     output, no cleanup runs, and the chain is re-admitted function by function only as the rewrite
     census in §5.7 clears each one. The most conservative option, and the one that makes the
     census's completion the gate rather than a promise.

   The audit recommends **(c) as the Phase-2 default with (b) as the exit path**: quarantine now,
   re-admit each function on the evidence of its own fixture. It no longer recommends any option
   that treats `<td>` cells as a safe harbour. **No OCR-fed document may be validated until this
   pair is ruled**, and the per-function rewrite census of all six chain members (§5.7) is the
   deliverable that makes the ruling actionable.
2. **Does the no-statement-hardcodes guard extend to `ocr/`?** F-3 is issuer-specific behaviour
   (a named issuer, a masked rectangle, five tuned render variants) in the intake layer, where
   `tests/test_no_statement_hardcodes.py` does not reach. Declare it as permitted intake furniture,
   or bring `ocr/` into scope?
3. **The `$0` guarantee (F-4): enforce it in code?** An `OCR_BASE_URL` allowlist would make the
   invariant that `ocr/availability.py:5-6` asserts actually true. It would also make a deliberate
   paid experiment require an explicit, recorded opt-in. Ruling wanted before the rung is enabled.
4. **Trigger T (truncation-flagged Tesseract reads):** admit it as a third escalation trigger, or
   keep truncation surface-only? It is the only trigger that would grow the residue beyond the
   measured 136.
5. **PaddleOCR's role:** first-choice free extractor for the residue (before Unlimited-OCR, since it
   needs no GPU), or a second opinion only where Unlimited-OCR's read goes unclaimed? The two orders
   have very different cost and very different provenance shapes.
6. **The RunPod half of `README.md`** documents a rented, per-hour, remote GPU. Delete it as a
   pre-deterministic remnant, or keep it as a documented escape hatch?
7. **Delete or keep the four legacy scripts** (#31–#34)? They are unreferenced, they predate the
   deterministic shift, and two of them can reach the OCR endpoint with default flags.
8. **F-9's fix is a prerequisite, not a nice-to-have** — confirm that `tools/cohort_replay.py` may be
   modified in Phase 2 despite being a batch-9 instrument, since the frozen baseline's replays would
   be unaffected (one artifact per input today) but every future one depends on it.

---

## 7. Reproduction

```
python tools/ocr_legacy_census.py --tree
python tools/ocr_legacy_census.py --cache-index .claude/recovery/webapp_data_train8_cold
```

Headline numbers and where each comes from:

| number | source |
|---|---|
| 447 first-party modules; 142 reachable from 8 production entry points | `--tree` |
| per-component LOC / last commit / commit count / importers / reachability | `--tree` |
| ocr stage: 3,364 rows, 3,364 distinct inputs, 1 distinct settings key, 0 multi-artifact inputs | `--cache-index` |
| analysis stage: 2,630 rows, 2,630 distinct inputs, 0 multi-artifact inputs | `--cache-index` |
| the single settings key = `(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False)` | `ocr_settings_key()` recomputed at this tree and compared to the index's distinct key |
| `visual_rung = not_attempted` and `cache_visual = bypass`, both 3,506/3,506; `source_path` and `source_model` distributions; outcome-class splits; R = 13 `deferred_visual_ocr`; U = 123; R ∪ U = 136, overlap 0; validated ∩ (R ∪ U) = 0; 2,625 distinct validated shas of 3,380 | `rows.csv` of the **batch-9 run of record**, `discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a` |
| the same intake-provenance columns on the batch-8 run, for the equivalence claim | `rows.csv` of `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` |
| F-1 demonstrated | three money tokens on three consecutive lines → one token; the same three inside `<td>` cells → unchanged; three DISTINCT amounts → unchanged; and `[a,a,a,b,c]` on five consecutive lines → `[a]`, i.e. two distinct amounts DELETED (`ocr.ocr_client.collapse_repeated_amounts` and `postprocess`, synthetic input, no document) |
| F-11 demonstrated | an Amount cell holding two fused money values → leading value moved into the description, trailing value promoted to the row's amount (`ocr.ocr_client.fix_amount_column_bleed`, synthetic input, no document) |
