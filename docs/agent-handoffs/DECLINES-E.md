# Agent Handoff - DECLINES-E (batch 7, card 5 - huntington + chase: readers that memorized a shape their bank prints wider)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** DECLINES-E - the two largest digital decline groups outside
  the core-processor complex (which is frozen until DESC-ATTRIB lands):
  `huntington` (12 declines: `huntington.py:681` x8 - `_validate` refuses
  after the ledger is read; `:662` x4 - the line-of-credit refusal) and
  `chase` (4: `chase.py:716` x3, `:595` x1). DECLINES-D's discipline is the
  model (W3 §DECLINESD D2-D6): census by refusal site first, widen only
  where an in-document arithmetic oracle gates the widening, and say what
  is NOT taken and why.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-declinese` -
  Worktree: `.claude/worktrees/mt7-declinese`. Own: analysis/huntington.py,
  analysis/chase.py, their tests, W3 log (#DECLINESE). No registration, no
  detection-marker change (conformance must stay at 74 x 73). Pinned
  documents: `chase` publishes 11 of the 109 - every one byte-identical
  before/after; `huntington` publishes none.

# The work
1. The census, live: every document each registration CLAIMS (detection
   replay, not rows.csv), its outcome, and for each decline the refusal
   site and the printed fact that defeats it. Rank by (population x
   fix-confidence).
2. `huntington.py:681` (8): `_validate(summary, txns, fee_txns,
   service_net, balances)` refuses after the ledger is read - find which
   identity fails on each document and whether the reader or the document
   is wrong. A widening is allowed only where the statement's own printed
   identity (summary totals, counts, daily balances) closes to the cent on
   the widened read.
3. `huntington.py:662` (4): a multi-account statement (a line of credit
   beside the deposit account). The refusal is honest under the
   single-account schema (L-1); do NOT publish one account and drop the
   other. Characterize the four (what the second account is, whether the
   deposit account alone reconciles) and report the L-1 ceiling - that is
   a Gustavo architecture question, not a widening.
4. `chase.py:716` (3) and `:595` (1): same discipline.
5. Mutation table for every gate touched; fixtures per printing class;
   full-family replay (every claimed document before/after, movers named,
   non-movers byte-identical).

# Expected archive movement
Ceiling 16 failed/parser_declined -> validated, realistically fewer; every
mover named by sha; zero movement outside the two claimed families; the 11
pinned Chase documents byte-identical.

# Report
The census table; per-site diagnosis; hunks verbatim; the L-1 cohort
characterized; the mutation table; the family replay; the sweep; proofs
with exit codes; commits; risks.

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
