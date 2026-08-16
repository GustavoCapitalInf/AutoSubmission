# Agent Handoff - DECLINES-D (batch 6, card 9 - the parser_declined pool, fourth sweep)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** DECLINES-D - the run of record has 132 documents where a
  registered parser CLAIMED and then DECLINED with a named reason. This is
  the third declines sweep (B and C landed +28/+21 in batch 3); the pool
  refreshed. Each decline reason is either (a) a reader gap on an attested
  printing - fix generically, (b) an honest refusal of a document that is
  not a parseable statement - leave it, name it, or (c) a template issue
  belonging to a family card - route it (FISERV-ISSUE3, GRAM-4, COLUMBIA-5
  are live this batch; check overlap by sha before touching).

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-declinesd` - Worktree:
  `.claude/worktrees/mt6-declinesd`. Own: the decliner modules you take up
  (each fix generic, evidence-gated), tests, W3 log (#DECLINESD).

# The evidence base (run 2e3ea385 declined_clusters; re-derive, don't trust)
core_processor_sectioned 22 · huntington 12 · wilson_muir 11 ·
community_section 9 · bmo_ca_business 6 · capital_one 6 · navy_federal 6 ·
chase 4 · citizens 4 · core_processor_daily 4 · first_citizens 4 ·
fiserv_premier 4 (likely = FISERV-ISSUE3's four - verify by sha and if so
they are NOT yours) · square_checking 4 · cibc_french 3 · tail below 3.
Start with the named-reason census: group the 132 by (parser, decline
reason), rank by (population x fix-confidence), take the top groups that
fit one disciplined branch. DECLINES-B/C's records (§ in W3 log) are the
method model: the reason is the card.

# Hard rules
- No speculative promotions: a fix must cite the attested printing it
  reads and the oracle that gates it. "It parses now" is not evidence.
- Woodforest-style period-boundary transactions: the ADB doctrine is
  RATIFIED - no generic one-day-outside rule exists; an initialization
  event is opening state only (ADB-DOCTRINE.md). Any decline whose remedy
  would need a doctrine change gets NAMED and escalated, not fixed.
- Any pinned document in a touched family: full published-block
  byte-identity or a named mover with Ocean informed BEFORE merge.

# Expected archive movement
Only within the (parser, reason) groups you take, every mover named by sha;
declines you do NOT take stay byte-identical. State the honest ceiling per
group before you code it (claimed != validated).

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
The reason census over all 132; the groups taken with per-group ceilings
and results; overlap check against the three family cards; the untouched
declines' byte-identity; hunks verbatim; proofs with exit codes; commits;
risks.
