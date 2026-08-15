# Agent Handoff - SCAN-SCOUT (batch 4, card 8 - READ-ONLY scout)
**You change NOTHING: no commits, no branch, no repo edits. Prototype
code lives in your private scratchpad subdir only. Your product is an
evidence report.**

# Identity
- **Agent:** SCAN-SCOUT - characterize the scanned-document population
  so batch 4/5 can staff scanned-capability cells on measured evidence.

# The survey (run of record d5c75ff6)
1. Census: every doc classified scanned (rows.csv `classification`) +
   its current outcome; group by folder label AND by structural family
   (mastheads/furniture in the OCR text, not folder names).
2. OCR reality: for a stratified sample (>=40 docs), read the cached OCR
   artifacts by direct path - text quality, truncation flags, page
   coverage, whether the local/free OCR output carries a readable ledger
   at all. NO new OCR runs, NO vendor calls ($0) - cache-first is the
   platform law; report where cache artifacts are missing entirely.
3. Prototype-measure 3-5 candidate families end-to-end in the
   scratchpad: can an existing parser's grammar read the OCR text as-is?
   What refuses (dates? money? structure?) and is the refusal an OCR
   artifact (rescan/regeometry could fix) or a genuine capability gap?
4. Rank implementation cards by (validated-gain x confidence), each with
   its named hash population, printed-shape description, the oracle a
   reader would gate on, and the fail-closed risks (fabricated rows and
   hallucinated values are the class killers - say how each card's
   oracle refuses them).

# Hard rules
Truncation/integrity detection is evidence, not noise - a truncated OCR
artifact is a named refusal cause. If a family cannot be validated
without new OCR spend, report the cost/benefit; do not spend.

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
The census; the OCR-quality findings; prototype measurements; ranked
cards with hash populations; risks.
