---
name: phase2-state
description: "PHASE 2.0 IN PROGRESS (opened 2026-09-01): OQ1-OQ11 RULED by Gustavo (PHASE2_RULINGS.md); Phase 2.0 = SAFETY FOUNDATIONS only (+0 coverage, 0 OCR-fed validated) on train10 from origin/main 746e1e9; five cells P20-ROUTER / P20-POSTPROCESS / P20-SEAM / P20-ARTIFACTS / P20-SURFACES; Sonnet 5 HIGH implementation, Opus adversarial reviews; STOP at the completion gate — Phase 2.1 (PaddleOCR) waits for Gustavo"
metadata:
  node_type: memory
  type: project
  originSessionId: 71746312-b66b-440b-a510-c04ff00bcdd2
  modified: 2026-09-01T00:00:00.000Z
---

**Baseline (unchanged)**: batch 9 FROZEN at `batch9-final` = `819d97d` (2,625 / 3,380 = 77.66%, 0
validated regressions; ANALYSIS_STAGE_VERSION 17, OCR_STAGE_VERSION 4, registry 84, suite 7,815 at
`7b25d70`). `origin/main` `746e1e9` = the freeze tree + the read-only `tools/ocr_legacy_census.py` +
docs (verified `git diff --stat 819d97d origin/main` outside docs = that one file). Run of record
`discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`; cold cache
`.claude/recovery/webapp_data_train9_cold` (OCR 3,364 / 1 key / 0 multi; analysis 2,656 / 1 / 0),
READ-ONLY.

**OCR-LEGACY-AUDIT**: COMPLETE, reviewed twice, merged to main at `09e6b75`; accepted architecture
`PHASE2_ARCHITECTURE_PLAN.md` at `746e1e9`.

**Gustavo's rulings (2026-09-01, `PHASE2_RULINGS.md`, binding)**: OQ1 = C (quarantine the whole
postprocess chain; per-function re-admission on census + fixtures + independent review; raw evidence
is the default) · OQ2 = YES (no-hardcodes guard into `ocr/`; TD masking only as declared intake
behavior with fixtures) · OQ3 = ALLOWLIST (local/private by default; remote/paid needs explicit
recorded opt-in; no silent local→remote hop) · OQ4 = Trigger T surface-only, measure, Phase 2.4 ·
OQ5 = PaddleOCR primary NEW visual extractor, Tesseract stays first image rung, Unlimited bounded
fallback after Paddle; neither implemented in 2.0 · OQ6 = RunPod stays a labeled paid escape hatch,
never automatic · OQ7 = salvage then quarantine/retire the legacy OCR scripts · OQ8 = YES adopt
`CachedArtifacts` · OQ9 = rename/remove the fake "OCR confidence", no substitute score · OQ10 =
run-of-record partition (never rows[0] / offline-first / visual-first / incidental order) · OQ11 =
supersede the standalone Paddle parser spec, keep its geometry ideas.

**Phase 2.0 — SAFETY FOUNDATIONS (authorized scope, nothing else)**: objective = make future OCR-fed
and geometry-fed validation possible without weakening the frozen model, and make "try extractors
until something balances" architecturally impossible. Failure classes A extraction / B structure / C
validation; **validator success may STOP escalation, validator failure may NEVER START it**; no
B→OCR, no C→OCR edge. Expected coverage **+0**; OCR-fed validated **0**; if coverage moves, STOP and
explain. Baseline re-derived 2026-09-01 from the run of record: R 13 · U 123 (89 `no_parser_matched`
+ 34 `parser_declined`; scanned 111 / mixed 12) · R∪U 136 · overlap 0 · validated∩(R∪U) 0 ·
Tesseract 36/15/5/123 · T surface 3 (1 in U). Baseline proof at `746e1e9`: guards 255 passed; the
OCR/artifact test slice 486 passed; corpus gate → recorded in BATCH9_TRANSITION §7.

**Cells (docs/agent-handoffs/, base `train10`, worktrees `.claude/worktrees/mt20-<card>`, branches
`wave20-<card>`)**: `P20-ROUTER` (A: `ocr/escalation.py`, EscalationRouter + ExtractionQualityGate +
failure classes, runner/worker rewired, U-extract/U-structure measured by `tools/phase2_trigger_split.py`,
tripwires, validated∩class-A = 0 pinned) · `P20-POSTPROCESS` (B1: nine-function census + synthetic
fixtures, whole-chain quarantine on analysis AND display paths, EMPTY re-admission tuple, OQ2 guard
into `ocr/` with the TD recovery in a declared `INTAKE_FURNITURE` register) · `P20-SEAM` (B2: closed
model-token charset + reserved-prefix refusal + `source_file` line-break refusal with hostile tests;
`ocr/endpoint_policy.py` loopback/private/remote with the exact opt-in literal; single endpoint, no
hop; `source_path_for` fallthrough closed; legacy scripts salvaged (`triage_scan.CHECKS` → test) then
retired; README RunPod relabeled) · `P20-ARTIFACTS` (C: `telemetry/run_of_record.py` shared by
`cohort_replay` and `CachedArtifacts`; runs record their partitions; OCR settings key gains extractor
/ postprocess state / raster + schema versions / endpoint class / binary versions; OCR_STAGE_VERSION
4→5 with its pin in the same commit; CASE 9 multi-partition determinism) · `P20-SURFACES` (D: "OCR
confidence" → validation verdict words, no number; Q3 class native-only via `analysis/provenance.py`
first-line reader, fail closed on non-native/absent; the two 2026-07 specs SUPERSEDED). Composition
order B2 → B1 → A → C → D. Models: Sonnet 5 HIGH implementation (explicit `model: sonnet`), Opus
independent adversarial reviews; Ocean (Fable 5.1) composes.

**Completion gate** (PHASE2-0-SAFETY.md §Completion): all cells reviewed/closed/re-reviewed, composed
on train10, cohort replay + archive sweep + `floor.sh` + the cold run (required by the v5 bump) vs the
batch-9 run of record `--fail-on-regression` (2,625 → 2,625), remote CI green, docs durable, worktree
clean → STOP; closure report to Gustavo; Phase 2.1 waits for his approval.

Related: [[batch9-state]] [[moneythumb-phase1-roadmap]] [[batch8-operating-model]] [[subagent-model-policy]]
