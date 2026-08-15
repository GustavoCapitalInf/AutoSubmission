# Agent Handoff - WIRING-2 (batch 5, card 1 - the activation + APPROVED ceremony)
Ocean reviews and merges; you never merge or push.
**Protected cell. Pinned-diff discipline; Ocean forensic review at merge.
Your complete evidence base: W3 #PIPEFIX (P0-P7, P4b) + #WIRING (WIRING-1's
stop analysis and the landed gate instrument). Read both before code.**

# Identity
- **Agent:** WIRING-2 - activate the page-declaration integrity fix and
  execute the ceremony Gustavo re-scoped and approved as OPTION A.

# Git ownership
- Base: main `b524f72` - Branch: `wave5-wiring2` - Worktree:
  `.claude/worktrees/mt5-wiring2`. Own: the three call sites
  (discovery/runner.py::_analyse, webapp/worker.py::_analyze_doc,
  batch.py - WIRING-1's caller sweep DECIDED batch.py is production),
  webapp/artifact_cache.py (input-hash digest hunk), the second key
  derivation at telemetry/stated_counts.py:774-779, corpus_artifacts.py
  + tests/corpus_cache (page lists for the six image-only pinned docs),
  corpus_gate.py PINNED_OUTCOMES + PRODUCTION_SUPPLIES_SHEETS flip +
  ANALYSIS_CALL_SITES, pinned expectations, tests, W3 log (#WIRING2).

# The APPROVED ceremony - Option A, verbatim scope (Gustavo 2026-08-15)
Exactly THREE movements, each already independently proven:
1. `Misc/Texas Bank.pdf` review -> validated (flags
   ['missing_declared_statement_page'] -> [], notes 1->0, risk
   review->clear; every audited field byte-identical);
2. `Regions/Regions.pdf` review -> validated (same shape; executable
   once the committed artifact carries its page list - the D-3 store
   holds it: 3 pages, model local-tesseract-ocr, joined markdown proven
   byte-identical to the committed artifact);
3. `Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf` withheld ->
   withheld with the false flag withdrawn from published evidence
   (flags 7->6, notes 8->7, class unchanged).
**ANY additional pinned movement is a HARD STOP - do not adjust, do not
re-baseline, report.** Enumerate all three field-by-field BEFORE running
anything; the other three flag-carrying pinned docs (Builder, Columbia,
Link Bank) KEEP their flags; gate expectation after ceremony:
102 validated / 4 review / 3 withheld (verify, do not trust this line).

# Card A - the wiring (3 sites + the flip)
Pass the intake object's page list at all three sites;
PRODUCTION_SUPPLIES_SHEETS -> True in the same commit (the AST test
enforces agreement). The forge-fixture family (content cannot fabricate
a sheet boundary; padding; str-footgun TypeError) stays green throughout.

# Card B - the cache key (the collision WIRING-1 proved)
A sheet COUNT still collides (same count, different partition, opposite
flags - demonstrated). Add a DIGEST OVER THE SHEET-LIST PARTITION to the
ANALYSIS INPUT HASH (webapp/artifact_cache.py:653 region), NOT to
analysis_settings_key (per-run constant; a per-document value there
silently blinds telemetry/stated_counts._ArtifactJoin). Re-point the
second derivation copy at telemetry/stated_counts.py:774-779 (it already
reconstructs pages) and update the docstring input table. Repo-wide grep
for any further reimplementation (FILENAME-BOUNDARY lesson). State
plainly: this invalidates the analysis cache by construction; Ocean's
composed stage bump covers re-measurement.

# Card C - committed-artifact page lists
tests/corpus_cache OCR artifacts are markdown-only; the six image-only
pinned statements need their page list persisted (from the D-3 store,
verified byte-identical markdown; NO new OCR). Extend the manifest
format additively - existing fields untouched.

# Expected archive movement (name every one)
The 114 false-flag withdrawals go LIVE: 101 non-publishing, 13
publishing movers (P3.5 named them; 3 review->validated incl. Apex
B279C19D..., 10 withheld shed the flag but stay withheld), plus the
ceremony docs. SCAN-SCOUT's 8-doc scanned-side table (in #WIRING's
record) is your independent cross-check. Zero movement beyond the named
populations; full-population before/after over all 3,380.

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
Ceremony enumeration first; hunks verbatim; the census reproduction
(157/114/43/0); full-population sweep with every mover named; proofs
with exit codes; commits; risks.
