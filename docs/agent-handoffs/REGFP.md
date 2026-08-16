# Agent Handoff - REGFP (batch 6, card 4 - the registry fingerprint enters the analysis settings key)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** REGFP - the analysis settings key cannot see the parser
  registry. A registration added, removed, or reordered WITHOUT a stage
  bump would serve stale analysis entries computed under the old registry.
  Today the composed ANALYSIS_STAGE_VERSION bump at every train masks this
  by policy; the card makes the cache honest by construction.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-regfp` - Worktree:
  `.claude/worktrees/mt6-regfp`. Own: webapp/artifact_cache.py
  (analysis_settings_key), the registry-side fingerprint helper, tests,
  W3 log (#REGFP).

# The evidence base
`analysis_settings_key` (webapp/artifact_cache.py:499-517) fingerprints
exactly: stage_version, parse_mode, model, escalation_model,
withholding_denominator_mode. The registration set (72 ids, their versions/
supersedes edges, EXPECTED_ORDER) is invisible.

# The work
1. A deterministic registry fingerprint: an ordered digest over
   (registration id, its declared version/revision material, supersedes
   edges) - decide the exact material by what actually changes dispatch
   outcomes, and justify each inclusion/exclusion. It must be stable across
   processes and platforms (no id(), no dict order luck).
2. Fold it into `analysis_settings_key` - the SETTINGS key, which is
   per-run constant, is the correct home (WIRING-2's lesson was the
   inverse: per-DOCUMENT material must go to the input hash; per-RUN
   material belongs here). Verify telemetry/stated_counts._ArtifactJoin
   still joins - it reconstructs the settings key, so it must pick up the
   same fingerprint through the shared function, not a copy (repo-wide grep
   for any second derivation; the FILENAME-BOUNDARY lesson).
3. State plainly: this invalidates the analysis cache by construction at
   the merge where it lands (the fingerprint enters the key). Ocean's
   composed train bump covers re-measurement - do NOT bump stage versions
   yourself.
4. Guard: a test that adds a synthetic registration in a scratch registry
   and proves the key moves; and one proving the key is byte-stable across
   two fresh processes on the unchanged registry.

# Expected archive movement
ZERO outcome movement (same registry, same code - only the key material
changes; every entry recomputes to identical values at the next cold run).
Full-population before/after on outcomes required all the same.

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
The fingerprint material with justifications; the join verification; the
two guards; hunks verbatim; zero-movement sweep; proofs with exit codes;
commits; risks.
