# Agent Handoff — TABLES-GRID-BALANCE (batch 9, shared-helper correctness; found by WH-ROW-CAPTURE)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds. Ocean reviews and composes; you never merge or push.

# Finding (W3 §ROWCAP, carried concern 1)
`analysis/tables.py:read_grid_rows` takes a money cell that OPENS a physical line as the
PREVIOUS row's BALANCE. It is the mechanism behind the six RBC withheld documents
(`WH:rbc`: captured magnitudes 0.739–0.999 of the bank's printed credit + debit pair — cells the
text layer lost or merged, then mis-assigned by the helper) and the helper is shared with
`analysis/cibc.py`. WH-ROW-CAPTURE did not touch it (outside its ownership; a shared helper is not
changed through a reader). `tools/rowcap_ceiling.py --mode wrapped_amount` is the committed
measurement to start from — it moves four of the six and validates none, overshooting on three,
so the helper fix alone may not close the RBC six; measure before promising.

# Method
1. Characterise the helper's contract on the cached text of every document that reaches it
   (rbc 159 validated + 6 withheld + 1 declined; cibc's cohort; any other caller — `git grep
   read_grid_rows`): where a physical line opens with a money cell, what the bank printed there
   (a balance continuation? a wrapped amount? a new row?) — shapes only, counted.
2. Fix the helper so a line-opening money cell is assigned by PRINTED structure (column position
   from the header, or the row's own date), never by adjacency — fail closed (refuse the row and
   let the identities decline) when the structure does not decide.
3. Proofs per BATCH9-RULES: `cohort_replay --parser rbc --parser cibc --parser cibc_french` and
   every other caller's registrations at base (`--expect-identical`) and at closure — preserved
   with identical payloads or a named, proven-correct leaf change (the CAD-pinned surfaces must not
   move); `--group WH:rbc --group DECL:rbc --group DECL:cibc_french` (targets); mutation table;
   privacy and message scans; the archive sweep at the final tree (a shared helper reaches every
   caller).

# Git ownership
Base `train9` at launch. Branch `wave9-tablesgrid`, worktree `.claude/worktrees/mt9-tablesgrid`.
Own: `analysis/tables.py`, its tests, `tools/tablesgrid_*.py`, W3 `§TABLESGRID`. Readers untouched.

# Report
BATCH9-RULES contract; per caller preserved n/n; newly validated by sha (the RBC six that close, if
any) or the measured ceiling saying why not.
