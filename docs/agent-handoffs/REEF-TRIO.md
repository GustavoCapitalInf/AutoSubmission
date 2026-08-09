# Agent Handoff — REEF-TRIO

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-TRIO · Track A cells 6–8, sequential
- **Task:** three cells in strict order, each fully proven before the next:
  1. `us_bank × {summary_identity 20, ledger_identity 2}` — 22 docs
  2. `truist × {detail_coverage 12, ledger_identity 8}` — 20 docs
  3. `pnc × {detail_coverage 14, ledger_identity 2}` — 16 docs
  Finishing only cell 1 (or 1+2) at full standard beats rushing all three.

# Git ownership
- **Base:** `5443cfa` · **Branch:** `wave3-trio-completeness` · **Worktree:** `.claude/worktrees/mt-trio`. Commit only there; never merge; never push.

# Context
Read in-tree, in order: `PROJECT_STATUS.md`, `WAVE2_EXECUTION_LOG.md` (rulings; the Track A standard: improved-only, zero regressions), `W3_2_TAXONOMY.md`, `W3_TRACKA_LOG.md` (all sections — the method; the recurring lesson: diagnosis classes are symptoms — direction (TD), signs (RBC), pre-flattened grids (BofA); us_bank's `summary_identity` class likely means the bank-stated summary fails ITS OWN identity as extracted — suspect summary-extraction capability, not the ledger).
- **Baseline:** run `70123cf2` (main checkout, gitignored): validated 1,533 / withheld 147. Derive each cell exactly from telemetry × rows.csv before working it; report counts.
- us_bank history: W3-1 fixed its AttributeError crash cluster (optional "Interest Earned this Period" line) — 36 docs recovered, 16 validated / 20 withheld; your cell 1 likely overlaps those 20. `analysis/tables.py` provides `group_rows` — consume-only.

# Scope
- **Allowed:** `analysis/us_bank.py`, `analysis/truist.py`, `analysis/pnc.py` (each ONLY during its cell); tests per parser; `W3_TRACKA_LOG.md` (append §TRIO with one subsection per cell); audit CSVs ONLY inside an approved re-baseline ceremony.
- **Protected:** shared utilities (consume-only; a PARALLEL agent owns wells.py — never touch it), all other parsers, pipeline/registry, financial core, ocr/, webapp/, discovery/, telemetry/, corpus_gate.py, audit scripts, .github/, corpus PDFs.

# Engineering requirements
Track A discipline verbatim per cell: instrument first (each bank's own printed self-assertions, validated against its already-validated population before use); structural family characterization via read-only archive sampling (synthetic fixtures only, aggregates only); root-cause; capability-level fixes (zero customer/date/amount constants; guards green); fail closed with documented volume; preserve every currently-validated document of each parser byte-identically. `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge.

# Validation (per cell, before moving on)
Family fixtures both directions; full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN byte-identical (unless ceremony); guards; honest per-cell measurement before → after by class.

# Stop conditions
Shared-utility needs; truth-set movement (formal ceremony only); materially wrong diagnosis; geometry-only families; shared-machinery defects; budget pressure (stop cleanly at a completed cell rather than degrade the standard).

# Definition of done
Each attempted cell fully characterized/ruled/proven/measured in §TRIO; zero regressions anywhere; all proofs green with exit codes; clean tree; explicit statement of which cells were completed vs handed back.

# Final report to Ocean
Per completed cell: root causes per family, approach, before/after by class. Plus: files changed; verbatim proofs; commit list; risks; unresolved questions; unworked-cell handoff notes.
