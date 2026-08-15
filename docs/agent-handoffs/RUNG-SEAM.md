# Agent Handoff - RUNG-SEAM (batch 5 - one ladder + the intake crash guard)
Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** RUNG-SEAM - (1) consolidate the six native-rung ladder
  copies into ONE shared ladder; (2) guard the FzErrorFormat crash class
  in _native_pages.

# Git ownership
- Base: main `b524f72` - Branch: `wave5-rungseam` - Worktree:
  `.claude/worktrees/mt5-rungseam`. Own: ocr/native_text.py (the shared
  ladder home + the crash guard), the six consumer modules' ladder
  functions (ocr/pipeline.py, adb_debug.py, adb_forensic_audit.py,
  balance_forensic_audit.py, build_corpus_cache.py,
  deterministic_coverage_audit.py - mechanical: call the shared ladder),
  tests/test_native_rung_parity.py (retire the drift guard into a
  single-source assertion + keep the completeness scan), W3 log (#RUNGSEAM).

# Card 1 - the seam
One function (ocr/native_text.py is the natural home - every copy
already imports from it) holding the ordered ladder; the six callers
delegate. Byte-identity: the pinned 109 through ocr/pipeline before and
after (the gate is the proof); the five oracle callers produce identical
markdown on a 100-doc sample incl. all woodforest/first_citizens/navy/
td/wells docs (the bank-specific rungs are the risk surface).

# Card 2 - FzErrorFormat
GEOM-1 found 4 archive docs raising FzErrorFormat out of _native_pages
(fitz.open guarded; the get_text('blocks') loop is not). Guard the loop
to a structured refusal (the rung returns None -> ladder falls through
to the next rung / generic), never an escaped exception. Name the 4
docs; their outcomes must be UNCHANGED or honestly improved (if the
generic rung can now read what the crash previously killed, that is
movement - name it); nothing else moves.

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
The seam diff; byte-identity sweeps; the 4 named docs; proofs; commits.
