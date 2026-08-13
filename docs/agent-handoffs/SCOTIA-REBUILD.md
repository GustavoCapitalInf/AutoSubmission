# Agent Handoff — SCOTIA-REBUILD

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. **Priority 1: scotiabank's
reconciliation is currently tautological — its validated documents are
certified by a check that re-derives the parser's own numbers.**

# Identity
- **Agent:** SCOTIA-REBUILD · restore the printed money cell as the amount
  of record in `analysis/scotia.py`, and the printed-vs-walk disagreement
  as a live, independent check.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-scotia`
  · **Worktree:** `.claude/worktrees/mt-scotia`.

# The measured defects (scout evidence; cohort = 80 distinct scotiabank docs)
1. **The tautology.** `analysis/scotia.py:113` sets
   `amount = round(balance - prev_balance, 2)` BEFORE reading the printed
   cell; `:114-118` looks like a guard but its body re-assigns the identical
   expression (dead branch); the printed amount (`values[-2]`) is discarded.
   Consequence: `sum_delta == 0.0` and `continuity_breaks == 0` on 80/80 BY
   CONSTRUCTION — the fail-closed gate lost independence. Measured: 11,174
   rows replayed, **615 divergent from the printed cell (512 in validated
   documents, 103 in withheld)**. Witnesses: `9EAD644B…` (16 rows, $98.00),
   `125127F3…` (9 rows, $25,922.30).
2. **Merchant-ref-as-balance.** Row assembly takes the last numeric token
   as the balance; an 11-digit merchant reference (`MRCH FIRST DATA
   CANADA(K)` continuation lines) becomes a balance in the tens of
   billions and amounts are back-solved from it (5 withheld docs incl.
   `125127F3…` dbt total $322,749,939,392.81 vs printed $31,652.49).
3. **Section discipline.** `_split_rows` (`:25-33`) splits the WHOLE
   document on dates: the `Deposit Interest` daily-yield ledger and
   `Service Charge` tables of the same PDF fabricate postings (2 docs,
   `9EAD644B…` 32 rows vs stated 4; zero-amount daily-balance rows).
4. **Zero-activity.** `:133-134` `if not txns: return None` declines a
   genuine printed `0 $0.00 0 $0.00` statement (1 doc, `90D94C41…`) — the
   same admissibility rule the Chase A′ card established: empty ledger
   admissible ONLY on printed zero-instances + balance agreement.
5. **Fail-closed remainders** (report volumes, do not force): the
   two-money-column flattened variant (3 docs — geometry class, native
   rung destroys column x-positions; goes to the geometry queue), and 7
   web-print `Account Details` documents (informal document class — a
   `formal_statement=False` registration question for Ocean, not parsing).

# THE PINNED-CORPUS QUESTION COMES FIRST (hard sequencing)
Before ANY production edit: identify every pinned-corpus scotiabank
document; replay the row loop on each; report whether restoring the
printed amount changes any AUDITED field (balance/ADB oracles) or any
published field on a pinned PASS document. **If audited values would move:
STOP and report — that is formal-ceremony territory and the decision is
Gustavo's.** If pinned docs are unaffected (their rows may be
non-divergent), proceed and say so with the replay numbers.

# Requirements
1. The printed money cell is the amount of record. The balance walk
   becomes what it must be: an independent cross-check whose disagreement
   is a live signal (reconciliation/withhold path), never silently
   resolved toward either side.
2. Rows are read from the `Account Details` section only (structural
   section bounds, not keyword blocklists); reference-number continuation
   lines cannot be balances (structural: the balance is the printed
   balance-column cell, with a plausibility relationship to its
   neighbors, not "last numeric token").
3. Zero-activity admissibility per the Chase A′ pattern, gated on the
   printed zero-count summary AND balance agreement.
4. Expect movement in BOTH directions and report it honestly: some
   currently-validated documents may become withheld when the printed
   cell disagrees with the walk (that is the check working — each such
   document individually named with its divergent rows); the ~29
   recoverable F1-class declines and the withheld back-solve docs should
   move up. Claimed-but-not-validated is not success.
5. Full sweeps: every one of the 80 cohort docs before/after,
   field-level, each difference explained by a named defect above. The
   detection surface must not move.

# Scope
- **Allowed:** `analysis/scotia.py`, tests (`tests/test_scotia_layouts.py`
  new + existing scotia tests), conformance fixture additions,
  `W3_TRACKA_LOG.md` (append §SCOTIA-REBUILD).
- **Protected:** everything else. count_semantics: scotiabank is
  COMPARABLE both directions — your rebuild must keep the stated-count
  fields' meaning (whole-direction printed figures); if it cannot, STOP.
  No registry machinery, no shared utils, no money.py (the U+2212 and
  parse_money issues are a separate integration card — consume what
  exists).

# Validation
Full default suite; corpus-marked; corpus_gate.py (see the pinned question
above — GREEN required unless you stopped); guards; conformance
cross-product; the 80-doc sweep; measurement preview vs 6893a75b. Exit
codes verbatim. Stage bump is Ocean's at merge.

# Final report to Ocean
Pinned-exposure replay FIRST; per-defect diffs; the 80-doc sweep with
every mover named and classified (up, down, and value-corrected-in-place);
proofs; commits; risks; unresolved questions.
