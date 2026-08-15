# Agent Handoff - SCAN-A (batch 4 refill; SCAN-SCOUT card A)
Ocean reviews and merges; you never merge or push.
**Scout-measured: +2 validated already demonstrated in prototype, ceiling
4. Confidence VERY HIGH. The scout's read-only instruments live in the
session scratchpad `scan-scout-5fb5b603/` (keys.py, harness.py,
exp_fifththird.py, exp_ft2.py) - reuse them.**

# Identity
- **Agent:** SCAN-A - the Fifth Third SCANNED issue of the layout
  `fifth_third` already parses (batch 3, UNID-PACK-B).

# Git ownership
- Base: main `707ba9e` - Branch: `wave4-scana` - Worktree:
  `.claude/worktrees/mt4-scana`. Own: analysis/fifth_third.py, its
  registry entry markers, tests, W3 log (#SCANA).

# Population (4 distinct shas, all scanned/failed/unclaimed)
53906D0EFDB5A5362D29AF88A5D773882CBF19B40F7832EC43A6A2A9D3304035 (-> validated, measured; REVIEW POINT: publishes adb=-53.54 - corroborate against printed daily balances before shipping)
6F57BE0899494DF11BAFB67741430A5A3537C623421D2A746232EA02B93AF7BC (-> validated, measured)
64A4958471C2E1625B1918EADB97C4B491520BEF5A560AB5E8BA94835A3C7645 (OCR prints '13. Deposits / Credits' - the stray full stop loses the count; the section head prints 13 correctly and is the corroborating second printing that makes a one-character tolerance safe)
CDB8A6CC9F8EFB5FAC151979BFA9141697595F9B46A88A623A2DB1D380DF8629 (summary + all heads + closing identity agree exactly; fails at scanned-detail row recovery - genuine work, take it only if the oracle holds)

# The two obstructions (scout-named exactly)
1. required('print_stream', ...) demands the ELECTRONIC print-stream
   header (FTCSTMT...UDSPDFSTMT) a scan cannot carry. Replace with
   evidence a scan does carry - and MEASURE THE BLAST RADIUS over all
   3,380 archive shas (the scout measured the widened set claims exactly
   the 13 current + these 4 and nothing else; reproduce that sweep with
   your final markers - exp_fifththird.py holds the pattern).
2. _SUMMARY_RE's middle group is (.*?) without DOTALL; the scan puts one
   summary component per line. Bound any cross-line span (<=400 chars) -
   an unbounded span could pair a beginning balance with a foreign
   ending balance.

# Oracle (already shipped; unchanged)
fifth_third's three instruments: closing identity, every component
agreeing with its own section head (including absent==absent), row
totals. A hallucinated or dropped row breaks two independent printings.
All 13 currently-claimed docs byte-identical (full family sweep).

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
Population outcomes; marker blast-radius sweep; diffs; family sweep;
proofs; commits; risks.
