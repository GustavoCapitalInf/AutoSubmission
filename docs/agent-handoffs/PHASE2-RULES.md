# Phase-2 standing rules (binding for every Phase-2 cell; read BATCH9-RULES.md first, then this delta)

`docs/agent-handoffs/BATCH9-RULES.md` carries forward in full (choreography, proof floors, instruments,
host lessons, report contract, git ownership). This file is the Phase-2 DELTA. Ocean reviews and
composes; you never merge or push.

## Base facts (Phase 2.0)
- Frozen baseline: tag `batch9-final` = `819d97d` (**2,625 / 3,380 = 77.66%**, 0 validated regressions).
  Code tree of `origin/main` (`746e1e9`) = the freeze tree + the read-only `tools/ocr_legacy_census.py`
  + documentation; nothing under `analysis/`, `ocr/`, `webapp/`, `discovery/`, `telemetry/` changed.
- Train branch: **`train10`** (opened from `origin/main` `746e1e9`). Your base is `train10` at your
  handoff's commit. Worktree `.claude/worktrees/mt20-<card>`, branch `wave20-<card>`.
- Tree at base: registry **84**, `ANALYSIS_STAGE_VERSION` **17**, `OCR_STAGE_VERSION` **4**. Floor at
  the composed batch-9 tree `7b25d70`: suite **7,815 passed** (44 skipped, 35 deselected); guards and
  conformance green; `python corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED.
- Run of record: `discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a` (tree
  `ff35b3d`; 3,506 rows / 3,380 shas; validated 2,697 rows = 2,625 distinct shas; `visual_rung =
  not_attempted` 3,506/3,506; `source_path` native 3,297 / local_tesseract 179 / none 30). Its cold
  cache is `.claude/recovery/webapp_data_train9_cold` (OCR v4: 3,364 rows / 3,364 inputs / 1 key / 0
  multi-artifact inputs; analysis v17: 2,656 / 2,656 / 1 / 0). **READ-ONLY.** The batch-8 cold cache
  `.claude/recovery/webapp_data_train8_cold` is likewise read-only. Nothing writes to either.
- Baseline triggers on the run of record (Ocean, 2026-09-01, re-derived from `rows.csv`): **R = 13**
  (`deferred_visual_ocr`), **U = 123** (`source_path = local_tesseract AND dispatch_outcome != claimed`;
  identical to `… AND outcome_class = failed`), **R ∪ U = 136**, overlap **0**, **validated ∩ (R ∪ U)
  = 0**; Tesseract split 36 validated / 15 withheld / 5 review / 123 failed; U by reason
  `no_parser_matched` 89 / `parser_declined` 34; U by profile scanned 111 / mixed 12; Tesseract reads
  with `truncated_pages > 0` = **3** (T's surface population), of which 1 is in U.

## Gustavo's rulings and doctrine (binding)
- `docs/moneythumb-replacement/PHASE2_RULINGS.md` — OQ1–OQ11 RULED 2026-09-01. No cell re-opens one.
- `docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md` — the accepted architecture. The
  governing invariant: **validator success may STOP escalation; validator failure may NEVER START
  escalation.** Three failure classes: A extraction / B structure / C validation. No B → OCR edge, no
  C → OCR edge, no validator → extractor path of any kind.
- Phase 2.0 is **+0 coverage**. `newly validated` must be 0 in every cell's report and at the composed
  train; `OCR-fed validated` must be 0. If a cell's replay shows new `validated`, STOP and report why
  before anything else.
- Every protection of the frozen model is untouchable (reconciliation, ledger identity, transaction
  coverage, opening/ending identities, page completeness, account completeness, statement period,
  explicit currency evidence, ADB, integrity checks, multi-account independence, package membership).
  One account → one ADB. No invented values. No rewriting source values to force reconciliation.
- Raw OCR evidence is immutable. The validator is not a candidate optimizer; no candidate auto-adoption.
- $0 vendor stays: no paid OCR, no VLM, no rented GPU, no hosted model call anywhere (tests included).
  Nothing in Phase 2.0 makes a network request; the visual rung is never enabled for production.
- No statement-specific hardcodes — now in `ocr/` too (OQ2). Institution furniture must be declared
  and justified as intake behavior with fixtures, never discovered.

## Hard exclusions (Phase 2.0)
PaddleOCR · Phase 2.1 · geometry coverage work · Phase 2.2 experiments · Unlimited OCR enablement ·
Phase 2.3 · Trigger T live routing · Phase 2.4 · paid/cloud OCR · RunPod automatic fallback ·
PP-Structure as truth · character-level fusion · confidence-based arbitration · new bank parsers ·
deterministic parser expansion · candidate auto-adoption · validator-picked candidates · distributed
OCR workers · Kubernetes · unrelated product features. A future-phase prerequisite you discover is
DOCUMENTED in your W3 section and left unbuilt.

## Proof floor per Phase-2 cell
The batch-9 floor per branch, unchanged (full default suite; the 5 canonical guards; the 7 canonical
conformance files; `python corpus_gate.py` GREEN; `cohort_replay` at base with `--expect-identical`
and at closure over your named cohort; privacy scan 0; message scan 0) PLUS:
- a **mutation table** for every gate, router edge, charset, allowlist or selection rule you add —
  every mutant applied as documented, every killer named; prefer tests that prove the ABSENCE of a
  forbidden edge over happy-path tests;
- **architectural tripwires** where your card names them (AST/import guards, signature guards),
  because comments and discipline do not count as enforcement;
- **`newly validated = 0`** and **`previously validated preserved = all, payload identical`** — every
  Phase-2.0 cell is a hygiene card under the batch-9 report contract;
- for cells that touch the intake ladder or cache keys: the cohort replay proves the OFFLINE partition
  byte-identical; the visual partition has no baseline and must remain EMPTY (no artifact written).

## Cohort replay under Phase 2.0
`tools/cohort_replay.py` replays from the batch-9 run of record (`--run` defaults to the train-8 pointer
— pass the batch-9 run directory EXPLICITLY) against `.claude/recovery/webapp_data_train9_cold`
(`--data-dir`). Cell P20-ARTIFACTS changes its artifact selection; until that composes, the other cells
replay with the tool as it stands, which is correct on this cache by measurement (one artifact per
input, both stages).

## Report contract
BATCH9-RULES' contract, with Phase-2 additions: `failure-class evidence` (which of A/B/C your change
touches and the test that proves the forbidden edges are absent) and `escalation evidence` (legal
escalation population, illegal-escalation checks) where your card names them. Never summarise a cell
as green on a net count.

## Host and git
As BATCH9-RULES: `tasklist` before a heavy proof, one harness at a time, detached Git-bash for long
runs with an `EXIT=` line, OneDrive `PermissionError`s retried, caches read-only, W3 section appended
with its own `# §<CARD> — …` heading, commit messages in CLASSES not instances, never merge or push.
Python on this host is 3.14.5; CI pins 3.12 — write for both (no 3.13+-only APIs).
