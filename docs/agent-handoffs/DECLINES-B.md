# Agent Handoff - DECLINES-B
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
# Identity
- **Agent:** DECLINES-B - us_bank + capital_one attempted-declined gaps
  (scouts SC-USBANK 17 + SC-CAPONE 38; verify).
# Git ownership
- Base: current main - Branch: `wave3-declines-b` - Worktree:
  `.claude/worktrees/mt-declb`. Own: `analysis/us_bank.py`,
  `analysis/capital_one.py`, tests, W3 log (#DECLB section).
# Scout evidence (verify at file:line)
us_bank (expect ~18):
- US-DAYS (11): optional Days in Statement Period line treated as
  required (us_bank.py:132-134).
- US-CONSUMER (5): consumer summary grid prints no item counts;
  _SUMMARY_CATEGORY_RE hard-requires the count cell (:50-53).
- US-ECHECK (1): Checks Paid itemized across two section headings;
  _DETAIL_HEADING maps one-to-one (:40-47).
- US-PERIOD (1): period halves not separated by through (:102-114).
- ALSO the us_bank hardcoded product-name defect (publishes a product 36
  of 40 validated docs do not print - R-1 class): fix by reading the
  printed product line; this CHANGES published fields on validated docs -
  every mover named, verified against the printed line. count_semantics:
  us_bank is COMPARABLE - your changes must not alter count meaning; if
  the consumer grid (no counts) claims, counts go None (not_printed),
  which is correct - state it.
capital_one (expect ~18):
- zero-service-charge decline (10): :26 requires literal parens; the bank
  prints them only when a charge exists.
- cycle-boundary fee ADB exclusion (2): :117-136.
- Capital One 360 layout (6): markers require AN IMPORTANT MESSAGE TO OUR
  CLIENTS which 360 does not print - new sub-registration or marker set
  under full R-3/R-4.
- multi-account (6, rec 0): L-1 blocked; fail closed, record.
- The service-charge count-scope card (13 docs): capital_one:debit is
  INCOMPARABLE in count_semantics with the +1 mapping specified by
  COUNTS-P1 sec 3.2 - if your rebuild makes the printed scope provable,
  propose the promotion WITH a fresh counterfactual in your report; the
  table edit is Ocean's.

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
Per-card diffs, sweeps over both parsers' full populations with named
movers, proofs, commits, risks.
