# Agent Handoff - SCAN-FINISH (batch 7, card 8 - southside + citizens: finish the readers that exist)

Ocean reviews and merges; you never merge or push.

# Identity
- **Agent:** SCAN-FINISH - two SN3 families whose readers already exist and
  stop short (W3 §SCANNEXT SN3 rows 3 and 5; §DECLINESD D5.1 for citizens):
  - `southside` (9 scanned `SOUTHSIDE STATEMENT OF ACCOUNT`, PO Box 1079
    Tyler TX): `southside_scanned` (analysis/scanned_small_bank.py) claims 3
    and publishes 2 (`4C96DDA2` review/integrity_flags, `B3110297`
    withheld/withheld_adb) while declining `9D7EB67A` (:281 - the summary
    regex); six are unclaimed, four of which are 1-2 page fragments
    (827-1,688 chars) that are page extracts, not statements. Ceiling <=6,
    honestly fewer.
  - `citizens_rop` (5: `Business Account Statement` / `Commercial Account
    Statement`, ROP, PO Box 7000 Providence RI; 20k-25k chars each):
    `citizens` claims all five - four decline at `citizens.py:66` (the
    summary regex expects `Current Balance` then `Daily Balance` - the
    separator is furniture, and the strip's identity previous - checks -
    debits + deposits = current closes on all four), one (`675EB43935FE`)
    publishes withheld_adb. With the summary alone widened all four land
    withheld_adb with ZERO credits published (credit_coverage 0.000; debit
    coverage 0.80-0.94) - the three causes are in D5.1; the identity is the
    oracle. Ceiling <=5.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-scanfinish` -
  Worktree: `.claude/worktrees/mt7-scanfinish`. Own:
  analysis/scanned_small_bank.py (the southside reader only - `apex_scanned`
  shares the module: byte-identical), analysis/citizens.py, their tests, W3
  log (#SCANFINISH). No new registration. Pinned: `citizens` publishes 4 of
  the 109 and `southside_scanned` 1 - byte-identical before/after.

# The work
1. Census both families live (detection replay + artifact text by direct
   path); per document: does a ledger survive the scan; which gate refuses;
   what the printed identity says.
2. Widen behind the identity and the printed counts; Tesseract-mangled
   printings handled by evidence, never by tolerance; page-declaration
   integrity under the WIRING-2 regime (sheets live in the analysis input
   key). Fragments that are not statements stay failed, named.
3. The ADB doctrine decides withheld vs validated - a document whose daily
   balance evidence does not cover the printed period stays withheld,
   honestly. State the ceiling per document BEFORE implementing.
4. Mutation table; fixtures; family replays.

# Expected archive movement
Ceiling 11, realistically ~6; every mover named with its outcome; zero
movement outside the two families; 5 pinned documents byte-identical.

# Report
Census; per-document ceiling vs result; hunks verbatim; mutation table;
replays; the sweep; proofs with exit codes; commits; risks.

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
