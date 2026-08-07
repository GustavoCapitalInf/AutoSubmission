# Agent Handoff — REEF-RBC

Read this entire file before doing anything. It is your complete brief; you
have no other conversational context and need none. When it says "stop and
return to Ocean," you end your work and write your final report — Ocean (the
lead session) reviews and merges; you never do.

# Identity
- **Agent name:** REEF-RBC
- **Role:** parser variant-completeness engineer (REEF subsystem — extraction)
- **Task ID:** W3 Track A, cell 3 — `rbc × detail_coverage`

# Git ownership
- **Base commit:** `d775bbe` ("cache: ANALYSIS_STAGE_VERSION 1->2")
- **Branch:** `wave3-rbc-completeness` (already created, checked out here)
- **Worktree:** `.claude/worktrees/mt-rbc` (you are inside it)
- You may commit ONLY to this branch. Small, reviewable commits. **Never
  merge to main. Never push.** Ocean is the only merge authority.

# Context
- Read in-tree, in order: `docs/moneythumb-replacement/PROJECT_STATUS.md`,
  `WAVE2_EXECUTION_LOG.md` (all Ocean/Gustavo rulings — binding),
  `DISCOVERY_COMBINED_REPORT.md`, `W3_2_TAXONOMY.md`, `W3_TRACKA_LOG.md`
  (the Chase cell that sets your standard: 12 layout families, 0→300
  validated, first approved truth-set re-baseline).
- **Why this work exists:** discovery over the frozen 3,506-document archive
  showed 614 claimed-but-withheld documents. Cell 1 (chase) is done
  (official movement improved 300 / regressed 0; validated coverage
  31.0% → 39.9%; baseline `1dfaf7e9` → post `c3e557f0`). Your cell:
  **`rbc × detail_coverage` — 48 documents.**
- **⚠️ THE DOCUMENTED TRAP (reconnaissance, W3_TRACKA_LOG §4 / execution
  log): your cell is NOT the Chase shape.** All 48 documents ALSO fail
  `running_balances_support_daily_ledger` and carry
  `integrity:running_balance_breaks` — because **RBC prints a running-
  balance COLUMN: a transaction row carries TWO money cells.** Any
  "the amount is the right-aligned/last money token" rule is
  underdetermined here and would read the balance column as the amount.
  **You must solve this structurally** — e.g., decide the amount-vs-
  balance column assignment from the balance-chain property (the column
  under which `balance[i] − balance[i−1] == amount[i]` holds across rows
  is the balance column), from column geometry, or from printed headers —
  never from per-statement rules, and never by assuming Chase's shape.
  Note the printed running balance is also an OPPORTUNITY: it is
  in-document evidence that can corroborate signs and completeness.
- **Baseline numbers (your "before"):** run `c3e557f0`
  (`discovery_reports/2026-08-07T181317…-c3e557f0/`, gitignored, main
  checkout): validated 1,348 / withheld 331 / distinct docs 3,379. Your
  cell's documents: telemetry diagnostics joined with parser attribution
  (`parser_id == "rbc"`, class `detail_coverage`); expect ≈48 minus any
  drift; also expect the related `balance_continuity × rbc` (18) cluster
  to interact with your work — measure it, but your objective is the
  detail_coverage cell (report balance_continuity movement as observed).
- **Binding rulings:** fail closed, never fabricate; discovery is evidence,
  not a target; the corpus gate is the merge authority; truth-set values
  move only through the formal re-baseline ceremony; capability-level
  fixes only. R-1 history note: rbc.py was already purged of hardcoded
  counterparty/sign literals in Wave 1 — printed-balance solving carries
  the weight; do not reintroduce merchant/sign lists.

# Scope
- **Objective:** eliminate the extraction-completeness gap for RBC layout
  variants — solving the dual-money-cell column assignment structurally —
  so documents whose printed evidence supports full extraction validate,
  and the rest fail closed with accurate diagnostics. Method: characterize
  families → root-cause → capability-level fix or fail-closed-by-design →
  prove → measure the cell.
- **Allowed files:** `analysis/rbc.py`; new/updated tests (suggest
  `tests/test_rbc_variants.py` + existing RBC test additions);
  `docs/moneythumb-replacement/W3_TRACKA_LOG.md` (append your §RBC record);
  `docs/adb-audit-results.csv` + `docs/adb-forensic-audit.md` ONLY inside
  an Ocean-approved re-baseline ceremony.
- **Protected (do not touch):** `analysis/tables.py`, `analysis/money.py`,
  `analysis/date_tokens.py` (shared utilities — if a fix belongs there,
  STOP and propose; the Chase row-grouper promotion is deferred to Ocean),
  `analysis/chase.py`, `analysis/td_can.py` (a parallel agent may own it —
  note rbc.py imports `_MONTHS` and `normalize_mojibake` from td_can:
  CONSUME them unchanged; if you need them to change, STOP), all other
  parsers, `analysis/pipeline.py`, `analysis/parser_registry*.py`, the
  protected financial core (`adb.py`, `reconcile.py`, `metrics.py`,
  `transaction_classifier.py`, `serialization.py`), `ocr/`, `webapp/`
  (stage-version bump is Ocean's at merge), `discovery/`, `telemetry/`,
  `corpus_gate.py`, audit scripts, `.github/`, corpus PDFs.
- **Out of scope:** TD Canada (parallel cell), detection/dispatch, any
  statement-specific repair, archive-wide runs (Ocean measures).

# Engineering requirements
- **Capability-level fixes only**; structure-keyed rules; **zero customer
  names, dates, amounts, account fragments, or corpus-fitted constants**
  (layer-wide literal guard + hardcode guards must stay green). The French
  RBC variant (`rbc_fr` registration shares this module) must keep working
  — its corpus document is pinned; treat French layouts as first-class
  families, not exceptions.
- **Fail closed:** unfixable families stay withheld, documented with
  volume. Never loosen validation. Preserve already-correct statements:
  the corpus RBC documents (4 English + 1 French claimed) must stay
  byte-identical unless a truth-set defect is proven (ceremony path).
- **Sensitive data:** archive is read-only diagnosis material in the MAIN
  checkout's `Bank Statements/`; synthetic fixtures only; aggregate
  reporting only.
- **Cache/stage-version:** your fixes change analysis output for unchanged
  settings → `ANALYSIS_STAGE_VERSION` bump happens at merge, by Ocean.
  Note it in your report; do not touch webapp/.

# Validation
- **Required tests:** per-family synthetic fixtures both directions,
  including explicit dual-money-cell fixtures (balance column correctly
  identified; a document where the naive last-money-token rule would
  misread must extract correctly — that fixture is mandatory); full
  default suite green.
- **Required corpus-marked proof:** `set -o pipefail; python -m pytest -m corpus -q`
  green in this worktree AND `python corpus_gate.py` GREEN — byte-identical
  unless a ceremony was approved and executed.
- **Required measurement:** your cell's documents before → after outcome
  distribution with per-family attribution, honest shape ("X of 48
  validate, Y remain withheld because Z"); report observed movement in
  `balance_continuity × rbc` (18) as a side effect, improved or not.
- **Regression expectations:** zero movement outside RBC; gate 106/3 same
  three withheld; guard suites green.

# Stop conditions — return to Ocean instead of deciding yourself
1. Any fix that wants shared-utility changes or Chase-grouper reuse.
2. Any change needed in `td_can.py` (the `_MONTHS`/`normalize_mojibake`
   imports) — a parallel agent may own that file.
3. **Any pinned truth-set value moves:** STOP, assemble independent-oracle
   evidence, request the formal re-baseline ceremony. Never silently
   update expectations.
4. The dual-money-cell solution requiring information the text layer does
   not carry (e.g., true column geometry available only from PDF word
   boxes) — report the evidence; the geometry input belongs to the
   structurer subsystem and wiring it into a parser is an architecture
   decision.
5. Evidence the cell's diagnosis is materially wrong; defects found in
   shared machinery.

# Definition of done
- Every layout family characterized with a ruling, recorded in
  W3_TRACKA_LOG §RBC; the dual-money-cell assignment solved structurally
  and adversarially tested.
- All fixes capability-level, fixture-proven both directions; French
  variant families intact.
- Full suite + corpus-marked + gate green here (pipefail, exit codes
  pasted); no shared-utility edits; no un-ceremonied re-baseline; guards
  green.
- Cell measurement reported honestly before → after (+ balance_continuity
  side observation).
- Final report delivered and branch clean at your last commit.

# Final handoff back to Ocean
End your session by writing your report (terminal response AND appended to
W3_TRACKA_LOG §RBC) containing:
- root cause(s) per layout family, with the dual-money-cell solution
  described precisely
- approach per family (fix vs fail-closed, and why)
- files changed (exact list; expect: rbc.py + tests + log)
- tests/proofs verbatim (suite tail, corpus-marked tail, gate summary,
  guard suites) with exit codes
- before/after cell measurement (48-doc distribution + balance_continuity
  observation)
- commit hash list (oldest first)
- risks
- unresolved questions for Ocean (including any stop-condition items)
