# Agent Handoff - UNKNOWN-ISSUER (batch 4, card 2)
Ocean reviews and merges; you never merge or push.
**Approved policy (Gustavo 2026-08-14): where statement structure is
validated but issuer identity is not proven, publish bank=None. NEVER infer
issuer from filename, folder label, template similarity alone, nearby
corpus organization, or weak branding. Parser/layout identity and
bank/issuer identity are SEPARATE FACTS. A structurally validated
statement with unknown issuer beats a confidently wrong bank name.**

# Identity
- **Agent:** UNKNOWN-ISSUER - two evidence-complete populations, +11
  expected: community_section's 5 issuer-less docs + the French-caisse
  template family (6 of 16 reconcile).

# Git ownership
- Base: main `ea8d8e8` - Branch: `wave4-unkissuer` - Worktree:
  `.claude/worktrees/mt4-unkissuer`. Own: analysis/community_section.py
  (the issuer-refusal path ONLY), one NEW module for the French-caisse
  template, registry entries (NEW only), tests, W3 log (#UNKISSUER).

# Card 1 - community_section unknown issuer (+5)
W3 #JHA J9.2: five documents reconcile against every printed figure but
name no issuer; the parser currently declines them (fail-closed pending
this exact ruling). Change the refusal to publication with bank=None.
The masthead issuer read (label-corroborated, line-scoped after the JHA
review closures) stays EXACTLY as is for documents that do print an
issuer - zero movement on the 56 current claims (full family sweep).
Verify the platform tolerates bank=None end-to-end (Statement.bank is
str|None; check by_bank_label consumers, folder-agreement rollup,
webapp surfaces - name what displays where).

# Card 2 - the French-caisse template (+6 of 16)
W3 #UNID-B card 8 (UB5): a French template family in the Unidentified
folder names NO institution anywhere; only folder labels ever suggested
"Desjardins" and the cell proved folder labels wrong twice in one day.
Register it TEMPLATE-KEYED (furniture: the FACTURATION DETAILLEE fee
table terminating the ledger structurally; detached minus with comma
decimals - parse_french_amount exists; the MM JJ date pair colliding
with space-thousands amounts unless anchored on a following capital),
bank=None, registration id descriptive of the TEMPLATE not an issuer.
analysis/desjardins.py stays zero-diff; its 6 existing claims
byte-identical (sweep). 6 reconcile / 10 fail closed named (4
chain-broken per the scout). The 16 hashes: re-derive from the run of
record; UB5 has the structural description.

# Hard rules
Registry 68 -> 69 (one new registration; community_section's is
unchanged). Conformance cross-product to 69x68 with a fixture carrying
template furniture only. No excluding/supersedes edges expected - prove
additive (whole-archive claim diff: only your populations move).

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
Characterization confirmation, diffs, both family sweeps, whole-archive
claim diff, probe, proofs, commits, risks.
