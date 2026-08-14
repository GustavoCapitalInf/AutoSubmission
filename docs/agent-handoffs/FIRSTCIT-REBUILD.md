# Agent Handoff - FIRSTCIT-REBUILD
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
**Correctness-first cell: this parser is a transcription of one document,
and its reconciliation cannot fail (P1-adjacent).**
# Identity
- **Agent:** FIRSTCIT-REBUILD - rebuild analysis/first_citizens.py; fix
  the citizens.py section slice (scout SC-FIRSTCIT, 30 distinct; verify).
# Git ownership
- Base: current main - Branch: `wave3-firstcit` - Worktree:
  `.claude/worktrees/mt-firstcit`. Own: `analysis/first_citizens.py`,
  `analysis/citizens.py`, tests, W3 log (#FIRSTCIT section).
# Scout evidence (verify each at file:line)
- FC-A (9, rec 9): the statement MONTH is hardcoded as literal 03 in two
  row regexes (first_citizens.py:99, :117). Also investigate WHY the
  no-statement-hardcodes guard missed a month literal and report; if the
  fix is test-side (a new guard class), include it.
- FC-B (6, rec 6): parse gated on a memorized four-section count/total
  fingerprint of one document (:235-243).
- FC-C (4, rec 4): optional section header used as a required boundary
  (:209-210).
- FC-D (2, rec 0): body rasterized inside a digital doc - intake class;
  fail closed, record.
- THE P1-ADJACENT DEFECT (earlier survey): first_citizens derives
  beginning_balance and takes ending from a grid position so its
  reconciliation is an identity, not a test - the rebuild MUST read both
  balances from the printed At-A-Glance summary so reconcile becomes
  independent again (the scotia standard). Pinned-corpus exposure check
  FIRST if any first_citizens/citizens doc is pinned.
- CIT-A (4, rec 4): citizens.py:161 reads only one of the printed debit
  sub-sections (section boundary taken as terminator).
# Expected: ~23 claimed and validated (19 FC + 4 CIT); currently-validated
  docs byte-identical UNLESS the balance-source fix legitimately changes
  derived fields - every field mover named and justified against the
  printed statement.

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
Pinned-exposure first; per-family diffs; sweeps; proofs; commits; risks.
