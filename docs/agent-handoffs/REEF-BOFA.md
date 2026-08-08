# Agent Handoff — REEF-BOFA

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-BOFA · Track A cell 4 — the bank_of_america withheld family
- **Task:** `bank_of_america × {detail_coverage 30, ledger_identity 25, posting_date_coverage 15}` — 70 documents, the dominant remaining withheld family.

# Git ownership
- **Base:** `e614fcc` · **Branch:** `wave3-bofa-completeness` · **Worktree:** `.claude/worktrees/mt-bofa` (you are inside it). Commit only to this branch; never merge to main; never push.

# Context
Read in-tree, in order: `PROJECT_STATUS.md`, `WAVE2_EXECUTION_LOG.md` (all rulings; the 2026-08-08 entry has your cell table and the movement standard you are held to: improved-only, zero regressions), `W3_2_TAXONOMY.md`, `W3_TRACKA_LOG.md` (§1 Chase, §TD, §5 RBC — the method and the traps; note TD's direction-loss and RBC's sign-inversion findings: "detail_coverage" is a symptom class, the cause may be one level down).
- **Baseline (your "before"):** run `7a98b6cd` (`discovery_reports/2026-08-08T213201…-7a98b6cd/`, gitignored, main checkout): validated 1,462 / withheld 217. Your cell: telemetry diagnostics joined to rows.csv attribution, `parser_id == "bank_of_america"` — expect ≈70 docs across the three classes (re-derive exactly; report your count).
- Prior bofa history: W3-1 fixed a ValueError crash cluster (16 docs) via shared `iso_or_none`; bofa validates 291+ docs already — **those must not regress.**

# Scope
- **Allowed:** `analysis/bofa.py`; tests (suggest `tests/test_bofa_variants.py` + existing additions); `W3_TRACKA_LOG.md` (append §BOFA); audit CSVs ONLY inside an approved re-baseline ceremony.
- **Protected:** shared utilities (`tables.py` is being refactored by a PARALLEL agent — absolutely no edits; if your fix wants shared code, STOP and report), all other parsers, pipeline/registry, financial core, ocr/, webapp/, discovery/, telemetry/, corpus_gate.py, audit scripts, .github/, corpus PDFs.

# Engineering requirements
Same discipline that produced Chase/TD/RBC: characterize layout families structurally (read-only archive sampling; the archive is sensitive — synthetic fixtures only, aggregate reporting only, never copy/modify/commit archive files) → root-cause per family → capability-level fixes keyed on structure (zero customer/date/amount constants; guards must stay green) → fail closed where printed evidence is insufficient, with volume documented → build the in-document measurement instrument FIRST (BofA prints statement summaries; find the per-direction totals/counts the document itself asserts) → never loosen validation; preserve every currently-validated bofa document byte-identically.
Cache: your fixes change analysis output → `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge; do not touch webapp/.

# Validation
Per-family synthetic fixtures both directions; full default suite; `set -o pipefail; python -m pytest -m corpus -q` green; `python corpus_gate.py` GREEN (byte-identical unless a ceremony is approved); guard suites green; honest cell measurement before → after ("X of 70 validate, Y remain withheld because Z"), including the three classes separately.

# Stop conditions
Shared-utility needs (esp. anything the grouper-promotion agent owns); any pinned truth-set movement (assemble independent-oracle evidence, request the formal ceremony — never silently update); evidence the diagnosis is materially wrong; geometry-only families (report volume, don't force); defects in shared machinery.

# Definition of done
Every family characterized with a ruling in §BOFA; fixes capability-level and fixture-proven; zero regressions on validated bofa docs; all proofs green with exit codes pasted; honest measurement; clean tree.

# Final report to Ocean
Root cause per family; approach; files changed; verbatim proofs; before/after by class; commit list; risks; unresolved questions (incl. any stop-condition items).
