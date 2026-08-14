# Agent Handoff - MONEY-GRAMMAR
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
**Single integration owner for analysis/money.py - the highest-blast-radius
card of the batch. Byte-identity discipline throughout.**
# Identity
- **Agent:** MONEY-GRAMMAR - the shared money-grammar hardening the wave's
  evidence has fully specified (SC-MONEY + F-MONEYFMT + scotia/TD/RBC
  findings; verify everything).
# Git ownership
- Base: current main - Branch: `wave3-money-grammar` - Worktree:
  `.claude/worktrees/mt-money`. Own: `analysis/money.py`, the minimal
  consumer change for card 1 wherever the chase-export money reader lives
  (survey first; state the file), tests, W3 log (#MONEY section).
# Cards
1. NON-ASCII MINUS CLASS (P1, 3 withheld docs recoverable): no money
   grammar recognizes U+2212 MINUS or U+2013 EN DASH; the Chase-for-
   Business web export prints them, so debits were booked as credits
   until those docs withheld. Normalize the sign-glyph class in ONE place
   in money.py so every AmountFormat inherits it. Expect exactly the 3
   chase_export withheld docs to move; name them.
2. ONE-DECIMAL TRUNCATION (latent, platform-wide): parse_money(34.9-form)
   returns 34.0 silently. The scotia cell pads at its call site. Implement
   the structural answer in money.py: REJECT one-decimal as not-money
   (fail-closed default) unless a surveyed format legitimately prints one
   decimal; scotia pads before calling, so rejection is safe there - the
   sweep proves it.
3. DECIMAL-BOUND (crash class, all parsers): money tokens with >=26
   integer digits raise decimal.InvalidOperation from adb.py
   (F-STRUCTURE finding; chase page-barcode digit runs are the plausible
   source). Bound token acceptance in money.py (integer part >13 digits
   is not money - non-match, fail closed). adb.py is PROTECTED - the
   bound lands at the grammar, never there.
4. parse_money anchor/guard hardening (SC-MONEY F8): parse_money reads
   money out of dates and reference numbers when callers hand it whole
   lines (a date reads as 12.0; 100.00CREDIT reads as -100.0 via the D
   substring rule). Fix the D/DR rule to match the marker token exactly.
   The three offending callers are OUTSIDE your scope - report per-caller
   cards instead of editing them.
# HARD DISCIPLINE
money.py is imported by ~20 parsers. EVERY change lands behind a
byte-identity sweep over the ENTIRE claimed archive population (~2,0xx
distinct claimed docs via cached OCR artifacts, analyze_markdown in
memory): expected movers ONLY the 3 chase_export docs (card 1) - every
other document byte-identical. Any unexpected mover = stop and diagnose.
Fixtures: every mutant form from the F-MONEYFMT gauntlet (scratchpad
gauntlet_*.py) that touches your cards, pre-fix proven.

# Standing wave rules (binding)
Read in-tree first: PROJECT_STATUS.md, WAVE2_EXECUTION_LOG.md (the 08-13/14
entries), W3_TRACKA_LOG.md (your predecessors' sections are the standard).
Characterize before code; structural capability over literals; NO
statement-specific constants (guard-enforced); claimed-but-not-validated is
NOT success - per-document instrument (summary identity, balance walk,
printed counts where present) before claiming; fail closed with named
diagnoses where evidence is insufficient; zero ambiguity (full conformance
cross-product); truth-set movement = STOP (ceremony is Gustavo's).
Baseline run of record: discovery_reports/2026-08-14T060822.665646-0000-88be9dd3
(v10; validated 2,030 / review 10 / withheld 60 / failed 1,267 over 3,380
distinct; NOTE: 1,034 cache-served rows carry no dispatch/parser_id - derive
populations by content_sha256 + outcome, enrich parser identity from earlier
runs if needed). Archive + D-3 cache in the MAIN checkout, read-only, direct
artifact file paths ONLY (never the sqlite index). $0 vendor. Private
scratchpad subdirectory. Long background shells get killed in this
environment - for any proof over 20 min, prefer sequential single commands
and re-check results from output files if a shell dies. Machine runs
parallel cells - generous timeouts. ANALYSIS_STAGE_VERSION bump is Ocean's.
Validation floor: full default suite; corpus-marked; corpus_gate.py GREEN
106/3 byte-identical (audited-field movement = STOP); guards; conformance
cross-product zero; stratified non-target probe (>=400 docs) for any new
registration; full-population before/after sweeps with every mover named.
Exit codes verbatim. Commit incrementally, repo style; never merge or push.

# Final report to Ocean
Per-card diffs; the archive-wide byte-identity sweep with the 3 named
movers; crash-class regression test; proofs; commits; risks.
