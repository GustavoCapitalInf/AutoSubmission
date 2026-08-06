# Wave 1 Execution Brief

Author: Ocean. Date: 2026-08-06. Status: proposed — awaiting approval; nothing implemented.
Baseline: `main` at `515369d` (Wave 0 merged: corpus gate, doc fixes, D-2a hardening).
Candidates evaluated: H-2, R-1, O-1, D-1. Nothing beyond these four.

CI note: the first remote corpus-gate run failed before acquiring a hosted runner —
infrastructure, not a workflow defect. The workflow is frozen unless a rerun reaches
the job steps and fails there. The LOCAL gate (`python corpus_gate.py`, GREEN in
4m41s at `515369d`) is the merge authority for all of Wave 1.

---

## 0. Ranking

| Rank | Task | Why it ranks here |
|---|---|---|
| 1 | **R-1 hardcode purge** | Highest production risk: memorized constants (customer names, exact dates/amounts, hardcoded years) silently misfire on the next customer's statement and undermine the honesty of "validated." Blocks the 4,000-statement discovery corpus and any certification claim. Benefits every bank by making the validation evidence real. Highest token cost — the centerpiece of the wave. |
| 2 | **H-2 comparison harness** | Near-zero regression risk (read-only tooling, new directory), small size, and it directly advances the replacement goal: Milestone 2 (parallel validation) is impossible without it. Executes FIRST despite ranking second because it baselines the benchmark comparisons that R-1 will change — KLR and Field Trucking are both benchmark statements AND R-1-affected parsers (verified: all 6 benchmark sets map to corpus PDFs). |
| 3 | **D-1 durable persistence** | Largest remaining serving-layer gap (R-20/R-21): results and analyst review decisions still vanish on restart. Fully independent of `analysis/` — zero financial regression surface. Prerequisite for storing 4,000-statement discovery results and for D-2b auth in a later wave. |
| 4 | **O-1 unified preflight** | Valuable (dedup, triage, unknown-bank intake signals) but its outputs want somewhere durable (D-1) and its consumer integration touches `webapp/worker.py`, which D-1 also rewires — so it sequences after D-1. Least urgent of the four; nothing regresses by doing it last. |

Unknown-bank support: O-1 contributes intake classification and H-2 contributes the
evidence workflow, but true unknown-bank parsing (P2-1) is deliberately NOT in this
wave — no candidate should be stretched toward it.

## 1. Agent allocation

**Two implementation agents, strictly sequential within each:**

- **Agent A (analysis/benchmark track):** H-2 → R-1. Same agent on purpose: H-2's
  discrepancy reports are direct evidence for R-1's rulings on `scanned_small_bank`
  and `community_section`, and the two tasks share fixture knowledge.
- **Agent B (serving track):** D-1 → O-1. Sequential because both touch
  `webapp/worker.py`; O-1 rebases on D-1's worker changes and hands its duplicate-hash
  into D-1's store.

The tracks share no files (verified against the allowlists below) and run in parallel.
Never more than two agents active.

---

## 2. Task cards

### H-2 — MoneyThumb comparison harness

- **Objective:** a re-runnable harness that, for each benchmark set, normalizes and
  compares four sources — original statement evidence, our pipeline output, MoneyThumb
  output, and the independently audited expectations (audit CSVs) where available —
  and classifies every compared field into exactly one of:
  `BOTH_MATCH_EXPECTED | OUR_SYSTEM_CORRECT | MONEYTHUMB_CORRECT | BOTH_INCORRECT |
  DIFFERENT_DEFINITION | SOURCE_CONTRADICTION | INSUFFICIENT_EVIDENCE | UNRESOLVED`.
  MoneyThumb is never automatic ground truth; a difference with no audited expectation
  and no source evidence lands in INSUFFICIENT_EVIDENCE or UNRESOLVED, never in a
  "correct" bucket.
- **Scope:**
  - Source-mapping manifest: benchmark set → corpus PDF(s). Verified mapping:
    `bmo_jan` → `Misc/BMO_Statement_January_2026 Final-1-2 (1).pdf`; `chase_dec` →
    `Chase/Chase Salomon Dec 2025.pdf`; `chase_jan_feb_mar` → Salomon January /
    February / March 2026 (package); `field_trucking_nov`, `klr_may`, `wmb_may` →
    their Misc PDFs. `klr_may` is recorded as a MoneyThumb no-result (202 stub) —
    an automatic capability finding, not a field comparison.
  - MoneyThumb response.json reader (schema per FIELD_MAPPING.md); our-side runner
    reuses the pipeline offline (native text + the committed OCR artifacts from
    `tests/corpus_cache/` — KLR's artifact already exists; no live OCR, no Gemini).
  - Field normalizer using FIELD_MAPPING verdicts (HAVE fields compared; IGNORE
    fields skipped by design and listed as skipped; known MT defects — e.g. "Total
    Revenue" = net cash flow — pre-classified DIFFERENT_DEFINITION/BOTH-side rulings
    with citations).
  - Package comparison for `chase_jan_feb_mar` against `/package_analysis` semantics.
  - Report emitter: per-set and rollup, machine-readable (JSON/CSV) + human summary.
    Every non-`BOTH_MATCH_EXPECTED` row carries evidence pointers. UNRESOLVED rows
    queue for Ocean ruling; no code changes may be made in response to a discrepancy
    without that ruling.
- **Sensitive-content rule:** `moneythumbResults/` stays untracked and read-only; the
  benchmark PDFs' full ledgers and holder identities are not committed. Committed
  artifacts = harness code, the mapping manifest (paths + hashes only), and tests
  using synthetic fixtures. Real comparison reports write to a gitignored output
  directory; account numbers in any report are masked last-4.
- **File allowlist:** new `benchmark/` package; new `tests/test_benchmark_harness.py`
  (synthetic fixtures only); `.gitignore` (add report output dir); `README.md`
  (run instructions — Agent A owns README this wave).
- **Protected:** everything else — `analysis/`, `ocr/`, `webapp/`, corpus PDFs, audit
  CSVs, `moneythumbResults/` (read-only), the corpus gate.
- **Dependencies:** none. First task to start.
- **Acceptance:** one command produces classified reports for all 6 sets (5 compared +
  klr_may capability finding); runs fully offline; every compared field traceable to
  a FIELD_MAPPING verdict; zero modifications under `moneythumbResults/`; corpus gate
  untouched and green.
- **Required tests:** classifier unit tests (all 8 outcomes reachable, precedence
  documented); normalizer tests on synthetic MT payloads; masking test on report
  output; a smoke test that the manifest's corpus paths + hashes resolve.
- **Known risks:** LOW. Read-only. Main risk is silent comparison-coverage gaps —
  mitigated by requiring every MT field to appear as compared/skipped-by-verdict in
  the rollup (no silent omissions).
- **Size:** small-medium (~600–900 LOC + tests; one agent-session).
- **Parallel:** yes — with D-1 (zero file overlap).
- **Merge order:** first of the wave.

### R-1 — statement-specific hardcode purge

- **Objective:** eliminate every statement-, customer-, date-, amount-, and
  year-specific constant from parsers and repairs. A repair survives only as a
  generic, evidence-gated, regression-tested rule; anything that cannot be defensibly
  generalized converts the affected result to explicit review/withholding. No
  fabricated correctness. Corpus gate green throughout.
- **Scope — the audited inventory (each item = inventory entry → ruling → remediation
  → fixture test → gate re-run):**
  1. `analysis/scanned_small_bank.py:300-321` — repair keyed to literal date
     "2026-06-18" + "Check 1944" + amount −4500.00→−1500.00.
  2. `analysis/scanned_small_bank.py:214-216, 338` — literal holders "THE GRANITE
     GIRLS, LLC", "KLR ENTERPRISES" as parser gates.
  3. `analysis/scanned_small_bank.py:418-419` — `len(txns) < 20` magic threshold.
  4. `analysis/community_section.py:29` — literal "GREEN CONVERGENCE" / "FIELD
     TRUCKING LLC" scrub list.
  5. `analysis/community_section.py:226` — Dakota West gate on literal account
     `35127380`.
  6. `analysis/bank_repairs.py:115-134` — Chase repair firing only on exactly
     −1000.00 with a 1000–2000 Remote Online Deposit.
  7. `analysis/rbc.py:47-64` — counterparties "FUNDIFI CANADA", "2313833 ONTARIO"
     inside sign heuristics; `:235-241, 288-291` — French parser Dec/Jan-only with
     hardcoded period start and default years (2025, 2026); `:246` mojibake regex.
  8. `analysis/td_can.py:153-174` — merchant-name sign lists (DANNY, PIZZ, PHO,
     FRESHCO, CASH 4 YOU, LIGHTSPEED, CANACAP CLN).
  9. `analysis/wells.py:20-22` — `_infer_year` defaulting to 2026.
  10. `analysis/wilson_muir.py:152` — `days_in_period=30` guess.
  11. Mojibake-encoded regexes: `scanned_small_bank.py:146, 211` (+ rbc above) —
      match real characters after a normalization step, not corpus double-encoding.
  12. Registry counterparty entries (R-6): `classification_registry.py:143`
      ("11-101 Signal R" as operating source), `:42` ("3329001101"), `:33-34`
      ("MC 844 662 3467"). **Each requires an individual Ocean ruling** — these are
      LEDGER-owned data; Agent A proposes, Ocean disposes.
  - Remediation menu, in preference order: (a) generalize into an evidence-gated rule
    (e.g. year inference from statement period metadata; sign resolution from printed
    balances via the existing solver; scrub rules driven by structural markers, not
    names); (b) move genuine counterparty knowledge into the registry WITH fixture
    tests (per the documented contract); (c) fail closed — the statement becomes
    review/withheld, with an evidence dossier.
  - **Out of scope:** `pipeline.py` orchestrator cleanup (that is R-8), parser
    registry/dispatch (P1-1), any change to protected financial modules.
- **File allowlist:** `analysis/scanned_small_bank.py`, `analysis/community_section.py`,
  `analysis/bank_repairs.py`, `analysis/rbc.py`, `analysis/td_can.py`,
  `analysis/wells.py`, `analysis/wilson_muir.py`; `tests/test_analysis.py` + new test
  modules/fixtures; `docs/moneythumb-replacement/R1_HARDCODE_LOG.md` (new — the
  inventory-and-ruling record); `analysis/classification_registry.py` ONLY per-entry
  after Ocean approval; `docs/adb-audit-results.csv`,
  `docs/balance-metrics-audit-results.csv` and `corpus_gate.py` expected-count
  constants ONLY via an approved re-baseline (see acceptance).
- **Protected:** `analysis/adb.py`, `reconcile.py`, `metrics.py`,
  `transaction_classifier.py` (code), `serialization.py`, `analysis/pipeline.py`,
  all other parsers, `ocr/`, `webapp/`, corpus PDFs, `moneythumbResults/`.
- **Dependencies:** corpus gate (done, Wave 0). H-2 baseline report for the KLR /
  Field Trucking / BMO comparisons SHOULD exist first (same agent guarantees it).
- **Acceptance:**
  - Zero literal customer names, account numbers, single dates, exact amounts, or
    hardcoded years remain in any parser/repair (enforced by a new guard test that
    greps the parser modules for the removed literals and fails on reintroduction).
  - Every inventory item has a logged ruling (generalized / registry / fail-closed)
    with evidence.
  - Corpus gate GREEN. Target: zero outcome changes. If a statement legitimately
    changes status (e.g. a memorized-constant pass becomes review), that is an
    Ocean-approved documented re-baseline: audit scripts re-run deliberately, CSVs
    regenerated, gate constants updated, delta explained per statement in the log.
    An unapproved red gate is a stop-the-line event, not a re-baseline.
  - H-2 re-run afterwards; comparison deltas for affected statements recorded.
- **Required tests:** per-remediation fixture tests (positive + negative: the
  generalized rule fires on structural evidence, not on the memorized instance);
  the literal-reintroduction guard test; full suite; corpus gate.
- **Known risks:** MODERATE-HIGH (highest of the wave). Behavior changes on validated
  corpus statements are possible by design; the gate catches every drift field-by-
  field. Canadian sign-list generalization (item 8) is the hardest — printed-balance
  solving must carry the weight the merchant lists carried; where it cannot, fail
  closed rather than guess.
- **Size:** LARGE (~12 discrete remediations × ruling + tests + gate re-runs;
  multi-session; the wave's main token cost).
- **Parallel:** with D-1 yes (disjoint files). Never with another `analysis/` task.
- **Merge order:** after H-2 and after D-1 (see §3 rationale).

### O-1 — unified document preflight

- **Objective:** one reusable pre-parser inspection layer producing a
  `DocumentProfile` for every upload, consumed by a single intake ladder — replacing
  the drifted duplicate preflights in `ocr/pipeline.py:38-52` and
  `webapp/worker.py:22-29`. Inspection only: NO parser logic is rewritten.
- **Scope:** new `ocr/inspect.py` with `DocumentProfile`: PDF validity (header,
  parseable xref), encryption flag, page count, content SHA-256 (definition shared
  with D-1: uppercase hex of raw bytes, identical to the corpus-audit convention),
  per-page native-text availability, digital/scanned/mixed classification, likely-OCR
  flag, malformed-page list, likely account count (marker heuristics only — counting
  "Account Number/Type" blocks; advisory field, consumed by nothing yet), and basic
  layout signals (table markers, statement-period markers, "Page N of M" presence —
  reusing the existing integrity scan patterns, not duplicating them). Integrate as
  the single ladder entry in `ocr/pipeline.py`; `webapp/worker.py` consumes it
  (deleting its private ladder); duplicate-hash surfaces to D-1's store and the
  upload response.
- **File allowlist:** new `ocr/inspect.py`; `ocr/pipeline.py`; `webapp/worker.py`
  (consumer rewiring only, after D-1 merges); `webapp/app.py` (only to surface
  duplicate/profile fields in upload/status responses, minimal); `parse.py` (adopt
  the ladder); new `tests/test_inspect.py`; `tests/test_pipeline.py`,
  `tests/test_webapp_worker.py` (behavior-parity updates).
- **Protected:** all `analysis/` (every parser — "do not rewrite parser logic" is
  absolute), `ocr/native_text.py` internals (called, not modified),
  `ocr/ocr_client.py`, `webapp/jobs.py`/storage (D-1's, consumed via its API), audit
  assets, corpus gate.
- **Dependencies:** D-1 merged (shared `webapp/worker.py`; hash storage target).
  Hash-definition handshake with D-1 agreed before D-1 finishes.
- **Acceptance:** exactly one preflight ladder in the codebase; behavior parity on
  the corpus — every corpus PDF resolves to the same source path (native/tesseract/
  visual) as before, proven by a parity test over the 109 documents using recorded
  expectations; corpus gate GREEN byte-identical (pure-refactor standard); duplicate
  upload of identical bytes is flagged in the upload response; encrypted/invalid PDFs
  rejected with a JSON error instead of a worker exception.
- **Required tests:** profile unit tests per signal (synthetic PDFs: encrypted,
  malformed, mixed); ladder parity test; duplicate-flag test; existing suites green.
- **Known risks:** MODERATE. Touching the intake path risks changing which extractor
  serves a document — the parity test is the specific control. The account-count and
  layout signals must stay advisory (consumed by nothing) to keep regression surface
  at zero.
- **Size:** medium (~300–500 LOC + tests).
- **Parallel:** no — sequenced after D-1 (shared worker file). Runs while Agent A is
  mid-R-1, which is fine (no shared files with R-1).
- **Merge order:** last of the wave.

### D-1 — durable persistence

- **Objective:** the smallest production-appropriate persistence layer: jobs and
  results survive restart; analyst review decisions are recorded with actor,
  timestamp, and prior value; packages become durable records. No auth, no external
  queue, no cloud, no multi-tenancy (all explicitly out of scope — D-2b/Wave 2+).
- **Scope:** SQLite via stdlib `sqlite3` (no new dependency; single-writer matches
  the current one-worker model; Postgres is a Wave 3+ swap behind the same
  interface). New `webapp/storage.py`: schema + data-access for
  `documents` (id, content sha256 — O-1's definition — filename, size, page count,
  uploaded_at), `jobs` (status, stage, parse settings, error, timings, result JSON =
  the existing `report_to_dict` payload verbatim, stored unmasked with masking still
  applied at serving), `packages` + `package_members` (durable id, caller reference,
  member jobs), `review_decisions` (append-only: job, source_location, decision,
  actor — free-text until auth exists — timestamp, prior state), `audit_log`
  (append-only event rows: upload/status-change/review/export). `webapp/jobs.py`
  becomes a thin facade over the store (PDF bytes on disk under a data dir keyed by
  content hash — not in SQLite, not in RAM after processing); `webapp/app.py` wiring:
  queue re-hydration on startup (queued/processing jobs resume or mark interrupted),
  package endpoints accept/mint durable package ids (comma-id form kept working),
  review endpoint writes decision rows; `webapp/worker.py` persists status
  transitions. Migration/back-compat evaluation (required by the brief): there is no
  existing durable data — the in-memory store IS the migration story, so v1 ships a
  versioned schema (`schema_version` table + forward-only migration hook) and no data
  importer; the serialized analysis payload is stored as opaque JSON so `analysis/`
  contract changes do not require schema migrations.
- **File allowlist:** new `webapp/storage.py`; `webapp/jobs.py`; `webapp/app.py`;
  `webapp/worker.py`; new `tests/test_webapp_storage.py`; `tests/test_webapp_jobs.py`,
  `tests/test_webapp_app.py`, `tests/test_webapp_worker.py` (updates); `.gitignore`
  (data dir); `run.ps1` (data-dir env, only if needed).
- **Protected:** all `analysis/` (the stored payload is consumed verbatim — zero
  serialization changes), all `ocr/`, corpus/audit assets, D-2a's security behaviors
  (masking/limits/escaping tests must keep passing unmodified).
- **Dependencies:** none to start. Coordinates one definition with O-1 (content
  hash) before completion.
- **Acceptance:** kill and restart the server mid-queue → completed results are
  served, queued jobs resume or are explicitly marked interrupted (never silently
  lost); review decisions survive restart and their full history is queryable;
  package by durable id reproduces the same payload after restart; a processed job
  no longer holds `pdf_bytes` in RAM; all D-2a security tests pass unchanged; full
  suite green; corpus gate green (it does not touch webapp state, so byte-identical).
- **Required tests:** restart-simulation tests (store torn down and reopened);
  review-history append-only test; package durability test; RAM-release test;
  existing webapp suites updated only where the in-memory assumption was the thing
  under test (documented deltas).
- **Known risks:** MODERATE. `webapp/app.py` is 1300+ lines and D-2a just changed it
  — Agent B must branch from post-Wave-0 `main` (515369d), not from any older tree.
  Concurrency stays single-writer (the existing one-worker queue), so no locking
  redesign; that constraint is stated in code.
- **Size:** medium-large (~500–800 LOC + test updates).
- **Parallel:** yes — with H-2 and with R-1 (zero file overlap with either).
- **Merge order:** second of the wave (after H-2, before R-1's merge — see §3).

---

## 3. Cross-task file matrix and sequencing

| | H-2 | R-1 | D-1 | O-1 |
|---|---|---|---|---|
| H-2 | — | none shared | none shared | none shared |
| R-1 | — | — | none shared | none shared |
| D-1 | — | — | — | **webapp/worker.py, webapp/app.py, .gitignore** |
| O-1 | — | — | sequenced after | — |

(H-2 and D-1 both may touch `.gitignore` — one-line additions; Agent B rebases
trivially. No other intersections.)

- **Execution order:** Agent A: H-2 → R-1. Agent B: D-1 → O-1. Tracks in parallel.
- **Merge order:** **H-2 → D-1 → R-1 → O-1.**
  - H-2 first: zero-risk, and its baseline must predate R-1's parser changes.
  - D-1 second: it will finish before R-1 (smaller) and shares nothing with it.
  - R-1 third: merges only when its full inventory is resolved and the gate is green
    (or Ocean-approved re-baselined) — do not merge partial purges.
  - O-1 last: rebases on D-1's worker, proven by the parity test, gate byte-identical.
- **Standing criteria for every PR (unchanged):** full suite green; LOCAL corpus gate
  green attached to the PR; no new statement-specific constants; no protected-module
  diffs; Ocean review for R-1 rulings, registry entries, and both re-baseline events
  (should any occur).

## 4. Worktree plan

Reuse; do not create new checkouts (each carries the 109-PDF corpus):

- **Agent A** → `.claude/worktrees/mt-benchmark` — fast-forward to `main` (515369d),
  branch `wave1-benchmark-parsers` (H-2 commits, then R-1 commits).
- **Agent B** → `.claude/worktrees/mt-universal-extraction` — switch to a new branch
  `wave1-serving` off `main` (its `wave0-d2a` branch is merged; the misleading
  worktree name is cosmetic).
- Delete: `wave0-integration` worktree + `wave0-integration`/`wave0-d2a` branches
  (merged).
- `mt-lead` remains Ocean's. `mt-ledger` / `mt-underwriting` stay idle (no Wave 1
  owner).

## 5. Final recommendations

1. **First task:** H-2 (Agent A) — smallest, zero-risk, and it must baseline the
   benchmark comparisons before R-1 changes them. (R-1 remains the wave's top
   *priority*; H-2 is first in *execution*.)
2. **Second task:** D-1 (Agent B), started in parallel with H-2.
3. **Minimum implementation agents:** 2 (Agent A: H-2→R-1; Agent B: D-1→O-1).
4. **Worktrees to reuse:** `mt-benchmark` (Agent A), `mt-universal-extraction`
   (Agent B); delete `wave0-integration`.
5. **Execution order:** H-2 ∥ D-1 → R-1 (Agent A) ∥ O-1 (Agent B, after D-1 merges).
6. **Merge order:** H-2 → D-1 → R-1 → O-1.
7. **Before the 4,000-statement discovery corpus:** R-1 complete (memorized constants
   would silently misfire at scale — hard blocker); H-2 operational (the discrepancy-
   classification workflow is how discovery results get adjudicated); D-1 complete
   (results at that scale need durable storage); O-1 complete (dedup + digital/
   scanned triage of 4,000 documents is the intake filter). In short: all four —
   which is exactly why Wave 1 is scoped to them. Telemetry (H-3) is the one known
   gap deliberately deferred; discovery throughput analysis will be manual until it
   lands.
8. **Remote corpus-gate green before Wave 1 starts?** No. The failure never reached
   the job steps (runner acquisition — infrastructure). The gate is proven and
   enforced locally, and the local run is the merge authority. Condition: every Wave
   1 PR attaches a green local gate run, and if the remote runner problem persists to
   the end of Wave 1, resolving it becomes a Wave 2 entry gate so R-1's merged state
   is continuously protected without depending on developer discipline.
