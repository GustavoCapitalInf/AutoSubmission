# Agent Handoff - FINTECH-CELL
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
# Identity
- **Agent:** FINTECH-CELL - Mercury/Found/Brex fintech statements (scout
  SC-MERCURY, 56 distinct in cluster; verify).
# Git ownership
- Base: current main - Branch: `wave3-fintech` - Worktree:
  `.claude/worktrees/mt-fintech`. Own: new `analysis/mercury.py`,
  `analysis/found_lead.py`, `analysis/brex.py` (names your call, stated),
  registry entries (NEW only), tests, W3 log (#FINTECH section).
# Scout evidence (verify)
- MERCURY_MONTHLY (31, rec 31): Mercury/Column N.A. + Choice Financial.
  KNOWN TRAPS from earlier scouting: Amount and End-of-Day Balance
  flattened onto one line with balance printed only on the LAST row of a
  day; the Type column contradicts the printed sign on 245 rows - direction
  must come from the printed sign, NEVER the Type column. Template-stable.
- FOUND_LEAD_BANK (15, rec 15): Found fintech / Lead Bank. No registration;
  top near-miss navigant 0.2.
- BREX_COLUMN_CHECKING (6, rec 6): Brex business checking via Column;
  capital_one 0.167 near-miss fires on CAPITAL ONE appearing in ledger
  text - your markers must be issuer furniture, not that.
- RHO (1): multi-account - blocked on L-1; fail closed, record.
- BREX invoices x2 + treasury receipt x1: non-statements; fail closed.
# Expected honest result: ~52 claimed and validated.

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
Same shape as HUNT-CELL.
