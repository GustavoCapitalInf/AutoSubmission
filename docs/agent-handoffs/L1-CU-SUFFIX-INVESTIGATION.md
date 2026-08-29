# Agent Handoff — L1-CU-SUFFIX-INVESTIGATION (batch 9, READ-ONLY architecture / ruling investigation; no production change)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. This card changes NO production
file, registers nothing, and moves nothing. Its deliverable is a committed ruling packet.

# Why
The census's largest deterministic reservoir is `FAM-CU-SUFFIX-CORE`: 37 credit-union
statement families, 176 documents (`census_batch9/opportunity_estimates.json` lists the
groups; `clusters.json` the sha16s; `per_sha.csv` the per-sha facts), census yield 95.0,
potential +25 to +95 — GATED by the L-1 rule: the extraction schema carries ONE account per
statement (`analysis/schema.py`: `account_name`, `account_number`, one ledger); a reader may
skip a DORMANT sibling (symitar's two idle declarations, ratified batch 7) but must refuse a
statement on which TWO deposit accounts genuinely post, because publishing one and silently
dropping the other is a correctness defect. The same rule refuses ≈ 70 documents inside the
`DECL:*` groups (WAVE2 log, batch-7 escalation 1: huntington `:662` ×4 line-of-credit
sibling, community_section `:896` ×7, navy_federal `:127` ×4, capital_one ×6, consumers ×3)
and ATB's consolidated statements (`WH:atb`, coverage ≈ 10×). Gustavo's question, verbatim:
determine how many of the 176 actually share one structural family; what varies between
institutions; how accounts are separated in multi-account statements; whether account
boundaries can be established from explicit statement evidence; whether each account can be
reconstructed and validated independently; whether one shared parser architecture can cover
the family without institution-specific or statement-specific hardcodes; the expected safely
recoverable population; the regression surface; the exact fail-closed conditions. A large
engineering effort is acceptable if the solution is genuinely shared, evidence-driven,
preserves every previously validated statement, and keeps per-document inference cost zero.

# Method (deterministic where possible; every count from a committed instrument)
1. **Population**: the 176 CU shas + the ≈ 70 L-1 refusals (enumerate them by re-running the
   readers' refusal gates on the cached text — a committed probe `tools/l1_census.py`, gate
   names only) + `WH:atb` 2 + Space Coast (in the 176) + LILI's 3 named by batch 8. Read the
   batch-8 census family records (`CENSUS_BATCH8_DIGITAL.md`, sections 4, 8, 10, 13, 14, 15,
   21, 24, 25, 29, 31, 37–48, 52–56, 58, 61, 65, 66, 71 …) for the printed identities already
   established — then VERIFY them on the text, do not repeat them.
2. **Structural census** over the cached text (an instrument, `tools/l1_structure_census.py`,
   reporting SHAPES and counts, never values): per document — how many account/share
   sections print (the header shape: `Share ID / Suffix / Account`, `Summary of Accounts`
   roll-up, per-share `Previous Balance … New Balance` equations, per-share ledgers, a
   `Total` roll-up), whether each section prints its own opening/closing pair, its own
   counts/totals, its own ledger, its own daily balances; whether sections are delimited by
   explicit printed boundaries (a header line naming the share, a footer, a page form);
   whether a roll-up page states per-account balances that the sections must reproduce (an
   oracle for the partition). Group families by the SAME boundary + identity mechanics —
   that grouping is the "structural family" answer (expected: a few core processors —
   Symitar/Episys, Jack Henry, CU*BASE, Fiserv/XP2 — each with a consistent suffix grammar).
3. **Account separation and independent validation**: for each structural family, can every
   section be reconstructed as its own Statement (period, opening, closing, counts, totals,
   ledger, daily balances) and validated independently by the EXISTING deterministic
   validator (`reconcile` + ADB checks) with zero change to the validator? Prototype this
   READ-ONLY in a scratch tool (never registered, never imported by production — the
   `tests/test_experiments_are_not_wired.py` guard applies): split, reconstruct, run
   `reconcile`/ADB per section, count how many sections close, per family. That measured
   table is the "expected safely recoverable" answer — not an estimate.
4. **Publication model** (the ruling question): options with their exact fail-closed
   conditions — (A) refuse all multi-active (today); (B) publish ONE account under a
   printed, unambiguous PRIMARY rule (which printed evidence makes an account the primary —
   e.g. the only checking/draft share with member activity; the section the platform's own
   roll-up names first; a product name) with the omitted siblings SURFACED in the payload
   (the SIBLING-OMISSION-SURFACE design: `unpublished_sibling_sections`, an integrity
   NOTE); (C) a multi-account payload (schema change: `accounts: list[Statement]`, package
   math per account, the ADB per account, the webapp/report surfaces) — the largest change;
   (D) a hybrid: (C) internally, one declared primary externally. For each: what moves on
   the protected 2,596 (must be nothing), what the validator must refuse (ambiguous primary;
   a section that does not close; a roll-up that does not reproduce; an account whose
   currency differs), and the per-document cost (zero inference).
5. **Regression surface**: every reader that carries an L-1 refusal today, symitar's ratified
   skip rule, community_section's one-account rule, consumers (CONS-L1 ceremony), the
   pinned corpus (109; which pinned documents are multi-account), packages / the webapp
   surfaces if (C).
6. **Recommendation**: which option, which structural families first, the exact fail-closed
   conditions, the proof plan (cohort_replay populations, mutation tables, the archive
   sweep), the expected safely recoverable count per family FROM THE MEASURED TABLE, and
   what needs Gustavo's ruling before any code is written.

# Deliverable
`docs/moneythumb-replacement/L1_CU_SUFFIX_RULING_PACKET.md` (committed on your branch;
Ocean composes) with the measured tables (counts, shapes, gate names — never a printed
value, name, account number, amount or date; the privacy scan of your branch must be 0
against the whole population), the committed instruments under `tools/l1_*.py`, and the
report in the BATCH9-RULES contract shape (population | root cause | solution options |
expected safe gain (measured) | regression surface | fail-closed conditions | recommended
implementation). Read-only over archive and caches; $0.

# Git ownership
Base `train9` at launch. Branch `wave9-l1inv`, worktree `.claude/worktrees/mt9-l1inv`. Own:
the packet, `tools/l1_*.py`, W3 `§L1INV` (append-only). NO production change; NO
registration; NO test that imports the scratch prototype.
