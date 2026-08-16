# Agent Handoff - SCAN-NEXT (batch 6, card 10 - the next scanned family, ranking re-derived)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** SCAN-NEXT - continue the scanned ladder (SCAN-A fifth_third
  photographed, SCAN-B the second core processor, SCAN-C the four-way
  partitioned summary, batch-5's scanned promotions). The scout's original
  ranking is stale after four batches of movement: RE-DERIVE it from the
  run of record, then implement the top unimplemented family in the same
  branch.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-scannext` - Worktree:
  `.claude/worktrees/mt6-scannext`. Own: the census (report section), the
  one new scanned registration you rank first, tests, W3 log (#SCANNEXT).

# Phase 1 - the census (SCAN-SCOUT's documented method, half a day, no code)
Over run 2e3ea385: every doc classified scanned/mixed + current outcome;
group by STRUCTURAL family (mastheads/furniture in the cached OCR text,
never folder names); for the top unclaimed families read the cached OCR
artifacts by direct path - text quality, truncation, whether the local
Tesseract output carries a readable ledger AT ALL. Rank by
(validated-gain x confidence). NO new OCR, NO vendor calls; where a family
cannot validate without new OCR spend, report cost/benefit and stop there.
Batch-5 context you must honor: RUNG-SEAM landed one shared native ladder
with the unreadable-text-layer guard + reason channel - refusal reasons in
artifacts are now first-class evidence; use them in the ranking.

# Phase 2 - the top family, implemented
Same discipline as SCAN-A/B/C (their W3 records are the model):
fail-closed oracles (fabricated rows and hallucinated values are the class
killers - say what your family's oracle refuses); Tesseract-mangled
printings handled by evidence, not tolerance-widening; page-declaration
integrity under the WIRING-2 regime (sheets are live in the analysis input
key - a scanned doc's page list matters; flags must be earned, not
inherited).

# Expected archive movement
Named by the census: your family's shas only, ceiling stated before
implementation. Zero movement outside the family.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base main `eef77c6` (v13, OCR v3, registry 72, suite 4,511,
corpus-marked 27). Run of record:
`discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` (validated 2,430 /
review 15 / withheld 63 / failed 859 / deferred 13; 3,380 distinct shas;
analysis regenerated cold at v13). Archive + caches READ-ONLY; OCR artifacts
by DIRECT file path only (never the webapp_data sqlite index); $0 vendor;
private uniquely-named scratchpad subdir. Long background shells get killed -
run long proofs as SEQUENTIAL single commands; detached-process aliveness via
`tasklist`, never MSYS `kill -0`. Family populations: derive by live
detection replay or artifact-store enumeration, NEVER from rows.csv parser_id
alone. Proof floor per branch: full default suite + corpus-marked slice +
`python corpus_gate.py` GREEN (106/3; verdicts 102 validated / 4 review / 3
withheld) + guards + conformance cross-product (updated if a registration is
added, pins in the SAME commit); exit codes verbatim; every mover named by
content_sha256 + outcome + field; claimed != validated; zero movement
outside your named populations; commit incrementally, clean tree; NEVER
merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump is Ocean's
at merge. Fail-closed everywhere.

# Final report to Ocean
The re-derived ranking (full table, so batch 7 can staff from it without
another census); the implemented family's record in the SCAN-A/B/C shape;
hunks verbatim; proofs with exit codes; commits; risks.
