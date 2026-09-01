# Agent Handoff — P20-ARTIFACTS (Phase 2.0 cell C: run-of-record artifact selection, cache identity for a multi-extractor world, `OCR_STAGE_VERSION` 4 → 5)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (OQ8 = YES, OQ10 = RUN-OF-RECORD), then
`OCR_LEGACY_AUDIT.md` F-6 / F-9 / §5.3 / §5.6 and the review's MAJOR-3 / MINOR-4, then
`PHASE2_ARCHITECTURE_PLAN.md` §10, then the umbrella `PHASE2-0-SAFETY.md`. Ocean reviews and
composes; you never merge or push. **Hygiene card: `newly validated = 0`; previously validated
preserved, payload identical.** The two cold caches are READ-ONLY; your tests use `tmp_path` caches.

# Why
`tools/cohort_replay.py::ColdCache._payload` takes `rows[0]` with no `ORDER BY` and no settings-key
filter; `telemetry/stated_counts.py::CachedArtifacts` selects from a hard-coded preference list that
ranks the visual partition LAST. Both are correct today only because every input holds exactly one
artifact per stage. The first OCR-fed document — or a data directory spanning two registry
fingerprints — makes the replay's source arbitrary and the observer's preference an unratified
extractor ranking. Gustavo ruled OQ10: historical truth follows the artifact the official run
actually consumed. The cache key also lacks the extractor id, the postprocess state and the binary
versions Phase 2 makes load-bearing (F-6), and the bump that carries them must land with its pin.

# Design (ruled — do not re-decide)
1. **`telemetry/run_of_record.py` (new) — ONE selection policy, shared.**
   * `RunPartitions` — what a run of record consumed: `ocr_keys_by_source: {source_path → settings_key}`
     (e.g. `native`/`local_tesseract` → the offline key of the run's mode; `visual` → the visual key),
     `analysis_key`, `ocr_stage_version`, `analysis_stage_version`, `origin` (`recorded` |
     `reconstructed`).
   * `partitions_for_run(run_dir) -> RunPartitions`: reads `provenance.json`. Runs that RECORD their
     partitions (this cell adds them — see 3) are `recorded`. Historical runs (batch 8 `cda8882d`,
     batch 9 `91f5179a`) are `reconstructed` deterministically from what the run did record:
     `OCR_STAGE_VERSION`, `ANALYSIS_STAGE_VERSION`, `analysis_settings_key_deterministic`, the run's
     mode (from `summary.json`) → the offline key is `ocr_settings_key(force_ocr=False,
     allow_local_ocr=<mode in LOCAL_OCR_MODES>, allow_visual_ocr=False)` at THAT stage version with
     the run's recorded OCR env, the visual key `(True, False, True)`. The reconstruction is VERIFIED
     against the cache: every key it names must exist in the index or be absent for every row that
     claims it (the batch-9 cold cache holds exactly one OCR key and one analysis key — assert the
     reconstruction reproduces both; a mismatch is exit 5, never a guess).
   * `ocr_partition_for_row(row, partitions) -> settings_key`: from the row's own `source_path` /
     `visual_rung` (`recovered`/`upgraded` → visual; else offline). `analysis_partition(partitions)`.
   * `select_artifact(conn, stage, input_sha, settings_key) -> path | None`: `WHERE stage=? AND
     input_sha256=? AND settings_key=?` — the primary key `(stage, cache_key)` makes this at most one
     row; assert `len(rows) <= 1` and raise on more (a corrupt index is a finding, not a choice).
2. **Both readers adopt it (OQ8 / F-9).** `tools/cohort_replay.py::ColdCache` takes the run
   directory, calls `partitions_for_run`, and selects by the row's partition on BOTH stages; the
   `--run` pointer default moves from the train-8 file to an explicit REQUIRED argument (the batch-9
   run of record is the current base; write it into `discovery_reports/train9-logs/train9_run_dir.txt`
   as the new pointer and read it by default). `CachedArtifacts` drops `_ocr_keys` and takes
   `RunPartitions` (from the run it observes); the analysis filter uses the run's recorded analysis key,
   not the current tree's (`observe_run` already knows the run dir). Fidelity proof: at the current
   tree over the batch-9 run + cold cache, both readers resolve exactly the rows they resolved before
   (cohort replay `--expect-identical` over the huntington 38 + the `guardian_cu` family + a 100-sha
   random sample: exit 0 before and after; `observe_run` rollup counts identical).
3. **Runs record their partitions.** `tools/train/provenance.py` records, beside the existing keys,
   `run_of_record.partitions` = `{offline_ocr_key, visual_ocr_key, analysis_key, mode}` computed from
   the run's actual flags (not `ocr_settings_key()`'s defaults, which today record a key the runner
   never uses — say so in the docstring). The runner itself is cell A's; you do not touch
   `discovery/*` — provenance is written by the train tooling before and after the run, which is
   where the batch-9 record came from.
4. **Cache identity (`webapp/artifact_cache.py`).** `ocr_settings_key` gains: `extractor`
   (`"offline"` when `allow_visual_ocr` is False or the offline ladder is what can run; `"visual"`
   for the forced visual partition — derived from the three booleans by ONE function, pinned),
   `postprocess_state` + `postprocess_admitted` (imported from `ocr.ocr_client` — cell B1 exports
   `POSTPROCESS_STATE` and `ADMITTED_POSTPROCESS`; until B1 composes, read them through `getattr`
   with the quarantined defaults and pin the defaults), `raster_version` (a new constant
   `ocr.rasterize.RASTER_VERSION = 1`), `extraction_schema_version` (a new constant
   `EXTRACTION_SCHEMA_VERSION = 1` in `webapp/artifact_cache.py` beside the stage versions —
   `ocr/document.py` is B2's file), `endpoint_class` (from `Settings`, cell B2;
   `getattr` default `"loopback"` until it composes), and the binary versions `tesseract_version`,
   `poppler_version`, `pymupdf_version` (each `unknown` when unobtainable — partitions
   conservatively; a probe helper `ocr_toolchain_versions()` that shells out ONCE per process and
   caches; NEVER raises). Still excluded by design: timeout, retries, api_key, filename, workers,
   callbacks, profile. Update the module docstring's key inventory.
5. **`OCR_STAGE_VERSION` 4 → 5 in the SAME commit** as the key change and the pin at
   `tests/test_artifact_cache.py:854` (with the bump-history comment: v5 = Phase 2.0 — extractor id,
   postprocess quarantine state, raster/schema versions, endpoint class and binary versions join the
   key; GLOBAL by construction; the Phase 2.0 cold run re-reads the archive; vendor cost $0). The
   ANALYSIS stage is untouched (its key already carries the registry fingerprint; Ocean bumps
   `ANALYSIS_STAGE_VERSION` at composition only if a cell changed analysis output — none should).
6. **Multi-partition determinism test (CASE 9).** In a `tmp_path` cache seed one input with THREE
   OCR artifacts (offline-local, offline-nolocal, visual) and two analysis artifacts (two registry
   fingerprints); write a synthetic run directory whose rows name different partitions per sha;
   prove both readers return the partition the row names, identically across 20 runs with shuffled
   insertion order, and that a row naming a partition absent from the cache resolves to `None`
   (never to another partition). A mutant restoring `rows[0]`, a mutant restoring the `_ocr_keys`
   preference, and a mutant preferring visual-first must each be killed.

# Mutation table (minimum)
| mutant | killer |
|---|---|
| `_payload` restored to `rows[0]` | CASE 9 shuffle test |
| `_ocr_keys` preference restored | CASE 9 preference mutant |
| visual-first preference | CASE 9 |
| `select_artifact` tolerates 2 rows | the corrupt-index test |
| reconstruction guesses a key absent from the cache | the reconstruction-verified test (exit 5) |
| `OCR_STAGE_VERSION` bumped without the pin | the pin (`== 5`) |
| key drops `postprocess_state` | the knob-partition test (one per new knob, as `tests/test_visual_rung.py:492-501` does) |
| `tesseract_version` unobtainable → key omits it | the `unknown`-sentinel test |

# Measurements to report
Fidelity before/after for both readers (exit codes, counts) · the reconstruction's verified keys for
the batch-9 run (must equal the cache's single OCR key and single analysis key) · cohort replay at
base and at closure (the SAME numbers — this cell changes selection, not content) · the new key
material and its partition tests · CASE 9 · mutation table · privacy 0 · tests added · targeted suite.

# Ownership
`webapp/artifact_cache.py`, `ocr/rasterize.py` (ONLY the `RASTER_VERSION` constant),
`telemetry/run_of_record.py` (new), `telemetry/stated_counts.py` (`CachedArtifacts` only),
`tools/cohort_replay.py`, `tools/train/provenance.py`, `discovery_reports/train9-logs/train9_run_dir.txt`
(gitignored — record the path in your W3 section too), `tests/test_artifact_cache.py`,
`tests/test_run_of_record.py` (new), `tests/test_stated_counts.py`, `tests/test_cohort_replay_selection.py`
(new), `tests/test_visual_rung.py` ONLY the knob-partition parametrization, W3 `§P20ARTIFACTS`. NOT
yours: `discovery/*`, `webapp/worker.py` (A); `ocr/ocr_client.py`, `ocr/pipeline.py` (B1);
`ocr/config.py`, `ocr/document.py` (B2); `webapp/static/*`, `analysis/*` (D).

# Exclusions
No `page_extractor` per-page provenance (2.1). No page-level keys. No change to artifact content or
envelope (`CACHE_FORMAT_VERSION` stays 1). No ANALYSIS_STAGE_VERSION bump. No writes to either cold
cache. No PaddleOCR key material beyond the `extractor` slot.

# Git
Base `train10` at your handoff's commit. Branch `wave20-artifacts`, worktree
`.claude/worktrees/mt20-artifacts`.
