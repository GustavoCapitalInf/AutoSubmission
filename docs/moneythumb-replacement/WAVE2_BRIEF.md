# Wave 2 Execution Brief — Discovery-Ready Platform

Author: Ocean (Lead Architect). Date: 2026-08-06.
Status: **proposed — awaiting approval; nothing implemented, no agents launched.**
Baseline: `main` at `da63ec2` (Wave 1 merged: H-2, D-1, R-1, O-1).
All delegated agents run on Claude Opus 5 (`CLAUDE_CODE_SUBAGENT_MODEL=opus`, verified).

---

## 0. The milestone question: is the 4,000-statement discovery corpus next?

**Yes — as this wave's capstone, not its first act.**

The discovery corpus is the highest-value *objective* on the board. G1 ("coverage is
corpus-shaped, not market-shaped") is the largest gap in PRODUCTION_GAPS.md, Milestone 2
(parallel validation at scale) cannot happen without real-world statement flow, and all
four prerequisites named in WAVE1_BRIEF §5.7 — R-1, H-2, D-1, O-1 — are now merged.
Nothing blocks *starting* it.

But running 4,000 unknown statements through today's platform would waste most of the
information the run exists to produce:

1. **No telemetry (H-3).** There is no per-statement record of path taken
   (native/tesseract/visual), parser used, fallback reason, timing, or cost. The single
   most important discovery output — the deterministic-coverage rate and its failure
   taxonomy — would have to be hand-mined from logs. WAVE1_BRIEF already flagged this
   as the one deliberately deferred gap.
2. **No artifact cache (D-3).** Discovery is an iterative activity: parse, fix
   intake-classification issues, re-run. Without the content-addressed cache
   (sha256 → OCR markdown → extraction), every iteration over the scanned fraction
   re-pays ~23 s/page OCR. D-3 is also the last substantive P0 item.
3. **Dispatch is still an ordered substring or-chain (R-3/R-4).** 4,000 foreign
   statements is exactly the input that makes a mis-claiming parser likely (a parser's
   sniff string appearing in another bank's boilerplate). There is no detection
   scoring, no ambiguity handling, and six parsers have no direct tests at all. The
   reconciliation gate catches most bad parses, but a wrong-parser claim that happens
   to reconcile is silent corruption of discovery statistics — and of any real result.
4. **The remote corpus gate is broken.** The only GitHub Actions run failed at
   hosted-runner acquisition ("not acquired by Runner of type hosted", 15 min, run
   31122891522) and never reached the job steps. WAVE1_BRIEF §5.8 made resolving this
   a Wave 2 entry gate: R-1's merged state is currently protected only by local
   discipline.

The platform work that fixes 1–3 is precisely the Wave 2 already sketched in
MERGE_PLAN §3 (R-2 → R-3 → R-4, D-3, O-3, H-3). So the milestone is:

> **Make the platform able to run, measure, and cheaply re-run the discovery corpus —
> then run it.** Platform-level improvements only; zero individual-parser feature work.

Alternatives considered and rejected as *the* milestone:
- **Discovery-first, platform-later:** produces an expensive, weakly-instrumented run
  whose numbers can't be trusted or reproduced; every later re-run re-pays OCR.
- **Schema v2 / packages (L-1/L-2) first:** highest-coordination change in the plan
  (analysis/ merge freeze); discovery does not need it, and discovery data will inform
  multi-account container design with real multi-account documents.
- **Generic understanding (P2-1) first:** explicitly investigation-gated (AD-7);
  building it before discovery data exists means designing against guesses. Discovery
  output is its requirements document.
- **D-4 concurrency first:** throughput matters only for the scanned tranche;
  intake triage (O-1 profiles) lets us run the fast digital tranche first and decide
  about D-4 with real numbers. Deferred, revisit after tranche 1.

## 1. Scope

**In:** R-2, R-3, R-4 (parser platform, pure refactor), D-3 (content-hash artifact
cache + dedup surfacing), O-3 (truncation detection), H-3 (telemetry), CI-1 (remote
corpus-gate repair), DSC-1/DSC-2 (discovery tooling + the discovery run itself).

**Out (explicit):** O-4 side-channel schema, D-4 concurrency/async, D-2b auth trio,
all LEDGER tasks (L-1…L-6), R-5 cross-check, R-7/P2-1 build, any new bank parser,
any change to protected financial modules (MASTER_PLAN §4).

**Entry gate:** local corpus gate GREEN at `da63ec2` (verified in PROJECT_STATUS.md).
CI-1 merges first so every subsequent PR is remotely protected.

## 2. Agent allocation — 4 Opus 5 implementation agents (minimum 3)

| Agent | Subsystem | Tasks (sequential within agent) | Why this grouping |
|---|---|---|---|
| **A — REEF** | Parser platform | R-2 → R-3 → R-4 | The three stages share total knowledge of the 43 parsers; splitting them across agents would triple ramp-up and create analysis/-wide merge conflicts. Largest workstream; the wave's main token cost. |
| **B — DELTA** | Cache & dedup | D-3 | Webapp/storage side only; zero overlap with analysis/. Extends D-1's store and O-1's hash — both merged. |
| **C — HARBOR** | Proof & measurement | CI-1 → H-3 → DSC-1 | CI first (protects the whole wave), telemetry after R-3's dispatch seam exists, then the discovery runner that consumes telemetry + cache + preflight. |
| **D — SONAR** | OCR integrity | O-3 | Small, ocr/-only, independent. Truncation flags must exist before the scanned discovery tranche — a silently truncated page inflates "parsed but failed reconciliation" statistics. |

Minimum configuration: 3 agents — defer O-3 until after the digital tranche and give
it to Agent D later (it stays SONAR-scoped; folding ocr/ work into another agent
violates MERGE_PLAN boundaries). Recommended: all 4, launched together; A/B/D are
immediately parallel (disjoint trees), C starts with CI-1 which touches only
`.github/`.

The discovery **run** itself (DSC-2) is an operational phase driven from the lead
session with Ocean adjudication — not a delegated implementation agent.

## 3. Task cards

### CI-1 — Remote corpus-gate repair (Agent C, first)

- **Objective:** a green `Corpus gate` workflow run on `main` on hosted
  infrastructure, so the gate stops depending on developer discipline.
- **Known facts:** run 31122891522 failed with "The job was not acquired by Runner of
  type hosted even after multiple attempts" — infrastructure, not workflow content;
  the workflow itself never executed a step. Only one run exists despite several
  pushes.
- **Scope:** diagnose (repo Actions settings, billing/minutes, runner label
  availability); minimal workflow adjustments if implicated (e.g. runner label,
  concurrency, `fail-fast` retry step); document root cause and fix in the workflow
  header comment. If the root cause is account-level (billing/plan), produce the
  exact remediation steps for Gustavo — agent stops there and reports; it does not
  change billing.
- **File allowlist:** `.github/workflows/corpus-gate.yml`, `README.md` (CI section
  only). Nothing else.
- **Acceptance:** a green run of the full workflow (suite + gate) on `main` visible in
  Actions, OR a documented account-level blocker with exact operator steps, approved
  by Gustavo as this wave's fallback (local gate remains merge authority in that
  case).
- **Tests:** the workflow run is the test.
- **Risk:** LOW. No product code.

### R-2 — Shared utilities (Agent A, stage 1) [P1-1a]

- **Objective:** consolidate the 38 `_money`/`_parse_money` clones (incl. French
  formats) into one `analysis/money.py`; shared date helpers; shared HTML-table and
  section-chunking utilities; remove the `td_can` import inversion.
- **Standard:** pure refactor — corpus gate **byte-identical**, full suite green,
  each parser's diff mechanical (import + call-site swap only).
- **File allowlist:** new `analysis/money.py`, new/extended shared helper modules
  under `analysis/`, all 43 `analysis/<bank>.py` (mechanical swaps only),
  `analysis/extract.py`, `tests/` (new unit tests for the shared modules).
- **Protected:** `analysis/adb.py`, `reconcile.py`, `metrics.py`,
  `transaction_classifier.py`, `serialization.py`, `analysis/pipeline.py` (that seam
  belongs to R-3), `webapp/`, `ocr/`.
- **Acceptance:** zero `_money` clones remain (guard grep test); `td_can` inversion
  gone; money module has exhaustive unit tests (US/CA/French formats, negatives,
  parens, thousands separators); corpus gate byte-identical.
- **Risk:** LOW-MODERATE. Purely mechanical but wide; the gate catches any slip
  field-by-field.

### R-3 — Parser protocol + registry dispatch (Agent A, stage 2) [P1-1b]

- **Objective:** `Parser` protocol (`detect(markdown) -> score`,
  `parse(markdown) -> Statement | None`), a registry with explicit, tested detection
  scoring and ordering metadata; the 43-way or-chain in `analysis/pipeline.py`
  replaced by registry dispatch. **RFC to Ocean before implementation** (MERGE_PLAN
  §2.1) — the RFC fixes the score semantics, tie-breaking, and ambiguity policy
  (two parsers scoring above threshold → explicit ambiguity outcome routed to review,
  never silent first-wins).
- **File allowlist:** new `analysis/parser_registry.py`, `analysis/pipeline.py`
  (dispatch section only), per-parser `detect` additions in `analysis/<bank>.py`,
  new `tests/test_parser_registry.py` (dispatch + ambiguity cases).
- **Also folds in R-8's dispatch half** if cheap: orchestrator bank-name literals
  (BMO contradiction check, Chase-export sentinel) move into the owning parser/repair
  layer. If not cheap, R-8 stays a named leftover — do not stretch the stage.
- **Acceptance:** adding a parser touches zero orchestrator code; dispatch order is
  data with tests; every corpus PDF resolves to the same parser as before (recorded-
  expectation parity test over 109 documents); corpus gate byte-identical.
- **Risk:** MODERATE. Dispatch changes are the one place a wrong-parser claim could
  appear; the parser-parity test over the corpus is the specific control.

### R-4 — Per-parser conformance harness (Agent A, stage 3) [P1-1c]

- **Objective:** every one of the 43 parsers gets detection-positive,
  detection-negative, and self-invalidation tests (incl. wells, scotia, columbia,
  navigant, relay, first_farmers — currently untested directly). Detection-negative
  matters most for discovery: it proves parser X does NOT claim bank Y's statement.
- **File allowlist:** `tests/` (new conformance modules + synthetic fixtures). No
  production code changes; any defect found is reported to Ocean, not silently fixed.
- **Acceptance:** 43/43 coverage, enforced by a completeness test that enumerates the
  registry and fails on an uncovered parser; suite green.
- **Risk:** LOW. Test-only.

### D-3 — Content-hash artifact cache + duplicate surfacing (Agent B) [P0-5]

- **Objective:** content-addressed store keyed by the established sha256 convention
  (uppercase hex of raw bytes): pdf hash → OCR markdown → extraction → report
  artifacts. Re-upload or re-analysis of identical bytes performs **zero** OCR/LLM
  calls. Duplicate detection (already flagged by O-1/D-1) surfaces in package
  responses. The cache read/write interface is importable outside Flask (module-level
  API in `webapp/storage.py` or a sibling), because the discovery runner (DSC-1) and
  `batch.py` consume it from the CLI.
- **File allowlist:** `webapp/storage.py`, `webapp/jobs.py`, `webapp/worker.py`,
  `webapp/app.py` (surfacing only), new cache module if split out,
  `tests/test_webapp_storage.py` + webapp suite updates, `.gitignore` (cache dir).
- **Protected:** `analysis/` (all), `ocr/` (all — consumes `parse_statement`
  results, never modifies the ladder), corpus/audit assets, D-2a security behaviors.
- **Acceptance:** re-upload test proves zero OCR calls (call-counting fake); cache
  survives restart (extends D-1 durability tests); package flags duplicates in the
  payload; corpus gate green (untouched paths); existing 795-test suite green.
- **Risk:** MODERATE. Cache-key correctness (hash must include nothing but content;
  parse-settings variations must partition the cache, not poison it) — settings hash
  joins the key, tested.

### O-3 — Truncation detection (Agent D) [P1-4c]

- **Objective:** detect OCR truncation (finish_reason / token-ceiling signals, and
  structural page-tail heuristics); flag suspect pages for re-OCR or review. No
  silent-truncation path remains.
- **File allowlist:** `ocr/` (pipeline + client + inspect integration), new
  `tests/test_truncation.py` with a dense-page fixture. Nothing outside `ocr/` and
  its tests.
- **Acceptance:** dense-page fixture demonstrates the flag; corpus paths unchanged
  (parity: no corpus page newly flagged without justification, documented if any);
  gate green.
- **Risk:** LOW-MODERATE. Flag-only — it must not change extraction output.

### H-3 — Telemetry (Agent C, after R-3 merges) [P1-7]

- **Objective:** per-statement telemetry record: content hash, path taken
  (native/tesseract/visual), parser id + detection score (from R-3's registry seam),
  fallback reason, per-stage timings, model calls, estimated cost, outcome class
  (validated / withheld / review / failed). Emitted by both `batch.py` and the
  webapp worker; stored via D-1/D-3's store on the webapp path and JSONL on the CLI
  path. Deterministic-coverage rate computable with one query/script.
- **Record schema reviewed by Ocean before implementation** (it is the discovery
  run's data contract).
- **File allowlist:** new telemetry module (HARBOR-owned per MERGE_PLAN),
  `analysis/pipeline.py` (emit hooks at the post-R-3 seam — coordinate with Agent A;
  one-pipeline-PR-at-a-time rule applies), `batch.py`, `webapp/worker.py` (emit call
  only), `webapp/storage.py` (telemetry table, coordinate with Agent B), tests.
- **Acceptance:** zero change to any analysis output (telemetry is write-only
  side-band); coverage rate computable from a fresh run over the corpus; suite +
  gate green.
- **Risk:** MODERATE, purely from touching the pipeline seam — mitigated by
  sequencing after R-3 and the byte-identical gate standard.

### DSC-1 — Discovery runner & report tooling (Agent C, last build task)

- **Objective:** a re-runnable CLI (`discovery/` package or `python -m discovery`)
  that takes an input directory of arbitrary PDFs and produces an intake-and-outcome
  report, consuming only merged platform pieces: O-1 `inspect` profiles (validity,
  encryption, digital/scanned, dedup hash), D-3 cache (never re-OCR), the pipeline
  (Gemini fallback **disabled** — deterministic + local OCR only; fallback-eligible
  documents are recorded, not sent), H-3 telemetry, and H-2's classification
  vocabulary for outcome buckets.
- **Report:** per-document row (hash, profile, dedup status, parser + score, outcome
  class, failure taxonomy) + rollups (deterministic coverage, bank/layout frequency
  clusters, top unknown-layout groups by volume). All identifiers masked last-4;
  reports write to a gitignored directory; **no discovery PDF and no unmasked datum
  is ever committed** (same sensitive-content rule as H-2).
- **File allowlist:** new `discovery/` package, new `tests/test_discovery.py`
  (synthetic fixtures), `README.md` (run instructions), `.gitignore`.
- **Acceptance (dry-run standard):** pointed at `Bank Statements/`, it must
  reproduce known truth — 109 documents, 0 unexpected duplicates, all 109 claimed by
  the expected parsers (R-3 parity expectations), 106 validated / 3 withheld — before
  it is ever pointed at the 4,000. Runs fully offline.
- **Risk:** LOW. Read-only consumer of everything else; the dry-run standard is the
  control.

### DSC-2 — The discovery run (operational, lead-driven; not an implementation agent)

- **Tranche 0:** intake profiling only (no parsing): document count, dedup rate,
  digital/scanned split, encrypted/invalid rate. Cost: seconds/doc. Output reviewed
  before proceeding.
- **Tranche 1:** all digital-native documents through the deterministic pipeline.
- **Tranche 2 (after O-3 merged and tranche-1 review):** scanned documents through
  local OCR — throughput measured; this is where a D-4 decision gets made with real
  numbers.
- **Adjudication:** unknown-layout clusters ranked by volume become the evidence
  base for the next roadmap decision (P2-1 generic understanding vs targeted parser
  additions vs registry expansion). Individual failures route through the H-2
  discrepancy-classification workflow; **no code changes in response to discovery
  findings inside this wave** — findings are Wave 3 input.
- **Required from Gustavo before DSC-2 starts:** the ~4,000-statement archive
  location (local path or transfer), confirmation it may be processed on this
  machine, and any retention/handling constraints.

## 4. Cross-workstream file matrix

| | A (R-2/3/4) | B (D-3) | C (CI-1/H-3/DSC-1) | D (O-3) |
|---|---|---|---|---|
| A | — | none | **analysis/pipeline.py** (H-3 emit hooks after R-3; sequenced, never parallel) | none |
| B | — | — | **webapp/storage.py** (H-3 telemetry table; C rebases on B's merged schema), .gitignore (trivial) | none |
| C | — | — | — | none |
| D | none | none | none | — |

Rules carried forward: one `analysis/pipeline.py` PR in flight at a time (Ocean
sequences); protected modules require Ocean review + forensic audit attached;
byte-identical corpus proof for R-2/R-3/O-3; no new statement-specific constants
anywhere (guard test enforces).

## 5. Execution & merge order

```
Execute:  CI-1 (C)  ∥  R-2 (A)  ∥  D-3 (B)  ∥  O-3 (D)
   then:  R-3 (A, after RFC approval)  →  R-4 (A)
   then:  H-3 (C; needs R-3 merged, D-3 merged)
   then:  DSC-1 (C)
   then:  DSC-2 tranche 0 → 1 → review → 2   (operational)

Merge:    CI-1 → R-2 → D-3 → O-3 → R-3 → R-4 → H-3 → DSC-1
```

- CI-1 first: every later PR gets remote gate protection (or the approved fallback).
- R-2 before D-3/O-3 is not required (disjoint) — order among those three is
  completion order; listed order is the expected one.
- R-3 merges only after its corpus-wide parser-parity test passes; R-4 immediately
  after (it pins R-3's registry).
- H-3 strictly after R-3 and D-3 (both seams must be final).
- DSC-1 last: it may only consume merged, gate-proven pieces.

## 6. Review checkpoints (Ocean)

1. **R-3 RFC** — protocol signatures, score semantics, ambiguity policy. Before any
   R-3 code.
2. **H-3 record schema** — before implementation; it is DSC-2's data contract.
3. **Per-merge** — standing criteria: full suite green (795+), local corpus gate
   GREEN attached (byte-identical for R-2/R-3/O-3; no re-baselines are expected this
   wave — an unapproved red gate is stop-the-line), no new statement-specific
   constants, no protected-module diffs.
4. **R-4 completeness report** — any parser defect found is a finding for Ocean, not
   a silent fix.
5. **DSC-1 dry-run report** on the 109-corpus — must match known truth exactly
   before the archive is touched.
6. **DSC-2 tranche gates** — tranche-0 profile review before tranche 1; tranche-1
   coverage report review before tranche 2; final discovery report becomes the Wave 3
   prioritization input.

## 7. Milestone acceptance (wave exit)

- Parser platform: registry dispatch live, 43/43 conformance coverage, corpus gate
  byte-identical throughout, zero orchestrator bank names (or documented R-8 leftover).
- Cache: identical-bytes re-analysis performs zero OCR/LLM calls, proven by test.
- Telemetry: deterministic-coverage rate for any batch computable with one command.
- CI: remote gate green on main, or Gustavo-approved documented fallback.
- Discovery: tranche 0 and tranche 1 complete with reports; scanned tranche complete
  or explicitly scheduled with measured throughput data; ranked unknown-layout
  cluster report delivered.
- PROJECT_STATUS.md updated as the wave closes.
