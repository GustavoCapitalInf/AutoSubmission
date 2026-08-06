# PROJECT STATUS — Single Source of Truth

**Read this first.** This document is the authoritative project status for every
session. Trust it over conversational memory; trust the repository over it if they
ever disagree, and then fix this file. Update it at every wave close and at any
material state change.

Last verified: **2026-08-06** (all numbers below re-measured, not copied).

---

## Where we are

| Fact | Value |
|---|---|
| Current milestone | **Wave 2 "Discovery-Ready Platform" — APPROVED 2026-08-06, IN EXECUTION** (`WAVE2_BRIEF.md` incl. §9 amendments). Discovery archive delivered: **3,506 PDFs / 0.89 GB / 69 bank folders (965 Unidentified)** inside `Bank Statements/`, untracked, protected by `.gitignore` `Bank Statements/**`. Archive copy had deleted the 109 tracked corpus PDFs from the working tree — restored intact 2026-08-06. H-0 (gate re-scope) is the first merge of the wave. |
| Completed milestones | Phase 1 audit + architecture plan (8 docs in this directory); **Wave 0** (H-1 corpus gate, H-6 doc/fixture fixes, D-2a dev-server hardening); **Wave 1** (H-2 MoneyThumb harness, D-1 durable persistence, R-1 hardcode purge, O-1 unified preflight) — all merged to `main`, pushed |
| Current commit | `main` = `1c82a2b` ("Merge H-0 + CI-1"), pushed. Lead branch `worktree-mt-lead` carries the execution log ahead of main (docs only). Wave 2 agent branches: `wave2-parser-platform` (in progress), `wave2-cache` (D-3 done, approved), `wave2-proof` (H-0/CI-1 merged; CI-1b in progress), `wave2-ocr-integrity` (O-3 done, approved). |
| Test count | **801 passed** in the main checkout post-H-0 (2 deselected opt-in: `live`, `corpus`+ladder-parity). Branch counts: D-3 → 846, O-3 → 827 (merge-pending). Was 523 at planning, 795 post-Wave-1. |
| Corpus gate | **GREEN — manifest-scoped since H-0 (`1c82a2b`)**: the gate audits the pinned 109-path manifest (both audit CSVs must pin the identical set; every pin must exist + hash-match) and reports foreign PDFs under the shared root as ignored, names withheld. Verified in the main checkout WITH the 3,507-file archive present: 106 PASS / 3 WITHHELD, GREEN, 341 s. Run: `python corpus_gate.py` (merge authority), `--corpus-root` to audit another checkout. |
| Remote CI | **Workflow FIXED, verification in progress.** Original runner-acquisition failure = transient GitHub capacity (disproved billing hypothesis). Real failure = missing poppler/tesseract → fixed (`1c82a2b`). Residual: columbia fixtures drift under the runner's older tesseract → CI-1b in progress (serve from committed artifacts). **CI-2 open anomaly: push events create no runs (only `workflow_dispatch` works)** — interim protocol: manual dispatch after every merge to main. |
| MoneyThumb parity | `PARITY_MATRIX.md` (26 capabilities, as of the pre-Wave-1 audit): 8 ✅ ahead, 6 🟡 split, 12 🔴 behind. Wave 1 improved but did not re-score: #26 duplicates (now flagged via O-1+D-1), #18/#23 (persistence exists; auth/concurrency still missing), #22 maintainability (hardcodes purged; parser platform still pending). H-2 comparison harness is operational over all 6 benchmark sets (`python -m benchmark`, offline); reports write to gitignored `benchmark_reports/` on demand and are deliberately not committed. |
| Active worktrees | Main checkout (`main`) + permanent lead worktree `.claude/worktrees/mt-lead` (`worktree-mt-lead`). Wave 0/1 temporary worktrees and branches removed. |
| Active branches | Local: `main`, `worktree-mt-lead`, plus Wave 2 agent branches (see WAVE2_BRIEF §9). Remote: `origin/main` plus two stale branches — `origin/cursor/cloud-agent-1785900428099-wlfy6`, `origin/feature/universal-statement-intelligence` — **verified 2026-08-06: each holds one unique unmerged commit (prior universal-statement-intelligence prototypes touching protected modules). NOT deleted; kept as P2-1 reference pending Gustavo's call.** |

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
