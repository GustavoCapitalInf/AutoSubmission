# Agent Handoff - CORE-ENCLOSURES (batch 8, card 1 - the largest family in the archive: the core-processor "Enclosures / Average Ledger" issue, 58 documents)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** CORE-ENCLOSURES - census rank 1 (`core_enclosures_avgledger_leading_counts`,
  n=58, adversarially verified: identity confirmed on 16 sampled, 4 misfiled
  named, honest ceiling 30-36). The core-processor deposit block printed
  under ~30 small-bank mastheads, most printing NO bank name in the text
  layer: `<PRODUCT>  Number of Enclosures N / Account Number ... / Statement
  Dates m/dd/yy thru m/dd/yy / Previous Balance ... / Days in the statement
  period N / <n> Deposits/Credits ... Average Ledger / <m> Checks/Debits ...
  Average Collected / Service Charge / Interest Paid / Ending (or Current)
  Balance`, an ASCII pipe box `Total For This Period | Total Year-to-Date`,
  sectioned ledgers and a 3-up `Daily Balance Information` grid on ~2/3.
  This is the next grammar of the core-processor complex (§LCPERIOD,
  §GRAM4, §DESCATTRIB lineage) - the complex was frozen in batch 7 until
  DESC-ATTRIB landed; it has, and `tables.attributed_descriptions` is the
  ONLY description path you may use.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave8-coreenc` - Worktree:
  `.claude/worktrees/mt8-coreenc`. Own: ONE new registration in the
  core-processor family (name yours, stated; sibling discipline: coexistence
  with core_processor_counted / daily / sectioned / fiserv_premier /
  farmers_merchants / linkbank / capital_one proven by the conformance
  cross-product and a family replay of every existing claimant - their
  published payloads byte-identical), registry entries (NEW only; pins in the
  same commit), tests, W3 log (#COREENC). Do NOT touch the existing
  core-processor modules or `analysis/tables.py` (CORE-ISSUES-2 and
  DESC-COLUMNS run in parallel on the complex; coordinate populations by sha
  list - overlap must be zero, prove it).

# The evidence base (read the census record for rank 1 in full, including the four misfiles)
- Register on FURNITURE (Enclosures / Average Ledger / Average Collected /
  the pipe box / Daily Balance Information), never a masthead: the
  institution is image-only on most members. Label drift is real: Previous
  vs Balance Last Statement; Ending vs Current vs Balance This Statement;
  Service Charge vs MAINTENANCE CHARGE; Enclosures vs Images. Banners
  duplicated 2-4x. Two ledger arrangements; debit-side trailing minus.
- The four misfiles the verifier named are NOT yours: `8CCAE7DD…` (a
  six-branch OK bank, different processor - WELCH's family), `5ED19A08…`
  (same vocabulary, order-scrambled text layer) and the other two in the
  record; prove your detector refuses them.
- Three gates, all printed: count(rows) == printed count per direction;
  sum(rows) == printed total per direction; the last row of each day ==
  the Daily Balance Information cell where the grid prints. Where the grid
  does not print, the ADB doctrine decides withheld vs validated - say the
  ceiling per document BEFORE implementing.

# Expected archive movement
Up to 58 failed/no_parser_matched → validated/withheld (verified ceiling
30-36 validated); every mover named; zero movement outside the named
population; every existing core-processor claimant byte-identical; the
stratified probe proves zero new claims outside the family.

# Report
The re-derived population (with the misfiles refused); the per-document
ceiling table; hunks verbatim; the mutation table; the family replays (yours
and every sibling's); the probe; the sweep; proofs with exit codes; the
privacy grep count; commits; risks.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the batch-7 entry in WAVE2_EXECUTION_LOG.md first;
your predecessors' W3_TRACKA_LOG.md sections are the standard (batch 7's
§DECLINESE/F/G, §SCANFINISH, §TANGERINE, §DESCATTRIB, §REPAIRDOC, §CURRSRC,
§PRIVACY3 are the most recent). Base: main at this handoff's commit
(ANALYSIS_STAGE_VERSION 15, OCR v3, registry 75, suite
5,857, corpus-marked 30, `python corpus_gate.py` GREEN
105 PASS / 3 WITHHELD / 1 REFUSED with verdicts 102 validated / 3 review / 3 withheld / 1 refused, the pinned currency surface
108/108 = 14 CAD / 94 USD (+1 pinned refusal) and the pinned provenance surface 108/108 = 89 schema_default / 7 institution_default / 7 product / 4 jurisdiction_default / 1 printed (+1 pinned refusal)). Run of
record: `discovery_reports/2026-08-23T020128.909387-0000-356a4269` (mode --scanned; validated 2,469 / review 17 / withheld 72 / failed 809 / deferred 13 over 3,380 distinct shas; analysis regenerated
cold at v15 under the deterministic settings key `24675EF06C2E08DD6803362ACD56045607BBFD3B80642A849D08D0DF541B5CAC`).

THE CENSUS IS COMMITTED: `docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md` — the 598 digital no-parser documents
as 91 printed-identity families (top 14 adversarially verified) with FULL sha
lists, plus the withheld-61 report. Staff from it; re-derive your family by
live detection replay / artifact text before writing a line of code, and name
every document by content_sha256. A family's folder labels are NOT its issuer
(batch 7: "tangerine" was EQ Bank; "ATB Chequing" was a Consolidated
Statement).

THE ARCHIVE INSTRUMENT IS COMMITTED - use it, do not rebuild it:
`python -m tools.regfp_zero_movement_sweep --rows discovery_reports/2026-08-23T020128.909387-0000-356a4269/rows.csv --data-dir
webapp_data --baseline-settings-key 24675EF06C2E08DD6803362ACD56045607BBFD3B80642A849D08D0DF541B5CAC --start A --end B --out <private>`
run at your branch HEAD (chunk with --start/--end; the counts add). Every
`moved` / `no_payload_now_publishes` / `payload_now_raises` finding must be
inside your NAMED population by content_sha256, or it is a regression you
must explain or remove. The tool reports field NAMES only; where your card
moves a field on purpose, prove what moved INSIDE it with your own leaf-diff
(never print document text or figures into a report). A family replay over
every document your changed `parse` can run on (parse runs only on claimed
documents; conformance pins detection) is the proportionate proof for a
closure round; the full sweep is owed once per card at its final production
tree.

PRIVACY (batch-7 BLOCK, now a standing rule): NO archive content may enter
tracked source - not a balance, an amount, a name, an account number, nor an
"example" block copied from a document; fixtures are INVENTED. Before your
final commit, build the list of every printed figure/name/account/date token
from your family's documents and grep the whole branch diff for each: the
count must be 0 and you report it.

Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
the webapp_data sqlite index; the read-only helper pattern in
`tools/regfp_zero_movement_sweep.py` enumerates every OCR partition); $0
vendor (no hosted model call anywhere, tests included); private uniquely-named
scratchpad subdir. Long proofs as SEQUENTIAL single commands, or detached
processes launched via `C:\Program Files\Git\bin\bash.exe` with POSIX paths
and tracked via `tasklist` (never MSYS `kill -0`); background tool commands die
at ~10 minutes; a completion signal must be producible only by completion
(append your own `EXIT=<code>` terminator to a durable log; keep the logs -
a headline number with no log does not exist). Mutation harnesses restore
with `git checkout --` and are only correct on a CLEAN tree (batch 7: one
harness silently reverted an uncommitted edit); OneDrive holds file handles -
retry transient PermissionErrors rather than scoring them.

Proof floor per branch (exit codes verbatim): full default suite (durable
log); corpus-marked slice; `python corpus_gate.py` GREEN (105 PASS / 3 WITHHELD / 1 REFUSED;
verdicts 102 validated / 3 review / 3 withheld / 1 refused; currency 108/108 = 14 CAD / 94 USD (+1 pinned refusal); currency_source
108/108 = 89 schema_default / 7 institution_default / 7 product / 4 jurisdiction_default / 1 printed (+1 pinned refusal)) unless your card is a ceremony that enumerates otherwise; the
CANONICAL guard set (tests/test_no_statement_hardcodes.py
tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py
tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -
252 at registry 75 before your changes) and the
CANONICAL conformance set (tests/test_parser_conformance.py
tests/test_parser_registry_entries.py tests/test_parser_detection_markers.py
tests/test_parser_registry.py tests/test_parser_crash_shapes.py
tests/test_parser_exception_boundary.py tests/test_count_semantics.py -
1,164 at 75 x 74; registry pins
updated in the SAME commit as any registration); a MUTATION TABLE for every
gate you add or touch, run WITHOUT `-x` so every killer is named, every
mutant applied as DOCUMENTED (batch 7: a "reorder" mutant that actually
deleted the reading pinned nothing) - a test named after a gate is not a test
of that gate; the archive sweep above. Every mover named by content_sha256 +
outcome + field; claimed != validated; zero movement outside your named
populations; ledgers record measurements, not inferences (every headline
number must reproduce from committed evidence - commit your instruments
under tools/ when they produce headline numbers); characterize before code;
structural capability over literals (no statement-specific constants -
guard-enforced; no merchant/lender vocabularies; institution furniture such
as phone ladders, PO boxes, routing numbers and domains is allowed and must
be justified as furniture); a stratified non-target probe (>=400 documents,
all scanned + all Canadian included) for any new registration; commit
incrementally, clean tree; NEVER merge or push - Ocean runs the train;
ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed everywhere: a
refusal is an answer and an exception is not (close every `ValueError` /
`TypeError` path a mangled token can reach - `str.isdigit()` admits
superscripts; sort keys must not compare `None`).

Doctrine binding: the ADB doctrine (08-16 batch-5 entry, ADB-SPLIT: one
user-facing calendar-day ADB over the printed period; withheld when daily
evidence does not cover it; bank averages are evidence-only),
docs/moneythumb-replacement/CURRENCY_DOCTRINE.md (native currency canonical;
no FX; no cross-currency aggregation; fail closed across units; jurisdiction
defaults are affirmative evidence, never absence rules - a new Canadian
reader publishes the schema default and NAMES itself as a future mover
unless a packet exists), the L-1 rule (single-account schema: never publish
one account and silently drop another; the ONLY admitted idle-sibling
exemptions are `No Transactions This Period` and the batch-7 yield-only
sibling bounded by the platform's own Dividends column - both published
silently today, owned by SIBLING-OMISSION-SURFACE), and the repair doctrine
(batch 7: parsers never write an amount; discard-and-flag or fail closed).
Truth-set movement outside an approved ceremony = STOP and report. The
machine is shared with the other batch-8 cells - keep probes light and
sequential.

# Final report to Ocean
The card's own report section, plus the W3 section in the shape your
predecessors set - measurements, not inferences; every number reproducible
from committed evidence; the privacy grep count; risks last.
