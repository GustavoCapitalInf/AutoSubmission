# Phase 2.0 — SAFETY FOUNDATIONS (umbrella implementation card; Ocean, 2026-09-01)

**Authority:** Gustavo's Phase 2.0 authorization and OQ1–OQ11 rulings
(`docs/moneythumb-replacement/PHASE2_RULINGS.md`); the accepted architecture
(`docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md` §17 "Phase 2.0"); the standing rules
(`docs/agent-handoffs/BATCH9-RULES.md` + `docs/agent-handoffs/PHASE2-RULES.md`).

## Objective (exact)
Make future OCR-fed and geometry-fed validation possible without weakening the frozen Batch 9
correctness model, and make "try extractors until something balances" architecturally impossible.
Expected coverage movement: **+0**. OCR-fed validated count at closure: **0**. No new OCR engine is
enabled for production validation.

## Scope (exact) — five bounded cells, disjoint file ownership, parallel-safe
| cell | card | what it delivers | rulings it executes |
|---|---|---|---|
| A | `P20-ROUTER.md` | `ocr/escalation.py`: the closed failure-class vocabulary (A/B/C), the independent `EscalationRouter`, the `ExtractionQualityGate`; the U-extract / U-structure split measured on the run of record; runner + worker rewired so only pre-financial evidence can START an extractor and only `validated` can STOP one; the tripwires that keep it that way; `validated ∩ class-A = 0` pinned | invariant; failure model; §5–§7 of the authorization; OQ4 (T surface-only, measured) |
| B1 | `P20-POSTPROCESS.md` | the nine-function postprocess census with per-function synthetic fixtures; the whole chain quarantined on every path (analysis AND display); raw evidence immutable; the re-admission mechanism present and EMPTY; the no-hardcodes guard extended into `ocr/` with the TD recovery declared as named intake behavior | OQ1 = C; OQ2 = YES; §8 |
| B2 | `P20-SEAM.md` | the OCR_MODEL / `source_file` provenance-token injection closed (closed charset, reserved-prefix refusal, hostile tests); the endpoint allowlist / $0 default enforced in code with explicit recorded opt-in and no local→remote hop; legacy OCR entry points salvaged then retired/quarantined; RunPod relabeled as the opt-in escape hatch; `SOURCE_PATHS` / `FREE_MODELS` closed against the fallthrough | OQ3 = ALLOWLIST; OQ6; OQ7; §9–§10 |
| C | `P20-ARTIFACTS.md` | run-of-record artifact selection shared by `tools/cohort_replay.py` and `CachedArtifacts` (no `rows[0]`, no list preference, no incidental order); provenance records the run's actual partitions; the OCR settings key gains extractor id, postprocess state, raster version, extraction schema version and binary versions; `OCR_STAGE_VERSION` 4 → 5 with its pinned test in the same commit | OQ8 = YES; OQ10; §11 |
| D | `P20-SURFACES.md` | the fabricated "OCR confidence" removed from the webapp (verdict label, no number); the Q3 omission class gated native-only at the seam (fail closed on non-native or absent provenance); the 2026-07 PaddleOCR and Nanonets specs marked SUPERSEDED with the geometry ideas preserved | OQ9; OQ11; §12–§13 |

Composition order at the train: **B2 → B1 → A → C → D** (config/seam first, then the chain, then the
router that consumes the quality gate, then the cache bump, then the surfaces). File ownership is
disjoint by construction; any overlap discovered is reported to Ocean, never resolved by a cell.

## Expected files / modules touched (by cell — see each card for the exact ownership list)
- A: `ocr/escalation.py` (new), `discovery/runner.py`, `discovery/report.py` (new columns), `webapp/worker.py`, `telemetry/record.py` (vocabulary only), `tools/phase2_trigger_split.py` (new, read-only instrument), `tests/test_escalation_router.py` (new), `tests/test_escalation_tripwires.py` (new), existing `tests/test_visual_rung.py` / `tests/test_discovery.py` updates.
- B1: `ocr/ocr_client.py`, `ocr/pipeline.py` (the raw return only), `ocr/render.py`, `tools/ocr_postprocess_census.py` (new), `tests/fixtures/ocr_postprocess/` (new synthetic fixtures), `tests/test_ocr_postprocess_census.py` (new), `tests/test_ocr_client.py`, `tests/test_no_statement_hardcodes.py` (OQ2 extension), `tests/test_ocr_intake_furniture.py` (new).
- B2: `ocr/config.py`, `ocr/document.py`, `ocr/availability.py`, `ocr/endpoint_policy.py` (new), `telemetry/prices.py`, the `source_path_for` fallthrough closure in `telemetry/record.py` lines 119–133 ONLY (A owns the two new vocabularies in that module and nothing in that function), `parse.py`, `batch.py`, `sweep_ocr.py` (retire), `triage_scan.py` (salvage then retire), `coverage_audit.py` (retire), `deterministic_coverage_audit.py` (retire), `README.md`, `corpus_gate.py` register entries for the retired scripts, `tests/test_native_rung_parity.py` (binding list), `tests/test_ocr_provenance_injection.py` (new), `tests/test_ocr_endpoint_policy.py` (new), `tests/test_ocr_defect_signatures.py` (new, salvaged CHECKS).
- C: `webapp/artifact_cache.py`, `telemetry/run_of_record.py` (new), `telemetry/stated_counts.py` (`CachedArtifacts`), `tools/cohort_replay.py`, `tools/train/provenance.py` (C records the run's actual partitions there and in the runner-independent `run_of_record.py` reader; `discovery/report.py` belongs to A), `tests/test_artifact_cache.py`, `tests/test_run_of_record.py` (new), `tests/test_stated_counts.py`, `tests/test_cohort_replay_selection.py` (new).
- D: `webapp/static/app.js`, `webapp/templates/index.html`, `analysis/pipeline.py` (the Q3 gate at the omission publish site) or `analysis/sibling_omission.py`, `analysis/provenance.py` (new; the header reader that reads ONLY the first-line comment — `ocr/document.py` belongs to B2), `tests/test_q3_native_only.py` (new), `tests/test_webapp_confidence_label.py` (new), `docs/superpowers/specs/2026-07-21-…` and `…07-22-…` (SUPERSEDED banners).

## Baseline measurements (Ocean, 2026-09-01, before any implementation)
| measurement | value | source |
|---|---|---|
| origin/main | `746e1e9` (docs + read-only census tool on the freeze tree) | `git rev-parse origin/main` |
| batch9-final | `819d97d` (annotated tag `630da31`) | `git rev-parse batch9-final^{commit}` |
| code delta 819d97d → 746e1e9 outside docs | `tools/ocr_legacy_census.py` only (+439) | `git diff --stat` |
| ANALYSIS_STAGE_VERSION / OCR_STAGE_VERSION / registry | 17 / 4 / 84 | tree |
| validated (distinct shas) | **2,625** / 3,380 | run-of-record `rows.csv` |
| R / U / R∪U / overlap / validated∩(R∪U) | **13 / 123 / 136 / 0 / 0** | `rows.csv`, re-derived 2026-09-01 |
| U by outcome_reason | no_parser_matched 89 · parser_declined 34 | same |
| U by profile | scanned 111 · mixed 12 | same |
| T surface (Tesseract, truncated_pages>0) | 3 (1 inside U) | same |
| cold cache train9 | OCR 3,364/3,364/1 key/0 multi · analysis 2,656/2,656/1/0 | sqlite `mode=ro` |
| suite at 7b25d70 | 7,815 passed / 44 skipped / 35 deselected | BATCH9_TRANSITION §7 |
| baseline proof at 746e1e9 (guards, OCR tests, gate) | recorded in `BATCH9_TRANSITION.md` §7 when the detached run completes | `discovery_reports/train10-logs/baseline-746e1e9.log` |

## Implementation sequence (per cell, the batch-9 choreography)
bounded card → baseline measurement at base (`cohort_replay --expect-identical` on the named cohort;
the card's own census at base) → implementation with tests first for every forbidden edge →
focused tests → corpus measurement (cohort replay at closure; census re-run) → adversarial review
(independent agent) → reproduce every finding → close accepted findings → re-review → Ocean composes
on `train10` → regression proof at the train (cohort replay over the union of cohorts; the archive
sweep where a reader changed) → full suite + guards + conformance + gate + corpus-marked slice
(`tools/train/floor.sh`) → the cold run (`tools/train/coldrun.sh` — REQUIRED because C bumps
`OCR_STAGE_VERSION`) compared to the batch-9 run of record with `--fail-on-regression` → remote CI →
durable documentation (`BATCH9_TRANSITION.md` §7 log, `PHASE2_STATE.md`, `PROJECT_STATUS.md`,
`PHASE2_HANDOFF.md`) → STOP.

## Tests the phase must prove (the eleven cases, mapped)
| case | property | cell |
|---|---|---|
| 1 | usable evidence, parser does not claim → Class B → no OCR scheduled | A |
| 2 | claimed reconstruction fails a financial oracle → Class C → no OCR scheduled | A |
| 3 | independent extraction failure → Class A → may schedule only an allowed extractor while an independent trigger remains | A |
| 4 | validator failure cannot request or invoke the router (structural: signature + import tripwires + mutation) | A |
| 5 | legacy postprocess cannot mutate admissible evidence on the production analysis path | B1 |
| 6 | OCR_MODEL / provenance injection (newline, CRLF, `-->`, `<`, `>`, money literal, parser-marker text) is killed; provenance preserved | B2 |
| 7 | endpoint outside the allowlist → refused before any request | B2 |
| 8 | remote/paid endpoint without explicit opt-in → refused; a failed local rung never hops | B2 |
| 9 | artifact/replay selection with multiple candidate partitions → deterministic, run-of-record policy | C |
| 10 | Q3 OCR-fed reliance → refused / not admitted | D |
| 11 | the frozen validated population preserved (cohort replay + cold run + compare) | train |
Plus: the no-hardcodes guard extended into `ocr/` (B1); architectural tripwires / mutation tables in
A, B1, B2, C, D as each card names them.

## Corpus measurements at closure (the §17 report)
baseline validated · tip validated · validated regressions · R · U · U-extract · U-structure ·
overlap · legal escalation population (R + U-extract; the router's own count) · illegal-escalation
checks (tests + the runner's refusal counter) · OCR-fed validated (must be 0) · the 9-function census ·
tests added · targeted / full suite / gate / cohort replay / compare / CI results · stage-version and
cache-selection changes · the UI label change · endpoint-policy result · worktree status · final SHAs.

## Regression gates
- Per cell: `newly validated = 0`; `previously validated preserved = all, payload identical` on the
  offline partition; mutation tables complete; privacy + message scans 0.
- At the train: `tools/cohort_replay.py` over the union of the cells' cohorts (exit 0); the archive
  sweep where a reader changed; `floor.sh` green; the cold run at the composed tree vs the batch-9 run
  of record with `--fail-on-regression` (exit 0; 2,625 → 2,625; 0 movers outside a named population);
  remote CI green (run id recorded).

## Review plan
Every cell branch gets an independent adversarial review (a fresh agent that reads only the rulings,
the card, the diff and the tests) whose brief is to find: validator-driven escalation · Class B
treated as A · Class C treated as A · postprocess mutation reaching admissible evidence · cache
partition ambiguity · silent remote OCR fallback · metadata injection · Q3 OCR leakage · fake
confidence surviving under another name · hardcoded benchmark/bank behavior introduced into `ocr/`.
Findings are reproduced before acceptance; BLOCK/MAJOR close pre-compose; re-review must be green.
Ocean composes; cells never merge.

## Explicit exclusions
See `PHASE2-RULES.md` §Hard exclusions. In particular: no PaddleOCR code, no Unlimited enablement, no
Trigger T routing (measure only), no candidate auto-adoption, no page-level routing, no
`page_extractor` per-page provenance (Phase 2.1), no `evidence_refs[]` lineage (Phase 2.1), no holdout
cage build (operational track, separate), no new parsers, no coverage.

## Completion criteria (Phase 2.0 is complete only when ALL hold)
implementation complete · OQ rulings durable · A/B/C explicit in code and rows · independent
escalation policy proven (cases 1–4 + tripwires + mutation) · Trigger U split measured and published ·
nine-function census complete with fixtures · postprocess quarantined on every path · OCR_MODEL /
provenance injection closed with hostile tests · endpoint policy enforced with refusal tests ·
artifact/run-of-record selection deterministic with a multi-partition test · Q3 native-only with a
refusal test · misleading "OCR confidence" gone · 2,625 preserved · 0 blocking regressions ·
adversarial reviews completed, findings reproduced and closed, re-reviews green · full suite green ·
corpus gate / cohort replay / cold-run compare green · CI green · documentation durable · worktree
clean → **STOP. Return the closure report to Gustavo. Phase 2.1 (PaddleOCR) waits for his approval.**

## Closure (Ocean, 2026-09-02)
Every completion criterion above is met at composed code tree `941918f` (`train10`): five cells +
the P20-REPLAY-SHAPE addendum, each reviewed → closed → re-reviewed; floor preserved by the
full-archive replay (2,625 of 2,625 identical) and the cold run (2,625 → 2,625, 3,380 unchanged,
compare exit 0); suite 8,342; guards 267; conformance 1,282; gate 105/3/1; corpus slice 34; CI green
(33599700440); worktree clean. Measurements, the closure record and the residual rulings owed to
Gustavo are in `docs/moneythumb-replacement/BATCH9_TRANSITION.md` §7 (2026-09-01/02) and
`PHASE2_STATE.md`. **STOPPED. Phase 2.1 waits for Gustavo's approval.**
