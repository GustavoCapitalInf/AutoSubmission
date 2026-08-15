# Agent Handoff - MG-C (batch 4, card 6)
Ocean reviews and merges; you never merge or push.
**Keep money grammar GENERALIZED in analysis/money.py - no parser-local
regex variants. The MONEY-GRAMMAR discipline applies: differential
matrix coverage for any money.py change, declared divergences, byte-
identity sweep over the full archive with every mover named.**

# Identity
- **Agent:** MG-C - two staged follow-ups: MG-C1 chase_export wrapped
  rows; MG-C2 the fail-open `or 0.0` money-read sites.

# Git ownership
- Base: main `ea8d8e8` - Branch: `wave4-mgc` - Worktree:
  `.claude/worktrees/mt4-mgc`. Own: analysis/money.py (if needed),
  analysis/chase.py chase_export region, the parser files whose `or 0.0`
  sites you close (SEE EXCLUSION below), tests, W3 log (#MGC).

# MG-C1 - chase_export wrapped rows
W3 #MG7: the three corrected sign movers (112431717DA1, 5A29258D7626,
5C93775BBA87) publish correct signed ledgers but stay withheld_adb -
wrapped lines like `-$702.32 $9,610.54` leave rows short of the full
grid. Recover the wrapped-row shape structurally in the chase_export
reader; target: the three docs reach an honest terminal state (validated
if their instruments close; if they stay withheld for an independent
reason, name it). The #MG7 nuance is your fixture source: on 7302/7501
head drops rows base kept (description '-' vs ''). All other
chase_export docs byte-identical.

# MG-C2 - the fail-open `or 0.0` class
W3 #MG8.2 catalogued ~12 sites in ~10 parsers where a money-read refusal
collapses to 0.0 (`_money(x) or 0.0` and kin) - a refusal becoming a
published zero is the fail-open shape the wave exists to kill.
RE-DERIVE the site list on current main (batch 3 moved code; new parsers
may have added sites - grep the whole analysis layer, report the census).
For each site: refusal must propagate (decline/withhold/None-field), not
zero. **EXCLUSION: if sites exist in first_citizens.py or woodforest.py,
LIST them but do not edit - FC-EXTRACT and WOODFOREST-INIT own those
files this batch; Ocean sequences the leftovers.** Differential fixtures
per site (pre-fix publishes 0.0, post-fix refuses); full-archive sweep:
byte-identical except docs where a genuine refusal now surfaces - name
every one with its printed cause.

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
MG-C1 doc outcomes; MG-C2 site census (edited/excluded/clean); sweeps;
proofs; commits; risks.
