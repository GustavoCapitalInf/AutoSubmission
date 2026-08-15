# Agent Handoff - CURRENCY-1 (batch 5 - the APPROVED platform invariant)
Ocean reviews and merges; you never merge or push.
**Gustavo's standing invariant (2026-08-15, verbatim): "Currency should
be derived from document evidence when available and must not be
silently asserted by a schema default when the document proves
otherwise. If RBC or any other pinned expected result moves, use the
formal truth-set ceremony before changing expectations."**

# Identity
- **Agent:** CURRENCY-1 - survey currency evidence platform-wide, then
  implement the invariant, with a full ceremony enumeration for every
  pinned mover BEFORE any expectation changes (Ocean executes the
  ceremony at merge; you prepare it).

# Git ownership
- Base: main `b524f72` - Branch: `wave5-currency` - Worktree:
  `.claude/worktrees/mt5-currency`. Own: the parser files whose currency
  reads you add (surveyed, listed in your report), tests, W3 log
  (#CURRENCY). schema.py default stays (a default is fine where no
  evidence exists); the invariant governs documents that PROVE a
  currency.

# The survey FIRST (report before implementing)
Census: which registrations publish currency today and from what
(printed evidence vs default); which documents print currency evidence
the parser ignores (rbc's 156 Canadian docs publishing USD is the known
case - characterize its printed evidence: $ CAD markers? French
locale? account domicile?); which pinned docs would move. Known
instances: rbc USD-on-Canadian (pinned movers likely -> ceremony),
community_section's 5 bank=None movers defaulting USD (what do they
print?), wealthsimple/td french CAD reads (already evidence-based -
your positive pattern). THE ORACLE BAR: currency publishes from printed
evidence (currency code, locale-bound product line, explicit symbol
convention the layout proves); ambiguous evidence -> the default
STANDS and the ambiguity is named. No geography inference, no
folder/filename inference.

# Ceremony preparation (Gustavo pre-authorized the PROCESS)
For every pinned document whose published currency changes: enumerate
(field, old, new, printed evidence line) in a ceremony table; zero
UNENUMERATED pinned movement is a hard stop. Audit CSVs: check whether
currency is an audited column; if yes the ceremony includes the CSV
change, prepared not applied.

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
The survey; the implementation; the ceremony enumeration table;
full-archive movement with every mover named; proofs; commits; risks.
