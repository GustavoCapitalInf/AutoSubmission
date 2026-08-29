# Agent Handoff — DECL-HUNTINGTON (batch 9, 9A-1 card 1, coverage)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Identity
The 12 documents the `huntington` reader (`analysis/huntington.py`, 710 lines, registration
`huntington` / "Huntington National Bank") CLAIMS at detection (required markers only, score
exactly 0.5) and DECLINES in `parse` — `failed / parser_declined`, all native text, 3–10
pages, every one filed under the `Huntington Bank` folder, and every one already declined in
the batch-7 control run (this is not a batch-8 artefact). Census group `DECL:huntington`
(sha16 list in `census_batch9/clusters.json`; per-sha facts in `per_sha.csv`). The reader's
baseline cohort is 38 validated documents, 0 withheld, 0 review — every one protected.

# What is already known (characterise before code)
- W3 / WAVE2 (batch 7 train): huntington `:662` refuses ×4 as an HONEST L-1 refusal — a
  line-of-credit / overdraft-protection account printed with its own summary, advances,
  payments and daily-balance table on the same statement (`_LINE_OF_CREDIT_RE` → `return
  None`), because the single-account schema cannot publish one account and silently drop the
  other. Those documents are NOT this card's to widen: the L-1 ruling is being investigated
  separately (card `L1-CU-SUFFIX-INVESTIGATION`). Name them by sha and leave them declined.
- The reader validates four printed identities (summary, per-direction subtotals, service
  charges, `Balance Activity`) and returns None if any misses — the safety argument. Widening
  never weakens any of the four; a decline whose root cause is "one of the four does not
  close on this document" is a document finding, not a grammar gap.

# Method
1. **Decline probe** (read-only instrument, commit it as `tools/huntington_decline_probe.py`):
   for each of the 12, run the reader's stages on the cached text (`cohort_replay`'s cache
   access pattern; text never leaves the tool) and record WHICH gate returned None — the
   L-1 refusal, `_period`, `_summary`, a section grammar, one of the four identities — as a
   per-sha table of gate NAMES (no values). Classify: (a) L-1 refusal → out of scope, named;
   (b) grammar gap on a shape ≥ 2 documents share → in scope; (c) a document whose own
   arithmetic does not close → stays declined, named.
2. **Widen only the shared shapes** found in (b): label drift, a section the grammar does not
   know, a continuation form, a period wording — as structural capability (no literals that
   name a customer, an amount, a date or an account). Every widening keeps the four identities
   mandatory.
3. Proofs per BATCH9-RULES: `cohort_replay --group DECL:huntington` (target) and
   `cohort_replay --parser huntington` (38 protected) at base (`--expect-identical`) and at
   every closure tree — preserved 38/38 with identical payloads, or a named, proven-correct
   leaf change; a mutation table for every grammar you touch (`tools/huntington_mutation_table.py`);
   privacy scan of added lines against the 50-document population (0); canonical guards,
   conformance, suite, corpus gate; the archive sweep at your final tree.
4. WELCH-PRINTED-ROWS is NOT here (it is folded into CP-DECLINES sub-card B).

# Expected movement
`DECL:huntington`: ≥ 1 newly validated (the estimate was 6–10 before the L-1 split; report
the measured split); the 4 L-1 refusals stay declined and are named; nothing else in the
archive moves. `previously validated preserved = 38/38`, `regressions = 0` — or the card is
not done.

# Git ownership
Base `train9` at launch (Ocean names the commit). Branch `wave9-huntington`, worktree
`.claude/worktrees/mt9-huntington`. Own: `analysis/huntington.py`, `tests/test_huntington*.py`,
`tools/huntington_*.py`, W3 `§HUNT9` (append-only). No registry change unless a new
registration is the honest answer (then pins in the same commit + a stratified non-target probe
≥ 400 documents); no version bump (Ocean's at the train).

# Report
BATCH9-RULES contract: population 12 | root cause (the gate table by class) | solution |
newly validated (by sha) | other ladder movement | previously validated preserved 38/38 |
regressions 0 | correctness evidence (identities still mandatory; mutation table; leaf diffs)
| generalization evidence (the widened shape and how many documents share it); commits;
proof-floor exits; privacy count; risks last.
