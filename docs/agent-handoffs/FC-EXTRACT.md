# Agent Handoff - FC-EXTRACT (batch 4, card 5)
Ocean reviews and merges; you never merge or push.
**Ruling (Gustavo): recover the actual printed transaction descriptions
STRUCTURALLY. Do not solve revenue classification by inventing
descriptions or by amount/source heuristics. Extraction first; revenue
logic stays downstream and untouched.**

# Identity
- **Agent:** FC-EXTRACT - the first_citizens layout extractor. The
  batch-3 rebuild validates 35 docs on balances/counts/reconciliation
  but flattens descriptions, so 12 description-keyed production fields
  are ZERO on 35/35 (verified_revenue_*, nsf, insurance, pos, ach,
  atm...; W3 #FI14.1) - revenue verification is impossible for this bank
  until the printed descriptions are recovered.

# Git ownership
- Base: main `ea8d8e8` - Branch: `wave4-fcextract` - Worktree:
  `.claude/worktrees/mt4-fcextract`. Own: analysis/first_citizens.py,
  tests, W3 log (#FCX). metrics.py/transaction_classifier.py/detect.py:
  ZERO-diff (they consume descriptions; they do not change).

# The work
Characterize FIRST: what do the OCR text layers of the 35 docs actually
carry for each posting's description, and where did the batch-3 reader
lose it (interleaved columns? section reflow? the #FI record documents
the flattening decision). Then recover structurally, preserving every
batch-3 gate: the control-record gate (_matches), summary closure,
per-section count+total checks, the daily-balance walk. Descriptions are
PUBLISHED FACTS: each recovered description must be the printed text of
that posting (no synthesis, no cross-row bleed - fixture a wrapped
description next to a money-bearing memo line).

# Expected movement (name it all)
The 35 validated docs stay validated with balances/ADB byte-identical;
description fields change (that is the point); the description-keyed
metrics move as a CONSEQUENCE - the pinned first_citizens doc's expected
recovery is measured in #FI14.1 (nsf 0->1, insurance 0->1/$494, pos
0->18, ach 0->5 - your result should restore those, and any audited-CSV
field must remain byte-identical; the pinned corpus gate must stay
GREEN with zero balance/ADB drift). Measure the same fields family-wide
and name every mover per doc. Zero movement outside first_citizens.

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
Characterization; the recovery design; per-doc mover table (pinned doc
first); family sweep; proofs; commits; risks.
