# Phase 2.3 — BROAD PADDLE EVIDENCE WAVE (umbrella implementation card; Ocean, 2026-09-11)

**Authority:** Gustavo's FULL PHASE 2 EXECUTION AUTHORIZATION and rulings R1–R14
(`docs/moneythumb-replacement/PHASE2_RULINGS.md` §"Phase 2 remainder", 2026-09-03 — binding, read all of
it: the Paddle customer-data authorization (provider Vast.ai · execution_class `remote_paid` · extractor
PaddleOCR; populations CTRL / U755 / SLICE / the wave; retention; the opt-in rules), R1, R3, R4, R5, R6,
R10, R11, R12, the anti-optimizer rule, the STOP conditions; **R2 WITHDRAWN — cost/billing is Gustavo's,
never Ocean's**); the approved plan `phase2_remainder/PHASE2_REMAINDER_PLAN.md` (§G.2.3 is this
milestone's design; §H the coverage plan; §D.4 the reason vocabulary; §J the classifier; §M the risks);
the Phase 2.2 instruments as composed (`docs/agent-handoffs/PHASE2-2-TRUTH.md` and its five cells); the
standing rules (`BATCH9-RULES.md` + `PHASE2-RULES.md`, carried forward in full; the Phase-2.3 delta is
§"Rules delta" below); `ORCHESTRATION-MODEL-POLICY.md`. Every Phase 2.0 / 2.1 / 2.2 invariant is binding.
**Validator success may STOP escalation; validator failure may NEVER START escalation. The validator is a
verifier, never an optimizer. Research admission and production admission are different concepts.**

## Objective (exact)
Give PaddleOCR its controlled, explicit opportunity on real customer statements, in RESEARCH partitions
the run of record can never select, and turn the result into EVIDENCE for 2.4 and 2.5: (1) read every
page of the control sample `CTRL` and of the unresolved corpus `U755` on the approved Vast Secure Cloud
instance through the Phase 2.2 research mode (`--research-paddle`), storing one immutable
`ExtractionEvidence` per page under a pinned production configuration; (2) measure extraction quality
without ground truth (E-gate v2, measured and versioned, ADMITTED AS NOTHING in 2.3); (3) measure
native↔Paddle agreement and the geometry census, calibrated on `CTRL` first; (4) run the two ruled
configuration A/Bs as separately pinned partitions (R5 PP-OCRv6; R6 orientation classifiers) on `SLICE`
and the stratified samples — the production pin does not change; (5) re-classify scans on real word
evidence, publish the **corpus truth table v2** (classifier-proposed beside adjudicated), and prepare
adjudication slice 2 for Gustavo; (6) record the first **stage-by-stage fallout** E → G → L → C → V with
the existing structurer as the baseline reconstruction, per geometry source, with every
research-validated sha NAMED and never counted; (7) the Phase 1 hygiene ceremony R10 over the six
bank-keyed `bank_repairs` rewrites; (8) the classifier-precision cycle over the Phase 2.2 residue.
Expected official coverage movement **+0**; OCR-fed validated **0**; the 2,625 floor untouched and
payload-identical; **"Paddle helped" is a per-document stage record, never one number.**

## Baseline (verified at the 2.2 closure; every number from its log)
| fact | value |
|---|---|
| `origin/main` = `HEAD` of `train13` | `d84af95` (the composed code tree `52bd8f2` — the tree the floor and the cold run measured — plus the closure docs `d591468` and one tests-only portability commit `d84af95`; `git diff 52bd8f2 d84af95 -- . ':!docs' ':!tests'` is empty) |
| `phase2.2-final` | `d84af95` (annotated, pushed 2026-09-11); CI dispatched on `origin/train12`: run 34567212012 at `52bd8f2` FAILED on one Linux-only test (a Windows-separator variant of T's containment pin, fixed in the test at `d84af95`) → run **34567935218 SUCCESS** at `d84af95`; the main-push run is recorded in `BATCH9_TRANSITION.md` §7 |
| train branch | **`train13`** (opened 2026-09-11 from `main` at `phase2.2-final` = `d84af95`, checked out in the main checkout) |
| floor | 2,625 / 3,380 (77.66 %); Phase 2.2 cold run **`discovery_reports/TRAIN12-52bd8f2/<run>`** vs the Phase 2.1 run of record: 2,625 → 2,625, 3,380 unchanged, compare exit 0; its cold cache **`.claude/recovery/webapp_data_train12_cold`** (READ-ONLY; OCR schema 3 / stage 5 / raster 2; analysis stage 18) — THE run of record and cold cache for every 2.3 comparison |
| versions | OCR_STAGE_VERSION 5 · EXTRACTION_SCHEMA_VERSION 3 · EVIDENCE_SCHEMA_VERSION 1 · RASTER_VERSION 2 · ANALYSIS_STAGE_VERSION 18 · DIAGNOSTICS_VERSION 5 · UNRESOLVED_TAXONOMY_VERSION 1 · CLASSIFIER_VERSION (cell C's) · registry 84 |
| suite at the composed tree | 9,827 passed / 48 skipped / 39 deselected / 0 failed (with the real Paddle `.env` present); guards 276; conformance 1,282; gate GREEN 105/3/1; corpus slice 34 |
| the 755 (run of record) | disjoint primary layer L1 415 · L3 223 · L5 65 · L4 35 · L0 16 · L2 1; classifier (cache census) 3,380 = 2,518 / 581 / 15 / 23 / 16 / 227 and 755 = 324 / 217 / 15 / 22 / 16 / 161 by kind; validated exceptions 431 (a signal defect, never a coverage question); diagnostic labels R 13 · U 123 · A 0 / B 656 / C 70 · truncation 4 · refused 0 |
| Paddle | attempted 0 on any customer page to date; the Vast Secure Cloud instance proven with the Phase 2.1 lifecycle (worker loopback 8765, tunnel local 18765; connection only in the gitignored `.env`); warm median ≈ 1.2–1.9 s / synthetic page; VRAM 7.7 GB of 32 |
| adjudication | slice-1 queue: 214 packets prepared for Gustavo (cell H); NOTHING adjudicated yet — v1 truth lands whenever he adjudicates; never a gate |

## Scope — six bounded cells, disjoint FILE ownership; Ocean composes
| cell | card | delivers | plan |
|---|---|---|---|
| **W — WAVE RUNNER** | `P23-WAVE.md` | `tools/paddle_wave.py` (resumable by sha; instance up → tunnel → identity against the pins → pages one at a time under the existing bounds → evidence stored → instance stopped; every page attempted or refused with an E0 reason; a page never sent twice under one configuration — cache hit with sha equality); the per-request technical telemetry threaded to the row (`bytes_up` / `bytes_down` / `inference_ms` / `vram_mb` — cell T's named STOP: one field on `StatementMarkdown` in `ocr/document.py` and one line in `ocr/pipeline.py`); rasters retained in the research partition (D2); the retention attestation (`/version` reports `retention: none`; `stop` leaves no files on the instance — proven on the real instance); the three population files and their digests; the wave logs | §G.2.3 cell W (runner half), §H.1, D1–D5 |
| **E — E-GATE v2** | `P23-EGATE.md` | `ocr/extraction_quality.py` v2: per-page word count and density, rec-score distribution (mean, p10) calibrated PER CONFIGURATION, money-shape parse rate, lexicon rate (EN/FR/ES from `layout/signals.py`), garbage-token rate, box regularity, ink-versus-box coverage from the raster, orientation votes — every metric MEASURED and VERSIONED, none admitted as a trigger (Ruling B's discipline); synthetic defect pages for each metric; the E-class census E0–E3/E5 (§H.4) on CTRL and U755 | §G.2.3 cell W (gate half), §H.4 |
| **X — AGREEMENT & GEOMETRY CENSUS** | `P23-AGREE.md` | `layout/agreement.py`: greedy IoU ≥ 0.5 alignment after frame normalisation for every page with both native and Paddle words; matched ratio each way; normalised character agreement; exact agreement of parsed amounts and dates; unmatched density in candidate table regions; page-size / rotation / skew census; calibrated on CTRL before U755 (D3); the K re-review latents closed here (N-1 overhanging CropBox on a rotated page; N-2 an indirect `/Rotate` object) | §G.2.3 cell X |
| **V — CONFIGURATION A/B (R5, R6 — RULED YES)** | `P23-CONFIG.md` | two further pinned configurations, each its own pin block and partition: `research/paddle-v5-orient` (`use_doc_orientation_classify=True`, `use_textline_orientation=True`) on the scanned/mixed population; `research/paddle-v6` (`PP-OCRv6` per R5's comparison list: numeric and character fidelity, missing/extra tokens, geometry, completeness, scanned pages, downstream reconstruction, false evidence, stability, latency, VRAM) on SLICE + a 200-page stratified sample; the production pin UNCHANGED; never a silent switch | §G.2.3 cell V, §H.2, R5, R6 |
| **B — BASELINE FALLOUT** | `P23-FALLOUT.md` | the existing structurer under `reconstruction_mode=research` in the research partition, geometry from native and from Paddle evidence SEPARATELY, over U755: the funnel E → G → L → C → V per geometry source with every research-validated sha named and every refusal coded (B1–B8 into L3, the W3-2 classes into L4); on CTRL the Paddle-path candidate's key fields (opening, closing, count, Σ) compared to the recorded validated payload — any disagreement a FALSE-ACCEPT CANDIDATE sent to adjudication, the comparison blind to the validated payload until it runs; "Paddle helped" per document (§H.6); truth table v2 (`tools/truth_report.py` extended: classifier on Paddle evidence for scans, adjudicated beside proposed); adjudication slice 2 queue (verdict changed between Tesseract text and Paddle evidence; every KIND_UNCERTAIN; every false-accept candidate; a random 50) | §G.2.3 cell B + adjudication slice 2, §H.3, §H.6 |
| **P — PRECISION & HYGIENE** | `P23-PRECISION.md` | the classifier-precision cycle (inputs: the C re-review R-1..R-4 — MICR over-closure, the boilerplate-footer page-marker precedence, the head counterpart of the restart rule, hyphen-joined ISO ranges; the 431/461 validated-exception residue by its two signal classes; the truth table v0 → v2 movement measured per rule); the R10 Phase 1 hygiene ceremony over the six bank-keyed `bank_repairs.py` rewrites (inventory → independent reproduction → comparison with the repair doctrine → classification safe-normalisation / unsafe-rewrite / legacy-needing-replacement → tests and tripwires; delete nothing for being bank-specific, keep nothing for being old; no new bank-keyed repair as coverage); the Phase 2.2 test residue: F re-review-3 Q2 (one top-level definition per orchestration name in the fence tripwire) and Q1 (the mutation harness appends, never overwrites, its table log); T's carried latents if any | R10, the 2.2 reviews' residue |

Composition order at the train: **W → E → X → (V after W) → B → P** (E, X, P may be launched in parallel
with W on synthetic fixtures; V and B need W's partitions; B needs E and X). Ownership is disjoint by
construction (each card lists exact files); any overlap discovered is reported to Ocean, never resolved
by a cell.

## Material design decisions (Ocean; each preserves every binding invariant)

**D1 — research partitions are immutable and excluded from the run of record by construction.**
`research_partition` in the OCR settings key (cell K) + `run_of_record`'s refusal (K) + the research
mode's separate `--data-dir` (T, refused if it is or is inside a production cache); a research evidence
file is never rewritten; a second run under the same configuration is a cache hit with sha equality
asserted. *Tests:* case 1, 2.

**D2 — page rasters are retained in the research partition** (PNG at 300 dpi, sha-named, gitignored,
under the archive's retention rule) so 2.4 and a future Phase 3 measure on the same pixels; production
partitions keep only `raster_sha256`. *Tests:* case 3.

**D3 — control sample first.** CTRL runs before U755 so the agreement baseline and the false-accept
instrument exist before any unresolved document is read. *Tests:* case 8 (the wave refuses to start U755
while CTRL has an unattempted page).

**D4 — every page attempted or refused with a reason** (E0 with the worker's error class); no silent
skips; the escalation count equals the population size by construction. *Tests:* case 4 (a mutant that
skips on exception fails the population-count test).

**D5 — cost is OUT OF SCOPE (R2 withdrawn).** The plan's "cost computed from the ruled rate" is
SUPERSEDED: no rate, no cost column, no cost gate, no billing field — the T grep test stands; the report
prints GPU-seconds, bytes, latency and VRAM as TECHNICAL measurements only. Gustavo tracks the charges.

**D6 — the customer-data opt-in lives only in the run's environment.** `PADDLE_REMOTE_OPT_IN` and
`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` are set in the command environment of an authorized wave run and
nowhere else — never in a tracked file, never in `.env`, never the default of auto mode; the research
mode's up-front preflight names the missing literal; the wave runner records in its log which population
and partition the run was authorized for (R1's scope), never a document's contents. *Tests:* case 5.

**D7 — E-metrics are labelled evidence, never triggers.** Every threshold is versioned
(`EXTRACTION_QUALITY_VERSION`), every metric has a synthetic defect page that moves it, and NOTHING
under `ocr/escalation.py`'s admitted triggers changes in 2.3; the E-gate v2 verdicts are row columns.
*Tests:* case 6; the D4 tripwire and the router's admitted set pinned unchanged.

**D8 — the false-accept instrument is blind until comparison.** On CTRL, the Paddle-path candidate is
produced and its key fields recorded BEFORE the validated payload is read; the comparison is a separate
step over recorded rows. A disagreement is a false-accept CANDIDATE → adjudication; never a label.
*Tests:* case 9.

**D9 — a research-validated sha is NAMED, never COUNTED.** The headline coverage excludes research
partitions by construction (T); the report prints "research-validated pending admission" as its own
row; admission is 2.5's, after measured triggers. *Tests:* case 10.

**D10 — the second configurations are separate pins and partitions; the production pin is untouched.**
`ocr/paddle_config.py` gains named CONFIGURATION blocks (`paddle-v5-prod` = the Phase 2.1 pins;
`paddle-v5-orient`; `paddle-v6`) selected by the wave runner ONLY; production code reads the production
block; a test pins the production block byte-identical to Phase 2.1's. *Tests:* case 11.

**D11 — the host lock and the spend-limit recovery are rules of every card.** Acquire ONLY with
`mkdir discovery_reports/train13-logs/HARNESS.lock`, write `holder.txt` inside, poll UNBOUNDED, release
ONLY your own holder, retry on `PermissionError` and use Git bash `rmdir` when Python's is refused, confirm
the directory is gone; wave runs are resumable by sha and every runner writes a durable log ending in
`EXIT=`; an agent terminated mid-task is resumed from the disk state, never restarted.

## Contracts
* **Populations** (`discovery_reports/train13-logs/populations/`, gitignored; digests in the W3):
  `CTRL.shas` = all Tesseract-validated scans (36 at the run of record) + native-validated documents
  stratified by census family and page-count bucket (≈ 114); `U755.shas` = every unresolved sha at the
  run of record (755 / 5,110 pages); `SLICE.shas` = the 34-document corpus slice; `HOLD` = never in any
  research population (refused by the digest, cell H/T). Every population file is content shas with `#`
  comments; a sha in two populations is read once per configuration.
* **Partitions:** `research/paddle-v5-prod` (the one that counts), `research/paddle-v5-orient`,
  `research/paddle-v6` — ids validated by K's shape; each under its own `--data-dir`.
* **Rows:** the Phase 2.2 funnel columns populated (`stage_extract = paddle`, `stage_evidence`,
  `stage_geometry`, `stage_layout`, `stage_candidate`, `stage_verdict`), the E-class, the agreement
  statistics, the classifier verdict on Paddle evidence, `research_partition`, the technical telemetry.
* **Reports:** the E-metric census; the agreement report; the truth table v2; the fallout funnel per
  source; the "Paddle helped" table by census family; the retention attestation; the technical
  performance table (latency percentiles, VRAM, bytes, peak RSS) — no cost.

## Required cases (mapped)
| case | property | cell |
|---|---|---|
| 1 | a research partition's artifacts are refused by `run_of_record` and never selected by `cohort_replay` or the train's cold run; the production OCR key is byte-identical with the partition empty | W |
| 2 | a second wave run under the same configuration is a cache hit with sha equality; a drifted evidence blob is a named finding, never rewritten | W |
| 3 | rasters retained sha-named under the partition; the production partition keeps only `raster_sha256` | W |
| 4 | every page attempted-or-refused; the population count equals attempted + refused; a skip-on-exception mutant is caught | W |
| 5 | the wave refuses without both literals in ITS environment, names the missing one, sends nothing; the literals appear in no tracked file and not in `.env` | W |
| 6 | every E-metric moves on its synthetic defect page (blank, half-covered, 90°, noise, digit-glyph substitution); thresholds versioned; `ADMITTED_TRIGGERS` unchanged | E |
| 7 | agreement on synthetic native+raster pairs: identical → 1.0; shifted → known drop; perturbed amounts → exact-agreement drop; rotation/skew census correct on the 0/90/180/270 fixtures; K's N-1/N-2 pages handled by name | X |
| 8 | CTRL before U755 by construction | W |
| 9 | the false-accept comparison is blind until it runs; a disagreement is a candidate row, never a verdict | B |
| 10 | research-validated shas named in their own row; headline coverage unchanged; `--fail-on-regression` against the 2.2 run of record exit 0 | B |
| 11 | the production configuration block is byte-identical to Phase 2.1's; the two A/B blocks are selectable by the wave runner only | V |
| 12 | the retention attestation inspects the real instance after `stop` (no worker files, no request artefacts) and is recorded in the closure | W |
| 13 | no document text in any wave log, row, report or commit (privacy scan over the wave outputs and every branch; message scans) | all |
| 14 | the technical telemetry columns are populated on Paddle rows from the client's per-request fields and empty elsewhere; no cost/price/rate/usd/billing key anywhere (T's grep test) | W |
| 15 | the R10 ceremony: each of the six rewrites inventoried, reproduced independently, classified, and either kept with a tripwire or replaced with the doctrine's reason; the corpus gate and the union replay identical | P |
| 16 | the precision cycle: every rule change measured on the cache census before/after (validated exceptions per class), the truth table v0 → v2 movement named per rule; no routing from classification | P |

## Corpus measurements at closure
CTRL and U755 every page attempted-or-refused (counts by E-class) · the E-metric census per configuration
· the agreement report (CTRL calibration; U755 distribution) · the geometry census · the truth table v2
with adjudication status per sha · the fallout funnel per geometry source with research-validated shas
named and "Paddle helped" by census family · the false-accept candidates (named, queued) · adjudication
slice 2 (count, packet digest) · the A/B partitions' comparisons (R5, R6) · technical performance
(latency percentiles, VRAM, bytes up/down, GPU-seconds, peak RSS) · the retention attestation · newly
validated 0 · OCR-fed validated 0 · floor, cold run vs the 2.2 run of record, CI.

## Regression gates
Per cell: `newly validated = 0`; `previously validated preserved = all, payload identical` (cohort
replay `--expect-identical` at base and closure over the cell's named cohorts; the union for any cell
touching `ocr/`, `analysis/` or the runner's analysis call); mutation tables complete; privacy scan 0
over added lines AND over the wave outputs; message scan 0; no secret, host, port, token, literal in any
added line. At the train: the union replay; `floor.sh` green; the cold run at the composed tree vs the 2.2
run of record with `--fail-on-regression` (2,625 → 2,625); CI green with its run id read.

## Adversarial review plan
Every cell branch gets an independent adversarial review (fresh agent; reads only the rulings, this
card, the cell card, the diff and the tests), findings reproduced before acceptance, BLOCK/MAJOR closed
pre-compose, re-review green; MINORs closed where cheap or carried as recorded residue. Attack list: a
research artifact selectable by a production replay · a page leaving the machine without both literals
in THAT run's environment · document text in any log, row, report or message · an E-metric reaching a
trigger or a verdict · the false-accept instrument reading the validated payload before comparison · a
research-validated sha counted anywhere · the production pin changed by an A/B block · the retention
attestation not inspecting the instance · a holdout sha in any population · a repairs rewrite kept
without a doctrine reason or deleted without one · a classifier rule change moving a verdict without a
measured before/after.

## Rules delta for Phase 2.3 cells (over BATCH9-RULES + PHASE2-RULES + the 2.2 delta)
* Train **`train13`** from `origin/main` at `phase2.2-final`; worktree `.claude/worktrees/mt23-<card>`,
  branch `wave23-<card>`; run of record and cold cache = the Phase 2.2 cold run and
  `webapp_data_train12_cold` (READ-ONLY; every earlier cold cache READ-ONLY).
* **Network:** ONLY the wave runner (cell W) and the A/B cell (V) contact the Vast Secure Cloud instance,
  only through the Phase 2.1 lifecycle (`python -m tools.paddle_vast check/deploy/start/tunnel-up/
  status/measure/stop/tunnel-down`; loopback tunnel; connection details from the gitignored `.env` only),
  only in an authorized wave run whose environment carries both literals, only over the named
  populations. Every other cell: the in-process fake worker.
* **Customer data:** authorized for CTRL / U755 / SLICE on this instance (R1); the remote worker keeps
  nothing; request artefacts removed after processing; local partitions and rasters under the archive's
  retention rule; no customer statement, raster, extracted content, sha-with-verdict or figure in any
  tracked file, log excerpt, W3 line or commit message. The 13-document Phase 2.1 population is part of
  U755 and is read under this authorization. Do NOT use the previous (pre-2026-09-04) instance.
* **Cost / billing:** never measured, estimated, recorded or gated. Technical performance only.
* **Heavy proofs and wave runs one at a time on this host** under the mkdir-only lock (D11); the wave's
  long runs detached, resumable, with `EXIT=` logs under `discovery_reports/train13-logs/<cell>/`.
* **Spend-limit recovery:** read the disk (branch tips, worktree status, `MASTER.log`s, W3 section
  counts, the wave's resume state), resume the same agent with the exact facts or re-dispatch with them;
  never rerun a completed proof; never restart a cell.
* Python 3.14 locally / 3.12 in CI. W3 sections `# §P23<CARD> — …` appended to `W3_TRACKA_LOG.md`.
  Report contract as PHASE2-RULES plus **evidence-wave evidence** (attempted / refused / E-class counts;
  the partition ids; the retention attestation) and **agreement evidence** (X), **fallout evidence** (B).

## Explicit exclusions (Phase 2.3)
Any production routing change (2.5) · admission of any E-metric or agreement statistic as a trigger ·
structurer or `rows.py` / `core.py` reconstruction changes (2.4) · a production pin change (v6 or
orientation — separate partitions only) · Unlimited (2.6, a SEPARATE computer) · new bank parsers · a
Paddle read of any HOLD sha · running the wave in auto mode or through the webapp · any cost accounting ·
the R14 integrity flag (2.4) · the declined branch (2.4) · `evidence_refs[]` on published values.

## Completion criteria (Phase 2.3 is complete only when ALL hold — then CONTINUE to 2.4 without asking)
Every page of CTRL and U755 attempted-or-refused under `paddle-v5-prod` · the E-metric census, the
agreement report and the geometry census published · the truth table v2 published with adjudication
status per sha and slice 2 prepared for Gustavo (adjudication NOT a gate) · the baseline fallout table
published per geometry source with research-validated shas named and ZERO admitted coverage movement ·
the R5 and R6 partitions measured and compared, the production pin unchanged · the retention attestation
recorded · the technical performance table recorded (no cost) · R10 ceremony complete · the precision
cycle measured · mutation tables complete · every case green · 2,625 preserved payload-identical ·
newly validated 0 · OCR-fed validated 0 · proof floor green · cold run vs the 2.2 run of record green ·
CI green · adversarial reviews complete, re-reviews green · docs durable (`BATCH9_TRANSITION.md` §7,
`PHASE2_STATE.md`, `PROJECT_STATUS.md`, this card's §Closure, the reviews, the handoff) · worktree clean
→ **Phase 2.4 opens (`PHASE2-4-RECON.md`) with the archetype list derived from the B-class fallout,
without a user approval.**
