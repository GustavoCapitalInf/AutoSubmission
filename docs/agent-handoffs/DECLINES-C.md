# Agent Handoff - DECLINES-C
Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
# Identity
- **Agent:** DECLINES-C - bluevine + navy_federal + relay declines
  (scouts SC-BLUEVINE 14 / SC-NAVYFED 10 / SC-RELAY 31; verify).
# Git ownership
- Base: current main - Branch: `wave3-declines-c` - Worktree:
  `.claude/worktrees/mt-declc`. Own: `analysis/bluevine.py`,
  `analysis/navy_federal.py`, `analysis/relay.py`, tests, W3 log
  (#DECLC section).
# Scout evidence (verify at file:line)
bluevine (expect ~12): abbreviated month with a period (Feb.) unreadable
  by the word-char-only period regex at bluevine.py:31-34 (12 docs).
  Fragmented rows (2 docs) - geometry, fail closed.
navy_federal (expect ~9): the retail/consumer product label hardcoded as
  structural anchor (10 docs, 9 rec); read the product from the document
  per the dakota_west precedent. Multi-account (10): L-1 blocked - fail
  closed, record. Zero-activity (1): the A-prime admissibility rule is
  Gustavo-pending for non-chase parsers - fail closed, record (do NOT
  copy the rule).
relay (expect ~9): private-use-area glyphs replace printed +/- signs
  (6 docs) - normalize the PUA glyph class at the relay reader; measure
  whether the class is platform-wide and report (do not touch ocr/ -
  consume-only). Split rows (3 docs): _ROW_RE single-line assumption at
  relay.py:12-18. The withheld doc (rec 0): genuine source defect -
  keep refused.

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
Per-parser cards, sweeps over full claimed populations, proofs, commits,
risks.
