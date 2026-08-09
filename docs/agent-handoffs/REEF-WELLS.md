# Agent Handoff — REEF-WELLS

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-WELLS · Track A cell 5 — the wells_fargo withheld family
- **Task:** `wells_fargo × {period_integrity 22, detail_coverage 13, balance_continuity 5}` — 40 documents.

# Git ownership
- **Base:** `5443cfa` · **Branch:** `wave3-wells-completeness` · **Worktree:** `.claude/worktrees/mt-wells`. Commit only there; never merge; never push.

# Context
Read in-tree, in order: `PROJECT_STATUS.md`, `WAVE2_EXECUTION_LOG.md` (all rulings; you are held to the Track A standard: improved-only, zero regressions — four cells have hit it), `W3_2_TAXONOMY.md`, `W3_TRACKA_LOG.md` (§1 Chase, §TD, §5 RBC, §GROUPER, §BOFA — method and traps; the recurring lesson: the diagnosis class is a SYMPTOM; TD's was direction, RBC's was signs, BofA's was pre-flattened grids).
- **Baseline (your "before"):** run `70123cf2` (`discovery_reports/2026-08-09T002648…-70123cf2/`, gitignored, main checkout): validated 1,533 / withheld 147. Derive your cell exactly (telemetry diagnostics × rows.csv, `parser_id == "wells_fargo"`); report your count (expect ≈40: 22 period_integrity + 13 detail_coverage + 5 balance_continuity).
- Wells history you must know: R-1 removed `_infer_year` defaulting to 2026 (no fabricated years — period evidence only); W3-2's class table says period_integrity dominates — 22 docs where the statement PERIOD itself cannot be established. Suspect the period-extraction capability first; a missing/differently-printed period line makes every downstream check fail. `analysis/tables.py` now provides `group_rows` (promoted, byte-identical) — you MAY consume it as Chase/TD/RBC do, but may NOT modify it (stop condition).

# Scope
- **Allowed:** `analysis/wells.py`; tests (suggest `tests/test_wells_variants.py`); `W3_TRACKA_LOG.md` (append §WELLS); audit CSVs ONLY inside an approved re-baseline ceremony.
- **Protected:** all shared utilities (consume-only), all other parsers, pipeline/registry, financial core, ocr/, webapp/, discovery/, telemetry/, corpus_gate.py, audit scripts, .github/, corpus PDFs.

# Engineering requirements
Track A discipline verbatim: instrument first (find what Wells prints and asserts about itself — summary totals, period lines, daily balance sections; validate the instrument against already-validated wells docs before trusting it); characterize families structurally via read-only archive sampling (sensitive: synthetic fixtures only, aggregate reporting only); root-cause; capability-level fixes keyed on structure (zero customer/date/amount constants — and specifically ZERO year literals; period evidence only, the R-1 rule); fail closed with documented volume where printed evidence is insufficient; preserve every currently-validated wells document byte-identically (192+ validated). Cache: `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge.

# Validation
Per-family fixtures both directions; full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN (byte-identical unless ceremony-approved); guards green; honest cell measurement before → after by class.

# Stop conditions
Shared-utility modification needs; pinned truth-set movement (formal ceremony only); materially wrong diagnosis; geometry-only families (report volume); shared-machinery defects; any temptation to infer a period the document does not print.

# Definition of done
Families characterized + ruled in §WELLS; capability-level fixes fixture-proven; zero regressions; all proofs green with exit codes pasted; honest measurement; clean tree.

# Final report to Ocean
Root cause per family; approach; files changed; verbatim proofs; before/after by class; commit list; risks; unresolved questions.
