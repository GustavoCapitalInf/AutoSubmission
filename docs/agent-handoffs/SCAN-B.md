# Agent Handoff - SCAN-B (batch 4 refill; SCAN-SCOUT card B)
Ocean reviews and merges; you never merge or push.
**Scout-measured: +7 already publish in a ~200-line prototype
(proto_coreproc.py in scratchpad scan-scout-5fb5b603/); 33 addressable
(17 digital, 15 scanned, 1 mixed). This card is LARGER outside the
scanned population than inside it. The JHA-CELL pattern is your
precedent: register the PLATFORM, read the issuer off the document,
name no bank in code (guard scans comments too).**

# Identity
- **Agent:** SCAN-B - the second core-processor platform template
  (variant B sectioned + relationship to variant A that first_farmers
  already reads).

# Git ownership
- Base: main `707ba9e` - Branch: `wave4-scanb` - Worktree:
  `.claude/worktrees/mt4-scanb`. Own: one NEW module, registry entries
  (NEW registration + the first_farmers supersedes edge), tests, W3 log
  (#SCANB).

# Evidence (scout-verified; re-derive the 39-sha roster via sweep.py)
- Shared furniture: PAGE:/ACCOUNT:/DOCUMENTS:/TELEPHONE: plus the
  decisive TOTAL DAYS IN STATEMENT PERIOD mm/dd/yy THROUGH mm/dd/yy: N
  (hits exactly 39 archive docs and nothing else - scout-measured; but
  COMPOSE it with the summary-balance labels or it becomes a broad
  claimant).
- Variant B sections: LAST STATEMENT/MINIMUM BALANCE/N CREDITS/AVG
  AVAILABLE BALANCE/N DEBITS/AVERAGE BALANCE/THIS STATEMENT, then
  DEPOSITS / OTHER CREDITS / CHECKS / OTHER DEBITS / DAILY BALANCE.
- Oracle: printed credit count+total, debit count+total, begin+net==end,
  AND the DAILY BALANCE grid walked against the running ledger - five
  independent printings. Scout's refusals were all "recovered N,
  document printed M": preserve exactly that behavior.
- **The supersedes edge to first_farmers is MANDATORY** - without it its
  6 validated docs resolve ambiguous and regress (the JHA sibling
  pattern: full first_farmers population byte-identical, sweep it).
- The 15 scanned members are SouthState/UnitedCommunity glyph-corrupted
  ($00.00 for 500.00); the oracle refuses them today and MUST keep
  refusing - the card's honest value is digital-first. Name each refusal.
- One digital member carries Cyrillic U+0415 inside 'DATE' - font-
  encoding hazard; guard structurally (the money/date grammar must not
  silently read a look-alike), fixture it.
- The 7 prototype publishers: 8DB7534133814385.., A30FC5E65BC573AE..,
  C2DEBD927CAD21DE.., D15B05CDE8223B77.., D92C5112EB2B583F..,
  D9C32AF444276783.. (digital), ADE55A5BADF4DE8C.. (scanned, 20pp,
  434 credits/101 debits exact).

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
Characterization; the platform/issuer separation; supersedes proof;
per-doc outcomes incl. named refusals; whole-archive claim diff; proofs;
commits; risks.
