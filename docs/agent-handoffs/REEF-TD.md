# Agent Handoff — REEF-TD

Read this entire file before doing anything. It is your complete brief; you
have no other conversational context and need none. When it says "stop and
return to Ocean," you end your work and write your final report — Ocean (the
lead session) reviews and merges; you never do.

# Identity
- **Agent name:** REEF-TD
- **Role:** parser variant-completeness engineer (REEF subsystem — extraction)
- **Task ID:** W3 Track A, cell 2 — `td_canada_native × detail_coverage`

# Git ownership
- **Base commit:** `d775bbe` ("cache: ANALYSIS_STAGE_VERSION 1->2")
- **Branch:** `wave3-td-completeness` (already created, checked out here)
- **Worktree:** `.claude/worktrees/mt-td` (you are inside it)
- You may commit ONLY to this branch. Small, reviewable commits. **Never
  merge to main. Never push.** Ocean is the only merge authority.

# Context
- Read in-tree, in order: `docs/moneythumb-replacement/PROJECT_STATUS.md`,
  `WAVE2_EXECUTION_LOG.md` (all Ocean/Gustavo rulings — binding),
  `DISCOVERY_COMBINED_REPORT.md`, `W3_2_TAXONOMY.md`, `W3_TRACKA_LOG.md`
  (the Chase cell that sets your standard: 12 layout families, 0→300
  validated, first approved truth-set re-baseline).
- **Why this work exists:** discovery over the frozen 3,506-document archive
  showed 614 claimed-but-withheld documents. Cell 1 (chase) is done:
  official movement improved 300 / regressed 0 (baseline run `1dfaf7e9` →
  post run `c3e557f0`; validated coverage 31.0% → 39.9%). Your cell is next
  by evidence rank: **`td_canada_native × detail_coverage` — 61 documents**
  whose extracted rows fall short of the statement's own stated totals
  (debit coverage short 61/61, credit 59/61; running-balance checks pass —
  reconnaissance says this cell RESEMBLES the Chase shape, unlike RBC).
- **Baseline numbers (your "before"):** run `c3e557f0`
  (`discovery_reports/2026-08-07T181317…-c3e557f0/`, gitignored, main
  checkout): validated 1,348 / withheld 331 / distinct docs 3,379. Your
  cell's documents are identified by joining that run's telemetry
  diagnostics with rows.csv parser attribution (`parser_id ==
  "td_canada_native"`, class `detail_coverage`).
- **Binding architectural rulings that constrain you:** fail closed, never
  fabricate; the discovery corpus is EVIDENCE, not a target to force; the
  corpus gate is the merge authority; truth-set values move only through
  the formal re-baseline ceremony (see below); capability-level fixes only.

# Scope
- **Objective:** eliminate the extraction-completeness gap for TD Canada
  native-path layout variants so that documents whose printed evidence
  supports full extraction validate, and the rest fail closed with accurate
  diagnostics. Work at the layout-family level using the Chase-cell method:
  (1) characterize families structurally (read-only sampling of the cell's
  archive documents), (2) root-cause per family, (3) capability-level fix
  or documented fail-closed-by-design, (4) prove, (5) measure the cell.
- **Allowed files:** `analysis/td_can.py`; new/updated tests (suggest
  `tests/test_td_can_native_variants.py` + additions where TD tests live);
  `docs/moneythumb-replacement/W3_TRACKA_LOG.md` (append your §TD
  inventory-and-ruling record); `docs/adb-audit-results.csv` +
  `docs/adb-forensic-audit.md` ONLY inside an Ocean-approved re-baseline
  ceremony (see Stop conditions).
- **Protected (do not touch):** `analysis/tables.py`, `analysis/money.py`,
  `analysis/date_tokens.py` (shared utilities — if a fix genuinely belongs
  there, STOP and propose; the Chase row-grouper promotion decision is
  deliberately deferred to Ocean), `analysis/chase.py`, `analysis/rbc.py`
  (a parallel agent may own it), `analysis/pipeline.py`,
  `analysis/parser_registry*.py`, `analysis/adb.py`, `reconcile.py`,
  `metrics.py`, `transaction_classifier.py`, `serialization.py`, `ocr/`,
  `webapp/` (including `webapp/artifact_cache.py` — stage-version handling
  is Ocean's, see Engineering requirements), `discovery/`, `telemetry/`,
  `corpus_gate.py`, audit scripts, `.github/`, the corpus PDFs.
- **Out of scope:** RBC (parallel cell), detection/dispatch changes (the
  registry is settled), any statement-specific repair, tranche runs over
  the archive (Ocean runs measurements; you measure your cell only).

# Engineering requirements
- **Capability-level fixes only.** Rules fire on structure (section
  headings, column geometry of the text layout, stated-count/total checks),
  never on memorized content. **Zero customer names, dates, amounts,
  account fragments, or corpus-fitted constants** — the layer-wide guard
  test (`test_removed_literals_stay_removed_anywhere_in_analysis`) and the
  no-hardcodes guards must stay green.
- **Fail closed:** a family that cannot be completely extracted stays
  withheld — document it as fail-closed-by-design with its volume. Never
  loosen validation to increase coverage. Preserve already-correct
  statements: the 6 corpus TD Canada documents (claimed via
  `td_canada_native`) must produce byte-identical outputs unless a
  truth-set defect is proven (ceremony path).
- **Sensitive data:** archive documents are read-only diagnosis material in
  the MAIN checkout's `Bank Statements/` — never copy/move/modify/commit
  them; committed fixtures are SYNTHETIC (invented institutions/amounts)
  reproducing structural shapes; reports carry aggregates and structure
  descriptions only.
- **Cache/stage-version implication:** if your fixes change analysis output
  for unchanged settings (they will, for your cell), note in your report
  that `ANALYSIS_STAGE_VERSION` must be bumped at merge — do NOT bump it
  yourself (webapp/ is protected for you); Ocean owns the bump, as done for
  Cell 1.

# Validation
- **Required tests:** per-family synthetic fixtures (fails-before /
  passes-after, plus negative fixtures proving the rule keys on structure);
  the full default suite green; existing TD tests untouched in their
  assertions unless a delta is documented and justified.
- **Required corpus-marked proof:** `set -o pipefail; python -m pytest -m corpus -q`
  green in this worktree, AND `python corpus_gate.py` GREEN — byte-identical
  unless the ceremony was approved and executed.
- **Required measurement (your cell, before/after):** re-run your cell's
  documents (read-only, via `analyze_markdown` locally — see
  W3_TRACKA_LOG §measurement for the Chase pattern) and report the outcome
  distribution before → after with per-family attribution. Ocean runs the
  authoritative archive-wide movement measurement after merge; your numbers
  are the preview and must be honest ("X of 61 validate, Y remain withheld
  because Z" is the required shape).
- **Regression expectations:** zero movement outside your cell; corpus
  gate 106/3 with the same three withheld; guard suites green.

# Stop conditions — return to Ocean instead of deciding yourself
1. Any fix that wants to live in a shared utility (`tables.py`, `money.py`,
   `date_tokens.py`) or reuse/promote Chase's row grouper.
2. **Any pinned truth-set value moves** (gate red on a TD corpus document):
   STOP, assemble the evidence (independent oracle — e.g. the document's
   own printed daily-balance or summary sections — before/after field
   table), and request the formal re-baseline ceremony. Never silently
   update expected values; never regenerate the CSVs without approval.
3. Any change that would touch a protected file or another parser.
4. Evidence that the cell's diagnosis is wrong at scale (e.g. most of the
   61 are actually a different failure class) — report, don't improvise.
5. A defect discovered in shared machinery (money/date/table parsing) —
   report with a minimal reproduction.

# Definition of done
- Every layout family in the cell characterized, with a ruling each
  (fixed / fail-closed-by-design), recorded in W3_TRACKA_LOG §TD.
- All fixes capability-level, fixture-proven both directions.
- Full suite + corpus-marked selection + corpus gate green in this
  worktree (pipefail, explicit exit codes pasted).
- Cell measurement reported honestly, before → after.
- No shared-utility edits, no re-baseline performed without ceremony
  approval, no literals introduced (guards green).
- Final report delivered (below) and the branch left clean at your last
  commit.

# Final handoff back to Ocean
End your session by writing your report (in the terminal response AND
appended to W3_TRACKA_LOG §TD) containing:
- root cause(s) per layout family
- approach per family (fix vs fail-closed, and why)
- files changed (exact list; expect: td_can.py + tests + log)
- tests/proofs verbatim (suite tail, corpus-marked tail, gate summary
  block, guard suites) with exit codes
- before/after cell measurement (61-doc outcome distribution)
- commit hash list (oldest first)
- risks (what could regress, what you could not verify)
- unresolved questions for Ocean (including any stop-condition items)
