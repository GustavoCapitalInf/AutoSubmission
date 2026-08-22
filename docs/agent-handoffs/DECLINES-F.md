# Agent Handoff - DECLINES-F (batch 7, card 6 - bmo_ca_business + capital_one + first_citizens, with the DACO2 scanned sibling)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** DECLINES-F - three digital decline groups with one module
  each, plus the scanned cohort adjacent to one of them:
  `bmo_ca_business` (6: `bmo_ca_business.py:262` - the account-row reader
  returns None), `capital_one` (6: `capital_one.py:394` x5 - no
  transactions or no balances after the native read; `:201` x1),
  `first_citizens` (4 digital: `first_citizens.py:317` - the control/bare/
  days/signed shape test) and the SN3 #9 scanned family `fc_daco2` (3
  documents, 18k-35k chars, `Central Bank Operations - DACO2`; "adjacent to
  the shipped first_citizens reader; settle sibling/supersedes before
  registering").

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-declinesf` -
  Worktree: `.claude/worktrees/mt7-declinesf`. Own: analysis/bmo_ca_business.py,
  analysis/capital_one.py, analysis/first_citizens.py (+ ONE new scanned
  registration only if DACO2 is proven a sibling rather than an extension;
  registry pins in the same commit, conformance 75 x 74), their tests, W3
  log (#DECLINESF). CURRENCY-SOURCE edits the currency-assignment line of
  bmo_ca_business.py (:351) in parallel - do not touch that line. Pinned
  documents: `capital_one` publishes 4 of the 109 and `first_citizens` 1 -
  byte-identical before/after.

# The work
1. The census, live, per registration (DECLINES-D's D2 shape): claimed
   documents, outcomes, refusal site + printed fact per decline. For the
   DACO2 three: the SCAN-NEXT SN2/SN3 method - read the cached OCR text by
   direct path; does a ledger survive the scan at all; is the template the
   first_citizens layout (extension) or a different printing (sibling)?
2. Widen only behind in-document oracles (printed totals, counts, daily
   balances closing to the cent). Fabricated rows and hallucinated values
   are the class killers on the scanned three - say what the oracle refuses.
3. bmo_ca_business is a CAD reader (institution default) - currency
   behaviour unchanged here; capital_one's cycle-date normalization and
   first_citizens' three-figure control shape are documented design
   decisions in their modules - read their W3 history before widening.
4. Mutation table; fixtures; full-family replay per registration.

# Expected archive movement
Ceiling 19 (6 + 6 + 4 + 3) failed -> validated, realistically fewer; every
mover named; zero movement outside the claimed families; the 5 pinned
documents byte-identical.

# Report
Census tables; per-site diagnosis; the DACO2 sibling/extension ruling with
evidence; hunks verbatim; mutation table; family replays; the sweep; proofs
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
