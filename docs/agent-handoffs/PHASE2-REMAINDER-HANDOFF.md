# PHASE 2 REMAINDER — HANDOFF TO THE NEXT LEAD ORCHESTRATOR (written 2026-09-10 by Ocean, Fable 5.1)

> **UPDATE 2026-09-11 (Ocean, the session that resumed from this file): PHASE 2.2 IS COMPLETE.** Everything in §2–§3 below
> happened as planned and is now history: F closure-2's W3 section was completed from its logs (`fc65067`), F went through
> re-review 2 → closure-3 → re-review 3 (APPROVE WITH FINDINGS; Q1/Q2 carried) and COMPOSED at `b49bbc2`; Ocean's item 2 landed
> at `4a9ba53`; T was re-dispatched from its dirty state, delivered `01ab992`, review → closure `0273626` → re-review → the
> MINOR-8 comment `59a3b3b`, COMPOSED at `72269f4` (the W3 rebuilt EXPLICITLY — the helper would have duplicated F's sections
> because of two merge bases); one composed-tree integration fix `52bd8f2` (the Paddle-config token pin made hermetic — it
> read the host's minted `.paddle_runtime/worker.token`). Closure proofs at `52bd8f2`: suite 9,827 / 0 failed with the real
> `.env`; guards 276; conformance 1,282; gate GREEN 105/3/1; corpus slice 34; privacy 4 residue sites all adjudicated
> (pytest durations / a synthetic probe in review prose); messages WORDS 8 (own prose); **cold run
> `discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f` vs the Phase 2.1 run of record: 2,625 → 2,625,
> 3,380 unchanged, the matrix wholly diagonal, refused 0, compare exit 0** (cold cache `.claude/recovery/webapp_data_train12_cold`
> — READ-ONLY from now on; the run started under `FLOOR_GB=1.5 CAP_GB=4 OCR_MAX_WORKERS=1` because the desktop leaves ≈ 2 GB
> available). CI: dispatch run 34567212012 at `52bd8f2` FAILED on one Linux-only test (a Windows-separator
> variant of T's containment pin; fixed in the test at `d84af95`) → dispatch run 34567935218 SUCCESS at `d84af95`;
> main fast-forwarded to `d84af95`, tag `phase2.2-final`, main-push run 34569026745 SUCCESS. The durable record: `BATCH9_TRANSITION.md` §7 (2026-09-10 / 09-11 entries),
> `PHASE2_STATE.md`, `PROJECT_STATUS.md`, `PHASE2-2-TRUTH.md` §Closure, the five reviews. **The next lead reads
> `docs/agent-handoffs/PHASE2-3-WAVE.md` (the Phase 2.3 umbrella card) and the transition log's last entries; §4–§6 below
> remain the operating discipline. Lock rule: mkdir-only, holder inside, own-holder release, Git bash `rmdir` when Python's is
> refused, unbounded waits. Open items for Gustavo: slice-1 adjudication (214 packets); the untracked
> `docs/moneythumb-replacement/superpowers/` directory (an old copy found on disk 2026-09-10, left in place); rotating
> `.paddle_runtime/worker.token` before the first 2.3 wave run (its value was printed into a gitignored local log, redacted).**


You are taking over as **Ocean**, the lead orchestrator of the Capital Infusion bank-statement engine, in the
middle of **Phase 2.2 (Truth Instruments)** of the Phase 2 remainder program. This file tells you exactly
what the program is, what has been implemented, what is in flight (and where it stopped), and what is left.
Everything below was verified from the repository, the branches, the worktrees and the logs on
2026-09-10 immediately before this handoff; nothing is from memory alone.

**Recover from durable state; never restart completed work; never rerun a completed heavy proof.**

---

## 0. Read these first, in this order

1. `docs/moneythumb-replacement/PHASE2_RULINGS.md` — all of it. The section
   "Phase 2 remainder — FULL EXECUTION AUTHORIZATION and rulings R1–R14 (Gustavo, 2026-09-03) — BINDING"
   is your authorization and your limits (STOP conditions included).
2. `docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md` — the plan (sections A–R).
   §F/§G are the milestone cards 2.2 → 2.7; §O is the roadmap; §D.4 the reason vocabulary; §H the Paddle
   wave; §I the reconstruction plan; §J classification; §K Unlimited; §M risks. The nine companion memos are
   under `docs/moneythumb-replacement/phase2_remainder/research/`.
3. `docs/agent-handoffs/PHASE2-2-TRUTH.md` — the Phase 2.2 umbrella card (design decisions D1–D11, the
   contracts, the 25 cases, the rules delta, the completion criteria). Then the five cell cards
   `P22-IDENTITY.md`, `P22-CLASSIFY.md`, `P22-HOLDOUT.md`, `P22-FENCE.md`, `P22-TRUTHTABLE.md`.
4. `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `ORCHESTRATION-MODEL-POLICY.md` — the house
   discipline every cell and reviewer follows.
5. `docs/moneythumb-replacement/BATCH9_TRANSITION.md` §7 (the execution log; the last entries are the Phase
   2.2 compositions), `PHASE2_STATE.md`, `PROJECT_STATUS.md`.
6. `docs/moneythumb-replacement/W3_TRACKA_LOG.md` — append-only. The Phase 2.2 sections are headed
   `# §P22IDENTITY*`, `# §P22CLASSIFY*`, `# §P22HOLDOUT*`, `# §P22FENCE*` (each cell's report, closure and
   proof numbers live there, not in this file).
7. The committed reviews: `docs/moneythumb-replacement/reviews/PHASE2_P22{IDENTITY,CLASSIFY,HOLDOUT,FENCE}_REVIEW.md`
   (each holds the first review and the re-review sections).

---

## 1. The program (what Phase 2 remainder is)

Phase 1 (deterministic parsers + multi-account v1) is FROZEN at tag `batch9-final` with the official floor
**2,625 / 3,380 validated (77.66%)**. Phase 2.0 (safety foundations) and Phase 2.1 (PaddleOCR 3.7 / PP-OCRv5
on a Vast RTX 5090 as a `remote_paid`, opt-in extractor; canonical evidence; one `DocumentGeometry`) are
COMPLETE on `main` (tag `phase2.1-final`, code tree `4f7d798`). The run of record for every comparison is
`discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136` (3,380 shas; 2,625 validated;
755 unresolved) with the READ-ONLY cold cache `.claude/recovery/webapp_data_train11_cold`.

The remainder is six milestones, executed autonomously on GREEN gates (Gustavo's authorization, R1–R14):

| Milestone | Content | State |
|---|---|---|
| 2.2 Truth Instruments | classifier · unresolved taxonomy L0–L6 · `refused` + two denominators · sealed truth store + holdout · native evidence + geometry-aware analysis key · R9 fence · research mode | **IN PROGRESS — see §2/§3** |
| 2.3 Broad Paddle Evidence Wave | CTRL + U755 (+ SLICE) populations through Paddle on the Vast Secure Cloud instance · E-gate v2 · agreement · truth table v2 · baseline fallout · config A/B (R5 PP-OCRv6, R6 orientation) · R10 bank_repairs hygiene ceremony · classifier-precision cycle | NOT STARTED (card `PHASE2-3-WAVE.md` not yet written) |
| 2.4 Generalized Reconstruction v1 | `layout/` LayoutModel + structurer v2 · archetypes · holdout pass · native gains admitted | NOT STARTED |
| 2.5 Reconstruction v2 + Paddle production admission | measured triggers · page-level · disagreement · lineage · deployment class (R8) | NOT STARTED |
| 2.6 Unlimited OCR go/no-go | SEPARATE computer (R7); extractor-only; STOP before any customer document reaches a new external provider | NOT STARTED |
| 2.7 Phase 2 closure | routing frozen from evidence · both denominators · runbooks · Phase 3 seam · `phase2-final` | NOT STARTED |

Phase 3 (multimodal producer) is NOT authorized. Do not begin it.

**Binding constraints you inherit (verbatim in effect):** cost/billing is Gustavo's and never Ocean's (no
rate, no cost telemetry, no billing fields, no cost gates — a grep test in cell T enforces this); Gustavo is
the only adjudicator of truth (R3; MoneyThumb / folder / census / parser / OCR outputs are never labels);
the validator is a verifier only — never "try candidates until one reconciles"; never weaken the validator;
any exit from `validated` is a regression; never commit the Vast host, SSH details, credentials, secrets or
customer data (connection details live only in the gitignored `.env`); `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN`
may be set only in the environment of an authorized research/evaluation run, never in a tracked file, never
the default of ordinary auto mode; no customer statements, rasters or extracted contents in any tracked file,
fixture, test or commit message (synthetic fixtures, dates ≥ 2031); do not use the previous Vast instance for
new customer data; do not silently switch to PP-OCRv6; the Unlimited computer is separate and any forwarding
to Baidu-hosted inference or another vendor is NOT authorized (STOP first).

**STOP conditions** (report to Gustavo, do not proceed): validator weakening; an unclosable false accept; an
unexplained validated regression; customer data to a NEW external provider; abandoning Phase 1 / 2.1 /
the 2,625 floor; security/legal beyond the authorization; holdout fundamental failure; a disproven premise;
Phase 3; the Unlimited computer unavailable for a live proof.

---

## 2. Phase 2.2 — what is DONE (composed on `train12`)

Branch `train12` (opened from `main` `a7ac9b0`; Phase 2.2 code base commit `b23cb50` carries the cards).
**`train12` tip at this handoff: `0f83190`.** Composition order was K → C → H → (F) → (T).

| Cell | Branch / tip | Composed on train12 | What landed |
|---|---|---|---|
| **K** P22-IDENTITY | `wave22-identity` `bc6e7cb` (code `f96617e`) | **YES** `87b5474` (+ docs `0d2c99c`) | The one native reader `evidence/native.py` (display-frame word boxes; ruling (c): a `pdf_point` frame is a viewport — out-of-frame words noted, never refused); native evidence persisted with its sha (`EXTRACTION_SCHEMA_VERSION` 3, `EVIDENCE_SCHEMA_VERSION` 1); `analysis_input_sha(..., evidence_sha256=)`; `Settings.reconstruction_mode ∈ {off, research, production}` in the analysis key (`ANALYSIS_STAGE_VERSION` 18; `GENERIC_STRUCTURER_ENABLED` retired); the OCR key's `research_partition` field refused by `run_of_record`; `tools/train/provenance.py --research-partition`; the rasteriser renders the CropBox (`RASTER_VERSION` 2); invalid `/Rotate` refused; the hermetic provenance test (K made `tests/test_run_of_record.py` control its own `PADDLE_*` environment — Gustavo: "Do NOT remove my real Paddle config; make the test control its own environment"). Review APPROVE WITH FINDINGS (4 MINOR) → closure-2 → re-review APPROVE WITH FINDINGS (two latent zero-population MINORs recorded for 2.3). |
| **C** P22-CLASSIFY | `wave22-classify` `4a5f381` (code `473f7d7`) | **YES** `40f619f` (+ docs `fcbb759`) | `layout/document_class.py::classify_document(evidence, page_texts, profile) -> DocumentClass` (KINDS: STATEMENT_COMPLETE / STATEMENT_PARTIAL / STATEMENT_ILLEGIBLE / ACTIVITY_EXPORT / NOT_A_STATEMENT / FILE_INVALID / KIND_UNCERTAIN; tiers structural / lexical / uncertain; card ∧ deposit-furniture → KIND_UNCERTAIN); `tools/classify_census.py`; committed mutation harness `tools/p22classify_mutation_table.py`. `Finding.detail` is a closed `key=number` grammar (a reader that renders it must be in `ALLOWED_DETAIL_READERS`). Precision residue: 461 (native) / 431 (cache) validated docs classified as exceptions, all signal defects — scheduled for the **classifier-precision cycle in 2.3** (inputs: C re-review R-1..R-4). Review → closure → re-review APPROVE WITH FINDINGS. |
| **H** P22-HOLDOUT | `wave22-holdout` `3464eb4` | **YES** `e32c1a4` (+ docs `1bc8022`) | Sealed truth store OUTSIDE the checkout/OneDrive (`SEALED_TRUTH_DIR`), hash-chained append-only JSONL with manifest verification before every append; `tools/adjudicate.py`; the holdout manifest with freeze-tag graduation (`*-final` tag dated after evaluation); dev-corpus assertion against the run-of-record `rows.csv` digest; Decimal money comparison in `tools/holdout/evaluate.py`; the leakage firewall test (nothing under `discovery/` or `telemetry/` may reference `SEALED_TRUTH_DIR` or `tools.holdout`); the repository digest `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` (the ONLY thing runtime code may read about the holdout). **Slice-1 adjudication queue: 214 packets at `C:\Users\GustavoPrietodePaula\AppData\Local\CapitalInfusion\adjudication\packets\slice1`** — Gustavo adjudicates; adjudication is NOT a gate. Review (3 MAJOR / 6 MINOR) → closure → re-review (1 new MAJOR: money compared as strings) → closure-2 → re-review 2 APPROVE. |
| **F** P22-FENCE | `wave22-fence` `1c09faa` (closure-2 code; re-reviewed tip was `5c59524`) | **NO — closure-2 done, re-review-2 and composition pending** | The reconciliation-based selection between two hosted extractions REMOVED from `analysis/pipeline.py` (R9); the auto-mode Class-B → hosted edge fenced behind `HOSTED_EXTRACTION_OPT_IN == "I_ACCEPT_HOSTED_MODEL_EXTRACTION"` (`analysis.pipeline.hosted_extraction_opted_in`); AST tripwires (per-unit cross-scope, name-integrity N1–N6, rule B5, definers scanned); deterministic mode byte-identical over the union of every registration. Consequence handed to T: `issues.append(` sites in `analysis/` are now 6 (reconcile.py) / 0 (pipeline.py). See §3.1 for the exact state. |
| **T** P22-TRUTHTABLE | `wave22-truthtable` `1901201` (+ uncommitted work) | **NO — implementation started, agent died** | See §3.2. |

**Ocean's own composition items** (checklist kept in the session scratchpad; reproduced here):
1. `webapp/static/app.js` no-parser guidance reworded — **DONE, `0f83190` on train12** (F review MINOR F5).
2. `webapp/artifact_cache.py::analysis_settings_key` must partition on the hosted-extraction opt-in (F review
   MINOR F3, second half) — **DRAFTED, NOT APPLIED**: add the field `"hosted_extraction_opt_in":
   bool(hosted_extraction_opted_in())` (import `from analysis.pipeline import hosted_extraction_opted_in`
   function-locally, next to `structurer_enabled`), a docstring paragraph, and a test in
   `tests/test_artifact_cache.py` (delenv → key A; setenv literal → key B ≠ A; setenv "yes" → key A). Apply on
   train12 ONLY AFTER F composes (the predicate lives in F's code). `ANALYSIS_STAGE_VERSION` stays 18 (no run
   of record exists at 18 yet; the train12 cold run rebuilds every analysis payload anyway).
3. `webapp/worker.py::_DECLARED_ANALYSIS_REFUSALS` — after F's closure-2 reverted the message line, the worker
   publishes the deterministic literal again; a `hosted_extraction` attribute publication is OPTIONAL, not
   blocking.

**Infrastructure proven for 2.3 (no customer page has been sent anywhere yet):** the Vast Secure Cloud
instance (host / SSH port / user only in the gitignored `.env`: `PADDLE_PROVIDER=vast.ai`,
`PADDLE_EXECUTION_CLASS=remote_paid`, `PADDLE_VAST_HOST`, `PADDLE_VAST_SSH_PORT`, `PADDLE_VAST_SSH_USER`) was
proven end to end twice with the unchanged Phase 2.1 lifecycle `python -m tools.paddle_vast
check/deploy/start/tunnel-up/status/measure/stop/tunnel-down` (worker on the instance loopback 8765, tunnel
local 18765 — the instance's Jupyter owns 0.0.0.0:8080, so the requested 8080 was NOT used; documented in
`PADDLE_VAST_RUNBOOK.md` / `PADDLE_MEASUREMENTS.md`). `PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR`
only in a command's environment; live test `tests/test_paddle_live.py -m live`; the customer-scope probe
without the customer-data opt-in refuses (`PaddleRefused: remote_customer_data_refused`) before any
connection. PP-OCRv5 is the baseline; v6 only as a separately pinned A/B config (R5).

---

## 3. Phase 2.2 — what is IN FLIGHT (exact stop points)

Both running agents were terminated by the API spend limit on 2026-09-10 at about 10:20. Their durable state:

### 3.1 Cell F closure-2 (worktree `.claude/worktrees/mt22-fence`, branch `wave22-fence`)
* Code + tests committed at **`1c09faa`** ("closure-2 of the re-review — N1 the refusal message reverted to
  the deterministic text (attribute kept), N2 the tripwire's loop / sibling-route / re-invocation
  walk-arounds closed, N3 the block comment corrected, N4 the definers scanned too"). Diff vs `5c59524`:
  `analysis/pipeline.py` (+34/−) and `tests/test_pipeline_escalation_fence.py` only. Worktree clean.
* The closure-2 proof driver COMPLETED under the host lock (`discovery_reports/train12-logs/p22fence/closure2/MASTER.log`,
  `EXIT=done`): mutants E10 / E11 / E8b / N4m all KILLED (`mutants.log`); guards EXIT=0; conformance
  EXIT=0; no-parser replay (685 shas, 656 replayed, 0 regressions, 0 payload changes, `replay-noparser-closure.md`);
  chunk-01 replay (`--parser chase`, identical, EXIT=0); privacy scan `b23cb50..HEAD` residue_sites 0
  (`privacy.log`); message scan EXIT=0.
* **NOT done:** the W3 section `# §P22FENCE-CLOSURE-2 — …` (the log has FENCE, FENCE-2, FENCE-CLOSURE only)
  and the final report. The agent died while re-reading the re-review before writing the section.
* **Lock incident (recorded here; add it to the transition log at the 2.2 closure):** the driver's lock
  release failed with `PermissionError` (OneDrive), leaving an EMPTY orphaned `HARNESS.lock` (no holder.txt).
  Ocean verified no python process was alive and removed it at 10:35. Rule for every future card: acquire
  only with `mkdir`, write `holder.txt` inside, release only your own (holder must name you), retry the
  release on `PermissionError`, unbounded waits.
* **Next steps for F:** (a) resume (or re-dispatch) the F implementer to append the W3 closure-2 section citing
  the logs above and commit; (b) dispatch the F re-review-2 to the SAME re-reviewer (worktree
  `.claude/worktrees/rerev22-fence`, currently detached at `5c59524` — move it to the new tip) using the
  re-review brief pattern (§5); it must confirm N1 (message reverted, attribute kept — the webapp's
  `test_the_declared_refusal_still_reaches_the_user` holds again), N2 (rule B5 + no-decorator / single-call-site
  pins; mutants E10/E11/E8b), N4 (guard over extract/reconcile); (c) commit the re-review on train12;
  (d) compose F onto train12 (`git merge --no-ff wave22-fence`), resolving the `W3_TRACKA_LOG.md` conflict at
  the shared append point BYTE-EXACTLY (ours + theirs[len(base):]; verify `grep -c "^<<<<<<<\|^>>>>>>>"` is 0
  on the committed blob and the section count is right); (e) apply Ocean item 2 (§2) with its test; (f) record
  the composition in `BATCH9_TRANSITION.md` §7.

### 3.2 Cell T (worktree `.claude/worktrees/mt22-truthtable`, branch `wave22-truthtable`)
* Base: **`b7af37b`** = train12 `0d2c99c` (K+C+H composed) + `wave22-fence` `5c59524` merged (the integration
  base; W3 11 sections; `issues.append(` reconcile.py 6 / pipeline.py 0). NOTE: T's base carries F at
  `5c59524`, not F's closure-2 `1c09faa`; the closure-2 diff is confined to `analysis/pipeline.py` and
  `tests/test_pipeline_escalation_fence.py`, neither of which T owns, so T composes cleanly after F.
* Committed: **`1901201`** — the failing tests written first: `tests/test_unresolved_taxonomy.py` (L0–L6, drift
  guards, precedence pin), `tests/test_refused_outcome.py` (the `refused` outcome, the exact transition matrix,
  the raw-denominator refusal), `tests/test_two_denominators.py` (both denominators, the disjoint sum beside
  the never-summed diagnostic labels), `tests/test_research_mode.py` (door refusals, mode-only trigger, the
  synthetic end-to-end proof with the fake worker).
* **UNCOMMITTED (dirty worktree — keep it, it is T's partial implementation):** `ocr/escalation.py`
  (+`OPERATOR_FORCED_PADDLE = "operator_forced_paddle"` in `ALL_TRIGGERS` and `TRIGGER_REPORT_PRIORITY`),
  `telemetry/diagnostics.py` (`DIAGNOSTICS_VERSION` 4 → 5 with the changelog entry; `RETIRED_RECON_ISSUE_CODES`
  = {`recon:escalation_extraction_failed`}; `LIVE_RECON_ISSUE_ANCHORS`, 6 at v5), `telemetry/record.py`
  (`OUTCOME_CLASSES` + `refused`; `DEFERRED_REASONS` + `research_skipped_not_in_population`,
  `research_refused_holdout`; `REFUSED_REASONS` closed tuple, reserved; `EXTRACTION_TRIGGERS` +
  `operator_forced_paddle`; `source_section` edits in progress). `git -C .claude/worktrees/mt22-truthtable diff`
  shows exactly this.
* **Still to deliver (the card's items 1–10):** `telemetry/unresolved_taxonomy.py` (L0–L6, precedence, drift
  guards, `UNRESOLVED_TAXONOMY_VERSION`); `refused` through `classify_outcome` and `discovery/compare.py`
  (unranked vs failed/withheld/review; ANY exit from validated = regression; the transition matrix; refusal of
  differing raw denominators); the two denominators (`raw_coverage` in the runner; `tools/truth_report.py`
  joins the sealed store — a `tools/` instrument, allowed to read `SEALED_TRUTH_DIR`); the classifier wired as
  a recorded fact (never passed to `analyze_document`; payload identity proven); `evidence_sha256` on native
  rows (K's one-liner in `telemetry/record.py::source_section`: `"evidence_sha256": (... if evidence is not
  None else None) or getattr(doc, "native_evidence_sha256", None)`); funnel + technical-telemetry columns
  appended to `ROW_FIELDS` (no cost/price/rate/billing field — grep test); the research mode
  `--research-paddle --population --research-partition` through the router (`RESEARCH_TRIGGERS` constant the
  one place the name is spelled outside `ocr/escalation.py`; both literals required up front; a production
  `--data-dir` refused; a holdout sha from `MANIFEST_DIGEST.txt` refused before any read;
  `--research-partition` passed to `provenance.py` and `research_partition=` to `cached_ocr`; the D4 AST
  tripwire still passes); the geometry seam behind `reconstruction_mode` (byte-identity when `off`); the
  diagnostics count guard update (7 → 6, anchor kept, v5 entry in `W3_2_TAXONOMY.md` §11); the OQ2 scan roots
  check. Then: mutation table M1–M17, the synthetic research-mode proof, the union cohort replay at base and
  closure (chunked `--parser` replays; offline partition byte-identical), the proof floor, the run-of-record
  measurement (disjoint classification sums 755 / 3,380 with validated exceptions by sha16 and kind; the
  diagnostic-label table; funnel columns), the W3 section `# §P22TRUTHTABLE — …`, the report.
* **Next steps for T:** resume (or re-dispatch) the T implementer with this exact state (base, commit, dirty
  files listed above, the card, the discipline in §5); then independent adversarial review (brief pattern
  §5; worktree `rev22-truthtable`), closure, re-review, compose T onto train12 (same byte-exact W3 rule).

### 3.3 After T composes — the 2.2 closure sequence (none of it started)
1. Composed-tree floor on train12 with the real `.env` present: full suite (K's hermeticity keeps it green
   with `PADDLE_*` set); guards; conformance; the diagnostics guard (fails until T composes — expected in the
   interim); `python -c "import analysis.pipeline, layout.document_class, evidence.native, tools.holdout.digest"`.
2. Cold run at the composed tree → `.claude/recovery/webapp_data_train12_cold` (OCR schema 3 + analysis
   stage 18 + raster 2 → both caches rebuild; ~75+ min), compared against the Phase 2.1 run of record with
   `--fail-on-regression`: expected 2,625 → 2,625, newly validated 0, OCR-fed validated 0, no customer page
   leaves the machine.
3. Privacy scan + message scan over `b23cb50..train12` (`tools/privacy_scan_branch.py --rows <run>/rows.csv
   --run <run> --data-dir .claude/recovery/webapp_data_train11_cold --base b23cb50 --ref <tip>`) → residue 0
   or adjudicated.
4. CI green (record the run id); durable docs: `BATCH9_TRANSITION.md` §7 closure entry (include the lock
   incidents and the mkdir-only rule), `PHASE2_STATE.md`, `PROJECT_STATUS.md`, the umbrella card's §Closure,
   the reviews committed; memory note updated; worktree clean.
5. Check every line of the umbrella's **Completion criteria** (`PHASE2-2-TRUTH.md` §"Completion criteria").
   All hold → Phase 2.3 opens WITHOUT asking (merge train12 to main only at a composed, proven train, as in
   Phase 2.1 — see the transition log for the exact ceremony).

---

## 4. Phase 2.3 and beyond — what is LEFT (nothing written yet)

Write `docs/agent-handoffs/PHASE2-3-WAVE.md` from plan §G.2.3 / §H, then cells. Content it must carry:
* Populations in order (§H.1): **CTRL** (a validated control slice — Paddle must not move it), **U755** (the
  755 unresolved of the run of record), **SLICE** (Gustavo's slice-1 adjudicated set), all through Paddle
  on the Vast Secure Cloud instance in **research mode** (T's `--research-paddle --population
  --research-partition`, both opt-in literals in the run's environment only, research partitions never
  selectable by `run_of_record`). Holdout shas are refused by construction.
* E-gate v2, extractor agreement, truth table v2, stage-by-stage fallout (§H.3), "Paddle helped" defined
  (§H.6) — **+0 official**: nothing from Paddle is admitted to the floor in 2.3; the wave produces EVIDENCE.
* Config A/B: PP-OCRv5 baseline vs PP-OCRv6 (R5, separate pins) and the orientation classifiers as a second
  pinned config (R6). Never silently switch.
* R10 Phase 1 hygiene ceremony cell: the six `bank_repairs` rewrites.
* The classifier-precision cycle (C re-review R-1..R-4; K re-review N-1/N-2 latent MINORs; the 461/431
  validated-exception residue).
* The lock rule (mkdir-only, own-holder release, retry on PermissionError, unbounded waits) and the
  spend-limit recovery rule (§5).
* Cost is out of scope: no rate, no cost columns, no billing gates anywhere.

Then 2.4 (plan §G.2.4 / §I: `layout/` LayoutModel, structurer v2, archetypes, holdout pass; STOP-and-report if
geometry does not generalise), 2.5 (§G.2.5: reconstruction v2, measured triggers, Paddle production admission,
deployment class R8), 2.6 (§G.2.6 / §K: Unlimited on the separate computer; go/no-go on the residual Class-A
population; STOP before any new external transmission), 2.7 (§G.2.7: routing frozen from evidence, both
denominators, runbooks, the Phase 3 seam, `phase2-final`).

---

## 5. How Ocean works here (the operating discipline you must keep)

* **Every milestone**: bounded card → implementation cell (agent, model per `ORCHESTRATION-MODEL-POLICY.md`)
  → tests → mutation/tripwire tables → corpus measurement → independent adversarial review (fresh detached
  worktree at the cell tip; review file under `docs/moneythumb-replacement/reviews/`; Ocean commits reviews on
  the train) → the cell reproduces every finding before closing it → re-review by an independent re-reviewer
  → Ocean composes onto the train (`--no-ff`), resolves the W3 append-point conflict byte-exactly, records the
  composition in `BATCH9_TRANSITION.md` §7 → composed-tree proof → CI → durable docs. Cells never merge or
  push; Ocean alone composes. Never pass a RED gate.
* **Cell prompts** carry: read order; disjoint FILE ownership (a file outside ownership → STOP and report);
  two commit trailers (`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01VTtXwK2nJi8PvirXUsR8eJ` — use YOUR session's line);
  commit messages in classes not instances (the message scan rejects archive tokens); host lock protocol;
  no customer data; synthetic fixtures ≥ 2031; one heavy proof at a time; detached heavy runs with a durable
  log ending in `EXIT=<code>`; W3 section with its own heading; the report contract (population · root cause ·
  solution · newly validated · ladder movement · preserved · regressions · evidence tables · commits · proof
  exits · privacy count · risks last).
* **Review / re-review briefs**: the attack list from the umbrella; reproduce every claim; apply every mutant;
  ownership check; privacy + message scans over `b23cb50..tip`; numbers re-derived from logs ("a number with
  no log does not exist"); verdict BLOCK / APPROVE WITH FINDINGS / APPROVE.
* **Host**: Windows 11, Python 3.14 locally, CI pins 3.12; OneDrive `PermissionError`s are transient — retry;
  instruments via file tools, never heredocs; archive (`Bank Statements/`) and caches READ-ONLY; scope greps to
  code/docs dirs (a whole-repo grep over the corpus folder times out); never a bare `git stash` in a worktree.
* **API spend-limit terminations** (six so far): agents die mid-task; detached runners survive; pollers die.
  Recovery = read the disk (branch tips, worktree status, `discovery_reports/train12-logs/**/MASTER.log`,
  W3 section counts), then resume the same agent via a message with the exact on-disk facts, or re-dispatch
  with them. Never rerun a completed proof; never restart a cell.
* **Gustavo**: adjudicates truth (slice-1 packets await him), owns cost, is the final authority; he issued the
  full authorization and does not need per-milestone approval on GREEN. Report the recovered state
  concisely, then resume.

---

## 6. Quick verification commands (run from the repo root before doing anything)

```
git log --oneline -3 train12
for b in wave22-identity wave22-classify wave22-holdout wave22-fence wave22-truthtable; do echo "$b $(git rev-parse --short $b)"; done
git worktree list | grep -i "mt22\|rev22"
git -C .claude/worktrees/mt22-truthtable status --short          # expect: M ocr/escalation.py, M telemetry/diagnostics.py, M telemetry/record.py
git -C .claude/worktrees/mt22-fence status --short                # expect: clean at 1c09faa
ls discovery_reports/train12-logs/HARNESS.lock                    # expect: absent (no harness running)
grep -c "^# §P22" docs/moneythumb-replacement/W3_TRACKA_LOG.md    # train12: 8 (K 3 · C 2 · H 3), wave22-fence: 3 (FENCE, FENCE-2, FENCE-CLOSURE), wave22-truthtable: 11 (train12's 8 + F's 3)
tail -3 discovery_reports/train12-logs/p22fence/closure2/MASTER.log
```

Expected at handoff: `train12` = `0f83190`; K `bc6e7cb`; C `4a5f381`; H `3464eb4`; F `1c09faa`; T `1901201` + the
three dirty files; lock absent; no python runners alive.
