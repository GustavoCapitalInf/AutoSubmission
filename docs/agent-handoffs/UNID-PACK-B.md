# Agent Handoff - UNID-PACK-B
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
# Identity
- **Agent:** UNID-PACK-B - Fifth Third commercial (card 5), Fiserv
  Premier/Precision (card 2), Desjardins French extension (card 8).
# Git ownership
- Base: current main - Branch: `wave3-unid-b` - Worktree:
  `.claude/worktrees/mt-unidb`. Own: two new modules (fifth_third +
  the fiserv family - names yours, stated), `analysis/desjardins.py`
  (card 8 extension), registry entries (NEW only), tests, W3 log
  (#UNID-B section).
# Scout evidence (prototype-measured; verify; hashes in SC-UNID-3 report)
- FIFTH THIRD (13 docs, 12 rec): FTCSTMT...UDSPDFSTMT header. THE TRAP:
  the summary has THREE debit-side components (Checks + Withdrawals/
  Debits, plus the credits clause) - omitting the separate Checks total
  breaks the identity on 7/13. Parenthesised negatives $(3,869.28).
  Checks print as a 3-up Number/Date/Amount grid with flags,
  interleaved across pages with continued sections - needs a global
  sectioniser. 1 doc missing the withdrawals clause - fail closed.
- FISERV (56 in-folder, 30 rec; +10 other folders): **DETECTION TRAP,
  binding: the counts clause alone matches 197 validated wells_fargo
  docs - the opening-balance clause is REQUIRED in the marker
  conjunction (scout verified 0 collisions with it). Your stratified
  probe must include a wells_fargo-heavy stratum and prove zero
  claims.** Row order flips between issues - segment on money tokens,
  keep segments with exactly one date. Leading-dot amounts (.24) - use
  money.pad_leading_decimal. Service charge/interest may print as BOTH
  a summary line and a ledger row (fixture both). Sub-splits: F1
  classic 23 rec, F2 additions/deductions 3 rec (rest geometry - fail
  closed named), F3 DAILY ACTIVITY 4 rec, F4 Southside scanned 0 -
  fail closed.
- DESJARDINS FR (10 docs, 6 rec): extend analysis/desjardins.py (5
  existing claims must stay byte-identical - sweep). French money
  grammar (parse_french_amount, detached minus). The ledger runs into
  a FACTURATION DETAILLEE fee table that must TERMINATE it (structural
  bound). The two-digit date pair pattern collides with space-thousands
  amounts unless anchored (scout: anchor on a following capital).
  4 docs chain-broken - fail closed, named.
# Expected honest result: ~48 claimed and validated across the three.
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
Same shape as prior cells; the Fiserv anti-collision proof gets its own
section.
