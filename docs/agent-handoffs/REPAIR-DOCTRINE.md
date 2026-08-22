# Agent Handoff - REPAIR-DOCTRINE (batch 7, card 1 - the APPROVED repair ceremony: columbia_bank stops writing amounts)

Ocean reviews and merges; you never merge or push.
**Protected ceremony cell. Pinned-diff discipline; Ocean forensic review at
merge. Gustavo's ruling (2026-08-21) is binding verbatim: "APPROVED. Proceed
with the pinned ceremony. Parsers must never rewrite transaction amounts just
to force reconciliation. Replace repair-by-rewrite with discard-and-flag /
fail-closed. Require exact before/after proof and zero unrelated movement."
Any pinned movement beyond the one you enumerate in your report is a HARD
STOP for the train.**

# Identity
- **Agent:** REPAIR-DOCTRINE - remove the two amount-rewriting repairs from
  `analysis/columbia_bank.py`, replace them with discard-and-flag /
  fail-closed, and execute the resulting pinned-expectation movement on
  `Misc/Columbia May 26 complete.pdf`
  (`0CBD2AD897B90137878F81EF608778735CA0DFEAB23D25793F2C6F1DF6C6127D`,
  pinned today as review / `missing_declared_statement_page`, 108
  transactions, opening 6,291.76, ending 13,904.87, highest 37,211.56,
  lowest 4,831.08, ADB 13,275.65 = the printed Average Balance, USD).

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-repairdoc` -
  Worktree: `.claude/worktrees/mt7-repairdoc`. Own: analysis/columbia_bank.py,
  its tests, the pinned expectations for this ONE document (corpus_gate.py
  `PINNED_OUTCOMES` / `PINNED_CURRENCY` entries if they move; the document's
  rows in docs/adb-audit-results.csv and docs/balance-metrics-audit-results.csv;
  its entry in tests/data/parser_expectations.json), W3 log (#REPAIRDOC).
  Nobody else in batch 7 touches columbia_bank.py or this document's pins.
  Do NOT touch analysis/pipeline.py's repair seam: PIPELINE-5's
  `apply_statement_repairs` boundary guards repairs that RAISE; this card
  removes repairs that REWRITE. Different seam, different card.

# The finding (batch-6 COLUMBIA-5 review, carried; verify every number on the base tree before changing anything)
`_repair_repeated_amounts` (columbia_bank.py:188) replaces a row's amount
with its counterparty group's modal amount whenever that lands the section
nearer its printed total; `_repair_single_section_delta` (:270) rewrites ONE
row's amount by the section's residual and keeps the candidate that best
matches the daily grid. Both run at :536-539 BEFORE the section gates at
:546-560, so the gates test the repair's own objective function. On the
pinned document three published amounts are parser-WRITTEN, not read:
`40,962.30 -> 10,962.30`, `4,500.00 -> 1,500.00`, `3,036.83 -> 3,035.83`.
Separately, the daily evidence publishes
`reconstructed.get(snapshot_date, snapshots[snapshot_date])` (:~598):
parser arithmetic preferred over the bank's printed grid cell, unflagged
(05-20: 7,525.18 published against 7,825.18 printed).

# The work
1. MEASURE FIRST on the unchanged base tree: the columbia_bank family by live
   detection replay (the batch-6 cohort is four documents - the pinned one
   plus three refusals §COLUMBIA5 attributed to OCR corruption the bank's
   own totals catch; re-derive, don't trust). For each: the full published
   payload or the refusal reason. For the pinned one: every row whose
   published amount differs from the figure the OCR text prints (enumerate
   the three and prove there is no fourth), and every `stated_daily_balances`
   entry that differs from the printed grid cell.
2. Remove both rewrite repairs. The doctrine shape: a row is published at
   the figure the text prints, or it is not published. A section whose rows
   do not sum to its printed total either (a) FAILS CLOSED - the reader
   returns None with a named reason, the shape the three refusals already
   take - or (b) publishes the rows as printed with an integrity flag naming
   the disagreement (section + delta; no row invented, no amount changed).
   Choose by evidence and say why; (a) is the default whenever the daily
   grid cannot locate the defect to a single row with certainty. Under NO
   outcome may a published amount differ from a printed figure, and no
   rewrite may survive under another name (a "discard" that drops the row
   AND adjusts a total is a rewrite).
3. `stated_daily_balances`: publish the PRINTED grid cell; where the
   reconstructed balance disagrees with it, FLAG the disagreement (never
   substitute). Unreadable cells (the em-dash placeholder class the module's
   own comment documents) stay omitted.
4. The ceremony: whatever the document publishes after 2-3, enumerate the
   exact before/after on every audited field (verdict, flags, notes, risk,
   transaction count 108 -> N, opening/ending/highest/lowest, the ADB and its
   printed-match status, currency) and update the pinned files in the SAME
   commit as the code. Expected shapes: review -> failed/declined (fail
   closed) or review with new flags; the ADB audit row's status may leave
   PASS. If the document no longer parses, say what the gate audits for it
   (a pinned refusal is a pinned fact - do not delete the document from the
   manifest; the gate must go RED if it ever parses again unannounced).
   Record the diff verbatim in your report BEFORE Ocean reads it at merge.
5. Tests: fixtures for the three rewrite classes proving the amount is NOT
   rewritten (the row publishes the printed figure or the document refuses);
   the grid-vs-reconstruction flag; the mutation table (re-introduce each
   repair -> a named test fails; drop the flag -> a named test fails).

# Expected archive movement
The columbia_bank family only - name every sha. The pinned document moves
exactly as enumerated; the three refusals stay refused (their refusal is on
the bank's totals) or are named. The archive sweep at HEAD must place every
finding inside this family. The other 108 pinned documents byte-identical;
gate GREEN with the updated pins live (state 106/3 or the new split and
why).

# Proof floor (ceremony)
The standing floor, plus: the pinned before/after enumeration; the family
replay with every payload diffed leaf-by-leaf; the full 3,380 sweep with
findings enumerated; the mutation table.

# Report
The pinned diff first; the base-tree measurement; the hunks verbatim; the
family replay; the sweep; the mutation table; proofs with exit codes;
commits; risks.

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
