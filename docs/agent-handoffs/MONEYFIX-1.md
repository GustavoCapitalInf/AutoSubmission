# Agent Handoff — MONEYFIX-1

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. Three parser-local money-grammar
cards, all fuzzer-evidenced (F-MONEYFMT report, reproducers in the wave
scratchpad: repro_moneyfmt.py — run it first to see all three live).

# Identity
- **Agent:** MONEYFIX-1 · attested money-grammar fixes: rbc totals rows,
  truist summary rows, capital_one unguarded scrub.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-moneyfix-1`
  · **Worktree:** `.claude/worktrees/mt-moneyfix`.

# Card R — rbc: the total rows refuse the currency symbol (P1)
`analysis/rbc.py:399,403`: `Total deposits & credits \((\d+)\)\s*\+?\s*
([\d,]+\.\d{2})` (and the debits sibling) admit no `$`, while the balance
rows of the SAME printed block at `:393,396` do (`-?\$?[\d,]+\.\d{2}`).
A statement printing `$` on the total rows loses stated_total_credits,
stated_total_debits, stated_credit_count AND stated_debit_count silently:
summary_ok None → identity check skipped → coverage skipped → approved with
summary_totals_reliable=True. Fix: admit the same money syntax the block's
balance rows already admit — reuse, not new grammar. Fixtures: `$`-bearing
total rows parse; a deliberate mismatch on a `$`-bearing total is CAUGHT
(proves the oracle is live again); `$`-less statements byte-identical.

# Card T — truist: `_DOLLAR` not applied where its docstring says (P2)
`analysis/truist.py:31-33`: the three Account-summary activity rows
(`Checks\s+-\s+...` etc.) omit `_DOLLAR` (defined `:22` with a docstring
claiming every money pattern admits it). Truist prints the currency symbol
as its own cell (module's own note `:16`, 20 archive documents; the W3 F1
fix repaired the identical defect one function away). Today it fails
closed (whole parse None). Fix: apply `_DOLLAR` as documented. Fixtures
both ways. This may recover some of the 3 truist class-1 declines — check
them (manifest class1_truist in the wave-manifests scratch dir; main
checkout run 6893a75b read-only) and report per-document outcomes.

# Card C — capital_one: unguarded digit scrub (P1)
`analysis/capital_one.py:15`: `parse_digit_scrubbed(value, parens=True,
trailing_minus=True)` with no `guard=` and no `leading_minus=True` —
`money.py:132-135` documents guard as existing precisely to stop misreading
reference numbers as amounts. Evidenced: 'Page 3 of 8' → 38.0,
'REF#000000012345' → 12345.0, '-$1,234.56' → +1234.56 (sign dropped).
Fix: pass guard= and leading_minus=True the way `chase.py:25-27` already
does — reuse the codebase's own correct call. Fixtures: each hostile cell
refuses; real capital_one shapes unchanged.

# Hard rules
- These three files ONLY: `analysis/rbc.py`, `analysis/truist.py`,
  `analysis/capital_one.py` + tests + `W3_TRACKA_LOG.md` (append
  §MONEYFIX-1). Do NOT touch `analysis/money.py` (shared util — separate
  integration card), `analysis/chase.py` (owned by CHASE-CLOSURE),
  pipeline/reconcile/count_semantics, or anything else.
- No grammar WIDENING beyond what each card's printed evidence attests.
  Structural reuse of each module's own existing signed pattern where one
  exists; no speculative formats.
- Per-parser before/after sweeps over each parser's ENTIRE claimed
  population in run 6893a75b (rbc ~153, truist ~48, capital_one ~10-12
  distinct — derive exact sets): byte-identical EXCEPT documents genuinely
  exhibiting the fixed shape, each such mover individually named and
  explained. Card R may legitimately move stated fields from None to
  values; outcome classes must not regress anywhere.
- Pinned corpus: gate GREEN 106/3 byte-identical. If any audited field
  moves on a pinned document → STOP (ceremony is Gustavo's).

# Validation
Full default suite; corpus-marked; corpus_gate.py; guards; conformance
cross-product; the three sweeps; the truist decline re-checks. Exit codes
verbatim. ANALYSIS_STAGE_VERSION bump is Ocean's at merge.

# Final report to Ocean
Per card: verbatim diff, fixtures, sweep summary with named movers, proofs
with exit codes; commit list; risks; unresolved questions.
