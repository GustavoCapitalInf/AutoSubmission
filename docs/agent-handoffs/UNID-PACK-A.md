# Agent Handoff - UNID-PACK-A
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
# Identity
- **Agent:** UNID-PACK-A - three new registrations from SC-UNID-3:
  Woodforest (card 3), Wealthsimple (card 4), Symitar CU (card 7).
# Git ownership
- Base: current main - Branch: `wave3-unid-a` - Worktree:
  `.claude/worktrees/mt-unida`. Own: three new modules, registry entries
  (NEW only), tests, W3 log (#UNID-A section).
# Scout evidence (prototype-measured; verify; hashes in SC-UNID-3 report)
- WOODFOREST (20 docs, 17 rec): ACCOUNT TYPE AND NUMBER BALANCE FORWARD
  TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE + Transactions grid (Date
  Credits Debits Balance Description). Credits/debits share ambiguous
  columns - the printed running balance is the ONLY sign oracle
  (direction from balance movement, magnitude from the printed cell;
  the scotia standard: disagreement withholds). 3 scrambled-reading-
  order docs (one account): geometry - fail closed, named.
- WEALTHSIMPLE (17 docs, 16 rec; +3 parserless-validated in the CIBC
  folder - those 3 must remain byte-identical or move to your claim
  WITHOUT field changes - sweep them explicitly): Chequing monthly
  statement + DATE POSTED DATE DESCRIPTION AMOUNT (CAD) BALANCE (CAD).
  Unicode minus (U+2013/U+2212) printed, NOT ASCII - read the printed
  sign-glyph class explicitly in your reader (MONEY-GRAMMAR is landing
  the shared class in a parallel cell; do NOT depend on it; note the
  overlap for Ocean's merge). CAD currency must be set. 1 doc has no
  parsable rows - fail closed.
- SYMITAR CU (8 docs, 8 rec): the six-figure equation row (Balance +
  Deposits + Earned - Withdrawals - Charges = Balance) is the
  per-account oracle; amount and balance sit BEFORE the description;
  multi-account per PDF with dormant accounts printing no rows (a
  dormant sibling must not fail-close the doc - but genuinely-multiple
  ACTIVE accounts are L-1 blocked; characterize and state per doc).
# Expected honest result: ~41 claimed and validated; 4-5 named
  fail-closed.
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
Same shape as prior cells.
