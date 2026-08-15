# Agent Handoff - PIPELINE-5 (batch 5 - two pinned pipeline hunks)
Ocean reviews and merges; you never merge or push.
**Protected cell: analysis/pipeline.py, two minimal hunks ONLY, quoted
verbatim in your report. The REPAIR-GUARD half is already drafted by
MG-C at docs/agent-handoffs/REPAIR-GUARD.md - read it.**

# Identity
- **Agent:** PIPELINE-5 - (1) REPAIR-GUARD: wrap apply_statement_repairs
  in the parser-exception seam; (2) MODEL-LABEL: honest model_used for
  bank=None documents.

# Git ownership
- Base: main `b524f72` - Branch: `wave5-pipeline5` - Worktree:
  `.claude/worktrees/mt5-pipeline5`. Own: analysis/pipeline.py (the two
  hunks), tests, W3 log (#PIPE5).

# Hunk 1 - REPAIR-GUARD
apply_statement_repairs at pipeline.py:542 runs OUTSIDE _guarded; a
repair-stage refusal escapes as a bare exception and its class/misattribution
lands in webapp job errors (the MG-C review demonstrated it; read_money's
message no longer quotes tokens, but the seam must still catch the class).
Wrap the repair call in the same guarded discipline parse uses
(ParserFailure with registry id + exception class name only). Fixture: a
raising repair produces the guarded outcome, never an escaped exception;
the three chase movers and the 114-withdrawal populations byte-identical.

# Hunk 2 - MODEL-LABEL (narrowly scoped)
pipeline.py:545's (stmt.bank or "bank") makes every bank=None document
publish model_used="bank-deterministic" - dishonest aggregation. Scope
NARROWLY: when stmt.bank is None AND a registration claimed the document,
model_used = "<registration.id>-deterministic". Documents with a bank
label are UNCHANGED (zero movement there). Expected movers: exactly the
bank=None population (releve_facturation 16 + community_section 5 +
core_processor_sectioned bank=None subset + balance_by_date 11 +
fifth_third/fiserv where applicable - census it live, name every doc).
LLM-path unaffected (no registration -> current behavior).

# Hard rules
Zero outcome movement anywhere; the two hunks compose with WIRING-2's
call-site changes (different files) and PREPARED-HANDOFF (different
pipeline region - coordinate via log notes; Ocean sequences the train).

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
Hunks verbatim; mover census; sweeps; proofs; commits; risks.
