# Agent Handoff - HYGIENE-8 (batch 8, card 11 - the batch-7 review carries, zero coverage movement)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** HYGIENE-8 - the findings batch 7's reviews carried that move
  no outcome and belong together:
  - SIBLING-OMISSION-SURFACE: a payload-level statement that a deposit
    section existed and was not published, for BOTH idle-sibling
    declarations (`No Transactions This Period` and the yield-only sibling),
    across every parser that makes one (symitar, zions `_inert`,
    community_section's one-account rule, …). Design: a field on the
    Statement (e.g. `unpublished_sibling_sections: list[{label, reason,
    posting_count}]`) + an integrity NOTE (not a verdict-moving flag - say
    why, or make it a flag and name the verdict movers). It moves
    already-validated documents across parsers: name every one; a pinned
    mover is a ceremony → STOP and report.
  - QUEUE-SUPERVISOR: `webapp/app.py:_process_job_queue` never resets
    `_job_worker_active` after a `BaseException` kills the thread; every
    later upload strands at `queued`. A `try/finally` that resets the flag
    and re-raises, plus the drain/re-arm decision; delete the two
    known-limitation tests PRIVACY-3 pinned (their failure messages name
    you).
  - RAISE-PRIVACY-3: the five sites PRIVACY-3 listed in other cells' files
    (chase.py `_money_required`; scanned_small_bank.py `_money`/`_iso`;
    columbia_bank.py's two `strptime`; scotia.py's one) → `money_refusal` /
    `date_refusal` / `parsed_datetime`; extend `CHAIN_GUARDED`; poisoned
    tests; the `OverflowError` contract for the three `date_tokens` helpers
    documented to return None (decide: refuse, with a sweep).
  - EXTRACT-PROMPT: `analysis/extract.py`'s `_INSTRUCTIONS` carry a real
    insurer name and five exact-cent constants (R-1 class) - replace with
    synthetic values, delete `extract.py` from `PATTERN_SCAN_EXEMPT`; the
    LLM branch is unexercised offline, say so.
  - REFUSAL-CLASS: a third discovery refusal class ("claimed layout,
    document fails its own totals") so the pinned Columbia refusal stops
    filing under `unknown_layout_clusters` (`discovery/report.py:191`);
    report + rows.csv + compare must carry it; a full-archive differential.
  - DETECT-BUDGET-GATE: `test_detect_sweep_stays_affordable_for_the_discovery_run`
    asserts `worst × 80 ÷ len(registrations)` with `worst` ~99%
    registry-independent, so it gets EASIER with every registration; make
    it measure the marginal per-registration cost (or the prepared-text
    sweep at a fixed registry) so it can gate growth.
  - CURRENCY-CONTRADICTION: td_can publishes CAD as `institution_default`
    when the page prints TWO different suffixes (rbc refuses the same
    shape); cibc.py:432's `\b([A-Z]{3})\b` accepts any three-cap token as
    `printed`; desjardins' silent arm publishes a USD product name while
    declaring `schema_default`. Decide per site (refuse / narrow the read /
    a seventh vocabulary member), with the pinned surfaces' movement named
    - a pinned class mover is a ceremony → STOP.
  - ZERO-ACTIVITY-MONTH: positive recognition of a zero-activity statement
    (both totals 0.00, beginning == ending, no ledger printed, one daily
    cell) so the quiet month is a measurement, not null gates.
  - CHASE-SAVINGS-MARKER: narrow chase_savings's `excluding("checking_summary",
    …)` to fire only when a SAVINGS SUMMARY is also present; this deletes the
    chase → chase_savings import edge (and its ALLOWED_PRIVATE_IMPORTS
    entries); proof population: the 10 chase_savings documents, the 3
    DECLINES-E movers, the 4 combined statements.
  - ATB-LABEL: `analysis/atb.py:114` hardcodes `account_name="Unlimited
    Business Banking"`; read the product from the `A summary of Deposit
    Account <product>` line (2 archive movers print `Business Self-serve`);
    the 5 pinned print the literal → byte-identical; prove it.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave8-hygiene8` - Worktree:
  `.claude/worktrees/mt8-hygiene8`. Own: webapp/app.py, analysis/extract.py,
  discovery/report.py + compare + runner (REFUSAL-CLASS), the named raise
  sites, analysis/td_can.py + cibc.py + desjardins.py currency sites,
  analysis/chase.py + chase_savings.py, analysis/atb.py, analysis/schema.py
  (the omission field), the sibling-omission sites in symitar.py / zions.py
  / community_section.py, the detect-budget test, tests, W3 log (#HYGIENE8).
  Collisions this batch: WITHHELD-GRIDS owns community_section.py's
  daily-evidence reader and WITHHELD-TD owns td_can.py's balance reader -
  touch ONLY the named lines in those files and say so.

# Expected archive movement
Named per sub-card: SIBLING-OMISSION-SURFACE moves a new field on its named
documents; REFUSAL-CLASS moves report bookkeeping, not outcomes; ATB-LABEL
moves `account_name` on 2 archive documents; everything else zero. Full
sweep at the final tree with every finding attributed to a sub-card.

# Report
Per sub-card: census, hunks, mutation table, movers by sha; the sweep;
proofs; privacy grep count; commits; risks.

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
