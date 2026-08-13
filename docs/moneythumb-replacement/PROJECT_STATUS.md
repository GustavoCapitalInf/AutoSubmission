# PROJECT STATUS — Single Source of Truth

**Read this first.** This document is the authoritative project status for every
session. Trust it over conversational memory; trust the repository over it if they
ever disagree, and then fix this file. Update it at every wave close and at any
material state change.

Last verified: **2026-08-13** (all numbers below re-measured, not copied).

---

## Where we are

| Fact | Value |
|---|---|
| Current milestone | **UNCLAIMED-LAYOUT PHASE IN PROGRESS (2026-08-13).** Cell 1 (BMO) OFFICIAL: improved 154 / regressed 0, claim coverage 50.4% → 55.0% (§BMO-LAYOUTS). FIXUPS-1 OFFICIAL: improved 26 / regressed 0 (instrument `04e24c20` → `ca2ba0eb`, exit 0 under --fail-on-regression). **Current totals (distinct docs, denominator 3,380): validated 1,776 (52.5%) · review 10 · withheld 58 · failed 1,523 · claim coverage 55.0%. Cumulative vs canonical baseline `1dfaf7e9`: validated 1,048 → 1,776 (+728, +69%); withheld 650 → 58; zero regressions anywhere; $0 vendor cost.** COUNTS-P1 phase-1 measurement merged (observe-only, zero production change); D5 forensic verdict `semantics_difference` — pinned PASS stands, no truth-set movement; first_community count-scope card landed in FIXUPS-1. Remote CI red 08-07→08-12 (one Linux-only path-spelling test, zero financial drift) fixed `8c01930`, GREEN since. **Open: cell 2 REEF-CHASE-LAYOUTS dispatched (handoff refreshed to the `ca2ba0eb` baseline, branch at current main) — awaiting Gustavo's session launch; Phase-2 stated-count go awaiting Gustavo.** Prior history: **WAVE 3 TRACK A CELL PHASE COMPLETE (2026-08-09).** Seven parser cells + grouper promotion, all merged/pushed/CI-green: chase 300, TD 56, RBC 58, BofA 71, Wells 36, us_bank 20, truist 20, pnc 13. **Cumulative vs canonical baseline: validated 1,048 → 1,622 (+574, +55%); coverage 31.0% → 48.0%; withheld 650 → 58; ZERO regressions anywhere; $0 vendor cost; no truth-set movement outside the one approved ceremony (Chase posting dates).** Remaining 58 withheld = geometry class 19 + honest fail-closed + cells ≤3. W3-1/2/4/5, W3-3c structurer (opt-in off), all merged. Next-phase recommendation (unclaimed-layout class: BMO 164, Chase 176…) awaiting Gustavo; stated-count check proposal in preparation. Per-cell records: `W3_TRACKA_LOG.md`; reviews/rulings: `WAVE2_EXECUTION_LOG.md`. **DISCOVERY (2026-08-07):** both tranches over the frozen 3,506-doc archive, ambiguous 0, $0.00 — `DISCOVERY_COMBINED_REPORT.md`. Wave 2 build history follows. **Wave 2 "Discovery-Ready Platform" — BUILD COMPLETE 2026-08-07.** All workstreams merged and remotely verified: H-0 gate re-scope, CI-1/1b/1c, R-2 shared utils, R-3.0–3.4 registry dispatch, R-4/R-4b conformance + detection fixes, D-3/D-3b artifact cache, O-3 truncation flags, H-3 telemetry, DSC-1/1b discovery runner. **Remaining: the operational discovery tranches (1: ~3,297 digital; 2: ~176 scanned) — awaiting Gustavo's tranche-1 go.** Full review/merge history: `WAVE2_EXECUTION_LOG.md`. Discovery archive: frozen at 3,768 files / 3,615 PDFs / 996,080,803 bytes (109 pinned + 3,506 discovery), gitignore-protected; tranche-0 profile: 94.0% digital, 5.0% scanned, ~206 duplicates, 33 malformed/encrypted. |
| Completed milestones | Phase 1 audit + architecture plan (8 docs in this directory); **Wave 0** (H-1 corpus gate, H-6 doc/fixture fixes, D-2a dev-server hardening); **Wave 1** (H-2 MoneyThumb harness, D-1 durable persistence, R-1 hardcode purge, O-1 unified preflight) — all merged to `main`, pushed |
| Current commit | `main` = `8c01930` ("fix(discovery): case-folded pinned documents read through disk spelling"), pushed, remote CI GREEN (run `31662641324`). All wave-2/3 agent branches fully merged; active dispatch branch `wave3-chase-layouts` (no agent commits yet). Lead branch `worktree-mt-lead` carries the execution log. |
| Test count | **2,475 passed** in the main checkout (18 deselected opt-in: `live` + `corpus`-marked), re-run 2026-08-13. Trajectory: 523 (planning) → 795 (Wave 1) → 1,745 (Wave 2 build) → 2,475 (Wave 3 phase cells). |
| Corpus gate | **GREEN — manifest-scoped (H-0), separator-agnostic (CI-1c)**: audits the pinned 109-path manifest (both audit CSVs must pin the identical set, every pin exists + hash-matches), foreign PDFs reported ignored with names withheld. 106 PASS / 3 WITHHELD throughout the entire wave — zero re-baselines, zero financial drift across ~15 gate runs on two platforms. `python corpus_gate.py`; `--corpus-root` audits another checkout. |
| Remote CI | **OPERATIONAL, GREEN since `8c01930` (2026-08-12).** Push triggers work (CI-2 resolved). **Record correction (2026-08-13):** every push run 2026-08-07→08-10 was RED on exactly one Linux-only test (case-folded pinned path opened by manifest spelling — FileNotFoundError on case-sensitive filesystems; zero financial drift; all other tests + gate unaffected); entries claiming "CI green" in that window had not read the remote conclusions. Standing rule now: a merge is "CI green" only when the remote run's conclusion is read and its run id recorded. Earlier failure genealogy: `CI1_FINDINGS.md`. |
| Discovery readiness | `python -m discovery` with `--dry-run` / `--profile-only` / `--digital` / `--scanned` modes. Dry run reproduces the pinned 109 exactly (coverage 100%, validated 100 / review 6 / withheld 3 by name, expectations-file parity). Tranche-0 profile complete. Production-ladder-only resolution (binding); Gemini structurally excluded in discovery mode; telemetry JSONL + report rollups incl. folder-label agreement and near-miss vectors; reports gitignored, identifiers masked. **Tranche 1 awaits Gustavo's go.** |
| MoneyThumb parity | `PARITY_MATRIX.md` (26 capabilities, as of the pre-Wave-1 audit): 8 ✅ ahead, 6 🟡 split, 12 🔴 behind. Wave 1 improved but did not re-score: #26 duplicates (now flagged via O-1+D-1), #18/#23 (persistence exists; auth/concurrency still missing), #22 maintainability (hardcodes purged; parser platform still pending). H-2 comparison harness is operational over all 6 benchmark sets (`python -m benchmark`, offline); reports write to gitignored `benchmark_reports/` on demand and are deliberately not committed. |
| Active worktrees | Main checkout (`main`) + permanent lead worktree `.claude/worktrees/mt-lead` (`worktree-mt-lead`) + active dispatch worktree `.claude/worktrees/mt-chase` (`wave3-chase-layouts`, awaiting agent session). All other phase-cell worktrees/branches removed after merge (2026-08-13 housekeeping). |
| Active branches | Local: `main`, `worktree-mt-lead`, `wave3-chase-layouts`. Remote: `origin/main` plus two stale branches — `origin/cursor/cloud-agent-1785900428099-wlfy6`, `origin/feature/universal-statement-intelligence` — **verified 2026-08-06: each holds one unique unmerged commit (prior universal-statement-intelligence prototypes touching protected modules). NOT deleted; kept as P2-1 reference pending Gustavo's call.** |

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
