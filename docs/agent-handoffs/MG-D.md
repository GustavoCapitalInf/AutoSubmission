# Agent Handoff - MG-D (batch 5 - the minus-glyph canon)
Ocean reviews and merges; you never merge or push.
**analysis/money.py under the MONEY-GRAMMAR discipline: differential
INPUTS matrix coverage for every change, declared divergences,
full-archive byte-identity sweep with every mover named.**

# Identity
- **Agent:** MG-D - resolve the MINUS_GLYPHS double definition. The
  module is internally inconsistent TODAY: money.py:104 defines the
  2-glyph canon (U+2212, U+2013), money.py:569 rebinds 4 glyphs
  (adds ASCII hyphen + U+2014 em dash) at module scope; MINUS_CLASS and
  _MINUS_TABLE froze the 2-glyph value. Measured consequence:
  parse_money('—$500.00') -> +500.0 while
  parse_signed_decimal('—$500.00') -> -500.00 - two exported
  parsers, opposite signs, one token. SIGNED_MONEY_TOKEN admits em dash.

# The ruling to implement (evidence-backed)
EM DASH STAYS OUT - both archive attestations argue against admitting
it: 88AAC06119FC (Columbia) prints '03-16 — 39,692.35' where the
dash is a column placeholder on a POSITIVE balance (admitting it would
flip a printed positive), FFEBAF819F74 (TD) is OCR noise; both on
failed docs. Canonicalize to ONE definition consumed by every consumer
(the class, the table, SIGNED_MONEY_TOKEN, parse_signed_decimal);
ASCII hyphen handling must remain exactly what each consumer does today
where attested (survey each consumer's live behavior FIRST and pin it
before unifying - the FINTECH/mercury sign class depends on
parse_signed_decimal's current semantics; their tests are your guard).

# Git ownership
- Base: main `b524f72` - Branch: `wave5-mgd` - Worktree:
  `.claude/worktrees/mt5-mgd`. Own: analysis/money.py, tests
  (test_money.py + the INPUTS matrix rows + declarations), W3 log
  (#MGD).

# Proof bar
Full-archive byte-identity sweep (3,380): expected ZERO movers (0
attested em-dash signs; the placeholder doc must stay byte-identical).
The differential matrix gains the em-dash rows with declarations;
mercury/brex/found/wealthsimple sign tests all green; every consumer of
the old shadow surveyed and named.

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
Consumer survey; the canon diff; matrix rows; sweep; proofs; commits.
