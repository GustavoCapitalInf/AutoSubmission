# Agent Handoff - WIRING-1 (batch 4, card 1 - HIGHEST PRIORITY)
Ocean reviews and merges; you never merge or push.
**Protected cell: webapp/, discovery/runner.py, analysis/pipeline.py seam,
webapp/artifact_cache.py key material, corpus_gate.py, pinned expectations.
Pinned-diff discipline: minimal hunks quoted verbatim in your report; Ocean
forensic review at merge. The PIPELINE-FIX-2 entries in W3_TRACKA_LOG.md
(#PIPEFIX P0-P7 + P4b) are your complete evidence base - read them first.**

# Identity
- **Agent:** WIRING-1 - activate the page-declaration integrity fix
  (PIPELINE-FIX-2 card 2, currently INERT), execute the APPROVED truth-set
  ceremony for exactly two pinned documents, and harden the corpus gate.

# Git ownership
- Base: main `ea8d8e8` - Branch: `wave4-wiring` - Worktree:
  `.claude/worktrees/mt4-wiring`. Own: the three call sites (#PIPEFIX P4b.5
  tabulates them), webapp/artifact_cache.py (key material hunk ONLY),
  corpus_gate.py (outcome-class check), tests/data/parser_expectations.json
  + dry-run truth data (the two ceremony entries ONLY), tests, W3 log
  (#WIRING section).

# Card A - the wiring (3 call sites)
`assess_document_integrity` takes `sheets` (intake object's page list;
str is refused with TypeError). No production caller passes it. Wire the
three sites named in #PIPEFIX P4b.5 - each already holds the intake object.
Census after wiring must reproduce #PIPEFIX P3.4 exactly: 157 flag carriers
/ 114 withdrawn / 43 kept / 0 raised over 3,367 docs.

# Card B - the cache-key material (REQUIRED with the wiring, same commit)
The analysis cache key is text_sha256(admissible_text(markdown))
(webapp/artifact_cache.py:638 area). admissible_text strips the header
carrying `pages: N`, and to_markdown is not injective - the adversarial
review DEMONSTRATED an honest 3-sheet document and a forged 1-sheet
document sharing one cache key with different correct answers. Add the
sheet/page-count evidence to the analysis key material (do NOT re-admit the
header - it carries the filename; the FILENAME-BOUNDARY seam is law).
Repo-wide grep for every reimplementation of the key derivation (the
FILENAME-BOUNDARY lesson: a second copy existed at telemetry/stated_counts).
This invalidates the whole v11 cache by construction - state that plainly;
Ocean's composed stage bump covers the re-measurement.

# Card C - the APPROVED ceremony (Gustavo, 2026-08-14, verbatim scope)
The ONLY approved pinned movement: `Regions/Regions.pdf` and
`Misc/Texas Bank.pdf`, review -> validated, because their
missing_declared_statement_page flags are FALSE (pages present as
unlabelled sheets; measured table in #PIPEFIX P4b). Requirements:
- enumerate EVERY expected field/status movement on both docs before
  running anything (flags ['missing_declared_statement_page'] -> [],
  outcome review->validated, risk high->clear derived; every audited
  balance/ADB field byte-identical);
- independent evidence unchanged: both audit CSVs untouched;
- ZERO unrelated pinned movement - the other three flag-carrying pinned
  docs (Builder June 2026, Columbia May 26 complete, Link Bank April)
  KEEP their flags (measured expectations in #PIPEFIX P4b);
- record IN THE EXPECTATIONS FILE ENTRIES + W3 log that the previous gate
  could not detect review<->validated movement inside its PASS class;
- preserve the motivating evidence (cite #PIPEFIX P4b tables);
- **if anything beyond the approved movement changes, STOP and report -
  do not adjust, do not re-baseline.**

# Card D - gate hardening (same branch)
corpus_gate.py buckets PASS = validated+review, so approved-vs-review
movement is invisible to it. Add a per-document OUTCOME-CLASS check to the
gate's own sub-checks: every pinned document's outcome class must equal
its expectations-file class, failing RED on any mismatch. Prove by
mutation: flip one expectation in memory -> gate RED; restore -> GREEN.
After the ceremony entries land, gate expects 102 validated / 4 review /
3 withheld (verify these numbers yourself against the expectations file -
do not trust this sentence).

# Hard rules
The forge fixture family (page content cannot fabricate a sheet boundary,
padding, str-footgun) must stay green at every commit. The 13 publishing
movers outside the pinned corpus (P3.5 named them) will move at the NEXT
archive run - expected, upward-only, already adjudicated; name them in
your report as expected movers. Nothing else moves: full-population
before/after over all 3,367 (the movers = 114 flag withdrawals, of which
13 publish + the 2 ceremony docs change outcome; everything else
byte-identical).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-14 batch-3 entry in WAVE2_EXECUTION_LOG.md
first. Base main `ea8d8e8` (v11, registry 68, suite 3,769). Run of record:
`discovery_reports/2026-08-14T214345.671986-0000-d5c75ff6` (validated 2,357 /
review 22 / withheld 69 / failed 919 / deferred 13; 3,380 distinct shas).
Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
open the webapp_data sqlite index - it writes on read); $0 vendor spend;
private uniquely-named scratchpad subdir (cells have collided on the shared
top level). Long background shells get killed - run long proofs as
SEQUENTIAL single commands. Proof floor per branch: full default suite +
corpus-marked slice (MANDATORY - the corpus gate is structurally blind to
review<->validated movement inside its PASS bucket; proven in batch 3) +
`python corpus_gate.py` GREEN 106/3 + guards + conformance cross-product;
exit codes verbatim; every mover named by content_sha256 + outcome + field;
claimed != validated; zero movement outside your named populations; commit
incrementally with clean tree at the end; NEVER merge or push - Ocean runs
the train. ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed
everywhere: a document you cannot prove publishes nothing.

# Final report to Ocean
Pinned-exposure first (gate at your HEAD with the hardened check);
hunks verbatim; the ceremony enumeration table; census reproduction;
full-population sweep; proofs with exit codes; commits; risks.
