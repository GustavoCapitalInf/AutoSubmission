# Agent Handoff - TEL-COV (batch 6, card 5 - telemetry tells the truth on cache hits)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** TEL-COV - three recorded telemetry-truth defects from DISCOBS's
  DO7 ledger, one card. Discovery's row projection was fixed in batch 5;
  the H-3 telemetry layer still lies on cache hits.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-telcov` - Worktree:
  `.claude/worktrees/mt6-telcov`. Own: telemetry/report.py,
  telemetry record emission (dispatch_section material), discovery/evidence.py
  label check, H3_SCHEMA.md corrections, tests, W3 log (#TELCOV).

# The evidence base (read first: W3 §DISCOBS DO7, items 1-3)
1. **The coverage numerator collapses on warm runs.** telemetry/report.py
   computes `claimed / total` where `claimed` comes from `dispatch.outcome`
   - null on a cache hit - while `total` counts every record.
   `H3_SCHEMA.md §5.4`'s claim that the rate "stays computable on re-runs"
   is false and was false for both rollups.
2. **Records carry `dispatch.source = "unavailable"` and null parser_id on
   cache hits.** rows.csv is self-sufficient since batch 5; the H-3 JSONL is
   not - `discovery.evidence.parser_index` (--enrich) remains a bridge.
   Card: pass a truthful `dispatch.source` and the reconstructed ids into
   `dispatch_section`, then retire the enrichment join (keep --enrich as a
   no-op-with-warning or remove per what its callers need - measure, then
   decide).
3. **discovery/evidence.py's label check has the template blind spot one
   layer over `registration_labels()`** answers with registry id + registry
   bank label; for a template (§U) registration both are template names, so
   a `Desjardins/` document reads as a false label disagreement.

# The work
Fix all three with the same discipline: the value published on a WARM row
must equal the value the COLD row published (DISCOBS's warm==cold test is
your model - extend it to the telemetry layer, don't copy it). OBSERVER/
DIAGNOSTICS version constants: if the H-3 record shape or vocabulary moves,
say so in the report - the composed bump decision is Ocean's at the train.
Correct H3_SCHEMA.md §5.4 to describe the fixed behaviour.

# Expected archive movement
ZERO outcome movement. The deterministic-coverage RATE printed by warm-run
reports will move (numerator repaired) - name the before/after rate on a
warm replay and show cold is unchanged.

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
withheld) + guards + conformance cross-product (72x71); exit codes verbatim;
every mover named by content_sha256 + outcome + field; claimed != validated;
zero movement outside your named populations; commit incrementally, clean
tree; NEVER merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump
is Ocean's at merge. Fail-closed everywhere.

# Final report to Ocean
The three fixes with warm==cold proofs; the --enrich disposition with caller
measurement; version-constant implications stated; H3_SCHEMA.md diff; hunks
verbatim; zero-outcome-movement sweep; proofs with exit codes; commits;
risks.
