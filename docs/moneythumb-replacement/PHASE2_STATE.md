---
name: phase2-state
description: "Phase 2.2 complete; Phase 2.3 in flight on train13. Reviewed W/E/X composed at b4fe667; P final closure and V/B implementation in progress. Full Phase 2.3-2.7 execution authorized on green gates; Phase 3 excluded. Read current status below; historical milestone records retain their original dated scope."
metadata:
  node_type: memory
  type: project
  originSessionId: 71746312-b66b-440b-a510-c04ff00bcdd2
  modified: 2026-09-16T01:50:00.000Z
---

## Current continuation — 2026-09-16 UTC

Reviewed W/E/X are composed at `b4fe667` on `train13`; their complete W3 histories and reviewed
source remain intact. W's live wave, custody/export boundary, equivalent historical exports and
source-qualified final privacy review are complete. Raw historical failures and scanner counts stay
visible. The five-fence P replay preserves all 2,695 selected payloads, including all 2,625 validated
results; classifier census is unchanged and all 82 completed mutations are accounted for. Its full
suite's sole comment-guard failure is preserved; the generic-comment correction passed 116 affected
tests, the 105/3/1 corpus gate, all 34 corpus tests and the ceremony inventory. The ceremony-console
privacy correction is committed at `ee0234e`; its focused baseline passed 46 tests, five new
instrument-only mutations were killed, and independent paired proof is closed. W3 is frozen at
`778be7f` with its 82-row join reviewed. The strict freeze's encoding refusal remains preserved;
source-bound reversible views resolved 19 affected files. The 243-file freeze and final scans are
complete: added lines have zero retained findings; all 16 message findings are attributed; the
232 output findings include 15 historical emission defects across three logs. Original files and
actual exits remain unchanged. Three strict aggregate summaries and explicit custody bindings are
being prepared for a fresh publication output scan and independent final P approval.

V and B now implement in separate worktrees based on `b4fe667`. Root deliberately permits this
independent source work during serialized proof windows. The composed integration passed 74 tests,
the exact two expected M7 mutation failures and two restoration checks, with a clean final tree.
V's metadata-only compiler passed synthetic proof and froze six study manifests. The V6 sample is
48 documents / 220 known pages; the orientation subset retains its explicit unknown-profile
disposition and unchanged held-metadata compiler result. Its synthetic warm-up fixture, two schedules
and four study definitions are frozen and independently reviewed. B's observer passed 45 synthetic
tests with no unintended application store; its blind comparison passed 20. The measurement/report
proof passed 158 and failed one, revealing a digest case mismatch. The reviewed fix and actual
projection-to-report round-trip passed 65 focused recovery tests; the failed result is preserved.
Each cell's remaining synthetic, review and live gates precedes execution. No alternative
configuration has processed customer pages, and no production routing or Paddle pin has changed.
The new statement batch stays sealed outside the archive until evaluation after design freeze.
Continue Phase 2.3 through 2.7 on green gates under the existing authorization; do not begin Phase 3.

The durable transition log records each merge. The current handoff and private
`discovery_reports/train13-logs/ROOT-RESUME-20260915.md` name active processes and proof paths.
Historical records below describe earlier milestones and do not revoke the later authorization.


**Baseline (unchanged)**: batch 9 FROZEN at `batch9-final` = `819d97d` (2,625 / 3,380 = 77.66%).
Phase 2.0 base `train10` opened from `origin/main` `746e1e9` (the freeze tree + the read-only census
tool + docs). Gustavo's OQ1–OQ11 rulings: `docs/moneythumb-replacement/PHASE2_RULINGS.md` (binding).

**PHASE 2.0 — SAFETY FOUNDATIONS — COMPLETE 2026-09-02 (completion gate met; STOPPED pending
Gustavo's approval of the closure report).** Composed code tree **`941918f`** on `train10` (merges
`d4bb48c` SEAM → `db63c25` POSTPROCESS → `88e33b8` ROUTER → `422c8c6` ARTIFACTS → `7424e43` SURFACES
→ Ocean's composition `51692c3` → `941918f` REPLAY-SHAPE); docs tip on the train after it. Every
cell: implementation (Sonnet 5 HIGH) → independent adversarial review (Opus; four BLOCK, two
APPROVE WITH FINDINGS) → closure with every finding reproduced first → re-review → APPROVE WITH
FINDINGS with every residual closed. Reviews under `docs/moneythumb-replacement/reviews/PHASE2_P20*`.

**What landed** (durable record: `BATCH9_TRANSITION.md` §7, 2026-09-01/02 entries):
* `ocr/escalation.py` — closed failure classes A/B/C; closed trigger vocabulary (T defined and
  refused, OQ4); `RouterInputs` with no verdict field and one constructor; `EscalationRouter` where
  only pre-financial triggers START and only `validated` STOPS; `ExtractionQualityGate` on
  extractor-produced evidence only with the parameter-free admitted triad; the density criterion
  SURFACE-ONLY (a candidate for Phase 2.1 with labelled evidence); endpoint policy enforced once at
  `ocr_client._build_client`; vocabularies enforced at the row projection; import / signature /
  subclass / repo-wide call-site tripwires; validated∩class-A = 0 pinned row-wide.
* **Trigger-U split measured** (batch-9 run and the new run of record agree): R 13 · U 123 ·
  **U-extract (admitted) 0 · U-structure 123 · density-surfaced candidate 23 · legal escalation
  population 13** · T surface 3 (1 in U) · validated∩(R∪U) 0 · row-level Class-A 0.
* Nine-function postprocess census (31 synthetic fixtures, mechanical numeric-token accounting; the
  audit's UNPROVEN debit/credit/balance fold settled as constructible); the whole chain quarantined
  on analysis AND display paths behind an EMPTY admission tuple; `embed_image_regions` unwired;
  `INTAKE_FURNITURE` register (7 entries); the no-hardcodes guard layer-wide in `ocr/` with an
  exact-match issuer-string ratchet (OQ1 = C, OQ2).
* OCR_MODEL / `source_file` injection closed (`\A…\Z` charset, money-shape and reserved-prefix
  refusal, line-break and `-->` refusal in `source_file`); `ocr/endpoint_policy.py` loopback /
  private / remote / invalid with the exact opt-in literal `I_ACCEPT_REMOTE_PAID_OCR`, IMDS and CGNAT
  forced remote, one endpoint per process, refusal before any client exists; endpoint class and
  opt-in recorded in telemetry; `source_path_for` fallthrough closed with the unrecognized-model
  diagnostic; four legacy OCR scripts retired after salvaging their checks; `parse.py`/`batch.py`
  offline by default; RunPod relabeled the paid escape hatch (OQ3, OQ6, OQ7).
* `telemetry/run_of_record.py` — the one artifact-selection policy (recorded or verified-
  reconstructed partitions with a 90 % correspondence check; row-driven; raise on a corrupt index)
  adopted by `cohort_replay`, `CachedArtifacts`, the three shared scanners and the two fixpriv
  instruments; runs record their partitions (`coldrun.sh --mode`); the OCR settings key gained
  extractor / postprocess state / raster + schema versions / endpoint class / toolchain versions;
  **OCR_STAGE_VERSION 4 → 5** with its pin (OQ8, OQ10).
* `cohort_replay` replays through the runner's exact document call (P20-REPLAY-SHAPE): full archive
  3,380 shas at the closure tip — replayed 3,351, newly validated 0, **preserved 2,625 of 2,625
  identical**, regressions 0, `--expect-unresolved 29`, exit 0.
* The fabricated "OCR confidence" replaced by validation verdict words (no number; literal guard);
  the Q3 class admitted only on `native-pdf-text*` provenance through `analysis/provenance.py`'s
  ambiguity-refuses reader (exactly one well-formed field run terminating line one), raising
  `Q3ProvenanceRefused` in EVERY parse_mode (`q3_provenance_refused` reason token); the two 2026-07
  specs SUPERSEDED (OQ9, OQ11).

**Proof at the composed tree** (`941918f`): full suite **8,342 passed / 45 skipped / 38 deselected**;
guards 267; conformance 1,282; `corpus_gate.py` GREEN 105/3/1; corpus slice 34; remote CI GREEN
run 33599700440 on `origin/train10`; **cold run** `discovery_reports/TRAIN10-941918f/2026-09-02T063646…-ef34ee30`
vs the batch-9 run of record with `--fail-on-regression`: **2,625 → 2,625, 3,380 unchanged, 0
regressed, compare exit 0**, peak 1,242 MB; the run's provenance records its partitions (the first
`origin = recorded` run); OCR-fed validated 0; ANALYSIS_STAGE_VERSION stays 17 (no payload changed).

**Discovered, NOT in scope, for Gustavo**: the pre-existing webapp auto-mode edge
`dispatch unclaimed / parser_exception → extract_statement` (`analysis/pipeline.py`, hosted model)
is a Class-B → hosted-model-call path in the product's default mode, pinned unchanged by Phase 2.0
and reported for a ruling under OQ3's spirit. Backlog carried: 33 historical `tools/*.py` still use
the old `ColdCache` signature; `tools/ocr_legacy_census.py` names the four retired scripts.

**Next**: Gustavo reviews the closure report. Phase 2.1 (PaddleOCR as the primary NEW visual
extractor, geometry into `document_geometry`, allowed only on R + U-extract, per-page provenance)
is NOT authorized until he approves.

Related: [[batch9-state]] [[moneythumb-phase1-roadmap]] [[batch8-operating-model]] [[subagent-model-policy]]

**PHASE 2.1 — PADDLEOCR + CANONICAL WORD BOXES + DOCUMENTGEOMETRY — IN PROGRESS (opened
2026-09-02).** Gustavo approved Phase 2.0 and authorized Phase 2.1 only. Train **`train11`** from
`origin/main` `9a54952`. Rulings A (automatic hosted extraction REFUSED) and B (density
SURFACE-ONLY) and the explicit Vast.ai `remote_paid` authorization (with the DATA PRIVACY BOUNDARY:
no production customer statements to Vast without a separate ruling) are recorded in
`PHASE2_RULINGS.md` §"Phase 2.1". Umbrella card `docs/agent-handoffs/PHASE2-1-PADDLE.md`; cells
`P21-GEOMETRY` (G), `P21-PADDLE` (P), `P21-ROUTING` (R — after P composes). Ocean's cell 0 landed the
`evidence/` package and `ocr/paddle_config.py` (`1282eb0`, `888fb1c`). Live record: `BATCH9_TRANSITION.md`
§7, 2026-09-02 "PHASE 2.1 OPENED" and later entries. Expected coverage movement in this phase: the
13-document legal population is customer data and is NOT sent to Vast (D8) — synthetic proof only;
Paddle-eligible 13 / attempted 0 / newly validated 0 reported honestly; the 2,625 floor untouched.

**PHASE 2.1 — COMPLETE 2026-09-03 (completion gate met; STOPPED pending Gustavo's approval of the
closure report).** Composed code tree **`4f7d798`** on `train11`: cell 0 (`evidence/` +
`ocr/paddle_config.py`, Ocean) → G `6380f67` (one `DocumentGeometry` from canonical evidence; native
byte-identical on all 109 corpus PDFs / 830 pages) → P `db2ad95` + live proof `c2c1d82` (the loopback
stdlib worker on the Vast RTX 5090, the bounded client with declaration + worker corroboration, the
3.7 adapter into immutable evidence, the fail-closed rung, the lifecycle tool, the synthetic
measurements) → R `d757f86` (`RouterInputs.enabled`; `EXTRACTOR_ORDER` = local_tesseract, paddle,
visual; the forced-path-only rung; `--scanned-paddle`; per-page provenance on every rung;
EXTRACTION_SCHEMA_VERSION 2; the customer-scope refusal at the runner) → three composed-tree integration
fixes (`bf8cd11`, `4f7d798`). Every cell: implementation → independent adversarial review → every
finding reproduced → closure → independent re-review → residuals closed (G: BLOCK → APPROVE WITH
FINDINGS; P: APPROVE WITH FINDINGS twice; R: APPROVE WITH FINDINGS twice, the re-review and closure-2
performed in the Fable 5.1 environment under `ORCHESTRATION-MODEL-POLICY.md`).

**Proof at the composed tree**: full suite **8,756 passed / 45 skipped / 39 deselected**; guards 275;
conformance 1,282; gate GREEN 105/3/1; corpus slice 34; remote CI GREEN run 33705014589; **cold run
`discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136` vs the Phase 2.0 run of
record: 2,625 → 2,625, 3,380 unchanged, compare exit 0** (peak 1,239 MB; the offline OCR partition
rebuilt under schema 2); cohort replay 2,625 / 2,625 identical at every cell's base and closure.
Measured on the new run of record: R 13 · U 123 · U-extract 0 · U-structure 123 · density-surfaced
23 · legal escalation population 13 · row-level Class-A 0 · OCR-fed validated 0 · **Paddle-eligible 13
documents / 17 pages · attempted 0 · newly validated Paddle-fed SHAs NONE · false accepts 0** (the
Paddle path proven end to end on synthetic fixtures: real PP-OCRv5 inference over the tunnel, cold e2e
5,208 ms, warm median 1,872 ms, `evidence_sha256` stable, cost "rate not measured").

**Rulings requested from Gustavo (not assumed)**: (1) may the 13-document legal escalation population
(customer statements, 17 pages) be sent to the Vast worker — the remote-data / privacy / retention
ruling (D8); until then `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` stays unset and a `--scanned-paddle`
archive run refuses by construction; (2) the Vast hourly rate for the cost figure. **Documented, not
built (Phase 2.2 prerequisites)**: the rotation-frame mismatch (0/830 pages today); the native
geometry path's discarded evidence sha (~2.7×); `analysis_input_sha` is geometry-blind; Tesseract word
boxes; a `local_free` worker deployment. **Next**: Gustavo reviews the closure report. Phase 2.2 is
NOT started; Unlimited OCR is NOT enabled.

**PHASE 2 REMAINDER — FULLY AUTHORIZED 2026-09-03 (Gustavo): 2.2 → 2.7 proceed autonomously on GREEN
gates; rulings R1–R14 in `PHASE2_RULINGS.md` §"Phase 2 remainder"; the plan
`phase2_remainder/PHASE2_REMAINDER_PLAN.md`; cost accounting is Gustavo's (never Ocean's); Unlimited
lives on a SEPARATE computer (never Vast).**

**PHASE 2.2 — TRUTH INSTRUMENTS — IN PROGRESS (opened 2026-09-03 on `train12` from `main` `a7ac9b0`;
code tree `4f7d798`).** Umbrella `docs/agent-handoffs/PHASE2-2-TRUTH.md`; cells K `P22-IDENTITY`,
C `P22-CLASSIFY`, H `P22-HOLDOUT`, F `P22-FENCE` (parallel), then T `P22-TRUTHTABLE` from the
integration base after K + C compose. Delivers: classifier (disjoint kinds summing to 755 / 3,380),
taxonomy L0–L6, `refused` + transition matrix + two denominators, sealed truth store + adjudication CLI
+ holdout cage + firewall, native evidence persisted (schema 3) in the display frame, geometry-aware
analysis key (stage 18), research partitions refused by `run_of_record`, research mode through the
router (`operator_forced_paddle`), R9 fence. Expected coverage +0; no customer page leaves the machine;
adjudication prepared for Gustavo, not a gate. Live record: `BATCH9_TRANSITION.md` §7 (2026-09-03
"PHASE 2.2 OPENED" onward). Next on GREEN: Phase 2.3 (`PHASE2-3-WAVE.md`) without a user approval.

**PHASE 2.2 — TRUTH INSTRUMENTS — COMPLETE 2026-09-11 (completion gate met; CONTINUED to 2.3 under the full authorization).** Composed code tree **`52bd8f2`** on `train12` (K → C → H → F → Ocean's two items → T `72269f4` → the hermetic Paddle-config test pin `52bd8f2`; fifteen `§P22*` W3 sections; five reviews with every finding reproduced and closed, MINOR residue recorded). Proof at the composed tree: full suite **9,827 passed / 48 skipped / 39 deselected / 0 failed** with the real `.env` present; guards 276; conformance 1,282; gate GREEN 105/3/1; corpus slice 34; privacy scan over `b23cb50..52bd8f2` (26,357 added lines): 4 residue sites, every one adjudicated non-document provenance (three pytest durations and one synthetic probe value quoted in review prose); message scan MONEY/DIGITS/DATES 0 (WORDS 8, the cells' and Ocean's own prose, attributed); **cold run `discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f` vs the Phase 2.1 run of record: 2,625 → 2,625, 3,380 unchanged, every class on the transition-matrix diagonal, refused 0, compare exit 0 (peak 1,261 MB; 5,966 s; both caches rebuilt from nothing under OCR schema 3 / raster 2 / analysis stage 18; the run started under a 1.5 GB free-memory floor and the 4 GB cap because the operator's desktop leaves ≈ 2 GB available — recorded)**; remote CI run 34567212012 (dispatched on `origin/train12` at `52bd8f2`; conclusion in the transition log). Measured on the run of record: the 755 disjoint by primary layer L1 415 · L3 223 · L5 65 · L4 35 · L0 16 · L2 1; by kind (cache census) 324 / 217 / 15 / 22 / 16 / 161; R 13 · U 123 · B 656 · C 70; Paddle attempted 0; newly validated 0; OCR-fed validated 0. Delivered: the classifier (`layout/`), the taxonomy, `refused` + the matrix + both denominators, the sealed store + adjudication CLI + holdout cage + firewall (slice-1 queue 214 packets for Gustavo), native evidence persisted with its sha in the display frame, the geometry-aware analysis key, research partitions refused by the run of record, the research mode through the router, R9 removed with the hosted edge fenced and the cache key partitioned on the opt-in, funnel/technical columns. **Next: Phase 2.3 (`PHASE2-3-WAVE.md`) on `train13` from `phase2.2-final`.**
