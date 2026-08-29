# Agent Handoff — DECL-COMMUNITY-SECTION (batch 9, 9A-1 card 4, coverage)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The 9 native documents the `community_section` reader (`analysis/community_section.py`, 990
lines, registration `community_section` / "Core Statement Platform" — the sectioned core
family, the largest platform reader) claims at detection (score 0.5) and declines in `parse`
(`failed / parser_declined`; folders Rogue Credit Union 3, Chase 2, Unidentified 4; all
already declined in the batch-7 control run). Baseline cohort protected: 59 validated +
2 review (`missing_declared_statement_page`, owned by the RV-PAGE-COVERAGE probe — leave
them). Census group `DECL:community_section`.

# What is already known
WAVE2 (batch 7 train) names community_section `:896` ×7 as HONEST L-1 refusals — a second
ACTIVE deposit account on the statement, which the single-account schema cannot publish
without silently dropping one account. Those are out of scope until the L-1 ruling (card
`L1-CU-SUFFIX-INVESTIGATION`): name them by sha and leave them declined. That leaves ≈ 2
candidates — so this card is FIRST a measurement (the decline probe) and only then a
widening, and only if the probe finds a shape shared by ≥ 2 documents. A widening for one
document is not a rule; if the probe finds nothing shared, the honest deliverable is the
probe, the table and a closed card with `newly validated = 0` — say so plainly.

# Method
1. Decline probe (`tools/commsec_decline_probe.py`): gate names per sha, classified L-1 /
   grammar gap / document defect.
2. If a shared gap exists: widen as structural capability; the platform's printed identities
   (`Statement Ending`, the summary block, the section subtotals, the daily-balance grid
   WITHHELD-GRIDS reads) stay mandatory; the one-account rule stays exactly as ruled.
3. Proofs per BATCH9-RULES: `cohort_replay --group DECL:community_section` (target) and
   `--parser community_section` (61 protected, incl. the 2 review) at base and closure —
   WITHHELD-GRIDS' running-balance leaves must stay identical; mutation table; privacy scan
   against the 70-document population (0); guards, conformance, suite, corpus gate; the
   archive sweep at your final tree (a platform reader change reaches every document it
   claims).

# Expected movement
0–2 newly validated (report the measured split); the 7 L-1 refusals named and unchanged;
59/59 validated preserved, 2/2 review unchanged; `regressions = 0`.

# Git ownership
Base `train9` at launch (Ocean names the commit). Branch `wave9-commsec`, worktree
`.claude/worktrees/mt9-commsec`. Own: `analysis/community_section.py`,
`tests/test_community_section*.py`, `tools/commsec_*.py`, W3 `§COMMSEC9` (append-only).

# Report
BATCH9-RULES contract; the gate table by class is the primary deliverable.
