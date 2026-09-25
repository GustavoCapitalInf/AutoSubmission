# Re-analysis of Saved Statements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A saved statement analysed under older rules can be re-analysed on demand: `POST /analysis/<job_id>/reanalyze` runs its stored PDF through the worker's own read and analysis path with its reading served from the artifact cache only (a statement whose reading is not cached is refused, and no reading rung runs), replaces the job's analysis in place (same job id, same place in Recent), writes the replaced analysis to the audit log first, replays the analyst's revenue decisions where their posting is unchanged, reports the ones that need redoing and the ones a rule now decides, and the dashboard's Re-analyze button calls it and redraws from the answer.

**Architecture:**
- `analysis/revenue.py` gains `record_serialized_revenue_review`, the review writer without the rebuild (`apply_serialized_revenue_review` becomes that writer plus one rebuild, unchanged in behaviour), so the replay can write every decision onto one copy and rebuild once.
- `webapp/reanalysis.py` (new) holds the two halves of the work:
  - `replay_reviews` re-applies `review_decisions` rows onto one copy of the fresh analysis, only onto the one row whose account number, location, description and amount equal the decision's recorded prior state, and rebuilds the revenue views once. A decision the analyst has since redone is not reported again, and a decision on a row a rule now decides is reported apart.
  - `rerun_analysis` calls `webapp.worker.run_job` itself, unchanged, against a stand-in job store. The stand-in reads through the real artifact cache, but its reading is cache-only: where the worker would read the statement (a reading cache miss, a cached reading that fails its own checks, a reading rung starting, a live read streaming), the run is stopped before any reader runs or any page goes to a remote model (Decision 2 states the one narrow limit). It writes nothing into the artifact cache, whose one writer stays the upload queue's worker. It captures every job-state write, so the saved job is not written until the route accepts the new analysis.
- `Storage.record_reanalysis` writes the audit row (holding the replaced `analysis_json`, verbatim) and then updates the job row, in one transaction. `JobStore.apply_reanalysis` wraps it and updates the in-memory job.
- The route follows the review routes' rules: JSON only, the statement's review lock, fixed refusal texts, `_masked(_displayed(...))` on the way out. It runs on the request thread: with no reading rung it needs no place in the upload queue's single worker slot (`webapp/app.py:116-120`), which exists to keep two OCR jobs from running at once.
- `webapp/static/app.js` gains a click handler for `#reanalyzeButton`, and every revenue review (the bulk bar and the row buttons) waits while a re-analysis is in flight. The button and the notice around it are S4's markup (C8).
- `tools/l1s3_surface_census.py` declares the new payload readers, as `tests/test_l1s3_census.py` requires of every production function that reads the `statement` key.

**Tech Stack:** Python 3.14 (`C:\Python314\python.exe`), pytest 9, Flask, SQLite (`webapp/storage.py`), vanilla JS (`webapp/static/app.js`, tested in node through `tests/webapp_js_harness.py`).

## Global Constraints

- Only MCA/revenue-based funders and equipment financing are lenders (`confirmed_lender`). Nothing else enters `lender_*`, `withholding_*`, `eligible_deposits` (except the D1 proceeds exclusion) or the package `decision`.
- Every flag group has a Settings key, default `True`, applied at serving time. Unticking hides only (D7).
- Counterparty names and aliases live **only** in `analysis/classification_registry.py`. The guard is `tests/test_no_statement_hardcodes.py:85-87`, and there is no second exempt module.
- **Privacy:**
  - Tests use fabricated descriptors only.
  - Never commit statement text, amounts, account numbers, dates or customer names.
  - Commit messages quote no statement values.
  - Re-pinned regression expectations use derived totals only.
- `CLASSIFICATION_VERSION = "5.0"` and `ANALYSIS_STAGE_VERSION = 19` land in the same commit as the classifier change (S2).
- Run tests with `C:\Python314\python.exe -m pytest tests/<files> -q -p no:cacheprovider`. **Always pass paths under `tests/`**: a bare `pytest` also collects `discovery_reports/`.
- Known failure that predates this work, and must not be attributed to it: `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`.
- Write or patch Python with the Write/Edit tools, not with Bash heredocs (the Bash tool mangles backslashes here). Restart Flask after template edits.
- Subagents: Opus 5.5 only, never Fable. Each service runs on its own branch, and only the orchestrator merges.
- No payee or brand literals in `webapp/static/app.js` (`tests/test_revenue_classification.py:812-844`, `tests/test_lender_insurance_classification.py:566-584`). Every `formatMoney(` call passes an explicit currency (`tests/test_package_currency.py:773-796`).

**S5-specific constraints:**
- Branch `ld-s5-reanalysis`, from `lender-detection`. Never merge it; the orchestrator does.
- **Sequencing.** Tasks 1-10 need only the interface contract. Task 11 needs S2 **and S3** merged into `lender-detection`. The master plan's order table says so: S5 "finishes on top of S2 and S3", and the merge order is S1 → S2 → S3 → {S4, S5} ("What the orchestrator must ratify", item 3, adopted).
- `webapp/worker.py`, `vlm/pair.py` and `webapp/artifact_cache.py` are **not modified**. The re-analysis calls `run_job` as it is.
- **A re-analysis runs no reading rung.** Its reading (every rung of the worker's reading ladder, native text included, and the visual pair) is served from the artifact cache, or the re-analysis is refused (Decision 2). No OCR engine runs and no page goes to a remote model; the one model-identity request Decision 2's known limit names sends no statement content. What does run on the request thread is the worker's local preflight: `run_job` calls `inspect_pdf(pdf_bytes)` (`webapp/worker.py:633-635`; `ocr/inspect.py:185`), a native-text profile of the PDF, which is not OCR and not remote. Request threads already do local PDF work of that kind: `/render` rasterizes pages (`webapp/app.py:2184`). So the re-analysis does not compete with the upload queue's worker for OCR.
- **A re-analysis writes nothing into the artifact cache.** Today the upload queue's worker is the cache's only writer (`webapp/app.py:149` is the only `run_job` caller, and no route calls a `cached_*` or `put_*`). The cache writes each entry through one fixed temporary file, `<key>.json.tmp`, and then `os.replace`s it (`ArtifactCache._write_payload`, `webapp/artifact_cache.py:1135-1141`). So two threads writing one entry at once make one of them raise (`FileNotFoundError`, or `PermissionError` on Windows), and on the worker's side that fails an upload: a failed `put_analysis` becomes the upload's durable analysis error through `_analyze_doc`'s `except` (`webapp/worker.py:395-402`), and a failed `put_report` (`cached_report`, `:343`, outside that `try`) or `put_ocr` (`cached_ocr`, `webapp/artifact_cache.py:1457`) fails the whole job. These three are the only cache writes the worker makes (`webapp/artifact_cache.py:1457, 1522, 1544`). `_CacheOnly`'s `put_ocr`, `put_analysis` and `put_report` therefore write nothing (Decision 2; pinned in Task 7). The new analysis is saved with the job, and the next upload of the statement caches it.
- **The saved job is never written before a new analysis is accepted.** A refused or failed re-analysis leaves `jobs.analysis_json`, `jobs.analysis_error`, `jobs.status` and the in-memory `Job` exactly as they were.
- **No exception text crosses a boundary.**
  - `webapp/reanalysis.py` and the new route never bind a caught exception (`except X:` with no `as`). `tests/test_worker_privacy.py::test_the_webapp_exception_ledger_is_complete` scans every `webapp/*.py`.
  - Every `reason` returned is text the worker already publishes and serves (`_stage_failure`, `_analysis_failure`, its no-native-text notice), or one of this plan's two fixed texts, `READING_NOT_CACHED` and `READS_DIFFERENTLY`.
- No schema migration (`SCHEMA_VERSION` stays 4). The re-analysis writes one `audit_log` row and never writes to `review_decisions`: a replay is not an analyst decision.
- A re-analysis writes no telemetry record. The stand-in store has no `storage`, so `telemetry.emit.open_sqlite_sink` (`telemetry/emit.py:109-113`) opens a null sink.
- **The surface census.** `tests/test_l1s3_census.py::test_the_census_holds_at_this_tree` fails for any production function that reads the payload key `statement` and is neither declared in `tools/l1s3_surface_census.py`'s `READERS` nor excused in its `EXCUSED` (`tools/l1s3_surface_census.py:442-460`). Tasks 3 and 4 keep it green, and every run step that touches a reader includes it. (It was in none of the master plan's three selections, which is why the first draft of this plan broke it unnoticed. The master plan now runs it as its own "Surface census" item.)
  - Run it from a worktree or clone that has no `discovery_reports/`. The census sweeps every `*.py` under the checkout, and the main checkout's gitignored `discovery_reports/` holds scratch copies of production modules, so there it fails before any S5 change (`2 failed, 20 passed`, measured at `4f219cd`). Without `discovery_reports/`, it holds at `4f219cd`.
- **Flag groups.** S5 names no flag group, state, settings key, label or registry in its production code: the replay and the replacement carry whatever the analysis stage produced. Task 11 pins all eleven groups, by iterating `FLAG_GROUPS`, including premium financing's special case (an `insurance` row that also carries the flag).
- `app.js`:
  - S5 adds **no `els` entry and no markup**. `#rulesOutdatedNotice` and `#reanalyzeButton` are S4's (C8).
  - S5 looks the button up with `document.getElementById("reanalyzeButton")` and binds with `?.`. It is inert until S4's markup exists, and a top-level `const` would collide with S4's code.
  - S5 owns the listener and deliberately adds no `els.reanalyzeButton`, so the two branches never both edit the `els` literal next to S4's `els.rulesOutdatedNotice`. The lookup by id returns the same element.
  - The S4 plan agrees in all three places that name the split: its Global Constraints ("Split with S5": "Neither plan adds `els.reanalyzeButton`, and S4 adds no listener on the button"), its outdated-notice task (Task 10), and its self-review (item 4, "The split with S5"). S4's code references neither name.
  - Besides its new block, S5 edits four existing lines, all outside S4's edit sites and outside `app.js:1612-2271`: the review flags (`:804-806`), `syncBulkReview`'s `held` (`:837`), and the guards of `submitBulkReview` (`:933`) and `submitRevenueReview` (`:4162-4163`).
  - Keep the block outside `app.js:1612-2271`, which `tests/test_webapp_accounts_view.py:23-25` executes on its own.
  - No 60-99 numeric literal (`tests/test_webapp_confidence_label.py:103-134`).
- **Commits.** Each commit step gives the exact `git add` paths, the subject line and the attribution lines as a second `-m`, as the S4 plan does:
  - The `Co-Authored-By` line is fixed for an Opus 5.5 (1M context) cell.
  - The `Claude-Session` URL belongs to the session that commits. Take it from that session's system reminder, which is the only place it exists, and put it where the step shows `<the Claude-Session URL from your system reminder>`.
  - If the system reminder gives different lines, use its lines.
  - Messages never quote statement values.

---

## Decisions this plan makes (contract gaps it had to close)

C9 and §8.6 do not settle these points. Each is fixed below and pinned by a test. The owner or the orchestrator may overrule any of them at review; the ones that change C9 or need an owner ruling are listed again under "What the orchestrator must ratify".

1. **"The same read/analyze path the worker uses".**
   - `rerun_analysis` calls `webapp.worker.run_job` with the job's own `force_ocr` and `parse_mode`, pinned by two tests (Task 6): a deterministic-mode job is re-run in deterministic mode, and a job uploaded with Force visual OCR is re-run through the visual pair's path. A re-run in the wrong mode could make the hosted analysis call the operator did not choose for that job.
   - It runs against `_CapturedJobStore`, a stand-in exposing exactly the methods `webapp/worker.py` calls: `cache`, `get`, `set_status`, `set_stage`, `append_page_live`, `set_page_live`, `set_result`, `set_error` and `record_cache_hit`. These are every `store.` call in the module, verified at `webapp/worker.py:416, 576, 591, 611-612, 641-647, 685, 710, 720, 725-727, 736, 764, 780-782`.
   - The branching of every mode (deterministic, auto, forced visual pair, pair fallback) is therefore the worker's own, and nothing is duplicated.
   - Cache hits are still recorded as `cache_hit` audit rows on the real job. That is the proof that the reading was served from cache.
2. **The reading is served from the cache, or the re-analysis is refused (spec §8.6.2).** *Owner ruling requested:* this plan chooses cache-only; the owner may choose re-reads through the upload queue's worker slot instead (below).
   - **Why not re-read.** The request thread is outside the upload queue's single worker slot, and "the slot is what keeps two OCR jobs from running at once on this host" (`webapp/app.py:116-120`; `_process_job_queue`, `:140-160`, is the only other `run_job` caller). A re-read could run local OCR beside the queue's worker, or send the statement to the remote visual pair when `OCR_ALLOW_VISUAL_PAIR=1` (`webapp/worker.py:561-587, 700-703`), all while holding the statement's review lock. A non-deterministic reader's new text would then differ from the saved one almost surely, and the run would be refused anyway.
   - **What still runs.** The worker's preflight, `inspect_pdf` (`webapp/worker.py:633-635`), profiles the PDF's native text on the request thread, as it does before every read; it is local and is not OCR. The analysis stage runs again, as a re-analysis must.
   - **How, without touching `worker.py`.** The stand-in's `cache` is `_CacheOnly`, a view of the real `ArtifactCache` whose `get_ocr` stops the run on a miss. `cached_ocr` asks `get_ocr` first and computes only on a miss (`webapp/artifact_cache.py:1418, 1447-1448`), and both the ladder (`_read_document`, `webapp/worker.py:513-533`) and the visual pair (`_read_visual_pair`, `:581-586`) read through `cached_ocr`. So on a miss neither the reader nor any remote model is called.
   - **It writes nothing into the cache.** `_CacheOnly`'s `put_ocr`, `put_analysis` and `put_report` write nothing, so the upload queue's worker stays the artifact cache's one writer: a request-thread write of an entry that an upload of the same statement is writing could fail that upload (Global Constraints). The new analysis is saved with the job, and the next upload of the statement caches it. A cached pair reading that failed its own checks and that the pair answered again from its own local evidence (below) stays in the cache as it was, for the next upload to repair. Task 7 pins all three writes.
   - **This guard is the only one on the visual pair's path.** The pair does work before it names its first step: it answers from its own local evidence index with no `progress` call (`vlm/pair.py:688-697`), or asks both model servers for their model lists and writes the PDF to its evidence directory (`vlm/pair.py:698-701`) before `report('visual_pair_rendering')` (`:702`). Task 7 pins `_CacheOnly` on its own: a reader that names no stage, and a fabricated visual pair that names no step, are both refused on a miss and never called.
   - **The backstop.** A cached reading that fails its own round-trip check is treated as a miss and read again (`webapp/artifact_cache.py:1419-1446`); `get_ocr` has already answered a hit by then. The stand-in therefore also stops the run on any stage other than `"analyzing"`, the one stage the worker names outside a read (`webapp/worker.py:685, 725`). The ladder names each rung just before running it (`ocr/pipeline.py:95, 114, 157, 187`, through `webapp/worker.py:640-641`); an exception raised there reaches `run_job`'s own boundary, since `_notify_stage` (`ocr/pipeline.py:18-20`) and `parse_statement` catch nothing. `append_page_live`, called only by a live read (`webapp/worker.py:643-644`), stops it too. Task 7 pins both, each with the other out of the way.
   - **Known limit of the backstop, for the owner.** It can only stop a read at the first step the read names or streams, and the visual pair does two things before its first step. This happens only when all of these hold at once:
     - the pair is enabled (`OCR_ALLOW_VISUAL_PAIR=1`) or the job was uploaded with Force visual OCR, and its customer-data fence is open (`check_remote_authorization` runs first, `webapp/worker.py:567`);
     - the cached pair reading fails its own hash check;
     - the pair's own local evidence index for this PDF and configuration is gone too. When that index exists, the pair answers from it with no network call (`vlm/pair.py:688-697`); that answer is a cached reading, and the re-analysis goes on with it.

     Then the pair asks each of its two model servers for its model list (`_check_model`, a `GET /v1/models`, `vlm/pair.py:88-95, 698-700`), which sends no statement content, and writes the PDF into its private local evidence directory (`vlm/pair.py:701`). It then names `visual_pair_rendering` (`:702`), and the re-analysis stops there with `READING_NOT_CACHED`: no page is rendered or sent. Closing this needs a hook inside `vlm/pair.py` or `webapp/artifact_cache.py`, which S5 does not touch.
   - **Known limit of sharing the cache, for the owner.** A re-analysis writes no cache entry, but it reads them, and one overlap with an upload remains:
     - On Windows a file that is open for reading cannot be replaced: `os.replace` raises `PermissionError` (checked on this host).
     - The worker replaces the file of an entry that is already indexed only when it repairs a cached reading that failed its own checks (`cached_ocr`, `webapp/artifact_cache.py:1457`). Every other entry is written before its index row exists (`ArtifactCache.put`, `:1166-1191`), and a re-analysis opens a file only through its row (`ArtifactCache.get`, `:1145-1164`).
     - So the overlap needs the same statement uploaded again while its cached reading is drifted, and the re-analysis reading that entry in the instant the upload writes its repair. The upload then fails with the worker's own stage failure; the drifted entry is left as it was, and the statement can be uploaded again.
     - In the backstop's limit above, the pair's evidence write (`_blob`, `vlm/pair.py:70-81`) creates its file exclusively. An upload of the same statement writing that file in the same instant can find it half-written and stop with `visual_pair_evidence_changed`.
   - A stopped run answers 422 with the fixed reason `READING_NOT_CACHED`: "the reading this re-analysis needs is not cached, and a re-analysis only analyzes a reading already made; upload the statement again instead". This covers an OCR cache that was pruned, a new OCR toolchain (a new settings key), and a statement that now needs a reading it never had (the pair fallback, where the deterministic path claimed it before).
   - The analysis stage's one hosted call stays behind the operator's opt-in fence (`analysis/pipeline.py:1065-1076`), exactly as for an upload.
   - **The alternative, if the owner prefers re-reads:** hand the run to `_enqueue_job`'s single slot, answer 202, and let the dashboard poll. That changes C9's synchronous 200 and is out of this plan.
3. **A re-run that produces no analysis to save** (a pipeline refusal, a crash, `READING_NOT_CACHED`, or `READS_DIFFERENTLY`). C9 lists no status for it. The route answers **422** `{"error": "no new analysis was saved; the saved analysis is unchanged", "reason": <published reason>}`, and nothing is written. The error text holds whether no analysis was produced or one was produced and refused.
   - `READS_DIFFERENTLY` ("under the current rules the analysis comes from another reading of the statement than the saved one") is the refusal of an analysis made from a cached reading other than the one the saved analysis was made from: the worker chose the other of its deterministic and visual-pair paths (`webapp/worker.py:684-703`). The saved analysis and its source view (`jobs.markdown`, `jobs.html`) must describe one reading.
   - The test is `markdown != job.markdown`. It cannot refuse the same reading for its formatting: the worker's markdown is `doc.to_markdown()` (`webapp/worker.py:341`), which is kept byte-stable on purpose because the committed corpus artifacts are pinned to it (`ocr/document.py:222-238`). It has not changed since 2026-08-06.
4. **Order of the C9 refusals:**
   1. 400 `{"error": "the request must be a JSON object"}` for a body that is not a JSON object. This is the review and settings routes' CSRF rule, not in C9.
   2. 404 `job not found`.
   3. 409 `job is not finished` (any status other than `done`).
   4. 409 `the original PDF is not stored`.
   - A `done` job whose analysis is `None` (it stored an `analysis_error`) may be re-analysed.
5. **"Same account" for the replay, and what is reported back.** *Owner ruling requested* on the last bullet group ("Decided by a rule").
   - `review_decisions` has no account column (`webapp/storage.py:218-226`), but every row's `prior_state` is the posting's classification record at decision time (`webapp/jobs.py:63-100, 330-338`), and that record carries the statement's account number (`account`).
   - A decision is replayed only when exactly one row in the new analysis, across every account, matches it on all four of:
     - `source_location`;
     - `account` (the statement's account number), so a deposit alike in two accounts is two postings (pinned in Task 4);
     - `original_description`;
     - `amount` (to the cent).
   - The index of that row's account is what is passed to the review writer.
   - Of several decisions on one such row (the same four fields), the **latest** is the one replayed. Each decision sets the state outright.
   - A latest decision of `reset` is neither replayed nor counted. A fresh analysis is already pending, so nothing needs redoing.
   - **Needs redoing** (`reviews_not_replayed`): no row or several rows match, and no later decision **redid** it. A later decision redid it when it was made on the same account number (pinned in Task 5) and either the same location (the analyst decided that row again, whatever it printed by then) or the same posting wherever it sat by then (the same description, amount and date). Without this, an analyst's redo on a changed or moved posting would leave the old decision reported as needing redoing at every later re-analysis.
     - Redoing is judged only for decisions that do not replay. It never stops a decision from replaying: two postings of one account alike in description, amount and date (two identical deposits on one day) keep their own decisions. The one cost of that likeness is that a decision on one of them whose row changed may be taken as redone by a decision on the other, so the count says one review too few; no decision is lost.
     - The date is part of "the same posting" here, although the replay match (the spec's four fields) leaves it out: without it, a decision on a recurring deposit would be taken as redone by a decision on the same deposit another month.
   - **Decided by a rule** (`reviews_decided_by_rules`): exactly one row matches, but it no longer awaits review, because a rule of the current analysis decides it. Under the 5.0 rules that is a credit from a payee of any `FINANCING_STATES` group (D1: lenders, alternative positions, lines of credit, bank loans, vehicle financing, mortgages, personal loans, floor plan, factoring), which is financing proceeds, and a credit from a premium-finance payee, which keeps the insurance credit treatment (§4.2). The review writer refuses such a row (`analysis/revenue.py:250-253`), so the analyst could not redo the decision. It is not replayed and not counted as needing redoing, but **it is reported back**: spec §8.6.5 says anything that cannot be replayed is reported, and D12 says nothing re-labels silently. The route's answer carries `reviews_decided_by_rules`, the audit detail lists the ids, and the notice says "N reviews are now decided by the rules" in amber, with the notifications opened, even when the rule agrees with the analyst.
     - *The alternative, if the owner prefers:* count these in `reviews_not_replayed` ("N reviews need redoing"). The plan does not, because the analyst cannot redo them: the row's review buttons are gone.
   - A decision whose prior state cannot be read is counted as needing redoing, unless it is a `reset`.
   - Every replayable decision is written onto **one** copy of the analysis, whose revenue views are rebuilt **once**, after the last (Task 3's writer, Task 4's `_applied`). A decision the writer refuses is refused alone (it checks everything before it writes). When the rebuilt views do not hold, which no decision can cause (a posted credit with no valid classification record), every decision counts as needing redoing and the analysis is kept exactly as the analysis stage produced it, as the review routes keep their saved analysis when a rebuild refuses (`webapp/app.py:2338-2343, 2410-2414`). `replay_reviews` never changes the analysis it is handed.
   - `reviews_replayed`, `reviews_not_replayed` and `reviews_decided_by_rules` count decisions, one per posting.
   - A replayed record keeps the analyst's own `decided_at` as `revenue_reviewed_at`.
6. **What "replaces the job's analysis" writes.**
   - It writes `jobs.analysis_json` and clears `jobs.analysis_error`. A run that produced an analysis has none.
   - `markdown`, `html`, `parse_model`, `status`, `created_at` and `finished_at` are untouched.
   - The audit row has `event_type = "reanalysis"` and `detail = {"reviews_replayed": [ids], "reviews_not_replayed": [ids], "reviews_decided_by_rules": [ids], "previous_analysis_json": <stored text, verbatim>, "previous_analysis_error": <text or null>}`.
   - The route's answer keeps C9's keys and adds `reviews_decided_by_rules` (Decision 5).
7. **The per-job lock** is the review routes' `_review_lock(job_id)` (`webapp/app.py:2277-2286`). It is held from reading the job to saving the new analysis. With no reading rung (Decision 2) that is the time of the preflight, the analysis stage and the replay; the replay costs one copy and one rebuild of the revenue views however many decisions there are (Decision 5).
8. **Dashboard status messages** go through the existing `notify(text, tone)`:
   - green when every review was kept;
   - amber when any needs redoing or is now decided by the rules, with the notifications opened;
   - red on refusal, with the notifications opened.
   - While the request is in flight, the button is disabled and labelled "Re-analyzing...". Its label is restored afterwards.
   - When a package is on screen, the button does nothing (`currentJobIds.length > 1`).
9. **Reviews wait for a re-analysis in flight.** The answer replaces the rows a decision names, so while `reanalysisBusy` is set the bulk-review bar is held (`syncBulkReview`), and `submitBulkReview` and `submitRevenueReview` send nothing. A re-analysis does not start while a batch or a row's decision is in flight either. The server's lock (Decision 7) only orders the requests; it cannot tell that a decision was made on the rows the re-analysis replaced.
10. **Known limit, for the owner: a second tab.** A tab still showing the old analysis sends its reviews by account and location only (`webapp/app.py:2313-2358`). After a re-analysis in another tab, such a review lands on whatever row now sits at that location. Closing this needs a revision token on the review routes (the analysis the decision was made on), which is beyond S5 and C9.

## What the orchestrator must ratify

This plan extends or changes the master plan in the places below. Each is implemented and tested as written. Items 1, 3 and 5 are now written into the master plan (its C9, its order table, and its "Surface census" item); item 2 still waits for the owner, and item 4 is a note for the rebase.

1. **C9 amendment** (now in the master plan's C9). Proposed text, to append to C9:
   - The 200 body also carries `"reviews_decided_by_rules": int` (Decision 5).
   - 400 `{"error": "the request must be a JSON object"}` for a body that is not a JSON object (Decision 4).
   - 422 `{"error": "no new analysis was saved; the saved analysis is unchanged", "reason": str}` when the re-run produces no analysis to save (Decision 3). `reason` is text the worker already publishes, or `READING_NOT_CACHED` / `READS_DIFFERENTLY` (`webapp/reanalysis.py`).
   - The audit row is `event_type = "reanalysis"` with the detail of Decision 6.
2. **Owner rulings.**
   - Decision 2: cache-only, against re-reads through the upload queue. The ruling covers its two known limits: the backstop's, and the one overlap left in sharing the cache with an upload.
   - Decision 5's "Decided by a rule": reported apart, against counting them as needing redoing.
3. **Order table** (now in the master plan). S5 finishes on top of S2 **and S3** (Task 11 pins C6's `analysis_rules_outdated` and S3's `flag_shown`).
4. **Shared files.** S5 edits `analysis/revenue.py` (Task 3; no other plan edits it) and `tools/l1s3_surface_census.py` (Tasks 3 and 4). A rebase conflict in the census's `READERS` tuple or `EXCUSED` dict is resolved by keeping both sides.
   - S3's Task 3 also adds one `READERS` entry, `analysis/flagged_view.py::apply_flagged_groups_to_payload`, placed after `webapp/worker.py`'s entry and before `analysis/nsf_days.py`'s. S5's Task 4 anchor (the `analysis/nsf_days.py` entry and the tuple's closing `)`) is therefore unchanged after S3 merges, and the two edits rebase without a conflict.
5. **The census in the selections** (now in the master plan, as its own "Surface census" item). `tests/test_l1s3_census.py` was in none of the master plan's Core, Guards/JS or Wider selections. Any service that adds a production function reading the `statement` key by its literal fails it unless that service declares the reader, as S5 does in Tasks 3 and 4. The master plan runs it at each merge as its own item rather than inside Guards/JS, because S1 and S2 pin the Guards/JS counts. (S3's planned `analysis/flagged_view.py` reads the key through the imported name `STATEMENT_KEY`, which the census does not follow: `_key_aliases` only collects names bound in the module itself, `tools/l1s3_surface_census.py:266-285`. The master plan's decision: S3 declares that reader, as `analysis/nsf_days.py::apply_nsf_basis_to_payload` is declared.)

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `analysis/revenue.py` | Modify: `apply_serialized_revenue_review` (`:209-276`) becomes `record_serialized_revenue_review` plus a three-line `apply_serialized_revenue_review` | The review writer without the rebuild, taking the decision's own time |
| `tools/l1s3_surface_census.py` | Modify: the `READERS` entry at `:133-134`; a `READERS` entry after `:153-154`, the last one; an `EXCUSED` entry after `:178` | Declares the payload readers S5 adds or moves |
| `webapp/storage.py` | Modify: insert after `set_job_analysis` (`:627-629`) | `Storage.record_reanalysis`: one transaction, first the audit row holding the replaced analysis, then the job row |
| `webapp/jobs.py` | Modify: insert after `replace_analysis` (`:305-312`) | `JobStore.apply_reanalysis`: durable write plus the in-memory `Job` |
| `webapp/reanalysis.py` | Create | `replay_reviews` (decision replay) and `rerun_analysis` (the worker's own path into a capturing store whose reading is cache-only and which writes nothing into the cache) |
| `webapp/app.py` | Modify: import after `:37`; route after `revenue_reviews` (ends `:2422`), before `/package_analysis` (`:2425`) | `POST /analysis/<job_id>/reanalyze` (C9 plus the ratification items) |
| `webapp/static/app.js` | Modify: the flag `reanalysisBusy` after `rowReviewsInFlight` (`:804-806`); `syncBulkReview`'s `held` (`:837`); the guards of `submitBulkReview` (`:933`) and `submitRevenueReview` (`:4162-4163`); a new block after the bulk-review bar listener (ends `:4223`), before `document.querySelectorAll("[data-transaction-filter]")` (`:4225`) | `#reanalyzeButton` click handler, `reanalysisNotice`, `reanalyzeShownStatement`; reviews wait while a re-analysis is in flight |
| `tests/test_webapp_reanalysis.py` | Create | Storage, job store, review writer, replay, re-run, route, lock and integration tests |
| `tests/test_webapp_reanalysis_ui.py` | Create | Node-harness tests of the button |

No existing test pins flip. A case-insensitive grep of `tests/` for `reanaly|re-analy` finds only unrelated wording: the analysis cache in `tests/test_artifact_cache.py` (`:1018, 1184, 1207, 1307`) and the corpus runs in `tests/test_discovery.py:3` and `tests/test_telemetry_corpus.py:4`. The guards that read `analysis/revenue.py`, `webapp/*.py` or `app.js` stay green, and each run step names them: `tests/test_privacy3_boundaries.py:1448-1461` still finds `rebuild_serialized_revenue_views(analysis)` in `apply_serialized_revenue_review`'s source, and `:1384-1438` still drive every declared review refusal through it; `tests/test_l1s3_census.py` holds with the census edits of Tasks 3 and 4.

---

### Task 1: The store records a re-analysis, auditing the analysis it replaces

**Files:**
- Modify: `webapp/storage.py` (insert after line 629, the end of `set_job_analysis`; before `mark_interrupted_jobs` at line 631)
- Test: `tests/test_webapp_reanalysis.py` (create)

**Interfaces:**
- Consumes: `Storage._connect`, `Storage._insert_audit` (`webapp/storage.py:297-303, 772-790`).
- Produces: `Storage.record_reanalysis(self, job_id: str, *, analysis_json: str, detail: dict) -> bool`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_webapp_reanalysis.py` with the Write tool. The header imports everything later tasks use: each import names an existing module, and `threading` is used from Task 9.

```python
"""Re-analysis of a saved statement (spec docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6 and D12;
the interface contract's C9): POST /analysis/<job>/reanalyze runs the stored PDF through the worker's own read path
again, its reading served from the artifact cache, replaces the job's analysis in place after writing the analysis it
replaces to the audit log, and replays the analyst's revenue decisions where their posting is unchanged. Fabricated
statements only, whole-dollar amounts; the storage and job-store tests use opaque stand-in payloads."""
import copy
import json
import threading

import pytest

from tests.test_webapp_revenue_batch import ROWS, _records, _two_accounts
from tests.test_webapp_studio_views import _report
from webapp.jobs import JobStore
from webapp.storage import Storage


# --- the store: one transaction, the replaced analysis audited first -------------------------------------------------


def test_a_reanalysis_audits_the_analysis_it_replaces_in_the_same_transaction(tmp_path):
    storage = Storage(tmp_path / "data")
    storage.create_job("job-a", filename="fabricated.pdf")
    storage.set_job_result("job-a", markdown="# F", html="<p>F</p>", analysis_json='{"rules": "old"}',
                           analysis_error=None, parse_model="fabricated-reader")
    assert storage.record_reanalysis("job-a", analysis_json='{"rules": "new"}',
                                     detail={"reviews_replayed": [3], "reviews_not_replayed": [4]}) is True
    row = storage.load_job("job-a")
    assert row["analysis_json"] == '{"rules": "new"}' and row["status"] == "done"
    events = storage.audit_events("reanalysis", job_id="job-a")
    assert len(events) == 1
    assert json.loads(events[0]["detail"]) == {
        "reviews_replayed": [3], "reviews_not_replayed": [4],
        "previous_analysis_json": '{"rules": "old"}', "previous_analysis_error": None}


def test_a_reanalysis_that_produced_an_analysis_clears_the_old_analysis_error(tmp_path):
    storage = Storage(tmp_path / "data")
    storage.create_job("job-a", filename="fabricated.pdf")
    storage.set_job_result("job-a", markdown="# F", html="<p>F</p>", analysis_json=None,
                           analysis_error="fabricated refusal", parse_model=None)
    assert storage.record_reanalysis("job-a", analysis_json='{"rules": "new"}', detail={}) is True
    row = storage.load_job("job-a")
    assert (row["analysis_json"], row["analysis_error"]) == ('{"rules": "new"}', None)
    detail = json.loads(storage.audit_events("reanalysis", job_id="job-a")[0]["detail"])
    assert (detail["previous_analysis_json"], detail["previous_analysis_error"]) == (None, "fabricated refusal")


def test_a_reanalysis_of_an_unknown_job_writes_nothing(tmp_path):
    storage = Storage(tmp_path / "data")
    assert storage.record_reanalysis("no-such-job", analysis_json="{}", detail={}) is False
    assert storage.audit_events("reanalysis") == []
```

- [ ] **Step 2: Run the tests and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 3 failed with `AttributeError: 'Storage' object has no attribute 'record_reanalysis'`.

- [ ] **Step 3: Implement.** With the Edit tool, insert after `set_job_analysis` in `webapp/storage.py`. The `old_string` is the whole of lines 627-629 plus the blank line and the `def mark_interrupted_jobs` line.

```python
    def set_job_analysis(self, job_id: str, analysis_json: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE jobs SET analysis_json = ? WHERE id = ?", (analysis_json, job_id))

    def record_reanalysis(self, job_id: str, *, analysis_json: str, detail: dict) -> bool:
        """Replace a job's analysis with a re-analysis of its statement (spec §8.6), in ONE transaction: the audit
        row carrying the analysis being replaced, verbatim, is written first, then the job row takes the new analysis
        and loses any old analysis error (a re-analysis that produced an analysis has none). `detail` goes into the
        audit row beside the replaced analysis. Returns False, writing nothing, for a job that does not exist."""
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT analysis_json, analysis_error FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return False
            self._insert_audit(
                conn,
                "reanalysis",
                job_id=job_id,
                detail={
                    **detail,
                    "previous_analysis_json": row["analysis_json"],
                    "previous_analysis_error": row["analysis_error"],
                },
            )
            conn.execute(
                "UPDATE jobs SET analysis_json = ?, analysis_error = NULL WHERE id = ?",
                (analysis_json, job_id),
            )
        return True

    def mark_interrupted_jobs(self, note: str) -> list[str]:
```

- [ ] **Step 4: Run the tests and the storage suite.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_webapp_storage.py -q -p no:cacheprovider`
Expected: PASS (26 passed; the 3 new tests among them).

- [ ] **Step 5: Commit.**

```bash
git add webapp/storage.py tests/test_webapp_reanalysis.py
git commit -m "webapp: the store records a re-analysis, auditing the analysis it replaces" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 2: The job store applies a re-analysis in place

**Files:**
- Modify: `webapp/jobs.py` (insert after line 312, the end of `replace_analysis`; before `apply_review` at line 314)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes: `Storage.record_reanalysis(job_id, *, analysis_json, detail) -> bool` (Task 1).
- Produces: `JobStore.apply_reanalysis(self, job_id: str, analysis: dict, *, replayed: tuple[int, ...] = (), not_replayed: tuple[int, ...] = (), decided_by_rules: tuple[int, ...] = ()) -> dict | None`. It returns a deep copy of the saved analysis, or None for an unknown job.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- the job store: the same job, in memory and on disk -------------------------------------------------------------


def test_the_job_store_replaces_the_analysis_in_memory_and_on_disk(tmp_path):
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("fabricated.pdf")
    store.set_result(job.id, "# F", "<p>F</p>", analysis={"rules": "old"})
    saved = store.apply_reanalysis(job.id, {"rules": "new"}, replayed=(5,), not_replayed=(6,), decided_by_rules=(7,))
    assert saved == {"rules": "new"} and store.get(job.id).analysis == {"rules": "new"}
    saved["rules"] = "edited by a caller"  # the store keeps its own copy
    assert store.get(job.id).analysis == {"rules": "new"}
    assert JobStore(Storage(tmp_path / "data")).get(job.id).analysis == {"rules": "new"}  # a restart reads it back
    detail = json.loads(store.storage.audit_events("reanalysis", job_id=job.id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [5], [6], [7])
    assert json.loads(detail["previous_analysis_json"]) == {"rules": "old"}


def test_the_job_store_clears_the_analysis_error_and_refuses_an_unknown_job(tmp_path):
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("fabricated.pdf")
    store.set_result(job.id, "# F", "<p>F</p>", analysis=None, analysis_error="fabricated refusal")
    assert store.apply_reanalysis(job.id, {"rules": "new"}) == {"rules": "new"}
    assert (store.get(job.id).analysis, store.get(job.id).analysis_error) == ({"rules": "new"}, None)
    assert store.apply_reanalysis("no-such-job", {"rules": "new"}) is None
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 2 failed with `AttributeError: 'JobStore' object has no attribute 'apply_reanalysis'`, and 3 passed.

- [ ] **Step 3: Implement.** With the Edit tool, in `webapp/jobs.py` replace the `replace_analysis` method (lines 305-312) with itself followed by the new method:

```python
    def replace_analysis(self, job_id: str, analysis: dict) -> dict | None:
        job = self.get(job_id)
        if job is None or job.analysis is None:
            return None
        with self._lock:
            job.analysis = deepcopy(analysis)
        self._storage.set_job_analysis(job_id, json.dumps(analysis))
        return deepcopy(analysis)

    def apply_reanalysis(
        self,
        job_id: str,
        analysis: dict,
        *,
        replayed: tuple[int, ...] = (),
        not_replayed: tuple[int, ...] = (),
        decided_by_rules: tuple[int, ...] = (),
    ) -> dict | None:
        """Replace a job's analysis with a re-analysis of its statement: the same job, so the same id and the same
        place in Recent. The analysis replaced goes to the audit log first, in the same storage transaction
        (`Storage.record_reanalysis`), beside the ids of the review decisions the re-analysis replayed, of those that
        need redoing, and of those a rule now decides (their row no longer awaits review, so there is nothing to
        redo). A re-analysis that produced an analysis has no analysis error."""
        job = self.get(job_id)
        if job is None:
            return None
        written = self._storage.record_reanalysis(
            job_id,
            analysis_json=json.dumps(analysis),
            detail={
                "reviews_replayed": list(replayed),
                "reviews_not_replayed": list(not_replayed),
                "reviews_decided_by_rules": list(decided_by_rules),
            },
        )
        if not written:
            return None
        with self._lock:
            job.analysis = deepcopy(analysis)
            job.analysis_error = None
        return deepcopy(analysis)
```

- [ ] **Step 4: Run the tests and the job-store suites.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_webapp_jobs.py tests/test_webapp_storage.py -q -p no:cacheprovider`
Expected: PASS (35 passed).

- [ ] **Step 5: Commit.**

```bash
git add webapp/jobs.py tests/test_webapp_reanalysis.py
git commit -m "webapp: the job store applies a re-analysis in place" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 3: The review writer takes the decision's own time and leaves the rebuild to its caller

**Files:**
- Modify: `analysis/revenue.py` (lines 209-216, the head of `apply_serialized_revenue_review`, and lines 272-276, its tail)
- Modify: `tools/l1s3_surface_census.py` (lines 133-134, the `READERS` entry of `apply_serialized_revenue_review`)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes: the body of today's `apply_serialized_revenue_review` (`analysis/revenue.py:209-276`), moved unchanged but for the time it writes.
- Produces:
  - `analysis.revenue.record_serialized_revenue_review(analysis: dict, *, source_location: str, decision: Literal["confirm", "reject", "reset"], account: int | None = None, reviewed_at: str | None = None) -> dict`. It returns the written record and does not rebuild the revenue views; it writes nothing when it refuses (`LookupError` / `ValueError`, the same seven messages as today).
  - `apply_serialized_revenue_review(analysis, *, source_location, decision, account=None) -> dict`, unchanged in signature and behaviour: the writer, then `rebuild_serialized_revenue_views(analysis)`.
  - Test helpers `DECIDED_AT` and `_payload(rows=ROWS)`, used by every later task.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- the review writer the replay uses ------------------------------------------------------------------------------

DECIDED_AT = "2031-04-02T09:00:00+00:00"


def _payload(rows=ROWS):
    """A fabricated business checking statement, analysed by the real analysis path."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows))


def test_the_review_writer_keeps_the_decision_s_own_time_and_leaves_the_rebuild_to_its_caller():
    from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review

    analysis = _payload()
    metrics = copy.deepcopy(analysis["metrics"])
    record = record_serialized_revenue_review(analysis, source_location="transaction:2", decision="confirm",
                                              reviewed_at=DECIDED_AT)
    assert record is _records(analysis)["transaction:2"]
    assert (record["revenue_review_status"], record["revenue_classification"], record["revenue_reviewed_at"]) == (
        "confirmed", "verified_revenue", DECIDED_AT)
    assert analysis["metrics"] == metrics  # the views wait for the caller's one rebuild
    rebuild_serialized_revenue_views(analysis)
    assert analysis["metrics"]["verified_revenue_total"] == metrics["verified_revenue_total"] + 300.0
    reset = record_serialized_revenue_review(analysis, source_location="transaction:2", decision="reset",
                                             reviewed_at=DECIDED_AT)
    assert (reset["revenue_review_status"], reset["revenue_reviewed_at"]) == ("pending", None)


@pytest.mark.parametrize("location, decision, refusal", [
    ("transaction:1", "confirm", ValueError),   # revenue a rule verified: not the analyst's to decide
    ("transaction:99", "confirm", LookupError),  # no such row
    ("transaction:2", "approve", ValueError),    # no such decision
])
def test_the_review_writer_writes_nothing_when_it_refuses(location, decision, refusal):
    from analysis.revenue import record_serialized_revenue_review

    analysis = _payload()
    before = copy.deepcopy(analysis)
    with pytest.raises(refusal):
        record_serialized_revenue_review(analysis, source_location=location, decision=decision)
    assert analysis == before
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 4 failed with `ImportError: cannot import name 'record_serialized_revenue_review' from 'analysis.revenue'`, and 5 passed.

- [ ] **Step 3: Implement.** Three edits with the Edit tool.

(a) In `analysis/revenue.py`, rename the function and give it the decision's time. Replace this `old_string` (lines 209-216):

```python
def apply_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
    account: int | None = None,
) -> dict:
    """Apply a human decision to one potential credit and rebuild all views.
```

with:

```python
def record_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
    account: int | None = None,
    reviewed_at: str | None = None,
) -> dict:
    """Write a human decision onto one potential credit's classification record
    and return the record, WITHOUT rebuilding the revenue views.
    `apply_serialized_revenue_review` is this followed by the rebuild; a caller
    writing several decisions (the re-analysis replay, `webapp/reanalysis.py`)
    rebuilds once, after the last. Every check below comes before the first
    write, so a refused decision leaves `analysis` exactly as it was.
    `reviewed_at` is when the decision was made (default: now); a reset clears
    it.
```

(b) In `analysis/revenue.py`, the tail. Replace this `old_string` (lines 272-276):

```python
    record["revenue_reviewed_at"] = (
        None if decision == "reset" else datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state))
    return rebuild_serialized_revenue_views(analysis)
```

with:

```python
    record["revenue_reviewed_at"] = (
        None if decision == "reset" else reviewed_at or datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state))
    return record


def apply_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
    account: int | None = None,
) -> dict:
    """Apply a human decision to one potential credit and rebuild all views:
    `record_serialized_revenue_review`, whose checks and account rules these
    are, followed by one rebuild."""
    record_serialized_revenue_review(
        analysis, source_location=source_location, decision=decision, account=account,
    )
    return rebuild_serialized_revenue_views(analysis)
```

(c) In `tools/l1s3_surface_census.py`, the body that reads the ledger (the `statement` key) moved with the checks, so the declared reader moves with it. Replace this `old_string` (lines 133-134):

```python
    ("analysis/revenue.py", "apply_serialized_revenue_review", "per_account",
     "a reviewer acts on a POSTING, and a posting belongs to one account"),
```

with:

```python
    ("analysis/revenue.py", "record_serialized_revenue_review", "per_account",
     "a reviewer acts on a POSTING, and a posting belongs to one account"),
```

- [ ] **Step 4: Run the tests, the review suites and the guards that read `analysis/revenue.py`.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_revenue_classification.py tests/test_webapp_revenue_batch.py tests/test_privacy3_boundaries.py tests/test_l1s3_census.py tests/test_l1s3_surfaces.py tests/test_webapp_review_ui.py -q -p no:cacheprovider`
Expected: PASS (all passed). `test_the_census_holds_at_this_tree` holds only with edit (c): without it the census reports `apply_serialized_revenue_review` as a `per_account` reader that reaches no shape helper, and `record_serialized_revenue_review` as an undeclared reader.

- [ ] **Step 5: Commit.**

```bash
git add analysis/revenue.py tools/l1s3_surface_census.py tests/test_webapp_reanalysis.py
git commit -m "revenue: the review writer takes the decision's time and leaves the rebuild to its caller" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 4: Replay the analyst's decisions where their posting is unchanged

**Files:**
- Create: `webapp/reanalysis.py`
- Modify: `tools/l1s3_surface_census.py` (after lines 153-154, the last `READERS` entry; after line 178, the `EXCUSED` entry of `webapp/app.py::_package_analysis`)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes:
  - `analysis.revenue.record_serialized_revenue_review` (Task 3) and `rebuild_serialized_revenue_views(analysis)` (`analysis/revenue.py:60-83`, in place, returns the same object, raises `ValueError` when a posted credit has no valid classification record);
  - `analysis.payload_shape.payload_accounts(payload, *, surface)`, which raises `PayloadShapeError(ValueError)`;
  - `JobStore.review_history(job_id)` rows `{id, job_id, source_location, decision, actor, decided_at, prior_state}` (`webapp/storage.py:722-729`).
- Produces:
  - `webapp.reanalysis.Replay(analysis: dict, replayed: tuple[int, ...], not_replayed: tuple[int, ...], decided_by_rules: tuple[int, ...] = ())`;
  - `webapp.reanalysis.replay_reviews(analysis: dict, history: Sequence[Mapping]) -> Replay` (`decided_by_rules` stays empty until Task 5);
  - test helpers `CHANGED_ROWS`, `SHIFTED_ROWS`, `TWIN_ROWS`, `TWIN_CHANGED_ROWS`, `_decision`, `_alike_in_both_accounts`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- replaying the analyst's decisions ------------------------------------------------------------------------------

# The same statement read under new rules, where one deposit now prints another amount: the row at that location is
# no longer the posting the analyst decided.
CHANGED_ROWS = [(day, text, 250.0) if text == "DEPOSIT FABRICATED TWO" else (day, text, amount)
                for day, text, amount in ROWS]
# The same statement with one more row read near the top: every later posting moved one location down.
SHIFTED_ROWS = [ROWS[0], (3, "DEPOSIT FABRICATED EARLY", 50.0), *ROWS[1:]]
# Two deposits alike but for their day; then the same statement where the first of them prints another amount.
TWIN_ROWS = [ROWS[0], (4, "DEPOSIT FABRICATED TWIN", 300.0), (6, "DEPOSIT FABRICATED TWIN", 300.0), *ROWS[3:]]
TWIN_CHANGED_ROWS = [ROWS[0], (4, "DEPOSIT FABRICATED TWIN", 350.0), *TWIN_ROWS[2:]]


def _decision(row_id, analysis, location, decision, account=1):
    """A `review_decisions` row as `JobStore.review_history` returns it, its prior state the record in `analysis`."""
    return {"id": row_id, "job_id": "fabricated-job", "source_location": location, "decision": decision,
            "actor": "local-analyst", "decided_at": DECIDED_AT,
            "prior_state": json.dumps(_records(analysis, account)[location])}


def _alike_in_both_accounts():
    """`_two_accounts()` where the savings account's second row is the checking account's second deposit, printed
    under the savings account's own number: one location, description and amount in two accounts."""
    from analysis.revenue import rebuild_serialized_revenue_views

    payload = _two_accounts()
    checking, savings = (account["statement"]["transactions"] for account in payload["accounts"])
    row = copy.deepcopy(checking[1])
    row["classification"]["account"] = savings[1]["classification"]["account"]
    savings[1] = row
    return rebuild_serialized_revenue_views(payload)


def test_a_decision_is_replayed_where_its_posting_is_unchanged():
    from webapp.reanalysis import replay_reviews

    old, new = _payload(), _payload()
    before = new["metrics"]["verified_revenue_total"]
    replay = replay_reviews(new, [_decision(7, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((7,), (), ())
    record = _records(replay.analysis)["transaction:2"]
    assert (record["revenue_review_status"], record["revenue_classification"]) == ("confirmed", "verified_revenue")
    assert replay.analysis["metrics"]["verified_revenue_total"] == before + 300.0
    assert new["metrics"]["verified_revenue_total"] == before  # the analysis handed in is left as it was
    # The decision keeps the time the analyst made it, on the row and on every copy of its record.
    assert record["revenue_reviewed_at"] == DECIDED_AT
    copies = [item for item in replay.analysis["classifications"] if item["source_location"] == "transaction:2"]
    assert [item["revenue_reviewed_at"] for item in copies] == [DECIDED_AT]


def test_a_decision_is_not_replayed_where_the_row_at_its_location_changed():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    changed = replay_reviews(_payload(CHANGED_ROWS), [_decision(8, old, "transaction:3", "reject")])
    assert (changed.replayed, changed.not_replayed) == ((), (8,))
    assert _records(changed.analysis)["transaction:3"]["revenue_review_status"] == "pending"
    # The posting still exists one row further down. A location names a row, so the decision does not follow it.
    shifted = replay_reviews(_payload(SHIFTED_ROWS), [_decision(9, old, "transaction:2", "confirm")])
    assert (shifted.replayed, shifted.not_replayed) == ((), (9,))
    records = _records(shifted.analysis)
    assert records["transaction:2"]["revenue_review_status"] == "pending"
    assert records["transaction:3"]["revenue_review_status"] == "pending"


def test_a_posting_s_latest_decision_is_replayed_and_a_reset_needs_nothing():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:4", "confirm"),
               _decision(3, old, "transaction:2", "reject"), _decision(4, old, "transaction:4", "reset")]
    replay = replay_reviews(_payload(), history)
    assert (replay.replayed, replay.not_replayed) == ((3,), ())
    records = _records(replay.analysis)
    assert records["transaction:2"]["revenue_review_status"] == "rejected"
    assert records["transaction:4"]["revenue_review_status"] == "pending"


def test_each_account_gets_its_own_decisions_back():
    from webapp.reanalysis import replay_reviews

    old = _two_accounts()
    history = [_decision(1, old, "transaction:2", "confirm", account=2),
               _decision(2, old, "transaction:2", "reject", account=1)]
    replay = replay_reviews(_two_accounts(), history)
    assert (replay.replayed, replay.not_replayed) == ((1, 2), ())
    assert _records(replay.analysis, 2)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(replay.analysis, 1)["transaction:2"]["revenue_review_status"] == "rejected"


def test_a_posting_two_accounts_hold_alike_is_not_guessed():
    from webapp.reanalysis import replay_reviews

    old, new = _two_accounts(), _two_accounts()
    new["accounts"][1] = copy.deepcopy(new["accounts"][0])  # both accounts now print the same row at the same place
    replay = replay_reviews(new, [_decision(3, old, "transaction:2", "confirm", account=1)])
    assert (replay.replayed, replay.not_replayed) == ((), (3,))


def test_a_decision_never_follows_its_posting_into_another_account():
    """The account number is part of what a decision was made on: a deposit alike in two accounts is two postings."""
    from webapp.reanalysis import replay_reviews

    old, new = _alike_in_both_accounts(), _alike_in_both_accounts()
    # The savings account's deposit now prints another amount; the checking account's, alike before, is unchanged.
    changed = new["accounts"][1]["statement"]["transactions"][1]
    changed["amount"] = changed["classification"]["amount"] = 350.0
    replay = replay_reviews(new, [_decision(4, old, "transaction:2", "confirm", account=2)])
    assert (replay.replayed, replay.not_replayed) == ((), (4,))
    assert _records(replay.analysis, 1)["transaction:2"]["revenue_review_status"] == "pending"


@pytest.mark.parametrize("prior_state", [None, "not a record", "[1, 2]"])
def test_a_decision_whose_prior_state_cannot_be_read_is_not_replayed(prior_state):
    from webapp.reanalysis import replay_reviews

    history = [{"id": 1, "source_location": "transaction:2", "decision": "confirm", "decided_at": DECIDED_AT,
                "prior_state": prior_state},
               {"id": 2, "source_location": "transaction:3", "decision": "reset", "decided_at": DECIDED_AT,
                "prior_state": prior_state}]
    replay = replay_reviews(_payload(), history)
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((), (1,), ())


def test_a_decision_that_cannot_be_applied_leaves_the_analysis_as_it_was():
    from webapp.reanalysis import replay_reviews

    old, new = _payload(), _payload()
    # Another credit of the account has lost its classification record: rebuilding the revenue views refuses, after
    # the decision was already written onto its row.
    new["statement"]["transactions"][0]["classification"] = None
    before = copy.deepcopy(new)
    replay = replay_reviews(new, [_decision(7, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed) == ((), (7,))
    assert replay.analysis == before and new == before


def test_every_decision_is_replayed_onto_one_copy_rebuilt_once(monkeypatch):
    """The replay runs under the statement's review lock, so its cost must not grow with the decisions times the
    statement: one copy of the analysis takes every decision, and its revenue views are rebuilt once, after the
    last."""
    import webapp.reanalysis as reanalysis

    old = _payload()
    rebuilds, copies = [], []
    rebuild, deepcopy = reanalysis.rebuild_serialized_revenue_views, reanalysis.deepcopy
    monkeypatch.setattr(reanalysis, "rebuild_serialized_revenue_views",
                        lambda analysis: rebuilds.append(1) or rebuild(analysis))
    monkeypatch.setattr(reanalysis, "deepcopy", lambda value: copies.append(1) or deepcopy(value))
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:3", "reject"),
               _decision(3, old, "transaction:4", "confirm")]
    replay = reanalysis.replay_reviews(_payload(), history)
    assert (replay.replayed, len(rebuilds), len(copies)) == ((1, 2, 3), 1, 1)
    records = _records(replay.analysis)
    assert [records[f"transaction:{number}"]["revenue_review_status"] for number in (2, 3, 4)] == [
        "confirmed", "rejected", "confirmed"]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 11 failed with `ModuleNotFoundError: No module named 'webapp.reanalysis'`, and 9 passed.

- [ ] **Step 3: Implement.** Two parts.

(a) Create `webapp/reanalysis.py` with the Write tool:

```python
"""Re-analysis of a saved statement (docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6, D12).

`replay_reviews` puts the analyst's revenue decisions (the append-only `review_decisions` table) back onto a fresh
analysis of the same statement, only where the posting is unchanged: the row at the same account and location has the
same description and amount. The others are counted, so the analyst can be told how many reviews need redoing.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from analysis.payload_shape import payload_accounts
from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review

#: Named once: it reaches a shape refusal's message.
_REPLAY_SURFACE = "webapp/reanalysis.py::replay_reviews"


@dataclass(frozen=True)
class Replay:
    """A fresh analysis with the decisions replayed, and the `review_decisions` ids replayed, needing redoing, and
    decided by a rule (their row no longer awaits review, so there is nothing to redo)."""

    analysis: dict
    replayed: tuple[int, ...]
    not_replayed: tuple[int, ...]
    decided_by_rules: tuple[int, ...] = ()


def _money(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def _prior_state(row: Mapping) -> dict | None:
    """The classification record a decision changed, as the review route recorded it; None when it cannot be read."""
    text = row.get("prior_state")
    if not isinstance(text, str):
        return None
    try:
        prior = json.loads(text)
    except ValueError:
        return None
    return prior if isinstance(prior, dict) else None


def _identity(row: Mapping) -> tuple | None:
    """What a decision was made on, from its recorded prior state: (account number, location, description, amount to
    the cent, date). None when the prior state cannot be read."""
    prior = _prior_state(row)
    if prior is None:
        return None
    return (prior.get("account"), row.get("source_location"), prior.get("original_description"),
            _money(prior.get("amount")), prior.get("date"))


def _records(holder: Mapping) -> Iterator[dict]:
    """One account's classification records, in ledger order."""
    for transaction in (holder.get("statement") or {}).get("transactions") or []:
        if isinstance(transaction, dict) and isinstance(transaction.get("classification"), dict):
            yield transaction["classification"]


def _same_posting(record: Mapping, identity: tuple) -> bool:
    """The row is the one the decision was made on (spec §8.6.5): the same account number, location, description and
    amount to the cent. The date is not compared: the spec names these four."""
    account, location, description, amount, _date = identity
    return (record.get("source_location") == location
            and isinstance(description, str) and record.get("original_description") == description
            and amount is not None and _money(record.get("amount")) == amount
            and record.get("account") == account)


def _places(accounts: Sequence[Mapping], identity: tuple | None) -> list[tuple[int, dict]]:
    """Every (1-based account number, record) holding the posting `identity` names, across every account."""
    if identity is None:
        return []
    return [(number, record)
            for number, holder in enumerate(accounts, start=1)
            for record in _records(holder)
            if _same_posting(record, identity)]


def _applied(analysis: dict, history: Sequence[Mapping],
             waiting: Sequence[tuple[int, int]]) -> tuple[dict, list[int], list[int]]:
    """`analysis` with the decisions `waiting` names applied, and the history indexes applied and refused. `waiting`
    holds (history index, 1-based account number) pairs.

    Every decision is written onto ONE copy of `analysis`, whose revenue views are rebuilt once, after the last: the
    cost is one copy and one rebuild however many decisions there are. A decision the review writer refuses is refused
    alone; the writer checks everything before it writes, so the copy is as it was. When the rebuilt views do not hold,
    which no decision can cause (a posted credit with no valid classification record), every decision is refused and
    `analysis` is returned as it was handed, as the review routes keep the saved analysis when their rebuild refuses."""
    if not waiting:
        return analysis, [], []
    candidate = deepcopy(analysis)
    applied: list[int] = []
    refused: list[int] = []
    for index, account in waiting:
        row = history[index]
        decided_at = row.get("decided_at")
        try:
            record_serialized_revenue_review(
                candidate, source_location=row.get("source_location"), decision=row.get("decision"),
                account=account, reviewed_at=decided_at if isinstance(decided_at, str) else None)
        except (LookupError, ValueError):
            refused.append(index)
            continue
        applied.append(index)
    if not applied:
        return analysis, [], refused
    try:
        rebuild_serialized_revenue_views(candidate)
    except (LookupError, ValueError):
        return analysis, [], sorted(refused + applied)
    return candidate, applied, refused


def _ids(history: Sequence[Mapping], indexes: Iterable[int]) -> tuple[int, ...]:
    return tuple(history[index].get("id") for index in indexes)


def replay_reviews(analysis: dict, history: Sequence[Mapping]) -> Replay:
    """Replay `history` (`JobStore.review_history` rows, oldest first) onto `analysis`, a fresh analysis of the
    statement the decisions were made on. `analysis` itself is never changed: the decisions are applied to one copy,
    kept only when its rebuilt revenue views hold.

    A decision is replayed only onto the one row, across every account, whose account number, location, description
    and amount are the ones it was made on; a location names a row, so a posting that moved is not followed. Of several
    decisions on one such row the latest is replayed: each sets the state outright. A reset asks for the pending state
    a fresh analysis already has, so it is neither replayed nor counted. Replayed decisions keep the time the analyst
    made them.

    A decision that is not replayed needs redoing. Nothing here writes a decision: the replay is part of the
    re-analysis, which the audit log records.
    """
    identities = [_identity(row) for row in history]
    latest: dict[tuple, int] = {}
    for index, identity in enumerate(identities):
        key = ("unreadable", index) if identity is None else identity[:4]
        latest.pop(key, None)  # the later decision replaces the earlier one, and is replayed in its own turn
        latest[key] = index
    try:
        accounts = payload_accounts(analysis, surface=_REPLAY_SURFACE)
    except ValueError:
        accounts = []
    waiting: list[tuple[int, int]] = []
    redo: list[int] = []
    for index in latest.values():
        if history[index].get("decision") == "reset":
            continue
        places = _places(accounts, identities[index])
        if len(places) != 1:
            redo.append(index)
            continue
        waiting.append((index, places[0][0]))
    updated, applied, refused = _applied(analysis, history, waiting)
    return Replay(updated, _ids(history, applied), _ids(history, sorted(redo + refused)))
```

(b) Declare the new payload reader in `tools/l1s3_surface_census.py`, with the Edit tool. First, replace this `old_string` (lines 153-155, the last `READERS` entry and the tuple's close):

```python
    ("analysis/nsf_days.py", "apply_nsf_basis_to_payload", "per_account",
     "the NSF basis is a property of one account's ledger; every account is re-based, a malformed document passes untouched"),
)
```

with:

```python
    ("analysis/nsf_days.py", "apply_nsf_basis_to_payload", "per_account",
     "the NSF basis is a property of one account's ledger; every account is re-based, a malformed document passes untouched"),
    ("webapp/reanalysis.py", "replay_reviews", "per_account",
     "a decision names one posting of one account; every account is searched through payload_accounts"),
)
```

Then replace this `old_string` (line 178):

```python
    "webapp/app.py::_package_analysis": "reads one MEMBER's account payload, supplied by `_package_members`",
```

with:

```python
    "webapp/app.py::_package_analysis": "reads one MEMBER's account payload, supplied by `_package_members`",
    "webapp/reanalysis.py::_records": "one ACCOUNT's records; `replay_reviews` hands it each account from `payload_accounts`",
```

- [ ] **Step 4: Run the tests, the census and the privacy census.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_l1s3_census.py tests/test_worker_privacy.py tests/test_webapp_revenue_batch.py -q -p no:cacheprovider`
Expected: PASS (all passed). `test_the_webapp_exception_ledger_is_complete` stays green because no handler binds its exception; `test_the_census_holds_at_this_tree` holds only with Step 3(b), since `_records` reads the `statement` key.

- [ ] **Step 5: Commit.**

```bash
git add webapp/reanalysis.py tools/l1s3_surface_census.py tests/test_webapp_reanalysis.py
git commit -m "webapp: replay revenue decisions onto a re-analysis where the posting is unchanged" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 5: A redone review is not reported again, and a review a rule now decides is reported apart

**Files:**
- Modify: `webapp/reanalysis.py` (the `analysis.revenue` import, and `replay_reviews`, the last function of the file)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes: `analysis.revenue.LEGACY_REVENUE_STATE_MAP` (`analysis/revenue.py:26`), read as the review writer reads it (`:250-253`); `_identity`, `_places`, `_applied`, `_ids` (Task 4).
- Produces: `replay_reviews` fills `Replay.decided_by_rules`; the private `_redone(identity, later) -> bool` and `_awaits_review(record) -> bool`; the test helper `_ruled(analysis, location, account=1) -> dict`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
def _ruled(analysis, location, account=1):
    """`analysis` after a new rule decided the deposit at `location` (S2's D1, say: a credit from a financing payee is
    financing proceeds): the rule classifies the credit itself, so the row no longer awaits the analyst, who could not
    review it again (analysis/revenue.py refuses any row a rule decided)."""
    from analysis.revenue import rebuild_serialized_revenue_views

    _records(analysis, account)[location].update(
        revenue_classification="non_revenue", revenue_initial_classification="non_revenue",
        revenue_review_required=False, revenue_review_status="not_required",
        revenue_match_method="financing_proceeds_credit")
    return rebuild_serialized_revenue_views(analysis)


def test_a_decision_on_a_row_a_rule_now_decides_is_reported_apart():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    replay = replay_reviews(_ruled(_payload(), "transaction:2"), [_decision(5, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((), (), (5,))
    assert _records(replay.analysis)["transaction:2"]["revenue_classification"] == "non_revenue"


def test_a_review_redone_on_a_changed_row_is_not_reported_again():
    from webapp.reanalysis import replay_reviews

    old, changed = _payload(), _payload(CHANGED_ROWS)
    # The analyst's decision; a re-analysis on which its row prints another amount; the analyst's redo on that row.
    history = [_decision(1, old, "transaction:3", "confirm"), _decision(2, changed, "transaction:3", "confirm")]
    replay = replay_reviews(_payload(CHANGED_ROWS), history)
    assert (replay.replayed, replay.not_replayed) == ((2,), ())
    assert _records(replay.analysis)["transaction:3"]["revenue_review_status"] == "confirmed"


def test_a_review_redone_where_its_posting_moved_is_not_reported_again():
    from webapp.reanalysis import replay_reviews

    old, shifted = _payload(), _payload(SHIFTED_ROWS)
    # The posting decided at transaction:2 moved to transaction:3, and the analyst decided it again there.
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, shifted, "transaction:3", "confirm")]
    replay = replay_reviews(_payload(SHIFTED_ROWS), history)
    assert (replay.replayed, replay.not_replayed) == ((2,), ())
    records = _records(replay.analysis)
    assert (records["transaction:2"]["revenue_review_status"], records["transaction:3"]["revenue_review_status"]) == (
        "pending", "confirmed")


def test_a_decision_on_a_posting_alike_on_another_day_is_not_a_redo():
    from webapp.reanalysis import replay_reviews

    old = _payload(TWIN_ROWS)
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:3", "confirm")]
    # While both twins are unchanged, each keeps its own decision.
    both = replay_reviews(_payload(TWIN_ROWS), history)
    assert (both.replayed, both.not_replayed) == ((1, 2), ())
    # When the first prints another amount, its decision needs redoing: the decision on the second twin was made on
    # another day's posting, so it did not redo the first.
    changed = replay_reviews(_payload(TWIN_CHANGED_ROWS), history)
    assert (changed.replayed, changed.not_replayed) == ((2,), (1,))


def test_a_decision_on_another_account_is_not_a_redo():
    """A redo is made on the same account number: the other account's row at the same location is another posting."""
    from webapp.reanalysis import replay_reviews

    old, new = _two_accounts(), _two_accounts()
    changed = new["accounts"][0]["statement"]["transactions"][1]  # the checking account's transaction:2
    changed["amount"] = changed["classification"]["amount"] = 350.0
    history = [_decision(1, old, "transaction:2", "confirm", account=1),
               _decision(2, old, "transaction:2", "confirm", account=2)]
    replay = replay_reviews(new, history)
    assert (replay.replayed, replay.not_replayed) == ((2,), (1,))
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 3 failed, 22 passed:
- `test_a_decision_on_a_row_a_rule_now_decides_is_reported_apart`: `assert ((), (5,), ()) == ((), (), (5,))` (the review writer refused the row, so Task 4 counts it as needing redoing);
- the two redo tests: `assert ((2,), (1,)) == ((2,), ())`.
The two tests of what is *not* a redo already pass; they guard Step 3 against taking too much for a redo.

- [ ] **Step 3: Implement.** Two edits to `webapp/reanalysis.py` with the Edit tool.

(a) Replace the import line

```python
from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review
```

with:

```python
from analysis.revenue import (
    LEGACY_REVENUE_STATE_MAP,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)
```

(b) Replace the whole `replay_reviews` function (from `def replay_reviews(analysis: dict, history: Sequence[Mapping]) -> Replay:` to the end of the file) with:

```python
def _redone(identity: tuple | None, later: Sequence[tuple | None]) -> bool:
    """Whether a decision made after this one (`later`, their identities) redid it: on the same account number, and
    either the same row (the analyst decided that row again, whatever it printed by then) or the same posting wherever
    it sat by then (the same description, amount and date). Two postings of one account alike in all three are the one
    case this cannot tell apart; a decision on one of them then passes for a redo of the other, and the count says one
    review too few."""
    if identity is None:
        return False
    return any(other is not None and other[0] == identity[0]
               and (other[1] == identity[1] or other[2:] == identity[2:])
               for other in later)


def _awaits_review(record: Mapping) -> bool:
    """The row is a deposit the analyst decides, not one a rule decided: the review writer refuses any other
    (analysis/revenue.py), so the analyst could not redo a decision on it."""
    initial = record.get("revenue_initial_classification")
    return LEGACY_REVENUE_STATE_MAP.get(initial, initial) == "unverified_deposit"


def replay_reviews(analysis: dict, history: Sequence[Mapping]) -> Replay:
    """Replay `history` (`JobStore.review_history` rows, oldest first) onto `analysis`, a fresh analysis of the
    statement the decisions were made on. `analysis` itself is never changed: the decisions are applied to one copy,
    kept only when its rebuilt revenue views hold.

    A decision is replayed only onto the one row, across every account, whose account number, location, description
    and amount are the ones it was made on; a location names a row, so a posting that moved is not followed. Of several
    decisions on one such row the latest is replayed: each sets the state outright. A reset asks for the pending state
    a fresh analysis already has, so it is neither replayed nor counted. Replayed decisions keep the time the analyst
    made them.

    A decision that is not replayed needs redoing, unless a later decision redid it (`_redone`). One whose row a rule
    of the current analysis now decides cannot be redone (the analyst can no longer review that row), so it is
    reported apart, as decided by the rules (spec §8.6.5: anything that cannot be replayed is reported back). Nothing
    here writes a decision: the replay is part of the re-analysis, which the audit log records.
    """
    identities = [_identity(row) for row in history]
    latest: dict[tuple, int] = {}
    for index, identity in enumerate(identities):
        key = ("unreadable", index) if identity is None else identity[:4]
        latest.pop(key, None)  # the later decision replaces the earlier one, and is replayed in its own turn
        latest[key] = index
    try:
        accounts = payload_accounts(analysis, surface=_REPLAY_SURFACE)
    except ValueError:
        accounts = []
    waiting: list[tuple[int, int]] = []
    redo: list[int] = []
    ruled: list[int] = []
    for index in latest.values():
        if history[index].get("decision") == "reset":
            continue
        places = _places(accounts, identities[index])
        if len(places) != 1:
            if not _redone(identities[index], identities[index + 1:]):
                redo.append(index)
            continue
        number, record = places[0]
        if not _awaits_review(record):
            ruled.append(index)
            continue
        waiting.append((index, number))
    updated, applied, refused = _applied(analysis, history, waiting)
    return Replay(updated, _ids(history, applied), _ids(history, sorted(redo + refused)), _ids(history, ruled))
```

- [ ] **Step 4: Run the tests and the census.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_l1s3_census.py tests/test_worker_privacy.py -q -p no:cacheprovider`
Expected: PASS (all passed).

- [ ] **Step 5: Commit.**

```bash
git add webapp/reanalysis.py tests/test_webapp_reanalysis.py
git commit -m "webapp: a redone review is not reported again; a review a rule now decides is reported apart" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 6: Re-run a saved statement through the worker's own path, into a store that captures it

**Files:**
- Modify: `webapp/reanalysis.py` (module docstring, imports, and new code appended at the end)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes:
  - `webapp.worker.run_job(job_id, pdf_bytes, filename, store, force_ocr=False, parse_mode="auto") -> None` (`webapp/worker.py:594-601`);
  - `webapp.jobs.Job`, `JobStore.create(filename, *, page_count=0, force_ocr=False, parse_mode="auto", pdf_bytes=None)`, `JobStore.cache`, `JobStore.record_cache_hit` (`webapp/jobs.py:33-49, 115-130, 136-144`);
  - the visual pair's one entry point, `vlm.pair.extract_visual_pair(pdf, *, settings, evidence_dir, progress, data_scope)`, which `_read_visual_pair` imports when it reads (`webapp/worker.py:561-575`), and `webapp.worker.check_remote_authorization`, as `tests/test_private_artifacts.py:92-110` fabricates them; `ocr.private_artifacts.PRIVATE_ROOT_ENV`.
- Produces:
  - `webapp.reanalysis.READS_DIFFERENTLY: str`;
  - `webapp.reanalysis.Rerun(analysis: dict | None, reason: str | None = None)`;
  - `webapp.reanalysis.rerun_analysis(store: JobStore, job: Job, pdf_bytes: bytes) -> Rerun`;
  - the private `_CapturedJobStore(store, job)`;
  - test helpers `PDF`, `WITHHELD`, the fixtures `private_store`, `pipeline` and `visual_pair`, `_Pipeline`, `_stamped`, `_json`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`. The helpers are used by Tasks 7-11 too.

```python
# --- re-running the statement through the worker's own path ---------------------------------------------------------

PDF = b"%PDF-1.7\nfabricated statement for the re-analysis tests"
WITHHELD = "(message withheld; an exception message can quote statement text)"


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    """A job store of its own (so an artifact cache of its own), installed where the routes read it. The visual pair
    stays off, as it is by default: these statements are read by the fabricated reader below."""
    from webapp import app as webapp_app

    store = JobStore(Storage(tmp_path / "data"))
    monkeypatch.setattr(webapp_app, "store", store)
    monkeypatch.delenv("OCR_ALLOW_VISUAL_PAIR", raising=False)
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)
    return store


class _Pipeline:
    """The worker's two expensive stages, fabricated: a reader that counts its reads and, like the real ladder
    (ocr/pipeline.py), names its rung before it reads; and an analysis stage that answers with the payload of the rules
    in force. Everything between them (the worker, the artifact cache, the job store) is real, so an upload leaves the
    reading cached exactly as production does.

    `announce = False` makes a reader that names no stage before it reads, and `stream = True` one that streams text
    through the live view before it reads: each takes one of the re-analysis's guards out of the way of the other."""

    def __init__(self, monkeypatch, store):
        self.monkeypatch, self.store = monkeypatch, store
        self.reads = 0
        self.announce = True
        self.stream = False
        self.payload = None
        self.analysis_failure = None
        monkeypatch.setattr("webapp.worker.parse_statement", self._read)
        monkeypatch.setattr("webapp.worker.analyze_document", self._analyze)
        monkeypatch.setattr("webapp.worker.document_to_json", lambda document: copy.deepcopy(self.payload))

    def _read(self, pdf_bytes, source_file="", on_stage=None, on_page_delta=None, **kwargs):
        from ocr.document import StatementMarkdown

        if self.stream and on_page_delta is not None:
            on_page_delta(0, "FABRICATED")
        if self.announce and on_stage is not None:
            on_stage("native")
        self.reads += 1
        return StatementMarkdown(source_file=source_file, model="fabricated-reader",
                                 pages=["FABRICATED STATEMENT PAGE"])

    def _analyze(self, markdown, **kwargs):
        if self.analysis_failure is not None:
            raise self.analysis_failure
        return object()

    def upload(self, payload, filename="fabricated.pdf", *, force_ocr=False, parse_mode="auto"):
        """One upload through the real worker, with the job's own read flag and parse mode; returns the job id."""
        from webapp.worker import run_job

        self.payload = payload
        job = self.store.create(filename, pdf_bytes=PDF, force_ocr=force_ocr, parse_mode=parse_mode)
        run_job(job.id, PDF, filename, self.store, force_ocr=force_ocr, parse_mode=parse_mode)
        assert self.store.get(job.id).status == "done"
        return job.id

    def new_rules(self, payload):
        """What a release of new rules does: the analysis stage version moves on, so the cached analysis is not
        served, and the analysis stage answers under the new rules. The reading stays cached."""
        from webapp import artifact_cache

        self.monkeypatch.setattr(artifact_cache, "ANALYSIS_STAGE_VERSION", artifact_cache.ANALYSIS_STAGE_VERSION + 1)
        self.payload = payload

    def forget_ocr(self):
        """The reading is no longer cached (a pruned cache, a new OCR toolchain)."""
        for entry in self.store.storage.cache_entries("ocr"):
            self.store.storage.cache_forget("ocr", entry["cache_key"])

    def drift_ocr(self):
        """The cached reading fails its own round-trip check (`cached_ocr` in webapp/artifact_cache.py): the cache
        takes it for a miss after answering a hit, and would read the statement again."""
        for entry in self.store.storage.cache_entries("ocr"):
            path = self.store.cache.root / entry["artifact_path"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["artifact"]["document"]["visual_pair"] = {"fabricated": True}
            payload["artifact"]["document"]["visual_pair_sha256"] = "0" * 64
            path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def pipeline(monkeypatch, private_store):
    return _Pipeline(monkeypatch, private_store)


@pytest.fixture
def visual_pair(monkeypatch, tmp_path):
    """The visual pair, fabricated at its one entry point (`vlm.pair.extract_visual_pair`, imported by the worker when
    it reads), as tests/test_private_artifacts.py does. It records each call and answers as the pair does from its own
    local evidence index: it names no step and streams nothing. Its customer-data fence is opened for these fabricated
    statements, and its private evidence root is a temporary directory. The answer is not a pair document (no pair
    evidence, another model name), so the fabricated analysis stage reads it."""
    from ocr import private_artifacts
    from ocr.document import StatementMarkdown

    calls = []

    def extract(pdf, **kwargs):
        calls.append(pdf)
        return StatementMarkdown(source_file="statement.pdf", model="fabricated-pair-reader",
                                 pages=["FABRICATED STATEMENT PAGE"])

    monkeypatch.setenv(private_artifacts.PRIVATE_ROOT_ENV, str(tmp_path / "private"))
    monkeypatch.setattr("webapp.worker.check_remote_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr("vlm.pair.extract_visual_pair", extract)
    return calls


def _stamped(payload, parse_mode="auto"):
    """A payload as the worker saves it: stamped with the parse mode it ran under (webapp/worker.py:392-393)."""
    return {**payload, "parse_mode": parse_mode}


def _json(value):
    return json.loads(json.dumps(value))


def test_a_rerun_reads_the_statement_from_the_ocr_cache_and_leaves_the_saved_job_alone(pipeline, private_store):
    from webapp.reanalysis import rerun_analysis

    old, new = _payload(), _payload(SHIFTED_ROWS)
    job_id = pipeline.upload(old)
    assert pipeline.reads == 1
    pipeline.new_rules(new)
    statuses = len(private_store.storage.audit_events("status_change", job_id=job_id))
    telemetry = len(private_store.storage.telemetry_records())

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert rerun.reason is None and rerun.analysis == _stamped(new)
    assert pipeline.reads == 1  # the statement was not read again
    hits = [json.loads(row["detail"])["stage"] for row in private_store.storage.audit_events("cache_hit", job_id=job_id)]
    assert "ocr" in hits
    # Nothing of the saved job moved: no status change, no telemetry record, the same analysis in memory and on disk.
    saved = private_store.get(job_id)
    assert saved.status == "done" and saved.analysis == _stamped(old)
    assert json.loads(private_store.storage.load_job(job_id)["analysis_json"]) == _json(_stamped(old))
    assert len(private_store.storage.audit_events("status_change", job_id=job_id)) == statuses
    assert len(private_store.storage.telemetry_records()) == telemetry


def test_a_rerun_keeps_the_job_s_own_parse_mode(pipeline, private_store):
    """A job uploaded in deterministic mode is re-run in deterministic mode: in auto mode the analysis stage may make
    the hosted call the operator did not choose for this job."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), parse_mode="deterministic")
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.reason, rerun.analysis) == (None, _stamped(new, "deterministic"))


def test_a_statement_the_visual_pair_read_is_reanalyzed_from_the_pair_s_cached_reading(
        pipeline, private_store, visual_pair):
    """A job uploaded with Force visual OCR was read by the visual pair. Its re-analysis takes the same path (the
    job's own read flag), and the pair's reading comes from the cache: the pair is not called again."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    assert (len(visual_pair), pipeline.reads) == (1, 0)
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert (len(visual_pair), pipeline.reads) == (1, 0)


@pytest.mark.parametrize("failure, reason", [
    (RuntimeError("no deterministic parser matched this statement"), "no deterministic parser matched this statement"),
    (RuntimeError("FABRICATED STATEMENT TEXT"), f"analysis stage failed: RuntimeError {WITHHELD}"),
])
def test_a_rerun_that_produces_no_analysis_gives_the_worker_s_own_reason(pipeline, private_store, failure, reason):
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = failure
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, reason)


def test_a_rerun_whose_analysis_comes_from_another_reading_is_not_accepted(pipeline, private_store):
    from webapp.reanalysis import READS_DIFFERENTLY, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    # The saved analysis was made from another reading than the one the current rules analyse: a statement the visual
    # pair read, say, which the deterministic path now claims from its own cached reading.
    saved = copy.copy(private_store.get(job_id))
    saved.markdown = "<!-- fabricated: the reading the saved analysis was made from -->"
    rerun = rerun_analysis(private_store, saved, private_store.pdf_bytes(job_id))
    assert pipeline.reads == 1
    assert (rerun.analysis, rerun.reason) == (None, READS_DIFFERENTLY)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 6 failed with `ImportError: cannot import name 'rerun_analysis' from 'webapp.reanalysis'` (or `READS_DIFFERENTLY`, the first name the last test imports), and 25 passed.

- [ ] **Step 3: Implement.** Three edits to `webapp/reanalysis.py` with the Edit tool.

(a) Replace the module docstring with:

```python
"""Re-analysis of a saved statement (docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6, D12).

`rerun_analysis` runs the statement's stored PDF through the worker's own read and analysis path
(`webapp.worker.run_job`) into a stand-in for the job store, so the saved job is not touched until the route accepts
the new analysis.

`replay_reviews` puts the analyst's revenue decisions (the append-only `review_decisions` table) back onto a fresh
analysis of the same statement, only where the posting is unchanged: the row at the same account and location has the
same description and amount. The others are counted, so the analyst can be told how many reviews need redoing.
"""
```

(b) Replace the import block

```python
from analysis.revenue import (
    LEGACY_REVENUE_STATE_MAP,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)
```

with:

```python
from analysis.revenue import (
    LEGACY_REVENUE_STATE_MAP,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)

from .jobs import Job, JobStore
from .worker import run_job
```

(c) Append at the end of the file:

```python


#: Why a re-run that produced an analysis is still not accepted: under the current rules the analysis comes from
#: another cached reading of the statement than the one the saved analysis was made from (the worker chose the other
#: of its deterministic and visual-pair paths). The saved analysis and the source view beside it describe one reading,
#: so the saved job is kept.
READS_DIFFERENTLY = (
    "under the current rules the analysis comes from another reading of the statement than the saved one"
)


class _CapturedJobStore:
    """What `run_job` is handed during a re-analysis, in place of the job store.

    Every stage reads and writes through the real artifact cache, and cache hits are recorded in the real audit log
    (the evidence of what was served from the cache). Every job-state write lands here, so the saved job keeps its
    status, its stage and its analysis until the route accepts the new one. It has no `storage`, so the run writes no
    telemetry record (`telemetry.emit.open_sqlite_sink` opens a null sink): telemetry counts intake runs, and the
    audit log records the re-analysis. Its methods are exactly the ones `webapp/worker.py` calls on its store."""

    def __init__(self, store: JobStore, job: Job) -> None:
        self._store = store
        self.cache = store.cache
        self.job = Job(id=job.id, filename=job.filename, force_ocr=job.force_ocr, parse_mode=job.parse_mode,
                       page_count=job.page_count, content_sha256=job.content_sha256)
        self.result: tuple[str, str, dict | None, str | None, str | None] | None = None
        self.error: str | None = None

    def get(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.id else None

    def record_cache_hit(self, job_id: str, stage: str, cache_key: str | None) -> None:
        self._store.record_cache_hit(job_id, stage, cache_key)

    def set_status(self, job_id: str, status: str) -> None:
        self.job.status = status

    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        self.job.stage = stage

    def append_page_live(self, job_id: str, page: int, chunk: str) -> None:
        return None

    def set_page_live(self, job_id: str, page: int, text: str) -> None:
        # A cached reading replays its pages here.
        return None

    def set_result(self, job_id: str, markdown: str, html: str, analysis: dict | None = None,
                   analysis_error: str | None = None, parse_model: str | None = None) -> None:
        self.job.status = "done"
        self.result = (markdown, html, analysis, analysis_error, parse_model)

    def set_error(self, job_id: str, error: str) -> None:
        self.job.status = "error"
        self.error = error


@dataclass(frozen=True)
class Rerun:
    """A re-run's new analysis; or None, with the reason it is not accepted: text the worker already publishes for
    that outcome (`_stage_failure`, `_analysis_failure`, its no-native-text notice) or READS_DIFFERENTLY."""

    analysis: dict | None
    reason: str | None = None


def rerun_analysis(store: JobStore, job: Job, pdf_bytes: bytes) -> Rerun:
    """Run a saved job's statement through `webapp.worker.run_job` again, with the job's own read flag and parse mode,
    into a `_CapturedJobStore`. Nothing of the saved job is written here."""
    run = _CapturedJobStore(store, job)
    run_job(job.id, pdf_bytes, job.filename, run, force_ocr=job.force_ocr, parse_mode=job.parse_mode)
    if run.error is not None or run.result is None:
        return Rerun(None, run.error)
    markdown, _html, analysis, analysis_error, _parse_model = run.result
    if analysis is None:
        return Rerun(None, analysis_error)
    if markdown != job.markdown:
        return Rerun(None, READS_DIFFERENTLY)
    return Rerun(analysis)
```

- [ ] **Step 4: Run the tests and the worker and cache suites.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_worker_privacy.py tests/test_webapp_worker.py tests/test_artifact_cache.py tests/test_visual_pair_worker.py tests/test_l1s3_census.py -q -p no:cacheprovider`
Expected: PASS (all passed).

- [ ] **Step 5: Commit.**

```bash
git add webapp/reanalysis.py tests/test_webapp_reanalysis.py
git commit -m "webapp: re-run a saved statement through the worker's own path into a capturing store" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 7: A re-analysis runs no reading rung for a statement whose reading is not cached, and writes nothing into the cache

**Files:**
- Modify: `webapp/reanalysis.py` (module docstring, imports, and the block Task 6 appended)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes:
  - `webapp.artifact_cache.ArtifactCache.get_ocr(content_hash, settings_key) -> tuple[bool, dict | None]` (`webapp/artifact_cache.py:1193-1200`), which `cached_ocr` calls before it computes (`:1418, 1447-1448`);
  - the three cache writes the worker makes, `put_ocr(content_hash, settings_key, document)`, `put_analysis(markdown_hash, settings_key, analysis)` and `put_report(markdown_hash, settings_key, html)` (`:1202, 1256, 1263`), called by `cached_ocr`, `cached_analysis` and `cached_report` (`:1457, 1522, 1544`), each of which ignores the key they return;
  - the fixtures and helpers of Task 6.
- Produces:
  - `webapp.reanalysis.READING_NOT_CACHED: str`;
  - the private `_ReadingRefused(Exception)` and `_CacheOnly(cache, run)`, whose `put_ocr`, `put_analysis` and `put_report` write nothing;
  - `_CapturedJobStore.refuse_reading()` and `_CapturedJobStore.reading_refused: bool`; its `cache` becomes `_CacheOnly`, and its `set_stage` and `append_page_live` stop a read;
  - `rerun_analysis` answers `Rerun(None, READING_NOT_CACHED)` for a stopped run;
  - the test helper `_cache_files(store)`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- the reading comes from the cache, or the re-analysis is refused ------------------------------------------------


def test_a_rerun_runs_no_reader_for_a_statement_whose_reading_is_not_cached(pipeline, private_store):
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    old = _payload()
    job_id = pipeline.upload(old)
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    statuses = len(private_store.storage.audit_events("status_change", job_id=job_id))

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1  # the reader was never called
    assert private_store.storage.cache_entries("ocr") == []  # and nothing was read into the cache
    saved = private_store.get(job_id)
    assert (saved.status, saved.analysis) == ("done", _stamped(old))
    assert len(private_store.storage.audit_events("status_change", job_id=job_id)) == statuses


def test_a_miss_stops_the_run_before_a_reader_that_names_no_stage(pipeline, private_store):
    """The cache lookup is the guard, not the stage a reader names: here nothing but the lookup stands between the run
    and the reader."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    pipeline.announce = False
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1


def test_a_cached_reading_that_fails_its_own_checks_is_not_read_again(pipeline, private_store):
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.drift_ocr()
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1  # stopped where the ladder named its rung, before the rung read


def test_a_reading_that_streams_before_it_names_a_stage_is_stopped(pipeline, private_store):
    """A cached reading that fails its own checks is read again after the lookup answered a hit; a reader that streams
    its text before it names a stage is stopped at its first streamed chunk."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.drift_ocr()
    pipeline.announce, pipeline.stream = False, True
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1


def test_the_visual_pair_is_never_called_for_a_reading_that_is_not_cached(pipeline, private_store, visual_pair):
    """The pair answers from its own evidence, or asks its model servers for their models, before it names a step, so
    on its path the cache lookup is the only guard."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert (len(visual_pair), pipeline.reads) == (1, 0)  # the upload's call, and no other


def test_a_statement_that_now_needs_the_visual_pair_is_refused_without_calling_it(
        pipeline, private_store, visual_pair, monkeypatch):
    """With the pair on, a statement the deterministic path no longer analyses falls back to the visual pair
    (webapp/worker.py), a reading this statement never had."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    monkeypatch.setenv("OCR_ALLOW_VISUAL_PAIR", "1")
    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = RuntimeError("no deterministic parser matched this statement")
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert (visual_pair, pipeline.reads) == ([], 1)


# --- the upload queue's worker stays the artifact cache's one writer ------------------------------------------------


def _cache_files(store):
    """Every artifact-cache entry by stage: its key and the bytes of its file. Hit counts are left out, since serving
    a hit updates them."""
    return {stage: [(entry["cache_key"], (store.cache.root / entry["artifact_path"]).read_bytes())
                    for entry in store.storage.cache_entries(stage)]
            for stage in ("ocr", "analysis", "report")}


def test_a_rerun_writes_no_analysis_and_no_report_into_the_cache(pipeline, private_store):
    """The new analysis and the report rendered again are not cached: an upload of the same statement writing the
    same entry at that moment could fail on the cache's one temporary file per entry."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload())
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    for entry in private_store.storage.cache_entries("report"):
        private_store.storage.cache_forget("report", entry["cache_key"])  # so the report is rendered again
    before = _cache_files(private_store)

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert _cache_files(private_store) == before


def test_a_pair_reading_answered_again_from_the_pair_s_own_evidence_is_not_written_back(
        pipeline, private_store, visual_pair):
    """A cached pair reading that fails its own checks is read again, and the pair answers from its own local
    evidence, naming no step (the fabricated pair answers that way). That answer is a reading already made, so the
    re-analysis goes on with it, and it leaves the drifted entry for the next upload to repair."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    pipeline.drift_ocr()
    before = _cache_files(private_store)

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert (len(visual_pair), pipeline.reads) == (2, 0)
    assert _cache_files(private_store) == before
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 8 failed and 31 passed:
- 6 with `ImportError: cannot import name 'READING_NOT_CACHED' from 'webapp.reanalysis'`;
- the two cache-writer tests at `assert _cache_files(private_store) == before`: Task 6's stand-in writes the new analysis (and, in the first, the report rendered again; in the second, the pair's answer over the drifted entry) into the real cache.

- [ ] **Step 3: Implement.** Three edits to `webapp/reanalysis.py` with the Edit tool.

(a) In the module docstring, replace the paragraph

```python
`rerun_analysis` runs the statement's stored PDF through the worker's own read and analysis path
(`webapp.worker.run_job`) into a stand-in for the job store, so the saved job is not touched until the route accepts
the new analysis.
```

with:

```python
`rerun_analysis` runs the statement's stored PDF through the worker's own read and analysis path
(`webapp.worker.run_job`), its reading served from the artifact cache only: a re-analysis only analyzes a reading
already made, and no reading rung runs. It writes nothing into the cache, whose one writer stays the upload queue's
worker. The run writes into a stand-in for the job store, so the saved job is not touched until the route accepts the
new analysis.
```

(b) Replace the import lines

```python
from .jobs import Job, JobStore
from .worker import run_job
```

with:

```python
from .artifact_cache import ArtifactCache
from .jobs import Job, JobStore
from .worker import run_job
```

(c) Replace the whole block Task 6 Step 3(c) appended, from the line `#: Why a re-run that produced an analysis is still not accepted: under the current rules the analysis comes from` to the end of the file, with:

```python
#: Why a re-analysis stops where the worker would read the statement: the reading it needs is not in the artifact
#: cache (a pruned cache, a new OCR toolchain, or a reading the statement never had, such as the visual pair's where
#: the deterministic path claimed it before). The reading is served from the cache only (spec §8.6.2): a re-analysis
#: runs on the request thread, outside the upload queue's single worker slot, which keeps two OCR jobs from running
#: at once.
READING_NOT_CACHED = (
    "the reading this re-analysis needs is not cached, and a re-analysis only analyzes a reading already made; "
    "upload the statement again instead"
)

#: Why a re-run that produced an analysis is still not accepted: under the current rules the analysis comes from
#: another cached reading of the statement than the one the saved analysis was made from (the worker chose the other
#: of its deterministic and visual-pair paths). The saved analysis and the source view beside it describe one reading,
#: so the saved job is kept.
READS_DIFFERENTLY = (
    "under the current rules the analysis comes from another reading of the statement than the saved one"
)


class _ReadingRefused(Exception):
    """Raised inside `run_job` where a re-analysis would read the statement. The worker's own boundary catches it
    (`run_job`'s `except Exception`) and records its fixed stage failure on the stand-in store; `rerun_analysis`
    answers READING_NOT_CACHED from the stand-in's flag instead."""


class _CacheOnly:
    """The artifact cache as a re-analysis sees it: every stage reads through the real cache, a reading the cache does
    not hold is never computed, and nothing is written into it.

    `cached_ocr` asks `get_ocr` before it computes (webapp/artifact_cache.py), and the worker's reading ladder and its
    visual pair both read through `cached_ocr`, so a miss stops the run before any reader or remote model is called.
    On the visual pair's path this is the only guard: the pair does work before it names its first step.

    The upload queue's worker stays the cache's one writer. The cache writes each entry through one fixed temporary
    file, so a write from this request thread to an entry an upload of the same statement is writing at that moment
    could fail the upload. The three writes below are the only ones the worker's cache helpers make (`cached_ocr`,
    `cached_analysis`, `cached_report`), and each helper ignores the key a write returns. The new analysis is saved
    with the job, and the next upload of the statement caches it."""

    def __init__(self, cache: ArtifactCache, run: _CapturedJobStore) -> None:
        self._cache = cache
        self._run = run

    def __getattr__(self, name: str):
        return getattr(self._cache, name)

    def get_ocr(self, content_hash: str, settings_key: str) -> tuple[bool, dict | None]:
        hit, document = self._cache.get_ocr(content_hash, settings_key)
        if not hit:
            self._run.refuse_reading()
        return hit, document

    def put_ocr(self, content_hash: str, settings_key: str, document: object) -> None:
        # In a re-analysis this is reached only when the visual pair answered again from its own local evidence, over
        # a cached reading that failed its own checks (every rung of the ladder names itself first and is stopped).
        # That entry is left for the next upload to repair.
        return None

    def put_analysis(self, markdown_hash: str, settings_key: str, analysis: dict) -> None:
        return None

    def put_report(self, markdown_hash: str, settings_key: str, html: str) -> None:
        return None


class _CapturedJobStore:
    """What `run_job` is handed during a re-analysis, in place of the job store.

    Its cache is `_CacheOnly`, so no reading rung runs and nothing is written into the cache. Cache hits are recorded
    in the real audit log (the evidence that the reading was served from the cache), but every job-state write lands
    here, so the saved job keeps its status, its stage and its analysis until the route accepts the new one. It has no
    `storage`, so the run writes no telemetry record (`telemetry.emit.open_sqlite_sink` opens a null sink): telemetry
    counts intake runs, and the audit log records the re-analysis. Its methods are exactly the ones `webapp/worker.py`
    calls on its store."""

    def __init__(self, store: JobStore, job: Job) -> None:
        self._store = store
        self.cache = _CacheOnly(store.cache, self)
        self.job = Job(id=job.id, filename=job.filename, force_ocr=job.force_ocr, parse_mode=job.parse_mode,
                       page_count=job.page_count, content_sha256=job.content_sha256)
        self.result: tuple[str, str, dict | None, str | None, str | None] | None = None
        self.error: str | None = None
        self.reading_refused = False

    def refuse_reading(self) -> None:
        """Stop the run where the worker would read the statement."""
        self.reading_refused = True
        raise _ReadingRefused()

    def get(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.id else None

    def record_cache_hit(self, job_id: str, stage: str, cache_key: str | None) -> None:
        self._store.record_cache_hit(job_id, stage, cache_key)

    def set_status(self, job_id: str, status: str) -> None:
        self.job.status = status

    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        # "analyzing" is the one stage the worker names outside a read (`run_job`). Every other stage is a rung of its
        # reading ladder or a step of the visual pair, named just before it reads: a cached reading that fails its own
        # checks is read again by `cached_ocr` after `get_ocr` has answered a hit, and it is stopped here.
        if stage != "analyzing":
            self.refuse_reading()
        self.job.stage = stage

    def append_page_live(self, job_id: str, page: int, chunk: str) -> None:
        # Only a live read streams text.
        self.refuse_reading()

    def set_page_live(self, job_id: str, page: int, text: str) -> None:
        # A cached reading replays its pages here.
        return None

    def set_result(self, job_id: str, markdown: str, html: str, analysis: dict | None = None,
                   analysis_error: str | None = None, parse_model: str | None = None) -> None:
        self.job.status = "done"
        self.result = (markdown, html, analysis, analysis_error, parse_model)

    def set_error(self, job_id: str, error: str) -> None:
        self.job.status = "error"
        self.error = error


@dataclass(frozen=True)
class Rerun:
    """A re-run's new analysis; or None, with the reason it is not accepted: text the worker already publishes for
    that outcome (`_stage_failure`, `_analysis_failure`, its no-native-text notice), READING_NOT_CACHED, or
    READS_DIFFERENTLY."""

    analysis: dict | None
    reason: str | None = None


def rerun_analysis(store: JobStore, job: Job, pdf_bytes: bytes) -> Rerun:
    """Run a saved job's statement through `webapp.worker.run_job` again, with the job's own read flag and parse mode,
    into a `_CapturedJobStore`, its reading from the artifact cache only. Nothing of the saved job is written here."""
    run = _CapturedJobStore(store, job)
    run_job(job.id, pdf_bytes, job.filename, run, force_ocr=job.force_ocr, parse_mode=job.parse_mode)
    if run.reading_refused:
        return Rerun(None, READING_NOT_CACHED)
    if run.error is not None or run.result is None:
        return Rerun(None, run.error)
    markdown, _html, analysis, analysis_error, _parse_model = run.result
    if analysis is None:
        return Rerun(None, analysis_error)
    if markdown != job.markdown:
        return Rerun(None, READS_DIFFERENTLY)
    return Rerun(analysis)
```

- [ ] **Step 4: Run the tests and the worker and cache suites.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_worker_privacy.py tests/test_webapp_worker.py tests/test_artifact_cache.py tests/test_visual_pair_worker.py tests/test_l1s3_census.py -q -p no:cacheprovider`
Expected: PASS (all passed).

- [ ] **Step 5: Commit.**

```bash
git add webapp/reanalysis.py tests/test_webapp_reanalysis.py
git commit -m "webapp: a re-analysis runs no reading rung for a statement whose reading is not cached" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 8: `POST /analysis/<job_id>/reanalyze` replaces a saved analysis in place

**Files:**
- Modify: `webapp/app.py` (import after line 37; the route after line 2422, the last line of `revenue_reviews`, before `@app.route("/package_analysis")` at line 2425)
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes:
  - `rerun_analysis`, `replay_reviews`, `READING_NOT_CACHED` (Tasks 4-7);
  - `JobStore.apply_reanalysis` (Task 2);
  - `JobStore.pdf_bytes`, `JobStore.review_history`;
  - `_displayed(analysis)` (today `webapp/app.py:197`; S3 adds keyword arguments, and this call passes none);
  - `_masked` (`webapp/app.py:209`);
  - `_ruled` (Task 5).
- Produces the contract's C9, with the ratification items:
  - `POST /analysis/<job_id>/reanalyze` → 200 `{"analysis": <displayed, masked>, "reviews_replayed": int, "reviews_not_replayed": int, "reviews_decided_by_rules": int}`;
  - 404 `{"error": "job not found"}`;
  - 409 `{"error": "job is not finished"}`;
  - 409 `{"error": "the original PDF is not stored"}`;
  - 400 `{"error": "the request must be a JSON object"}` and 422 `{"error": REANALYSIS_NOT_SAVED, "reason": str}` (Decisions 3 and 4);
  - `webapp.app.REANALYSIS_NOT_SAVED: str`;
  - test helpers `_reanalyze`, `_review`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- the route ------------------------------------------------------------------------------------------------------


def _reanalyze(job_id, body=None):
    from webapp.app import app

    return app.test_client().post(f"/analysis/{job_id}/reanalyze", json={} if body is None else body)


def _review(job_id, location, decision):
    from webapp.app import app

    response = app.test_client().post(f"/analysis/{job_id}/revenue-review",
                                      json={"source_location": location, "decision": decision})
    assert response.status_code == 200


def test_a_reanalysis_replaces_the_analysis_in_place(pipeline, private_store):
    from webapp.app import app

    old, new = _payload(), _payload(SHIFTED_ROWS)
    job_id = pipeline.upload(old)
    before = private_store.storage.load_job(job_id)
    pipeline.new_rules(new)

    response = _reanalyze(job_id)

    assert response.status_code == 200
    body = response.get_json()
    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (0, 0, 0)
    # The same job: its id, its creation time and its source view do not change; its analysis does.
    after = private_store.storage.load_job(job_id)
    assert after["id"] == job_id and after["status"] == "done"
    assert (after["created_at"], after["markdown"], after["html"]) == (
        before["created_at"], before["markdown"], before["html"])
    assert private_store.get(job_id).analysis == _stamped(new)
    assert json.loads(after["analysis_json"]) == _json(_stamped(new))
    # The page is drawn from the answer, which is the analysis as /analysis/<job> now serves it, masked.
    assert body["analysis"] == app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]
    assert body["analysis"]["statement"]["account_number"] == "****1010"
    # The analysis replaced is in the audit log, verbatim.
    events = private_store.storage.audit_events("reanalysis", job_id=job_id)
    assert len(events) == 1
    detail = json.loads(events[0]["detail"])
    assert detail["previous_analysis_json"] == before["analysis_json"]
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [], [], [])
    # A restart reads the new analysis back.
    assert JobStore(Storage(private_store.storage.data_dir)).get(job_id).analysis == _json(_stamped(new))


def test_a_reanalysis_replays_the_revenue_decisions_whose_posting_is_unchanged(pipeline, private_store):
    job_id = pipeline.upload(_payload())
    _review(job_id, "transaction:2", "confirm")  # unchanged under the new rules: replayed
    _review(job_id, "transaction:3", "reject")   # its row now prints another amount: needs redoing
    _review(job_id, "transaction:4", "confirm")
    _review(job_id, "transaction:4", "reset")    # left pending: nothing to redo
    history = private_store.review_history(job_id)
    pipeline.new_rules(_payload(CHANGED_ROWS))

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (1, 1, 0)
    records = _records(private_store.get(job_id).analysis)
    assert records["transaction:2"]["revenue_review_status"] == "confirmed"
    assert records["transaction:2"]["revenue_reviewed_at"] == history[0]["decided_at"]
    assert records["transaction:3"]["revenue_review_status"] == "pending"
    assert records["transaction:4"]["revenue_review_status"] == "pending"
    assert _records(body["analysis"])["transaction:2"]["revenue_review_status"] == "confirmed"
    # The audit row names the decisions by id; replaying records no decision of its own.
    detail = json.loads(private_store.storage.audit_events("reanalysis", job_id=job_id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [history[0]["id"]], [history[1]["id"]], [])
    assert private_store.review_history(job_id) == history


def test_a_reanalysis_reports_the_reviews_a_rule_now_decides(pipeline, private_store):
    """Nothing re-labels silently (D12): a deposit the analyst confirmed that a rule of the current analysis now
    decides is not replayed, and the answer says so."""
    job_id = pipeline.upload(_payload())
    _review(job_id, "transaction:2", "confirm")
    history = private_store.review_history(job_id)
    pipeline.new_rules(_ruled(_payload(), "transaction:2"))

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (0, 0, 1)
    record = _records(private_store.get(job_id).analysis)["transaction:2"]
    assert (record["revenue_classification"], record["revenue_review_status"]) == ("non_revenue", "not_required")
    detail = json.loads(private_store.storage.audit_events("reanalysis", job_id=job_id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [], [], [history[0]["id"]])


def test_a_reanalysis_puts_each_account_s_decisions_back_on_that_account(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_two_accounts())
    response = app.test_client().post(f"/analysis/{job_id}/revenue-reviews", json={"decisions": [
        {"source_location": "transaction:2", "decision": "confirm", "account": 1},
        {"source_location": "transaction:2", "decision": "reject", "account": 2}]})
    assert response.status_code == 200
    pipeline.new_rules(_two_accounts())

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"]) == (2, 0)
    analysis = private_store.get(job_id).analysis
    assert _records(analysis, 1)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(analysis, 2)["transaction:2"]["revenue_review_status"] == "rejected"


def test_an_unknown_job_is_not_found(private_store):
    response = _reanalyze("no-such-job")
    assert response.status_code == 404 and response.get_json() == {"error": "job not found"}


def test_a_job_that_is_not_finished_is_refused(private_store):
    queued = private_store.create("fabricated.pdf", pdf_bytes=PDF)  # still waiting for the worker
    failed = private_store.create("fabricated.pdf", pdf_bytes=PDF)
    private_store.set_error(failed.id, "fabricated failure")
    for job_id in (queued.id, failed.id):
        response = _reanalyze(job_id)
        assert response.status_code == 409 and response.get_json() == {"error": "job is not finished"}
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_job_whose_pdf_is_not_stored_is_refused(pipeline, private_store):
    job_id = pipeline.upload(_payload())
    before = copy.deepcopy(private_store.get(job_id).analysis)
    private_store.storage.pdf_path(private_store.get(job_id).content_sha256).unlink()  # the stored PDF is gone
    never = private_store.create("fabricated.pdf")  # a job saved without its PDF
    private_store.set_result(never.id, "# F", "<p>F</p>", analysis=_payload())
    for refused in (job_id, never.id):
        response = _reanalyze(refused)
        assert response.status_code == 409 and response.get_json() == {"error": "the original PDF is not stored"}
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_request_that_is_not_a_json_object_is_refused(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    before = copy.deepcopy(private_store.get(job_id).analysis)
    form = app.test_client().post(f"/analysis/{job_id}/reanalyze",
                                  data={"reanalyze": "1"})  # a cross-site form cannot send JSON
    listed = _reanalyze(job_id, ["reanalyze"])
    assert form.status_code == listed.status_code == 400
    assert form.get_json() == {"error": "the request must be a JSON object"}
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_reanalysis_that_produces_no_analysis_keeps_the_saved_one(pipeline, private_store):
    from webapp.app import REANALYSIS_NOT_SAVED

    job_id = pipeline.upload(_payload())
    before = copy.deepcopy(private_store.get(job_id).analysis)
    stored_text = private_store.storage.load_job(job_id)["analysis_json"]
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = RuntimeError("FABRICATED STATEMENT TEXT")

    response = _reanalyze(job_id)

    assert response.status_code == 422
    assert response.get_json() == {"error": REANALYSIS_NOT_SAVED,
                                   "reason": f"analysis stage failed: RuntimeError {WITHHELD}"}
    assert REANALYSIS_NOT_SAVED == "no new analysis was saved; the saved analysis is unchanged"
    assert "FABRICATED STATEMENT TEXT" not in response.get_data(as_text=True)
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.load_job(job_id)["analysis_json"] == stored_text
    assert private_store.storage.audit_events("reanalysis", job_id=job_id) == []


def test_a_statement_whose_reading_is_not_cached_is_refused_and_runs_no_reader(pipeline, private_store):
    from webapp.app import REANALYSIS_NOT_SAVED
    from webapp.reanalysis import READING_NOT_CACHED

    job_id = pipeline.upload(_payload())
    stored_text = private_store.storage.load_job(job_id)["analysis_json"]
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()

    response = _reanalyze(job_id)

    assert response.status_code == 422
    assert response.get_json() == {"error": REANALYSIS_NOT_SAVED, "reason": READING_NOT_CACHED}
    assert READING_NOT_CACHED == ("the reading this re-analysis needs is not cached, and a re-analysis only "
                                  "analyzes a reading already made; upload the statement again instead")
    assert pipeline.reads == 1  # the upload's read, and no other
    assert private_store.storage.load_job(job_id)["analysis_json"] == stored_text
    assert private_store.storage.audit_events("reanalysis", job_id=job_id) == []
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py -q -p no:cacheprovider`
Expected: FAIL. 10 failed and 39 passed. No route matches, so every POST answers Flask's HTML 404, whose body is not JSON:
- `assert 404 == 200` in `test_a_reanalysis_replaces_the_analysis_in_place`;
- `TypeError: 'NoneType' object is not subscriptable` in the three replay tests, which read the body's counts;
- in the refusal tests, `assert (404 == 404 and None == {'error': 'job not found'})` for the unknown job, `assert (404 == 409)` for the unfinished and PDF-less jobs, and `assert 404 == 400` for the body that is not a JSON object;
- `ImportError: cannot import name 'REANALYSIS_NOT_SAVED' from 'webapp.app'` in the last two tests.

- [ ] **Step 3: Implement.** Two edits to `webapp/app.py` with the Edit tool.

(a) After line 37, `from .worker import run_job`, add:

```python
from .reanalysis import replay_reviews, rerun_analysis
```

(b) The `old_string` is the last line of `revenue_reviews` plus the two blank lines and the `/package_analysis` decorator:

```python
    return jsonify({"analysis": _masked(_displayed(stored)), "applied": len(parsed)})


@app.route("/package_analysis")
```

Replace it with:

```python
    return jsonify({"analysis": _masked(_displayed(stored)), "applied": len(parsed)})


#: A re-analysis with no analysis to save: none was produced, or the one produced was refused. The saved analysis
#: stays; the `reason` beside this is text the worker already publishes for the same outcome (`webapp/worker.py`
#: `_stage_failure` / `_analysis_failure`) or `webapp/reanalysis.py`'s READING_NOT_CACHED or READS_DIFFERENTLY, never
#: an exception's own text.
REANALYSIS_NOT_SAVED = "no new analysis was saved; the saved analysis is unchanged"


@app.route("/analysis/<job_id>/reanalyze", methods=["POST"])
def reanalyze(job_id):
    """Analyze a saved statement again under the current rules (spec §8.6, D12) and replace its analysis in place:
    the job keeps its id and its place in Recent.

    The stored PDF (kept on disk by content hash) goes through the worker's own read and analysis path, its reading
    served from the artifact cache only (`webapp/reanalysis.py::rerun_analysis`): a statement whose reading is not
    cached is refused and no reading rung runs, so this request thread never competes with the upload queue's worker
    for OCR. The analysis replaced is written to the audit log first, in the same transaction as the replacement
    (`JobStore.apply_reanalysis`), and the analyst's revenue decisions are replayed where their posting is unchanged
    (`replay_reviews`); the answer counts those replayed, those that need redoing and those a rule now decides. JSON
    only, like the review and settings routes: a cross-site HTML form cannot send it without a preflight."""
    if not isinstance(request.get_json(silent=True), dict):
        return jsonify({"error": "the request must be a JSON object"}), 400
    job = store.get(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404
    if job.status != "done":
        return jsonify({"error": "job is not finished"}), 409
    pdf_bytes = store.pdf_bytes(job_id)
    if pdf_bytes is None:
        return jsonify({"error": "the original PDF is not stored"}), 409
    rerun = rerun_analysis(store, job, pdf_bytes)
    if rerun.analysis is None:
        return jsonify({"error": REANALYSIS_NOT_SAVED, "reason": rerun.reason}), 422
    replay = replay_reviews(rerun.analysis, store.review_history(job_id))
    stored = store.apply_reanalysis(
        job_id, replay.analysis, replayed=replay.replayed, not_replayed=replay.not_replayed,
        decided_by_rules=replay.decided_by_rules)
    if stored is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify({
        "analysis": _masked(_displayed(stored)),
        "reviews_replayed": len(replay.replayed),
        "reviews_not_replayed": len(replay.not_replayed),
        "reviews_decided_by_rules": len(replay.decided_by_rules),
    })


@app.route("/package_analysis")
```

- [ ] **Step 4: Run the tests and the webapp suites.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_webapp_revenue_batch.py tests/test_webapp_app.py tests/test_webapp_security.py tests/test_worker_privacy.py tests/test_privacy3_boundaries.py tests/test_queue_supervisor.py tests/test_l1s3_census.py -q -p no:cacheprovider`
Expected: PASS (all passed; 49 in `tests/test_webapp_reanalysis.py`).

- [ ] **Step 5: Commit.**

```bash
git add webapp/app.py tests/test_webapp_reanalysis.py
git commit -m "webapp: POST /analysis/<job>/reanalyze replaces a saved analysis in place" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 9: A re-analysis holds the statement's review lock

**Files:**
- Modify: `webapp/app.py`, the `reanalyze` function written in Task 8
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes: `_review_lock(job_id) -> threading.Lock` and `_review_locks` (`webapp/app.py:2277-2286`).
- Produces: no new name. `reanalyze` now serializes with `revenue_review` / `revenue_reviews` on the same job.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_webapp_reanalysis.py`:

```python
def test_a_review_waits_for_a_reanalysis_of_the_same_statement(pipeline, private_store, monkeypatch):
    """A row's decision while its statement is being re-analyzed. Without the statement's lock it would be saved on
    the old analysis and then overwritten when the re-analysis saved its own, while its decision row stayed
    recorded."""
    from webapp import app as webapp_app

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload())
    entered, release = threading.Event(), threading.Event()
    save = private_store.apply_reanalysis

    def held_save(*args, **kwargs):
        entered.set()
        release.wait(5)
        return save(*args, **kwargs)

    monkeypatch.setattr(private_store, "apply_reanalysis", held_save)
    results = {}
    rerun = threading.Thread(target=lambda: results.update(rerun=_reanalyze(job_id)))
    review = threading.Thread(target=lambda: results.update(review=webapp_app.app.test_client().post(
        f"/analysis/{job_id}/revenue-review", json={"source_location": "transaction:3", "decision": "reject"})))
    rerun.start()
    assert entered.wait(5)
    review.start()
    review.join(timeout=1)
    waited = review.is_alive()
    release.set()
    rerun.join(5)
    review.join(5)
    assert waited
    assert results["rerun"].status_code == results["review"].status_code == 200
    assert _records(private_store.get(job_id).analysis)["transaction:3"]["revenue_review_status"] == "rejected"
    # A request naming no statement leaves no lock behind: the table of locks holds statements, not guesses.
    assert _reanalyze("no-such-job").status_code == 404 and "no-such-job" not in webapp_app._review_locks
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py::test_a_review_waits_for_a_reanalysis_of_the_same_statement -q -p no:cacheprovider`
Expected: FAIL at `assert waited` (`assert False`). Without the lock the review completes while the re-analysis is held.

- [ ] **Step 3: Implement.** With the Edit tool, replace the whole `reanalyze` function from Task 8 (its decorator line through its final `})`) with:

```python
@app.route("/analysis/<job_id>/reanalyze", methods=["POST"])
def reanalyze(job_id):
    """Analyze a saved statement again under the current rules (spec §8.6, D12) and replace its analysis in place:
    the job keeps its id and its place in Recent.

    The stored PDF (kept on disk by content hash) goes through the worker's own read and analysis path, its reading
    served from the artifact cache only (`webapp/reanalysis.py::rerun_analysis`): a statement whose reading is not
    cached is refused and no reading rung runs, so this request thread never competes with the upload queue's worker
    for OCR. The analysis replaced is written to the audit log first, in the same transaction as the replacement
    (`JobStore.apply_reanalysis`), and the analyst's revenue decisions are replayed where their posting is unchanged
    (`replay_reviews`); the answer counts those replayed, those that need redoing and those a rule now decides. JSON
    only, like the review and settings routes: a cross-site HTML form cannot send it without a preflight.

    Held under the statement's review lock from reading the job to saving the new analysis: a decision saved in
    between would land on the old analysis and then be overwritten, while its decision row stayed recorded. Reviews
    of other statements do not wait."""
    if not isinstance(request.get_json(silent=True), dict):
        return jsonify({"error": "the request must be a JSON object"}), 400
    if store.get(job_id) is None:
        return jsonify({"error": "job not found"}), 404
    with _review_lock(job_id):
        job = store.get(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        if job.status != "done":
            return jsonify({"error": "job is not finished"}), 409
        pdf_bytes = store.pdf_bytes(job_id)
        if pdf_bytes is None:
            return jsonify({"error": "the original PDF is not stored"}), 409
        rerun = rerun_analysis(store, job, pdf_bytes)
        if rerun.analysis is None:
            return jsonify({"error": REANALYSIS_NOT_SAVED, "reason": rerun.reason}), 422
        replay = replay_reviews(rerun.analysis, store.review_history(job_id))
        stored = store.apply_reanalysis(
            job_id, replay.analysis, replayed=replay.replayed, not_replayed=replay.not_replayed,
            decided_by_rules=replay.decided_by_rules)
    if stored is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify({
        "analysis": _masked(_displayed(stored)),
        "reviews_replayed": len(replay.replayed),
        "reviews_not_replayed": len(replay.not_replayed),
        "reviews_decided_by_rules": len(replay.decided_by_rules),
    })
```

- [ ] **Step 4: Run the whole file and the review suites.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_webapp_revenue_batch.py tests/test_worker_privacy.py -q -p no:cacheprovider`
Expected: PASS (all passed; 50 in `tests/test_webapp_reanalysis.py`).

- [ ] **Step 5: Commit.**

```bash
git add webapp/app.py tests/test_webapp_reanalysis.py
git commit -m "webapp: a re-analysis holds the statement's review lock" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 10: The Re-analyze button re-runs the statement shown and draws the answer

**Files:**
- Modify: `webapp/static/app.js`, five edits, each anchored on quoted text:
  - the review flags (lines 804-806): `reanalysisBusy` after `rowReviewsInFlight`;
  - `syncBulkReview`'s `held` (line 837);
  - `submitBulkReview`'s guard (line 933);
  - `submitRevenueReview`'s guard (lines 4162-4163);
  - the new block after line 4223, the `});` that closes `els.bulkReviewBar?.addEventListener("click", ...)`, and before line 4225, `document.querySelectorAll("[data-transaction-filter]").forEach((button) => {`.
- Test: `tests/test_webapp_reanalysis_ui.py` (create). Needs `node` on PATH.

**Interfaces:**
- Consumes:
  - the route's answer `{analysis, reviews_replayed, reviews_not_replayed, reviews_decided_by_rules}` and `{error, reason?}` (Task 8);
  - C8's button id `reanalyzeButton`;
  - existing app.js functions and state: `responseJson` (:867), `holdRowReviews` (:823), `syncBulkReview` (:831), `clearBulkSelection` (:859), `showNotifications` (:893), `submitBulkReview` (:932), `submitRevenueReview` (:4157), `renderAnalysis` (:2271), `setActions` (:1174), `appendStatusExports` (:2853), `rememberShownStatement` (:3743), `notify` (:3920), `formatNumber` (:338), `bulkBusy`, `rowReviewsInFlight`, `currentJobId`, `currentJobIds`, `currentAnalysis` and `currentDocument`;
  - test helpers: `DRAWN` (`tests/test_webapp_review_ui.py:17-37`: `tick`, `press`, `boxesIn`, `buttonsIn`, `posts`), `_pending` (`tests/test_webapp_studio_views.py:454-457`).
- Produces:
  - `let reanalysisBusy` (a top-level flag beside `bulkBusy`);
  - `function reviewsLabel(count) -> string`;
  - `function reanalysisNotice(payload) -> [text, tone]`;
  - `async function reanalyzeShownStatement()`;
  - a `click` listener on `#reanalyzeButton`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_webapp_reanalysis_ui.py` with the Write tool:

```python
"""The Re-analyze button of the outdated-rules notice (spec §8.6; the interface contract's C8 and C9), driven end to
end: the whole webapp/static/app.js runs in node on a fake page (tests/webapp_js_harness.py). The notice's markup and
when it shows belong to the dashboard's own plan (C8); this file drives the button. Fabricated statements only."""
import json

import pytest

from tests.test_webapp_review_ui import DRAWN
from tests.test_webapp_studio_views import CHECKING_ROWS, _pending, _report, _serve
from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# One more deposit read under the new rules, so the page drawn from the answer is told apart from the one before.
LATE_ROW = (20, "DEPOSIT FABRICATED LATE", 100.0)


def _statement(rows, month=3):
    """A fabricated business checking statement, analysed by the real analysis path."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows, month))


def _answer(analysis, replayed=0, not_replayed=0, decided_by_rules=0):
    """What POST /analysis/<job>/reanalyze answers."""
    return {"json": {"analysis": analysis, "reviews_replayed": replayed, "reviews_not_replayed": not_replayed,
                     "reviews_decided_by_rules": decided_by_rules}}


def _open_stale(answer):
    """The statement `stale` open as a reopen from Recent shows it, its re-analysis answering `answer`. The button
    carries the label the dashboard draws, the notifications are closed, and the requests so far are forgotten."""
    return (_serve(stale=_statement(CHECKING_ROWS))
            + f"Object.assign(FAKE_RESPONSES, {json.dumps({'/analysis/stale/reanalyze': answer})});\n" + """
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale'); await settle();
const button = document.getElementById('reanalyzeButton');
button.textContent = 'Re-analyze';
els.notificationsPopover.hidden = true;
REQUESTS.length = 0;
""")


CLICK = """
button.dispatch('click', {});
const during = {disabled: button.disabled, label: button.textContent};
await settle();
"""


def test_the_button_reanalyzes_the_statement_shown_and_draws_the_answer():
    fresh = _statement([*CHECKING_ROWS, LATE_ROW])
    result = run_dashboard(_open_stale(_answer(fresh, replayed=2, not_replayed=1, decided_by_rules=1)) + CLICK + """
console.log(JSON.stringify({
  requests: REQUESTS.map((request) => [request.method, request.url, request.body]),
  during, after: {disabled: button.disabled, label: button.textContent},
  rows: currentAnalysis.statement.transactions.length,
  notice: notifications[0], opened: !els.notificationsPopover.hidden}));
""")
    # One request: the page is drawn from the answer, not fetched again.
    assert result["requests"] == [["POST", "/analysis/stale/reanalyze", "{}"]]
    assert result["rows"] == len(CHECKING_ROWS) + 1
    # Held while the statement is re-analyzed, and given its label back after.
    assert result["during"] == {"disabled": True, "label": "Re-analyzing..."}
    assert result["after"] == {"disabled": False, "label": "Re-analyze"}
    # A review that could not be replayed is not left to a dot: the notifications open on it.
    assert result["notice"]["text"] == ("Re-analyzed with the current rules; 1 review needs redoing; "
                                        "1 review is now decided by the rules")
    assert result["notice"]["tone"] == "amber" and result["opened"] is True


def test_the_notification_counts_the_reviews_kept_redone_and_decided_by_the_rules():
    result = run_dashboard("""
console.log(JSON.stringify([[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [4, 3, 0], [0, 0, 1], [2, 1, 2]].map(
  ([kept, redo, ruled]) => reanalysisNotice(
    {reviews_replayed: kept, reviews_not_replayed: redo, reviews_decided_by_rules: ruled}))));
""")
    done = "Re-analyzed with the current rules"
    assert result == [
        [done, "green"], [f"{done}; 1 review kept", "green"], [f"{done}; 2 reviews kept", "green"],
        [f"{done}; 1 review needs redoing", "amber"], [f"{done}; 3 reviews need redoing", "amber"],
        [f"{done}; 1 review is now decided by the rules", "amber"],
        [f"{done}; 1 review needs redoing; 2 reviews are now decided by the rules", "amber"]]


def test_a_reanalysis_that_kept_every_review_is_a_quiet_success():
    result = run_dashboard(_open_stale(_answer(_statement(CHECKING_ROWS), replayed=2)) + CLICK + """
console.log(JSON.stringify({notice: notifications[0], opened: !els.notificationsPopover.hidden}));
""")
    assert result["notice"]["text"] == "Re-analyzed with the current rules; 2 reviews kept"
    assert result["notice"]["tone"] == "green" and result["opened"] is False


@pytest.mark.parametrize("answer, text", [
    ({"status": 409, "json": {"error": "the original PDF is not stored"}},
     "Not re-analyzed: the original PDF is not stored"),
    ({"status": 422, "json": {"error": "no new analysis was saved; the saved analysis is unchanged",
                              "reason": "no deterministic parser matched this statement"}},
     "Not re-analyzed: no new analysis was saved; the saved analysis is unchanged "
     "(no deterministic parser matched this statement)"),
    ({"status": 502, "text": "bad gateway"}, "Not re-analyzed: status 502"),
])
def test_a_refusal_keeps_the_statement_on_screen_and_says_why(answer, text):
    result = run_dashboard(_open_stale(answer) + CLICK + """
console.log(JSON.stringify({rows: currentAnalysis.statement.transactions.length, notice: notifications[0],
  opened: !els.notificationsPopover.hidden, after: {disabled: button.disabled, label: button.textContent}}));
""")
    assert result["rows"] == len(CHECKING_ROWS)
    assert (result["notice"]["text"], result["notice"]["tone"]) == (text, "red")
    assert result["opened"] is True
    assert result["after"] == {"disabled": False, "label": "Re-analyze"}


def test_the_statement_keeps_its_place_in_recent():
    fresh = _statement([*CHECKING_ROWS, LATE_ROW])
    result = run_dashboard(_serve(other=_statement(CHECKING_ROWS, month=4)) + _open_stale(_answer(fresh)) + """
currentJobId = 'other'; currentJobIds = ['other']; loadResults('other'); await settle();
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale', {reveal: false}); await settle();
const before = recentAnalyses.map((item) => item.key);
""" + CLICK + """
console.log(JSON.stringify({before, after: recentAnalyses.map((item) => item.key),
  rows: currentAnalysis.statement.transactions.length}));
""")
    assert result["before"] == result["after"] == ["other", "stale"]
    assert result["rows"] == len(CHECKING_ROWS) + 1


def test_one_click_sends_one_request_and_a_package_sends_none():
    result = run_dashboard(_open_stale(_answer(_statement(CHECKING_ROWS))) + """
button.dispatch('click', {}); button.dispatch('click', {});
await settle();
const single = REQUESTS.filter((request) => request.method === 'POST').length;
currentJobIds = ['stale', 'other'];
button.dispatch('click', {});
await settle();
console.log(JSON.stringify({single, package: REQUESTS.filter((request) => request.method === 'POST').length - single}));
""")
    assert result == {"single": 1, "package": 0}


def test_reviews_wait_while_the_statement_is_being_reanalyzed():
    """A decision made while the re-analysis is in flight would name a row of the analysis it is about to replace:
    neither the bulk bar's batch nor a row's own button sends anything until it answers."""
    answer = json.dumps({"/analysis/stale/reanalyze": _answer(_pending(3))})
    result = run_dashboard(DRAWN + _serve(stale=_pending(3)) + f"Object.assign(FAKE_RESPONSES, {answer});\n" + """
currentJobId = 'stale'; currentJobIds = ['stale']; loadResults('stale'); await settle();
const reanalyze = document.getElementById('reanalyzeButton');
tick(boxesIn(els.transactionTable.innerHTML)[0]);
const row = fakeElement('row'); Object.assign(row.attributes, buttonsIn(els.transactionTable.innerHTML)[0]);
REQUESTS.length = 0;
reanalyze.dispatch('click', {});
press('confirm');
await submitRevenueReview(row);
await settle();
console.log(JSON.stringify({posts: posts().map(([url]) => url), selected: bulkSelection.size,
  busy: [reanalysisBusy, bulkBusy, rowReviewsInFlight]}));
""")
    # The re-analysis answered: its new rows took the tick away, and every flag is down again.
    assert result == {"posts": ["/analysis/stale/reanalyze"], "selected": 0, "busy": [False, False, 0]}
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis_ui.py -q -p no:cacheprovider`
Expected: FAIL. 9 failed:
- no listener exists, so `requests == []` and `during.disabled` is false;
- `reanalysisNotice is not defined` and `reanalysisBusy is not defined`, so node exits 1 and the harness asserts `returncode == 0`;
- the notification assertions see the load's own "... analyzed" entry.

- [ ] **Step 3: Implement.** Five edits to `webapp/static/app.js` with the Edit tool.

(a) The review flags. Replace this `old_string` (lines 804-806):

```js
let bulkBusy = false;
// Reviews of single rows still waiting for the server: the bar's decisions wait for them, and they for the bar's.
let rowReviewsInFlight = 0;
```

with:

```js
let bulkBusy = false;
// Reviews of single rows still waiting for the server: the bar's decisions wait for them, and they for the bar's.
let rowReviewsInFlight = 0;
// A re-analysis of the statement on screen still waiting for the server (reanalyzeShownStatement): every review waits
// for it, since its answer replaces the rows a decision names; and it waits for them.
let reanalysisBusy = false;
```

(b) `syncBulkReview` holds the bar during a re-analysis. Replace this `old_string` (line 837):

```js
  const held = bulkBusy || rowReviewsInFlight > 0;
```

with:

```js
  const held = bulkBusy || rowReviewsInFlight > 0 || reanalysisBusy;
```

(c) The batch waits. Replace this `old_string` (line 933):

```js
  if (bulkBusy || rowReviewsInFlight > 0 || !bulkSelection.size) return;
```

with:

```js
  if (bulkBusy || rowReviewsInFlight > 0 || reanalysisBusy || !bulkSelection.size) return;
```

(d) A row's own decision waits. Replace this `old_string` (lines 4162-4163):

```js
  // While the multi-select's batch is being saved, a row's own decision waits: both would start from one analysis.
  if (!jobId || !sourceLocation || !decision || bulkBusy) return;
```

with:

```js
  // While the multi-select's batch is being saved, a row's own decision waits: both would start from one analysis.
  // While the statement is re-analyzed it waits too: the row it names is about to be replaced.
  if (!jobId || !sourceLocation || !decision || bulkBusy || reanalysisBusy) return;
```

(e) The new block. Replace this `old_string` (lines 4221-4225):

```js
  if (action === "clear") clearBulkSelection({ refocus: true });
  else submitBulkReview(action);
});

document.querySelectorAll("[data-transaction-filter]").forEach((button) => {
```

with:

```js
  if (action === "clear") clearBulkSelection({ refocus: true });
  else submitBulkReview(action);
});

/* --- re-analysis of a saved statement ---------------------------------------
   The Re-analyze button of the outdated-rules notice (#reanalyzeButton; the results page draws the notice and decides
   when it shows) runs the statement on screen again under the current rules. POST /analysis/<job>/reanalyze replaces
   its saved analysis in place (the same statement, in the same place in Recent) and answers with the new one, so the
   page is drawn again from the answer. The analyst's revenue decisions come back where their row is unchanged; the
   notification says how many need redoing and how many a rule of the current analysis now decides. While it runs,
   every review waits (reanalysisBusy, declared beside bulkBusy). */
function reviewsLabel(count) {
  return `${formatNumber(count)} ${count === 1 ? "review" : "reviews"}`;
}

// [text, tone] of the notification a finished re-analysis leaves. A review that needs redoing, or that a rule now
// decides in the analyst's place, is news the analyst must see: amber, and the notifications open on it.
function reanalysisNotice(payload) {
  const kept = Number(payload.reviews_replayed) || 0;
  const redo = Number(payload.reviews_not_replayed) || 0;
  const ruled = Number(payload.reviews_decided_by_rules) || 0;
  const done = "Re-analyzed with the current rules";
  const news = [];
  if (redo) news.push(`${reviewsLabel(redo)} ${redo === 1 ? "needs" : "need"} redoing`);
  if (ruled) news.push(`${reviewsLabel(ruled)} ${ruled === 1 ? "is" : "are"} now decided by the rules`);
  if (news.length) return [`${done}; ${news.join("; ")}`, "amber"];
  return [kept ? `${done}; ${reviewsLabel(kept)} kept` : done, "green"];
}

async function reanalyzeShownStatement() {
  const jobId = currentJobId;
  // One statement on screen, and none of its decisions being saved: the answer would be drawn over them.
  if (reanalysisBusy || bulkBusy || rowReviewsInFlight > 0 || !jobId || currentJobIds.length > 1) return;
  reanalysisBusy = true;
  const button = document.getElementById("reanalyzeButton");
  const label = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "Re-analyzing...";
  }
  // Every review waits for the answer: the bar's buttons and the rows' own are held.
  syncBulkReview();
  holdRowReviews(true);
  let saved = false;
  try {
    const response = await fetch(`/analysis/${encodeURIComponent(jobId)}/reanalyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const payload = await responseJson(response);
    if (!response.ok || !payload.analysis) {
      const reason = payload.reason ? ` (${payload.reason})` : "";
      throw new Error(payload.error ? `${payload.error}${reason}` : `status ${response.status}`);
    }
    saved = true;
    if (currentJobId === jobId && currentJobIds.length <= 1) {
      // The rows were read afresh: a tick made on the old rows could name another posting now.
      clearBulkSelection();
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      if (currentAnalysis || currentDocument) rememberShownStatement(jobId);
      else appendStatusExports(`/download/${encodeURIComponent(jobId)}`);
    }
    const [text, tone] = reanalysisNotice(payload);
    notify(text, tone);
    if (tone !== "green") showNotifications();
  } catch (error) {
    const message = error.message || String(error);
    notify(saved ? `Re-analyzed, but ${message}: open the statement again to see it` : `Not re-analyzed: ${message}`,
      "red");
    showNotifications();
  } finally {
    reanalysisBusy = false;
    // No batch and no row's decision can have started meanwhile (their guards read reanalysisBusy), so every review
    // button is given back.
    holdRowReviews(false);
    syncBulkReview();
    if (button) {
      button.disabled = false;
      button.textContent = label;
    }
  }
}

document.getElementById("reanalyzeButton")?.addEventListener("click", () => { reanalyzeShownStatement(); });

document.querySelectorAll("[data-transaction-filter]").forEach((button) => {
```

- [ ] **Step 4: Run the new tests and every guard that reads `app.js`.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis_ui.py tests/test_webapp_review_ui.py tests/test_webapp_studio_views.py tests/test_webapp_accounts_view.py tests/test_webapp_confidence_label.py tests/test_package_currency.py tests/test_lender_insurance_classification.py::test_browser_consumes_classification_records_without_keyword_scans tests/test_revenue_classification.py::test_revenue_ui_uses_authoritative_fields_and_exposes_review_controls tests/test_adb.py::test_dashboard_balance_cards_bind_to_backend_fields_without_recalculation tests/test_privacy3_boundaries.py -q -p no:cacheprovider`
Expected: PASS (all passed; 9 in `tests/test_webapp_reanalysis_ui.py`).

- [ ] **Step 5: Commit.**

```bash
git add webapp/static/app.js tests/test_webapp_reanalysis_ui.py
git commit -m "dashboard: the Re-analyze button re-runs the statement shown; reviews wait for it" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 11 (after S2 and S3 have merged into `lender-detection`): integration pins on the 5.0 rules and the eleven flag groups

The orchestrator starts this task once both S2 and S3 are merged (see the sequencing constraint). Both tests are written and seen to fail on the pre-rebase branch, then pass after one rebase. S5's other fixtures never import S2 or S3 code. Every test in `tests/test_webapp_reanalysis.py` and `tests/test_webapp_reanalysis_ui.py` builds its payloads with the real classifier, whatever version it is, so all of them are re-run on the rebased branch.

**What these pins prove, and what they do not.** `_Pipeline` fakes the analysis stage, so the 5.0 records come from `_payload()`, which runs S2's real classifier inside the test. The tests do not show that a re-analysis applies the current rules; Task 8 pins S5's own behaviour (the saved analysis becomes whatever the current analysis stage produced). They show that on the rebased branch:
- an analysis carrying every one of the eleven flag groups, with S2's new states and record fields, goes through S5's replay and replacement, is saved whole and is served back through S3's serving (every flagged row shown, since every group is ticked by default);
- premium financing, the one group with no state of its own, is saved as an `insurance` row that keeps `contributes_to_insurance_totals` and also carries `flagged_group="premium_financing"` and `contributes_to_flagged_totals`;
- an analyst's confirmation of a deposit that the 5.0 rules now decide (a floor-plan or factoring credit, which is financing proceeds under D1 since both states are in `FINANCING_STATES`, and a premium-finance credit, which keeps the insurance credit treatment) is reported as decided by the rules, while an ordinary deposit's decision is replayed;
- C6's `analysis_rules_outdated` is true on the saved analysis before the re-analysis and false after it.

**Files:**
- Test: `tests/test_webapp_reanalysis.py` (append)

**Interfaces:**
- Consumes:
  - C1 `analysis.flag_groups.FLAG_GROUPS` (all eleven, iterated; `state is None` is premium financing);
  - C3 `registry_match`, through which S2's insurance rule reads `PREMIUM_FINANCE_ALIASES`. C3 keeps today's `_registry_match` semantics (`analysis/transaction_classifier.py:197-213`), so an empty registry matches nothing, and it compiles once per registry *object*, so each table patched in below is a new object and is compiled afresh;
  - S2's test fixtures in `tests/flag_group_fixtures.py`: `FAKE_PAYEES` (alias → (entity, state), one or more payees for every flag-group state but `bank_loan`) and `fake_match` (a stand-in for C3's `match_known_payee` over them);
  - S2's module names `analysis.transaction_classifier.match_known_payee` (C3) and `analysis.transaction_classifier.PREMIUM_FINANCE_ALIASES` (C2), patched as S2's own `fake_payees` / `fake_premium_finance` fixtures patch them;
  - nothing of the registry's content. Every payee here is fabricated and patched in, so the pins do not depend on what the curated ledger (C10) renders into `analysis/classification_registry.py`. They assume only that no rendered alias reaches the fabricated descriptors (`FABRICATED ...`, `TRANSFER TO LOAN 0001`, `DEPOSIT FABRICATED ORDINARY`), which name no company; C10's validator refuses bare generic words such as `LOAN` as aliases. If a rendered alias does reach one, Step 4's rule applies: it is a finding for the orchestrator, not an expectation to re-pin;
  - S2's own-bank loan transfer rule (D5: a plain `TRANSFER TO LOAN` debit is a `bank_loan`);
  - S3's top-level `analysis_rules_outdated: bool` (C6) and each served row's `classification.flag_shown` (C6);
  - `_payload`, `_records`, `_review`, `_reanalyze`, the `pipeline` and `private_store` fixtures (Tasks 3-8).
- Produces: test helpers `PREMIUM_FINANCE_PAYEE`, `_saved_under_old_rules(payload) -> dict`, `_every_group_rows() -> tuple[list, list[str]]`.

- [ ] **Step 1: Write the tests on the pre-rebase branch.** Append to `tests/test_webapp_reanalysis.py`:

```python
# --- after S2 and S3: the current rules are the 5.0 rules, served through the flag groups --------------------------

#: The fabricated premium financier the 5.0 insurance rule is shown. S2 reads `PREMIUM_FINANCE_ALIASES` only inside
#: the insurance rule, so it is not one of S2's `FAKE_PAYEES`.
PREMIUM_FINANCE_PAYEE = "FABRICATED PFC"


def _saved_under_old_rules(payload):
    """A payload as a statement analysed before the 5.0 rules left it: every record stamped with the old version."""
    for account in payload["accounts"] if "accounts" in payload else [payload]:
        for transaction in account["statement"]["transactions"]:
            transaction["classification"]["classification_version"] = "4.1"
    return payload


def _every_group_rows():
    """A fabricated statement's rows: a deposit from the floor-plan, factoring and premium-finance payees each and an
    ordinary deposit, then one debit to a payee of each of the eleven flag groups, in FLAG_GROUPS order. The payees
    are S2's fabricated FAKE_PAYEES; the bank loan is the statement bank's own loan transfer (D5), which no payee
    registry names; premium financing is the fabricated premium financier above. Every row has an amount of its own,
    so no recurrence rule (D6) groups them. Returns the rows and the deposits' locations."""
    from analysis.flag_groups import FLAG_GROUPS
    from tests.flag_group_fixtures import FAKE_PAYEES

    payee_of = {}
    for alias, (_entity, state) in FAKE_PAYEES.items():
        payee_of.setdefault(state, alias)
    debits = []
    for group in FLAG_GROUPS:
        if group.state is None:  # premium financing: an insurance row that also carries the flag
            debits.append(f"ACH DEBIT {PREMIUM_FINANCE_PAYEE} 0001")
        elif group.state == "bank_loan":
            debits.append("TRANSFER TO LOAN 0001")
        else:
            debits.append(f"ACH DEBIT {payee_of[group.state]} 0001")
    deposits = [f"{payee_of['floor_plan_financing']} DEPOSIT 0001", f"{payee_of['factoring']} DEPOSIT 0001",
                f"{PREMIUM_FINANCE_PAYEE} DEPOSIT 0001", "DEPOSIT FABRICATED ORDINARY"]
    rows = [(2 + index, text, 400.0 + 50.0 * index) for index, text in enumerate(deposits)]
    rows += [(2 + len(deposits) + index, text, -100.0 - 10.0 * index) for index, text in enumerate(debits)]
    return rows, [f"transaction:{index + 1}" for index in range(len(deposits))]


def test_a_reanalysis_under_the_5_0_rules_saves_and_serves_every_flag_group(pipeline, private_store, monkeypatch):
    """An integration pin (Task 11 of the S5 plan): the analysis stage is fabricated, and the payloads it answers with
    are built here by S2's real classifier: first with registries that know none of these payees (the rules the
    statement was analysed under), then with S2's fabricated payees and premium financier (the current rules)."""
    from analysis import transaction_classifier
    from analysis.flag_groups import FLAG_GROUPS
    from tests.flag_group_fixtures import fake_match
    from webapp.app import app

    keys = {group.key for group in FLAG_GROUPS}
    rows, deposits = _every_group_rows()
    monkeypatch.setattr(transaction_classifier, "match_known_payee", lambda normalized_text: None)
    monkeypatch.setattr(transaction_classifier, "PREMIUM_FINANCE_ALIASES", {})
    job_id = pipeline.upload(_saved_under_old_rules(_payload(rows)))
    for location in deposits:
        _review(job_id, location, "confirm")
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is True
    monkeypatch.setattr(transaction_classifier, "match_known_payee", fake_match)
    monkeypatch.setattr(transaction_classifier, "PREMIUM_FINANCE_ALIASES",
                        {"Fabricated Premium Finance": (PREMIUM_FINANCE_PAYEE,)})
    pipeline.new_rules(_payload(rows))

    body = _reanalyze(job_id).get_json()

    # The ordinary deposit keeps its review. The floor-plan and factoring deposits are financing proceeds now, and the
    # premium financier's keeps the insurance credit treatment: a rule decides all three, and the answer says so.
    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (1, 0, 3)
    saved = private_store.get(job_id).analysis
    records = _records(saved)
    assert records[deposits[-1]]["revenue_review_status"] == "confirmed"
    assert {records[location]["revenue_classification"] for location in deposits[:-1]} == {"non_revenue"}
    # Every one of the eleven groups is saved: on its row, in the metrics and in the detection.
    flagged = [record for record in records.values() if record.get("contributes_to_flagged_totals")]
    assert {record["flagged_group"] for record in flagged} == keys
    assert set(saved["metrics"]["flagged_groups"]) == keys
    assert {position["group"] for position in saved["detection"]["flagged_positions"]} == keys
    assert {record["classification_version"] for record in records.values()} == {"5.0"}
    # Premium financing is no state of its own: the row stays insurance, in the insurance totals, and carries its flag.
    (premium,) = [record for record in flagged if record["flagged_group"] == "premium_financing"]
    assert (premium["classification"], premium["contributes_to_insurance_totals"]) == ("insurance", True)
    # The answer is the analysis as it is now served: every group is ticked by default, so every flagged row shows,
    # and the rules are current.
    served = _records(body["analysis"])
    assert [served[record["source_location"]]["flag_shown"] for record in flagged] == [True] * len(keys)
    assert body["analysis"]["analysis_rules_outdated"] is False


def test_the_outdated_rules_flag_clears_after_a_reanalysis(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_saved_under_old_rules(_payload()))
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is True
    pipeline.new_rules(_payload())
    body = _reanalyze(job_id).get_json()
    assert body["analysis"]["analysis_rules_outdated"] is False
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is False
```

- [ ] **Step 2: Run them before the rebase and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py::test_a_reanalysis_under_the_5_0_rules_saves_and_serves_every_flag_group tests/test_webapp_reanalysis.py::test_the_outdated_rules_flag_clears_after_a_reanalysis -q -p no:cacheprovider`
Expected: FAIL, 2 failed:
- the eleven-group pin with `ModuleNotFoundError: No module named 'analysis.flag_groups'` (S1 is not on the branch) or `No module named 'tests.flag_group_fixtures'` (S1 is, S2 is not);
- the outdated-flag pin with `KeyError: 'analysis_rules_outdated'` (S3 is not on the branch).

- [ ] **Step 3: Rebase onto the branch that carries S2 and S3.**

```bash
git stash
git rebase lender-detection
git stash pop
```

Resolve any conflict by keeping both sides. Never drop an S2, S3 or S4 line. The likely conflicts are adjacent insertions in `webapp/app.py`, `webapp/static/app.js` and the census's `READERS` tuple and `EXCUSED` dict (`tools/l1s3_surface_census.py`).

- [ ] **Step 4: Run them and every S5 test on the rebased branch.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_reanalysis.py tests/test_webapp_reanalysis_ui.py tests/test_webapp_revenue_batch.py tests/test_worker_privacy.py tests/test_webapp_storage.py tests/test_webapp_jobs.py tests/test_webapp_settings.py tests/test_l1s3_census.py tests/test_privacy3_boundaries.py -q -p no:cacheprovider`
Expected: PASS (all passed; 52 in `tests/test_webapp_reanalysis.py`, 9 in `tests/test_webapp_reanalysis_ui.py`).

If the eleven-group pin fails on its counts or its groups, read the saved records before changing anything: the pin states S2's contract (C1 `FINANCING_STATES`, C4's premium-financing rule and the D5 own-bank loan transfer), so a difference is a finding to report to the orchestrator, not an expectation to re-pin.

Then run the master plan's **Core**, **Guards/JS** and **Wider** selections, plus `tests/test_l1s3_census.py`. The only failure allowed is the known `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 5: Commit.**

```bash
git add tests/test_webapp_reanalysis.py
git commit -m "tests: a re-analysis on the 5.0 rules saves and serves every flag group" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

## Self-Review

**Spec coverage (§8.6, D12, C9, and the 2026-09-24 amendment where S5 touches it):**

| Requirement | Where |
|---|---|
| §8.6.1 read the job's stored PDF bytes, kept on disk by content hash | Task 8/9 route: `store.pdf_bytes(job_id)`, which is `Storage.load_pdf(content_sha256)` (`webapp/jobs.py:377-385`) |
| §8.6.2 OCR is served from the cache | Tasks 6-7: `rerun_analysis` calls `run_job` against `_CapturedJobStore`, whose cache is `_CacheOnly` over the real artifact cache. Pinned by `reads == 1` and an `ocr` `cache_hit` audit row, and for the visual pair by a pair that is called once, at upload. A reading that is not cached, or a cached one that fails its own checks, stops the run before any reading rung runs (the local preflight still profiles the PDF's native text): `READING_NOT_CACHED`, 422 through the route. The cache-only guard is pinned on its own (a reader that names no stage, a pair that names no step, a statement that now falls back to the pair), and so are the stage and stream backstops. The re-analysis writes no cache entry, pinned for the analysis, the report and the pair's answer over a drifted entry (Task 7; Decision 2, with its two stated limits) |
| §8.6.3 replace the analysis in place; job id and place in Recent unchanged | Tasks 1, 2, 8. Server side: id, `created_at`, markdown and html pinned. Client side: `rememberAnalysis` updates in place (`app.js:3697-3704`), pinned by Task 10's Recent test |
| §8.6.4 previous analysis kept in the audit log | Task 1: audit row first, same transaction, `previous_analysis_json` verbatim. Task 8 checks it through the route |
| §8.6.5 replay only where same account, location, description and amount | Task 4 (the four fields, the account number included, the latest decision, resets, one copy and one rebuild); Task 5 (redo detection); Task 8 (through the route) |
| §8.6.5 anything that cannot be replayed is reported back: "N reviews need redoing" | Tasks 5, 8, 10: needing redoing and decided by the rules are both counted, answered, audited and shown ("1 review needs redoing", "1 review is now decided by the rules", pluralised, amber) |
| §8.6 refuse when the stored PDF is missing | Task 8: file deleted, and a job that never stored its PDF → 409 |
| D12: nothing re-labels silently | The re-analysis runs only on an explicit POST; serving is untouched; a decision a new rule overrides is reported (Decision 5) |
| C9 200 body keys; 404/409/409 texts | Task 8 asserts each exact body; the extensions are listed under "What the orchestrator must ratify" |
| C9 audit before replacement | Task 1 (the transaction's order), Task 8 |
| C9 JS calls it from `#reanalyzeButton` and re-renders from the response | Task 10: one POST and no re-fetch; the page is drawn from `payload.analysis` |
| Per-job lock like the review routes | Task 9 |
| CSRF / JSON-only, privacy of refusal texts | Task 8 (400 for a form and for a list body; 422 never echoes the exception); `test_the_webapp_exception_ledger_is_complete` in Tasks 4-8 |
| Amendment: eleven groups, three new ones with their own states / key / setting | S5's production code names no group. Task 11 iterates `FLAG_GROUPS` (all eleven) and pins each group on its saved row, in `metrics.flagged_groups`, in `detection.flagged_positions` and as served (`flag_shown`) |
| Amendment: floor plan and factoring credits are financing proceeds (`FINANCING_STATES`) | Task 11: a confirmed deposit from each is reported as decided by the rules after the re-analysis (Decision 5) |
| Amendment: premium financing stays `insurance` and in the insurance totals, and also carries its flag | Task 11: the saved premium-financing row is `insurance`, `contributes_to_insurance_totals`, `flagged_group="premium_financing"`, `contributes_to_flagged_totals`, and is shown; its confirmed deposit is decided by the rules |

**Out of S5's scope and owned elsewhere:**
- the notice's markup, text and visibility (`#rulesOutdatedNotice`, "Analysed with older lender rules"): S4, C8;
- `analysis_rules_outdated` and `flag_shown`: S3, C6;
- the new classifications, including the premium-financing rule: S2.

Task 11 pins S5's end of each of these once they land.

**Review findings of 2026-09-25, each checked against the code and addressed:**
1. *The cache-only guard had no test of its own* (the fake reader named a stage first). Confirmed: `_Pipeline._read` called `on_stage("native")` before reading, and the pair's pre-step work is at `vlm/pair.py:688-701`. Task 7 now pins `_CacheOnly` with a reader that names no stage, with a fabricated pair on a forced job, and with a statement that now falls back to the pair.
2. *Decisions a new rule decides were dropped silently.* Confirmed against §8.6.5 and D12. They are now reported: `reviews_decided_by_rules` in the answer and the notice (Decision 5, Tasks 8 and 10), listed for ratification.
3. *Replay cost.* Confirmed: one copy and two rebuilds per decision. Task 3 splits the review writer from its rebuild, and Task 4 applies every decision to one copy with one rebuild, pinned by counting both.
4. *Unpinned rules.* Confirmed. Now pinned: the account number in the replay match (Task 4) and in redo detection (Task 5), the job's own `parse_mode` and `force_ocr` (Task 6), the stream refusal (Task 7).
5. *"Never reads" overstated.* Confirmed (`webapp/worker.py:633-635`). The constraint, Decision 2 and `READING_NOT_CACHED` now say that no reading rung runs and that the local preflight does.
6. *Contract and schedule extensions.* Listed under "What the orchestrator must ratify"; Tasks 3-7 split the old Tasks 3-4; the two integration pins are one task whose red step always runs.
7. *Found while re-checking, not in the review:* the first draft's `webapp/reanalysis.py::_records` reads the `statement` key and would have failed `tests/test_l1s3_census.py::test_the_census_holds_at_this_tree` (reproduced on the reviewer's replay of the first draft: `webapp/reanalysis.py::_records: reads a published payload key and is neither a declared reader nor an excused site`). Tasks 3 and 4 declare the readers.

**Verification findings of 2026-09-25 (second round), each checked against the code:**
1. *The re-analysis was a second writer of the artifact cache.* Confirmed.
   - The worker is the only writer today (`webapp/app.py:149` is the only `run_job` caller).
   - Through `_CacheOnly.__getattr__`, the re-analysis reached the real `put_analysis` and `put_report`, and `put_ocr` on the pair's local-evidence path.
   - `_write_payload` replaces one fixed temporary file per entry (`webapp/artifact_cache.py:1135-1141`). On this host, a second `os.replace` of that file raises `FileNotFoundError`, and replacing a file another handle holds raises `PermissionError`.
   - Now `_CacheOnly` writes nothing (Global Constraints, Decision 2). Task 7 pins this with two tests, and a mutation restoring any one of the three writes is caught.
   - The one overlap left, and the pair's own evidence write, are stated in Decision 2's known limits. They are part of the owner's ruling (ratification item 2).
2. *"Never reads" was still overstated* in the Task 7 heading and commit subject, in two test names and in the §8.6.2 row. Confirmed (`webapp/worker.py:633-635`). They now say that no reading rung runs, and the two tests are named for what they count (`..._runs_no_reader`).
3. *C10 and the other plans.* S5 uses no S1 builder, research input or ledger, and it cites S1 and S2 by contract name (C1-C3, C10) and file, never by task number. Task 11 states what it needs of C3's `registry_match`: an empty registry matches nothing, and each registry object is compiled afresh. It depends on no rendered registry content.

**Placeholder scan:**
- No "TBD", "TODO", "similar to", "add error handling" or unnamed helper.
- Every code step carries the full code.
- Every test step carries the full test.
- Every run step names its command and the failure or pass expected.
- Task 11 is gated on named merges (S2, S3), not on unknowns.

**Contract-name consistency:**
- **C9:** the route path `/analysis/<job_id>/reanalyze`; the response keys `analysis`, `reviews_replayed`, `reviews_not_replayed` and `reviews_decided_by_rules` (now in the master plan's C9, subject to the owner's ruling on Decision 5); the 400 and 422 bodies of Decisions 3-4, also in the master's C9; the errors `job not found`, `job is not finished`, `the original PDF is not stored`. All are spelled identically in the route (Tasks 8-9), the tests (Task 8) and the JS tests (Task 10).
- **C8:** the id `reanalyzeButton` is used verbatim. `rulesOutdatedNotice` is S4's and is not referenced.
- **C1/C4/C6:** `FLAG_GROUPS`, `FlagGroup.state`/`.key`, the group keys `premium_financing` and the states `bank_loan`, `floor_plan_financing`, `factoring`, `classification_version` "5.0", `flagged_group`, `contributes_to_flagged_totals`, `contributes_to_insurance_totals`, `metrics.flagged_groups`, `detection.flagged_positions`, `flag_shown`, `analysis_rules_outdated` (Task 11), as the contract spells them. S2's fixture names `FAKE_PAYEES` and `fake_match` (in `tests/flag_group_fixtures.py`) and the classifier's module names `match_known_payee` (C3) and `PREMIUM_FINANCE_ALIASES` (C2) are used as the S2 plan defines them. S1 and S2 are cited by contract name and file, never by task number, since both plans are revised apart from this one.
- `_displayed(analysis)` is called with no keyword argument, so it matches today's signature and S3's `_displayed(analysis, *, carry_over=None, settings=None)`.
- **Names this plan introduces**, each defined before it is used:
  - `Storage.record_reanalysis` (Task 1)
  - `JobStore.apply_reanalysis` (Task 2)
  - `record_serialized_revenue_review` (Task 3)
  - `Replay`, `replay_reviews`, and the private `_places`, `_applied`, `_ids` (Task 4); `_redone`, `_awaits_review` (Task 5)
  - `READS_DIFFERENTLY`, `Rerun`, `rerun_analysis`, the private `_CapturedJobStore` (Task 6); `READING_NOT_CACHED`, the private `_ReadingRefused`, `_CacheOnly` (Task 7)
  - `REANALYSIS_NOT_SAVED`, `reanalyze` (Task 8)
  - `reviewsLabel`, `reanalysisNotice`, `reanalyzeShownStatement`, `reanalysisBusy` (Task 10)
  - test helpers: `DECIDED_AT`, `_payload` (Task 3); `CHANGED_ROWS`, `SHIFTED_ROWS`, `TWIN_ROWS`, `TWIN_CHANGED_ROWS`, `_decision`, `_alike_in_both_accounts` (Task 4); `_ruled` (Task 5); `PDF`, `WITHHELD`, `private_store`, `_Pipeline`, `pipeline`, `visual_pair`, `_stamped`, `_json` (Task 6); `_cache_files` (Task 7); `_reanalyze`, `_review` (Task 8); `LATE_ROW`, `_statement`, `_answer`, `_open_stale`, `CLICK` (Task 10); `PREMIUM_FINANCE_PAYEE`, `_saved_under_old_rules`, `_every_group_rows` (Task 11).
- Names used from existing tests: `ROWS`, `_records`, `_two_accounts` (`tests/test_webapp_revenue_batch.py:13, 33, 57`); `_report`, `CHECKING_ROWS`, `_serve`, `_pending` (`tests/test_webapp_studio_views.py:24, 17, 67, 454`); `DRAWN` (`tests/test_webapp_review_ui.py:17`); `NODE`, `run_dashboard` (`tests/webapp_js_harness.py:15, 109`).

**Evidence behind the plan (re-run 2026-09-25).** Every task through Task 10 was applied exactly as written, step by step, to a scratch copy of the repository at `4f219cd`, with nothing written in the repository. A script took each step's code blocks from this file and applied them with the old strings the steps quote, each found once in its file. Every "Expected" line above was observed. After the second verification round, every step was applied again, from this text, to a fresh export of `4f219cd`, and every old string was again found once. What was run again:
- the red and green steps of Tasks 7, 8 and 9;
- Task 10's green step (286 passed);
- Task 11's red step and its stand-in check;
- the mutation probe and the wide selection.

The test runs of Tasks 1-6 and Task 10's red step, which that round did not change, were not repeated:

| Step | Observed |
|---|---|
| Task 1 red / green | 3 failed (`AttributeError ... record_reanalysis`) / 26 passed with `tests/test_webapp_storage.py` |
| Task 2 red / green | 2 failed, 3 passed / 35 passed with the job and storage suites |
| Task 3 red / green | 4 failed (`ImportError ... record_serialized_revenue_review`), 5 passed / 405 passed with the review suites, the privacy boundaries and the census |
| Task 4 red / green | 11 failed (`ModuleNotFoundError`), 9 passed / 115 passed with the census, privacy and batch suites |
| Task 5 red / green | 3 failed (the three assertions its Step 2 quotes), 22 passed / 87 passed |
| Task 6 red / green | 6 failed (`ImportError`), 25 passed / 236 passed with the worker, cache, visual-pair and census suites |
| Task 7 red / green | 8 failed (6 `ImportError ... READING_NOT_CACHED`, 2 at `assert _cache_files(private_store) == before`), 31 passed / 244 passed with the same suites |
| Task 8 red / green | 10 failed, 39 passed (the failures listed in its Step 2) / 443 passed with the webapp, security, privacy, queue and census suites; 49 in the file |
| Task 9 red / green | `assert False` at `assert waited` / 123 passed; 50 in the file |
| Task 10 red / green | 9 failed / 286 passed with the JS and guard suites; 9 in the new file |
| Task 11 | Red before the rebase exactly as its Step 2 says (`No module named 'analysis.flag_groups'`, `KeyError: 'analysis_rules_outdated'`). With stand-ins for S1's `analysis/flag_groups.py` (C1 verbatim), S2's fixture names and version bump, and C6's flag in `_displayed`, the outdated-flag pin passes (51 passed in the file), and `_every_group_rows()` builds four deposits at `transaction:1-4` and eleven debits, one per group. The eleven-group pin cannot pass before S2's classifier exists, so its green is first seen on the rebased branch |
| Mutation probe | Each safeguard weakened on its own, on the replay of Tasks 1-10; every mutation was caught by the test named: the cache-only lookup (`test_a_miss_stops_the_run_before_a_reader_that_names_no_stage`), the stage backstop (`test_a_cached_reading_that_fails_its_own_checks_is_not_read_again`), the stream refusal (`test_a_reading_that_streams_before_it_names_a_stage_is_stopped`), the account number in the replay match (`test_a_decision_never_follows_its_posting_into_another_account`) and in redo detection (`test_a_decision_on_another_account_is_not_a_redo`), the job's `parse_mode` (`test_a_rerun_keeps_the_job_s_own_parse_mode`) and `force_ocr` (`test_a_statement_the_visual_pair_read_is_reanalyzed_from_the_pair_s_cached_reading`), the answer's `reviews_decided_by_rules` (`test_a_reanalysis_reports_the_reviews_a_rule_now_decides`), the rule-decided check, the redo check, the decision's own time, the reset skip, the other-reading refusal and the route's status check. 15 of 15 caught. On the second-round replay, 9 more were run, and all 9 were caught:<br>- each of the three cache writes restored on its own: `put_ocr` by `test_a_pair_reading_answered_again_from_the_pair_s_own_evidence_is_not_written_back`, `put_report` by `test_a_rerun_writes_no_analysis_and_no_report_into_the_cache`, and `put_analysis` by both;<br>- the cache-only lookup, the wrapper bypassed, the stage and stream backstops, and each of the two census edits |
| Wide selection after Task 10 | The master plan's Core, Guards/JS and Wider selections, plus both S5 files and every suite a step of this plan runs (the census and surface tests, the privacy boundaries, the worker, visual-pair, batch, security, queue, jobs, storage, document-outcome, currency-source and confidence-label suites): 1457 passed, 2 deselected (the `live` and `corpus` markers of `pytest.ini`). The first round's 1455 is lower by Task 7's two new tests. The one failure is the known `test_no_literal_account_numbers_in_ocr`. The whole `tests/` directory was not run to the end: it was stopped at a few percent after 10 minutes on this shared host |
| Not in any step | `tests/test_private_artifacts.py` fails 5 tests on this Windows host before any S5 change (symlink privilege `WinError 1314`, and a POSIX directory mode), so no step runs it |
