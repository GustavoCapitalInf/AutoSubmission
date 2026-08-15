# Agent Handoff - DISCOVERY-OBS (batch 5 - the observability holes)
Ocean reviews and merges; you never merge or push.
**Measurement infrastructure only - zero analysis-layer changes, zero
outcome movement anywhere, byte-identical payloads.**

# Identity
- **Agent:** DISCOVERY-OBS - close the two known rows.csv blind spots:
  (1) cache-served rows carry no parser_id/dispatch (the hole that
  shortened COUNTS-P3's counterfactual denominators and blinded the
  coverage metric on warm runs); (2) the folder-agreement rollup's
  handling of bank=None registrations (label_unmatched noise - report
  honestly, never suggest renaming a parser after a folder).

# Git ownership
- Base: main `b524f72` - Branch: `wave5-discobs` - Worktree:
  `.claude/worktrees/mt5-discobs`. Own: discovery/runner.py (the row
  projection ONLY), discovery/report.py, tests, W3 log (#DISCOBS).

# The work
(1) When the analysis stage is served from cache, project parser
identity into the row from the cached payload (the payload carries
detection/dispatch data - survey what it holds; if identity is genuinely
absent from old payloads, re-resolve detection live for the row -
detection is cheap post-DETECT-BUDGET - and MARK the provenance
('parser_id_source: cache|live-detect') so the instrument can tell).
(2) report.py: a registration whose bank label is a template name and
whose Statement.bank is None gets its own rollup class (e.g.
'template_claim') instead of label_unmatched noise; the warning from
#U (never rename a parser to silence the rollup) goes in the code
comment. Prove: a warm re-run of the run of record reproduces its
outcome split exactly with parser_id now populated on the previously
blank rows; rows that had identity keep it byte-identical.

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
The projection design + provenance marking; warm-run reproduction;
diffs; proofs; commits.
