# Agent Handoff - COUNTS-MAP (batch 5 - the mapping schema)
Ocean reviews and merges; you never merge or push.
**Protected cell: analysis/count_semantics.py (schema) +
analysis/reconcile.py (application). Pinned-diff discipline. The
COUNTS-P3 record (#COUNTSP3 + its review) is your evidence base: the
naive promotions cost 11 and 9 validated->review with the gate blind -
the mapping field exists to make those promotions SAFE.**

# Identity
- **Agent:** COUNTS-MAP - add CountSemantics.mapping so a printed count
  that deterministically excludes a named row class becomes comparable
  WITH the mapping applied, then promote capital_one:debit and
  first_citizens:debit on the already-measured evidence.

# Git ownership
- Base: main `b524f72` - Branch: `wave5-countsmap` - Worktree:
  `.claude/worktrees/mt5-countsmap`. Own: count_semantics.py (schema +
  the two entries), reconcile.py (the comparison hunk ONLY, pinned),
  telemetry/stated_counts.py OBSERVER_VERSION 3->4 (its contract
  requires it), tests, W3 log (#COUNTSMAP).

# The design bar
The mapping must be DECLARATIVE and closed (e.g. "captured includes the
billed service-charge row the printed count excludes: expected =
printed + (1 if billed else 0)") - no open-ended callables the table
cannot audit. Fresh counterfactuals on the current archive for both
promotions (capital_one 22 docs: 10 exact-zero-charge + 12 at +1;
first_citizens 35: 26 + 9 - re-derive, do not trust). Measured result
REQUIRED: 0 outcome movers, 0 false mismatch flags; the mapping catches
a REAL mismatch (fixture: a document whose captured count is off by 2 -
one charge + one genuinely missing row - must flag). The COUNTS-P3
tautology/falsifier/disclosure discipline applies to both entries.
mismatch stays advisory - never in any ok-set, never mechanical
withholding.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-15 batch-4 entry in WAVE2_EXECUTION_LOG.md
first. Base main `b524f72` (v12, OCR v3, registry 71, suite 4,240,
corpus-marked 25). Run of record:
`discovery_reports/2026-08-15T111704.195314-0000-c924d751` (validated
2,405 / review 25 / withheld 65 / failed 872 / deferred 13; 3,380 distinct
shas; BOTH caches regenerated cold at v12/v3). Archive + caches READ-ONLY;
OCR artifacts by DIRECT file path only (never the webapp_data sqlite
index); $0 vendor; private uniquely-named scratchpad subdir. Long
background shells get killed - run long proofs as SEQUENTIAL single
commands. Family populations: derive by live detection replay or
artifact-store enumeration, NEVER from rows.csv parser_id alone (the
cache-hit hole, W3 #COUNTSP3). Proof floor per branch: full default suite
+ corpus-marked slice + `python corpus_gate.py` GREEN (106/3 with the
verdict line 6 review / 100 validated / 3 withheld - the gate now pins
every pinned document's full published integrity block) + guards +
conformance cross-product (71x70); exit codes verbatim; every mover named
by content_sha256 + outcome + field; claimed != validated; zero movement
outside your named populations; commit incrementally, clean tree; NEVER
merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump is
Ocean's at merge. Fail-closed everywhere.

# Final report to Ocean
Schema diff; both entries' fresh evidence; reconcile hunk verbatim;
whole-archive movement (expect 0/0); proofs; commits; risks.
