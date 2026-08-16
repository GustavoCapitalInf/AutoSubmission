# Agent Handoff - PKG-CURRENCY (batch 6, card 12 - the package layer stops mixing currencies)

Ocean reviews and merges; you never merge or push.
**Doctrine card: read docs/moneythumb-replacement/CURRENCY_DOCTRINE.md
FIRST - section F is your charter verbatim.**

# Identity
- **Agent:** PKG-CURRENCY - `webapp/app.py::_package_analysis` sums ADB
  (weighted), credits, debits, revenue, lender totals and every other
  financial figure across the package's jobs with ZERO currency awareness
  (the word "currency" does not appear in webapp/app.py - verified on the
  base commit). `30,000 CAD + 20,000 USD != 50,000 package ADB`. The
  doctrine: same-currency packages aggregate normally; multi-currency
  packages preserve statement-level results and STOP cross-currency
  aggregation until a package-level FX policy is explicitly approved.

# Git ownership
- Base: main `90e9eb6` - Branch: `wave6-pkgcurrency` - Worktree:
  `.claude/worktrees/mt6-pkgcurrency`. Own: the package aggregation path
  in webapp/app.py (_package_analysis and its render/CSV/XLSX consumers
  as far as the currency behaviour requires), tests, W3 log (#PKGCURR).

# The work
1. MEASURE FIRST: where does each statement's currency live in
   job.analysis after batch-5's CURRENCY-1? What value does a document
   with no currency evidence carry today (null? schema default? - the
   CURRENCY-1 record in the W3 log is your map). Your design must handle:
   all-same-currency, mixed known currencies, and unknown/null currency,
   and say which bucket each of the archive's package-relevant shapes
   falls into.
2. Same-currency package: aggregate exactly as today, byte-identical
   output plus the package currency denomination surfaced once (doctrine
   D: ONE ADB metric, denominated - e.g. "$42,500 CAD").
3. Multi-currency package: statement-level results preserved and
   presented per currency; every cross-currency total REFUSED (absent or
   explicitly marked not-computable - decide with the existing UI/JSON
   contract and justify; silent zero is forbidden; fabricating a
   converted number is forbidden).
4. Unknown-currency statements: fail closed - they must not silently
   join a same-currency pool as if proven. Decide and justify the
   honest presentation (their own bucket, package totals refused, or
   flagged) from the doctrine's fail-closed clause.
5. API compatibility: _package_rows/_package_csv/_package_xlsx and the
   version-3.0 deprecated aliases must degrade honestly for
   multi-currency packages - no consumer may receive a mixed-unit number.
   Census the consumers before choosing the shape.

# Expected archive movement
ZERO on the 3,380 (discovery does not run packages). The webapp package
path changes behaviour ONLY for multi-currency and unknown-currency
packages; single-currency packages byte-identical (prove with a
fixture-level before/after over representative package shapes).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base main `90e9eb6` (v13, OCR v3, registry 72, suite 4,511,
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
NOTE: WORKER-PRIVACY (running this batch) owns webapp/worker.py and may
touch webapp/ exception sinks; your hunks are the package aggregation
region of app.py - stay out of exception-boundary hunks and note any
unavoidable adjacency in your report.

# Final report to Ocean
The currency-field map from measurement; the three-bucket design with
justifications; the consumer census; the single-currency byte-identity
proof; fixture proofs for mixed and unknown; hunks verbatim; proofs with
exit codes; commits; risks.
