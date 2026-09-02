# PROJECT STATUS — Single Source of Truth

**Read this first.** This document is the authoritative project status for every
session. Trust it over conversational memory; trust the repository over it if they
ever disagree, and then fix this file. Update it at every wave close and at any
material state change.

Last verified: **2026-08-31** (all numbers below re-measured on the Windows host, not copied).

---

## Where we are

| Fact | Value |
|---|---|
| Current milestone | **COVERAGE WAVE BATCH 9 OFFICIAL AND FROZEN (2026-08-31, Windows host): `2,596 / 3,380 → 2,625 / 3,380` — 76.80% → 77.66%, +29 validated, +0.86 percentage points; 32 improved / 3 regressed / 3,345 unchanged; the 3 regressed are PNC-LAYOUTS' fail-closed movement named in advance (`1F31588B36B2E4AF`, `5684857C24B79344`, `BE703D525955253C`, withheld→failed), 0 validated regressions; registry 83 → 84; ANALYSIS_STAGE_VERSION 16 → 17; OCR v4 unchanged.** Measured against the batch-8 run of record `cda8882d` with the EMPTY retired quarantine (shared 3,380 = comparable 3,380 + quarantined 0) as run `TRAIN9-7b25d70/2026-08-31T185527…-91f5179a` at tree `ff35b3d`, under bounded low-memory execution (floor 2.0 GB / cap 4 GB / serial OCR; measured peak 1,236.3 MB — within 2 MB of batch 8's). **This is the deterministic-v1 / multi-account-v1 baseline (`batch9-final`)**: the L-1 architecture delivered through five reviewed stages — `DocumentReport` and the document seam (RULE S), evidence-based sibling omission on the document object (Q10: surface, never demote; 15 protected carriers pinned both legs), every reader and seam taught the document shape, the serialized shape by account count alone, and the first multi-account publisher (guardian_cu, +8/12 accounts) with the corroborated Q3 idle-sibling class, printed-designation-only internal transfers, and account-based package membership (rulings §8.8–§8.16). SCOPE FROZEN per §8.11: no new deterministic coverage; the backlog is `BATCH9_BACKLOG.md`; Phase 2 (Unlimited OCR + PaddleOCR as extractors only) begins with the read-only `OCR-LEGACY-AUDIT`. Durable record: `BATCH9_TRANSITION.md` §7–§8. |
| **Phase 2.1 — IN PROGRESS (opened 2026-09-02)** | **PADDLEOCR + CANONICAL WORD BOXES + DOCUMENTGEOMETRY.** Gustavo approved Phase 2.0 and authorized Phase 2.1 ONLY. Train `train11` from `origin/main` `9a54952`. Rulings recorded (`PHASE2_RULINGS.md` §Phase 2.1): A — automatic hosted extraction REFUSED; B — density SURFACE-ONLY; the explicit Vast.ai `remote_paid` authorization (RTX 5090, PaddleOCR 3.7.0, PP-OCRv5, word boxes proven; explicit opt-in `PADDLE_REMOTE_OPT_IN`; connection from the environment only; localhost is not local; NO production customer statements to Vast without a separate ruling). Umbrella card `docs/agent-handoffs/PHASE2-1-PADDLE.md` (D1–D9, twenty cases, gate); cells P21-GEOMETRY / P21-PADDLE / P21-ROUTING. Cell 0 on the train: `evidence/` (canonical frames/words/lines, immutable raw, sha round-trip) and `ocr/paddle_config.py` (pins, vocabularies, two opt-ins, fail-closed loader). Floor 2,625 untouched; OCR_STAGE_VERSION 5; EXTRACTION_SCHEMA_VERSION 1 → 2 planned (cell R). Scope consequence: the 13-document legal population is NOT run through Vast in this phase (privacy boundary, D8); end-to-end proof + runtime/cost on synthetic fixtures; Paddle-eligible 13 / attempted 0 / newly validated 0 reported honestly. Live record: `BATCH9_TRANSITION.md` §7 (2026-09-02 "PHASE 2.1 OPENED" onward), `PHASE2_STATE.md`. |
| **Phase 2.0 — COMPLETE (2026-09-02)** | **PHASE 2.0 SAFETY FOUNDATIONS COMPLETE — completion gate met; STOPPED pending Gustavo's approval of the closure report.** Composed code tree `941918f` on `train10` (five cells + P20-REPLAY-SHAPE, each reviewed → closed → re-reviewed to APPROVE WITH FINDINGS with every residual closed). Proof: full suite **8,342 passed** / 45 skipped / 38 deselected; guards 267; conformance 1,282; gate GREEN 105/3/1; corpus slice 34; remote CI GREEN (run 33599700440); full-archive cohort replay 2,625 of 2,625 identical (0 newly validated, 0 regressions); **cold run `TRAIN10-941918f/…-ef34ee30` vs the batch-9 run of record: 2,625 → 2,625, 3,380 unchanged, compare exit 0** (peak 1,242 MB). OCR_STAGE_VERSION 4 → 5 (ANALYSIS stays 17; registry 84). Measured: R 13 · U 123 · U-extract (admitted) 0 · U-structure 123 · density-surfaced candidate 23 · legal escalation population 13 · validated∩class-A 0 · OCR-fed validated 0 · coverage movement +0 (as expected). Durable record: `BATCH9_TRANSITION.md` §7 (2026-09-01/02), `PHASE2_STATE.md`, `reviews/PHASE2_P20*_REVIEW.md`. **Phase 2.1 (PaddleOCR) NOT authorized until Gustavo approves.** |
| Phase 2.0 (opening record) | PHASE 2.0 — SAFETY FOUNDATIONS opened 2026-09-01. Gustavo ruled OQ1–OQ11 (`PHASE2_RULINGS.md`, binding) and authorized Phase 2.0 ONLY: failure classes A/B/C, the independent EscalationRouter + ExtractionQualityGate (validator success may STOP escalation, validator failure may NEVER START it), the Trigger-U split (U-extract / U-structure) measured on the batch-9 run of record, the nine-function postprocess census + whole-chain quarantine (OQ1 = C), OCR_MODEL/provenance-token injection closed, the endpoint allowlist / $0 default enforced in code, run-of-record artifact selection (OQ10) + `OCR_STAGE_VERSION` 4→5 with its pin, Q3 native-only, the fake "OCR confidence" removed, the no-hardcodes guard into `ocr/` (OQ2). **Expected coverage movement +0; OCR-fed validated 0; the 2,625 floor untouched.** Train `train10` from `origin/main` `746e1e9`; umbrella card `docs/agent-handoffs/PHASE2-0-SAFETY.md`; cells `P20-ROUTER` / `P20-POSTPROCESS` / `P20-SEAM` / `P20-ARTIFACTS` / `P20-SURFACES`; rules delta `docs/agent-handoffs/PHASE2-RULES.md`. Baseline at `746e1e9` (2026-09-01): R 13 · U 123 · R∪U 136 · validated∩(R∪U) 0; guards 255 passed; OCR/artifact slice 486 passed. **Phase 2.1 (PaddleOCR) is NOT authorized** until the Phase 2.0 closure report is approved by Gustavo. |
| Previous milestone (batch 8) | **COVERAGE WAVE BATCH 8 OFFICIAL (2026-08-29, Windows host): 2,469 → 2,596 / 3,380 — 73.05% → 76.80%, +127 validated; 138 improved / 0 regressed; registry 75 → 83; v15 → 16; OCR v3 → 4.** Control `CONTROL-B7-WIN-302f8f2 / 5e730887`; run of record `cda8882d`; quarantine retired to empty. Batch 7 and earlier: git history and the BATCH*_TRANSITION logs. |
| Completed milestones | Phase 1 audit + architecture plan (8 docs in this directory); **Wave 0** (H-1 corpus gate, H-6 doc/fixture fixes, D-2a dev-server hardening); **Wave 1** (H-2 MoneyThumb harness, D-1 durable persistence, R-1 hardcode purge, O-1 unified preflight) — all merged to `main`, pushed |
| Current commit | `main` = the batch-9 freeze commit on top of `8ed0ead` (batch-9 train fast-forwarded: the composed L-1 stages + RV-PAGE-COVERAGE + Q3 probe + v17, registry 84, and the batch-9 durable record), tagged `batch9-final`, pushed. Remote CI: SUCCESS on the train tree (run 33419094234 at `b5d8f00`); the main-push run is recorded in `BATCH9_TRANSITION.md` §7. Lead worktree `.claude/worktrees/mt-lead` on `main`. |
| Test count | **7,815 passed** (44 skipped, 35 deselected opt-in), run 2026-08-31 on the batch-9 composed tree `7b25d70`. Trajectory: 523 (planning) → 795 (Wave 1) → 1,745 (Wave 2 build) → 2,562 (Wave 3 cells) → 2,854 (b1) → 3,013 (b2) → 3,769 (b3) → 4,240 (b4) → 4,511 (b5) → 5,374 (b6) → 5,857 (b7) → 6,742 (b8) → 7,815 (b9). |
| Corpus gate | **GREEN — manifest-scoped (H-0), separator-agnostic (CI-1c)**: audits the pinned 109-path manifest (both audit CSVs must pin the identical set, every pin exists + hash-matches), foreign PDFs reported ignored with names withheld. 105 PASS / 3 WITHHELD / 1 REFUSED since the batch-7 REPAIR-DOCTRINE ceremony (106/3 before it) — zero re-baselines, zero financial drift across ~15 gate runs on two platforms. `python corpus_gate.py`; `--corpus-root` audits another checkout. Batch-8 train: GREEN 105 / 3 / 1 at `152e904`, at the `302f8f2` control worktree on this host, and on remote CI for `train8` and `main`. |
| Remote CI | **OPERATIONAL, GREEN since `8c01930` (2026-08-12).** Push triggers work (CI-2 resolved). **Record correction (2026-08-13):** every push run 2026-08-07→08-10 was RED on exactly one Linux-only test (case-folded pinned path opened by manifest spelling — FileNotFoundError on case-sensitive filesystems; zero financial drift; all other tests + gate unaffected); entries claiming "CI green" in that window had not read the remote conclusions. Standing rule now: a merge is "CI green" only when the remote run's conclusion is read and its run id recorded. Earlier failure genealogy: `CI1_FINDINGS.md`. |
| Discovery readiness | `python -m discovery` with `--dry-run` / `--profile-only` / `--digital` / `--scanned` modes; dry run reproduces the pinned 109 exactly (coverage 108 / 109, validated 102 / review 3 / withheld 3 / refused 1, currency 108 / 108, provenance 108 / 108). Batch-8 measurement tooling on `main`: `tools/train/control_b7.sh` (same-host batch-7 control), `tools/train/coldrun.sh` (base and cold cache REQUIRED; comparison = `tools/train8_compare.py`), `tools/train/winrun.py` (Windows Job-Object cap / timeout / floor / peak telemetry), `tools/train/provenance.py`, `tools/recon_b7_check.py`. Runs of record on this host: control `5e730887`, train 8 `cda8882d` (`discovery_reports/`, gitignored; the run-directory paths are in `discovery_reports/train8-logs/`). |
| MoneyThumb parity | `PARITY_MATRIX.md` (26 capabilities, as of the pre-Wave-1 audit): 8 ✅ ahead, 6 🟡 split, 12 🔴 behind. Wave 1 improved but did not re-score: #26 duplicates (now flagged via O-1+D-1), #18/#23 (persistence exists; auth/concurrency still missing), #22 maintainability (hardcodes purged; parser platform still pending). H-2 comparison harness is operational over all 6 benchmark sets (`python -m benchmark`, offline); reports write to gitignored `benchmark_reports/` on demand and are deliberately not committed. |
| Active worktrees | Main checkout (`main`) + lead worktree `.claude/worktrees/mt-lead` (`main`). Batch-8 worktrees still registered after the freeze: the twelve `mt8-*` cell worktrees, `b7-302f8f2` (the control tree; holds the control run and its cold cache), `train8-prebump` (`504986e`, used for the OCR-v3 instruments), `welch-tip`; plus sixty stale wave-3…7 worktrees whose metadata OneDrive locks — prune when convenient (housekeeping, not a train item). |
| Active branches | Local: `main`, `worktree-mt-lead`. Remote: `origin/main` plus two stale branches — `origin/cursor/cloud-agent-1785900428099-wlfy6`, `origin/feature/universal-statement-intelligence` — **verified 2026-08-06: each holds one unique unmerged commit (prior universal-statement-intelligence prototypes touching protected modules). NOT deleted; kept as P2-1 reference pending Gustavo's call.** |

## Architecture status

The platform remains a **validated analysis engine** whose shell is being
industrialized wave by wave. Financial core (ADB, reconciliation, metrics,
classification, serialization) is protected and untouched since Phase 1 — see
MASTER_PLAN §4 do-not-touch list. What Waves 0–1 added:

- **Continuous proof:** deterministic offline corpus gate (`corpus_gate.py`) enforcing
  the audited truth set field-by-field, plus the CI workflow (remote runner pending).
- **Honest validation:** all 12 statement-specific hardcode classes purged from
  parsers (`R1_HARDCODE_LOG.md`); reintroduction blocked by
  `tests/test_no_statement_hardcodes.py`; corpus outcomes unchanged (106/3, field-identical).
- **Durable serving base:** SQLite store (`webapp/storage.py`) — jobs/results survive
  restart, analyst review decisions append-only with actor+timestamp, packages
  durable, audit-log events; dev-server hardening (waitress, upload limits, masking,
  CSV-injection guards) from D-2a.
- **Unified intake:** single preflight ladder + `DocumentProfile` (`ocr/inspect.py`):
  validity, encryption rejection, digital/scanned classification, content sha256,
  duplicate flag; schema v2 document profiles; the drifted duplicate ladder in
  `webapp/worker.py` is gone.
- **Benchmark tooling:** `benchmark/` package compares our pipeline vs MoneyThumb vs
  audited expectations with 8-way discrepancy classification; MT is never auto-truth.

Still prototype-grade (unchanged): dispatch is an ordered substring or-chain across
43 parsers (no detection scoring/conformance suite), no telemetry, no artifact cache
(identical bytes re-pay full OCR), single worker/no async, no auth (D-2b), packages
lack month-map/coherence (L-2), single-account schema at extraction (L-1),
no generic unknown-bank understanding (P2-1).

## Outstanding production gaps (delta view of PRODUCTION_GAPS.md)

| Gap | Status after Wave 1 |
|---|---|
| G1 coverage corpus-shaped | **OPEN — largest gap.** Discovery corpus is the measurement instrument; P2-1 is the eventual fix. |
| G2 prototype serving layer | Partially closed: persistence ✅ (D-1), dev-server safety ✅ (D-2a). Open: auth/rate limiting/runbook (D-2b), concurrency (D-4), multi-tenancy/audit/retention (D-7), versioned API (D-6). |
| G3 hardcode integrity | **CLOSED** (R-1 + guard test). |
| G4 validation not continuous | Closed locally (gate + workflow); **remote enforcement open** (CI-1). |
| G5 multi-account & packages | OPEN (L-1, L-2; O-1 now detects likely account count as advisory signal). |
| G6 underwriting intelligence | OPEN (L-3; forensics O-5). |
| G7 scanned throughput | OPEN (D-3 cache is the Wave-2 piece; D-4 concurrency deferred pending discovery throughput data). |
| G8 export ergonomics | OPEN (L-6). |
| G9 no comparison tooling | **CLOSED** (H-2 harness; per-bank accuracy tracking H-5 still future). |

## Recommended next objectives (decision pending)

Per `WAVE2_BRIEF.md`: the 4,000-statement discovery corpus is the highest-value
objective and is now unblocked (all four WAVE1 §5.7 prerequisites merged), but it
should land as the **capstone** of a platform wave, not before it. Wave 2 =
CI-1 (remote gate) + R-2/R-3/R-4 (parser platform, byte-identical) + D-3 (artifact
cache) + O-3 (truncation flags) + H-3 (telemetry) + DSC-1 (discovery runner, dry-run
proven on the 109-corpus) → DSC-2 (the discovery run, tranched digital-first).
4 Opus 5 implementation agents recommended (minimum 3). Discovery findings are
Wave 3 input — no code reactions inside Wave 2.

Required from Gustavo before DSC-2: archive location/transfer, processing
confirmation, retention constraints. Required before any agents launch: Wave 2 brief
approval.

## Standing rules (unchanged)

- Local corpus gate GREEN attached to every merge; unapproved red = stop-the-line.
- No new statement-specific constants (guard test enforces); registry-only
  counterparty knowledge, with fixtures.
- Protected modules (MASTER_PLAN §4) require Ocean review + forensic audit.
- All delegated agents run on Claude Opus 5 (`CLAUDE_CODE_SUBAGENT_MODEL=opus`);
  verify before launch, stop and ask if misconfigured.
- MoneyThumb outputs are never ground truth; discrepancies go through H-2
  classification and Ocean ruling.
- `moneythumbResults/`, discovery PDFs, and unmasked reports are never committed.

## Document map

`MASTER_PLAN.md` (thesis, decisions AD-1…9, P0–P3 roadmap, protected list, milestone
gates M1–M5) · `TASK_BOARD.md` (per-agent tasks + status updates section) ·
`MERGE_PLAN.md` (agent boundaries, interface contracts, wave sequencing) ·
`PARITY_MATRIX.md` · `PRODUCTION_GAPS.md` · `RISK_REGISTER.md` · `FIELD_MAPPING.md` ·
`CURRENT_ARCHITECTURE.md` · `R1_HARDCODE_LOG.md` (Wave 1 rulings) ·
`WAVE0_BRIEF.md` / `WAVE1_BRIEF.md` (+ prompts, historical) · `WAVE2_BRIEF.md`
(proposed next milestone).
