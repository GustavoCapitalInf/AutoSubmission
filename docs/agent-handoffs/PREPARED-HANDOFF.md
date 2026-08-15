# Agent Handoff - PREPARED-HANDOFF (batch 5 - the double-sweep seam)
Ocean reviews and merges; you never merge or push.
**Protected cell: analysis/pipeline.py (resolve seam) +
telemetry/collect.py. Pinned-diff discipline. DETECT-BUDGET's DT9.1 is
your evidence: the discovery run sweeps detection TWICE per document
(pipeline.resolve, then telemetry/collect.score_vector ->
detection_report); handing the first sweep's PreparedDocument to the
second halves detection cost again.**

# Identity
- **Agent:** PREPARED-HANDOFF - one prepared-text computation per
  document across both sweeps.

# Git ownership
- Base: main `b524f72` - Branch: `wave5-prephand` - Worktree:
  `.claude/worktrees/mt5-prephand`. Own: the pipeline resolve-seam hunk
  (pinned, minimal), telemetry/collect.py, tests, W3 log (#PREPHAND).

# The bar (DETECT-BUDGET's own discipline)
Full-archive equivalence: complete detection_report (score, matched,
excluded_by) per registration per document, identical before/after,
digest-compared; the near-miss vectors byte-identical (they rank future
parser cells); the crash guard preserved AND exercised (deliberate
crash injection - the DT7.1 caveat: a sample with zero natural raises
proves nothing about the guard); measured cost before/after on the
pinned 109 + the 40 largest. Zero payload movement anywhere.
Coordinate: PIPELINE-5 also touches pipeline.py (different region -
:542/:545); note your hunk's exact lines for Ocean's train.

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
Hunks verbatim; equivalence digests; crash-arm; cost table; proofs.
