# Agent Handoff - FROST-OZK (batch 8, card 5 - two Texas/Arkansas bank printings with load-bearing summaries: Frost (9) and Bank OZK (8))

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** FROST-OZK - census ranks 6 and 7:
  - `frost_bank_business_checking` (n=9; verified 8-9: prototype reconciled
    every printed oracle on every document). Monospace mainframe print: `FOR
    INFORMATION CALL 210-220-5111 / 361-844-1001 OR 1-800-513-7678`,
    `STATEMENT ISSUED mm-dd-yyyy`, banner `FROST BUSINESS CHECKING : ACCOUNT
    NO.`, an ASCII box `| DEPOSITS | WITHDRAWALS |` over `BALANCE LAST
    STATEMENT | NO. | AMOUNT | NO. | AMOUNT | BALANCE THIS STATEMENT`, dashed
    rules `---- DEPOSITS/CREDITS ----` / `---- DAILY BALANCE ----`. The
    summary is a bare run of six numbers bound POSITIONALLY by the rule-drawn
    header; DEPOSITS/CREDITS prints TWO transactions per physical line
    separated by `|`. THE TRAP the verifier found: the printed withdrawal
    `NO.` EXCLUDES `SERVICE CHARGE/FEE` rows while the printed withdrawal
    `AMOUNT` INCLUDES them - a count-semantics fact for
    `analysis/count_semantics.py`, proven on every Corpus Christi statement.
  - `bank_ozk_plus_less_summary` (n=8; verified 5-6, bimodal). No wordmark;
    identity is the ozk.com/disclosures sentence + the product banner
    `<PRODUCT>* ACCOUNT - <acct>` + `FDCS BKOZ` descriptors. Direction in
    `OTHER TRANSACTIONS` is carried ONLY by which of two unlabelled columns a
    figure sits in, and the text layer flattens both - AFFIRMATIVELY
    misleading locally; the printed counts and totals disambiguate it
    (§SCANNEXT's per-day subset-sum discipline: exactly one solution or
    refuse).

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave8-frostozk` - Worktree:
  `.claude/worktrees/mt8-frostozk`. Own: two new registrations (names
  yours), registry entries, tests, the count-semantics entry for Frost, W3
  log (#FROSTOZK). `analysis/balance_by_date.py` (the BALANCE BY DATE
  issue) must stay byte-identical - replay it.

# Expected archive movement
Up to 17 failed → validated (verified 8-9 + 5-6), named; zero elsewhere.

# Report
Both populations; the Frost count-semantics proof; the OZK direction solve
and its refusals; hunks; mutation table; probe; sweep; proofs with exit
codes; privacy grep count; commits; risks.

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
