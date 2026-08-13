# Agent Handoff — STRUCTFIX-1

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. Three fuzzer-evidenced
false-validation cards (F-STRUCTURE report; live reproducers in the wave
scratchpad: repro.py — run it FIRST to see all three publish approved/clear
with wrong numbers).

# Identity
- **Agent:** STRUCTFIX-1 · false-validation fixes: pnc space-thousands +
  pnc phantom `.00` furniture row + bmo_ca_business English money pattern.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-structfix-1`
  · **Worktree:** `.claude/worktrees/mt-structfix`.

# Card P1 — pnc: space/NBSP thousands truncation (PRIORITY 1)
`analysis/pnc.py:50` `_SUMMARY_MONEY_RE`: the lookbehind `(?<![\d.,])`
omits space/NBSP and the integer part is optional, so `1 000.00` (or the
NBSP variant an OCR layer can emit) matches only `000.00`. Measured: both
balances shift by the same amount, every identity closes, publishes
approved/clear with beginning/ending/ADB all wrong by $1,000. Fix
structurally: the lookbehind must exclude the separator characters
`analysis/money.py` already surveys (`:17` lists space thousands;
`EITHER_MINUS_SPACED` `:214` exists for it), and the optional-integer
concession (there for reading a bare `.87`) must not be able to truncate a
thousands-bearing figure. Prove pre-fix failure in-process; fixture both
the space and NBSP variants plus the genuine bare-`.87` shape that
motivated the optionality (it must keep working).

# Card P2 — pnc: dated zero-amount furniture becomes a posting (PRIORITY 1)
`analysis/pnc.py:131`: the row regex accepts `\.\d{2}` (PNC genuinely
prints `.00` without a leading zero), so a dated informational line —
`04/30 .00 Overdraft fees assessed this statement period` — publishes as a
transaction at approved/clear. PNC has no per-direction count oracle
(disclosed in `analysis/count_semantics.py` SECTION_LEVEL_ORACLES), so
nothing downstream can catch it. Fix structurally: a posting row must be
distinguished from furniture by structure (section membership, column
positions, the row grammar PNC actually prints for postings), NOT by
matching the words of known furniture lines. Fixture: the exact fuzzer
line refused; the genuine printed `Total Overdraft Fees .00 .00` shapes
still handled as they are today; a real `.00`-amount POSTING (if PNC
prints them — characterize from cached docs) still parses.

# Card B — bmo_ca_business: `_MONEY_EN` rejects Canadian space thousands (PRIORITY 1)
`analysis/bmo_ca_business.py:89` `_MONEY_EN` lookbehind omits space, so
`1 000.00` — the Canadian/SI convention, on a CANADIAN bank — silently
truncates to `000.00`: a $1,000 deposit publishes as $0.00 with every
identity self-consistently wrong, approved/clear. Line `:90` `_MONEY_FR`
already enumerates `[   ]` — align `_MONEY_EN` with its own
sibling (reuse, not new grammar). Diagnostic fingerprint for your fixtures:
the orphaned leading digit lands in the description. Prove pre-fix failure
in-process; sweep must show which real archive docs (if any) move — each
named and explained.

# Hard rules
- Files: `analysis/pnc.py`, `analysis/bmo_ca_business.py` + tests +
  `W3_TRACKA_LOG.md` (append §STRUCTFIX-1). Nothing else — not money.py,
  not truist.py (owned elsewhere), not pipeline/reconcile/count_semantics.
- Structural fixes only; no furniture-text blocklists; no grammar widening
  beyond what the module or money.py already surveys.
- Before/after sweeps over each parser's ENTIRE claimed population in run
  `6893a75b` (pnc ~45+13 claimed, bmo_ca_business ~130 — derive exact sets;
  manifests in the wave-manifests scratch dir): byte-identical except
  genuinely-affected documents, each named and explained. Movers that
  become MORE correct (a truncated figure now read fully) are the point —
  but any outcome-class regression is a stop.
- Pinned corpus: gate GREEN 106/3 byte-identical; any audited-field
  movement on pinned docs = STOP (ceremony is Gustavo's).

# Validation
Full default suite; corpus-marked; corpus_gate.py; guards; conformance
cross-product; both sweeps. Exit codes verbatim. Stage bump is Ocean's.

# Final report to Ocean
Per card: verbatim diff, pre-fix-failure proof, fixtures, sweep summary
with named movers, proofs with exit codes; commit list; risks; unresolved
questions.
