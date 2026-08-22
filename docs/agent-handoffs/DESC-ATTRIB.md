# Agent Handoff - DESC-ATTRIB (batch 7, card 2 - P0: a description stays attached to its own posting)

Ocean reviews and merges; you never merge or push.
**Gustavo's ruling (2026-08-21), binding: "Batch 7 P0. Fix the
core-processor description-row misattribution before expanding that family
further. Descriptions must stay attached to the correct transaction so
lender/funder attribution remains trustworthy."** No core-processor
expansion is staffed in batch 7 until this lands.

# Identity
- **Agent:** DESC-ATTRIB - on the core-processor complex the published
  description carries the PRECEDING row's merchant text on 111 of 279
  measured rows (40%; W3 §GRAM4 G7.7). Monetary fields are untouched and
  gated; descriptions are not, which is why fourteen gates cannot see it.
  Fix the attribution in BOTH readers that share the call, measure the
  movement on every already-validated document of the complex, and add the
  gate that makes description attribution visible from now on.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-descattrib` -
  Worktree: `.claude/worktrees/mt7-descattrib`. Own:
  analysis/core_processor_daily.py, analysis/core_processor_counted.py,
  analysis/tables.py (`dated_cells` / `DatedCell` - ONLY if the fix belongs
  there, and then every other caller proven byte-identical), their tests,
  W3 log (#DESCATTRIB). analysis/core_processor_sectioned.py: READ it to
  census whether the class exists there; touch it only if it shares the
  defect and say so. No registration, no detection change, no widening
  anywhere. No other batch-7 cell owns these files.

# The evidence base (read first: W3 §GRAM4 G7.7; §LCPERIOD L5.2/L5.3; the `_described` docstring at core_processor_counted.py:528; `DatedCell` at tables.py:250)
- `_described(cell.described)` is the byte-identical call in both readers.
  `DatedCell.described` is "what the statement printed BETWEEN the date and
  the amount"; on the flattened layer a block of merchant lines belonging to
  row k lands in row k+1's span. The clearest printing is `91A2DE99...`
  2026-03-02: THE HARTFORD's own row publishes a bare `Preauthorized Debit`
  and THE HARTFORD's name is published on ULISES IBARGUREN's row. Twelve
  rows are additionally cut mid-token by the 200-character cap.
- Per-document split measured in G7.7 on core_processor_counted: 1ADC8AD7
  22 of 48 rows, 7B3B8113 30/49, 91A2DE99 30/60, A3539AB3 1/30, C80C0CC8
  0/2, FC385FC2 0/9. core_processor_daily's 13 validated documents carry the
  same class, UNMEASURED - measure them.
- KAPITUS, HEADWAY, ONDECK and CELTIC BANK appear in these statements. A
  lender name on the wrong posting is a wrong answer in the one place this
  platform is asked for one. Doctrine §E (lender-matching separation): the
  attribution rule must come from the document's printed structure, never
  from a lender or merchant vocabulary.

# The work
1. MEASURE FIRST, before any code: for all validated documents of the
   complex (13 daily + 8 counted - re-derive by live detection replay) and
   any sectioned documents sharing the span logic, a per-row classification
   of what the span contains: own label only / own label + a block belonging
   to the row BEFORE / a block belonging to the row AFTER / indeterminate.
   State the structural rule you used to decide ownership (position relative
   to the previous amount, the row's own physical line vs continuation
   lines, the layer's interleaving pattern). That rule IS the design.
2. Implement it: the block is published on the row it belongs to, or -
   where ownership is indeterminate - on NO row (a bare label), never on the
   wrong one. Both readers through ONE code path (the helper-clone guard is
   live). Decide the 200-character cap honestly: a cut mid-token is a string
   the bank did not print - raise the cap with a stated bound or cut at a
   token boundary, and name the rows that change because of it.
3. The gate: a description-attribution oracle the readers can fail against -
   a fixture family for the three printings `dated_cells` documents
   (wrap-below, interleaved block, several rows on one line) with expected
   per-row descriptions, plus the mutation table (revert to the old span ->
   a named test fails; attribute to the row after -> a named test fails;
   drop the indeterminate branch -> a named test fails).
4. The movement report: for every document, a row-level before/after of
   descriptions with counts per class; everything else - amounts, dates,
   directions, counts, totals, the grid, the ADB, verdicts, flags - proven
   byte-identical by leaf-diff of the full published payload with
   `description` masked, then the unmasked diff of descriptions only.

# Expected archive movement
Description-only movement on the complex's validated documents (named by
sha; up to 21 plus any sectioned). ZERO pinned movement - no pinned document
is published by these registrations (verify on the base tree:
tests/data/parser_expectations.json names no core_processor_* parser).
ZERO outcome/verdict movement anywhere. The archive sweep reports `moved`
only for your named shas; prove the inside of the moved field yourself.

# Proof floor
The standing floor + the per-row measurement table + the leaf-diff proof +
the mutation table.

# Report
The attribution rule and its evidence; the per-document before/after row
classes; hunks verbatim; the fixture family; the mutation table; the sweep;
proofs with exit codes; commits; risks - especially every row whose
ownership was indeterminate and what it publishes now.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-20 batch-6 entry in WAVE2_EXECUTION_LOG.md
first; your predecessors' W3_TRACKA_LOG.md sections are the standard. Base:
main at this handoff's commit (ANALYSIS_STAGE_VERSION 14, OCR v3, registry
74, suite 5,374, corpus-marked 29, `python corpus_gate.py` GREEN 106/3 with
verdicts 102 validated / 4 review / 3 withheld and the pinned currency
surface 109/109 = 14 CAD / 95 USD). Run of record: `discovery_reports/2026-08-21T014415.938236-0000-7a317445` (mode --scanned;
validated 2,456 / review 16 / withheld 63 / failed 832 / deferred 13 over
3,380 distinct shas; analysis regenerated cold at v14 under the deterministic
settings key `D3370EEBDCB87892A2739BCB0D882A66E72DCBFAB2553101111157B5A231DE24`).

THE ARCHIVE INSTRUMENT IS COMMITTED - use it, do not rebuild it:
`python -m tools.regfp_zero_movement_sweep --rows discovery_reports/2026-08-21T014415.938236-0000-7a317445/rows.csv --data-dir
webapp_data --baseline-settings-key D3370EEBDCB87892A2739BCB0D882A66E72DCBFAB2553101111157B5A231DE24 --start A --end B --out <private>`
run at your branch HEAD (chunk with --start/--end; the counts add). Every
`moved` / `no_payload_now_publishes` / `payload_now_raises` finding must be
inside your NAMED population by content_sha256, or it is a regression you
must explain or remove. The tool reports field NAMES only; where your card
moves a field on purpose, prove what moved INSIDE it with your own leaf-diff
(never print document text or figures into a report).

Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
the webapp_data sqlite index); enumerate per document by the run's own keys
(the sweep tool shows how) - never by one settings_key; $0 vendor (no hosted
model call anywhere, tests included); private uniquely-named scratchpad
subdir. Family populations by live detection replay or artifact-store
enumeration, NEVER rows.csv parser_id alone. Long proofs as SEQUENTIAL
single commands, or detached processes launched via `C:\Program
Files\Git\bin\bash.exe` with POSIX paths and tracked via `tasklist` (never
MSYS `kill -0`; the PATH `bash` is the WSL launcher and exits silently);
background tool commands die at ~10 minutes; a completion signal must be
producible only by completion (append your own `EXIT=<code>` terminator to a
durable log; "log non-empty" is pytest's progress dots).

Proof floor per branch (exit codes verbatim): full default suite;
corpus-marked slice; `python corpus_gate.py` GREEN (106/3; verdicts 102/4/3;
currency 109/109) unless your card is a ceremony that enumerates otherwise;
the CANONICAL guard set (tests/test_no_statement_hardcodes.py
tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py
tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -
242 at registry 74 before your changes) and the CANONICAL conformance set
(tests/test_parser_conformance.py tests/test_parser_registry_entries.py
tests/test_parser_detection_markers.py tests/test_parser_registry.py
tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py
tests/test_count_semantics.py - 1,151 at 74 x 73; registry pins updated in
the SAME commit as any registration); a MUTATION TABLE for every gate you
add or touch - a test named after a gate is not a test of that gate: weaken
or revert each gate and name the test that fails; the archive sweep above.
Every mover named by content_sha256 + outcome + field; claimed != validated;
zero movement outside your named populations; ledgers record measurements,
not inferences (every headline number must reproduce from committed
evidence); characterize before code; structural capability over literals
(no statement-specific constants - guard-enforced; no merchant/lender
vocabularies); commit incrementally, clean tree; NEVER merge or push - Ocean
runs the train; ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed
everywhere.

Doctrine binding: the ADB doctrine (08-16 batch-5 entry, ADB-SPLIT: one
user-facing calendar-day ADB over the printed period; bank averages are
evidence-only; MoneyThumb's banking-day figure is never truth) and
docs/moneythumb-replacement/CURRENCY_DOCTRINE.md (native currency canonical;
no FX; no cross-currency aggregation; fail closed across units; jurisdiction
defaults are affirmative evidence, never absence rules). Truth-set movement
outside an approved ceremony = STOP and report. The machine is shared with
the other batch-7 cells - keep probes light and sequential.

# Final report to Ocean
The card's own report section, plus the W3 section in the shape your
predecessors set - measurements, not inferences; every number reproducible
from committed evidence.
